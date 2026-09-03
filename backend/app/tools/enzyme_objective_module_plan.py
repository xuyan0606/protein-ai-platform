"""Objective-specific gates for enzyme engineering.

This tool translates the confirmed foundation profile into target-specific
analysis requirements.  It does not rank mutations; it decides whether a target
module is ready and what evidence is still missing.
"""

from __future__ import annotations

from typing import Any

from app.tools.registry import ToolRegistry


_OBJECTIVE_ALIASES = {
    "thermostability": {"thermostability", "thermal_stability", "heat_stability", "耐热", "热稳定"},
    "specific_activity": {"specific_activity", "activity", "catalytic_efficiency", "kcat", "比活", "酶活", "催化效率"},
    "substrate_specificity": {"substrate_specificity", "specificity", "底物特异性", "底物谱"},
    "ph_profile": {"ph_profile", "ph_lowering", "ph_raising", "ph", "optimal_ph", "最适ph", "ph活性谱"},
    "soluble_expression": {"soluble_expression", "solubility", "expression", "可溶", "表达", "包涵体"},
}


def _normalize_objective(value: str) -> str:
    lower = str(value or "").strip().lower()
    for canonical, aliases in _OBJECTIVE_ALIASES.items():
        if lower in {alias.lower() for alias in aliases}:
            return canonical
    for canonical, aliases in _OBJECTIVE_ALIASES.items():
        if any(alias.lower() in lower for alias in aliases):
            return canonical
    return "general"


def _unique_list(items: list[Any]) -> list[Any]:
    seen: set[str] = set()
    output: list[Any] = []
    for item in items:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output




