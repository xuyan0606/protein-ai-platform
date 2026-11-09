from __future__ import annotations

import asyncio

import httpx

from app.tools import enzyme_assistant_predict as adapter


SEQUENCE = "M" + "A" * 30


def test_recommend_blocks_without_service_url(monkeypatch):
    monkeypatch.delenv("ENZYME_ASSISTANT_SERVICE_URL", raising=False)
    result = asyncio.run(adapter.enzyme_assistant_recommend(sequence=SEQUENCE))

    assert result["status"] == "blocked_model_service_unavailable"
    assert result["evidence_level"] == "research_only_heuristic"
    assert result["manual_review_required"] is True


def test_build_rejects_invalid_mutation(monkeypatch):
    monkeypatch.setenv("ENZYME_ASSISTANT_SERVICE_URL", "http://assistant:8105")
    result = asyncio.run(adapter.enzyme_assistant_build(sequence=SEQUENCE, mutations=["not-a-mutation"]))

    assert result["status"] == "blocked_invalid_mutation"
    assert "NOT-A-MUTATION" in result["blocked_reason"]


def test_build_fails_closed_on_empty_mutations(monkeypatch):
    monkeypatch.setenv("ENZYME_ASSISTANT_SERVICE_URL", "http://assistant:8105")
    result = asyncio.run(adapter.enzyme_assistant_build(sequence=SEQUENCE, mutations=[]))

    assert result["status"] == "blocked_invalid_input"


def test_recommend_propagates_service_rejection(monkeypatch):
    request = httpx.Request("POST", "http://assistant:8105/recommend")
    response = httpx.Response(
        400,
        json={"blocked_reason": "Sequence contains invalid residues."},
        request=request,
    )

    async def fake_request(path, payload):
        raise httpx.HTTPStatusError("bad request", request=request, response=response)

    monkeypatch.setattr(adapter, "_request", fake_request)
    monkeypatch.setenv("ENZYME_ASSISTANT_SERVICE_URL", "http://assistant:8105")
    result = asyncio.run(adapter.enzyme_assistant_recommend(sequence=SEQUENCE))

    assert result["status"] == "blocked_invalid_input"
    assert result["blocked_reason"] == "Sequence contains invalid residues."


def test_recommend_returns_unranked_research_only_result(monkeypatch):
    seen = {}

    async def fake_request(path, payload):
        seen.update({"path": path, "payload": payload})
        return {
            "status": "ok",
            "input_sha256": "a" * 64,
            "candidates": [{"mutation": "Q12K", "filter": "可考虑"}],
        }

    monkeypatch.setattr(adapter, "_request", fake_request)
    monkeypatch.setenv("ENZYME_ASSISTANT_SERVICE_URL", "http://assistant:8105")
    result = asyncio.run(adapter.enzyme_assistant_recommend(sequence=SEQUENCE, goal="thermo", n=5))

    assert seen["path"] == "/recommend"
    assert seen["payload"]["use_esm"] is False
    assert seen["payload"]["goal"] == "thermo"
    assert seen["payload"]["nomination_mode"] == "rule_prior"
    assert result["ranked"] is False
    assert result["evidence_level"] == "research_only_heuristic"
    assert result["manual_review_required"] is True
    assert "numbering_note" in result
