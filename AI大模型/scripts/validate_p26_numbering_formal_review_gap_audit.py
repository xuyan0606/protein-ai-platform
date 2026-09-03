#!/usr/bin/env python3
"""Validate the P26 numbering formal-review gap audit."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET_BOARD = AI_ROOT / "datasets" / "curation" / "numbering_review_packet_board.jsonl"
PACKET_REPORT = AI_ROOT / "reports" / "numbering_review_packet_board_report.json"
BRIEFING_BOARD = AI_ROOT / "datasets" / "curation" / "numbering_review_briefing_status_board.jsonl"
BRIEFING_REPORT = AI_ROOT / "reports" / "numbering_review_briefing_status_board_report.json"
AUDIT = AI_ROOT / "datasets" / "curation" / "p26_numbering_formal_review_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p26_numbering_formal_review_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p26_numbering_formal_review_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    packet_rows = load_jsonl(PACKET_BOARD)
    packet_report = load_json(PACKET_REPORT)
    briefing_rows = load_jsonl(BRIEFING_BOARD)
    briefing_report = load_json(BRIEFING_REPORT)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    expected_total = len(packet_rows) + len(briefing_rows)

    fail_if(len(audit_rows) != expected_total, failures, "audit_rows_expected", len(audit_rows), expected_total)
    fail_if(report.get("audit_rows") != expected_total, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_total)
    fail_if(report.get("packet_audit_rows") != len(packet_rows), failures, "packet_audit_rows_bound", report.get("packet_audit_rows"), len(packet_rows))
    fail_if(report.get("briefing_audit_rows") != len(briefing_rows), failures, "briefing_audit_rows_bound", report.get("briefing_audit_rows"), len(briefing_rows))
    fail_if(report.get("packet_report_rows") != packet_report.get("packet_board_rows"), failures, "packet_report_rows_bound", report.get("packet_report_rows"), packet_report.get("packet_board_rows"))
    fail_if(report.get("briefing_report_rows") != briefing_report.get("status_rows"), failures, "briefing_report_rows_bound", report.get("briefing_report_rows"), briefing_report.get("status_rows"))
    fail_if(report.get("packet_completion_ready_rows") != 0, failures, "packet_completion_ready_zero", report.get("packet_completion_ready_rows"), 0)
    fail_if(report.get("briefing_completion_ready_rows") != 0, failures, "briefing_completion_ready_zero", report.get("briefing_completion_ready_rows"), 0)
    fail_if(report.get("formal_review_rows") != 0, failures, "formal_review_rows_zero", report.get("formal_review_rows"), 0)

    packet_audit = [row for row in audit_rows if row.get("gap_type") == "numbering_review_packet"]
    briefing_audit = [row for row in audit_rows if row.get("gap_type") == "numbering_review_briefing"]
    fail_if(len(packet_audit) != len(packet_rows), failures, "packet_audit_count_exact", len(packet_audit), len(packet_rows))
    fail_if(len(briefing_audit) != len(briefing_rows), failures, "briefing_audit_count_exact", len(briefing_audit), len(briefing_rows))

    for idx, row in enumerate(packet_audit):
        fail_if(row.get("completion_ready") is not False, failures, "packet_completion_ready_false", {"index": idx, "observed": row.get("completion_ready")}, False)
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(row.get(field) is not False, failures, f"packet_{field}_false", {"index": idx, "observed": row.get(field)}, False)
    for idx, row in enumerate(briefing_audit):
        fail_if(row.get("completion_ready") is not False, failures, "briefing_completion_ready_false", {"index": idx, "observed": row.get("completion_ready")}, False)
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(row.get(field) is not False, failures, f"briefing_{field}_false", {"index": idx, "observed": row.get(field)}, False)

    fail_if(report.get("packet_status_counts") != dict(sorted(Counter(row.get("packet_status") for row in packet_rows).items())), failures, "packet_status_counts_bound", report.get("packet_status_counts"), dict(sorted(Counter(row.get("packet_status") for row in packet_rows).items())))
    fail_if(report.get("briefing_status_counts") != dict(sorted(Counter(row.get("briefing_status") for row in briefing_rows).items())), failures, "briefing_status_counts_bound", report.get("briefing_status_counts"), dict(sorted(Counter(row.get("briefing_status") for row in briefing_rows).items())))
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "packet_audit_rows": len(packet_audit),
        "briefing_audit_rows": len(briefing_audit),
        "packet_open_blocked_rows": packet_report.get("open_blocked_packet_rows"),
        "briefing_open_blocked_rows": briefing_report.get("open_blocked_briefing_rows"),
        "failures": failures,
        "formal_review_rows": 0,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Numbering packet and briefing rows remain human-review navigation artifacts and do not authorize downstream use.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "audit_rows": validation["audit_rows"],
        "packet_audit_rows": validation["packet_audit_rows"],
        "briefing_audit_rows": validation["briefing_audit_rows"],
        "formal_review_rows": 0,
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
