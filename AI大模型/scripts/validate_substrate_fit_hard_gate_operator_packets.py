#!/usr/bin/env python3
"""Validate fail-closed substrate-fit hard-gate operator packets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKETS = AI_ROOT / "datasets" / "governance" / "substrate_fit_hard_gate_operator_packets.jsonl"
REPORT = AI_ROOT / "reports" / "substrate_fit_hard_gate_operator_packet_report.json"
GAP_REPORT = AI_ROOT / "reports" / "substrate_fit_label_gap_plan_report.json"
STATUS_OUT = AI_ROOT / "datasets" / "governance" / "substrate_fit_hard_gate_operator_packet_status.jsonl"
VALIDATION_OUT = AI_ROOT / "reports" / "substrate_fit_hard_gate_operator_packet_validation_report.json"


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing_input:{relative(path)}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"invalid_json:{relative(path)}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"invalid_json_object:{relative(path)}")
        return {}
    return data


def load_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        errors.append(f"missing_input:{relative(path)}")
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"invalid_jsonl:{relative(path)}:{line_number}")
            continue
        if not isinstance(row, dict):
            errors.append(f"invalid_jsonl_object:{relative(path)}:{line_number}")
            continue
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def expected_counts(gap: dict[str, Any]) -> dict[str, int]:
    actions = [row for row in gap.get("actions") or [] if isinstance(row, dict)]
    sources = [row for row in gap.get("candidate_sources") or [] if isinstance(row, dict)]
    return {
        "packet_rows": len(actions) + len(sources),
        "action_packet_rows": len(actions),
        "source_packet_rows": len(sources),
    }


def row_errors(row: dict[str, Any], seen: set[str]) -> list[str]:
    errors: list[str] = []
    packet_id = str(row.get("packet_id") or "")
    packet_type = row.get("packet_type")
    if not packet_id:
        errors.append("missing_packet_id")
    elif packet_id in seen:
        errors.append("duplicate_packet_id")
    seen.add(packet_id)
    if row.get("status") != "open_blocked":
        errors.append("status_not_open_blocked")
    if row.get("completion_ready") is True:
        errors.append("completion_ready_must_not_be_true")
    if row.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    if row.get("training_label_written_by_packet") is not False:
        errors.append("training_label_written_by_packet_not_false")
    if row.get("model_claim_allowed") is not False:
        errors.append("model_claim_allowed_not_false")
    if row.get("release_ready") is not False:
        errors.append("release_ready_not_false")
    if packet_type == "substrate_fit_action":
        if row.get("schema_or_source_approved_by_packet") is not False:
            errors.append("schema_or_source_approved_by_packet_not_false")
        if not row.get("source_action_id"):
            errors.append("missing_source_action_id")
        if not isinstance(row.get("required_human_checks"), list) or len(row.get("required_human_checks")) < 3:
            errors.append("required_human_checks_missing")
    elif packet_type == "candidate_source_review":
        if row.get("source_approved_by_packet") is not False:
            errors.append("source_approved_by_packet_not_false")
        if not row.get("source_id"):
            errors.append("missing_source_id")
        shortcuts = row.get("forbidden_shortcuts")
        if not isinstance(shortcuts, list) or "generic_activity_as_substrate_fit" not in shortcuts:
            errors.append("forbidden_shortcuts_missing_generic_activity_guard")
    else:
        errors.append("unexpected_packet_type")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate substrate-fit hard-gate operator packets")
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--packet-report", type=Path, default=REPORT)
    parser.add_argument("--gap-report", type=Path, default=GAP_REPORT)
    parser.add_argument("--status-output", type=Path, default=STATUS_OUT)
    parser.add_argument("--report-output", type=Path, default=VALIDATION_OUT)
    args = parser.parse_args()

    input_errors: list[str] = []
    packets = load_jsonl(args.packets, input_errors)
    packet_report = load_json(args.packet_report, input_errors)
    gap = load_json(args.gap_report, input_errors)
    expected = expected_counts(gap)

    seen: set[str] = set()
    status_rows: list[dict[str, Any]] = []
    for row in packets:
        errors = row_errors(row, seen)
        status_rows.append(
            {
                "packet_id": row.get("packet_id"),
                "packet_type": row.get("packet_type"),
                "status": row.get("status"),
                "validation_status": "valid" if not errors else "invalid",
                "errors": errors,
                "completion_ready": False,
                "requires_human_input": row.get("requires_human_input") is True,
                "safe_for_training_import": False,
                "safe_for_model_claim": False,
                "release_ready": False,
            }
        )

    packet_type_counts = Counter(str(row.get("packet_type") or "") for row in packets)
    report_errors = list(input_errors)
    if packet_report.get("packet_rows") != len(packets):
        report_errors.append(f"report_packet_rows_mismatch:{packet_report.get('packet_rows')}!={len(packets)}")
    for field, expected_value in expected.items():
        if expected_value != len(packets) and field == "packet_rows":
            report_errors.append(f"gap_{field}_mismatch:{expected_value}!={len(packets)}")
        elif field == "action_packet_rows" and expected_value != packet_type_counts.get("substrate_fit_action", 0):
            report_errors.append(f"gap_action_packet_rows_mismatch:{expected_value}!={packet_type_counts.get('substrate_fit_action', 0)}")
        elif field == "source_packet_rows" and expected_value != packet_type_counts.get("candidate_source_review", 0):
            report_errors.append(f"gap_source_packet_rows_mismatch:{expected_value}!={packet_type_counts.get('candidate_source_review', 0)}")
    if packet_report.get("safe_for_model_claim") is not False:
        report_errors.append("packet_report_safe_for_model_claim_not_false")
    if packet_report.get("release_ready") is not False:
        report_errors.append("packet_report_release_ready_not_false")
    if packet_report.get("completion_ready_rows") != 0:
        report_errors.append("packet_report_completion_ready_rows_not_zero")

    invalid_rows = [row for row in status_rows if row["validation_status"] != "valid"]
    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "inputs": {
            "packets": relative(args.packets),
            "packet_report": relative(args.packet_report),
            "gap_report": relative(args.gap_report),
        },
        "outputs": {
            "status": relative(args.status_output),
            "report": relative(args.report_output),
        },
        "packet_rows": len(packets),
        "valid_rows": len(packets) - len(invalid_rows),
        "invalid_rows": len(invalid_rows),
        "all_operator_packets_valid": not invalid_rows and not report_errors,
        "report_errors": report_errors,
        "packet_type_counts": dict(sorted(packet_type_counts.items())),
        "expected_counts": expected,
        "completion_ready_rows": 0,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }

    write_jsonl(args.status_output, status_rows)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "all_operator_packets_valid": validation["all_operator_packets_valid"],
        "packet_rows": validation["packet_rows"],
        "invalid_rows": validation["invalid_rows"],
        "report_errors": len(report_errors),
        "safe_for_model_claim": validation["safe_for_model_claim"],
        "output": relative(args.report_output),
    }, ensure_ascii=False))
    return 0 if validation["all_operator_packets_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
