"""Coordinator Agent — parallel orchestration of Data + Literature agents.

Part of the Phase 4 multi-agent split:
  DataAgent        → structured data (KG + vector embeddings)
  LiteratureAgent  → unstructured data (papers + RAG + experience memory)
  Coordinator      → THIS FILE: parallel execution + result merging

The Coordinator:
1. Extracts key entities from the user message (protein name, sequence, EC number)
2. Launches DataAgent and LiteratureAgent in parallel (asyncio.gather)
3. Merges results into a unified context string for PI/SC prompt injection
4. Times out gracefully if any agent takes too long

This replaces the old inline _get_knowledge_context() in agent_graph.py.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field

from app.core.data_agent import DataAgent, DataAgentResult
from app.core.literature_agent import LiteratureAgent, LiteratureAgentResult

logger = logging.getLogger(__name__)

# Maximum time to wait for knowledge gathering (seconds)
_GATHER_TIMEOUT = 30


@dataclass
class CoordinatorResult:
    """Merged output from Coordinator.gather()."""

    context: str = ""  # Full merged context string for LLM injection
    data: DataAgentResult | None = None
    literature: LiteratureAgentResult | None = None
    elapsed: float = 0.0
    sources: list[str] = field(default_factory=list)  # which sources returned data

    @property
    def has_results(self) -> bool:
        return bool(self.context)


class CoordinatorAgent:
    """Orchestrates parallel knowledge gathering from Data + Literature agents."""

    def __init__(self):
        self._data_agent = DataAgent()
        self._literature_agent = LiteratureAgent()

    async def gather(
        self,
        message: str,
        task_type: str = "research",
    ) -> CoordinatorResult:
        """Run DataAgent + LiteratureAgent in parallel and merge results.

        Args:
            message: The user's original message (entities will be extracted)
            task_type: Task classification from the router (design/analyze/research)

        Returns:
            CoordinatorResult with merged context for PI/SC prompt injection.
        """
        start = time.time()

        # Extract entities from message
        protein_name = self._extract_protein_name(message)
        sequence = self._extract_sequence(message)
        ec_number = self._extract_ec_number(message)

        # Run both agents in parallel with timeout
        try:
            data_result, lit_result = await asyncio.wait_for(
                asyncio.gather(
                    self._data_agent.gather(
                        protein_name=protein_name,
                        sequence=sequence,
                        ec_number=ec_number,
                    ),
                    self._literature_agent.gather(
                        protein_name=protein_name,
                        task_type=task_type,
                        user_message=message,
                        sequence=sequence,
                    ),
                ),
                timeout=_GATHER_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("Knowledge gathering timed out after %ds", _GATHER_TIMEOUT)
            data_result = DataAgentResult()
            lit_result = LiteratureAgentResult()
        except Exception as e:
            logger.warning("Knowledge gathering failed: %s", e)
            data_result = DataAgentResult()
            lit_result = LiteratureAgentResult()

        # Merge results
        sections = []
        sources = []

        # Data agent results (KG + vector search)
        data_context = data_result.to_context_string()
        if data_context:
            sections.append(data_context)
            if data_result.kg_context:
                sources.append("knowledge_graph")
            if data_result.similar_enzymes:
                sources.append("esm2_vector")

        # Literature agent results (papers + experience)
        lit_context = lit_result.to_context_string()
        if lit_context:
            sections.append(lit_context)
            if lit_result.literature_context:
                sources.append("literature")
            if lit_result.experience_context:
                sources.append("experience_memory")

        elapsed = time.time() - start
        merged = "\n\n".join(sections) if sections else ""

        if sources:
            logger.info(
                "Coordinator gathered context from %s in %.1fs",
                ", ".join(sources), elapsed,
            )

        return CoordinatorResult(
            context=merged,
            data=data_result,
            literature=lit_result,
            elapsed=elapsed,
            sources=sources,
        )

    # ─── Entity Extraction ──────────────────────────────────────────────

    @staticmethod
    def _extract_protein_name(text: str) -> str | None:
        """Extract a likely protein/gene name from a natural language query.

        Same logic as AgentOrchestrator._extract_protein_name but standalone.
        """
        # Common prefixes that introduce a protein name
        prefix_str = (
            r'(?i:design|bind(?:er)?|for|target(?:ing)?|against|of|on|about|analy[sz]e|study|'
            r'investigate|engineer|mutate|optimize|improve|enhance|modify|evolve|screen)\s+'
            r'(?:a\s+|an\s+|the\s+)?'
            r'(?:(?:high|low)[\s-]*(?:affinity|specificity)\s+)?'
            r'(?:protein\s+|enzyme\s+|binder\s+)?'
            r'(?:for\s+|of\s+|to\s+|against\s+|targeting\s+)?'
        )
        protein_pattern = r'([A-Z][A-Z0-9]+(?:[-/][A-Z0-9]+)*)'

        match = re.search(prefix_str + protein_pattern, text)
        if match:
            name = match.group(1).strip()
            if len(name) >= 2:
                return name

        # Fallback: find any uppercase identifier (2-15 chars)
        matches = re.findall(r'\b([A-Z][A-Z0-9]+(?:[-/][A-Z0-9]+)*)\b', text)
        if matches:
            english_upper = {
                'A', 'I', 'THE', 'IS', 'ARE', 'BE', 'DO', 'FOR', 'AND',
                'NOT', 'BUT', 'OR', 'NOR', 'SO', 'YET', 'THIS',
            }
            candidates = [
                m for m in matches
                if m.upper() not in english_upper and len(m) >= 2
            ]
            if candidates:
                return max(candidates, key=len)

        return None

    @staticmethod
    def _extract_sequence(text: str) -> str | None:
        """Extract a valid amino-acid sequence (10+ consecutive standard AAs)."""
        matches = re.findall(r'[ACDEFGHIKLMNPQRSTVWY]{10,}', text, re.IGNORECASE)
        if matches:
            return max(matches, key=len).upper()
        return None

    @staticmethod
    def _extract_ec_number(text: str) -> str | None:
        """Extract an EC number pattern (e.g. EC 1.1.1.1 or 3.4.21.4)."""
        match = re.search(r'(?:EC\s*)?(\d+\.\d+\.\d+\.\d+)', text)
        if match:
            return match.group(1)
        return None
