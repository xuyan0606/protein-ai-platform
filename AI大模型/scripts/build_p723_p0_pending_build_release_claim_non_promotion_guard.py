#!/usr/bin/env python3
"""Build P723 release-claim non-promotion guard from P722."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p722_p0_pending_build_formal_decision_write_authorization_gate.jsonl"
OUT = ROOT / "datasets/governance/p723_p0_pending_build_release_claim_non_promotion_guard.jsonl"
REPORT = ROOT / "reports/p723_p0_pending_build_release_claim_non_promotion_guard_report.json"
MD = ROOT / "reports/p723_p0_pending_build_release_claim_non_promotion_guard.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [row for row in load_jsonl(SOURCE) if row.get("lane") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "non_promotion_guard_id": f"p723::{source.get('authorization_gate_id')}",
            "non_promotion_guard_order": order,
            "created_at": created,
            "lane": source.get("lane"),
            "source_p722_id": source.get("authorization_gate_id"),
            "guard_status": "blocked_claim_non_promotion",
            "formal_decision_approved": False,
            "model_claim_allowed": False,
            "customer_delivery_allowed": False,
            "release_claim_allowed": False,
            "production_claim_allowed": False,
            "claim_promoted": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "blocker_reason": "Formal decision approval and authorization prerequisites are absent.",
            "operator_action": "Do not promote model, delivery, release, or production claims.",
            "policy": "P723 is a non-promotion guard only; it does not create, approve, or publish claims.",
        })
    summary = {
        "non_promotion_guard_id": "p723::summary",
        "non_promotion_guard_order": len(rows) + 1,
        "created_at": created,
        "lane": "summary",
        "non_promotion_guard_rows": len(rows),
        "formal_decision_approved_rows": 0,
        "claim_promoted_rows": 0,
        "release_ready_rows": 0,
        "production_execution_allowed_rows": 0,
        "policy": "P723 confirms all downstream claims remain blocked.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P723", "created_at": created, "local_only": True,
        "non_promotion_guard_rows": len(rows), "formal_decision_approved_rows": 0,
        "claim_promoted_rows": 0, "release_ready_rows": 0, "production_execution_allowed_rows": 0,
        "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)),
        "policy": "P723 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P723 release-claim non-promotion guard\n\nRows: `{len(rows)}`. Claims promoted: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P723", "non_promotion_guard_rows": len(rows), "claim_promoted_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
