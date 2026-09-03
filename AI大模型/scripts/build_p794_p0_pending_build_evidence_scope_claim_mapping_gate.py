#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p793_p0_pending_build_evidence_source_integrity_lineage_gate.jsonl"
OUT = ROOT / "datasets/governance/p794_p0_pending_build_evidence_scope_claim_mapping_gate.jsonl"
REPORT = ROOT / "reports/p794_p0_pending_build_evidence_scope_claim_mapping_gate_report.json"
MD = ROOT / "reports/p794_p0_pending_build_evidence_scope_claim_mapping_gate.md"
FIELDS = ("scope_identified", "claim_target_identified", "scope_authorized", "claim_evidence_mapped", "risk_boundary_validated", "customer_scope_validated", "formal_decision_ready", "release_ready", "production_execution_allowed")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"scope_gate_id": f"p794::{source.get('lineage_gate_id')}", "scope_gate_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p793_id": source.get("lineage_gate_id"), "gate_status": "empty_no_authorized_scope_claim_mapping", "blocker_reason": "No authorized scope, claim target, evidence mapping, customer boundary, or risk boundary exists for a formal decision.", "operator_action": "Do not broaden, narrow, or infer claims, scope, customer applicability, or risk acceptance.", "policy": "P794 is a read-only evidence scope/claim mapping gate; it performs no claim approval or release."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"scope_gate_id": "p794::summary", "scope_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "scope_gate_rows": len(rows), **zero, "policy": "P794 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P794", "created_at": created, "local_only": True, "scope_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P794 is monitoring-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P794 evidence scope/claim mapping gate\n\nRows: `{len(rows)}`. Mapped claims: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P794", "scope_gate_rows": len(rows), "claim_evidence_mapped_rows": 0, "formal_decision_ready_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
