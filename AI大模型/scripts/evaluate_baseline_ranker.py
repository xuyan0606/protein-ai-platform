#!/usr/bin/env python3
"""Evaluate the local baseline ranker against the local training table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRAINING_TABLE = ROOT / "datasets" / "curated" / "training_table.jsonl"
MODEL_FILE = ROOT / "prototype" / "baseline_ranker_model.json"
REPORT_OUT = ROOT / "reports" / "baseline_ranker_eval.json"


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def score_row(row: dict[str, Any], weights: dict[str, float], bias: float) -> float:
    score = bias
    for key, weight in weights.items():
        value = row.get(key)
        if isinstance(value, bool):
            numeric = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            numeric = float(value)
        else:
            numeric = 0.0
        score += float(weight) * numeric
    return max(0.0, min(100.0, score))


def decision(score: float, row: dict[str, Any]) -> str:
    if row.get("risk_protected_catalytic") or row.get("has_prior_no_go"):
        return "no_go"
    if score >= 80:
        return "go"
    if score >= 45:
        return "watch"
    return "no_go"


def expected_decision(row: dict[str, Any]) -> str:
    if row.get("risk_protected_catalytic") or row.get("has_prior_no_go"):
        return "no_go"
    if row.get("has_prior_go"):
        return "go"
    return "watch"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate local baseline ranker")
    parser.add_argument("--input", type=Path, default=TRAINING_TABLE)
    parser.add_argument("--model", type=Path, default=MODEL_FILE)
    parser.add_argument("--output", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_rows(args.input)
    model = json.loads(args.model.read_text(encoding="utf-8"))
    weights = model["weights"]
    bias = float(model["bias"])

    records = []
    correct = 0
    for row in rows:
        score = score_row(row, weights, bias)
        predicted = decision(score, row)
        expected = expected_decision(row)
        if predicted == expected:
            correct += 1
        records.append({
            "case_id": row.get("case_id"),
            "mutation": row.get("mutation"),
            "score": round(score, 3),
            "predicted": predicted,
            "expected": expected,
        })

    report = {
        "rows": len(rows),
        "correct": correct,
        "accuracy": round(correct / len(rows), 3) if rows else 0,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "accuracy": report["accuracy"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["accuracy"] >= 0.7 else 1


if __name__ == "__main__":
    raise SystemExit(main())

