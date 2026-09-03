#!/usr/bin/env python3
"""Build P726 production-execution non-authorization guard from P725."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p725_p0_pending_build_customer_delivery_non_authorization_guard.jsonl"
OUT = ROOT / "datasets/governance/p726_p0_pending_build_production_execution_non_authorization_guard.jsonl"
REPORT = ROOT / "reports/p726_p0_pending_build_production_execution_non_authorization_guard_report.json"
MD = ROOT / "reports/p726_p0_pending_build_production_execution_non_authorization_guard.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("lane") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "production_guard_id": f"p726::{source.get('delivery_guard_id')}",
            "production_guard_order": order,
            "created_at": created,
            "lane": source.get("lane"),
            "source_p725_id": source.get("delivery_guard_id"),
            "guard_status": "blocked_production_execution_non_authorization",
            "formal_decision_approved": False,
            "release_approved": False,
            "customer_scope_confirmed": False,
            "production_change_reviewed": False,
            "production_execution_authorized": False,
            "production_execution_started": False,
            "production_execution_allowed": False,
            "release_ready": False,
            "blocker_reason": "Formal decision, release approval, customer scope, and production review are absent.",
            "operator_action": "Do not start or authorize production execution.",
            "policy": "P726 is a non-authorization guard only; it does not deploy, execute, or authorize production changes.",
        })
    summary = {
        "production_guard_id": "p726::summary", "production_guard_order": len(rows) + 1,
        "created_at": created, "lane": "summary", "production_guard_rows": len(rows),
        "formal_decision_approved_rows": 0, "release_approved_rows": 0,
        "customer_scope_confirmed_rows": 0, "production_change_reviewed_rows": 0,
        "production_execution_authorized_rows": 0, "production_execution_started_rows": 0,
        "production_execution_allowed_rows": 0, "release_ready_rows": 0,
        "policy": "P726 confirms production execution remains unauthorized.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P726", "created_at": created, "local_only": True,
        "production_guard_rows": len(rows), "formal_decision_approved_rows": 0,
        "release_approved_rows": 0, "customer_scope_confirmed_rows": 0,
        "production_change_reviewed_rows": 0, "production_execution_authorized_rows": 0,
        "production_execution_started_rows": 0, "production_execution_allowed_rows": 0,
        "release_ready_rows": 0, "artifact_jsonl": str(OUT.relative_to(ROOT)),
        "artifact_md": str(MD.relative_to(ROOT)), "policy": "P726 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P726 production-execution non-authorization guard\n\nRows: `{len(rows)}`. Production execution authorized: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P726", "production_guard_rows": len(rows), "production_execution_authorized_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
