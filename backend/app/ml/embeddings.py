"""ESM-2 embedding and zero-shot mutation scoring service.

Provides reusable functions for:
- Per-residue and per-sequence embeddings (1280-dim for 650M model)
- Zero-shot mutation effect scoring via masked marginal log-odds ratio
"""

from __future__ import annotations

import logging
import torch
import math
from app.ml.model_cache import ModelCache
from app.ml.config import ml_settings

logger = logging.getLogger(__name__)

# Standard amino acid list
_AA_LIST = list("ACDEFGHIKLMNPQRSTVWY")

# ESM-2 model variants and their embedding dimensions
_ESM_VARIANTS: dict[str, dict] = {
    "esm2_t6_8M_UR50D": {"params": "8M", "dim": 320, "layers": 6},
    "esm2_t12_35M_UR50D": {"params": "35M", "dim": 480, "layers": 12},
    "esm2_t30_150M_UR50D": {"params": "150M", "dim": 640, "layers": 30},
    "esm2_t33_650M_UR50D": {"params": "650M", "dim": 1280, "layers": 33},
}


def _load_esm2():
    """Load ESM-2 model and alphabet from fair-esm."""
    import esm

    model_name = ml_settings.ESM2_MODEL
    logger.info("Downloading/loading ESM-2 model: %s", model_name)
    model, alphabet = esm.pretrained.load_model_and_alphabet(model_name)
    model.eval()
    torch.set_num_threads(ml_settings.NUM_THREADS)
    return {"model": model, "alphabet": alphabet, "name": model_name}


def _get_esm2():
    """Get or load the ESM-2 model from shared cache."""
    cache = ModelCache.instance()
    return cache.get("esm2", _load_esm2)


def get_embedding_dim() -> int:
    variant = _ESM_VARIANTS.get(ml_settings.ESM2_MODEL, {})
    return variant.get("dim", 1280)


def get_mean_embedding(sequence: str) -> list[float]:
    """Compute the full mean embedding for a sequence (for vector DB indexing).

    Returns the raw 1280-dim float list — no preview, no per-residue details.
    """
    seq = sequence.strip().upper()
    n = len(seq)

    esm_data = _get_esm2()
    model = esm_data["model"]
    alphabet = esm_data["alphabet"]
    layer = ml_settings.ESM2_EMBEDDING_LAYER

    batch_converter = alphabet.get_batch_converter()
    _, _, batch_tokens = batch_converter([("query", seq)])

    with torch.no_grad():
        result = model(batch_tokens, repr_layers=[layer], return_contacts=False)
        representations = result["representations"][layer]

    per_residue = representations[0, 1 : n + 1]  # [L, D]
    mean_emb = per_residue.mean(dim=0)  # [D]
    return [float(v) for v in mean_emb.tolist()]


def extract_embeddings(sequence: str) -> dict:
    """Extract per-residue and mean embeddings using ESM-2.

    Returns:
        dict with per_residue embeddings (list of [position, aa, emb_preview]),
        mean_embedding, embedding_dim, model name, and sequence_length.
    """
    seq = sequence.strip().upper()
    n = len(seq)

    esm_data = _get_esm2()
    model = esm_data["model"]
    alphabet = esm_data["alphabet"]
    layer = ml_settings.ESM2_EMBEDDING_LAYER

    batch_converter = alphabet.get_batch_converter()
    _, _, batch_tokens = batch_converter([("query", seq)])

    with torch.no_grad():
        result = model(batch_tokens, repr_layers=[layer], return_contacts=False)
        representations = result["representations"][layer]  # [1, L+2, D]

    # Remove BOS/EOS tokens
    per_residue = representations[0, 1 : n + 1]  # [L, D]
    mean_emb = per_residue.mean(dim=0)  # [D]

    # Build per-residue preview (first 5 dims only, to keep output compact)
    residues = []
    for i in range(n):
        residues.append({
            "position": i + 1,
            "amino_acid": seq[i],
            "embedding_preview": [round(float(v), 4) for v in per_residue[i, :5].tolist()],
        })

    return {
        "sequence_length": n,
        "embedding_dim": per_residue.shape[1],
        "model": esm_data["name"],
        "layer": layer,
        "per_residue": residues,
        "mean_embedding_preview": [round(float(v), 4) for v in mean_emb[:20].tolist()],
    }


