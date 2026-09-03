#!/usr/bin/env python3
"""Validate operator receipt summaries against the local release manifest."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT_REPORT = AI_ROOT / "reports" / "next_unlock_operator_work_receipt_report.json"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "next_unlock_operator_work_receipt_validation_report.json"
MANIFEST = AI_ROOT / "reports" / "local_release_manifest.json"
OUT = AI_ROOT / "reports" / "operator_work_receipt_manifest_consistency_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def check(name: str, passed: bool, observed: Any = None, expected: Any = None) -> dict[str, Any]:
    row: dict[str, Any] = {"name": name, "passed": bool(passed)}
    if observed is not None:
        row["observed"] = observed
    if expected is not None:
        row["expected"] = expected
    return row


def matching_check(name: str, validation: dict[str, Any], readiness: dict[str, Any], validation_key: str, manifest_key: str) -> dict[str, Any]:
    return check(
        name,
        validation.get(validation_key) == readiness.get(manifest_key),
        {"validation": validation.get(validation_key), "manifest": readiness.get(manifest_key)},
        "same",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate operator receipt manifest consistency")
    parser.add_argument("--report", type=Path, default=OUT)
    args = parser.parse_args()

    receipt = load_json(RECEIPT_REPORT)
    validation = load_json(RECEIPT_VALIDATION)
    manifest = load_json(MANIFEST)
    readiness = manifest.get("readiness_summary") or {}
    checks = [
        check("receipt validation success", validation.get("invalid_receipt_rows") == 0, validation.get("invalid_receipt_rows"), 0),
        check("receipt rows match", receipt.get("receipt_rows") == readiness.get("next_unlock_operator_work_receipt_rows"), {"receipt": receipt.get("receipt_rows"), "manifest": readiness.get("next_unlock_operator_work_receipt_rows")}, "same"),
        check("open blocked rows match", receipt.get("open_blocked_receipt_rows") == readiness.get("next_unlock_operator_work_receipt_open_blocked_rows"), {"receipt": receipt.get("open_blocked_receipt_rows"), "manifest": readiness.get("next_unlock_operator_work_receipt_open_blocked_rows")}, "same"),
        check("completion-ready rows match", receipt.get("completion_ready_items") == readiness.get("next_unlock_operator_work_receipt_completion_ready_items"), {"receipt": receipt.get("completion_ready_items"), "manifest": readiness.get("next_unlock_operator_work_receipt_completion_ready_items")}, "same"),
        check("human input rows match", receipt.get("requires_human_input_items") == readiness.get("next_unlock_operator_work_receipt_requires_human_input_items"), {"receipt": receipt.get("requires_human_input_items"), "manifest": readiness.get("next_unlock_operator_work_receipt_requires_human_input_items")}, "same"),
        check("observed decision rows match", receipt.get("observed_decision_input_rows") == readiness.get("next_unlock_operator_work_receipt_observed_decision_input_rows"), {"receipt": receipt.get("observed_decision_input_rows"), "manifest": readiness.get("next_unlock_operator_work_receipt_observed_decision_input_rows")}, "same"),
        check("target rows met match", receipt.get("target_rows_met_items") == readiness.get("next_unlock_operator_work_receipt_target_rows_met_items"), {"receipt": receipt.get("target_rows_met_items"), "manifest": readiness.get("next_unlock_operator_work_receipt_target_rows_met_items")}, "same"),
        matching_check("validated receipt rows match", validation, readiness, "validated_receipt_rows", "next_unlock_operator_work_receipt_validated_rows"),
        matching_check("invalid receipt rows match", validation, readiness, "invalid_receipt_rows", "next_unlock_operator_work_receipt_invalid_rows"),
        matching_check("validation completion-ready items match", validation, readiness, "completion_ready_items", "next_unlock_operator_work_receipt_validation_completion_ready_items"),
        matching_check("validation target rows met items match", validation, readiness, "target_rows_met_items", "next_unlock_operator_work_receipt_validation_target_rows_met_items"),
        matching_check("validation target rows met completion-ready items match", validation, readiness, "target_rows_met_completion_ready_items", "next_unlock_operator_work_receipt_validation_target_rows_met_completion_ready_items"),
        check("completion remains blocked", receipt.get("completion_ready_items") == 0 and readiness.get("next_unlock_operator_work_receipt_completion_ready_items") == 0, {"receipt": receipt.get("completion_ready_items"), "manifest": readiness.get("next_unlock_operator_work_receipt_completion_ready_items")}, 0),
        check("release remains blocked", manifest.get("release_ready") is False, manifest.get("release_ready"), False),
    ]
    failures = [item for item in checks if not item["passed"]]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "checks": checks,
        "failures": failures,
        "receipt_rows": receipt.get("receipt_rows"),
        "open_blocked_receipt_rows": receipt.get("open_blocked_receipt_rows"),
        "completion_ready_items": receipt.get("completion_ready_items"),
        "observed_decision_input_rows": receipt.get("observed_decision_input_rows"),
        "target_rows_met_items": receipt.get("target_rows_met_items"),
        "validated_receipt_rows": validation.get("validated_receipt_rows"),
        "invalid_receipt_rows": validation.get("invalid_receipt_rows"),
        "validation_completion_ready_items": validation.get("completion_ready_items"),
        "validation_target_rows_met_items": validation.get("target_rows_met_items"),
        "validation_target_rows_met_completion_ready_items": validation.get("target_rows_met_completion_ready_items"),
        "release_ready": False,
        "policy": "Consistency validation only. Operator receipts track local work and do not create decisions, approvals, claims, ordering, customer delivery, or release readiness.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "failures": len(failures), "output": str(args.report)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
