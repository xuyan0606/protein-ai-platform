#!/usr/bin/env python3
"""Build P731 review-dispatch readiness board from P730."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p730_p0_pending_build_next_review_action_checklist.jsonl"
OUT = ROOT / "datasets/governance/p731_p0_pending_build_review_dispatch_readiness.jsonl"
REPORT = ROOT / "reports/p731_p0_pending_build_review_dispatch_readiness_report.json"
MD = ROOT / "reports/p731_p0_pending_build_review_dispatch_readiness.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "dispatch_readiness_id": f"p731::{source.get('next_review_id')}",
            "dispatch_readiness_order": order,
            "created_at": created,
            "boundary": source.get("boundary"),
            "source_p730_id": source.get("next_review_id"),
            "dispatch_status": "blocked_not_ready",
            "dispatch_target_defined": False,
            "dispatch_authorized": False,
            "execution_window_defined": False,
            "receipt_contract_defined": True,
            "review_dispatched": False,
            "review_executed": False,
            "formal_decision_ready": False,
            "blocker_reason": "No approved target, dispatch authorization, or execution window exists.",
            "operator_action": "Keep review queued; do not dispatch or execute.",
            "policy": "P731 is dispatch-readiness planning only; it does not send work or authorize execution.",
        })
    summary = {
        "dispatch_readiness_id": "p731::summary", "dispatch_readiness_order": len(rows) + 1,
        "created_at": created, "boundary": "summary", "dispatch_readiness_rows": len(rows),
        "dispatch_target_defined_rows": 0, "dispatch_authorized_rows": 0,
        "execution_window_defined_rows": 0, "review_dispatched_rows": 0,
        "review_executed_rows": 0, "formal_decision_ready_rows": 0,
        "policy": "P731 records blocked dispatch readiness only.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P731", "created_at": created, "local_only": True,
        "dispatch_readiness_rows": len(rows), "dispatch_target_defined_rows": 0,
        "dispatch_authorized_rows": 0, "execution_window_defined_rows": 0,
        "review_dispatched_rows": 0, "review_executed_rows": 0,
        "formal_decision_ready_rows": 0, "artifact_jsonl": str(OUT.relative_to(ROOT)),
        "artifact_md": str(MD.relative_to(ROOT)), "policy": "P731 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P731 review-dispatch readiness\n\nRows: `{len(rows)}`. Dispatched: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P731", "dispatch_readiness_rows": len(rows), "review_dispatched_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
