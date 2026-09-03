"""Multi-dimensional mutation priority scoring for enzyme engineering.

Implements the 5-dimension scoring framework from mutation_design/SKILL.md:
  1. Surface Exposure (ASA %) — weight 0.20
  2. Sequence spacing from protected catalytic residues — weight 0.25
  3. Evolutionary Conservation (ConSurf score) — weight 0.25
  4. Mutation ΔΔG (kcal/mol) — weight 0.15
  5. Functional Relevance — weight 0.15

Composite Priority = sum(score_i × weight_i), 0-10 scale.
Tier 1: >7.0  |  Tier 2: 5.0-7.0  |  Tier 3: <5.0
"""

from __future__ import annotations

import math

from app.core.database import session_scope
from app.services.lipase_db_status import build_lipase_evidence_context
from app.services.candidate_decision import decide_candidate_output
from app.tools.catalytic_site_lookup import _infer_catalytic_residues
from app.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Residue property tables
# ---------------------------------------------------------------------------

_AA_LIST = list("ACDEFGHIKLMNPQRSTVWY")
_AA_INDEX: dict[str, int] = {aa: i for i, aa in enumerate(_AA_LIST)}

# Kyte-Doolittle hydropathy (proxy for surface exposure likelihood)
_KD: dict[str, float] = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5,
    "E": -3.5, "Q": -3.5, "G": -0.4, "H": -3.2, "I": 4.5,
    "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6,
    "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}

# Side-chain pKa values
_PKA_SIDE: dict[str, float | None] = {
    "D": 3.86, "E": 4.25, "C": 8.33, "Y": 10.0,
    "H": 6.00, "K": 10.53, "R": 12.48,
}

# Residue volumes (Å³)
_AA_VOLUME: dict[str, float] = {
    "A": 88.6, "R": 173.4, "N": 117.7, "D": 111.1, "C": 108.5,
    "Q": 143.9, "E": 138.4, "G": 60.1, "H": 153.2, "I": 166.7,
    "L": 166.7, "K": 168.6, "M": 162.9, "F": 189.9, "P": 122.7,
    "S": 89.0, "T": 116.1, "W": 227.8, "Y": 193.6, "V": 140.0,
}

# Simplified ASA propensity: charged + polar → surface, hydrophobic → buried
# Higher score → higher likelihood of surface exposure
_SURFACE_PROPENSITY: dict[str, float] = {
    "R": 9.0, "K": 8.5, "D": 8.0, "E": 8.0, "N": 7.0, "Q": 7.0,
    "H": 6.5, "S": 6.0, "T": 6.0, "P": 5.5, "G": 5.0,
    "Y": 4.0, "W": 3.5, "M": 3.0, "C": 2.5, "A": 2.0,
    "V": 1.5, "L": 1.0, "I": 1.0, "F": 0.5,
}

# ConSurf-like conservation: frequency-based score from UniProt amino acid distribution
# Higher = more conserved (appears less frequently in nature)
_CONSERVATION_BIAS: dict[str, float] = {
    "W": 9.0, "C": 8.5, "H": 7.5, "M": 7.0, "F": 6.5, "Y": 6.0,
    "P": 5.5, "R": 5.0, "N": 4.5, "Q": 4.5, "D": 4.0, "E": 4.0,
    "G": 3.5, "K": 3.5, "T": 3.0, "S": 2.5, "A": 2.0, "I": 1.5,
    "V": 1.0, "L": 1.0,
}

# Catalytic residue motifs (NEVER mutate these)
_CATALYTIC_MOTIFS: dict[str, list[str]] = {
    "GH13": ["D", "E", "D"],           # α-amylase catalytic triad
    "serine_protease": ["H", "D", "S"],
    "cysteine_protease": ["C", "H", "N"],
    "aspartyl_protease": ["D", "D"],
    "kinase": ["D", "N", "D"],
    "general_acid_base": ["D", "E", "H"],
    "metal_binding": ["H", "C", "D", "E"],
    "disulfide": ["C"],
}

# Known enzyme family active-site motifs (position patterns)
_ACTIVE_SITE_PATTERNS: dict[str, list[dict]] = {
    "GH13_amylase": [
        {"region": "β4 strand", "pattern": "D[AVL][IV][LN]H", "role": "nucleophile"},
        {"region": "β5 strand", "pattern": "G[FY]R[LI][DN]A[AV]K[HN]", "role": "acid/base catalyst"},
        {"region": "β7 strand", "pattern": "F[LI][VA][DN][NH]HD", "role": "transition state stabilizer"},
    ],
}

# Residue categories that MUST NOT be mutated
_NEVER_MUTATE = {
    "catalytic": ["catalytic triad/center residues", 9],
    "metal_binding": ["metal-binding residues (Ca²⁺, Zn²⁺)", 9],
    "disulfide": ["Cys in disulfide bonds", 8],
    "cis_proline": ["cis-Proline residues (structural)", 8],
    "unusual_gly": ["Gly with unusual φ/ψ angles", 7],
    "invariant": ["totally invariant residues across family", 9],
}

# High-value engineering targets
_HIGH_VALUE_TARGETS = {
    "surface_K_R": {"replace": ["E", "D", "Q"], "purpose": "pH lowering", "score_boost": 1.0},
    "surface_G_loop": {"replace": ["P"], "purpose": "thermostability", "score_boost": 1.0},
    "unpaired_C": {"replace": ["A", "S"], "purpose": "remove reactive thiol", "score_boost": 0.5},
    "core_cavity": {"replace": ["I", "L", "V", "F"], "purpose": "fill cavity", "score_boost": 0.5},
    "surface_N_Q": {"replace": ["D", "E"], "purpose": "acid resistance", "score_boost": 0.5},
}

_CLEAR_ENGINEERING_GOALS = {"thermostability", "activity", "specificity", "ph_lowering", "ph_raising"}
_OBJECTIVE_SCORE_SCHEMA_VERSION = "mutation_objective_score_v1"
_OBJECTIVE_SCORE_NAMES = (
    "activity_score",
    "stability_score",
    "specificity_score",
    "ph_profile_score",
    "expression_score",
    "risk_score",
)
_CANDIDATE_TABLE_SCHEMA_VERSION = "candidate_table_generation_v1"


def _terminal_guard_band(seq_len: int) -> int:
    """Return a conservative terminal band where apparent flexibility may be construct noise."""
    return max(30, int(seq_len * 0.10))


def _is_terminal_region(position: int, seq_len: int) -> bool:
    band = _terminal_guard_band(seq_len)
    return position <= band or position > seq_len - band


def _has_clear_engineering_objective(
    engineering_goal: str,
    *,
    target_ph: float | None = None,
    target_tm: float | None = None,
    objective_gate: dict | None = None,
) -> bool:
    """Return whether a low-evidence table is allowed to be exploratory."""
    goal = str(engineering_goal or "").strip().lower()
    if goal in _CLEAR_ENGINEERING_GOALS:
        return True
    if target_ph is not None or target_tm is not None:
        return True
    if isinstance(objective_gate, dict):
        objective = str(objective_gate.get("objective") or objective_gate.get("module") or "").strip().lower()
        if objective and objective not in {"general", "unknown", "unclear", "none", "n/a"}:
            return True
    return False


def _canonical_objective_signal(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"activity", "specific_activity", "catalytic_efficiency", "kcat", "km", "比活", "酶活", "催化效率"}:
        return "activity"
    if text in {"thermostability", "thermal_stability", "heat_stability", "耐热", "热稳定", "热稳定性"}:
        return "thermostability"
    if text in {"specificity", "substrate_specificity", "底物特异性", "底物谱"}:
        return "specificity"
    if text in {"ph_profile", "ph_lowering", "ph_raising", "ph", "optimal_ph"}:
        return "ph_profile"
    if text in {"solubility", "soluble_expression", "expression"}:
        return "solubility"
    return text


def _objective_signal_set(
    engineering_goal: str,
    objective_signals: list[str] | None,
    objective_gate: dict | None,
) -> set[str]:
    signals = {
        _canonical_objective_signal(item)
        for item in (objective_signals or [])
        if str(item or "").strip()
    }
    if engineering_goal:
        signals.add(_canonical_objective_signal(engineering_goal))
    if isinstance(objective_gate, dict):
        gate_signals = objective_gate.get("objective_signals")
        if isinstance(gate_signals, list):
            signals.update(
                _canonical_objective_signal(item)
                for item in gate_signals
                if str(item or "").strip()
            )
        gate_objective = objective_gate.get("objective")
        if gate_objective:
            signals.add(_canonical_objective_signal(str(gate_objective)))
    return {item for item in signals if item}


def _clamp_objective_score(value: float | None) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(max(0.0, min(10.0, float(value))), 1)


def _objective_score_contract(
    *,
    aa: str | None = None,
    asa_score: float | None = None,
    dist_score: float | None = None,
    cons_score: float | None = None,
    func_score: float | None = None,
    min_active_dist: int | None = None,
    is_protected: bool = False,
    target_type: str | None = None,
    structure_feature: dict | None = None,
    risk_flags: list[str] | None = None,
    profile_ready: bool,
    objective_candidate_table_status: str,
    objective_signal_set: set[str],
    engineering_goal: str,
    target_ph: float | None = None,
) -> dict:
    """Build the additive P2-2 contract without changing legacy ranking.

    Scores are deliberately component-local and traceable to existing residue
    features.  Missing objective-specific evidence stays unknown instead of
    receiving a neutral score.  The contract can therefore block a candidate
    while legacy composite/tier output remains available for compatibility.
    """
    feature = structure_feature if isinstance(structure_feature, dict) else {}
    risks = [str(item) for item in (risk_flags or []) if str(item).strip()]
    active_objectives = {
        item for item in objective_signal_set
        if item not in {"general", "unknown", "unclear", "none"}
    }
    if engineering_goal and engineering_goal != "general":
        active_objectives.add(_canonical_objective_signal(engineering_goal))

    components: dict[str, dict] = {}

    def _component(
        name: str,
        score: float | None,
        *,
        status: str,
        source: list[str],
        rationale: str,
    ) -> None:
        components[name] = {
            "score": _clamp_objective_score(score),
            "status": status,
            "source": source,
            "rationale": rationale,
        }

    # Existing functional relevance is the only local activity proxy currently
    # available; it is explicitly marked as a computational hypothesis.
    _component(
        "activity_score",
        func_score,
        status="hypothesis" if func_score is not None else "unknown",
        source=["mutation_priority_score.scores.functional_relevance"],
        rationale="位点功能相关性启发式；不能替代比活力、kcat/Km 或蛋白归一化 assay。",
    )

    stability_score = None
    stability_source = ["mutation_priority_score.residue_features"]
    stability_rationale = "缺少可追溯的结构/ddG 稳定性特征，保持 unknown。"
    if asa_score is not None and dist_score is not None and cons_score is not None:
        stability_score = 0.40 * asa_score + 0.35 * dist_score + 0.25 * (10.0 - cons_score)
        if aa == "G":
            stability_score -= 1.0
        if aa == "C":
            stability_score -= 1.0
        if target_type == "core_cavity":
            stability_score -= 1.0
        stability_source = [
            "mutation_priority_score.scores.surface_exposure",
            "mutation_priority_score.scores.active_site_distance",
            "mutation_priority_score.scores.conservation_mutability",
        ]
        stability_rationale = "基于暴露度、保护位点距离和保守性构成的结构筛选假设；不能替代 ddG/Tm/半衰期 assay。"
    _component(
        "stability_score",
        stability_score,
        status="hypothesis" if stability_score is not None else "unknown",
        source=stability_source,
        rationale=stability_rationale,
    )

    pocket_status = str(feature.get("pocket_channel_interface_status") or "")
    specificity_score = None
    specificity_status = "unknown"
    specificity_source = ["site_structure_features.pocket_channel_interface_status"]
    specificity_rationale = "缺少已计算的目标/非目标底物口袋或选择性特征，保持 unknown。"
    if pocket_status in {"computed", "computed_from_input_pdb", "verified"}:
        specificity_score = _clamp_objective_score(func_score)
        specificity_status = "hypothesis" if specificity_score is not None else "unknown"
        specificity_rationale = "仅使用结构口袋/通道特征与功能相关性作筛选假设；必须并行目标/非目标底物 assay。"
    _component(
        "specificity_score",
        specificity_score,
        status=specificity_status,
        source=specificity_source,
        rationale=specificity_rationale,
    )

    ph_score = None
    ph_status = "unknown"
    ph_source = ["mutation_priority_score.scores.surface_exposure", "mutation_priority_score.sequence_residue"]
    ph_rationale = "缺少 pH-activity 曲线或可验证 pKa 特征，保持 unknown。"
    if target_ph is not None or "ph_profile" in active_objectives:
        if aa in {"D", "E", "H", "K", "R", "C", "Y"} and asa_score is not None:
            ph_score = asa_score
            ph_status = "hypothesis"
            ph_rationale = "基于可滴定侧链和暴露度的 pH 方向筛选假设；不能声称最适 pH 已改变。"
    _component("ph_profile_score", ph_score, status=ph_status, source=ph_source, rationale=ph_rationale)

    expression_score = None
    expression_status = "unknown"
    expression_source = ["mutation_priority_score.sequence_residue", "mutation_priority_score.construct_boundary"]
    expression_rationale = "缺少宿主、构建边界、可溶产量和聚集实测，保持 unknown。"
    if asa_score is not None and aa is not None:
        expression_score = 5.0 + (asa_score - 5.0) * 0.35
        if aa in {"I", "L", "V", "F", "W"}:
            expression_score -= 1.0
        if target_type == "core_cavity":
            expression_score -= 1.0
        expression_status = "hypothesis"
        expression_rationale = "仅为序列暴露/疏水和构建边界启发式；不能替代表达、可溶性或聚集 assay。"
    _component(
        "expression_score",
        expression_score,
        status=expression_status,
        source=expression_source,
        rationale=expression_rationale,
    )

    risk_score = 0.0
    risk_source = ["mutation_priority_score.risk_flags", "mutation_priority_score.guardrails"]
    if is_protected:
        risk_score = 10.0
    elif min_active_dist is not None and min_active_dist <= 4:
        risk_score = max(risk_score, 7.0)
    if aa == "C":
        risk_score = max(risk_score, 7.0)
    if aa == "G" and "thermostability" in active_objectives:
        risk_score = max(risk_score, 6.0)
    if target_type == "core_cavity":
        risk_score = max(risk_score, 6.0)
    if not profile_ready:
        risk_score = max(risk_score, 9.0)
    if objective_candidate_table_status != "ready":
        risk_score = max(risk_score, 7.0)
    if risks:
        risk_score = max(risk_score, min(10.0, 4.0 + len(risks) * 0.5))
    _component(
        "risk_score",
        risk_score,
        status="computed",
        source=risk_source,
        rationale="风险分越高越接近保护位点、证据缺口或结构/构建风险；不是收益分。",
    )

    blocking_reason: list[str] = []
    if is_protected:
        blocking_reason.append("protected_catalytic_or_functional_position")
    if not profile_ready:
        blocking_reason.append("identity_or_numbering_gate_not_ready")
    if objective_candidate_table_status != "ready":
        blocking_reason.append("objective_assay_or_wt_baseline_missing")
    if risk_score >= 7.0 and "high_risk_residue_or_evidence_gap" not in blocking_reason:
        blocking_reason.append("high_risk_residue_or_evidence_gap")
    required_by_objective = {
        "activity": ["specific_activity_or_kcat_km_assay", "protein_normalized_wt_control"],
        "thermostability": ["tm_or_thermal_half_life_assay", "residual_activity_after_heat_challenge"],
        "specificity": ["target_and_off_target_substrate_kinetics"],
        "ph_profile": ["full_ph_activity_curve", "ph_stability_residual_activity"],
        "solubility": ["soluble_yield_purity_and_aggregation_assay", "activity_after_expression_qc"],
        "expression": ["soluble_yield_purity_and_aggregation_assay", "activity_after_expression_qc"],
    }
    assay_required: list[str] = []
    for objective in sorted(active_objectives):
        for assay in required_by_objective.get(objective, []):
            if assay not in assay_required:
                assay_required.append(assay)
    for component_name in _OBJECTIVE_SCORE_NAMES:
        if components[component_name]["status"] == "unknown":
            blocking_reason.append(f"{component_name}_unknown")
    if not active_objectives:
        blocking_reason.append("engineering_objective_unknown")
    blocking_reason = list(dict.fromkeys(blocking_reason))

    return {
        "schema_version": _OBJECTIVE_SCORE_SCHEMA_VERSION,
        "activity_score": components["activity_score"]["score"],
        "stability_score": components["stability_score"]["score"],
        "specificity_score": components["specificity_score"]["score"],
        "ph_profile_score": components["ph_profile_score"]["score"],
        "expression_score": components["expression_score"]["score"],
        "risk_score": components["risk_score"]["score"],
        "score_components": components,
        "confidence_level": "blocked" if blocking_reason else "low",
        "evidence_level": "blocked" if blocking_reason else "computational_hypothesis",
        "assay_required": assay_required,
        "blocking_reason": blocking_reason,
        "decision": "blocked" if blocking_reason else "review_only",
        "no_composite_score": True,
    }


