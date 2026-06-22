"""ChromaDB vector database for protein sequence semantic search.

Collections:
- sequences: protein sequences with metadata for similarity search
- literature: research paper abstracts (future RAG use)
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from chromadb import HttpClient, Collection
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: HttpClient | None = None
_collections: dict[str, Collection] = {}

SEQUENCE_COLLECTION = "protein_sequences"
LITERATURE_COLLECTION = "protein_literature"


def _get_client() -> HttpClient:
    global _client
    if _client is None:
        chroma_host = settings.REDIS_HOST  # chromadb runs on same host in docker-compose
        try:
            _client = HttpClient(
                host="localhost",
                port=8001,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            _client.heartbeat()
            logger.info("ChromaDB connected at localhost:8001")
        except Exception:
            logger.warning("ChromaDB unavailable — vector search disabled")
            _client = None
    return _client


def _get_collection(name: str) -> Collection | None:
    if name in _collections:
        return _collections[name]
    client = _get_client()
    if client is None:
        return None
    try:
        coll = client.get_or_create_collection(
            name=name,
            metadata={"description": f"Protein AI — {name}"},
        )
        _collections[name] = coll
        return coll
    except Exception as e:
        logger.warning("Failed to get/create ChromaDB collection '%s': %s", name, e)
        return None


# ---------------------------------------------------------------------------
# Simple protein sequence feature embedding (MVP)
# ---------------------------------------------------------------------------
# In production, replace with ESM2 embeddings. For MVP we use:
# 1. Amino acid composition (20-dim)
# 2. Sequence length normalized
# 3. Physicochemical properties (hydrophobicity, charge, etc.)
# Total: ~26 dimensional → adequate for basic similarity search

_AA_NAMES = list("ACDEFGHIKLMNPQRSTVWY")

_HYDROPHOBICITY = {
    "A": 1.8, "C": 2.5, "D": -3.5, "E": -3.5, "F": 2.8, "G": -0.4,
    "H": -3.2, "I": 4.5, "K": -3.9, "L": 3.8, "M": 1.9, "N": -3.5,
    "P": -1.6, "Q": -3.5, "R": -4.5, "S": -0.8, "T": -0.7, "V": 4.2,
    "W": -0.9, "Y": -1.3,
}

_CHARGE = {
    "A": 0, "C": 0, "D": -1, "E": -1, "F": 0, "G": 0,
    "H": 0.1, "I": 0, "K": 1, "L": 0, "M": 0, "N": 0,
    "P": 0, "Q": 0, "R": 1, "S": 0, "T": 0, "V": 0,
    "W": 0, "Y": 0,
}


def _sequence_embedding(sequence: str, length: int = 0) -> list[float]:
    """Compute a simple embedding vector for a protein sequence."""
    seq = sequence.upper().strip()
    if not seq:
        return [0.0] * 26

    n = len(seq)

    # Amino acid composition (20 dims)
    composition = [seq.count(aa) / n for aa in _AA_NAMES]

    # Normalized length
    norm_len = min(n / 500.0, 1.0)

    # Average hydrophobicity
    avg_hydro = sum(_HYDROPHOBICITY.get(aa, 0.0) for aa in seq) / n

    # Net charge density
    net_charge = sum(_CHARGE.get(aa, 0.0) for aa in seq) / n

    # Shannon diversity (sequence complexity)
    entropy = 0.0
    for aa in set(seq):
        p = seq.count(aa) / n
        entropy -= p * (p ** 0.5)  # simplified

    # Aromatic content
    aromatic = (seq.count("F") + seq.count("Y") + seq.count("W")) / n

    return composition + [norm_len, avg_hydro, net_charge, entropy, aromatic]


def _seq_hash(sequence: str) -> str:
    return hashlib.sha256(sequence.upper().encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_sequence(
    sequence: str,
    metadata: dict[str, Any] | None = None,
    seq_id: str | None = None,
) -> str | None:
    """Index a protein sequence. Returns the sequence ID or None if DB unavailable."""
    coll = _get_collection(SEQUENCE_COLLECTION)
    if coll is None:
        return None

    seq_id = seq_id or _seq_hash(sequence)
    embedding = _sequence_embedding(sequence)

    meta = metadata or {}
    meta["sequence_preview"] = sequence[:100]

    try:
        coll.upsert(
            ids=[seq_id],
            embeddings=[embedding],
            metadatas=[meta],
            documents=[sequence],
        )
        return seq_id
    except Exception as e:
        logger.warning("ChromaDB upsert failed: %s", e)
        return None


def search_similar_sequences(
    sequence: str,
    n_results: int = 10,
    min_similarity: float = 0.3,
) -> list[dict[str, Any]]:
    """Find sequences similar to the query sequence."""
    coll = _get_collection(SEQUENCE_COLLECTION)
    if coll is None:
        return []

    embedding = _sequence_embedding(sequence)

    try:
        results = coll.query(
            query_embeddings=[embedding],
            n_results=min(n_results, 50),
        )
    except Exception as e:
        logger.warning("ChromaDB query failed: %s", e)
        return []

    out = []
    if results["ids"] and results["ids"][0]:
        for i, sid in enumerate(results["ids"][0]):
            dist = results["distances"][0][i] if results.get("distances") else [0]
            similarity = 1.0 - (dist[i] if isinstance(dist, list) else dist)
            if similarity < min_similarity:
                continue
            meta = (results["metadatas"][0][i] or {}) if results.get("metadatas") else {}
            doc = (results["documents"][0][i] or "") if results.get("documents") else ""
            out.append({
                "id": sid,
                "similarity": round(similarity, 4),
                "sequence_preview": doc[:100] if doc else meta.get("sequence_preview", ""),
                "metadata": meta,
            })

    return out


def delete_sequence(seq_id: str) -> bool:
    """Remove a sequence from the index."""
    coll = _get_collection(SEQUENCE_COLLECTION)
    if coll is None:
        return False
    try:
        coll.delete(ids=[seq_id])
        return True
    except Exception:
        return False


def collection_stats() -> dict[str, Any]:
    """Return statistics about indexed sequences."""
    coll = _get_collection(SEQUENCE_COLLECTION)
    if coll is None:
        return {"available": False, "count": 0}
    try:
        return {"available": True, "count": coll.count()}
    except Exception:
        return {"available": False, "count": 0}
