#!/usr/bin/env python3
"""Build P733 receipt atomicity/integrity guard from P732."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p732_p0_pending_build_review_dispatch_receipt_contract.jsonl"
OUT = ROOT / "datasets/governance/p733_p0_pending_build_review_receipt_atomicity_integrity_guard.jsonl"
REPORT = ROOT / "reports/p733_p0_pending_build_review_receipt_atomicity_integrity_guard_report.json"
MD = ROOT / "reports/p733_p0_pending_build_review_receipt_atomicity_integrity_guard.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "integrity_guard_id": f"p733::{source.get('receipt_contract_id')}",
            "integrity_guard_order": order,
            "created_at": created,
            "boundary": source.get("boundary"),
            "source_p732_id": source.get("receipt_contract_id"),
            "guard_status": "empty_no_receipt_to_check",
            "receipt_present": False,
            "atomic_commit_verified": False,
            "partial_write_detected": False,
            "hash_verified": False,
            "provenance_consistent": False,
            "receipt_validated": False,
            "formal_decision_ready": False,
            "blocker_reason": "No dispatch receipt exists to check for atomicity or integrity.",
            "operator_action": "Do not synthesize, patch, or partially write a receipt.",
            "policy": "P733 is an integrity guard only; it does not create or validate receipts without a real artifact.",
        })
    summary = {
        "integrity_guard_id": "p733::summary", "integrity_guard_order": len(rows) + 1,
        "created_at": created, "boundary": "summary", "integrity_guard_rows": len(rows),
        "receipt_present_rows": 0, "atomic_commit_verified_rows": 0,
        "partial_write_detected_rows": 0, "hash_verified_rows": 0,
        "provenance_consistent_rows": 0, "receipt_validated_rows": 0,
        "formal_decision_ready_rows": 0, "policy": "P733 records empty receipt integrity checks only.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P733", "created_at": created, "local_only": True,
        "integrity_guard_rows": len(rows), "receipt_present_rows": 0,
        "atomic_commit_verified_rows": 0, "partial_write_detected_rows": 0,
        "hash_verified_rows": 0, "provenance_consistent_rows": 0,
        "receipt_validated_rows": 0, "formal_decision_ready_rows": 0,
        "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)),
        "policy": "P733 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P733 review receipt atomicity/integrity guard\n\nRows: `{len(rows)}`. Receipts present: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P733", "integrity_guard_rows": len(rows), "receipt_present_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
