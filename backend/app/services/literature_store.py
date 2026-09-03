"""Literature store — ChromaDB index for protein literature abstracts.

Activates the protein_literature collection (previously defined but unused in vectordb.py).
Provides semantic search over paper abstracts for RAG injection into agent responses.

Supports pluggable embedding models via app.services.embedding_models:
  - "specter2" (default): allenai/specter2-base, scientific-paper-specialised
  - "biobert":            dmis-lab/biobert-v1.1, biomedical-domain BERT
  - None:                 ChromaDB built-in default embedding (legacy)

Each embedding model uses its own ChromaDB collection so indexed vectors
remain consistent across searches.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from chromadb import HttpClient, Collection
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.services.embedding_models import (
    DEFAULT_EMBEDDING_MODEL,
    get_embedding_function,
    list_embedding_models,
)

logger = logging.getLogger(__name__)

# Base collection name; model suffix is appended when a biomedical model is used.
_BASE_COLLECTION_NAME = "protein_literature"


def _collection_name_for(embedding_model: str | None) -> str:
    """Return the ChromaDB collection name for the given embedding model."""
    if not embedding_model:
        return _BASE_COLLECTION_NAME
    return f"{_BASE_COLLECTION_NAME}_{embedding_model.lower().strip()}"


def _get_client() -> HttpClient | None:
    """Get ChromaDB HTTP client (same config as vectordb.py)."""
    try:
        client = HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        client.heartbeat()
        return client
    except Exception as e:
        logger.warning(
            "ChromaDB not available at %s:%s: %s",
            settings.CHROMA_HOST,
            settings.CHROMA_PORT,
            e,
        )
        return None


def _get_collection(
    embedding_model: str | None = DEFAULT_EMBEDDING_MODEL,
) -> Collection | None:
    """Get or create a protein_literature collection for the given embedding model.

    When ``embedding_model`` is set, the collection is created with the
    corresponding HuggingFace-backed EmbeddingFunction. When it is None,
    the collection uses ChromaDB's built-in default embedding (legacy behaviour).
    """
    client = _get_client()
    if client is None:
        return None

    name = _collection_name_for(embedding_model)
    kwargs: dict[str, Any] = {
        "name": name,
        "metadata": {
            "hnsw:space": "cosine",
            "description": f"Protein AI — {name}",
            "embedding_model": embedding_model or "default",
        },
    }

    try:
        return client.get_or_create_collection(**kwargs)
    except Exception as e:
        logger.warning("Failed to get/create ChromaDB collection '%s': %s", name, e)
        return None


class LiteratureStore:
    """ChromaDB-based literature index for protein science papers.

    Args:
        embedding_model: embedding backend to use. One of "specter2" (default),
            "biobert", or None for ChromaDB's built-in default. Each model
            maps to a separate collection so embeddings remain consistent.
    """

    def __init__(self, embedding_model: str | None = DEFAULT_EMBEDDING_MODEL):
        self.embedding_model = embedding_model
        self.collection_name = _collection_name_for(embedding_model)
        try:
            self.collection = _get_collection(embedding_model)
        except Exception:
            logger.warning("ChromaDB not available, literature store disabled")
            self.collection = None

    def is_available(self) -> bool:
        return self.collection is not None

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_papers(self, papers: list[dict]) -> int:
        """Index paper abstracts into ChromaDB.

        Args:
            papers: list of dicts with keys: pmid, title, authors, journal, year, abstract, doi, mesh_terms

        Returns:
            Number of papers indexed.
        """
        if not self.collection or not papers:
            return 0

        ids = []
        documents = []
        metadatas = []

        for paper in papers:
            pmid = paper.get("pmid", "")
            abstract = paper.get("abstract", "")
            title = paper.get("title", "")

            if not pmid or not (abstract or title):
                continue

            # Combine title + abstract for richer embedding
            doc_text = f"{title}\n\n{abstract}" if abstract else title

            ids.append(f"pmid_{pmid}")
            documents.append(doc_text)
            metadatas.append({
                "pmid": pmid,
                "title": title[:500],  # ChromaDB metadata has size limits
                "authors": json.dumps(paper.get("authors", []))[:500],
                "journal": (paper.get("journal") or "")[:200],
                "year": paper.get("year", 0) or 0,
                "doi": (paper.get("doi") or "")[:200],
                "mesh_terms": json.dumps(paper.get("mesh_terms", []))[:500],
                "embedding_model": (self.embedding_model or "default")[:50],
            })

        if ids:
            try:
                upsert_kwargs: dict[str, Any] = {
                    "ids": ids,
                    "documents": documents,
                    "metadatas": metadatas,
                }
                if self.embedding_model:
                    embed_fn = get_embedding_function(self.embedding_model)
                    embeddings = embed_fn(documents)
                    upsert_kwargs["embeddings"] = embeddings

                self.collection.upsert(**upsert_kwargs)
                logger.info(
                    "Indexed %d papers to ChromaDB %s (model=%s)",
                    len(ids),
                    self.collection_name,
                    self.embedding_model or "default",
                )
                return len(ids)
            except Exception:
                logger.exception("Failed to index papers to ChromaDB")
        return 0

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_year: int | None = None,
        protein_name: str | None = None,
    ) -> list[dict]:
        """Semantic search over indexed paper abstracts.

        The query is embedded with the same model used to index the collection,
        ensuring vector-space compatibility.

        Args:
            query: search query (protein name, EC number, keyword)
            top_k: number of results to return
            min_year: filter papers published after this year
            protein_name: filter by protein name in title/abstract

        Returns:
            List of dicts with paper metadata + similarity score.
        """
        if not self.collection:
            return []

        # Build where filter
        where_filter = None
        conditions = []
        if min_year:
            conditions.append({"year": {"$gte": min_year}})
        if protein_name:
            conditions.append({"title": {"$contains": protein_name}})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        # Compute query embedding explicitly so the same model is used
        # regardless of how the collection was created.
        query_kwargs: dict[str, Any] = {
            "n_results": top_k,
            "where": where_filter if where_filter else None,
            "include": ["documents", "metadatas", "distances"],
        }
        if self.embedding_model:
            try:
                embed_fn = get_embedding_function(self.embedding_model)
                query_kwargs["query_embeddings"] = embed_fn([query])
            except Exception as e:
                logger.warning(
                    "Embedding for query failed (%s); falling back to query_texts", e
                )
                query_kwargs["query_texts"] = [query]
        else:
            query_kwargs["query_texts"] = [query]

        try:
            results = self.collection.query(**query_kwargs)

            papers = []
            if results and results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 1.0
                    document = results["documents"][0][i] if results["documents"] else ""

                    papers.append({
                        "pmid": metadata.get("pmid", ""),
                        "title": metadata.get("title", ""),
                        "authors": json.loads(metadata.get("authors", "[]")) if isinstance(metadata.get("authors"), str) else [],
                        "journal": metadata.get("journal", ""),
                        "year": metadata.get("year", 0),
                        "doi": metadata.get("doi", ""),
                        "mesh_terms": json.loads(metadata.get("mesh_terms", "[]")) if isinstance(metadata.get("mesh_terms"), str) else [],
                        "abstract_snippet": document[:300] if document else "",
                        "similarity": round(1.0 - distance, 4),  # cosine distance → similarity
                        "embedding_model": self.embedding_model or "default",
                    })

            return papers
        except Exception:
            logger.exception("Literature search failed for query: %s", query)
            return []

    def search_by_enzyme(
        self,
        protein_name: str,
        ec_number: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Search literature specifically for an enzyme."""
        query_parts = [protein_name]
        if ec_number:
            query_parts.append(f"EC {ec_number}")
        query = " ".join(query_parts)

        return self.search(
            query=query,
            top_k=top_k,
            protein_name=protein_name,
        )

    # ------------------------------------------------------------------
    # Stats / admin
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get collection statistics."""
        if not self.collection:
            return {"available": False, "embedding_model": self.embedding_model or "default"}
        try:
            count = self.collection.count()
            return {
                "available": True,
                "collection": self.collection_name,
                "papers_indexed": count,
                "embedding_model": self.embedding_model or "default",
            }
        except Exception:
            return {"available": False, "embedding_model": self.embedding_model or "default"}

    def delete_paper(self, pmid: str) -> bool:
        """Remove a paper from the index."""
        if not self.collection:
            return False
        try:
            self.collection.delete(ids=[f"pmid_{pmid}"])
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def get_all_stats() -> dict[str, dict]:
    """Return stats for every supported embedding model (plus default)."""
    stats: dict[str, dict] = {}
    for model in [None] + list_embedding_models():
        store = LiteratureStore(embedding_model=model)
        key = model or "default"
        stats[key] = store.get_stats()
    return stats
