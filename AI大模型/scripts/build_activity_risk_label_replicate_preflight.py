#!/usr/bin/env python3
"""Build a fail-closed activity_risk label and replicate decision preflight.

This script turns the current numeric wet-lab activity feedback into a review
packet and blank decision template. It does not write formal labels, infer
replicates, start training, or open model/release gates.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
PREFLIGHT = AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_preflight.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_decisions.template.jsonl"
REPORT = AI_ROOT / "reports" / "activity_risk_label_replicate_preflight_report.json"

ALLOWED_LABEL_DECISIONS = [
    "low_activity_risk",
    "watch_activity_risk",
    "high_activity_risk",
    "exclude_from_activity_risk_training",
    "needs_more_info",
]

ALLOWED_REPLICATE_DECISIONS = [
    "single_measurement_not_replicate",
    "approved_replicate_group",
    "needs_raw_plate_or_replicate_map",
    "exclude_replicate_from_training",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
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


def proposed_label(value: float) -> str:
    if value >= 1.10:
        return "low_activity_risk_candidate"
    if value >= 0.95:
        return "watch_activity_risk_candidate"
    return "high_activity_risk_candidate"


def explicit_replicate_id(row: dict[str, Any]) -> str | None:
    cond = condition(row)
    for key in ("replicate", "replicate_id", "replicate_index"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
        value = cond.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def stable_review_id(row: dict[str, Any]) -> str:
    return f"activity-risk-preflight::{row.get('feedback_id')}"


def preflight_row(row: dict[str, Any]) -> dict[str, Any]:
    cond = condition(row)
    value = float(row["activity_relative_to_wt"])
    replicate_id = explicit_replicate_id(row)
    return {
        "preflight_id": stable_review_id(row),
        "feedback_id": row.get("feedback_id"),
        "project_id": row.get("project_id"),
        "enzyme_id": row.get("enzyme_id"),
        "mutation": row.get("mutation"),
        "canonical_position": row.get("canonical_position"),
        "numbering_verified": bool(row.get("numbering_verified")),
        "assay_type": row.get("assay_type"),
        "metric": cond.get("metric"),
        "ph": cond.get("ph"),
        "comparison_condition": cond.get("comparison_condition"),
        "batch_id": cond.get("batch_id"),
        "sample_id": cond.get("sample_id"),
        "control_sample_id": cond.get("control_sample_id"),
        "activity_relative_to_wt": value,
        "existing_outcome": row.get("outcome"),
        "proposed_label_from_ratio_only": proposed_label(value),
        "activity_risk_label": None,
        "proposal_is_formal_decision": False,
        "explicit_replicate_id": replicate_id,
        "replicate_status": "explicit_replicate_missing" if replicate_id is None else "explicit_replicate_present",
        "proposed_replicate_decision": (
            "single_measurement_not_replicate" if replicate_id is None else "needs_raw_plate_or_replicate_map"
        ),
        "replicate_count_counted_for_training": 0,
        "formal_decision_required": True,
        "formal_decision_written": False,
        "training_import_written": False,
        "ready_for_training_import": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "source_trace": {
            "notes": row.get("notes"),
            "recorded_at": row.get("recorded_at"),
            "source": row.get("source"),
        },
        "human_review_questions": [
            "Confirm whether the ratio-only proposal can become an activity_risk_label.",
            "Confirm whether this measurement has an explicit replicate or remains a single measurement.",
            "Confirm whether this row should be excluded from training until raw plate/replicate evidence is available.",
        ],
        "policy": (
            "Ratio-derived proposal only. The row remains non-training until a human-reviewed "
            "activity_risk label and replicate decision are written and validated elsewhere."
        ),
    }


def template_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": f"activity-risk-decision::{row.get('feedback_id')}",
        "feedback_id": row.get("feedback_id"),
        "preflight_id": stable_review_id(row),
        "mutation": row.get("mutation"),
        "metric": condition(row).get("metric"),
        "activity_relative_to_wt": row.get("activity_relative_to_wt"),
        "activity_risk_label_decision": "",
        "replicate_decision": "",
        "replicate_group_id": "",
        "reviewer": "",
        "reviewed_at": "",
        "review_basis": "",
        "replicate_basis": "",
        "allowed_activity_risk_label_decisions": ALLOWED_LABEL_DECISIONS,
        "allowed_replicate_decisions": ALLOWED_REPLICATE_DECISIONS,
        "template_status": "blank_not_formal",
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Template only. Blank rows are not formal decisions and must not be imported as labels.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build activity_risk label/replicate preflight")
    parser.add_argument("--feedback", type=Path, default=FEEDBACK)
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    source_rows = load_jsonl(args.feedback)
    numeric_rows = [row for row in source_rows if is_numeric_activity_feedback(row)]
    preflight_rows = [preflight_row(row) for row in numeric_rows]
    template_rows = [template_row(row) for row in numeric_rows]

    write_jsonl(args.preflight, preflight_rows)
    write_jsonl(args.template, template_rows)

    variant_counts = Counter(str(row.get("mutation")) for row in numeric_rows)
    proposed_label_counts = Counter(row["proposed_label_from_ratio_only"] for row in preflight_rows)
    replicate_status_counts = Counter(row["replicate_status"] for row in preflight_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_feedback": rel(args.feedback),
        "preflight_output": rel(args.preflight),
        "decision_template_output": rel(args.template),
        "source_numeric_activity_rows": len(numeric_rows),
        "preflight_rows": len(preflight_rows),
        "decision_template_rows": len(template_rows),
        "variant_count": len(variant_counts),
        "variant_counts": dict(sorted(variant_counts.items())),
        "proposed_label_counts": dict(sorted(proposed_label_counts.items())),
        "replicate_status_counts": dict(sorted(replicate_status_counts.items())),
        "formal_decision_rows": 0,
        "activity_risk_label_rows_created": 0,
        "replicate_rows_counted_for_training": 0,
        "training_import_written_rows": 0,
        "ready_for_training_import_rows": 0,
        "ready_for_training_import": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "validator_command": "python3 scripts/validate_activity_risk_label_replicate_preflight.py",
        "policy": (
            "Preflight and template only. The builder does not write formal activity_risk labels, "
            "does not infer replicates, and does not change benchmark, training, model-claim or release gates."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "preflight_rows": report["preflight_rows"],
        "decision_template_rows": report["decision_template_rows"],
        "formal_decision_rows": report["formal_decision_rows"],
        "ready_for_training_import_rows": report["ready_for_training_import_rows"],
        "output": rel(args.preflight),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
