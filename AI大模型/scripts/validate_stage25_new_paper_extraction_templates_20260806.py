#!/usr/bin/env python3
"""Validate Stage 25 new-paper extraction templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = AI_ROOT / "datasets" / "governance" / "stage25_new_paper_extraction_templates_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_new_paper_extraction_template_validation_20260806.json"

EXPECTED_IDS = {
    "stage25_extract_39743673_dsm4",
    "stage25_extract_42134585_9k_xynb2",
    "stage25_extract_42235695_cm5",
    "stage25_extract_42248057_xyest_benchmark",
}
ALLOWED_LEVELS = {"source_table", "source_figure", "source_supplementary_table"}


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
    fail_if(not TEMPLATES.exists(), failures, "template_file_exists", "missing", str(TEMPLATES))
    rows = load_jsonl(TEMPLATES) if TEMPLATES.exists() else []
    ids = {str(row.get("template_id")) for row in rows}
    fail_if(ids != EXPECTED_IDS, failures, "template_ids", sorted(ids), sorted(EXPECTED_IDS))
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(not row.get("required_source_files"), failures, f"{prefix}.required_source_files_present", row.get("required_source_files"), "non-empty")
        fail_if(len(row.get("required_fields") or []) < 8, failures, f"{prefix}.required_fields_minimum", len(row.get("required_fields") or []), ">=8")
        fail_if(set(row.get("allowed_source_evidence_levels") or []) != ALLOWED_LEVELS, failures, f"{prefix}.allowed_levels", row.get("allowed_source_evidence_levels"), sorted(ALLOWED_LEVELS))
        for term in ("abstract_only", "boundary", "TBD"):
            fail_if(term not in set(row.get("forbidden_terms") or []), failures, f"{prefix}.forbidden_term.{term}", row.get("forbidden_terms"), f"contains {term}")
        for flag in ("ready_for_allowlist_approval", "ready_for_sqlite_apply"):
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_new_paper_extraction_template_validation",
        "stage": 25,
        "templates_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "template_rows": len(rows),
        "ready_for_allowlist_approval_rows": 0,
        "ready_for_sqlite_apply_rows": 0,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "release_ready": False,
        "safe_for_model_claim": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "templates_valid": report["templates_valid"], "failure_count": report["failure_count"], "template_rows": report["template_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["templates_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
