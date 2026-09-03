#!/usr/bin/env python3
"""Validate active P26-P31 execution matrix stays fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "active_stage_execution_matrix_report.json"
JSONL = AI_ROOT / "datasets" / "governance" / "active_stage_execution_matrix.jsonl"
OUT = AI_ROOT / "reports" / "active_stage_execution_matrix_validation_report.json"
EXPECTED_STAGES = ["P26", "P27", "P28", "P29", "P30", "P31"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    report = load_json(REPORT)
    rows = report.get("rows") or []
    jsonl_rows = load_jsonl(JSONL)
    failures: list[dict[str, Any]] = []

    ids = [row.get("stage_id") for row in rows]
    jsonl_ids = [row.get("stage_id") for row in jsonl_rows]
    fail_if(ids != EXPECTED_STAGES, failures, "report_stage_order", ids, EXPECTED_STAGES)
    fail_if(jsonl_ids != EXPECTED_STAGES, failures, "jsonl_stage_order", jsonl_ids, EXPECTED_STAGES)
    fail_if(report.get("stage_count") != len(EXPECTED_STAGES), failures, "stage_count", report.get("stage_count"), len(EXPECTED_STAGES))

    for field in ("training_import_allowed", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    for row in rows:
        stage_id = row.get("stage_id")
        for field in ("training_import_allowed", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(row.get(field) is not False, failures, f"{stage_id}_{field}_false", row.get(field), False)
        fail_if(not row.get("nonhuman_next_actions"), failures, f"{stage_id}_nonhuman_next_actions_present", row.get("nonhuman_next_actions"), "non-empty list")
        fail_if(not row.get("blockers"), failures, f"{stage_id}_blockers_present", row.get("blockers"), "non-empty list")
        if stage_id in {"P28", "P31"}:
            fail_if(not row.get("human_or_external_next_actions"), failures, f"{stage_id}_human_actions_present", row.get("human_or_external_next_actions"), "non-empty list")
        if stage_id == "P31":
            fail_if(row.get("status") != "review_preparation_only", failures, "P31_review_preparation_only", row.get("status"), "review_preparation_only")
            blockers = " ".join(str(item).lower() for item in row.get("blockers") or [])
            fail_if("production execution is forbidden" not in blockers, failures, "P31_production_forbidden_blocker", row.get("blockers"), "production execution is forbidden")

    report_out = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "stage_count": len(rows),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validator rejects positive training/model/release/production flags and requires explicit blockers for every active stage.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report_out["success"],
        "stage_count": report_out["stage_count"],
        "failures": len(failures),
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
