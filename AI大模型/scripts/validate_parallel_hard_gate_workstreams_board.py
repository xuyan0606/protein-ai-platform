#!/usr/bin/env python3
"""Validate the four-lane parallel hard-gate board fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "parallel_hard_gate_workstreams_board_report.json"
JSONL = AI_ROOT / "datasets" / "governance" / "parallel_hard_gate_workstreams_board.jsonl"
OUT = AI_ROOT / "reports" / "parallel_hard_gate_workstreams_board_validation_report.json"
EXPECTED = ["benchmark_readiness", "ddg_runtime_probe_receipt", "five_head_minimum_samples", "human_preflight_packages"]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def rel_exists(rel_path: Any) -> bool:
    return isinstance(rel_path, str) and (AI_ROOT / rel_path).exists()


def main() -> int:
    report = load_json(REPORT)
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    jsonl_rows = load_jsonl(JSONL)
    failures: list[dict[str, Any]] = []
    ids = [item.get("lane_id") for item in rows]
    jsonl_ids = [item.get("lane_id") for item in jsonl_rows]
    fail_if(ids != EXPECTED, failures, "report_lane_order", ids, EXPECTED)
    fail_if(jsonl_ids != EXPECTED, failures, "jsonl_lane_order", jsonl_ids, EXPECTED)
    fail_if(report.get("lane_count") != 4, failures, "lane_count", report.get("lane_count"), 4)
    fail_if(report.get("started_lane_count") != 4, failures, "started_lane_count", report.get("started_lane_count"), 4)
    for key in ("training_import_allowed", "training_execution_allowed", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        fail_if(report.get(key) is not False, failures, f"report_{key}_false", report.get(key), False)
    for item in rows:
        lane = item.get("lane_id")
        fail_if(item.get("started") is not True, failures, f"{lane}_started", item.get("started"), True)
        fail_if(item.get("status") != "started_blocked", failures, f"{lane}_status", item.get("status"), "started_blocked")
        for key in ("training_import_allowed", "training_execution_allowed", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(item.get(key) is not False, failures, f"{lane}_{key}_false", item.get(key), False)
        fail_if(not item.get("source_reports"), failures, f"{lane}_source_reports_present", item.get("source_reports"), "non-empty list")
        fail_if(not item.get("evidence"), failures, f"{lane}_evidence_present", item.get("evidence"), "non-empty object")
        fail_if(not item.get("nonhuman_actions"), failures, f"{lane}_nonhuman_actions_present", item.get("nonhuman_actions"), "non-empty list")
        fail_if(not item.get("human_or_external_blockers"), failures, f"{lane}_blockers_present", item.get("human_or_external_blockers"), "non-empty list")
        fail_if(not item.get("acceptance_artifacts"), failures, f"{lane}_acceptance_artifacts_present", item.get("acceptance_artifacts"), "non-empty list")
        missing_source_reports = [path for path in item.get("source_reports") or [] if not rel_exists(path)]
        missing_acceptance_artifacts = [path for path in item.get("acceptance_artifacts") or [] if not rel_exists(path)]
        fail_if(bool(missing_source_reports), failures, f"{lane}_source_reports_exist", missing_source_reports, [])
        fail_if(bool(missing_acceptance_artifacts), failures, f"{lane}_acceptance_artifacts_exist", missing_acceptance_artifacts, [])
    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "lane_count": len(rows),
        "failures": failures,
        "training_import_allowed": False,
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Every lane must remain started_blocked with evidence, non-human actions, explicit human/external blockers and acceptance artifacts. Positive execution/claim/release flags are rejected.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "lane_count": len(rows), "failures": len(failures), "output": str(OUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
