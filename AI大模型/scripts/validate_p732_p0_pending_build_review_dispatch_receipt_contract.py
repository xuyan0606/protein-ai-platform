#!/usr/bin/env python3
"""Validate P732 review-dispatch receipt contract."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p732_p0_pending_build_review_dispatch_receipt_contract.jsonl"
REPORT = ROOT / "reports/p732_p0_pending_build_review_dispatch_receipt_contract_report.json"
OUT = ROOT / "reports/p732_p0_pending_build_review_dispatch_receipt_contract_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    contracts = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(contracts) != 5, len(contracts))
    for field in ("dispatch_sent_rows", "dispatch_received_rows", "dispatch_acknowledged_rows", "review_executed_rows", "result_received_rows", "receipt_validated_rows", "formal_decision_ready_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(contracts, 1):
        fail(f"row_{index}_status", row.get("contract_status") != "defined_empty_no_dispatch", row.get("contract_status"))
        fail(f"row_{index}_required_fields", len(row.get("required_fields") or []) != 7, row.get("required_fields"))
        for field in ("dispatch_sent", "dispatch_received", "dispatch_acknowledged", "review_executed", "result_received", "receipt_validated", "formal_decision_ready"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P732", "local_only": True,
        "success": not failures, "failure_count": len(failures), "failures": failures,
        "receipt_contract_rows": len(contracts), "dispatch_sent_rows": 0,
        "dispatch_received_rows": 0, "dispatch_acknowledged_rows": 0,
        "review_executed_rows": 0, "result_received_rows": 0,
        "receipt_validated_rows": 0, "formal_decision_ready_rows": 0,
        "policy": "Validation only; P732 remains empty and fail-closed.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "receipt_contract_rows": len(contracts), "receipt_validated_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
