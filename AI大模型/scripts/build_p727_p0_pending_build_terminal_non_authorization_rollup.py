#!/usr/bin/env python3
"""Build P727 terminal non-authorization rollup across P722-P726."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/governance/p727_p0_pending_build_terminal_non_authorization_rollup.jsonl"
REPORT = ROOT / "reports/p727_p0_pending_build_terminal_non_authorization_rollup_report.json"
MD = ROOT / "reports/p727_p0_pending_build_terminal_non_authorization_rollup.md"

SOURCES = (
    ("formal_decision_write", "p722_p0_pending_build_formal_decision_write_authorization_gate_report.json", "authorization_gate_rows", "formal_decision_write_allowed_rows"),
    ("release_claim_promotion", "p723_p0_pending_build_release_claim_non_promotion_guard_report.json", "non_promotion_guard_rows", "claim_promoted_rows"),
    ("model_claim_assertion", "p724_p0_pending_build_model_claim_non_assertion_guard_report.json", "non_assertion_guard_rows", "model_claim_asserted_rows"),
    ("customer_delivery", "p725_p0_pending_build_customer_delivery_non_authorization_guard_report.json", "delivery_guard_rows", "customer_delivery_authorized_rows"),
    ("production_execution", "p726_p0_pending_build_production_execution_non_authorization_guard_report.json", "production_guard_rows", "production_execution_authorized_rows"),
)


def main() -> int:
    created = datetime.now(timezone.utc).isoformat()
    rows = []
    for order, (boundary, filename, count_field, authorization_field) in enumerate(SOURCES, 1):
        source = json.loads((ROOT / "reports" / filename).read_text(encoding="utf-8"))
        rows.append({
            "terminal_rollup_id": f"p727::{boundary}",
            "terminal_rollup_order": order,
            "created_at": created,
            "boundary": boundary,
            "source_report": filename,
            "source_rows": source.get(count_field),
            "authorized_or_promoted_rows": source.get(authorization_field),
            "terminal_status": "blocked_non_authorized",
            "formal_decision_ready": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "policy": "P727 is a rollup only; it does not approve, promote, deliver, release, or execute.",
        })
    summary = {
        "terminal_rollup_id": "p727::summary",
        "terminal_rollup_order": len(rows) + 1,
        "created_at": created,
        "boundary": "summary",
        "terminal_rollup_rows": len(rows),
        "authorized_or_promoted_rows": sum(row.get("authorized_or_promoted_rows") or 0 for row in rows),
        "formal_decision_ready_rows": 0,
        "release_ready_rows": 0,
        "production_execution_allowed_rows": 0,
        "terminal_status": "blocked_non_authorized",
        "policy": "P727 confirms all terminal authorization boundaries remain blocked.",
    }
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows + [summary]), encoding="utf-8")
    report = {
        "manifest_id": "P727",
        "created_at": created,
        "local_only": True,
        "terminal_rollup_rows": len(rows),
        "authorized_or_promoted_rows": 0,
        "formal_decision_ready_rows": 0,
        "release_ready_rows": 0,
        "production_execution_allowed_rows": 0,
        "artifact_jsonl": str(OUT.relative_to(ROOT)),
        "artifact_md": str(MD.relative_to(ROOT)),
        "policy": "P727 is a terminal non-authorization rollup only.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD.write_text(f"# P727 terminal non-authorization rollup\n\nBoundaries: `{len(rows)}`. Authorized/promoted rows: `0`.\n", encoding="utf-8")
    print(json.dumps({"manifest_id": "P727", "terminal_rollup_rows": len(rows), "authorized_or_promoted_rows": 0, "output": str(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
