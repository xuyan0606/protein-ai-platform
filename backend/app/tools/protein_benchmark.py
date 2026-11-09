"""Protein benchmarking and comparative analysis tool.

Implements the protein_benchmarking SKILL.md protocol:
  1. Enzyme family identification (from BLAST results or user input)
  2. Multiple sequence alignment (simplified pairwise to reference)
  3. Conservation analysis (position-specific scoring)
  4. Structural feature comparison (MW, pI, composition vs family)
  5. Known engineering successes lookup per enzyme family

GH13 α-amylase family has built-in expert knowledge (catalytic residues,
Ca²⁺ binding sites, domain architecture, pH engineering examples).
"""

from __future__ import annotations

from app.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Enzyme family knowledge base
# ---------------------------------------------------------------------------

_KNOWN_FAMILIES: dict[str, dict] = {
    "GH13": {
        "name": "GH13 α-Amylase Family",
        "ec": "3.2.1.1",
        "mechanism": "Retaining (double displacement)",
        "catalytic_residues": {
            "nucleophile": "Asp",
            "acid_base": "Glu",
            "stabilizer": "Asp",
            "typical_positions": {
                "nucleophile": "~200-230 (β4 strand)",
                "acid_base": "~250-270 (β5 strand)",
                "stabilizer": "~290-310 (β7 strand)",
            },
        },
        "conserved_regions": [
            {"name": "Region I", "pattern": "D[AVL][IV][LN]H", "position": "β4"},
            {"name": "Region II", "pattern": "G[FY]R[LI][DN]A[AV]K[HN]", "position": "β5"},
            {"name": "Region III", "pattern": "E[IV]W[HN]", "position": "β5-β6 loop"},
            {"name": "Region IV", "pattern": "F[LI][VA][DN][NH]HD", "position": "β7"},
        ],
        "ca_binding_sites": [
            {"site": "Ca-I", "location": "between A and B domains", "ligands": ["D", "N", "D", "H2O"]},
            {"site": "Ca-II", "location": "A domain surface", "ligands": ["N", "D", "D", "H2O"]},
        ],
        "domain_architecture": [
            {"domain": "A", "fold": "(β/α)8 TIM barrel", "size": "~280 residues", "role": "catalytic core"},
            {"domain": "B", "fold": "variable", "size": "~40-80 residues", "role": "substrate specificity, pH sensitivity"},
            {"domain": "C", "fold": "β-sandwich", "size": "~80 residues", "role": "structural stability"},
        ],
        "known_engineering_successes": [
            {"mutation": "Surface K→E (multiple)", "effect": "pH optimum shifted from 6.5 to 5.0", "organism": "B. licheniformis"},
            {"mutation": "His→Asn near active site", "effect": "improved acid stability", "organism": "A. oryzae"},
            {"mutation": "Domain B loop deletion", "effect": "increased thermostability by 5°C", "organism": "B. stearothermophilus"},
            {"mutation": "SLKSK motif engineering", "effect": "altered substrate specificity", "organism": "Various"},
        ],
        "ph_engineering_targets": [
            "Domain B loop residues (~170-210)",
            "Surface residues near substrate binding cleft entrance",
            "Residues interacting with the catalytic acid/base Glu",
            "Ca²⁺-binding loop (DO NOT mutate coordinating residues)",
        ],
        "thermostability_targets": [
            "Cavity-filling in domain A core",
            "Gly→Pro in surface loops",
            "Additional Ca²⁺ binding sites",
            "Domain B-C interface salt bridges",
        ],
        "key_references": [
            "Nielsen et al. (2001) Protein Eng.",
            "Shaw et al. (1999) J. Mol. Biol.",
            "Bessler et al. (2003) Protein Sci.",
        ],
    },
    "GH11": {
        "name": "GH11 Xylanase Family",
        "ec": "3.2.1.8",
        "mechanism": "Retaining (double displacement)",
        "catalytic_residues": {
            "nucleophile": "Glu",
            "acid_base": "Glu",
        },
        "conserved_regions": [
            {"name": "Catalytic core", "pattern": "E[YF][IVL]", "position": "active site"},
        ],
        "known_engineering_successes": [
            {"mutation": "N-terminal region engineering", "effect": "pH optimum shift from 5.5 to 4.5", "organism": "T. reesei"},
        ],
    },
    "GH7": {
        "name": "GH7 Cellobiohydrolase Family",
        "ec": "3.2.1.176",
        "mechanism": "Retaining (double displacement)",
        "catalytic_residues": {
            "nucleophile": "Glu",
            "acid_base": "Glu",
        },
        "known_engineering_successes": [
            {"mutation": "Tunnel loop mutations", "effect": "improved processivity", "organism": "T. reesei Cel7A"},
        ],
    },
    "GH5": {
        "name": "GH5 Endoglucanase Family",
        "ec": "3.2.1.4",
        "mechanism": "Retaining (double displacement)",
        "catalytic_residues": {
            "nucleophile": "Glu",
            "acid_base": "Glu",
        },
    },
    "GH1": {
        "name": "GH1 β-Glucosidase Family",
        "ec": "3.2.1.21",
        "mechanism": "Retaining (double displacement)",
        "catalytic_residues": {
            "nucleophile": "Glu",
            "acid_base": "Glu",
        },
    },
}

