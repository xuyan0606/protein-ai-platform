#!/usr/bin/env python3
"""Validate P733 receipt atomicity/integrity guard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p733_p0_pending_build_review_receipt_atomicity_integrity_guard.jsonl"
REPORT = ROOT / "reports/p733_p0_pending_build_review_receipt_atomicity_integrity_guard_report.json"
OUT = ROOT / "reports/p733_p0_pending_build_review_receipt_atomicity_integrity_guard_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    guards = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(guards) != 5, len(guards))
    for field in ("receipt_present_rows", "atomic_commit_verified_rows", "partial_write_detected_rows", "hash_verified_rows", "provenance_consistent_rows", "receipt_validated_rows", "formal_decision_ready_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(guards, 1):
        fail(f"row_{index}_status", row.get("guard_status") != "empty_no_receipt_to_check", row.get("guard_status"))
        for field in ("receipt_present", "atomic_commit_verified", "partial_write_detected", "hash_verified", "provenance_consistent", "receipt_validated", "formal_decision_ready"):
            expected = False
            fail(f"row_{index}_{field}", row.get(field) is not expected, row.get(field))
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P733", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "integrity_guard_rows": len(guards), "receipt_present_rows": 0,
        "atomic_commit_verified_rows": 0, "partial_write_detected_rows": 0,
        "hash_verified_rows": 0, "provenance_consistent_rows": 0,
        "receipt_validated_rows": 0, "formal_decision_ready_rows": 0,
        "policy": "Validation only; P733 confirms no receipt exists to validate.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "integrity_guard_rows": len(guards), "receipt_present_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
