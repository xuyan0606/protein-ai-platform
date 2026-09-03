#!/usr/bin/env python3
"""Validate multi-task training readiness remains source-bound and fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
OUT = AI_ROOT / "reports" / "multitask_training_readiness_validation_report.json"
STRICT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
AUDITED = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_audited.jsonl"
ACTIVITY_RISK_IMPORT = AI_ROOT / "datasets" / "training" / "activity_risk_training_import_labels.jsonl"
ACTIVITY_RISK_IMPORT_VALIDATION = AI_ROOT / "reports" / "activity_risk_training_import_label_validation_report.json"
EXPECTED_HEADS = ("mutation_rank", "stability", "activity_risk", "substrate_fit", "assay_success")


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


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def count_present(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> int:
    return sum(1 for row in rows if any(row.get(key) not in (None, "") for key in keys))


def activity_risk_training_import_label_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("head") == "activity_risk"
        and row.get("ready_for_training_import") is True
        and row.get("training_label_source") is True
        and row.get("label_value") not in (None, "")
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate multi-task training readiness report")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    strict_rows = load_jsonl(STRICT)
    audited_rows = load_jsonl(AUDITED)
    activity_risk_import_rows = load_jsonl(ACTIVITY_RISK_IMPORT)
    activity_risk_import_validation = load_json(ACTIVITY_RISK_IMPORT_VALIDATION)
    activity_risk_labels = activity_risk_training_import_label_rows(activity_risk_import_rows)
    activity_risk_validation_rows = as_int(
        activity_risk_import_validation.get("training_import_label_rows")
        if "training_import_label_rows" in activity_risk_import_validation
        else activity_risk_import_validation.get("training_import_written_rows")
    )

    failures: list[dict[str, Any]] = []
    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(report.get("status") != "blocked", failures, "status_blocked", report.get("status"), "blocked")
    for key in ("training_execution_allowed", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(key) is not False, failures, f"{key}_false", report.get(key), False)

    source_counts = report.get("source_counts") if isinstance(report.get("source_counts"), dict) else {}
    fail_if(as_int(report.get("strict_rows")) != len(strict_rows), failures, "strict_rows_match_jsonl", report.get("strict_rows"), len(strict_rows))
    fail_if(as_int(report.get("audited_rows")) != len(audited_rows), failures, "audited_rows_match_jsonl", report.get("audited_rows"), len(audited_rows))
    fail_if(as_int(source_counts.get("strict_supervised_rows")) != len(strict_rows), failures, "source_strict_rows_match_jsonl", source_counts.get("strict_supervised_rows"), len(strict_rows))
    fail_if(as_int(source_counts.get("audited_training_rows")) != len(audited_rows), failures, "source_audited_rows_match_jsonl", source_counts.get("audited_training_rows"), len(audited_rows))
    fail_if(
        as_int(source_counts.get("activity_risk_training_import_jsonl_rows")) != len(activity_risk_import_rows),
        failures,
        "source_activity_risk_import_jsonl_rows_match_jsonl",
        source_counts.get("activity_risk_training_import_jsonl_rows"),
        len(activity_risk_import_rows),
    )
    fail_if(
        as_int(source_counts.get("activity_risk_training_import_label_rows")) != len(activity_risk_labels),
        failures,
        "source_activity_risk_import_label_rows_match_jsonl",
        source_counts.get("activity_risk_training_import_label_rows"),
        len(activity_risk_labels),
    )
    fail_if(
        as_int(source_counts.get("activity_risk_training_import_validation_report_rows")) != activity_risk_validation_rows,
        failures,
        "source_activity_risk_import_rows_match_validation_report",
        source_counts.get("activity_risk_training_import_validation_report_rows"),
        activity_risk_validation_rows,
    )

    source_consistency = report.get("source_consistency") if isinstance(report.get("source_consistency"), dict) else {}
    activity_consistency = (
        source_consistency.get("activity_risk_training_import")
        if isinstance(source_consistency.get("activity_risk_training_import"), dict)
        else {}
    )
    fail_if(activity_consistency.get("validation_report_present") is not True, failures, "activity_risk_validation_report_present", activity_consistency.get("validation_report_present"), True)
    fail_if(activity_consistency.get("validation_success") is not True, failures, "activity_risk_validation_success", activity_consistency.get("validation_success"), True)
    fail_if(activity_consistency.get("training_execution_allowed") is not False, failures, "activity_risk_validation_training_execution_allowed_false", activity_consistency.get("training_execution_allowed"), False)
    fail_if(activity_consistency.get("consistent") is not True, failures, "activity_risk_source_consistent", activity_consistency.get("consistent"), True)

    expected_rows = {
        "mutation_rank": count_present(strict_rows, ("label_decision",)),
        "stability": count_present(strict_rows, ("label_stability_delta_tm_c", "label_ddg")),
        "activity_risk": len(activity_risk_labels),
        "substrate_fit": count_present(audited_rows, ("substrate_fit_label",)),
        "assay_success": count_present(audited_rows, ("assay_success",)),
    }
    heads = report.get("heads") if isinstance(report.get("heads"), dict) else {}
    fail_if(set(heads) != set(EXPECTED_HEADS), failures, "all_heads_present", sorted(heads), sorted(EXPECTED_HEADS))
    computed_missing_heads: list[str] = []
    for head in EXPECTED_HEADS:
        row = heads.get(head) if isinstance(heads.get(head), dict) else {}
        observed_rows = as_int(row.get("rows"))
        minimum_rows = as_int(row.get("minimum_rows"))
        expected_ready = observed_rows >= minimum_rows and minimum_rows >= 100
        fail_if(observed_rows != expected_rows[head], failures, f"{head}_rows_match_source", observed_rows, expected_rows[head])
        fail_if(minimum_rows < 100, failures, f"{head}_minimum_rows_at_least_100", row.get("minimum_rows"), ">=100")
        fail_if(row.get("ready") is not expected_ready, failures, f"{head}_ready_matches_rows", row.get("ready"), expected_ready)
        if head == "activity_risk":
            fail_if(row.get("training_import_source_consistent") is not True, failures, "activity_risk_training_import_source_consistent", row.get("training_import_source_consistent"), True)
            fail_if(row.get("training_execution_allowed") is not False, failures, "activity_risk_training_execution_allowed_false", row.get("training_execution_allowed"), False)
            fail_if(row.get("safe_for_model_claim") is not False, failures, "activity_risk_safe_for_model_claim_false", row.get("safe_for_model_claim"), False)
            fail_if(row.get("release_ready") is not False, failures, "activity_risk_release_ready_false", row.get("release_ready"), False)
        if not expected_ready:
            computed_missing_heads.append(head)

    fail_if(report.get("ready_head_count") != 0, failures, "ready_head_count_zero", report.get("ready_head_count"), 0)
    fail_if(
        sorted(report.get("missing_head_labels") or []) != sorted(computed_missing_heads),
        failures,
        "missing_head_labels_match_non_ready_heads",
        report.get("missing_head_labels"),
        computed_missing_heads,
    )

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_report": str(args.report),
        "source_counts": source_counts,
        "expected_head_rows": expected_rows,
        "missing_head_labels": report.get("missing_head_labels"),
        "ready_head_count": report.get("ready_head_count"),
        "training_execution_allowed": report.get("training_execution_allowed"),
        "failures": failures,
        "success": not failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed validation for multi-task readiness; source rows are not synthetic supervision.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "ready_head_count": validation["ready_head_count"],
        "expected_head_rows": expected_rows,
        "training_execution_allowed": validation["training_execution_allowed"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