def _foundation_ready(identity_profile: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if not isinstance(identity_profile, dict):
        return False, ["enzyme_identity_profile output is required."]
    missing: list[str] = []
    if identity_profile.get("identity_status") != "identified":
        missing.append("identity_status must be identified.")
    guardrail = identity_profile.get("guardrail", {})
    if not isinstance(guardrail, dict) or guardrail.get("status") != "ready":
        missing.append("guardrail.status must be ready.")
    if not identity_profile.get("protected_positions"):
        missing.append("protected catalytic/key positions are not available.")
    return not missing, missing


def _module_definition(objective: str) -> dict[str, Any]:
    if objective == "thermostability":
        return {
            "module": "thermostability",
            "primary_question": "Can stability improve while protected catalytic/functional residues and activity are retained?",
            "required_evidence": [
                "confirmed foundation profile and protected residues",
                "structure or reliable homolog model for buried/surface/loop classification",
                "baseline Tm, half-life, or residual activity assay condition",
            ],
            "candidate_mechanisms": [
                "surface salt-bridge or hydrogen-bond network",
                "loop rigidification such as Gly->Pro only outside protected regions",
                "hydrophobic core cavity filling after structure review",
                "disulfide engineering only with geometry and function-distance checks",
                "consensus/back-to-thermophile mutations within confirmed family",
            ],
            "validation_metrics": ["Tm/Tagg", "thermal half-life", "residual activity", "specific activity retention"],
            "forbidden_shortcuts": [
                "do not treat total activity after heat challenge as pure catalytic improvement",
                "do not introduce disulfides without structure geometry checks",
            ],
        }
    if objective == "specific_activity":
        return {
            "module": "specific_activity",
            "primary_question": "Does the mutation improve specific activity, kcat, or kcat/Km rather than expression or stability alone?",
            "required_evidence": [
                "confirmed catalytic residues and no-touch zone",
                "substrate identity and assay condition",
                "purified or protein-normalized activity data for feedback rounds",
            ],
            "candidate_mechanisms": [
                "second-shell active-site electrostatics",
                "substrate positioning residues outside catalytic core",
                "transition-state stabilization network",
                "flap/loop dynamics affecting substrate entry and product release",
                "remote candidates only with conservation/literature/structure-connectivity evidence",
            ],
            "validation_metrics": ["specific activity", "kcat", "Km", "kcat/Km", "protein concentration or purity"],
            "forbidden_shortcuts": [
                "do not interpret total broth/supernatant activity as catalytic improvement",
                "do not mutate catalytic residues unless the user explicitly requests mechanistic probing",
            ],
        }
    if objective == "substrate_specificity":
        return {
            "module": "substrate_specificity",
            "primary_question": "Does the mutation improve target/off-target substrate selectivity?",
            "required_evidence": [
                "target substrate and at least one off-target comparator substrate",
                "binding pocket or subsite definition",
                "assay conditions matched across substrates",
            ],
            "candidate_mechanisms": [
                "reshape binding pocket volume",
                "alter polar/hydrophobic complementarity",
                "add steric exclusion against non-target substrate",
                "adjust substrate-entry region without blocking access",
                "modify auxiliary substrate-binding domain only when domain evidence exists",
            ],
            "validation_metrics": ["kcat/Km_target", "kcat/Km_off_target", "selectivity ratio", "substrate batch metadata"],
            "forbidden_shortcuts": [
                "do not claim specificity from activity on one substrate",
                "do not use docking score alone as specificity evidence",
            ],
        }
    if objective == "ph_profile":
        return {
            "module": "ph_profile",
            "primary_question": "Is the goal optimum shift, window broadening, acid/base stability, or a single pH activity ratio?",
            "required_evidence": [
                "full pH-activity curve or explicit statement that only point-ratio data exists",
                "known catalytic acid/base residues and titratable second-shell residues",
                "pH stability/residual activity data separated from pH optimum data",
            ],
            "candidate_mechanisms": [
                "second-shell electrostatics around catalytic acid/base residues",
                "titratable His/Asp/Glu/Lys network near the active site",
                "local water/hydrogen-bond network near catalytic residues",
                "surface charge network only for pH stability, not direct optimum-shift claims",
            ],
            "validation_metrics": ["full pH curve", "fitted apparent pKa where appropriate", "pH incubation residual activity", "pH4.5/pH6.0 ratio"],
            "forbidden_shortcuts": [
                "do not call pH4.5/pH6.0 ratio improvement an optimum shift",
                "do not claim standard MD output gives catalytic pKa or pH optimum",
            ],
        }
    if objective == "soluble_expression":
        return {
            "module": "soluble_expression",
            "primary_question": "Does the variant improve soluble folded protein yield without damaging function?",
            "required_evidence": [
                "expression host and construct boundaries",
                "soluble/insoluble fraction data or purified yield",
                "functional assay after solubility improvement",
            ],
            "candidate_mechanisms": [
                "remove exposed hydrophobic patches outside functional sites",
                "reduce aggregation-prone motifs",
                "optimize surface charge and disorder boundaries",
                "consider signal peptide/propeptide/mature chain boundaries before mutating",
            ],
            "validation_metrics": ["soluble yield", "purity", "specific activity", "folding/aggregation assay"],
            "forbidden_shortcuts": [
                "do not treat total expression as soluble active enzyme",
                "do not redesign propeptide or signal peptide without construct evidence",
            ],
        }
    return {
        "module": "general",
        "primary_question": "The objective is not specific enough for target-module candidate design.",
        "required_evidence": ["clarify the engineering objective"],
        "candidate_mechanisms": [],
        "validation_metrics": [],
        "forbidden_shortcuts": ["do not run a generic mutation table for an unclear objective"],
    }


def _compact_module(objective: str) -> dict[str, Any]:
    module = _module_definition(objective)
    return {
        "objective": objective,
        "module": module.get("module"),
        "primary_question": module.get("primary_question"),
        "required_evidence": module.get("required_evidence", []),
        "candidate_mechanisms": module.get("candidate_mechanisms", []),
        "validation_metrics": module.get("validation_metrics", []),
        "forbidden_shortcuts": module.get("forbidden_shortcuts", []),
    }


def enzyme_objective_module_plan(
    objective: str,
    identity_profile: dict[str, Any] | None = None,
    assay_context: dict[str, Any] | None = None,
    objective_signals: list[str] | None = None,
) -> dict[str, Any]:
    """Return objective-specific evidence requirements and blocked shortcuts."""
    normalized = _normalize_objective(objective)
    module = _module_definition(normalized)
    ready, foundation_missing = _foundation_ready(identity_profile)
    context = assay_context if isinstance(assay_context, dict) else {}
    raw_signals = objective_signals
    if not isinstance(raw_signals, list):
        raw_signals = context.get("objective_signals") if isinstance(context.get("objective_signals"), list) else []
    canonical_signals = sorted({
        _normalize_objective(str(item))
        for item in raw_signals
        if str(item or "").strip()
    })
    if not canonical_signals:
        canonical_signals = [normalized]
    objective_modules = [_compact_module(item) for item in canonical_signals]

    missing = list(foundation_missing)
    def add_missing(item: str) -> None:
        if item not in missing:
            missing.append(item)

    if "specific_activity" in canonical_signals and not any(context.get(key) for key in ("specific_activity", "kcat", "km", "protein_normalized")):
        add_missing("specific activity/kcat/Km or protein-normalized assay context is required.")
    if "substrate_specificity" in canonical_signals and not (context.get("target_substrate") and context.get("off_target_substrate")):
        add_missing("target_substrate and off_target_substrate are required.")
    if "ph_profile" in canonical_signals and not (context.get("ph_curve") or context.get("point_ratio")):
        add_missing("Provide full pH curve or explicitly mark point_ratio-only evidence.")
    if "thermostability" in canonical_signals and not any(context.get(key) for key in ("tm", "half_life", "residual_activity")):
        add_missing("Provide baseline Tm, half-life, or thermal residual activity context.")

    combined_required_evidence = _unique_list([
        item
        for module_item in objective_modules
        for item in module_item.get("required_evidence", [])
    ])
    combined_validation_metrics = _unique_list([
        item
        for module_item in objective_modules
        for item in module_item.get("validation_metrics", [])
    ])
    combined_forbidden_shortcuts = _unique_list([
        item
        for module_item in objective_modules
        for item in module_item.get("forbidden_shortcuts", [])
    ])

    status = "ready" if ready and not missing else "blocked"
    return {
        "status": status,
        "objective": normalized,
        "objective_signals": canonical_signals,
        "multi_objective": len(canonical_signals) > 1,
        "objective_modules": objective_modules,
        "combined_required_evidence": combined_required_evidence,
        "combined_validation_metrics": combined_validation_metrics,
        **module,
        "forbidden_shortcuts": combined_forbidden_shortcuts or module.get("forbidden_shortcuts", []),
        "foundation_gate": {
            "status": "ready" if ready else "blocked",
            "missing": foundation_missing,
        },
        "missing_evidence": missing,
        "candidate_output_allowed": status == "ready",
        "ranking_boundary": (
            "Candidate ranking may proceed only under this objective module."
            if status == "ready"
            else "Return a补证据 plan; do not output mutation candidate tables."
        ),
        "claim_controls": [
            "Separate facts, evidence-backed inferences, design hypotheses, and wet-lab validation needs.",
            "Any formula/threshold not calibrated on this project must be marked DESIGN_HYPOTHESIS.",
        ],
    }


ToolRegistry.register(
    name="enzyme_objective_module_plan",
    description=(
        "Select and gate the objective-specific enzyme engineering module after "
        "Foundation Profile. Returns required evidence, allowed mechanisms, validation "
        "metrics, forbidden shortcuts, and whether candidate ranking is allowed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "objective": {"type": "string", "description": "Engineering objective: thermostability, activity, specificity, pH, solubility."},
            "objective_signals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "All detected engineering objectives; used to avoid collapsing multi-objective tasks into one target.",
            },
            "identity_profile": {"type": "object", "description": "enzyme_identity_profile output."},
            "assay_context": {"type": "object", "description": "Optional assay context such as substrates, pH curve, Tm, kcat/Km."},
        },
        "required": ["objective"],
    },
    handler=enzyme_objective_module_plan,
    category="analysis",
    timeout_seconds=30,
)