def _candidate_status_for_row(
    row: dict,
    *,
    candidate_table_status: str,
    exploratory: bool = False,
) -> str:
    if candidate_table_status == "blocked_by_identity_gate":
        return "blocked"
    if row.get("is_protected") is True or row.get("experiment_priority") == "No-Go":
        return "blocked"
    objective_score = row.get("objective_score") if isinstance(row.get("objective_score"), dict) else {}
    blocking_reasons = objective_score.get("blocking_reason")
    if not isinstance(blocking_reasons, list):
        blocking_reasons = []
    if any(str(reason).startswith("protected_") for reason in blocking_reasons):
        return "blocked"
    if exploratory or candidate_table_status != "ready":
        return "exploratory"
    if str(objective_score.get("decision") or "").strip().lower() == "blocked":
        return "exploratory"
    return "high_confidence"


def _is_experiment_design_schedulable(row: dict) -> bool:
    if row.get("is_protected") is True:
        return False
    if row.get("experiment_priority") == "No-Go":
        return False
    if row.get("candidate_status") == "blocked":
        return False
    recommended = row.get("recommended_mutations")
    return bool(recommended)


def _feature_completeness_contract(structure_feature: dict | None) -> dict:
    if not isinstance(structure_feature, dict):
        return {
            "schema_version": "candidate_feature_completeness_v1",
            "status": "missing",
            "available_features": [],
            "missing_feature_reasons": ["residue_feature_table_not_provided_for_position"],
            "evidence_level": "not_available",
            "no_wet_lab_claim": True,
        }

    available: list[str] = []
    missing: list[str] = []

    def _record(name: str, ready: bool, missing_reason: str) -> None:
        (available if ready else missing).append(name if ready else missing_reason)

    _record(
        "ca_geometry",
        bool(structure_feature.get("ca_coordinate") or structure_feature.get("nearest_ca_neighbor_distance_angstrom") is not None),
        "ca_geometry_missing",
    )
    _record(
        "secondary_structure",
        bool(structure_feature.get("secondary_structure")),
        "secondary_structure_missing",
    )
    _record(
        "rel_sasa",
        structure_feature.get("rel_sasa_status") == "computed_from_input_pdb",
        "rel_sasa_not_computed",
    )
    _record(
        "pocket_channel_interface",
        str(structure_feature.get("pocket_channel_interface_status") or "").startswith("computed"),
        "pocket_channel_interface_not_computed",
    )
    _record(
        "nonpolymer_proximity",
        structure_feature.get("nonpolymer_proximity_status") in {"computed_from_input_pdb", "computed"},
        "nonpolymer_proximity_not_computed",
    )
    _record(
        "backbone_torsion",
        structure_feature.get("backbone_torsion_status") in {"computed_from_input_pdb", "computed"},
        "backbone_torsion_not_computed",
    )
    _record(
        "conservation",
        structure_feature.get("conservation_status") in {"computed", "available"},
        "conservation_not_available",
    )
    _record(
        "ddg_or_packing",
        structure_feature.get("ddg_status") in {"computed", "available"} or structure_feature.get("packing_status") in {"computed", "available"},
        "ddg_or_packing_not_available",
    )
    _record(
        "md_rmsf",
        structure_feature.get("md_rmsf_status") in {"computed", "available"},
        "md_rmsf_not_available",
    )

    status = "complete" if not missing else "partial" if available else "missing"
    return {
        "schema_version": "candidate_feature_completeness_v1",
        "status": status,
        "available_features": available,
        "missing_feature_reasons": missing,
        "available_feature_count": len(available),
        "missing_feature_count": len(missing),
        "evidence_level": "computed_structure_features_partial" if available else "not_available",
        "no_wet_lab_claim": True,
    }


def _p2_candidate_readiness_summary(
    *,
    results: list[dict],
    tier1_output: list[dict],
    tier2_output: list[dict],
    candidate_table_status: str,
) -> dict:
    report_rows = list(tier1_output) + list(tier2_output)
    summary_rows = report_rows if report_rows else [
        row for row in results if row.get("is_protected") is not True
    ]
    completeness_status_counts: dict[str, int] = {}
    missing_reason_counts: dict[str, int] = {}
    available_feature_counts: dict[str, int] = {}
    candidate_status_counts: dict[str, int] = {}

    for row in summary_rows:
        candidate_status = str(row.get("candidate_status") or "exploratory")
        candidate_status_counts[candidate_status] = candidate_status_counts.get(candidate_status, 0) + 1

        completeness = row.get("feature_completeness")
        if not isinstance(completeness, dict):
            completeness = _feature_completeness_contract(None)
        status = str(completeness.get("status") or "missing")
        completeness_status_counts[status] = completeness_status_counts.get(status, 0) + 1
        for feature in completeness.get("available_features") or []:
            key = str(feature)
            available_feature_counts[key] = available_feature_counts.get(key, 0) + 1
        for reason in completeness.get("missing_feature_reasons") or []:
            key = str(reason)
            missing_reason_counts[key] = missing_reason_counts.get(key, 0) + 1

    if candidate_table_status == "blocked_by_identity_gate":
        status = "blocked"
    elif not summary_rows:
        status = "no_candidate_rows"
    elif missing_reason_counts:
        status = "partial"
    else:
        status = "complete"

    return {
        "schema_version": "p2_candidate_readiness_summary_v1",
        "status": status,
        "candidate_table_status": candidate_table_status,
        "candidate_row_scope": "reported_candidates" if report_rows else "non_protected_all_positions",
        "reported_candidate_count": len(report_rows),
        "all_position_count": len(results),
        "feature_completeness_status_counts": completeness_status_counts,
        "candidate_status_counts": candidate_status_counts,
        "available_feature_counts": dict(sorted(available_feature_counts.items())),
        "missing_feature_reason_counts": dict(sorted(missing_reason_counts.items())),
        "top_missing_feature_reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                missing_reason_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:8]
        ],
        "report_action": (
            "show_missing_p2_evidence_before_candidate_claims"
            if missing_reason_counts else "candidate_feature_coverage_complete_for_reported_rows"
        ),
        "must_not_claim": [
            "complete_residue_feature_table_when_missing_reasons_exist",
            "pocket_channel_interface_computed_without_explicit_status",
            "conservation_ddg_or_md_evidence_when_missing",
            "wet_lab_validated_candidate_from_completeness_summary",
        ],
    }


def _p2_objective_score_readiness_summary(*, results: list[dict]) -> dict:
    component_status_counts: dict[str, dict[str, int]] = {
        name: {} for name in _OBJECTIVE_SCORE_NAMES
    }
    unknown_component_counts: dict[str, int] = {}
    assay_required_counts: dict[str, int] = {}
    blocking_reason_counts: dict[str, int] = {}
    objective_row_count = 0

    for row in results:
        objective_score = row.get("objective_score")
        if not isinstance(objective_score, dict):
            continue
        if objective_score.get("schema_version") != _OBJECTIVE_SCORE_SCHEMA_VERSION:
            continue
        objective_row_count += 1
        components = objective_score.get("score_components")
        if not isinstance(components, dict):
            components = {}
        for component_name in _OBJECTIVE_SCORE_NAMES:
            component = components.get(component_name)
            status = "missing"
            if isinstance(component, dict):
                status = str(component.get("status") or "unknown")
            component_counts = component_status_counts.setdefault(component_name, {})
            component_counts[status] = component_counts.get(status, 0) + 1
            if status in {"unknown", "missing"}:
                unknown_component_counts[component_name] = unknown_component_counts.get(component_name, 0) + 1
        for assay in objective_score.get("assay_required") or []:
            key = str(assay)
            assay_required_counts[key] = assay_required_counts.get(key, 0) + 1
        for reason in objective_score.get("blocking_reason") or []:
            key = str(reason)
            blocking_reason_counts[key] = blocking_reason_counts.get(key, 0) + 1

    if objective_row_count == 0:
        status = "missing"
    elif unknown_component_counts or blocking_reason_counts:
        status = "partial"
    else:
        status = "complete"

    return {
        "schema_version": "p2_objective_score_readiness_summary_v1",
        "status": status,
        "objective_row_count": objective_row_count,
        "component_status_counts": component_status_counts,
        "unknown_component_counts": dict(sorted(unknown_component_counts.items())),
        "top_unknown_components": [
            {"component": component, "count": count}
            for component, count in sorted(
                unknown_component_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
        "assay_required_counts": dict(sorted(assay_required_counts.items())),
        "blocking_reason_counts": dict(sorted(blocking_reason_counts.items())),
        "top_blocking_reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                blocking_reason_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:8]
        ],
        "aggregation": "none",
        "no_composite_score": True,
        "report_action": (
            "show_unknown_objective_components_before_candidate_claims"
            if unknown_component_counts else "objective_components_available_for_reported_rows"
        ),
        "must_not_claim": [
            "single_total_objective_score",
            "unknown_objective_component_as_neutral_score",
            "measured_activity_stability_specificity_ph_or_expression_without_assay",
        ],
    }


def _p2_structure_feature_gap_summary(*, results: list[dict]) -> dict:
    completeness_status_counts: dict[str, int] = {}
    missing_reason_counts: dict[str, int] = {}
    available_feature_counts: dict[str, int] = {}
    row_count = 0

    for row in results:
        completeness = row.get("feature_completeness")
        if not isinstance(completeness, dict):
            continue
        if completeness.get("schema_version") != "candidate_feature_completeness_v1":
            continue
        row_count += 1
        status = str(completeness.get("status") or "missing")
        completeness_status_counts[status] = completeness_status_counts.get(status, 0) + 1
        for feature in completeness.get("available_features") or []:
            key = str(feature)
            available_feature_counts[key] = available_feature_counts.get(key, 0) + 1
        for reason in completeness.get("missing_feature_reasons") or []:
            key = str(reason)
            missing_reason_counts[key] = missing_reason_counts.get(key, 0) + 1

    if row_count == 0:
        status = "missing"
    elif missing_reason_counts:
        status = "partial"
    else:
        status = "complete"

    return {
        "schema_version": "p2_structure_feature_gap_summary_v1",
        "status": status,
        "row_count": row_count,
        "feature_completeness_status_counts": completeness_status_counts,
        "available_feature_counts": dict(sorted(available_feature_counts.items())),
        "missing_feature_reason_counts": dict(sorted(missing_reason_counts.items())),
        "top_missing_feature_reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                missing_reason_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:8]
        ],
        "report_action": (
            "show_structure_feature_gap_summary_beside_candidate_rows"
            if missing_reason_counts else "structure_feature_coverage_complete_for_reported_rows"
        ),
        "must_not_claim": [
            "pocket_channel_interface_computed_without_explicit_status",
            "conservation_ddg_or_md_evidence_when_missing",
            "wet_lab_validated_candidate_from_structure_gap_summary",
        ],
    }


