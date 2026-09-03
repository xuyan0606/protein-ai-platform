#!/usr/bin/env python3
"""Build P729 blocker monitoring/review-cycle board from P728."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p728_p0_pending_build_stop_restart_entry_board.jsonl"
OUT = ROOT / "datasets/governance/p729_p0_pending_build_blocker_monitoring_review_cycle.jsonl"
REPORT = ROOT / "reports/p729_p0_pending_build_blocker_monitoring_review_cycle_report.json"
MD = ROOT / "reports/p729_p0_pending_build_blocker_monitoring_review_cycle.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "monitoring_id": f"p729::{source.get('stop_restart_id')}",
            "monitoring_order": order,
            "created_at": created,
            "boundary": source.get("boundary"),
            "source_p728_id": source.get("stop_restart_id"),
            "monitoring_status": "blocked_pending_periodic_review",
            "review_cycle_defined": True,
            "review_due": False,
            "review_executed": False,
            "staleness_reassessed": False,
            "new_evidence_detected": False,
            "restart_trigger_validated": False,
            "restart_authorized": False,
            "work_restarted": False,
            "formal_decision_ready": False,
            "blocker_reason": "Stop condition remains active and no new qualifying evidence is present.",
            "review_action": "Recheck only on the defined cycle; do not infer progress from unchanged state.",
            "policy": "P729 monitors blocker state only; it does not create evidence, restart work, or authorize action.",
        })
    summary = {
        "monitoring_id": "p729::summary", "monitoring_order": len(rows) + 1,
        "created_at": created, "boundary": "summary", "monitoring_rows": len(rows),
        "review_cycle_defined_rows": len(rows), "review_due_rows": 0,
        "review_executed_rows": 0, "staleness_reassessed_rows": 0,
        "new_evidence_detected_rows": 0, "restart_trigger_validated_rows": 0,
        "restart_authorized_rows": 0, "work_restarted_rows": 0,
        "formal_decision_ready_rows": 0, "policy": "P729 confirms monitoring without progression.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P729", "created_at": created, "local_only": True,
        "monitoring_rows": len(rows), "review_cycle_defined_rows": len(rows),
        "review_due_rows": 0, "review_executed_rows": 0, "staleness_reassessed_rows": 0,
        "new_evidence_detected_rows": 0, "restart_trigger_validated_rows": 0,
        "restart_authorized_rows": 0, "work_restarted_rows": 0,
        "formal_decision_ready_rows": 0, "artifact_jsonl": str(OUT.relative_to(ROOT)),
        "artifact_md": str(MD.relative_to(ROOT)), "policy": "P729 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P729 blocker monitoring/review cycle\n\nBoundaries: `{len(rows)}`. Review executed: `0`; restarted: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P729", "monitoring_rows": len(rows), "review_executed_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
