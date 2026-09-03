#!/usr/bin/env python3
"""Build the wet-lab feedback authorization consumption contract."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = AI_ROOT / "reports" / "wet_lab_feedback_authorization_contract_report.json"

REPORTS = {
    "candidate_report": "reports/wet_lab_mutant_library_feedback_candidate_report.json",
    "authorization_report": "reports/wet_lab_mutant_library_feedback_authorization_validation_report.json",
    "preflight_report": "reports/wet_lab_mutant_library_feedback_preflight_report.json",
    "apply_plan_report": "reports/wet_lab_mutant_library_feedback_intake_apply_plan_report.json",
    "duplicate_audit_report": "reports/wet_lab_feedback_apply_duplicate_audit_report.json",
    "duplicate_audit_validation_report": "reports/wet_lab_feedback_apply_duplicate_audit_validation_report.json",
    "semantic_guard_report": "reports/feedback_training_import_semantic_guard_report.json",
}

JSONL = {
    "candidate_rows": "datasets/feedback/wet_lab_mutant_library_feedback_candidates.jsonl",
    "authorization_rows": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
    "preflight_rows": "datasets/feedback/wet_lab_mutant_library_feedback_preflight.jsonl",
    "apply_plan_rows": "datasets/feedback/wet_lab_mutant_library_feedback_intake_apply_plan.jsonl",
    "duplicate_audit_rows": "datasets/feedback/wet_lab_feedback_apply_duplicate_audit.jsonl",
}


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT)) if path.is_absolute() else str(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl_profile(path: Path) -> dict[str, Any]:
    profile = {
        "path": rel(path),
        "exists": path.exists(),
        "rows": 0,
        "valid_json_rows": 0,
        "invalid_json_rows": 0,
        "rows_with_numeric_training_candidate": 0,
        "rows_with_authorized_decision": 0,
        "rows_with_ready_for_training_import": 0,
        "rows_with_claim_eligible_now": 0,
        "rows_with_safe_for_model_claim": 0,
        "rows_with_release_ready": 0,
    }
    if not path.exists():
        return profile

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        profile["rows"] += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            profile["invalid_json_rows"] += 1
            continue
        if not isinstance(row, dict):
            profile["invalid_json_rows"] += 1
            continue
        profile["valid_json_rows"] += 1
        if row.get("numeric_training_candidate") is True:
            profile["rows_with_numeric_training_candidate"] += 1
        if row.get("authorized_for_feedback_intake") is True or row.get("authorization_decision") == "approved_for_feedback_intake":
            profile["rows_with_authorized_decision"] += 1
        if row.get("ready_for_training_import") is True:
            profile["rows_with_ready_for_training_import"] += 1
        if row.get("claim_eligible_now") is True:
            profile["rows_with_claim_eligible_now"] += 1
        if row.get("safe_for_model_claim") is True:
            profile["rows_with_safe_for_model_claim"] += 1
        if row.get("release_ready") is True:
            profile["rows_with_release_ready"] += 1
    return profile


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback authorization consumption contract")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report_paths = {name: AI_ROOT / path for name, path in REPORTS.items()}
    jsonl_paths = {name: AI_ROOT / path for name, path in JSONL.items()}
    reports = {name: load_json(path) for name, path in report_paths.items()}
    profiles = {name: load_jsonl_profile(path) for name, path in jsonl_paths.items()}

    candidate_report = reports["candidate_report"]
    authorization_report = reports["authorization_report"]
    preflight_report = reports["preflight_report"]
    apply_plan_report = reports["apply_plan_report"]
    duplicate_audit_report = reports["duplicate_audit_report"]
    duplicate_audit_validation_report = reports["duplicate_audit_validation_report"]
    semantic_guard_report = reports["semantic_guard_report"]

    candidate_rows = as_int(candidate_report.get("candidate_rows"))
    numeric_candidate_rows = as_int(candidate_report.get("numeric_training_candidate_rows"))
    authorization_rows = as_int(authorization_report.get("authorization_rows"))
    authorized_rows = as_int(authorization_report.get("authorized_rows"))
    preflight_rows = as_int(preflight_report.get("preflight_rows"))
    apply_plan_rows = as_int(apply_plan_report.get("apply_plan_rows"))
    ready_for_training_import_rows = max(
        as_int(authorization_report.get("ready_for_training_import_rows")),
        as_int(preflight_report.get("ready_for_training_import_rows")),
        as_int(apply_plan_report.get("ready_for_training_import_rows")),
    )
    claim_eligible_rows_now = max(
        as_int(authorization_report.get("claim_eligible_rows_now")),
        as_int(preflight_report.get("claim_eligible_rows_now")),
        as_int(apply_plan_report.get("claim_eligible_rows_now")),
    )

    source_values = {
        "wet_lab_candidate_rows": candidate_rows,
        "numeric_training_candidate_rows": numeric_candidate_rows,
        "authorization_rows": authorization_rows,
        "authorized_rows": authorized_rows,
        "preflight_rows": preflight_rows,
        "apply_plan_rows": apply_plan_rows,
        "ready_for_training_import_rows": ready_for_training_import_rows,
        "claim_eligible_rows_now": claim_eligible_rows_now,
        "numeric_training_import_eligible": as_int(
            semantic_guard_report.get("numeric_training_import_eligible")
        ),
        "apply_duplicate_already_represented_rows": as_int(duplicate_audit_report.get("already_represented_rows")),
        "apply_duplicate_new_feedback_only_rows": as_int(duplicate_audit_report.get("new_feedback_only_rows")),
        "apply_duplicate_safe_to_append_rows": as_int(duplicate_audit_report.get("safe_to_append_rows")),
        "apply_duplicate_training_import_rows": as_int(
            duplicate_audit_report.get("training_import_eligible_from_apply_plan_rows")
        ),
        "apply_duplicate_validation_success": duplicate_audit_validation_report.get("success"),
        "semantic_guard_claim_eligible_rows": as_int(semantic_guard_report.get("claim_eligible_rows")),
        "safe_for_model_claim": semantic_guard_report.get("safe_for_model_claim"),
        "release_ready": semantic_guard_report.get("release_ready"),
    }

    expected_state = {
        "wet_lab_candidate_rows": 445,
        "numeric_training_candidate_rows": 12,
        "authorization_rows": authorization_rows,
        "authorized_rows": authorized_rows,
        "preflight_rows": preflight_rows,
        "apply_plan_rows": apply_plan_rows,
        "ready_for_training_import_rows": ready_for_training_import_rows,
        "claim_eligible_rows_now": claim_eligible_rows_now,
    }
    source_state_matches_expected = (
        candidate_rows == 445
        and numeric_candidate_rows == 12
        and authorized_rows <= authorization_rows
        and preflight_rows <= authorized_rows
        and apply_plan_rows <= authorized_rows
        and ready_for_training_import_rows == 0
        and claim_eligible_rows_now == 0
        and as_int(duplicate_audit_report.get("safe_to_append_rows")) == 0
        and as_int(duplicate_audit_report.get("training_import_eligible_from_apply_plan_rows")) == 0
        and duplicate_audit_validation_report.get("success") is True
    )
    missing_reports = [path for name, path in REPORTS.items() if not report_paths[name].exists()]
    missing_jsonl = [path for name, path in JSONL.items() if not jsonl_paths[name].exists()]

    report = {
        "report_id": "wet_lab_feedback_authorization_contract_report",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": source_state_matches_expected and not missing_reports and not missing_jsonl,
        "source_reports": REPORTS,
        "source_jsonl": JSONL,
        "source_values": source_values,
        "expected_current_state": expected_state,
        "source_state_matches_expected": source_state_matches_expected,
        "candidate_rows": candidate_rows,
        "numeric_training_candidate_rows": numeric_candidate_rows,
        "authorization_rows": authorization_rows,
        "authorized_rows": authorized_rows,
        "preflight_rows": preflight_rows,
        "apply_plan_rows": apply_plan_rows,
        "ready_for_training_import_rows": ready_for_training_import_rows,
        "claim_eligible_rows_now": claim_eligible_rows_now,
        "candidate_jsonl_rows": profiles["candidate_rows"]["rows"],
        "authorization_jsonl_rows": profiles["authorization_rows"]["rows"],
        "preflight_jsonl_rows": profiles["preflight_rows"]["rows"],
        "apply_plan_jsonl_rows": profiles["apply_plan_rows"]["rows"],
        "missing_reports": missing_reports,
        "missing_jsonl": missing_jsonl,
        "jsonl_rows": profiles,
        "consumption_contract": {
            "candidate_evidence_exists": candidate_rows > 0,
            "numeric_candidates_are_candidates_only": True,
            "human_authorization_required_before_preflight": True,
            "authorization_consumed_candidate_rows": authorized_rows,
            "preflight_consumed_authorized_rows": preflight_rows,
            "intake_apply_plan_consumed_preflight_rows": apply_plan_rows,
            "duplicate_audit_already_represented_rows": as_int(
                duplicate_audit_report.get("already_represented_rows")
            ),
            "duplicate_audit_new_feedback_only_rows": as_int(duplicate_audit_report.get("new_feedback_only_rows")),
            "duplicate_audit_safe_to_append_rows": as_int(duplicate_audit_report.get("safe_to_append_rows")),
            "training_import_consumed_rows": as_int(
                semantic_guard_report.get("numeric_training_import_eligible")
            ),
            "model_claim_consumed_rows": claim_eligible_rows_now,
            "authorization_required_for_each_stage": True,
            "qualitative_feedback_is_not_numeric_training_import": True,
        },
        "stage_status": {
            "wet_lab_candidates_present": candidate_rows > 0,
            "human_authorization_present": authorized_rows > 0,
            "preflight_consumption_allowed": authorized_rows > 0 and preflight_rows > 0,
            "intake_consumption_allowed": preflight_rows > 0 and apply_plan_rows > 0,
            "training_import_allowed": as_int(
                semantic_guard_report.get("numeric_training_import_eligible")
            ) > 0,
            "model_claim_allowed": claim_eligible_rows_now > 0,
        },
        "safety_flags": {
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        "blocking_reasons": [
            "E331Q critical tradeoff rows remain unapproved",
            "thermal retention rows are not converted into dTm/ddG stability labels",
            "apply-plan duplicate audit has zero safe-to-append rows",
            "model claims require independent strict supervised, benchmark and release gates",
        ],
        "policy": (
            "Real wet-lab candidates may be reported as evidence, but candidate presence or numeric candidate "
            "status is never authorization. Validated authorizations may enter preflight and local feedback "
            "intake; model claims and release remain blocked until independent downstream gates pass."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "wet_lab_candidate_rows": candidate_rows,
        "numeric_training_candidate_rows": numeric_candidate_rows,
        "authorization_rows": authorization_rows,
        "authorized_rows": authorized_rows,
        "preflight_rows": preflight_rows,
        "apply_plan_rows": apply_plan_rows,
        "ready_for_training_import_rows": ready_for_training_import_rows,
        "claim_eligible_rows_now": claim_eligible_rows_now,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
