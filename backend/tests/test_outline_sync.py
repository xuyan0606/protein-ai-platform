"""Tests for Outline API client and sync script (Phase 4).

Covers:
- T13: OutlineClient instantiation, header construction, health_check
- T14: sync_to_outline.py dry-run mode, Markdown formatting, EC grouping
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestOutlineClient:
    """T13: OutlineClient basic functionality."""

    def test_client_instantiation(self):
        from app.services.outline_client import OutlineClient
        client = OutlineClient(api_url="http://test:3001/api", api_token="test-token")
        assert client.api_url == "http://test:3001/api"
        assert client.api_token == "test-token"

    def test_headers_include_bearer(self):
        from app.services.outline_client import OutlineClient
        client = OutlineClient(api_token="my-secret-token")
        headers = client._headers
        assert headers["Authorization"] == "Bearer my-secret-token"
        assert headers["Content-Type"] == "application/json"

    def test_trailing_slash_stripped(self):
        from app.services.outline_client import OutlineClient
        client = OutlineClient(api_url="http://test:3001/api/")
        assert client.api_url == "http://test:3001/api"

    def test_singleton_get_outline_client(self):
        from app.services.outline_client import get_outline_client, OutlineClient
        # Reset singleton
        import app.services.outline_client as mod
        mod._client = None

        client = get_outline_client()
        assert isinstance(client, OutlineClient)
        # Second call returns same instance
        assert get_outline_client() is client

        # Cleanup
        mod._client = None

    @pytest.mark.asyncio
    async def test_health_check_unreachable(self):
        """Health check should return False when Outline is not running."""
        from app.services.outline_client import OutlineClient
        client = OutlineClient(
            api_url="http://localhost:19999/api",
            api_token="test",
        )
        result = await client.health_check()
        assert result is False


class TestSyncFormatting:
    """T14: sync_to_outline.py Markdown formatting and EC grouping."""

    def test_format_enzyme_markdown(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
        from sync_to_outline import format_enzyme_markdown

        enzyme = {
            "name": "Test Hydrolase",
            "ec_number": "3.1.1.1",
            "uniprot_id": "P12345",
            "organism": "Escherichia coli",
            "sequence": "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQ",
            "properties": {
                "molecular_weight_kda": 42.5,
                "isoelectric_point": 6.8,
                "gravy": -0.312,
                "stability": "stable",
            },
            "function": "Catalyzes hydrolysis of ester bonds.",
            "catalytic_activity": "A carboxylic ester + H2O = a carboxylate + an alcohol",
            "keywords": ["hydrolase", "esterase"],
        }

        md = format_enzyme_markdown(enzyme)

        assert "# Test Hydrolase" in md
        assert "3.1.1.1" in md
        assert "P12345" in md
        assert "42.5" in md  # MW
        assert "6.80" in md  # pI
        assert "hydrolase" in md.lower()
        assert "Escherichia coli" in md

    def test_format_ec_summary_markdown(self):
        from sync_to_outline import format_ec_summary_markdown

        enzymes = [
            {"ec_number": "3.1.1.1", "name": "Carboxylesterase", "uniprot_id": "P12345",
             "organism": "E. coli", "sequence": "MKTVRQ"},
            {"ec_number": "3.2.1.1", "name": "Alpha-amylase", "uniprot_id": "P67890",
             "organism": "B. subtilis", "sequence": "MLKSTV" * 20},
        ]

        md = format_ec_summary_markdown("EC.3", enzymes)

        assert "EC.3" in md
        assert "Hydrolases" in md
        assert "Total enzymes" in md
        assert "P12345" in md
        assert "P67890" in md

    def test_ec_classes_complete(self):
        """All 7 EC classes should be defined."""
        from sync_to_outline import EC_CLASSES
        assert len(EC_CLASSES) == 7
        for prefix in ["EC.1", "EC.2", "EC.3", "EC.4", "EC.5", "EC.6", "EC.7"]:
            assert prefix in EC_CLASSES, f"Missing {prefix}"
            assert "name" in EC_CLASSES[prefix]
            assert "desc" in EC_CLASSES[prefix]

    @pytest.mark.asyncio
    async def test_load_enzymes_sample_data(self):
        """load_enzymes_from_db should fall back to sample data when DB unavailable."""
        from sync_to_outline import load_enzymes_from_db
        enzymes = await load_enzymes_from_db(limit=10)
        assert len(enzymes) == 10
        for e in enzymes:
            assert "name" in e
            assert "ec_number" in e
            assert "uniprot_id" in e
            assert "sequence" in e

    @pytest.mark.asyncio
    async def test_load_enzymes_category_filter(self):
        """Category filter should only return matching EC class."""
        from sync_to_outline import load_enzymes_from_db
        enzymes = await load_enzymes_from_db(category="EC.3", limit=50)
        for e in enzymes:
            assert e["ec_number"].startswith("3."), (
                f"EC.3 filter returned {e['ec_number']}"
            )

    @pytest.mark.asyncio
    async def test_sync_dry_run(self):
        """sync_to_outline --dry-run should not crash."""
        from sync_to_outline import sync_to_outline
        # Should complete without error (no Outline connection needed)
        await sync_to_outline(dry_run=True, limit=5)
