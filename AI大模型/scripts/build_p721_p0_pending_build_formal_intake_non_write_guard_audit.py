#!/usr/bin/env python3
"""Build P721 formal-intake non-write guard audit from P720."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p720_p0_pending_build_formal_intake_dry_run_guard.jsonl"
OUT = ROOT / "datasets/governance/p721_p0_pending_build_formal_intake_non_write_guard_audit.jsonl"
REPORT = ROOT / "reports/p721_p0_pending_build_formal_intake_non_write_guard_audit_report.json"
MD = ROOT / "reports/p721_p0_pending_build_formal_intake_non_write_guard_audit.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [row for row in load_jsonl(SOURCE) if row.get("lane") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "non_write_guard_id": f"p721::{source.get('intake_guard_id')}",
            "non_write_guard_order": order,
            "created_at": created,
            "lane": source.get("lane"),
            "source_p720_id": source.get("intake_guard_id"),
            "guard_status": "open_non_write_fail_closed",
            "formal_intake_dry_run_executed": False,
            "formal_intake_written": False,
            "runtime_receipt_written": False,
            "training_label_written": False,
            "reviewed_decision_written": False,
            "formal_decision_ready": False,
            "blocker_reason": "No qualifying input, evidence, route, or validator result exists; all writes remain prohibited.",
            "operator_action": "Do not write intake, receipt, label, decision, release, or authorization artifacts.",
            "policy": "P721 is an audit-only non-write guard; it performs no intake, write, execution, or authorization.",
        })
    summary = {
        "non_write_guard_id": "p721::summary",
        "non_write_guard_order": len(rows) + 1,
        "created_at": created,
        "lane": "summary",
        "non_write_guard_rows": len(rows),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_written_rows": 0,
        "runtime_receipt_written_rows": 0,
        "training_label_written_rows": 0,
        "reviewed_decision_written_rows": 0,
        "formal_decision_ready_rows": 0,
        "policy": "P721 confirms all formal-intake writes remain blocked.",
    }
    OUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]),
        encoding="utf-8",
    )
    report = {
        "manifest_id": "P721",
        "created_at": created,
        "local_only": True,
        "non_write_guard_rows": len(rows),
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_written_rows": 0,
        "runtime_receipt_written_rows": 0,
        "training_label_written_rows": 0,
        "reviewed_decision_written_rows": 0,
        "formal_decision_ready_rows": 0,
        "artifact_jsonl": str(OUT.relative_to(ROOT)),
        "artifact_md": str(MD.relative_to(ROOT)),
        "policy": "P721 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(
        f"# P721 formal-intake non-write guard audit\n\nRows: `{len(rows)}`. All intake/receipt/label/decision writes: `0`.\n",
        encoding="utf-8",
    )
    print(json.dumps({"manifest_id": "P721", "non_write_guard_rows": len(rows), "formal_intake_written_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
