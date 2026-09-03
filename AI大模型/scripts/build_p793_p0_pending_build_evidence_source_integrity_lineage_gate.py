#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets/governance/p792_p0_pending_build_governance_evidence_freshness_time_anchor_gate.jsonl"
OUT = ROOT / "datasets/governance/p793_p0_pending_build_evidence_source_integrity_lineage_gate.jsonl"
REPORT = ROOT / "reports/p793_p0_pending_build_evidence_source_integrity_lineage_gate_report.json"
MD = ROOT / "reports/p793_p0_pending_build_evidence_source_integrity_lineage_gate.md"
FIELDS = ("source_identified", "source_authorized", "content_hash_verified", "signature_verified", "provenance_complete", "integrity_validated", "evidence_fresh", "formal_decision_ready", "reopen_authorized", "production_execution_allowed")

def main():
    created = datetime.now(timezone.utc).isoformat()
    source_rows = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]
    rows = []
    for i, source in enumerate(source_rows, 1):
        row = {"lineage_gate_id": f"p793::{source.get('freshness_gate_id')}", "lineage_gate_order": i, "created_at": created, "boundary": source.get("boundary"), "source_p792_id": source.get("freshness_gate_id"), "gate_status": "empty_no_verified_evidence_source_integrity_lineage", "blocker_reason": "No authorized source, verified hash/signature, or complete provenance exists to support a state transition.", "operator_action": "Do not synthesize, accept, or attest evidence source, integrity, or lineage.", "policy": "P793 is a read-only evidence source/integrity lineage gate; it performs no attestation or authorization."}
        row.update({field: False for field in FIELDS})
        rows.append(row)
    zero = {field + "_rows": 0 for field in FIELDS}
    summary = {"lineage_gate_id": "p793::summary", "lineage_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "lineage_gate_rows": len(rows), **zero, "policy": "P793 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {"manifest_id": "P793", "created_at": created, "local_only": True, "lineage_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P793 is monitoring-only and fail-closed."}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P793 evidence source/integrity lineage gate\n\nRows: `{len(rows)}`. Integrity-validated rows: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P793", "lineage_gate_rows": len(rows), "integrity_validated_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
