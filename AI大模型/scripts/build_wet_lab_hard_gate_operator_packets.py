#!/usr/bin/env python3
"""Build fail-closed operator packets for wet-lab head authorization gates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GAP_REPORT = AI_ROOT / "reports" / "wet_lab_head_authorization_gap_plan_report.json"
OUT = AI_ROOT / "reports" / "wet_lab_hard_gate_operator_packet_report.json"
MD_OUT = AI_ROOT / "reports" / "wet_lab_hard_gate_operator_packets.md"
JSONL_OUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_hard_gate_operator_packets.jsonl"

POLICY = (
    "Fail-closed wet-lab operator packets only. They do not write authorization decisions, "
    "preflight rows, apply-plan rows, experiment feedback records, head labels, training rows, "
    "model claims, deployments, syncs, or release readiness."
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_score(row: dict[str, Any]) -> float:
    ratio = as_float(row.get("vs_control_ratio"))
    if ratio is None:
        return 0.0
    return abs(ratio - 1.0)


def action_to_packet(row: dict[str, Any], order: int) -> dict[str, Any]:
    authorization = row.get("authorization_state") if isinstance(row.get("authorization_state"), dict) else {}
    missing = authorization.get("missing_or_invalid_fields")
    if not isinstance(missing, list):
        missing = []
    approval_requirements = authorization.get("approval_requirements")
    if not isinstance(approval_requirements, list):
        approval_requirements = []
    ratio = as_float(row.get("vs_control_ratio"))
    raw = as_float(row.get("raw_value_numeric"))
    control = as_float(row.get("control_value_numeric"))
    target_head = row.get("target_head")
    return {
        "packet_id": f"wetlab-hard-gate-{row.get('feedback_candidate_id')}",
        "execution_order": order,
        "workstream": "wet_lab_training_eligible_feedback",
        "priority": "P0",
        "status": "open_blocked",
        "variant": row.get("variant"),
        "sample_id": row.get("sample_id"),
        "batch_id": row.get("batch_id"),
        "feedback_candidate_id": row.get("feedback_candidate_id"),
        "authorization_worklist_id": row.get("authorization_worklist_id"),
        "authorization_template_id": row.get("authorization_template_id"),
        "metric_name": row.get("metric_name"),
        "metric_class": row.get("metric_class"),
        "assay_type": row.get("assay_type"),
        "target_head": target_head,
        "expected_authorization_head": row.get("expected_authorization_head"),
        "outcome_candidate": row.get("outcome_candidate"),
        "raw_value_numeric": raw,
        "control_value_numeric": control,
        "vs_control_ratio": ratio,
        "ratio_delta_from_control": round(ratio - 1.0, 6) if ratio is not None else None,
        "absolute_ratio_delta": round(row_score(row), 6),
        "review_priority": row.get("review_priority"),
        "conflicting_property_signal": bool(row.get("conflicting_property_signal")),
        "variant_property_call": row.get("variant_property_call"),
        "source_file": row.get("source_file"),
        "source_row_index": row.get("source_row_index"),
        "head_current_training_rows": row.get("head_current_training_rows"),
        "head_missing_to_minimum": row.get("head_missing_to_minimum"),
        "head_schema_gap": row.get("head_schema_gap"),
        "missing_authorization_fields": missing,
        "approval_requirements": approval_requirements,
        "decision_write_target_after_human_review": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
        "allowed_human_decisions": ["approved_for_feedback_intake", "rejected", "needs_more_info"],
        "post_decision_commands": [
            "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
            "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
            "python3 scripts/build_wet_lab_mutant_library_feedback_intake_apply_plan.py",
            "python3 scripts/build_wet_lab_head_authorization_gap_plan.py",
            "python3 scripts/build_wet_lab_hard_gate_operator_packets.py",
            "python3 scripts/run_safe_training_pipeline.py",
        ],
        "completion_condition": (
            "A human must record a valid authorization row with reviewer, reviewed_at, basis, QC, source trace, "
            "numbering, unit/condition, batch/control and replicate checks. A separate explicit apply action is "
            "required before any feedback intake or head-label mapping."
        ),
        "authorization_decision_written_by_packet": False,
        "feedback_intake_written_by_packet": False,
        "training_label_written_by_packet": False,
        "model_claim_allowed": False,
        "release_ready": False,
        "requires_human_input": True,
        "policy": POLICY,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Wet-Lab Hard-Gate Operator Packets",
        "",
        f"Generated: {report['created_at']}",
        "",
        "These packets organize manual wet-lab authorization work. They do not write decisions or labels.",
        "",
        "## Summary",
        "",
        f"- Packet rows: {report['packet_rows']}",
        f"- Completion ready rows: {report['completion_ready_rows']}",
        f"- Variants: {report['variant_counts']}",
        f"- Head counts: {report['head_counts']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Packets",
        "",
        "| order | variant | metric | head | ratio | priority | missing fields |",
        "|---:|---|---|---|---:|---|---:|",
    ]
    for row in report["top_packets"]:
        lines.append(
            f"| {row['execution_order']} | {row['variant']} | {row['metric_name']} | {row['target_head']} | "
            f"{row['vs_control_ratio']} | {row['review_priority']} | {len(row['missing_authorization_fields'])} |"
        )
    lines.extend(["", "## Policy", "", report["policy"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab hard-gate operator packets")
    parser.add_argument("--gap-report", type=Path, default=GAP_REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    gap = load_json(args.gap_report)
    actions = gap.get("actions") if isinstance(gap.get("actions"), list) else []
    sorted_actions = sorted(
        [row for row in actions if isinstance(row, dict)],
        key=lambda row: (
            {"critical_tradeoff_review": 0, "medium_mixed_benefit_review": 1}.get(str(row.get("review_priority")), 9),
            -row_score(row),
            str(row.get("variant") or ""),
            str(row.get("metric_name") or ""),
        ),
    )
    packets = [action_to_packet(row, index) for index, row in enumerate(sorted_actions, 1)]
    write_jsonl(args.jsonl, packets)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "source_gap_report": str(args.gap_report),
        "jsonl": str(args.jsonl),
        "packet_rows": len(packets),
        "completion_ready_rows": 0,
        "authorization_decision_written_rows": 0,
        "feedback_intake_written_rows": 0,
        "training_label_written_rows": 0,
        "requires_human_input_rows": len(packets),
        "variant_counts": dict(sorted(Counter(str(row.get("variant")) for row in packets).items())),
        "head_counts": dict(sorted(Counter(str(row.get("target_head")) for row in packets).items())),
        "review_priority_counts": dict(sorted(Counter(str(row.get("review_priority")) for row in packets).items())),
        "missing_authorization_field_counts": dict(
            sorted(Counter(field for row in packets for field in row["missing_authorization_fields"]).items())
        ),
        "top_packets": packets,
        "safe_for_feedback_intake": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": POLICY,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, args.markdown)
    print(json.dumps({
        "status": report["status"],
        "packet_rows": report["packet_rows"],
        "completion_ready_rows": report["completion_ready_rows"],
        "authorization_decision_written_rows": report["authorization_decision_written_rows"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
