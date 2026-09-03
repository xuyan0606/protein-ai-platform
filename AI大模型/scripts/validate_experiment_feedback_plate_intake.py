#!/usr/bin/env python3
"""Validate local plate-level experiment feedback intake fail-closed."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_plate.local.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_plate.template.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json"

VALID_QC = {"pass", "warning", "fail", "not_reviewed"}
VALID_REVIEW = {"draft", "reviewed", "rejected"}
VALID_ASSAYS = {"expression", "purification", "activity", "stability", "substrate_fit", "combined"}
WELL_RE = re.compile(r"^[A-Za-z][0-9]{1,2}$")


TEMPLATE_ROW = {
    "plate_id": "template-plate-001",
    "well_id": "A1",
    "variant_id": "template-variant",
    "parent_sequence_hash": None,
    "mutation_set": [],
    "sample_batch": "template-batch",
    "substrate_smiles": None,
    "temperature_c": None,
    "ph": None,
    "assay_type": "activity",
    "replicate": 1,
    "raw_signal": None,
    "normalized_activity": None,
    "qc_flag": "not_reviewed",
    "instrument": "template-instrument",
    "protocol_version": "template-protocol",
    "operator": "template-operator",
    "raw_data_uri": None,
    "recorded_at": "2026-07-27T00:00:00+08:00",
    "review_status": "draft"
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["plate_id", "well_id", "variant_id", "sample_batch", "assay_type", "replicate", "qc_flag", "instrument", "protocol_version", "operator", "recorded_at"]:
        if row.get(field) in {None, ""}:
            errors.append(f"missing_{field}")
    if row.get("well_id") and not WELL_RE.match(str(row.get("well_id"))):
        errors.append("invalid_well_id")
    if row.get("assay_type") not in VALID_ASSAYS:
        errors.append("invalid_assay_type")
    if row.get("qc_flag") not in VALID_QC:
        errors.append("invalid_qc_flag")
    if row.get("review_status", "draft") not in VALID_REVIEW:
        errors.append("invalid_review_status")
    if not isinstance(row.get("replicate"), int) or int(row.get("replicate") or 0) < 1:
        errors.append("invalid_replicate")
    ph = row.get("ph")
    if ph is not None and (not isinstance(ph, (int, float)) or ph < 0 or ph > 14):
        errors.append("invalid_ph")
    if row.get("review_status") != "reviewed":
        errors.append("not_reviewed")
    if row.get("qc_flag") not in {"pass", "warning", "fail"}:
        errors.append("qc_not_usable")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate plate-level feedback intake")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    args.template.parent.mkdir(parents=True, exist_ok=True)
    args.template.write_text(json.dumps(TEMPLATE_ROW, ensure_ascii=False) + "\n", encoding="utf-8")
    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")

    rows = load_jsonl(args.input)
    records = []
    errors = Counter()
    for row in rows:
        row_errors = validate(row)
        errors.update(row_errors)
        records.append({
            "plate_id": row.get("plate_id"),
            "well_id": row.get("well_id"),
            "variant_id": row.get("variant_id"),
            "valid": not row_errors,
            "training_eligible": not row_errors,
            "errors": row_errors,
        })
    report = {
        "input": str(args.input),
        "template": str(args.template),
        "input_rows": len(rows),
        "valid_rows": sum(1 for item in records if item["valid"]),
        "invalid_rows": sum(1 for item in records if not item["valid"]),
        "training_eligible_rows": sum(1 for item in records if item["training_eligible"]),
        "ready_for_training": False,
        "error_counts": dict(errors),
        "records": records[:200],
        "policy": "Plate-level rows must be reviewed and QC-classified before any training eligibility; empty intake remains safe.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"input_rows": len(rows), "valid_rows": report["valid_rows"], "training_eligible_rows": report["training_eligible_rows"], "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
