#!/usr/bin/env python3
"""Build a fail-closed five-head benchmark evaluation gap plan.

The script reads only benchmark planning and validation artifacts. Its outputs
are planning records, not benchmark acquisition, approval, model execution, or
release inputs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MATRIX = AI_ROOT / "reports" / "benchmark_matrix_report.json"
ACQUISITION_REPORT = AI_ROOT / "reports" / "benchmark_acquisition_plan_report.json"
ACQUISITION_PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
CACHE_VALIDATION = AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json"
CACHE_MANIFEST = AI_ROOT / "reports" / "benchmark_score_cache_manifest.json"
CLAIM_READINESS = AI_ROOT / "reports" / "claim_readiness_matrix.json"
MULTITASK_READINESS = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
REPORT_OUT = AI_ROOT / "reports" / "five_head_benchmark_gap_plan_report.json"
MARKDOWN_OUT = AI_ROOT / "reports" / "five_head_benchmark_gap_plan.md"
ACTIONS_OUT = AI_ROOT / "datasets" / "governance" / "five_head_benchmark_gap_actions.jsonl"

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

POLICY = (
    "Fail closed: this benchmark gap plan remains blocked unless all five canonical heads have every "
    "required benchmark cache-validated, locally checksummed, license-reviewed, leakage-checked, "
    "human-accepted, and all source reports agree. It is an evaluation planning artifact only and "
    "never grants approval, a model claim, a training import, or release readiness."
)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path, input_errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        input_errors.append(f"missing_input:{relative(path)}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        input_errors.append(f"invalid_json:{relative(path)}")
        return {}
    if not isinstance(data, dict):
        input_errors.append(f"invalid_json_object:{relative(path)}")
        return {}
    return data


def load_jsonl(path: Path, input_errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        input_errors.append(f"missing_input:{relative(path)}")
        return []

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            input_errors.append(f"invalid_jsonl:{relative(path)}:{line_number}")
            continue
        if not isinstance(row, dict):
            input_errors.append(f"invalid_jsonl_object:{relative(path)}:{line_number}")
            continue
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def index_by_head_benchmark(
    rows: list[dict[str, Any]],
    source_name: str,
    input_errors: list[str],
) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        head = row.get("head")
        benchmark_name = row.get("benchmark_name")
        if not isinstance(head, str) or not isinstance(benchmark_name, str):
            input_errors.append(f"invalid_{source_name}_identity")
            continue
        key = (head, benchmark_name)
        if key in indexed:
            input_errors.append(f"duplicate_{source_name}_row:{head}:{benchmark_name}")
            continue
        indexed[key] = row
    return indexed


def license_ready(status: Any) -> bool:
    value = str(status or "")
    return value.startswith("approved")


def benchmark_gap_requirements(
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

    return {
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
        "cache_validation_valid": validation_valid,
        "cache_validation_errors": validation_errors,
    }


def benchmark_row_status(
    benchmark_name: str,
    plan_row: dict[str, Any] | None,
    validation_row: dict[str, Any] | None,
    manifest_row: dict[str, Any] | None,
) -> dict[str, Any]:
    plan_status = str(plan_row.get("acquisition_status") or "not_planned") if plan_row else "not_planned"
    configured = plan_status == "configured"
    requirements = benchmark_gap_requirements(benchmark_name, plan_row, validation_row, manifest_row)
    validation_valid = requirements["cache_validation_valid"]
    validation_errors = requirements["cache_validation_errors"]

    blockers: list[str] = []
    if not plan_row:
        blockers.append("acquisition_plan_row_missing")
    elif not configured:
        blockers.append(f"acquisition_status:{plan_status}")
    if not validation_row:
        blockers.append("cache_validation_record_missing")
    elif not validation_valid:
        blockers.extend(str(error) for error in validation_errors)

    return {
        "benchmark_name": benchmark_name,
        "acquisition_plan_status": plan_status,
        "acquisition_configured": configured,
        "cache_validation_valid": validation_valid,
        "cache_validation_errors": validation_errors,
        "status": "ready" if configured and validation_valid else "blocked",
        "blockers": blockers,
        **requirements,
    }


def markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Five-Head Benchmark Gap Plan",
        "",
        "## Status",
        "",
        f"- Status: `{report['status']}`",
        f"- Required benchmarks: `{summary['required_benchmarks']}`",
        f"- Acquisition-configured benchmarks: `{summary['configured_benchmarks']}`",
        f"- Cache-validated benchmarks: `{summary['cache_validated_benchmarks']}`",
        f"- Missing cache validation: `{summary['missing_cache_validation_benchmarks']}`",
        f"- Heads with complete scorecards: `{summary['heads_with_complete_scorecards']}/{summary['required_heads']}`",
        f"- Ready for model claim: `{report['ready_for_model_claim']}`",
        f"- Safe for model claim: `{report['safe_for_model_claim']}`",
        f"- Release ready: `{report['release_ready']}`",
        "",
        "## Head Gaps",
        "",
        "| Head | Required | Configured | Cache-valid | Download/cache | License | Human acceptance | Status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for head in report["heads"]:
        lines.append(
            "| {head} | {required} | {configured} | {valid} | {download} | {license} | {acceptance} | {status} |".format(
                head=head["head"],
                required=head["required_benchmarks"],
                configured=head["acquisition_configured_benchmarks"],
                valid=head["cache_validated_benchmarks"],
                download=len(head["benchmarks_requiring_download_or_cache"]),
                license=len(head["benchmarks_requiring_license_authorization"]),
                acceptance=len(head["benchmarks_requiring_human_acceptance"]),
                status=head["status"],
            )
        )

    lines.extend(["", "## Metrics That Cannot Be Declared", ""])
    for row in report["not_claimable_model_metrics"]:
        lines.append(
            f"- `{row['head']}`: {', '.join(row['not_claimable_metrics'])}; "
            f"blockers: {', '.join(row['blocking_reasons']) or 'none'}."
        )

    lines.extend(["", "## Required Follow-Up", ""])
    for action in report["actions"]:
        lines.append(
            f"- `{action['head']}`: download/cache `{len(action['benchmarks_requiring_download_or_cache'])}`, "
            f"license/authorize `{len(action['benchmarks_requiring_license_authorization'])}`, "
            f"human-accept `{len(action['benchmarks_requiring_human_acceptance'])}`; "
            "do not treat this plan as approval or release evidence."
        )

    lines.extend(
        [
            "",
            "## Policy",
            "",
            report["policy"],
            "",
            "Inputs are read-only reports and plan rows. This plan does not download data, approve a benchmark, "
            "run a model, change a manifest, or loosen any claim or release gate.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build fail-closed five-head benchmark gap plan")
    parser.add_argument("--matrix", type=Path, default=MATRIX)
    parser.add_argument("--acquisition-report", type=Path, default=ACQUISITION_REPORT)
    parser.add_argument("--acquisition-plan", type=Path, default=ACQUISITION_PLAN)
    parser.add_argument("--cache-validation", type=Path, default=CACHE_VALIDATION)
    parser.add_argument("--cache-manifest", type=Path, default=CACHE_MANIFEST)
    parser.add_argument("--claim-readiness", type=Path, default=CLAIM_READINESS)
    parser.add_argument("--multitask-readiness", type=Path, default=MULTITASK_READINESS)
    parser.add_argument("--output", type=Path, default=REPORT_OUT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN_OUT)
    parser.add_argument("--actions", type=Path, default=ACTIONS_OUT)
    args = parser.parse_args()

    input_errors: list[str] = []
    matrix = load_json(args.matrix, input_errors)
    acquisition_report = load_json(args.acquisition_report, input_errors)
    acquisition_rows = load_jsonl(args.acquisition_plan, input_errors)
    cache_validation = load_json(args.cache_validation, input_errors)
    cache_manifest = load_json(args.cache_manifest, input_errors)
    claim_readiness = load_json(args.claim_readiness, input_errors)
    multitask_readiness = load_json(args.multitask_readiness, input_errors)

    matrix_heads = matrix.get("heads")
    if not isinstance(matrix_heads, list):
        input_errors.append("matrix_heads_missing_or_invalid")
        matrix_heads = []
    matrix_by_head: dict[str, dict[str, Any]] = {}
    for row in matrix_heads:
        if not isinstance(row, dict) or not isinstance(row.get("head"), str):
            input_errors.append("matrix_head_row_invalid")
            continue
        head = row["head"]
        if head in matrix_by_head:
            input_errors.append(f"duplicate_matrix_head:{head}")
            continue
        matrix_by_head[head] = row

    unexpected_matrix_heads = sorted(set(matrix_by_head) - set(HEADS))
    for head in unexpected_matrix_heads:
        input_errors.append(f"unexpected_matrix_head:{head}")
    for head in HEADS:
        if head not in matrix_by_head:
            input_errors.append(f"missing_matrix_head:{head}")

    plan_by_key = index_by_head_benchmark(acquisition_rows, "acquisition_plan", input_errors)
    validation_records = cache_validation.get("records")
    if not isinstance(validation_records, list):
        input_errors.append("cache_validation_records_missing_or_invalid")
        validation_records = []
    validation_rows = [row for row in validation_records if isinstance(row, dict)]
    if len(validation_rows) != len(validation_records):
        input_errors.append("cache_validation_record_invalid")
    validation_by_key = index_by_head_benchmark(validation_rows, "cache_validation", input_errors)

    manifest_records = cache_manifest.get("rows")
    if not isinstance(manifest_records, list):
        input_errors.append("cache_manifest_rows_missing_or_invalid")
        manifest_records = []
    manifest_rows = [row for row in manifest_records if isinstance(row, dict)]
    if len(manifest_rows) != len(manifest_records):
        input_errors.append("cache_manifest_row_invalid")
    manifest_by_key = index_by_head_benchmark(manifest_rows, "cache_manifest", input_errors)

    multitask_heads = multitask_readiness.get("heads")
    if not isinstance(multitask_heads, dict):
        input_errors.append("multitask_readiness_heads_missing_or_invalid")
        multitask_heads = {}
    blocked_claim_ids = claim_readiness.get("blocked_claim_ids")
    if not isinstance(blocked_claim_ids, list):
        input_errors.append("claim_readiness_blocked_claim_ids_missing_or_invalid")
        blocked_claim_ids = []
    blocked_claim_ids = [str(claim_id) for claim_id in blocked_claim_ids]

    heads: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    not_claimable_model_metrics: list[dict[str, Any]] = []
    total_required = 0
    total_configured = 0
    total_valid = 0
    complete_heads = 0
    error_counts: Counter[str] = Counter()
    requirement_counts: Counter[str] = Counter()

    for head in HEADS:
        matrix_row = matrix_by_head.get(head, {})
        required = matrix_row.get("required_benchmarks")
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            input_errors.append(f"required_benchmarks_missing_or_invalid:{head}")
            required = []
        if len(required) != len(set(required)):
            input_errors.append(f"duplicate_required_benchmark:{head}")

        benchmark_rows = [
            benchmark_row_status(
                benchmark_name,
                plan_by_key.get((head, benchmark_name)),
                validation_by_key.get((head, benchmark_name)),
                manifest_by_key.get((head, benchmark_name)),
            )
            for benchmark_name in required
        ]
        required_count = len(benchmark_rows)
        configured_count = sum(1 for row in benchmark_rows if row["acquisition_configured"])
        valid_count = sum(1 for row in benchmark_rows if row["cache_validation_valid"])
        missing_count = required_count - valid_count
        configured_gap = required_count - configured_count
        plan_gap = sum(1 for row in benchmark_rows if row["acquisition_plan_status"] == "not_planned")
        benchmark_blockers = sorted(
            {blocker for row in benchmark_rows for blocker in row["blockers"]}
        )
        for row in benchmark_rows:
            error_counts.update(row["cache_validation_errors"])
            requirement_counts.update(row["required_operator_actions"])

        complete = (
            required_count > 0
            and plan_gap == 0
            and configured_count == required_count
            and valid_count == required_count
            and not any(row["requires_human_acceptance"] for row in benchmark_rows)
        )
        head_status = "ready" if complete else "blocked"
        head_training = multitask_heads.get(head) if isinstance(multitask_heads.get(head), dict) else {}
        not_claimable_metrics = [] if complete and head_training.get("ready") is True else HEAD_METRIC_CLAIMS[head]
        benchmarks_requiring_download_or_cache = [
            row["benchmark_name"] for row in benchmark_rows if row["requires_download_or_cache"]
        ]
        benchmarks_requiring_license_authorization = [
            row["benchmark_name"] for row in benchmark_rows if row["requires_license_authorization"]
        ]
        benchmarks_requiring_human_acceptance = [
            row["benchmark_name"] for row in benchmark_rows if row["requires_human_acceptance"]
        ]
        benchmarks_requiring_acquisition_configuration = [
            row["benchmark_name"] for row in benchmark_rows if row["requires_acquisition_configuration"]
        ]
        if not_claimable_metrics:
            not_claimable_model_metrics.append(
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
        head_report = {
            "head": head,
            "matrix_status": matrix_row.get("status", "missing"),
            "required_benchmarks": required_count,
            "planned_benchmarks": required_count - plan_gap,
            "acquisition_configured_benchmarks": configured_count,
            "acquisition_configuration_coverage": ratio(configured_count, required_count),
            "cache_validated_benchmarks": valid_count,
            "cache_validation_coverage": ratio(valid_count, required_count),
            "missing_acquisition_plan_benchmarks": plan_gap,
            "missing_acquisition_configuration_benchmarks": configured_gap,
            "missing_cache_validation_benchmarks": missing_count,
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
            "status": head_status,
            "safe_for_model_claim": False,
        }
        heads.append(head_report)
        actions.append(
            {
                "action_id": f"five_head_benchmark_gap::{head}",
                "head": head,
                "priority": "P0",
                "status": "open_blocked",
                "required_benchmarks": required_count,
                "acquisition_configured_benchmarks": configured_count,
                "cache_validated_benchmarks": valid_count,
                "missing_acquisition_configuration_benchmarks": configured_gap,
                "missing_cache_validation_benchmarks": missing_count,
                "missing_benchmarks": [
                    row["benchmark_name"] for row in benchmark_rows if not row["cache_validation_valid"]
                ],
                "benchmarks_requiring_acquisition_configuration": benchmarks_requiring_acquisition_configuration,
                "benchmarks_requiring_download_or_cache": benchmarks_requiring_download_or_cache,
                "benchmarks_requiring_license_authorization": benchmarks_requiring_license_authorization,
                "benchmarks_requiring_human_acceptance": benchmarks_requiring_human_acceptance,
                "not_claimable_metrics": not_claimable_metrics,
                "metric_claim_allowed": False,
                "blocking_reasons": benchmark_blockers,
                "next_action": (
                    "Record only locally available benchmark artifacts through the existing acquisition, "
                    "license-review, leakage-check, scorecard, and cache-validation workflow; require human "
                    "acceptance before any metric claim, then rerun this read-only gap plan."
                ),
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
                "allowed_use": "benchmark evaluation gap planning only",
                "forbidden_use": (
                    "Do not download data, approve a benchmark, treat benchmark data as KWB wet-lab labels, "
                    "run a model claim, or release a model."
                ),
                "safe_for_model_claim": False,
                "release_ready": False,
            }
        )

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
    if not source_report_consistent:
        input_errors.append("source_report_counts_or_readiness_inconsistent")

    benchmark_evaluation_coverage_complete = (
        not input_errors
        and total_required > 0
        and total_configured == total_required
        and total_valid == total_required
        and complete_heads == len(HEADS)
        and source_report_consistent
    )
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "inputs": {
            "benchmark_matrix_report": relative(args.matrix),
            "benchmark_acquisition_plan_report": relative(args.acquisition_report),
            "benchmark_acquisition_plan": relative(args.acquisition_plan),
            "benchmark_score_cache_validation_report": relative(args.cache_validation),
            "benchmark_score_cache_manifest": relative(args.cache_manifest),
            "claim_readiness_matrix": relative(args.claim_readiness),
            "multitask_training_readiness_report": relative(args.multitask_readiness),
        },
        "input_errors": sorted(set(input_errors)),
        "summary": {
            "required_heads": len(HEADS),
            "heads_with_complete_scorecards": complete_heads,
            "required_benchmarks": total_required,
            "planned_benchmarks": sum(head["planned_benchmarks"] for head in heads),
            "configured_benchmarks": total_configured,
            "acquisition_configuration_coverage": ratio(total_configured, total_required),
            "cache_validated_benchmarks": total_valid,
            "cache_validation_coverage": ratio(total_valid, total_required),
            "missing_acquisition_plan_benchmarks": sum(
                head["missing_acquisition_plan_benchmarks"] for head in heads
            ),
            "missing_acquisition_configuration_benchmarks": total_required - total_configured,
            "missing_cache_validation_benchmarks": total_required - total_valid,
            "cache_validation_error_counts": dict(sorted(error_counts.items())),
            "operator_action_counts": dict(sorted(requirement_counts.items())),
            "heads_with_not_claimable_metrics": len(not_claimable_model_metrics),
            "benchmarks_requiring_download_or_cache": sum(
                len(head["benchmarks_requiring_download_or_cache"]) for head in heads
            ),
            "benchmarks_requiring_license_authorization": sum(
                len(head["benchmarks_requiring_license_authorization"]) for head in heads
            ),
            "benchmarks_requiring_human_acceptance": sum(
                len(head["benchmarks_requiring_human_acceptance"]) for head in heads
            ),
            "blocked_claim_ids": blocked_claim_ids,
            "source_report_consistent": source_report_consistent,
            "benchmark_evaluation_coverage_complete": benchmark_evaluation_coverage_complete,
        },
        "heads": heads,
        "not_claimable_model_metrics": not_claimable_model_metrics,
        "actions": actions,
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": POLICY,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.actions, actions)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "required_benchmarks": total_required,
                "cache_validated_benchmarks": total_valid,
                "heads_with_complete_scorecards": complete_heads,
                "ready_for_model_claim": report["ready_for_model_claim"],
                "output": relative(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
