#!/usr/bin/env python3
"""Validate formal FireProt supervised-import authorization fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "curation" / "fireprot_reviewed_import_candidates.jsonl"
INPUT = AI_ROOT / "datasets" / "curation" / "fireprot_supervised_import_authorization.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "curation" / "fireprot_supervised_import_authorization.template.jsonl"
REPORT = AI_ROOT / "reports" / "fireprot_supervised_import_authorization_validation_report.json"

VALID_DECISIONS = {"authorized", "authorized_with_conditions", "rejected", "needs_more_info"}
AUTH_DECISIONS = {"authorized", "authorized_with_conditions"}
TARGETS = {
    "datasets/curated/fireprot_external_supervised_import.reviewed.jsonl",
}

TEMPLATE_ROW = {
    "authorization_id": "fireprot-supervised-import-001",
    "source_dataset": "fireprot_reviewed_import_candidates",
    "authorization_decision": "needs_more_info",
    "approved_reviewed_import_candidate_ids": [],
    "max_rows_authorized": 0,
    "supervised_schema_target": "datasets/curated/fireprot_external_supervised_import.reviewed.jsonl",
    "required_validation_reports": [
        "reports/fireprot_dedup_review_decision_validation_report.json",
        "reports/fireprot_reviewed_import_candidate_report.json",
        "reports/fireprot_curated_import_leakage_review_report.json",
    ],
    "reviewer": "",
    "reviewed_at": "",
    "authorization_basis": "",
    "conditions": [],
    "residual_risks": [],
    "policy": "Template only; not an authorization and not a training import.",
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


def exists_rel(rel: str) -> bool:
    path = Path(rel)
    if path.is_absolute():
        try:
            path.relative_to(AI_ROOT)
        except ValueError:
            return False
        return path.exists()
    return (AI_ROOT / path).exists()


def validate(row: dict[str, Any], candidate_ids: set[str]) -> list[str]:
    errors: list[str] = []
    required = [
        "authorization_id",
        "source_dataset",
        "authorization_decision",
        "approved_reviewed_import_candidate_ids",
        "max_rows_authorized",
        "supervised_schema_target",
        "required_validation_reports",
        "reviewer",
        "reviewed_at",
        "authorization_basis",
        "conditions",
        "residual_risks",
    ]
    for field in required:
        if field not in row:
            errors.append(f"missing_{field}")

    decision = row.get("authorization_decision")
    if decision not in VALID_DECISIONS:
        errors.append("invalid_authorization_decision")
    if row.get("source_dataset") != "fireprot_reviewed_import_candidates":
        errors.append("invalid_source_dataset")
    if row.get("supervised_schema_target") not in TARGETS:
        errors.append("invalid_supervised_schema_target")

    approved_ids = row.get("approved_reviewed_import_candidate_ids")
    if not isinstance(approved_ids, list):
        errors.append("invalid_approved_reviewed_import_candidate_ids")
        approved_ids = []
    unknown_ids = [candidate_id for candidate_id in approved_ids if candidate_id not in candidate_ids]
    if unknown_ids:
        errors.append("approved_candidate_id_not_in_reviewed_import_candidates")

    max_rows = row.get("max_rows_authorized")
    if not isinstance(max_rows, int) or max_rows < 0:
        errors.append("invalid_max_rows_authorized")
        max_rows = 0
    if isinstance(approved_ids, list) and len(approved_ids) > max_rows:
        errors.append("approved_ids_exceed_max_rows_authorized")

    reports = row.get("required_validation_reports")
    if not isinstance(reports, list):
        errors.append("invalid_required_validation_reports")
        reports = []
    missing_reports = [path for path in reports if not isinstance(path, str) or not exists_rel(path)]
    if missing_reports:
        errors.append("missing_required_validation_report_path")

    if row.get("conditions") is not None and not isinstance(row.get("conditions"), list):
        errors.append("invalid_conditions")
    if row.get("residual_risks") is not None and not isinstance(row.get("residual_risks"), list):
        errors.append("invalid_residual_risks")

    if decision in AUTH_DECISIONS:
        for field in ["reviewer", "reviewed_at", "authorization_basis"]:
            if missing(row.get(field)):
                errors.append(f"authorization_missing_{field}")
        if not approved_ids:
            errors.append("authorization_without_approved_candidate_ids")
        if row.get("residual_risks"):
            errors.append("authorization_with_residual_risks")
        if decision == "authorized_with_conditions" and not row.get("conditions"):
            errors.append("authorized_with_conditions_missing_conditions")
    else:
        if approved_ids:
            errors.append("non_authorized_decision_with_approved_ids")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FireProt supervised import authorization")
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
    candidate_ids = {str(row.get("reviewed_import_candidate_id")) for row in candidates}

    records: list[dict[str, Any]] = []
    errors = Counter()
    seen = set()
    duplicate_ids = set()
    for row in decisions:
        auth_id = str(row.get("authorization_id"))
        if auth_id in seen:
            duplicate_ids.add(auth_id)
        seen.add(auth_id)
        row_errors = validate(row, candidate_ids)
        errors.update(row_errors)
        authorized = row.get("authorization_decision") in AUTH_DECISIONS and not row_errors
        approved_ids = row.get("approved_reviewed_import_candidate_ids") if isinstance(row.get("approved_reviewed_import_candidate_ids"), list) else []
        records.append({
            "authorization_id": row.get("authorization_id"),
            "authorization_decision": row.get("authorization_decision"),
            "valid": not row_errors,
            "authorized": authorized,
            "approved_reviewed_import_candidate_ids": approved_ids if authorized else [],
            "authorized_candidate_rows": len(approved_ids) if authorized else 0,
            "errors": row_errors,
        })

    if duplicate_ids:
        errors.update({"duplicate_authorization_id": len(duplicate_ids)})
        for record in records:
            if str(record["authorization_id"]) in duplicate_ids:
                record["valid"] = False
                record["authorized"] = False
                record["approved_reviewed_import_candidate_ids"] = []
                record["authorized_candidate_rows"] = 0
                record["errors"].append("duplicate_authorization_id")

    authorized_ids = sorted({
        candidate_id
        for record in records
        if record["authorized"]
        for candidate_id in record["approved_reviewed_import_candidate_ids"]
    })
    valid_rows = sum(1 for row in records if row["valid"])
    authorized_rows = sum(1 for row in records if row["authorized"])
    report = {
        "local_only": True,
        "candidates": str(args.candidates),
        "input": str(args.input),
        "template": str(args.template),
        "reviewed_import_candidate_rows": len(candidates),
        "authorization_rows": len(decisions),
        "valid_authorization_rows": valid_rows,
        "invalid_authorization_rows": len(records) - valid_rows,
        "authorized_rows": authorized_rows,
        "authorized_candidate_rows": len(authorized_ids),
        "authorized_reviewed_import_candidate_ids": authorized_ids[:100],
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "error_counts": dict(errors),
        "records": records[:200],
        "safe_for_model_claim": False,
        "policy": "Authorization validation is required before any FireProt row can be considered for supervised import.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "reviewed_import_candidate_rows": report["reviewed_import_candidate_rows"],
        "authorization_rows": report["authorization_rows"],
        "authorized_candidate_rows": report["authorized_candidate_rows"],
        "ready_for_training_import_rows": report["ready_for_training_import_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