def _p2_objective_assay_gap_summary(
    *,
    results: list[dict],
    calibration_context: dict | None,
) -> dict:
    objective_row_count = 0
    assay_required_counts: dict[str, int] = {}
    blocking_reason_counts: dict[str, int] = {}

    for row in results:
        objective_score = row.get("objective_score")
        if not isinstance(objective_score, dict):
            continue
        if objective_score.get("schema_version") != _OBJECTIVE_SCORE_SCHEMA_VERSION:
            continue
        objective_row_count += 1
        for assay in objective_score.get("assay_required") or []:
            key = str(assay)
            assay_required_counts[key] = assay_required_counts.get(key, 0) + 1
        for reason in objective_score.get("blocking_reason") or []:
            key = str(reason)
            blocking_reason_counts[key] = blocking_reason_counts.get(key, 0) + 1

    feedback_context = calibration_context or {}
    feedback_status = "not_provided"
    if feedback_context:
        feedback_status = str(feedback_context.get("evidence_level") or "computational_hypothesis")
    if objective_row_count == 0:
        status = "missing"
    elif assay_required_counts or blocking_reason_counts or feedback_status == "not_provided":
        status = "partial"
    else:
        status = "complete"

    return {
        "schema_version": "p2_objective_assay_gap_summary_v1",
        "status": status,
        "objective_row_count": objective_row_count,
        "assay_required_counts": dict(sorted(assay_required_counts.items())),
        "top_assay_gaps": [
            {"assay": assay, "count": count}
            for assay, count in sorted(
                assay_required_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:8]
        ],
        "blocking_reason_counts": dict(sorted(blocking_reason_counts.items())),
        "top_blocking_reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                blocking_reason_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:8]
        ],
        "project_feedback_readiness": {
            "status": feedback_status,
            "evidence_level": feedback_context.get("evidence_level") or "unknown",
            "data_quality_grade": feedback_context.get("data_quality_grade") or "unknown",
            "measured_variant_count": feedback_context.get("measured_variant_count") or 0,
            "hit_rate": feedback_context.get("hit_rate"),
            "objective": feedback_context.get("objective"),
            "assay_key": feedback_context.get("assay_key"),
            "dataset_fingerprint": feedback_context.get("dataset_fingerprint"),
            "boundary": feedback_context.get("boundary")
            or "Project feedback can calibrate ranking context, but each candidate still requires direct wet-lab validation.",
        },
        "report_action": "show_objective_assay_gaps_beside_project_feedback_readiness",
        "must_not_claim": [
            "objective_improvement_without_matched_assay",
            "unknown_objective_component_as_neutral_score",
            "wet_lab_validated_candidate_from_assay_gap_summary",
        ],
    }


def _candidate_table_generation_contract(
    *,
    candidate_table_status: str,
    identity_gate: dict,
    objective_gate: dict,
    results: list[dict],
    tier1_output: list[dict],
    tier2_output: list[dict],
    experiment_output: list[dict],
    site_structure_features: list[dict] | None,
) -> dict:
    statuses: dict[str, int] = {"high_confidence": 0, "exploratory": 0, "blocked": 0}
    for row in results:
        status = str(row.get("candidate_status") or "exploratory")
        statuses[status] = statuses.get(status, 0) + 1
    blocked_excluded = [
        row for row in (tier1_output + tier2_output)
        if not _is_experiment_design_schedulable(row)
    ]

    return {
        "schema_version": _CANDIDATE_TABLE_SCHEMA_VERSION,
        "status": candidate_table_status,
        "input_contracts": {
            "residue_feature_table": (
                "site_structure_function_features_v1"
                if isinstance(site_structure_features, list) and site_structure_features
                else "not_provided"
            ),
            "objective_score": _OBJECTIVE_SCORE_SCHEMA_VERSION,
            "identity_gate_status": identity_gate.get("status"),
            "objective_gate_status": objective_gate.get("status"),
        },
        "selection_policy": {
            "legacy_rank_reused": True,
            "legacy_rank_fields": ["composite_priority", "tier"],
            "objective_score_used_for_status": True,
            "aggregation": "none",
            "no_wet_lab_claim": True,
        },
        "experiment_design_policy": {
            "schema_version": "experiment_design_schedulability_policy_v1",
            "excluded_candidate_statuses": ["blocked"],
            "excluded_priorities": ["No-Go"],
            "requires_recommended_mutation": True,
            "blocked_rows_excluded_count": len(blocked_excluded),
            "blocked_rows_remain_traceable": "all_positions",
            "no_wet_lab_claim": True,
        },
        "output_groups": statuses,
        "output_counts": {
            "tier_1_candidates": len(tier1_output),
            "tier_2_candidates": len(tier2_output),
            "experiment_design_table": len(experiment_output),
        },
        "row_contract": {
            "required_fields": [
                "position",
                "wild_type",
                "recommended_mutations",
                "objective_score",
                "candidate_status",
                "risk_flags",
                "experiment_action",
            ],
            "status_values": ["high_confidence", "exploratory", "blocked"],
            "blocked_policy": "blocked rows remain traceable in all_positions but are not promoted to bench candidate groups",
        },
        "boundary": (
            "Candidate table rows are generated from existing residue rows plus objective_score. "
            "This contract does not introduce a new total score, relax identity/objective gates, "
            "or convert computational hypotheses into wet-lab-supported claims."
        ),
    }


def _p2_engineering_scorecard_contract(
    *,
    candidate_table_status: str,
    identity_gate: dict,
    objective_gate: dict,
    results: list[dict],
    site_structure_features: list[dict] | None,
) -> dict:
    residue_feature_ready = isinstance(site_structure_features, list) and bool(site_structure_features)
    objective_rows = [
        row for row in results
        if isinstance(row.get("objective_score"), dict)
        and row["objective_score"].get("schema_version") == _OBJECTIVE_SCORE_SCHEMA_VERSION
    ]
    candidate_statuses = {
        str(row.get("candidate_status") or "exploratory")
        for row in results
    }
    blockers: list[str] = []
    if not residue_feature_ready:
        blockers.append("residue_feature_table_not_provided")
    if not objective_rows:
        blockers.append("objective_score_rows_missing")
    if candidate_table_status != "ready":
        blockers.append(f"candidate_table_status_{candidate_table_status}")
    if identity_gate.get("status") != "passed":
        blockers.append("identity_gate_not_passed")
    if objective_gate.get("status") not in {None, "ready", "exploratory_allowed"}:
        blockers.append("objective_gate_not_ready")

    status = "ready" if not blockers else "partial"
    return {
        "schema_version": "p2_engineering_scorecard_contract_v1",
        "status": status,
        "input_contracts": {
            "residue_feature_table": "site_structure_function_features_v1" if residue_feature_ready else "missing",
            "objective_score": _OBJECTIVE_SCORE_SCHEMA_VERSION if objective_rows else "missing",
            "candidate_table_generation": _CANDIDATE_TABLE_SCHEMA_VERSION,
        },
        "component_status": {
            "residue_feature_table": "ready" if residue_feature_ready else "missing",
            "objective_score_rows": "ready" if objective_rows else "missing",
            "candidate_table": candidate_table_status,
            "identity_gate": identity_gate.get("status"),
            "objective_gate": objective_gate.get("status"),
        },
        "candidate_statuses": sorted(candidate_statuses),
        "blocked_reasons": blockers,
        "report_action": "allow_p2_candidate_table_with_boundaries" if status == "ready" else "show_p2_partial_contract_and_required_inputs",
        "must_not_claim": [
            "single_total_objective_score",
            "wet_lab_validated_improvement",
            "candidate_reason_without_residue_feature_or_objective_component",
        ],
        "upgrade_requires": [
            "verified residue feature table for reported structural claims",
            "objective-specific assay and WT baseline evidence before improvement claims",
            "candidate_status gate before bench promotion",
        ],
    }


def _exploratory_mutation_options(
    aa: str,
    pos: int,
    engineering_goal: str,
    *,
    surface_score: float,
    dist_score: float,
) -> list[dict]:
    """Small, goal-aware fallback substitutions for exploratory first-round screening."""
    goal = str(engineering_goal or "general")
    options: list[dict] = []

    def _add(target: str, mutation_type: str, purpose: str) -> None:
        if target != aa and not any(item["mutation"].endswith(target) for item in options):
            options.append({"mutation": f"{aa}{pos}{target}", "type": mutation_type, "purpose": purpose})

    if goal == "thermostability":
        if aa == "M":
            _add("L", "氧化敏感位点探索", "M→L 保持疏水体积并降低硫醚氧化敏感性；仅作为首轮计算假设。")
        elif aa in {"S", "T", "N", "Q"} and surface_score >= 5.0:
            _add("A", "表面柔性/去酰胺风险探索", f"{aa}→A 用于测试表面极性侧链对局部柔性或降解风险的影响。")
        elif aa in {"A", "V"} and surface_score <= 4.0:
            _add("I" if aa == "V" else "V", "核心packing探索", f"{aa} 位于较低暴露区域，可用小幅体积增加测试 packing 改善。")
    elif goal in {"activity", "specificity"}:
        mutation_type = "口袋/通道微环境探索" if goal == "specificity" else "催化二壳层微环境探索"
        if aa in {"S", "T"}:
            _add("A", mutation_type, f"{aa}→A 用于测试极性羟基对底物进入、局部水网络或构象柔性的贡献。")
        elif aa in {"N", "Q"}:
            _add("D" if aa == "N" else "E", mutation_type, f"{aa}→{'D' if aa == 'N' else 'E'} 用于测试局部氢键/电荷环境对活性或选择性的影响。")
        elif aa in {"D", "E"}:
            _add("N" if aa == "D" else "Q", mutation_type, f"{aa}→{'N' if aa == 'D' else 'Q'} 中和负电荷，探索底物通道或二壳层电性贡献。")
        elif aa in {"K", "R"}:
            _add("Q", mutation_type, f"{aa}→Q 温和降低正电荷，探索局部电性对底物进入或催化效率的影响。")
        elif aa == "H" and dist_score >= 3.0:
            _add("N", mutation_type, "H→N 用于测试 pH 敏感侧链对局部催化微环境的影响。")
        elif aa in {"M", "L", "I", "V", "F", "Y", "W"}:
            _add("A", mutation_type, f"{aa}→A 小幅削减疏水/体积效应，探索底物通道空间约束。")
    elif goal == "ph_lowering" and aa in {"K", "R", "H"}:
        _add("Q" if aa in {"K", "R"} else "N", "pH 电荷探索", f"{aa} 位点可用于测试局部正电荷或 pH 敏感侧链对酸性条件的影响。")
    elif goal == "ph_raising" and aa in {"D", "E", "H"}:
        _add("Q" if aa in {"D", "E"} else "K", "pH 电荷探索", f"{aa} 位点可用于测试局部负电荷或 pH 敏感侧链对碱性条件的影响。")

    return options[:2]


def _score_surface_exposure(aa: str, position: int, seq_len: int) -> tuple[float, str]:
    """Score surface exposure likelihood (0-10).

    Uses hydropathy + charge + positional heuristics.
    N/C-terminal bias: first and last 10% of sequence are more likely exposed.
    """
    base = _SURFACE_PROPENSITY.get(aa, 5.0)

    # N/C-terminal boost (termini tend to be surface-exposed)
    if position <= max(3, seq_len * 0.1):
        base = min(10, base + 2.0)
    elif position >= seq_len - max(2, int(seq_len * 0.1)):
        base = min(10, base + 1.5)

    # Charged residues are almost always surface
    if aa in ("R", "K", "D", "E"):
        base = max(base, 8.0)

    # Very hydrophobic → likely buried
    if aa in ("I", "L", "V", "F", "W") and not (position <= 5 or position >= seq_len - 5):
        base = min(base, 3.0)

    rationale = f"ASA propensity={base:.1f}"
    return base, rationale


def _score_active_site_distance(
    position: int, active_site_positions: list[int], seq_len: int,
) -> tuple[float, str]:
    """Score sequence-neighborhood separation from protected catalytic residues.

    This is a sequence-only guardrail.  It must not be reported or treated as a
    3D distance because uploaded PDB coordinates may be predicted, incomplete, or
    unmapped to a curated active site.
    """
    if not active_site_positions:
        # No known active site: assume moderate safety, mildly penalize center.
        center = seq_len // 2
        dist_proxy = abs(position - center)
        norm_dist = dist_proxy / (seq_len / 2)
        score = min(10, 5.0 + 5.0 * norm_dist)
        return score, f"no known active site; sequence-center proxy={norm_dist:.1f}"

    min_dist = min(abs(position - ap) for ap in active_site_positions)
    if min_dist <= 1:
        score = 0.0
    elif min_dist <= 2:
        score = 3.0
    elif min_dist <= 5:
        score = 5.0
    elif min_dist <= 12:
        score = 7.0
    else:
        score = 10.0

    return score, f"sequence spacing from protected catalytic residue={min_dist} aa"


def _score_conservation(aa: str, position: int, family_conserved: dict[int, str] | None = None) -> tuple[float, str]:
    """Score evolutionary conservation (0-10, reversed).

    10: Variable (safe to mutate) — ConSurf 1-3
    5: Average — ConSurf 4-6
    0: Conserved (DO NOT MUTATE) — ConSurf 7-9

    We invert: low conservation bias → high mutate-ability score.
    """
    # If we know specific conserved positions
    if family_conserved and position in family_conserved:
        return 0.0, f"conserved in family ({family_conserved[position]})"

    # General conservation bias
    cons = _CONSERVATION_BIAS.get(aa, 5.0)
    # Invert: rare amino acids (high conservation bias) → low mutability
    score = max(0.0, 10.0 - cons)
    return score, f"conservation bias={cons:.1f} → mutability={score:.1f}"


def _score_mutation_ddg(aa: str, proposed_mutation: str | None = None) -> tuple[float, str]:
    """Score mutation ΔΔG (0-10).

    10: Stabilizing (ΔΔG < -1.0)
    5: Neutral (-1.0 to +1.0)
    0: Destabilizing (> +1.0, avoid)

    Simplified model based on volume and hydrophobicity changes.
    """
    if proposed_mutation is None:
        return 5.0, "no mutation specified; assumed neutral"

    mt = proposed_mutation
    d_vol = _AA_VOLUME.get(mt, 150.0) - _AA_VOLUME.get(aa, 150.0)
    d_hydro = _KD.get(mt, 0.0) - _KD.get(aa, 0.0)

    # Predict ddG
    ddg = 0.5 + 1.2 * abs(d_vol / 150.0) + 1.0 * (d_hydro / 9.0)

    if ddg < 0.5:
        score = 10.0
        label = "stabilizing"
    elif ddg < 1.5:
        score = 7.0
        label = "mildly stabilizing"
    elif ddg < 2.5:
        score = 4.0
        label = "neutral"
    elif ddg < 4.0:
        score = 1.5
        label = "destabilizing"
    else:
        score = 0.0
        label = "highly destabilizing"

    return score, f"ΔΔG~{ddg:.1f} kcal/mol ({label})"


