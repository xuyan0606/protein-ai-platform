"""Zvec-backed semantic enzyme search.

Provides fast vector similarity search over enzyme sequences using
ESM-2 embeddings stored in Zvec (embedded vector DB).
Enables semantic "this enzyme is similar to..." queries that go beyond
text search, finding functionally related enzymes by sequence embedding proximity.
"""

from __future__ import annotations

import logging
from pathlib import Path

from zvec import (
    create_and_open,
    open as zvec_open,
    Collection,
    CollectionSchema,
    FieldSchema,
    VectorSchema,
    Doc,
    Query,
    FlatIndexParam,
    MetricType,
)
from zvec.typing import DataType

from app.ml.embeddings import get_mean_embedding

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/enzyme_vectors.zvec")
EMBEDDING_DIM = 1280  # ESM-2 t33_650M mean embedding dimension
VECTOR_FIELD = "embedding"


class EnzymeVectorSearch:
    """Semantic enzyme search using ESM-2 embeddings + Zvec vector store."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        path_str = str(self.db_path)

        if self.db_path.exists() and any(self.db_path.glob("manifest.*")):
            self.col = zvec_open(path_str)
        else:
            schema = CollectionSchema(
                name="enzymes",
                fields=[
                    FieldSchema("uniprot_id", DataType.STRING),
                    FieldSchema("enzyme_id", DataType.INT64),
                ],
                vectors=[
                    VectorSchema(
                        VECTOR_FIELD,
                        DataType.VECTOR_FP32,
                        dimension=EMBEDDING_DIM,
                        index_param=FlatIndexParam(metric_type=MetricType.COSINE),
                    ),
                ],
            )
            self.col = create_and_open(path_str, schema)

    def index_enzymes_batch(self, items: list[tuple[int, str, list[float]]]) -> int:
        """Index a batch of enzymes.

        Args:
            items: list of (enzyme_id, uniprot_id, embedding_1280d)

        Returns:
            Number of vectors indexed.
        """
        docs = []
        for enzyme_id, uniprot_id, embedding in items:
            if len(embedding) != EMBEDDING_DIM:
                logger.warning("skip %s: expected dim %d, got %d", uniprot_id, EMBEDDING_DIM, len(embedding))
                continue
            docs.append(Doc(
                id=str(enzyme_id),
                vectors={VECTOR_FIELD: embedding},
                fields={"uniprot_id": uniprot_id, "enzyme_id": enzyme_id},
            ))
        if docs:
            self.col.upsert(docs)
            self.col.flush()
        return len(docs)

    def search_similar(self, query_embedding: list[float], top_k: int = 20) -> list[dict]:
        """Find top-k most similar enzymes by embedding cosine distance.

        Args:
            query_embedding: 1280-dim ESM-2 mean embedding
            top_k: number of results

        Returns:
            List of {enzyme_id, uniprot_id, score} sorted by similarity (desc).
        """
        q = Query(VECTOR_FIELD, vector=query_embedding)
        results = self.col.query(
            queries=q,
            topk=top_k,
            output_fields=["uniprot_id", "enzyme_id"],
        )
        return [
            {"enzyme_id": doc.fields.get("enzyme_id", 0), "uniprot_id": doc.fields.get("uniprot_id", ""), "score": float(doc.score)}
            for doc in results
        ]

    def search_by_sequence(self, sequence: str, top_k: int = 20) -> list[dict]:
        """Search by raw protein sequence (computes embedding on the fly)."""
        embedding = get_mean_embedding(sequence)
        if not embedding:
            raise ValueError("failed to compute ESM-2 embedding for query sequence")
        return self.search_similar(embedding, top_k=top_k)

    def count(self) -> int:
        return self.col.stats.doc_count

    def close(self):
        pass  # Zvec Collection doesn't need explicit close
