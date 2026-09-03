#!/usr/bin/env python3
"""Validate structure-feature hard-gate operator packets fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKETS = AI_ROOT / "datasets" / "governance" / "structure_feature_hard_gate_operator_packets.jsonl"
STATUS = AI_ROOT / "datasets" / "governance" / "structure_feature_hard_gate_operator_packet_status.jsonl"
REPORT = AI_ROOT / "reports" / "structure_feature_hard_gate_operator_packet_validation_report.json"
PACKET_REPORT = AI_ROOT / "reports" / "structure_feature_hard_gate_operator_packet_report.json"
GAP_REPORT = AI_ROOT / "reports" / "structure_feature_head_gap_plan_report.json"
BACKLOG_REPORT = AI_ROOT / "reports" / "structure_chain_mapping_backlog_readiness_report.json"
GRAPH_VALIDATION_REPORT = AI_ROOT / "reports" / "reviewed_structure_graph_feature_validation_report.json"
GRAPH_VALIDATION_FALLBACK = AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json"

EXPECTED_PACKET_ROWS = 14
EXPECTED_STRICT_ROWS = 9
EXPECTED_HEAD_ROWS = 5
STRICT_PACKET_TYPE = "strict_evidence_chain_mapping_review"
HEAD_PACKET_TYPE = "head_effective_feature_gap"
FAIL_CLOSED_POLICY_PHRASES = (
    "do not write",
    "train models",
    "model claims",
    "release artifacts",
)


def load_json(path: Path, label: str) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, [f"missing_source_report:{label}"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, [f"invalid_source_report:{label}"]
    if not isinstance(value, dict):
        return {}, [f"source_report_not_object:{label}"]
    return value, []


def load_jsonl(path: Path, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"missing_source_jsonl:{label}"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], [f"unreadable_source_jsonl:{label}"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"invalid_source_jsonl:{label}:line_{line_number}")
            continue
        if not isinstance(value, dict):
            errors.append(f"source_jsonl_row_not_object:{label}:line_{line_number}")
            continue
        rows.append(value)
    return rows, errors


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def selected_graph_report() -> Path:
    if GRAPH_VALIDATION_REPORT.exists():
        return GRAPH_VALIDATION_REPORT
    return GRAPH_VALIDATION_FALLBACK


def add_error(errors: list[str], value: str) -> None:
    if value not in errors:
        errors.append(value)


def validate_common(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "packet_id",
        "execution_order",
        "workstream",
        "packet_type",
        "status",
        "priority",
        "completion_condition",
        "decision_written_by_packet",
        "coordinate_claim_allowed",
        "training_label_written_by_packet",
        "model_claim_allowed",
        "release_ready",
        "requires_human_input",
        "policy",
    ]
    for field in required:
        if field not in packet:
            errors.append(f"missing_{field}")

    if packet.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    for field in (
        "decision_written_by_packet",
        "coordinate_claim_allowed",
        "training_label_written_by_packet",
        "model_claim_allowed",
        "release_ready",
    ):
        if packet.get(field) is not False:
            errors.append(f"{field}_not_false")
    if "completion_ready" in packet and packet.get("completion_ready") is not False:
        errors.append("completion_ready_not_false")
    if not isinstance(packet.get("completion_condition"), str) or not packet.get("completion_condition"):
        errors.append("completion_condition_missing")

    policy = str(packet.get("policy") or "").lower()
    if not all(phrase in policy for phrase in FAIL_CLOSED_POLICY_PHRASES):
        errors.append("policy_missing_fail_closed_language")
    return errors


def validate_strict_packet(
    packet: dict[str, Any],
    expected: dict[str, Any] | None,
    order: int,
) -> list[str]:
    errors = validate_common(packet)
    if expected is None:
        errors.append("unexpected_strict_candidate")
        return errors

    expected_values = {
        "packet_id": f"structure-feature-hard-gate-{expected.get('structure_id')}",
        "execution_order": order,
        "workstream": "structure_feature_expansion",
        "packet_type": STRICT_PACKET_TYPE,
        "status": "open_blocked_waiting_for_human_review",
        "structure_id": expected.get("structure_id"),
        "canonical_uniprot_id": expected.get("canonical_uniprot_id"),
        "source_packet_id": expected.get("packet_id"),
        "suggested_selected_chain_id": expected.get("suggested_selected_chain_id"),
        "strict_evidence_sources": expected.get("strict_evidence_sources") or [],
        "decision_input_after_human_review": expected.get("decision_input"),
        "required_human_checks": expected.get("required_human_checks") or [],
    }
    for field, value in expected_values.items():
        if packet.get(field) != value:
            errors.append(f"{field}_mismatch")
    return errors


def validate_head_packet(
    packet: dict[str, Any],
    expected: dict[str, Any] | None,
    order: int,
) -> list[str]:
    errors = validate_common(packet)
    if expected is None:
        errors.append("unexpected_head_gap")
        return errors

    expected_values = {
        "packet_id": f"structure-feature-head-gap-{expected.get('head')}",
        "execution_order": order,
        "workstream": "structure_feature_head_capacity",
        "packet_type": HEAD_PACKET_TYPE,
        "status": "open_blocked",
        "head": expected.get("head"),
        "current_label_rows": int(expected.get("current_label_rows") or 0),
        "minimum_rows": int(expected.get("minimum_rows") or 0),
        "effective_training_rows_with_structure_features": int(
            expected.get("effective_training_rows_with_structure_features") or 0
        ),
        "effective_gap_to_minimum": int(expected.get("effective_gap_to_minimum") or 0),
        "chain_mapping_backlog_rows": int(expected.get("chain_mapping_backlog_rows") or 0),
        "next_strict_chain_candidate_rows": int(expected.get("next_strict_chain_candidate_rows") or 0),
        "blocking_gate": expected.get("blocking_gate"),
        "blockers": expected.get("blockers") or [],
    }
    for field, value in expected_values.items():
        if packet.get(field) != value:
            errors.append(f"{field}_mismatch")
    return errors


def source_blocked_reasons(
    packet_report: dict[str, Any],
    gap_report: dict[str, Any],
    backlog_report: dict[str, Any],
) -> list[str]:
    reasons: set[str] = {
        "human_review_required",
        "completion_ready_false",
        "coordinate_claims_closed",
        "training_import_closed",
        "model_claim_closed",
        "release_closed",
    }
    for report in (packet_report, gap_report, backlog_report):
        for reason in report.get("blockers") or []:
            reasons.add(str(reason))
    for row in gap_report.get("head_readiness") or []:
        for reason in row.get("blockers") or []:
            reasons.add(str(reason))
    return sorted(reason for reason in reasons if reason)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate structure-feature hard-gate operator packets")
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--packet-report", type=Path, default=PACKET_REPORT)
    parser.add_argument("--gap-report", type=Path, default=GAP_REPORT)
    parser.add_argument("--backlog-report", type=Path, default=BACKLOG_REPORT)
    parser.add_argument("--graph-validation-report", type=Path, default=GRAPH_VALIDATION_REPORT)
    parser.add_argument("--status-output", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    packets, packet_errors = load_jsonl(args.packets, "operator_packets")
    packet_report, packet_report_errors = load_json(args.packet_report, "operator_packet_report")
    gap_report, gap_report_errors = load_json(args.gap_report, "head_gap_plan_report")
    backlog_report, backlog_report_errors = load_json(args.backlog_report, "chain_mapping_backlog_readiness_report")

    graph_path = args.graph_validation_report
    if graph_path == GRAPH_VALIDATION_REPORT and not graph_path.exists() and GRAPH_VALIDATION_FALLBACK.exists():
        graph_path = GRAPH_VALIDATION_FALLBACK
    graph_report, graph_report_errors = load_json(graph_path, "reviewed_structure_graph_feature_validation_report")
    source_errors = packet_errors + packet_report_errors + gap_report_errors + backlog_report_errors + graph_report_errors

    strict_candidates = [
        row for row in gap_report.get("strict_evidence_chain_candidates") or [] if isinstance(row, dict)
    ]
    head_rows = [row for row in gap_report.get("head_readiness") or [] if isinstance(row, dict)]
    strict_by_structure = {str(row.get("structure_id")): row for row in strict_candidates}
    heads_by_name = {str(row.get("head")): row for row in head_rows}
    expected_strict_ids = [str(row.get("structure_id")) for row in strict_candidates]
    expected_heads = [str(row.get("head")) for row in head_rows]
    expected_packet_ids = [
        f"structure-feature-hard-gate-{structure_id}" for structure_id in expected_strict_ids
    ] + [f"structure-feature-head-gap-{head}" for head in expected_heads]

    seen_packet_ids: list[str] = []
    duplicate_packet_ids: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    error_counts = Counter(source_errors)

    for index, packet in enumerate(packets, start=1):
        packet_id = str(packet.get("packet_id") or "")
        if packet_id in seen_packet_ids:
            duplicate_packet_ids.add(packet_id)
        seen_packet_ids.append(packet_id)

        packet_type = packet.get("packet_type")
        if packet_type == STRICT_PACKET_TYPE:
            expected = strict_by_structure.get(str(packet.get("structure_id")))
            row_errors = validate_strict_packet(packet, expected, index)
        elif packet_type == HEAD_PACKET_TYPE:
            expected = heads_by_name.get(str(packet.get("head")))
            row_errors = validate_head_packet(packet, expected, index)
        else:
            row_errors = validate_common(packet)
            row_errors.append("unexpected_packet_type")

        error_counts.update(row_errors)
        status_rows.append(
            {
                "record_type": "structure_feature_hard_gate_operator_packet",
                "record_id": packet.get("packet_id"),
                "packet_id": packet.get("packet_id"),
                "execution_order": packet.get("execution_order"),
                "packet_type": packet.get("packet_type"),
                "workstream": packet.get("workstream"),
                "structure_id": packet.get("structure_id"),
                "head": packet.get("head"),
                "status": packet.get("status"),
                "valid": not row_errors,
                "completion_ready": False,
                "requires_human_input": True,
                "decision_written_by_packet": False,
                "coordinate_claim_allowed": False,
                "training_label_written_by_packet": False,
                "model_claim_allowed": False,
                "release_ready": False,
                "errors": row_errors,
                "blocked_reasons": [],
                "policy": (
                    "Validation only; packet remains blocked and requires human review. "
                    "It is not a chain-mapping decision, training import, model claim, or release approval."
                ),
            }
        )

    actual_strict_ids = [
        str(packet.get("structure_id"))
        for packet in packets
        if packet.get("packet_type") == STRICT_PACKET_TYPE
    ]
    actual_heads = [
        str(packet.get("head"))
        for packet in packets
        if packet.get("packet_type") == HEAD_PACKET_TYPE
    ]
    actual_packet_ids = [str(packet.get("packet_id") or "") for packet in packets]
    missing_packet_ids = sorted(set(expected_packet_ids) - set(actual_packet_ids))
    unexpected_packet_ids = sorted(set(actual_packet_ids) - set(expected_packet_ids))
    duplicate_packet_id_list = sorted(duplicate_packet_ids)
    global_errors: list[str] = []

    if len(packets) != EXPECTED_PACKET_ROWS:
        global_errors.append("packet_count_mismatch")
    if len(strict_candidates) != EXPECTED_STRICT_ROWS:
        global_errors.append("strict_candidate_source_count_mismatch")
    if len(head_rows) != EXPECTED_HEAD_ROWS:
        global_errors.append("head_gap_source_count_mismatch")
    if len(actual_strict_ids) != EXPECTED_STRICT_ROWS:
        global_errors.append("strict_candidate_packet_count_mismatch")
    if len(actual_heads) != EXPECTED_HEAD_ROWS:
        global_errors.append("head_gap_packet_count_mismatch")
    if actual_strict_ids != expected_strict_ids:
        global_errors.append("strict_candidate_order_or_coverage_mismatch")
    if actual_heads != expected_heads:
        global_errors.append("head_gap_order_or_coverage_mismatch")
    if missing_packet_ids:
        global_errors.append("missing_packet_rows")
    if unexpected_packet_ids:
        global_errors.append("unexpected_packet_rows")
    if duplicate_packet_id_list:
        global_errors.append("duplicate_packet_rows")

    expected_packet_report_values = {
        "status": "blocked",
        "packet_rows": EXPECTED_PACKET_ROWS,
        "strict_candidate_packet_rows": EXPECTED_STRICT_ROWS,
        "head_gap_packet_rows": EXPECTED_HEAD_ROWS,
        "completion_ready_rows": 0,
        "decision_written_rows": 0,
        "coordinate_claim_allowed_rows": 0,
        "training_label_written_rows": 0,
        "requires_human_input_rows": EXPECTED_PACKET_ROWS,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    for field, expected in expected_packet_report_values.items():
        if packet_report.get(field) != expected:
            global_errors.append(f"packet_report_{field}_mismatch")

    expected_gap_values = {
        "status": "blocked",
        "action_rows": EXPECTED_PACKET_ROWS,
        "strict_candidate_action_rows": EXPECTED_STRICT_ROWS,
        "head_action_rows": EXPECTED_HEAD_ROWS,
        "coordinate_claim_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    for field, expected in expected_gap_values.items():
        if gap_report.get(field) != expected:
            global_errors.append(f"gap_report_{field}_mismatch")

    if backlog_report.get("remaining_unreviewed_rows", 0) <= 0:
        global_errors.append("chain_mapping_backlog_unexpectedly_empty")
    if backlog_report.get("strict_evidence_remaining_rows") != EXPECTED_STRICT_ROWS:
        global_errors.append("backlog_strict_remaining_count_mismatch")
    if sorted(str(value) for value in backlog_report.get("strict_evidence_remaining_structure_ids") or []) != sorted(
        expected_strict_ids
    ):
        global_errors.append("backlog_strict_remaining_coverage_mismatch")
    for field in ("completion_ready", "safe_for_model_claim", "release_ready"):
        if backlog_report.get(field) is not False:
            global_errors.append(f"backlog_report_{field}_not_false")

    if graph_report.get("invalid_rows") != 0:
        global_errors.append("reviewed_structure_graph_invalid_rows_nonzero")
    if graph_report.get("safe_for_model_claim") is not False:
        global_errors.append("reviewed_structure_graph_safe_for_model_claim_not_false")
    if graph_report.get("ready_for_coordinate_feature_use") is not True:
        global_errors.append("reviewed_structure_graph_coordinate_features_not_ready")

    all_global_errors = list(dict.fromkeys(source_errors + global_errors))
    for status in status_rows:
        if all_global_errors:
            status["valid"] = False
            status["errors"] = list(dict.fromkeys(status["errors"] + all_global_errors))
        status["blocked_reasons"] = source_blocked_reasons(packet_report, gap_report, backlog_report)
        status["blocked_reasons"].extend(
            error for error in status["errors"] if error not in status["blocked_reasons"]
        )
        status["blocked_reasons"] = sorted(set(status["blocked_reasons"]))

    valid_rows = sum(1 for row in status_rows if row["valid"])
    invalid_rows = len(status_rows) - valid_rows
    blocked_reasons = source_blocked_reasons(packet_report, gap_report, backlog_report)
    blocked_reasons.extend(all_global_errors)
    blocked_reasons = sorted(set(blocked_reasons))
    blocked_reason_counts = Counter()
    for row in status_rows:
        blocked_reason_counts.update(row["blocked_reasons"])

    coverage = {
        "expected_total": EXPECTED_PACKET_ROWS,
        "observed_total": len(packets),
        "expected_strict_candidates": EXPECTED_STRICT_ROWS,
        "observed_strict_candidates": len(actual_strict_ids),
        "expected_head_gaps": EXPECTED_HEAD_ROWS,
        "observed_head_gaps": len(actual_heads),
        "expected_structure_ids": expected_strict_ids,
        "observed_structure_ids": actual_strict_ids,
        "expected_heads": expected_heads,
        "observed_heads": actual_heads,
        "missing_packet_ids": missing_packet_ids,
        "unexpected_packet_ids": unexpected_packet_ids,
        "duplicate_packet_ids": duplicate_packet_id_list,
        "backlog_strict_remaining_structure_ids": sorted(
            str(value) for value in backlog_report.get("strict_evidence_remaining_structure_ids") or []
        ),
    }
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet_rows": len(packets),
        "status_rows": len(status_rows),
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "all_operator_packets_valid": (
            not all_global_errors
            and not duplicate_packet_id_list
            and len(packets) == EXPECTED_PACKET_ROWS
            and valid_rows == len(packets)
        ),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "coverage": coverage,
        "blocked_reasons": blocked_reasons,
        "blocked_reason_counts": dict(sorted(blocked_reason_counts.items())),
        "error_counts": dict(sorted(error_counts.items())),
        "source_reports": {
            "operator_packets": str(args.packets),
            "operator_packet_report": str(args.packet_report),
            "head_gap_plan_report": str(args.gap_report),
            "chain_mapping_backlog_readiness_report": str(args.backlog_report),
            "reviewed_structure_graph_feature_validation_report": str(graph_path),
        },
        "requested_reviewed_structure_graph_feature_validation_report": str(args.graph_validation_report),
        "graph_validation_report_compatibility_fallback_used": graph_path != args.graph_validation_report,
        "status_output": str(args.status_output),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Fail-closed validation only. A valid packet is still blocked, requires human review, "
            "cannot write decisions or labels, cannot support training or model claims, and cannot release artifacts."
        ),
    }

    write_jsonl(args.status_output, status_rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "packet_rows": report["packet_rows"],
                "valid_rows": report["valid_rows"],
                "invalid_rows": report["invalid_rows"],
                "all_operator_packets_valid": report["all_operator_packets_valid"],
                "status_output": str(args.status_output),
                "report": str(args.report),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
