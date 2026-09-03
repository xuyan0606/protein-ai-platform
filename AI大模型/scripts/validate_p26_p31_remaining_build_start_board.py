#!/usr/bin/env python3
"""Validate the P26-P31 remaining-build start board stays fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "p26_p31_remaining_build_start_board.json"
JSONL = AI_ROOT / "datasets" / "governance" / "p26_p31_remaining_build_start_actions.jsonl"
PLATE_BACKLOG = AI_ROOT / "reports" / "experiment_feedback_plate_intake_backlog_report.json"
HUMAN_BACKLOG = AI_ROOT / "reports" / "human_decision_backlog_fail_closed_consistency_validation_report.json"
FEATURE_COVERAGE = AI_ROOT / "reports" / "feature_coverage_by_head_group_report.json"
FEATURE_COVERAGE_VALIDATION = AI_ROOT / "reports" / "feature_coverage_by_head_group_validation_report.json"
OUT = AI_ROOT / "reports" / "p26_p31_remaining_build_start_board_validation_report.json"

EXPECTED_ACTION_IDS = [
    "P26-A001",
    "P26-A002",
    "P26-A003",
    "P26-A004",
    "P27-A001",
    "P27-A002",
    "P27-A003",
    "P28-A001",
    "P28-A002",
    "P28-A003",
    "P29-A001",
    "P29-A002",
    "P29-A003",
    "P29-A004",
    "P30-A001",
    "P30-A002",
    "P30-A003",
    "P31-A001",
    "P31-A002",
    "P31-A003",
]
EXPECTED_STAGE_IDS = ["P26", "P27", "P28", "P29", "P30", "P31"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    report = load_json(REPORT)
    rows = report.get("actions") if isinstance(report.get("actions"), list) else []
    jsonl_rows = load_jsonl(JSONL)
    plate_backlog = load_json(PLATE_BACKLOG)
    human_backlog = load_json(HUMAN_BACKLOG)
    feature_coverage = load_json(FEATURE_COVERAGE)
    feature_coverage_validation = load_json(FEATURE_COVERAGE_VALIDATION)
    failures: list[dict[str, Any]] = []

    action_ids = [row.get("action_id") for row in rows]
    jsonl_action_ids = [row.get("action_id") for row in jsonl_rows]
    if action_ids != EXPECTED_ACTION_IDS:
        failures.append({"check": "action_ids_exact", "observed": action_ids, "expected": EXPECTED_ACTION_IDS})
    if jsonl_action_ids != EXPECTED_ACTION_IDS:
        failures.append({"check": "jsonl_action_ids_exact", "observed": jsonl_action_ids, "expected": EXPECTED_ACTION_IDS})
    if report.get("stage_ids") != EXPECTED_STAGE_IDS:
        failures.append({"check": "stage_ids_exact", "observed": report.get("stage_ids"), "expected": EXPECTED_STAGE_IDS})
    if report.get("action_count") != len(EXPECTED_ACTION_IDS):
        failures.append({"check": "action_count", "observed": report.get("action_count"), "expected": len(EXPECTED_ACTION_IDS)})
    if report.get("started_action_count") != len(EXPECTED_ACTION_IDS):
        failures.append({"check": "started_action_count", "observed": report.get("started_action_count"), "expected": len(EXPECTED_ACTION_IDS)})

    for field in ("training_import_allowed", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        if report.get(field) is not False:
            failures.append({"check": f"report_{field}_false", "observed": report.get(field), "expected": False})

    plate_rows = plate_backlog.get("backlog_rows")
    human_missing = human_backlog.get("total_missing_rows")
    for row in rows:
        action_id = row.get("action_id")
        if row.get("started") is not True:
            failures.append({"check": "action_started_true", "action_id": action_id, "observed": row.get("started"), "expected": True})
        if not row.get("status") or not row.get("blocker") or not row.get("next_action"):
            failures.append({"check": "action_has_status_blocker_next_action", "action_id": action_id})
        for field in ("training_import_allowed", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            if row.get(field) is not False:
                failures.append({"check": f"action_{field}_false", "action_id": action_id, "observed": row.get(field), "expected": False})
        source_state = row.get("source_state") if isinstance(row.get("source_state"), dict) else {}
        if action_id in {"P26-A003", "P28-A002"} and source_state.get("plate_backlog_rows") != plate_rows:
            failures.append({"check": "plate_backlog_source_bound", "action_id": action_id, "observed": source_state.get("plate_backlog_rows"), "expected": plate_rows})
        if action_id in {"P26-A001", "P26-A004", "P28-A001", "P28-A003", "P30-A002"} and source_state.get("human_backlog_total_missing_rows") != human_missing:
            failures.append({"check": "human_backlog_source_bound", "action_id": action_id, "observed": source_state.get("human_backlog_total_missing_rows"), "expected": human_missing})
        if action_id == "P27-A003":
            if source_state.get("coverage_rows") != feature_coverage.get("coverage_row_count"):
                failures.append({"check": "feature_coverage_rows_source_bound", "action_id": action_id, "observed": source_state.get("coverage_rows"), "expected": feature_coverage.get("coverage_row_count")})
            if source_state.get("protein_group_count") != feature_coverage.get("protein_group_count"):
                failures.append({"check": "feature_coverage_protein_group_count_source_bound", "action_id": action_id, "observed": source_state.get("protein_group_count"), "expected": feature_coverage.get("protein_group_count")})
            if source_state.get("validation_success") is not (feature_coverage_validation.get("success") is True):
                failures.append({"check": "feature_coverage_validation_success_source_bound", "action_id": action_id, "observed": source_state.get("validation_success"), "expected": feature_coverage_validation.get("success") is True})
        if str(row.get("stage_id")) == "P31" and row.get("production_execution_allowed") is not False:
            failures.append({"check": "P31_production_execution_forbidden", "action_id": action_id})

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "action_count": len(rows),
        "started_action_count": sum(1 for row in rows if row.get("started") is True),
        "expected_action_count": len(EXPECTED_ACTION_IDS),
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. P26-P31 remaining work items are started locally and remain fail-closed.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "action_count": validation["action_count"],
        "started_action_count": validation["started_action_count"],
        "failures": len(failures),
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
