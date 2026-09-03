#!/usr/bin/env python3
"""Validate fail-closed benchmark hard-gate operator packets."""

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
PACKETS = AI_ROOT / "datasets" / "governance" / "benchmark_hard_gate_operator_packets.jsonl"
PACKET_REPORT = AI_ROOT / "reports" / "benchmark_hard_gate_operator_packet_report.json"
MARKDOWN = AI_ROOT / "reports" / "benchmark_hard_gate_operator_packets.md"
OUTPUT = AI_ROOT / "reports" / "benchmark_hard_gate_operator_packet_validation_report.json"

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

FAIL_CLOSED_FALSE_FIELDS = [
    "download_allowed_by_packet",
    "benchmark_approval_granted",
    "write_benchmark_score_cache_intake_allowed",
    "manifest_update_allowed",
    "safe_pipeline_integration_allowed",
    "model_claim_allowed",
    "training_unlocked",
    "release_ready",
    "safe_for_model_claim",
]


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:72] or "benchmark"


def check(condition: bool, failures: list[dict[str, Any]], name: str, observed: Any, expected: Any) -> None:
    if not condition:
        failures.append({"check": name, "observed": observed, "expected": expected})


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
            failures.append({"check": f"{label}_valid_jsonl", "line": line_number, "observed": str(exc), "expected": "JSON object"})
            continue
        if not isinstance(value, dict):
            failures.append({"check": f"{label}_jsonl_object", "line": line_number, "observed": type(value).__name__, "expected": "object"})
            continue
        rows.append(value)
    return rows


def read_text(path: Path, failures: list[dict[str, Any]], label: str) -> str:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return ""
    return path.read_text(encoding="utf-8")


def index_by_key(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row.get("head")), str(row.get("benchmark_name"))): row
        for row in rows
        if isinstance(row.get("head"), str) and isinstance(row.get("benchmark_name"), str)
    }


