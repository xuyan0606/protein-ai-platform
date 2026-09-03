#!/usr/bin/env python3
"""Validate the P28 feedback authorization and parent-sequence gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
AUTH_GAPS = AI_ROOT / "datasets" / "feedback" / "wet_lab_head_authorization_gap_actions.jsonl"
AUTH_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_report.json"
SEQUENCE_TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_project_sequences.template.jsonl"
SEQUENCE_INPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_project_sequences.local.jsonl"
SEQUENCE_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_project_sequence_intake_validation_report.json"
AUDIT_JSONL = AI_ROOT / "datasets" / "feedback" / "p28_feedback_intake_gap_audit.jsonl"
AUDIT_REPORT = AI_ROOT / "reports" / "p28_feedback_intake_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p28_feedback_intake_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    auth_rows = load_jsonl(AUTH_GAPS)
    auth_report = load_json(AUTH_REPORT)
    sequence_template = load_jsonl(SEQUENCE_TEMPLATE)
    sequence_input = load_jsonl(SEQUENCE_INPUT)
    sequence_validation = load_json(SEQUENCE_VALIDATION)
    audit_rows = load_jsonl(AUDIT_JSONL)
    audit_report = load_json(AUDIT_REPORT)
    failures: list[dict[str, Any]] = []
    expected_auth = len(auth_rows)
    expected_sequence = len(sequence_input) if sequence_input else len(sequence_template)
    expected_total = expected_auth + expected_sequence

    fail_if(len(audit_rows) != expected_total, failures, "audit_rows_expected", len(audit_rows), expected_total)
    fail_if(audit_report.get("audit_rows") != expected_total, failures, "audit_report_rows_expected", audit_report.get("audit_rows"), expected_total)
    fail_if(audit_report.get("authorization_worklist_rows") != expected_auth, failures, "authorization_rows_bound", audit_report.get("authorization_worklist_rows"), expected_auth)
    fail_if(audit_report.get("authorization_report_rows") != auth_report.get("authorization_worklist_rows"), failures, "authorization_report_rows_bound", audit_report.get("authorization_report_rows"), auth_report.get("authorization_worklist_rows"))
    fail_if(audit_report.get("authorization_report_ready_for_feedback_intake_rows") != 0, failures, "authorization_ready_for_feedback_intake_zero", audit_report.get("authorization_report_ready_for_feedback_intake_rows"), 0)
    fail_if(audit_report.get("parent_sequence_template_rows") != len(sequence_template), failures, "sequence_template_rows_bound", audit_report.get("parent_sequence_template_rows"), len(sequence_template))
    fail_if(audit_report.get("parent_sequence_input_rows") != len(sequence_input), failures, "sequence_input_rows_bound", audit_report.get("parent_sequence_input_rows"), len(sequence_input))
    fail_if(audit_report.get("parent_sequence_validation_approved_projects") != (sequence_validation.get("approved_projects") or []), failures, "sequence_validation_projects_bound", audit_report.get("parent_sequence_validation_approved_projects"), sequence_validation.get("approved_projects") or [])
    fail_if(audit_report.get("ready_for_feedback_intake_rows") != 0, failures, "report_ready_for_feedback_intake_zero", audit_report.get("ready_for_feedback_intake_rows"), 0)
    fail_if(audit_report.get("ready_for_numbering_audit") is not False, failures, "report_ready_for_numbering_audit_false", audit_report.get("ready_for_numbering_audit"), False)

    auth_audit = [row for row in audit_rows if row.get("gap_type") == "numeric_feedback_authorization"]
    sequence_audit = [row for row in audit_rows if row.get("gap_type") == "parent_sequence_intake"]
    fail_if(len(auth_audit) != expected_auth, failures, "authorization_audit_rows_exact", len(auth_audit), expected_auth)
    fail_if(len(sequence_audit) != expected_sequence, failures, "sequence_audit_rows_exact", len(sequence_audit), expected_sequence)

    expected_auth_by_id = {str(row.get("feedback_candidate_id")): row for row in auth_rows}
    for idx, row in enumerate(auth_audit):
        source = expected_auth_by_id.get(str(row.get("feedback_candidate_id")))
        if source is None:
            failures.append({"check": "authorization_source_row_present", "index": idx, "observed": row.get("feedback_candidate_id")})
            continue
        state = source.get("authorization_state") if isinstance(source.get("authorization_state"), dict) else {}
        fail_if(row.get("authorization_decision_present") is not (state.get("decision_present") is True), failures, "authorization_decision_present_bound", {"index": idx}, state.get("decision_present") is True)
        fail_if(row.get("authorization_valid") is not (state.get("valid") is True), failures, "authorization_valid_bound", {"index": idx}, state.get("valid") is True)
        fail_if(row.get("missing_or_invalid_fields") != (state.get("missing_or_invalid_fields") or []), failures, "authorization_missing_fields_bound", {"index": idx, "observed": row.get("missing_or_invalid_fields")}, state.get("missing_or_invalid_fields") or [])
        for field in ("ready_for_feedback_intake", "ready_for_training_import", "claim_eligible_now", "training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(row.get(field) is not False, failures, f"authorization_{field}_false", {"index": idx, "observed": row.get(field)}, False)

    sequence_source = sequence_input if sequence_input else sequence_template
    expected_sequence_by_id = {str(row.get("sequence_intake_id")): row for row in sequence_source}
    for idx, row in enumerate(sequence_audit):
        source = expected_sequence_by_id.get(str(row.get("sequence_intake_id")))
        if source is None:
            failures.append({"check": "sequence_source_row_present", "index": idx, "observed": row.get("sequence_intake_id")})
            continue
        expected_missing = [
            field for field in [
                "sequence_intake_id", "project_id", "sequence_id", "sequence_version", "sequence",
                "sequence_source", "reviewer", "reviewed_at", "review_basis",
                "approved_for_numbering_audit", "conditions", "residual_risks",
            ] if source.get(field) in (None, "", [])
        ]
        fail_if(row.get("missing_or_invalid_fields") != expected_missing, failures, "sequence_missing_fields_bound", {"index": idx, "observed": row.get("missing_or_invalid_fields")}, expected_missing)
        for field in ("approved_for_numbering_audit", "ready_for_numbering_audit", "ready_to_apply_numbering_flags", "training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(row.get(field) is not False, failures, f"sequence_{field}_false", {"index": idx, "observed": row.get(field)}, False)

    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        fail_if(audit_report.get(field) is not False, failures, f"report_{field}_false", audit_report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "authorization_rows": len(auth_audit),
        "authorization_blocked_rows": sum(1 for row in auth_audit if row.get("authorization_valid") is not True),
        "parent_sequence_rows": len(sequence_audit),
        "parent_sequence_blocked_rows": sum(1 for row in sequence_audit if row.get("ready_for_numbering_audit") is not True),
        "failures": failures,
        "ready_for_feedback_intake_rows": 0,
        "ready_for_numbering_audit": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. P28 authorization and parent-sequence gaps remain blocked and cannot create labels or training rows.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "audit_rows": validation["audit_rows"],
        "authorization_rows": validation["authorization_rows"],
        "authorization_blocked_rows": validation["authorization_blocked_rows"],
        "parent_sequence_rows": validation["parent_sequence_rows"],
        "parent_sequence_blocked_rows": validation["parent_sequence_blocked_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
