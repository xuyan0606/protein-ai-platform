#!/usr/bin/env python3
"""Validate activity_risk label/replicate preflight remains fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
PREFLIGHT = AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_preflight.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_decisions.template.jsonl"
REPORT = AI_ROOT / "reports" / "activity_risk_label_replicate_preflight_report.json"
OUT = AI_ROOT / "reports" / "activity_risk_label_replicate_preflight_validation_report.json"

EXPECTED_CURRENT_NUMERIC_ROWS = 6
GATE_FIELDS = (
    "ready_for_training_import",
    "safe_for_training_import",
    "safe_for_model_claim",
    "release_ready",
)
TEMPLATE_REQUIRED_BLANK_FIELDS = (
    "activity_risk_label_decision",
    "replicate_decision",
    "replicate_group_id",
    "reviewer",
    "reviewed_at",
    "review_basis",
    "replicate_basis",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


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


def is_numeric_activity_feedback(row: dict[str, Any]) -> bool:
    return (
        row.get("source") == "kwb_wet_lab"
        and row.get("quantitative_assay_available") is True
        and row.get("assay_type") == "activity"
        and isinstance(row.get("activity_relative_to_wt"), (int, float))
    )


def fail_if(
    condition: bool,
    failures: list[dict[str, Any]],
    check: str,
    observed: Any,
    expected: Any,
) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def row_id(row: dict[str, Any]) -> Any:
    return row.get("feedback_id") or row.get("preflight_id") or row.get("decision_id")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate activity_risk label/replicate preflight")
    parser.add_argument("--feedback", type=Path, default=FEEDBACK)
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    feedback_rows = load_jsonl(args.feedback)
    source_numeric_rows = [row for row in feedback_rows if is_numeric_activity_feedback(row)]
    preflight_rows = load_jsonl(args.preflight)
    template_rows = load_jsonl(args.template)
    report = load_json(args.report)
    failures: list[dict[str, Any]] = []

    source_ids = {row.get("feedback_id") for row in source_numeric_rows}
    preflight_ids = {row.get("feedback_id") for row in preflight_rows}
    template_ids = {row.get("feedback_id") for row in template_rows}

    fail_if(len(source_numeric_rows) != EXPECTED_CURRENT_NUMERIC_ROWS, failures, "current_numeric_activity_rows", len(source_numeric_rows), EXPECTED_CURRENT_NUMERIC_ROWS)
    fail_if(len(preflight_rows) != len(source_numeric_rows), failures, "preflight_covers_source_rows", len(preflight_rows), len(source_numeric_rows))
    fail_if(len(template_rows) != len(source_numeric_rows), failures, "template_covers_source_rows", len(template_rows), len(source_numeric_rows))
    fail_if(preflight_ids != source_ids, failures, "preflight_feedback_ids_match_source", sorted(preflight_ids), sorted(source_ids))
    fail_if(template_ids != source_ids, failures, "template_feedback_ids_match_source", sorted(template_ids), sorted(source_ids))

    for idx, row in enumerate(preflight_rows, start=1):
        fail_if(not row.get("preflight_id"), failures, "preflight_id_present", {"row": idx, "row_id": row_id(row)}, "non-empty")
        fail_if(row.get("activity_risk_label") not in (None, ""), failures, "no_activity_risk_label_written", {"row": idx, "row_id": row_id(row), "value": row.get("activity_risk_label")}, None)
        fail_if(row.get("proposal_is_formal_decision") is not False, failures, "proposal_not_formal_decision", {"row": idx, "row_id": row_id(row), "value": row.get("proposal_is_formal_decision")}, False)
        fail_if(row.get("formal_decision_written") is not False, failures, "formal_decision_not_written", {"row": idx, "row_id": row_id(row), "value": row.get("formal_decision_written")}, False)
        fail_if(row.get("training_import_written") is not False, failures, "training_import_not_written", {"row": idx, "row_id": row_id(row), "value": row.get("training_import_written")}, False)
        fail_if(int(row.get("replicate_count_counted_for_training") or 0) != 0, failures, "replicate_count_not_counted", {"row": idx, "row_id": row_id(row), "value": row.get("replicate_count_counted_for_training")}, 0)
        for field in GATE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"{field}_false", {"row": idx, "row_id": row_id(row), "value": row.get(field)}, False)

    for idx, row in enumerate(template_rows, start=1):
        fail_if(row.get("template_status") != "blank_not_formal", failures, "template_status_blank_not_formal", {"row": idx, "row_id": row_id(row), "value": row.get("template_status")}, "blank_not_formal")
        for field in TEMPLATE_REQUIRED_BLANK_FIELDS:
            fail_if(row.get(field) not in ("", None), failures, f"template_{field}_blank", {"row": idx, "row_id": row_id(row), "value": row.get(field)}, "blank")
        for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(field) is not False, failures, f"template_{field}_false", {"row": idx, "row_id": row_id(row), "value": row.get(field)}, False)

    for key, expected in (
        ("source_numeric_activity_rows", len(source_numeric_rows)),
        ("preflight_rows", len(preflight_rows)),
        ("decision_template_rows", len(template_rows)),
        ("formal_decision_rows", 0),
        ("activity_risk_label_rows_created", 0),
        ("replicate_rows_counted_for_training", 0),
        ("training_import_written_rows", 0),
        ("ready_for_training_import_rows", 0),
    ):
        fail_if(int(report.get(key) or 0) != expected, failures, f"report_{key}", report.get(key), expected)
    for field in GATE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_feedback": str(args.feedback.relative_to(AI_ROOT)),
        "checked_preflight": str(args.preflight.relative_to(AI_ROOT)),
        "checked_template": str(args.template.relative_to(AI_ROOT)),
        "source_numeric_activity_rows": len(source_numeric_rows),
        "preflight_rows": len(preflight_rows),
        "decision_template_rows": len(template_rows),
        "formal_decision_rows": 0,
        "activity_risk_label_rows_created": 0,
        "replicate_rows_counted_for_training": 0,
        "training_import_written_rows": 0,
        "ready_for_training_import_rows": 0,
        "success": not failures,
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Validation proves the package is a preflight/template only. It does not make "
            "activity_risk trainable and it does not satisfy replicate or benchmark gates."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "source_numeric_activity_rows": validation["source_numeric_activity_rows"],
        "preflight_rows": validation["preflight_rows"],
        "decision_template_rows": validation["decision_template_rows"],
        "formal_decision_rows": validation["formal_decision_rows"],
        "failures": len(failures),
        "output": str(args.output.relative_to(AI_ROOT)),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
