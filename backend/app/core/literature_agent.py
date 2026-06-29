"""Literature Agent — paper search + RAG + retrospective memory.

Part of the Phase 4 multi-agent split:
  DataAgent        → structured data (KG + vector embeddings)
  LiteratureAgent  → unstructured data (papers + RAG + experience memory)
  Coordinator      → parallel orchestration of Data + Literature

This agent searches PubMed/Europe PMC for relevant papers, queries the
ChromaDB literature index for semantic matches, and retrieves past
execution experiences (MLEvolve retrospective memory). All three sources
run in parallel and results are merged.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.agent_schemas import (
    SourceResult, Citation, PipelineExperience,
    format_section_header,
)

logger = logging.getLogger(__name__)


@dataclass
class LiteratureAgentResult:
    """Structured output from LiteratureAgent.gather()."""

    literature_context: str = ""  # Formatted paper citations
    experience_context: str = ""  # Past execution experiences
    papers: list[dict] = field(default_factory=list)  # Raw paper metadata
    experiences: list[dict] = field(default_factory=list)  # Raw experience records

    @property
    def has_results(self) -> bool:
        return bool(self.literature_context or self.experience_context)

    def to_context_string(self) -> str:
        """Format results as LLM-injectable text."""
        sections = []
        if self.literature_context:
            sections.append(f"{format_section_header('RELATED LITERATURE', 'pubmed/europe_pmc')}\n{self.literature_context}")
        if self.experience_context:
            sections.append(f"{format_section_header('PAST EXPERIENCES', 'mlevolve_memory')}\n{self.experience_context}")
        return "\n\n".join(sections)

    def to_source_results(self) -> list[SourceResult]:
        """Convert to standardized SourceResult envelopes."""
        results = []
        if self.literature_context:
            citations = [
                Citation(
                    pmid=p.get("pmid", ""),
                    title=p.get("title", ""),
                    authors=p.get("authors", []),
                    journal=p.get("journal", ""),
                    year=p.get("year"),
                    doi=p.get("doi"),
                )
                for p in self.papers
            ]
            results.append(SourceResult(
                source="pubmed",
                status="success",
                context_text=self.literature_context,
                citations=citations,
            ))
        if self.experience_context:
            exps = [
                PipelineExperience(
                    task_type=e.get("task_type", ""),
                    protein_family=e.get("protein_family", ""),
                    pipeline=e.get("pipeline", []),
                    success_rate=e.get("success_rate", 0.0),
                    total_duration=e.get("total_duration", 0.0),
                    round_number=e.get("round_number", 1),
                )
                for e in self.experiences
            ]
            results.append(SourceResult(
                source="experience",
                status="success",
                context_text=self.experience_context,
                experiences=exps,
            ))
        return results


class LiteratureAgent:
    """Gathers unstructured knowledge: papers + semantic search + experience memory."""

    async def gather(
        self,
        protein_name: str | None = None,
        task_type: str = "research",
        user_message: str = "",
        sequence: str | None = None,
    ) -> LiteratureAgentResult:
        """Gather literature + experience data in parallel.

        Args:
            protein_name: Protein/gene name for literature search
            task_type: Task classification (design/analyze/research)
            user_message: Original user message for experience matching
            sequence: Protein sequence for sequence-based experience search

        Returns:
            LiteratureAgentResult with merged context from all sources.
        """
        tasks = []

        # Task 1: PubMed/Europe PMC search
        if protein_name:
            tasks.append(self._search_literature(protein_name))
        else:
            tasks.append(self._noop())

        # Task 2: ChromaDB semantic search
        if protein_name:
            tasks.append(self._search_literature_store(protein_name))
        else:
            tasks.append(self._noop())

        # Task 3: Experience memory retrieval
        if task_type or protein_name:
            tasks.append(self._search_experiences(task_type, protein_name or "", sequence or ""))
        else:
            tasks.append(self._noop())

        pubmed_result, chroma_result, experience_result = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # Merge literature from PubMed + ChromaDB
        papers = []
        lit_parts = []

        if isinstance(pubmed_result, tuple):
            pubmed_text, pubmed_papers = pubmed_result
            if pubmed_text:
                lit_parts.append(pubmed_text)
                papers.extend(pubmed_papers)

        if isinstance(chroma_result, tuple):
            chroma_text, chroma_papers = chroma_result
            if chroma_text:
                lit_parts.append(chroma_text)
                papers.extend(chroma_papers)

        # Experience context
        exp_context = ""
        exp_data = []
        if isinstance(experience_result, tuple):
            exp_context, exp_data = experience_result

        return LiteratureAgentResult(
            literature_context="\n\n".join(lit_parts) if lit_parts else "",
            experience_context=exp_context,
            papers=papers,
            experiences=exp_data,
        )

    async def _noop(self) -> tuple[str, list]:
        """No-op placeholder when a source isn't applicable."""
        return ("", [])

    async def _search_literature(self, protein_name: str) -> tuple[str, list[dict]]:
        """Search PubMed/Europe PMC for relevant papers.

        Returns (formatted_citations, raw_paper_dicts).
        """
        try:
            from app.services.literature_client import LiteratureClient

            client = LiteratureClient()
            papers = await client.search_by_protein(protein_name, max_results=5)
            if papers:
                citations = LiteratureClient.format_citations(papers)
                paper_dicts = [p.to_dict() if hasattr(p, 'to_dict') else {} for p in papers]
                return (citations, paper_dicts)
        except Exception as e:
            logger.debug("Literature search failed for '%s': %s", protein_name, e)
        return ("", [])

    async def _search_literature_store(self, protein_name: str) -> tuple[str, list[dict]]:
        """Semantic search in ChromaDB literature index.

        Returns (formatted_results, raw_result_dicts).
        """
        try:
            from app.services.literature_store import LiteratureStore

            store = LiteratureStore()
            results = await store.search_by_enzyme(protein_name, top_k=3)
            if results:
                lines = ["Semantically related papers (ChromaDB):"]
                paper_dicts = []
                for r in results:
                    title = r.get("metadata", {}).get("title", "Unknown")
                    journal = r.get("metadata", {}).get("journal", "")
                    year = r.get("metadata", {}).get("year", "")
                    distance = r.get("distance", 1.0)
                    relevance = round(1.0 - distance, 3)
                    lines.append(f"- {title} ({journal} {year}) [relevance: {relevance}]")
                    paper_dicts.append(r)
                return ("\n".join(lines), paper_dicts)
        except Exception as e:
            logger.debug("Literature store search failed: %s", e)
        return ("", [])

    async def _search_experiences(
        self, task_type: str, protein_family: str, sequence: str
    ) -> tuple[str, list[dict]]:
        """Query MLEvolve retrospective memory for past experiences.

        Returns (formatted_context, raw_experience_dicts).
        """
        try:
            from app.memory.experience_store import get_experience_store

            store = get_experience_store()
            experiences = await store.search_similar(
                task_type=task_type,
                protein_family=protein_family,
                sequence=sequence,
                top_k=3,
            )
            if not experiences:
                return ("", [])

            lines = ["Past execution experiences for similar tasks:"]
            exp_dicts = []
            for exp in experiences:
                status = "✓" if exp.success_rate >= 0.8 else "⚠"
                pipeline_preview = ", ".join(exp.pipeline[:5])
                if len(exp.pipeline) > 5:
                    pipeline_preview += "..."
                lines.append(
                    f"- {status} Pipeline [{pipeline_preview}] "
                    f"({exp.success_rate:.0%} success, {exp.total_duration:.0f}s)"
                )
                exp_dicts.append({
                    "task_type": exp.task_type,
                    "protein_family": exp.protein_family,
                    "pipeline": exp.pipeline,
                    "success_rate": exp.success_rate,
                    "total_duration": exp.total_duration,
                    "round_number": exp.round_number,
                })

            # Get best pipeline recommendation
            best = await store.get_best_pipeline(task_type, protein_family)
            if best:
                lines.append(f"Recommended pipeline: {' → '.join(best)}")

            return ("\n".join(lines), exp_dicts)
        except Exception as e:
            logger.debug("Experience search failed: %s", e)
        return ("", [])