def _score_functional_relevance(
    aa: str, position: int, active_site_positions: list[int],
    is_charged: bool, family_info: dict | None = None,
) -> tuple[float, str]:
    """Score functional relevance (0-10, reversed).

    10: No known function in the region
    5: Part of a functional domain but not core
    0: Catalytic, substrate-binding, metal-binding, or structurally essential
    """
    # Near active site → high functional relevance → low score
    if active_site_positions:
        min_dist = min(abs(position - ap) for ap in active_site_positions)
        if min_dist <= 2:
            return 0.0, f"adjacent to catalytic residue (dist={min_dist})"
        if min_dist <= 5:
            return 3.0, f"near catalytic residue (dist={min_dist})"

    # Metal-binding residues
    if aa in ("H", "C", "D", "E") and family_info:
        metal_binding = family_info.get("metal_binding_sites", [])
        if position in metal_binding:
            return 0.0, "predicted metal-binding site"

    # Cysteine — potential disulfide
    if aa == "C":
        return 2.0, "Cys — may form disulfide; verify before mutating"

    # Gly with potential unusual angles
    if aa == "G":
        return 4.0, "Gly — may have unusual backbone angles"

    # Charged surface residue → often not functionally critical
    if is_charged:
        return 8.0, "charged surface residue; unlikely functional core"

    return 6.0, "no known functional role in this region"


def _detect_engineering_target_type(aa: str, position: int, seq_len: int, surface_score: float) -> str | None:
    """Detect if this residue is a high-value engineering target type."""
    if surface_score >= 7.0:
        if aa in ("K", "R"):
            return "surface_K_R"
        if aa == "G":
            return "surface_G_loop"
        if aa in ("N", "Q"):
            return "surface_N_Q"
        if aa == "C":
            return "unpaired_C"
    if surface_score <= 3.0 and aa in ("A", "S", "G", "V"):
        return "core_cavity"
    return None


def _identify_category(aa: str, position: int, active_site_positions: list[int]) -> list[str]:
    """Classify a residue into NEVER-MUTATE or HIGH-VALUE categories."""
    categories = []

    # Check NEVER-MUTATE
    if active_site_positions and position in active_site_positions:
        categories.append("catalytic")
    if aa == "C":
        categories.append("potential_disulfide")
    if aa == "P":
        categories.append("potential_cis_proline")
    if aa == "G":
        categories.append("potential_unusual_gly")

    # Check HIGH-VALUE
    if _SURFACE_PROPENSITY.get(aa, 5.0) >= 6.0:
        categories.append("surface_exposed")

    return categories


def _build_engineering_strategy(
    engineering_goal: str,
    *,
    target_ph: float | None = None,
    target_tm: float | None = None,
    objective_signals: set[str] | None = None,
) -> dict:
    """Return the target-level design logic that sits above residue ranking.

    The score is only a screening signal.  This structured strategy makes the
    intended design direction, guardrails, and experiment order explicit so a
    ranked list cannot be mistaken for a complete engineering plan.
    """
    signals = objective_signals or set()
    if "activity" in signals and "thermostability" in signals:
        return {
            "goal": "activity_stability",
            "objective": "同时提高比活力/催化效率和热稳定性；候选必须以双指标共同验证，不能只按单一活性或单一增稳分数排序。",
            "design_principle": "先保护催化核心和结构核心，再优先审查口袋入口、二壳层、局部网络和非催化柔性区；任何候选都要标注提活-增稳取舍。",
            "screening_logic": [
                "比活力线要求 specific activity、kcat 或 kcat/Km 证据，不能用总活或表达量代替。",
                "热稳定线要求 Tm、热半衰期或热处理残余活性证据，并复核原始条件活性保持。",
                "优先保留机制互补候选：入口/二壳层微环境、局部氢键/盐桥网络、非催化 loop 刚性调节。",
                "降低只靠表面电荷翻转、远端暴露位点或启发式 kcat 的排序权重。",
            ],
            "preserved_constraints": [
                "催化残基、底物锚定位点、金属结合位点、保守二硫键和编号冲突位点不进入首轮候选。",
                "单点通过后才允许组合；组合前必须检查上位性、结构距离和活性-稳定性冲突。",
            ],
            "experiment_plan": [
                {"priority": "P1", "scope": "机制互补单点", "purpose": "同时验证比活力方向和热稳定保持/改善", "gate": "比活力优于 WT，Tm/半衰期/残余活性不下降或改善，表达/可溶性不明显变差"},
                {"priority": "P2", "scope": "第二梯队单点", "purpose": "覆盖不同机制，避免只押注活性或只押注稳定性", "gate": "同批 WT、阴/阳性对照和 n>=3 通过"},
                {"priority": "P3", "scope": "二点组合", "purpose": "只组合单点均通过且机制互补的候选", "gate": "完成上位性和结构冲突复核"},
            ],
            "confidence_boundary": "双目标排序是计算假设；任何改善声明必须来自同批 WT 对照下的比活力和热稳定实验。",
        }
    if engineering_goal == "thermostability":
        return {
            "goal": "thermostability",
            "objective": f"提高热稳定性{f'，目标 Tm {target_tm}°C' if target_tm is not None else ''}，同时尽量保持催化活性、表达和可溶性。",
            "design_principle": "优先加固非催化、可突变的柔性环和局部疏松区域；避免直接改造催化中心及其近邻，先做单点验证，再逐步组合。",
            "screening_logic": [
                "排除催化/金属结合/结构性保护位点及其近邻。",
                "优先筛选表面暴露、保守性较低且远离活性中心的位点。",
                "按具体残基类型选择机制：Gly→Pro 侧重降低 loop 构象熵，疏松核心位点侧重改善 packing，非配对 Cys 侧重降低错误氧化风险。",
                "把活性保持、可溶表达和聚集风险作为反向约束，而不是只按稳定性分数排序。",
            ],
            "preserved_constraints": [
                "催化残基、金属结合位点和已知二硫键 Cys 不进入首轮突变。",
                "任何预测增稳候选都必须复测表达、可溶性、活性和 Tm/残余活性。",
            ],
            "experiment_plan": [
                {"priority": "P1", "scope": "单点候选", "purpose": "先验证最高优先级位点的增稳方向及活性保持", "gate": "表达/可溶性通过，Tm 或热处理残余活性有改善，活性无明显下降"},
                {"priority": "P2", "scope": "第二梯队单点", "purpose": "扩展机制不同的候选，避免只押注同一类突变", "gate": "与 P1 相同，并检查聚集/降解"},
                {"priority": "P3", "scope": "双位点组合", "purpose": "仅组合已通过单点验证且机制互补的位点", "gate": "先做上位性/空间冲突检查，再进入组合实验"},
            ],
            "confidence_boundary": "位点排序是计算筛选假设，不等同于实测 ΔTm；预期幅度需以实验为准。",
        }
    if engineering_goal in {"ph_lowering", "ph_raising"}:
        direction = "降低" if engineering_goal == "ph_lowering" else "提高"
        charge = "正电荷" if engineering_goal == "ph_lowering" else "负电荷"
        return {
            "goal": engineering_goal,
            "objective": f"{direction}酶的最适/耐受 pH{f'，目标 pH {target_ph}' if target_ph is not None else ''}，同时保持催化效率。",
            "design_principle": f"优先调整远离催化核心的表面 {charge} 残基，改变局部电荷和 pKa 环境；活性中心附近只作为高风险备选。",
            "screening_logic": [
                "先锁定催化、金属结合和底物识别的保护位点。",
                "优先选择表面暴露且远离活性中心的电荷位点。",
                "用同一位点的多个替换方向形成小梯度，而不是只押注一个氨基酸。",
                "同时比较目标 pH 和原始 pH 下的活性，识别活性保持与 pH 偏移的权衡。",
            ],
            "preserved_constraints": ["不以牺牲催化残基、底物结合位点或金属配位为代价换取 pH 偏移。"],
            "experiment_plan": [
                {"priority": "P1", "scope": "表面电荷单点梯度", "purpose": "验证 pH 方向是否正确并测量活性保持", "gate": "目标 pH 下活性改善且原始条件活性可接受"},
                {"priority": "P2", "scope": "不同机制的单点", "purpose": "区分电荷、pKa 和局部构象贡献", "gate": "重复实验和稳定性检查通过"},
                {"priority": "P3", "scope": "组合突变", "purpose": "仅组合已验证且不共享同一局部电荷冲突的位点", "gate": "完成上位性和编号复核"},
            ],
            "confidence_boundary": "pH 变化方向和幅度属于计算假设，必须通过 pH-activity 曲线验证。",
        }
    if engineering_goal in {"activity", "specificity"}:
        label = "比活力/催化效率" if engineering_goal == "activity" else "底物特异性"
        return {
            "goal": engineering_goal,
            "objective": f"优化{label}，同时保护整体折叠、表达和热稳定性。",
            "design_principle": "围绕催化中心、底物通道和口袋边缘区分层设计；催化核心保守，优先改变可调节的二壳层/入口位点。",
            "screening_logic": [
                "先确定催化残基和底物结合约束，再筛选邻近但非核心的可调位点。",
                "把结构距离、保守性、替换后的物化性质和已有实验/文献证据交叉判断。",
                "候选需要同时看活性收益、底物谱变化、表达和稳定性风险。",
            ],
            "preserved_constraints": ["催化三联体、金属结合和关键底物锚定位点默认不作为首轮突变。"],
            "experiment_plan": [
                {"priority": "P1", "scope": "口袋边缘/通道单点", "purpose": "先验证方向性和底物谱变化", "gate": "目标底物活性改善且非目标副作用可接受"},
                {"priority": "P2", "scope": "二壳层单点", "purpose": "扩大可调空间并保持折叠", "gate": "表达、稳定性和动力学复核通过"},
                {"priority": "P3", "scope": "组合设计", "purpose": "仅组合机制互补且上位性风险可控的单点", "gate": "完成结构/编号/上位性检查"},
            ],
            "confidence_boundary": "活性和特异性预测对底物、结构和实验条件敏感，候选不能替代动力学实测。",
        }
    return {
        "goal": "general",
        "objective": "在用户约束下寻找可解释、可验证的改造位点。",
        "design_principle": "先保护功能核心，再按暴露度、保守性、结构距离和物化变化筛选候选。",
        "screening_logic": ["候选必须有明确突变逻辑、风险提示和实验优先级。", "不把单一模型分数当作确定性结论。"],
        "preserved_constraints": ["催化、金属结合、二硫键和编号不确定位点需人工复核。"],
        "experiment_plan": [
            {"priority": "P1", "scope": "最高优先级单点", "purpose": "验证候选方向", "gate": "表达、活性和目标性质均需实测"},
            {"priority": "P2", "scope": "第二梯队单点", "purpose": "扩大验证覆盖", "gate": "通过同样的质量门控"},
            {"priority": "P3", "scope": "组合突变", "purpose": "仅组合已验证单点", "gate": "完成上位性检查"},
        ],
        "confidence_boundary": "当前结果用于实验设计排序，不代表已验证的工程效果。",
    }


def _experiment_action_for_goal(engineering_goal: str, objective_signals: set[str] | None = None) -> str:
    """Return a bench-facing validation action for candidate rows."""
    signals = objective_signals or set()
    if "activity" in signals and "thermostability" in signals:
        return "构建单点突变体；同批测 WT/突变体比活力与 kcat/Km；同步测 Tm/热半衰期或热处理残余活性，并检查表达、可溶性和聚集风险。"
    if engineering_goal == "thermostability":
        return "构建单点突变体；与 WT 同批表达纯化；测 Tm/热处理残余活性；同步复测比活、可溶性和聚集风险。"
    if engineering_goal in {"ph_lowering", "ph_raising"}:
        return "构建单点突变体；测 pH-activity 曲线；比较目标 pH 与原始 pH 活性；同步检查稳定性和表达。"
    if engineering_goal == "activity":
        return "构建单点突变体；同批测 WT 与突变体比活；优先补 kcat/Km；同步复测稳定性避免提活降稳。"
    if engineering_goal == "specificity":
        return "构建单点突变体；用目标/非目标底物并行测 kcat/Km 或初速；计算选择性比值并复核表达稳定性。"
    return "构建单点突变体；与 WT 同批表达纯化；按目标性质做主实验，并复测活性、稳定性和可溶性。"


async def _load_curated_catalytic_positions(uniprot_id: str) -> list[int]:
    if not uniprot_id:
        return []

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.domain import CatalyticSite, EnzymeRecord

    async with session_scope() as session:
        result = await session.execute(
            select(EnzymeRecord)
            .options(selectinload(EnzymeRecord.catalytic_sites).selectinload(CatalyticSite.residues))
            .where(EnzymeRecord.uniprot_id == uniprot_id)
        )
        enzyme = result.scalar_one_or_none()
        if not enzyme:
            return []

        positions = {
            residue.residue_pos
            for site in enzyme.catalytic_sites
            for residue in site.residues
            if residue.residue_pos
        }
        return sorted(positions)


