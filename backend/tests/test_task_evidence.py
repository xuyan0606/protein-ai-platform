from app.services.task_evidence import classify_task_evidence


def test_submitted_task_is_a_receipt_not_scientific_evidence():
    result = classify_task_evidence([
        {"tool_name": "blast_search", "status": "submitted", "result": '{"task_id":"x"}'},
    ])

    assert result["scientific_evidence"] == []
    assert result["task_receipts"][0]["tool_name"] == "blast_search"


def test_completed_but_blocked_payload_is_not_scientific_evidence():
    result = classify_task_evidence([
        {"tool_name": "gromacs_md", "status": "completed", "result": '{"status":"blocked","reason":"missing topology"}'},
    ])

    assert result["scientific_evidence"] == []
    assert result["rejected_terminal_results"][0]["tool_name"] == "gromacs_md"


def test_completed_usable_payload_is_scientific_evidence():
    result = classify_task_evidence([
        {"tool_name": "blast_search", "status": "completed", "result": '{"status":"completed","results_count":1}'},
    ])

    assert result["scientific_evidence"][0]["tool_name"] == "blast_search"
    assert result["task_receipts"] == []


def test_completed_blast_with_degraded_payload_is_rejected():
    result = classify_task_evidence([{
        "tool_name": "blast_search", "status": "completed",
        "result": {"status": "degraded", "error_code": "BLAST_TIMEOUT", "results_count": 0,
                   "evidence_source": {"status": "degraded"}},
    }])
    assert result["scientific_evidence"] == []
    assert len(result["rejected_terminal_results"]) == 1


def test_cached_blast_cannot_be_promoted_to_live_scientific_evidence():
    for payload_status in ("completed", "stale_cache"):
        result = classify_task_evidence([{
            "tool_name": "blast_search", "status": "completed",
            "result": {"status": payload_status, "results_count": 1,
                       "evidence_source": {"status": "degraded", "mode": "cache_hit"}},
        }])
        assert result["scientific_evidence"] == []
