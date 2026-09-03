#!/usr/bin/env python3
"""Build P756 audit-receipt integrity/immutability gates from P755."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from build_p700_p0_real_input_pending_build_checklist import load_jsonl
ROOT = Path(__file__).resolve().parents[1]; SOURCE = ROOT / "datasets/governance/p755_p0_pending_build_production_audit_receipt_preflight_gate.jsonl"; OUT = ROOT / "datasets/governance/p756_p0_pending_build_audit_receipt_integrity_immutability_gate.jsonl"; REPORT = ROOT / "reports/p756_p0_pending_build_audit_receipt_integrity_immutability_gate_report.json"; MD = ROOT / "reports/p756_p0_pending_build_audit_receipt_integrity_immutability_gate.md"
FIELDS = ("audit_receipt_present", "receipt_hash_verified", "receipt_signature_verified", "receipt_timestamp_verified", "receipt_provenance_validated", "receipt_immutability_validated", "execution_success_attested", "release_complete_attested", "production_state_validated")
def main() -> int:
    created = datetime.now(timezone.utc).isoformat(); source = [r for r in load_jsonl(SOURCE) if r.get("boundary") != "summary"]; rows = []
    for order, src in enumerate(source, 1):
        row = {"integrity_gate_id": f"p756::{src.get('audit_preflight_id')}", "integrity_gate_order": order, "created_at": created, "boundary": src.get("boundary"), "source_p755_id": src.get("audit_preflight_id"), "gate_status": "empty_no_receipt_to_validate_or_retain", "blocker_reason": "No authentic audit receipt exists; integrity, provenance, immutability, and execution attestations cannot be established.", "operator_action": "Do not generate or infer hashes, signatures, timestamps, provenance, retention proof, or production attestations.", "policy": "P756 is an integrity/immutability gate only; it creates no receipt or execution attestation."}
        row.update({field: False for field in FIELDS}); rows.append(row)
    zero = {f"{field}_rows": 0 for field in FIELDS}; summary = {"integrity_gate_id": "p756::summary", "integrity_gate_order": len(rows) + 1, "created_at": created, "boundary": "summary", "integrity_gate_rows": len(rows), **zero, "policy": "P756 remains empty and fail-closed."}
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows + [summary]), encoding="utf-8"); report = {"manifest_id": "P756", "created_at": created, "local_only": True, "integrity_gate_rows": len(rows), **zero, "artifact_jsonl": str(OUT.relative_to(ROOT)), "artifact_md": str(MD.relative_to(ROOT)), "policy": "P756 is planning-only and fail-closed."}; REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); MD.write_text(f"# P756 audit-receipt integrity/immutability gate\n\nRows: `{len(rows)}`. Validated immutable receipts: `0`.\n", encoding="utf-8"); print(json.dumps({"manifest_id": "P756", "integrity_gate_rows": len(rows), "receipt_immutability_validated_rows": 0, "output": str(REPORT)}, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
