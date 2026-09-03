#!/usr/bin/env python3
"""Build variant-level execution queue for wet-lab feedback authorization review."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_operator_receipts.jsonl"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_operator_receipt_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_execution_queue.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue_report.json"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_execution_queue.md"

MODE_ORDER = {
    "tradeoff_review_required": 0,
    "positive_candidate_review_required": 1,
    "watch_candidate_review_required": 2,
    "negative_candidate_review_required": 3,
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


def variant_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    modes = item.get("review_mode_counts") or {}
    top = min((MODE_ORDER.get(str(mode), 99) for mode, count in modes.items() if count), default=99)
    return (top, str(item.get("variant") or ""))


def next_action(mode_counts: Counter[str]) -> str:
    if mode_counts.get("tradeoff_review_required", 0):
        return "Review the full variant tradeoff as one bundle before any metric-level authorization decision."
    if mode_counts.get("positive_candidate_review_required", 0):
        return "Review positive candidate metrics after source trace, numbering, unit/condition, batch/control, and replicate/QC checks."
    return "Review watch metrics and decide whether each should remain needs_more_info or become reviewed evidence."


def build_queue(receipts: list[dict[str, Any]], receipt_validation: dict[str, Any]) -> list[dict[str, Any]]:
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for receipt in receipts:
        by_variant[str(receipt.get("variant") or "")].append(receipt)

    rows: list[dict[str, Any]] = []
    for variant, variant_receipts in by_variant.items():
        mode_counts = Counter(str(row.get("review_mode") or "") for row in variant_receipts)
        status_counts = Counter(str(row.get("receipt_status") or "") for row in variant_receipts)
        rows.append({
            "execution_queue_id": f"wetlab-mutlib-auth-exec-{variant.lower()}",
            "variant": variant,
            "metric_receipt_rows": len(variant_receipts),
            "review_mode_counts": dict(sorted(mode_counts.items())),
            "receipt_status_counts": dict(sorted(status_counts.items())),
            "open_blocked_receipt_rows": status_counts.get("open_blocked_no_authorization_decision", 0),
            "decision_present_rows": sum(1 for row in variant_receipts if row.get("decision_row_present") is True),
            "authorized_rows": sum(1 for row in variant_receipts if row.get("authorized_for_feedback_intake") is True),
            "preflight_present_rows": sum(1 for row in variant_receipts if row.get("preflight_row_present") is True),
            "receipt_validation_all_rows_valid": bool(receipt_validation.get("all_receipt_rows_valid")),
            "queue_status": "open_blocked_waiting_for_human_authorization",
            "next_action_summary": next_action(mode_counts),
            "operator_open_first": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.template.jsonl",
            "write_reviewed_decisions_to": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "validator_command": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "preflight_command": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "safe_pipeline_command": "python3 scripts/run_safe_training_pipeline.py",
            "metric_receipts": [
                {
                    "operator_receipt_id": row.get("operator_receipt_id"),
                    "feedback_candidate_id": row.get("feedback_candidate_id"),
                    "metric_name": row.get("metric_name"),
                    "review_mode": row.get("review_mode"),
                    "receipt_status": row.get("receipt_status"),
                    "decision_row_present": row.get("decision_row_present"),
                    "preflight_row_present": row.get("preflight_row_present"),
                }
                for row in sorted(variant_receipts, key=lambda item: str(item.get("metric_name") or ""))
            ],
            "completion_condition": "all metric authorization decisions validate and downstream preflight is generated; execution queue alone is never sufficient",
            "requires_human_input": True,
            "completion_ready": False,
            "policy": "Execution queue only; not an authorization, not feedback preflight, and not a training label.",
        })
    return sorted(rows, key=variant_sort_key)


def build_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Wet-lab Feedback Authorization Execution Queue",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This queue is local operator navigation only. It is not an authorization, not feedback preflight, and not a training label.",
        "",
        "| Order | Variant | Metrics | Modes | Receipt status | Authorized | Preflight | Status |",
        "|---:|---|---:|---|---|---:|---:|---|",
    ]
    for idx, row in enumerate(rows, start=1):
        modes = ", ".join(f"{key}:{value}" for key, value in (row.get("review_mode_counts") or {}).items())
        statuses = ", ".join(f"{key}:{value}" for key, value in (row.get("receipt_status_counts") or {}).items())
        lines.append(
            f"| {idx} | {row.get('variant')} | {row.get('metric_receipt_rows')} | {modes} | "
            f"{statuses} | {row.get('authorized_rows')} | {row.get('preflight_present_rows')} | {row.get('queue_status')} |"
        )
    lines.extend([
        "",
        "## Commands",
        "",
        "1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py`",
        "1. `python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py`",
        "1. `python3 scripts/run_safe_training_pipeline.py`",
        "",
        "## Policy",
        "",
        report["policy"],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization execution queue")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--receipt-validation", type=Path, default=RECEIPT_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    args = parser.parse_args()

    receipts = load_jsonl(args.receipts)
    receipt_validation = load_json(args.receipt_validation)
    rows = build_queue(receipts, receipt_validation)
    write_jsonl(args.output, rows)

    status_counts = Counter(str(row.get("queue_status") or "") for row in rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "execution_queue_rows": len(rows),
        "operator_receipt_rows": len(receipts),
        "receipt_validation_all_rows_valid": bool(receipt_validation.get("all_receipt_rows_valid")),
        "open_blocked_queue_rows": status_counts.get("open_blocked_waiting_for_human_authorization", 0),
        "tradeoff_queue_rows": sum(1 for row in rows if (row.get("review_mode_counts") or {}).get("tradeoff_review_required")),
        "decision_present_rows": sum(int(row.get("decision_present_rows") or 0) for row in rows),
        "authorized_rows": sum(int(row.get("authorized_rows") or 0) for row in rows),
        "preflight_present_rows": sum(int(row.get("preflight_present_rows") or 0) for row in rows),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(rows),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "review_order": [row["variant"] for row in rows],
        "status_counts": dict(sorted(status_counts.items())),
        "output": str(args.output),
        "markdown": str(args.markdown),
        "policy": "Execution queue guides human review only; it never grants authorization, writes preflight, appends labels, or enables model claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(build_markdown(report, rows), encoding="utf-8")
    print(json.dumps({
        "execution_queue_rows": report["execution_queue_rows"],
        "open_blocked_queue_rows": report["open_blocked_queue_rows"],
        "review_order": report["review_order"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
