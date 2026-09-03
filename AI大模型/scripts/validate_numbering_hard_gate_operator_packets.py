#!/usr/bin/env python3
"""Validate reviewed-numbering hard-gate operator packets fail-closed.

This validator checks packet integrity and coverage only. It does not write
curation decisions, apply curation, import labels, run training, or update a
manifest.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKETS = AI_ROOT / "datasets" / "governance" / "numbering_hard_gate_operator_packets.jsonl"
PACKET_REPORT = AI_ROOT / "reports" / "numbering_hard_gate_operator_packet_report.json"
OPERATOR_QUEUE = AI_ROOT / "reports" / "numbering_review_operator_queue.json"
SEMANTIC_CONFLICT_QUEUE = (
    AI_ROOT / "datasets" / "curation" / "numbering_decision_semantic_conflict_queue.jsonl"
)
PROVENANCE_REPORT = AI_ROOT / "reports" / "label_provenance_audit_report.json"
STATUS_OUT = AI_ROOT / "datasets" / "governance" / "numbering_hard_gate_operator_packet_status.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_hard_gate_operator_packet_validation_report.json"

EXPECTED_PACKET_STATUS = "open_blocked"
EXPECTED_WORKSTREAM = "reviewed_numbering_hard_gate"

REQUIRED_FALSE_FIELDS = (
    "completion_ready",
    "decision_written_by_packet",
    "curation_apply_by_packet",
    "label_import_by_packet",
    "safe_for_model_claim",
    "release_ready",
)

OPTIONAL_FALSE_FIELDS = (
    "safe_pipeline_integration_allowed",
    "manifest_update_allowed",
    "training_unlocked",
)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing_input:{rel(path)}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"invalid_json:{rel(path)}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"invalid_json_object:{rel(path)}")
        return {}
    return value


def load_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        errors.append(f"missing_input:{rel(path)}")
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        errors.append(f"invalid_jsonl:{rel(path)}")
        return []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"invalid_jsonl:{rel(path)}:{line_number}")
            continue
        if not isinstance(value, dict):
            errors.append(f"invalid_jsonl_object:{rel(path)}:{line_number}")
            continue
        rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def as_record_ids(row: dict[str, Any]) -> list[str]:
    raw = row.get("record_ids")
    if not isinstance(raw, list):
        return []
    return [str(record_id) for record_id in raw if record_id]


def duplicate_values(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def open_packet_group_key(row: dict[str, Any]) -> str:
    return str(row.get("packet_id") or row.get("review_bucket") or "unassigned")


def queue_rows(operator_queue: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    raw_rows = operator_queue.get("rows")
    if not isinstance(raw_rows, list):
        errors.append("operator_queue_rows_missing_or_invalid")
        return []
    return [row for row in raw_rows if isinstance(row, dict)]


def validate_packet_row(
    packet: dict[str, Any],
    line_number: int,
    conflict_record_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    for field in ("packet_id", "execution_order", "packet_type", "workstream", "status", "record_count", "record_ids"):
        if field not in packet:
            errors.append(f"missing_{field}")

    packet_type = packet.get("packet_type")
    record_ids = as_record_ids(packet)

    if not packet.get("packet_id"):
        errors.append("empty_packet_id")
    if packet.get("execution_order") != line_number:
        errors.append("execution_order_not_sequential")
    if packet.get("workstream") != EXPECTED_WORKSTREAM:
        errors.append("invalid_workstream")
    if packet.get("status") != EXPECTED_PACKET_STATUS:
        errors.append("status_not_open_blocked")
    if packet_type not in {"semantic_conflict", "open_numbering_batch"}:
        errors.append("invalid_packet_type")
    if packet.get("record_count") != len(record_ids):
        errors.append("record_count_mismatch")
    if not record_ids:
        errors.append("empty_record_ids")

    for field in REQUIRED_FALSE_FIELDS:
        if packet.get(field) is not False:
            errors.append(f"{field}_not_false")
    for field in OPTIONAL_FALSE_FIELDS:
        if field in packet and packet.get(field) is not False:
            errors.append(f"{field}_not_false")
    if packet.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")

    provenance_gate = packet.get("label_provenance_gate")
    if not isinstance(provenance_gate, dict):
        errors.append("missing_label_provenance_gate")
    elif provenance_gate.get("safe_for_model_claim") is not False:
        errors.append("label_provenance_gate_safe_for_model_claim_not_false")

    if packet_type == "semantic_conflict":
        if packet.get("record_count") != 1:
            errors.append("semantic_conflict_record_count_not_one")
        if not packet.get("conflict_id"):
            errors.append("missing_conflict_id")
        for record_id in record_ids:
            if record_id not in conflict_record_ids:
                errors.append("semantic_conflict_record_not_in_conflict_queue")
    elif packet_type == "open_numbering_batch":
        if not packet.get("source_packet_id"):
            errors.append("missing_source_packet_id")
        for record_id in record_ids:
            if record_id in conflict_record_ids:
                errors.append("open_packet_contains_semantic_conflict_record")

    policy = str(packet.get("policy") or "").lower()
    for phrase in ("do not write", "apply curation", "import labels", "release readiness"):
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate numbering hard-gate operator packets")
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--packet-report", type=Path, default=PACKET_REPORT)
    parser.add_argument("--operator-queue", type=Path, default=OPERATOR_QUEUE)
    parser.add_argument("--semantic-conflict-queue", type=Path, default=SEMANTIC_CONFLICT_QUEUE)
    parser.add_argument("--label-provenance-report", type=Path, default=PROVENANCE_REPORT)
    parser.add_argument("--status-output", type=Path, default=STATUS_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    input_errors: list[str] = []
    packets = load_jsonl(args.packets, input_errors)
    packet_report = load_json(args.packet_report, input_errors)
    operator_queue = load_json(args.operator_queue, input_errors)
    conflict_rows = load_jsonl(args.semantic_conflict_queue, input_errors)
    provenance_report = load_json(args.label_provenance_report, input_errors)
    operator_rows = queue_rows(operator_queue, input_errors)

    conflict_record_ids = {str(row.get("record_id")) for row in conflict_rows if row.get("record_id")}
    open_queue_record_ids = {
        str(row.get("record_id"))
        for row in operator_rows
        if row.get("operator_status") == "todo" and row.get("record_id")
    }
    semantic_queue_record_ids = {
        str(row.get("record_id"))
        for row in operator_rows
        if row.get("operator_status") == "semantic_conflict" and row.get("record_id")
    }
    expected_semantic_conflict_rows = len(conflict_record_ids)
    expected_open_numbering_rows = len(open_queue_record_ids)
    expected_open_packet_rows = len(
        {open_packet_group_key(row) for row in operator_rows if row.get("operator_status") == "todo"}
    )
    expected_packet_rows = expected_semantic_conflict_rows + expected_open_packet_rows

    packet_ids: list[str] = []
    status_rows: list[dict[str, Any]] = []
    row_error_counts: Counter[str] = Counter()
    semantic_packet_record_ids: list[str] = []
    open_packet_record_ids: list[str] = []

    for line_number, packet in enumerate(packets, start=1):
        packet_id = str(packet.get("packet_id") or "")
        packet_ids.append(packet_id)
        record_ids = as_record_ids(packet)
        if packet.get("packet_type") == "semantic_conflict":
            semantic_packet_record_ids.extend(record_ids)
        if packet.get("packet_type") == "open_numbering_batch":
            open_packet_record_ids.extend(record_ids)
        row_errors = validate_packet_row(packet, line_number, conflict_record_ids)
        row_error_counts.update(row_errors)
        status_rows.append(
            {
                "packet_id": packet_id,
                "execution_order": packet.get("execution_order"),
                "packet_type": packet.get("packet_type"),
                "status": packet.get("status"),
                "record_count": packet.get("record_count"),
                "covered_record_count": len(record_ids),
                "valid": not row_errors,
                "validation_status": "valid_blocked" if not row_errors else "invalid_blocked",
                "errors": row_errors,
                "completion_ready": False,
                "requires_human_input": True,
                "decision_written_by_packet": False,
                "curation_apply_by_packet": False,
                "label_import_by_packet": False,
                "safe_for_model_claim": False,
                "release_ready": False,
                "policy": (
                    "Status validation only; this row is not a decision, label import, curation apply, "
                    "model-claim approval, or release approval."
                ),
            }
        )

    duplicate_packet_ids = duplicate_values(packet_ids)
    duplicate_semantic_packet_records = duplicate_values(semantic_packet_record_ids)
    duplicate_open_packet_records = duplicate_values(open_packet_record_ids)

    for status in status_rows:
        if status["packet_id"] in duplicate_packet_ids:
            status["valid"] = False
            status["validation_status"] = "invalid_blocked"
            status["errors"].append("duplicate_packet_id")
            row_error_counts.update({"duplicate_packet_id": 1})

    semantic_packet_record_set = set(semantic_packet_record_ids)
    open_packet_record_set = set(open_packet_record_ids)
    missing_semantic_records = sorted(conflict_record_ids - semantic_packet_record_set)
    unexpected_semantic_records = sorted(semantic_packet_record_set - conflict_record_ids)
    missing_open_records = sorted(open_queue_record_ids - open_packet_record_set)
    unexpected_open_records = sorted(open_packet_record_set - open_queue_record_ids)

    global_errors: list[str] = []
    if input_errors:
        global_errors.extend(input_errors)
    if len(packets) != expected_packet_rows:
        global_errors.append(f"packet_row_count_mismatch:{len(packets)}!={expected_packet_rows}")
    if len(semantic_queue_record_ids) != expected_semantic_conflict_rows:
        global_errors.append(
            f"operator_queue_semantic_conflict_count_mismatch:{len(semantic_queue_record_ids)}!={expected_semantic_conflict_rows}"
        )
    if len(semantic_packet_record_ids) != expected_semantic_conflict_rows:
        global_errors.append(
            f"semantic_packet_record_count_mismatch:{len(semantic_packet_record_ids)}!={expected_semantic_conflict_rows}"
        )
    if len(open_packet_record_ids) != expected_open_numbering_rows:
        global_errors.append(f"open_packet_record_count_mismatch:{len(open_packet_record_ids)}!={expected_open_numbering_rows}")
    if missing_semantic_records:
        global_errors.append(f"missing_semantic_conflict_record_coverage:{len(missing_semantic_records)}")
    if unexpected_semantic_records:
        global_errors.append(f"unexpected_semantic_conflict_record_coverage:{len(unexpected_semantic_records)}")
    if duplicate_semantic_packet_records:
        global_errors.append(f"duplicate_semantic_conflict_record_coverage:{len(duplicate_semantic_packet_records)}")
    if missing_open_records:
        global_errors.append(f"missing_open_numbering_record_coverage:{len(missing_open_records)}")
    if unexpected_open_records:
        global_errors.append(f"unexpected_open_numbering_record_coverage:{len(unexpected_open_records)}")
    if duplicate_open_packet_records:
        global_errors.append(f"duplicate_open_numbering_record_coverage:{len(duplicate_open_packet_records)}")
    if set(conflict_record_ids) != semantic_queue_record_ids:
        global_errors.append("semantic_conflict_queue_operator_queue_record_mismatch")

    summary = packet_report.get("summary") if isinstance(packet_report.get("summary"), dict) else {}
    report_expectations = {
        "packet_rows": expected_packet_rows,
        "semantic_conflict_rows": expected_semantic_conflict_rows,
        "open_numbering_rows": expected_open_numbering_rows,
        "completion_ready_rows": 0,
        "requires_human_input_rows": expected_packet_rows,
        "decision_rows_written": 0,
        "curation_applied_rows": 0,
        "label_imported_rows": 0,
    }
    for field, expected in report_expectations.items():
        if summary.get(field) != expected:
            global_errors.append(f"packet_report_summary_{field}_mismatch:{summary.get(field)}!={expected}")
    for field in ("safe_for_model_claim", "release_ready", "safe_pipeline_integration_allowed", "manifest_update_allowed"):
        if packet_report.get(field) is not False:
            global_errors.append(f"packet_report_{field}_not_false")
    if packet_report.get("packet_ids") and packet_report.get("packet_ids") != packet_ids:
        global_errors.append("packet_report_packet_ids_mismatch")

    if operator_queue.get("open_numbering_rows") != expected_open_numbering_rows:
        global_errors.append(
            f"operator_queue_report_open_numbering_rows_mismatch:{operator_queue.get('open_numbering_rows')}!={expected_open_numbering_rows}"
        )
    if operator_queue.get("semantic_conflict_rows") != expected_semantic_conflict_rows:
        global_errors.append(
            f"operator_queue_report_semantic_conflict_rows_mismatch:{operator_queue.get('semantic_conflict_rows')}!={expected_semantic_conflict_rows}"
        )
    if provenance_report.get("safe_for_model_claim") is not False:
        global_errors.append("label_provenance_safe_for_model_claim_not_false")
    if int(provenance_report.get("claim_eligible_rows") or 0) != 0:
        global_errors.append("label_provenance_claim_eligible_rows_not_zero")

    status_counts = Counter(str(packet.get("status") or "") for packet in packets)
    packet_type_counts = Counter(str(packet.get("packet_type") or "") for packet in packets)
    valid_rows = sum(1 for row in status_rows if row["valid"])
    invalid_rows = len(status_rows) - valid_rows
    all_operator_packets_valid = invalid_rows == 0 and not global_errors

    coverage = {
        "expected_packet_rows": expected_packet_rows,
        "actual_packet_rows": len(packets),
        "expected_semantic_conflict_rows": expected_semantic_conflict_rows,
        "semantic_conflict_queue_rows": len(conflict_record_ids),
        "operator_queue_semantic_conflict_rows": len(semantic_queue_record_ids),
        "semantic_packet_record_rows": len(semantic_packet_record_ids),
        "semantic_conflict_records_covered": not missing_semantic_records
        and not unexpected_semantic_records
        and not duplicate_semantic_packet_records,
        "missing_semantic_conflict_record_ids": missing_semantic_records,
        "unexpected_semantic_conflict_record_ids": unexpected_semantic_records,
        "duplicate_semantic_conflict_record_ids": duplicate_semantic_packet_records,
        "expected_open_numbering_rows": expected_open_numbering_rows,
        "expected_open_packet_rows": expected_open_packet_rows,
        "operator_queue_open_numbering_rows": len(open_queue_record_ids),
        "open_packet_record_rows": len(open_packet_record_ids),
        "open_numbering_records_covered": not missing_open_records
        and not unexpected_open_records
        and not duplicate_open_packet_records,
        "missing_open_record_ids": missing_open_records,
        "unexpected_open_record_ids": unexpected_open_records,
        "duplicate_open_record_ids": duplicate_open_packet_records,
        "expected_total_covered_rows": expected_semantic_conflict_rows + expected_open_numbering_rows,
        "actual_total_covered_rows": len(semantic_packet_record_ids) + len(open_packet_record_ids),
    }

    write_jsonl(args.status_output, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "inputs": {
            "packets": rel(args.packets),
            "packet_report": rel(args.packet_report),
            "numbering_review_operator_queue": rel(args.operator_queue),
            "numbering_decision_semantic_conflict_queue": rel(args.semantic_conflict_queue),
            "label_provenance_audit_report": rel(args.label_provenance_report),
        },
        "outputs": {
            "status": rel(args.status_output),
            "report": rel(args.report),
        },
        "all_operator_packets_valid": all_operator_packets_valid,
        "invalid_rows": invalid_rows,
        "valid_rows": valid_rows,
        "operator_packet_rows": len(packets),
        "expected_operator_packet_rows": expected_packet_rows,
        "coverage": coverage,
        "packet_status_counts": dict(sorted(status_counts.items())),
        "packet_type_counts": dict(sorted(packet_type_counts.items())),
        "error_counts": dict(sorted(row_error_counts.items())),
        "global_errors": global_errors,
        "completion_ready_rows": sum(1 for packet in packets if packet.get("completion_ready") is True),
        "requires_human_input_rows": sum(1 for packet in packets if packet.get("requires_human_input") is True),
        "decision_written_by_packet_rows": sum(1 for packet in packets if packet.get("decision_written_by_packet") is True),
        "curation_apply_by_packet_rows": sum(1 for packet in packets if packet.get("curation_apply_by_packet") is True),
        "label_import_by_packet_rows": sum(1 for packet in packets if packet.get("label_import_by_packet") is True),
        "safe_for_model_claim_rows": sum(1 for packet in packets if packet.get("safe_for_model_claim") is True),
        "release_ready_rows": sum(1 for packet in packets if packet.get("release_ready") is True),
        "safe_pipeline_integration_allowed_rows": sum(
            1 for packet in packets if packet.get("safe_pipeline_integration_allowed") is True
        ),
        "manifest_update_allowed_rows": sum(1 for packet in packets if packet.get("manifest_update_allowed") is True),
        "training_unlocked_rows": sum(1 for packet in packets if packet.get("training_unlocked") is True),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Validator/status only. It validates fail-closed operator-packet integrity and coverage; "
            "it does not create curation decisions, apply curation, import labels, run training, update manifests, "
            "approve model claims, or approve release readiness."
        ),
    }
    write_json(args.report, report)
    print(
        json.dumps(
            {
                "all_operator_packets_valid": report["all_operator_packets_valid"],
                "operator_packet_rows": report["operator_packet_rows"],
                "valid_rows": report["valid_rows"],
                "invalid_rows": report["invalid_rows"],
                "global_errors": len(global_errors),
                "coverage": {
                    "semantic_conflict_rows": coverage["semantic_packet_record_rows"],
                    "open_numbering_rows": coverage["open_packet_record_rows"],
                    "packet_rows": coverage["actual_packet_rows"],
                },
                "outputs": report["outputs"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if all_operator_packets_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
