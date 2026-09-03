#!/usr/bin/env python3
"""Validate activity_risk training-import labels against formal evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LABELS = AI_ROOT / "datasets" / "training" / "activity_risk_training_import_labels.jsonl"
DECISIONS = AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_decisions.jsonl"
FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
AUTHORIZATIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
REPORT = AI_ROOT / "reports" / "activity_risk_training_import_label_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate activity_risk training-import labels")
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--feedback", type=Path, default=FEEDBACK)
    parser.add_argument("--authorizations", type=Path, default=AUTHORIZATIONS)
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()

    labels = load_jsonl(args.labels)
    decisions = load_jsonl(args.decisions)
    feedback_rows = load_jsonl(args.feedback)
    authorization_rows = load_jsonl(args.authorizations)
    decisions_by_feedback = {row.get("feedback_id"): row for row in decisions}
    feedback_by_id = {row.get("feedback_id"): row for row in feedback_rows}
    authorization_by_id = {row.get("authorization_id"): row for row in authorization_rows}

    failures: list[dict[str, Any]] = []
    fail_if(not args.labels.exists(), failures, "labels_file_present", str(args.labels), "existing file")
    fail_if(len(labels) != 6, failures, "training_import_label_rows_six", len(labels), 6)
    fail_if(len({row.get("training_import_label_id") for row in labels}) != len(labels), failures, "label_ids_unique", "duplicates", "unique")
    fail_if(len({row.get("feedback_id") for row in labels}) != len(labels), failures, "feedback_ids_unique", "duplicates", "unique")

    for row in labels:
        feedback_id = row.get("feedback_id")
        decision = decisions_by_feedback.get(feedback_id) or {}
        feedback = feedback_by_id.get(feedback_id) or {}
        authorization = authorization_by_id.get(row.get("authorization_id")) or {}
        fail_if(row.get("head") != "activity_risk", failures, "head_activity_risk", {"feedback_id": feedback_id, "value": row.get("head")}, "activity_risk")
        fail_if(row.get("label_value") != decision.get("activity_risk_label"), failures, "label_matches_formal_decision", {"feedback_id": feedback_id, "value": row.get("label_value")}, decision.get("activity_risk_label"))
        fail_if(decision.get("ready_for_training_import") is not True, failures, "decision_ready_for_training_import", {"feedback_id": feedback_id, "value": decision.get("ready_for_training_import")}, True)
        fail_if(decision.get("training_label_source") is not True, failures, "decision_training_label_source", {"feedback_id": feedback_id, "value": decision.get("training_label_source")}, True)
        fail_if(feedback.get("source") != "kwb_wet_lab", failures, "feedback_source_kwb_wet_lab", {"feedback_id": feedback_id, "value": feedback.get("source")}, "kwb_wet_lab")
        fail_if(feedback.get("assay_type") != "activity", failures, "feedback_assay_activity", {"feedback_id": feedback_id, "value": feedback.get("assay_type")}, "activity")
        fail_if(not isinstance(feedback.get("activity_relative_to_wt"), (int, float)) or isinstance(feedback.get("activity_relative_to_wt"), bool), failures, "feedback_numeric_activity", {"feedback_id": feedback_id, "value": feedback.get("activity_relative_to_wt")}, "number")
        fail_if(row.get("activity_relative_to_wt") != feedback.get("activity_relative_to_wt"), failures, "activity_value_matches_feedback", {"feedback_id": feedback_id, "value": row.get("activity_relative_to_wt")}, feedback.get("activity_relative_to_wt"))
        fail_if(feedback.get("numbering_verified") is not True, failures, "feedback_numbering_verified", {"feedback_id": feedback_id, "value": feedback.get("numbering_verified")}, True)
        fail_if(authorization.get("authorization_decision") != "approved_for_feedback_intake", failures, "authorization_approved", {"feedback_id": feedback_id, "value": authorization.get("authorization_decision")}, "approved_for_feedback_intake")
        fail_if("activity_risk_head" not in (authorization.get("approved_training_heads") or []), failures, "authorization_head_scope", {"feedback_id": feedback_id, "value": authorization.get("approved_training_heads")}, "activity_risk_head")
        fail_if(row.get("ready_for_training_import") is not True, failures, "row_ready_for_training_import", {"feedback_id": feedback_id, "value": row.get("ready_for_training_import")}, True)
        fail_if(row.get("safe_for_training_import") is not True, failures, "row_safe_for_training_import", {"feedback_id": feedback_id, "value": row.get("safe_for_training_import")}, True)
        fail_if(row.get("eligible_for_training_execution") is not False, failures, "row_training_execution_false", {"feedback_id": feedback_id, "value": row.get("eligible_for_training_execution")}, False)
        fail_if(int(row.get("replicate_count_counted_for_training") or 0) != 0, failures, "replicate_count_not_inferred", {"feedback_id": feedback_id, "value": row.get("replicate_count_counted_for_training")}, 0)
        for key in ("safe_for_model_claim", "customer_delivery_ready", "release_ready"):
            fail_if(row.get(key) is not False, failures, f"{key}_false", {"feedback_id": feedback_id, "value": row.get(key)}, False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "training_import_written_rows": len(labels) if not failures else 0,
        "training_import_label_rows": len(labels),
        "independent_group_count": len({row.get("mutation") for row in labels if row.get("mutation")}),
        "explicit_replicate_count": len({row.get("replicate_group_id") for row in labels if row.get("replicate_group_id")}),
        "replicate_rows_counted_for_training": sum(int(row.get("replicate_count_counted_for_training") or 0) for row in labels),
        "failures": failures,
        "safe_for_training_import": not failures and bool(labels),
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Validates materialized activity_risk training-import labels. Passing validation does not "
            "allow five-head training execution, model-quality claims, customer delivery, or release."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "training_import_written_rows": validation["training_import_written_rows"],
        "failures": len(failures),
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
