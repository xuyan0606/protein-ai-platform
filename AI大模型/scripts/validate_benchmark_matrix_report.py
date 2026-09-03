#!/usr/bin/env python3
"""Validate the five-head benchmark matrix is source-bound and fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "benchmark_matrix_report.json"
OUT = AI_ROOT / "reports" / "benchmark_matrix_validation_report.json"
MULTITASK = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
EXPECTED_BENCHMARKS = {
    "mutation_rank": ["ProteinGym", "FLIP/FLIP2-style protein/family/time split", "KWB strict mutation holdout"],
    "stability": ["ThermoMPNN comparison", "ATOM3D MSP", "FireProt/ProTherm reviewed stability set"],
    "activity_risk": [
        "KWB activity numeric feedback smoke",
        "KWB plate-level wet-lab feedback",
        "CatPred/GotEnzymes predicted reference only",
    ],
    "substrate_fit": ["PDBbind/CASF/D3R-style affinity or pose benchmark", "PoseBusters-style pose plausibility", "reviewed substrate identity set"],
    "assay_success": ["KWB plate-level feedback", "replicate consistency", "QC fail-rate calibration"],
}
EXPECTED_HEADS = tuple(EXPECTED_BENCHMARKS)
EXPECTED_BLOCKERS = [
    "benchmark dataset is not configured locally",
    "head is not training-ready with reviewed labels",
    "external predicted/reference data cannot substitute for wet-lab labels",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def head_rows(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row.get("head"): row
        for row in (report.get("heads") or [])
        if isinstance(row, dict)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark matrix report")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    multitask = load_json(MULTITASK)
    matrix_heads = head_rows(report)
    multitask_heads = multitask.get("heads") if isinstance(multitask.get("heads"), dict) else {}
    failures: list[dict[str, Any]] = []

    expected_ready_for_model_claim = all(
        bool(row.get("training_ready")) and bool(row.get("benchmark_data_ready")) and bool(row.get("scorecard_ready"))
        for row in matrix_heads.values()
    )

    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(report.get("local_only") is not True, failures, "local_only_true", report.get("local_only"), True)
    fail_if(report.get("matrix_artifact_ready") is not True, failures, "matrix_artifact_ready_true", report.get("matrix_artifact_ready"), True)
    fail_if(set(matrix_heads) != set(EXPECTED_HEADS), failures, "matrix_heads_expected", sorted(matrix_heads), sorted(EXPECTED_HEADS))
    fail_if(list(matrix_heads) != list(EXPECTED_HEADS), failures, "matrix_head_order_expected", list(matrix_heads), list(EXPECTED_HEADS))
    fail_if(set(multitask_heads) != set(EXPECTED_HEADS), failures, "multitask_heads_expected", sorted(multitask_heads), sorted(EXPECTED_HEADS))
    fail_if(report.get("ready_for_model_claim") != expected_ready_for_model_claim, failures, "ready_for_model_claim_matches_rows", report.get("ready_for_model_claim"), expected_ready_for_model_claim)
    fail_if(report.get("ready_for_model_claim") is not False, failures, "ready_for_model_claim_false", report.get("ready_for_model_claim"), False)

    for head in EXPECTED_HEADS:
        row = matrix_heads.get(head, {})
        source = multitask_heads.get(head) if isinstance(multitask_heads.get(head), dict) else {}
        fail_if(row.get("label_rows") != as_int(source.get("rows")), failures, f"{head}_label_rows_match_multitask", row.get("label_rows"), as_int(source.get("rows")))
        fail_if(row.get("minimum_rows") != as_int(source.get("minimum_rows")), failures, f"{head}_minimum_rows_match_multitask", row.get("minimum_rows"), as_int(source.get("minimum_rows")))
        fail_if(row.get("training_ready") != bool(source.get("ready")), failures, f"{head}_training_ready_matches_multitask", row.get("training_ready"), bool(source.get("ready")))
        fail_if(row.get("required_benchmarks") != EXPECTED_BENCHMARKS[head], failures, f"{head}_required_benchmarks_expected", row.get("required_benchmarks"), EXPECTED_BENCHMARKS[head])
        fail_if(row.get("benchmark_data_ready") is not False, failures, f"{head}_benchmark_data_ready_false", row.get("benchmark_data_ready"), False)
        fail_if(row.get("scorecard_ready") is not False, failures, f"{head}_scorecard_ready_false", row.get("scorecard_ready"), False)
        fail_if(row.get("status") != "blocked", failures, f"{head}_status_blocked", row.get("status"), "blocked")
        fail_if(row.get("blockers") != EXPECTED_BLOCKERS, failures, f"{head}_blockers_expected", row.get("blockers"), EXPECTED_BLOCKERS)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_report": str(args.report),
        "expected_heads": list(EXPECTED_HEADS),
        "heads": len(matrix_heads),
        "ready_for_model_claim": False,
        "failures": failures,
        "success": not failures,
        "policy": "Benchmark matrix validation is fail-closed; benchmark artifacts are evaluation gates only and do not create training labels, model claims, or release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "heads": validation["heads"],
        "ready_for_model_claim": False,
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
