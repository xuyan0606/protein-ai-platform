"""Evidence-gated next-round planning for enzyme engineering feedback loops.

This is a constrained design planner, not a project-specific epistasis model.
It keeps the distinction explicit so small wet-lab datasets cannot be presented
as a trained mechanistic predictor.
"""

from __future__ import annotations

import itertools
from typing import Any

from app.services.experiment_feedback import analyze_feedback_payload, normalize_mutations
from app.tools.mutation_epistasis_check import mutation_epistasis_check
from app.tools.registry import ToolRegistry

NEXT_ROUND_LIBRARY_SCHEMA_VERSION = "next_round_library_design_v1"


def _record_interpretation(record: dict[str, Any]) -> dict[str, Any]:
    existing = record.get("interpretation_payload") or record.get("interpretation") or {}
    generated = analyze_feedback_payload(record)
    return {**generated, **existing}


def _single_mutation(record: dict[str, Any]) -> str | None:
    mutations = normalize_mutations(record.get("mutations") or [])
    return mutations[0] if len(mutations) == 1 else None


def _effect_matches_objective(effect: dict[str, Any], objective: str) -> bool:
    objective = (objective or "multi_objective").strip().lower()
    primary = effect.get("primary_effect")
    if objective in {"specific_activity", "catalytic_efficiency", "activity"}:
        return primary == "catalytic"
    if objective in {"stability", "thermostability", "ph_stability", "ion_tolerance"}:
        return bool(effect.get("supports_stability_gain"))
    if objective in {"expression", "solubility", "secretion"}:
        return bool(effect.get("supports_expression_gain"))
    return primary in {"catalytic", "stability_mediated", "expression_mediated"}


def _dataset_quality(records: list[dict[str, Any]], validated: list[dict[str, Any]]) -> dict[str, Any]:
    single_count = sum(1 for record in records if _single_mutation(record))
    direct_effect_count = sum(
        1
        for record in records
        if (_record_interpretation(record).get("effect_classification") or {}).get("primary_effect")
        in {"catalytic", "stability_mediated", "expression_mediated"}
    )
    completeness = direct_effect_count / max(len(records), 1)
    return {
        "single_mutant_records": single_count,
        "validated_single_mutants": len(validated),
        "effect_disambiguated_records": direct_effect_count,
        "effect_disambiguation_fraction": round(completeness, 3),
        "quality_level": (
            "high" if len(validated) >= 2 and completeness >= 0.75
            else "moderate" if validated
            else "low"
        ),
    }


def _exploration_policy(quality: dict[str, Any]) -> dict[str, Any]:
    """Transparent project-state policy, deliberately not a historical statistic."""
    validated = int(quality["validated_single_mutants"])
    completeness = float(quality["effect_disambiguation_fraction"])
    if validated < 2:
        return {
            "exploit_fraction": 1.0,
            "explore_fraction": 0.0,
            "reason": "Fewer than two validated orthogonal single mutants: complete the singleton evidence before combination or remote-region exploration.",
        }
    if completeness < 0.75:
        return {
            "exploit_fraction": 0.8,
            "explore_fraction": 0.2,
            "reason": "Phenotype mechanism is incompletely resolved: prioritize confirmation while reserving a small, evidence-gated exploration arm.",
        }
    return {
        "exploit_fraction": 0.7,
        "explore_fraction": 0.3,
        "reason": "At least two validated single mutants and sufficient phenotype separation: balance validated mechanisms with evidence-gated new mechanisms.",
        }


