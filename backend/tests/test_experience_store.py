"""Tests for app.memory.experience_store — ExperienceRecord & ExperienceStore.

All async tests use pytest.mark.asyncio.  No external services required.
"""

from __future__ import annotations

import re
import time

import pytest

from app.memory.experience_store import (
    MAX_EXPERIENCES,
    ExperienceRecord,
    ExperienceStore,
    get_experience_store,
)


# ── helpers ──────────────────────────────────────────────────────────

def _make_record(
    *,
    task_type: str = "design",
    protein_family: str = "EC 3.4.21",
    sequence: str = "MVLSPAD",
    pipeline: list[str] | None = None,
    success_rate: float = 0.9,
    timestamp: float | None = None,
) -> ExperienceRecord:
    """Create an ExperienceRecord with sensible defaults."""
    pipeline = pipeline or ["tool_a", "tool_b"]
    return ExperienceRecord(
        task_type=task_type,
        protein_family=protein_family,
        sequence_hash=ExperienceRecord.hash_sequence(sequence),
        pipeline=pipeline,
        pipeline_hash=ExperienceRecord.hash_pipeline(pipeline),
        step_results={t: "completed" for t in pipeline},
        success_rate=success_rate,
        total_duration=1.23,
        user_message_short="Design enzyme",
        research_notes_short="Notes here",
        timestamp=timestamp if timestamp is not None else time.time(),
    )


# =====================================================================
# 1. ExperienceRecord.hash_sequence
# =====================================================================


class TestHashSequence:
    """ExperienceRecord.hash_sequence — empty → '', non-empty → 16 hex."""

    def test_empty_string_returns_empty(self):
        assert ExperienceRecord.hash_sequence("") == ""

    def test_non_empty_returns_16_hex(self):
        result = ExperienceRecord.hash_sequence("MVLSPADKTNVKAAWGK")
        assert len(result) == 16
        assert re.fullmatch(r"[0-9a-f]{16}", result)

    def test_deterministic(self):
        """Same input → same hash."""
        assert (
            ExperienceRecord.hash_sequence("ACDEFGH")
            == ExperienceRecord.hash_sequence("ACDEFGH")
        )

    def test_different_inputs_differ(self):
        assert (
            ExperienceRecord.hash_sequence("AAAA")
            != ExperienceRecord.hash_sequence("BBBB")
        )


# =====================================================================
# 2. ExperienceRecord.hash_pipeline
# =====================================================================


class TestHashPipeline:
    """ExperienceRecord.hash_pipeline — list → 12 hex."""

    def test_returns_12_hex(self):
        result = ExperienceRecord.hash_pipeline(["blast", "hmmscan", "foldx"])
        assert len(result) == 12
        assert re.fullmatch(r"[0-9a-f]{12}", result)

    def test_deterministic(self):
        assert (
            ExperienceRecord.hash_pipeline(["a", "b"])
            == ExperienceRecord.hash_pipeline(["a", "b"])
        )

    def test_order_matters(self):
        assert (
            ExperienceRecord.hash_pipeline(["a", "b"])
            != ExperienceRecord.hash_pipeline(["b", "a"])
        )

    def test_empty_list(self):
        result = ExperienceRecord.hash_pipeline([])
        assert len(result) == 12
        assert re.fullmatch(r"[0-9a-f]{12}", result)


# =====================================================================
# 3. ExperienceStore.record + search_similar
# =====================================================================


