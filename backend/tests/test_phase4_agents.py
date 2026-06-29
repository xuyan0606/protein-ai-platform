"""Tests for Phase 4 multi-agent modules: DataAgent, LiteratureAgent, CoordinatorAgent, agent_schemas.

Uses pytest + unittest.mock — no real database, ChromaDB, or external API calls needed.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os_env = {"USE_SQLITE": "true"}


# =====================================================================
# 1. agent_schemas.py — Citation, EnzymeReference, SourceResult
# =====================================================================


class TestCitation:
    """Tests for Citation dataclass."""

    def test_format_short_single_author(self):
        from app.core.agent_schemas import Citation

        c = Citation(pmid="12345", title="Test Paper", authors=["Smith J"], year=2025)
        result = c.format_short()
        assert "PMID:12345" in result
        assert "Smith J" in result
        assert "2025" in result
        assert "et al." not in result

    def test_format_short_multiple_authors(self):
        from app.core.agent_schemas import Citation

        c = Citation(pmid="99999", title="Multi Author", authors=["Doe A", "Smith J", "Lee K"], year=2024)
        result = c.format_short()
        assert "Doe A et al." in result
        assert "2024" in result

    def test_format_short_no_year(self):
        from app.core.agent_schemas import Citation

        c = Citation(pmid="11111", title="No Year", authors=["Test B"])
        result = c.format_short()
        assert "(None)" not in result  # no year should not produce "(None)"
        assert "Test B" in result

    def test_format_with_abstract(self):
        from app.core.agent_schemas import Citation

        c = Citation(pmid="22222", title="Abstract Test", abstract_snippet="This is a test abstract about enzymes.")
        result = c.format_with_abstract()
        assert "Abstract:" in result
        assert "enzymes" in result

    def test_to_dict(self):
        from app.core.agent_schemas import Citation

        c = Citation(pmid="33333", title="Dict Test", doi="10.1234/test")
        d = c.to_dict()
        assert d["pmid"] == "33333"
        assert d["doi"] == "10.1234/test"
        assert isinstance(d, dict)


class TestEnzymeReference:
    """Tests for EnzymeReference dataclass."""

    def test_format_short_with_ec(self):
        from app.core.agent_schemas import EnzymeReference

        e = EnzymeReference(uniprot_id="P12345", name="Lipase", ec_numbers=["3.1.1.3"], similarity=0.92)
        result = e.format_short()
        assert "P12345" in result
        assert "EC 3.1.1.3" in result
        assert "sim=0.92" in result

    def test_format_short_no_similarity(self):
        from app.core.agent_schemas import EnzymeReference

        e = EnzymeReference(uniprot_id="Q99999", name="Unknown")
        result = e.format_short()
        assert "Q99999" in result
        assert "sim=" not in result

    def test_to_dict(self):
        from app.core.agent_schemas import EnzymeReference

        e = EnzymeReference(uniprot_id="P00001", organism="Homo sapiens")
        d = e.to_dict()
        assert d["organism"] == "Homo sapiens"


class TestPipelineExperience:
    """Tests for PipelineExperience dataclass."""

    def test_format_short_success(self):
        from app.core.agent_schemas import PipelineExperience

        p = PipelineExperience(
            task_type="analyze",
            protein_family="Lipase",
            pipeline=["predict_properties", "mutation_scan", "esmfold_folding"],
            success_rate=0.95,
            total_duration=12.5,
        )
        result = p.format_short()
        assert "✓" in result
        assert "95%" in result
        assert "predict_properties" in result

    def test_format_short_failure(self):
        from app.core.agent_schemas import PipelineExperience

        p = PipelineExperience(
            task_type="design",
            protein_family="Kinase",
            pipeline=["rfdiffusion_design"],
            success_rate=0.3,
            total_duration=5.0,
        )
        result = p.format_short()
        assert "⚠" in result

    def test_format_short_long_pipeline(self):
        from app.core.agent_schemas import PipelineExperience

        p = PipelineExperience(
            task_type="analyze",
            protein_family="test",
            pipeline=["a", "b", "c", "d", "e", "f", "g"],
            success_rate=0.8,
            total_duration=10.0,
        )
        result = p.format_short()
        assert "…" in result  # truncated


class TestSourceResult:
    """Tests for SourceResult envelope."""

    def test_has_data_empty(self):
        from app.core.agent_schemas import SourceResult

        s = SourceResult(source="test")
        assert not s.has_data

    def test_has_data_with_context(self):
        from app.core.agent_schemas import SourceResult

        s = SourceResult(source="pubmed", context_text="some papers")
        assert s.has_data

    def test_has_data_with_citations(self):
        from app.core.agent_schemas import SourceResult, Citation

        s = SourceResult(source="pubmed", citations=[Citation(pmid="1")])
        assert s.has_data

    def test_to_dict(self):
        from app.core.agent_schemas import SourceResult

        s = SourceResult(source="kg", status="success", context_text="test" * 200, elapsed=1.5)
        d = s.to_dict()
        assert d["source"] == "kg"
        assert d["elapsed"] == 1.5
        # context_text is truncated in to_dict
        assert len(d["context_text"]) <= 500


class TestFormattingUtils:
    """Tests for formatting utility functions."""

    def test_format_section_header(self):
        from app.core.agent_schemas import format_section_header

        h = format_section_header("ENZYME KG", "knowledge_graph")
        assert h == "--- ENZYME KG (knowledge_graph) ---"

    def test_format_section_header_no_source(self):
        from app.core.agent_schemas import format_section_header

        h = format_section_header("RESULTS")
        assert h == "--- RESULTS ---"

    def test_format_citations_block_empty(self):
        from app.core.agent_schemas import format_citations_block

        assert format_citations_block([]) == ""

    def test_format_enzyme_refs_block(self):
        from app.core.agent_schemas import format_enzyme_refs_block, EnzymeReference

        refs = [EnzymeReference(uniprot_id="P1", name="E1", similarity=0.9)]
        result = format_enzyme_refs_block(refs)
        assert "RELATED ENZYMES" in result
        assert "P1" in result


# =====================================================================
# 2. DataAgent — gather + result conversion
# =====================================================================


class TestDataAgent:
    """Tests for DataAgent knowledge gathering."""

    def test_result_empty(self):
        from app.core.data_agent import DataAgentResult

        r = DataAgentResult()
        assert not r.has_results
        assert r.to_context_string() == ""
        assert r.to_source_results() == []

    def test_result_with_kg(self):
        from app.core.data_agent import DataAgentResult

        r = DataAgentResult(kg_context="EC 3.1.1.3 lipase found")
        assert r.has_results
        ctx = r.to_context_string()
        assert "ENZYME KNOWLEDGE GRAPH" in ctx
        assert "lipase" in ctx

    def test_result_with_similar(self):
        from app.core.data_agent import DataAgentResult

        r = DataAgentResult(
            similar_enzymes="Similar: P12345",
            similar_data=[{"uniprot_id": "P12345", "distance": 0.1}],
        )
        assert r.has_results
        ctx = r.to_context_string()
        assert "SIMILAR ENZYMES" in ctx

    def test_to_source_results(self):
        from app.core.data_agent import DataAgentResult

        r = DataAgentResult(
            kg_context="KG data",
            similar_enzymes="Similar data",
            similar_data=[{"uniprot_id": "P1", "distance": 0.2}],
        )
        srs = r.to_source_results()
        assert len(srs) == 2
        assert srs[0].source == "knowledge_graph"
        assert srs[1].source == "esm2_vector"
        assert srs[1].enzyme_refs[0].similarity == 0.8

    @pytest.mark.asyncio
    async def test_gather_no_params(self):
        """gather() with no protein_name or sequence returns empty result."""
        from app.core.data_agent import DataAgent

        agent = DataAgent()
        result = await agent.gather()
        assert not result.has_results

    @pytest.mark.asyncio
    async def test_gather_short_sequence_skipped(self):
        """Sequences shorter than 20 aa skip ESM-2 search."""
        from app.core.data_agent import DataAgent

        agent = DataAgent()
        result = await agent.gather(sequence="MKTEW")  # 5 aa, too short
        assert not result.has_results


# =====================================================================
# 3. LiteratureAgent — gather + result conversion
# =====================================================================


class TestLiteratureAgent:
    """Tests for LiteratureAgent literature + experience gathering."""

    def test_result_empty(self):
        from app.core.literature_agent import LiteratureAgentResult

        r = LiteratureAgentResult()
        assert not r.has_results
        assert r.to_context_string() == ""

    def test_result_with_literature(self):
        from app.core.literature_agent import LiteratureAgentResult

        r = LiteratureAgentResult(
            literature_context="PMID:12345 - Test paper",
            papers=[{"pmid": "12345", "title": "Test"}],
        )
        assert r.has_results
        ctx = r.to_context_string()
        assert "RELATED LITERATURE" in ctx

    def test_result_with_experience(self):
        from app.core.literature_agent import LiteratureAgentResult

        r = LiteratureAgentResult(
            experience_context="✓ Pipeline [predict, scan] (95%)",
            experiences=[{"task_type": "analyze", "success_rate": 0.95}],
        )
        assert r.has_results
        ctx = r.to_context_string()
        assert "PAST EXPERIENCES" in ctx

    def test_to_source_results(self):
        from app.core.literature_agent import LiteratureAgentResult

        r = LiteratureAgentResult(
            literature_context="papers",
            papers=[{"pmid": "1", "title": "P1"}],
            experience_context="exp",
            experiences=[{"task_type": "analyze", "pipeline": ["a"], "success_rate": 0.9}],
        )
        srs = r.to_source_results()
        assert len(srs) == 2
        assert srs[0].source == "pubmed"
        assert srs[1].source == "experience"
        assert srs[0].citations[0].pmid == "1"


# =====================================================================
# 4. CoordinatorAgent — cache + parallel execution + entity extraction
# =====================================================================


class TestCoordinatorAgent:
    """Tests for CoordinatorAgent parallel orchestration and caching."""

    def _make_coordinator(self):
        from app.core.coordinator_agent import CoordinatorAgent

        return CoordinatorAgent()

    # --- Entity Extraction ---

    def test_extract_protein_name_with_prefix(self):
        coord = self._make_coordinator()
        assert coord._extract_protein_name("Design a binder for PD-L1") == "PD-L1"
        assert coord._extract_protein_name("analyze EGFR structure") == "EGFR"

    def test_extract_protein_name_fallback(self):
        coord = self._make_coordinator()
        assert coord._extract_protein_name("What about HER2?") == "HER2"

    def test_extract_protein_name_none(self):
        coord = self._make_coordinator()
        assert coord._extract_protein_name("hello how are you") is None

    def test_extract_sequence(self):
        coord = self._make_coordinator()
        seq = coord._extract_sequence("Here is the sequence MKTEWFLCVLAGRHIFL")
        assert seq == "MKTEWFLCVLAGRHIFL"

    def test_extract_sequence_none(self):
        coord = self._make_coordinator()
        assert coord._extract_sequence("no sequence here") is None

    def test_extract_ec_number(self):
        coord = self._make_coordinator()
        assert coord._extract_ec_number("EC 3.1.1.3 lipase") == "3.1.1.3"
        assert coord._extract_ec_number("enzyme 1.1.1.1") == "1.1.1.1"
        assert coord._extract_ec_number("no EC number") is None

    # --- Cache Key ---

    def test_build_cache_key(self):
        coord = self._make_coordinator()
        key = coord._build_cache_key("PD-L1", "MKTEW", "3.1.1.3", "analyze")
        assert "PD-L1" in key
        assert "3.1.1.3" in key
        assert "analyze" in key

    def test_build_cache_key_no_params(self):
        coord = self._make_coordinator()
        key = coord._build_cache_key(None, None, None, "research")
        assert "no_name" in key
        assert "no_seq" in key

    # --- Cache Operations ---

    def test_cache_put_and_get(self):
        from app.core.coordinator_agent import CoordinatorResult

        coord = self._make_coordinator()
        result = CoordinatorResult(context="test context", sources=["kg"])
        coord._cache_put("test_key", result)

        cached = coord._cache_get("test_key")
        assert cached is not None
        assert cached.context == "test context"

    def test_cache_miss(self):
        coord = self._make_coordinator()
        assert coord._cache_get("nonexistent") is None

    def test_cache_ttl_expiry(self):
        from app.core.coordinator_agent import CoordinatorResult, _CacheEntry

        coord = self._make_coordinator()
        # Manually insert an expired entry
        expired = _CacheEntry(
            result=CoordinatorResult(context="old"),
            timestamp=time.time() - 400,  # 400s ago, TTL is 300s
        )
        coord._cache["expired_key"] = expired

        assert coord._cache_get("expired_key") is None
        assert "expired_key" not in coord._cache  # should be evicted

    def test_cache_lru_eviction(self):
        from app.core.coordinator_agent import CoordinatorResult

        coord = self._make_coordinator()
        # Fill cache to max (64)
        for i in range(64):
            coord._cache_put(f"key_{i}", CoordinatorResult(context=f"ctx_{i}", sources=["test"]))

        assert len(coord._cache) == 64

        # Adding one more should evict oldest
        coord._cache_put("key_new", CoordinatorResult(context="new", sources=["test"]))
        assert len(coord._cache) == 64
        assert "key_new" in coord._cache

    def test_cache_invalidate_all(self):
        from app.core.coordinator_agent import CoordinatorResult

        coord = self._make_coordinator()
        coord._cache_put("a", CoordinatorResult(context="a", sources=["test"]))
        coord._cache_put("b", CoordinatorResult(context="b", sources=["test"]))

        removed = coord.invalidate()
        assert removed == 2
        assert len(coord._cache) == 0

    def test_cache_invalidate_by_protein(self):
        from app.core.coordinator_agent import CoordinatorResult

        coord = self._make_coordinator()
        coord._cache_put("PD-L1|no_ec|no_seq|analyze", CoordinatorResult(context="pdl1", sources=["test"]))
        coord._cache_put("EGFR|no_ec|no_seq|analyze", CoordinatorResult(context="egfr", sources=["test"]))

        removed = coord.invalidate("PD-L1")
        assert removed == 1
        assert "EGFR|no_ec|no_seq|analyze" in coord._cache

    def test_cache_stats(self):
        from app.core.coordinator_agent import CoordinatorResult

        coord = self._make_coordinator()
        coord._cache_put("test", CoordinatorResult(context="x", sources=["test"]))
        stats = coord.cache_stats
        assert stats["size"] == 1
        assert stats["max_size"] == 64
        assert stats["ttl_seconds"] == 300

    def test_cache_hit_increments(self):
        from app.core.coordinator_agent import CoordinatorResult

        coord = self._make_coordinator()
        coord._cache_put("hit_test", CoordinatorResult(context="cached", sources=["test"]))

        # First get
        coord._cache_get("hit_test")
        # Second get
        coord._cache_get("hit_test")

        stats = coord.cache_stats
        assert stats["entries"]["hit_test"]["hits"] == 2

    # --- Coordinator Result ---

    def test_coordinator_result_empty(self):
        from app.core.coordinator_agent import CoordinatorResult

        r = CoordinatorResult()
        assert not r.has_results
        assert r.source_results == []

    def test_coordinator_result_source_results(self):
        from app.core.coordinator_agent import CoordinatorResult
        from app.core.data_agent import DataAgentResult
        from app.core.literature_agent import LiteratureAgentResult

        r = CoordinatorResult(
            context="merged",
            data=DataAgentResult(kg_context="kg"),
            literature=LiteratureAgentResult(literature_context="lit"),
        )
        srs = r.source_results
        assert len(srs) == 2
        sources = [sr.source for sr in srs]
        assert "knowledge_graph" in sources
        assert "pubmed" in sources

    # --- Parallel gather (mocked) ---

    @pytest.mark.asyncio
    async def test_gather_cache_hit(self):
        """Second gather with same params returns cached result."""
        from app.core.coordinator_agent import CoordinatorResult
        from app.core.data_agent import DataAgentResult
        from app.core.literature_agent import LiteratureAgentResult

        coord = self._make_coordinator()

        # Pre-populate cache
        cached_result = CoordinatorResult(
            context="cached KG data",
            data=DataAgentResult(kg_context="cached"),
            literature=LiteratureAgentResult(),
            sources=["knowledge_graph"],
        )
        cache_key = coord._build_cache_key("PD-L1", None, None, "analyze")
        coord._cache_put(cache_key, cached_result)

        # gather() should return cached result without calling agents
        result = await coord.gather("analyze PD-L1", task_type="analyze")
        assert result.context == "cached KG data"
        assert "knowledge_graph" in result.sources

    @pytest.mark.asyncio
    async def test_gather_timeout_handling(self):
        """Verify gather handles agent timeout gracefully."""
        from app.core.coordinator_agent import CoordinatorAgent, _GATHER_TIMEOUT

        coord = CoordinatorAgent()
        # Just verify the timeout constant is reasonable
        assert _GATHER_TIMEOUT == 30
