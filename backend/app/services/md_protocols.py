"""Curated GROMACS protocol templates for MD task setup."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_PROTOCOLS: dict[str, dict[str, Any]] = {
    "smoke_short": {
        "id": "smoke_short",
        "label": "Smoke short validation",
        "purpose": "Fast runtime validation for uploads, task plumbing, and artifact generation.",
        "recommended_for": ["PDB upload validation", "deployment smoke test", "small single-chain protein sanity check"],
        "risk_level": "low_runtime_low_scientific_confidence",
        "parameters": {
            "simulation_time_ns": 0.1,
            "equilibration_ps": 100.0,
            "temperature_k": 310.0,
            "pressure_bar": 1.0,
            "salt_concentration_m": 0.15,
            "ensemble": "npt",
            "force_field": "amber99sb-ildn",
            "water_model": "tip3p",
            "mdrun_threads": 1,
            "constraint_algorithm": "lincs",
            "constraints": "h-bonds",
            "coulombtype": "PME",
            "cutoff_scheme": "Verlet",
            "rcoulomb_nm": 1.0,
            "rvdw_nm": 1.0,
        },
        "scientific_controls": {
            "force_field_rationale": "AMBER99SB-ILDN is a conservative default for soluble protein backbone dynamics.",
            "water_model_rationale": "TIP3P is widely supported and compatible with the selected AMBER-family force field.",
            "system_preparation_checks": [
                "Confirm missing residues, alternate locations, and unresolved atoms before interpreting results.",
                "Confirm protonation states for catalytic residues and pH-sensitive residues.",
                "Confirm ligands, cofactors, metals, glycosylation, and disulfide bonds are intentionally retained or removed.",
            ],
            "cutoff_policy": {
                "coulombtype": "PME",
                "cutoff_scheme": "Verlet",
                "rcoulomb_nm": 1.0,
                "rvdw_nm": 1.0,
            },
            "constraint_policy": {
                "constraints": "h-bonds",
                "constraint_algorithm": "lincs",
                "timestep_ps": 0.002,
            },
            "replicate_policy": {
                "recommended_replicates": 1,
                "minimum_for_ranking": 3,
                "note": "Smoke runs validate pipeline behavior only; do not rank variants from a single sub-ns trajectory.",
            },
        },
        "interpretation_policy": {
            "minimum_publishable_ns": 10.0,
            "expected_confidence": "low",
            "review_note": "Use only to verify pipeline behavior. Do not treat as publication-grade MD.",
        },
    },
    "engineering_short": {
        "id": "engineering_short",
        "label": "Engineering short screen",
        "purpose": "Short comparative WT/mutant stability screen before committing GPU time.",
        "recommended_for": ["mutation triage", "small batch engineering review", "WT vs single mutant comparison"],
        "risk_level": "moderate_runtime_screening_only",
        "parameters": {
            "simulation_time_ns": 1.0,
            "equilibration_ps": 200.0,
            "temperature_k": 310.0,
            "pressure_bar": 1.0,
            "salt_concentration_m": 0.15,
            "ensemble": "npt",
            "force_field": "amber99sb-ildn",
            "water_model": "tip3p",
            "mdrun_threads": 2,
            "constraint_algorithm": "lincs",
            "constraints": "h-bonds",
            "coulombtype": "PME",
            "cutoff_scheme": "Verlet",
            "rcoulomb_nm": 1.0,
            "rvdw_nm": 1.0,
        },
        "scientific_controls": {
            "force_field_rationale": "AMBER99SB-ILDN is used for protein engineering triage where backbone stability is the main signal.",
            "water_model_rationale": "TIP3P keeps runtime and compatibility predictable for screening.",
            "system_preparation_checks": [
                "Review mutations near active sites, interfaces, termini, and flexible loops.",
                "Confirm protonation and histidine tautomers before comparing WT/mutant trajectories.",
                "Confirm ligand/cofactor treatment is consistent across all candidates.",
            ],
            "cutoff_policy": {
                "coulombtype": "PME",
                "cutoff_scheme": "Verlet",
                "rcoulomb_nm": 1.0,
                "rvdw_nm": 1.0,
            },
            "constraint_policy": {
                "constraints": "h-bonds",
                "constraint_algorithm": "lincs",
                "timestep_ps": 0.002,
            },
            "replicate_policy": {
                "recommended_replicates": 3,
                "minimum_for_ranking": 3,
                "note": "Use replicate agreement before promoting mutation candidates.",
            },
        },
        "interpretation_policy": {
            "minimum_publishable_ns": 10.0,
            "expected_confidence": "medium",
            "review_note": "Use for ranking and follow-up selection. Confirm top candidates with longer trajectories.",
        },
    },
    "production_review": {
        "id": "production_review",
        "label": "Production review candidate",
        "purpose": "Human-reviewed production candidate settings for real GPU execution.",
        "recommended_for": ["final candidate validation", "report-grade trajectory preparation"],
        "risk_level": "high_runtime_requires_expert_review",
        "parameters": {
            "simulation_time_ns": 10.0,
            "equilibration_ps": 500.0,
            "temperature_k": 310.0,
            "pressure_bar": 1.0,
            "salt_concentration_m": 0.15,
            "ensemble": "npt",
            "force_field": "amber99sb-ildn",
            "water_model": "tip3p",
            "mdrun_threads": 4,
            "constraint_algorithm": "lincs",
            "constraints": "h-bonds",
            "coulombtype": "PME",
            "cutoff_scheme": "Verlet",
            "rcoulomb_nm": 1.0,
            "rvdw_nm": 1.0,
        },
        "scientific_controls": {
            "force_field_rationale": "AMBER99SB-ILDN remains the default unless expert review selects CHARMM/OPLS/GROMOS for a specific chemistry.",
            "water_model_rationale": "TIP3P is compatible with the default protocol; switch only with explicit force-field review.",
            "system_preparation_checks": [
                "Resolve missing loops, termini caps, protonation, ligands, cofactors, metals, glycans, and disulfides.",
                "Check topology generation warnings manually before accepting production evidence.",
                "Run WT and candidate systems with matched seeds, box, salt, thermostat/barostat, and analysis windows.",
            ],
            "cutoff_policy": {
                "coulombtype": "PME",
                "cutoff_scheme": "Verlet",
                "rcoulomb_nm": 1.0,
                "rvdw_nm": 1.0,
            },
            "constraint_policy": {
                "constraints": "h-bonds",
                "constraint_algorithm": "lincs",
                "timestep_ps": 0.002,
            },
            "replicate_policy": {
                "recommended_replicates": 3,
                "minimum_for_ranking": 3,
                "note": "Report-grade conclusions require replicate consistency and expert topology review.",
            },
        },
        "interpretation_policy": {
            "minimum_publishable_ns": 10.0,
            "expected_confidence": "medium_to_high_after_replicates",
            "review_note": "Requires topology, protonation, cofactors, ligands, and replicate strategy review.",
        },
    },
}


def build_protocol_review(protocol_id: str | None, parameters: dict[str, Any]) -> dict[str, Any]:
    """Return scientific review guidance for resolved MD parameters."""
    protocol = get_md_protocol(protocol_id or "") if protocol_id else None
    controls = protocol.get("scientific_controls", {}) if protocol else {}
    simulation_time_ns = float(parameters.get("simulation_time_ns") or 0)
    recommended_replicates = int((controls.get("replicate_policy") or {}).get("recommended_replicates") or 1)
    warnings: list[str] = []
    if simulation_time_ns < 1:
        warnings.append("Trajectory is below 1 ns; use only as pipeline smoke evidence.")
    elif simulation_time_ns < 10:
        warnings.append("Trajectory is below 10 ns; use for screening only, not final claims.")
    if recommended_replicates < 3:
        warnings.append("Replicate policy is below ranking-grade; repeat before comparing candidates.")
    return {
        "protocol_id": protocol_id,
        "protocol_label": protocol.get("label") if protocol else None,
        "risk_level": protocol.get("risk_level") if protocol else "custom_unreviewed",
        "force_field": parameters.get("force_field"),
        "water_model": parameters.get("water_model"),
        "ensemble": parameters.get("ensemble"),
        "scientific_controls": controls,
        "review_warnings": warnings,
        "requires_expert_review": bool(simulation_time_ns >= 10 or (protocol and "requires_expert_review" in str(protocol.get("risk_level", "")))),
    }


def list_md_protocols() -> dict[str, Any]:
    """Return available MD protocol templates."""
    protocols = [deepcopy(value) for value in _PROTOCOLS.values()]
    return {
        "version": 1,
        "default_protocol_id": "smoke_short",
        "protocols": protocols,
    }


def get_md_protocol(protocol_id: str) -> dict[str, Any] | None:
    """Return one MD protocol template by id."""
    protocol = _PROTOCOLS.get(protocol_id)
    return deepcopy(protocol) if protocol else None


def resolve_md_protocol_parameters(protocol_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge allowed user overrides into one protocol parameter payload."""
    protocol = get_md_protocol(protocol_id)
    if protocol is None:
        raise KeyError(protocol_id)
    parameters = dict(protocol["parameters"])
    for key, value in (overrides or {}).items():
        if key in parameters and value is not None:
            parameters[key] = value
    return {
        "protocol_id": protocol_id,
        "parameters": parameters,
        "template": protocol,
        "protocol_review": build_protocol_review(protocol_id, parameters),
    }
