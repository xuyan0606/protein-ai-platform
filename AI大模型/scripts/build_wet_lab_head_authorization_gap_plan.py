#!/usr/bin/env python3
"""Build a fail-closed executor plan from wet-lab authorization worklist to heads."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.template.jsonl"
AUTH_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
PREFLIGHT_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_preflight_report.json"
APPLY_PLAN_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_intake_apply_plan_report.json"
MULTITASK_REPORT = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_head_authorization_gap_actions.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_head_authorization_gap_plan_report.json"
MARKDOWN = AI_ROOT / "reports" / "wet_lab_head_authorization_gap_plan.md"

PRIORITY_ORDER = {
    "critical_tradeoff_review": 0,
    "medium_mixed_benefit_review": 1,
    "standard_multi_property_review": 2,
}
MISSING_APPROVAL_FIELDS = [
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
COMMANDS = {
    "authorization_validation": "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
    "preflight": "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
    "apply_plan": "python3 scripts/build_wet_lab_mutant_library_feedback_intake_apply_plan.py",
}
HEAD_BY_ASSAY = {
    "activity": {
        "head_key": "activity_risk",
        "authorization_head": "activity_risk_head",
        "feedback_measurement": "activity_relative_to_wt",
        "head_schema_note": (
            "Current head contract also requires activity_risk_label. "
            "This plan does not derive that label from the wet-lab ratio."
        ),
    },
    "stability": {
        "head_key": "stability",
        "authorization_head": "stability_head",
        "feedback_measurement": "stability_relative_to_wt",
        "head_schema_note": (
            "Current head contract expects label_stability_delta_tm_c or label_ddg. "
            "An 85C/3min relative-retention metric is not automatically converted to either target."
        ),
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"missing_required_input:{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected_json_object:{path}")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"missing_required_input:{path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"expected_json_object:{path}:{line_number}")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
    qc = row.get("qc_context") if isinstance(row.get("qc_context"), dict) else {}
    return (
        PRIORITY_ORDER.get(str(qc.get("review_priority") or ""), 99),
        str(row.get("variant") or ""),
        str(row.get("metric_name") or ""),
    )


def required_head_fields(multitask: dict[str, Any], head_key: str) -> list[str]:
    heads = multitask.get("heads") if isinstance(multitask.get("heads"), dict) else {}
    item = heads.get(head_key) if isinstance(heads.get(head_key), dict) else {}
    fields = item.get("label_fields") if isinstance(item.get("label_fields"), list) else []
    return [str(field) for field in fields]


def source_snapshot(
    authorization: dict[str, Any],
    preflight: dict[str, Any],
    apply_plan: dict[str, Any],
) -> dict[str, int]:
    return {
        "authorization_rows": int(authorization.get("authorization_rows") or 0),
        "authorized_candidate_rows": int(authorization.get("authorized_candidate_rows") or 0),
        "missing_candidate_authorization_rows": int(
            authorization.get("missing_candidate_authorization_rows") or 0
        ),
        "preflight_rows": int(preflight.get("preflight_rows") or 0),
        "valid_preflight_rows": int(apply_plan.get("valid_preflight_rows") or 0),
        "apply_plan_rows": int(apply_plan.get("apply_plan_rows") or 0),
        "applied_rows": int(apply_plan.get("applied_rows") or 0),
    }


def action_row(
    index: int,
    work: dict[str, Any],
    template: dict[str, Any],
    multitask: dict[str, Any],
    upstream: dict[str, int],
) -> dict[str, Any]:
    assay_type = str(work.get("assay_type") or "")
    mapping = HEAD_BY_ASSAY[assay_type]
    head_key = mapping["head_key"]
    head_info = (multitask.get("heads") or {}).get(head_key) or {}
    qc = work.get("qc_context") if isinstance(work.get("qc_context"), dict) else {}
    decision_present = bool(work.get("authorization_decision_present"))
    authorization_valid = bool(work.get("authorization_valid"))
    authorized = bool(work.get("authorized_for_feedback_intake"))
    authorization_errors = [str(item) for item in work.get("authorization_errors") or []]
    missing_fields = [] if authorization_valid else MISSING_APPROVAL_FIELDS.copy()
    if decision_present and authorization_errors:
        missing_fields = sorted(set(authorization_errors))

    template_heads = template.get("approved_training_heads")
    if not isinstance(template_heads, list):
        template_heads = []

    return {
        "executor_action_id": f"wetlab-head-gap-{work.get('feedback_candidate_id')}",
        "execution_order": index,
        "feedback_candidate_id": work.get("feedback_candidate_id"),
        "authorization_worklist_id": work.get("authorization_worklist_id"),
        "authorization_template_id": work.get("authorization_template_id"),
        "variant": work.get("variant"),
        "metric_name": work.get("metric_name"),
        "metric_class": work.get("metric_class"),
        "assay_type": assay_type,
        "outcome_candidate": work.get("outcome_candidate"),
        "raw_value_numeric": work.get("raw_value_numeric"),
        "control_value_numeric": work.get("control_value_numeric"),
        "vs_control_ratio": work.get("vs_control_ratio"),
        "batch_id": work.get("batch_id"),
        "sample_id": work.get("sample_id"),
        "source_file": work.get("source_file"),
        "source_row_index": work.get("source_row_index"),
        "review_priority": qc.get("review_priority"),
        "conflicting_property_signal": bool(qc.get("conflicting_property_signal")),
        "variant_property_call": qc.get("property_call"),
        "target_head": head_key,
        "authorization_head_template": template_heads,
        "expected_authorization_head": mapping["authorization_head"],
        "head_current_training_rows": int(head_info.get("rows") or 0),
        "head_minimum_rows": int(head_info.get("minimum_rows") or 0),
        "head_missing_to_minimum": max(
            int(head_info.get("minimum_rows") or 0) - int(head_info.get("rows") or 0),
            0,
        ),
        "feedback_measurement_after_intake": mapping["feedback_measurement"],
        "current_head_label_fields": required_head_fields(multitask, head_key),
        "head_schema_gap": mapping["head_schema_note"],
        "authorization_state": {
            "decision_present": decision_present,
            "valid": authorization_valid,
            "authorized_for_feedback_intake": authorized,
            "missing_or_invalid_fields": missing_fields,
            "human_must_choose_one_of": [
                "approved_for_feedback_intake",
                "rejected",
                "needs_more_info",
            ],
            "approval_requirements": [
                "Set qc_decision to pass or pass_with_conditions.",
                "Set source_trace_reviewed, numbering_reviewed, unit_condition_reviewed, batch_control_reviewed, and replicate_policy_reviewed to true.",
                "Provide reviewer, reviewed_at, and authorization_basis.",
                "Keep allow_append_to_experiment_feedback_local false.",
                f"Keep approved_training_heads aligned with {mapping['authorization_head']}.",
            ],
            "decision_write_target": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
        },
        "upstream_state": {
            "authorization_report_rows": upstream["authorization_rows"],
            "authorized_candidate_rows": upstream["authorized_candidate_rows"],
            "preflight_rows": upstream["preflight_rows"],
            "apply_plan_rows": upstream["apply_plan_rows"],
            "applied_rows": upstream["applied_rows"],
        },
        "path_after_human_authorization": [
            COMMANDS["authorization_validation"],
            COMMANDS["preflight"],
            COMMANDS["apply_plan"],
            "Require a separate explicit user-authorized apply action outside this plan.",
            "Validate the resulting feedback record and perform a separate reviewed head-target mapping.",
        ],
        "head_entry_status": "blocked_pending_human_authorization_feedback_intake_and_head_mapping",
        "ready_for_feedback_intake": False,
        "ready_for_training_import": False,
        "claim_eligible_now": False,
        "policy": (
            "Executor-plan row only. It does not write an authorization decision, preflight row, "
            "apply-plan row, experiment feedback record, head label, or training import."
        ),
    }


def validate_inputs(
    worklist: list[dict[str, Any]],
    templates: list[dict[str, Any]],
    multitask: dict[str, Any],
    authorization: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if not worklist:
        raise ValueError("empty_authorization_worklist")
    work_ids = [str(row.get("feedback_candidate_id") or "") for row in worklist]
    if "" in work_ids or len(set(work_ids)) != len(work_ids):
        raise ValueError("worklist_candidate_ids_missing_or_duplicate")

    template_by_id = {
        str(row.get("feedback_candidate_id") or ""): row
        for row in templates
        if row.get("feedback_candidate_id")
    }
    if set(work_ids) != set(template_by_id):
        raise ValueError("worklist_template_candidate_coverage_mismatch")
    if int(authorization.get("numeric_training_candidate_rows") or 0) != len(worklist):
        raise ValueError("authorization_report_worklist_count_mismatch")

    heads = multitask.get("heads") if isinstance(multitask.get("heads"), dict) else {}
    for row in worklist:
        assay_type = str(row.get("assay_type") or "")
        if assay_type not in HEAD_BY_ASSAY:
            raise ValueError(f"unsupported_assay_type:{assay_type}")
        expected_head = HEAD_BY_ASSAY[assay_type]["authorization_head"]
        template_heads = template_by_id[str(row["feedback_candidate_id"])].get("approved_training_heads")
        if template_heads != [expected_head]:
            raise ValueError(f"template_head_mapping_mismatch:{row.get('feedback_candidate_id')}")
        if HEAD_BY_ASSAY[assay_type]["head_key"] not in heads:
            raise ValueError(f"missing_multitask_head:{HEAD_BY_ASSAY[assay_type]['head_key']}")
    return template_by_id


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Wet-Lab Head Authorization Gap Plan",
        "",
        f"Generated: {report['created_at']}",
        "",
        "Fail-closed executor plan only. It neither writes human authorization decisions nor imports training labels.",
        "",
        "## Current State",
        "",
        f"- Worklist actions: {report['action_rows']}",
        f"- Authorization rows / authorized candidates: {report['source_state']['authorization_rows']} / {report['source_state']['authorized_candidate_rows']}",
        f"- Preflight rows / apply-plan rows / applied rows: {report['source_state']['preflight_rows']} / {report['source_state']['apply_plan_rows']} / {report['source_state']['applied_rows']}",
        f"- Safe for training import: {str(report['safe_for_training_import']).lower()}",
        "",
        "## Head Paths",
        "",
        "| head | candidates | current rows | missing to minimum | schema gap |",
        "|---|---:|---:|---:|---|",
    ]
    for row in report["head_summaries"]:
        lines.append(
            "| {head} | {candidate_rows} | {current_training_rows} | {missing_to_minimum} | {schema_gap} |".format(
                **row
            )
        )

    lines.extend([
        "",
        "## Per-Metric Actions",
        "",
        "| order | variant | metric | head | outcome | ratio | priority | missing authorization fields |",
        "|---:|---|---|---|---|---:|---|---|",
    ])
    for action in report["actions"]:
        missing = ", ".join(action["authorization_state"]["missing_or_invalid_fields"])
        lines.append(
            "| {execution_order} | {variant} | {metric_name} | {target_head} | {outcome_candidate} | "
            "{vs_control_ratio:.6g} | {review_priority} | {missing} |".format(
                missing=missing,
                **action,
            )
        )

    lines.extend([
        "",
        "## Human Authorization Contract",
        "",
        "- Each metric is independent. Choose one of `approved_for_feedback_intake`, `rejected`, or `needs_more_info`; this plan does not select one.",
        "- An approval requires QC pass/pass-with-conditions, five completed review flags, reviewer, timestamp, and basis. `allow_append_to_experiment_feedback_local` remains `false`.",
        "- After a valid decision, run the authorization validator, preflight builder, and apply-plan builder. A separate explicit apply action and a separate reviewed head-target mapping remain required.",
        "",
        "## Guardrails",
        "",
        "- Activity metrics can become feedback evidence for `activity_risk`, but `activity_risk_label` is still not derived here.",
        "- The 85C/3min thermal metrics can become feedback evidence for `stability`, but they are not automatically translated into `label_stability_delta_tm_c` or `label_ddg`.",
        "- None of these actions changes a training table, head row count, model claim, safe pipeline, or manifest.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab authorization-to-head fail-closed executor plan")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--authorization-report", type=Path, default=AUTH_REPORT)
    parser.add_argument("--preflight-report", type=Path, default=PREFLIGHT_REPORT)
    parser.add_argument("--apply-plan-report", type=Path, default=APPLY_PLAN_REPORT)
    parser.add_argument("--multitask-report", type=Path, default=MULTITASK_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    args = parser.parse_args()

    try:
        worklist = sorted(load_jsonl(args.worklist), key=sort_key)
        templates = load_jsonl(args.template)
        authorization = load_json(args.authorization_report)
        preflight = load_json(args.preflight_report)
        apply_plan = load_json(args.apply_plan_report)
        multitask = load_json(args.multitask_report)
        template_by_id = validate_inputs(worklist, templates, multitask, authorization)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked_input_validation_failed", "error": str(exc)}, ensure_ascii=False))
        return 2

    upstream = source_snapshot(authorization, preflight, apply_plan)
    actions = [
        action_row(
            index,
            work,
            template_by_id[str(work["feedback_candidate_id"])],
            multitask,
            upstream,
        )
        for index, work in enumerate(worklist, start=1)
    ]
    head_summaries = []
    for assay_type, mapping in HEAD_BY_ASSAY.items():
        head_key = mapping["head_key"]
        head_info = (multitask.get("heads") or {}).get(head_key) or {}
        head_actions = [row for row in actions if row["target_head"] == head_key]
        head_summaries.append({
            "head": head_key,
            "candidate_rows": len(head_actions),
            "current_training_rows": int(head_info.get("rows") or 0),
            "minimum_rows": int(head_info.get("minimum_rows") or 0),
            "missing_to_minimum": max(
                int(head_info.get("minimum_rows") or 0) - int(head_info.get("rows") or 0),
                0,
            ),
            "authorization_head": mapping["authorization_head"],
            "current_head_label_fields": required_head_fields(multitask, head_key),
            "schema_gap": mapping["head_schema_note"],
            "ready_candidate_rows": sum(
                1 for row in head_actions if row["authorization_state"]["authorized_for_feedback_intake"]
            ),
            "training_rows_added_by_plan": 0,
        })

    field_counts = Counter(
        field
        for action in actions
        for field in action["authorization_state"]["missing_or_invalid_fields"]
    )
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked_fail_closed",
        "action_rows": len(actions),
        "variant_rows": len({str(row["variant"]) for row in actions}),
        "head_action_counts": dict(sorted(Counter(row["target_head"] for row in actions).items())),
        "review_priority_counts": dict(sorted(Counter(row["review_priority"] for row in actions).items())),
        "missing_authorization_field_counts": dict(sorted(field_counts.items())),
        "source_state": upstream,
        "head_summaries": head_summaries,
        "actions": actions,
        "authorization_path": [
            "Human writes one reviewed authorization decision per metric to the existing authorization input.",
            COMMANDS["authorization_validation"],
            COMMANDS["preflight"],
            COMMANDS["apply_plan"],
            "Separate explicit user-authorized apply action outside this plan.",
            "Separate reviewed mapping from feedback record to head-specific target fields.",
        ],
        "training_rows_added_by_plan": 0,
        "safe_for_feedback_intake": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "policy": (
            "This executor plan is read-only with respect to authorization, preflight, apply-plan, "
            "feedback, and training inputs. It only emits planning artifacts and remains fail-closed."
        ),
    }
    write_jsonl(args.output, actions)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown)
    print(json.dumps({
        "status": report["status"],
        "action_rows": report["action_rows"],
        "head_action_counts": report["head_action_counts"],
        "authorized_candidate_rows": report["source_state"]["authorized_candidate_rows"],
        "training_rows_added_by_plan": report["training_rows_added_by_plan"],
        "report": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
