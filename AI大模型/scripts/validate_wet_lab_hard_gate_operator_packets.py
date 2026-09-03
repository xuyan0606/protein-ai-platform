#!/usr/bin/env python3
"""Validate fail-closed wet-lab hard-gate operator packets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GAP_REPORT = AI_ROOT / "reports" / "wet_lab_head_authorization_gap_plan_report.json"
PACKET_REPORT = AI_ROOT / "reports" / "wet_lab_hard_gate_operator_packet_report.json"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_hard_gate_operator_packets.md"
PACKETS = AI_ROOT / "datasets" / "feedback" / "wet_lab_hard_gate_operator_packets.jsonl"
OUTPUT = AI_ROOT / "reports" / "wet_lab_hard_gate_operator_packet_validation_report.json"

POLICY = (
    "Fail-closed wet-lab operator packets only. They do not write authorization decisions, "
    "preflight rows, apply-plan rows, experiment feedback records, head labels, training rows, "
    "model claims, deployments, syncs, or release readiness."
)

FALSE_FIELDS = [
    "authorization_decision_written_by_packet",
    "feedback_intake_written_by_packet",
    "training_label_written_by_packet",
    "model_claim_allowed",
    "release_ready",
]


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


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


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_score(row: dict[str, Any]) -> float:
    ratio = as_float(row.get("vs_control_ratio"))
    if ratio is None:
        return 0.0
    return abs(ratio - 1.0)


def action_to_packet(row: dict[str, Any], order: int) -> dict[str, Any]:
    authorization = row.get("authorization_state") if isinstance(row.get("authorization_state"), dict) else {}
    missing = authorization.get("missing_or_invalid_fields")
    if not isinstance(missing, list):
        missing = []
    approval_requirements = authorization.get("approval_requirements")
    if not isinstance(approval_requirements, list):
        approval_requirements = []
    ratio = as_float(row.get("vs_control_ratio"))
    raw = as_float(row.get("raw_value_numeric"))
    control = as_float(row.get("control_value_numeric"))
    return {
        "packet_id": f"wetlab-hard-gate-{row.get('feedback_candidate_id')}",
        "execution_order": order,
        "workstream": "wet_lab_training_eligible_feedback",
        "priority": "P0",
        "status": "open_blocked",
        "variant": row.get("variant"),
        "sample_id": row.get("sample_id"),
        "batch_id": row.get("batch_id"),
        "feedback_candidate_id": row.get("feedback_candidate_id"),
        "authorization_worklist_id": row.get("authorization_worklist_id"),
        "authorization_template_id": row.get("authorization_template_id"),
        "metric_name": row.get("metric_name"),
        "metric_class": row.get("metric_class"),
        "assay_type": row.get("assay_type"),
        "target_head": row.get("target_head"),
        "expected_authorization_head": row.get("expected_authorization_head"),
        "outcome_candidate": row.get("outcome_candidate"),
        "raw_value_numeric": raw,
        "control_value_numeric": control,
        "vs_control_ratio": ratio,
        "ratio_delta_from_control": round(ratio - 1.0, 6) if ratio is not None else None,
        "absolute_ratio_delta": round(row_score(row), 6),
        "review_priority": row.get("review_priority"),
        "conflicting_property_signal": bool(row.get("conflicting_property_signal")),
        "variant_property_call": row.get("variant_property_call"),
        "source_file": row.get("source_file"),
        "source_row_index": row.get("source_row_index"),
        "head_current_training_rows": row.get("head_current_training_rows"),
        "head_missing_to_minimum": row.get("head_missing_to_minimum"),
        "head_schema_gap": row.get("head_schema_gap"),
        "missing_authorization_fields": missing,
        "approval_requirements": approval_requirements,
        "decision_write_target_after_human_review": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
        "allowed_human_decisions": ["approved_for_feedback_intake", "rejected", "needs_more_info"],
        "post_decision_commands": [
            "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "python3 scripts/build_wet_lab_mutant_library_feedback_intake_apply_plan.py",
            "python3 scripts/build_wet_lab_head_authorization_gap_plan.py",
            "python3 scripts/build_wet_lab_hard_gate_operator_packets.py",
            "python3 scripts/run_safe_training_pipeline.py",
        ],
        "completion_condition": (
            "A human must record a valid authorization row with reviewer, reviewed_at, basis, QC, source trace, "
            "numbering, unit/condition, batch/control and replicate checks. A separate explicit apply action is "
            "required before any feedback intake or head-label mapping."
        ),
        "authorization_decision_written_by_packet": False,
        "feedback_intake_written_by_packet": False,
        "training_label_written_by_packet": False,
        "model_claim_allowed": False,
        "release_ready": False,
        "requires_human_input": True,
        "policy": POLICY,
    }


def expected_packets(gap: dict[str, Any]) -> list[dict[str, Any]]:
    actions = gap.get("actions") if isinstance(gap.get("actions"), list) else []
    sorted_actions = sorted(
        [row for row in actions if isinstance(row, dict)],
        key=lambda row: (
            {"critical_tradeoff_review": 0, "medium_mixed_benefit_review": 1}.get(str(row.get("review_priority")), 9),
            -row_score(row),
            str(row.get("variant") or ""),
            str(row.get("metric_name") or ""),
        ),
    )
    return [action_to_packet(row, index) for index, row in enumerate(sorted_actions, 1)]


def comparable_packet(packet: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "packet_id",
        "execution_order",
        "workstream",
        "priority",
        "status",
        "variant",
        "sample_id",
        "batch_id",
        "feedback_candidate_id",
        "authorization_worklist_id",
        "authorization_template_id",
        "metric_name",
        "metric_class",
        "assay_type",
        "target_head",
        "expected_authorization_head",
        "outcome_candidate",
        "raw_value_numeric",
        "control_value_numeric",
        "vs_control_ratio",
        "ratio_delta_from_control",
        "absolute_ratio_delta",
        "review_priority",
        "conflicting_property_signal",
        "variant_property_call",
        "source_file",
        "source_row_index",
        "head_current_training_rows",
        "head_missing_to_minimum",
        "head_schema_gap",
        "missing_authorization_fields",
        "approval_requirements",
        "decision_write_target_after_human_review",
        "allowed_human_decisions",
        "post_decision_commands",
        "completion_condition",
        *FALSE_FIELDS,
        "requires_human_input",
        "policy",
    ]
    return {field: packet.get(field) for field in fields}


def report_projection(created_at: str, packets: list[dict[str, Any]], gap_report: Path, jsonl: Path) -> dict[str, Any]:
    return {
        "created_at": created_at,
        "local_only": True,
        "status": "blocked",
        "source_gap_report": str(gap_report),
        "jsonl": str(jsonl),
        "packet_rows": len(packets),
        "completion_ready_rows": 0,
        "authorization_decision_written_rows": 0,
        "feedback_intake_written_rows": 0,
        "training_label_written_rows": 0,
        "requires_human_input_rows": len(packets),
        "variant_counts": dict(sorted(Counter(str(row.get("variant")) for row in packets).items())),
        "head_counts": dict(sorted(Counter(str(row.get("target_head")) for row in packets).items())),
        "review_priority_counts": dict(sorted(Counter(str(row.get("review_priority")) for row in packets).items())),
        "missing_authorization_field_counts": dict(sorted(Counter(field for row in packets for field in row["missing_authorization_fields"]).items())),
        "top_packets": packets,
        "safe_for_feedback_intake": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": POLICY,
    }


def markdown_projection(report: dict[str, Any]) -> str:
    lines = [
        "# Wet-Lab Hard-Gate Operator Packets",
        "",
        f"Generated: {report['created_at']}",
        "",
        "These packets organize manual wet-lab authorization work. They do not write decisions or labels.",
        "",
        "## Summary",
        "",
        f"- Packet rows: {report['packet_rows']}",
        f"- Completion ready rows: {report['completion_ready_rows']}",
        f"- Variants: {report['variant_counts']}",
        f"- Head counts: {report['head_counts']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Packets",
        "",
        "| order | variant | metric | head | ratio | priority | missing fields |",
        "|---:|---|---|---|---:|---|---:|",
    ]
    for row in report["top_packets"]:
        lines.append(
            f"| {row['execution_order']} | {row['variant']} | {row['metric_name']} | {row['target_head']} | "
            f"{row['vs_control_ratio']} | {row['review_priority']} | {len(row['missing_authorization_fields'])} |"
        )
    lines.extend(["", "## Policy", "", report["policy"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab hard-gate operator packets")
    parser.add_argument("--gap-report", type=Path, default=GAP_REPORT)
    parser.add_argument("--packet-report", type=Path, default=PACKET_REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--jsonl", type=Path, default=PACKETS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    gap = load_json(args.gap_report, failures, "gap_report")
    report = load_json(args.packet_report, failures, "packet_report")
    markdown_text = read_text(args.markdown, failures, "markdown")
    packets = load_jsonl(args.jsonl, failures, "packets")
    expected = expected_packets(gap)

    observed_cmp = [comparable_packet(packet) for packet in packets]
    expected_cmp = [comparable_packet(packet) for packet in expected]
    check(observed_cmp == expected_cmp, failures, "packets_match_gap_actions", observed_cmp, expected_cmp)

    expected_report = report_projection(report.get("created_at"), expected, args.gap_report, args.jsonl)
    check(report == expected_report, failures, "report_matches_current_packets", report, expected_report)
    expected_md = markdown_projection(expected_report)
    markdown_matches = markdown_text == expected_md
    check(markdown_matches, failures, "markdown_matches_current_packets", markdown_text, expected_md)

    for packet in packets:
        packet_id = packet.get("packet_id")
        check(packet.get("status") == "open_blocked", failures, f"{packet_id}:status_open_blocked", packet.get("status"), "open_blocked")
        check(packet.get("requires_human_input") is True, failures, f"{packet_id}:requires_human_input", packet.get("requires_human_input"), True)
        for field in FALSE_FIELDS:
            check(packet.get(field) is False, failures, f"{packet_id}:{field}_false", packet.get(field), False)
    for field in ("authorization_decision_written_rows", "feedback_intake_written_rows", "training_label_written_rows", "completion_ready_rows"):
        check(report.get(field) == 0, failures, f"report_{field}_zero", report.get(field), 0)
    for field in ("safe_for_feedback_intake", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
        check(report.get(field) is False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "contract_valid": not failures,
        "status": "blocked",
        "packet_rows": len(packets),
        "expected_packet_rows": len(expected),
        "completion_ready_rows": sum(1 for packet in packets if packet.get("completion_ready") is True),
        "report_matches_current_packets": report == expected_report,
        "markdown_matches_current_packets": markdown_matches,
        "failure_count": len(failures),
        "failures": failures[:500],
        "safe_for_feedback_intake": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation only. Passing means wet-lab hard-gate packets are current and fail-closed, not approved.",
        "inputs": {"wet_lab_head_authorization_gap_plan_report": relative(args.gap_report)},
        "packets": relative(args.jsonl),
        "packet_report": relative(args.packet_report),
        "markdown": relative(args.markdown),
        "output": relative(args.output),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "contract_valid": validation["contract_valid"],
        "packet_rows": validation["packet_rows"],
        "expected_packet_rows": validation["expected_packet_rows"],
        "completion_ready_rows": validation["completion_ready_rows"],
        "failure_count": validation["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
