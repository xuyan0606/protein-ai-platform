#!/usr/bin/env python3
"""Validate the P28 experiment-feedback source-review gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET_REPORT = AI_ROOT / "reports" / "experiment_feedback_source_review_packet_report.json"
VALIDATION_REPORT = AI_ROOT / "reports" / "experiment_feedback_source_review_decision_validation_report.json"
AUDIT = AI_ROOT / "datasets" / "feedback" / "p28_feedback_source_review_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p28_feedback_source_review_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p28_feedback_source_review_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    packet_report = load_json(PACKET_REPORT)
    validation = load_json(VALIDATION_REPORT)
    report = load_json(REPORT)
    audit_rows = load_jsonl(AUDIT)
    packets = packet_report.get("packet_reports") or []
    expected_rows = len(packets) + 1
    candidate_rows = int(validation.get("candidate_rows") or packet_report.get("input_rows") or 0)
    decision_rows = int(validation.get("decision_rows") or 0)
    valid_rows = int(validation.get("valid_rows") or 0)
    failures: list[dict[str, Any]] = []

    def check(condition: bool, name: str, observed: Any, expected: Any) -> None:
        if condition:
            failures.append({"check": name, "observed": observed, "expected": expected})

    check(len(audit_rows) != expected_rows, "audit_rows_exact", len(audit_rows), expected_rows)
    check(report.get("audit_rows") != expected_rows, "report_audit_rows_exact", report.get("audit_rows"), expected_rows)
    check(report.get("packet_audit_rows") != len(packets), "packet_audit_rows_exact", report.get("packet_audit_rows"), len(packets))
    check(report.get("candidate_rows") != candidate_rows, "candidate_rows_bound", report.get("candidate_rows"), candidate_rows)
    check(report.get("decision_rows") != decision_rows, "decision_rows_bound", report.get("decision_rows"), decision_rows)
    check(report.get("valid_rows") != valid_rows, "valid_rows_bound", report.get("valid_rows"), valid_rows)
    check(report.get("missing_source_review_rows") != validation.get("missing_source_review_rows"), "missing_rows_bound", report.get("missing_source_review_rows"), validation.get("missing_source_review_rows"))
    check(report.get("approved_for_feedback_extraction_rows") != 0, "approved_extraction_zero", report.get("approved_for_feedback_extraction_rows"), 0)
    check(report.get("approved_for_feedback_intake_rows") != 0, "approved_intake_zero", report.get("approved_for_feedback_intake_rows"), 0)
    check(report.get("ready_for_feedback_extraction") is not False, "ready_extraction_false", report.get("ready_for_feedback_extraction"), False)
    check(report.get("ready_for_feedback_intake") is not False, "ready_intake_false", report.get("ready_for_feedback_intake"), False)
    check(report.get("completion_ready") is not False, "completion_ready_false", report.get("completion_ready"), False)
    for idx, row in enumerate(audit_rows):
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            check(row.get(field) is not False, f"{field}_false", {"index": idx, "observed": row.get(field)}, False)
        check(row.get("completion_ready") is not False, "row_completion_ready_false", {"index": idx, "observed": row.get("completion_ready")}, False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "packet_audit_rows": len(packets),
        "candidate_rows": candidate_rows,
        "decision_rows": decision_rows,
        "valid_rows": valid_rows,
        "missing_source_review_rows": validation.get("missing_source_review_rows"),
        "approved_for_feedback_extraction_rows": 0,
        "approved_for_feedback_intake_rows": 0,
        "ready_for_feedback_extraction": False,
        "ready_for_feedback_intake": False,
        "completion_ready": False,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Source-review packets are not source approval or feedback intake.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "audit_rows": len(audit_rows), "candidate_rows": candidate_rows, "decision_rows": decision_rows, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
