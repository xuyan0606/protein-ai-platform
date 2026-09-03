#!/usr/bin/env python3
"""Validate wet-lab mutant-library feedback intake authorizations fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
INPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.template.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"

VALID_DECISIONS = {"approved_for_feedback_intake", "rejected", "needs_more_info"}
AUTH_DECISIONS = {"approved_for_feedback_intake"}
VALID_QC_DECISIONS = {"pass", "pass_with_conditions", "fail", "not_reviewed"}
VALID_TRAINING_HEADS = {"activity_risk_head", "stability_head", "assay_success_head"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def missing(value: Any) -> bool:
    return value in (None, "", [])


def exists_rel(rel: str | None) -> bool:
    if not rel or not isinstance(rel, str):
        return False
    path = Path(rel)
    if path.is_absolute():
        try:
            path.relative_to(AI_ROOT)
        except ValueError:
            return False
        return path.exists()
    return (AI_ROOT / path).exists()


def numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def build_template_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for candidate in candidates:
        if not candidate.get("numeric_training_candidate"):
            continue
        cid = str(candidate.get("feedback_candidate_id"))
        assay_type = candidate.get("assay_type")
        suggested_heads = ["activity_risk_head"] if assay_type == "activity" else ["stability_head"]
        rows.append({
            "authorization_id": f"wetlab-mutlib-auth-{cid.replace('wetlab-mutlib-', '')}",
            "feedback_candidate_id": cid,
            "authorization_decision": "needs_more_info",
            "approved_training_heads": suggested_heads,
            "approved_data_granularity": "numeric_relative_to_control_measurement",
            "qc_decision": "not_reviewed",
            "source_trace_reviewed": False,
            "numbering_reviewed": False,
            "unit_condition_reviewed": False,
            "batch_control_reviewed": False,
            "replicate_policy_reviewed": False,
            "allow_append_to_experiment_feedback_local": False,
            "reviewer": "",
            "reviewed_at": "",
            "authorization_basis": "",
            "conditions": [],
            "residual_risks": [
                "template_row_not_reviewed",
                "not_authorized_for_training_intake",
            ],
            "candidate_summary": {
                "source_project": candidate.get("source_project"),
                "variant": candidate.get("variant"),
                "mutation_set": candidate.get("mutation_set"),
                "assay_type": assay_type,
                "metric_name": candidate.get("metric_name"),
                "raw_value_numeric": candidate.get("raw_value_numeric"),
                "vs_control_ratio": candidate.get("vs_control_ratio"),
                "outcome_candidate": candidate.get("outcome_candidate"),
                "batch_id": candidate.get("batch_id"),
                "sample_id": candidate.get("sample_id"),
                "source_file": candidate.get("source_file"),
                "source_row_index": candidate.get("source_row_index"),
            },
            "policy": "Template only; not an authorization and not a training label.",
        })
    return rows


def validate(row: dict[str, Any], candidates_by_id: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    required = [
        "authorization_id",
        "feedback_candidate_id",
        "authorization_decision",
        "approved_training_heads",
        "approved_data_granularity",
        "qc_decision",
        "source_trace_reviewed",
        "numbering_reviewed",
        "unit_condition_reviewed",
        "batch_control_reviewed",
        "replicate_policy_reviewed",
        "allow_append_to_experiment_feedback_local",
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

    cid = str(row.get("feedback_candidate_id"))
    candidate = candidates_by_id.get(cid)
    if not candidate:
        errors.append("feedback_candidate_id_not_found")
        candidate = {}
    else:
        if candidate.get("numeric_training_candidate") is not True:
            errors.append("candidate_not_numeric_training_candidate")
        if candidate.get("numbering_verified") is not True:
            errors.append("candidate_numbering_not_verified")
        if candidate.get("is_control") is True:
            errors.append("candidate_is_control")
        if candidate.get("source") != "kwb_wet_lab":
            errors.append("candidate_source_not_kwb_wet_lab")
        if not candidate.get("mutation_set"):
            errors.append("candidate_missing_mutation_set")
        if candidate.get("unresolved_variant_tokens"):
            errors.append("candidate_has_unresolved_variant_tokens")
        if not numeric(candidate.get("raw_value_numeric")):
            errors.append("candidate_missing_raw_numeric")
        if not numeric(candidate.get("control_value_numeric")):
            errors.append("candidate_missing_control_numeric")
        if not numeric(candidate.get("vs_control_ratio")):
            errors.append("candidate_missing_vs_control_ratio")
        if not exists_rel(candidate.get("source_file")):
            errors.append("candidate_source_file_missing")

    heads = row.get("approved_training_heads")
    if not isinstance(heads, list):
        errors.append("invalid_approved_training_heads")
        heads = []
    elif any(head not in VALID_TRAINING_HEADS for head in heads):
        errors.append("invalid_training_head")

    if row.get("approved_data_granularity") != "numeric_relative_to_control_measurement":
        errors.append("invalid_approved_data_granularity")

    if row.get("qc_decision") not in VALID_QC_DECISIONS:
        errors.append("invalid_qc_decision")

    for flag in [
        "source_trace_reviewed",
        "numbering_reviewed",
        "unit_condition_reviewed",
        "batch_control_reviewed",
        "replicate_policy_reviewed",
        "allow_append_to_experiment_feedback_local",
    ]:
        if not isinstance(row.get(flag), bool):
            errors.append(f"invalid_{flag}")

    if row.get("conditions") is not None and not isinstance(row.get("conditions"), list):
        errors.append("invalid_conditions")
    if row.get("residual_risks") is not None and not isinstance(row.get("residual_risks"), list):
        errors.append("invalid_residual_risks")

    if decision in AUTH_DECISIONS:
        for field in ["reviewer", "reviewed_at", "authorization_basis"]:
            if missing(row.get(field)):
                errors.append(f"authorization_missing_{field}")
        for flag in [
            "source_trace_reviewed",
            "numbering_reviewed",
            "unit_condition_reviewed",
            "batch_control_reviewed",
            "replicate_policy_reviewed",
        ]:
            if row.get(flag) is not True:
                errors.append(f"authorization_missing_{flag}")
        if row.get("qc_decision") not in {"pass", "pass_with_conditions"}:
            errors.append("authorization_without_qc_pass")
        if row.get("qc_decision") == "pass_with_conditions" and not row.get("conditions"):
            errors.append("conditional_qc_missing_conditions")
        if row.get("allow_append_to_experiment_feedback_local") is True:
            errors.append("direct_append_to_experiment_feedback_local_not_allowed_by_this_gate")
        if not heads:
            errors.append("authorization_without_training_heads")
        if row.get("residual_risks"):
            errors.append("authorization_with_residual_risks")
    else:
        if row.get("allow_append_to_experiment_feedback_local") is True:
            errors.append("non_authorized_decision_allows_append")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab mutant library feedback authorizations")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    candidates_by_id = {str(row.get("feedback_candidate_id")): row for row in candidates}
    candidate_ids = {cid for cid, row in candidates_by_id.items() if row.get("numeric_training_candidate")}

    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, build_template_rows(candidates))

    decisions = load_jsonl(args.input)
    records: list[dict[str, Any]] = []
    errors = Counter()
    seen_auth = set()
    seen_candidate = set()
    duplicate_auth_ids = set()
    duplicate_candidate_ids = set()
    for row in decisions:
        auth_id = str(row.get("authorization_id"))
        cid = str(row.get("feedback_candidate_id"))
        if auth_id in seen_auth:
            duplicate_auth_ids.add(auth_id)
        if cid in seen_candidate:
            duplicate_candidate_ids.add(cid)
        seen_auth.add(auth_id)
        seen_candidate.add(cid)
        row_errors = validate(row, candidates_by_id)
        errors.update(row_errors)
        authorized = row.get("authorization_decision") in AUTH_DECISIONS and not row_errors
        records.append({
            "authorization_id": row.get("authorization_id"),
            "feedback_candidate_id": row.get("feedback_candidate_id"),
            "authorization_decision": row.get("authorization_decision"),
            "valid": not row_errors,
            "authorized_for_feedback_intake": authorized,
            "approved_training_heads": row.get("approved_training_heads") if authorized else [],
            "errors": row_errors,
        })

    if duplicate_auth_ids:
        errors.update({"duplicate_authorization_id": len(duplicate_auth_ids)})
    if duplicate_candidate_ids:
        errors.update({"duplicate_feedback_candidate_id": len(duplicate_candidate_ids)})
    if duplicate_auth_ids or duplicate_candidate_ids:
        for record in records:
            if str(record["authorization_id"]) in duplicate_auth_ids:
                record["valid"] = False
                record["authorized_for_feedback_intake"] = False
                record["errors"].append("duplicate_authorization_id")
            if str(record["feedback_candidate_id"]) in duplicate_candidate_ids:
                record["valid"] = False
                record["authorized_for_feedback_intake"] = False
                record["errors"].append("duplicate_feedback_candidate_id")

    authorized_ids = sorted({
        str(record["feedback_candidate_id"])
        for record in records
        if record["authorized_for_feedback_intake"]
    })
    missing_candidates = sorted(candidate_ids - seen_candidate)
    valid_rows = sum(1 for record in records if record["valid"])
    authorized_rows = sum(1 for record in records if record["authorized_for_feedback_intake"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidates": str(args.candidates),
        "input": str(args.input),
        "template": str(args.template),
        "numeric_training_candidate_rows": len(candidate_ids),
        "authorization_rows": len(decisions),
        "valid_authorization_rows": valid_rows,
        "invalid_authorization_rows": len(records) - valid_rows,
        "authorized_rows": authorized_rows,
        "authorized_candidate_rows": len(authorized_ids),
        "authorized_feedback_candidate_ids": authorized_ids,
        "missing_candidate_authorization_rows": len(missing_candidates),
        "missing_feedback_candidate_ids": missing_candidates[:100],
        "ready_for_feedback_intake_rows": len(authorized_ids),
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "error_counts": dict(errors),
        "records": records[:200],
        "policy": "Human authorization is required before wet-lab mutant-library candidates can enter feedback preflight; this validator never appends training labels.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "numeric_training_candidate_rows": report["numeric_training_candidate_rows"],
        "authorization_rows": report["authorization_rows"],
        "authorized_candidate_rows": report["authorized_candidate_rows"],
        "ready_for_feedback_intake_rows": report["ready_for_feedback_intake_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
