#!/usr/bin/env python3
"""Build fail-closed operator packets for missing benchmark hard gates.

This script is intentionally read-only with respect to benchmark intake,
pipeline, and manifest artifacts. It creates operator packets that describe the
missing local evidence required before any separate benchmark cache intake can
be considered.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GAP_PLAN_REPORT = AI_ROOT / "reports" / "five_head_benchmark_gap_plan_report.json"
CACHE_VALIDATION_REPORT = AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json"
ACQUISITION_PLAN = AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl"
CACHE_MANIFEST = AI_ROOT / "reports" / "benchmark_score_cache_manifest.json"
PACKETS_OUT = AI_ROOT / "datasets" / "governance" / "benchmark_hard_gate_operator_packets.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "benchmark_hard_gate_operator_packet_report.json"
MARKDOWN_OUT = AI_ROOT / "reports" / "benchmark_hard_gate_operator_packets.md"

REQUIRED_GATE_FIELDS = [
    "local_dataset_uri",
    "checksum",
    "license_review_status",
    "leakage_check_status",
    "scorecard_uri",
    "metric_report_uri",
    "human_acceptance_receipt",
]

POLICY = (
    "Fail closed: these packets are operator scaffolds only. They do not download benchmark data, "
    "approve licenses, approve benchmark use, write benchmark_score_cache_intake.local.jsonl, update "
    "benchmark_score_cache_manifest.json, run a safe pipeline, attach a benchmark to model claims, "
    "or grant release readiness."
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


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:72] or "benchmark"


def checksum_from(plan_row: dict[str, Any], manifest_row: dict[str, Any]) -> Any:
    return (
        manifest_row.get("dataset_sha256")
        or manifest_row.get("checksum")
        or plan_row.get("checksum")
    )


def first_present(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return default


def missing_required_fields(packet: dict[str, Any]) -> list[str]:
    missing = []
    for field in REQUIRED_GATE_FIELDS:
        value = packet.get(field)
        if field == "license_review_status":
            if not str(value or "").startswith("approved"):
                missing.append(field)
        elif field == "leakage_check_status":
            if value != "passed":
                missing.append(field)
        elif value in (None, "", False):
            missing.append(field)
    return missing


def is_missing_benchmark(gap_row: dict[str, Any], validation_row: dict[str, Any], manifest_row: dict[str, Any]) -> bool:
    manifest_status = first_present(manifest_row.get("status"), gap_row.get("manifest_status"), default="missing")
    validation_valid = first_present(validation_row.get("valid"), gap_row.get("cache_validation_valid"), default=False)
    validation_errors = validation_row.get("errors") if "errors" in validation_row else gap_row.get("cache_validation_errors")
    if not isinstance(validation_errors, list):
        validation_errors = []
    return manifest_status != "present" or validation_valid is not True or bool(validation_errors)


def build_packets(
    gap_report: dict[str, Any],
    validation_report: dict[str, Any],
    acquisition_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    input_errors: list[str],
) -> list[dict[str, Any]]:
    validation_records = validation_report.get("records")
    if not isinstance(validation_records, list):
        input_errors.append("cache_validation_records_missing_or_invalid")
        validation_records = []
    manifest_rows = manifest.get("rows")
    if not isinstance(manifest_rows, list):
        input_errors.append("cache_manifest_rows_missing_or_invalid")
        manifest_rows = []

    validation_by_key = index_by_head_benchmark(
        [row for row in validation_records if isinstance(row, dict)],
        "cache_validation",
        input_errors,
    )
    manifest_by_key = index_by_head_benchmark(
        [row for row in manifest_rows if isinstance(row, dict)],
        "cache_manifest",
        input_errors,
    )
    plan_by_key = index_by_head_benchmark(acquisition_rows, "acquisition_plan", input_errors)

    packets: list[dict[str, Any]] = []
    heads = gap_report.get("heads")
    if not isinstance(heads, list):
        input_errors.append("gap_report_heads_missing_or_invalid")
        heads = []

    execution_order = 0
    for head_row in heads:
        if not isinstance(head_row, dict):
            input_errors.append("gap_report_head_row_invalid")
            continue
        head = head_row.get("head")
        benchmark_rows = head_row.get("benchmark_rows")
        if not isinstance(head, str) or not isinstance(benchmark_rows, list):
            input_errors.append("gap_report_head_identity_or_rows_invalid")
            continue
        for gap_row in benchmark_rows:
            if not isinstance(gap_row, dict) or not isinstance(gap_row.get("benchmark_name"), str):
                input_errors.append(f"gap_report_benchmark_row_invalid:{head}")
                continue
            benchmark_name = gap_row["benchmark_name"]
            key = (head, benchmark_name)
            plan_row = plan_by_key.get(key, {})
            validation_row = validation_by_key.get(key, {})
            manifest_row = manifest_by_key.get(key, {})
            if not is_missing_benchmark(gap_row, validation_row, manifest_row):
                continue

            execution_order += 1
            checksum = checksum_from(plan_row, manifest_row)
            local_dataset_uri = first_present(
                manifest_row.get("local_dataset_uri"),
                plan_row.get("local_dataset_uri"),
                gap_row.get("local_dataset_uri"),
            )
            license_review_status = first_present(
                manifest_row.get("license_review_status"),
                plan_row.get("license_review_status"),
                gap_row.get("license_review_status"),
                default="not_reviewed",
            )
            leakage_check_status = first_present(
                manifest_row.get("leakage_check_status"),
                plan_row.get("leakage_check_status"),
                gap_row.get("leakage_check_status"),
                default="not_run",
            )
            scorecard_uri = first_present(
                manifest_row.get("scorecard_uri"),
                gap_row.get("scorecard_uri"),
            )
            metric_report_uri = first_present(
                manifest_row.get("metric_report_uri"),
                gap_row.get("metric_report_uri"),
            )
            validation_errors = validation_row.get("errors") if validation_row else gap_row.get("cache_validation_errors")
            if not isinstance(validation_errors, list):
                validation_errors = ["cache_validation_errors_invalid"]

            source_gap_actions = (
                gap_row.get("required_operator_actions")
                if isinstance(gap_row.get("required_operator_actions"), list)
                else []
            )
            packet = {
                "packet_id": f"benchmark-hard-gate-{head}-{slug(benchmark_name)}",
                "execution_order": execution_order,
                "workstream": "benchmark_scorecard_hard_gate",
                "priority": "P0",
                "status": "open_blocked",
                "head": head,
                "benchmark_name": benchmark_name,
                "local_dataset_uri": local_dataset_uri,
                "checksum": checksum,
                "license_review_status": license_review_status,
                "leakage_check_status": leakage_check_status,
                "scorecard_uri": scorecard_uri,
                "metric_report_uri": metric_report_uri,
                "human_acceptance_receipt": None,
                "required_gate_fields": REQUIRED_GATE_FIELDS,
                "required_gate_field_status": {
                    "local_dataset_uri": "present" if local_dataset_uri else "missing",
                    "checksum": "present" if checksum else "missing",
                    "license_review_status": license_review_status,
                    "leakage_check_status": leakage_check_status,
                    "scorecard_uri": "present" if scorecard_uri else "missing",
                    "metric_report_uri": "present" if metric_report_uri else "missing",
                    "human_acceptance_receipt": "missing",
                },
                "acquisition_plan_status": first_present(
                    plan_row.get("acquisition_status"),
                    gap_row.get("acquisition_plan_status"),
                    default="not_planned",
                ),
                "manifest_status": first_present(
                    manifest_row.get("status"),
                    gap_row.get("manifest_status"),
                    default="missing",
                ),
                "cache_validation_valid": bool(
                    first_present(validation_row.get("valid"), gap_row.get("cache_validation_valid"), default=False)
                ),
                "cache_validation_errors": validation_errors,
                "gap_plan_blockers": gap_row.get("blockers") if isinstance(gap_row.get("blockers"), list) else [],
                "source_gap_required_operator_actions": source_gap_actions,
                "required_operator_actions": [
                    "configure_acquisition_plan_row",
                    "register_authorized_local_benchmark_cache",
                    "complete_license_review",
                    "complete_leakage_check",
                    "attach_scorecard_and_metric_report",
                    "record_human_acceptance_receipt",
                    "rerun_benchmark_score_cache_validation",
                ],
                "intake_target_after_all_gates": "datasets/benchmark/benchmark_score_cache_intake.local.jsonl",
                "intake_schema": "contracts/benchmark_score_cache_intake.schema.json",
                "post_gate_validation_command": "python3 scripts/validate_benchmark_score_cache.py",
                "rerun_gap_plan_command": "python3 scripts/build_five_head_benchmark_gap_plan.py",
                "completion_condition": (
                    "Only after a separate reviewed intake row contains the local dataset URI, checksums, "
                    "license review, leakage check, scorecard, metric report, reviewer, reviewed_at, and a "
                    "human acceptance receipt may operators rerun validation and gap planning."
                ),
                "completion_ready": False,
                "requires_human_input": True,
                "model_claim_allowed": False,
                "training_unlocked": False,
                "release_ready": False,
                "safe_for_model_claim": False,
                "download_allowed_by_packet": False,
                "benchmark_approval_granted": False,
                "write_benchmark_score_cache_intake_allowed": False,
                "manifest_update_allowed": False,
                "safe_pipeline_integration_allowed": False,
                "policy": POLICY,
            }
            packet["missing_required_fields"] = missing_required_fields(packet)
            packets.append(packet)

    return packets


def markdown(report: dict[str, Any], packets: list[dict[str, Any]]) -> str:
    summary = report["summary"]
    lines = [
        "# Benchmark Hard-Gate Operator Packets",
        "",
        "## Status",
        "",
        f"- Status: `{report['status']}`",
        f"- Missing benchmark packets: `{summary['packet_rows']}`",
        f"- Heads covered: `{summary['heads_with_packets']}`",
        f"- Packets missing local dataset URI: `{summary['missing_local_dataset_uri_rows']}`",
        f"- Packets missing checksum: `{summary['missing_checksum_rows']}`",
        f"- Packets missing license review: `{summary['license_not_approved_rows']}`",
        f"- Packets missing leakage check: `{summary['leakage_not_passed_rows']}`",
        f"- Packets missing scorecard: `{summary['missing_scorecard_uri_rows']}`",
        f"- Packets missing metric report: `{summary['missing_metric_report_uri_rows']}`",
        f"- Packets missing human acceptance: `{summary['missing_human_acceptance_receipt_rows']}`",
        f"- Safe pipeline integration allowed: `{report['safe_pipeline_integration_allowed']}`",
        f"- Manifest update allowed: `{report['manifest_update_allowed']}`",
        f"- Intake write allowed: `{report['write_benchmark_score_cache_intake_allowed']}`",
        "",
        "## Packets",
        "",
        "| Order | Head | Benchmark | local_dataset_uri | checksum | license | leakage | scorecard | metric report | human receipt |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for packet in packets:
        lines.append(
            "| {order} | {head} | {benchmark} | {dataset} | {checksum} | {license} | {leakage} | {scorecard} | {metric} | {receipt} |".format(
                order=packet["execution_order"],
                head=packet["head"],
                benchmark=packet["benchmark_name"],
                dataset="present" if packet["local_dataset_uri"] else "missing",
                checksum="present" if packet["checksum"] else "missing",
                license=packet["license_review_status"],
                leakage=packet["leakage_check_status"],
                scorecard="present" if packet["scorecard_uri"] else "missing",
                metric="present" if packet["metric_report_uri"] else "missing",
                receipt="present" if packet["human_acceptance_receipt"] else "missing",
            )
        )

    lines.extend(
        [
            "",
            "## Fail-Closed Policy",
            "",
            report["policy"],
            "",
            "Generated packets are not benchmark-score-cache intake rows and are not safe-pipeline or manifest inputs.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build fail-closed benchmark hard-gate operator packets")
    parser.add_argument("--gap-plan-report", type=Path, default=GAP_PLAN_REPORT)
    parser.add_argument("--cache-validation-report", type=Path, default=CACHE_VALIDATION_REPORT)
    parser.add_argument("--acquisition-plan", type=Path, default=ACQUISITION_PLAN)
    parser.add_argument("--cache-manifest", type=Path, default=CACHE_MANIFEST)
    parser.add_argument("--packets", type=Path, default=PACKETS_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN_OUT)
    args = parser.parse_args()

    input_errors: list[str] = []
    gap_report = load_json(args.gap_plan_report, input_errors)
    validation_report = load_json(args.cache_validation_report, input_errors)
    acquisition_rows = load_jsonl(args.acquisition_plan, input_errors)
    manifest = load_json(args.cache_manifest, input_errors)

    packets = build_packets(gap_report, validation_report, acquisition_rows, manifest, input_errors)
    head_counts = Counter(packet["head"] for packet in packets)
    missing_field_counts: Counter[str] = Counter(
        field for packet in packets for field in packet["missing_required_fields"]
    )
    license_not_approved = sum(
        1 for packet in packets if not str(packet["license_review_status"]).startswith("approved")
    )
    leakage_not_passed = sum(1 for packet in packets if packet["leakage_check_status"] != "passed")

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "inputs": {
            "five_head_benchmark_gap_plan_report": relative(args.gap_plan_report),
            "benchmark_score_cache_validation_report": relative(args.cache_validation_report),
            "benchmark_acquisition_plan": relative(args.acquisition_plan),
            "benchmark_score_cache_manifest": relative(args.cache_manifest),
        },
        "outputs": {
            "packets": relative(args.packets),
            "report": relative(args.report),
            "markdown": relative(args.markdown),
        },
        "input_errors": sorted(set(input_errors)),
        "summary": {
            "packet_rows": len(packets),
            "heads_with_packets": len(head_counts),
            "packets_by_head": dict(sorted(head_counts.items())),
            "missing_local_dataset_uri_rows": missing_field_counts.get("local_dataset_uri", 0),
            "missing_checksum_rows": missing_field_counts.get("checksum", 0),
            "license_not_approved_rows": license_not_approved,
            "leakage_not_passed_rows": leakage_not_passed,
            "missing_scorecard_uri_rows": missing_field_counts.get("scorecard_uri", 0),
            "missing_metric_report_uri_rows": missing_field_counts.get("metric_report_uri", 0),
            "missing_human_acceptance_receipt_rows": missing_field_counts.get("human_acceptance_receipt", 0),
            "completion_ready_rows": sum(1 for packet in packets if packet["completion_ready"]),
            "requires_human_input_rows": sum(1 for packet in packets if packet["requires_human_input"]),
        },
        "packet_ids": [packet["packet_id"] for packet in packets],
        "forbidden_outputs": [
            "datasets/benchmark/benchmark_score_cache_intake.local.jsonl",
            "reports/benchmark_score_cache_manifest.json",
            "safe training or safe pipeline manifests",
        ],
        "download_allowed_by_packet": False,
        "benchmark_approval_granted": False,
        "write_benchmark_score_cache_intake_allowed": False,
        "manifest_update_allowed": False,
        "safe_pipeline_integration_allowed": False,
        "model_claim_allowed": False,
        "training_unlocked": False,
        "release_ready": False,
        "safe_for_model_claim": False,
        "policy": POLICY,
    }

    write_jsonl(args.packets, packets)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown(report, packets), encoding="utf-8")

    print(
        json.dumps(
            {
                "packet_rows": len(packets),
                "heads_with_packets": report["summary"]["heads_with_packets"],
                "completion_ready_rows": report["summary"]["completion_ready_rows"],
                "write_benchmark_score_cache_intake_allowed": False,
                "safe_pipeline_integration_allowed": False,
                "output": str(args.report),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
