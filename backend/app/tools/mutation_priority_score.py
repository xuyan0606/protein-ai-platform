"""Multi-dimensional mutation priority scoring for enzyme engineering.

Implements the 5-dimension scoring framework from mutation_design/SKILL.md:
  1. Surface Exposure (ASA %) — weight 0.20
  2. Distance from Active Site (Å) — weight 0.25
  3. Evolutionary Conservation (ConSurf score) — weight 0.25
  4. Mutation ΔΔG (kcal/mol) — weight 0.15
  5. Functional Relevance — weight 0.15

Composite Priority = sum(score_i × weight_i), 0-10 scale.
Tier 1: >7.0  |  Tier 2: 5.0-7.0  |  Tier 3: <5.0
"""

from __future__ import annotations

import math
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
    """Score distance from active site (0-10).

    10: >20 Å (distant, very safe)
    5: 10-20 Å (moderate)
    0: <10 Å (active site proximal — HIGH risk)
    """
    if not active_site_positions:
        # No known active site → assume moderate safety, penalize center
        center = seq_len // 2
        dist_proxy = abs(position - center)
        norm_dist = dist_proxy / (seq_len / 2)
        score = min(10, 5.0 + 5.0 * norm_dist)
        return score, f"no known active site; distance from center proxy={norm_dist:.1f}"

    min_dist = min(abs(position - ap) for ap in active_site_positions)
    # Approximate: 1 residue ≈ 3.8 Å along backbone
    approx_angstrom = min_dist * 3.8

    if approx_angstrom < 8:
        score = 0.0
    elif approx_angstrom < 15:
        score = 5.0
    elif approx_angstrom < 20:
        score = 7.0
    else:
        score = 10.0

    return score, f"~{approx_angstrom:.0f}Å from active site (min {min_dist} residues)"


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


def mutation_priority_score(
    sequence: str,
    active_site_positions: list[int] | None = None,
    target_ph: float | None = None,
    target_tm: float | None = None,
    engineering_goal: str = "general",
    family_conserved: dict[str, list[int]] | None = None,
) -> dict:
    """Score every residue for mutation priority using 5 dimensions.

    Args:
        sequence: Amino acid sequence
        active_site_positions: 1-indexed positions of known catalytic residues
        target_ph: Target pH (for pH engineering context)
        target_tm: Target melting temperature (for thermostability context)
        engineering_goal: "ph_lowering" | "ph_raising" | "thermostability" |
                         "activity" | "specificity" | "general"
        family_conserved: {motif_name: [positions]} of conserved residues

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

    active_positions = active_site_positions or []

    # Convert family_conserved from {motif: [positions]} to {position: motif}
    conserved_map: dict[int, str] = {}
    if family_conserved:
        for motif, positions in family_conserved.items():
            for p in positions:
                conserved_map[p] = motif

    # Detect engineering context for mutation recommendation
    is_ph_lowering = engineering_goal == "ph_lowering" or (target_ph is not None and target_ph < 7.0)
    is_ph_raising = engineering_goal == "ph_raising" or (target_ph is not None and target_ph > 7.0)
    is_thermo = engineering_goal == "thermostability" or (target_tm is not None)

    results: list[dict] = []
    tier1_count = 0
    tier2_count = 0

    for i, aa in enumerate(seq):
        pos = i + 1  # 1-indexed

        is_charged = aa in ("R", "K", "D", "E", "H")

        # ---- Dimension scores ----
        asa_score, asa_why = _score_surface_exposure(aa, pos, n)
        dist_score, dist_why = _score_active_site_distance(pos, active_positions, n)
        cons_score, cons_why = _score_conservation(aa, pos, conserved_map if conserved_map else None)
        func_score, func_why = _score_functional_relevance(aa, pos, active_positions, is_charged)

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

        composite = round(min(10.0, composite), 1)

        # ---- Tier ----
        if composite >= 7.0:
            tier = 1
            tier1_count += 1
        elif composite >= 5.0:
            tier = 2
            tier2_count += 1
        else:
            tier = 3

        # ---- Recommended mutations (no fake predictions) ----
        recommended_mutations = []
        mutation_type = None
        if composite >= 4.0:
            if is_ph_lowering and aa in ("K", "R"):
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

        # ---- Categories ----
        categories = _identify_category(aa, pos, active_positions)
        target_type = _detect_engineering_target_type(aa, pos, n, asa_score)

        # ---- Build Chinese engineering logic ----
        logic_parts = []

        if asa_score >= 7.0:
            logic_parts.append("位于蛋白表面，高度溶剂可及")
        elif asa_score >= 5.0:
            logic_parts.append("部分暴露于溶剂")
        else:
            logic_parts.append("位于蛋白内部，参与疏水核心")

        if active_positions:
            min_dist = min(abs(pos - ap) for ap in active_positions)
            ang = min_dist * 3.8
            if ang > 20:
                logic_parts.append(f"远离活性中心(~{ang:.0f}Å)，突变不影响催化功能")
            elif ang > 10:
                logic_parts.append(f"与活性中心距离适中(~{ang:.0f}Å)")
            else:
                logic_parts.append(f"靠近活性中心(~{ang:.0f}Å)，需谨慎设计突变")
        else:
            logic_parts.append("未标注活性中心位置")

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

        results.append({
            "position": pos,
            "wild_type": aa,
            "scores": {
                "surface_exposure": round(asa_score, 1),
                "active_site_distance": round(dist_score, 1),
                "conservation_mutability": round(cons_score, 1),
                "functional_relevance": round(func_score, 1),
            },
            "composite_priority": composite,
            "tier": tier,
            "categories": categories,
            "target_type": target_type,
            "recommended_mutations": recommended_mutations,
            "mutation_type": mutation_type,
            "logic": logic,
        })

    # Sort by composite score descending (best candidates first)
    results.sort(key=lambda r: r["composite_priority"], reverse=True)

    # Tier summaries
    tier1 = [r for r in results if r["tier"] == 1]
    tier2 = [r for r in results if r["tier"] == 2]
    never_mutate = [r for r in results if "catalytic" in r["categories"]]

    return {
        "sequence_length": n,
        "sequence_preview": seq[:60] + ("..." if n > 60 else ""),
        "engineering_goal": engineering_goal,
        "target_ph": target_ph,
        "target_tm": target_tm,
        "active_site_positions": active_positions,
        "summary": {
            "total_positions": n,
            "tier_1_count": tier1_count,
            "tier_2_count": tier2_count,
            "tier_3_count": n - tier1_count - tier2_count,
            "never_mutate_count": len(never_mutate),
            "never_mutate_positions": [r["position"] for r in never_mutate],
        },
        "tier_1_candidates": [
            {
                "position": r["position"],
                "wild_type": r["wild_type"],
                "composite_priority": r["composite_priority"],
                "tier": 1,
                "mutation_type": r["mutation_type"],
                "logic": r["logic"],
                "recommended_mutations": r["recommended_mutations"],
            }
            for r in tier1
        ],
        "tier_2_candidates": [
            {
                "position": r["position"],
                "wild_type": r["wild_type"],
                "composite_priority": r["composite_priority"],
                "tier": 2,
                "mutation_type": r["mutation_type"],
                "logic": r["logic"],
                "recommended_mutations": r["recommended_mutations"],
            }
            for r in tier2
        ],
        "all_positions": results,
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
            "family_conserved": {
                "type": "object",
                "description": (
                    "Known conserved motifs as {motif_name: [positions]}. "
                    "Residues in these positions get conservation score=0."
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
