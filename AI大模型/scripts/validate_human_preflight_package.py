#!/usr/bin/env python3
"""Validate the unified human preflight package remains fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "governance" / "human_preflight_package.jsonl"
REPORT = AI_ROOT / "reports" / "human_preflight_package_validation_report.json"

EXPECTED_LANES = {"fireprot", "plate", "retention_85c_3min"}
EXPECTED_PACKAGE_IDS = {
    "human-preflight-fireprot-dedup-review",
    "human-preflight-plate-50-backlog",
    "human-preflight-retention-85c-3min-feedback-only",
}
COMMON_PROHIBITED_ACTIONS = {
    "do_not_write_formal_decision",
    "do_not_append_to_experiment_feedback_local",
    "do_not_import_training_rows",
    "do_not_create_or_modify_label_ddg",
    "do_not_create_or_modify_label_stability_delta_tm_c",
    "do_not_change_model_or_release_flags",
}
REQUIRED_BY_LANE = {
    "fireprot": {
        "dedup_candidate_id",
        "decision",
        "selected_source_mapping_ids",
        "approved_label_ddg_kcal_mol",
        "approved_assay_signature",
        "source_provenance_checked",
        "numbering_reviewed",
        "license_scope",
        "reviewer",
        "reviewed_at",
        "review_basis",
        "reviewed_import_receipt",
    },
    "plate": {
        "plate_id",
        "well_id",
        "variant_id",
        "sample_batch",
        "assay_type",
        "replicate",
        "raw_signal",
        "qc_flag",
        "instrument",
        "protocol_version",
        "operator",
        "recorded_at",
    },
    "retention_85c_3min": {
        "feedback_candidate_id",
        "mutation",
        "assay_condition.temperature_c",
        "assay_condition.duration_min",
        "assay_condition.metric",
        "raw_value_numeric",
        "control_value_numeric",
        "vs_control_ratio",
        "stability_relative_to_wt",
        "source_file",
        "source_file_sha256",
        "source_row_index",
        "numbering_verified",
        "authorization_valid",
        "head_schema_gap_acknowledged",
    },
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def missing(value: Any) -> bool:
    return value in (None, "", [])


def as_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def validate_common(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in [
        "package_id",
        "lane",
        "scope",
        "source_artifacts",
        "decision_target",
        "decision_validator",
        "source_state",
        "required_fields",
        "human_must_choose_one_of",
        "evidence_required",
        "prohibited_actions",
        "status",
        "ready_for_formal_decision",
        "ready_for_training_import",
        "safe_for_model_claim",
        "policy",
    ]:
        if field not in row:
            errors.append(f"missing_{field}")

    if row.get("package_id") not in EXPECTED_PACKAGE_IDS:
        errors.append("unexpected_package_id")
    lane = str(row.get("lane") or "")
    if lane not in EXPECTED_LANES:
        errors.append("unexpected_lane")

    for list_field in ["source_artifacts", "required_fields", "human_must_choose_one_of", "evidence_required", "prohibited_actions"]:
        if not isinstance(row.get(list_field), list) or not row.get(list_field):
            errors.append(f"invalid_{list_field}")

    prohibited = as_set(row.get("prohibited_actions"))
    missing_common = sorted(COMMON_PROHIBITED_ACTIONS - prohibited)
    if missing_common:
        errors.append("missing_common_prohibited_actions")

    for flag in ["ready_for_formal_decision", "ready_for_training_import", "safe_for_model_claim"]:
        if row.get(flag) is not False:
            errors.append(f"{flag}_must_remain_false")
    if row.get("ready_for_feedback_intake") is True:
        errors.append("ready_for_feedback_intake_must_not_be_true")

    state = row.get("source_state")
    if not isinstance(state, dict):
        errors.append("invalid_source_state")

    required = REQUIRED_BY_LANE.get(lane, set())
    missing_required = sorted(required - as_set(row.get("required_fields")))
    if missing_required:
        errors.append("missing_lane_required_fields")

    return errors


def validate_lane(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lane = str(row.get("lane") or "")
    state = row.get("source_state") if isinstance(row.get("source_state"), dict) else {}

    if lane == "fireprot":
        if int(state.get("packet_rows") or 0) != 2133:
            errors.append("fireprot_packet_rows_not_2133")
        if int(state.get("packet_count") or 0) != 22:
            errors.append("fireprot_packet_count_not_22")
        if int(state.get("decision_rows_present") or 0) != 0:
            errors.append("fireprot_formal_decisions_present")
        if int(state.get("ready_for_training_import_rows") or 0) != 0:
            errors.append("fireprot_training_rows_unexpected")
        if "do_not_select_or_average_ddg_without_human_review" not in as_set(row.get("prohibited_actions")):
            errors.append("fireprot_missing_ddg_selection_guard")

    if lane == "plate":
        backlog_rows = int(state.get("backlog_rows") or 0)
        review_workspace_rows = int(state.get("review_workspace_rows") or 0)
        packet_rows = int(state.get("packet_rows") or 0)
        blocked_review_workspace_rows = int(state.get("blocked_review_workspace_rows") or 0)
        if backlog_rows <= 0:
            errors.append("plate_backlog_rows_empty")
        if review_workspace_rows != backlog_rows:
            errors.append("plate_review_workspace_rows_mismatch")
        if packet_rows != backlog_rows:
            errors.append("plate_packet_rows_mismatch")
        if blocked_review_workspace_rows != backlog_rows:
            errors.append("plate_blocked_review_workspace_rows_mismatch")
        if int(state.get("ready_for_feedback_intake_rows") or 0) != 0:
            errors.append("plate_ready_for_intake_unexpected")
        if int(state.get("local_intake_rows") or 0) != 0:
            errors.append("plate_local_intake_rows_unexpected")
        if "do_not_copy_review_workspace_rows_into_local_intake" not in as_set(row.get("prohibited_actions")):
            errors.append("plate_missing_no_copy_guard")

    if lane == "retention_85c_3min":
        if int(state.get("feedback_only_rows") or 0) != 2:
            errors.append("retention_feedback_only_rows_not_2")
        if int(state.get("retention_authorized_rows") or 0) != 2:
            errors.append("retention_authorized_rows_not_2")
        if int(state.get("ready_for_training_import_rows") or 0) != 0:
            errors.append("retention_training_rows_unexpected")
        if int(state.get("claim_eligible_rows_now") or 0) != 0:
            errors.append("retention_claim_eligible_unexpected")
        if "keep_feedback_only" not in as_set(row.get("human_must_choose_one_of")):
            errors.append("retention_missing_feedback_only_decision")
        for guard in [
            "do_not_convert_retention_to_delta_tm",
            "do_not_convert_retention_to_ddg",
            "do_not_mark_retention_as_supervised_stability_label",
        ]:
            if guard not in as_set(row.get("prohibited_actions")):
                errors.append(f"retention_missing_{guard}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate unified human preflight package")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    records: list[dict[str, Any]] = []
    errors = Counter()
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for row in rows:
        package_id = str(row.get("package_id") or "")
        if package_id in seen_ids:
            duplicate_ids.add(package_id)
        seen_ids.add(package_id)
        row_errors = [*validate_common(row), *validate_lane(row)]
        errors.update(row_errors)
        records.append({
            "package_id": row.get("package_id"),
            "lane": row.get("lane"),
            "valid": not row_errors,
            "errors": row_errors,
            "ready_for_training_import": False,
            "safe_for_model_claim": False,
        })

    if duplicate_ids:
        errors.update({"duplicate_package_id": len(duplicate_ids)})
        for record in records:
            if str(record.get("package_id")) in duplicate_ids:
                record["valid"] = False
                record["errors"].append("duplicate_package_id")

    lane_set = {str(row.get("lane") or "") for row in rows}
    missing_lanes = sorted(EXPECTED_LANES - lane_set)
    unexpected_lanes = sorted(lane_set - EXPECTED_LANES)
    if missing_lanes:
        errors.update({"missing_expected_lane": len(missing_lanes)})
    if unexpected_lanes:
        errors.update({"unexpected_lane": len(unexpected_lanes)})

    valid_rows = sum(1 for record in records if record["valid"])
    report = {
        "local_only": True,
        "input": str(args.input),
        "package_rows": len(rows),
        "valid_package_rows": valid_rows,
        "invalid_package_rows": len(records) - valid_rows,
        "expected_lanes": sorted(EXPECTED_LANES),
        "missing_lanes": missing_lanes,
        "unexpected_lanes": unexpected_lanes,
        "formal_decisions_written": False,
        "training_rows_imported": False,
        "model_or_release_flags_changed": False,
        "ready_for_training_import_rows": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "success": valid_rows == len(rows) and len(rows) == len(EXPECTED_LANES) and not errors,
        "error_counts": dict(errors),
        "records": records,
        "policy": "Validation only; no formal decisions, feedback intake rows, training imports, or model/release flags are written.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "package_rows": report["package_rows"],
        "valid_package_rows": report["valid_package_rows"],
        "success": report["success"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
