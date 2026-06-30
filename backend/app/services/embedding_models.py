"""Biomedical embedding models for literature RAG.

Wraps SPECTER2 (allenai/specter2-base) and BioBERT (dmis-lab/biobert-v1.1)
as ChromaDB-compatible EmbeddingFunction implementations.

- SPECTER2: scientific-paper-specialised transformer, 768-dim, mean pooling
- BioBERT:  biomedical-domain BERT, 768-dim, CLS-token pooling

Models are lazy-loaded on first use and cached for the process lifetime.
If transformers/torch are unavailable, a lightweight fallback (TF-IDF-style
hashing via ChromaDB's built-in default) is used automatically.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases matching chromadb.api.types (avoids importing chromadb at module
# level so this file stays importable in core-only containers without torch).
# ---------------------------------------------------------------------------
try:
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
except ImportError:  # pragma: no cover
    Documents = Sequence[str]  # type: ignore[misc]
    Embeddings = Sequence[Sequence[float]]  # type: ignore[misc]
    EmbeddingFunction = object  # type: ignore[misc,assignment]


# ---------------------------------------------------------------------------
# Singleton model cache (model_name -> (tokenizer, model))
# ---------------------------------------------------------------------------
_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}
_CACHE_LOCK = threading.Lock()


def _load_hf_model(model_name: str) -> tuple[Any, Any]:
    """Load a HuggingFace tokenizer+model pair, caching by model_name.

    Raises ImportError if transformers/torch are not installed.
    """
    with _CACHE_LOCK:
        if model_name in _MODEL_CACHE:
            return _MODEL_CACHE[model_name]

        from transformers import AutoTokenizer, AutoModel  # type: ignore[import-untyped]

        logger.info("Loading embedding model: %s", model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        model.eval()
        _MODEL_CACHE[model_name] = (tokenizer, model)
        logger.info("Embedding model ready: %s", model_name)
        return tokenizer, model


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class _HuggingFaceEmbedding(EmbeddingFunction):  # type: ignore[misc]
    """Base ChromaDB EmbeddingFunction backed by a HuggingFace transformer.

    Subclasses set MODEL_NAME and implement _pool().
    """

    MODEL_NAME: str = ""
    MAX_LENGTH: int = 512
    DIM: int = 768

    def __call__(self, input: Documents) -> Embeddings:  # type: ignore[override]
        try:
            tokenizer, model = _load_hf_model(self.MODEL_NAME)
        except Exception as e:
            logger.warning(
                "Cannot load %s (%s); falling back to hash embedding", self.MODEL_NAME, e
            )
            return _hash_fallback(input, self.DIM)

        import torch  # local import — not available in core-only container

        embeddings: list[list[float]] = []
        # Process in mini-batches to limit peak memory
        batch_size = 16
        for start in range(0, len(input), batch_size):
            batch = list(input[start : start + batch_size])
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.MAX_LENGTH,
                return_tensors="pt",
            )
            with torch.no_grad():
                outputs = model(**encoded)
            pooled = self._pool(outputs, encoded.get("attention_mask"))
            embeddings.extend(pooled.tolist())
        return embeddings

    # ---- pooling strategies -----------------------------------------------

    def _pool(self, outputs: Any, attention_mask: Any | None) -> Any:
        """Mean pooling over non-padding tokens (default for SPECTER2)."""
        import torch

        hidden = outputs.last_hidden_state  # (B, T, D)
        if attention_mask is not None:
            mask = attention_mask.unsqueeze(-1).float()  # (B, T, 1)
            summed = (hidden * mask).sum(dim=1)  # (B, D)
            counts = mask.sum(dim=1).clamp(min=1e-9)  # (B, 1)
            return summed / counts
        return hidden.mean(dim=1)


# ---------------------------------------------------------------------------
# Concrete models
# ---------------------------------------------------------------------------
class SPECTER2Embedding(_HuggingFaceEmbedding):
    """allenai/specter2-base — scientific paper embedding (mean pooling)."""

    MODEL_NAME = "allenai/specter2-base"
    MAX_LENGTH = 512
    DIM = 768


class BioBERTEmbedding(_HuggingFaceEmbedding):
    """dmis-lab/biobert-v1.1 — biomedical text embedding (CLS pooling)."""

    MODEL_NAME = "dmis-lab/biobert-v1.1"
    MAX_LENGTH = 512
    DIM = 768

    def _pool(self, outputs: Any, attention_mask: Any | None) -> Any:
        """CLS token pooling (standard for BERT-style models)."""
        return outputs.last_hidden_state[:, 0, :]


# ---------------------------------------------------------------------------
# Fallback: deterministic hash-based pseudo-embedding
# ---------------------------------------------------------------------------
def _hash_fallback(texts: Documents, dim: int = 768) -> Embeddings:
    """Generate deterministic pseudo-embeddings from text hashes.

    Used when transformers/torch are unavailable. Not semantically meaningful
    but keeps the pipeline functional for unit tests and lightweight setups.
    """
    import hashlib
    import math

    result: list[list[float]] = []
    for text in texts:
        h = hashlib.sha256(text.encode("utf-8", errors="replace")).digest()
        # Expand 32-byte hash to `dim` floats via cyclic reuse
        raw = list(h)
        vec: list[float] = []
        for i in range(dim):
            vec.append(float(raw[i % len(raw)]) / 255.0 - 0.5)
        # L2-normalise so cosine similarity is well-defined
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vec = [v / norm for v in vec]
        result.append(vec)
    return result


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_EMBEDDING_REGISTRY: dict[str, type[_HuggingFaceEmbedding]] = {
    "specter2": SPECTER2Embedding,
    "biobert": BioBERTEmbedding,
}

DEFAULT_EMBEDDING_MODEL = "specter2"


def get_embedding_function(model_name: str | None = None) -> EmbeddingFunction:
    """Return a ChromaDB-compatible embedding function by name.

    Args:
        model_name: one of "specter2", "biobert", or None (= default specter2).
                    Unknown names raise ValueError.

    Returns:
        An EmbeddingFunction instance (cached singleton per model).
    """
    name = (model_name or DEFAULT_EMBEDDING_MODEL).lower().strip()
    cls = _EMBEDDING_REGISTRY.get(name)
    if cls is None:
        valid = ", ".join(sorted(_EMBEDDING_REGISTRY))
        raise ValueError(f"Unknown embedding model '{name}'. Available: {valid}")
    return cls()


def list_embedding_models() -> list[str]:
    """Return names of registered embedding models."""
    return sorted(_EMBEDDING_REGISTRY)
