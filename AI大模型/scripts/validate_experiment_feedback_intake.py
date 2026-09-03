#!/usr/bin/env python3
"""Validate local experiment-feedback intake without promoting any labels."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json"

VALID_OUTCOMES = {"go", "watch", "no_go", "failed", "inconclusive"}
NUMERIC_LABEL_FIELDS = {"activity_relative_to_wt", "stability_delta_tm_c", "expression_yield_relative"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(row: dict[str, Any]) -> list[str]:
    errors = []
    if not row.get("feedback_id"):
        errors.append("missing_feedback_id")
    if not row.get("mutation"):
        errors.append("missing_mutation")
    if row.get("outcome") not in VALID_OUTCOMES:
        errors.append("invalid_outcome")
    if row.get("source") not in {"kwb_wet_lab", "kwb_historical"}:
        errors.append("untrusted_source")
    if row.get("numbering_verified") is not True:
        errors.append("numbering_not_verified")
    return errors


def has_numeric_label(row: dict[str, Any]) -> bool:
    return any(isinstance(row.get(field), (int, float)) and not isinstance(row.get(field), bool) for field in NUMERIC_LABEL_FIELDS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate experiment feedback intake")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    records = []
    for row in rows:
        errors = validate(row)
        numeric_label = has_numeric_label(row)
        records.append({
            "feedback_id": row.get("feedback_id"),
            "valid": not errors,
            "training_eligible": not errors,
            "qualitative_training_eligible": not errors and not numeric_label,
            "numeric_training_eligible": not errors and numeric_label,
            "data_granularity": row.get("data_granularity") or ("numeric_observation" if numeric_label else "qualitative_observation"),
            "errors": errors,
        })
    report = {
        "input_rows": len(rows),
        "valid_rows": sum(1 for row in records if row["valid"]),
        "invalid_rows": sum(1 for row in records if not row["valid"]),
        "training_eligible_rows": sum(1 for row in records if row["training_eligible"]),
        "qualitative_training_eligible_rows": sum(1 for row in records if row["qualitative_training_eligible"]),
        "numeric_training_eligible_rows": sum(1 for row in records if row["numeric_training_eligible"]),
        "numeric_label_fields": sorted(NUMERIC_LABEL_FIELDS),
        "error_counts": dict(Counter(error for row in records for error in row["errors"])),
        "records": records[:200],
        "policy": "empty or unverified feedback cannot become training labels; qualitative historical observations are separated from numeric assay labels",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "input_rows": report["input_rows"],
        "valid_rows": report["valid_rows"],
        "training_eligible_rows": report["training_eligible_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
