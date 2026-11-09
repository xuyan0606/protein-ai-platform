"""ESM-2 protein language model for mutation effect prediction and embeddings.

Uses Meta's ESM-2 650M model via fair-esm for:
- Zero-shot mutation effect scoring (wild-type marginal log-odds ratio)
- Per-residue embedding extraction (1280-dim for 650M model)
- Per-sequence mean embeddings for downstream analysis

Model loads lazily on first call (~2.6GB download, ~30-60s on first run).
Subsequent calls reuse the cached model from shared ModelCache.
"""

from __future__ import annotations

import os
from app.tools.registry import ToolRegistry

_AA = list("ACDEFGHIKLMNPQRSTVWY")


def esm2_predict(
    sequence: str,
    mutations: list[str] | None = None,
    mode: str = "mutations",
) -> dict:
    """ESM-2 prediction — mutation effect scoring or embedding extraction.

    Args:
        sequence: Amino acid sequence (1-letter code)
        mutations: List of mutations in format 'A123G'. If mode='mutations'
                   requires explicit candidates when mode='mutations'.
        mode: 'mutations' (default) or 'embedding'

    Returns:
        Dict with mutation scores/embeddings and model metadata.
    """
    seq = sequence.strip().upper()

    # Validate sequence
    invalid = set(seq) - set(_AA)
    if invalid:
        return {
            "error": f"Invalid amino acids: {sorted(invalid)}",
            "valid_aa": "".join(_AA),
        }

    if len(seq) < 5:
        return {"error": "Sequence too short (minimum 5 residues)"}

    if mode == "embedding":
        try:
            from app.ml.embeddings import extract_embeddings
            return extract_embeddings(seq)
        except Exception as e:
            return {"error": f"ESM-2 embedding failed: {e}", "is_real_inference": False}

    elif mode == "mutations":
        if not mutations:
            return {
                "status": "blocked",
                "blocked_reason": "mutations_required",
                "required_inputs": ["mutations"],
                "message": "Provide explicit candidate substitutions, for example A1V. No mutation scan was performed.",
                "is_real_inference": False,
            }

        if os.getenv('ESM_SERVICE_URL', '').strip():
            from app.services.esm_service import score_with_service
            return score_with_service(seq, mutations)

        try:
            from app.ml.embeddings import score_mutations
            return score_mutations(seq, mutations)
        except Exception as e:
            return {
                "error": f"ESM-2 scoring failed: {e}",
                "is_real_inference": False,
            }

    else:
        return {"error": f"Unknown mode: {mode}. Use 'mutations' or 'embedding'."}


ToolRegistry.register(
    name="esm2_predict",
    description=(
        "ESM-2 protein language model (Meta, 650M parameters). "
        "Scores explicit candidates via zero-shot wild-type marginal log-odds ratio "
        "(unmasked WT context; score = log P(mt|WT) - log P(wt|WT)). "
        "This language-model preference does not predict thermostability, ΔΔG or ΔTm. "
        "Also extracts per-residue and per-sequence embeddings (1280-dim). "
        "First call downloads ~2.6GB model weights; subsequent calls use cached model."
    ),
    handler=esm2_predict,
    category="prediction",
    timeout_seconds=600,
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
                "description": "Explicit mutations in format 'A123G' (wt+position+mt). Required for mutation mode; missing candidates return blocked.",
            },
            "mode": {
                "type": "string",
                "description": "Prediction mode: 'mutations' or 'embedding'",
                "default": "mutations",
            },
        },
        "required": ["sequence"],
    },
    errors=[
        {
            "reason": "compute_error",
            "code": "MODEL_LOAD_FAILED",
            "when": "ESM-2 model fails to download or load into memory",
            "recovery": "Check internet connection for first-load. Ensure 8GB+ RAM available.",
        },
        {
            "reason": "timeout",
            "code": "FIRST_LOAD_TIMEOUT",
            "when": "First model download exceeds 600 seconds",
            "recovery": "Model weights are ~2.6GB. Check network speed or pre-download manually.",
        },
    ],
)
