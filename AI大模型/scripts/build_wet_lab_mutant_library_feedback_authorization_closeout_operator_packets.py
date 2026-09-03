#!/usr/bin/env python3
"""Build operator packets from wet-lab feedback authorization closeout board."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CLOSEOUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_closeout_board.jsonl"
CLOSEOUT_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_board_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_closeout_operator_packets.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_report.json"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_operator_packets.md"

MODE_BY_VARIANT = {
    "E331Q": "tradeoff_closeout_review",
    "D105N": "positive_candidate_closeout_review",
    "S265T": "watch_only_closeout_review",
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


def packet_focus(row: dict[str, Any]) -> list[str]:
    missing_decisions = int(row.get("missing_decision_rows") or 0)
    missing_authorized = int(row.get("missing_authorized_rows") or 0)
    missing_preflight = int(row.get("missing_preflight_rows") or 0)
    items = []
    if missing_decisions:
        items.append("Collect reviewed authorization decisions for all metric rows.")
    if missing_authorized:
        items.append("Keep authorization validator closed until reviewed decisions exist.")
    if missing_preflight:
        items.append("Run downstream preflight only after authorization rows validate.")
    items.append("Re-run closeout board validator after any human decision input.")
    return items


def build_packets(closeout_rows: list[dict[str, Any]], closeout_validation: dict[str, Any]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for order, row in enumerate(sorted(closeout_rows, key=lambda item: int(item.get("execution_order") or 10**9)), start=1):
        variant = str(row.get("variant") or "")
        packets.append({
            "closeout_operator_packet_id": f"wetlab-mutlib-auth-closeout-packet-{variant.lower()}",
            "closeout_board_id": row.get("closeout_board_id"),
            "operator_packet_order": order,
            "variant": variant,
            "packet_mode": MODE_BY_VARIANT.get(variant, "closeout_review"),
            "packet_status": "open_blocked_waiting_for_human_authorization",
            "closeout_row_valid": bool(row.get("receipt_row_valid")),
            "closeout_validation_all_rows_valid": bool(closeout_validation.get("all_closeout_rows_valid")),
            "metric_receipt_rows": row.get("metric_receipt_rows"),
            "missing_decision_rows": row.get("missing_decision_rows"),
            "missing_authorized_rows": row.get("missing_authorized_rows"),
            "missing_preflight_rows": row.get("missing_preflight_rows"),
            "decision_rows_present": row.get("decision_rows_present"),
            "authorized_rows": row.get("authorized_rows"),
            "preflight_rows_present": row.get("preflight_rows_present"),
            "required_closeout_items": row.get("required_closeout_items") or [],
            "packet_focus": packet_focus(row),
            "operator_open_first": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
            "write_reviewed_decisions_to": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "authorization_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "closeout_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_closeout_board.py",
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "completion_condition": "all reviewed authorization decisions validate, preflight rows exist, and closeout board revalidates; closeout packet alone is never sufficient",
            "requires_human_input": True,
            "completion_ready": False,
            "ready_for_feedback_intake": False,
            "safe_for_model_claim": False,
            "policy": "Closeout operator packet only; not an authorization, not feedback preflight, not a training label, and not model claim readiness.",
        })
    return packets


def build_markdown(report: dict[str, Any], packets: list[dict[str, Any]]) -> str:
    lines = [
        "# Wet-lab Feedback Authorization Closeout Operator Packets",
        "",
        f"Generated: {report['created_at']}",
        "",
        "These packets are local operator navigation only. They are not an authorization, not feedback preflight, not a training label, and not model claim readiness.",
        "",
        "| Order | Variant | Mode | Metrics | Missing decisions | Missing preflight | Status |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    for packet in packets:
        lines.append(
            f"| {packet.get('operator_packet_order')} | {packet.get('variant')} | {packet.get('packet_mode')} | "
            f"{packet.get('metric_receipt_rows')} | {packet.get('missing_decision_rows')} | "
            f"{packet.get('missing_preflight_rows')} | {packet.get('packet_status')} |"
        )
    lines.extend([
        "",
        "## Commands",
        "",
        "1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py`",
        "1. `python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py`",
        "1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_closeout_board.py`",
        "1. `python3 scripts/run_safe_training_pipeline.py`",
        "",
        "## Policy",
        "",
        report["policy"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization closeout operator packets")
    parser.add_argument("--closeout", type=Path, default=CLOSEOUT)
    parser.add_argument("--closeout-validation", type=Path, default=CLOSEOUT_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    args = parser.parse_args()

    closeout_rows = load_jsonl(args.closeout)
    closeout_validation = load_json(args.closeout_validation)
    packets = build_packets(closeout_rows, closeout_validation)
    write_jsonl(args.output, packets)

    status_counts = Counter(str(row.get("packet_status") or "") for row in packets)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "closeout_operator_packet_rows": len(packets),
        "closeout_board_rows": len(closeout_rows),
        "closeout_validation_all_rows_valid": bool(closeout_validation.get("all_closeout_rows_valid")),
        "open_blocked_packet_rows": status_counts.get("open_blocked_waiting_for_human_authorization", 0),
        "decision_rows_present": sum(int(row.get("decision_rows_present") or 0) for row in packets),
        "authorized_rows": sum(int(row.get("authorized_rows") or 0) for row in packets),
        "preflight_rows_present": sum(int(row.get("preflight_rows_present") or 0) for row in packets),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(packets),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "review_order": [row.get("variant") for row in packets],
        "packet_status_counts": dict(sorted(status_counts.items())),
        "output": str(args.output),
        "markdown": str(args.markdown),
        "policy": "Closeout operator packets guide human review only; they never grant authorization, write preflight, append labels, or enable model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(build_markdown(report, packets), encoding="utf-8")
    print(json.dumps({
        "closeout_operator_packet_rows": report["closeout_operator_packet_rows"],
        "open_blocked_packet_rows": report["open_blocked_packet_rows"],
        "review_order": report["review_order"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