# General glycoside hydrolase families (GH13 is the most common α-amylase)
_GH_FAMILY_HINT = {
    "amylase": "GH13",
    "glucosidase": "GH13 or GH1",
    "xylanase": "GH11",
    "cellulase": "GH5 or GH7",
    "cellobiohydrolase": "GH7",
    "endoglucanase": "GH5 or GH9",
    "pullulanase": "GH13",
    "cyclodextrin": "GH13",
}


# ---------------------------------------------------------------------------
# Amino acid property tables
# ---------------------------------------------------------------------------

_STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")

_KD: dict[str, float] = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5,
    "E": -3.5, "Q": -3.5, "G": -0.4, "H": -3.2, "I": 4.5,
    "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6,
    "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}

_AA_VOLUME: dict[str, float] = {
    "A": 88.6, "R": 173.4, "N": 117.7, "D": 111.1, "C": 108.5,
    "Q": 143.9, "E": 138.4, "G": 60.1, "H": 153.2, "I": 166.7,
    "L": 166.7, "K": 168.6, "M": 162.9, "F": 189.9, "P": 122.7,
    "S": 89.0, "T": 116.1, "W": 227.8, "Y": 193.6, "V": 140.0,
}

_PKA_SIDE: dict[str, float | None] = {
    "D": 3.86, "E": 4.25, "C": 8.33, "Y": 10.0,
    "H": 6.00, "K": 10.53, "R": 12.48,
}

