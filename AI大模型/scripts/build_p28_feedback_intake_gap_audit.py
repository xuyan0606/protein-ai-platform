#!/usr/bin/env python3
"""Build a source-bound audit for P28 authorization and parent-sequence intake gaps."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
AUTH_GAPS = AI_ROOT / "datasets" / "feedback" / "wet_lab_head_authorization_gap_actions.jsonl"
AUTH_WORKLIST_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_report.json"
SEQUENCE_TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_project_sequences.template.jsonl"
SEQUENCE_INPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_project_sequences.local.jsonl"
SEQUENCE_REQUESTS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_sequence_request_packets.jsonl"
SEQUENCE_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_project_sequence_intake_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "feedback" / "p28_feedback_intake_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p28_feedback_intake_gap_audit_report.json"

AUTH_REQUIRED_FIELDS = [
    "authorization_decision_row",
    "authorization_decision",
    "qc_decision",
    "reviewer",
    "reviewed_at",
    "authorization_basis",
    "source_trace_reviewed",
    "numbering_reviewed",
    "unit_condition_reviewed",
    "batch_control_reviewed",
    "replicate_policy_reviewed",
]
SEQUENCE_REQUIRED_FIELDS = [
    "sequence_intake_id",
    "project_id",
    "sequence_id",
    "sequence_version",
    "sequence",
    "sequence_source",
    "reviewer",
    "reviewed_at",
    "review_basis",
    "approved_for_numbering_audit",
    "conditions",
    "residual_risks",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    auth_rows = load_jsonl(AUTH_GAPS)
    auth_report = load_json(AUTH_WORKLIST_REPORT)
    sequence_template = load_jsonl(SEQUENCE_TEMPLATE)
    sequence_input = load_jsonl(SEQUENCE_INPUT)
    sequence_requests = load_jsonl(SEQUENCE_REQUESTS)
    sequence_validation = load_json(SEQUENCE_VALIDATION)
    audit_rows: list[dict[str, Any]] = []
    missing_auth_counts: Counter[str] = Counter()

    for row in auth_rows:
        state = row.get("authorization_state") if isinstance(row.get("authorization_state"), dict) else {}
        missing_fields = list(state.get("missing_or_invalid_fields") or [])
        for field in missing_fields:
            missing_auth_counts[str(field)] += 1
        audit_rows.append({
            "created_at": created_at,
            "local_only": True,
            "audit_id": f"p28-authorization-gap::{row.get('feedback_candidate_id')}",
            "gap_type": "numeric_feedback_authorization",
            "feedback_candidate_id": row.get("feedback_candidate_id"),
            "variant": row.get("variant"),
            "target_head": row.get("target_head"),
            "metric_name": row.get("metric_name"),
            "execution_order": row.get("execution_order"),
            "authorization_decision_present": state.get("decision_present") is True,
            "authorization_valid": state.get("valid") is True,
            "missing_or_invalid_fields": missing_fields,
            "ready_for_feedback_intake": False,
            "ready_for_training_import": False,
            "claim_eligible_now": False,
            "source_authorization_gap_actions": "datasets/feedback/wet_lab_head_authorization_gap_actions.jsonl",
            "source_authorization_worklist_report": "reports/wet_lab_mutant_library_feedback_authorization_worklist_report.json",
            "training_import_allowed": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "policy": "Authorization/intake audit only; does not write decisions, preflight rows, feedback rows, labels, or training imports.",
        })

    sequence_rows = sequence_input if sequence_input else sequence_template
    request_by_project = {
        str(row.get("project_id")): row for row in sequence_requests if row.get("project_id")
    }
    for row in sequence_rows:
        project_id = str(row.get("project_id") or "")
        missing_fields = [
            field for field in SEQUENCE_REQUIRED_FIELDS
            if row.get(field) in (None, "", [])
        ]
        audit_rows.append({
            "created_at": created_at,
            "local_only": True,
            "audit_id": f"p28-parent-sequence-gap::{row.get('sequence_intake_id')}",
            "gap_type": "parent_sequence_intake",
            "project_id": project_id,
            "sequence_intake_id": row.get("sequence_intake_id"),
            "sequence_request_status": request_by_project.get(project_id, {}).get("status"),
            "missing_or_invalid_fields": missing_fields,
            "sequence_input_rows": len(sequence_input),
            "approved_for_numbering_audit": row.get("approved_for_numbering_audit") is True,
            "ready_for_numbering_audit": False,
            "ready_to_apply_numbering_flags": False,
            "source_sequence_template": "datasets/feedback/wet_lab_mutant_library_project_sequences.template.jsonl",
            "source_sequence_input": "datasets/feedback/wet_lab_mutant_library_project_sequences.local.jsonl",
            "source_sequence_requests": "datasets/feedback/wet_lab_mutant_library_sequence_request_packets.jsonl",
            "source_sequence_validation_report": "reports/wet_lab_mutant_library_project_sequence_intake_validation_report.json",
            "training_import_allowed": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "policy": "Parent-sequence intake audit only; does not accept a sequence, run numbering audit, update flags, or create labels.",
        })

    auth_blocked = sum(
        1 for row in auth_rows
        if (row.get("authorization_state") or {}).get("valid") is not True
    )
    auth_decision_present = sum(
        1 for row in auth_rows
        if (row.get("authorization_state") or {}).get("decision_present") is True
    )
    sequence_blocked = sum(1 for row in audit_rows if row["gap_type"] == "parent_sequence_intake")
    report = {
        "created_at": created_at,
        "local_only": True,
        "audit_rows": len(audit_rows),
        "authorization_worklist_rows": len(auth_rows),
        "authorization_decision_present_rows": auth_decision_present,
        "authorization_blocked_rows": auth_blocked,
        "authorization_report_rows": auth_report.get("authorization_worklist_rows"),
        "authorization_report_ready_for_feedback_intake_rows": auth_report.get("ready_for_feedback_intake_rows"),
        "authorization_missing_field_counts": dict(sorted(missing_auth_counts.items())),
        "parent_sequence_projects": sorted({str(row.get("project_id")) for row in sequence_rows}),
        "parent_sequence_template_rows": len(sequence_template),
        "parent_sequence_input_rows": len(sequence_input),
        "parent_sequence_blocked_rows": sequence_blocked,
        "parent_sequence_validation_approved_projects": sequence_validation.get("approved_projects") or [],
        "sequence_request_rows": len(sequence_requests),
        "ready_for_feedback_intake_rows": 0,
        "ready_for_numbering_audit": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/feedback/p28_feedback_intake_gap_audit.jsonl",
        "policy": "P28 feedback authorization and parent-sequence gap audit only. No formal decisions, intake, labels, training, claims, release, or production actions are performed.",
    }
    write_jsonl(OUT_JSONL, audit_rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "authorization_worklist_rows": report["authorization_worklist_rows"],
        "authorization_blocked_rows": report["authorization_blocked_rows"],
        "parent_sequence_blocked_rows": report["parent_sequence_blocked_rows"],
        "ready_for_feedback_intake_rows": 0,
        "ready_for_numbering_audit": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
