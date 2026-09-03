#!/usr/bin/env python3
"""Validate the current P26-P31 pending backlog all-started board."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "p26_p31_pending_backlog_all_started_board.json"
JSONL = AI_ROOT / "datasets" / "governance" / "p26_p31_pending_backlog_all_started_actions.jsonl"
GAP_JSONL = AI_ROOT / "datasets" / "features" / "feature_coverage_gap_queue.jsonl"
GAP_REPORT = AI_ROOT / "reports" / "feature_coverage_gap_queue_report.json"
GAP_VALIDATION = AI_ROOT / "reports" / "feature_coverage_gap_queue_validation_report.json"
PLATE_BACKLOG = AI_ROOT / "reports" / "experiment_feedback_plate_intake_backlog_report.json"
HUMAN_BACKLOG = AI_ROOT / "reports" / "human_decision_backlog_fail_closed_consistency_validation_report.json"
OUT = AI_ROOT / "reports" / "p26_p31_pending_backlog_all_started_board_validation_report.json"

EXPECTED_STAGE_IDS = ["P26", "P27", "P28", "P29", "P30", "P31"]
STATIC_ACTION_IDS = [
    "P26-B001",
    "P26-B002",
    "P26-B003",
    "P26-B004",
    "P28-B001",
    "P28-B002",
    "P28-B003",
    "P29-B001",
    "P29-B002",
    "P29-B003",
    "P29-B004",
    "P30-B001",
    "P30-B002",
    "P30-B003",
    "P31-B001",
    "P31-B002",
    "P31-B003",
]


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
    gap_rows = load_jsonl(GAP_JSONL)
    gap_report = load_json(GAP_REPORT)
    gap_validation = load_json(GAP_VALIDATION)
    plate_backlog = load_json(PLATE_BACKLOG)
    human_backlog = load_json(HUMAN_BACKLOG)
    failures: list[dict[str, Any]] = []

    p27_gap_ids = [f"P27-GAP-{idx:03d}" for idx in range(1, len(gap_rows) + 1)]
    expected_action_ids = STATIC_ACTION_IDS[:4] + p27_gap_ids + STATIC_ACTION_IDS[4:]
    action_ids = [row.get("action_id") for row in rows]
    jsonl_action_ids = [row.get("action_id") for row in jsonl_rows]

    if report.get("stage_ids") != EXPECTED_STAGE_IDS:
        failures.append({"check": "stage_ids_exact", "observed": report.get("stage_ids"), "expected": EXPECTED_STAGE_IDS})
    if action_ids != expected_action_ids:
        failures.append({"check": "action_ids_exact", "observed": action_ids, "expected": expected_action_ids})
    if jsonl_action_ids != expected_action_ids:
        failures.append({"check": "jsonl_action_ids_exact", "observed": jsonl_action_ids, "expected": expected_action_ids})
    if report.get("static_pending_action_count") != len(STATIC_ACTION_IDS):
        failures.append({"check": "static_pending_action_count", "observed": report.get("static_pending_action_count"), "expected": len(STATIC_ACTION_IDS)})
    if report.get("p27_gap_action_count") != len(gap_rows):
        failures.append({"check": "p27_gap_action_count", "observed": report.get("p27_gap_action_count"), "expected": len(gap_rows)})
    if report.get("source_gap_count") != gap_report.get("gap_count"):
        failures.append({"check": "source_gap_count_bound", "observed": report.get("source_gap_count"), "expected": gap_report.get("gap_count")})
    if report.get("source_gap_validation_success") is not (gap_validation.get("success") is True):
        failures.append({"check": "source_gap_validation_success_bound", "observed": report.get("source_gap_validation_success"), "expected": gap_validation.get("success") is True})
    if report.get("action_count") != len(expected_action_ids):
        failures.append({"check": "action_count", "observed": report.get("action_count"), "expected": len(expected_action_ids)})
    if report.get("started_action_count") != len(expected_action_ids):
        failures.append({"check": "started_action_count", "observed": report.get("started_action_count"), "expected": len(expected_action_ids)})

    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        if report.get(field) is not False:
            failures.append({"check": f"report_{field}_false", "observed": report.get(field), "expected": False})

    plate_rows = plate_backlog.get("backlog_rows")
    human_missing = human_backlog.get("total_missing_rows")
    gaps_by_action_id = {
        f"P27-GAP-{idx:03d}": gap for idx, gap in enumerate(gap_rows, start=1)
    }
    for row in rows:
        action_id = row.get("action_id")
        source_state = row.get("source_state") if isinstance(row.get("source_state"), dict) else {}
        if row.get("started") is not True:
            failures.append({"check": "action_started_true", "action_id": action_id, "observed": row.get("started"), "expected": True})
        if not row.get("status") or not row.get("blocker") or not row.get("next_action"):
            failures.append({"check": "action_has_status_blocker_next_action", "action_id": action_id})
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            if row.get(field) is not False:
                failures.append({"check": f"action_{field}_false", "action_id": action_id, "observed": row.get(field), "expected": False})
        if action_id in {"P26-B003", "P28-B002"} and source_state.get("plate_backlog_rows") != plate_rows:
            failures.append({"check": "plate_backlog_source_bound", "action_id": action_id, "observed": source_state.get("plate_backlog_rows"), "expected": plate_rows})
        if action_id in {"P26-B001", "P26-B004", "P28-B001", "P28-B003", "P30-B002"} and source_state.get("human_backlog_total_missing_rows") != human_missing:
            failures.append({"check": "human_backlog_source_bound", "action_id": action_id, "observed": source_state.get("human_backlog_total_missing_rows"), "expected": human_missing})
        if action_id in gaps_by_action_id:
            gap = gaps_by_action_id[str(action_id)]
            for field in ("gap_id", "head", "protein_group_id", "missing_input_feature_families"):
                if source_state.get(field) != gap.get(field):
                    failures.append({"check": f"p27_gap_{field}_source_bound", "action_id": action_id, "observed": source_state.get(field), "expected": gap.get(field)})
            if source_state.get("gap_validation_success") is not (gap_validation.get("success") is True):
                failures.append({"check": "p27_gap_validation_success_source_bound", "action_id": action_id, "observed": source_state.get("gap_validation_success"), "expected": gap_validation.get("success") is True})
        if str(row.get("stage_id")) == "P31" and row.get("production_execution_allowed") is not False:
            failures.append({"check": "P31_production_execution_forbidden", "action_id": action_id})

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "action_count": len(rows),
        "started_action_count": sum(1 for row in rows if row.get("started") is True),
        "expected_action_count": len(expected_action_ids),
        "p27_gap_action_count": len(p27_gap_ids),
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Pending backlog actions are started locally and remain fail-closed.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "action_count": validation["action_count"],
        "started_action_count": validation["started_action_count"],
        "p27_gap_action_count": validation["p27_gap_action_count"],
        "failures": len(failures),
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
