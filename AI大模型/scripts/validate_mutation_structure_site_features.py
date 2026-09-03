#!/usr/bin/env python3
"""Validate candidate-level mutation structure site features."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

AI_ROOT = Path(__file__).resolve().parents[1]
INDEX = AI_ROOT / "datasets" / "features" / "mutation_structure_site_features.jsonl"
REPORT = AI_ROOT / "reports" / "mutation_structure_site_feature_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(row: dict[str, Any]) -> list[str]:
    errors = []
    for field in ("feature_id", "record_id", "candidate_id", "structure_id", "selected_chain_id"):
        if not row.get(field):
            errors.append(f"{field}_missing")
    if row.get("mapping_status") != "deterministic_input_candidate":
        errors.append("mapping_status_not_deterministic")
    if float(row.get("neighbor_cutoff_angstrom") or 0) != 8.0:
        errors.append("neighbor_cutoff_invalid")
    if not isinstance(row.get("neighbor_count"), int) or row["neighbor_count"] < 0:
        errors.append("neighbor_count_invalid")
    if row.get("training_label") is not False:
        errors.append("training_label_must_be_false")
    if row.get("safe_for_model_claim") is not False:
        errors.append("safe_for_model_claim_must_be_false")
    if row.get("release_ready") is not False:
        errors.append("release_ready_must_be_false")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate mutation structure site features")
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    rows = load_jsonl(args.index)
    records = [{"feature_id": row.get("feature_id"), "valid": not validate(row), "errors": validate(row)} for row in rows]
    counts = Counter(error for record in records for error in record["errors"])
    report = {
        "input_rows": len(rows),
        "valid_rows": sum(record["valid"] for record in records),
        "invalid_rows": sum(not record["valid"] for record in records),
        "error_counts": dict(counts),
        "training_import_eligible_rows": 0,
        "safe_for_model_claim": False,
        "records": records,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
