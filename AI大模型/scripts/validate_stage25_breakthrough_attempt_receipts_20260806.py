#!/usr/bin/env python3
"""Validate Stage 25 breakthrough attempt receipts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "governance" / "stage25_breakthrough_attempt_receipts_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_breakthrough_attempt_receipt_validation_20260806.json"


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
    fail_if(not RECEIPTS.exists(), failures, "breakthrough_receipts_exist", "missing", str(RECEIPTS))
    rows = load_jsonl(RECEIPTS) if RECEIPTS.exists() else []
    fail_if(len(rows) != 2, failures, "receipt_row_count", len(rows), 2)

    seen = {row.get("attempt_type"): row for row in rows}
    fail_if("source_access_breakthrough" not in seen, failures, "source_access_receipt_present", sorted(seen), "source_access_breakthrough")
    fail_if("foldx_runtime_breakthrough_probe" not in seen, failures, "foldx_runtime_receipt_present", sorted(seen), "foldx_runtime_breakthrough_probe")

    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(not row.get("commands_attempted"), failures, f"{prefix}.commands_attempted_present", row.get("commands_attempted"), "non-empty")
        policy = str(row.get("policy") or "")
        for term in ("receipt only", "does not authorize"):
            fail_if(term not in policy, failures, f"{prefix}.policy_contains.{term}", policy, f"contains {term}")

    source = seen.get("source_access_breakthrough") or {}
    fail_if(source.get("breakthrough_status") != "attempted_blocked_by_publisher_access", failures, "source.breakthrough_status", source.get("breakthrough_status"), "attempted_blocked_by_publisher_access")
    for flag in ("evidence_closed", "fulltext_or_source_table_obtained", "variant_residue_identity_closed", "measurement_locator_closed", "safe_to_write_sqlite", "safe_to_approve_family_importer"):
        fail_if(source.get(flag) is not False, failures, f"source.{flag}_false", source.get(flag), False)
    observed_returns = [cmd.get("returncode") for cmd in source.get("commands_attempted") or []]
    fail_if(6 not in observed_returns or 56 not in observed_returns, failures, "source.returncodes_include_dns_and_403", observed_returns, "contains 6 and 56")

    foldx = seen.get("foldx_runtime_breakthrough_probe") or {}
    fail_if(foldx.get("breakthrough_status") != "attempted_runtime_not_found", failures, "foldx.breakthrough_status", foldx.get("breakthrough_status"), "attempted_runtime_not_found")
    for flag in ("foldx_executable_found", "foldx_license_approved", "foldx_runtime_receipt_ready", "foldx_physical_smoke_passed", "safe_for_physical_ddg_claim", "safe_for_model_claim", "release_ready"):
        fail_if(foldx.get(flag) is not False, failures, f"foldx.{flag}_false", foldx.get(flag), False)

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_breakthrough_attempt_receipt_validation",
        "stage": 25,
        "receipt_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "receipt_rows": len(rows),
        "source_access_attempt_recorded": "source_access_breakthrough" in seen,
        "foldx_runtime_probe_recorded": "foldx_runtime_breakthrough_probe" in seen,
        "evidence_closed": False,
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
    print(json.dumps({"output": str(OUTPUT), "receipt_valid": report["receipt_valid"], "failure_count": report["failure_count"], "receipt_rows": report["receipt_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["receipt_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
