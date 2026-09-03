#!/usr/bin/env python3
"""Validate the five-head benchmark gap plan is source-bound and fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "five_head_benchmark_gap_plan_report.json"
MARKDOWN = AI_ROOT / "reports" / "five_head_benchmark_gap_plan.md"
ACTIONS = AI_ROOT / "datasets" / "governance" / "five_head_benchmark_gap_actions.jsonl"
MATRIX = AI_ROOT / "reports" / "benchmark_matrix_report.json"
ACQUISITION_REPORT = AI_ROOT / "reports" / "benchmark_acquisition_plan_report.json"
ACQUISITION_PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
CACHE_VALIDATION = AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json"
CACHE_MANIFEST = AI_ROOT / "reports" / "benchmark_score_cache_manifest.json"
CLAIM_READINESS = AI_ROOT / "reports" / "claim_readiness_matrix.json"
MULTITASK_READINESS = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
OUT = AI_ROOT / "reports" / "five_head_benchmark_gap_plan_validation_report.json"

HEADS = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)

HEAD_METRIC_CLAIMS = {
    "mutation_rank": [
        "mutation-rank benchmark scorecard",
        "mutation ranking quality or Spearman/AUROC claim",
    ],
    "stability": [
        "stability benchmark scorecard",
        "deltaTm/ddG stability prediction quality claim",
    ],
    "activity_risk": [
        "activity-risk benchmark scorecard",
        "activity retention or activity-risk calibration claim",
    ],
    "substrate_fit": [
        "substrate-fit benchmark scorecard",
        "substrate affinity, pose, or fit quality claim",
    ],
    "assay_success": [
        "assay-success benchmark scorecard",
        "plate/QC success-rate prediction quality claim",
    ],
}

ACTION_PARITY_FIELDS = (
    "action_id",
    "head",
    "priority",
    "status",
    "required_benchmarks",
    "acquisition_configured_benchmarks",
    "cache_validated_benchmarks",
    "missing_acquisition_configuration_benchmarks",
    "missing_cache_validation_benchmarks",
    "missing_benchmarks",
    "benchmarks_requiring_acquisition_configuration",
    "benchmarks_requiring_download_or_cache",
    "benchmarks_requiring_license_authorization",
    "benchmarks_requiring_human_acceptance",
    "not_claimable_metrics",
    "metric_claim_allowed",
    "blocking_reasons",
    "required_acceptance_artifacts",
    "safe_for_model_claim",
    "release_ready",
)

POLICY = (
    "Fail-closed validation for five-head benchmark gap planning. The validated "
    "artifact remains planning evidence only; it does not approve benchmarks, "
    "write labels, run training, open model claims, or grant release readiness."
)


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path, failures: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append({"check": f"{label}_valid_json", "observed": str(exc), "expected": "JSON object"})
        return {}
    if not isinstance(value, dict):
        failures.append({"check": f"{label}_json_object", "observed": type(value).__name__, "expected": "object"})
        return {}
    return value


def load_jsonl(path: Path, failures: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append({
                "check": f"{label}_valid_jsonl",
                "line": line_number,
                "observed": str(exc),
                "expected": "one JSON object per line",
            })
            continue
        if not isinstance(value, dict):
            failures.append({
                "check": f"{label}_jsonl_object",
                "line": line_number,
                "observed": type(value).__name__,
                "expected": "object",
            })
            continue
        rows.append(value)
    return rows


def load_text(path: Path, failures: list[dict[str, Any]], label: str) -> str:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return ""
    return path.read_text(encoding="utf-8")


def check(condition: bool, failures: list[dict[str, Any]], name: str, observed: Any, expected: Any) -> None:
    if not condition:
        failures.append({"check": name, "observed": observed, "expected": expected})


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def license_ready(status: Any) -> bool:
    return str(status or "").startswith("approved")


def index_by_key(rows: list[dict[str, Any]], failures: list[dict[str, Any]], label: str) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        head = row.get("head")
        benchmark_name = row.get("benchmark_name")
        if not isinstance(head, str) or not isinstance(benchmark_name, str):
            failures.append({"check": f"{label}_identity", "observed": row, "expected": "head and benchmark_name strings"})
            continue
        key = (head, benchmark_name)
        if key in indexed:
            failures.append({"check": f"{label}_unique", "observed": key, "expected": "no duplicate rows"})
            continue
        indexed[key] = row
    return indexed


def sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def benchmark_requirements(
    benchmark_name: str,
    plan_row: dict[str, Any] | None,
    validation_row: dict[str, Any] | None,
    manifest_row: dict[str, Any] | None,
) -> dict[str, Any]:
    plan_status = str(plan_row.get("acquisition_status") or "not_planned") if plan_row else "not_planned"
    manifest_status = str(manifest_row.get("status") or "missing") if manifest_row else "missing"
    local_dataset_uri = (
        manifest_row.get("local_dataset_uri")
        if manifest_row and manifest_row.get("local_dataset_uri")
        else (plan_row.get("local_dataset_uri") if plan_row else None)
    )
    checksum = (
        manifest_row.get("dataset_sha256")
        if manifest_row and manifest_row.get("dataset_sha256")
        else (plan_row.get("checksum") if plan_row else None)
    )
    scorecard_uri = manifest_row.get("scorecard_uri") if manifest_row else None
    metric_report_uri = manifest_row.get("metric_report_uri") if manifest_row else None
    scorecard_status = str(plan_row.get("scorecard_status") or "not_ready") if plan_row else "not_ready"
    leakage_status = (
        manifest_row.get("leakage_check_status")
        if manifest_row and manifest_row.get("leakage_check_status")
        else (plan_row.get("leakage_check_status") if plan_row else "not_run")
    )
    license_status = (
        manifest_row.get("license_review_status")
        if manifest_row and manifest_row.get("license_review_status")
        else (plan_row.get("license_review_status") if plan_row else "not_reviewed")
    )
    validation_errors = validation_row.get("errors") if validation_row else ["validation_record_missing"]
    if not isinstance(validation_errors, list):
        validation_errors = ["validation_errors_invalid"]
    validation_valid = bool(validation_row and validation_row.get("valid") is True and not validation_errors)
    scorecard_ready = scorecard_status == "ready" or bool(validation_valid and scorecard_uri and metric_report_uri)
    leakage_ready = leakage_status == "passed" or bool(validation_valid and benchmark_name == "KWB strict mutation holdout")

    requires_acquisition_configuration = plan_status != "configured"
    requires_download_or_cache = manifest_status != "present" or not local_dataset_uri or not checksum
    requires_license_authorization = not license_ready(license_status)
    requires_scorecard_artifacts = not scorecard_ready
    requires_leakage_check = not leakage_ready
    requires_human_acceptance = (
        requires_acquisition_configuration
        or requires_download_or_cache
        or requires_license_authorization
        or requires_scorecard_artifacts
        or requires_leakage_check
        or not validation_valid
    )

    required_operator_actions: list[str] = []
    if requires_acquisition_configuration:
        required_operator_actions.append("configure_acquisition_plan_row")
    if requires_download_or_cache:
        required_operator_actions.append("download_or_register_local_benchmark_cache")
    if requires_license_authorization:
        required_operator_actions.append("complete_license_authorization")
    if requires_scorecard_artifacts:
        required_operator_actions.append("attach_scorecard_and_metric_artifacts")
    if requires_leakage_check:
        required_operator_actions.append("run_or_record_leakage_check")
    if not validation_valid:
        required_operator_actions.append("rerun_benchmark_cache_validation")
    if requires_human_acceptance:
        required_operator_actions.append("human_acceptance_before_metric_claim")

    blockers: list[str] = []
    if not plan_row:
        blockers.append("acquisition_plan_row_missing")
    elif requires_acquisition_configuration:
        blockers.append(f"acquisition_status:{plan_status}")
    if not validation_row:
        blockers.append("cache_validation_record_missing")
    elif not validation_valid:
        blockers.extend(str(error) for error in validation_errors)

    return {
        "acquisition_plan_status": plan_status,
        "acquisition_configured": plan_status == "configured",
        "cache_validation_valid": validation_valid,
        "cache_validation_errors": validation_errors,
        "status": "ready" if plan_status == "configured" and validation_valid else "blocked",
        "blockers": blockers,
        "manifest_status": manifest_status,
        "local_dataset_uri": local_dataset_uri,
        "checksum_present": bool(checksum),
        "license_review_status": license_status,
        "scorecard_status": "ready" if scorecard_ready else scorecard_status,
        "scorecard_uri": scorecard_uri,
        "metric_report_uri": metric_report_uri,
        "leakage_check_status": leakage_status,
        "requires_acquisition_configuration": requires_acquisition_configuration,
        "requires_download_or_cache": requires_download_or_cache,
        "requires_license_authorization": requires_license_authorization,
        "requires_scorecard_artifacts": requires_scorecard_artifacts,
        "requires_leakage_check": requires_leakage_check,
        "requires_human_acceptance": requires_human_acceptance,
        "required_operator_actions": required_operator_actions,
        "benchmark_metric_claim_allowed": False,
        "claim_gate": "blocked_until_cache_license_leakage_scorecard_and_human_acceptance_pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate five-head benchmark gap plan")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--actions", type=Path, default=ACTIONS)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    report = load_json(args.report, failures, "report")
    markdown = load_text(args.markdown, failures, "markdown")
    action_rows = load_jsonl(args.actions, failures, "actions")
    matrix = load_json(MATRIX, failures, "matrix")
    acquisition_report = load_json(ACQUISITION_REPORT, failures, "acquisition_report")
    acquisition_rows = load_jsonl(ACQUISITION_PLAN, failures, "acquisition_plan")
    cache_validation = load_json(CACHE_VALIDATION, failures, "cache_validation")
    cache_manifest = load_json(CACHE_MANIFEST, failures, "cache_manifest")
    claim_readiness = load_json(CLAIM_READINESS, failures, "claim_readiness")
    multitask_readiness = load_json(MULTITASK_READINESS, failures, "multitask_readiness")

    matrix_heads = matrix.get("heads") if isinstance(matrix.get("heads"), list) else []
    matrix_by_head = {
        row.get("head"): row
        for row in matrix_heads
        if isinstance(row, dict) and isinstance(row.get("head"), str)
    }
    check(tuple(matrix_by_head) == HEADS, failures, "matrix_heads_expected_order", list(matrix_by_head), list(HEADS))

    plan_by_key = index_by_key(acquisition_rows, failures, "acquisition_plan")
    validation_rows = cache_validation.get("records") if isinstance(cache_validation.get("records"), list) else []
    validation_by_key = index_by_key([row for row in validation_rows if isinstance(row, dict)], failures, "cache_validation")
    manifest_rows = cache_manifest.get("rows") if isinstance(cache_manifest.get("rows"), list) else []
    manifest_by_key = index_by_key([row for row in manifest_rows if isinstance(row, dict)], failures, "cache_manifest")
    multitask_heads = multitask_readiness.get("heads") if isinstance(multitask_readiness.get("heads"), dict) else {}
    blocked_claim_ids = claim_readiness.get("blocked_claim_ids") if isinstance(claim_readiness.get("blocked_claim_ids"), list) else []
    blocked_claim_ids = [str(claim_id) for claim_id in blocked_claim_ids]

    expected_heads: list[dict[str, Any]] = []
    expected_actions: list[dict[str, Any]] = []
    expected_not_claimable: list[dict[str, Any]] = []
    error_counts: Counter[str] = Counter()
    operator_action_counts: Counter[str] = Counter()
    total_required = 0
    total_configured = 0
    total_valid = 0
    complete_heads = 0

    for head in HEADS:
        matrix_row = matrix_by_head.get(head, {}) if isinstance(matrix_by_head.get(head), dict) else {}
        required = matrix_row.get("required_benchmarks")
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            failures.append({"check": f"{head}_required_benchmarks_from_matrix", "observed": required, "expected": "list[str]"})
            required = []
        benchmark_rows = [
            {
                "benchmark_name": benchmark_name,
                **benchmark_requirements(
                    benchmark_name,
                    plan_by_key.get((head, benchmark_name)),
                    validation_by_key.get((head, benchmark_name)),
                    manifest_by_key.get((head, benchmark_name)),
                ),
            }
            for benchmark_name in required
        ]
        required_count = len(benchmark_rows)
        configured_count = sum(1 for row in benchmark_rows if row["acquisition_configured"])
        valid_count = sum(1 for row in benchmark_rows if row["cache_validation_valid"])
        benchmark_blockers = sorted({blocker for row in benchmark_rows for blocker in row["blockers"]})
        for row in benchmark_rows:
            error_counts.update(str(error) for error in row["cache_validation_errors"])
            operator_action_counts.update(row["required_operator_actions"])
        complete = (
            required_count > 0
            and configured_count == required_count
            and valid_count == required_count
            and not any(row["requires_human_acceptance"] for row in benchmark_rows)
        )
        head_training = multitask_heads.get(head) if isinstance(multitask_heads.get(head), dict) else {}
        not_claimable_metrics = [] if complete and head_training.get("ready") is True else HEAD_METRIC_CLAIMS[head]
        benchmarks_requiring_acquisition_configuration = [
            row["benchmark_name"] for row in benchmark_rows if row["requires_acquisition_configuration"]
        ]
        benchmarks_requiring_download_or_cache = [
            row["benchmark_name"] for row in benchmark_rows if row["requires_download_or_cache"]
        ]
        benchmarks_requiring_license_authorization = [
            row["benchmark_name"] for row in benchmark_rows if row["requires_license_authorization"]
        ]
        benchmarks_requiring_human_acceptance = [
            row["benchmark_name"] for row in benchmark_rows if row["requires_human_acceptance"]
        ]

        expected_head = {
            "head": head,
            "matrix_status": matrix_row.get("status", "missing"),
            "required_benchmarks": required_count,
            "planned_benchmarks": required_count - sum(1 for row in benchmark_rows if row["acquisition_plan_status"] == "not_planned"),
            "acquisition_configured_benchmarks": configured_count,
            "acquisition_configuration_coverage": ratio(configured_count, required_count),
            "cache_validated_benchmarks": valid_count,
            "cache_validation_coverage": ratio(valid_count, required_count),
            "missing_acquisition_plan_benchmarks": sum(1 for row in benchmark_rows if row["acquisition_plan_status"] == "not_planned"),
            "missing_acquisition_configuration_benchmarks": required_count - configured_count,
            "missing_cache_validation_benchmarks": required_count - valid_count,
            "complete_scorecard": complete,
            "training_ready_from_matrix": matrix_row.get("training_ready") is True,
            "benchmark_rows": benchmark_rows,
            "blockers": benchmark_blockers,
            "benchmarks_requiring_acquisition_configuration": benchmarks_requiring_acquisition_configuration,
            "benchmarks_requiring_download_or_cache": benchmarks_requiring_download_or_cache,
            "benchmarks_requiring_license_authorization": benchmarks_requiring_license_authorization,
            "benchmarks_requiring_human_acceptance": benchmarks_requiring_human_acceptance,
            "not_claimable_metrics": not_claimable_metrics,
            "metric_claim_allowed": False,
            "status": "ready" if complete else "blocked",
            "safe_for_model_claim": False,
        }
        expected_heads.append(expected_head)
        if not_claimable_metrics:
            expected_not_claimable.append(
                {
                    "head": head,
                    "not_claimable_metrics": not_claimable_metrics,
                    "blocking_reasons": sorted(
                        set(
                            benchmark_blockers
                            + list(matrix_row.get("blockers") or [])
                            + ["head_training_readiness_false"]
                        )
                    ),
                    "source_claim_blockers": [
                        claim_id
                        for claim_id in blocked_claim_ids
                        if claim_id in {"model_quality_claim", "five_head_training_run"}
                    ],
                    "safe_for_model_claim": False,
                    "metric_claim_allowed": False,
                }
            )

        expected_actions.append({
            "action_id": f"five_head_benchmark_gap::{head}",
            "head": head,
            "priority": "P0",
            "status": "open_blocked",
            "required_benchmarks": required_count,
            "acquisition_configured_benchmarks": configured_count,
            "cache_validated_benchmarks": valid_count,
            "missing_acquisition_configuration_benchmarks": required_count - configured_count,
            "missing_cache_validation_benchmarks": required_count - valid_count,
            "missing_benchmarks": [row["benchmark_name"] for row in benchmark_rows if not row["cache_validation_valid"]],
            "benchmarks_requiring_acquisition_configuration": benchmarks_requiring_acquisition_configuration,
            "benchmarks_requiring_download_or_cache": benchmarks_requiring_download_or_cache,
            "benchmarks_requiring_license_authorization": benchmarks_requiring_license_authorization,
            "benchmarks_requiring_human_acceptance": benchmarks_requiring_human_acceptance,
            "not_claimable_metrics": not_claimable_metrics,
            "metric_claim_allowed": False,
            "blocking_reasons": benchmark_blockers,
            "required_acceptance_artifacts": [
                "configured_acquisition_plan_row",
                "local_dataset_uri",
                "dataset_checksum",
                "license_review_status",
                "split_or_leakage_check_status",
                "scorecard_uri",
                "metric_report_uri",
                "cache_validation_record",
                "human_acceptance_receipt",
            ],
            "safe_for_model_claim": False,
            "release_ready": False,
        })
        total_required += required_count
        total_configured += configured_count
        total_valid += valid_count
        complete_heads += int(complete)

    source_report_consistent = (
        matrix.get("matrix_artifact_ready") is True
        and acquisition_report.get("plan_rows") == total_required
        and cache_validation.get("benchmark_rows") == total_required
        and cache_validation.get("valid_rows") == total_valid
        and cache_manifest.get("expected_benchmarks") == total_required
        and cache_manifest.get("accepted_benchmarks") == total_valid
    )
    expected_summary = {
        "required_heads": len(HEADS),
        "heads_with_complete_scorecards": complete_heads,
        "required_benchmarks": total_required,
        "planned_benchmarks": sum(head["planned_benchmarks"] for head in expected_heads),
        "configured_benchmarks": total_configured,
        "acquisition_configuration_coverage": ratio(total_configured, total_required),
        "cache_validated_benchmarks": total_valid,
        "cache_validation_coverage": ratio(total_valid, total_required),
        "missing_acquisition_plan_benchmarks": sum(head["missing_acquisition_plan_benchmarks"] for head in expected_heads),
        "missing_acquisition_configuration_benchmarks": total_required - total_configured,
        "missing_cache_validation_benchmarks": total_required - total_valid,
        "cache_validation_error_counts": sorted_counter(error_counts),
        "operator_action_counts": sorted_counter(operator_action_counts),
        "heads_with_not_claimable_metrics": len(expected_not_claimable),
        "benchmarks_requiring_download_or_cache": sum(len(head["benchmarks_requiring_download_or_cache"]) for head in expected_heads),
        "benchmarks_requiring_license_authorization": sum(len(head["benchmarks_requiring_license_authorization"]) for head in expected_heads),
        "benchmarks_requiring_human_acceptance": sum(len(head["benchmarks_requiring_human_acceptance"]) for head in expected_heads),
        "blocked_claim_ids": blocked_claim_ids,
        "source_report_consistent": source_report_consistent,
        "benchmark_evaluation_coverage_complete": (
            total_required > 0
            and total_configured == total_required
            and total_valid == total_required
            and complete_heads == len(HEADS)
            and source_report_consistent
        ),
    }

    check(report.get("local_only") is True, failures, "report_local_only_true", report.get("local_only"), True)
    check(report.get("status") == "blocked", failures, "report_status_blocked", report.get("status"), "blocked")
    for key in ("ready_for_model_claim", "safe_for_model_claim", "release_ready"):
        check(report.get(key) is False, failures, f"report_{key}_false", report.get(key), False)
    check(report.get("summary") == expected_summary, failures, "summary_matches_current_sources", report.get("summary"), expected_summary)
    check(report.get("heads") == expected_heads, failures, "heads_match_current_sources", report.get("heads"), expected_heads)
    check(
        report.get("not_claimable_model_metrics") == expected_not_claimable,
        failures,
        "not_claimable_metrics_match_current_sources",
        report.get("not_claimable_model_metrics"),
        expected_not_claimable,
    )

    report_actions = report.get("actions") if isinstance(report.get("actions"), list) else []
    check(len(action_rows) == len(HEADS), failures, "actions_jsonl_rows_match_expected_heads", len(action_rows), len(HEADS))
    check(report_actions == action_rows, failures, "actions_jsonl_matches_report_actions", action_rows, report_actions)
    for observed, expected in zip(report_actions, expected_actions):
        head = expected["head"]
        for field in ACTION_PARITY_FIELDS:
            check(
                isinstance(observed, dict) and observed.get(field) == expected[field],
                failures,
                f"{head}_action_{field}_matches_current_sources",
                observed.get(field) if isinstance(observed, dict) else None,
                expected[field],
            )
        if isinstance(observed, dict):
            check(observed.get("metric_claim_allowed") is False, failures, f"{head}_action_metric_claim_allowed_false", observed.get("metric_claim_allowed"), False)
            check(observed.get("safe_for_model_claim") is False, failures, f"{head}_action_safe_for_model_claim_false", observed.get("safe_for_model_claim"), False)
            check(observed.get("release_ready") is False, failures, f"{head}_action_release_ready_false", observed.get("release_ready"), False)

    expected_markdown_lines = [
        f"- Status: `{report.get('status')}`",
        f"- Required benchmarks: `{expected_summary['required_benchmarks']}`",
        f"- Acquisition-configured benchmarks: `{expected_summary['configured_benchmarks']}`",
        f"- Cache-validated benchmarks: `{expected_summary['cache_validated_benchmarks']}`",
        f"- Missing cache validation: `{expected_summary['missing_cache_validation_benchmarks']}`",
        f"- Heads with complete scorecards: `{expected_summary['heads_with_complete_scorecards']}/{expected_summary['required_heads']}`",
        "- Ready for model claim: `False`",
        "- Safe for model claim: `False`",
        "- Release ready: `False`",
    ]
    missing_markdown_lines = [line for line in expected_markdown_lines if line not in markdown]
    check(not missing_markdown_lines, failures, "markdown_summary_lines_match_report", missing_markdown_lines, [])

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_report": relative(args.report),
        "checked_markdown": relative(args.markdown),
        "checked_actions": relative(args.actions),
        "expected_heads": list(HEADS),
        "action_rows": len(action_rows),
        "required_benchmarks": total_required,
        "cache_validated_benchmarks": total_valid,
        "heads_with_complete_scorecards": complete_heads,
        "source_report_consistent": source_report_consistent,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "failures": failures[:500],
        "failure_count": len(failures),
        "success": not failures,
        "policy": POLICY,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "required_benchmarks": total_required,
        "cache_validated_benchmarks": total_valid,
        "heads_with_complete_scorecards": complete_heads,
        "failures": len(failures),
        "output": relative(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
