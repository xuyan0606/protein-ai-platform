#!/usr/bin/env python3
"""Validate the Stage 25 public web literature search receipt."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT = AI_ROOT / "reports" / "stage25_literature_web_search_receipt_20260806.json"
OUT = AI_ROOT / "reports" / "stage25_literature_web_search_receipt_validation_20260806.json"
EXPECTED_PMIDS = {"39743673", "42134585", "42235695", "42248057"}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not RECEIPT.exists(), failures, "receipt_exists", "missing", str(RECEIPT))
    receipt = load_json(RECEIPT) if RECEIPT.exists() else {}
    rows = receipt.get("rows") if isinstance(receipt.get("rows"), list) else []
    pmids = {str(row.get("pmid")) for row in rows if isinstance(row, dict)}

    fail_if(receipt.get("mode") != "stage25_literature_web_search_receipt", failures, "mode", receipt.get("mode"), "stage25_literature_web_search_receipt")
    fail_if(receipt.get("paper_rows") != 4, failures, "paper_rows", receipt.get("paper_rows"), 4)
    fail_if(pmids != EXPECTED_PMIDS, failures, "expected_pmids", sorted(pmids), sorted(EXPECTED_PMIDS))
    fail_if(receipt.get("source_table_locators_verified") != 0, failures, "source_table_locators_verified_zero", receipt.get("source_table_locators_verified"), 0)
    fail_if(receipt.get("ready_for_sqlite_apply_rows") != 0, failures, "ready_for_sqlite_apply_rows_zero", receipt.get("ready_for_sqlite_apply_rows"), 0)
    fail_if(receipt.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", receipt.get("formal_decision_rows_written"), 0)
    for row in rows:
        prefix = f"row[{row.get('pmid')}]"
        fail_if(not row.get("primary_pages_found"), failures, f"{prefix}.primary_pages_found", row.get("primary_pages_found"), "non-empty")
        fail_if(not row.get("evidence_level"), failures, f"{prefix}.evidence_level", row.get("evidence_level"), "non-empty")
        fail_if(not row.get("importer_decision"), failures, f"{prefix}.importer_decision", row.get("importer_decision"), "non-empty")
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(receipt.get(flag) is not False, failures, f"{flag}_false", receipt.get(flag), False)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_literature_web_search_receipt_validation",
        "stage": 25,
        "receipt_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "paper_rows": len(rows),
        "secondary_lead_rows": receipt.get("secondary_lead_rows"),
        "source_table_locators_verified": receipt.get("source_table_locators_verified"),
        "ready_for_sqlite_apply_rows": receipt.get("ready_for_sqlite_apply_rows"),
        "formal_decision_rows_written": 0,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "receipt_valid": validation["receipt_valid"],
        "failure_count": validation["failure_count"],
        "paper_rows": validation["paper_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if validation["receipt_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
