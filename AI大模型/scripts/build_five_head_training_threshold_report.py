#!/usr/bin/env python3
"""Build a fail-closed per-head sample/replicate/group threshold report.

This report is an evidence census only. It does not create labels, approve
feedback, start training, or change claim/release state.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "five_head_training_threshold_report.json"

EXPECTED_HEADS = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)

# These are conservative entry thresholds for this lane. They are data-quality
# gates, not a license to train or to make a model-quality claim.
THRESHOLDS = {
    "mutation_rank": {"minimum_samples": 100, "minimum_replicates": 3, "minimum_groups": 10},
    "stability": {"minimum_samples": 100, "minimum_replicates": 3, "minimum_groups": 10},
    "activity_risk": {"minimum_samples": 100, "minimum_replicates": 3, "minimum_groups": 10},
    "substrate_fit": {"minimum_samples": 100, "minimum_replicates": 3, "minimum_groups": 10},
    "assay_success": {"minimum_samples": 100, "minimum_replicates": 3, "minimum_groups": 10},
}

PATHS = {
    "strict": AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl",
    "numeric_feedback": AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl",
    "fireprot_reviewed": AI_ROOT / "datasets" / "curation" / "fireprot_reviewed_import_candidates.jsonl",
    "plate": AI_ROOT / "datasets" / "feedback" / "experiment_feedback_plate.local.jsonl",
    "validated_features": AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl",
    "audited_training": AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_audited.jsonl",
    "fireprot_mapping_candidates": AI_ROOT / "datasets" / "curation" / "fireprot_curated_kwb_schema_mapping_candidates.jsonl",
    "wet_lab_candidates": AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl",
    "activity_risk_decisions": AI_ROOT / "datasets" / "feedback" / "activity_risk_label_replicate_decisions.jsonl",
    "activity_risk_training_import": AI_ROOT / "datasets" / "training" / "activity_risk_training_import_labels.jsonl",
}

REPORT_PATHS = {
    "feedback_validation": "reports/experiment_feedback_intake_validation_report.json",
    "label_provenance": "reports/label_provenance_audit_report.json",
    "fireprot_reviewed": "reports/fireprot_reviewed_import_candidate_report.json",
    "plate_validation": "reports/experiment_feedback_plate_intake_validation_report.json",
    "activity_risk_formal_label_decision": "reports/activity_risk_formal_label_decision_report.json",
    "activity_risk_training_import": "reports/activity_risk_training_import_label_validation_report.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if not path.exists():
        return rows, errors
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({"line": line_number, "error": str(exc)})
            continue
        if not isinstance(value, dict):
            errors.append({"line": line_number, "error": "row_is_not_object"})
            continue
        rows.append(value)
    return rows, errors


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def non_null(value: Any) -> bool:
    return value is not None and value != ""


def first_value(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if non_null(row.get(key)):
            return row[key]
    return None


def nested_value(row: dict[str, Any], container: str, keys: Iterable[str]) -> Any:
    nested = row.get(container)
    if not isinstance(nested, dict):
        return None
    return first_value(nested, keys)


def group_key(row: dict[str, Any]) -> str | None:
    value = first_value(row, ("group_id", "variant_id", "mutation", "record_id"))
    if non_null(value):
        return str(value)
    value = nested_value(row, "assay_condition", ("sample_id", "variant_id", "mutation"))
    return str(value) if non_null(value) else None


def replicate_key(row: dict[str, Any]) -> str | None:
    value = first_value(row, ("replicate", "replicate_id", "replicate_index"))
    if not non_null(value):
        value = nested_value(row, "assay_condition", ("replicate", "replicate_id", "replicate_index"))
    return str(value) if non_null(value) else None


def measurement_group(row: dict[str, Any]) -> str | None:
    value = first_value(row, ("batch_id", "sample_batch", "project_id", "enzyme_id", "uniprot_id"))
    if not non_null(value):
        value = nested_value(row, "assay_condition", ("batch_id", "sample_batch"))
    return str(value) if non_null(value) else None


def row_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {value for value in (group_key(row) for row in rows) if value is not None}
    replicate_levels = {value for value in (replicate_key(row) for row in rows) if value is not None}
    replicate_observations = {
        (group_key(row), replicate_key(row))
        for row in rows
        if group_key(row) is not None and replicate_key(row) is not None
    }
    group_measurements = {
        value for value in (measurement_group(row) for row in rows) if value is not None
    }
    return {
        "sample_count": len(rows),
        "group_count": len(groups),
        "replicate_count": len(replicate_levels),
        "replicate_observation_count": len(replicate_observations),
        "groups_with_explicit_replicate": len(
            {group for group, _replicate in replicate_observations if group is not None}
        ),
        "measurement_group_count": len(group_measurements),
        "rows_missing_explicit_replicate": sum(1 for row in rows if replicate_key(row) is None),
        "group_values": sorted(groups)[:20],
        "replicate_values": sorted(replicate_levels)[:20],
    }


def threshold_result(metrics: dict[str, Any], thresholds: dict[str, int]) -> dict[str, Any]:
    checks = {
        "minimum_samples": {
            "observed": metrics["sample_count"],
            "required": thresholds["minimum_samples"],
            "met": metrics["sample_count"] >= thresholds["minimum_samples"],
        },
        "minimum_replicates": {
            "observed": metrics["replicate_count"],
            "required": thresholds["minimum_replicates"],
            "met": metrics["replicate_count"] >= thresholds["minimum_replicates"],
        },
        "minimum_groups": {
            "observed": metrics["group_count"],
            "required": thresholds["minimum_groups"],
            "met": metrics["group_count"] >= thresholds["minimum_groups"],
        },
    }
    return {
        "thresholds": thresholds,
        "checks": checks,
        "thresholds_met": all(check["met"] for check in checks.values()),
    }


def has_any(row: dict[str, Any], fields: Iterable[str]) -> bool:
    return any(non_null(row.get(field)) for field in fields)


def numeric_feedback_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numeric_fields = ("activity_relative_to_wt", "stability_delta_tm_c", "expression_yield_relative")
    return [
        row
        for row in rows
        if row.get("source") == "kwb_wet_lab"
        and row.get("quantitative_assay_available") is True
        and has_any(row, numeric_fields)
    ]


def plate_training_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("review_status") == "reviewed"
        and row.get("qc_flag") in {"pass", "warning"}
        and has_any(row, ("raw_signal", "normalized_activity"))
    ]


def head_rows(
    head: str,
    strict_rows: list[dict[str, Any]],
    numeric_rows: list[dict[str, Any]],
    fireprot_rows: list[dict[str, Any]],
    plate_rows: list[dict[str, Any]],
    activity_risk_decisions: list[dict[str, Any]],
    activity_risk_training_import: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[str, ...], list[str]]:
    if head == "mutation_rank":
        label_rows = [row for row in strict_rows if has_any(row, ("label_decision",))]
        return label_rows, [], ("label_decision",), ["strict_supervised"]

    if head == "stability":
        label_rows = [
            row for row in strict_rows + fireprot_rows
            if has_any(row, ("label_stability_delta_tm_c", "label_ddg", "ddg", "delta_tm_c"))
        ]
        return label_rows, [], ("label_stability_delta_tm_c", "label_ddg"), [
            "strict_supervised",
            "fireprot_reviewed_import",
        ]

    if head == "activity_risk":
        candidate_rows = [
            row for row in numeric_rows
            if non_null(row.get("activity_relative_to_wt"))
        ]
        label_rows = [
            row for row in activity_risk_training_import
            if row.get("head") == "activity_risk"
            and row.get("ready_for_training_import") is True
            and row.get("training_label_source") is True
            and non_null(row.get("label_value"))
        ]
        return label_rows, candidate_rows, ("activity_relative_to_wt", "activity_risk_label"), [
            "numeric_feedback",
            "activity_risk_formal_label_decisions",
            "activity_risk_training_import_labels",
        ]

    if head == "substrate_fit":
        candidate_rows = [
            row for row in numeric_rows
            if row.get("assay_type") == "substrate_fit"
        ]
        label_rows = [
            row for row in candidate_rows
            if non_null(row.get("substrate_fit_label"))
        ]
        return label_rows, candidate_rows, ("substrate_fit_label",), ["numeric_feedback"]

    candidate_rows = list(plate_rows)
    label_rows = [
        row for row in candidate_rows
        if non_null(row.get("assay_success"))
    ]
    return label_rows, candidate_rows, ("assay_success",), ["plate_feedback"]


def build_head_report(
    head: str,
    strict_rows: list[dict[str, Any]],
    numeric_rows: list[dict[str, Any]],
    fireprot_rows: list[dict[str, Any]],
    plate_rows: list[dict[str, Any]],
    activity_risk_decisions: list[dict[str, Any]],
    activity_risk_training_import: list[dict[str, Any]],
) -> dict[str, Any]:
    label_rows, candidate_rows, required_fields, label_sources = head_rows(
        head,
        strict_rows,
        numeric_rows,
        fireprot_rows,
        plate_rows,
        activity_risk_decisions,
        activity_risk_training_import,
    )
    label_metrics = row_metrics(label_rows)
    candidate_metrics = row_metrics(candidate_rows)
    result = threshold_result(label_metrics, THRESHOLDS[head])
    missing_fields_in_candidates = {
        field: sum(1 for row in candidate_rows if not non_null(row.get(field)))
        for field in required_fields
    }
    missing_fields_in_label_rows = {
        field: sum(1 for row in label_rows if not non_null(row.get(field)))
        for field in required_fields
    }
    blockers: list[str] = []
    if not label_rows:
        blockers.append("no_head_label_rows")
    if label_rows and any(count > 0 for count in missing_fields_in_label_rows.values()):
        blockers.append("required_head_label_fields_missing")
    if not result["thresholds_met"]:
        blockers.append("sample_replicate_group_thresholds_not_met")
    if candidate_rows and not label_rows:
        blockers.append("candidate_rows_are_not_labels")

    status = "ready_for_threshold_review" if result["thresholds_met"] else (
        "label_rows_below_threshold" if label_rows else ("candidate_only" if candidate_rows else "blocked")
    )
    return {
        "head": head,
        "status": status,
        "required_label_fields": list(required_fields),
        "label_sources": label_sources,
        "label_rows": len(label_rows),
        "candidate_rows": len(candidate_rows),
        "label_metrics": label_metrics,
        "candidate_metrics": candidate_metrics,
        "missing_required_fields_in_label_rows": missing_fields_in_label_rows,
        "missing_required_fields_in_candidates": missing_fields_in_candidates,
        "thresholds": result["thresholds"],
        "threshold_checks": result["checks"],
        "thresholds_met": result["thresholds_met"],
        "trainable": False,
        "training_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "blockers": blockers,
        "policy": (
            "Candidate rows are evidence only. A head label row must satisfy the explicit "
            "head label contract; rows without replicate metadata do not receive inferred replicates."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build five-head sample/replicate/group threshold report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    loaded: dict[str, list[dict[str, Any]]] = {}
    parse_errors: dict[str, list[dict[str, Any]]] = {}
    for name, path in PATHS.items():
        loaded[name], parse_errors[name] = load_jsonl(path)

    strict_rows = loaded["strict"]
    feedback_rows = loaded["numeric_feedback"]
    numeric_rows = numeric_feedback_rows(feedback_rows)
    fireprot_rows = loaded["fireprot_reviewed"]
    activity_risk_decisions = loaded["activity_risk_decisions"]
    activity_risk_training_import = loaded["activity_risk_training_import"]
    plate_rows = loaded["plate"]
    eligible_plate_rows = plate_training_rows(plate_rows)
    source_reports = {
        name: load_json(AI_ROOT / path)
        for name, path in REPORT_PATHS.items()
    }

    source_counts = {
        "numeric_feedback_rows": len(numeric_rows),
        "strict_supervised_rows": len(strict_rows),
        "fireprot_reviewed_import_rows": len(fireprot_rows),
        "plate_training_eligible_rows": len(eligible_plate_rows),
        "activity_risk_formal_label_decision_rows": len(activity_risk_decisions),
        "activity_risk_training_import_label_rows": len(activity_risk_training_import),
    }
    source_report_counts = {
        "numeric_feedback_rows": as_int(
            source_reports["feedback_validation"].get("numeric_training_eligible_rows")
        ),
        "strict_supervised_rows": as_int(
            source_reports["label_provenance"].get("strict_rows")
        ),
        "fireprot_reviewed_import_rows": as_int(
            source_reports["fireprot_reviewed"].get("reviewed_import_candidate_rows")
        ),
        "plate_training_eligible_rows": as_int(
            source_reports["plate_validation"].get("training_eligible_rows")
        ),
        "activity_risk_formal_label_decision_rows": as_int(
            source_reports["activity_risk_formal_label_decision"].get("formal_decision_rows")
        ),
        "activity_risk_training_import_label_rows": as_int(
            source_reports["activity_risk_training_import"].get("training_import_written_rows")
        ),
    }
    consistency_failures = [
        {
            "source": key,
            "observed_from_jsonl": source_counts[key],
            "reported": source_report_counts[key],
        }
        for key in source_counts
        if source_counts[key] != source_report_counts[key]
    ]

    heads = {
        head: build_head_report(
            head,
            strict_rows,
            numeric_rows,
            fireprot_rows,
            eligible_plate_rows,
            activity_risk_decisions,
            activity_risk_training_import,
        )
        for head in EXPECTED_HEADS
    }
    threshold_ready_heads = [
        head for head, report in heads.items()
        if report["thresholds_met"] and report["label_rows"] > 0
    ]
    candidate_heads = [
        head for head, report in heads.items()
        if report["status"] == "candidate_only"
    ]
    zero_label_heads = [
        head for head, report in heads.items()
        if report["status"] == "blocked"
    ]
    below_threshold_heads = [
        head for head, report in heads.items()
        if report["label_rows"] > 0 and not report["thresholds_met"]
    ]
    blocked_heads = [
        head for head, report in heads.items()
        if not (report["thresholds_met"] and report["label_rows"] > 0)
    ]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "expected_heads": list(EXPECTED_HEADS),
        "threshold_policy": {
            "minimum_samples": 100,
            "minimum_replicates": 3,
            "minimum_independent_groups": 10,
            "replicate_definition": "explicit replicate/replicate_id/replicate_index only; missing means zero",
            "group_definition": "unique mutation/variant/record identity; no inferred grouping from feature rows",
        },
        "source_paths": {
            key: str(path.relative_to(AI_ROOT))
            for key, path in PATHS.items()
        },
        "source_counts": source_counts,
        "source_report_counts": source_report_counts,
        "source_consistency_failures": consistency_failures,
        "excluded_from_label_counts": {
            "validated_feature_index_rows": len(loaded["validated_features"]),
            "audited_training_rows": len(loaded["audited_training"]),
            "fireprot_mapping_candidate_rows": len(loaded["fireprot_mapping_candidates"]),
            "wet_lab_mutant_library_candidate_rows": len(loaded["wet_lab_candidates"]),
        },
        "feature_label_boundary": {
            "feature_rows_observed": len(loaded["validated_features"]),
            "feature_rows_counted_as_labels": 0,
            "feature_inputs_are_labels": False,
            "policy": "Feature rows are input-only and never satisfy a head label threshold.",
        },
        "parse_errors": parse_errors,
        "heads": heads,
        "threshold_ready_heads": threshold_ready_heads,
        "trainable_heads": [],
        "candidate_heads": candidate_heads,
        "zero_label_heads": zero_label_heads,
        "below_threshold_heads": below_threshold_heads,
        "blocked_heads": blocked_heads,
        "ready_head_count": 0,
        "training_execution_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "This report is a local evidence census only. It never converts numeric feedback "
            "candidates into labels, never counts feature rows as labels, never starts training, "
            "and never opens model-claim or release gates."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "source_counts": source_counts,
        "threshold_ready_heads": threshold_ready_heads,
        "candidate_heads": candidate_heads,
        "zero_label_heads": zero_label_heads,
        "below_threshold_heads": below_threshold_heads,
        "blocked_heads": blocked_heads,
        "training_execution_allowed": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
