#!/usr/bin/env python3
"""Build P732 review-dispatch receipt contract from P731."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p731_p0_pending_build_review_dispatch_readiness.jsonl"
OUT = ROOT / "datasets/governance/p732_p0_pending_build_review_dispatch_receipt_contract.jsonl"
REPORT = ROOT / "reports/p732_p0_pending_build_review_dispatch_receipt_contract_report.json"
MD = ROOT / "reports/p732_p0_pending_build_review_dispatch_receipt_contract.md"
REQUIRED_FIELDS = ("dispatch_id", "target_id", "sent_at", "received_at", "acknowledged_at", "result", "provenance")


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "receipt_contract_id": f"p732::{source.get('dispatch_readiness_id')}",
            "receipt_contract_order": order,
            "created_at": created,
            "boundary": source.get("boundary"),
            "source_p731_id": source.get("dispatch_readiness_id"),
            "contract_status": "defined_empty_no_dispatch",
            "required_fields": list(REQUIRED_FIELDS),
            "dispatch_sent": False,
            "dispatch_received": False,
            "dispatch_acknowledged": False,
            "review_executed": False,
            "result_received": False,
            "receipt_validated": False,
            "formal_decision_ready": False,
            "rejection_rule": "Reject missing identity, timestamps, result, or provenance.",
            "policy": "P732 defines a receipt contract only; it does not dispatch, acknowledge, execute, or validate review work.",
        })
    summary = {
        "receipt_contract_id": "p732::summary", "receipt_contract_order": len(rows) + 1,
        "created_at": created, "boundary": "summary", "receipt_contract_rows": len(rows),
        "dispatch_sent_rows": 0, "dispatch_received_rows": 0, "dispatch_acknowledged_rows": 0,
        "review_executed_rows": 0, "result_received_rows": 0, "receipt_validated_rows": 0,
        "formal_decision_ready_rows": 0, "policy": "P732 records empty receipt contracts only.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P732", "created_at": created, "local_only": True,
        "receipt_contract_rows": len(rows), "dispatch_sent_rows": 0,
        "dispatch_received_rows": 0, "dispatch_acknowledged_rows": 0,
        "review_executed_rows": 0, "result_received_rows": 0,
        "receipt_validated_rows": 0, "formal_decision_ready_rows": 0,
        "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)),
        "policy": "P732 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P732 review-dispatch receipt contract\n\nContracts: `{len(rows)}`. Receipts validated: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P732", "receipt_contract_rows": len(rows), "receipt_validated_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
