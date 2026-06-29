"""Data Agent — enzyme knowledge graph + ESM-2 vector search.

Part of the Phase 4 multi-agent split:
  DataAgent      → structured data (KG + vector embeddings)
  LiteratureAgent → unstructured data (papers + RAG)
  Coordinator    → parallel orchestration of Data + Literature

This agent queries the enzyme knowledge graph (virtual graph over 15 PostgreSQL
tables) and performs ESM-2 embedding-based similarity search. Both sources run
in parallel and results are merged into a structured context dict.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DataAgentResult:
    """Structured output from DataAgent.gather()."""

    kg_context: str = ""  # Knowledge graph natural language summary
    similar_enzymes: str = ""  # ESM-2 vector search results
    kg_data: dict[str, Any] = field(default_factory=dict)  # Raw KG dict for downstream use
    similar_data: list[dict] = field(default_factory=list)  # Raw similar enzymes data

    @property
    def has_results(self) -> bool:
        return bool(self.kg_context or self.similar_enzymes)

    def to_context_string(self) -> str:
        """Format results as LLM-injectable text."""
        sections = []
        if self.kg_context:
            sections.append(f"--- ENZYME KNOWLEDGE GRAPH ---\n{self.kg_context}")
        if self.similar_enzymes:
            sections.append(f"--- SIMILAR ENZYMES (ESM-2 embedding) ---\n{self.similar_enzymes}")
        return "\n\n".join(sections)


class DataAgent:
    """Queries structured enzyme data: knowledge graph + ESM-2 vector search."""

    def __init__(self):
        self._sync_engine = None

    async def gather(
        self,
        protein_name: str | None = None,
        sequence: str | None = None,
        ec_number: str | None = None,
    ) -> DataAgentResult:
        """Gather structured data from KG + vector search in parallel.

        Args:
            protein_name: Protein/gene name for KG lookup (e.g. "PD-L1", "EGFR")
            sequence: Amino acid sequence for ESM-2 vector search (≥20 aa)
            ec_number: EC number for direct EC-based KG lookup

        Returns:
            DataAgentResult with merged context from both sources.
        """
        tasks = []

        # Task 1: Knowledge graph query
        if protein_name or ec_number:
            tasks.append(self._query_knowledge_graph(protein_name or "", ec_number))
        else:
            tasks.append(self._noop(""))

        # Task 2: ESM-2 vector search
        if sequence and len(sequence) >= 20:
            tasks.append(self._search_similar_enzymes(sequence))
        else:
            tasks.append(self._noop(""))

        kg_result, similar_result = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions gracefully
        kg_context = ""
        kg_data = {}
        if isinstance(kg_result, Exception):
            logger.debug("KG query failed: %s", kg_result)
        elif isinstance(kg_result, tuple):
            kg_context, kg_data = kg_result

        similar_text = ""
        similar_data = []
        if isinstance(similar_result, Exception):
            logger.debug("ESM-2 vector search failed: %s", similar_result)
        elif isinstance(similar_result, tuple):
            similar_text, similar_data = similar_result

        return DataAgentResult(
            kg_context=kg_context,
            similar_enzymes=similar_text,
            kg_data=kg_data,
            similar_data=similar_data,
        )

    async def _noop(self, default: str) -> tuple[str, Any]:
        """No-op placeholder when a data source isn't applicable."""
        return (default, {} if default == "" else [])

    async def _query_knowledge_graph(
        self, protein_name: str, ec_number: str | None = None
    ) -> tuple[str, dict]:
        """Query enzyme knowledge graph in a thread executor.

        Returns (natural_language_context, raw_kg_dict).
        """
        def _sync_query():
            try:
                from app.core.database import _engine
                from sqlalchemy import create_engine
                from sqlalchemy.orm import Session as SyncSession
                from app.services.knowledge_graph import EnzymeKnowledgeGraph

                # Create sync engine from async URL
                sync_url = str(_engine.url).replace("+asyncpg", "+psycopg2").replace("+aiosqlite", "+sqlite")

                # Reuse cached sync engine if available
                if self._sync_engine is None:
                    self._sync_engine = create_engine(sync_url, echo=False, pool_pre_ping=True)

                with SyncSession(self._sync_engine) as session:
                    kg = EnzymeKnowledgeGraph(session)

                    # Strategy 1: exact name match
                    if protein_name:
                        enzyme = kg.query_by_name(protein_name)
                        if enzyme:
                            context = kg.query_enzyme_context(enzyme.uniprot_id)
                            return (kg.to_natural_language(context), context)

                    # Strategy 2: EC number search
                    ec = ec_number or ""
                    if not ec and protein_name and protein_name.startswith("EC"):
                        ec = protein_name
                    if ec:
                        results = kg.query_by_ec(ec)
                        if results:
                            return (kg.to_natural_language(results[0]), results[0])

                    return ("", {})
            except Exception as e:
                logger.debug("Knowledge graph query unavailable: %s", e)
                return ("", {})

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_query)

    async def _search_similar_enzymes(self, sequence: str) -> tuple[str, list[dict]]:
        """Search for similar enzymes using ESM-2 vector embeddings.

        Returns (formatted_text, raw_data_list).
        """
        try:
            from app.ml.vector_search import EnzymeVectorSearch

            def _sync_search():
                vsearch = EnzymeVectorSearch()
                return vsearch.search_by_sequence(sequence, top_k=3)

            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(None, _sync_search)

            if results:
                lines = ["Similar enzymes found by ESM-2 embedding similarity:"]
                for r in results:
                    uniprot_id = r.get("uniprot_id", "unknown")
                    distance = r.get("distance", 1.0)
                    similarity = round(1.0 - distance, 3)
                    lines.append(f"- {uniprot_id} (cosine similarity: {similarity})")
                return ("\n".join(lines), results)
        except Exception as e:
            logger.debug("ESM-2 vector search unavailable: %s", e)
        return ("", [])
