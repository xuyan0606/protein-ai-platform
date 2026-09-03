#!/usr/bin/env python3
"""Build QC/tradeoff matrix for wet-lab mutant-library feedback candidates."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_qc_matrix.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_qc_matrix_report.json"

OUTCOME_SCORE = {"no_go": -1, "watch": 0, "go": 1}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def metric_class(metric: str, assay_type: str) -> str:
    if "酸性保持率" in metric or "pH4.8/pH6.0" in metric:
        return "acid_retention"
    if "pH4.8" in metric:
        return "acid_activity"
    if "pH6.0" in metric or "pH6" in metric:
        return "neutral_activity"
    if assay_type == "stability" or "热稳定" in metric or "85C" in metric:
        return "thermal_stability"
    return assay_type or "unknown"


def review_priority(outcomes: Counter[str], metric_classes: set[str]) -> str:
    if outcomes.get("go", 0) and outcomes.get("no_go", 0):
        return "critical_tradeoff_review"
    if outcomes.get("no_go", 0):
        return "high_no_go_review"
    if outcomes.get("go", 0) and outcomes.get("watch", 0):
        return "medium_mixed_benefit_review"
    if outcomes.get("go", 0):
        return "medium_confirmatory_review"
    if len(metric_classes) >= 3:
        return "standard_multi_property_review"
    return "standard_review"


def property_call(outcomes: Counter[str]) -> str:
    if outcomes.get("go", 0) and outcomes.get("no_go", 0):
        return "tradeoff_go_and_no_go"
    if outcomes.get("no_go", 0):
        return "contains_no_go"
    if outcomes.get("go", 0):
        return "contains_go"
    if outcomes.get("watch", 0):
        return "watch_only"
    return "inconclusive"


def build_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        if row.get("numeric_training_candidate") is True:
            grouped[(str(row.get("source_project")), str(row.get("variant")))].append(row)

    matrix_rows = []
    for (project, variant), rows in sorted(grouped.items()):
        metric_rows = []
        outcomes: Counter[str] = Counter()
        metric_classes = set()
        assay_types = set()
        ratios = []
        for row in sorted(rows, key=lambda item: str(item.get("metric_name"))):
            metric = str(row.get("metric_name") or "")
            klass = metric_class(metric, str(row.get("assay_type") or ""))
            outcome = str(row.get("outcome_candidate") or "inconclusive")
            outcomes[outcome] += 1
            metric_classes.add(klass)
            assay_types.add(str(row.get("assay_type") or ""))
            if isinstance(row.get("vs_control_ratio"), (int, float)):
                ratios.append(float(row["vs_control_ratio"]))
            metric_rows.append({
                "feedback_candidate_id": row.get("feedback_candidate_id"),
                "metric_name": row.get("metric_name"),
                "metric_class": klass,
                "assay_type": row.get("assay_type"),
                "raw_value_numeric": row.get("raw_value_numeric"),
                "control_value_numeric": row.get("control_value_numeric"),
                "vs_control_ratio": row.get("vs_control_ratio"),
                "outcome_candidate": outcome,
                "confidence_tier": row.get("confidence_tier"),
                "batch_id": row.get("batch_id"),
                "sample_id": row.get("sample_id"),
                "source_file": row.get("source_file"),
                "source_row_index": row.get("source_row_index"),
            })

        conflicting_property_signal = outcomes.get("go", 0) > 0 and outcomes.get("no_go", 0) > 0
        score_sum = sum(OUTCOME_SCORE.get(outcome, 0) * count for outcome, count in outcomes.items())
        matrix_rows.append({
            "qc_matrix_id": f"wetlab-mutlib-qc-{project.lower()}-{variant.lower()}",
            "source_project": project,
            "variant": variant,
            "mutation_set": rows[0].get("mutation_set") if rows else [],
            "candidate_rows": len(rows),
            "metric_classes": sorted(metric_classes),
            "assay_types": sorted(assay_types),
            "outcome_counts": dict(sorted(outcomes.items())),
            "property_call": property_call(outcomes),
            "review_priority": review_priority(outcomes, metric_classes),
            "conflicting_property_signal": conflicting_property_signal,
            "ratio_min": min(ratios) if ratios else None,
            "ratio_max": max(ratios) if ratios else None,
            "ratio_range": (max(ratios) - min(ratios)) if ratios else None,
            "metric_rows": metric_rows,
            "authorization_guidance": [
                "Do not collapse this variant into one training label.",
                "Authorize or reject each metric/candidate row independently.",
                "Require reviewer confirmation of unit, condition, batch/control, replicate policy and source trace.",
            ],
            "ready_for_feedback_intake": False,
            "claim_eligible_now": False,
            "policy": "QC matrix only; not authorization, not training intake, and not model-quality evidence.",
        })
    return matrix_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback QC matrix")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    matrix_rows = build_rows(candidates)
    priority_counts = Counter(row["review_priority"] for row in matrix_rows)
    property_counts = Counter(row["property_call"] for row in matrix_rows)
    conflicting = [row for row in matrix_rows if row["conflicting_property_signal"]]
    write_jsonl(args.output, matrix_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidates": str(args.candidates),
        "output": str(args.output),
        "numeric_training_candidate_rows": sum(1 for row in candidates if row.get("numeric_training_candidate") is True),
        "qc_matrix_rows": len(matrix_rows),
        "variant_rows": len(matrix_rows),
        "conflicting_property_rows": len(conflicting),
        "critical_tradeoff_review_rows": priority_counts.get("critical_tradeoff_review", 0),
        "priority_counts": dict(sorted(priority_counts.items())),
        "property_call_counts": dict(sorted(property_counts.items())),
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "policy": "QC matrix summarizes real wet-lab candidate tradeoffs but never authorizes intake or creates labels.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "qc_matrix_rows": report["qc_matrix_rows"],
        "conflicting_property_rows": report["conflicting_property_rows"],
        "critical_tradeoff_review_rows": report["critical_tradeoff_review_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
