#!/usr/bin/env python3
"""Validate Stage 25 source-drop extraction readiness candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "governance" / "stage25_source_drop_extraction_readiness_candidates_20260806.jsonl"
SOURCE_DROP_REPORT = AI_ROOT / "reports" / "stage25_source_drop_manifest_validation_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_source_drop_extraction_readiness_candidate_validation_20260806.json"

EXPECTED_PMIDS = {"39743673", "42134585", "42235695", "42248057"}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


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
    fail_if(not CANDIDATES.exists(), failures, "candidate_file_exists", "missing", str(CANDIDATES))
    fail_if(not SOURCE_DROP_REPORT.exists(), failures, "source_drop_report_exists", "missing", str(SOURCE_DROP_REPORT))
    rows = load_jsonl(CANDIDATES) if CANDIDATES.exists() else []
    source_drop = load_json(SOURCE_DROP_REPORT) if SOURCE_DROP_REPORT.exists() else {}
    pmids = {str(row.get("pmid")) for row in rows}
    fail_if(pmids != EXPECTED_PMIDS, failures, "pmids", sorted(pmids), sorted(EXPECTED_PMIDS))
    ready_by_source_id = {
        row.get("source_id"): row.get("ready_for_extraction") is True
        for row in source_drop.get("source_status") or []
    }

    ready_for_reviewed_extraction_rows = 0
    ready_for_sqlite_apply_rows = 0
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(int(row.get("required_source_count") or 0) < 2, failures, f"{prefix}.required_source_count_min", row.get("required_source_count"), ">=2")
        required_sources = row.get("required_sources") or []
        expected_ready = sum(1 for source in required_sources if ready_by_source_id.get(source.get("source_id")) is True)
        expected_missing = sorted(
            str(source.get("source_id"))
            for source in required_sources
            if ready_by_source_id.get(source.get("source_id")) is not True
        )
        expected_all_ready = bool(required_sources and expected_ready == len(required_sources))
        fail_if(row.get("ready_source_count") != expected_ready, failures, f"{prefix}.ready_source_count_matches_source_report", row.get("ready_source_count"), expected_ready)
        fail_if(sorted(row.get("missing_source_ids") or []) != expected_missing, failures, f"{prefix}.missing_source_ids_match_source_report", row.get("missing_source_ids"), expected_missing)
        fail_if(row.get("all_required_sources_ready") is not expected_all_ready, failures, f"{prefix}.all_required_sources_ready_matches_source_report", row.get("all_required_sources_ready"), expected_all_ready)
        for flag in (
            "ready_for_reviewed_extraction",
            "reviewed_extraction_completed",
            "ready_for_allowlist_approval",
            "ready_for_sqlite_apply",
            "external_sqlite_mutated",
            "export_safe_released",
            "safe_for_model_claim",
            "release_ready",
        ):
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
        fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written_zero", row.get("formal_decision_rows_written"), 0)
        ready_for_reviewed_extraction_rows += 1 if row.get("ready_for_reviewed_extraction") is True else 0
        ready_for_sqlite_apply_rows += 1 if row.get("ready_for_sqlite_apply") is True else 0
        policy = str(row.get("policy") or "")
        for term in ("readiness candidate only", "SQLite apply", "formal decisions"):
            fail_if(term not in policy, failures, f"{prefix}.policy_contains.{term}", policy, f"contains {term}")

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_source_drop_extraction_readiness_candidate_validation",
        "stage": 25,
        "candidates_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "candidate_rows": len(rows),
        "ready_for_reviewed_extraction_rows": ready_for_reviewed_extraction_rows,
        "ready_for_sqlite_apply_rows": ready_for_sqlite_apply_rows,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "release_ready": False,
        "safe_for_model_claim": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "candidates_valid": report["candidates_valid"], "failure_count": report["failure_count"], "candidate_rows": report["candidate_rows"], "ready_for_reviewed_extraction_rows": report["ready_for_reviewed_extraction_rows"], "ready_for_sqlite_apply_rows": report["ready_for_sqlite_apply_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["candidates_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
