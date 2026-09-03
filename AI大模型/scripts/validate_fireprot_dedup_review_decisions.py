#!/usr/bin/env python3
"""Validate FireProt duplicate-review decisions fail-closed."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "curation" / "fireprot_curated_dedup_aggregation_candidates.jsonl"
INPUT = AI_ROOT / "datasets" / "curation" / "fireprot_dedup_review_decisions.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "curation" / "fireprot_dedup_review_decisions.template.jsonl"
REPORT = AI_ROOT / "reports" / "fireprot_dedup_review_decision_validation_report.json"

VALID_DECISIONS = {"pending", "select_source_row", "approve_median", "keep_separate", "exclude"}
APPROVAL_DECISIONS = {"select_source_row", "approve_median"}
TRAINING_LICENSE_SCOPES = {
    "approved_for_training",
    "approved_for_training_with_conditions",
}

TEMPLATE_ROW = {
    "dedup_candidate_id": "<required: candidate id from review packet>",
    "decision": "pending",
    "selected_source_mapping_ids": [],
    "approved_label_ddg_kcal_mol": None,
    "approved_assay_signature": None,
    "review_basis": "",
    "source_provenance_checked": False,
    "numbering_reviewed": False,
    "license_scope": None,
    "reviewer": "",
    "reviewed_at": "",
    "reviewed_import_receipt": None,
    "notes": "",
    "policy": (
        "Human decision template only. Copy a filled row into "
        "fireprot_dedup_review_decisions.jsonl after review; template rows are "
        "not training labels."
    ),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def missing(value: Any) -> bool:
    return value is None or value == "" or value == []


def as_float(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def same_float(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= 1e-9


def signature_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def source_ddg_by_mapping(candidate: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for row in candidate.get("source_rows") or []:
        mapping_id = row.get("mapping_id")
        ddg = as_float(row.get("label_ddg_kcal_mol"))
        if isinstance(mapping_id, str) and ddg is not None:
            values[mapping_id] = ddg
    return values


def hard_review_checks_pass(row: dict[str, Any]) -> bool:
    return (
        row.get("source_provenance_checked") is True
        and row.get("numbering_reviewed") is True
        and row.get("license_scope") in TRAINING_LICENSE_SCOPES
        and not missing(row.get("reviewed_import_receipt"))
        and not missing(row.get("reviewer"))
        and not missing(row.get("reviewed_at"))
        and not missing(row.get("review_basis"))
    )


def validate(row: dict[str, Any], candidate_by_id: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for field in [
        "dedup_candidate_id",
        "decision",
        "selected_source_mapping_ids",
        "review_basis",
        "source_provenance_checked",
        "numbering_reviewed",
        "license_scope",
        "reviewer",
        "reviewed_at",
        "reviewed_import_receipt",
    ]:
        if field not in row:
            errors.append(f"missing_{field}")

    candidate_id = str(row.get("dedup_candidate_id"))
    candidate = candidate_by_id.get(candidate_id)
    if not candidate:
        errors.append("unknown_dedup_candidate_id")
        return errors

    decision = row.get("decision")
    if decision not in VALID_DECISIONS:
        errors.append("invalid_decision")

    if not isinstance(row.get("selected_source_mapping_ids"), list):
        errors.append("invalid_selected_source_mapping_ids")
        selected: list[Any] = []
    else:
        selected = row.get("selected_source_mapping_ids") or []

    known_mapping_ids = set(candidate.get("source_mapping_ids") or [])
    unknown_selected = [mapping_id for mapping_id in selected if mapping_id not in known_mapping_ids]
    if unknown_selected:
        errors.append("selected_source_mapping_id_not_in_candidate")

    approved_ddg = as_float(row.get("approved_label_ddg_kcal_mol"))
    if row.get("approved_label_ddg_kcal_mol") is not None and approved_ddg is None:
        errors.append("invalid_approved_label_ddg_kcal_mol")

    if row.get("source_provenance_checked") is not None and not isinstance(row.get("source_provenance_checked"), bool):
        errors.append("invalid_source_provenance_checked")
    if row.get("numbering_reviewed") is not None and not isinstance(row.get("numbering_reviewed"), bool):
        errors.append("invalid_numbering_reviewed")

    approved_signature = row.get("approved_assay_signature")
    candidate_signatures = {signature_key(item) for item in candidate.get("assay_signatures") or []}
    if approved_signature is not None and signature_key(approved_signature) not in candidate_signatures:
        errors.append("approved_assay_signature_not_in_candidate")

    if decision == "pending":
        errors.append("pending_decision_not_reviewed")

    if decision == "approve_median":
        if not candidate.get("same_assay_signature"):
            errors.append("median_not_allowed_for_heterogeneous_assay")
        if candidate.get("label_value_median_kcal_mol") is None:
            errors.append("candidate_median_missing")
        if selected:
            errors.append("median_decision_must_not_select_source_rows")
        if approved_signature is None:
            errors.append("median_decision_missing_assay_signature")
        if not same_float(approved_ddg, as_float(candidate.get("label_value_median_kcal_mol"))):
            errors.append("approved_ddg_does_not_match_candidate_median")

    if decision == "select_source_row":
        if len(selected) != 1:
            errors.append("select_source_row_requires_exactly_one_source_mapping")
        if approved_signature is None:
            errors.append("select_source_row_missing_assay_signature")
        source_values = source_ddg_by_mapping(candidate)
        selected_value = source_values.get(str(selected[0])) if len(selected) == 1 else None
        if not same_float(approved_ddg, selected_value):
            errors.append("approved_ddg_does_not_match_selected_source")

    if decision == "keep_separate":
        if candidate.get("same_assay_signature"):
            errors.append("keep_separate_expected_for_heterogeneous_assay_only")
        if selected:
            errors.append("keep_separate_must_not_select_training_source")
        if approved_ddg is not None:
            errors.append("keep_separate_must_not_approve_single_ddg")

    if decision == "exclude":
        if selected:
            errors.append("exclude_must_not_select_source_rows")
        if approved_ddg is not None:
            errors.append("exclude_must_not_approve_ddg")

    if decision in APPROVAL_DECISIONS:
        for field in [
            "review_basis",
            "reviewer",
            "reviewed_at",
            "license_scope",
            "reviewed_import_receipt",
        ]:
            if missing(row.get(field)):
                errors.append(f"approval_missing_{field}")
        if row.get("source_provenance_checked") is not True:
            errors.append("approval_without_source_provenance_check")
        if row.get("numbering_reviewed") is not True:
            errors.append("approval_without_numbering_review")
        if row.get("license_scope") not in TRAINING_LICENSE_SCOPES:
            errors.append("approval_without_training_license_scope")
    else:
        # Non-approval decisions can be valid review decisions, but they never
        # become training-import rows.
        for field in ["reviewer", "reviewed_at", "review_basis"]:
            if decision in {"keep_separate", "exclude"} and missing(row.get(field)):
                errors.append(f"review_decision_missing_{field}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FireProt dedup review decisions")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, [TEMPLATE_ROW])

    candidates = load_jsonl(args.candidates)
    decisions = load_jsonl(args.input)
    candidate_by_id = {str(row.get("dedup_candidate_id")): row for row in candidates}

    records: list[dict[str, Any]] = []
    errors = Counter()
    seen = set()
    duplicate_ids = set()
    for row in decisions:
        candidate_id = str(row.get("dedup_candidate_id"))
        if candidate_id in seen:
            duplicate_ids.add(candidate_id)
        seen.add(candidate_id)
        row_errors = validate(row, candidate_by_id)
        errors.update(row_errors)
        approved = row.get("decision") in APPROVAL_DECISIONS and not row_errors and hard_review_checks_pass(row)
        keep_separate = row.get("decision") == "keep_separate" and not row_errors
        excluded = row.get("decision") == "exclude" and not row_errors
        records.append({
            "dedup_candidate_id": row.get("dedup_candidate_id"),
            "decision": row.get("decision"),
            "valid": not row_errors,
            "approved_for_import_candidate": approved,
            "keep_separate_reviewed": keep_separate,
            "excluded": excluded,
            "errors": row_errors,
        })

    if duplicate_ids:
        errors.update({"duplicate_dedup_candidate_id": len(duplicate_ids)})
        for record in records:
            if str(record["dedup_candidate_id"]) in duplicate_ids:
                record["valid"] = False
                record["approved_for_import_candidate"] = False
                record["keep_separate_reviewed"] = False
                record["excluded"] = False
                record["errors"].append("duplicate_dedup_candidate_id")

    valid_rows = sum(1 for item in records if item["valid"])
    approved_rows = sum(1 for item in records if item["approved_for_import_candidate"])
    keep_separate_rows = sum(1 for item in records if item["keep_separate_reviewed"])
    excluded_rows = sum(1 for item in records if item["excluded"])
    reviewed_ids = {
        str(item["dedup_candidate_id"])
        for item in records
        if item["valid"] and (item["approved_for_import_candidate"] or item["keep_separate_reviewed"] or item["excluded"])
    }
    missing_review_candidate_ids = sorted(set(candidate_by_id) - reviewed_ids)

    report = {
        "local_only": True,
        "candidates": str(args.candidates),
        "input": str(args.input),
        "template": str(args.template),
        "candidate_rows": len(candidates),
        "decision_rows": len(decisions),
        "valid_decision_rows": valid_rows,
        "invalid_decision_rows": len(records) - valid_rows,
        "approved_for_import_candidate_rows": approved_rows,
        "keep_separate_reviewed_rows": keep_separate_rows,
        "excluded_rows": excluded_rows,
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "all_candidates_reviewed": len(missing_review_candidate_ids) == 0 and bool(candidates),
        "missing_review_candidate_count": len(missing_review_candidate_ids),
        "missing_review_candidate_examples": missing_review_candidate_ids[:50],
        "error_counts": dict(errors),
        "records": records[:500],
        "safe_for_model_claim": False,
        "policy": (
            "Dedup decisions only produce import candidates. A separate formal "
            "supervised import, license gate, numbering gate, and reviewed receipt "
            "are still required before training."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": report["candidate_rows"],
        "decision_rows": report["decision_rows"],
        "valid_decision_rows": report["valid_decision_rows"],
        "approved_for_import_candidate_rows": report["approved_for_import_candidate_rows"],
        "ready_for_training_import_rows": report["ready_for_training_import_rows"],
        "all_candidates_reviewed": report["all_candidates_reviewed"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
