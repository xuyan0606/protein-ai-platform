#!/usr/bin/env python3
"""Validate that draft markers stay inside draft/backlog namespaces."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "draft_namespace_isolation_validation_report.json"

MARKERS = ("review_draft", "draft_policy", "REVIEW_DRAFT", ".review_draft")
ALLOWED_NAMESPACE_PATTERNS = [
    re.compile(r"(?:^|/)[^/]*\.review_draft\.jsonl$"),
    re.compile(r"(?:^|/)[^/]*\.draft\.jsonl$"),
    re.compile(r"(?:^|/)[^/]*\.stage25_draft_[0-9]{8}\.jsonl$"),
    re.compile(r"(?:^|/)[^/]*_drafts\.jsonl$"),
    re.compile(r"(?:^|/)[^/]+_drafts/[^/]+\.jsonl$"),
    re.compile(r"(?:^|/)datasets/feedback/experiment_feedback_plate_intake_backlog\.jsonl$"),
    re.compile(r"(?:^|/)datasets/feedback/plate_intake_schema_gap_audit\.jsonl$"),
    re.compile(r"(?:^|/)datasets/governance/p605_review_draft_formal_boundary_gap_audit\.jsonl$"),
    re.compile(r"(?:^|/)datasets/curation/batches/[^/]+/[^/]+\.decision_review_template\.jsonl$"),
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSONL row: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: row must be a JSON object")
        rows.append(row)
    return rows


def has_marker(value: Any) -> bool:
    if isinstance(value, dict):
        return any(has_marker(v) for v in value.values()) or any(marker in value for marker in MARKERS)
    if isinstance(value, list):
        return any(has_marker(v) for v in value)
    if isinstance(value, str):
        return any(marker in value for marker in MARKERS)
    return False


def draft_text_marker(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.lower()
    return any(
        marker in text
        for marker in (
            "draft",
            "backlog",
            "not reviewed",
            "not_reviewed",
            "not_authorization",
            "not an authorization",
            "template only",
            "not a training label",
            "not applied",
            "not_applied",
        )
    )


def is_allowed_namespace(rel_path: str) -> bool:
    return any(pattern.search(rel_path) for pattern in ALLOWED_NAMESPACE_PATTERNS)


def validate_plate_backlog(rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    allowed_false_fields = {
        "approved_for_plate_intake": False,
        "training_eligible": False,
        "claim_eligible_now": False,
    }
    expected_strings = {
        "review_status": "draft",
        "qc_flag": "not_reviewed",
    }
    required_policy = "Draft backlog row only"
    bad_rows = 0
    for idx, row in enumerate(rows, start=1):
        row_failures = []
        for field, expected in allowed_false_fields.items():
            if row.get(field) is not expected:
                row_failures.append(f"{field}!=false")
        for field, expected in expected_strings.items():
            if row.get(field) != expected:
                row_failures.append(f"{field}!={expected}")
        policy = str(row.get("policy") or "")
        if required_policy not in policy:
            row_failures.append("policy_missing_backlog_guard")
        if row.get("source") != "plate_review_draft":
            row_failures.append("source_not_plate_review_draft")
        if not row.get("required_human_actions"):
            row_failures.append("missing_required_human_actions")
        if row_failures:
            bad_rows += 1
            failures.append({
                "check": "plate_backlog_row_semantics",
                "row": idx,
                "backlog_id": row.get("backlog_id"),
                "failures": row_failures,
            })
    return {
        "rows": len(rows),
        "bad_rows": bad_rows,
        "all_rows_draft_backlog_only": bad_rows == 0 and len(rows) > 0,
    }


def validate_generic_draft_namespace(rel_path: str, rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    bad_rows = 0
    for idx, row in enumerate(rows, start=1):
        row_failures = []
        if row.get("review_draft") is not None and row.get("review_draft") is not True:
            row_failures.append("review_draft_not_true")
        if "draft_policy" in row and not draft_text_marker(row.get("draft_policy")):
            row_failures.append("draft_policy_missing_draft_semantics")
        if "policy" in row and not draft_text_marker(row.get("policy")):
            row_failures.append("policy_missing_draft_semantics")
        if "decision" in row and str(row.get("decision") or "") in {"approved", "accept", "accepted", "reviewed"}:
            row_failures.append("decision_too_final_for_draft_namespace")
        for field in ("approved_for_plate_intake", "approved_for_feedback_intake", "training_eligible", "claim_eligible_now", "safe_for_model_claim", "release_ready"):
            if row.get(field) is True:
                row_failures.append(f"{field}_must_not_be_true_in_draft_namespace")
        if row.get("review_status") == "reviewed":
            row_failures.append("review_status_must_not_be_reviewed")
        if row.get("qc_flag") == "pass" and "draft" in rel_path and "plate_intake_backlog" not in rel_path:
            row_failures.append("qc_pass_not_expected_in_draft_namespace")
        if row_failures:
            bad_rows += 1
            failures.append({
                "check": "generic_draft_namespace_semantics",
                "file": rel_path,
                "row": idx,
                "failures": row_failures,
            })
    return {
        "rows": len(rows),
        "bad_rows": bad_rows,
        "all_rows_keep_draft_semantics": bad_rows == 0 and len(rows) > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate draft namespace isolation")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    scanned_files: dict[str, dict[str, Any]] = {}
    allowed_marker_files: list[str] = []
    unexpected_marker_files: list[str] = []
    plate_backlog_report: dict[str, Any] = {"rows": 0, "bad_rows": 0, "all_rows_draft_backlog_only": False}
    generic_draft_namespace_reports: dict[str, Any] = {}

    for path in sorted((AI_ROOT / "datasets").rglob("*.jsonl")):
        rel_path = str(path.relative_to(AI_ROOT))
        rows = load_jsonl(path)
        marker_rows = [idx for idx, row in enumerate(rows, start=1) if has_marker(row)]
        allowed = is_allowed_namespace(rel_path)
        if marker_rows and allowed:
            allowed_marker_files.append(rel_path)
        if marker_rows and not allowed:
            unexpected_marker_files.append(rel_path)
            failures.append({
                "check": "draft_markers_must_stay_in_allowed_namespaces",
                "file": rel_path,
                "marker_rows": marker_rows[:50],
                "marker_row_count": len(marker_rows),
            })
        scanned_files[rel_path] = {
            "rows": len(rows),
            "marker_row_count": len(marker_rows),
            "allowed_namespace": allowed,
        }
        if rel_path == "datasets/feedback/experiment_feedback_plate_intake_backlog.jsonl":
            plate_backlog_report = validate_plate_backlog(rows, failures)
        elif allowed and marker_rows:
            generic_draft_namespace_reports[rel_path] = validate_generic_draft_namespace(rel_path, rows, failures)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "scanned_files": scanned_files,
        "allowed_marker_files": allowed_marker_files,
        "allowed_marker_file_count": len(allowed_marker_files),
        "unexpected_marker_files": unexpected_marker_files,
        "unexpected_marker_file_count": len(unexpected_marker_files),
        "generic_draft_namespace_reports": generic_draft_namespace_reports,
        "generic_draft_namespace_count": len(generic_draft_namespace_reports),
        "plate_intake_backlog": plate_backlog_report,
        "failures": failures,
        "safe_for_training_pipeline": not failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Draft markers may exist only in explicit draft/backlog namespaces. Any leak outside those namespaces fails closed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "allowed_marker_files": report["allowed_marker_file_count"],
        "unexpected_marker_files": report["unexpected_marker_file_count"],
        "plate_backlog_rows": plate_backlog_report.get("rows"),
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
