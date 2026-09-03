#!/usr/bin/env python3
"""Build a lineage ledger for activity_risk formal labels.

The ledger traces each activity_risk label from feedback row to authorization,
formal label decision, training-import contract, and five-head threshold state.
It is evidence-only and does not write training rows or open model/release gates.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
AUTHORIZATIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
DECISIONS = AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_decisions.jsonl"
TRAINING_CONTRACT = AI_ROOT / "reports" / "training_label_import_contract_report.json"
THRESHOLD_REPORT = AI_ROOT / "reports" / "five_head_training_threshold_report.json"
OUT = AI_ROOT / "datasets" / "governance" / "activity_risk_training_lineage_ledger.jsonl"
REPORT = AI_ROOT / "reports" / "activity_risk_training_lineage_ledger_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: row must be a JSON object")
        rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def nested(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build activity_risk training lineage ledger")
    parser.add_argument("--output-jsonl", type=Path, default=OUT)
    parser.add_argument("--output-report", type=Path, default=REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    feedback_rows = load_jsonl(FEEDBACK)
    authorization_rows = load_jsonl(AUTHORIZATIONS)
    decision_rows = load_jsonl(DECISIONS)
    training_contract = load_json(TRAINING_CONTRACT)
    threshold = load_json(THRESHOLD_REPORT)
    activity_threshold = ((threshold.get("heads") or {}).get("activity_risk") or {})

    feedback_by_id = {row.get("feedback_id"): row for row in feedback_rows if row.get("feedback_id")}
    auth_by_candidate = {
        row.get("feedback_candidate_id"): row
        for row in authorization_rows
        if row.get("feedback_candidate_id")
    }
    contract_totals = (
        training_contract.get("contract_totals")
        if isinstance(training_contract.get("contract_totals"), dict)
        else {}
    )

    ledger_rows: list[dict[str, Any]] = []
    for index, decision in enumerate(sorted(decision_rows, key=lambda row: str(row.get("decision_id"))), start=1):
        feedback = feedback_by_id.get(decision.get("feedback_id"), {})
        authorization = auth_by_candidate.get(decision.get("feedback_candidate_id"), {})
        condition = nested(feedback, "assay_condition")
        threshold_metrics = activity_threshold.get("label_metrics") if isinstance(activity_threshold.get("label_metrics"), dict) else {}
        threshold_checks = activity_threshold.get("threshold_checks") if isinstance(activity_threshold.get("threshold_checks"), dict) else {}
        ledger_rows.append({
            "ledger_id": f"activity-risk-lineage::{index}",
            "feedback_id": decision.get("feedback_id"),
            "feedback_present": bool(feedback),
            "feedback_candidate_id": decision.get("feedback_candidate_id"),
            "authorization_id": decision.get("authorization_id"),
            "authorization_present": bool(authorization),
            "authorization_decision": decision.get("authorization_decision"),
            "authorization_qc_decision": decision.get("authorization_qc_decision"),
            "authorization_reviewed_at": decision.get("authorization_reviewed_at"),
            "formal_decision_id": decision.get("decision_id"),
            "formal_label_present": decision.get("ready_for_activity_risk_head_label") is True,
            "activity_risk_label": decision.get("activity_risk_label"),
            "mutation": decision.get("mutation"),
            "canonical_position": decision.get("canonical_position"),
            "metric": decision.get("metric") or condition.get("metric"),
            "ph": decision.get("ph") or condition.get("ph"),
            "batch_id": decision.get("batch_id") or condition.get("batch_id"),
            "sample_id": decision.get("sample_id") or condition.get("sample_id"),
            "control_sample_id": decision.get("control_sample_id") or condition.get("control_sample_id"),
            "activity_relative_to_wt": decision.get("activity_relative_to_wt"),
            "source_trace_reviewed": decision.get("source_trace_reviewed") is True,
            "numbering_reviewed": decision.get("numbering_reviewed") is True,
            "unit_condition_reviewed": decision.get("unit_condition_reviewed") is True,
            "batch_control_reviewed": decision.get("batch_control_reviewed") is True,
            "replicate_policy_reviewed": decision.get("replicate_policy_reviewed") is True,
            "replicate_decision": decision.get("replicate_decision"),
            "replicate_count_counted_for_training": int(decision.get("replicate_count_counted_for_training") or 0),
            "training_import_contract_source": "numeric_feedback_training_import_semantic_guard",
            "source_training_import_eligible": decision.get("ready_for_training_import") is True,
            "global_training_import_eligible_rows": int(contract_totals.get("training_import_eligible_rows") or 0),
            "five_head_threshold_label_rows": int(activity_threshold.get("label_rows") or 0),
            "five_head_threshold_group_count": int(threshold_metrics.get("group_count") or 0),
            "five_head_threshold_replicate_count": int(threshold_metrics.get("replicate_count") or 0),
            "five_head_thresholds_met": activity_threshold.get("thresholds_met") is True,
            "five_head_threshold_checks": threshold_checks,
            "training_execution_allowed": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Lineage evidence only. This row can explain training-import eligibility, but it does not write training data or satisfy five-head execution thresholds.",
        })

    write_jsonl(args.output_jsonl, ledger_rows)
    missing_feedback = [row["feedback_id"] for row in ledger_rows if not row["feedback_present"]]
    missing_authorization = [row["feedback_candidate_id"] for row in ledger_rows if not row["authorization_present"]]
    report = {
        "created_at": created_at,
        "local_only": True,
        "ledger_rows": len(ledger_rows),
        "feedback_matched_rows": sum(1 for row in ledger_rows if row["feedback_present"]),
        "authorization_matched_rows": sum(1 for row in ledger_rows if row["authorization_present"]),
        "formal_label_rows": sum(1 for row in ledger_rows if row["formal_label_present"]),
        "source_training_import_eligible_rows": sum(1 for row in ledger_rows if row["source_training_import_eligible"]),
        "replicate_rows_counted_for_training": sum(row["replicate_count_counted_for_training"] for row in ledger_rows),
        "missing_feedback_ids": missing_feedback,
        "missing_authorization_candidate_ids": missing_authorization,
        "activity_risk_threshold": {
            "label_rows": activity_threshold.get("label_rows"),
            "group_count": ((activity_threshold.get("label_metrics") or {}).get("group_count")),
            "replicate_count": ((activity_threshold.get("label_metrics") or {}).get("replicate_count")),
            "thresholds_met": activity_threshold.get("thresholds_met"),
            "blockers": activity_threshold.get("blockers"),
        },
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output_jsonl": rel(args.output_jsonl),
        "policy": "Activity-risk lineage ledger only. It traces six formal labels and their remaining threshold blockers without importing training rows or opening model/release gates.",
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "ledger_rows": report["ledger_rows"],
        "feedback_matched_rows": report["feedback_matched_rows"],
        "authorization_matched_rows": report["authorization_matched_rows"],
        "source_training_import_eligible_rows": report["source_training_import_eligible_rows"],
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "output": rel(args.output_report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
