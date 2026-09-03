#!/usr/bin/env python3
"""Build P730 next-review action checklist from P729 monitoring rows."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p729_p0_pending_build_blocker_monitoring_review_cycle.jsonl"
OUT = ROOT / "datasets/governance/p730_p0_pending_build_next_review_action_checklist.jsonl"
REPORT = ROOT / "reports/p730_p0_pending_build_next_review_action_checklist_report.json"
MD = ROOT / "reports/p730_p0_pending_build_next_review_action_checklist.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "next_review_id": f"p730::{source.get('monitoring_id')}",
            "next_review_order": order,
            "created_at": created,
            "boundary": source.get("boundary"),
            "source_p729_id": source.get("monitoring_id"),
            "review_action_status": "queued_not_executed",
            "review_object": "Check whether qualifying external input, evidence, owner acknowledgement, validator result, or authorization has arrived.",
            "required_input": "Source-bound response or evidence receipt.",
            "acceptance_condition": "Only independently verifiable, provenance-bearing material may change state.",
            "prohibited_action": "Do not infer progress, restart work, write decisions, release, deliver, or execute production.",
            "review_scheduled": True,
            "review_executed": False,
            "new_evidence_detected": False,
            "restart_authorized": False,
            "work_restarted": False,
            "formal_decision_ready": False,
            "policy": "P730 is a queued review-action checklist only; it does not perform review or authorize action.",
        })
    summary = {
        "next_review_id": "p730::summary", "next_review_order": len(rows) + 1,
        "created_at": created, "boundary": "summary", "next_review_rows": len(rows),
        "review_scheduled_rows": len(rows), "review_executed_rows": 0,
        "new_evidence_detected_rows": 0, "restart_authorized_rows": 0,
        "work_restarted_rows": 0, "formal_decision_ready_rows": 0,
        "policy": "P730 records queued review actions only.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P730", "created_at": created, "local_only": True,
        "next_review_rows": len(rows), "review_scheduled_rows": len(rows),
        "review_executed_rows": 0, "new_evidence_detected_rows": 0,
        "restart_authorized_rows": 0, "work_restarted_rows": 0,
        "formal_decision_ready_rows": 0, "artifact_jsonl": str(OUT.relative_to(ROOT)),
        "artifact_md": str(MD.relative_to(ROOT)), "policy": "P730 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P730 next-review action checklist\n\nQueued review actions: `{len(rows)}`. Executed: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P730", "next_review_rows": len(rows), "review_scheduled_rows": len(rows), "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
