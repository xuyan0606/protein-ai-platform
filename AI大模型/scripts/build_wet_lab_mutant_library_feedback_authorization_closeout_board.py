#!/usr/bin/env python3
"""Build closeout board for wet-lab feedback authorization packet receipts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipts.jsonl"
RECEIPT_STATUS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_status.jsonl"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipt_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_closeout_board.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_board_report.json"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_closeout_board.md"


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


def required_closeout_items(receipt: dict[str, Any]) -> list[str]:
    items = []
    metric_rows = int(receipt.get("metric_receipt_rows") or 0)
    decision_rows = int(receipt.get("decision_rows_present") or 0)
    authorized_rows = int(receipt.get("authorized_rows") or 0)
    preflight_rows = int(receipt.get("preflight_rows_present") or 0)
    if decision_rows < metric_rows:
        items.append("append_reviewed_authorization_decisions_for_all_metric_rows")
    if authorized_rows < metric_rows:
        items.append("pass_authorization_validator_for_approved_metric_rows")
    if preflight_rows < metric_rows:
        items.append("run_downstream_preflight_after_valid_authorization")
    items.extend([
        "rerun_packet_receipt_validator",
        "rerun_safe_training_pipeline",
    ])
    return items


def build_board(receipts: list[dict[str, Any]], receipt_status: list[dict[str, Any]], receipt_validation: dict[str, Any]) -> list[dict[str, Any]]:
    status_lookup = status_by_variant(receipt_status)
    rows: list[dict[str, Any]] = []
    for receipt in sorted(receipts, key=lambda row: int(row.get("execution_order") or 10**9)):
        variant = str(receipt.get("variant") or "")
        status = status_lookup.get(variant, {})
        metric_rows = int(receipt.get("metric_receipt_rows") or 0)
        decision_rows = int(receipt.get("decision_rows_present") or 0)
        authorized_rows = int(receipt.get("authorized_rows") or 0)
        preflight_rows = int(receipt.get("preflight_rows_present") or 0)
        rows.append({
            "closeout_board_id": f"wetlab-mutlib-auth-closeout-{variant.lower()}",
            "operator_packet_receipt_id": receipt.get("operator_packet_receipt_id"),
            "operator_packet_id": receipt.get("operator_packet_id"),
            "execution_order": receipt.get("execution_order"),
            "variant": variant,
            "packet_mode": receipt.get("packet_mode"),
            "receipt_status": receipt.get("receipt_status"),
            "receipt_row_valid": bool(status.get("valid")),
            "receipt_validation_all_rows_valid": bool(receipt_validation.get("all_operator_packet_receipts_valid")),
            "metric_receipt_rows": metric_rows,
            "decision_rows_present": decision_rows,
            "missing_decision_rows": max(metric_rows - decision_rows, 0),
            "authorized_rows": authorized_rows,
            "missing_authorized_rows": max(metric_rows - authorized_rows, 0),
            "preflight_rows_present": preflight_rows,
            "missing_preflight_rows": max(metric_rows - preflight_rows, 0),
            "feedback_candidate_ids": receipt.get("feedback_candidate_ids") or [],
            "required_closeout_items": required_closeout_items(receipt),
            "operator_open_first": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
            "write_reviewed_decisions_to": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "authorization_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "receipt_validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipts.py",
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "closeout_status": "open_blocked_waiting_for_human_authorization",
            "completion_condition": "all metric decisions are reviewed, authorization validator passes, preflight rows exist, and safe pipeline passes; closeout board alone is never sufficient",
            "requires_human_input": True,
            "completion_ready": False,
            "ready_for_feedback_intake": False,
            "safe_for_model_claim": False,
            "policy": "Authorization closeout board only; not an authorization, not feedback preflight, not a training label, and not model claim readiness.",
        })
    return rows


def build_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Wet-lab Feedback Authorization Closeout Board",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This board is local operator tracking only. It is not an authorization, not feedback preflight, not a training label, and not model claim readiness.",
        "",
        "| Order | Variant | Mode | Metrics | Decisions Missing | Authorized Missing | Preflight Missing | Status |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('execution_order')} | {row.get('variant')} | {row.get('packet_mode')} | "
            f"{row.get('metric_receipt_rows')} | {row.get('missing_decision_rows')} | "
            f"{row.get('missing_authorized_rows')} | {row.get('missing_preflight_rows')} | {row.get('closeout_status')} |"
        )
    lines.extend([
        "",
        "## Commands",
        "",
        "1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py`",
        "1. `python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py`",
        "1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_execution_queue_operator_packet_receipts.py`",
        "1. `python3 scripts/run_safe_training_pipeline.py`",
        "",
        "## Policy",
        "",
        report["policy"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization closeout board")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--receipt-status", type=Path, default=RECEIPT_STATUS)
    parser.add_argument("--receipt-validation", type=Path, default=RECEIPT_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    args = parser.parse_args()

    receipts = load_jsonl(args.receipts)
    receipt_status = load_jsonl(args.receipt_status)
    receipt_validation = load_json(args.receipt_validation)
    rows = build_board(receipts, receipt_status, receipt_validation)
    write_jsonl(args.output, rows)

    status_counts = Counter(str(row.get("closeout_status") or "") for row in rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "closeout_board_rows": len(rows),
        "operator_packet_receipt_rows": len(receipts),
        "receipt_validation_all_rows_valid": bool(receipt_validation.get("all_operator_packet_receipts_valid")),
        "receipt_row_valid_closeout_rows": sum(1 for row in rows if row.get("receipt_row_valid") is True),
        "metric_receipt_rows": sum(int(row.get("metric_receipt_rows") or 0) for row in rows),
        "decision_rows_present": sum(int(row.get("decision_rows_present") or 0) for row in rows),
        "missing_decision_rows": sum(int(row.get("missing_decision_rows") or 0) for row in rows),
        "authorized_rows": sum(int(row.get("authorized_rows") or 0) for row in rows),
        "missing_authorized_rows": sum(int(row.get("missing_authorized_rows") or 0) for row in rows),
        "preflight_rows_present": sum(int(row.get("preflight_rows_present") or 0) for row in rows),
        "missing_preflight_rows": sum(int(row.get("missing_preflight_rows") or 0) for row in rows),
        "open_blocked_closeout_rows": status_counts.get("open_blocked_waiting_for_human_authorization", 0),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "review_order": [row.get("variant") for row in rows],
        "closeout_status_counts": dict(sorted(status_counts.items())),
        "output": str(args.output),
        "markdown": str(args.markdown),
        "policy": "Authorization closeout board tracks missing human decisions only; it never grants authorization, writes preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(build_markdown(report, rows), encoding="utf-8")
    print(json.dumps({
        "closeout_board_rows": report["closeout_board_rows"],
        "missing_decision_rows": report["missing_decision_rows"],
        "open_blocked_closeout_rows": report["open_blocked_closeout_rows"],
        "review_order": report["review_order"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
