#!/usr/bin/env python3
"""Build a fail-closed contract for five-head training execution."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "five_head_training_execution_contract_report.json"

INPUTS = {
    "multitask_training_readiness": "reports/multitask_training_readiness_report.json",
    "five_head_training_gap_plan": "reports/five_head_training_gap_plan_report.json",
    "five_head_training_threshold": "reports/five_head_training_threshold_report.json",
    "training_label_import_contract_validation": "reports/training_label_import_contract_validation_report.json",
    "wet_lab_feedback_authorization_contract_validation": "reports/wet_lab_feedback_authorization_contract_validation_report.json",
    "benchmark_coverage_dashboard_validation": "reports/benchmark_coverage_dashboard_validation_report.json",
    "advanced_model_feature_contract_validation": "reports/advanced_model_feature_contract_validation_report.json",
}

EXPECTED_HEADS = ("mutation_rank", "stability", "activity_risk", "substrate_fit", "assay_success")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build five-head training execution contract")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    paths = {name: AI_ROOT / rel_path for name, rel_path in INPUTS.items()}
    reports = {name: load_json(path) for name, path in paths.items()}
    missing_inputs = [rel(path) for path in paths.values() if not path.exists()]

    multitask = reports["multitask_training_readiness"]
    gap = reports["five_head_training_gap_plan"]
    threshold = reports["five_head_training_threshold"]
    label_contract = reports["training_label_import_contract_validation"]
    wetlab_contract = reports["wet_lab_feedback_authorization_contract_validation"]
    benchmark_contract = reports["benchmark_coverage_dashboard_validation"]
    feature_contract = reports["advanced_model_feature_contract_validation"]

    threshold_heads = threshold.get("heads") if isinstance(threshold.get("heads"), dict) else {}
    legacy_heads = multitask.get("heads") if isinstance(multitask.get("heads"), dict) else {}
    multitask_threshold_parity = {}
    multitask_threshold_parity_failures = []
    head_rows = {}
    for head in EXPECTED_HEADS:
        threshold_row = threshold_heads.get(head) if isinstance(threshold_heads.get(head), dict) else {}
        legacy_row = legacy_heads.get(head) if isinstance(legacy_heads.get(head), dict) else {}
        thresholds = threshold_row.get("thresholds") if isinstance(threshold_row.get("thresholds"), dict) else {}
        label_rows = as_int(threshold_row.get("label_rows"))
        legacy_rows = as_int(legacy_row.get("rows"))
        minimum_samples = as_int(thresholds.get("minimum_samples")) or as_int(legacy_row.get("minimum_rows")) or 100
        legacy_minimum_rows = as_int(legacy_row.get("minimum_rows")) or 100
        row_parity = {
            "multitask_rows": legacy_rows,
            "threshold_label_rows": label_rows,
            "rows_match": legacy_rows == label_rows,
            "multitask_minimum_rows": legacy_minimum_rows,
            "threshold_minimum_samples": minimum_samples,
            "minimum_rows_match": legacy_minimum_rows == minimum_samples,
            "multitask_ready": legacy_row.get("ready") is True,
            "thresholds_met": threshold_row.get("thresholds_met") is True,
        }
        multitask_threshold_parity[head] = row_parity
        if not row_parity["rows_match"]:
            multitask_threshold_parity_failures.append({
                "head": head,
                "check": "multitask_rows_match_threshold_label_rows",
                "multitask_rows": legacy_rows,
                "threshold_label_rows": label_rows,
            })
        if not row_parity["minimum_rows_match"]:
            multitask_threshold_parity_failures.append({
                "head": head,
                "check": "multitask_minimum_rows_match_threshold_minimum_samples",
                "multitask_minimum_rows": legacy_minimum_rows,
                "threshold_minimum_samples": minimum_samples,
            })
        head_rows[head] = {
            "rows": label_rows,
            "label_rows": label_rows,
            "candidate_rows": as_int(threshold_row.get("candidate_rows")),
            "minimum_rows": minimum_samples,
            "minimum_samples": minimum_samples,
            "minimum_replicates": as_int(thresholds.get("minimum_replicates")),
            "minimum_groups": as_int(thresholds.get("minimum_groups")),
            "sample_count": as_int((threshold_row.get("label_metrics") or {}).get("sample_count")),
            "replicate_count": as_int((threshold_row.get("label_metrics") or {}).get("replicate_count")),
            "group_count": as_int((threshold_row.get("label_metrics") or {}).get("group_count")),
            "thresholds_met": threshold_row.get("thresholds_met") is True,
            "ready": threshold_row.get("thresholds_met") is True and label_rows > 0,
            "missing_to_minimum": max(minimum_samples - label_rows, 0),
            "status": threshold_row.get("status"),
        }
    threshold_ready = (
        not missing_inputs
        and bool(threshold)
        and threshold.get("expected_heads") == list(EXPECTED_HEADS)
        and threshold.get("source_consistency_failures") == []
        and threshold.get("training_execution_allowed") is False
        and not multitask_threshold_parity_failures
    )
    ready_heads = [head for head, row in head_rows.items() if row["ready"]]
    total_head_rows = sum(row["rows"] for row in head_rows.values())
    label_totals = label_contract.get("contract_totals") if isinstance(label_contract.get("contract_totals"), dict) else {}

    training_import_eligible_rows = as_int(
        label_totals.get("training_import_eligible_rows")
        if label_totals
        else label_contract.get("training_import_eligible_rows")
    )
    wetlab_ready_rows = as_int(wetlab_contract.get("ready_for_training_import_rows"))
    benchmark_ready = bool(benchmark_contract.get("ready_for_model_claim"))
    feature_refs = as_int((feature_contract.get("feature_contract") or {}).get("ready_feature_refs"))

    blocked_reasons = []
    if training_import_eligible_rows == 0:
        blocked_reasons.append("training_import_eligible_rows_zero")
    elif training_import_eligible_rows < 100:
        blocked_reasons.append("training_import_eligible_rows_below_minimum")
    if not threshold_ready:
        blocked_reasons.append("per_head_threshold_report_missing_or_inconsistent")
    elif len(ready_heads) < len(EXPECTED_HEADS):
        blocked_reasons.append("per_head_sample_replicate_group_thresholds_not_met")
    if ready_heads:
        blocked_reasons.append("unexpected_ready_heads_present")
    else:
        blocked_reasons.append("all_five_heads_missing_minimum_training_rows")
    if wetlab_ready_rows == 0:
        blocked_reasons.append("wet_lab_training_import_rows_zero")
    if not benchmark_ready:
        blocked_reasons.append("benchmark_ready_for_model_claim_false")

    training_execution_allowed = (
        not missing_inputs
        and training_import_eligible_rows >= 100
        and len(ready_heads) == len(EXPECTED_HEADS)
        and benchmark_ready
    )
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not missing_inputs,
        "checked_inputs": INPUTS,
        "missing_inputs": missing_inputs,
        "status": "blocked",
        "expected_heads": list(EXPECTED_HEADS),
        "head_rows": head_rows,
        "ready_heads": ready_heads,
        "ready_head_count": len(ready_heads),
        "total_head_training_rows": total_head_rows,
        "minimum_rows_per_head": 100,
        "training_label_import": {
            "contract_success": bool(label_contract.get("success")),
            "training_import_eligible_rows": training_import_eligible_rows,
            "safe_for_training_import": bool(label_contract.get("safe_for_training_import")),
            "safe_for_model_claim": bool(label_contract.get("safe_for_model_claim")),
        },
        "per_head_threshold_gate": {
            "report": INPUTS["five_head_training_threshold"],
            "report_present": bool(threshold),
            "report_consistent": threshold_ready,
            "multitask_threshold_parity": multitask_threshold_parity,
            "multitask_threshold_parity_failures": multitask_threshold_parity_failures,
            "source_counts": threshold.get("source_counts"),
            "candidate_heads": threshold.get("candidate_heads"),
            "blocked_heads": threshold.get("blocked_heads"),
            "threshold_ready_heads": threshold.get("threshold_ready_heads"),
            "feature_rows_counted_as_labels": (
                threshold.get("feature_label_boundary") or {}
            ).get("feature_rows_counted_as_labels"),
        },
        "wet_lab_authorization": {
            "contract_success": bool(wetlab_contract.get("success")),
            "numeric_training_candidate_rows": wetlab_contract.get("numeric_training_candidate_rows"),
            "authorized_rows": wetlab_contract.get("authorized_rows"),
            "ready_for_training_import_rows": wetlab_ready_rows,
        },
        "benchmark_gate": {
            "contract_success": bool(benchmark_contract.get("success")),
            "benchmark_rows": benchmark_contract.get("benchmark_rows"),
            "valid_rows": benchmark_contract.get("valid_rows"),
            "ready_for_model_claim": benchmark_ready,
        },
        "feature_input_gate": {
            "contract_success": bool(feature_contract.get("success")),
            "ready_feature_refs": feature_refs,
            "feature_inputs_are_labels": False,
        },
        "blocked_reasons": blocked_reasons,
        "training_execution_allowed": training_execution_allowed,
        "model_quality_claim_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Five-head training execution is blocked until every head has enough reviewed, "
            "authorized, provenance-backed labels and benchmark gates are ready. Feature refs "
            "are input-only and cannot unlock training execution. Per-head sample, explicit "
            "replicate, and independent-group thresholds are required before any head can be "
            "considered threshold-ready."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "ready_head_count": report["ready_head_count"],
        "total_head_training_rows": total_head_rows,
        "training_import_eligible_rows": training_import_eligible_rows,
        "training_execution_allowed": training_execution_allowed,
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
