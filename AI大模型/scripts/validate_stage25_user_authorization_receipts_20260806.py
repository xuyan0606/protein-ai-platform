#!/usr/bin/env python3
"""Validate Stage 25 user authorization receipts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "governance" / "stage25_user_authorization_receipts_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_user_authorization_receipt_validation_20260806.json"


REQUIRED_TRUE_FLAGS = (
    "sqlite_write_authorized_by_user",
    "formal_decision_authorized_by_user",
    "apply_authorized_by_user",
    "export_release_authorized_by_user",
    "model_claim_authorized_by_user",
)

REQUIRED_FALSE_FLAGS = (
    "sqlite_write_executed",
    "apply_executed",
    "export_safe_released",
    "safe_for_model_claim",
    "release_ready",
    "benchmark_ready_for_model_claim",
    "external_sqlite_mutated",
)

REQUIRED_EVIDENCE_GATES = (
    "fulltext_or_source_table_receipt",
    "variant_residue_identity",
    "WT_or_parent_baseline",
    "measurement_value_unit_condition_locator",
    "human_reviewer_decision_where_required",
    "benchmark_receipt",
    "runtime_license_receipt",
    "release_acceptance",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not RECEIPTS.exists(), failures, "authorization_receipts_exist", "missing", str(RECEIPTS))
    rows = load_jsonl(RECEIPTS) if RECEIPTS.exists() else []
    fail_if(len(rows) != 1, failures, "receipt_row_count", len(rows), 1)

    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(row.get("authorization_scope") != "maximum_local_workspace_permission_granted_by_user", failures, f"{prefix}.authorization_scope", row.get("authorization_scope"), "maximum_local_workspace_permission_granted_by_user")
        for flag in REQUIRED_TRUE_FLAGS:
            fail_if(row.get(flag) is not True, failures, f"{prefix}.{flag}_true", row.get(flag), True)
        for flag in REQUIRED_FALSE_FLAGS:
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
        fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written_zero", row.get("formal_decision_rows_written"), 0)
        gates = set(row.get("non_substitutable_evidence_gates") or [])
        for gate in REQUIRED_EVIDENCE_GATES:
            fail_if(gate not in gates, failures, f"{prefix}.required_evidence_gate.{gate}", sorted(gates), f"contains {gate}")
        policy = str(row.get("validator_policy") or "")
        for term in ("permission only", "not evidence closure", "not", "SQLite mutation"):
            fail_if(term not in policy, failures, f"{prefix}.validator_policy_contains.{term}", policy, f"contains {term}")

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_user_authorization_receipt_validation",
        "stage": 25,
        "receipt_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "receipt_rows": len(rows),
        "authorization_recorded": bool(rows) and not failures,
        "sqlite_write_authorized_by_user": bool(rows and rows[0].get("sqlite_write_authorized_by_user") is True),
        "formal_decision_authorized_by_user": bool(rows and rows[0].get("formal_decision_authorized_by_user") is True),
        "apply_authorized_by_user": bool(rows and rows[0].get("apply_authorized_by_user") is True),
        "export_release_authorized_by_user": bool(rows and rows[0].get("export_release_authorized_by_user") is True),
        "model_claim_authorized_by_user": bool(rows and rows[0].get("model_claim_authorized_by_user") is True),
        "sqlite_write_executed": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "release_ready": False,
        "safe_for_model_claim": False,
        "benchmark_ready_for_model_claim": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "receipt_valid": report["receipt_valid"], "failure_count": report["failure_count"], "authorization_recorded": report["authorization_recorded"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["receipt_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