def score_mutations(sequence: str, mutations: list[str]) -> dict:
    """Score mutations using ESM-2 zero-shot masked marginal log-odds.

    score = log P(mt_aa | context) - log P(wt_aa | context)

    Positive score → mutation is favored over wild-type.
    Negative score → mutation is disfavored.
    """
    seq = sequence.strip().upper()
    n = len(seq)

    # Validate
    invalid = set(seq) - set(_AA_LIST)
    if invalid:
        raise ValueError(f"INVALID_AA: {''.join(sorted(invalid))}")

    esm_data = _get_esm2()
    model = esm_data["model"]
    alphabet = esm_data["alphabet"]

    batch_converter = alphabet.get_batch_converter()
    _, _, batch_tokens = batch_converter([("query", seq)])

    with torch.no_grad():
        output = model(batch_tokens)
        logits = output["logits"]  # [1, L+2, vocab_size]

    results = []
    for mut_str in mutations:
        mut_str = mut_str.strip()
        if not mut_str or len(mut_str) < 3:
            results.append({"mutation": mut_str, "error": "Invalid mutation format, expected e.g. A123G"})
            continue

        wt_aa = mut_str[0]
        mt_aa = mut_str[-1]
        pos_str = mut_str[1:-1]

        try:
            pos = int(pos_str)
        except ValueError:
            results.append({"mutation": mut_str, "error": f"Invalid position: {pos_str}"})
            continue

        if pos < 1 or pos > n:
            results.append({"mutation": mut_str, "error": f"Position {pos} out of range (1-{n})"})
            continue

        if seq[pos - 1] != wt_aa:
            results.append({
                "mutation": mut_str,
                "error": f"Wild-type mismatch: expected {seq[pos-1]} at position {pos}, got {wt_aa}",
            })
            continue

        if mt_aa not in _AA_LIST:
            results.append({"mutation": mut_str, "error": f"Invalid mutant amino acid: {mt_aa}"})
            continue

        wt_idx = alphabet.get_idx(wt_aa)
        mt_idx = alphabet.get_idx(mt_aa)

        # log_odds = log(p_mt) - log(p_wt)
        wt_logp = float(logits[0, pos, wt_idx])
        mt_logp = float(logits[0, pos, mt_idx])
        log_odds = round(mt_logp - wt_logp, 4)

        # Classify
        if log_odds > 1.0:
            prediction = "strongly_favored"
        elif log_odds > 0.0:
            prediction = "mildly_favored"
        elif log_odds > -1.0:
            prediction = "neutral"
        elif log_odds > -2.0:
            prediction = "disfavored"
        else:
            prediction = "strongly_disfavored"

        results.append({
            "mutation": mut_str,
            "position": pos,
            "wild_type": wt_aa,
            "mutant": mt_aa,
            "score": log_odds,
            "prediction": prediction,
            "method": "ESM-2 zero-shot log-odds",
        })

    return {
        "mutations": results,
        "model": esm_data["name"],
        "method": "zero-shot masked marginal probability ratio",
        "is_real_inference": True,
    }


def score_mutations_esm(
    sequence: str,
    mutations: list[tuple[int, str, str]],
) -> dict[tuple[int, str, str], float]:
    """Batch-score mutations using ESM-2 from a single forward pass.

    Args:
        sequence: wild-type amino acid sequence.
        mutations: list of (position_1based, wt_aa, mt_aa) tuples.

    Returns:
        Dict mapping (pos, wt, mt) → log_odds_score.
        Positive = mutation favored over wild-type.
        Negative = mutation disfavored.
    """
    seq = sequence.strip().upper()
    n = len(seq)

    invalid = set(seq) - set(_AA_LIST)
    if invalid:
        raise ValueError(f"INVALID_AA: {''.join(sorted(invalid))}")

    if not mutations:
        return {}

    esm_data = _get_esm2()
    model = esm_data["model"]
    alphabet = esm_data["alphabet"]

    batch_converter = alphabet.get_batch_converter()
    _, _, batch_tokens = batch_converter([("query", seq)])

    with torch.no_grad():
        output = model(batch_tokens)
        logits = output["logits"]  # [1, L+2, vocab_size]

    scores: dict[tuple[int, str, str], float] = {}
    for pos, wt, mt in mutations:
        if pos < 1 or pos > n:
            continue
        if seq[pos - 1] != wt:
            continue
        if mt not in _AA_LIST:
            continue
        wt_idx = alphabet.get_idx(wt)
        mt_idx = alphabet.get_idx(mt)
        wt_logp = float(logits[0, pos, wt_idx])
        mt_logp = float(logits[0, pos, mt_idx])
        scores[(pos, wt, mt)] = round(mt_logp - wt_logp, 4)

    return scores
