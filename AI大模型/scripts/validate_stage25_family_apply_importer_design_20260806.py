#!/usr/bin/env python3
"""Validate Stage 25 family apply importer design packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DESIGNS = AI_ROOT / "datasets" / "governance" / "stage25_family_apply_importer_design_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_family_apply_importer_design_validation_20260806.json"

EXPECTED = {
    "xylanase": {"papers", "variants", "measurements"},
    "lipase": {"papers", "variants", "variant_mutations", "evidence_claims", "metrics"},
}
REQUIRED_PREFLIGHT_TERMS = {
    "allowlist_decision_approved_for_family_importer",
    "full_text_obtained_true",
    "identity_closed_true",
    "variant_sites_extracted_true",
    "measurement_payload_mapped_true",
    "pragma_integrity_check_ok",
}
REQUIRED_TRANSACTION_TERMS = {
    "copy2_backup_before_apply",
    "BEGIN_IMMEDIATE",
    "rerun_duplicate_check_inside_transaction",
    "postcondition_counts",
    "commit_only_if_all_checks_pass_else_rollback",
}


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
    fail_if(not DESIGNS.exists(), failures, "design_file_exists", "missing", str(DESIGNS))
    rows = load_jsonl(DESIGNS) if DESIGNS.exists() else []
    by_family = {row.get("family"): row for row in rows}
    fail_if(set(by_family) != set(EXPECTED), failures, "families", sorted(by_family), sorted(EXPECTED))
    for family, expected_tables in EXPECTED.items():
        row = by_family.get(family) or {}
        prefix = f"{family}"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(set(row.get("write_tables") or []) != expected_tables, failures, f"{prefix}.write_tables", row.get("write_tables"), sorted(expected_tables))
        preflight = set(row.get("required_preflight") or [])
        transaction = set(row.get("transaction_steps") or [])
        for term in REQUIRED_PREFLIGHT_TERMS:
            fail_if(term not in preflight, failures, f"{prefix}.preflight.{term}", sorted(preflight), f"contains {term}")
        for term in REQUIRED_TRANSACTION_TERMS:
            fail_if(term not in transaction, failures, f"{prefix}.transaction.{term}", sorted(transaction), f"contains {term}")
        for flag in ("dry_run_required", "ready_to_implement_code"):
            fail_if(row.get(flag) is not True, failures, f"{prefix}.{flag}_true", row.get(flag), True)
        for flag in ("apply_executed", "external_sqlite_mutated", "ready_to_apply_now", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_family_apply_importer_design_validation",
        "stage": 25,
        "design_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "design_rows": len(rows),
        "families": sorted(by_family),
        "ready_to_implement_code_rows": sum(1 for row in rows if row.get("ready_to_implement_code") is True),
        "ready_to_apply_now_rows": 0,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "release_ready": False,
        "safe_for_model_claim": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "design_valid": report["design_valid"], "failure_count": report["failure_count"], "design_rows": report["design_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["design_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