# ConSurf-like conservation frequency (rare AA = more conserved)
_CONSERVATION_SCORE: dict[str, float] = {
    "W": 9.0, "C": 8.5, "H": 7.5, "M": 7.0, "F": 6.5, "Y": 6.0,
    "P": 5.5, "R": 5.0, "N": 4.5, "Q": 4.5, "D": 4.0, "E": 4.0,
    "G": 3.5, "K": 3.5, "T": 3.0, "S": 2.5, "A": 2.0, "I": 1.5,
    "V": 1.0, "L": 1.0,
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def protein_benchmark(
    query_sequence: str,
    homolog_sequences: list[dict] | None = None,
    known_family: str | None = None,
    enzyme_type: str | None = None,
    blast_results: list[dict] | None = None,
    identity_profile: dict | None = None,
) -> dict:
    """Benchmark a query protein against known homologs and enzyme families.

    Args:
        query_sequence: Query amino acid sequence
        homolog_sequences: List of {name, sequence} for known homologs
        known_family: Known enzyme family (e.g., "GH13", "GH11")
        enzyme_type: Type of enzyme for family hints (e.g., "amylase")
        blast_results: Pre-computed BLAST results [{name, identity, sequence, ...}]
        identity_profile: Optional enzyme_identity_profile output for family/key-residue gating

    Returns:
        Comprehensive benchmark report with family info, conservation analysis,
        structural comparison, and engineering recommendations.
    """
    seq = query_sequence.strip().upper()
    n = len(seq)

    # Validation
    if n < 10:
        raise ValueError(f"SEQUENCE_TOO_SHORT: {n} residues; minimum 10 required")
    invalid = set(seq) - _STANDARD_AA
    if invalid:
        raise ValueError(f"INVALID_AA: {''.join(sorted(invalid))}")

    # --- 1. Family Identification ---
    # This tool is a downstream explainer, not an identity caller.  Explicit
    # known_family/enzyme_type hints are kept as user context, but they must not
    # unlock family knowledge or engineering recommendations without a current
    # enzyme_identity_profile that passed the foundation/numbering gate.
    identity_summary = _extract_identity_profile(identity_profile)
    profile_ready = bool(identity_summary)
    family = _resolve_family_from_identity(identity_summary) if profile_ready else None
    family_info = _KNOWN_FAMILIES.get(family) if family else None
    family_label = family_info["name"] if family_info else None
    family_ec = family_info.get("ec") if family_info else None
    family_mechanism = family_info.get("mechanism") if family_info else None
    if identity_summary.get("family"):
        family_label = str(identity_summary.get("family"))
        family_ec = identity_summary.get("ec") or family_ec
        family_mechanism = identity_summary.get("family_superfamily") or family_mechanism
        family = family or None
    profile_key_residues = identity_summary.get("key_residues", [])
    profile_protected_positions = identity_summary.get("protected_positions", [])

    # --- 2. Property Computation ---
    properties = _compute_properties(seq)

    # --- 3. Conservation Analysis ---
    conservation = _analyze_conservation(seq)

    if not profile_ready:
        homolog_comparison = _compare_homologs(
            seq, properties, homolog_sequences or [], blast_results or []
        )
        return {
            "status": "blocked",
            "capability_status": "foundation_dependent_explainer",
            "evidence_level": "BLOCKED",
            "report_boundary": (
                "protein_benchmark 只解释已确认家族；enzyme_identity_profile 的身份、编号和保护位点门控未通过时，"
                "不得输出家族特异工程建议、催化残基或候选位点依据。"
            ),
            "query_info": {
                "length": n,
                "sequence_preview": seq[:60] + ("..." if n > 60 else ""),
            },
            "foundation_gate": {
                "status": "blocked",
                "reason": "enzyme_identity_profile_required",
                "message": (
                    "protein_benchmark only explains confirmed enzyme families. "
                    "Run annotation_bundle -> enzyme_identity_profile first, and pass a profile "
                    "with identity_status=identified and guardrail.status=ready."
                ),
                "user_supplied_context": {
                    "known_family": known_family,
                    "enzyme_type": enzyme_type,
                },
                "blocked_outputs": [
                    "family-specific motifs",
                    "catalytic residue prediction",
                    "domain architecture inference",
                    "engineering recommendations",
                    "known engineering successes",
                ],
            },
            "family": {"identified": None, "name": "Unknown enzyme family", "confidence": "none"},
            "properties": properties,
            "conservation_analysis": conservation,
            "homolog_comparison": homolog_comparison,
            "family_motifs": [],
            "catalytic_residues": {
                "known": False,
                "note": "Blocked until enzyme_identity_profile confirms family and numbering.",
            },
            "domain_architecture": [],
            "engineering_targets": {
                "ph_lowering": [],
                "thermostability": [],
                "activity_modulation": [],
                "never_mutate": [],
            },
            "benchmark_metrics": {
                "status": "blocked",
                "reason": "family_not_confirmed",
            },
            "known_engineering_successes": [],
            "identity_profile": None,
            "recommendations": [
                {
                    "priority": 0,
                    "category": "Foundation evidence required",
                    "action": "Resolve enzyme family, catalytic/key residues, and numbering before benchmarking.",
                    "plan": [
                        "Run annotation_bundle against curated/local data.",
                        "Run enzyme_identity_profile and verify identity_status=identified.",
                        "Confirm guardrail.status=ready before using family-specific engineering knowledge.",
                    ],
                }
            ],
        }

    # --- 4. Family-Specific Motif Search ---
    family_motifs = _search_family_motifs(seq, family_info) if family_info else []

    # --- 5. Homolog Comparison ---
    homolog_comparison = _compare_homologs(
        seq, properties, homolog_sequences or [], blast_results or []
    )

    # --- 6. Catalytic Residue Prediction ---
    catalytic = _predict_catalytic_residues(seq, family_info, identity_summary)

    # --- 7. Domain Architecture Annotation ---
    domains = _annotate_domains(n, family_info)

    # --- 8. Engineering Target Regions ---
    engineering_targets = _identify_engineering_targets(seq, family_info, properties)

    # --- 9. Benchmark Metrics ---
    benchmark = _compute_benchmark_metrics(properties, family_info)

    return {
        "capability_status": "foundation_dependent_explainer",
        "evidence_level": "IDENTITY_PROFILE_DERIVED",
        "report_boundary": (
            "仅用于解释已通过 enzyme_identity_profile 门控的家族/保守性背景；"
            "不能替代同源检索、结构编号映射、目标 assay 或湿实验验证。"
        ),
        "query_info": {
            "length": n,
            "sequence_preview": seq[:60] + ("..." if n > 60 else ""),
        },
        "family": {
            "identified": family or identity_summary.get("family_accession"),
            "name": family_label if family_label else "Unknown enzyme family",
            "ec": family_ec,
            "mechanism": family_mechanism,
            "confidence": "high" if family_info or identity_summary else "none",
            "source": "identity_profile" if identity_summary else ("curated_family" if family_info else None),
        } if (family_info or identity_summary) else {"identified": None, "name": "Unknown enzyme family", "confidence": "none"},
        "properties": properties,
        "conservation_analysis": conservation,
        "family_motifs": family_motifs,
        "catalytic_residues": catalytic,
        "domain_architecture": domains,
        "homolog_comparison": homolog_comparison,
        "engineering_targets": engineering_targets,
        "benchmark_metrics": benchmark,
        "known_engineering_successes": family_info.get("known_engineering_successes", []) if family_info else [],
        "identity_profile": {
            "family": identity_summary.get("family"),
            "ec": identity_summary.get("ec"),
            "protected_positions": profile_protected_positions,
            "key_residues": profile_key_residues[:10] if isinstance(profile_key_residues, list) else [],
            "source": "enzyme_identity_profile" if identity_summary else None,
        } if identity_summary else None,
        "recommendations": _generate_recommendations(
            family_info, properties, conservation, engineering_targets
        ),
    }


def _resolve_family_from_identity(identity_summary: dict) -> str | None:
    """Resolve built-in explanation pack only from confirmed identity evidence."""
    accession = str(identity_summary.get("family_accession") or "").upper()
    family_name = str(identity_summary.get("family") or "").upper()
    if accession == "IPR006046" or "GH13" in family_name or "ALPHA AMYLASE" in family_name:
        return "GH13"
    if "GH11" in family_name or "XYLANASE" in family_name:
        return "GH11"
    if "GH7" in family_name or "CELLOBIOHYDROLASE" in family_name:
        return "GH7"
    if "GH5" in family_name or "ENDOGLUCANASE" in family_name:
        return "GH5"
    if "GH1" in family_name or "GLUCOSIDASE" in family_name:
        return "GH1"
    return None


def _extract_identity_profile(identity_profile: dict | None) -> dict:
    """Extract a conservative identity summary from enzyme_identity_profile output."""
    if not isinstance(identity_profile, dict):
        return {}
    if str(identity_profile.get("identity_status") or "") != "identified":
        return {}
    guardrail = identity_profile.get("guardrail", {})
    if not isinstance(guardrail, dict) or str(guardrail.get("status") or "") != "ready":
        return {}

    family_candidates = identity_profile.get("family_candidates", [])
    ec_candidates = identity_profile.get("ec_candidates", [])
    top_family = family_candidates[0] if isinstance(family_candidates, list) and family_candidates and isinstance(family_candidates[0], dict) else {}
    top_ec = ec_candidates[0] if isinstance(ec_candidates, list) and ec_candidates and isinstance(ec_candidates[0], dict) else {}
    key_residues = identity_profile.get("key_residues", [])
    protected_positions = identity_profile.get("protected_positions", [])
    return {
        "family": top_family.get("name"),
        "family_accession": top_family.get("accession"),
        "family_confidence": top_family.get("confidence"),
        "family_superfamily": top_family.get("superfamily"),
        "ec": top_ec.get("ec"),
        "ec_name": top_ec.get("name"),
        "ec_confidence": top_ec.get("confidence"),
        "key_residues": key_residues if isinstance(key_residues, list) else [],
        "protected_positions": protected_positions if isinstance(protected_positions, list) else [],
        "missing_evidence": identity_profile.get("missing_evidence", []),
    }


def _compute_properties(seq: str) -> dict:
    """Compute basic physicochemical properties."""
    n = len(seq)

    # Molecular weight
    aa_mass = {
        "A": 89.09, "R": 174.20, "N": 132.12, "D": 133.10, "C": 121.16,
        "E": 147.13, "Q": 146.15, "G": 75.07, "H": 155.16, "I": 131.18,
        "L": 131.18, "K": 146.19, "M": 149.21, "F": 165.19, "P": 115.13,
        "S": 105.09, "T": 119.12, "W": 204.23, "Y": 181.19, "V": 117.15,
    }
    mw = sum(aa_mass.get(aa, 0) for aa in seq) - 18.015 * (n - 1)

    # pI (simplified)
    pI = _compute_pi(seq)

    # GRAVY
    gravy = sum(_KD.get(aa, 0) for aa in seq) / n

    # Composition
    composition = {aa: round(seq.count(aa) / n * 100, 1) for aa in sorted(set(seq))}

    # Charge counts
    acidic = seq.count("D") + seq.count("E")
    basic = seq.count("R") + seq.count("K") + seq.count("H")
    polar_uncharged = seq.count("N") + seq.count("Q") + seq.count("S") + seq.count("T")
    hydrophobic = seq.count("A") + seq.count("V") + seq.count("L") + seq.count("I") + \
                  seq.count("F") + seq.count("W") + seq.count("Y") + seq.count("M")
    special = seq.count("C") + seq.count("G") + seq.count("P")

    return {
        "molecular_weight_kda": round(mw / 1000, 2),
        "isoelectric_point": round(pI, 2),
        "gravy": round(gravy, 4),
        "amino_acid_composition": composition,
        "charge_distribution": {
            "acidic_D_E_pct": round((acidic / n) * 100, 1),
            "basic_R_K_H_pct": round((basic / n) * 100, 1),
            "polar_N_Q_S_T_pct": round((polar_uncharged / n) * 100, 1),
            "hydrophobic_pct": round((hydrophobic / n) * 100, 1),
            "special_C_G_P_pct": round((special / n) * 100, 1),
        },
        "surface_lys_arg_count": seq.count("K") + seq.count("R"),
        "surface_candidate_count": seq.count("K") + seq.count("R") + seq.count("D") + seq.count("E"),
        "gly_count": seq.count("G"),
        "pro_count": seq.count("P"),
        "cys_count": seq.count("C"),
    }


def _compute_pi(seq: str) -> float:
    """Iterative pI computation."""
    pka_n = 9.69
    pka_c = 2.34

    def net_charge(pH: float) -> float:
        q = 0.0
        q += 1.0 / (1.0 + 10 ** (pH - pka_n))
        q -= 1.0 / (1.0 + 10 ** (pka_c - pH))
        for aa in seq:
            pKa = _PKA_SIDE.get(aa)
            if pKa is None:
                continue
            if aa in ("D", "E", "C", "Y"):
                q -= 1.0 / (1.0 + 10 ** (pKa - pH))
            elif aa in ("H", "K", "R"):
                q += 1.0 / (1.0 + 10 ** (pH - pKa))
        return q

    lo, hi = 0.0, 14.0
    for _ in range(80):
        mid = (lo + hi) / 2
        q = net_charge(mid)
        if abs(q) < 1e-6:
            return round(mid, 2)
        if q > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 2)


