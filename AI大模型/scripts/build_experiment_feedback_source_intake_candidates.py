#!/usr/bin/env python3
"""Build extraction candidates from validated feedback source-review decisions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_source_candidates.jsonl"
DECISIONS = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_source_review_decisions.local.jsonl"
VALIDATION_REPORT = AI_ROOT / "reports" / "experiment_feedback_source_review_decision_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_source_intake_candidates.jsonl"
REPORT = AI_ROOT / "reports" / "experiment_feedback_source_intake_candidate_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build experiment feedback source intake candidates")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--validation-report", type=Path, default=VALIDATION_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    decisions = load_jsonl(args.decisions)
    validation = load_json(args.validation_report)
    candidate_by_path = {str(row.get("relative_path") or row.get("path")): row for row in candidates}
    valid_by_path = {
        str(row.get("source_path")): row
        for row in validation.get("records", [])
        if row.get("valid") and row.get("approved_for_feedback_extraction")
    }

    rows: list[dict[str, Any]] = []
    for decision in decisions:
        source_path = str(decision.get("source_path") or "")
        if source_path not in valid_by_path:
            continue
        source = candidate_by_path.get(source_path, {})
        rows.append({
            "source_intake_candidate_id": "feedback-source-intake-" + source_path.encode("utf-8").hex()[:24],
            "source_path": source_path,
            "absolute_source_path": source.get("path"),
            "source_review_bucket": source.get("source_review_bucket"),
            "reviewed_source_type": decision.get("reviewed_source_type"),
            "extractability": decision.get("extractability"),
            "candidate_feedback_rows": decision.get("candidate_feedback_rows"),
            "approved_for_feedback_extraction": True,
            "approved_for_feedback_intake": False,
            "ready_for_extraction": True,
            "ready_for_feedback_intake": False,
            "ready_for_training_import": False,
            "required_next_checks": [
                "extract rows into experiment_feedback.local.jsonl using the schema",
                "verify mutation numbering for every extracted row",
                "verify assay units, conditions, batch/control, replicate and QC policy",
                "run validate_experiment_feedback_intake.py before any model use",
            ],
            "evidence_summary": decision.get("evidence_summary"),
            "reviewer": decision.get("reviewer"),
            "reviewed_at": decision.get("reviewed_at"),
            "policy": "Extraction candidate only; not a feedback row and not training data.",
        })

    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidate_source_rows": len(candidates),
        "decision_rows": len(decisions),
        "valid_approved_source_rows": len(valid_by_path),
        "source_intake_candidate_rows": len(rows),
        "ready_for_extraction_rows": len(rows),
        "ready_for_feedback_intake_rows": 0,
        "ready_for_training_import_rows": 0,
        "safe_for_model_claim": False,
        "outputs": {"jsonl": str(args.output)},
        "policy": "Human source approval can only create extraction candidates; schema-valid feedback intake remains a separate reviewed step.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_intake_candidate_rows": len(rows),
        "ready_for_feedback_intake_rows": 0,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
