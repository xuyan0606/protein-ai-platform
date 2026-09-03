"""Regression tests for the live, read-only connectivity probe."""

import asyncio

from app.tools import external_connectivity_check as connectivity_module
from app.tools.registry import ToolRegistry


def test_external_connectivity_check_is_registered_read_only():
    tool = ToolRegistry.get_tool("external_connectivity_check")
    assert tool is not None
    assert tool.category == "research"
    assert tool.annotations["read_only"] is True
    assert tool.annotations["external_network"] is True
    assert tool.parameters["additionalProperties"] is False


def test_external_connectivity_check_reports_current_partial_live_result(monkeypatch):
    async def fake_probe(client, name, url, params):
        status = "blocked" if name == "InterPro API" else "live"
        return {"source": name, "endpoint": url, "status": status, "latency_ms": 3}

    monkeypatch.setattr(connectivity_module, "_probe_endpoint", fake_probe)
    payload = asyncio.run(connectivity_module.external_connectivity_check())

    assert payload["status"] == "live"
    assert payload["connected"] is True
    assert payload["summary"] == {
        "successful_probes": 2,
        "total_probes": 3,
        "all_reachable": False,
    }
    assert payload["evidence_source"]["mode"] == "partial_official_api_connectivity"
    assert payload["evidence_source"]["live_query_executed"] is True


def test_external_connectivity_check_fails_closed_when_all_probes_blocked(monkeypatch):
    async def fake_probe(client, name, url, params):
        return {"source": name, "endpoint": url, "status": "blocked", "error_type": "ConnectError"}

    monkeypatch.setattr(connectivity_module, "_probe_endpoint", fake_probe)
    payload = asyncio.run(connectivity_module.external_connectivity_check())

    assert payload["status"] == "blocked"
    assert payload["connected"] is False
    assert payload["summary"]["successful_probes"] == 0
    assert payload["evidence_source"]["status"] == "blocked"
    assert payload["evidence_source"]["live_query_executed"] is False
