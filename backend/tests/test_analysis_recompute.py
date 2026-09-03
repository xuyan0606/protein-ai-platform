from app.services.analysis_recompute import build_recompute_decision


def test_async_completion_does_not_implicitly_authorize_report_mutation():
    decision = build_recompute_decision(
        analysis_fingerprint="analysis-v1",
        tool_results=[{"tool_name": "blast_search", "status": "completed", "result": '{"status":"completed","results_count":1}'}],
        requested=False,
    )

    assert decision["status"] == "explicit_recompute_required"
    assert decision["report_mutation_allowed"] is False


def test_explicit_recompute_waits_for_submitted_task_terminal_state():
    decision = build_recompute_decision(
        analysis_fingerprint="analysis-v1",
        tool_results=[{"tool_name": "gromacs_md", "status": "submitted", "result": '{"task_id":"md-1"}'}],
        requested=True,
    )

    assert decision["status"] == "tasks_not_terminal"
    assert decision["report_mutation_allowed"] is False


def test_explicit_recompute_requires_usable_terminal_payload():
    decision = build_recompute_decision(
        analysis_fingerprint="analysis-v1",
        tool_results=[{"tool_name": "gromacs_md", "status": "completed", "result": '{"status":"blocked"}'}],
        requested=True,
    )

    assert decision["status"] == "terminal_task_result_rejected"
    assert decision["report_mutation_allowed"] is False


def test_explicit_recompute_creates_new_evidence_snapshot_fingerprint():
    decision = build_recompute_decision(
        analysis_fingerprint="analysis-v1",
        tool_results=[{"tool_name": "blast_search", "status": "completed", "result": '{"status":"completed","results_count":1}'}],
        requested=True,
    )

    assert decision["status"] == "recompute_ready"
    assert decision["report_mutation_allowed"] is True
    assert len(decision["evidence_snapshot_fingerprint"]) == 64
