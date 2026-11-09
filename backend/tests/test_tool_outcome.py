from app.core.tool_outcome import normalize_tool_exception, normalize_tool_result
from app.services.task_evidence import classify_task_evidence


def test_timeout_is_terminal_and_never_completed():
    outcome = normalize_tool_exception(TimeoutError("folding timed out"))

    assert outcome.status == "timeout"
    assert outcome.terminal is True
    assert outcome.claim_eligible is False
    assert outcome.reason == "folding timed out"


def test_result_statuses_preserve_pending_receipts_and_terminal_states():
    assert normalize_tool_result({"status": "completed_geometry_scan"}).status == "completed"
    assert normalize_tool_result({"status": "blocked_missing_engine"}).status == "blocked"
    assert normalize_tool_result({"status": "failed", "error": "bad"}).status == "failed"
    assert normalize_tool_result({"status": "cancelled"}).status == "failed"
    assert normalize_tool_result({"status": "timeout", "error": "slow"}).status == "timeout"
    assert normalize_tool_result({"status": "ready", "claim_eligible": False}).status == "blocked"
    assert normalize_tool_result("scalar result").status == "completed"
    for raw in ("submitted", "pending", "running", "queued", "started"):
        outcome = normalize_tool_result({"status": raw, "task_id": "task-1", "claim_eligible": False})
        assert outcome.status == "submitted"
        assert outcome.terminal is False
        assert outcome.claim_eligible is False


def test_research_only_result_is_completed_but_not_claim_eligible():
    result = {
        "status": "ok",
        "evidence_level": "research_only_heuristic",
        "candidates": [{"mutation": "Q12K"}],
    }
    outcome = normalize_tool_result(result)

    assert outcome.status == "completed"
    assert outcome.terminal is True
    assert outcome.claim_eligible is False


def test_research_only_evidence_is_rejected_rather_than_promoted():
    partition = classify_task_evidence([
        {
            "tool_name": "enzyme_assistant_recommend",
            "status": "completed",
            "result": '{"status":"ok","evidence_level":"research_only_heuristic"}',
        },
        {
            "tool_name": "predict_properties",
            "status": "completed",
            "result": '{"status":"completed","length":120}',
        },
    ])

    assert [item["tool_name"] for item in partition["scientific_evidence"]] == ["predict_properties"]
    assert [item["tool_name"] for item in partition["rejected_terminal_results"]] == ["enzyme_assistant_recommend"]
    assert partition["records"][0]["tool_status"] == "completed"
    assert partition["records"][0]["evidence_status"] == "rejected"