async def mutation_priority_score(
    sequence: str,
    active_site_positions: list[int] | None = None,
    target_ph: float | None = None,
    target_tm: float | None = None,
    engineering_goal: str = "general",
    objective_signals: list[str] | None = None,
    family_conserved: dict[str, list[int]] | None = None,
    uniprot_id: str = "",
    identity_profile: dict | None = None,
    objective_module_plan: dict | None = None,
    pdb_coordinate_mapping: list[dict] | None = None,
    chain_id: str = "A",
    sequence_provenance: str = "",
    site_structure_features: list[dict] | None = None,
    pocket_residue_positions: list[dict] | None = None,
    specified_mutations: list[str] | None = None,
    include_lipase_evidence: bool = True,
    lipase_evidence_query: str | None = None,
    wet_lab_calibration_summary: dict | None = None,
) -> dict:
    """Score every residue for mutation priority using 5 dimensions.

    Args:
        sequence: Amino acid sequence
        active_site_positions: 1-indexed positions of known catalytic residues
        target_ph: Target pH (for pH engineering context)
        target_tm: Target melting temperature (for thermostability context)
        engineering_goal: "ph_lowering" | "ph_raising" | "thermostability" |
                         "activity" | "specificity" | "general"
        objective_signals: all detected engineering objectives, used for report
                           provenance and multi-objective gate visibility
        family_conserved: {motif_name: [positions]} of conserved residues
        uniprot_id: optional UniProt accession used to load curated catalytic sites
        identity_profile: optional enzyme_identity_profile output for key-residue guardrails
        objective_module_plan: optional enzyme_objective_module_plan output for target evidence gating
        specified_mutations: optional user-requested point mutations such as P338T
                             that require explicit review rather than silent omission
        site_structure_features: optional build_site_structure_function_features
                                 feature rows used as structure evidence and
                                 protected-site guardrails, not as wet-lab proof
        include_lipase_evidence: enrich recommendations with KWB lipase evidence
        lipase_evidence_query: optional query used for lipase evidence context
        wet_lab_calibration_summary: optional project-level wet-lab feedback/calibration
                                 summary; it never validates a specific candidate

    Returns:
        Dict with per-residue scores, tier classification, and recommended mutations.
    """
    seq = sequence.strip().upper()
    n = len(seq)

    # Validation
    if n < 5:
        raise ValueError(f"SEQUENCE_TOO_SHORT: {n} residues; minimum 5 required")
    invalid = set(seq) - set(_AA_LIST)
    if invalid:
        raise ValueError(f"INVALID_AA: {''.join(sorted(invalid))}")

    def _parse_specified_mutation(raw: str) -> dict | None:
        text = str(raw or "").strip().upper()
        if len(text) < 3:
            return None
        wt = text[0]
        mt = text[-1]
        pos_text = text[1:-1]
        if wt not in _AA_LIST or mt not in _AA_LIST or not pos_text.isdigit():
            return None
        return {"mutation": f"{wt}{int(pos_text)}{mt}", "wild_type": wt, "position": int(pos_text), "mutant": mt}

    specified_items: list[dict] = []
    seen_specified: set[str] = set()
    for raw in specified_mutations or []:
        item = _parse_specified_mutation(str(raw))
        if not item or item["mutation"] in seen_specified:
            continue
        seen_specified.add(item["mutation"])
        specified_items.append(item)

    pdb_position_map: dict[int, str] = {}
    uniprot_position_map: dict[int, int] = {}
    if isinstance(pdb_coordinate_mapping, list):
        for row in pdb_coordinate_mapping:
            if not isinstance(row, dict):
                continue
            aa = str(row.get("residue_aa") or row.get("residue") or "").strip().upper()[:1]
            try:
                seq_pos = int(row.get("uniprot_position") or row.get("pdb_residue_no"))
                pdb_pos = int(row.get("pdb_residue_no"))
            except (TypeError, ValueError):
                continue
            if not (1 <= seq_pos <= n):
                continue
            if aa and aa != seq[seq_pos - 1]:
                continue
            row_chain = str(row.get("chain_id") or chain_id or "A")
            pdb_position_map[seq_pos] = f"{row_chain}:{pdb_pos}"
            if row.get("uniprot_position") not in {None, ""}:
                try:
                    uniprot_position_map[seq_pos] = int(row["uniprot_position"])
                except (TypeError, ValueError):
                    pass

    structure_features_by_position: dict[int, dict] = {}
    structure_protected_positions: set[int] = set()
    for feature in site_structure_features or []:
        if not isinstance(feature, dict):
            continue
        position_values = (
            feature.get("position"),
            feature.get("uniprot_position"),
            feature.get("pdb_residue_no"),
        )
        normalized_positions: list[int] = []
        for value in position_values:
            try:
                position = int(value)
            except (TypeError, ValueError):
                continue
            if not (1 <= position <= n) or position in normalized_positions:
                continue
            normalized_positions.append(position)
            structure_features_by_position.setdefault(position, feature)
        if feature.get("is_protected") is True or feature.get("is_catalytic") is True:
            structure_protected_positions.update(normalized_positions)

    pocket_positions: set[int] = set()
    for item in pocket_residue_positions or []:
        if not isinstance(item, dict):
            continue
        for key in ("user_sequence_position", "source_position", "pdb_residue_no", "position"):
            try:
                value = int(item.get(key))
            except (TypeError, ValueError):
                continue
            if 1 <= value <= n:
                pocket_positions.add(value)
                break

    objective_gate = objective_module_plan if isinstance(objective_module_plan, dict) else {}
    candidate_decision = decide_candidate_output(identity_profile, objective_gate)
    objective_missing = objective_gate.get("missing_evidence", []) if objective_gate else []
    objective_candidate_table_status = (
        "ready" if candidate_decision["candidate_output_allowed"] else candidate_decision["status"]
    )
    objective_signal_list = [
        str(item)
        for item in (objective_signals or [])
        if str(item or "").strip()
    ]
    objective_signal_set = _objective_signal_set(
        engineering_goal,
        objective_signal_list,
        objective_gate,
    )
    is_activity_stability = "activity" in objective_signal_set and "thermostability" in objective_signal_set
    clear_engineering_objective = bool(objective_signal_list) or _has_clear_engineering_objective(
        engineering_goal,
        target_ph=target_ph,
        target_tm=target_tm,
        objective_gate=objective_gate,
    )
    calibration_context = None
    if isinstance(wet_lab_calibration_summary, dict) and wet_lab_calibration_summary:
        try:
            measured_variant_count = int(wet_lab_calibration_summary.get("measured_variant_count") or 0)
        except (TypeError, ValueError):
            measured_variant_count = 0
        calibration_context = {
            "evidence_level": wet_lab_calibration_summary.get("evidence_level") or "computational_hypothesis",
            "data_quality_grade": wet_lab_calibration_summary.get("data_quality_grade") or "unknown",
            "measured_variant_count": measured_variant_count,
            "hit_rate": wet_lab_calibration_summary.get("hit_rate"),
            "objective": wet_lab_calibration_summary.get("objective"),
            "assay_key": wet_lab_calibration_summary.get("assay_key"),
            "dataset_fingerprint": wet_lab_calibration_summary.get("dataset_fingerprint"),
            "candidate_scope": "project_level_calibration_not_direct_variant_validation",
            "boundary": "Project/assay feedback can calibrate ranking context, but each proposed mutation still requires direct wet-lab validation.",
        }

    profile = identity_profile if isinstance(identity_profile, dict) else {}
    profile_status = str(profile.get("identity_status") or "")
    profile_guardrail = profile.get("guardrail") if isinstance(profile.get("guardrail"), dict) else {}
    profile_ready = profile_status == "identified" and profile_guardrail.get("status") == "ready"
    profile_positions: list[int] = []
    for value in profile.get("protected_positions", []) if isinstance(profile.get("protected_positions"), list) else []:
        try:
            pos = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= pos <= n:
            profile_positions.append(pos)

    explicit_active_positions = sorted(set((active_site_positions or []) + profile_positions))
    curated_positions = await _load_curated_catalytic_positions(uniprot_id)
    inferred_positions = []
    if not explicit_active_positions and not curated_positions:
        inferred_positions = sorted({item["position"] for item in _infer_catalytic_residues(seq)})

    active_positions = sorted(set(explicit_active_positions + curated_positions + inferred_positions))
    active_position_sources: dict[int, list[str]] = {}
    for pos in explicit_active_positions:
        active_position_sources.setdefault(pos, []).append("input")
    for pos in curated_positions:
        active_position_sources.setdefault(pos, []).append("curated")
    for pos in inferred_positions:
        active_position_sources.setdefault(pos, []).append("heuristic")
    for pos in profile_positions:
        active_position_sources.setdefault(pos, []).append("identity_profile")
    for pos in sorted(structure_protected_positions):
        if pos not in active_positions:
            active_positions.append(pos)
        active_position_sources.setdefault(pos, []).append("site_structure_features")
    active_positions.sort()

    # Convert family_conserved from {motif: [positions]} to {position: motif}
    conserved_map: dict[int, str] = {}
    if family_conserved:
        for motif, positions in family_conserved.items():
            for p in positions:
                conserved_map[p] = motif

    # Detect engineering context for mutation recommendation
    is_ph_lowering = engineering_goal == "ph_lowering" or (target_ph is not None and target_ph < 7.0)
    is_ph_raising = engineering_goal == "ph_raising" or (target_ph is not None and target_ph > 7.0)
    is_thermo = engineering_goal == "thermostability" or "thermostability" in objective_signal_set or (target_tm is not None)

    results: list[dict] = []
    tier1_count = 0
    tier2_count = 0

    for i, aa in enumerate(seq):
        pos = i + 1  # 1-indexed
        structure_feature = structure_features_by_position.get(pos)

        is_charged = aa in ("R", "K", "D", "E", "H")
        is_terminal = _is_terminal_region(pos, n)

        # ---- Dimension scores ----
        asa_score, asa_why = _score_surface_exposure(aa, pos, n)
        dist_score, dist_why = _score_active_site_distance(pos, active_positions, n)
        cons_score, cons_why = _score_conservation(aa, pos, conserved_map if conserved_map else None)
        func_score, func_why = _score_functional_relevance(aa, pos, active_positions, is_charged)
        has_pocket_evidence = pos in pocket_positions
        if has_pocket_evidence:
            func_score = min(10.0, func_score + 1.0)
            func_why = f"P2Rank/fpocket 几何口袋残基证据；{func_why}"

        # ---- Composite priority ----
        composite = (
            asa_score * 0.20
            + dist_score * 0.25
            + cons_score * 0.25
            + 5.0 * 0.15      # ddG baseline (no specific mutation yet)
            + func_score * 0.15
        )

        # ---- Adjust for engineering goal ----
        if is_ph_lowering and aa in ("K", "R") and asa_score >= 7.0:
            composite += 1.5  # boost surface K/R for pH lowering
        elif is_ph_lowering and aa in ("H") and dist_score >= 5.0:
            composite += 0.5  # His pH switch near active site
        if is_thermo and aa == "G" and asa_score >= 5.0:
            composite += 1.0  # boost Gly→Pro candidates
        if is_ph_raising and aa in ("D", "E") and asa_score >= 7.0:
            composite += 1.5
        if is_thermo and is_terminal:
            composite = max(0.0, composite - 3.0)

        min_active_dist = min((abs(pos - ap) for ap in active_positions), default=999)
        is_protected = pos in active_positions
        if is_protected:
            composite = 0.0
        elif min_active_dist <= 1:
            composite = max(0.0, composite - 4.5)
        elif min_active_dist <= 2:
            composite = max(0.0, composite - 2.5)
        elif min_active_dist <= 4:
            composite = max(0.0, composite - 1.0)

        composite = round(min(10.0, composite), 1)

        # ---- Tier ----
        if is_protected:
            tier = 3
        elif composite >= 7.0:
            tier = 1
            tier1_count += 1
        elif composite >= 5.0:
            tier = 2
            tier2_count += 1
        else:
            tier = 3

        # ---- Categories ----
        categories = _identify_category(aa, pos, active_positions)
        if is_protected and "protected_catalytic" not in categories:
            categories.append("protected_catalytic")
        target_type = _detect_engineering_target_type(aa, pos, n, asa_score)

        # ---- Recommended mutations (no fake predictions) ----
        recommended_mutations = []
        mutation_type = None
        if not is_protected and composite >= 4.0:
            if is_thermo and aa == "G" and asa_score >= 5.0:
                mutation_type = "增加loop刚性"
                recommended_mutations.append({
                    "mutation": f"{aa}{pos}P",
                    "type": mutation_type,
                    "purpose": "Gly→Pro减少主链构象熵，优先用于加固暴露loop；需要确认该位置不是催化/底物通道关键柔性位点",
                })
            elif is_thermo and target_type == "unpaired_C":
                mutation_type = "降低氧化风险"
                recommended_mutations.extend([
                    {
                        "mutation": f"{aa}{pos}S",
                        "type": mutation_type,
                        "purpose": "Cys→Ser移除潜在游离巯基，降低错误氧化和聚集风险；需先排除二硫键作用",
                    },
                    {
                        "mutation": f"{aa}{pos}A",
                        "type": mutation_type,
                        "purpose": "Cys→Ala移除潜在反应性侧链，作为保守的对照方向",
                    },
                ])
            elif is_thermo and target_type == "core_cavity":
                mutation_type = "核心packing优化"
                packing_target = {"A": "V", "S": "V", "G": "A", "V": "I"}.get(aa)
                if packing_target:
                    recommended_mutations.append({
                        "mutation": f"{aa}{pos}{packing_target}",
                        "type": mutation_type,
                        "purpose": f"{aa}→{packing_target}增加局部侧链体积，尝试填补疏松核心；需警惕空间冲突和折叠损失",
                    })
            elif is_thermo and aa in ("K", "R") and asa_score >= 7.0:
                mutation_type = "表面电荷网络优化"
                recommended_mutations.extend([
                    {
                        "mutation": f"{aa}{pos}E",
                        "type": mutation_type,
                        "purpose": "表面K/R→E用于重排表面电荷网络，尝试形成新的盐桥或降低局部电荷斥力；需实验确认不影响表达和活性",
                    },
                    {
                        "mutation": f"{aa}{pos}Q",
                        "type": mutation_type,
                        "purpose": "表面K/R→Q降低局部正电荷和柔性水化扰动，作为较温和的热稳定性验证方向",
                    },
                ])
            elif is_thermo and aa in ("D", "E") and asa_score >= 7.0:
                mutation_type = "表面电荷网络优化"
                recommended_mutations.extend([
                    {
                        "mutation": f"{aa}{pos}K",
                        "type": mutation_type,
                        "purpose": "表面D/E→K用于测试反向盐桥或电荷网络重排的增稳可能；需警惕局部pI和表达变化",
                    },
                    {
                        "mutation": f"{aa}{pos}Q",
                        "type": mutation_type,
                        "purpose": "表面D/E→Q中和局部负电荷，作为较温和的热稳定性验证方向",
                    },
                ])
            elif is_ph_lowering and aa in ("K", "R"):
                mutation_type = "表面电荷翻转"
                for mt in ["E", "D", "Q"]:
                    recommended_mutations.append({
                        "mutation": f"{aa}{pos}{mt}",
                        "type": mutation_type,
                        "purpose": f"将表面正电荷({aa})替换为负电荷或极性残基，降低局部pKa，适应酸性环境",
                    })
            elif is_ph_lowering and aa == "H" and dist_score <= 5.0:
                mutation_type = "活性中心电荷中和"
                for mt in ["N", "F", "Q"]:
                    recommended_mutations.append({
                        "mutation": f"{aa}{pos}{mt}",
                        "type": mutation_type,
                        "purpose": "消除活性中心附近的pH敏感His开关，减少pH依赖的活性波动",
                    })
            elif is_thermo and aa == "G" and asa_score >= 5.0:
                mutation_type = "增加loop刚性"
                recommended_mutations.append({
                    "mutation": f"{aa}{pos}P",
                    "type": mutation_type,
                    "purpose": "Gly→Pro减少主链构象熵，提高loop区刚性，增强热稳定性",
                })
            elif is_ph_raising and aa in ("D", "E"):
                mutation_type = "表面电荷翻转"
                for mt in ["K", "R", "H"]:
                    recommended_mutations.append({
                        "mutation": f"{aa}{pos}{mt}",
                        "type": mutation_type,
                        "purpose": f"将表面负电荷({aa})替换为正电荷残基，提升局部pKa，适应碱性环境",
                    })
            # Fallback for general candidates
            if not recommended_mutations:
                if aa in ("K", "R") and asa_score >= 7.0:
                    mutation_type = "表面电荷优化"
                    recommended_mutations.append({
                        "mutation": f"{aa}{pos}E",
                        "type": mutation_type,
                        "purpose": "表面K/R→E，优化电荷分布，可调节pH适应性",
                    })
                if aa == "G" and asa_score >= 5.0:
                    mutation_type = mutation_type or "loop稳定性"
                    recommended_mutations.append({
                        "mutation": f"{aa}{pos}P",
                        "type": mutation_type,
                        "purpose": "Gly→Pro减少loop柔性，提升整体结构稳定性",
                    })
            if not recommended_mutations and clear_engineering_objective:
                exploratory_options = _exploratory_mutation_options(
                    aa,
                    pos,
                    engineering_goal,
                    surface_score=asa_score,
                    dist_score=dist_score,
                )
                if exploratory_options:
                    mutation_type = mutation_type or exploratory_options[0]["type"]
                    recommended_mutations.extend(exploratory_options)

        # ---- Build Chinese engineering logic ----
        logic_parts = []

        structure_rel_sasa = (
            structure_feature.get("rel_sasa")
            if isinstance(structure_feature, dict)
            else None
        )
        structure_rel_sasa_status = (
            str(structure_feature.get("rel_sasa_status") or "")
            if isinstance(structure_feature, dict)
            else ""
        )
        if (
            isinstance(structure_rel_sasa, (int, float))
            and structure_rel_sasa_status == "computed_from_input_pdb"
        ):
            if structure_rel_sasa >= 0.5:
                logic_parts.append(f"输入PDB relSASA={structure_rel_sasa:.3f}，结构上相对暴露")
            elif structure_rel_sasa >= 0.2:
                logic_parts.append(f"输入PDB relSASA={structure_rel_sasa:.3f}，结构上部分暴露")
            else:
                logic_parts.append(f"输入PDB relSASA={structure_rel_sasa:.3f}，结构上相对埋藏")
        elif asa_score >= 7.0:
            logic_parts.append("基于序列组成的表面暴露倾向较高，仍需结构复核")
        elif asa_score >= 5.0:
            logic_parts.append("基于序列组成的表面暴露倾向中等，仍需结构复核")
        else:
            logic_parts.append("基于序列组成的埋藏倾向较高，仍需结构复核")

        if active_positions:
            if is_protected:
                source_text = "/".join(active_position_sources.get(pos, ["guardrail"]))
                logic_parts.append(f"命中催化保护位点({source_text})，默认禁止突变")
            elif min_active_dist > 5:
                logic_parts.append(f"与催化保护位点序列间隔 {min_active_dist} aa；未提供三维距离，需结构复核")
            elif min_active_dist > 2:
                logic_parts.append(f"靠近催化保护位点的序列邻域({min_active_dist} aa)，需谨慎设计")
            else:
                logic_parts.append(f"靠近催化保护位点({min_active_dist} aa)，需谨慎设计突变")
        else:
            logic_parts.append("未标注活性中心位置")

        if isinstance(structure_feature, dict):
            distance_ca = structure_feature.get("nearest_catalytic_distance_ca_angstrom")
            contact_count = structure_feature.get("contact_count_ca_8a")
            nearest_ca_neighbor = structure_feature.get("nearest_ca_neighbor_distance_angstrom")
            nearest_ca_neighbor_position = structure_feature.get("nearest_ca_neighbor_position")
            b_factor = structure_feature.get("b_factor")
            if isinstance(distance_ca, (int, float)):
                logic_parts.append(f"最近催化CA距离 {distance_ca} A")
            if isinstance(nearest_ca_neighbor, (int, float)):
                neighbor_label = (
                    f"位点{nearest_ca_neighbor_position}"
                    if nearest_ca_neighbor_position is not None
                    else "最近邻位点"
                )
                logic_parts.append(f"最近CA邻居{neighbor_label}距离 {nearest_ca_neighbor} A")
            if isinstance(contact_count, int):
                logic_parts.append(f"8A CA接触数={contact_count}")
            if isinstance(b_factor, (int, float)):
                logic_parts.append(f"CA B-factor={b_factor}")

        if cons_score >= 7.0:
            logic_parts.append("序列保守性低，可突变空间大")
        elif cons_score >= 4.0:
            logic_parts.append("保守性中等")
        else:
            logic_parts.append("序列高度保守，突变风险较高")

        if func_score >= 7.0:
            logic_parts.append("位于非功能核心区域")
        elif func_score >= 4.0:
            logic_parts.append("可能参与结构维持")
        else:
            logic_parts.append("位于功能关键区域，需谨慎评估")

        if is_ph_lowering and aa in ("K", "R") and asa_score >= 7.0:
            logic_parts.append("表面正电荷残基是pH降低改造的优先靶点")
        elif is_thermo and aa == "G" and asa_score >= 5.0:
            logic_parts.append("Gly→Pro可减少主链构象熵，是热稳定性改造的经典策略")
        elif is_ph_raising and aa in ("D", "E") and asa_score >= 7.0:
            logic_parts.append("表面负电荷残基是pH升高改造的优先靶点")

        logic = "；".join(logic_parts)
        if has_pocket_evidence:
            logic_parts.append("P2Rank/fpocket 输出将该位点标记为几何口袋残基；不等同催化位点或活性增益证据")
            logic = "；".join(logic_parts)

        risk_flags: list[str] = []
        if is_protected:
            risk_flags.append("催化/功能保护位点，禁止作为首轮候选")
        elif min_active_dist <= 4:
            risk_flags.append("靠近活性中心，需复核催化和底物结合影响")
        if aa == "C":
            risk_flags.append("需确认是否参与二硫键或金属配位")
        if aa == "G" and is_thermo:
            risk_flags.append("Gly→Pro可能误伤必要柔性")
        if is_thermo and is_terminal:
            risk_flags.append("位于N/C端构建体边界区域，热稳定性信号可能来自末端柔性或标签/截短效应，默认不作为首轮优先候选")
        if target_type == "core_cavity":
            risk_flags.append("核心packing改变可能造成空间冲突或表达下降")
        if not recommended_mutations and not is_protected:
            risk_flags.append("当前仅支持位点级排序，尚未形成可信的具体替换方向")
        if not profile_ready and not is_protected:
            risk_flags.append("酶身份或残基编号未确认，不能作为高置信 P1/P2 候选")
        if objective_candidate_table_status != "ready" and not is_protected:
            risk_flags.append("目标实验上下文不足，候选为探索性排单，需先补基线/对照实验")
        if calibration_context and not is_protected:
            if calibration_context["evidence_level"] == "wet_lab_calibrated":
                risk_flags.append("同项目/同assay已有湿实验校准背景；该具体候选仍需单独实验确认")
            else:
                risk_flags.append("已有湿实验反馈可辅助排序，但样本量或assay一致性不足，不能升级为湿实验级候选")
        if isinstance(structure_feature, dict):
            structure_risks = structure_feature.get("risk_flags")
            if isinstance(structure_risks, list):
                for risk in structure_risks:
                    risk_text = str(risk or "").strip()
                    if risk_text and risk_text not in risk_flags:
                        risk_flags.append(risk_text)

        objective_score = _objective_score_contract(
            aa=aa,
            asa_score=asa_score,
            dist_score=dist_score,
            cons_score=cons_score,
            func_score=func_score,
            min_active_dist=None if min_active_dist == 999 else min_active_dist,
            is_protected=is_protected,
            target_type=target_type,
            structure_feature=structure_feature,
            risk_flags=risk_flags,
            profile_ready=profile_ready,
            objective_candidate_table_status=objective_candidate_table_status,
            objective_signal_set=objective_signal_set,
            engineering_goal=engineering_goal,
            target_ph=target_ph,
        )
        feature_completeness = _feature_completeness_contract(structure_feature)

        if is_protected:
            experiment_priority = "No-Go"
        elif tier == 1 and recommended_mutations:
            experiment_priority = "P1"
        elif tier == 2 and recommended_mutations:
            experiment_priority = "P2"
        else:
            experiment_priority = "P3"

        if engineering_goal == "thermostability":
            expected_effect = "候选用于提高局部结构稳定性；Tm/热处理残余活性需实验确认"
        elif engineering_goal in {"ph_lowering", "ph_raising"}:
            expected_effect = "候选用于改变局部电荷/pKa环境；pH-activity曲线和活性保持需实验确认"
        elif engineering_goal == "specificity":
            expected_effect = "候选用于调整底物通道或口袋微环境；底物谱变化需动力学实测"
        elif is_activity_stability:
            expected_effect = "候选用于同时探索催化效率/底物进入与热稳定保持；kcat/Km、比活力、Tm/半衰期或热处理残余活性必须同批实测"
        elif engineering_goal == "activity":
            expected_effect = "候选用于改善催化效率或底物进入；kcat/Km和稳定性需实验确认"
        else:
            expected_effect = "候选改造方向需结合目标性质和实验数据确认"

        results.append({
            "position": pos,
            "user_position": pos,
            "pdb_position": pdb_position_map.get(pos),
            "uniprot_position": uniprot_position_map.get(pos),
            "numbering_status": (
                "pdb_coordinate_derived"
                if pdb_position_map.get(pos) and sequence_provenance == "pdb_coordinate_derived"
                else "mapped_from_pdb_coordinates"
                if pdb_position_map.get(pos)
                else "user_sequence_only"
            ),
            "structure_feature_status": "available" if isinstance(structure_feature, dict) else "not_available",
            "feature_completeness": feature_completeness,
            "missing_feature_reasons": feature_completeness["missing_feature_reasons"],
            "ca_b_factor": structure_feature.get("b_factor") if isinstance(structure_feature, dict) else None,
            "nearest_catalytic_distance_ca_angstrom": (
                structure_feature.get("nearest_catalytic_distance_ca_angstrom")
                if isinstance(structure_feature, dict) else None
            ),
            "contact_count_ca_8a": (
                structure_feature.get("contact_count_ca_8a")
                if isinstance(structure_feature, dict) else None
            ),
            "nearest_ca_neighbor_distance_angstrom": (
                structure_feature.get("nearest_ca_neighbor_distance_angstrom")
                if isinstance(structure_feature, dict) else None
            ),
            "nearest_ca_neighbor_position": (
                structure_feature.get("nearest_ca_neighbor_position")
                if isinstance(structure_feature, dict) else None
            ),
            "nearest_ca_neighbor_pdb_position": (
                structure_feature.get("nearest_ca_neighbor_pdb_position")
                if isinstance(structure_feature, dict) else None
            ),
            "ca_contact_environment": (
                structure_feature.get("ca_contact_environment")
                if isinstance(structure_feature, dict) else None
            ),
            "secondary_structure": (
                structure_feature.get("secondary_structure")
                if isinstance(structure_feature, dict) else None
            ),
            "secondary_structure_source": (
                structure_feature.get("secondary_structure_source")
                if isinstance(structure_feature, dict) else None
            ),
            "rel_sasa": (
                structure_feature.get("rel_sasa")
                if isinstance(structure_feature, dict) else None
            ),
            "residue_sasa_angstrom2": (
                structure_feature.get("residue_sasa_angstrom2")
                if isinstance(structure_feature, dict) else None
            ),
            "rel_sasa_status": (
                structure_feature.get("rel_sasa_status")
                if isinstance(structure_feature, dict) else None
            ),
            "pocket_channel_interface_status": (
                "professional_tool_geometry"
                if has_pocket_evidence else (
                    structure_feature.get("pocket_channel_interface_status")
                    if isinstance(structure_feature, dict) else None
                )
            ),
            "pocket_residue_evidence": has_pocket_evidence,
            "nonpolymer_proximity_status": (
                structure_feature.get("nonpolymer_proximity_status")
                if isinstance(structure_feature, dict) else None
            ),
            "nearest_nonpolymer_heteroatom_distance_angstrom": (
                structure_feature.get("nearest_nonpolymer_heteroatom_distance_angstrom")
                if isinstance(structure_feature, dict) else None
            ),
            "nearest_nonpolymer_component_id": (
                structure_feature.get("nearest_nonpolymer_component_id")
                if isinstance(structure_feature, dict) else None
            ),
            "nearest_nonpolymer_component_position": (
                structure_feature.get("nearest_nonpolymer_component_position")
                if isinstance(structure_feature, dict) else None
            ),
            "nonpolymer_component_ids_within_4a": (
                list(structure_feature.get("nonpolymer_component_ids_within_4a", []))
                if isinstance(structure_feature, dict)
                and isinstance(structure_feature.get("nonpolymer_component_ids_within_4a"), list)
                else []
            ),
            "phi_deg": structure_feature.get("phi_deg") if isinstance(structure_feature, dict) else None,
            "psi_deg": structure_feature.get("psi_deg") if isinstance(structure_feature, dict) else None,
            "backbone_torsion_status": (
                structure_feature.get("backbone_torsion_status")
                if isinstance(structure_feature, dict) else None
            ),
            "backbone_torsion_reason": (
                structure_feature.get("backbone_torsion_reason")
                if isinstance(structure_feature, dict) else None
            ),
            "backbone_torsion_source": (
                structure_feature.get("backbone_torsion_source")
                if isinstance(structure_feature, dict) else None
            ),
            "structure_feature_risk_flags": (
                list(structure_feature.get("risk_flags", []))
                if isinstance(structure_feature, dict) and isinstance(structure_feature.get("risk_flags"), list)
                else []
            ),
            "wild_type": aa,
            "scores": {
                "surface_exposure": round(asa_score, 1),
                "active_site_distance": round(dist_score, 1),
                "conservation_mutability": round(cons_score, 1),
                "functional_relevance": round(func_score, 1),
            },
            "objective_score": objective_score,
            "composite_priority": composite,
            "tier": tier,
            "categories": categories,
            "target_type": target_type,
            "is_protected": is_protected,
            "active_site_distance_residues": None if min_active_dist == 999 else min_active_dist,
            "active_site_sources": active_position_sources.get(pos, []),
            "recommended_mutations": recommended_mutations,
            "mutation_type": mutation_type,
            "logic": logic,
            "design_logic": logic,
            "expected_effect": expected_effect,
            "risk_flags": risk_flags,
            "experiment_action": _experiment_action_for_goal(engineering_goal, objective_signal_set),
            "experiment_priority": experiment_priority,
            "candidate_evidence_status": "computational_hypothesis",
            "calibration_evidence_status": calibration_context["evidence_level"] if calibration_context else "not_calibrated",
            "objective_missing_evidence": objective_missing[:5] if isinstance(objective_missing, list) else [],
        })

    # Sort by composite score descending (best candidates first)
    results.sort(key=lambda r: r["composite_priority"], reverse=True)

    lipase_evidence_context: dict | None = None
    if include_lipase_evidence:
        recommended_codes = sorted(
            {
                str(item.get("mutation") or "")
                for row in results
                for item in row.get("recommended_mutations", [])
                if item.get("mutation")
            }
        )
        candidate_positions = [int(row["position"]) for row in results if row["tier"] in {1, 2}]
        lipase_evidence_context = build_lipase_evidence_context(
            mutations=recommended_codes,
            positions=candidate_positions[:100],
            q=lipase_evidence_query or engineering_goal,
            limit=50,
        )
        exact_by_mutation: dict[str, list[dict]] = {}
        for match in lipase_evidence_context.get("exact_mutation_matches") or []:
            code = str(match.get("mutation_code") or "").upper()
            exact_by_mutation.setdefault(code, []).append(match)
        position_counts: dict[int, int] = {}
        for match in lipase_evidence_context.get("position_matches") or []:
            try:
                position = int(match.get("position"))
            except (TypeError, ValueError):
                continue
            position_counts[position] = position_counts.get(position, 0) + 1

        for row in results:
            row["lipase_position_evidence_count"] = position_counts.get(int(row["position"]), 0)
            for recommendation in row.get("recommended_mutations", []):
                code = str(recommendation.get("mutation") or "").upper()
                matches = exact_by_mutation.get(code, [])
                recommendation["lipase_evidence"] = {
                    "exact_match_count": len(matches),
                    "matches": matches[:3],
                    "source": "kwb_lipase_db",
                    "interpretation": (
                        "exact literature evidence exists for this mutation in the KWB lipase database"
                        if matches
                        else "no exact mutation evidence found in the KWB lipase database"
                    ),
                }

    # Tier summaries
    tier1 = [r for r in results if r["tier"] == 1]
    tier2 = [r for r in results if r["tier"] == 2]
    never_mutate = [r for r in results if "catalytic" in r["categories"]]
    # A PDB-derived sequence is sufficient for a coordinate-level stability
    # hypothesis table. Structure features enrich the rows when available, but
    # a wiring miss must not collapse the entire exploratory table to zero.
    structure_bound_exploration = sequence_provenance == "pdb_coordinate_derived"
    # An independent FASTA paired with an uploaded model can still provide a
    # verified coordinate frame even when the model has no PDB accession (for
    # example SWISS-MODEL). Preserve exploratory structure hypotheses in that
    # case; the identity/assay gates continue to prevent P1 claims.
    exact_coordinate_mapping = any(
        isinstance(row, dict)
        and str(row.get("confidence") or row.get("mapping_confidence") or "").lower() in {"exact", "exact_input_sequence_match"}
        for row in (pdb_coordinate_mapping or [])
    )
    structure_bound_exploration = structure_bound_exploration or exact_coordinate_mapping
    identity_gate = {
        "status": "passed" if profile_ready else (
            "exploratory" if profile_status == "identified" or structure_bound_exploration else "blocked"
        ),
        "identity_status": profile_status or None,
        "reason": (
            None if profile_ready else (
                "enzyme_identity_profile is required before P1/P2 mutation ranking"
                if not profile else "enzyme identity or residue numbering is not confirmed enough for P1/P2 mutation ranking"
            )
        ),
        "protected_positions_from_profile": profile_positions,
    }
    if identity_gate["status"] == "blocked":
        tier1_count = 0
        tier2_count = 0

    # Candidate generation is an evidence decision, not a report convenience.
    # Coordinate-derived sequences and clear objectives may support QC output,
    # but they do not authorize mutation rows.  Require both confirmed identity
    # and an objective module that explicitly allows candidate output.
    exploratory_table_allowed = False
    if candidate_decision["candidate_output_allowed"]:
        candidate_table_status = "ready"
    else:
        candidate_table_status = candidate_decision["status"]

    for row in results:
        row["candidate_status"] = _candidate_status_for_row(
            row,
            candidate_table_status=candidate_table_status,
        )

    def _select_thermostability_diverse_rows(rows: list[dict], limit: int = 20) -> list[dict]:
        """Keep thermostability output mechanism-diverse instead of all surface charge flips."""
        if engineering_goal != "thermostability":
            return rows[:limit]
        quotas = {
            "surface_charge": 4,
            "gly_loop": 4,
            "core_packing": 4,
            "polar_surface": 3,
            "cys_risk": 2,
            "other": 3,
        }

        def bucket(row: dict) -> str:
            aa = str(row.get("wild_type") or "")
            if aa == "G":
                return "gly_loop"
            if aa == "C":
                return "cys_risk"
            if row.get("target_type") == "core_cavity":
                return "core_packing"
            if aa in {"K", "R", "D", "E", "H"}:
                return "surface_charge"
            if aa in {"S", "T", "N", "Q", "Y"}:
                return "polar_surface"
            return "other"

        selected: list[dict] = []
        counts: dict[str, int] = {}
        for row in rows:
            row_bucket = bucket(row)
            if counts.get(row_bucket, 0) >= quotas.get(row_bucket, 2):
                continue
            selected.append(row)
            counts[row_bucket] = counts.get(row_bucket, 0) + 1
            if len(selected) >= limit:
                return selected
        for row in rows:
            if row in selected:
                continue
            selected.append(row)
            if len(selected) >= limit:
                break
        return selected

    if candidate_table_status == "ready":
        tier1_output_source = _select_thermostability_diverse_rows(tier1, limit=12)
        tier2_output_source = _select_thermostability_diverse_rows(tier2, limit=12)
        tier1_summary_count = len(tier1_output_source)
        tier2_summary_count = len(tier2_output_source)
    elif exploratory_table_allowed:
        exploratory_source = _select_thermostability_diverse_rows([
            row
            for row in results
            if not row.get("is_protected") and row.get("recommended_mutations") and row["tier"] in {1, 2, 3}
        ], limit=20)
        tier1_output_source = []
        tier2_output_source = exploratory_source
        tier1_summary_count = 0
        tier2_summary_count = len(tier2_output_source)
    else:
        tier1_output_source = []
        tier2_output_source = []
        tier1_summary_count = 0
        tier2_summary_count = 0

    def _candidate_output(row: dict, *, exploratory: bool = False) -> dict:
        risk_flags = list(row.get("risk_flags", []))
        objective_missing_items = list(row.get("objective_missing_evidence", []))
        if exploratory:
            if identity_gate["status"] != "passed":
                reason = identity_gate.get("reason") or "enzyme identity or residue numbering is not confirmed"
                if reason not in objective_missing_items:
                    objective_missing_items.append(str(reason))
            if "探索性候选：只能用于首轮小批量单点验证，不能写成已验证改造结论" not in risk_flags:
                risk_flags.append("探索性候选：只能用于首轮小批量单点验证，不能写成已验证改造结论")
        return {
            "position": row["position"],
            "user_position": row.get("user_position"),
            "pdb_position": row.get("pdb_position"),
            "uniprot_position": row.get("uniprot_position"),
            "numbering_status": row.get("numbering_status"),
            "structure_feature_status": row.get("structure_feature_status"),
            "feature_completeness": row.get("feature_completeness"),
            "missing_feature_reasons": row.get("missing_feature_reasons", []),
            "ca_b_factor": row.get("ca_b_factor"),
            "nearest_catalytic_distance_ca_angstrom": row.get("nearest_catalytic_distance_ca_angstrom"),
            "contact_count_ca_8a": row.get("contact_count_ca_8a"),
            "nearest_ca_neighbor_distance_angstrom": row.get("nearest_ca_neighbor_distance_angstrom"),
            "nearest_ca_neighbor_position": row.get("nearest_ca_neighbor_position"),
            "nearest_ca_neighbor_pdb_position": row.get("nearest_ca_neighbor_pdb_position"),
            "ca_contact_environment": row.get("ca_contact_environment"),
            "secondary_structure": row.get("secondary_structure"),
            "secondary_structure_source": row.get("secondary_structure_source"),
            "rel_sasa": row.get("rel_sasa"),
            "residue_sasa_angstrom2": row.get("residue_sasa_angstrom2"),
            "rel_sasa_status": row.get("rel_sasa_status"),
            "pocket_channel_interface_status": row.get("pocket_channel_interface_status"),
            "nonpolymer_proximity_status": row.get("nonpolymer_proximity_status"),
            "nearest_nonpolymer_heteroatom_distance_angstrom": row.get("nearest_nonpolymer_heteroatom_distance_angstrom"),
            "nearest_nonpolymer_component_id": row.get("nearest_nonpolymer_component_id"),
            "nearest_nonpolymer_component_position": row.get("nearest_nonpolymer_component_position"),
            "nonpolymer_component_ids_within_4a": row.get("nonpolymer_component_ids_within_4a", []),
            "phi_deg": row.get("phi_deg"),
            "psi_deg": row.get("psi_deg"),
            "backbone_torsion_status": row.get("backbone_torsion_status"),
            "backbone_torsion_reason": row.get("backbone_torsion_reason"),
            "backbone_torsion_source": row.get("backbone_torsion_source"),
            "structure_feature_risk_flags": row.get("structure_feature_risk_flags", []),
            "wild_type": row["wild_type"],
            "objective_score": row["objective_score"],
            "candidate_status": _candidate_status_for_row(
                row,
                candidate_table_status=candidate_table_status,
                exploratory=exploratory,
            ),
            "composite_priority": row["composite_priority"],
            "tier": 2 if exploratory else row["tier"],
            "mutation_type": row["mutation_type"],
            "logic": row["logic"],
            "recommended_mutations": row["recommended_mutations"],
            "active_site_distance_residues": None if row["active_site_distance_residues"] == 999 else row["active_site_distance_residues"],
            "expected_effect": row["expected_effect"],
            "risk_flags": risk_flags,
            "experiment_action": row.get("experiment_action"),
            "experiment_priority": "P2-探索" if exploratory else row["experiment_priority"],
            "candidate_evidence_status": "computational_hypothesis",
            "calibration_evidence_status": row.get("calibration_evidence_status"),
            "objective_missing_evidence": objective_missing_items[:8],
            "blocked_upgrade_conditions": [
                "必须完成身份/编号或结构映射复核后，才可升级为正式 P1/P2 排名。",
                "必须有 WT 同批基线、目标性质 assay 和阴/阳性对照后，才可声称方向性改善。",
                "具体候选只有获得该突变体直接湿实验数据后，才可升级为 experimental_supported。",
            ] if exploratory else [],
            "lipase_position_evidence_count": row.get("lipase_position_evidence_count", 0),
        }

    tier1_output = [_candidate_output(r) for r in tier1_output_source]
    tier2_output = [_candidate_output(r, exploratory=exploratory_table_allowed) for r in tier2_output_source]
    experiment_source_rows = [
        row for row in (tier1_output + tier2_output)
        if _is_experiment_design_schedulable(row)
    ][:20]
    experiment_output = [
        {
            "experiment_priority": r["experiment_priority"],
            "tier": r["tier"],
            "position": r["position"],
            "user_position": r.get("user_position"),
            "pdb_position": r.get("pdb_position"),
            "uniprot_position": r.get("uniprot_position"),
            "numbering_status": r.get("numbering_status"),
            "structure_feature_status": r.get("structure_feature_status"),
            "feature_completeness": r.get("feature_completeness"),
            "missing_feature_reasons": r.get("missing_feature_reasons", []),
            "ca_b_factor": r.get("ca_b_factor"),
            "nearest_catalytic_distance_ca_angstrom": r.get("nearest_catalytic_distance_ca_angstrom"),
            "contact_count_ca_8a": r.get("contact_count_ca_8a"),
            "nearest_ca_neighbor_distance_angstrom": r.get("nearest_ca_neighbor_distance_angstrom"),
            "nearest_ca_neighbor_position": r.get("nearest_ca_neighbor_position"),
            "nearest_ca_neighbor_pdb_position": r.get("nearest_ca_neighbor_pdb_position"),
            "ca_contact_environment": r.get("ca_contact_environment"),
            "secondary_structure": r.get("secondary_structure"),
            "secondary_structure_source": r.get("secondary_structure_source"),
            "rel_sasa": r.get("rel_sasa"),
            "residue_sasa_angstrom2": r.get("residue_sasa_angstrom2"),
            "rel_sasa_status": r.get("rel_sasa_status"),
            "pocket_channel_interface_status": r.get("pocket_channel_interface_status"),
            "nonpolymer_proximity_status": r.get("nonpolymer_proximity_status"),
            "nearest_nonpolymer_heteroatom_distance_angstrom": r.get("nearest_nonpolymer_heteroatom_distance_angstrom"),
            "nearest_nonpolymer_component_id": r.get("nearest_nonpolymer_component_id"),
            "nearest_nonpolymer_component_position": r.get("nearest_nonpolymer_component_position"),
            "nonpolymer_component_ids_within_4a": r.get("nonpolymer_component_ids_within_4a", []),
            "phi_deg": r.get("phi_deg"),
            "psi_deg": r.get("psi_deg"),
            "backbone_torsion_status": r.get("backbone_torsion_status"),
            "backbone_torsion_reason": r.get("backbone_torsion_reason"),
            "backbone_torsion_source": r.get("backbone_torsion_source"),
            "structure_feature_risk_flags": r.get("structure_feature_risk_flags", []),
            "wild_type": r["wild_type"],
            "objective_score": r["objective_score"],
            "candidate_status": r.get("candidate_status"),
            "recommended_mutations": [m.get("mutation") for m in r.get("recommended_mutations", []) if m.get("mutation")],
            "mutation_logic": r["logic"],
            "expected_effect": r["expected_effect"],
            "risk_flags": r["risk_flags"],
            "experiment_action": r.get("experiment_action"),
            "candidate_evidence_status": r.get("candidate_evidence_status"),
            "calibration_evidence_status": r.get("calibration_evidence_status"),
            "objective_missing_evidence": r.get("objective_missing_evidence", []),
            "blocked_upgrade_conditions": r.get("blocked_upgrade_conditions", []),
        }
        for r in experiment_source_rows
    ]

    rows_by_position = {int(row["position"]): row for row in results if row.get("position")}
    specified_reviews: list[dict] = []
    for item in specified_items:
        pos = int(item["position"])
        observed = seq[pos - 1] if 1 <= pos <= n else None
        row = rows_by_position.get(pos)
        wild_type_match = observed == item["wild_type"] if observed else False
        is_protected = bool(row.get("is_protected")) if row else pos in active_positions
        risk_flags = list(row.get("risk_flags", [])) if row else []
        if not observed:
            risk_flags.append(f"position {pos} outside sequence range 1..{n}")
        elif not wild_type_match:
            risk_flags.append(f"wild-type mismatch: requested {item['wild_type']}{pos}, sequence has {observed}{pos}")
        if is_protected and "命中催化/功能保护位点，禁止作为首轮候选" not in risk_flags:
            risk_flags.append("命中催化/功能保护位点，禁止作为首轮候选")
        if not profile_ready:
            risk_flags.append("酶身份或编号未确认，指定突变不能升级为可排单候选")
        if objective_candidate_table_status != "ready":
            risk_flags.append("目标 assay 或 WT baseline 不足，指定突变只能作为 Watch 复核项")

        if not observed or not wild_type_match:
            decision = "blocked_numbering_mismatch"
        elif is_protected:
            decision = "no_go_protected_position"
        else:
            decision = "watch_review"

        tradeoff = "not_assessed"
        wt = item["wild_type"]
        mt = item["mutant"]
        if wt == "P" and mt == "T":
            tradeoff = (
                "Pro->Thr may release local backbone rigidity; if the residue is in a loop/channel gate, "
                "activity can improve while thermostability decreases. Treat as activity-stability trade-off."
            )
        elif "activity" in objective_signal_set and "thermostability" in objective_signal_set:
            tradeoff = "multi_objective_activity_stability_review_required"

        specified_reviews.append({
            "mutation": item["mutation"],
            "position": pos,
            "wild_type": item["wild_type"],
            "mutant": item["mutant"],
            "observed_wild_type": observed,
            "wild_type_match": wild_type_match,
            "is_protected": is_protected,
            "review_decision": decision,
            "candidate_row_matched": bool(row),
            "composite_priority": row.get("composite_priority") if row else None,
            "tier": row.get("tier") if row else None,
            "numbering_status": row.get("numbering_status") if row else "unknown",
            "pdb_position": row.get("pdb_position") if row else None,
            "uniprot_position": row.get("uniprot_position") if row else None,
            "activity_effect": row.get("expected_effect") if row else "requires substrate/reaction assay evidence",
            "stability_effect": "requires ddG/structure feature evidence",
            "tradeoff_interpretation": tradeoff,
            "risk_flags": risk_flags,
            "recommended_followup_actions": [
                "confirm residue numbering against user sequence/PDB/UniProt before wet-lab design",
                "measure WT and mutant in the same batch for activity, thermostability, expression, and purification quality",
                "if activity increases but stability drops, keep the activity-gain hypothesis and screen compensatory stability mutations before combinations",
            ],
            "evidence_level": "specified_mutation_review_computational_hypothesis",
        })

    return {
        "sequence_length": n,
        "sequence_preview": seq[:60] + ("..." if n > 60 else ""),
        "engineering_goal": engineering_goal,
        "objective_signals": objective_signal_list,
        "multi_objective": len(objective_signal_set) > 1,
        "ranking_mode": "activity_stability" if is_activity_stability else engineering_goal,
        "strategy": _build_engineering_strategy(
            engineering_goal,
            target_ph=target_ph,
            target_tm=target_tm,
            objective_signals=objective_signal_set,
        ),
        "target_ph": target_ph,
        "target_tm": target_tm,
        "uniprot_id": uniprot_id or None,
        "active_site_positions": active_positions,
        "active_site_position_sources": active_position_sources,
        "identity_gate": identity_gate,
        "objective_gate": {
            "status": objective_gate.get("status") if objective_gate else None,
            "objective": objective_gate.get("objective") if objective_gate else engineering_goal,
            "objective_signals": objective_gate.get("objective_signals") if objective_gate else objective_signal_list,
            "objective_modules": objective_gate.get("objective_modules") if objective_gate else [],
            "multi_objective": objective_gate.get("multi_objective") if objective_gate else len(objective_signal_set) > 1,
            "module": objective_gate.get("module") if objective_gate else None,
            "candidate_output_allowed": objective_gate.get("candidate_output_allowed") if objective_gate else True,
            "missing_evidence": objective_missing if isinstance(objective_missing, list) else [],
            "ranking_boundary": objective_gate.get("ranking_boundary") if objective_gate else None,
        },
        "candidate_decision": candidate_decision,
        "objective_score_contract": {
            "schema_version": _OBJECTIVE_SCORE_SCHEMA_VERSION,
            "activity_score": None,
            "stability_score": None,
            "specificity_score": None,
            "ph_profile_score": None,
            "expression_score": None,
            "risk_score": None,
            "score_components": {
                name: {
                    "type": "number_0_to_10_or_null",
                    "source": "all_positions[].objective_score.score_components",
                    "unknown_policy": "null_and_block",
                }
                for name in _OBJECTIVE_SCORE_NAMES
            },
            "evidence_level": "residue_level_computational_hypothesis",
            "confidence_level": "blocked_until_component_evidence_is_known",
            "assay_required": sorted({
                assay
                for row in results
                for assay in row.get("objective_score", {}).get("assay_required", [])
            }),
            "blocking_reason": [
                "objective scores are residue-level components; no total objective score is emitted",
                "unknown component or high risk is fail-closed",
            ],
            "multi_objective": len(objective_signal_set) > 1,
            "aggregation": "none",
        },
        "candidate_table_generation": _candidate_table_generation_contract(
            candidate_table_status=candidate_table_status,
            identity_gate=identity_gate,
            objective_gate=objective_gate,
            results=results,
            tier1_output=tier1_output,
            tier2_output=tier2_output,
            experiment_output=experiment_output,
            site_structure_features=site_structure_features,
        ),
        "p2_engineering_scorecard_contract": _p2_engineering_scorecard_contract(
            candidate_table_status=candidate_table_status,
            identity_gate=identity_gate,
            objective_gate=objective_gate,
            results=results,
            site_structure_features=site_structure_features,
        ),
        "p2_candidate_readiness_summary": _p2_candidate_readiness_summary(
            results=results,
            tier1_output=tier1_output,
            tier2_output=tier2_output,
            candidate_table_status=candidate_table_status,
        ),
        "p2_objective_score_readiness_summary": _p2_objective_score_readiness_summary(results=results),
        "p2_structure_feature_gap_summary": _p2_structure_feature_gap_summary(results=results),
        "p2_objective_assay_gap_summary": _p2_objective_assay_gap_summary(
            results=results,
            calibration_context=calibration_context,
        ),
        "candidate_table_status": candidate_table_status,
        "candidate_table_boundary": {
            "mode": "ready" if candidate_table_status == "ready" else ("exploratory" if exploratory_table_allowed else "blocked"),
            "evidence_level": "computational_hypothesis" if candidate_table_status != "blocked_by_identity_gate" else "blocked",
            "reason": (
                "full candidate table is ready for experimental planning"
                if candidate_table_status == "ready"
                else "exploratory candidates are allowed only because a valid sequence and clear engineering objective are present"
                if exploratory_table_allowed
                else "candidate generation requires a valid sequence plus a clear engineering objective and minimum identity context"
            ),
            "no_wet_lab_claim": True,
            "upgrade_requires": [
                "confirmed enzyme identity and residue numbering/mapping",
                "objective-specific WT baseline and assay controls",
                "direct wet-lab measurement for each proposed mutation before claiming improvement",
            ],
        },
        "summary": {
            "total_positions": n,
            "tier_1_count": tier1_summary_count,
            "tier_2_count": tier2_summary_count,
            "tier_3_count": (
                n - tier1_summary_count - tier2_summary_count
                if identity_gate["status"] == "passed"
                else 0
            ),
            "never_mutate_count": len(never_mutate),
            "never_mutate_positions": [r["position"] for r in never_mutate],
            "catalytic_guardrail_enabled": len(active_positions) > 0,
            "identity_gate_status": identity_gate["status"],
            "candidate_table_status": candidate_table_status,
        },
        "guardrails": {
            "protected_positions": active_positions,
            "sources": active_position_sources,
            "rule": "Protected catalytic positions and adjacent residues are penalized or blocked from recommendation.",
        },
        "lipase_evidence_context": lipase_evidence_context,
        "wet_lab_calibration_context": calibration_context,
        "specified_mutation_reviews": specified_reviews,
        "tier_1_candidates": tier1_output,
        "tier_2_candidates": tier2_output,
        "experiment_design_table": experiment_output,
        "all_positions": results if candidate_table_status == "ready" else [],
    }


