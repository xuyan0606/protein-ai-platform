"""Literature store — ChromaDB index for protein literature abstracts.

Activates the protein_literature collection (previously defined but unused in vectordb.py).
Provides semantic search over paper abstracts for RAG injection into agent responses.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from chromadb import HttpClient, Collection
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

# Use same ChromaDB connection as vectordb.py
_COLLECTION_NAME = "protein_literature"


def _get_client() -> HttpClient | None:
    """Get ChromaDB HTTP client (same config as vectordb.py)."""
    try:
        client = HttpClient(
            host="localhost",
            port=8001,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        client.heartbeat()
        return client
    except Exception:
        logger.warning("ChromaDB not available at localhost:8001")
        return None


def _get_collection() -> Collection | None:
    """Get or create the protein_literature collection."""
    client = _get_client()
    if client is None:
        return None
    try:
        return client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={
                "hnsw:space": "cosine",
                "description": "Protein AI — protein_literature",
            },
        )
    except Exception as e:
        logger.warning("Failed to get/create ChromaDB collection '%s': %s", _COLLECTION_NAME, e)
        return None


class LiteratureStore:
    """ChromaDB-based literature index for protein science papers."""

    def __init__(self):
        try:
            self.collection = _get_collection()
        except Exception:
            logger.warning("ChromaDB not available, literature store disabled")
            self.collection = None

    def is_available(self) -> bool:
        return self.collection is not None

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
            })

        if ids:
            try:
                self.collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
                logger.info("Indexed %d papers to ChromaDB %s", len(ids), _COLLECTION_NAME)
                return len(ids)
            except Exception:
                logger.exception("Failed to index papers to ChromaDB")
        return 0

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_year: int | None = None,
        protein_name: str | None = None,
    ) -> list[dict]:
        """Semantic search over indexed paper abstracts.

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

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter if where_filter else None,
                include=["documents", "metadatas", "distances"],
            )

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
                    })

            return papers
        except Exception:
            logger.exception("Literature search failed for query: %s", query)
            return []

    def search_by_enzyme(
        self, protein_name: str, ec_number: str | None = None, top_k: int = 5
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

    def get_stats(self) -> dict:
        """Get collection statistics."""
        if not self.collection:
            return {"available": False}
        try:
            count = self.collection.count()
            return {
                "available": True,
                "collection": _COLLECTION_NAME,
                "papers_indexed": count,
            }
        except Exception:
            return {"available": False}

    def delete_paper(self, pmid: str) -> bool:
        """Remove a paper from the index."""
        if not self.collection:
            return False
        try:
            self.collection.delete(ids=[f"pmid_{pmid}"])
            return True
        except Exception:
            return False
