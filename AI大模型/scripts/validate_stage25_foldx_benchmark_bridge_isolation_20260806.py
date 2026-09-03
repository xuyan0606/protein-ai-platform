#!/usr/bin/env python3
"""Validate that FoldX candidate drafts are isolated from benchmark/formal-decision intake."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FOLDX_DRAFT_REPORT = AI_ROOT / "reports" / "stage25_foldx_runtime_receipt_candidate_draft_validation_20260806.json"
BENCHMARK_REPORT = AI_ROOT / "reports" / "benchmark_readiness_packet_validation_report.json"
BRIDGE_REPORT = AI_ROOT / "reports" / "hard_gate_decision_benchmark_bridge_report.json"
OUTPUT = AI_ROOT / "reports" / "stage25_foldx_benchmark_bridge_isolation_validation_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    for path, name in (
        (FOLDX_DRAFT_REPORT, "foldx_draft_report"),
        (BENCHMARK_REPORT, "benchmark_report"),
        (BRIDGE_REPORT, "bridge_report"),
    ):
        fail_if(not path.exists(), failures, f"{name}_exists", "missing", str(path))

    foldx = load_json(FOLDX_DRAFT_REPORT) if FOLDX_DRAFT_REPORT.exists() else {}
    benchmark = load_json(BENCHMARK_REPORT) if BENCHMARK_REPORT.exists() else {}
    bridge = load_json(BRIDGE_REPORT) if BRIDGE_REPORT.exists() else {}

    fail_if(foldx.get("drafts_valid") is not True, failures, "foldx_drafts_valid", foldx.get("drafts_valid"), True)
    fail_if(foldx.get("receipt_decision") != "needs_more_info", failures, "foldx_receipt_decision", foldx.get("receipt_decision"), "needs_more_info")
    fail_if(foldx.get("formal_runtime_receipt_written") is not False, failures, "foldx_formal_runtime_receipt_written_false", foldx.get("formal_runtime_receipt_written"), False)
    fail_if(foldx.get("approved_for_physical_ddg_runtime") is not False, failures, "foldx_approved_for_physical_ddg_runtime_false", foldx.get("approved_for_physical_ddg_runtime"), False)

    fail_if(benchmark.get("status") != "blocked", failures, "benchmark_status_blocked", benchmark.get("status"), "blocked")
    fail_if(benchmark.get("completion_ready_rows") != 0, failures, "benchmark_completion_ready_rows_zero", benchmark.get("completion_ready_rows"), 0)
    fail_if(benchmark.get("score_values_recorded") != 0, failures, "benchmark_score_values_recorded_zero", benchmark.get("score_values_recorded"), 0)
    for flag in ("ready_for_model_claim", "safe_for_model_claim", "release_ready", "training_labels_modified", "release_flags_modified"):
        fail_if(benchmark.get(flag) is not False, failures, f"benchmark.{flag}_false", benchmark.get(flag), False)

    fail_if(bridge.get("intake_rows_written") != 0, failures, "bridge_intake_rows_written_zero", bridge.get("intake_rows_written"), 0)
    fail_if(bridge.get("training_import_written_rows") != 0, failures, "bridge_training_import_written_rows_zero", bridge.get("training_import_written_rows"), 0)
    fail_if(bridge.get("strict_formal_approved_rows") != 0, failures, "bridge_strict_formal_approved_rows_zero", bridge.get("strict_formal_approved_rows"), 0)
    fail_if(bridge.get("substrate_formal_approved_rows") != 0, failures, "bridge_substrate_formal_approved_rows_zero", bridge.get("substrate_formal_approved_rows"), 0)
    for flag in ("release_ready", "safe_for_model_claim"):
        fail_if(bridge.get(flag) is not False, failures, f"bridge.{flag}_false", bridge.get(flag), False)
    for lane in ("strict", "substrate"):
        lane_row = bridge.get(lane) or {}
        fail_if(lane_row.get("status") != "blocked_no_approved_decisions", failures, f"bridge.{lane}.status", lane_row.get("status"), "blocked_no_approved_decisions")
        fail_if(lane_row.get("intake_written") is not False, failures, f"bridge.{lane}.intake_written_false", lane_row.get("intake_written"), False)
        fail_if(lane_row.get("dataset_rows") != 0, failures, f"bridge.{lane}.dataset_rows_zero", lane_row.get("dataset_rows"), 0)

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_foldx_benchmark_bridge_isolation_validation",
        "stage": 25,
        "isolation_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "foldx_receipt_decision": foldx.get("receipt_decision"),
        "foldx_formal_runtime_receipt_written": False,
        "benchmark_completion_ready_rows": benchmark.get("completion_ready_rows"),
        "benchmark_score_values_recorded": benchmark.get("score_values_recorded"),
        "bridge_intake_rows_written": bridge.get("intake_rows_written"),
        "formal_decision_rows_written": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "isolation_valid": report["isolation_valid"], "failure_count": report["failure_count"], "bridge_intake_rows_written": report["bridge_intake_rows_written"], "benchmark_completion_ready_rows": report["benchmark_completion_ready_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["isolation_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
