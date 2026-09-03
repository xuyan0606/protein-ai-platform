#!/usr/bin/env python3
"""Validate P26-P31 all-started board remains fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "pending_stage_all_started_board.json"
JSONL = AI_ROOT / "datasets" / "governance" / "pending_stage_all_started_actions.jsonl"
OUT = AI_ROOT / "reports" / "pending_stage_all_started_board_validation_report.json"
EXPECTED = ["P26", "P27", "P28", "P29", "P30", "P31"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    board = load_json(BOARD)
    jsonl_rows = load_jsonl(JSONL)
    rows = board.get("rows") or []
    failures: list[dict[str, Any]] = []

    ids = [row.get("stage_id") for row in rows]
    jsonl_ids = [row.get("stage_id") for row in jsonl_rows]
    fail_if(ids != EXPECTED, failures, "board_stage_ids", ids, EXPECTED)
    fail_if(jsonl_ids != EXPECTED, failures, "jsonl_stage_ids", jsonl_ids, EXPECTED)
    fail_if(board.get("stage_count") != len(EXPECTED), failures, "stage_count", board.get("stage_count"), len(EXPECTED))
    fail_if(board.get("started_stage_count") != len(EXPECTED), failures, "started_stage_count", board.get("started_stage_count"), len(EXPECTED))
    fail_if(board.get("success") is not True, failures, "board_success_true", board.get("success"), True)

    for row in rows:
        stage_id = row.get("stage_id")
        fail_if(row.get("task_plan_status") != "in_progress", failures, f"{stage_id}_status_in_progress", row.get("task_plan_status"), "in_progress")
        fail_if(row.get("started") is not True, failures, f"{stage_id}_started_true", row.get("started"), True)
        for field in ("training_import_allowed", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(field) is not False, failures, f"{stage_id}_{field}_false", row.get(field), False)
        forbidden = row.get("forbidden_now") or []
        fail_if(not forbidden, failures, f"{stage_id}_forbidden_now_present", forbidden, "non-empty list")
        if stage_id == "P31":
            mode = row.get("start_mode")
            fail_if(mode != "review_preparation_started_no_production_execution", failures, "P31_no_production_execution", mode, "review_preparation_started_no_production_execution")
            forbidden_text = " ".join(str(item) for item in forbidden).lower()
            fail_if("sync to production" not in forbidden_text, failures, "P31_forbids_sync", forbidden, "sync to production forbidden")

    for field in ("training_import_allowed", "safe_for_model_claim", "release_ready"):
        fail_if(board.get(field) is not False, failures, f"board_{field}_false", board.get(field), False)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "stage_count": len(rows),
        "started_stage_count": sum(1 for row in rows if row.get("started") is True),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validator confirms P26-P31 workstreams are started locally while training, model claim, and production release gates remain closed.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "stage_count": report["stage_count"],
        "started_stage_count": report["started_stage_count"],
        "failures": len(failures),
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
