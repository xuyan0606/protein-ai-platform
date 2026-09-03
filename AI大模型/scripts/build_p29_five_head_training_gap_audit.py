#!/usr/bin/env python3
"""Build a source-bound audit of P29 five-head training execution gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GAP_ACTIONS = AI_ROOT / "datasets" / "governance" / "five_head_training_gap_actions.jsonl"
SAMPLE_QUEUE = AI_ROOT / "datasets" / "governance" / "five_head_training_sample_gap_queue.jsonl"
GAP_REPORT = AI_ROOT / "reports" / "five_head_training_gap_plan_report.json"
THRESHOLD_REPORT = AI_ROOT / "reports" / "five_head_training_threshold_report.json"
SAMPLE_REPORT = AI_ROOT / "reports" / "five_head_training_sample_gap_queue_report.json"
EXECUTION_REPORT = AI_ROOT / "reports" / "five_head_training_execution_contract_report.json"
EXECUTION_VALIDATION = AI_ROOT / "reports" / "five_head_training_execution_contract_validation_report.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
MODEL_QUALITY = AI_ROOT / "reports" / "model_quality_hard_gate_contract_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p29_five_head_training_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p29_five_head_training_gap_audit_report.json"


EXPECTED_HEADS = ("mutation_rank", "stability", "activity_risk", "substrate_fit", "assay_success")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def claim_row(matrix: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for row in matrix.get("claims") or []:
        if isinstance(row, dict) and row.get("claim_id") == claim_id:
            return row
    return {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base(audit_id: str, gap_type: str, source_report: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": source_report,
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "P29 five-head training gap audit only; it does not create labels, training rows, model claims, release approval, or production authorization.",
    }


def main() -> int:
    gap_actions = load_jsonl(GAP_ACTIONS)
    sample_rows = load_jsonl(SAMPLE_QUEUE)
    gap_report = load_json(GAP_REPORT)
    threshold = load_json(THRESHOLD_REPORT)
    sample_report = load_json(SAMPLE_REPORT)
    execution = load_json(EXECUTION_REPORT)
    execution_validation = load_json(EXECUTION_VALIDATION)
    claim_matrix = load_json(CLAIM_MATRIX)
    model_quality = load_json(MODEL_QUALITY)
    five_head_claim = claim_row(claim_matrix, "five_head_training_run")
    rows: list[dict[str, Any]] = []

    for row in gap_actions:
        head = row.get("head")
        rows.append(base(
            f"p29-five-head-gap-action::{head}",
            "five_head_training_gap_action",
            "reports/five_head_training_gap_plan_report.json",
            {
                "head": head,
                "head_status": row.get("head_status"),
                "current_training_rows": row.get("current_training_rows"),
                "candidate_rows_observed": row.get("candidate_rows_observed"),
                "ready_candidate_rows": row.get("ready_candidate_rows"),
                "minimum_rows": row.get("minimum_rows"),
                "minimum_replicates": row.get("minimum_replicates"),
                "minimum_groups": row.get("minimum_groups"),
                "missing_to_minimum": row.get("missing_to_minimum"),
                "thresholds_met": row.get("thresholds_met"),
                "training_unlocked": row.get("training_unlocked"),
            },
            "head-specific training gap action remains blocked below reviewed-label and threshold requirements",
        ) | {
            "head": head,
            "head_status": row.get("head_status"),
            "current_training_rows": row.get("current_training_rows"),
            "missing_to_minimum": row.get("missing_to_minimum"),
            "thresholds_met": row.get("thresholds_met") is True,
            "training_unlocked": row.get("training_unlocked") is True,
            "completion_ready": False,
        })

    for row in sample_rows:
        head = row.get("head")
        rows.append(base(
            f"p29-five-head-sample-gap::{head}",
            "five_head_sample_threshold_gap",
            "reports/five_head_training_sample_gap_queue_report.json",
            {
                "head": head,
                "current_label_rows": row.get("current_label_rows"),
                "current_replicate_count": row.get("current_replicate_count"),
                "current_group_count": row.get("current_group_count"),
                "minimum_label_rows": row.get("minimum_label_rows"),
                "minimum_replicates": row.get("minimum_replicates"),
                "minimum_groups": row.get("minimum_groups"),
                "missing_label_rows_to_minimum": row.get("missing_label_rows_to_minimum"),
                "missing_replicates_to_minimum": row.get("missing_replicates_to_minimum"),
                "missing_groups_to_minimum": row.get("missing_groups_to_minimum"),
                "status": row.get("status"),
            },
            "sample, explicit replicate, or independent-group thresholds remain unmet",
        ) | {
            "head": head,
            "current_label_rows": row.get("current_label_rows"),
            "missing_label_rows_to_minimum": row.get("missing_label_rows_to_minimum"),
            "missing_replicates_to_minimum": row.get("missing_replicates_to_minimum"),
            "missing_groups_to_minimum": row.get("missing_groups_to_minimum"),
            "completion_ready": False,
        })

    training_label = execution.get("training_label_import") if isinstance(execution.get("training_label_import"), dict) else {}
    rows.append(base(
        "p29-five-head-training-execution-summary",
        "five_head_training_execution_summary",
        "reports/five_head_training_execution_contract_report.json",
        {
            "ready_head_count": execution.get("ready_head_count"),
            "total_head_training_rows": execution.get("total_head_training_rows"),
            "training_import_eligible_rows": training_label.get("training_import_eligible_rows"),
            "training_execution_allowed": execution.get("training_execution_allowed"),
            "execution_validation_success": execution_validation.get("success"),
            "threshold_ready_heads": threshold.get("threshold_ready_heads"),
            "blocked_heads": threshold.get("blocked_heads"),
            "sample_gap_queue_rows": sample_report.get("queue_rows"),
            "missing_label_rows_total": sample_report.get("missing_label_rows_total"),
            "missing_replicates_total": sample_report.get("missing_replicates_total"),
            "missing_groups_total": sample_report.get("missing_groups_total"),
            "five_head_claim_ready": five_head_claim.get("ready"),
            "five_head_claim_allowed": five_head_claim.get("allowed"),
            "model_quality_ready": (model_quality.get("current_state") or {}).get("model_quality_ready"),
        },
        "global five-head training execution and claim gates remain blocked",
    ) | {
        "ready_head_count": execution.get("ready_head_count"),
        "training_import_eligible_rows": training_label.get("training_import_eligible_rows"),
        "training_execution_allowed": False,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "gap_action_rows": len(gap_actions),
        "sample_gap_rows": len(sample_rows),
        "expected_heads": list(EXPECTED_HEADS),
        "gap_action_heads": [row.get("head") for row in gap_actions],
        "sample_gap_heads": [row.get("head") for row in sample_rows],
        "gap_plan_ready_heads": gap_report.get("ready_heads"),
        "gap_plan_blocked_heads": gap_report.get("blocked_heads"),
        "threshold_ready_heads": threshold.get("threshold_ready_heads"),
        "threshold_blocked_heads": threshold.get("blocked_heads"),
        "ready_head_count": execution.get("ready_head_count"),
        "total_head_training_rows": execution.get("total_head_training_rows"),
        "training_import_eligible_rows": training_label.get("training_import_eligible_rows"),
        "sample_gap_queue_rows": sample_report.get("queue_rows"),
        "missing_label_rows_total": sample_report.get("missing_label_rows_total"),
        "missing_replicates_total": sample_report.get("missing_replicates_total"),
        "missing_groups_total": sample_report.get("missing_groups_total"),
        "blocked_reasons": execution.get("blocked_reasons"),
        "five_head_claim_ready": five_head_claim.get("ready"),
        "five_head_claim_allowed": five_head_claim.get("allowed"),
        "model_quality_ready": (model_quality.get("current_state") or {}).get("model_quality_ready"),
        "training_execution_allowed": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p29_five_head_training_gap_audit.jsonl",
        "policy": "P29 audit only. Five-head training remains blocked until all heads satisfy reviewed-label, sample, explicit replicate, independent-group, benchmark, and claim gates.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "gap_action_rows": report["gap_action_rows"],
        "sample_gap_rows": report["sample_gap_rows"],
        "ready_head_count": report["ready_head_count"],
        "training_execution_allowed": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