def _analyze_conservation(seq: str) -> dict:
    """Per-residue conservation scoring (ConSurf-like 1-9 scale)."""
    n = len(seq)
    per_residue = []
    conserved_positions = []
    variable_positions = []

    for i, aa in enumerate(seq):
        score = _CONSERVATION_SCORE.get(aa, 5.0)
        if score >= 7.0:
            level = "highly_conserved"
            conserved_positions.append(i + 1)
        elif score >= 4.0:
            level = "moderately_conserved"
        else:
            level = "variable"
            variable_positions.append(i + 1)

        per_residue.append({
            "position": i + 1,
            "residue": aa,
            "conservation_score": score,
            "level": level,
        })

    return {
        "highly_conserved_count": len(conserved_positions),
        "variable_count": len(variable_positions),
        "conserved_positions": conserved_positions[:20],  # top 20
        "variable_positions": variable_positions[:20],
        "per_residue": per_residue,
        "color_code": "Red=conserved(7-9), Yellow=moderate(4-6), Green=variable(1-3)",
    }


def _search_family_motifs(seq: str, family_info: dict | None) -> list[dict]:
    """Search for known conserved motifs in the sequence."""
    if not family_info:
        return []

    motifs_found = []
    for region in family_info.get("conserved_regions", []):
        pattern = region.get("pattern", "")
        if not pattern:
            continue
        # Convert simple patterns to regex: [AVL] becomes [AVL], X becomes .
        import re
        regex_pat = pattern
        # Simple approach: search for the most conserved residues in the pattern
        core = ""
        for ch in pattern:
            if ch not in "[]()|":
                core += ch
        # Search for the core string (heuristic)
        idx = seq.find(core)
        if idx >= 0:
            motifs_found.append({
                "region": region["name"],
                "pattern": pattern,
                "found_at": f"positions {idx + 1}-{idx + len(core)}",
                "position_in_structure": region.get("position", "unknown"),
                "matched_sequence": seq[idx:idx + len(core)],
            })
        else:
            # Try a more lenient search: first 2 conserved chars
            if len(core) >= 2:
                idx = seq.find(core[:2])
                if idx >= 0:
                    motifs_found.append({
                        "region": region["name"],
                        "pattern": pattern,
                        "found_at": f"positions {idx + 1}-{idx + min(len(core), 8)} (partial match)",
                        "position_in_structure": region.get("position", "unknown"),
                        "matched_sequence": seq[idx:idx + min(len(core), 8)],
                        "match_quality": "partial",
                    })
                else:
                    motifs_found.append({
                        "region": region["name"],
                        "pattern": pattern,
                        "found_at": "not detected",
                        "note": "may be in a different region or the sequence is not a classical member",
                    })

    return motifs_found


