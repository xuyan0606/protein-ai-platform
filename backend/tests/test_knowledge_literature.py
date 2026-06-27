"""Tests for knowledge_graph, literature_client, literature_store, and models.literature modules.

Uses pytest + unittest.mock — no real database or ChromaDB connections needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# =====================================================================
# 1. knowledge_graph.py — EnzymeKnowledgeGraph
# =====================================================================


class TestEnzymeKnowledgeGraph:
    """Tests for EnzymeKnowledgeGraph query and natural-language serialisation."""

    def _make_graph(self):
        """Create an EnzymeKnowledgeGraph with a mocked DB session."""
        from app.services.knowledge_graph import EnzymeKnowledgeGraph

        db = MagicMock()
        return EnzymeKnowledgeGraph(db), db

    def test_query_enzyme_context_not_found(self):
        """Querying a non-existent UniProt ID returns an empty dict."""
        graph, db = self._make_graph()
        # scalar_one_or_none returns None → enzyme not found
        db.execute.return_value.scalar_one_or_none.return_value = None

        result = graph.query_enzyme_context("FAKE_ID_000")

        assert result == {}
        db.execute.assert_called_once()

    def test_to_natural_language_empty(self):
        """Empty context dict produces an empty string."""
        graph, _ = self._make_graph()

        assert graph.to_natural_language({}) == ""
        assert graph.to_natural_language(None) == ""  # type: ignore[arg-type]

    def test_to_natural_language_basic(self):
        """A minimal context dict produces well-formatted natural language."""
        graph, _ = self._make_graph()

        context = {
            "enzyme": {
                "uniprot_id": "P00519",
                "protein_name": "Tyrosine-protein kinase ABL1",
                "gene_name": "ABL1",
                "seq_length": 1130,
                "function_annotation": "Non-receptor tyrosine-protein kinase.",
                "catalytic_activity": "ATP + L-tyrosyl-[protein] = ADP + H(+) + O-phospho-L-tyrosyl-[protein]",
            },
            "taxonomy": {
                "scientific_name": "Homo sapiens",
                "common_name": "Human",
                "lineage": "Eukaryota; Metazoa",
            },
            "ec_numbers": [
                {"ec_number": "2.7.10.2", "name": "Non-specific protein-tyrosine kinase"},
            ],
            "pdb_structures": [
                {"pdb_id": "1ABL", "method": "X-RAY", "resolution": 1.6},
            ],
            "alphafold_structures": [],
            "kinetics": [],
            "stability_records": [],
            "domains": [],
            "evolution": [],
            "xrefs": [],
            "literature_refs": ["PMID:7533118"],
        }

        output = graph.to_natural_language(context)

        # Basic info section
        assert "## Enzyme: Tyrosine-protein kinase ABL1" in output
        assert "UniProt ID: P00519" in output
        assert "Gene: ABL1" in output
        assert "1130 aa" in output

        # Taxonomy
        assert "### Organism" in output
        assert "Homo sapiens (Human)" in output

        # EC classification
        assert "### EC Classification" in output
        assert "2.7.10.2" in output

        # Structures
        assert "### Structures" in output
        assert "1ABL" in output

        # Literature
        assert "### Literature References" in output
        assert "PMID:7533118" in output

    def test_query_by_name_no_result(self):
        """query_by_name returns None when no enzyme matches."""
        graph, db = self._make_graph()
        db.execute.return_value.scalar_one_or_none.return_value = None

        result = graph.query_by_name("NonExistentKinase")

        assert result is None
        db.execute.assert_called_once()


# =====================================================================
# 2. literature_client.py — LiteratureClient, Paper, parse_literature_ref
# =====================================================================


class TestParseLiteratureRef:
    """Tests for the standalone parse_literature_ref helper."""

    def test_parse_literature_ref_pmid(self):
        from app.services.literature_client import parse_literature_ref

        assert parse_literature_ref("PMID:12345") == ("pmid", "12345")
        assert parse_literature_ref("pmid:99999") == ("pmid", "99999")

    def test_parse_literature_ref_doi(self):
        from app.services.literature_client import parse_literature_ref

        assert parse_literature_ref("doi:10.1234/abc") == ("doi", "10.1234/abc")
        assert parse_literature_ref("DOI:10.5678/xyz") == ("doi", "10.5678/xyz")

    def test_parse_literature_ref_bare_doi(self):
        from app.services.literature_client import parse_literature_ref

        assert parse_literature_ref("10.1234/foo.bar") == ("doi", "10.1234/foo.bar")

    def test_parse_literature_ref_digits(self):
        from app.services.literature_client import parse_literature_ref

        assert parse_literature_ref("12345") == ("pmid", "12345")
        assert parse_literature_ref("99999999") == ("pmid", "99999999")

    def test_parse_literature_ref_empty(self):
        from app.services.literature_client import parse_literature_ref

        assert parse_literature_ref("") is None
        assert parse_literature_ref("   ") is None
        assert parse_literature_ref(None) is None  # type: ignore[arg-type]


class TestPaperDataclass:
    """Tests for the Paper dataclass methods."""

    def _make_paper(self):
        from app.services.literature_client import Paper

        return Paper(
            pmid="12345",
            doi="10.1234/test",
            title="Engineering Enzyme Specificity",
            authors=["Smith J", "Doe A"],
            journal="Nature",
            year=2024,
            abstract="We engineered a novel enzyme...",
        )

    def test_paper_short_citation(self):
        paper = self._make_paper()
        citation = paper.short_citation

        assert "Smith J" in citation
        assert "et al." in citation
        assert "(2024)" in citation
        assert "Engineering Enzyme Specificity" in citation
        assert "Nature" in citation
        assert "PMID:12345" in citation

    def test_paper_to_dict(self):
        paper = self._make_paper()
        d = paper.to_dict()

        assert d["pmid"] == "12345"
        assert d["doi"] == "10.1234/test"
        assert d["title"] == "Engineering Enzyme Specificity"
        assert d["authors"] == ["Smith J", "Doe A"]
        assert d["journal"] == "Nature"
        assert d["year"] == 2024
        assert d["abstract"] == "We engineered a novel enzyme..."
        # source is NOT in to_dict
        assert "source" not in d


class TestFormatCitations:
    """Tests for LiteratureClient.format_citations static method."""

    def test_format_citations_empty(self):
        from app.services.literature_client import LiteratureClient

        assert LiteratureClient.format_citations([]) == "No related literature found."

    def test_format_citations_with_papers(self):
        from app.services.literature_client import LiteratureClient, Paper

        papers = [
            Paper(
                pmid="111",
                title="Paper One",
                authors=["Alice B"],
                journal="Science",
                year=2023,
                abstract="Short abstract.",
            ),
            Paper(
                pmid="222",
                title="Paper Two",
                authors=["Carol D"],
                journal="Cell",
                year=2024,
            ),
        ]

        output = LiteratureClient.format_citations(papers)

        # Numbered citations
        assert "1." in output
        assert "2." in output
        # First author names
        assert "Alice B" in output
        assert "Carol D" in output
        # First paper has abstract
        assert "Abstract: Short abstract." in output
        # Second paper has no abstract, so no "Abstract:" line for it beyond #1


# =====================================================================
# 3. literature_store.py — LiteratureStore
# =====================================================================


class TestLiteratureStore:
    """Tests for LiteratureStore graceful degradation when ChromaDB is unavailable."""

    @patch("app.services.literature_store._get_collection", return_value=None)
    def test_store_unavailable(self, mock_get_collection):
        from app.services.literature_store import LiteratureStore

        store = LiteratureStore()

        assert store.collection is None
        assert store.is_available() is False
        mock_get_collection.assert_called_once()

    @patch("app.services.literature_store._get_collection", return_value=None)
    def test_search_returns_empty_when_unavailable(self, mock_get_collection):
        from app.services.literature_store import LiteratureStore

        store = LiteratureStore()

        result = store.search("enzyme kinetics", top_k=5)

        assert result == []

    @patch("app.services.literature_store._get_collection", return_value=None)
    def test_index_papers_returns_zero_when_unavailable(self, mock_get_collection):
        from app.services.literature_store import LiteratureStore

        store = LiteratureStore()

        count = store.index_papers([{"pmid": "1", "title": "Test", "abstract": "abs"}])

        assert count == 0

    @patch("app.services.literature_store._get_collection", return_value=None)
    def test_get_stats_unavailable(self, mock_get_collection):
        from app.services.literature_store import LiteratureStore

        store = LiteratureStore()

        stats = store.get_stats()

        assert stats == {"available": False}

    @patch("app.services.literature_store._get_collection", return_value=None)
    def test_delete_paper_returns_false_when_unavailable(self, mock_get_collection):
        from app.services.literature_store import LiteratureStore

        store = LiteratureStore()

        assert store.delete_paper("12345") is False


# =====================================================================
# 4. models/literature.py — Paper, EnzymeLiteratureLink
# =====================================================================


class TestLiteratureModels:
    """Tests for SQLAlchemy model table names."""

    def test_paper_model_table_name(self):
        from app.models.literature import Paper

        assert Paper.__tablename__ == "papers"

    def test_enzyme_literature_link_table_name(self):
        from app.models.literature import EnzymeLiteratureLink

        assert EnzymeLiteratureLink.__tablename__ == "enzyme_literature_links"