def first_present(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return default


def checksum_from(plan_row: dict[str, Any], manifest_row: dict[str, Any]) -> Any:
    return manifest_row.get("dataset_sha256") or manifest_row.get("checksum") or plan_row.get("checksum")


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


def gap_plan_rows(gap_report: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for head_row in gap_report.get("heads") or []:
        if not isinstance(head_row, dict) or not isinstance(head_row.get("head"), str):
            continue
        head = head_row["head"]
        for gap_row in head_row.get("benchmark_rows") or []:
            if isinstance(gap_row, dict) and isinstance(gap_row.get("benchmark_name"), str):
                rows.append((head, gap_row))
    return rows


def expected_packets(
    gap_report: dict[str, Any],
    validation_report: dict[str, Any],
    acquisition_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    validation_by_key = index_by_key([row for row in validation_report.get("records") or [] if isinstance(row, dict)])
    manifest_by_key = index_by_key([row for row in manifest.get("rows") or [] if isinstance(row, dict)])
    plan_by_key = index_by_key(acquisition_rows)
    packets: list[dict[str, Any]] = []
    execution_order = 0
    for head, gap_row in gap_plan_rows(gap_report):
        benchmark_name = gap_row["benchmark_name"]
        key = (head, benchmark_name)
        plan_row = plan_by_key.get(key, {})
        validation_row = validation_by_key.get(key, {})
        manifest_row = manifest_by_key.get(key, {})
        if not is_missing_benchmark(gap_row, validation_row, manifest_row):
            continue
        execution_order += 1
        checksum = checksum_from(plan_row, manifest_row)
        local_dataset_uri = first_present(manifest_row.get("local_dataset_uri"), plan_row.get("local_dataset_uri"), gap_row.get("local_dataset_uri"))
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
        scorecard_uri = first_present(manifest_row.get("scorecard_uri"), gap_row.get("scorecard_uri"))
        metric_report_uri = first_present(manifest_row.get("metric_report_uri"), gap_row.get("metric_report_uri"))
        validation_errors = validation_row.get("errors") if validation_row else gap_row.get("cache_validation_errors")
        if not isinstance(validation_errors, list):
            validation_errors = ["cache_validation_errors_invalid"]
        source_gap_actions = gap_row.get("required_operator_actions") if isinstance(gap_row.get("required_operator_actions"), list) else []
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
            "acquisition_plan_status": first_present(plan_row.get("acquisition_status"), gap_row.get("acquisition_plan_status"), default="not_planned"),
            "manifest_status": first_present(manifest_row.get("status"), gap_row.get("manifest_status"), default="missing"),
            "cache_validation_valid": bool(first_present(validation_row.get("valid"), gap_row.get("cache_validation_valid"), default=False)),
            "cache_validation_errors": validation_errors,
            "gap_plan_blockers": gap_row.get("blockers") if isinstance(gap_row.get("blockers"), list) else [],
            "source_gap_required_operator_actions": source_gap_actions,
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


def expected_summary(packets: list[dict[str, Any]]) -> dict[str, Any]:
    head_counts = Counter(packet["head"] for packet in packets)
    missing_field_counts: Counter[str] = Counter(field for packet in packets for field in packet["missing_required_fields"])
    return {
        "packet_rows": len(packets),
        "heads_with_packets": len(head_counts),
        "packets_by_head": dict(sorted(head_counts.items())),
        "missing_local_dataset_uri_rows": missing_field_counts.get("local_dataset_uri", 0),
        "missing_checksum_rows": missing_field_counts.get("checksum", 0),
        "license_not_approved_rows": sum(1 for packet in packets if not str(packet["license_review_status"]).startswith("approved")),
        "leakage_not_passed_rows": sum(1 for packet in packets if packet["leakage_check_status"] != "passed"),
        "missing_scorecard_uri_rows": missing_field_counts.get("scorecard_uri", 0),
        "missing_metric_report_uri_rows": missing_field_counts.get("metric_report_uri", 0),
        "missing_human_acceptance_receipt_rows": missing_field_counts.get("human_acceptance_receipt", 0),
        "completion_ready_rows": sum(1 for packet in packets if packet["completion_ready"]),
        "requires_human_input_rows": sum(1 for packet in packets if packet["requires_human_input"]),
    }


def expected_markdown(report: dict[str, Any], packets: list[dict[str, Any]]) -> str:
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
    lines.extend(["", "## Fail-Closed Policy", "", report["policy"], "", "Generated packets are not benchmark-score-cache intake rows and are not safe-pipeline or manifest inputs.", ""])
    return "\n".join(lines)


def comparable_packet(packet: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "packet_id",
        "execution_order",
        "workstream",
        "priority",
        "status",
        "head",
        "benchmark_name",
        "local_dataset_uri",
        "checksum",
        "license_review_status",
        "leakage_check_status",
        "scorecard_uri",
        "metric_report_uri",
        "human_acceptance_receipt",
        "required_gate_fields",
        "required_gate_field_status",
        "acquisition_plan_status",
        "manifest_status",
        "cache_validation_valid",
        "cache_validation_errors",
        "gap_plan_blockers",
        "source_gap_required_operator_actions",
        "completion_ready",
        "requires_human_input",
        *FAIL_CLOSED_FALSE_FIELDS,
        "missing_required_fields",
        "policy",
    ]
    return {field: packet.get(field) for field in fields}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark hard-gate operator packets")
    parser.add_argument("--gap-plan-report", type=Path, default=GAP_PLAN_REPORT)
    parser.add_argument("--cache-validation-report", type=Path, default=CACHE_VALIDATION_REPORT)
    parser.add_argument("--acquisition-plan", type=Path, default=ACQUISITION_PLAN)
    parser.add_argument("--cache-manifest", type=Path, default=CACHE_MANIFEST)
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--packet-report", type=Path, default=PACKET_REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    gap_report = load_json(args.gap_plan_report, failures, "gap_plan_report")
    validation_report = load_json(args.cache_validation_report, failures, "cache_validation_report")
    acquisition_rows = load_jsonl(args.acquisition_plan, failures, "acquisition_plan")
    manifest = load_json(args.cache_manifest, failures, "cache_manifest")
    packets = load_jsonl(args.packets, failures, "packets")
    report = load_json(args.packet_report, failures, "packet_report")
    markdown_text = read_text(args.markdown, failures, "markdown")

    expected = expected_packets(gap_report, validation_report, acquisition_rows, manifest)
    observed_cmp = [comparable_packet(packet) for packet in packets]
    expected_cmp = [comparable_packet(packet) for packet in expected]
    check(observed_cmp == expected_cmp, failures, "packets_match_current_sources", observed_cmp, expected_cmp)

    summary = expected_summary(expected)
    expected_inputs = {
        "five_head_benchmark_gap_plan_report": relative(args.gap_plan_report),
        "benchmark_score_cache_validation_report": relative(args.cache_validation_report),
        "benchmark_acquisition_plan": relative(args.acquisition_plan),
        "benchmark_score_cache_manifest": relative(args.cache_manifest),
    }
    expected_outputs = {"packets": relative(args.packets), "report": relative(args.packet_report), "markdown": relative(args.markdown)}
    check(report.get("local_only") is True, failures, "report_local_only", report.get("local_only"), True)
    check(report.get("status") == "blocked", failures, "report_status_blocked", report.get("status"), "blocked")
    check(report.get("inputs") == expected_inputs, failures, "report_inputs_match", report.get("inputs"), expected_inputs)
    check(report.get("outputs") == expected_outputs, failures, "report_outputs_match", report.get("outputs"), expected_outputs)
    check(report.get("input_errors") == [], failures, "report_input_errors_empty", report.get("input_errors"), [])
    check(report.get("summary") == summary, failures, "report_summary_matches_packets", report.get("summary"), summary)
    check(report.get("packet_ids") == [packet["packet_id"] for packet in expected], failures, "report_packet_ids_match_packets", report.get("packet_ids"), [packet["packet_id"] for packet in expected])
    for field in FAIL_CLOSED_FALSE_FIELDS:
        check(report.get(field) is False, failures, f"report_{field}_false", report.get(field), False)
    check(report.get("policy") == POLICY, failures, "report_policy", report.get("policy"), POLICY)

    expected_report_for_markdown = {"status": "blocked", "summary": summary, "policy": POLICY, **{field: False for field in FAIL_CLOSED_FALSE_FIELDS}}
    markdown_matches = markdown_text == expected_markdown(expected_report_for_markdown, expected)
    check(markdown_matches, failures, "markdown_matches_current_packets", markdown_text, expected_markdown(expected_report_for_markdown, expected))

    packet_rows = len(packets)
    completion_ready_rows = sum(1 for packet in packets if packet.get("completion_ready") is True)
    validation_report_out = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "contract_valid": not failures,
        "status": "blocked",
        "packet_rows": packet_rows,
        "expected_packet_rows": len(expected),
        "completion_ready_rows": completion_ready_rows,
        "report_summary_matches_packets": report.get("summary") == summary,
        "markdown_matches_current_packets": markdown_matches,
        "failure_count": len(failures),
        "failures": failures[:500],
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "write_benchmark_score_cache_intake_allowed": False,
        "manifest_update_allowed": False,
        "safe_pipeline_integration_allowed": False,
        "policy": "Validation only. Passing means the benchmark hard-gate packets are current and fail-closed, not approved.",
        "inputs": expected_inputs,
        "packets": relative(args.packets),
        "packet_report": relative(args.packet_report),
        "markdown": relative(args.markdown),
        "output": relative(args.output),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation_report_out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "contract_valid": validation_report_out["contract_valid"],
        "packet_rows": packet_rows,
        "expected_packet_rows": len(expected),
        "completion_ready_rows": completion_ready_rows,
        "failure_count": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