def _predict_catalytic_residues(
    seq: str,
    family_info: dict | None,
    identity_summary: dict | None = None,
) -> dict:
    """Predict catalytic residue positions based on family knowledge."""
    if identity_summary and identity_summary.get("key_residues"):
        residues = []
        for item in identity_summary.get("key_residues", []):
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").lower()
            if "catalytic" not in role and "acid/base" not in role and "activates" not in role:
                continue
            residues.append({
                "role": item.get("role", "key residue"),
                "position": item.get("position"),
                "sequence": item.get("matched_sequence") or item.get("residue"),
                "residue": item.get("residue"),
                "source": "identity_profile",
            })
        if residues:
            return {
                "known": True,
                "family": identity_summary.get("family") or "identity_profile",
                "residues": residues,
            }

    if not family_info:
        return {"known": False, "note": "No family info available for catalytic prediction"}

    cat_info = family_info.get("catalytic_residues", {})
    typical_positions = cat_info.get("typical_positions", {})

    # For GH13: search for the conserved catalytic triad motifs
    catalytic = {"known": True, "family": family_info["name"], "residues": []}

    import re
    # GH13 nucleophile: D[AVL][IV][LN]H
    if "nucleophile" in typical_positions:
        for m in re.finditer(r"D[AVLI][IVL][LN]H", seq):
            catalytic["residues"].append({
                "role": "nucleophile",
                "position": m.start() + 1,
                "sequence": m.group(),
                "residue": "D",
            })
            break

    # GH13 acid/base: G[FY]R[LI][DN]A[AV]K[HN]
    if "acid_base" in typical_positions:
        for m in re.finditer(r"G[FY]R[LI][DN]A[AV]K[HN]", seq):
            catalytic["residues"].append({
                "role": "acid/base catalyst",
                "position": m.start() + 3,  # R is typically position 3 in motif
                "sequence": m.group(),
                "residue": "E",  # GH13: the actual catalytic acid is near this motif
            })
            break

    # GH13 stabilizer: F[LI][VA][DN][NH]HD
    if "stabilizer" in typical_positions:
        for m in re.finditer(r"F[LI][VA][DN][NH]HD", seq):
            catalytic["residues"].append({
                "role": "transition state stabilizer",
                "position": m.end() - 1,
                "sequence": m.group(),
                "residue": "D",
            })
            break

    return catalytic


