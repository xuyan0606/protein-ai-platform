import asyncio

from app.tools.blast_search import _POLL_BUDGET_SECONDS, _build_poll_schedule
from app.tools.esmfold_folding import _esmfold_api_fallback
from app.tools.protssn_score import protssn_score


def test_esmfold_api_fallback_is_torch_free():
    result = asyncio.run(_esmfold_api_fallback("ACDEFGHIKLMNPQRSTVWY"))

    assert result["status"] == "fallback"
    assert result["capability_status"] == "proxy"
    assert result["version"] == "proxy-mvp"
    assert result["checkpoint_or_weight"] is None
    assert result["input_sha256"]
    assert result["runtime"] is None
    assert result["logs"] == []
    assert result["artifact_manifest"]["total_count"] == 0
    assert result["scientific_boundary"]
    assert result["failure_reason"]
    assert result["esm2_embedding_available"] is False
    assert result["sequence_length"] == 20


def test_protssn_score_fallback_handles_missing_torch():
    result = protssn_score("ACDEFGHIKL", ["A1G", "A2G"])

    assert len(result["mutations"]) == 2
    assert result["mutations"][0]["mutation"] == "A1G"
    assert "combined_score" in result["mutations"][0]
    assert result["mutations"][1]["error"] == "Wild-type residue mismatch at 2: expected C, got A"


def test_blast_poll_schedule_stays_within_budget():
    schedule = _build_poll_schedule(30)

    assert schedule
    assert sum(schedule) <= _POLL_BUDGET_SECONDS
