"""ThermoMPNN model-service adapter with fail-closed evidence contracts."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

from app.tools.registry import ToolRegistry


_MUTATION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])(\d+)([ACDEFGHIKLMNPQRSTVWY])$")


async def _request_predict(payload: dict[str, Any]) -> dict[str, Any]:
    base_url = os.getenv("THERMOMPNN_SERVICE_URL", "").rstrip("/")
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(f"{base_url}/predict", json=payload)
        response.raise_for_status()
        return response.json()


async def thermompnn_predict(
    pdb_data: str,
    mutations: list[str],
    sequence: str = "",
    chain_id: str = "A",
) -> dict[str, Any]:
    """Predict mutation ΔΔG through the separately versioned model service."""
    normalized_sequence = "".join(sequence.split()).upper()
    normalized_mutations = [str(item).strip().upper() for item in mutations]
    for mutation in normalized_mutations:
        match = _MUTATION.fullmatch(mutation)
        if not match:
            return {
                "status": "blocked_invalid_mutation",
                "model": "ThermoMPNN",
                "predictions": [],
                "blocked_reason": f"Invalid mutation {mutation}; expected A123V format.",
            }
        position = int(match.group(2))
        if normalized_sequence and (
            position > len(normalized_sequence) or normalized_sequence[position - 1] != match.group(1)
        ):
            return {
                "status": "blocked_sequence_mutation_mismatch",
                "model": "ThermoMPNN",
                "predictions": [],
                "blocked_reason": f"Mutation {mutation} does not match the supplied sequence numbering.",
            }
    if not pdb_data.strip() or not any(line.startswith("ATOM") for line in pdb_data.splitlines()):
        return {
            "status": "blocked_missing_structure",
            "model": "ThermoMPNN",
            "predictions": [],
            "blocked_reason": "ThermoMPNN requires a valid PDB structure.",
        }
    if not os.getenv("THERMOMPNN_SERVICE_URL", "").strip():
        return {
            "status": "blocked_model_service_unavailable",
            "model": "ThermoMPNN",
            "predictions": [],
            "blocked_reason": "THERMOMPNN_SERVICE_URL is not configured.",
        }

    payload = {"pdb_data": pdb_data, "mutations": normalized_mutations, "chain_id": chain_id}
    try:
        result = await _request_predict(payload)
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "status": "blocked_model_service_unavailable",
            "model": "ThermoMPNN",
            "predictions": [],
            "blocked_reason": f"ThermoMPNN service request failed: {type(exc).__name__}",
        }
    return {
        **result,
        "evidence_level": "model_inference",
        "manual_review_required": True,
        "scientific_boundary": (
            "ThermoMPNN predicts mutation stability change from structure; it does not predict absolute Tm, "
            "catalytic activity, expression yield, or experimental success."
        ),
    }


ToolRegistry.register(
    name="thermompnn_predict",
    description="Run real ThermoMPNN structure-based mutation ΔΔG inference through the configured model service.",
    parameters={
        "type": "object",
        "properties": {
            "pdb_data": {"type": "string"},
            "mutations": {"type": "array", "items": {"type": "string"}},
            "sequence": {"type": "string"},
            "chain_id": {"type": "string", "default": "A"},
        },
        "required": ["pdb_data", "mutations"],
    },
    handler=thermompnn_predict,
    is_async=True,
    category="stability",
    timeout_seconds=210,
)
