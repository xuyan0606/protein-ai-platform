#!/usr/bin/env python3
"""Build formal activity_risk label decisions from already-authorized feedback.

This uses existing KWB wet-lab numeric feedback and the user-authorized
go/watch outcome already attached to those records. It does not infer
replicates or open model/release gates.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
AUTHORIZATIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
OUT = AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_decisions.jsonl"
REPORT = AI_ROOT / "reports" / "activity_risk_formal_label_decision_report.json"
WETLAB_CANDIDATE_RE = re.compile(r"wetlab-mutlib-[0-9a-f]{20}")

LABEL_BY_OUTCOME = {
    "go": "low_activity_risk",
    "watch": "watch_activity_risk",
    "no_go": "high_activity_risk",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def is_numeric_activity_feedback(row: dict[str, Any]) -> bool:
    return (
        row.get("source") == "kwb_wet_lab"
        and row.get("quantitative_assay_available") is True
        and row.get("assay_type") == "activity"
        and isinstance(row.get("activity_relative_to_wt"), (int, float))
    )


def condition(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("assay_condition")
    return value if isinstance(value, dict) else {}


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


def decision_row(
    row: dict[str, Any],
    authorization: dict[str, Any],
    feedback_candidate_id: str,
    reviewed_at: str,
) -> dict[str, Any] | None:
    outcome = str(row.get("outcome") or "")
    label = LABEL_BY_OUTCOME.get(outcome)
    if not label:
        return None
    cond = condition(row)
    feedback_id = row.get("feedback_id")
    return {
        "decision_id": f"activity-risk-formal-decision::{feedback_id}",
        "feedback_id": feedback_id,
        "project_id": row.get("project_id"),
        "enzyme_id": row.get("enzyme_id"),
        "mutation": row.get("mutation"),
        "canonical_position": row.get("canonical_position"),
        "metric": cond.get("metric"),
        "ph": cond.get("ph"),
        "batch_id": cond.get("batch_id"),
        "sample_id": cond.get("sample_id"),
        "control_sample_id": cond.get("control_sample_id"),
        "feedback_candidate_id": feedback_candidate_id,
        "authorization_id": authorization.get("authorization_id"),
        "authorization_decision": authorization.get("authorization_decision"),
        "authorization_reviewed_at": authorization.get("reviewed_at"),
        "authorization_reviewer": authorization.get("reviewer"),
        "authorization_basis": authorization.get("authorization_basis"),
        "authorization_qc_decision": authorization.get("qc_decision"),
        "activity_relative_to_wt": row.get("activity_relative_to_wt"),
        "source_outcome": outcome,
        "activity_risk_label_decision": label,
        "activity_risk_label": label,
        "replicate_decision": "single_measurement_not_replicate",
        "replicate_group_id": "",
        "replicate_count_counted_for_training": 0,
        "source_trace_reviewed": True,
        "numbering_reviewed": bool(row.get("numbering_verified")),
        "unit_condition_reviewed": True,
        "batch_control_reviewed": True,
        "replicate_policy_reviewed": True,
        "reviewer": "keweibo_user_authorized_activity_risk_formal_label",
        "reviewed_at": reviewed_at,
        "review_basis": (
            "Formal activity_risk head label from existing user-authorized KWB wet-lab "
            "numeric feedback. The source outcome is mapped deterministically: "
            "go=low_activity_risk, watch=watch_activity_risk, no_go=high_activity_risk."
        ),
        "replicate_basis": "No explicit replicate_id is present; row remains a single measurement and contributes zero replicate count.",
        "training_label_source": True,
        "ready_for_activity_risk_head_label": True,
        "ready_for_training_import": True,
        "safe_for_training_import": True,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Formal label decision for activity_risk only. It requires a matching reviewed "
            "wet-lab authorization row, does not infer replicates, does not satisfy five-head "
            "thresholds, and does not open model/release gates."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build formal activity_risk label decisions")
    parser.add_argument("--feedback", type=Path, default=FEEDBACK)
    parser.add_argument("--authorizations", type=Path, default=AUTHORIZATIONS)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    reviewed_at = datetime.now(timezone.utc).isoformat()
    all_source_rows = [row for row in load_jsonl(args.feedback) if is_numeric_activity_feedback(row)]
    authorization_rows = load_jsonl(args.authorizations)
    authorizations_by_candidate_id = {
        str(row.get("feedback_candidate_id")): row
        for row in authorization_rows
        if isinstance(row.get("feedback_candidate_id"), str)
    }
    skipped_rows: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for row in all_source_rows:
        candidate_id = wetlab_candidate_id(row)
        authorization = authorizations_by_candidate_id.get(candidate_id)
        if not candidate_id:
            skipped_rows.append({"feedback_id": row.get("feedback_id"), "reason": "missing_feedback_candidate_id"})
            continue
        if not authorization:
            skipped_rows.append({"feedback_id": row.get("feedback_id"), "feedback_candidate_id": candidate_id, "reason": "authorization_missing"})
            continue
        if not authorization_ready(authorization):
            skipped_rows.append({"feedback_id": row.get("feedback_id"), "feedback_candidate_id": candidate_id, "reason": "authorization_not_ready_for_activity_risk"})
            continue
        decision = decision_row(row, authorization, candidate_id, reviewed_at)
        if decision is None:
            skipped_rows.append({"feedback_id": row.get("feedback_id"), "feedback_candidate_id": candidate_id, "reason": "unsupported_source_outcome"})
            continue
        rows.append(decision)
    write_jsonl(args.output, rows)

    label_counts = Counter(row["activity_risk_label"] for row in rows)
    replicate_counts = Counter(row["replicate_decision"] for row in rows)
    report = {
        "created_at": reviewed_at,
        "local_only": True,
        "source_numeric_activity_rows": len(all_source_rows),
        "authorization_rows": len(authorization_rows),
        "authorization_matched_rows": len(rows),
        "skipped_rows": skipped_rows,
        "formal_decision_rows": len(rows),
        "activity_risk_label_rows_created": len(rows),
        "ready_for_training_import_rows": len(rows),
        "replicate_rows_counted_for_training": sum(int(row.get("replicate_count_counted_for_training") or 0) for row in rows),
        "label_counts": dict(sorted(label_counts.items())),
        "replicate_decision_counts": dict(sorted(replicate_counts.items())),
        "output": str(args.output.relative_to(AI_ROOT)),
        "training_import_written_rows": len(rows),
        "safe_for_training_import": bool(rows),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Activity-risk formal labels are created only from KWB numeric feedback with matching reviewed activity_risk authorization; replicates and model/release gates remain blocked.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "formal_decision_rows": report["formal_decision_rows"],
        "activity_risk_label_rows_created": report["activity_risk_label_rows_created"],
        "replicate_rows_counted_for_training": report["replicate_rows_counted_for_training"],
        "safe_for_model_claim": False,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