class TestRecordAndSearch:
    """Record an experience, then find it via search_similar."""

    @pytest.mark.asyncio
    async def test_record_then_search_finds_it(self):
        store = ExperienceStore()
        rec = _make_record(task_type="design", protein_family="EC 3.4.21")
        await store.record(rec)

        results = await store.search_similar("design", protein_family="EC 3.4.21")
        assert len(results) == 1
        assert results[0].pipeline == rec.pipeline

    @pytest.mark.asyncio
    async def test_search_filters_by_task_type(self):
        store = ExperienceStore()
        await store.record(_make_record(task_type="design"))
        await store.record(_make_record(task_type="analyze"))

        results = await store.search_similar("design")
        assert all(r.task_type == "design" for r in results)

    @pytest.mark.asyncio
    async def test_search_similar_ranks_by_sequence_match(self):
        store = ExperienceStore()
        seq = "MVLSPADKTNVKAAWGK"
        # Record with matching sequence
        await store.record(_make_record(task_type="design", sequence=seq))
        # Record with different sequence
        await store.record(
            _make_record(task_type="design", sequence="ZZZZZZZ", timestamp=time.time() + 1)
        )

        results = await store.search_similar("design", sequence=seq)
        assert len(results) == 2
        # First result should be the one with matching sequence
        assert results[0].sequence_hash == ExperienceRecord.hash_sequence(seq)

    @pytest.mark.asyncio
    async def test_search_similar_top_k(self):
        store = ExperienceStore()
        for i in range(5):
            await store.record(
                _make_record(task_type="design", pipeline=[f"tool_{i}"], timestamp=time.time() + i)
            )

        results = await store.search_similar("design", top_k=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_empty_store(self):
        store = ExperienceStore()
        results = await store.search_similar("design")
        assert results == []


# =====================================================================
# 4. ExperienceStore.get_best_pipeline
# =====================================================================


class TestGetBestPipeline:
    """High success → pipeline returned; low success → None."""

    @pytest.mark.asyncio
    async def test_high_success_returns_pipeline(self):
        store = ExperienceStore()
        pipeline = ["blast", "hmmscan", "foldx"]
        await store.record(
            _make_record(task_type="design", pipeline=pipeline, success_rate=0.95)
        )

        result = await store.get_best_pipeline("design")
        assert result == pipeline

    @pytest.mark.asyncio
    async def test_low_success_returns_none(self):
        store = ExperienceStore()
        await store.record(
            _make_record(task_type="design", success_rate=0.3)
        )

        result = await store.get_best_pipeline("design")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_records_returns_none(self):
        store = ExperienceStore()
        result = await store.get_best_pipeline("design")
        assert result is None

    @pytest.mark.asyncio
    async def test_exactly_at_threshold(self):
        """success_rate == 0.7 is the threshold (>=)."""
        store = ExperienceStore()
        pipeline = ["tool_x"]
        await store.record(
            _make_record(task_type="analyze", pipeline=pipeline, success_rate=0.7)
        )

        result = await store.get_best_pipeline("analyze")
        assert result == pipeline


# =====================================================================
# 5. ExperienceStore.get_stats
# =====================================================================


class TestGetStats:
    """Empty → total_records=0; with records → full stats."""

    def test_empty_store(self):
        store = ExperienceStore()
        stats = store.get_stats()
        assert stats == {"total_records": 0}

    @pytest.mark.asyncio
    async def test_with_records(self):
        store = ExperienceStore()
        await store.record(_make_record(task_type="design", protein_family="EC 3.4.21", success_rate=0.8))
        await store.record(_make_record(task_type="analyze", protein_family="EC 1.1.1", success_rate=0.6))

        stats = store.get_stats()
        assert stats["total_records"] == 2
        assert stats["task_types"] == {"design": 1, "analyze": 1}
        assert stats["unique_families"] == 2
        assert stats["avg_success_rate"] == 0.7  # (0.8+0.6)/2


# =====================================================================
# 6. ExperienceStore.clear
# =====================================================================


class TestClear:
    """After clear(), stats show empty store."""

    @pytest.mark.asyncio
    async def test_clear_empties_store(self):
        store = ExperienceStore()
        await store.record(_make_record())
        assert store.get_stats()["total_records"] == 1

        await store.clear()
        assert store.get_stats() == {"total_records": 0}

    @pytest.mark.asyncio
    async def test_clear_already_empty(self):
        store = ExperienceStore()
        await store.clear()  # should not raise
        assert store.get_stats() == {"total_records": 0}


# =====================================================================
# 7. get_experience_store — singleton
# =====================================================================


class TestGetExperienceStore:
    """Two calls return the same instance."""

    def test_singleton(self):
        import app.memory.experience_store as mod

        # Reset singleton to ensure fresh test
        original = mod._experience_store
        mod._experience_store = None
        try:
            s1 = get_experience_store()
            s2 = get_experience_store()
            assert s1 is s2
            assert isinstance(s1, ExperienceStore)
        finally:
            mod._experience_store = original


# =====================================================================
# 8. LRU eviction — MAX_EXPERIENCES
# =====================================================================


class TestLRUEviction:
    """Writing more than MAX_EXPERIENCES keeps total ≤ MAX_EXPERIENCES."""

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        store = ExperienceStore()
        total_to_insert = MAX_EXPERIENCES + 50  # 1050

        for i in range(total_to_insert):
            rec = _make_record(
                task_type="design",
                pipeline=[f"tool_{i}"],
                timestamp=time.time() + i,  # ensure unique keys
            )
            await store.record(rec)

        stats = store.get_stats()
        assert stats["total_records"] <= MAX_EXPERIENCES

    @pytest.mark.asyncio
    async def test_lru_evicts_oldest(self):
        """The earliest-inserted record should be evicted first."""
        store = ExperienceStore()

        # Insert exactly MAX_EXPERIENCES + 1 records
        first_rec = _make_record(
            task_type="design",
            pipeline=["first_tool"],
            timestamp=time.time(),
        )
        await store.record(first_rec)

        for i in range(1, MAX_EXPERIENCES + 1):
            rec = _make_record(
                task_type="design",
                pipeline=[f"tool_{i}"],
                timestamp=time.time() + i + 100,  # offset to avoid collision
            )
            await store.record(rec)

        # The very first record should have been evicted
        results = await store.search_similar("design", top_k=MAX_EXPERIENCES + 10)
        pipelines = [r.pipeline for r in results]
        assert ["first_tool"] not in pipelines
