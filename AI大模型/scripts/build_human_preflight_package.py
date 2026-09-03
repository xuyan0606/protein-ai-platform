#!/usr/bin/env python3
"""Build a unified fail-closed human preflight package for selected lanes."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FIREPROT_REPORT = AI_ROOT / "reports" / "fireprot_dedup_review_packet_report.json"
FIREPROT_DECISION_VALIDATION = AI_ROOT / "reports" / "fireprot_dedup_review_decision_validation_report.json"
PLATE_BACKLOG_REPORT = AI_ROOT / "reports" / "experiment_feedback_plate_intake_backlog_report.json"
PLATE_VALIDATION = AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json"
RETENTION_PREFLIGHT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_preflight.jsonl"
RETENTION_GAP_ACTIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_head_authorization_gap_actions.jsonl"
AUTH_VALIDATION = AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "governance" / "human_preflight_package.jsonl"
REPORT = AI_ROOT / "reports" / "human_preflight_package_report.json"


COMMON_PROHIBITED_ACTIONS = [
    "do_not_write_formal_decision",
    "do_not_append_to_experiment_feedback_local",
    "do_not_import_training_rows",
    "do_not_create_or_modify_label_ddg",
    "do_not_create_or_modify_label_stability_delta_tm_c",
    "do_not_change_model_or_release_flags",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path | str) -> str:
    value = Path(str(path))
    try:
        return str(value.relative_to(AI_ROOT)) if value.is_absolute() else str(value)
    except ValueError:
        return str(value)


def retention_rows(preflight_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in preflight_rows:
        condition = row.get("assay_condition") if isinstance(row.get("assay_condition"), dict) else {}
        metric = str(condition.get("metric") or row.get("metric_name") or "")
        if condition.get("temperature_c") == 85 and condition.get("duration_min") == 3 and "85C_3min" in metric:
            rows.append(row)
    return rows


def fireprot_package(report: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_id": "human-preflight-fireprot-dedup-review",
        "lane": "fireprot",
        "scope": "FireProt 2133 dedup review",
        "source_artifacts": [
            rel(FIREPROT_REPORT),
            "datasets/curation/fireprot_curated_dedup_aggregation_candidates.jsonl",
            "datasets/curation/fireprot_dedup_review_packets/*.jsonl",
            "datasets/curation/fireprot_dedup_review_decisions.template.jsonl",
        ],
        "decision_target": "datasets/curation/fireprot_dedup_review_decisions.jsonl",
        "decision_validator": "python3 scripts/validate_fireprot_dedup_review_decisions.py",
        "source_state": {
            "packet_rows": int(report.get("packet_rows") or 0),
            "packet_count": int(report.get("packet_count") or 0),
            "decision_rows_present": int(report.get("decision_rows_present") or 0),
            "approved_rows": int(report.get("approved_rows") or 0),
            "ready_for_training_import_rows": int(report.get("ready_for_training_import_rows") or 0),
            "review_class_counts": report.get("review_class_counts") or {},
            "validation_decision_rows": int(validation.get("decision_rows") or 0),
            "validation_approved_for_import_candidate_rows": int(
                validation.get("approved_for_import_candidate_rows") or 0
            ),
        },
        "required_fields": [
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
        ],
        "human_must_choose_one_of": [
            "select_source_row",
            "approve_median",
            "keep_separate",
            "exclude",
            "needs_more_info_before_decision",
        ],
        "evidence_required": [
            "source rows refer to the same protein sequence and mutation numbering",
            "source checksum, publication, assay method, pH, and temperature reviewed",
            "train/HF/test copies are treated as duplicate evidence, not independent experiments",
            "heterogeneous assays are kept separate and never pooled into a median",
            "license_scope is explicitly reviewed before any import-candidate approval",
        ],
        "prohibited_actions": COMMON_PROHIBITED_ACTIONS
        + [
            "do_not_select_or_average_ddg_without_human_review",
            "do_not_treat_import_candidate_as_training_label",
        ],
        "status": "blocked_waiting_for_human_review",
        "ready_for_formal_decision": False,
        "ready_for_training_import": False,
        "safe_for_model_claim": False,
        "policy": "Human preflight package only; it does not write FireProt decisions or approve training import.",
    }


def plate_package(report: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_id": "human-preflight-plate-50-backlog",
        "lane": "plate",
        "scope": "plate 50 backlog",
        "source_artifacts": [
            rel(PLATE_BACKLOG_REPORT),
            "datasets/feedback/experiment_feedback_plate_intake_backlog.jsonl",
            "datasets/feedback/plate_review_packets/feedback_plate_review_priority_001.jsonl",
            "contracts/experiment_feedback_plate.schema.json",
        ],
        "decision_target": "plate_review_workspace_pending_formal_intake",
        "decision_validator": "python3 scripts/validate_experiment_feedback_plate_intake.py",
        "source_state": {
            "backlog_rows": int(report.get("backlog_rows") or 0),
            "review_workspace_rows": int(report.get("draft_rows") or 0),
            "packet_rows": int(report.get("packet_rows") or 0),
            "blocked_review_workspace_rows": int(report.get("blocked_draft_rows") or 0),
            "ready_for_feedback_intake_rows": int(report.get("ready_for_feedback_intake_rows") or 0),
            "local_intake_rows": int(report.get("local_intake_rows") or 0),
            "local_valid_rows": int(report.get("local_valid_rows") or 0),
            "validation_valid_rows": int(validation.get("valid_rows") or 0),
            "missing_field_counts": report.get("missing_field_counts") or {},
            "blocker_counts": report.get("blocker_counts") or {},
        },
        "required_fields": [
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
        ],
        "human_must_choose_one_of": [
            "approved_for_plate_intake",
            "rejected",
            "needs_more_info",
        ],
        "evidence_required": [
            "source trace proves genuine wet-lab plate/well data",
            "plate_id, well_id, replicate, mutation and sample batch mapping are reviewed",
            "qc_flag is classified as pass, warning, or fail without dropping genuine failures",
            "instrument, protocol_version, operator and recorded_at are present",
            "schema validation passes before any later intake consideration",
        ],
        "prohibited_actions": COMMON_PROHIBITED_ACTIONS
        + [
            "do_not_copy_review_workspace_rows_into_local_intake",
            "do_not_promote_plate_rows_without_schema_validation",
        ],
        "status": "blocked_missing_required_schema_fields",
        "ready_for_formal_decision": False,
        "ready_for_feedback_intake": False,
        "ready_for_training_import": False,
        "safe_for_model_claim": False,
        "policy": "Human preflight package only; it does not approve or append plate feedback rows.",
    }


def retention_package(rows: list[dict[str, Any]], gap_rows: list[dict[str, Any]], auth: dict[str, Any]) -> dict[str, Any]:
    gap_by_candidate = {str(row.get("feedback_candidate_id")): row for row in gap_rows}
    candidate_ids = [str(row.get("feedback_candidate_id")) for row in rows]
    variants = sorted({str(row.get("mutation") or row.get("variant") or "") for row in rows if row.get("mutation") or row.get("variant")})
    authorized_rows = 0
    for candidate_id in candidate_ids:
        gap = gap_by_candidate.get(candidate_id) or {}
        auth_state = gap.get("authorization_state") if isinstance(gap.get("authorization_state"), dict) else {}
        if gap.get("authorization_valid") is True or auth_state.get("valid") is True:
            authorized_rows += 1
    return {
        "package_id": "human-preflight-retention-85c-3min-feedback-only",
        "lane": "retention_85c_3min",
        "scope": "85C/3min retention 2 feedback-only rows",
        "source_artifacts": [
            rel(RETENTION_PREFLIGHT),
            rel(RETENTION_GAP_ACTIONS),
            rel(AUTH_VALIDATION),
            "reports/wet_lab_head_authorization_gap_plan_report.json",
        ],
        "decision_target": "none_preflight_feedback_only",
        "decision_validator": "python3 scripts/validate_human_preflight_package.py",
        "source_state": {
            "feedback_only_rows": len(rows),
            "candidate_ids": candidate_ids,
            "variants": variants,
            "authorized_candidate_rows": int(auth.get("authorized_candidate_rows") or 0),
            "retention_authorized_rows": authorized_rows,
            "ready_for_training_import_rows": 0,
            "claim_eligible_rows_now": 0,
        },
        "required_fields": [
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
        ],
        "human_must_choose_one_of": [
            "keep_feedback_only",
            "needs_more_info",
            "exclude_from_feedback_view",
        ],
        "evidence_required": [
            "temperature_c is 85 and duration_min is 3",
            "retention is preserved as relative feedback evidence only",
            "source trace, source checksum, batch control and numbering are reviewed",
            "reviewer acknowledges this is not label_stability_delta_tm_c and not label_ddg",
            "separate head-target mapping is required before any supervised label discussion",
        ],
        "prohibited_actions": COMMON_PROHIBITED_ACTIONS
        + [
            "do_not_convert_retention_to_delta_tm",
            "do_not_convert_retention_to_ddg",
            "do_not_mark_retention_as_supervised_stability_label",
        ],
        "status": "feedback_only_fail_closed",
        "ready_for_formal_decision": False,
        "ready_for_feedback_intake": False,
        "ready_for_training_import": False,
        "safe_for_model_claim": False,
        "policy": "85C/3min retention rows are human-review feedback evidence only, not supervised stability labels.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build unified human preflight package")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    fireprot_report = load_json(FIREPROT_REPORT)
    fireprot_validation = load_json(FIREPROT_DECISION_VALIDATION)
    plate_report = load_json(PLATE_BACKLOG_REPORT)
    plate_validation = load_json(PLATE_VALIDATION)
    retention_preflight = retention_rows(load_jsonl(RETENTION_PREFLIGHT))
    retention_gap = load_jsonl(RETENTION_GAP_ACTIONS)
    auth_validation = load_json(AUTH_VALIDATION)

    rows = [
        fireprot_package(fireprot_report, fireprot_validation),
        plate_package(plate_report, plate_validation),
        retention_package(retention_preflight, retention_gap, auth_validation),
    ]
    write_jsonl(args.output, rows)

    lane_counts = Counter(row["lane"] for row in rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "output": rel(args.output),
        "package_rows": len(rows),
        "lane_counts": dict(sorted(lane_counts.items())),
        "fireprot_packet_rows": rows[0]["source_state"]["packet_rows"],
        "plate_backlog_rows": rows[1]["source_state"]["backlog_rows"],
        "retention_feedback_only_rows": rows[2]["source_state"]["feedback_only_rows"],
        "formal_decisions_written": False,
        "training_rows_imported": False,
        "model_or_release_flags_changed": False,
        "ready_for_training_import_rows": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "validator_command": "python3 scripts/validate_human_preflight_package.py",
        "policy": "Unified human preflight package only; no formal decisions, training imports, or model/release flag changes.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "package_rows": report["package_rows"],
        "fireprot_packet_rows": report["fireprot_packet_rows"],
        "plate_backlog_rows": report["plate_backlog_rows"],
        "retention_feedback_only_rows": report["retention_feedback_only_rows"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
