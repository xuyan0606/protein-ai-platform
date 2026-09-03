#!/usr/bin/env python3
"""Build operator packets from validated wet-lab feedback authorization execution queue."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue.jsonl"
QUEUE_STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_status.jsonl"
QUEUE_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packets.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_report.json"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packets.md"

PACKET_MODES = {
    "E331Q": "critical_tradeoff_bundle_review",
    "D105N": "mixed_positive_candidate_bundle_review",
    "S265T": "watch_only_bundle_review",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def status_by_variant(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("variant") or ""): row
        for row in rows
        if row.get("variant")
    }


def review_focus(row: dict[str, Any]) -> list[str]:
    modes = row.get("review_mode_counts") or {}
    if modes.get("tradeoff_review_required"):
        return [
            "Review all E331Q metrics together before any metric-level decision.",
            "Do not convert acid-retention benefit into a single go label while thermal stability is no_go.",
            "Record tradeoff rationale, residual risks, and whether each metric remains separate evidence.",
        ]
    if modes.get("positive_candidate_review_required"):
        return [
            "Review source trace, numbering, units/conditions, batch/control, and replicate/QC for each positive metric.",
            "Keep the watch metric separate unless reviewer basis explicitly supports intake.",
            "Authorize only metric rows that remain defensible after QC review.",
        ]
    return [
        "Review watch-only metrics for uncertainty and missing evidence.",
        "Use needs_more_info unless reviewer can justify a reviewed evidence decision.",
        "Do not promote watch-only evidence into a go/no-go training label without explicit basis.",
    ]


def build_packets(queue_rows: list[dict[str, Any]], status_rows: list[dict[str, Any]], queue_validation: dict[str, Any]) -> list[dict[str, Any]]:
    status_lookup = status_by_variant(status_rows)
    packets: list[dict[str, Any]] = []
    for order, row in enumerate(queue_rows, start=1):
        variant = str(row.get("variant") or "")
        status = status_lookup.get(variant, {})
        packets.append({
            "operator_packet_id": f"wetlab-mutlib-auth-exec-packet-{variant.lower()}",
            "execution_queue_id": row.get("execution_queue_id"),
            "execution_order": order,
            "variant": variant,
            "packet_mode": PACKET_MODES.get(variant, "variant_bundle_review"),
            "packet_status": "open_blocked_waiting_for_human_authorization",
            "queue_row_valid": bool(status.get("valid")),
            "queue_validation_all_rows_valid": bool(queue_validation.get("all_queue_rows_valid")),
            "metric_receipt_rows": row.get("metric_receipt_rows"),
            "review_mode_counts": row.get("review_mode_counts") or {},
            "receipt_status_counts": row.get("receipt_status_counts") or {},
            "metric_receipts": row.get("metric_receipts") or [],
            "decision_present_rows": row.get("decision_present_rows"),
            "authorized_rows": row.get("authorized_rows"),
            "preflight_present_rows": row.get("preflight_present_rows"),
            "review_focus": review_focus(row),
            "operator_open_first": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
            "write_reviewed_decisions_to": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "required_review_fields": [
                "authorization_decision",
                "qc_decision",
                "reviewer",
                "reviewed_at",
                "authorization_basis",
                "source_trace_reviewed",
                "numbering_reviewed",
                "unit_condition_reviewed",
                "batch_control_reviewed",
                "replicate_policy_reviewed",
                "residual_risks",
            ],
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "queue_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_execution_queue.py",
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "completion_condition": "reviewed metric authorization decisions validate, preflight rows are generated downstream, and execution packet status is revalidated; packet alone is never sufficient",
            "requires_human_input": True,
            "completion_ready": False,
            "policy": "Execution queue operator packet only; not an authorization, not feedback preflight, not a training label, and not model claim readiness.",
        })
    return packets


def build_markdown(report: dict[str, Any], packets: list[dict[str, Any]]) -> str:
    lines = [
        "# Wet-lab Feedback Authorization Execution Queue Operator Packets",
        "",
        f"Generated: {report['created_at']}",
        "",
        "These packets are local operator navigation only. They are not authorizations, not feedback preflight, not training labels, and not model claim readiness.",
        "",
        "| Order | Variant | Mode | Metrics | Queue valid | Authorized | Preflight | Status |",
        "|---:|---|---|---:|---|---:|---:|---|",
    ]
    for packet in packets:
        lines.append(
            f"| {packet.get('execution_order')} | {packet.get('variant')} | {packet.get('packet_mode')} | "
            f"{packet.get('metric_receipt_rows')} | {packet.get('queue_row_valid')} | "
            f"{packet.get('authorized_rows')} | {packet.get('preflight_present_rows')} | {packet.get('packet_status')} |"
        )
    lines.extend([
        "",
        "## Review Order",
        "",
    ])
    for packet in packets:
        lines.append(f"{packet.get('execution_order')}. {packet.get('variant')}: {packet.get('packet_mode')}")
    lines.extend([
        "",
        "## Commands",
        "",
        "1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py`",
        "1. `python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py`",
        "1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_execution_queue.py`",
        "1. `python3 scripts/run_safe_training_pipeline.py`",
        "",
        "## Policy",
        "",
        report["policy"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization execution queue operator packets")
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--queue-status", type=Path, default=QUEUE_STATUS)
    parser.add_argument("--queue-validation", type=Path, default=QUEUE_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    args = parser.parse_args()

    queue_rows = load_jsonl(args.queue)
    status_rows = load_jsonl(args.queue_status)
    queue_validation = load_json(args.queue_validation)
    packets = build_packets(queue_rows, status_rows, queue_validation)
    write_jsonl(args.output, packets)

    status_counts = Counter(str(row.get("packet_status") or "") for row in packets)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "operator_packet_rows": len(packets),
        "execution_queue_rows": len(queue_rows),
        "queue_validation_all_rows_valid": bool(queue_validation.get("all_queue_rows_valid")),
        "queue_row_valid_packets": sum(1 for row in packets if row.get("queue_row_valid") is True),
        "open_blocked_packet_rows": status_counts.get("open_blocked_waiting_for_human_authorization", 0),
        "decision_present_rows": sum(int(row.get("decision_present_rows") or 0) for row in packets),
        "authorized_rows": sum(int(row.get("authorized_rows") or 0) for row in packets),
        "preflight_present_rows": sum(int(row.get("preflight_present_rows") or 0) for row in packets),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(packets),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "review_order": [row.get("variant") for row in packets],
        "packet_status_counts": dict(sorted(status_counts.items())),
        "output": str(args.output),
        "markdown": str(args.markdown),
        "policy": "Execution queue operator packets guide human review only; they never grant authorization, write preflight, append labels, or enable model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(build_markdown(report, packets), encoding="utf-8")
    print(json.dumps({
        "operator_packet_rows": report["operator_packet_rows"],
        "open_blocked_packet_rows": report["open_blocked_packet_rows"],
        "review_order": report["review_order"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