def _combination_evidence_contract(
    *,
    structural_distance_source: str,
    pair_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    pair_contracts: list[dict[str, Any]] = []
    missing_evidence: set[str] = set()
    must_not_claim: set[str] = {
        "trained_epistasis_model",
        "validated_combination_effect",
        "higher_order_combination_safety",
    }

    for item in pair_candidates:
        risk = item.get("epistasis_risk") or {}
        contract = risk.get("report_contract") or {}
        pairwise_risks = risk.get("pairwise_risks") or []
        pair_distance_sources = sorted({
            str(row.get("distance_source") or "not_available")
            for row in pairwise_risks
            if isinstance(row, dict)
        })
        missing = list(risk.get("required_missing_evidence") or contract.get("required_missing_evidence") or [])
        missing_evidence.update(str(entry) for entry in missing if entry)
        must_not_claim.update(str(entry) for entry in contract.get("must_not_claim") or [] if entry)
        pair_contracts.append({
            "mutations": item.get("mutations") or [],
            "label": item.get("label") or "unknown",
            "epistasis_recommendation": risk.get("recommendation") or "unknown",
            "distance_sources": pair_distance_sources or ["not_available"],
            "evidence_inputs": contract.get("evidence_inputs") or {},
            "required_missing_evidence": missing,
        })

    eligible_count = sum(
        1
        for item in pair_candidates
        if item.get("label") == "validated_singletons_pending_pair_test"
    )
    if not pair_candidates:
        status = "not_applicable_no_pair_candidates"
    elif eligible_count:
        status = "ready_with_epistasis_contract"
    else:
        status = "blocked_or_not_promoted"

    return {
        "schema_version": "next_round_combination_evidence_contract_v1",
        "status": status,
        "structural_distance_source": structural_distance_source,
        "pair_candidate_count": len(pair_candidates),
        "eligible_pair_candidate_count": eligible_count,
        "pair_contracts": pair_contracts,
        "required_missing_evidence": sorted(missing_evidence),
        "must_not_claim": sorted(must_not_claim),
        "boundary": (
            "Combination candidates must remain tied to the epistasis check contract. "
            "A promoted pair is still a controlled experiment proposal, not a validated "
            "combination effect or trained epistasis model output."
        ),
    }


def _next_round_library_design(
    *,
    objective: str,
    structural_distance_source: str,
    singletons: list[dict[str, Any]],
    pair_candidates: list[dict[str, Any]],
    remote_plan: list[dict[str, Any]],
    quality: dict[str, Any],
    policy: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible_pairs = [
        item
        for item in pair_candidates
        if item.get("label") == "validated_singletons_pending_pair_test"
    ]
    exploratory_remote = [
        item
        for item in remote_plan
        if item.get("state") == "eligible_exploratory_remote_site"
    ]
    positive_pair_feedback = [
        record
        for record in records
        if len(normalize_mutations(record.get("mutations") or [])) == 2
        and (_record_interpretation(record).get("decision") == "go")
    ]
    training_eligible_records = [
        record
        for record in records
        if (_record_interpretation(record).get("import_contract") or {}).get("training_eligible") is True
    ]

    if eligible_pairs:
        status = "ready_for_controlled_pair_library"
    elif singletons:
        status = "singletons_only_extend_validation"
    else:
        status = "blocked_no_validated_singletons"

    plate_layout: list[dict[str, Any]] = [
        {
            "well_group": "controls",
            "variants": ["WT", "parent_variant"],
            "replicates": 3,
            "purpose": "matched baseline, expression/QC and assay normalization",
        }
    ]
    if singletons:
        plate_layout.append(
            {
                "well_group": "validated_singletons",
                "variants": [item["mutation"] for item in singletons],
                "replicates": 3,
                "purpose": "reconfirm single-mutant effect under the next-round assay condition",
            }
        )
    if eligible_pairs:
        plate_layout.append(
            {
                "well_group": "controlled_pairs",
                "variants": ["+".join(item["mutations"]) for item in eligible_pairs],
                "replicates": 3,
                "purpose": "measure epistasis only after both singletons have direct positive evidence",
            }
        )
    if exploratory_remote:
        plate_layout.append(
            {
                "well_group": "exploratory_remote_sites",
                "variants": [str(item.get("candidate")) for item in exploratory_remote],
                "replicates": 2,
                "purpose": "small explicit exploration arm; not a high-confidence recommendation",
            }
        )

    return {
        "schema_version": NEXT_ROUND_LIBRARY_SCHEMA_VERSION,
        "status": status,
        "objective": objective,
        "structural_distance_source": structural_distance_source,
        "combination_evidence_contract": _combination_evidence_contract(
            structural_distance_source=structural_distance_source,
            pair_candidates=pair_candidates,
        ),
        "source_evidence": {
            "validated_single_mutants": len(singletons),
            "eligible_pair_candidates": len(eligible_pairs),
            "positive_pair_feedback_records": len(positive_pair_feedback),
            "training_eligible_feedback_records": len(training_eligible_records),
            "data_quality_level": quality.get("quality_level"),
        },
        "single_point_pool": [
            {
                "mutation": item["mutation"],
                "variant_name": item.get("variant_name"),
                "use": "reconfirm_or_parent_for_pair",
                "effect_classification": item.get("effect_classification"),
            }
            for item in singletons
        ],
        "combination_pool": [
            {
                "mutations": item["mutations"],
                "status": "eligible_controlled_pair",
                "evidence": "both_singletons_go_and_pairwise_structure_available",
                "epistasis_recommendation": item.get("epistasis_risk", {}).get("recommendation"),
                "distance_sources": sorted({
                    str(row.get("distance_source") or "not_available")
                    for row in (item.get("epistasis_risk", {}).get("pairwise_risks") or [])
                    if isinstance(row, dict)
                }) or ["not_available"],
                "epistasis_report_contract_status": (
                    item.get("epistasis_risk", {}).get("report_contract", {}) or {}
                ).get("schema_version", "unknown"),
            }
            for item in eligible_pairs
        ],
        "exploration_pool": exploratory_remote,
        "allocation_policy": policy,
        "higher_order_rule": {
            "status": "blocked" if not positive_pair_feedback else "pair_feedback_required_before_three_site_design",
            "rule": "Higher-order combinations require positive measured pair data; strong singletons alone are insufficient.",
        },
        "plate_layout": plate_layout,
        "assay_required": [
            "matched WT and parent controls in the same plate/batch",
            "replicate count recorded for every variant",
            "QC status recorded before training or model-upgrade use",
            "objective-specific metrics and assay condition key recorded for every row",
        ],
        "boundary": (
            "This is a next-round library design contract. It does not train a model, "
            "does not infer high-order epistasis, and does not promote candidates lacking "
            "direct singleton or strong external evidence."
        ),
    }


async def feedback_iteration_planner(
    feedback_records: list[dict[str, Any]],
    objective: str = "multi_objective",
    mechanism_tags: dict[str, list[str]] | None = None,
    structural_distances: dict[str, float] | None = None,
    residue_distance_graph: dict[str, Any] | None = None,
    same_region_groups: list[list[str]] | None = None,
    remote_candidates: list[dict[str, Any]] | None = None,
    allow_exploratory_combinations: bool = False,
) -> dict[str, Any]:
    """Plan the next wet-lab round from recorded feedback without overclaiming."""
    records = [record for record in feedback_records or [] if isinstance(record, dict)]
    if not records:
        return {
            "status": "blocked",
            "blocked_reason": "feedback_records_required",
            "required_inputs": ["feedback_records"],
        }

    mechanism_tags = mechanism_tags or {}
    structural_distances = structural_distances or {}
    same_region_groups = same_region_groups or []

    singletons: list[dict[str, Any]] = []
    unresolved_effects: list[str] = []
    for record in records:
        mutation = _single_mutation(record)
        if not mutation:
            continue
        interpretation = _record_interpretation(record)
        effect = interpretation.get("effect_classification") or {}
        if effect.get("primary_effect", "").startswith("unresolved"):
            unresolved_effects.append(mutation)
        if interpretation.get("decision") == "go" and _effect_matches_objective(effect, objective):
            singletons.append({
                "mutation": mutation,
                "variant_name": record.get("variant_name"),
                "effect_classification": effect,
                "metrics": record.get("metrics_payload") or {},
            })

    quality = _dataset_quality(records, singletons)
    policy = _exploration_policy(quality)
    feedback_by_mutation = {
        item["mutation"]: {"decision": "go", "metrics": item["metrics"]}
        for item in singletons
    }
    pair_candidates: list[dict[str, Any]] = []
    for left, right in itertools.combinations(singletons, 2):
        pair = [left["mutation"], right["mutation"]]
        risk = await mutation_epistasis_check(
            pair,
            mechanism_tags=mechanism_tags,
            structural_distances=structural_distances,
            residue_distance_graph=residue_distance_graph,
            same_region_groups=same_region_groups,
            single_mutant_feedback=feedback_by_mutation,
        )
        has_structure_distance = all(
            row.get("distance_angstrom") is not None
            for row in risk.get("pairwise_risks") or []
        )
        if risk["recommendation"] == "go" and has_structure_distance:
            label = "validated_singletons_pending_pair_test"
        elif allow_exploratory_combinations and risk["recommendation"] != "no_go":
            label = "exploratory_pair_requires_explicit_risk_acknowledgement"
        else:
            label = "not_promoted"
        pair_candidates.append({
            "mutations": pair,
            "label": label,
            "epistasis_risk": risk,
        })

    remote_plan: list[dict[str, Any]] = []
    for candidate in remote_candidates or []:
        if not isinstance(candidate, dict):
            continue
        has_evolution = bool(candidate.get("conservation_evidence") or candidate.get("literature_evidence"))
        has_connectivity = bool(candidate.get("structural_connectivity_evidence"))
        has_md_artifact = bool(candidate.get("md_artifact"))
        if has_evolution and (has_connectivity or has_md_artifact):
            state = "eligible_exploratory_remote_site"
        else:
            state = "insufficient_evidence_not_promoted"
        remote_plan.append({
            "candidate": candidate.get("mutation") or candidate.get("position"),
            "state": state,
            "required_evidence": [
                item for item, present in {
                    "conservation_or_literature_evidence": has_evolution,
                    "structural_connectivity_or_real_md_artifact": has_connectivity or has_md_artifact,
                }.items()
                if not present
            ],
        })

    required_measurements = [
        "Purified-enzyme specific activity or kcat/Km under matched WT and variant conditions.",
        "Target-condition and baseline-condition activity curves for pH/ion/solvent objectives.",
        "Protein-normalized concentration, soluble or secreted expression, and total activity.",
        "Tm or process-relevant half-life plus aggregation/degradation QC.",
        "Replicate count, dispersion, substrate, buffer, temperature, and assay time.",
    ]
    status = "ready" if quality["validated_single_mutants"] >= 2 else "single_mutant_first"
    structural_distance_source = (
        "residue_distance_graph_v1"
        if isinstance(residue_distance_graph, dict) and residue_distance_graph.get("schema_version") == "residue_distance_graph_v1"
        else "explicit_pairwise_distance_map" if structural_distances else "none"
    )
    return {
        "status": status,
        "planner_mode": "constrained_feedback_reweighting_not_trained_epistasis_model",
        "objective": objective,
        "structural_distance_source": structural_distance_source,
        "data_quality": quality,
        "exploration_policy": policy,
        "validated_singletons": singletons,
        "unresolved_effect_singletons": sorted(set(unresolved_effects)),
        "pair_candidates": pair_candidates,
        "remote_exploration": remote_plan,
        "next_round_library_design": _next_round_library_design(
            objective=objective,
            structural_distance_source=structural_distance_source,
            singletons=singletons,
            pair_candidates=pair_candidates,
            remote_plan=remote_plan,
            quality=quality,
            policy=policy,
            records=records,
        ),
        "combination_rule": (
            "Only pairs labelled validated_singletons_pending_pair_test are eligible for a controlled two-site experiment. "
            "Higher-order variants require positive pair data. Exploratory pairs are not high-confidence recommendations."
        ),
        "required_next_measurements": required_measurements,
        "scientific_boundary": (
            "This planner reweights candidates using wet-lab filters and explicit structural/mechanism evidence. "
            "It does not infer residue pKa, allosteric communication, or project-specific epistasis from sparse data."
        ),
    }


ToolRegistry.register(
    name="feedback_iteration_planner",
    description=(
        "Plan a second enzyme-engineering round from wet-lab records. Separates catalytic, "
        "stability-mediated, and expression-mediated signals; gates combination designs on "
        "validated singleton evidence and explicit epistasis/structure inputs."
    ),
    parameters={
        "type": "object",
        "properties": {
            "feedback_records": {"type": "array", "items": {"type": "object"}},
            "objective": {"type": "string", "default": "multi_objective"},
            "mechanism_tags": {"type": "object"},
            "structural_distances": {"type": "object"},
            "residue_distance_graph": {"type": "object"},
            "same_region_groups": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
            "remote_candidates": {"type": "array", "items": {"type": "object"}},
            "allow_exploratory_combinations": {"type": "boolean", "default": False},
        },
        "required": ["feedback_records"],
    },
    handler=feedback_iteration_planner,
    category="engineering",
    timeout_seconds=30,
)
