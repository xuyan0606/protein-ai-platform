#!/usr/bin/env python3
"""Validate Stage 25 reviewed extraction output drafts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DRAFTS = AI_ROOT / "datasets" / "governance" / "stage25_reviewed_extraction_output_drafts_20260806.jsonl"
TEMPLATES = AI_ROOT / "datasets" / "governance" / "stage25_new_paper_extraction_templates_20260806.jsonl"
SOURCE_DROP_REPORT = AI_ROOT / "reports" / "stage25_source_drop_manifest_validation_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_reviewed_extraction_output_draft_validation_20260806.json"

EXPECTED_DRAFT_IDS = {
    "stage25_reviewed_extract_draft_39743673_dsm4",
    "stage25_reviewed_extract_draft_42134585_9k_xynb2",
    "stage25_reviewed_extract_draft_42235695_cm5",
    "stage25_reviewed_extract_draft_42248057_xyest_benchmark",
}
ALLOWED_BLOCKED_LEVELS = {"blocked_fulltext", "blocked_source_table"}


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


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not DRAFTS.exists(), failures, "draft_file_exists", "missing", str(DRAFTS))
    fail_if(not TEMPLATES.exists(), failures, "template_file_exists", "missing", str(TEMPLATES))
    fail_if(not SOURCE_DROP_REPORT.exists(), failures, "source_drop_report_exists", "missing", str(SOURCE_DROP_REPORT))

    rows = load_jsonl(DRAFTS) if DRAFTS.exists() else []
    templates = load_jsonl(TEMPLATES) if TEMPLATES.exists() else []
    source_drop = load_json(SOURCE_DROP_REPORT) if SOURCE_DROP_REPORT.exists() else {}
    template_ids = {str(row.get("template_id")) for row in templates}
    source_status = {
        row.get("source_id"): row.get("ready_for_extraction") is True
        for row in source_drop.get("source_status") or []
    }
    template_sources = {
        row.get("template_id"): list(row.get("required_source_files") or [])
        for row in templates
    }

    draft_ids = {str(row.get("draft_id")) for row in rows}
    fail_if(draft_ids != EXPECTED_DRAFT_IDS, failures, "draft_ids", sorted(draft_ids), sorted(EXPECTED_DRAFT_IDS))
    ready_source_rows = int(source_drop.get("ready_for_extraction_rows") or 0)
    all_sources_ready = source_drop.get("all_sources_ready_for_extraction") is True
    fail_if(all_sources_ready, failures, "all_sources_ready_false_until_local_drops", all_sources_ready, False)

    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(row.get("template_id") not in template_ids, failures, f"{prefix}.template_id_known", row.get("template_id"), sorted(template_ids))
        required_sources = template_sources.get(row.get("template_id")) or []
        expected_source_files_ready = bool(required_sources and all(source_status.get(source_id) is True for source_id in required_sources))
        fail_if(row.get("source_files_ready") is not expected_source_files_ready, failures, f"{prefix}.source_files_ready_matches_source_report", row.get("source_files_ready"), expected_source_files_ready)
        fail_if(row.get("reviewed_extraction_completed") is not False, failures, f"{prefix}.reviewed_extraction_completed_false", row.get("reviewed_extraction_completed"), False)
        fail_if(row.get("source_evidence_level") not in ALLOWED_BLOCKED_LEVELS, failures, f"{prefix}.source_evidence_level_blocked", row.get("source_evidence_level"), sorted(ALLOWED_BLOCKED_LEVELS))
        fail_if(row.get("source_locator") not in ("", None), failures, f"{prefix}.source_locator_empty_until_reviewed", row.get("source_locator"), "")
        for flag in ("variant_payload_ready", "measurement_payload_ready", "ready_for_allowlist_approval", "ready_for_sqlite_apply"):
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
        fail_if(not row.get("blocking_fields"), failures, f"{prefix}.blocking_fields_present", row.get("blocking_fields"), "non-empty")
        policy = str(row.get("policy") or "")
        for term in ("not a formal decision", "SQLite apply approval", "model claim"):
            fail_if(term not in policy, failures, f"{prefix}.policy_contains.{term}", policy, f"contains {term}")

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_reviewed_extraction_output_draft_validation",
        "stage": 25,
        "drafts_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "draft_rows": len(rows),
        "ready_source_rows": ready_source_rows,
        "reviewed_extraction_completed_rows": 0,
        "ready_for_allowlist_approval_rows": 0,
        "ready_for_sqlite_apply_rows": 0,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "release_ready": False,
        "safe_for_model_claim": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "drafts_valid": report["drafts_valid"], "failure_count": report["failure_count"], "draft_rows": report["draft_rows"], "reviewed_extraction_completed_rows": report["reviewed_extraction_completed_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["drafts_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