def _annotate_domains(seq_len: int, family_info: dict | None) -> list[dict]:
    """Annotate domain architecture based on family knowledge."""
    domains = []

    if family_info and "domain_architecture" in family_info:
        for dom in family_info["domain_architecture"]:
            # Estimate domain bounds based on typical proportions
            size_range = dom.get("size", "")
            domains.append({
                "domain": dom["domain"],
                "fold": dom["fold"],
                "role": dom["role"],
                "estimated_region": f"Approximately {size_range} residues",
            })
    else:
        # Generic domain annotation
        if seq_len > 300:
            domains.append({
                "domain": "catalytic",
                "fold": "Likely (β/α)8 TIM barrel if glycoside hydrolase",
                "estimated_region": f"~{seq_len * 0.6:.0f} residues",
            })
            domains.append({
                "domain": "C-terminal",
                "fold": "Variable",
                "estimated_region": f"~{seq_len * 0.4:.0f} residues",
            })

    return domains


def _compare_homologs(
    query_seq: str, query_props: dict,
    homologs: list[dict], blast_results: list[dict],
) -> dict:
    """Compare query against known homologs and BLAST results."""
    comparison = {
        "reference_homologs": [],
        "blast_top_hits": [],
        "summary": "",
    }

    # Process explicit homologs
    for h in homologs[:10]:
        h_seq = h.get("sequence", "")
        if h_seq:
            identity = _compute_identity(query_seq, h_seq)
            h_props = _compute_properties(h_seq)
            comparison["reference_homologs"].append({
                "name": h.get("name", "unknown"),
                "identity_pct": identity,
                "length": len(h_seq),
                "molecular_weight_kda": h_props["molecular_weight_kda"],
                "isoelectric_point": h_props["isoelectric_point"],
                "gravy": h_props["gravy"],
            })

    # Process BLAST results
    for r in (blast_results or [])[:10]:
        comparison["blast_top_hits"].append({
            "name": r.get("name", r.get("accession", "unknown")),
            "identity_pct": r.get("identity", 0),
            "e_value": r.get("e_value", "N/A"),
            "description": r.get("description", ""),
        })

    # Summary
    if comparison["blast_top_hits"]:
        top_id = max(r["identity_pct"] for r in comparison["blast_top_hits"])
        comparison["summary"] = (
            f"Best BLAST hit: {comparison['blast_top_hits'][0]['name']} "
            f"({top_id:.1f}% identity). "
            f"Query pI={query_props['isoelectric_point']}, "
            f"MW={query_props['molecular_weight_kda']} kDa."
        )
    elif comparison["reference_homologs"]:
        comparison["summary"] = (
            f"Compared to {len(comparison['reference_homologs'])} reference homologs. "
            f"Best: {comparison['reference_homologs'][0]['identity_pct']:.1f}% identity."
        )
    else:
        comparison["summary"] = "No homolog or BLAST data for comparison."

    return comparison


