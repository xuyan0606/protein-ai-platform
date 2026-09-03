from app.services.candidate_decision import decide_candidate_output


def test_candidate_decision_fails_closed_without_identity():
    decision = decide_candidate_output(
        {"identity_status": "unresolved", "guardrail": {"status": "blocked"}},
        {"status": "ready", "candidate_output_allowed": True},
    )

    assert decision["status"] == "blocked_by_identity_gate"
    assert decision["candidate_output_allowed"] is False
    assert "identity_status_must_be_identified" in decision["blockers"]


def test_candidate_decision_fails_closed_without_objective_assay_gate():
    decision = decide_candidate_output(
        {"identity_status": "identified", "guardrail": {"status": "ready"}},
        {"status": "blocked", "candidate_output_allowed": False},
    )

    assert decision["status"] == "blocked_by_objective_gate"
    assert decision["candidate_output_allowed"] is False


def test_candidate_decision_allows_rows_only_after_both_gates_pass():
    decision = decide_candidate_output(
        {"identity_status": "identified", "guardrail": {"status": "ready"}},
        {"status": "ready", "candidate_output_allowed": True},
    )

    assert decision["status"] == "ready"
    assert decision["candidate_output_allowed"] is True
