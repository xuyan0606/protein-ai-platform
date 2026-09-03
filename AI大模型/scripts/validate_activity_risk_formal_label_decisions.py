#!/usr/bin/env python3
"""Validate formal activity_risk decisions against source feedback."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
AUTHORIZATIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
DECISIONS = AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_decisions.jsonl"
REPORT = AI_ROOT / "reports" / "activity_risk_formal_label_decision_validation_report.json"
LABEL_BY_OUTCOME = {"go": "low_activity_risk", "watch": "watch_activity_risk", "no_go": "high_activity_risk"}
WETLAB_CANDIDATE_RE = re.compile(r"wetlab-mutlib-[0-9a-f]{20}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def is_numeric_activity_feedback(row: dict[str, Any]) -> bool:
    return (
        row.get("source") == "kwb_wet_lab"
        and row.get("quantitative_assay_available") is True
        and row.get("assay_type") == "activity"
        and isinstance(row.get("activity_relative_to_wt"), (int, float))
    )


def wetlab_candidate_id(row: dict[str, Any]) -> str:
    explicit = row.get("feedback_candidate_id")
    if isinstance(explicit, str) and explicit:
        return explicit
    notes = str(row.get("notes") or "")
    match = WETLAB_CANDIDATE_RE.search(notes)
    return match.group(0) if match else ""


def authorization_ready(row: dict[str, Any]) -> bool:
    return (
        row.get("authorization_decision") == "approved_for_feedback_intake"
        and "activity_risk_head" in (row.get("approved_training_heads") or [])
        and row.get("source_trace_reviewed") is True
        and row.get("numbering_reviewed") is True
        and row.get("unit_condition_reviewed") is True
        and row.get("batch_control_reviewed") is True
        and row.get("replicate_policy_reviewed") is True
        and str(row.get("qc_decision") or "") in {"pass", "pass_with_conditions"}
    )


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate activity_risk formal label decisions")
    parser.add_argument("--feedback", type=Path, default=FEEDBACK)
    parser.add_argument("--authorizations", type=Path, default=AUTHORIZATIONS)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()

    source_rows = [row for row in load_jsonl(args.feedback) if is_numeric_activity_feedback(row)]
    authorization_rows = load_jsonl(args.authorizations)
    decisions = load_jsonl(args.decisions)
    authorizations_by_candidate_id = {
        str(row.get("feedback_candidate_id")): row
        for row in authorization_rows
        if isinstance(row.get("feedback_candidate_id"), str)
    }
    authorized_source_rows = []
    unauthorized_source_rows = []
    for row in source_rows:
        candidate_id = wetlab_candidate_id(row)
        authorization = authorizations_by_candidate_id.get(candidate_id)
        if candidate_id and authorization and authorization_ready(authorization):
            authorized_source_rows.append(row)
        else:
            unauthorized_source_rows.append({
                "feedback_id": row.get("feedback_id"),
                "feedback_candidate_id": candidate_id,
                "reason": "missing_or_invalid_activity_risk_authorization",
            })

    by_source = {row.get("feedback_id"): row for row in authorized_source_rows}
    by_decision = {row.get("feedback_id"): row for row in decisions}
    failures: list[dict[str, Any]] = []

    fail_if(len(source_rows) != 6, failures, "source_numeric_activity_rows", len(source_rows), 6)
    fail_if(bool(unauthorized_source_rows), failures, "all_numeric_activity_rows_have_authorization", unauthorized_source_rows, [])
    fail_if(set(by_source) != set(by_decision), failures, "decision_ids_cover_source", sorted(by_decision), sorted(by_source))
    for feedback_id, source in by_source.items():
        decision = by_decision.get(feedback_id) or {}
        candidate_id = wetlab_candidate_id(source)
        authorization = authorizations_by_candidate_id.get(candidate_id) or {}
        expected_label = LABEL_BY_OUTCOME.get(str(source.get("outcome") or ""))
        fail_if(not expected_label, failures, "source_outcome_supported", {"feedback_id": feedback_id, "outcome": source.get("outcome")}, sorted(LABEL_BY_OUTCOME))
        fail_if(decision.get("activity_risk_label") != expected_label, failures, "label_matches_source_outcome", {"feedback_id": feedback_id, "label": decision.get("activity_risk_label")}, expected_label)
        fail_if(decision.get("feedback_candidate_id") != candidate_id, failures, "feedback_candidate_id_matches_source", {"feedback_id": feedback_id, "value": decision.get("feedback_candidate_id")}, candidate_id)
        fail_if(decision.get("authorization_id") != authorization.get("authorization_id"), failures, "authorization_id_matches_authorization", {"feedback_id": feedback_id, "value": decision.get("authorization_id")}, authorization.get("authorization_id"))
        fail_if(decision.get("authorization_decision") != "approved_for_feedback_intake", failures, "authorization_decision_approved", {"feedback_id": feedback_id, "value": decision.get("authorization_decision")}, "approved_for_feedback_intake")
        fail_if(decision.get("authorization_qc_decision") not in {"pass", "pass_with_conditions"}, failures, "authorization_qc_passed", {"feedback_id": feedback_id, "value": decision.get("authorization_qc_decision")}, "pass|pass_with_conditions")
        fail_if(decision.get("ready_for_activity_risk_head_label") is not True, failures, "ready_for_head_label_true", {"feedback_id": feedback_id, "value": decision.get("ready_for_activity_risk_head_label")}, True)
        fail_if(decision.get("ready_for_training_import") is not True, failures, "ready_for_training_import_true", {"feedback_id": feedback_id, "value": decision.get("ready_for_training_import")}, True)
        fail_if(decision.get("replicate_decision") != "single_measurement_not_replicate", failures, "replicate_not_inferred", {"feedback_id": feedback_id, "value": decision.get("replicate_decision")}, "single_measurement_not_replicate")
        fail_if(int(decision.get("replicate_count_counted_for_training") or 0) != 0, failures, "replicate_count_zero", {"feedback_id": feedback_id, "value": decision.get("replicate_count_counted_for_training")}, 0)
        fail_if(decision.get("safe_for_model_claim") is not False, failures, "safe_for_model_claim_false", {"feedback_id": feedback_id, "value": decision.get("safe_for_model_claim")}, False)
        fail_if(decision.get("release_ready") is not False, failures, "release_ready_false", {"feedback_id": feedback_id, "value": decision.get("release_ready")}, False)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "source_numeric_activity_rows": len(source_rows),
        "authorization_rows": len(authorization_rows),
        "authorized_numeric_activity_source_rows": len(authorized_source_rows),
        "unauthorized_numeric_activity_source_rows": len(unauthorized_source_rows),
        "formal_decision_rows": len(decisions),
        "activity_risk_label_rows_created": len(decisions) if not failures else 0,
        "ready_for_training_import_rows": len(decisions) if not failures else 0,
        "replicate_rows_counted_for_training": 0,
        "failures": failures,
        "safe_for_training_import": not failures and bool(decisions),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Formal activity_risk labels are valid only for KWB numeric activity feedback with matching reviewed authorization for the activity_risk head; replicate and model/release gates remain fail-closed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "formal_decision_rows": report["formal_decision_rows"],
        "activity_risk_label_rows_created": report["activity_risk_label_rows_created"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
