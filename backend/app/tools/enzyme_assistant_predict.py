"""Research-only enzyme assistant adapter: site candidates and mutant CDS.

The assistant behind this adapter has no model with thermostability predictive
power (ESM2 and ThermoMPNN both score at rho~0 for thermal deltas).  Its
activity scores are a soft harm-risk flag below the 0.5 gate, its candidates are
unranked, and its filters are a lower bound without structural coverage.  The
adapter therefore never presents output as a prediction or a ranking.
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

from app.tools.registry import ToolRegistry


_MUTATION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])(\d+)([ACDEFGHIKLMNPQRSTVWY])$")
_MUTATION_SEPARATORS = re.compile(r"[\s,;/+]+")

SCIENTIFIC_BOUNDARY = (
    "Research-only heuristic candidates from sequence-level motif filters and literature class priors. "
    "No model here predicts thermostability (ESM2 and ThermoMPNN both score rho~0 for thermal deltas); "
    "the ESM2-650M activity score is a soft harm-risk flag below its 0.5 validation gate. "
    "Candidates are unranked, carry no success probability, and require manual review."
)

_OFFSET_NOTE = (
    "Numbering is one-based from the translated input. For DNA input the translation includes the "
    "initiator methionine, so mature-protein numbering differs by the signal peptide offset."
)


def _service_url() -> str:
    return os.getenv("ENZYME_ASSISTANT_SERVICE_URL", "").strip().rstrip("/")


def _blocked(reason: str, status: str) -> dict[str, Any]:
    return {
        "status": status,
        "blocked_reason": reason,
        "evidence_level": "research_only_heuristic",
        "manual_review_required": True,
        "scientific_boundary": SCIENTIFIC_BOUNDARY,
    }


def _normalize_sequence(sequence: str) -> str:
    lines = [line.strip() for line in str(sequence).splitlines() if line.strip()]
    return "".join(line for line in lines if not line.startswith(">"))


async def _request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(f"{_service_url()}{path}", json=payload)
        response.raise_for_status()
        return response.json()


def _preflight(sequence: str) -> dict[str, Any] | None:
    if not sequence:
        return _blocked("A DNA or protein sequence is required.", "blocked_invalid_input")
    if not _service_url():
        return _blocked(
            "ENZYME_ASSISTANT_SERVICE_URL is not configured.",
            "blocked_model_service_unavailable",
        )
    return None


def _wrap(result: dict[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "evidence_level": "research_only_heuristic",
        "manual_review_required": True,
        "scientific_boundary": SCIENTIFIC_BOUNDARY,
        "numbering_note": _OFFSET_NOTE,
    }


async def _run(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return await _request(path, payload)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            detail = ""
            try:
                detail = str(exc.response.json().get("blocked_reason") or "")
            except ValueError:
                detail = ""
            return _blocked(
                detail or "The assistant rejected the input as invalid.",
                "blocked_invalid_input",
            )
        return _blocked(
            f"Enzyme assistant service request failed: {type(exc).__name__}",
            "blocked_model_service_unavailable",
        )
    except (httpx.HTTPError, ValueError) as exc:
        return _blocked(
            f"Enzyme assistant service request failed: {type(exc).__name__}",
            "blocked_model_service_unavailable",
        )


async def enzyme_assistant_recommend(
    sequence: str,
    goal: str = "both",
    n: int = 30,
    seed: int = 7,
    family: str = "",
) -> dict[str, Any]:
    """Return an unranked candidate set of single substitutions from a sequence."""
    normalized = _normalize_sequence(sequence)
    blocked = _preflight(normalized)
    if blocked:
        return blocked
    if goal not in {"both", "thermo"}:
        return _blocked("goal must be 'both' or 'thermo'.", "blocked_invalid_input")
    if not 1 <= int(n) <= 200:
        return _blocked("n must be between 1 and 200.", "blocked_invalid_input")
    payload: dict[str, Any] = {
        "sequence": normalized,
        "goal": goal,
        "n": int(n),
        "seed": int(seed),
        "use_esm": False,
        "nomination_mode": "rule_prior",
    }
    if family:
        payload["family"] = family
    result = await _run("/recommend", payload)
    if result.get("status") != "ok":
        return result
    return _wrap({**result, "ranked": False})


async def enzyme_assistant_build(
    sequence: str,
    mutations: list[str],
    family: str = "",
) -> dict[str, Any]:
    """Apply substitutions to a sequence and return the mutant protein and CDS."""
    normalized = _normalize_sequence(sequence)
    blocked = _preflight(normalized)
    if blocked:
        return blocked
    normalized_mutations: list[str] = []
    for item in mutations or []:
        for part in _MUTATION_SEPARATORS.split(str(item).strip().upper()):
            if not part or part in normalized_mutations:
                continue
            if not _MUTATION.fullmatch(part):
                return _blocked(
                    f"Invalid mutation {part}; expected A123V format.",
                    "blocked_invalid_mutation",
                )
            normalized_mutations.append(part)
    if not normalized_mutations:
        return _blocked("At least one mutation is required.", "blocked_invalid_input")
    payload: dict[str, Any] = {"sequence": normalized, "mutations": "+".join(normalized_mutations)}
    if family:
        payload["family"] = family
    result = await _run("/build", payload)
    if result.get("status") != "ok":
        return result
    return _wrap(result)


ToolRegistry.register(
    name="enzyme_assistant_recommend",
    description=(
        "Research-only: scan a DNA or protein sequence for single-substitution candidates using motif "
        "filters and literature class priors. Returns an unranked candidate set with no success "
        "probability and no thermostability prediction; manual review is required."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string"},
            "goal": {"type": "string", "enum": ["both", "thermo"], "default": "both"},
            "n": {"type": "integer", "minimum": 1, "maximum": 200, "default": 30},
            "seed": {"type": "integer", "default": 7},
            "family": {"type": "string"},
        },
        "required": ["sequence"],
    },
    handler=enzyme_assistant_recommend,
    is_async=True,
    category="engineering",
    timeout_seconds=190,
)

ToolRegistry.register(
    name="enzyme_assistant_build",
    description=(
        "Research-only: apply substitutions to a DNA or protein sequence and return the mutant protein "
        "plus, for DNA input, the mutant CDS with only the mutated codons replaced. Wild-type residues "
        "must match the supplied numbering; site filter results are reported but do not block."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sequence": {"type": "string"},
            "mutations": {"type": "array", "items": {"type": "string"}},
            "family": {"type": "string"},
        },
        "required": ["sequence", "mutations"],
    },
    handler=enzyme_assistant_build,
    is_async=True,
    category="engineering",
    timeout_seconds=190,
)