# ===================================================================
# Registration
# ===================================================================

ToolRegistry.register(
    name="mutation_priority_score",
    description=(
        "Multi-dimensional mutation priority scoring for enzyme engineering. "
        "Scores every residue on 5 dimensions: surface exposure, distance from "
        "active site, evolutionary conservation, functional relevance, and "
        "predicted ΔΔG. Weights: ASA(0.20), Distance(0.25), Conservation(0.25), "
        "ΔΔG(0.15), Functional(0.15). Returns Tier 1 (>7.0) and Tier 2 (5.0-7.0) "
        "candidates with mutation positions, Chinese engineering logic, specific "
        "recommended mutations, and priority scores. "
        "Use for pH engineering, thermostability, or general mutation design."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sequence": {
                "type": "string",
                "description": "Amino acid sequence (single-letter code)",
            },
            "active_site_positions": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "1-indexed positions of known catalytic residues. "
                    "Residues at these positions are flagged as NEVER-MUTATE."
                ),
            },
            "target_ph": {
                "type": "number",
                "description": "Target optimal pH for enzyme engineering",
            },
            "target_tm": {
                "type": "number",
                "description": "Target melting temperature (°C) for thermostability engineering",
            },
            "engineering_goal": {
                "type": "string",
                "enum": ["ph_lowering", "ph_raising", "thermostability", "activity", "specificity", "general"],
                "description": "Engineering objective — determines mutation recommendations",
                "default": "general",
            },
            "objective_signals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "All detected engineering objectives; preserves multi-objective tasks in reports and gates.",
            },
            "family_conserved": {
                "type": "object",
                "description": (
                    "Known conserved motifs as {motif_name: [positions]}. "
                    "Residues in these positions get conservation score=0."
                ),
            },
            "uniprot_id": {
                "type": "string",
                "description": (
                    "Optional UniProt accession. If provided, the tool loads curated "
                    "catalytic residues from the local database and applies them as "
                    "hard mutation guardrails."
                ),
            },
            "identity_profile": {
                "type": "object",
                "description": "Optional enzyme_identity_profile output used to gate and protect key residues.",
            },
            "objective_module_plan": {
                "type": "object",
                "description": "Optional enzyme_objective_module_plan output. Blocks candidate tables unless candidate_output_allowed=true.",
            },
            "pdb_coordinate_mapping": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional residue_mapping_sifts rows used to project candidate rows back to uploaded PDB coordinates.",
            },
            "chain_id": {
                "type": "string",
                "description": "Input PDB chain identifier when sequence was recovered from an uploaded coordinate model.",
                "default": "A",
            },
            "sequence_provenance": {
                "type": "string",
                "description": "Sequence provenance, e.g. pdb_coordinate_derived, user_fasta, or uniprot.",
            },
            "site_structure_features": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Optional residue-level rows from build_site_structure_function_features. "
                    "They add CA geometry/mapping evidence and protected-site guardrails; "
                    "they do not prove mutation benefit."
                ),
            },
            "include_lipase_evidence": {
                "type": "boolean",
                "description": "Attach read-only KWB lipase literature evidence to recommended mutations.",
                "default": True,
            },
            "lipase_evidence_query": {
                "type": "string",
                "description": "Optional KWB lipase evidence search query, e.g. CALB, thermostability, D223G.",
            },
            "wet_lab_calibration_summary": {
                "type": "object",
                "description": (
                    "Optional project-level wet-lab calibration summary from experiment feedback. "
                    "Used only as ranking context; it must not be treated as direct validation "
                    "of any proposed mutation."
                ),
            },
            "specified_mutations": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional user-requested point mutations such as P338T. "
                    "The tool returns specified_mutation_reviews instead of silently omitting them."
                ),
            },
        },
        "required": ["sequence"],
    },
    handler=mutation_priority_score,
    category="engineering",
    timeout_seconds=60,
    errors=[
        {
            "reason": "invalid_input",
            "code": "SEQUENCE_TOO_SHORT",
            "when": "sequence length < 5 residues",
            "recovery": "Provide a protein sequence of at least 5 amino acids.",
        },
        {
            "reason": "validation_failed",
            "code": "INVALID_AA",
            "when": "sequence contains non-standard amino acid characters",
            "recovery": "Use only the 20 standard letters (ACDEFGHIKLMNPQRSTVWY).",
        },
    ],
)
