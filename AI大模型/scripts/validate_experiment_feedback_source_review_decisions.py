#!/usr/bin/env python3
"""Validate human-reviewed experiment-feedback source decisions fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_source_candidates.jsonl"
INPUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_source_review_decisions.local.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_source_review_decisions.template.jsonl"
STATUS_OUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_source_review_status.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "experiment_feedback_source_review_decision_validation_report.json"

VALID_DECISIONS = {"approve_for_extraction", "reject_source", "keep_unvalidated", "needs_more_info"}
GENUINE_SOURCE_TYPES = {"kwb_wet_lab", "kwb_historical"}
VALID_EXTRACTABILITY = {"structured_table", "semi_structured_text", "manual_transcription_required", "not_extractable"}
BLOCKED_BUCKETS = {"fixture_or_reference", "development_or_noise", "low_signal_candidate"}

TEMPLATE_ROW = {
    "source_path": "matvenus-research/raw/example.stream-events.json",
    "decision": "needs_more_info",
    "reviewed_source_type": "kwb_historical",
    "extractability": "manual_transcription_required",
    "candidate_feedback_rows": 0,
    "approved_for_feedback_extraction": False,
    "approved_for_feedback_intake": False,
    "contains_genuine_experiment_outcome": False,
    "contains_model_prediction_only": False,
    "numbering_review_required": True,
    "unit_condition_qc_review_required": True,
    "reviewer": "human-feedback-source-reviewer",
    "reviewed_at": "2026-07-30T00:00:00+08:00",
    "evidence_summary": "Template only. State what wet-lab result is present and where.",
    "notes": "Copy to .local.jsonl only after human source review.",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def missing(value: Any) -> bool:
    return value is None or value == ""


def validate(row: dict[str, Any], candidate_by_path: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for field in [
        "source_path",
        "decision",
        "reviewed_source_type",
        "extractability",
        "candidate_feedback_rows",
        "approved_for_feedback_extraction",
        "approved_for_feedback_intake",
        "contains_genuine_experiment_outcome",
        "contains_model_prediction_only",
        "numbering_review_required",
        "unit_condition_qc_review_required",
        "reviewer",
        "reviewed_at",
        "evidence_summary",
    ]:
        if field not in row or missing(row.get(field)):
            errors.append(f"missing_{field}")

    source_path = str(row.get("source_path") or "")
    candidate = candidate_by_path.get(source_path)
    if not candidate:
        errors.append("unknown_source_path")
    elif candidate.get("source_review_bucket") in BLOCKED_BUCKETS and row.get("approved_for_feedback_extraction") is True:
        errors.append("blocked_bucket_cannot_be_approved_for_extraction")

    if row.get("decision") not in VALID_DECISIONS:
        errors.append("invalid_decision")
    if row.get("reviewed_source_type") not in GENUINE_SOURCE_TYPES | {"not_feedback_source", "protocol_only", "unknown"}:
        errors.append("invalid_reviewed_source_type")
    if row.get("extractability") not in VALID_EXTRACTABILITY:
        errors.append("invalid_extractability")

    for field in [
        "approved_for_feedback_extraction",
        "approved_for_feedback_intake",
        "contains_genuine_experiment_outcome",
        "contains_model_prediction_only",
        "numbering_review_required",
        "unit_condition_qc_review_required",
    ]:
        if not isinstance(row.get(field), bool):
            errors.append(f"invalid_{field}")

    if not isinstance(row.get("candidate_feedback_rows"), int) or isinstance(row.get("candidate_feedback_rows"), bool):
        errors.append("invalid_candidate_feedback_rows")
    elif row["candidate_feedback_rows"] < 0:
        errors.append("negative_candidate_feedback_rows")

    approved_for_extraction = row.get("approved_for_feedback_extraction") is True
    approved_for_intake = row.get("approved_for_feedback_intake") is True
    genuine = row.get("contains_genuine_experiment_outcome") is True
    prediction_only = row.get("contains_model_prediction_only") is True

    if approved_for_intake:
        errors.append("approved_for_feedback_intake_must_remain_false_at_source_review_stage")
    if approved_for_extraction and row.get("decision") != "approve_for_extraction":
        errors.append("extraction_approval_without_approve_decision")
    if row.get("decision") == "approve_for_extraction" and not approved_for_extraction:
        errors.append("approve_decision_without_extraction_flag")
    if approved_for_extraction and row.get("reviewed_source_type") not in GENUINE_SOURCE_TYPES:
        errors.append("extraction_approval_requires_genuine_kwb_source_type")
    if approved_for_extraction and not genuine:
        errors.append("extraction_approval_requires_genuine_experiment_outcome")
    if approved_for_extraction and prediction_only:
        errors.append("prediction_only_source_cannot_be_approved")
    if approved_for_extraction and row.get("candidate_feedback_rows", 0) <= 0:
        errors.append("extraction_approval_requires_candidate_feedback_rows")
    if approved_for_extraction and row.get("extractability") == "not_extractable":
        errors.append("approved_source_marked_not_extractable")
    if approved_for_extraction and len(str(row.get("evidence_summary") or "").strip()) < 20:
        errors.append("evidence_summary_too_short_for_approval")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate experiment feedback source-review decisions")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--status-output", type=Path, default=STATUS_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, [TEMPLATE_ROW])

    candidates = load_jsonl(args.candidates)
    decisions = load_jsonl(args.input)
    candidate_by_path = {str(row.get("relative_path") or row.get("path")): row for row in candidates}
    records: list[dict[str, Any]] = []
    errors = Counter()
    seen: set[str] = set()
    duplicates: set[str] = set()

    for row in decisions:
        source_path = str(row.get("source_path") or "")
        if source_path in seen:
            duplicates.add(source_path)
        seen.add(source_path)
        row_errors = validate(row, candidate_by_path)
        errors.update(row_errors)
        records.append({
            "source_path": source_path,
            "decision": row.get("decision"),
            "valid": not row_errors,
            "approved_for_feedback_extraction": bool(row.get("approved_for_feedback_extraction")) and not row_errors,
            "approved_for_feedback_intake": False,
            "candidate_feedback_rows": row.get("candidate_feedback_rows"),
            "errors": row_errors,
        })

    if duplicates:
        errors.update({"duplicate_source_path": len(duplicates)})
        for record in records:
            if record["source_path"] in duplicates:
                record["valid"] = False
                record["approved_for_feedback_extraction"] = False
                record["errors"].append("duplicate_source_path")

    valid_decision_paths = {row["source_path"] for row in records if row["valid"]}
    status_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        source_path = str(candidate.get("relative_path") or candidate.get("path") or "")
        matching = next((row for row in records if row["source_path"] == source_path), None)
        approved = bool(matching and matching["approved_for_feedback_extraction"])
        status_rows.append({
            "source_path": source_path,
            "source_review_bucket": candidate.get("source_review_bucket"),
            "candidate_score": candidate.get("candidate_score"),
            "decision_present": source_path in valid_decision_paths,
            "approved_for_feedback_extraction": approved,
            "approved_for_feedback_intake": False,
            "status": "ready_for_extraction_review" if approved else "blocked_waiting_for_source_review",
            "policy": "Status only; source review does not write experiment_feedback.local.jsonl.",
        })
    write_jsonl(args.status_output, status_rows)

    approved_rows = sum(1 for row in records if row["approved_for_feedback_extraction"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidate_rows": len(candidates),
        "decision_rows": len(decisions),
        "valid_rows": sum(1 for row in records if row["valid"]),
        "invalid_rows": sum(1 for row in records if not row["valid"]),
        "approved_for_feedback_extraction_rows": approved_rows,
        "approved_for_feedback_intake_rows": 0,
        "missing_source_review_rows": max(len(candidates) - len(valid_decision_paths), 0),
        "all_sources_reviewed": len(candidates) > 0 and len(valid_decision_paths) == len(candidates) and not errors,
        "ready_for_feedback_extraction": approved_rows > 0 and not errors,
        "ready_for_feedback_intake": False,
        "safe_for_model_claim": False,
        "error_counts": dict(errors),
        "records": records[:200],
        "outputs": {
            "template": str(args.template),
            "input": str(args.input),
            "status": str(args.status_output),
        },
        "policy": "Only human-reviewed genuine KWB wet-lab/historical sources may become extraction candidates; no source-review decision directly creates training rows.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": report["decision_rows"],
        "valid_rows": report["valid_rows"],
        "approved_for_feedback_extraction_rows": approved_rows,
        "ready_for_feedback_intake": False,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