def _compute_identity(seq1: str, seq2: str) -> float:
    """Compute sequence identity between two sequences."""
    if not seq1 or not seq2:
        return 0.0
    min_len = min(len(seq1), len(seq2))
    if min_len == 0:
        return 0.0
    matches = sum(1 for i in range(min_len) if seq1[i] == seq2[i])
    return round(matches / min_len * 100, 1)


def _identify_engineering_targets(
    seq: str, family_info: dict | None, properties: dict,
) -> dict:
    """Identify engineering target regions based on family knowledge."""
    n = len(seq)
    targets = {
        "ph_lowering": [],
        "thermostability": [],
        "activity_modulation": [],
        "never_mutate": [],
    }

    # pH lowering: surface K/R → candidates
    for i, aa in enumerate(seq):
        pos = i + 1
        if aa in ("K", "R"):
            # Heuristic: charged residues in N/C-terminal regions or flanked by hydrophilic
            is_surface_candidate = False
            # Check neighbors for hydrophilic context
            neighbors = ""
            if i > 0:
                neighbors += seq[i - 1]
            if i < n - 1:
                neighbors += seq[i + 1]
            hydrophilic_neighbors = sum(1 for na in neighbors if _KD.get(na, 0) < -1.0)
            if hydrophilic_neighbors >= 1:
                is_surface_candidate = True
            if pos <= n * 0.1 or pos >= n * 0.9:
                is_surface_candidate = True

            if is_surface_candidate:
                targets["ph_lowering"].append({
                    "position": pos,
                    "mutation": f"{aa}{pos}E",
                    "rationale": "Surface K/R→E for pH lowering",
                    "priority": "high" if pos <= n * 0.15 or pos >= n * 0.85 else "medium",
                })

    # Thermostability: Gly→Pro in loops
    for i, aa in enumerate(seq):
        pos = i + 1
        if aa == "G":
            # Gly flanked by non-Pro, non-Gly → likely in flexible loop
            flank_ok = True
            if i > 0 and seq[i - 1] in ("P", "G"):
                flank_ok = False
            if i < n - 1 and seq[i + 1] in ("P", "G"):
                flank_ok = False
            if flank_ok:
                targets["thermostability"].append({
                    "position": pos,
                    "mutation": f"G{pos}P",
                    "rationale": "Gly→Pro reduces backbone entropy, Tm +2-8°C",
                    "priority": "medium",
                })

    # Activity modulation: residues near (predicted) active site
    # Use family-specific targets
    if family_info and "ph_engineering_targets" in family_info:
        targets["ph_lowering_regions"] = family_info["ph_engineering_targets"]
    if family_info and "thermostability_targets" in family_info:
        targets["thermostability_regions"] = family_info["thermostability_targets"]

    # NEVER mutate: catalytic residues
    if family_info:
        cat_info = family_info.get("catalytic_residues", {})
        targets["never_mutate"].append({
            "category": "catalytic_triad",
            "residues": [
                cat_info.get("nucleophile", ""),
                cat_info.get("acid_base", ""),
                cat_info.get("stabilizer", ""),
            ],
            "reason": "Essential for catalysis — mutation abolishes activity",
        })
        if "ca_binding_sites" in family_info:
            targets["never_mutate"].append({
                "category": "ca_binding",
                "reason": "Ca²⁺ binding sites — mutation disrupts structural stability",
            })

    return targets


def _compute_benchmark_metrics(properties: dict, family_info: dict | None) -> dict:
    """Compute benchmark metrics against family standards."""
    metrics = {}

    # pI assessment for pH engineering
    pI = properties["isoelectric_point"]
    if pI > 7.0:
        metrics["ph_engineering"] = {
            "pI": pI,
            "assessment": "pI > 7 — surface charge engineering viable for pH lowering",
            "estimated_mutations_needed": f"{max(1, int((pI - 5.0) * 2))}-{max(2, int((pI - 5.0) * 3))} surface K/R→E",
        }
    elif pI < 5.0:
        metrics["ph_engineering"] = {
            "pI": pI,
            "assessment": "pI < 5 — surface charge engineering viable for pH raising",
            "estimated_mutations_needed": f"{max(1, int((7.0 - pI) * 2))}-{max(2, int((7.0 - pI) * 3))} surface D/E→K/R",
        }
    else:
        metrics["ph_engineering"] = {
            "pI": pI,
            "assessment": "pI in intermediate range — both directions possible",
        }

    # Thermostability assessment
    gly_count = properties.get("gly_count", 0)
    pro_count = properties.get("pro_count", 0)
    cys_count = properties.get("cys_count", 0)
    metrics["thermostability"] = {
        "gly_to_pro_candidates": gly_count,
        "existing_pro_stabilizers": pro_count,
        "disulfide_potential": "possible" if cys_count >= 2 else "need Cys pairs",
        "recommendation": (
            f"{gly_count} Gly residues are candidates for Pro substitution; "
            f"{'consider disulfide engineering' if cys_count >= 2 else 'introduce Cys pairs for disulfide stabilization'}"
        ),
    }

    # Family-specific benchmarks
    if family_info:
        metrics["family"] = family_info["name"]
        metrics["catalytic_residues"] = family_info.get("catalytic_residues", {})
        metrics["conserved_regions"] = len(family_info.get("conserved_regions", []))
        metrics["known_references"] = family_info.get("key_references", [])

    return metrics


