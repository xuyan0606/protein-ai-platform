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
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field

from app.core.agent_schemas import SourceResult
from app.core.data_agent import DataAgent, DataAgentResult
from app.core.literature_agent import LiteratureAgent, LiteratureAgentResult

logger = logging.getLogger(__name__)

# Maximum time to wait for knowledge gathering (seconds)
_GATHER_TIMEOUT = 30

# TTL for cached coordinator results (seconds) — same protein within this window
# won't trigger redundant KG/PubMed/ESM-2 API calls
_CACHE_TTL = 300  # 5 minutes
_MAX_CACHE_SIZE = 64  # LRU eviction threshold


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

    @property
    def source_results(self) -> list[SourceResult]:
        """All source results as standardized SourceResult envelopes."""
        results = []
        if self.data:
            results.extend(self.data.to_source_results())
        if self.literature:
            results.extend(self.literature.to_source_results())
        return results


@dataclass
class _CacheEntry:
    """Internal cache entry with TTL."""
    result: CoordinatorResult
    timestamp: float
    hits: int = 0


class CoordinatorAgent:
    """Orchestrates parallel knowledge gathering from Data + Literature agents.

    Features:
    - Parallel execution of DataAgent + LiteratureAgent via asyncio.gather
    - TTL cache: same protein within 5 min returns cached results (no redundant API calls)
    - Graceful timeout: any agent taking >30s returns empty, doesn't block the pipeline
    """

    def __init__(self):
        self._data_agent = DataAgent()
        self._literature_agent = LiteratureAgent()
        self._cache: dict[str, _CacheEntry] = {}

    async def gather(
        self,
        message: str,
        task_type: str = "research",
    ) -> CoordinatorResult:
        """Run DataAgent + LiteratureAgent in parallel and merge results.

        Uses a TTL cache keyed on (protein_name, sequence_hash, task_type).
        Same protein queried within 5 minutes returns cached results instantly.

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

        # --- Cache check ---
        cache_key = self._build_cache_key(protein_name, sequence, ec_number, task_type)
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.info("Coordinator cache hit for key=%s (age=%.0fs)", cache_key, time.time() - cached.timestamp)
            return cached

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

        result = CoordinatorResult(
            context=merged,
            data=data_result,
            literature=lit_result,
            elapsed=elapsed,
            sources=sources,
        )

        # --- Cache store ---
        if cache_key and result.has_results:
            self._cache_put(cache_key, result)

        return result

    # ─── Cache Management ────────────────────────────────────────────────

    @staticmethod
    def _build_cache_key(
        protein_name: str | None,
        sequence: str | None,
        ec_number: str | None,
        task_type: str,
    ) -> str:
        """Build a deterministic cache key from extracted entities."""
        seq_hash = hashlib.sha256((sequence or "").encode()).hexdigest()[:12] if sequence else "no_seq"
        return f"{protein_name or 'no_name'}|{ec_number or 'no_ec'}|{seq_hash}|{task_type}"

    def _cache_get(self, key: str) -> CoordinatorResult | None:
        """Get a cached result if it exists and hasn't expired."""
        if not key or key not in self._cache:
            return None
        entry = self._cache[key]
        age = time.time() - entry.timestamp
        if age > _CACHE_TTL:
            del self._cache[key]
            return None
        entry.hits += 1
        return entry.result

    def _cache_put(self, key: str, result: CoordinatorResult) -> None:
        """Store a result in the cache with LRU eviction."""
        # Evict oldest entries if cache is full
        while len(self._cache) >= _MAX_CACHE_SIZE:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].timestamp)
            del self._cache[oldest_key]
        self._cache[key] = _CacheEntry(result=result, timestamp=time.time())

    def invalidate(self, protein_name: str | None = None) -> int:
        """Invalidate cached results. If protein_name is given, only clear that protein.
        Returns the number of entries removed."""
        if protein_name is None:
            count = len(self._cache)
            self._cache.clear()
            return count
        # Remove entries matching this protein name
        to_remove = [k for k in self._cache if k.startswith(f"{protein_name}|")]
        for k in to_remove:
            del self._cache[k]
        return len(to_remove)

    @property
    def cache_stats(self) -> dict:
        """Return cache statistics for monitoring."""
        return {
            "size": len(self._cache),
            "max_size": _MAX_CACHE_SIZE,
            "ttl_seconds": _CACHE_TTL,
            "entries": {
                k: {"hits": e.hits, "age_seconds": round(time.time() - e.timestamp, 1)}
                for k, e in self._cache.items()
            },
        }

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
