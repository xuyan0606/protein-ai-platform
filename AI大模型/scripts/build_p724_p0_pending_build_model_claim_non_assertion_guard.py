#!/usr/bin/env python3
"""Build P724 model-claim non-assertion guard from P723."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p723_p0_pending_build_release_claim_non_promotion_guard.jsonl"
OUT = ROOT / "datasets/governance/p724_p0_pending_build_model_claim_non_assertion_guard.jsonl"
REPORT = ROOT / "reports/p724_p0_pending_build_model_claim_non_assertion_guard_report.json"
MD = ROOT / "reports/p724_p0_pending_build_model_claim_non_assertion_guard.md"


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [row for row in load_jsonl(SOURCE) if row.get("lane") != "summary"]
    rows = []
    for order, source in enumerate(source_rows, 1):
        rows.append({
            "non_assertion_guard_id": f"p724::{source.get('non_promotion_guard_id')}",
            "non_assertion_guard_order": order,
            "created_at": created,
            "lane": source.get("lane"),
            "source_p723_id": source.get("non_promotion_guard_id"),
            "guard_status": "blocked_model_claim_non_assertion",
            "quality_evidence_validated": False,
            "benchmark_evidence_validated": False,
            "formal_decision_approved": False,
            "model_claim_asserted": False,
            "model_claim_promoted": False,
            "customer_delivery_ready": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "blocker_reason": "Validated quality/benchmark evidence and approved formal decision are absent.",
            "operator_action": "Use uncertainty language only; do not assert or promote model claims.",
            "policy": "P724 is a non-assertion guard only; it does not evaluate quality or authorize claims.",
        })
    summary = {
        "non_assertion_guard_id": "p724::summary", "non_assertion_guard_order": len(rows) + 1,
        "created_at": created, "lane": "summary", "non_assertion_guard_rows": len(rows),
        "quality_evidence_validated_rows": 0, "benchmark_evidence_validated_rows": 0,
        "formal_decision_approved_rows": 0, "model_claim_asserted_rows": 0,
        "model_claim_promoted_rows": 0, "customer_delivery_ready_rows": 0,
        "release_ready_rows": 0, "production_execution_allowed_rows": 0,
        "policy": "P724 confirms model claims remain non-asserted and blocked.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P724", "created_at": created, "local_only": True,
        "non_assertion_guard_rows": len(rows), "quality_evidence_validated_rows": 0,
        "benchmark_evidence_validated_rows": 0, "formal_decision_approved_rows": 0,
        "model_claim_asserted_rows": 0, "model_claim_promoted_rows": 0,
        "customer_delivery_ready_rows": 0, "release_ready_rows": 0,
        "production_execution_allowed_rows": 0, "artifact_jsonl": str(OUT.relative_to(ROOT)),
        "artifact_md": str(MD.relative_to(ROOT)), "policy": "P724 is planning-only and fail-closed.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P724 model-claim non-assertion guard\n\nRows: `{len(rows)}`. Claims asserted: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P724", "non_assertion_guard_rows": len(rows), "model_claim_asserted_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
