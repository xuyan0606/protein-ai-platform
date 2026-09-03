#!/usr/bin/env python3
"""Register all P700 pending-build lanes as started, without executing them."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p700_p0_real_input_pending_build_checklist.jsonl"
OUT = ROOT / "datasets/governance/p701_p0_pending_build_all_started_board.jsonl"
REPORT = ROOT / "reports/p701_p0_pending_build_all_started_board_report.json"
MD = ROOT / "reports/p701_p0_pending_build_all_started_board.md"

FALSE_FIELDS = ("execution_started", "real_input_received", "evidence_received", "formal_decision_written", "formal_decision_ready", "training_import_allowed", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "p0_unblocked", "p0_completion_ready")

def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source = [r for r in load_jsonl(SOURCE) if r.get("lane") != "summary"]
    source.sort(key=lambda r: int(r.get("pending_build_checklist_order") or 0))
    rows = []
    for order, item in enumerate(source, 1):
        row = {
            "all_started_board_id": f"p701::{item.get('lane')}", "all_started_board_order": order,
            "created_at": created, "lane": item.get("lane"), "source_p700_checklist_id": item.get("pending_build_checklist_id"),
            "all_started": True, "all_started_status": "started_planning_only_blocked_execution",
            "start_scope": "local checklist construction and validation registration only",
            "execution_started": False, "blocker_reason": item.get("blocker_reason"),
            "next_unblocking_evidence": item.get("next_unblocking_evidence"),
            "policy": "P701 registers all pending-build lanes as started for planning only; it does not execute work or authorize any downstream action.",
        }
        row.update({f: False for f in FALSE_FIELDS})
        rows.append(row)
    summary = {"all_started_board_id": "p701::summary", "all_started_board_order": len(rows)+1, "created_at": created, "lane": "summary", "local_only": True, "all_started_board_rows": len(rows), "all_started_rows": len(rows), "execution_started_rows": 0, "real_input_received_rows": 0, "formal_decision_ready_rows": 0, "policy": "Planning registration only; execution and authorization remain fail-closed."}
    summary.update({f: False for f in FALSE_FIELDS})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True)+"\n" for r in rows+[summary]), encoding="utf-8")
    report = {"manifest_id":"P701", "created_at":created, "local_only":True, "all_started_board_rows":len(rows), "all_started_rows":len(rows), "execution_started_rows":0, "real_input_received_rows":0, "formal_decision_ready_rows":0, "artifact_jsonl":str(OUT.relative_to(ROOT)), "artifact_md":str(MD.relative_to(ROOT)), "policy":"P701 is planning-only start registration; no execution or authorization."}
    report.update({f:False for f in FALSE_FIELDS}); report.update({f"{f}_rows":0 for f in FALSE_FIELDS})
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    MD.write_text(f"# P701 all-started board\n\nAll `{len(rows)}` P700 lanes are started for planning/checklist construction only. Execution remains blocked.\n", encoding="utf-8")
    print(json.dumps({"manifest_id":"P701", "all_started_board_rows":len(rows), "execution_started_rows":0, "output":str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__": raise SystemExit(main())
