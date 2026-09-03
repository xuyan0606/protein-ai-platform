#!/usr/bin/env python3
"""Validate Stage 25 benchmark unblock design."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DESIGNS = AI_ROOT / "datasets" / "governance" / "stage25_benchmark_unblock_design_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_benchmark_unblock_design_validation_20260806.json"
EXPECTED_BENCHMARKS = {"kwb_strict_mutation_holdout", "reviewed_substrate_identity_set"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not DESIGNS.exists(), failures, "design_file_exists", "missing", str(DESIGNS))
    rows = load_jsonl(DESIGNS) if DESIGNS.exists() else []
    benchmarks = {str(row.get("benchmark_id")) for row in rows}
    fail_if(benchmarks != EXPECTED_BENCHMARKS, failures, "benchmark_ids", sorted(benchmarks), sorted(EXPECTED_BENCHMARKS))
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(row.get("current_status") != "blocked", failures, f"{prefix}.current_status", row.get("current_status"), "blocked")
        for field in ("required_formal_decision_file", "required_formal_decisions", "required_human_checks", "regenerated_artifacts_required", "required_acceptance_receipt", "not_auto_generatable"):
            fail_if(not row.get(field), failures, f"{prefix}.{field}_present", row.get(field), "non-empty")
        for flag in ("completion_ready_now", "benchmark_completion_ready", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
        fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written_zero", row.get("formal_decision_rows_written"), 0)
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_benchmark_unblock_design_validation",
        "stage": 25,
        "design_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "design_rows": len(rows),
        "blocked_benchmark_rows": sum(1 for row in rows if row.get("current_status") == "blocked"),
        "completion_ready_rows": 0,
        "formal_decision_rows_written": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "design_valid": report["design_valid"], "failure_count": report["failure_count"], "design_rows": report["design_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["design_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
