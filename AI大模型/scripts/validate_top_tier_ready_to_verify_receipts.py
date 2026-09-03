#!/usr/bin/env python3
"""Validate top-tier ready-to-verify receipts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "top_tier_model_execution_board.json"
RECEIPTS = AI_ROOT / "datasets" / "governance" / "top_tier_model_ready_to_verify_receipts.jsonl"
STATUS_OUT = AI_ROOT / "datasets" / "governance" / "top_tier_model_ready_to_verify_receipt_status.jsonl"
REPORT = AI_ROOT / "reports" / "top_tier_model_ready_to_verify_receipt_report.json"
OUT = AI_ROOT / "reports" / "top_tier_model_ready_to_verify_receipt_validation_report.json"

ALLOWED_READY_IDS = {
    "cross_rosetta_foldx_ddg_backend",
    "p0_kwb_wet_lab_feedback",
    "p0_reviewed_structure_graph",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate top-tier ready-to-verify receipts")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--receipt-report", type=Path, default=REPORT)
    parser.add_argument("--status-output", type=Path, default=STATUS_OUT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    board = load_json(args.board)
    receipt_report = load_json(args.receipt_report)
    receipts = load_jsonl(args.receipts)
    now = datetime.now(timezone.utc).isoformat()
    failures: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []

    board_rows = [row for row in board.get("rows", []) if isinstance(row, dict)]
    board_ready_ids = {str(row.get("workstream_id")) for row in board_rows if row.get("status") == "started_ready_to_verify"}
    board_blocked_ids = {str(row.get("workstream_id")) for row in board_rows if row.get("status") == "started_blocked"}
    receipt_ids = [str(row.get("workstream_id")) for row in receipts]
    receipt_id_set = set(receipt_ids)

    unexpected_board_ready = board_ready_ids - ALLOWED_READY_IDS
    if unexpected_board_ready:
        failures.append({"check": "board_ready_ids_within_allowlist", "allowed": sorted(ALLOWED_READY_IDS), "unexpected": sorted(unexpected_board_ready)})
    if receipt_id_set != board_ready_ids:
        failures.append({"check": "receipt_ids_match_board_ready_ids", "expected": sorted(board_ready_ids), "actual": sorted(receipt_id_set)})
    duplicate_ids = sorted({workstream_id for workstream_id in receipt_ids if receipt_ids.count(workstream_id) > 1})
    if duplicate_ids:
        failures.append({"check": "no_duplicate_receipts", "duplicates": duplicate_ids})
    if receipt_id_set & board_blocked_ids:
        failures.append({"check": "no_blocked_workstream_receipts", "blocked_receipts": sorted(receipt_id_set & board_blocked_ids)})
    if receipt_report.get("safe_for_training_import") is not False:
        failures.append({"check": "receipt_report_safe_for_training_import_false"})
    if receipt_report.get("safe_for_model_claim") is not False:
        failures.append({"check": "receipt_report_safe_for_model_claim_false"})
    if receipt_report.get("release_ready") is not False:
        failures.append({"check": "receipt_report_release_ready_false"})
    if receipt_report.get("blocked_workstreams_not_executed") is not True:
        failures.append({"check": "blocked_workstreams_not_executed"})

    for row in receipts:
        workstream_id = str(row.get("workstream_id"))
        row_failures: list[str] = []
        command_results = row.get("command_results") or []
        evidence = row.get("evidence") or {}
        checks = evidence.get("checks") or {}
        if workstream_id not in ALLOWED_READY_IDS:
            row_failures.append("workstream_not_in_allowlist")
        if row.get("source_status") != "started_ready_to_verify":
            row_failures.append("source_status_not_ready_to_verify")
        if row.get("verification_status") != "verification_passed":
            row_failures.append("verification_status_not_passed")
        if not command_results:
            row_failures.append("missing_command_results")
        if any(result.get("returncode") != 0 or not result.get("ok") for result in command_results if isinstance(result, dict)):
            row_failures.append("command_failure_present")
        if not checks or any(value is not True for value in checks.values()):
            row_failures.append("evidence_check_not_all_true")
        if row.get("completion_ready") is not False:
            row_failures.append("completion_ready_must_remain_false")
        if row.get("safe_for_training_import") is not False:
            row_failures.append("safe_for_training_import_must_remain_false")
        if row.get("safe_for_model_claim") is not False:
            row_failures.append("safe_for_model_claim_must_remain_false")
        if row.get("release_ready") is not False:
            row_failures.append("release_ready_must_remain_false")
        if row.get("blocked_lanes_executed") is not False:
            row_failures.append("blocked_lanes_executed_must_be_false")
        if row_failures:
            failures.append({"check": "receipt_row_semantics", "workstream_id": workstream_id, "failures": row_failures})
        status_rows.append({
            "created_at": now,
            "local_only": True,
            "workstream_id": workstream_id,
            "receipt_valid": not row_failures,
            "verification_status": row.get("verification_status"),
            "commands_ok": row.get("commands_ok"),
            "evidence_ok": row.get("evidence_ok"),
            "completion_ready": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Valid top-tier receipt means local evidence was verified for this allowed lane only; blocked lanes and model-quality claim remain closed.",
        })

    valid_rows = sum(1 for row in status_rows if row.get("receipt_valid"))
    report = {
        "created_at": now,
        "local_only": True,
        "receipt_rows": len(receipts),
        "expected_receipt_rows": len(board_ready_ids),
        "valid_receipt_rows": valid_rows,
        "invalid_receipt_rows": len(status_rows) - valid_rows,
        "board_ready_to_verify_workstreams": len(board_ready_ids),
        "board_blocked_workstreams": len(board_blocked_ids),
        "blocked_workstreams_not_executed": receipt_report.get("blocked_workstreams_not_executed") is True and not (receipt_id_set & board_blocked_ids),
        "verification_passed_workstreams": sum(1 for row in receipts if row.get("verification_status") == "verification_passed"),
        "failed_checks": len(failures),
        "success": not failures,
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation accepts current top-tier board ready-to-verify lanes only when they are within the allowlist, and explicitly keeps training, model-quality and release gates closed.",
    }
    write_jsonl(args.status_output, status_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "valid_receipt_rows": valid_rows,
        "invalid_receipt_rows": report["invalid_receipt_rows"],
        "failed_checks": report["failed_checks"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
