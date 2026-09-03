#!/usr/bin/env python3
"""Validate benchmark readiness packets without opening any downstream gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKETS = AI_ROOT / "datasets" / "governance" / "benchmark_readiness_packets.jsonl"
DEFAULT_PACKET_REPORT = AI_ROOT / "reports" / "benchmark_readiness_packet_report.json"
DEFAULT_MARKDOWN = AI_ROOT / "reports" / "benchmark_readiness_packets.md"
DEFAULT_REPORT = AI_ROOT / "reports" / "benchmark_readiness_packet_validation_report.json"

HEAD_ORDER = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)

INPUTS = {
    "benchmark_matrix_report": AI_ROOT / "reports" / "benchmark_matrix_report.json",
    "benchmark_acquisition_plan": AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl",
    "benchmark_score_cache_manifest": AI_ROOT / "reports" / "benchmark_score_cache_manifest.json",
    "benchmark_score_cache_intake_report": AI_ROOT / "reports" / "benchmark_score_cache_intake_report.json",
    "benchmark_score_cache_validation_report": AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json",
    "benchmark_coverage_dashboard": AI_ROOT / "reports" / "benchmark_coverage_dashboard.json",
    "benchmark_gap_queue": AI_ROOT / "datasets" / "benchmark" / "benchmark_gap_queue.jsonl",
    "five_head_benchmark_gap_actions": AI_ROOT / "datasets" / "governance" / "five_head_benchmark_gap_actions.jsonl",
    "five_head_benchmark_gap_plan_report": AI_ROOT / "reports" / "five_head_benchmark_gap_plan_report.json",
    "benchmark_score_cache_intake": AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl",
}

REQUIRED_CACHE_ARTIFACTS = (
    "local_dataset_uri",
    "dataset_sha256",
    "split_definition_uri",
    "split_sha256",
    "scorecard_uri",
    "scorecard_sha256",
    "metric_report_uri",
    "metric_sha256",
)

POLICY = (
    "Validation is fail-closed. A structurally valid blocked packet is an honest local "
    "readiness result, not a benchmark approval. --require-ready exits non-zero until every "
    "packet has all receipts and upstream cache/coverage gates are valid."
)

PACKET_POLICY = (
    "Benchmark readiness packet only. It is a local execution contract for resolving an "
    "invalid benchmark gap. It does not download data, accept licenses, write score-cache "
    "intake, update a manifest, create scores, open model claims, change training labels, "
    "change release flags, or grant release readiness."
)


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text[:80] or "benchmark"


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


def index_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row.get("head")), str(row.get("benchmark_name"))): row
        for row in rows
        if isinstance(row.get("head"), str) and isinstance(row.get("benchmark_name"), str)
    }


def matrix_keys(matrix: dict[str, Any]) -> list[tuple[str, str]]:
    keys = []
    for head_row in matrix.get("heads") or []:
        if not isinstance(head_row, dict):
            continue
        head = head_row.get("head")
        for benchmark_name in head_row.get("required_benchmarks") or []:
            if isinstance(head, str) and isinstance(benchmark_name, str):
                keys.append((head, benchmark_name))
    return keys


def coverage_keys(dashboard: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for head_row in dashboard.get("heads") or []:
        if not isinstance(head_row, dict):
            continue
        head = head_row.get("head")
        for benchmark_name in head_row.get("missing_benchmarks") or []:
            if isinstance(head, str) and isinstance(benchmark_name, str):
                keys.add((head, benchmark_name))
    return keys


def gap_queue_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for head_row in rows:
        head = head_row.get("head")
        for item in head_row.get("benchmark_gap_items") or []:
            if isinstance(head, str) and isinstance(item, dict) and isinstance(item.get("benchmark_name"), str):
                indexed[(head, item["benchmark_name"])] = item
    return indexed


def gap_plan_index(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for head_row in report.get("heads") or []:
        if not isinstance(head_row, dict):
            continue
        head = head_row.get("head")
        for item in head_row.get("benchmark_rows") or []:
            if isinstance(head, str) and isinstance(item, dict) and isinstance(item.get("benchmark_name"), str):
                indexed[(head, item["benchmark_name"])] = item
    return indexed


def source_discrepancies(
    dashboard: dict[str, Any],
    action_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage_by_head = {
        str(row.get("head")): list(row.get("missing_benchmarks") or [])
        for row in dashboard.get("heads") or []
        if isinstance(row, dict) and isinstance(row.get("head"), str)
    }
    actions_by_head = {
        str(row.get("head")): row
        for row in action_rows
        if isinstance(row.get("head"), str)
    }
    discrepancies = []
    for head in HEAD_ORDER:
        expected = coverage_by_head.get(head, [])
        observed = list(actions_by_head.get(head, {}).get("missing_benchmarks") or [])
        if observed != expected:
            discrepancies.append({
                "head": head,
                "authoritative_missing_benchmarks": expected,
                "gap_action_missing_benchmarks": observed,
                "reason": "gap action summary does not match current coverage dashboard",
            })
    return discrepancies


def source_snapshot() -> list[dict[str, Any]]:
    snapshot = []
    for name, path in INPUTS.items():
        exists = path.exists()
        snapshot.append({
            "name": name,
            "path": relative(path),
            "exists": exists,
            "sha256": sha256(path) if exists and path.is_file() else "",
            "size_bytes": path.stat().st_size if exists and path.is_file() else None,
        })
    return snapshot


def check(condition: bool, failures: list[dict[str, Any]], name: str, observed: Any, expected: Any) -> None:
    if not condition:
        failures.append({"check": name, "observed": observed, "expected": expected})


def read_text(path: Path, failures: list[dict[str, Any]], label: str) -> str:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return ""
    return path.read_text(encoding="utf-8")


def expected_packet_summary(packets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "packet_rows": len(packets),
        "invalid_gap_rows": sum(
            1
            for packet in packets
            if ((packet.get("current_observation") or {}).get("cache_validation") or {}).get("valid") is False
        ),
        "local_contract_only_rows": sum(
            1
            for packet in packets
            if (packet.get("acquisition_receipt") or {}).get("acquisition_mode") == "local_contract_only"
        ),
        "external_source_required_rows": sum(
            1
            for packet in packets
            if (packet.get("acquisition_receipt") or {}).get("acquisition_mode") == "external_source_required"
        ),
        "completion_ready_rows": sum(1 for packet in packets if packet.get("completion_ready") is True),
        "score_values_recorded": sum(
            1
            for packet in packets
            if (packet.get("score_receipt") or {}).get("score_values") not in (None, {})
            or (packet.get("score_receipt") or {}).get("metric_values") not in (None, {})
        ),
        "packets_by_head": dict(Counter(str(packet.get("head")) for packet in packets if isinstance(packet.get("head"), str))),
    }


def expected_markdown(summary: dict[str, Any], source_discrepancies_count: int, packets: list[dict[str, Any]]) -> str:
    lines = [
        "# Benchmark Readiness Packets",
        "",
        "## Status",
        "",
        f"- Packet rows: `{summary['packet_rows']}`",
        f"- Invalid gaps represented: `{summary['invalid_gap_rows']}`",
        f"- Local-contract-only rows: `{summary['local_contract_only_rows']}`",
        f"- External-source-required rows: `{summary['external_source_required_rows']}`",
        f"- Completion-ready rows: `{summary['completion_ready_rows']}`",
        f"- Score values recorded: `{summary['score_values_recorded']}`",
        f"- Source discrepancy notes: `{source_discrepancies_count}`",
        "- Model claims, training labels, release flags, and existing score-cache artifacts were not modified by packet generation.",
        "",
        "## Packet Matrix",
        "",
        "| Order | Head | Benchmark | Acquisition | Download executed | Current cache validation | Candidate | Completion |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for packet in packets:
        observation = packet.get("current_observation") or {}
        acquisition = packet.get("acquisition_receipt") or {}
        candidate = observation.get("intake_candidate")
        cache_validation = observation.get("cache_validation") or {}
        lines.append(
            "| {order} | {head} | {benchmark} | {mode} | {download} | {validation} | {candidate} | {completion} |".format(
                order=packet.get("execution_order"),
                head=packet.get("head"),
                benchmark=packet.get("benchmark_name"),
                mode=acquisition.get("acquisition_mode"),
                download=acquisition.get("download_executed"),
                validation=cache_validation.get("valid"),
                candidate="rejected" if candidate else "none",
                completion=packet.get("completion_ready"),
            )
        )
    lines.extend(
        [
            "",
            "## Execution Order",
            "",
            "1. Resolve the acquisition receipt using only authorized local source evidence or a separately approved local source.",
            "2. Resolve the score receipt with real dataset/split/scorecard/metric artifacts and SHA-256 values.",
            "3. Run the existing cache, coverage, and this packet validator; regenerate the packet after source reports change.",
            "",
            "## Fail-Closed Policy",
            "",
            PACKET_POLICY,
            "",
        ]
    )
    return "\n".join(lines)


def validate_packet_report_and_markdown(
    packet_report: dict[str, Any],
    markdown_text: str,
    packets: list[dict[str, Any]],
    args: argparse.Namespace,
    current_snapshot: list[dict[str, Any]],
    discrepancies: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> tuple[dict[str, Any], bool, bool]:
    expected_summary = expected_packet_summary(packets)
    missing_source_inputs = [item["name"] for item in current_snapshot if not item["exists"]]
    expected_outputs = {
        "packets": relative(args.packets),
        "report": relative(args.packet_report),
        "markdown": relative(args.markdown),
    }
    expected_inputs = {name: relative(path) for name, path in INPUTS.items()}
    expected_packet_ids = [packet.get("packet_id") for packet in packets]

    check(packet_report.get("local_only") is True, failures, "packet_report_local_only", packet_report.get("local_only"), True)
    check(packet_report.get("status") == "blocked", failures, "packet_report_status_blocked", packet_report.get("status"), "blocked")
    check(packet_report.get("inputs") == expected_inputs, failures, "packet_report_inputs_match_current_contract", packet_report.get("inputs"), expected_inputs)
    check(packet_report.get("outputs") == expected_outputs, failures, "packet_report_outputs_match_current_paths", packet_report.get("outputs"), expected_outputs)
    check(packet_report.get("source_input_missing") == missing_source_inputs, failures, "packet_report_missing_inputs_match_current_sources", packet_report.get("source_input_missing"), missing_source_inputs)
    check(packet_report.get("source_discrepancies") == discrepancies, failures, "packet_report_source_discrepancies_match_current_sources", packet_report.get("source_discrepancies"), discrepancies)
    check(packet_report.get("summary") == expected_summary, failures, "packet_report_summary_matches_current_packets", packet_report.get("summary"), expected_summary)
    check(packet_report.get("packet_ids") == expected_packet_ids, failures, "packet_report_packet_ids_match_jsonl", packet_report.get("packet_ids"), expected_packet_ids)
    for key in ("ready_for_model_claim", "safe_for_model_claim", "release_ready", "training_labels_modified", "release_flags_modified", "write_benchmark_score_cache_intake_allowed", "manifest_update_allowed"):
        check(packet_report.get(key) is False, failures, f"packet_report_{key}_false", packet_report.get(key), False)
    check(packet_report.get("policy") == PACKET_POLICY, failures, "packet_report_policy", packet_report.get("policy"), PACKET_POLICY)

    expected_md = expected_markdown(expected_summary, len(discrepancies), packets)
    markdown_matches = markdown_text == expected_md
    check(markdown_matches, failures, "packet_markdown_matches_current_packets", markdown_text, expected_md)
    return expected_summary, packet_report.get("summary") == expected_summary, markdown_matches


def validate_evidence(
    packet: dict[str, Any],
    failures: list[dict[str, Any]],
    packet_id: str,
) -> None:
    acquisition = packet.get("acquisition_receipt")
    if not isinstance(acquisition, dict):
        failures.append({"check": f"{packet_id}:acquisition_receipt_object", "observed": type(acquisition).__name__, "expected": "object"})
        return
    for item in acquisition.get("source_evidence") or []:
        if not isinstance(item, dict):
            failures.append({"check": f"{packet_id}:source_evidence_object", "observed": type(item).__name__, "expected": "object"})
            continue
        path_value = item.get("path")
        path = AI_ROOT / str(path_value) if path_value else None
        exists = bool(path and path.exists())
        check(exists == (item.get("exists") is True), failures, f"{packet_id}:source_evidence_exists:{path_value}", exists, item.get("exists") is True)
        if exists and path and path.is_file():
            actual = sha256(path)
            check(actual == str(item.get("sha256") or "").lower(), failures, f"{packet_id}:source_evidence_sha256:{path_value}", actual, item.get("sha256"))


def validate_packet(
    packet: dict[str, Any],
    expected_key: tuple[str, str],
    current_snapshot: list[dict[str, Any]],
    matrix_by_key: dict[tuple[str, str], dict[str, Any]],
    plan_by_key: dict[tuple[str, str], dict[str, Any]],
    manifest_by_key: dict[tuple[str, str], dict[str, Any]],
    validation_by_key: dict[tuple[str, str], dict[str, Any]],
    coverage_key_set: set[tuple[str, str]],
    queue_by_key: dict[tuple[str, str], dict[str, Any]],
    gap_plan_by_key: dict[tuple[str, str], dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    head, benchmark_name = expected_key
    packet_id = str(packet.get("packet_id") or f"{head}:{benchmark_name}")
    prefix = f"packet:{packet_id}"
    expected_packet_id = f"benchmark-readiness-{head}-{slug(benchmark_name)}"
    check(packet.get("schema_version") == "1.0.0", failures, f"{prefix}:schema_version", packet.get("schema_version"), "1.0.0")
    check(packet.get("packet_id") == expected_packet_id, failures, f"{prefix}:packet_id", packet.get("packet_id"), expected_packet_id)
    check(packet.get("head") == head, failures, f"{prefix}:head", packet.get("head"), head)
    check(packet.get("benchmark_name") == benchmark_name, failures, f"{prefix}:benchmark_name", packet.get("benchmark_name"), benchmark_name)
    check(packet.get("status") == "blocked", failures, f"{prefix}:status", packet.get("status"), "blocked")
    check(packet.get("completion_ready") is False, failures, f"{prefix}:completion_ready_false", packet.get("completion_ready"), False)
    check(packet.get("requires_human_input") is True, failures, f"{prefix}:requires_human_input", packet.get("requires_human_input"), True)
    for key in ("safe_for_training_import", "benchmark_metric_claim_allowed", "safe_for_model_claim", "release_ready", "write_benchmark_score_cache_intake_allowed", "manifest_update_allowed", "model_claim_allowed", "training_labels_modified", "release_flags_modified"):
        check(packet.get(key) is False, failures, f"{prefix}:{key}_false", packet.get(key), False)

    snapshot = packet.get("source_snapshot")
    check(isinstance(snapshot, dict), failures, f"{prefix}:source_snapshot_object", type(snapshot).__name__, "object")
    packet_inputs = snapshot.get("inputs") if isinstance(snapshot, dict) else None
    check(packet_inputs == current_snapshot, failures, f"{prefix}:source_snapshot_current", packet_inputs, current_snapshot)

    observation = packet.get("current_observation")
    check(isinstance(observation, dict), failures, f"{prefix}:current_observation_object", type(observation).__name__, "object")
    if isinstance(observation, dict):
        matrix = matrix_by_key.get(expected_key, {})
        plan = plan_by_key.get(expected_key, {})
        manifest = manifest_by_key.get(expected_key, {})
        validation = validation_by_key.get(expected_key, {})
        validation_errors = validation.get("errors")
        if not isinstance(validation_errors, list):
            validation_errors = ["cache_validation_record_missing"]
        observed_matrix = observation.get("matrix") or {}
        check(observed_matrix.get("head") == head, failures, f"{prefix}:matrix_head", observed_matrix.get("head"), head)
        check(observed_matrix.get("benchmark_name") == benchmark_name, failures, f"{prefix}:matrix_benchmark_name", observed_matrix.get("benchmark_name"), benchmark_name)
        check(observed_matrix.get("benchmark_data_ready") is (matrix.get("benchmark_data_ready") is True), failures, f"{prefix}:matrix_benchmark_data_ready", observed_matrix.get("benchmark_data_ready"), matrix.get("benchmark_data_ready") is True)
        check(observed_matrix.get("scorecard_ready") is (matrix.get("scorecard_ready") is True), failures, f"{prefix}:matrix_scorecard_ready", observed_matrix.get("scorecard_ready"), matrix.get("scorecard_ready") is True)
        observed_acquisition = observation.get("acquisition") or {}
        for field in ("acquisition_status", "license_review_status", "local_dataset_uri", "checksum", "split_strategy", "leakage_check_status", "scorecard_status"):
            check(observed_acquisition.get(field) == plan.get(field), failures, f"{prefix}:acquisition_{field}", observed_acquisition.get(field), plan.get(field))
        observed_manifest = observation.get("manifest") or {}
        for field in ("status", "dataset_version", "local_dataset_uri", "dataset_sha256", "split_definition_uri", "split_sha256", "scorecard_uri", "scorecard_sha256", "metric_report_uri", "metric_sha256", "leakage_check_status"):
            check(observed_manifest.get(field) == manifest.get(field), failures, f"{prefix}:manifest_{field}", observed_manifest.get(field), manifest.get(field))
        observed_validation = observation.get("cache_validation") or {}
        expected_valid = validation.get("valid") is True and not validation_errors
        check(observed_validation.get("valid") is expected_valid, failures, f"{prefix}:cache_validation_valid", observed_validation.get("valid"), expected_valid)
        check(observed_validation.get("errors") == [str(error) for error in validation_errors], failures, f"{prefix}:cache_validation_errors", observed_validation.get("errors"), validation_errors)

    check(expected_key in coverage_key_set, failures, f"{prefix}:current_coverage_gap", expected_key in coverage_key_set, True)
    queue_item = queue_by_key.get(expected_key)
    coverage_gap = (observation or {}).get("coverage_gap") if isinstance(observation, dict) else {}
    check(coverage_gap.get("gap_id") == (queue_item or {}).get("gap_id"), failures, f"{prefix}:gap_id_matches_queue", coverage_gap.get("gap_id"), (queue_item or {}).get("gap_id"))
    if queue_item:
        for field in ("status", "missing_requirements", "missing_cache_artifacts", "cache_validation_errors"):
            check(
                coverage_gap.get(field) == queue_item.get(field),
                failures,
                f"{prefix}:coverage_gap_{field}",
                coverage_gap.get(field),
                queue_item.get(field),
            )
    gap_plan_item = gap_plan_by_key.get(expected_key, {})
    observed_gap_plan = (observation or {}).get("gap_plan") if isinstance(observation, dict) else {}
    for field in ("status", "blockers", "required_operator_actions", "claim_gate"):
        check(
            observed_gap_plan.get(field) == gap_plan_item.get(field),
            failures,
            f"{prefix}:gap_plan_{field}",
            observed_gap_plan.get(field),
            gap_plan_item.get(field),
        )
    check(packet.get("gap_id") == (queue_item or {}).get("gap_id"), failures, f"{prefix}:packet_gap_id_matches_queue", packet.get("gap_id"), (queue_item or {}).get("gap_id"))

    for receipt_type in ("acquisition_receipt", "score_receipt", "validation_receipt"):
        receipt = packet.get(receipt_type)
        check(isinstance(receipt, dict), failures, f"{prefix}:{receipt_type}_object", type(receipt).__name__, "object")
        if not isinstance(receipt, dict):
            continue
        expected_type = receipt_type.removesuffix("_receipt")
        check(receipt.get("receipt_type") == expected_type, failures, f"{prefix}:{receipt_type}_type", receipt.get("receipt_type"), expected_type)
        check(receipt.get("receipt_id") == f"{expected_packet_id}::{expected_type}", failures, f"{prefix}:{receipt_type}_receipt_id", receipt.get("receipt_id"), f"{expected_packet_id}::{expected_type}")
        check(receipt.get("status") == "blocked", failures, f"{prefix}:{receipt_type}_status", receipt.get("status"), "blocked")
        check(receipt.get("receipt_input") is None, failures, f"{prefix}:{receipt_type}_input_empty", receipt.get("receipt_input"), None)
        check(receipt.get("completion_ready") is False, failures, f"{prefix}:{receipt_type}_completion_false", receipt.get("completion_ready"), False)
        check(receipt.get("no_fabricated_scores") is True, failures, f"{prefix}:{receipt_type}_no_fabricated_scores", receipt.get("no_fabricated_scores"), True)
        check(bool(receipt.get("required_outputs")), failures, f"{prefix}:{receipt_type}_required_outputs", receipt.get("required_outputs"), "non-empty")
        check(bool(receipt.get("operator_commands")), failures, f"{prefix}:{receipt_type}_operator_commands", receipt.get("operator_commands"), "non-empty")
        validate_evidence(packet, failures, prefix) if receipt_type == "acquisition_receipt" else None

    score_receipt = packet.get("score_receipt") or {}
    check(score_receipt.get("score_values") is None, failures, f"{prefix}:score_values_empty", score_receipt.get("score_values"), None)
    check(score_receipt.get("metric_values") is None, failures, f"{prefix}:metric_values_empty", score_receipt.get("metric_values"), None)
    check(score_receipt.get("score_values_prohibited") is True, failures, f"{prefix}:score_values_prohibited", score_receipt.get("score_values_prohibited"), True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark readiness packets")
    parser.add_argument("--packets", type=Path, default=DEFAULT_PACKETS)
    parser.add_argument("--packet-report", type=Path, default=DEFAULT_PACKET_REPORT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--require-ready", action="store_true", help="Return non-zero while any packet remains blocked.")
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    matrix = load_json(INPUTS["benchmark_matrix_report"], failures, "matrix")
    acquisition = load_jsonl(INPUTS["benchmark_acquisition_plan"], failures, "acquisition")
    manifest = load_json(INPUTS["benchmark_score_cache_manifest"], failures, "manifest")
    load_json(INPUTS["benchmark_score_cache_intake_report"], failures, "intake_report")
    validation = load_json(INPUTS["benchmark_score_cache_validation_report"], failures, "validation")
    dashboard = load_json(INPUTS["benchmark_coverage_dashboard"], failures, "coverage")
    gap_queue_rows = load_jsonl(INPUTS["benchmark_gap_queue"], failures, "gap_queue")
    gap_action_rows = load_jsonl(INPUTS["five_head_benchmark_gap_actions"], failures, "gap_actions")
    gap_plan = load_json(INPUTS["five_head_benchmark_gap_plan_report"], failures, "gap_plan")
    load_jsonl(INPUTS["benchmark_score_cache_intake"], failures, "intake")
    packets = load_jsonl(args.packets, failures, "packets")
    packet_report = load_json(args.packet_report, failures, "packet_report")
    markdown_text = read_text(args.markdown, failures, "markdown")

    matrix_keys_list = matrix_keys(matrix)
    matrix_by_key = index_rows(
        [
            {
                "head": head,
                "benchmark_name": benchmark_name,
                **(next(
                    (
                        row
                        for row in matrix.get("heads") or []
                        if isinstance(row, dict)
                        and row.get("head") == head
                    ),
                    {},
                )),
            }
            for head, benchmark_name in matrix_keys_list
        ]
    )
    plan_by_key = index_rows(acquisition)
    manifest_by_key = index_rows(manifest.get("rows") or [])
    validation_by_key = index_rows(validation.get("records") or [])
    coverage_key_set = coverage_keys(dashboard)
    queue_by_key = gap_queue_index(gap_queue_rows)
    gap_plan_by_key = gap_plan_index(gap_plan)
    current_snapshot = source_snapshot()
    discrepancies = source_discrepancies(dashboard, gap_action_rows)
    expected_summary, report_summary_matches, markdown_matches = validate_packet_report_and_markdown(
        packet_report,
        markdown_text,
        packets,
        args,
        current_snapshot,
        discrepancies,
        failures,
    )

    packet_keys = [(row.get("head"), row.get("benchmark_name")) for row in packets]
    packet_key_set = {
        (head, benchmark_name)
        for head, benchmark_name in packet_keys
        if isinstance(head, str) and isinstance(benchmark_name, str)
    }
    expected_keys = set(matrix_keys_list)
    check(len(packets) == len(packet_key_set), failures, "packet_identity_unique", len(packets), len(packet_key_set))
    check(packet_key_set == coverage_key_set, failures, "packets_cover_current_invalid_gaps", sorted(packet_key_set), sorted(coverage_key_set))
    check(coverage_key_set.issubset(expected_keys), failures, "coverage_gaps_are_matrix_keys", sorted(coverage_key_set), sorted(expected_keys))

    ordered_expected = [key for key in matrix_keys_list if key in coverage_key_set]
    for index, key in enumerate(ordered_expected, start=1):
        matching = [row for row in packets if (row.get("head"), row.get("benchmark_name")) == key]
        if matching:
            check(matching[0].get("execution_order") == index, failures, f"packet_order:{key}", matching[0].get("execution_order"), index)
            validate_packet(
                matching[0],
                key,
                current_snapshot,
                matrix_by_key,
                plan_by_key,
                manifest_by_key,
                validation_by_key,
                coverage_key_set,
                queue_by_key,
                gap_plan_by_key,
                failures,
            )

    packet_count = len(packets)
    completion_ready = sum(1 for row in packets if row.get("completion_ready") is True)
    score_values_recorded = sum(
        1
        for row in packets
        if (row.get("score_receipt") or {}).get("score_values") not in (None, {})
        or (row.get("score_receipt") or {}).get("metric_values") not in (None, {})
    )
    contract_valid = not failures
    ready = contract_valid and packet_count > 0 and completion_ready == packet_count and score_values_recorded == 0
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "contract_valid": contract_valid,
        "status": "ready" if ready else "blocked",
        "require_ready_requested": args.require_ready,
        "packet_rows": packet_count,
        "completion_ready_rows": completion_ready,
        "blocked_rows": packet_count - completion_ready,
        "score_values_recorded": score_values_recorded,
        "expected_summary": expected_summary,
        "packet_report_summary_matches_current_packets": report_summary_matches,
        "markdown_matches_current_packets": markdown_matches,
        "source_discrepancies": discrepancies,
        "failure_count": len(failures),
        "failures": failures[:500],
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "training_labels_modified": False,
        "release_flags_modified": False,
        "policy": POLICY,
        "inputs": {name: relative(path) for name, path in INPUTS.items()},
        "packets": relative(args.packets),
        "packet_report": relative(args.packet_report),
        "markdown": relative(args.markdown),
        "output": relative(args.output),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "contract_valid": contract_valid,
                "status": report["status"],
                "packet_rows": packet_count,
                "completion_ready_rows": completion_ready,
                "report_summary_matches": report_summary_matches,
                "markdown_matches": markdown_matches,
                "failure_count": len(failures),
                "output": str(args.output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    if not contract_valid:
        return 1
    if args.require_ready and not ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
