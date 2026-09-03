#!/usr/bin/env python3
"""Validate P771 receipt-to-decision lineage gates."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p770_p0_pending_build_review_receipt_freshness_gate.jsonl"; BOARD = ROOT / "datasets/governance/p771_p0_pending_build_receipt_to_decision_lineage_gate.jsonl"; REPORT = ROOT / "reports/p771_p0_pending_build_receipt_to_decision_lineage_gate_report.json"; OUT = ROOT / "reports/p771_p0_pending_build_receipt_to_decision_lineage_gate_validation_report.json"
FIELDS = ("receipt_present", "evidence_linked", "review_route_linked", "decision_target_linked", "authorization_chain_linked", "lineage_complete", "formal_decision_written", "formal_decision_ready", "restart_authorized")
def main() -> int:
    source = [row for row in load_jsonl(SOURCE) if row.get("boundary") != "summary"]; rows = load_jsonl(BOARD); gates = rows[:-1] if rows else []; summary = rows[-1] if rows else {}; report = load_json(REPORT); failures = []
    def fail(check, condition, observed, expected):
        if condition: failures.append({"check": check, "observed": observed, "expected": expected})
    fail("source_rows", len(source) != 5, len(source), 5); fail("lineage_gate_rows", len(gates) != 5, len(gates), 5); fail("summary", summary.get("boundary") != "summary", summary.get("boundary"), "summary"); fail("coverage", {row.get("source_p770_id") for row in gates} != {row.get("freshness_gate_id") for row in source}, "mismatch", "exact")
    for field in FIELDS: fail(field, report.get(f"{field}_rows") != 0, report.get(f"{field}_rows"), 0)
    for index, row in enumerate(gates, 1):
        fail(f"row_{index}_status", row.get("gate_status") != "empty_no_receipt_lineage_to_decide", row.get("gate_status"), "empty_no_receipt_lineage_to_decide")
        for field in FIELDS: fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field), False)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "manifest_id": "P771", "local_only": True, "success": not failures, "failure_count": len(failures), "failures": failures, "lineage_gate_rows": len(gates), **{f"{field}_rows": 0 for field in FIELDS}, "policy": "Validation only; P771 keeps lineage, decisions, and restart blocked."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"success": result["success"], "lineage_gate_rows": len(gates), "lineage_complete_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False)); return 0 if not failures else 1
if __name__ == "__main__": raise SystemExit(main())
