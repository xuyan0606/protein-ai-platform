"""Regression tests for the read-only research evidence API."""

from app.api import research
from app.tools.external_research_evidence import external_research_evidence


def test_research_router_exposes_read_only_evidence():
    routes = {route.path for route in research.router.routes}
    assert "/evidence" in routes


def test_research_evidence_function_keeps_release_blocked():
    result = external_research_evidence("release")
    assert result["normalized_result"]["release_ready"] is False
    assert result["read_only"] is True


def test_research_evidence_function_exposes_human_target_scope():
    result = external_research_evidence("human_target")
    assert result["normalized_result"]["ready_sources"] == 0
    assert result["normalized_result"]["blocked_sources"] == 7
    assert result["normalized_result"]["release_ready"] is False
