#!/usr/bin/env python3
"""Validate P727 terminal non-authorization rollup."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from build_p700_p0_real_input_pending_build_checklist import load_json, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "datasets/governance/p727_p0_pending_build_terminal_non_authorization_rollup.jsonl"
REPORT = ROOT / "reports/p727_p0_pending_build_terminal_non_authorization_rollup_report.json"
OUT = ROOT / "reports/p727_p0_pending_build_terminal_non_authorization_rollup_validation_report.json"


def main() -> int:
    rows = load_jsonl(BOARD)
    boundaries = rows[:-1]
    report = load_json(REPORT)
    failures = []

    def fail(check: str, condition: bool, observed: object) -> None:
        if condition:
            failures.append({"check": check, "observed": observed})

    fail("rows", len(boundaries) != 5, len(boundaries))
    for field in ("authorized_or_promoted_rows", "formal_decision_ready_rows", "release_ready_rows", "production_execution_allowed_rows"):
        fail(field, report.get(field) != 0, report.get(field))
    for index, row in enumerate(boundaries, 1):
        fail(f"row_{index}_status", row.get("terminal_status") != "blocked_non_authorized", row.get("terminal_status"))
        fail(f"row_{index}_authorized", row.get("authorized_or_promoted_rows") != 0, row.get("authorized_or_promoted_rows"))
        for field in ("formal_decision_ready", "release_ready", "production_execution_allowed"):
            fail(f"row_{index}_{field}", row.get(field) is not False, row.get(field))

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest_id": "P727",
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "terminal_rollup_rows": len(boundaries),
        "authorized_or_promoted_rows": 0,
        "formal_decision_ready_rows": 0,
        "release_ready_rows": 0,
        "production_execution_allowed_rows": 0,
        "policy": "Validation only; P727 confirms all terminal boundaries remain non-authorized.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": result["success"], "terminal_rollup_rows": len(boundaries), "authorized_or_promoted_rows": 0, "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
