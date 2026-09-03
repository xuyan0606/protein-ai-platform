#!/usr/bin/env python3
"""Validate that review drafts stay separated from formal decisions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "review_draft_formal_boundary_validation_report.json"
WET_LAB_AUTHORIZATION_VALIDATION = (
    AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
)

DRAFT_ONLY_FIELDS = {"review_draft", "draft_policy"}

DRAFT_SPECS = {
    "numbering_deterministic_reject": {
        "path": "datasets/curation/numbering_deterministic_reject_decisions.review_draft.jsonl",
        "expected_rows": 475,
        "id_fields": ["record_id"],
        "required_fields": {"record_id", "decision", "review_draft", "draft_policy", "curator", "curated_at", "source_refs"},
        "expected_values": {
            "decision": "reject_label",
            "mapping_basis": "unresolved",
            "confidence": 0,
            "curator": "",
            "curated_at": "",
        },
    },
    "structure_chain_mapping_dbref": {
        "path": "datasets/curation/structure_chain_mapping_dbref_decisions.review_draft.jsonl",
        "expected_rows": 9,
        "id_fields": ["structure_id", "selected_chain_id"],
        "required_fields": {"structure_id", "selected_chain_id", "decision", "review_draft", "draft_policy", "curator", "curated_at", "source_refs"},
        "expected_values": {
            "decision": "set_chain_mapping",
            "sequence_to_structure_mapping_status": "manual_alignment_reviewed",
            "residue_numbering_basis": "sifts_uniprot_mapping",
            "curator": "",
            "curated_at": "",
        },
    },
    "structure_chain_autoreview_acceptance": {
        "path": "datasets/curation/structure_chain_autoreview_decision_drafts/structure_chain_autoreview_acceptance_001.decision_acceptance.draft.jsonl",
        "expected_rows": 18,
        "id_fields": ["structure_id"],
        "required_fields": {"structure_id", "candidate_bucket", "human_acceptance_status", "review_draft", "draft_policy", "curator", "curated_at", "source_refs", "suggested_decision_row", "acceptance_required_checks", "policy"},
        "expected_values": {
            "human_acceptance_status": "not_reviewed",
            "review_draft": True,
            "curator": "",
            "curated_at": "",
        },
    },
    "wet_lab_feedback_authorization": {
        "path": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.review_draft.jsonl",
        "expected_rows": 12,
        "id_fields": ["authorization_id"],
        "required_fields": {"authorization_id", "feedback_candidate_id", "authorization_decision", "review_draft", "draft_policy", "reviewer", "reviewed_at"},
        "expected_values": {
            "authorization_decision": "needs_more_info",
            "allow_append_to_experiment_feedback_local": False,
            "qc_decision": "not_reviewed",
            "source_trace_reviewed": False,
            "numbering_reviewed": False,
            "unit_condition_reviewed": False,
            "batch_control_reviewed": False,
            "replicate_policy_reviewed": False,
            "reviewer": "",
            "reviewed_at": "",
        },
    },
}

FORMAL_SPECS = {
    "numbering_curation": {
        "path": "datasets/curation/numbering_curation_decisions.jsonl",
        "expected_rows": 4,
        "id_fields": ["record_id"],
        "paired_draft": "numbering_deterministic_reject",
    },
    "structure_chain_mapping": {
        "path": "datasets/curation/structure_chain_mapping_decisions.jsonl",
        "expected_rows": 34,
        "id_fields": ["structure_id", "selected_chain_id"],
        "paired_draft": "structure_chain_mapping_dbref",
    },
    "wet_lab_feedback_authorization": {
        "path": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
        "expected_rows": 0,
        "expected_rows_source": "reports/wet_lab_mutant_library_feedback_authorization_validation_report.json",
        "id_fields": ["authorization_id"],
        "paired_draft": "wet_lab_feedback_authorization",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


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


def row_key(row: dict[str, Any], fields: list[str]) -> str:
    return "|".join(str(row.get(field, "")) for field in fields)


def validate_draft_rows(name: str, spec: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    missing_required = 0
    bad_policy = 0
    unexpected_values = 0
    duplicate_keys: list[str] = []
    seen: set[str] = set()

    if len(rows) != int(spec["expected_rows"]):
        failures.append({"check": "draft_expected_row_count", "draft": name, "observed": len(rows), "expected": spec["expected_rows"]})

    for idx, row in enumerate(rows, start=1):
        key = row_key(row, spec["id_fields"])
        if key in seen:
            duplicate_keys.append(key)
        seen.add(key)
        required_missing = sorted(field for field in spec["required_fields"] if field not in row)
        if required_missing:
            missing_required += 1
            failures.append({"check": "draft_required_fields", "draft": name, "row": idx, "key": key, "missing": required_missing})
        if row.get("review_draft") is not True:
            bad_policy += 1
            failures.append({"check": "draft_review_draft_true", "draft": name, "row": idx, "key": key, "observed": row.get("review_draft")})
        draft_policy = str(row.get("draft_policy") or "")
        if "not_" not in draft_policy and "not " not in draft_policy:
            bad_policy += 1
            failures.append({"check": "draft_policy_declares_not_formal", "draft": name, "row": idx, "key": key, "observed": draft_policy})
        for field, expected in spec["expected_values"].items():
            if row.get(field) != expected:
                unexpected_values += 1
                failures.append({"check": "draft_expected_fail_closed_value", "draft": name, "row": idx, "key": key, "field": field, "observed": row.get(field), "expected": expected})

    if duplicate_keys:
        failures.append({"check": "draft_no_duplicate_keys", "draft": name, "duplicates": sorted(set(duplicate_keys))[:20], "duplicate_count": len(duplicate_keys)})

    return {
        "path": spec["path"],
        "rows": len(rows),
        "expected_rows": spec["expected_rows"],
        "missing_required_rows": missing_required,
        "bad_policy_rows": bad_policy,
        "unexpected_fail_closed_value_rows": unexpected_values,
        "duplicate_key_count": len(duplicate_keys),
        "all_rows_marked_review_draft": all(row.get("review_draft") is True for row in rows),
        "all_rows_draft_only": missing_required == 0 and bad_policy == 0 and unexpected_values == 0 and not duplicate_keys,
    }


def validate_formal_rows(
    name: str,
    spec: dict[str, Any],
    rows: list[dict[str, Any]],
    expected_rows: int,
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    draft_field_rows = 0
    duplicate_keys: list[str] = []
    seen: set[str] = set()

    if len(rows) != expected_rows:
        failures.append({"check": "formal_expected_row_count", "formal": name, "observed": len(rows), "expected": expected_rows})

    for idx, row in enumerate(rows, start=1):
        key = row_key(row, spec["id_fields"])
        if key in seen:
            duplicate_keys.append(key)
        seen.add(key)
        present_draft_fields = sorted(DRAFT_ONLY_FIELDS & set(row))
        if present_draft_fields:
            draft_field_rows += 1
            failures.append({"check": "formal_has_no_draft_only_fields", "formal": name, "row": idx, "key": key, "draft_fields": present_draft_fields})

    if duplicate_keys:
        failures.append({"check": "formal_no_duplicate_keys", "formal": name, "duplicates": sorted(set(duplicate_keys))[:20], "duplicate_count": len(duplicate_keys)})

    return {
        "path": spec["path"],
        "rows": len(rows),
        "expected_rows": expected_rows,
        "expected_rows_source": spec.get("expected_rows_source", "static_spec"),
        "draft_only_field_rows": draft_field_rows,
        "duplicate_key_count": len(duplicate_keys),
        "boundary_locked_to_current_human_reviewed_count": len(rows) == expected_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate review-draft and formal-decision boundary")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    draft_rows_by_name: dict[str, list[dict[str, Any]]] = {}
    formal_rows_by_name: dict[str, list[dict[str, Any]]] = {}
    draft_reports: dict[str, dict[str, Any]] = {}
    formal_reports: dict[str, dict[str, Any]] = {}
    overlap_reports: dict[str, dict[str, Any]] = {}
    wet_lab_authorization_validation = load_json(WET_LAB_AUTHORIZATION_VALIDATION)
    formal_expected_rows = {
        name: int(spec["expected_rows"])
        for name, spec in FORMAL_SPECS.items()
    }
    if wet_lab_authorization_validation:
        formal_expected_rows["wet_lab_feedback_authorization"] = int(
            wet_lab_authorization_validation.get("authorization_rows") or 0
        )

    for name, spec in DRAFT_SPECS.items():
        rows = load_jsonl(AI_ROOT / spec["path"])
        draft_rows_by_name[name] = rows
        draft_reports[name] = validate_draft_rows(name, spec, rows, failures)

    for name, spec in FORMAL_SPECS.items():
        rows = load_jsonl(AI_ROOT / spec["path"])
        formal_rows_by_name[name] = rows
        formal_reports[name] = validate_formal_rows(name, spec, rows, formal_expected_rows[name], failures)

    for name, spec in FORMAL_SPECS.items():
        paired_draft = spec["paired_draft"]
        formal_keys = {row_key(row, spec["id_fields"]) for row in formal_rows_by_name[name]}
        draft_keys = {row_key(row, DRAFT_SPECS[paired_draft]["id_fields"]) for row in draft_rows_by_name[paired_draft]}
        overlaps = sorted(formal_keys & draft_keys)
        overlap_reports[name] = {
            "paired_draft": paired_draft,
            "shared_decision_keys": overlaps[:50],
            "shared_decision_key_count": len(overlaps),
            "interpretation": "Shared keys are allowed only because formal row counts remain fixed and formal rows contain no draft-only fields; draft rows still cannot be counted as new formal decisions.",
        }

    total_draft_rows = sum(len(rows) for rows in draft_rows_by_name.values())
    total_formal_rows = sum(len(rows) for rows in formal_rows_by_name.values())
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "draft_files": draft_reports,
        "formal_files": formal_reports,
        "overlap_audit": overlap_reports,
        "total_review_draft_rows": total_draft_rows,
        "total_formal_decision_rows": total_formal_rows,
        "draft_rows_counted_as_formal_decisions": 0 if not failures else None,
        "formal_expected_counts": formal_expected_rows,
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Review drafts are operator aids only. They must retain review_draft/draft_policy markers and must not change formal decision counts, training labels, model-quality claims or release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "total_review_draft_rows": total_draft_rows,
        "total_formal_decision_rows": total_formal_rows,
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
