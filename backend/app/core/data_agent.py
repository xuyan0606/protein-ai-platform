"""Data Agent — enzyme knowledge graph + ESM-2 vector search + BRENDA + SABIO-RK.

Part of the Phase 4 multi-agent split:
  DataAgent      → structured data (KG + vector embeddings + external DBs)
  LiteratureAgent → unstructured data (papers + RAG)
  Coordinator    → parallel orchestration of Data + Literature

This agent queries the enzyme knowledge graph (virtual graph over 15 PostgreSQL
tables), performs ESM-2 embedding-based similarity search, and fetches data from
external enzyme databases (BRENDA and SABIO-RK). All four sources run in parallel
and results are merged into a structured context dict.

Data sources:
  1. knowledge_graph — internal PostgreSQL KG (EnzymeKnowledgeGraph, 15 tables)
  2. esm2_vector     — ESM-2 embedding similarity (EnzymeVectorSearch)
  3. BRENDA          — BRENDA enzyme database (https://www.brenda-enzymes.org/api/)
  4. SABIO-RK        — SABIO-RK kinetics database (https://sabiork.h-its.org/sabioREST/)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.agent_schemas import (
    SourceResult, EnzymeReference,
    format_section_header,
)

logger = logging.getLogger(__name__)


@dataclass
class DataAgentResult:
    """Structured output from DataAgent.gather()."""

    kg_context: str = ""  # Knowledge graph natural language summary
    similar_enzymes: str = ""  # ESM-2 vector search results
    brenda_context: str = ""  # BRENDA enzyme database results
    sabio_context: str = ""  # SABIO-RK kinetics database results
    kg_data: dict[str, Any] = field(default_factory=dict)  # Raw KG dict for downstream use
    similar_data: list[dict] = field(default_factory=list)  # Raw similar enzymes data
    brenda_data: list[dict] = field(default_factory=list)  # Raw BRENDA data
    sabio_data: list[dict] = field(default_factory=list)  # Raw SABIO-RK data

    @property
    def has_results(self) -> bool:
        return bool(self.kg_context or self.similar_enzymes or self.brenda_context or self.sabio_context)

    def to_context_string(self) -> str:
        """Format results as LLM-injectable text."""
        sections = []
        if self.kg_context:
            sections.append(f"{format_section_header('ENZYME KNOWLEDGE GRAPH', 'knowledge_graph')}\n{self.kg_context}")
        if self.similar_enzymes:
            sections.append(f"{format_section_header('SIMILAR ENZYMES', 'esm2_embedding')}\n{self.similar_enzymes}")
        if self.brenda_context:
            sections.append(f"{format_section_header('BRENDA ENZYME DATABASE', 'brenda')}\n{self.brenda_context}")
        if self.sabio_context:
            sections.append(f"{format_section_header('SABIO-RK KINETICS DATABASE', 'sabio_rk')}\n{self.sabio_context}")
        return "\n\n".join(sections)

    def to_source_results(self) -> list[SourceResult]:
        """Convert to standardized SourceResult envelopes."""
        results = []
        if self.kg_context:
            refs = []
            for item in self.similar_data:
                refs.append(EnzymeReference(
                    uniprot_id=item.get("uniprot_id", ""),
                    similarity=round(1.0 - item.get("distance", 1.0), 3),
                ))
            results.append(SourceResult(
                source="knowledge_graph",
                status="success",
                context_text=self.kg_context,
                enzyme_refs=refs,
                raw_data=self.kg_data,
            ))
        if self.similar_enzymes:
            refs = [
                EnzymeReference(
                    uniprot_id=r.get("uniprot_id", ""),
                    similarity=round(1.0 - r.get("distance", 1.0), 3),
                )
                for r in self.similar_data
            ]
            results.append(SourceResult(
                source="esm2_vector",
                status="success",
                context_text=self.similar_enzymes,
                enzyme_refs=refs,
            ))
        if self.brenda_context:
            refs = [
                EnzymeReference(
                    uniprot_id="",  # BRENDA uses EC numbers, not UniProt IDs
                    name=e.get("name", ""),
                    ec_numbers=[e.get("ec_number", "")] if e.get("ec_number") else [],
                    organism=", ".join(e.get("organisms", [])[:2]),
                )
                for e in self.brenda_data
            ]
            results.append(SourceResult(
                source="brenda",
                status="success",
                context_text=self.brenda_context,
                enzyme_refs=refs,
                raw_data={"enzymes": self.brenda_data},
            ))
        if self.sabio_context:
            refs = [
                EnzymeReference(
                    uniprot_id="",  # SABIO-RK uses entry IDs, not UniProt IDs
                    ec_numbers=[e.get("ec_number", "")] if e.get("ec_number") else [],
                    organism=e.get("organism", ""),
                )
                for e in self.sabio_data
            ]
            results.append(SourceResult(
                source="sabio_rk",
                status="success",
                context_text=self.sabio_context,
                enzyme_refs=refs,
                raw_data={"entries": self.sabio_data},
            ))
        return results


class DataAgent:
    """Queries structured enzyme data: knowledge graph + ESM-2 vector search + BRENDA + SABIO-RK."""

    def __init__(self):
        self._sync_engine = None

    async def gather(
        self,
        protein_name: str | None = None,
        sequence: str | None = None,
        ec_number: str | None = None,
    ) -> DataAgentResult:
        """Gather structured data from KG + vector search + BRENDA + SABIO-RK in parallel.

        Args:
            protein_name: Protein/gene name for KG lookup (e.g. "PD-L1", "EGFR")
            sequence: Amino acid sequence for ESM-2 vector search (≥20 aa)
            ec_number: EC number for direct EC-based KG lookup

        Returns:
            DataAgentResult with merged context from all sources.
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

        # Task 3: BRENDA enzyme database query
        if protein_name or ec_number:
            tasks.append(self._query_brenda(protein_name, ec_number))
        else:
            tasks.append(self._noop(""))

        # Task 4: SABIO-RK kinetics database query
        if ec_number or protein_name:
            tasks.append(self._query_sabio(ec_number, protein_name))
        else:
            tasks.append(self._noop(""))

        kg_result, similar_result, brenda_result, sabio_result = await asyncio.gather(
            *tasks, return_exceptions=True
        )

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

        brenda_context = ""
        brenda_data = []
        if isinstance(brenda_result, Exception):
            logger.debug("BRENDA query failed: %s", brenda_result)
        elif isinstance(brenda_result, tuple):
            brenda_context, brenda_data = brenda_result

        sabio_context = ""
        sabio_data = []
        if isinstance(sabio_result, Exception):
            logger.debug("SABIO-RK query failed: %s", sabio_result)
        elif isinstance(sabio_result, tuple):
            sabio_context, sabio_data = sabio_result

        return DataAgentResult(
            kg_context=kg_context,
            similar_enzymes=similar_text,
            brenda_context=brenda_context,
            sabio_context=sabio_context,
            kg_data=kg_data,
            similar_data=similar_data,
            brenda_data=brenda_data,
            sabio_data=sabio_data,
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

    async def _query_brenda(
        self, protein_name: str | None, ec_number: str | None
    ) -> tuple[str, list[dict]]:
        """Query BRENDA enzyme database by name or EC number.

        Returns (formatted_text, raw_data_list).
        """
        try:
            from app.services.brenda_client import BRENDA, format_brenda_context

            client = BRENDA()
            try:
                enzymes = []

                # Strategy 1: Direct EC number lookup (most precise)
                if ec_number:
                    enzyme = await client.get_by_ec(ec_number)
                    if enzyme:
                        enzymes.append(enzyme)

                # Strategy 2: Name-based search
                if not enzymes and protein_name:
                    search_results = await client.search(protein_name, max_results=5)
                    enzymes.extend(search_results)

                # Strategy 3: If protein_name looks like an EC number, try it
                if not enzymes and protein_name and protein_name.startswith("EC"):
                    ec_candidate = protein_name.replace("EC", "").strip()
                    enzyme = await client.get_by_ec(ec_candidate)
                    if enzyme:
                        enzymes.append(enzyme)

                if enzymes:
                    # Format context from first (best) result
                    context_lines = [format_brenda_context(enzymes[0])]

                    # Add summary of additional results
                    if len(enzymes) > 1:
                        context_lines.append(f"\n{len(enzymes) - 1} additional BRENDA entries found:")
                        for e in enzymes[1:3]:  # Show up to 2 more
                            ec = e.get("ec_number", "")
                            name = e.get("name", "")
                            context_lines.append(f"- EC {ec}: {name}" if ec and name else f"- {name or ec}")

                    return ("\n".join(context_lines), enzymes)

            finally:
                await client.close()

        except Exception as e:
            logger.debug("BRENDA query unavailable: %s", e)
        return ("", [])

    async def _query_sabio(
        self, ec_number: str | None, protein_name: str | None
    ) -> tuple[str, list[dict]]:
        """Query SABIO-RK kinetics database by EC number or enzyme name.

        Returns (formatted_text, raw_data_list).
        """
        try:
            from app.services.sabio_client import SABIOClient, format_sabio_context

            client = SABIOClient()
            try:
                entries = []

                # Strategy 1: Search by EC number (most precise for kinetics data)
                if ec_number:
                    search_results = await client.search(ec_number, max_results=5)
                    entries.extend(search_results)

                # Strategy 2: Search by protein/enzyme name
                if not entries and protein_name:
                    search_results = await client.search(protein_name, max_results=5)
                    entries.extend(search_results)

                # Strategy 3: If protein_name looks like an EC number, try it
                if not entries and protein_name and protein_name.startswith("EC"):
                    ec_candidate = protein_name.replace("EC", "").strip()
                    search_results = await client.search(ec_candidate, max_results=5)
                    entries.extend(search_results)

                if entries:
                    # Format context from first (best) result
                    context_lines = [format_sabio_context(entries[0])]

                    # Add summary of additional results
                    if len(entries) > 1:
                        context_lines.append(f"\n{len(entries) - 1} additional SABIO-RK entries found:")
                        for e in entries[1:3]:  # Show up to 2 more
                            entry_id = e.get("entry_id", "")
                            ec = e.get("ec_number", "")
                            organism = e.get("organism", "")
                            parts = [f"Entry {entry_id}"]
                            if ec:
                                parts.append(f"EC {ec}")
                            if organism:
                                parts.append(organism)
                            context_lines.append(f"- {' / '.join(parts)}")

                    return ("\n".join(context_lines), entries)

            finally:
                await client.close()

        except Exception as e:
            logger.debug("SABIO-RK query unavailable: %s", e)
        return ("", [])
