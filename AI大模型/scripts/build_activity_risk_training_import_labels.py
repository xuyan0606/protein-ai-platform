#!/usr/bin/env python3
"""Materialize activity_risk training-import labels from formal decisions.

This writer consumes only the already validated KWB wet-lab numeric feedback
formal labels. It does not start training, infer replicates, or open model
claim/release gates.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DECISIONS = AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_decisions.jsonl"
FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
AUTHORIZATIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
OUT = AI_ROOT / "datasets" / "training" / "activity_risk_training_import_labels.jsonl"
REPORT = AI_ROOT / "reports" / "activity_risk_training_import_label_report.json"


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def numeric_activity_feedback(row: dict[str, Any]) -> bool:
    return (
        row.get("source") == "kwb_wet_lab"
        and row.get("quantitative_assay_available") is True
        and row.get("assay_type") == "activity"
        and isinstance(row.get("activity_relative_to_wt"), (int, float))
        and not isinstance(row.get("activity_relative_to_wt"), bool)
    )


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


def build_row(
    decision: dict[str, Any],
    feedback: dict[str, Any],
    authorization: dict[str, Any],
    imported_at: str,
) -> dict[str, Any]:
    assay_condition = feedback.get("assay_condition") if isinstance(feedback.get("assay_condition"), dict) else {}
    return {
        "training_import_label_id": f"activity-risk-training-import::{decision.get('feedback_id')}",
        "head": "activity_risk",
        "label_name": "activity_risk_label",
        "label_value": decision.get("activity_risk_label"),
        "activity_risk_label": decision.get("activity_risk_label"),
        "label_source": "kwb_wet_lab_numeric_feedback",
        "training_label_source": True,
        "feedback_id": decision.get("feedback_id"),
        "formal_decision_id": decision.get("decision_id"),
        "feedback_candidate_id": decision.get("feedback_candidate_id"),
        "authorization_id": decision.get("authorization_id"),
        "authorization_decision": authorization.get("authorization_decision"),
        "authorization_qc_decision": authorization.get("qc_decision"),
        "authorization_reviewer": authorization.get("reviewer"),
        "authorization_reviewed_at": authorization.get("reviewed_at"),
        "project_id": feedback.get("project_id"),
        "enzyme_id": feedback.get("enzyme_id"),
        "uniprot_id": feedback.get("uniprot_id"),
        "mutation": feedback.get("mutation"),
        "canonical_position": feedback.get("canonical_position"),
        "assay_type": feedback.get("assay_type"),
        "metric": assay_condition.get("metric"),
        "ph": assay_condition.get("ph"),
        "batch_id": assay_condition.get("batch_id"),
        "sample_id": assay_condition.get("sample_id"),
        "control_sample_id": assay_condition.get("control_sample_id"),
        "activity_relative_to_wt": feedback.get("activity_relative_to_wt"),
        "source_outcome": feedback.get("outcome"),
        "data_granularity": feedback.get("data_granularity"),
        "numbering_verified": feedback.get("numbering_verified") is True,
        "source_trace_reviewed": decision.get("source_trace_reviewed") is True,
        "unit_condition_reviewed": decision.get("unit_condition_reviewed") is True,
        "batch_control_reviewed": decision.get("batch_control_reviewed") is True,
        "replicate_policy_reviewed": decision.get("replicate_policy_reviewed") is True,
        "replicate_decision": decision.get("replicate_decision"),
        "replicate_group_id": decision.get("replicate_group_id") or "",
        "replicate_count_counted_for_training": int(decision.get("replicate_count_counted_for_training") or 0),
        "imported_at": imported_at,
        "ready_for_training_import": True,
        "safe_for_training_import": True,
        "eligible_for_training_execution": False,
        "training_execution_block_reason": "below_five_head_sample_group_replicate_threshold",
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "policy": (
            "Materialized activity_risk training-import label. This is a real imported label "
            "artifact, but it does not satisfy five-head sample/group/replicate thresholds and "
            "does not authorize model-quality or release claims."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build activity_risk training-import labels")
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--feedback", type=Path, default=FEEDBACK)
    parser.add_argument("--authorizations", type=Path, default=AUTHORIZATIONS)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    imported_at = datetime.now(timezone.utc).isoformat()
    decisions = load_jsonl(args.decisions)
    feedback_rows = load_jsonl(args.feedback)
    authorization_rows = load_jsonl(args.authorizations)
    feedback_by_id = {row.get("feedback_id"): row for row in feedback_rows if isinstance(row.get("feedback_id"), str)}
    authorization_by_id = {
        row.get("authorization_id"): row for row in authorization_rows if isinstance(row.get("authorization_id"), str)
    }

    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for decision in decisions:
        feedback_id = decision.get("feedback_id")
        authorization_id = decision.get("authorization_id")
        feedback = feedback_by_id.get(feedback_id)
        authorization = authorization_by_id.get(authorization_id)
        if not feedback:
            skipped.append({"feedback_id": feedback_id, "reason": "missing_feedback_row"})
            continue
        if not authorization:
            skipped.append({"feedback_id": feedback_id, "authorization_id": authorization_id, "reason": "missing_authorization"})
            continue
        if not numeric_activity_feedback(feedback):
            skipped.append({"feedback_id": feedback_id, "reason": "feedback_not_numeric_activity"})
            continue
        if not authorization_ready(authorization):
            skipped.append({"feedback_id": feedback_id, "authorization_id": authorization_id, "reason": "authorization_not_ready"})
            continue
        if decision.get("ready_for_training_import") is not True or decision.get("training_label_source") is not True:
            skipped.append({"feedback_id": feedback_id, "reason": "formal_decision_not_training_import_ready"})
            continue
        rows.append(build_row(decision, feedback, authorization, imported_at))

    rows.sort(key=lambda row: str(row.get("training_import_label_id")))
    write_jsonl(args.output, rows)

    label_counts = Counter(str(row.get("label_value")) for row in rows)
    group_count = len({row.get("mutation") for row in rows if row.get("mutation")})
    report = {
        "created_at": imported_at,
        "local_only": True,
        "source_decision_rows": len(decisions),
        "source_numeric_feedback_rows": sum(1 for row in feedback_rows if numeric_activity_feedback(row)),
        "source_authorization_rows": len(authorization_rows),
        "training_import_written_rows": len(rows),
        "training_import_label_rows": len(rows),
        "imported_heads": ["activity_risk"] if rows else [],
        "label_counts": dict(sorted(label_counts.items())),
        "independent_group_count": group_count,
        "explicit_replicate_count": len({row.get("replicate_group_id") for row in rows if row.get("replicate_group_id")}),
        "replicate_rows_counted_for_training": sum(int(row.get("replicate_count_counted_for_training") or 0) for row in rows),
        "skipped_rows": skipped,
        "output": str(args.output.relative_to(AI_ROOT)),
        "safe_for_training_import": bool(rows) and not skipped,
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "This artifact materializes reviewed KWB wet-lab activity_risk labels for training import only. "
            "Training execution, model-quality claims, customer delivery, and release remain separately gated."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "training_import_written_rows": report["training_import_written_rows"],
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
