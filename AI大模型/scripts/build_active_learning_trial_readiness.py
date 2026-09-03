#!/usr/bin/env python3
"""Build fail-closed active learning trial readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "active_learning_trial_readiness_report.json"
DRAFT_OUT = AI_ROOT / "datasets" / "curation" / "active_learning_trial_drafts.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build active learning trial readiness")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--draft-output", type=Path, default=DRAFT_OUT)
    args = parser.parse_args()

    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    benchmark = load_json(AI_ROOT / "reports" / "benchmark_matrix_report.json")
    biosecurity = load_json(AI_ROOT / "reports" / "biosecurity_readiness_report.json")
    customer = load_json(AI_ROOT / "reports" / "customer_delivery_readiness_report.json")
    blockers = [
        "five-head model is not training-ready",
        "head-level benchmark scorecards are not ready",
        "plate-level feedback intake has no eligible rows",
        "human approval workflow is not configured",
        "budget and assay capacity are not approved",
    ]
    if not biosecurity.get("ready_for_ordering"):
        blockers.append("biosecurity/order gate is not approved")
    if not customer.get("ready"):
        blockers.append("customer delivery gate is blocked")
    args.draft_output.parent.mkdir(parents=True, exist_ok=True)
    args.draft_output.write_text("", encoding="utf-8")
    report = {
        "local_only": True,
        "ready": False,
        "draft_file": str(args.draft_output),
        "draft_rows": 0,
        "candidate_generation_allowed": False,
        "experiment_submission_allowed": False,
        "human_approval_required": True,
        "model_status": multitask.get("status"),
        "benchmark_ready_for_model_claim": benchmark.get("ready_for_model_claim"),
        "blockers": blockers,
        "policy": "active learning can rank human-reviewed candidates only after data, benchmark, approval, budget, and biosecurity gates pass",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ready": False, "draft_rows": 0, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