def _generate_recommendations(
    family_info: dict | None, properties: dict,
    conservation: dict, targets: dict,
) -> list[dict]:
    """Generate prioritized engineering recommendations."""
    recs = []

    # pH engineering
    if targets.get("ph_lowering"):
        recs.append({
            "priority": 1,
            "category": "pH Engineering",
            "action": "Surface charge mutagenesis",
            "candidates": targets["ph_lowering"][:8],
            "rationale": f"pI={properties['isoelectric_point']:.1f} — "
                        f"mutating surface K/R→E can shift pH optimum downward by 1-2 units",
        })

    # Thermostability
    if targets.get("thermostability"):
        recs.append({
            "priority": 2,
            "category": "Thermostability Engineering",
            "action": "Gly→Pro in flexible loops",
            "candidates": targets["thermostability"][:8],
            "rationale": "Proline in loops reduces backbone conformational entropy",
        })

    # NEVER mutate
    if targets.get("never_mutate"):
        recs.append({
            "priority": 0,
            "category": "DO NOT MUTATE",
            "action": "Protect essential residues",
            "residues": targets["never_mutate"],
            "rationale": "These residues are essential for catalysis or structural integrity",
        })

    # Family-specific
    if family_info:
        recs.append({
            "priority": 3,
            "category": "Family-Specific Targets",
            "action": "Reference known engineering successes",
            "examples": family_info.get("known_engineering_successes", []),
            "key_references": family_info.get("key_references", []),
        })

    # Experimental validation
    recs.append({
        "priority": 4,
        "category": "Experimental Validation",
        "action": "Recommended screening pipeline",
        "plan": [
            "Primary: Activity assay at target and original pH (3 replicates)",
            "Secondary: kcat/Km for top 20% hits",
            "Tertiary: Tm and t1/2 measurement",
            "Final: Full kinetics + structure validation for top 3 candidates",
        ],
    })

    return recs


# ===================================================================
# Registration
# ===================================================================

ToolRegistry.register(
    name="protein_benchmark",
    description=(
        "Comparative protein benchmarking — identify enzyme family, analyze "
        "conservation patterns, search for conserved motifs, predict catalytic "
        "residues, map domain architecture, and generate engineering recommendations. "
        "Has built-in expert knowledge for GH13 α-amylase, GH11 xylanase, GH7 "
        "cellobiohydrolase, GH5 endoglucanase, and GH1 β-glucosidase families. "
        "Use this for deep enzyme characterization and comparative analysis."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query_sequence": {
                "type": "string",
                "description": "Amino acid sequence of the query protein (single-letter code)",
            },
            "known_family": {
                "type": "string",
                "description": "Known enzyme family if available (e.g., 'GH13', 'GH11', 'GH7')",
            },
            "enzyme_type": {
                "type": "string",
                "description": "Type of enzyme for family hint (e.g., 'amylase', 'xylanase', 'cellulase')",
            },
            "homolog_sequences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "sequence": {"type": "string"},
                    },
                },
                "description": "Known homolog sequences for comparison [{name, sequence}]",
            },
            "blast_results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "identity": {"type": "number"},
                        "e_value": {"type": "string"},
                        "sequence": {"type": "string"},
                    },
                },
                "description": "Pre-computed BLAST results for comparison",
            },
            "identity_profile": {
                "type": "object",
                "description": "Optional enzyme_identity_profile output used to gate family and catalytic residue claims.",
            },
        },
        "required": ["query_sequence"],
    },
    handler=protein_benchmark,
    category="analysis",
    timeout_seconds=60,
    errors=[
        {
            "reason": "invalid_input",
            "code": "SEQUENCE_TOO_SHORT",
            "when": "sequence length < 10 residues",
            "recovery": "Provide a protein sequence of at least 10 amino acids.",
        },
        {
            "reason": "validation_failed",
            "code": "INVALID_AA",
            "when": "sequence contains non-standard amino acid characters",
            "recovery": "Use only the 20 standard letters (ACDEFGHIKLMNPQRSTVWY).",
        },
    ],
)
