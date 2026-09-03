#!/usr/bin/env python3
"""Validate the P482 master readiness stream gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "master_readiness_board.json"
BOARD_VALIDATION = AI_ROOT / "reports" / "master_readiness_board_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p482_master_readiness_stream_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p482_master_readiness_stream_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p482_master_readiness_stream_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    board = load_json(BOARD)
    validation = load_json(BOARD_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    streams = [row for row in board.get("streams") or [] if isinstance(row, dict)]
    blocked_stream_rows = sum(1 for row in streams if row.get("ready") is not True)
    failures: list[dict[str, Any]] = []
    expected_rows = len(streams) + 1

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("stream_audit_rows") != len(streams), failures, "stream_audit_rows_bound", report.get("stream_audit_rows"), len(streams))
    fail_if(report.get("blocked_stream_rows") != blocked_stream_rows, failures, "blocked_stream_rows_bound", report.get("blocked_stream_rows"), blocked_stream_rows)
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("overall_status") != board.get("overall_status"), failures, "overall_status_bound", report.get("overall_status"), board.get("overall_status"))
    fail_if(report.get("overall_status") != "blocked_for_model_claim", failures, "overall_status_blocked", report.get("overall_status"), "blocked_for_model_claim")
    fail_if(report.get("ready_streams") != board.get("ready_streams"), failures, "ready_streams_bound", report.get("ready_streams"), board.get("ready_streams"))
    fail_if(report.get("total_streams") != board.get("total_streams"), failures, "total_streams_bound", report.get("total_streams"), board.get("total_streams"))
    fail_if(report.get("ready_streams") != 1, failures, "ready_streams_one", report.get("ready_streams"), 1)
    fail_if(report.get("total_streams") != 8, failures, "total_streams_eight", report.get("total_streams"), 8)
    fail_if(report.get("data_quality_score") != board.get("data_quality_score"), failures, "data_quality_score_bound", report.get("data_quality_score"), board.get("data_quality_score"))
    fail_if(report.get("validation_success") is not True, failures, "validation_success_true", report.get("validation_success"), True)
    fail_if(report.get("validation_failures") != [], failures, "validation_failures_empty", report.get("validation_failures"), [])
    fail_if(report.get("validation_safe_for_model_claim") is not False, failures, "validation_safe_for_model_claim_false", report.get("validation_safe_for_model_claim"), False)
    fail_if(report.get("validation_release_ready") is not False, failures, "validation_release_ready_false", report.get("validation_release_ready"), False)
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(report.get("claims_allowed") != claim_matrix.get("claims_allowed"), failures, "claims_allowed_bound", report.get("claims_allowed"), claim_matrix.get("claims_allowed"))
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("overall_status") != "blocked_for_model_claim", failures, "source_validation_overall_status", validation.get("overall_status"), "blocked_for_model_claim")
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)

    streams_by_id = {row.get("stream"): row for row in streams}
    seen_streams: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"master_readiness_stream_gap", "master_readiness_stream_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P482 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "master_readiness_stream_gap":
            stream_id = row.get("stream")
            seen_streams.append(stream_id)
            source = streams_by_id.get(stream_id, {})
            fail_if(stream_id not in streams_by_id, failures, "stream_known", {"index": idx, "observed": stream_id}, sorted(streams_by_id))
            fail_if(row.get("stream_status") != source.get("status"), failures, "stream_status_bound", {"index": idx, "observed": row.get("stream_status")}, source.get("status"))
            fail_if(row.get("stream_ready_source") != (source.get("ready") is True), failures, "stream_ready_source_bound", {"index": idx, "observed": row.get("stream_ready_source")}, source.get("ready") is True)
            fail_if(row.get("stream_blocker_count") != len(source.get("blockers") or []), failures, "stream_blocker_count_bound", {"index": idx, "observed": row.get("stream_blocker_count")}, len(source.get("blockers") or []))
        if gap_type == "master_readiness_stream_summary_gap":
            fail_if(row.get("overall_status") != board.get("overall_status"), failures, "summary_overall_status_bound", row.get("overall_status"), board.get("overall_status"))
            fail_if(row.get("ready_streams") != board.get("ready_streams"), failures, "summary_ready_streams_bound", row.get("ready_streams"), board.get("ready_streams"))
            fail_if(row.get("total_streams") != board.get("total_streams"), failures, "summary_total_streams_bound", row.get("total_streams"), board.get("total_streams"))
            fail_if(row.get("blocked_stream_rows") != blocked_stream_rows, failures, "summary_blocked_stream_rows_bound", row.get("blocked_stream_rows"), blocked_stream_rows)

    fail_if(sorted(seen_streams) != sorted(streams_by_id), failures, "streams_exactly_covered", sorted(seen_streams), sorted(streams_by_id))
    fail_if(seen_types.count("master_readiness_stream_gap") != len(streams), failures, "stream_gap_type_count", seen_types.count("master_readiness_stream_gap"), len(streams))
    fail_if(seen_types.count("master_readiness_stream_summary_gap") != 1, failures, "summary_type_count", seen_types.count("master_readiness_stream_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "stream_audit_rows": len(streams),
        "blocked_stream_rows": blocked_stream_rows,
        "overall_status": board.get("overall_status"),
        "ready_streams": board.get("ready_streams"),
        "total_streams": board.get("total_streams"),
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Master readiness stream gaps do not authorize training, claims, delivery, release, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "stream_audit_rows": result["stream_audit_rows"],
        "blocked_stream_rows": result["blocked_stream_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
