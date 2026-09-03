#!/usr/bin/env python3
"""Train a dependency-free baseline ranker from local feature rows.

This is a rule-calibrated baseline, not a neural network. It creates a versioned
weights file so future learned models can be compared against a stable baseline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRAINING_TABLE = ROOT / "datasets" / "curated" / "training_table.jsonl"
STRICT_TRAINING_TABLE = ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
MODEL_OUT = ROOT / "prototype" / "baseline_ranker_model.json"


BASE_WEIGHTS = {
    "has_sequence": 3.0,
    "has_structure": 5.0,
    "numbering_verified": 8.0,
    "has_substrate": 3.0,
    "kwb_private_records": 2.5,
    "public_database_records": 1.2,
    "tool_result_count": 0.8,
    "has_ligand_tool_result": 4.0,
    "has_md_tool_result": 3.0,
    "has_annotation_result": 5.0,
    "assay_completeness": 2.0,
    "is_proline_mutation": 8.0,
    "is_charge_mutation": 2.0,
    "has_prior_go": 15.0,
    "has_prior_no_go": -22.0,
    "risk_protected_catalytic": -60.0,
    "risk_near_active_site": -20.0,
    "risk_near_pocket": -6.0,
    "risk_numbering_uncertain": -25.0,
    "risk_low_structure_confidence": -10.0,
}


def is_truthy_marker(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return False


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def assert_strict_supervised_rows(rows: list[dict[str, Any]], path: Path) -> None:
    failures: list[str] = []
    for index, row in enumerate(rows, start=1):
        if row.get("usable_as_supervised_label") is not True:
            failures.append(f"row_{index}:usable_as_supervised_label_not_true")
        if row.get("numbering_verified_by_sequence") is not True:
            failures.append(f"row_{index}:numbering_verified_by_sequence_not_true")
        if is_truthy_marker(row.get("usable_as_weak_evidence")):
            failures.append(f"row_{index}:weak_evidence")
        if row.get("integrity_flags"):
            failures.append(f"row_{index}:integrity_flags_present")
        if row.get("label_decision") not in {"go", "watch", "no_go"}:
            failures.append(f"row_{index}:invalid_label_decision")
    if failures:
        sample = ", ".join(failures[:10])
        raise SystemExit(
            f"Refusing non-strict baseline-ranker input {path}: "
            f"{len(failures)} guard failure(s): {sample}"
        )


def score_row(row: dict[str, Any], weights: dict[str, float], bias: float) -> float:
    score = bias
    for key, weight in weights.items():
        value = row.get(key)
        if isinstance(value, bool):
            numeric = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            numeric = float(value)
        elif value in {None, ""}:
            numeric = 0.0
        else:
            numeric = 0.0
        score += weight * numeric
    return max(0.0, min(100.0, score))


def main() -> int:
    parser = argparse.ArgumentParser(description="Train local baseline ranker")
    parser.add_argument("--input", type=Path, default=STRICT_TRAINING_TABLE)
    parser.add_argument("--output", type=Path, default=MODEL_OUT)
    args = parser.parse_args()

    rows = load_rows(args.input)
    assert_strict_supervised_rows(rows, args.input)
    if not rows:
        raise SystemExit("strict supervised training table is empty; training is blocked")

    # Bias is calibrated to keep unvalidated candidates in Watch range.
    bias = 25.0
    scores = [score_row(row, BASE_WEIGHTS, bias) for row in rows]
    model = {
        "model": "KWB-EnzymeDesigner-baseline-ranker",
        "version": "0.1.0-linear-baseline",
        "trained_on_rows": len(rows),
        "training_source": str(args.input),
        "bias": bias,
        "weights": BASE_WEIGHTS,
        "score_summary": {
            "min": round(min(scores), 3),
            "max": round(max(scores), 3),
            "mean": round(mean(scores), 3),
        },
        "decision_thresholds": {
            "go": 80,
            "watch": 45,
            "no_go": 0
        },
        "limitations": [
            "rule-calibrated baseline only",
            "not a trained neural model",
            "requires wet-lab validation",
            "benchmark cases are synthetic local R&D fixtures"
        ]
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "output": str(args.output), "mean_score": model["score_summary"]["mean"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
