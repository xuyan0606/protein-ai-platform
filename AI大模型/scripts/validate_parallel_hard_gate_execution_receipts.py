#!/usr/bin/env python3
"""Validate parallel hard-gate execution receipts remain evidence-only."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "governance" / "parallel_hard_gate_execution_receipts.jsonl"
OUT = AI_ROOT / "reports" / "parallel_hard_gate_execution_receipts_validation_report.json"

EXPECTED_LANES = {
    "benchmark_readiness",
    "ddg_runtime_probe_receipt",
    "five_head_minimum_sample_threshold",
    "human_preflight_fireprot_plate_retention",
}
FORBIDDEN_TRUE_FIELDS = {
    "eligibility_changed",
    "formal_decision_written",
    "runtime_receipt_written",
    "training_import_written",
    "model_or_release_flags_changed",
    "safe_for_model_claim",
    "release_ready",
    "physics_ddg_ready",
    "training_execution_allowed",
}
DDG_ALLOWED_TRUE_FIELDS = {
    "eligibility_changed",
    "formal_decision_written",
    "runtime_receipt_written",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate parallel hard-gate execution receipts")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    failures: list[dict[str, Any]] = []
    lanes = [str(row.get("lane") or "") for row in rows]
    lane_counts = Counter(lanes)

    if set(lanes) != EXPECTED_LANES:
        failures.append({"check": "expected_lanes", "observed": sorted(set(lanes)), "expected": sorted(EXPECTED_LANES)})
    for lane, count in lane_counts.items():
        if count != 1:
            failures.append({"check": "duplicate_lane", "lane": lane, "count": count})

    for index, row in enumerate(rows, start=1):
        row_failures: list[str] = []
        if row.get("execution_performed") is not True:
            row_failures.append("execution_not_marked_performed")
        if row.get("validation_passed") is not True:
            row_failures.append("validation_not_passed")
        if row.get("status") != "executed_blocked":
            row_failures.append("status_not_executed_blocked")
        if not row.get("execution_commands"):
            row_failures.append("missing_execution_commands")
        if not row.get("source_reports"):
            row_failures.append("missing_source_reports")
        lane = str(row.get("lane") or "")
        allowed_true_fields = DDG_ALLOWED_TRUE_FIELDS if lane == "ddg_runtime_probe_receipt" else set()
        for field in FORBIDDEN_TRUE_FIELDS:
            if field in allowed_true_fields:
                continue
            if row.get(field) is True:
                row_failures.append(f"forbidden_true_{field}")
        if lane == "benchmark_readiness":
            packet_rows = int(row.get("packet_rows") or 0)
            if packet_rows <= 0:
                row_failures.append("benchmark_packet_rows_missing")
            if int(row.get("completion_ready_rows") or 0) != 0:
                row_failures.append("benchmark_completion_ready_unexpected")
            if int(row.get("score_values_recorded") or 0) != 0:
                row_failures.append("benchmark_scores_recorded_unexpected")
        if lane == "ddg_runtime_probe_receipt":
            if int(row.get("physical_backend_rows") or 0) != 3:
                row_failures.append("ddg_physical_backend_rows_not_3")
            if int(row.get("approved_runtime_receipt_rows") or 0) < 1:
                row_failures.append("ddg_runtime_receipts_missing_after_pyrosetta_breakthrough")
            if row.get("physics_ddg_ready") is not False:
                row_failures.append("ddg_physics_ready_not_fail_closed")
            if row.get("training_import_written") is not False:
                row_failures.append("ddg_training_import_written_unexpected")
            if row.get("model_or_release_flags_changed") is not False:
                row_failures.append("ddg_model_or_release_flags_changed_unexpected")
        if lane == "five_head_minimum_sample_threshold":
            if int(row.get("ready_head_count") or 0) != 0:
                row_failures.append("five_head_ready_count_unexpected")
            if set(row.get("candidate_heads") or []) != set():
                row_failures.append("five_head_candidate_heads_unexpected")
        if lane == "human_preflight_fireprot_plate_retention":
            if int(row.get("package_rows") or 0) != 3:
                row_failures.append("human_package_rows_not_3")
            if int(row.get("ready_for_training_import_rows") or 0) != 0:
                row_failures.append("human_training_import_rows_unexpected")
        if row_failures:
            failures.append({"check": "row_policy", "row": index, "lane": lane, "failures": row_failures})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "receipt_rows": len(rows),
        "expected_lane_count": len(EXPECTED_LANES),
        "validation_passed_rows": sum(1 for row in rows if row.get("validation_passed") is True),
        "eligibility_changed_rows": sum(1 for row in rows if row.get("eligibility_changed") is True),
        "formal_decision_written_rows": sum(1 for row in rows if row.get("formal_decision_written") is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row.get("runtime_receipt_written") is True),
        "training_import_written_rows": sum(1 for row in rows if row.get("training_import_written") is True),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Receipts are local execution evidence only. The ddG lane may carry a reviewed local PyRosetta runtime receipt; training imports, model claims, and release remain fail-closed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "receipt_rows": report["receipt_rows"],
        "validation_passed_rows": report["validation_passed_rows"],
        "failures": len(failures),
        "safe_for_model_claim": report["safe_for_model_claim"],
        "release_ready": report["release_ready"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
