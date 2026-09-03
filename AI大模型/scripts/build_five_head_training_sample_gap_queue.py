#!/usr/bin/env python3
"""Build a fail-closed, machine-executable five-head sample gap queue.

This queue is an evidence census and operator work queue. It does not create
labels, infer replicates, approve source data, import training rows, or open
model/release gates.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSONL = AI_ROOT / "datasets" / "governance" / "five_head_training_sample_gap_queue.jsonl"
DEFAULT_REPORT = AI_ROOT / "reports" / "five_head_training_sample_gap_queue_report.json"

EXPECTED_HEADS = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)

INPUTS = {
    "threshold_report": "reports/five_head_training_threshold_report.json",
    "wet_lab_candidates": "datasets/feedback/wet_lab_mutant_library_feedback_candidates.jsonl",
    "wet_lab_authorization_gap_actions": "datasets/feedback/wet_lab_head_authorization_gap_actions.jsonl",
    "activity_risk_formal_label_decisions": "datasets/feedback/activity_risk_label_replicate_decisions.jsonl",
    "fireprot_mapping_candidates": "datasets/curation/fireprot_curated_kwb_schema_mapping_candidates.jsonl",
    "fireprot_reviewed_import_candidates": "datasets/curation/fireprot_reviewed_import_candidates.jsonl",
    "validated_feature_index": "datasets/features/validated_feature_index.jsonl",
}

HEAD_ACTIONS = {
    "mutation_rank": {
        "priority": "P0",
        "required_source_pools": ["reviewed_numbering", "real_supervised_labels"],
        "next_action": "Complete reviewed numbering and provenance decisions, then admit only real-source ranking labels.",
        "human_or_external_blockers": [
            "reviewed_numbering_decision_missing",
            "real_label_provenance_receipt_missing",
            "explicit_label_and_replicate_contract_missing",
        ],
        "forbidden_actions": [
            "do_not_promote_numbering_drafts",
            "do_not_count_feature_rows_as_labels",
            "do_not_import_without_real_source_receipt",
        ],
    },
    "stability": {
        "priority": "P0",
        "required_source_pools": ["fireprot_mapping_candidates", "fireprot_reviewed_import", "kwb_wet_lab_stability"],
        "next_action": "Resolve FireProt license/scope, dedup, numbering, and reviewed import decisions; separately review KWB stability metrics.",
        "human_or_external_blockers": [
            "fireprot_reviewed_import_receipt_missing",
            "fireprot_dedup_and_numbering_review_missing",
            "kwb_stability_metric_mapping_missing",
        ],
        "forbidden_actions": [
            "do_not_count_fireprot_mapping_candidates_as_labels",
            "do_not_convert_retention_or_proxy_ddg_into_delta_tm_or_kcal_labels",
            "do_not_import_without_reviewed_import_receipt",
        ],
    },
    "activity_risk": {
        "priority": "P0",
        "required_source_pools": ["kwb_wet_lab_activity_numeric", "activity_authorization_gap"],
        "next_action": "Obtain metric-level authorization and explicit activity_risk_label/replicate decisions, then rerun preflight and apply-plan validators.",
        "human_or_external_blockers": [
            "activity_metric_authorization_missing",
            "activity_risk_label_decision_missing",
            "explicit_replicate_metadata_missing",
        ],
        "forbidden_actions": [
            "do_not_infer_activity_risk_label_from_ratio",
            "do_not_treat_pH_or_metric_rows_as_replicates",
            "do_not_append_feedback_or_training_rows_without_authorized_apply",
        ],
    },
    "substrate_fit": {
        "priority": "P1",
        "required_source_pools": ["substrate_specific_assays"],
        "next_action": "Create and review a substrate-specific label schema; ingest only rows with substrate identity and assay context.",
        "human_or_external_blockers": [
            "substrate_label_schema_missing",
            "substrate_specific_source_missing",
            "explicit_replicate_and_group_contract_missing",
        ],
        "forbidden_actions": [
            "do_not_infer_substrate_fit_from_generic_activity",
            "do_not_count_msa_or_structure_features_as_substrate_labels",
            "do_not_import_without_substrate_identity_and_conditions",
        ],
    },
    "assay_success": {
        "priority": "P0",
        "required_source_pools": ["plate_well_feedback"],
        "next_action": "Review plate/well QC and extract both success and failure outcomes into the assay_success schema.",
        "human_or_external_blockers": [
            "plate_well_qc_review_missing",
            "assay_success_label_extraction_missing",
            "explicit_replicate_and_batch_contract_missing",
        ],
        "forbidden_actions": [
            "do_not_use_success_only_selection",
            "do_not_count_plate_backlog_as_labels",
            "do_not_import_without_qc_and_failure_outcomes",
        ],
    },
}


def load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, "missing_file"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"json_decode_error:{exc}"
    return (value if isinstance(value, dict) else {}), None


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], ["missing_file"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line_{line_number}:json_decode_error:{exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"line_{line_number}:row_not_object")
            continue
        rows.append(value)
    return rows, errors


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def non_null(value: Any) -> bool:
    return value is not None and value != ""


def candidate_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def first(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if non_null(row.get(key)):
                return row[key]
        return None

    groups = {
        str(value)
        for value in (first(row, ("group_id", "variant_id", "mutation", "variant", "record_id")) for row in rows)
        if non_null(value)
    }
    replicates = {
        str(value)
        for value in (first(row, ("replicate", "replicate_id", "replicate_index")) for row in rows)
        if non_null(value)
    }
    return {
        "rows": len(rows),
        "unique_groups": len(groups),
        "unique_explicit_replicates": len(replicates),
        "rows_with_explicit_replicate": sum(
            1 for row in rows if non_null(first(row, ("replicate", "replicate_id", "replicate_index")))
        ),
    }


def source_pool(
    name: str,
    path: str,
    rows: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]] | None = None,
    *,
    selection_is_training_eligible: bool = False,
    formal_decision_written_rows: int = 0,
) -> dict[str, Any]:
    selected = rows if selected_rows is None else selected_rows
    return {
        "pool": name,
        "path": path,
        "observed_rows": len(rows),
        "selected_rows_for_head": len(selected),
        "selection_is_training_eligible": selection_is_training_eligible,
        "training_import_written_rows": 0,
        "formal_decision_written_rows": formal_decision_written_rows,
        "sample_metrics": candidate_metric(selected),
    }


def build_queue_row(
    head: str,
    threshold_head: dict[str, Any],
    pools: list[dict[str, Any]],
) -> dict[str, Any]:
    config = HEAD_ACTIONS[head]
    thresholds = threshold_head.get("thresholds") if isinstance(threshold_head.get("thresholds"), dict) else {}
    label_metrics = threshold_head.get("label_metrics") if isinstance(threshold_head.get("label_metrics"), dict) else {}
    candidate_metrics = threshold_head.get("candidate_metrics") if isinstance(threshold_head.get("candidate_metrics"), dict) else {}
    current_rows = as_int(threshold_head.get("label_rows"))
    required_rows = as_int(thresholds.get("minimum_samples")) or 100
    current_groups = as_int(label_metrics.get("group_count"))
    current_replicates = as_int(label_metrics.get("replicate_count"))
    current_replicate_observations = as_int(label_metrics.get("replicate_observation_count"))
    required_groups = as_int(thresholds.get("minimum_groups")) or 10
    required_replicates = as_int(thresholds.get("minimum_replicates")) or 3
    return {
        "queue_id": f"five-head-gap-{head}",
        "head": head,
        "priority": config["priority"],
        "status": "blocked",
        "current_label_rows": current_rows,
        "current_group_count": current_groups,
        "current_replicate_count": current_replicates,
        "current_replicate_observation_count": current_replicate_observations,
        "minimum_label_rows": required_rows,
        "minimum_groups": required_groups,
        "minimum_replicates": required_replicates,
        "missing_label_rows_to_minimum": max(required_rows - current_rows, 0),
        "missing_groups_to_minimum": max(required_groups - current_groups, 0),
        "missing_replicates_to_minimum": max(required_replicates - current_replicates, 0),
        "threshold_candidate_rows": as_int(threshold_head.get("candidate_rows")),
        "threshold_candidate_metrics": candidate_metrics,
        "candidate_source_pools": pools,
        "required_source_pools": config["required_source_pools"],
        "next_action": config["next_action"],
        "human_or_external_blockers": config["human_or_external_blockers"],
        "forbidden_actions": config["forbidden_actions"],
        "thresholds_met": threshold_head.get("thresholds_met") is True,
        "training_import_written_rows": 0,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Evidence queue only. Candidate rows, source pools, feature rows, and "
            "computational ddG inputs do not become labels or training rows without "
            "the explicit source and head decisions."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build five-head training sample gap queue")
    parser.add_argument("--output-jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    threshold, threshold_error = load_json(AI_ROOT / INPUTS["threshold_report"])
    wet_candidates, wet_errors = load_jsonl(AI_ROOT / INPUTS["wet_lab_candidates"])
    auth_gap, auth_errors = load_jsonl(AI_ROOT / INPUTS["wet_lab_authorization_gap_actions"])
    fireprot_mapping, fireprot_errors = load_jsonl(AI_ROOT / INPUTS["fireprot_mapping_candidates"])
    fireprot_reviewed, reviewed_errors = load_jsonl(AI_ROOT / INPUTS["fireprot_reviewed_import_candidates"])
    activity_decisions, activity_decision_errors = load_jsonl(AI_ROOT / INPUTS["activity_risk_formal_label_decisions"])
    features, feature_errors = load_jsonl(AI_ROOT / INPUTS["validated_feature_index"])
    threshold_heads = threshold.get("heads") if isinstance(threshold.get("heads"), dict) else {}

    wet_activity = [
        row for row in wet_candidates
        if row.get("assay_type") == "activity"
        and row.get("numeric_training_candidate") is True
        and non_null(row.get("activity_relative_to_wt"))
    ]
    auth_activity = [row for row in auth_gap if row.get("expected_authorization_head") == "activity_risk_head"]
    wet_stability = [row for row in wet_candidates if row.get("assay_type") == "stability"]
    fireprot_stability = list(fireprot_mapping)

    pool_map = {
        "mutation_rank": [
            source_pool("reviewed_numbering", "reports/numbering_review_operator_queue.json", []),
            source_pool("real_supervised_labels", "datasets/curated/enzyme_mutation_supervised_repaired_verified.jsonl", []),
        ],
        "stability": [
            source_pool("fireprot_mapping_candidates", INPUTS["fireprot_mapping_candidates"], fireprot_stability),
            source_pool("fireprot_reviewed_import", INPUTS["fireprot_reviewed_import_candidates"], fireprot_reviewed),
            source_pool("kwb_wet_lab_stability", INPUTS["wet_lab_candidates"], wet_stability),
        ],
        "activity_risk": [
            source_pool("kwb_wet_lab_activity_numeric", INPUTS["wet_lab_candidates"], wet_activity),
            source_pool("activity_authorization_gap", INPUTS["wet_lab_authorization_gap_actions"], auth_activity),
            source_pool(
                "activity_risk_formal_label_decisions",
                INPUTS["activity_risk_formal_label_decisions"],
                activity_decisions,
                [
                    row for row in activity_decisions
                    if row.get("ready_for_activity_risk_head_label") is True
                    and row.get("ready_for_training_import") is True
                ],
                selection_is_training_eligible=bool(activity_decisions),
                formal_decision_written_rows=len(activity_decisions),
            ),
        ],
        "substrate_fit": [
            source_pool("substrate_specific_assays", "datasets/feedback/substrate_specific_assays.jsonl", []),
        ],
        "assay_success": [
            source_pool("plate_well_feedback", "datasets/feedback/experiment_feedback_plate.local.jsonl", []),
        ],
    }

    queue_rows = [
        build_queue_row(head, threshold_heads.get(head, {}), pool_map[head])
        for head in EXPECTED_HEADS
    ]
    parse_errors = {
        "threshold_report": [threshold_error] if threshold_error else [],
        "wet_lab_candidates": wet_errors,
        "wet_lab_authorization_gap_actions": auth_errors,
        "fireprot_mapping_candidates": fireprot_errors,
        "fireprot_reviewed_import_candidates": reviewed_errors,
        "activity_risk_formal_label_decisions": activity_decision_errors,
        "validated_feature_index": feature_errors,
    }
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "queue_rows": len(queue_rows),
        "expected_heads": list(EXPECTED_HEADS),
        "current_label_rows": sum(row["current_label_rows"] for row in queue_rows),
        "current_group_count_total": sum(row["current_group_count"] for row in queue_rows),
        "current_replicate_count_total": sum(row["current_replicate_count"] for row in queue_rows),
        "missing_label_rows_total": sum(row["missing_label_rows_to_minimum"] for row in queue_rows),
        "missing_groups_total": sum(row["missing_groups_to_minimum"] for row in queue_rows),
        "missing_replicates_total": sum(row["missing_replicates_to_minimum"] for row in queue_rows),
        "candidate_source_pool_rows": sum(
            pool["observed_rows"] for row in queue_rows for pool in row["candidate_source_pools"]
        ),
        "feature_rows_observed": len(features),
        "feature_rows_counted_as_labels": 0,
        "training_import_written_rows": 0,
        "observed_formal_decision_rows": sum(
            pool["formal_decision_written_rows"] for row in queue_rows for pool in row["candidate_source_pools"]
        ),
        "formal_decision_written_rows": 0,
        "model_or_release_flags_changed_rows": 0,
        "parse_errors": parse_errors,
        "heads_with_current_labels": [row["head"] for row in queue_rows if row["current_label_rows"] > 0],
        "candidate_heads": [row["head"] for row in queue_rows if row["candidate_source_pools"] and any(pool["observed_rows"] for pool in row["candidate_source_pools"])],
        "blocked_heads": list(EXPECTED_HEADS),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output_jsonl": str(args.output_jsonl.relative_to(AI_ROOT)),
        "policy": (
            "Machine-executable gap queue only. It quantifies missing samples, independent "
            "groups, and explicit replicates. It never infers labels or replicates, never "
            "writes formal decisions, and never opens training/model/release gates."
        ),
    }
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.output_jsonl.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in queue_rows),
        encoding="utf-8",
    )
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "queue_rows": report["queue_rows"],
        "missing_label_rows_total": report["missing_label_rows_total"],
        "candidate_heads": report["candidate_heads"],
        "training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
