#!/usr/bin/env python3
"""Audit wet-lab apply-plan rows against existing local feedback.

This is read-only. It exists to prevent appending the same wet-lab observation
twice when a preflight/apply plan is rebuilt after manual feedback import.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_preflight.jsonl"
APPLY_PLAN = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_intake_apply_plan.jsonl"
LOCAL_FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_feedback_apply_duplicate_audit.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_feedback_apply_duplicate_audit_report.json"

CANDIDATE_RE = re.compile(r"\bwetlab-mutlib-[0-9a-f]{20}\b")
SOURCE_ROW_RE = re.compile(r"source_row_index=(\d+)")
SOURCE_SHA_RE = re.compile(r"source_sha256=([0-9a-f]{64})")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def metric(row: dict[str, Any]) -> str:
    condition = row.get("assay_condition") if isinstance(row.get("assay_condition"), dict) else {}
    return str(condition.get("metric") or "")


def condition_value(row: dict[str, Any], key: str) -> Any:
    condition = row.get("assay_condition") if isinstance(row.get("assay_condition"), dict) else {}
    return condition.get(key) or row.get(key)


def candidate_ids(row: dict[str, Any]) -> set[str]:
    ids = set()
    if row.get("feedback_candidate_id"):
        ids.add(str(row["feedback_candidate_id"]))
    notes = str(row.get("notes") or "")
    ids.update(CANDIDATE_RE.findall(notes))
    return ids


def source_row_index(row: dict[str, Any]) -> str | None:
    if row.get("source_row_index") is not None:
        return str(row.get("source_row_index"))
    match = SOURCE_ROW_RE.search(str(row.get("notes") or ""))
    return match.group(1) if match else None


def source_sha256(row: dict[str, Any]) -> str | None:
    value = row.get("source_file_sha256") or row.get("source_sha256")
    if value:
        return str(value)
    match = SOURCE_SHA_RE.search(str(row.get("notes") or ""))
    return match.group(1) if match else None


def canonical_key(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("project_id") or ""),
        str(row.get("mutation") or ""),
        str(row.get("assay_type") or ""),
        metric(row),
        str(condition_value(row, "batch_id") or ""),
        str(condition_value(row, "sample_id") or ""),
        str(source_row_index(row) or ""),
        str(source_sha256(row) or ""),
    )


def is_stability_retention(row: dict[str, Any]) -> bool:
    return row.get("assay_type") == "stability" and "85C_3min" in metric(row)


def is_activity_training_label(row: dict[str, Any]) -> bool:
    return row.get("assay_type") == "activity" and isinstance(row.get("activity_relative_to_wt"), (int, float))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback apply duplicate audit")
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    parser.add_argument("--apply-plan", type=Path, default=APPLY_PLAN)
    parser.add_argument("--local-feedback", type=Path, default=LOCAL_FEEDBACK)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    preflight_rows = load_jsonl(args.preflight)
    apply_plan_rows = load_jsonl(args.apply_plan)
    feedback_rows = load_jsonl(args.local_feedback)

    existing_candidate_ids: set[str] = set()
    existing_keys: dict[tuple[str, ...], list[str]] = {}
    for row in feedback_rows:
        existing_candidate_ids.update(candidate_ids(row))
        existing_keys.setdefault(canonical_key(row), []).append(str(row.get("feedback_id") or ""))

    plan_ids = {str(row.get("feedback_candidate_id")) for row in apply_plan_rows if row.get("feedback_candidate_id")}
    audit_rows: list[dict[str, Any]] = []
    for row in preflight_rows:
        key = canonical_key(row)
        ids = candidate_ids(row)
        candidate_overlap = sorted(ids & existing_candidate_ids)
        key_matches = sorted(value for value in existing_keys.get(key, []) if value)
        already_represented = bool(candidate_overlap or key_matches)
        stability_retention = is_stability_retention(row)
        activity_candidate = row.get("assay_type") == "activity"
        if already_represented:
            recommended_action = "skip_existing_feedback_duplicate"
            remaining_blockers = ["already_represented_in_experiment_feedback_local"]
        elif stability_retention:
            recommended_action = "hold_feedback_only_until_stability_label_rule_reviewed"
            remaining_blockers = [
                "thermal_retention_percent_is_not_dt_m_or_physics_ddg",
                "stability_training_label_conversion_rule_missing",
                "separate_feedback_only_append_authorization_required",
            ]
        else:
            recommended_action = "hold_unrepresented_numeric_candidate_for_manual_review"
            remaining_blockers = ["unrepresented_numeric_candidate_requires_manual_duplicate_review"]

        audit_rows.append(
            {
                "audit_id": f"wetlab-feedback-duplicate-audit-{row.get('feedback_candidate_id')}",
                "feedback_candidate_id": row.get("feedback_candidate_id"),
                "proposed_feedback_id": row.get("proposed_feedback_id"),
                "mutation": row.get("mutation"),
                "assay_type": row.get("assay_type"),
                "metric": metric(row),
                "canonical_key": list(key),
                "apply_plan_present": str(row.get("feedback_candidate_id")) in plan_ids,
                "existing_candidate_id_matches": candidate_overlap,
                "existing_canonical_feedback_id_matches": key_matches,
                "already_represented_in_experiment_feedback_local": already_represented,
                "activity_training_label_candidate": activity_candidate,
                "stability_retention_percent_candidate": stability_retention,
                "training_import_eligible_from_apply_plan": False,
                "safe_to_append_to_experiment_feedback_local": False,
                "safe_to_append_as_training_label": False,
                "recommended_action": recommended_action,
                "remaining_blockers": remaining_blockers,
                "policy": (
                    "Duplicate audit only. Existing observations must not be appended again; "
                    "85C/3min retention percent is feedback evidence only until a reviewed "
                    "stability-label conversion rule exists."
                ),
            }
        )

    already = sum(1 for row in audit_rows if row["already_represented_in_experiment_feedback_local"])
    stability_new = sum(
        1
        for row in audit_rows
        if row["stability_retention_percent_candidate"] and not row["already_represented_in_experiment_feedback_local"]
    )
    unrepresented_activity = sum(
        1
        for row in audit_rows
        if row["activity_training_label_candidate"] and not row["already_represented_in_experiment_feedback_local"]
    )
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "preflight": str(args.preflight),
        "apply_plan": str(args.apply_plan),
        "local_feedback": str(args.local_feedback),
        "output": str(args.output),
        "preflight_rows": len(preflight_rows),
        "apply_plan_rows": len(apply_plan_rows),
        "existing_feedback_rows": len(feedback_rows),
        "already_represented_rows": already,
        "already_represented_activity_rows": sum(
            1
            for row in audit_rows
            if row["activity_training_label_candidate"] and row["already_represented_in_experiment_feedback_local"]
        ),
        "new_feedback_only_rows": stability_new,
        "new_stability_retention_percent_rows": stability_new,
        "unrepresented_activity_candidate_rows": unrepresented_activity,
        "duplicate_risk_rows": already,
        "safe_to_append_rows": 0,
        "safe_to_append_as_training_label_rows": 0,
        "training_import_eligible_from_apply_plan_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "success": True,
        "policy": (
            "Apply-plan rows are not appended here. Current D105N/S265T activity observations "
            "already exist in experiment_feedback.local.jsonl; thermal-retention percent rows "
            "remain non-training feedback evidence until a reviewed dTm/ddG conversion rule exists."
        ),
    }
    write_jsonl(args.output, audit_rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "preflight_rows": report["preflight_rows"],
                "already_represented_rows": report["already_represented_rows"],
                "new_feedback_only_rows": report["new_feedback_only_rows"],
                "safe_to_append_rows": report["safe_to_append_rows"],
                "output": str(args.report),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
