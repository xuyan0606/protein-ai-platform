"""Retrospective Memory — MLEvolve-inspired experience store.

Records tool pipeline execution experiences and retrieves them during
planning to inform better pipeline selection. Combines:
- Cold-start domain knowledge (via existing SKILL.md files)
- Dynamic global memory (accumulated execution experiences)
- Simple similarity matching for experience retrieval
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

MAX_EXPERIENCES = 1000  # LRU eviction threshold


@dataclass
class ExperienceRecord:
    """A single execution experience record."""
    task_type: str              # design, analyze, research
    protein_family: str         # EC number or protein family name
    sequence_hash: str          # SHA-256 of input sequence (or empty)
    pipeline: list[str]         # ordered list of tool names executed
    pipeline_hash: str          # hash of the pipeline
    step_results: dict[str, str]  # tool_name → status (completed/failed)
    success_rate: float         # fraction of successful steps
    total_duration: float       # total execution time in seconds
    user_message_short: str     # first 100 chars of user message
    research_notes_short: str   # first 200 chars of research notes
    round_number: int = 1       # iteration round (1=first, 2+=refinement)
    improvement_delta: float = 0.0  # improvement from previous round
    timestamp: float = field(default_factory=time.time)

    @staticmethod
    def hash_sequence(sequence: str) -> str:
        """SHA-256 hash of a protein sequence."""
        if not sequence:
            return ""
        return hashlib.sha256(sequence.encode()).hexdigest()[:16]

    @staticmethod
    def hash_pipeline(pipeline: list[str]) -> str:
        """Hash of a tool pipeline."""
        return hashlib.sha256("|".join(pipeline).encode()).hexdigest()[:12]


class ExperienceStore:
    """In-memory experience store with LRU eviction.

    Thread-safe via asyncio.Lock. Global singleton at module level.
    """

    def __init__(self):
        self._records: OrderedDict[str, ExperienceRecord] = OrderedDict()
        self._lock = asyncio.Lock()

    async def record(self, experience: ExperienceRecord) -> None:
        """Record a new execution experience."""
        async with self._lock:
            key = f"{experience.task_type}_{experience.protein_family}_{experience.pipeline_hash}_{experience.timestamp}"
            self._records[key] = experience
            # LRU eviction
            while len(self._records) > MAX_EXPERIENCES:
                self._records.popitem(last=False)
            logger.debug(
                "Recorded experience: %s/%s (pipeline=%s, success=%.1f%%)",
                experience.task_type, experience.protein_family,
                experience.pipeline_hash, experience.success_rate * 100,
            )

    async def search_similar(
        self,
        task_type: str,
        protein_family: str = "",
        sequence: str = "",
        top_k: int = 5,
    ) -> list[ExperienceRecord]:
        """Search for similar past experiences.

        Matching strategy:
        1. Exact task_type match (required)
        2. Protein family match (bonus)
        3. Sequence hash match (bonus)
        4. Recency (more recent = higher score)
        """
        async with self._lock:
            seq_hash = ExperienceRecord.hash_sequence(sequence) if sequence else ""

            scored = []
            for record in self._records.values():
                if record.task_type != task_type:
                    continue

                score = 0.0
                # Protein family match
                if protein_family and record.protein_family == protein_family:
                    score += 3.0
                elif protein_family and protein_family.lower() in record.protein_family.lower():
                    score += 1.5

                # Sequence match
                if seq_hash and record.sequence_hash == seq_hash:
                    score += 5.0

                # Success rate bonus
                score += record.success_rate * 2.0

                # Recency bonus (last 24h get +1, last hour +2)
                age_hours = (time.time() - record.timestamp) / 3600
                if age_hours < 1:
                    score += 2.0
                elif age_hours < 24:
                    score += 1.0

                scored.append((score, record))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [r for _, r in scored[:top_k]]

    async def get_best_pipeline(self, task_type: str, protein_family: str = "") -> list[str] | None:
        """Get the historically best-performing pipeline for a task type."""
        results = await self.search_similar(task_type, protein_family, top_k=1)
        if results and results[0].success_rate >= 0.7:
            return results[0].pipeline
        return None

    async def get_domain_knowledge(self, task_type: str) -> str:
        """Get cold-start domain knowledge for a task type.

        Uses the existing SKILL.md files via the skills module.
        """
        from app.core.skills import read_skill

        skill_map = {
            "design": "protein_design",
            "analyze": "mutation_design",
            "research": "sequence_analysis",
        }

        skill_name = skill_map.get(task_type, "sequence_analysis")
        skill = read_skill(skill_name)
        if skill:
            return f"\n--- DOMAIN KNOWLEDGE ({skill_name}) ---\n{skill[:500]}"
        return ""

    def get_stats(self) -> dict[str, Any]:
        """Get store statistics."""
        records = list(self._records.values())
        if not records:
            return {"total_records": 0}

        task_types = {}
        families = set()
        success_rates = []
        for r in records:
            task_types[r.task_type] = task_types.get(r.task_type, 0) + 1
            if r.protein_family:
                families.add(r.protein_family)
            success_rates.append(r.success_rate)

        return {
            "total_records": len(records),
            "task_types": task_types,
            "unique_families": len(families),
            "avg_success_rate": round(sum(success_rates) / len(success_rates), 3) if success_rates else 0,
        }

    async def clear(self) -> None:
        """Clear all stored experiences."""
        async with self._lock:
            self._records.clear()


# Global singleton
_experience_store: ExperienceStore | None = None


def get_experience_store() -> ExperienceStore:
    """Get the global experience store singleton."""
    global _experience_store
    if _experience_store is None:
        _experience_store = ExperienceStore()
    return _experience_store
