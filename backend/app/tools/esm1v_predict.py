"""ESM-1v mutation effect tool. Model weights are not wired in, so it reports an error instead of scores."""

from __future__ import annotations

from typing import Any

from app.tools.registry import ToolRegistry


def esm1v_predict(
    sequence: str,
    mutations: list[str] | None = None,
    scan_all: bool = False,
) -> dict[str, Any]:
    requested = len(mutations) if mutations else (len(sequence.strip()) * 19 if scan_all else 1)
    return {
        "error": "ESM-1v model is not connected; this tool returns no mutation scores.",
        "model": "ESM-1v",
        "is_real_inference": False,
        "mutations_requested": requested,
    }


ToolRegistry.register(
    name="esm1v_predict",
    description=(
        "ESM-1v zero-shot mutation effect tool. Currently returns an error because the "
        "ESM-1v model is not connected; it never returns estimated scores."
    ),
    handler=esm1v_predict,
    category="prediction",
    parameters={
        "type": "object",
        "properties": {
            "sequence": {
                "type": "string",
                "description": "Protein amino acid sequence (1-letter code)",
            },
            "mutations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Mutations to score in format 'A123G' (wt+position+mt).",
            },
            "scan_all": {
                "type": "boolean",
                "description": "Request all possible single-point mutations. Mutually exclusive with mutations list.",
                "default": False,
            },
        },
        "required": ["sequence"],
    },
)
