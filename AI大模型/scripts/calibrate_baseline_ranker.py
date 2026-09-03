#!/usr/bin/env python3
"""Suggest conservative baseline ranker calibration from evaluation errors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
EVAL = AI_ROOT / "reports" / "baseline_ranker_eval.json"
MODEL = AI_ROOT / "prototype" / "baseline_ranker_model.json"
OUT = AI_ROOT / "reports" / "baseline_calibration_suggestions.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate baseline ranker suggestions")
    parser.add_argument("--eval", type=Path, default=EVAL)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = json.loads(args.eval.read_text(encoding="utf-8"))
    model = json.loads(args.model.read_text(encoding="utf-8"))
    errors = [row for row in report.get("records", []) if row.get("predicted") != row.get("expected")]
    suggestions = []

    for row in errors:
        mutation = row.get("mutation")
        predicted = row.get("predicted")
        expected = row.get("expected")
        if expected == "go" and predicted == "watch":
            suggestions.append({
                "type": "increase_positive_feedback_weight",
                "reason": f"{mutation} has validated go evidence but remains watch",
                "candidate_weight": "has_prior_go",
                "current_value": model["weights"].get("has_prior_go"),
                "suggested_delta": 8.0,
            })
        elif expected == "watch" and predicted == "no_go":
            suggestions.append({
                "type": "soften_near_active_site_penalty",
                "reason": f"{mutation} near-active-site risk should be watch rather than automatic no_go",
                "candidate_weight": "risk_near_active_site",
                "current_value": model["weights"].get("risk_near_active_site"),
                "suggested_delta": 6.0,
            })

    payload = {
        "source_eval": str(args.eval),
        "model": model.get("version"),
        "error_count": len(errors),
        "suggestions": suggestions,
        "policy": "suggestions only; do not auto-change production weights",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"errors": len(errors), "suggestions": len(suggestions), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

