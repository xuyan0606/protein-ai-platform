import json
import sys

import validate_human_decision_backlog_fail_closed_consistency as backlog_validator
import validate_human_preflight_package as preflight_validator


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def plate_row(**source_state_overrides):
    source_state = {
        "backlog_rows": 52,
        "review_workspace_rows": 52,
        "packet_rows": 52,
        "blocked_review_workspace_rows": 52,
        "ready_for_feedback_intake_rows": 0,
        "local_intake_rows": 0,
    }
    source_state.update(source_state_overrides)
    return {
        "lane": "plate",
        "source_state": source_state,
        "prohibited_actions": ["do_not_copy_review_workspace_rows_into_local_intake"],
    }


def test_plate_preflight_accepts_dynamic_backlog_count():
    assert preflight_validator.validate_lane(plate_row()) == []


def test_plate_preflight_rejects_workspace_count_drift():
    assert "plate_review_workspace_rows_mismatch" in preflight_validator.validate_lane(
        plate_row(review_workspace_rows=50)
    )


def test_human_backlog_consistency_uses_dynamic_plate_rows(tmp_path, monkeypatch):
    expected = {
        backlog_id: dict(value)
        for backlog_id, value in backlog_validator.EXPECTED_BACKLOG.items()
    }
    expected["human_decision_feedback_source_001"].update({
        "required_rows": 172,
        "completed_rows": 0,
        "missing_rows": 172,
    })
    expected["human_decision_plate_feedback_001"].update({
        "required_rows": 52,
        "missing_rows": 52,
    })
    rows = []
    for backlog_id, value in expected.items():
        row = {
            "backlog_id": backlog_id,
            **value,
            "ready": False,
            "policy": "fail closed",
            "next_action": "human review required",
        }
        rows.append(row)

    backlog_report = {
        "backlog_items": len(rows),
        "open_items": len(rows),
        "ready_items": 0,
        "total_required_rows": sum(row["required_rows"] for row in rows),
        "total_completed_rows": sum(row["completed_rows"] for row in rows),
        "total_missing_rows": sum(row["missing_rows"] for row in rows),
    }
    paths = {
        "backlog_report": tmp_path / "backlog.json",
        "backlog_jsonl": tmp_path / "backlog.jsonl",
        "formal_boundary": tmp_path / "formal_boundary.json",
        "claim_policy": tmp_path / "claim_policy.json",
        "feedback_packets": tmp_path / "feedback_packets.json",
        "feedback_decisions": tmp_path / "feedback_decisions.json",
        "plate_backlog": tmp_path / "plate_backlog.json",
        "output": tmp_path / "out.json",
    }
    write_json(paths["backlog_report"], backlog_report)
    write_jsonl(paths["backlog_jsonl"], rows)
    write_json(paths["formal_boundary"], {"success": True, "draft_rows_counted_as_formal_decisions": 0})
    write_json(paths["claim_policy"], {"success": True, "blocked_claim_ids": [], "expected_blocked_claim_ids": []})
    write_json(paths["feedback_packets"], {"packet_rows": 172})
    write_json(paths["feedback_decisions"], {
        "approved_for_feedback_extraction_rows": 0,
        "candidate_rows": 172,
        "missing_source_review_rows": 172,
    })
    write_json(paths["plate_backlog"], {
        "backlog_rows": 52,
        "draft_rows": 52,
        "packet_rows": 52,
        "blocked_draft_rows": 52,
        "ready_for_feedback_intake_rows": 0,
        "local_intake_rows": 0,
    })

    monkeypatch.setattr(sys, "argv", [
        "validate_human_decision_backlog_fail_closed_consistency.py",
        "--backlog-report", str(paths["backlog_report"]),
        "--backlog-jsonl", str(paths["backlog_jsonl"]),
        "--formal-boundary", str(paths["formal_boundary"]),
        "--claim-policy", str(paths["claim_policy"]),
        "--feedback-source-packets", str(paths["feedback_packets"]),
        "--feedback-source-decisions", str(paths["feedback_decisions"]),
        "--plate-backlog-report", str(paths["plate_backlog"]),
        "--output", str(paths["output"]),
    ])
    assert backlog_validator.main() == 0
    report = json.loads(paths["output"].read_text(encoding="utf-8"))
    assert report["success"] is True
    assert report["plate_feedback_required_rows"] == 52
    assert report["total_missing_rows"] == 1198
