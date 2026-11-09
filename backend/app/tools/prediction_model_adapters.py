"""Fail-closed interfaces for unavailable Km and sequence-level Tm models."""

from __future__ import annotations

from collections import Counter

from app.tools.registry import ToolRegistry
from app.services.model_artifact_registry import configured_model, run_inference


STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")


def _sequence(sequence: str) -> str:
    protein = "".join(sequence.split()).upper()
    if not protein:
        raise ValueError("EMPTY_SEQUENCE: protein sequence must not be empty")
    invalid = set(protein) - STANDARD_AA
    if invalid:
        raise ValueError(f"INVALID_AA: {''.join(sorted(invalid))}")
    return protein


def km_predict(
    sequence: str,
    substrate_smiles: str,
    temperature_c: float | None = None,
    ph: float | None = None,
) -> dict:
    """Validate Km model inputs and refuse unvalidated numerical inference."""
    protein = _sequence(sequence)
    smiles = substrate_smiles.strip()
    if not smiles:
        raise ValueError("MISSING_SUBSTRATE: substrate_smiles must not be empty")
    if temperature_c is not None and not -10 <= temperature_c <= 120:
        raise ValueError("INVALID_TEMPERATURE: expected -10 to 120 C")
    if ph is not None and not 0 <= ph <= 14:
        raise ValueError("INVALID_PH: expected 0-14")
    readiness = configured_model("km")
    if readiness["status"] == "ready":
        inference = run_inference("km", {"sequence": protein, "substrate_smiles": smiles, "temperature_c": temperature_c, "ph": ph}, readiness)
        if inference["status"] in {"completed_model_prediction", "research_completed_model_prediction"}:
            output = inference["output"]
            return {"status": inference["status"], "sequence_length": len(protein), "substrate_smiles": smiles, "conditions": {"temperature_c": temperature_c, "ph": ph}, "predicted_km": output["prediction"], "unit": output.get("unit", "M"), "raw_prediction": output.get("raw_prediction"), "raw_unit": output.get("raw_unit"), "uncertainty": output["uncertainty"], "uncertainty_unit": output.get("uncertainty_unit"), "modeled_conditions": output.get("modeled_conditions", ["sequence", "substrate_smiles"]), "ignored_conditions": output.get("ignored_conditions", {}), "model_readiness": readiness}
        readiness = {**readiness, "inference": inference}
    blocked_status = readiness.get("inference", {}).get("status") if readiness["status"] == "ready" else readiness["status"]
    return {
        "status": blocked_status or "blocked_model_runtime_not_implemented",
        "sequence_length": len(protein),
        "substrate_smiles": smiles,
        "conditions": {"temperature_c": temperature_c, "ph": ph},
        "predicted_km": None,
        "unit": None,
        "model_readiness": readiness,
        "blocked_reason": "A validated Km artifact is not configured, or its runtime adapter is not implemented.",
        "required_action": "Register a versioned Km model, validate it on held-out enzyme-substrate pairs, then implement its inference adapter.",
        "alternative_path": {
            "status": "available_without_production_prediction",
            "options": ["research_only_smoke", "wetlab_km_assay", "expert_review"],
            "boundary": "Alternative paths do not produce a commercial Km estimate from this request.",
        },
    }


def tm_predict(sequence: str, ph: float | None = None) -> dict:
    """Return auditable sequence features while refusing an invented Tm value."""
    protein = _sequence(sequence)
    if ph is not None and not 0 <= ph <= 14:
        raise ValueError("INVALID_PH: expected 0-14")
    counts = Counter(protein)
    readiness = configured_model("tm")
    if readiness["status"] == "ready":
        inference = run_inference("tm", {"sequence": protein, "ph": ph}, readiness)
        if inference["status"] in {"completed_model_prediction", "research_completed_model_prediction"}:
            output = inference["output"]
            return {"status": inference["status"], "sequence_length": len(protein), "condition_ph": ph, "predicted_tm_c": output["prediction"], "uncertainty": output["uncertainty"], "unit": output.get("unit", "degC"), "modeled_conditions": output.get("modeled_conditions", ["sequence"]), "ignored_conditions": output.get("ignored_conditions", {}), "model_readiness": readiness}
        readiness = {**readiness, "inference": inference}
    blocked_status = readiness.get("inference", {}).get("status") if readiness["status"] == "ready" else readiness["status"]
    return {
        "status": blocked_status or "blocked_model_runtime_not_implemented",
        "sequence_length": len(protein),
        "condition_ph": ph,
        "sequence_features": {
            "proline_fraction": round(counts["P"] / len(protein), 4),
            "glycine_fraction": round(counts["G"] / len(protein), 4),
            "charged_fraction": round(sum(counts[aa] for aa in "DEKR") / len(protein), 4),
            "cysteine_count": counts["C"],
        },
        "predicted_tm_c": None,
        "model_readiness": readiness,
        "blocked_reason": "A validated Tm artifact is not configured, or its runtime adapter is not implemented.",
        "required_action": "Register a versioned Tm model, validate it on held-out data, then implement its inference adapter.",
        "alternative_path": {
            "status": "available_without_production_prediction",
            "options": ["research_only_smoke", "wetlab_thermal_shift_assay", "expert_review"],
            "boundary": "Alternative paths do not produce a commercial Tm estimate from this request.",
        },
    }


ToolRegistry.register(
    name="km_predict",
    description="Validate enzyme/substrate inputs for Km prediction and fail closed until a validated model is configured.",
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string"}, "substrate_smiles": {"type": "string"},
            "temperature_c": {"type": "number"}, "ph": {"type": "number"},
        },
        "required": ["sequence", "substrate_smiles"],
    },
    handler=km_predict,
    category="kinetics",
    timeout_seconds=30,
)

ToolRegistry.register(
    name="tm_predict",
    description="Validate sequence-level Tm inputs and fail closed until a validated predictive model is configured.",
    parameters={
        "type": "object",
        "properties": {"sequence": {"type": "string"}, "ph": {"type": "number"}},
        "required": ["sequence"],
    },
    handler=tm_predict,
    category="stability",
    timeout_seconds=30,
)
