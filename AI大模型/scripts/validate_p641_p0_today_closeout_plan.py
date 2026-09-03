#!/usr/bin/env python3
"""Validate the P641 P0 closeout plan remains complete and fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
AUDIT = AI_ROOT / "datasets" / "governance" / "p641_p0_today_closeout_plan.jsonl"
REPORT = AI_ROOT / "reports" / "p641_p0_today_closeout_plan_report.json"
OUT = AI_ROOT / "reports" / "p641_p0_today_closeout_plan_validation_report.json"

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    report = load_json(REPORT)
    rows = load_jsonl(AUDIT)
    failures: list[dict[str, Any]] = []

    def check(condition: bool, name: str, observed: Any, expected: Any) -> None:
        if condition:
            failures.append({"check": name, "observed": observed, "expected": expected})

    check(report.get("plan_id") != "P641", "plan_id", report.get("plan_id"), "P641")
    check(report.get("p0_local_closeout_package_ready") is not True, "local_package_ready", report.get("p0_local_closeout_package_ready"), True)
    check(report.get("p0_unblocked") is not False, "p0_unblocked_false", report.get("p0_unblocked"), False)
    check(report.get("p0_completion_ready") is not False, "p0_completion_ready_false", report.get("p0_completion_ready"), False)
    check(len(rows) != 11, "plan_rows_exact", len(rows), 11)
    check(report.get("plan_rows") != len(rows), "report_plan_rows_bound", report.get("plan_rows"), len(rows))
    check(report.get("blocked_rows") != len(rows), "blocked_rows_all", report.get("blocked_rows"), len(rows))
    check(report.get("requires_human_or_external_input_rows") != len(rows), "real_input_rows_all", report.get("requires_human_or_external_input_rows"), len(rows))

    ids = [row.get("plan_item_id") for row in rows]
    check(len(set(ids)) != len(rows), "plan_ids_unique", ids, "unique")
    check(set(ids) != {f"P0-{index:02d}" for index in range(1, 12)}, "plan_ids_complete", ids, "P0-01..P0-11")
    for index, row in enumerate(rows):
        check(row.get("status") != "blocked_awaiting_real_input", f"row_status_{index}", row.get("status"), "blocked_awaiting_real_input")
        check(row.get("requires_human_or_external_input") is not True, f"row_real_input_{index}", row.get("requires_human_or_external_input"), True)
        for field in FALSE_FIELDS:
            check(row.get(field) is not False, f"row_{field}_{index}", row.get(field), False)

    for field in FALSE_FIELDS:
        check(report.get(field) is not False, f"report_{field}", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "plan_id": "P641",
        "plan_rows": len(rows),
        "blocked_rows": sum(1 for row in rows if row.get("status") == "blocked_awaiting_real_input"),
        "requires_human_or_external_input_rows": sum(
            1 for row in rows if row.get("requires_human_or_external_input") is True
        ),
        "p0_local_closeout_package_ready": not failures,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": "Validation proves the local P0 closeout package is complete; it does not unlock P0.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "plan_id": "P641",
        "plan_rows": len(rows),
        "blocked_rows": result["blocked_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
