"""Auditable sequence-level pH screening and intrinsic residue pKa profiling."""

from __future__ import annotations

from collections import Counter
import json
import os
import subprocess

from app.tools.registry import ToolRegistry


STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")
SIDECHAIN_PKA = {
    "D": 3.86,
    "E": 4.25,
    "H": 6.00,
    "C": 8.33,
    "Y": 10.07,
    "K": 10.53,
    "R": 12.48,
}
ACIDIC = {"D", "E", "C", "Y"}
PKA_N_TERM = 9.69
PKA_C_TERM = 2.34


def _net_charge(sequence: str, ph: float) -> float:
    charge = 1.0 / (1.0 + 10 ** (ph - PKA_N_TERM))
    charge -= 1.0 / (1.0 + 10 ** (PKA_C_TERM - ph))
    for aa in sequence:
        pka = SIDECHAIN_PKA.get(aa)
        if pka is None:
            continue
        if aa in ACIDIC:
            charge -= 1.0 / (1.0 + 10 ** (pka - ph))
        else:
            charge += 1.0 / (1.0 + 10 ** (ph - pka))
    return charge


def _isoelectric_point(sequence: str) -> float:
    low, high = 0.0, 14.0
    for _ in range(80):
        middle = (low + high) / 2
        if _net_charge(sequence, middle) > 0:
            low = middle
        else:
            high = middle
    return round((low + high) / 2, 2)


def _normalise_positions(positions: list[int] | None, length: int) -> list[int]:
    result = sorted(set(positions or []))
    invalid = [position for position in result if position < 1 or position > length]
    if invalid:
        raise ValueError(f"INVALID_POSITION: outside sequence bounds: {invalid}")
    return result


def ph_opt_predict(
    sequence: str,
    target_residues: list[int] | None = None,
    structure_pdb: str | None = None,
) -> dict:
    """Return a sequence titration profile without claiming a false activity optimum."""
    protein = "".join(sequence.split()).upper()
    if not protein:
        raise ValueError("EMPTY_SEQUENCE: protein sequence must not be empty")
    invalid = set(protein) - STANDARD_AA
    if invalid:
        raise ValueError(f"INVALID_AA: {''.join(sorted(invalid))}")

    positions = _normalise_positions(target_residues, len(protein))
    selected = positions or [
        index for index, aa in enumerate(protein, start=1) if aa in SIDECHAIN_PKA
    ]
    residue_profile = [
        {
            "position": position,
            "residue": protein[position - 1],
            "intrinsic_pka": SIDECHAIN_PKA.get(protein[position - 1]),
            "ionizable": protein[position - 1] in SIDECHAIN_PKA,
        }
        for position in selected
    ]
    curve = [
        {"ph": ph / 2, "net_charge": round(_net_charge(protein, ph / 2), 3)}
        for ph in range(4, 25)
    ]
    pka_values = [
        item["intrinsic_pka"] for item in residue_profile if item["intrinsic_pka"] is not None
    ]
    screening_range = None
    if pka_values:
        screening_range = [
            round(max(2.0, min(pka_values) - 1.0), 1),
            round(min(12.0, max(pka_values) + 1.0), 1),
        ]

    has_structure = bool(structure_pdb and structure_pdb.strip())
    engine_status = "degraded_sequence_only"
    engine_result = None
    engine_bin = os.getenv("PH_ENGINE_BIN", "").strip()
    sequence_model_bin = os.getenv("PHOPT_MODEL_RUNNER_BIN", "").strip()
    if has_structure and engine_bin:
        try:
            completed = subprocess.run(
                [engine_bin], input=json.dumps({"sequence": protein, "structure_pdb": structure_pdb}),
                text=True, capture_output=True, timeout=120, check=True,
            )
            engine_result = json.loads(completed.stdout)
            if not isinstance(engine_result, dict) or "predicted_optimal_ph" not in engine_result:
                raise ValueError("missing predicted_optimal_ph")
            engine_status = engine_result.get("status", "completed_structure_pka_prediction")
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
            engine_status = "degraded_structure_engine_failed"
    elif has_structure:
        engine_status = "degraded_structure_engine_unavailable"
    elif sequence_model_bin:
        try:
            completed = subprocess.run(
                [sequence_model_bin], input=json.dumps({"sequence": protein}),
                text=True, capture_output=True, timeout=120, check=True,
            )
            sequence_model_result = json.loads(completed.stdout)
            if not isinstance(sequence_model_result, dict) or sequence_model_result.get("status") != "completed":
                raise ValueError("invalid sequence model output")
            engine_result = sequence_model_result
            engine_status = "completed_experimental_label_model"
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
            engine_status = "degraded_sequence_model_failed"
    return {
        "sequence_length": len(protein),
        "isoelectric_point": _isoelectric_point(protein),
        "ionizable_residue_counts": dict(
            sorted((aa, count) for aa, count in Counter(protein).items() if aa in SIDECHAIN_PKA)
        ),
        "intrinsic_residue_pka": residue_profile,
        "charge_titration_curve": curve,
        "suggested_screening_ph_range": screening_range,
        "predicted_optimal_ph": engine_result.get("predicted_optimal_ph") if engine_result else None,
        "structure_supplied": has_structure,
        "status": engine_status,
        "engine_evidence": engine_result,
        "limitations": [
            "Sequence composition and intrinsic pKa values cannot determine catalytic pH optimum.",
            "The screening range guides wet-lab assays; it is not a predicted activity optimum.",
            "Install and validate a structure-level pKa engine before reporting residue environment shifts or mutation-induced pH changes.",
        ],
        "alternative_path": {
            "status": "available_without_optimal_ph_claim",
            "options": ["charge_titration_screen", "structure_pka_research_runtime", "wetlab_ph_activity_panel", "expert_review"],
            "boundary": "These options do not establish an experimentally validated optimal pH.",
        },
    }


ToolRegistry.register(
    name="ph_opt_predict",
    description=(
        "Generate an auditable protein charge titration and intrinsic residue pKa profile. "
        "Returns an explicit degraded status until a validated structure-level pKa engine is available."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string", "description": "Protein amino-acid sequence"},
            "target_residues": {
                "type": "array",
                "items": {"type": "integer", "minimum": 1},
                "description": "Optional one-based residue positions",
            },
            "structure_pdb": {
                "type": "string",
                "description": "Optional PDB text; recorded for gating but not silently approximated",
            },
        },
        "required": ["sequence"],
    },
    handler=ph_opt_predict,
    category="prediction",
    timeout_seconds=30,
)
