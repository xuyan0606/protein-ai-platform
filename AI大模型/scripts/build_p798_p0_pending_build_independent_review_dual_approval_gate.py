#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p797_p0_pending_build_control_exception_remediation_closure_gate.jsonl"
OUT = ROOT / "datasets/governance/p798_p0_pending_build_independent_review_dual_approval_gate.jsonl"
REPORT = ROOT / "reports/p798_p0_pending_build_independent_review_dual_approval_gate_report.json"
MD = ROOT / "reports/p798_p0_pending_build_independent_review_dual_approval_gate.md"
FIELDS = ("review_scope_defined", "independent_reviewer_verified", "review_evidence_present", "conflict_check_passed", "first_approval_present", "second_approval_present", "dual_approval_validated", "formal_decision_ready", "release_ready", "production_execution_allowed")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"review_gate_id": f"p798::{source.get('exception_gate_id')}", "review_gate_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p797_id": source.get("exception_gate_id"), "gate_status": "empty_no_independent_review_or_dual_approval", "blocker_reason": "No independent reviewer, conflict check, review evidence, or dual approval exists to support a governance transition.", "operator_action": "Do not self-approve, infer independent review, or bypass the second-approver requirement.", "policy": "P798 is a read-only independent review/dual approval gate; it performs no approval or release."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"review_gate_id": "p798::summary", "review_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "review_gate_rows": len(rows), **zero, "policy": "P798 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P798", "created_at": created, "local_only": True, "review_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P798 is monitoring-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P798 independent review/dual approval gate\n\nRows: `{len(rows)}`. Dual approvals: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P798", "review_gate_rows": len(rows), "dual_approval_validated_rows": 0, "formal_decision_ready_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
