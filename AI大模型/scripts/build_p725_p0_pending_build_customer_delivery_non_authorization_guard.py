#!/usr/bin/env python3
"""Build P725 customer-delivery non-authorization guard from P724."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p724_p0_pending_build_model_claim_non_assertion_guard.jsonl"
OUT = ROOT / "datasets/governance/p725_p0_pending_build_customer_delivery_non_authorization_guard.jsonl"
REPORT = ROOT / "reports/p725_p0_pending_build_customer_delivery_non_authorization_guard_report.json"
MD = ROOT / "reports/p725_p0_pending_build_customer_delivery_non_authorization_guard.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [row for row in load_jsonl(SOURCE) if row.get("lane") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "delivery_guard_id": f"p725::{source.get('non_assertion_guard_id')}",
            "delivery_guard_order": order,
            "created_at": created,
            "lane": source.get("lane"),
            "source_p724_id": source.get("non_assertion_guard_id"),
            "guard_status": "blocked_customer_delivery_non_authorization",
            "formal_decision_approved": False,
            "customer_scope_confirmed": False,
            "delivery_artifact_validated": False,
            "customer_delivery_authorized": False,
            "customer_delivery_ready": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "blocker_reason": "Formal approval, customer scope, and validated delivery artifact are absent.",
            "operator_action": "Do not authorize, package, or deliver customer-facing output.",
            "policy": "P725 is a non-authorization guard only; it does not prepare or deliver customer artifacts.",
        })
    summary = {
        "delivery_guard_id": "p725::summary", "delivery_guard_order": len(rows) + 1,
        "created_at": created, "lane": "summary", "delivery_guard_rows": len(rows),
        "formal_decision_approved_rows": 0, "customer_scope_confirmed_rows": 0,
        "delivery_artifact_validated_rows": 0, "customer_delivery_authorized_rows": 0,
        "customer_delivery_ready_rows": 0, "release_ready_rows": 0,
        "production_execution_allowed_rows": 0,
        "policy": "P725 confirms customer delivery remains unauthorized.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P725", "created_at": created, "local_only": True,
        "delivery_guard_rows": len(rows), "formal_decision_approved_rows": 0,
        "customer_scope_confirmed_rows": 0, "delivery_artifact_validated_rows": 0,
        "customer_delivery_authorized_rows": 0, "customer_delivery_ready_rows": 0,
        "release_ready_rows": 0, "production_execution_allowed_rows": 0,
        "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)),
        "policy": "P725 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P725 customer-delivery non-authorization guard\n\nRows: `{len(rows)}`. Delivery authorized: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P725", "delivery_guard_rows": len(rows), "customer_delivery_authorized_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
