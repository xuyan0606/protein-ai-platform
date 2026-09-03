#!/usr/bin/env python3
"""Validate the ready-to-verify promotion board against live source facts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import build_ready_to_verify_promotion_board as contract


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "ready_to_verify_promotion_board.json"
OUTPUT = AI_ROOT / "reports" / "ready_to_verify_promotion_validation_report.json"

FALSE_FLAGS = (
    "automatic_promotion_allowed",
    "workstream_completion_ready",
    "execution_ready",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ready-to-verify promotion board")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    board = load_json(args.board)
    rows = [row for row in board.get("rows") or [] if isinstance(row, dict)]
    expected_rows = contract.build_rows()
    expected_by_id = {row["audit_id"]: row for row in expected_rows}
    actual_ids = [str(row.get("audit_id") or "") for row in rows]
    failures: list[dict[str, Any]] = []

    if set(actual_ids) != contract.EXPECTED_IDS:
        failures.append({"check": "audit_ids_exact", "expected": sorted(contract.EXPECTED_IDS), "actual": sorted(set(actual_ids))})
    duplicates = sorted({audit_id for audit_id in actual_ids if actual_ids.count(audit_id) > 1})
    if duplicates:
        failures.append({"check": "audit_ids_unique", "duplicates": duplicates})

    for row in rows:
        audit_id = str(row.get("audit_id") or "")
        expected = expected_by_id.get(audit_id)
        row_failures: list[str] = []
        if expected is None:
            row_failures.append("unexpected_audit_id")
        else:
            for field in (
                "scope",
                "workstream_id",
                "receipt_valid",
                "completion_checks",
                "context",
                "local_artifact_completion_checks_met",
                "promotion_status",
                "remaining_blockers",
                "selected_variant_rows",
            ):
                if row.get(field) != expected.get(field):
                    row_failures.append(f"{field}_source_parity")
        for field in FALSE_FLAGS:
            if row.get(field) is not False:
                row_failures.append(f"{field}_must_be_false")
        if row.get("selected_variant_rows") != 0:
            row_failures.append("selected_variant_rows_zero")
        if row_failures:
            failures.append({"check": "row_semantics", "audit_id": audit_id, "failures": row_failures})

    expected_report = contract.build_report()
    summary_fields = (
        "audit_rows",
        "receipt_valid_rows",
        "local_artifact_completion_rows",
        "verified_blocked_rows",
        "automatic_promotion_rows",
        "workstream_completion_ready_rows",
        "execution_ready_rows",
        "safe_for_training_import_rows",
        "safe_for_model_claim_rows",
        "customer_delivery_ready_rows",
        "release_ready_rows",
        "selected_variant_rows",
    )
    for field in summary_fields:
        if board.get(field) != expected_report.get(field):
            failures.append({"check": f"summary.{field}_source_parity", "expected": expected_report.get(field), "actual": board.get(field)})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "audit_rows": len(rows),
        "valid_rows": len(rows) - sum(item.get("check") == "row_semantics" for item in failures),
        "local_artifact_completion_rows": expected_report["local_artifact_completion_rows"],
        "verified_blocked_rows": expected_report["verified_blocked_rows"],
        "automatic_promotion_rows": 0,
        "failure_count": len(failures),
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation recomputes every promotion row from live receipts and source reports; positive downstream flags fail closed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "audit_rows": report["audit_rows"],
        "local_artifact_completion_rows": report["local_artifact_completion_rows"],
        "verified_blocked_rows": report["verified_blocked_rows"],
        "failure_count": report["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
