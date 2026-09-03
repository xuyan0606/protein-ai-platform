#!/usr/bin/env python3
"""Validate the local next-release operator decision packet.

This validator is read-only. It checks that the packet references real local
decision files, templates, reports, and build/validation scripts while keeping
the packet fail-closed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET = AI_ROOT / "reports" / "next_release_operator_decision_packet_20260805.md"
REPORT_OUT = AI_ROOT / "reports" / "next_release_operator_decision_packet_validation_report.json"

REQUIRED_PATHS = [
    "reports/operator_work_receipt_manifest_consistency_validation_report.json",
    "reports/local_release_manifest.json",
    "reports/local_release_manifest_fail_closed_consistency_validation_report.json",
    "reports/local_release_human_decision_control_plane_validation_report_20260806.json",
    "reports/claim_readiness_matrix.json",
    "reports/claim_readiness_matrix_fail_closed_policy_validation_report.json",
    "reports/model_claim_fail_closed_consistency_report.json",
    "reports/model_artifact_claim_guard_report.json",
    "reports/local_release_guard_coverage_validation_report.json",
    "reports/local_release_safety_guard_link_validation_report.json",
    "reports/report_positive_claim_gate_quarantine_validation_report.json",
    "reports/model_artifact_claim_guard_validation_report.json",
    "reports/ddg_proxy_not_physics_claim_validation_report.json",
    "reports/human_decision_backlog_report.json",
    "reports/human_decision_backlog_fail_closed_consistency_validation_report.json",
    "reports/human_decision_reviewer_input_package_20260806.json",
    "reports/human_decision_pending_row_index_20260806.json",
    "reports/human_decision_review_batches_20260806.json",
    "reports/human_decision_review_batches_validation_report_20260806.json",
    "reports/human_decision_priority_queue_20260806.json",
    "reports/human_decision_batch_session_board_20260806.json",
    "reports/human_decision_batch_session_board_validation_report_20260806.json",
    "reports/human_decision_release_blocker_matrix_20260806.json",
    "reports/human_decision_next_closeout_package_20260806.json",
    "reports/human_decision_first_assignment_wave_20260806.json",
    "reports/human_decision_first_assignment_wave_validation_report_20260806.json",
    "reports/release_benchmark_stage25_fail_closed_summary_20260806.json",
    "reports/release_benchmark_human_decision_worklist_20260806.json",
    "reports/release_benchmark_human_decision_worklist_validation_report_20260806.json",
    "reports/stage25_overall_fail_closed_index_20260806.json",
    "reports/stage25_handoff_bundle_manifest_20260806.json",
    "reports/stage25_handoff_bundle_manifest_validation_20260806.json",
    "reports/stage25_blocker_activation_map_20260806.json",
    "reports/stage25_blocker_activation_map_validation_20260806.json",
    "reports/stage25_execute_blocker_detail_20260806.json",
    "reports/stage25_execute_blocker_detail_validation_20260806.json",
    "reports/stage25_execute_closeout_checklist_20260806.json",
    "reports/stage25_execute_closeout_checklist_validation_20260806.json",
    "reports/stage25_unblock_operator_packet_validation_20260806.json",
    "reports/stage25_user_authorization_receipt_validation_20260806.json",
    "reports/stage25_claim_release_consistency_validation_20260806.json",
    "reports/stage25_breakthrough_attempt_receipt_validation_20260806.json",
    "reports/stage25_foldx_benchmark_bridge_isolation_validation_20260806.json",
    "reports/stage25_benchmark_unblock_design_validation_20260806.json",
    "../../酶数据库/fulltext_intake_manifest_20260806.json",
    "../../酶数据库/fulltext_intake_validation_report_20260806.json",
    "../../酶数据库/fulltext_source_locator_review_queue_20260806.json",
    "../../酶数据库/fulltext_source_locator_review_queue_validation_report_20260806.json",
    "../../酶数据库/fulltext_evidence_draft_20260806.json",
    "../../酶数据库/stage25_reviewer_package_20260806.json",
    "../../酶数据库/stage25_approved_apply_report_20260806.json",
    "../../酶数据库/stage25_approved_apply_report_validation_20260806.json",
    "reports/next_operator_packet_validation_order_validation_report_20260806.json",
    "reports/next_unlock_blocker_matrix.json",
    "reports/next_unlock_remediation_queue.json",
    "datasets/governance/next_unlock_remediation_queue.jsonl",
    "reports/operator_review_status_report.json",
    "reports/governance_readiness_report.json",
    "reports/biosecurity_readiness_report.json",
    "reports/benchmark_matrix_report.json",
    "reports/benchmark_acquisition_plan_report.json",
    "reports/benchmark_score_cache_manifest.json",
    "reports/benchmark_score_cache_validation_report.json",
    "reports/benchmark_coverage_dashboard.json",
    "reports/benchmark_coverage_dashboard_validation_report.json",
    "reports/kwb_activity_risk_smoke_benchmark_report.json",
    "reports/kwb_activity_risk_smoke_benchmark_validation_report.json",
    "reports/proteingym_benchmark_scorecard_report.json",
    "reports/flip2_amylase_benchmark_report.json",
    "reports/flip2_amylase_benchmark_validation_report.json",
    "reports/atom3d_msp_benchmark_report.json",
    "reports/atom3d_msp_benchmark_validation_report.json",
    "reports/casf_affinity_benchmark_report.json",
    "reports/casf_affinity_benchmark_validation_report.json",
    "reports/catpred_gotenzymes_reference_benchmark_report.json",
    "reports/catpred_gotenzymes_reference_benchmark_validation_report.json",
    "reports/posebusters_pose_plausibility_benchmark_report.json",
    "reports/posebusters_pose_plausibility_benchmark_validation_report.json",
    "reports/five_head_benchmark_gap_plan_report.json",
    "reports/five_head_benchmark_gap_plan.md",
    "datasets/governance/benchmark_readiness_packets.jsonl",
    "reports/benchmark_readiness_packet_report.json",
    "reports/benchmark_readiness_packets.md",
    "reports/benchmark_hard_gate_operator_packets.md",
    "reports/hard_gate_decision_benchmark_bridge_report.json",
    "reports/hard_gate_decision_benchmark_bridge_validation_report.json",
    "reports/benchmark_readiness_packet_validation_report.json",
    "reports/parallel_hard_gate_workstreams_board_report.json",
    "reports/parallel_hard_gate_workstreams_board_validation_report.json",
    "datasets/governance/parallel_hard_gate_workstreams_board.jsonl",
    "reports/ddg_physical_runtime_receipt_preflight_report.json",
    "reports/ddg_physical_runtime_receipt_preflight_validation_report.json",
    "datasets/governance/ddg_physical_runtime_receipt_preflight.jsonl",
    "reports/five_head_training_threshold_report.json",
    "reports/five_head_training_threshold_validation_report.json",
    "reports/master_readiness_board.json",
    "datasets/governance/external_license_review_decisions.jsonl",
    "datasets/governance/external_license_review_decisions.template.jsonl",
    "datasets/governance/external_license_review_missing_checklist.jsonl",
    "reports/external_license_review_missing_checklist_report.json",
    "reports/external_license_review_missing_checklist_validation_report.json",
    "datasets/curation/sequence_ip_review_packets/sequence_ip_review_internal_labels_001.jsonl",
    "reports/sequence_ip_review_packet_report.json",
    "reports/sequence_ip_review_packet_validation_report.json",
    "datasets/governance/biosecurity_screening_drafts.jsonl",
    "reports/biosecurity_screening_draft_report.json",
    "reports/biosecurity_screening_draft_validation_report.json",
    "datasets/governance/human_review_launch_board.jsonl",
    "reports/human_review_launch_board_report.json",
    "reports/human_review_launch_board_validation_report.json",
    "datasets/governance/human_review_closeout_board.jsonl",
    "reports/human_review_closeout_board_report.json",
    "reports/human_review_closeout_board_validation_report.json",
    "reports/human_review_release_consistency_validation_report.json",
    "datasets/governance/biosecurity_screening_decisions.jsonl",
    "datasets/governance/biosecurity_screening_decisions.template.jsonl",
    "datasets/governance/sequence_ip_fto_decisions.jsonl",
    "datasets/governance/sequence_ip_fto_decisions.template.jsonl",
    "datasets/governance/workstream_acceptance_decisions.jsonl",
    "datasets/governance/workstream_acceptance_decisions.template.jsonl",
    "datasets/governance/operator_review_action_decisions.jsonl",
    "datasets/governance/operator_review_action_decisions.template.jsonl",
    "reports/customer_delivery_readiness_report.json",
    "reports/operator_review_action_queue_report.json",
    "reports/workstream_acceptance_gates.json",
    "reports/external_license_review_decision_validation_report.json",
    "reports/biosecurity_screening_decision_validation_report.json",
    "reports/sequence_ip_fto_decision_validation_report.json",
    "reports/workstream_acceptance_decision_validation_report.json",
    "reports/operator_review_action_decision_validation_report.json",
]

REQUIRED_SCRIPTS = [
    "scripts/build_data_lake_manifest.py",
    "scripts/build_local_release_manifest.py",
    "scripts/validate_operator_work_receipt_manifest_consistency.py",
    "scripts/validate_local_release_manifest_fail_closed_consistency.py",
    "scripts/validate_local_release_human_decision_control_plane_20260806.py",
    "scripts/build_claim_readiness_matrix.py",
    "scripts/validate_claim_readiness_matrix_fail_closed_policy.py",
    "scripts/validate_model_claim_fail_closed_consistency.py",
    "scripts/validate_model_artifact_claim_guard_report.py",
    "scripts/validate_local_release_guard_coverage.py",
    "scripts/validate_local_release_safety_guard_links.py",
    "scripts/validate_report_positive_claim_gate_quarantine.py",
    "scripts/validate_ddg_proxy_not_physics_claim.py",
    "scripts/build_human_decision_backlog.py",
    "scripts/validate_human_decision_backlog_fail_closed_consistency.py",
    "scripts/build_human_decision_reviewer_input_package_20260806.py",
    "scripts/build_human_decision_pending_row_index_20260806.py",
    "scripts/build_human_decision_review_batches_20260806.py",
    "scripts/validate_human_decision_review_batches_20260806.py",
    "scripts/build_human_decision_priority_queue_20260806.py",
    "scripts/build_human_decision_batch_session_board_20260806.py",
    "scripts/validate_human_decision_batch_session_board_20260806.py",
    "scripts/build_human_decision_release_blocker_matrix_20260806.py",
    "scripts/build_human_decision_next_closeout_package_20260806.py",
    "scripts/build_human_decision_first_assignment_wave_20260806.py",
    "scripts/validate_human_decision_first_assignment_wave_20260806.py",
    "scripts/validate_release_benchmark_human_decision_worklist_20260806.py",
    "scripts/build_stage25_execute_blocker_detail_20260806.py",
    "scripts/validate_stage25_execute_blocker_detail_20260806.py",
    "../../酶数据库/validate_fulltext_intake_20260806.py",
    "../../酶数据库/validate_fulltext_source_locator_review_queue_20260806.py",
    "../../酶数据库/extract_fulltext_evidence_draft_20260806.py",
    "../../酶数据库/build_stage25_reviewer_package_20260806.py",
    "../../酶数据库/run_stage25_approved_apply_20260806.py",
    "../../酶数据库/validate_stage25_approved_apply_report_20260806.py",
    "scripts/validate_next_operator_packet_validation_order_20260806.py",
    "scripts/build_next_unlock_blocker_matrix.py",
    "scripts/build_next_unlock_remediation_queue.py",
    "scripts/build_operator_review_status_report.py",
    "scripts/build_governance_readiness.py",
    "scripts/build_biosecurity_readiness.py",
    "scripts/build_benchmark_acquisition_plan.py",
    "scripts/build_benchmark_matrix_report.py",
    "scripts/build_benchmark_coverage_dashboard.py",
    "scripts/validate_benchmark_coverage_dashboard.py",
    "scripts/build_five_head_benchmark_gap_plan.py",
    "scripts/build_benchmark_readiness_packet.py",
    "scripts/validate_benchmark_readiness_packet.py",
    "scripts/build_benchmark_hard_gate_operator_packets.py",
    "scripts/build_hard_gate_review_packets.py",
    "scripts/validate_hard_gate_review_packets.py",
    "scripts/build_hard_gate_decision_benchmark_bridge.py",
    "scripts/validate_hard_gate_decision_benchmark_bridge.py",
    "scripts/build_parallel_hard_gate_workstreams_board.py",
    "scripts/validate_parallel_hard_gate_workstreams_board.py",
    "scripts/build_ddg_physical_runtime_receipt_preflight.py",
    "scripts/validate_ddg_physical_runtime_receipt_preflight.py",
    "scripts/build_five_head_training_threshold_report.py",
    "scripts/validate_five_head_training_threshold_report.py",
    "scripts/build_master_readiness_board.py",
    "scripts/build_proteingym_benchmark_scorecard.py",
    "scripts/build_flip2_amylase_benchmark.py",
    "scripts/validate_flip2_amylase_benchmark.py",
    "scripts/build_atom3d_msp_benchmark.py",
    "scripts/validate_atom3d_msp_benchmark.py",
    "scripts/build_casf_affinity_benchmark.py",
    "scripts/validate_casf_affinity_benchmark.py",
    "scripts/build_catpred_gotenzymes_reference_benchmark.py",
    "scripts/validate_catpred_gotenzymes_reference_benchmark.py",
    "scripts/build_posebusters_pose_plausibility_benchmark.py",
    "scripts/validate_posebusters_pose_plausibility_benchmark.py",
    "scripts/build_kwb_activity_risk_smoke_benchmark.py",
    "scripts/validate_kwb_activity_risk_smoke_benchmark.py",
    "scripts/validate_external_license_review_decisions.py",
    "scripts/build_external_license_review_missing_checklist.py",
    "scripts/validate_external_license_review_missing_checklist.py",
    "scripts/build_sequence_ip_review_packets.py",
    "scripts/validate_sequence_ip_review_packets.py",
    "scripts/build_biosecurity_screening_drafts.py",
    "scripts/validate_biosecurity_screening_drafts.py",
    "scripts/build_human_review_launch_board.py",
    "scripts/validate_human_review_launch_board.py",
    "scripts/build_human_review_closeout_board.py",
    "scripts/validate_human_review_closeout_board.py",
    "scripts/validate_human_review_release_consistency.py",
    "scripts/validate_biosecurity_screening_decisions.py",
    "scripts/validate_sequence_ip_fto_decisions.py",
    "scripts/validate_workstream_acceptance_decisions.py",
    "scripts/validate_operator_review_action_decisions.py",
    "scripts/build_customer_delivery_readiness.py",
    "scripts/build_benchmark_matrix_report.py",
]

REQUIRED_TERMS = [
    "local-only operator packet",
    "does not approve, reject, unlock, train, release, deliver, or change any model claim",
    "Do not copy template rows",
    "Do not treat self-attested authorization as verified customer-delivery clearance",
    "Do not mark customer delivery, release, or claim readiness true from this packet",
    "Only complete formal decisions with receipts may flow through the bridge",
]

REQUIRED_UPSTREAM_VALIDATION_REPORTS = {
    "reports/operator_work_receipt_manifest_consistency_validation_report.json": [
        "release_ready",
    ],
    "reports/local_release_manifest_fail_closed_consistency_validation_report.json": [
        "release_ready",
        "safe_for_model_claim",
    ],
    "reports/local_release_safety_guard_link_validation_report.json": [
        "release_ready",
        "safe_for_model_claim",
    ],
}

BENCHMARK_READINESS_VALIDATION_REPORT = "reports/benchmark_readiness_packet_validation_report.json"


def file_exists(rel_path: str) -> bool:
    return (AI_ROOT / rel_path).exists()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def check(name: str, passed: bool, observed: Any = None, expected: Any = None) -> dict[str, Any]:
    row: dict[str, Any] = {"name": name, "passed": bool(passed)}
    if observed is not None:
        row["observed"] = observed
    if expected is not None:
        row["expected"] = expected
    return row


def read_json_report(rel_path: str) -> dict[str, Any]:
    path = AI_ROOT / rel_path
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def failure_count(report: dict[str, Any]) -> int | None:
    failures = report.get("failures")
    if failures is None:
        return 0
    if isinstance(failures, list):
        return len(failures)
    if isinstance(failures, int):
        return failures
    return None


def upstream_report_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for rel_path, fail_closed_flags in REQUIRED_UPSTREAM_VALIDATION_REPORTS.items():
        report = read_json_report(rel_path)
        failures = failure_count(report)
        checks.extend([
            check(
                f"{rel_path} success true",
                report.get("success") is True,
                report.get("success"),
                True,
            ),
            check(
                f"{rel_path} failures empty or zero",
                failures == 0,
                failures,
                0,
            ),
        ])
        for flag_name in fail_closed_flags:
            observed = report.get(flag_name)
            checks.append(check(
                f"{rel_path} {flag_name} remains false",
                observed is False,
                observed,
                False,
            ))
    return checks


def local_release_manifest_checks() -> list[dict[str, Any]]:
    manifest = read_json_report("reports/local_release_manifest.json")
    readiness_summary = manifest.get("readiness_summary")
    if not isinstance(readiness_summary, dict):
        readiness_summary = {}
    return [
        check(
            "reports/local_release_manifest.json release_ready remains false",
            manifest.get("release_ready") is False,
            manifest.get("release_ready"),
            False,
        ),
        check(
            "reports/local_release_manifest.json readiness_summary.customer_delivery_ready remains false",
            readiness_summary.get("customer_delivery_ready") is False,
            readiness_summary.get("customer_delivery_ready"),
            False,
        ),
        check(
            "reports/local_release_manifest.json readiness_summary.operator_work_receipt_manifest_consistency_success true",
            readiness_summary.get("operator_work_receipt_manifest_consistency_success") is True,
            readiness_summary.get("operator_work_receipt_manifest_consistency_success"),
            True,
        ),
    ]


def benchmark_readiness_validation_checks() -> list[dict[str, Any]]:
    report = read_json_report(BENCHMARK_READINESS_VALIDATION_REPORT)
    failures = failure_count(report)
    return [
        check(
            f"{BENCHMARK_READINESS_VALIDATION_REPORT} contract valid",
            report.get("contract_valid") is True,
            report.get("contract_valid"),
            True,
        ),
        check(
            f"{BENCHMARK_READINESS_VALIDATION_REPORT} failure_count zero",
            report.get("failure_count") == 0,
            report.get("failure_count"),
            0,
        ),
        check(
            f"{BENCHMARK_READINESS_VALIDATION_REPORT} failures empty",
            failures == 0,
            failures,
            0,
        ),
        check(
            f"{BENCHMARK_READINESS_VALIDATION_REPORT} ready_for_model_claim remains false",
            report.get("ready_for_model_claim") is False,
            report.get("ready_for_model_claim"),
            False,
        ),
        check(
            f"{BENCHMARK_READINESS_VALIDATION_REPORT} release_ready remains false",
            report.get("release_ready") is False,
            report.get("release_ready"),
            False,
        ),
        check(
            f"{BENCHMARK_READINESS_VALIDATION_REPORT} safe_for_model_claim remains false",
            report.get("safe_for_model_claim") is False,
            report.get("safe_for_model_claim"),
            False,
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local next release operator decision packet")
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    packet_text = args.packet.read_text(encoding="utf-8") if args.packet.exists() else ""
    normalized_text = " ".join(packet_text.split())
    missing_paths = [path for path in REQUIRED_PATHS if not file_exists(path)]
    missing_scripts = [path for path in REQUIRED_SCRIPTS if not file_exists(path)]
    missing_terms = [term for term in REQUIRED_TERMS if term not in normalized_text]

    checks = [
        check("packet exists", args.packet.exists(), rel(args.packet), "existing markdown packet"),
        check("required local paths exist", not missing_paths, missing_paths, []),
        check("required scripts exist", not missing_scripts, missing_scripts, []),
        check("fail-closed policy terms are present", not missing_terms, missing_terms, []),
        check("packet does not contain readiness unlock", "release_ready=true" not in normalized_text and "customer_ready=true" not in normalized_text and "safe_for_model_claim=true" not in normalized_text, "no true readiness flags", "no true readiness flags"),
    ]
    checks.extend(upstream_report_checks())
    checks.extend(local_release_manifest_checks())
    checks.extend(benchmark_readiness_validation_checks())
    failures = [item for item in checks if not item["passed"]]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet": rel(args.packet),
        "success": not failures,
        "checks": checks,
        "failures": failures,
        "required_paths": REQUIRED_PATHS,
        "required_scripts": REQUIRED_SCRIPTS,
        "safe_for_model_claim": False,
        "customer_ready": False,
        "release_ready": False,
        "policy": "Validation only. This report does not create decisions, approve customer delivery, or authorize release.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "failures": len(failures),
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
