#!/usr/bin/env python3
"""Build a fail-closed claim readiness matrix for local review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from claim_readiness_policy_contract import CANONICAL_CLAIM_IDS, POLICY_VERSION


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "claim_readiness_matrix.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def report_exists(rel: str) -> bool:
    return (AI_ROOT / rel).exists()


def assertion_passed(report: dict[str, Any]) -> bool:
    assertions = report.get("assertions")
    if not isinstance(assertions, dict) or not assertions:
        return False
    return all(bool(value) for value in assertions.values())


def requirement(name: str, passed: bool, evidence: Any = None) -> dict[str, Any]:
    item = {"name": name, "passed": bool(passed)}
    if evidence is not None:
        item["evidence"] = evidence
    return item


def stream_current(board: dict[str, Any], stream: str) -> dict[str, Any]:
    for row in board.get("streams") or []:
        if isinstance(row, dict) and row.get("stream") == stream:
            current = row.get("current")
            return current if isinstance(current, dict) else {}
    return {}


def claim(
    claim_id: str,
    label: str,
    scope: str,
    requirements: list[dict[str, Any]],
    allowed_when_ready: bool = True,
    policy: str | None = None,
) -> dict[str, Any]:
    missing = [item["name"] for item in requirements if not item["passed"]]
    ready = not missing
    allowed = bool(ready and allowed_when_ready)
    row = {
        "claim_id": claim_id,
        "label": label,
        "scope": scope,
        "ready": ready,
        "allowed": allowed,
        "status": "allowed" if allowed else "blocked",
        "missing_requirements": missing,
        "requirements": requirements,
    }
    if policy:
        row["policy"] = policy
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Build claim readiness matrix")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    pipeline = load_json(AI_ROOT / "reports" / "safe_training_pipeline_run.json")
    safe_entry = load_json(AI_ROOT / "reports" / "safe_training_entrypoint_check.json")
    master = load_json(AI_ROOT / "reports" / "master_readiness_board.json")
    training = load_json(AI_ROOT / "reports" / "training_readiness_report.json")
    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    benchmark = load_json(AI_ROOT / "reports" / "benchmark_matrix_report.json")
    governance = load_json(AI_ROOT / "reports" / "governance_readiness_report.json")
    customer = load_json(AI_ROOT / "reports" / "customer_delivery_readiness_report.json")
    active_learning = load_json(AI_ROOT / "reports" / "active_learning_trial_readiness_report.json")
    biosecurity = load_json(AI_ROOT / "reports" / "biosecurity_readiness_report.json")
    biosecurity_decisions = load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json")
    ip_decisions = load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json")
    license_decisions = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    operator_status = load_json(AI_ROOT / "reports" / "operator_review_status_report.json")
    workstream_acceptance = load_json(AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json")
    release = load_json(AI_ROOT / "reports" / "local_release_manifest.json")
    foreign_tools = load_json(AI_ROOT / "reports" / "foreign_tool_readiness_report.json")
    local_adapter = load_json(AI_ROOT / "reports" / "local_tool_adapter_demo.json")
    workflow_gate = load_json(AI_ROOT / "reports" / "structure_workflow_gate_demo.json")
    provenance = load_json(AI_ROOT / "reports" / "provenance_graph_report.json")
    label_provenance = load_json(AI_ROOT / "reports" / "label_provenance_audit_report.json")
    plate_feedback = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
    enzyme_tool_contracts = load_json(AI_ROOT / "reports" / "enzyme_tool_contract_validation_report.json")
    model_claim_consistency = load_json(AI_ROOT / "reports" / "model_claim_fail_closed_consistency_report.json")

    strict_rows = (
        training.get("label_integrity", {}).get("strict_supervised_rows")
        or multitask.get("strict_rows")
        or safe_entry.get("rows")
        or 0
    )
    claim_eligible_rows = label_provenance.get("claim_eligible_rows", 0)
    all_heads_ready = bool(multitask.get("heads")) and all(
        bool(head.get("ready")) for head in multitask.get("heads", {}).values()
    )
    release_summary = release.get("readiness_summary") if isinstance(release.get("readiness_summary"), dict) else {}
    human_target_projection_keys = [
        "human_target_projection_gap_report_valid",
        "human_target_projection_runtime_manifest_valid",
        "human_target_projection_runtime_receipts_valid",
        "human_target_projection_blocked_source_index_valid",
        "human_target_projection_blocked_split_manifests_valid",
        "human_target_projection_unlock_checklist_valid",
        "human_target_projection_unlock_report_valid",
    ]
    human_target_projection_ready = all(release_summary.get(key) is True for key in human_target_projection_keys)
    human_target_fail_closed = (
        human_target_projection_ready
        and release_summary.get("human_target_source_runtime_ready_sources") == 0
        and release_summary.get("human_target_source_unlock_ready_rows") == 0
    )
    governance_release_current = stream_current(master, "governance_release")
    claim_promotion_contract_keys = [
        "claim_promotion_decision_validation_success",
        "claim_promotion_decision_validation_failures",
        "claim_promotion_template_rows",
        "claim_promotion_template_matches_expected_contract",
        "claim_promotion_target_claim_rows",
        "claim_promotion_required_evidence_artifact_count",
        "claim_promotion_required_evidence_artifacts",
        "claim_promotion_required_validation_report_count",
        "claim_promotion_required_validation_reports",
        "claim_promotion_decision_rows",
        "claim_promotion_approved_rows",
        "claim_promotion_missing_decisions",
        "claim_promotion_decision_success",
        "claim_promotion_validation_failures",
    ]
    claim_promotion_coverage_keys = [
        "claim_promotion_requirement_name",
        "claim_promotion_target_claim_rows_with_contract_requirement",
        "claim_promotion_target_claim_rows_with_contract_requirement_passed",
        "claim_promotion_target_claim_contract_requirement_complete",
        "claim_promotion_target_claim_rows_with_contract_requirement_evidence",
        "claim_promotion_target_claim_contract_requirement_evidence_complete",
    ]
    claim_promotion_release_evidence = {key: release_summary.get(key) for key in claim_promotion_contract_keys}
    claim_promotion_master_evidence = {key: governance_release_current.get(key) for key in claim_promotion_contract_keys}
    claim_promotion_release_coverage_evidence = {key: release_summary.get(key) for key in claim_promotion_coverage_keys}
    claim_promotion_master_coverage_evidence = {key: governance_release_current.get(key) for key in claim_promotion_coverage_keys}
    claim_promotion_required_reports = [
        "reports/claim_readiness_matrix.json",
        "reports/claim_readiness_matrix_fail_closed_policy_current_validation_report.json",
        "reports/claim_readiness_policy_anchor_validation_report.json",
        "reports/local_release_guard_coverage_validation_report.json",
        "reports/local_release_manifest.json",
        "reports/master_readiness_board_validation_report.json",
    ]
    claim_promotion_required_evidence_artifacts = [
        "reports/claim_readiness_matrix.json",
        "reports/local_release_manifest.json",
        "reports/master_readiness_board.json",
    ]
    claim_promotion_contract_ready = (
        claim_promotion_release_evidence == claim_promotion_master_evidence
        and release_summary.get("claim_promotion_decision_validation_success") is True
        and release_summary.get("claim_promotion_decision_validation_failures") == 0
        and release_summary.get("claim_promotion_template_rows") == 9
        and release_summary.get("claim_promotion_template_matches_expected_contract") is True
        and release_summary.get("claim_promotion_target_claim_rows") == 9
        and release_summary.get("claim_promotion_required_evidence_artifact_count") == 3
        and release_summary.get("claim_promotion_required_evidence_artifacts") == claim_promotion_required_evidence_artifacts
        and release_summary.get("claim_promotion_required_validation_report_count") == 6
        and release_summary.get("claim_promotion_required_validation_reports") == claim_promotion_required_reports
        and release_summary.get("claim_promotion_decision_rows") == 0
        and release_summary.get("claim_promotion_approved_rows") == 0
        and release_summary.get("claim_promotion_missing_decisions") == 9
        and release_summary.get("claim_promotion_decision_success") is False
        and release_summary.get("claim_promotion_validation_failures") == 0
    )
    claim_promotion_contract_evidence = {
        "release_summary": claim_promotion_release_evidence,
        "master_governance_release": claim_promotion_master_evidence,
        "release_requirement_coverage": claim_promotion_release_coverage_evidence,
        "master_requirement_coverage": claim_promotion_master_coverage_evidence,
    }

    claims = [
        claim(
            "local_safe_training_pipeline",
            "Local safe training pipeline can be run for internal engineering checks",
            "internal_engineering",
            [
                requirement("safe pipeline report exists", report_exists("reports/safe_training_pipeline_run.json")),
                requirement("safe entrypoint safe for pipeline", safe_entry.get("safe_for_training_pipeline") is True),
                requirement("enzyme tool contracts valid", enzyme_tool_contracts.get("success") is True),
                requirement("model claim fail-closed consistency passes", model_claim_consistency.get("success") is True),
            ],
            policy="This permits local validation only, not model-quality or customer claims.",
        ),
        claim(
            "internal_design_review_artifacts",
            "Design and review artifacts may be used internally",
            "internal_r_and_d",
            [
                requirement("local adapter assertions pass", assertion_passed(local_adapter)),
                requirement("structure workflow gate assertions pass", assertion_passed(workflow_gate)),
                requirement("customer delivery remains blocked", customer.get("ready") is False),
            ],
            policy="Internal artifacts remain review outputs and are not customer-ready sequence packages.",
        ),
        claim(
            "model_quality_claim",
            "KWB-EnzymeDesigner model quality claim",
            "model_claim",
            [
                requirement("safe_for_model_claim", safe_entry.get("safe_for_model_claim") is True, safe_entry.get("warnings")),
                requirement("strict supervised rows >= 100", strict_rows >= 100, strict_rows),
                requirement("claim-eligible real supervised rows >= 100", claim_eligible_rows >= 100, claim_eligible_rows),
                requirement("no synthetic or unreceipted strict labels", (label_provenance.get("synthetic_or_unreceipted_rows") or 0) == 0, label_provenance.get("provenance_flag_counts")),
                requirement("all five heads ready", all_heads_ready, multitask.get("missing_head_labels")),
                requirement("benchmark matrix ready", benchmark.get("ready_for_model_claim") is True),
                requirement("master board ready", master.get("overall_status") == "ready_for_model_claim", master.get("overall_status")),
                requirement("human-target projection coverage valid", human_target_projection_ready, {key: release_summary.get(key) for key in human_target_projection_keys}),
                requirement("claim-promotion evidence contract valid", claim_promotion_contract_ready, claim_promotion_contract_evidence),
            ],
        ),
        claim(
            "five_head_training_run",
            "Five-head supervised training run",
            "training",
            [
                requirement("strict supervised rows >= 100", strict_rows >= 100, strict_rows),
                requirement("claim-eligible real supervised rows >= 100", claim_eligible_rows >= 100, claim_eligible_rows),
                requirement("no synthetic or unreceipted strict labels", (label_provenance.get("synthetic_or_unreceipted_rows") or 0) == 0, label_provenance.get("provenance_flag_counts")),
                requirement("all five heads have eligible labels", all_heads_ready, multitask.get("heads")),
                requirement("safe entrypoint allows training pipeline", safe_entry.get("safe_for_training_pipeline") is True),
                requirement("claim-promotion evidence contract valid", claim_promotion_contract_ready, claim_promotion_contract_evidence),
            ],
        ),
        claim(
            "active_learning_experiment_submission",
            "Active-learning experiment submission",
            "experiment_submission",
            [
                requirement("active learning readiness ready", active_learning.get("ready") is True),
                requirement("experiment submission allowed", active_learning.get("experiment_submission_allowed") is True),
                requirement("plate feedback eligible rows present", (plate_feedback.get("training_eligible_rows") or 0) > 0),
                requirement("operator review status ready", operator_status.get("ready") is True),
                requirement("biosecurity ready for ordering", biosecurity.get("ready_for_ordering") is True),
                requirement("claim-promotion evidence contract valid", claim_promotion_contract_ready, claim_promotion_contract_evidence),
            ],
        ),
        claim(
            "customer_sequence_package",
            "Customer-ready sequence package",
            "customer_delivery",
            [
                requirement("customer delivery readiness ready", customer.get("ready") is True, customer.get("blockers")),
                requirement("governance ready", governance.get("ready") is True, governance.get("blockers")),
                requirement("workstreams human accepted", workstream_acceptance.get("all_streams_accepted") is True),
                requirement("operator review status ready", operator_status.get("ready") is True, operator_status.get("blockers")),
                requirement("local release ready", release.get("release_ready") is True),
                requirement("human-target source/runtime fail-closed coverage valid", human_target_fail_closed, {
                    "projection_ready": human_target_projection_ready,
                    "ready_sources": release_summary.get("human_target_source_runtime_ready_sources"),
                    "unlock_ready_rows": release_summary.get("human_target_source_unlock_ready_rows"),
                }),
                requirement("claim-promotion evidence contract valid", claim_promotion_contract_ready, claim_promotion_contract_evidence),
            ],
        ),
        claim(
            "approved_for_ordering",
            "Sequence or construct approved for ordering",
            "ordering",
            [
                requirement("biosecurity readiness ready", biosecurity.get("ready_for_ordering") is True),
                requirement("biosecurity decisions ready", biosecurity_decisions.get("ready_for_ordering") is True),
                requirement("IP/FTO ready for delivery", ip_decisions.get("ready_for_customer_delivery") is True),
                requirement("customer delivery ready", customer.get("ready") is True),
                requirement("claim-promotion evidence contract valid", claim_promotion_contract_ready, claim_promotion_contract_evidence),
            ],
        ),
        claim(
            "ip_fto_cleared",
            "IP/FTO cleared",
            "legal_review",
            [
                requirement("IP/FTO decisions ready for delivery", ip_decisions.get("ready_for_customer_delivery") is True),
                requirement(
                    "all packet candidates decided for delivery",
                    ip_decisions.get("all_packet_candidates_decided_for_delivery") is True,
                ),
                requirement("claim-promotion evidence contract valid", claim_promotion_contract_ready, claim_promotion_contract_evidence),
            ],
        ),
        claim(
            "biosecurity_screened",
            "Biosecurity screened",
            "biosecurity",
            [
                requirement("biosecurity decisions ready for ordering", biosecurity_decisions.get("ready_for_ordering") is True),
                requirement("biosecurity readiness ready for ordering", biosecurity.get("ready_for_ordering") is True),
                requirement("claim-promotion evidence contract valid", claim_promotion_contract_ready, claim_promotion_contract_evidence),
            ],
        ),
        claim(
            "external_tool_production_use",
            "External tool production use",
            "tooling",
            [
                requirement("tool license decisions ready for delivery", license_decisions.get("ready_for_customer_delivery") is True),
                requirement("at least one foreign tool ready locally", (foreign_tools.get("ready_for_local_evaluation") or 0) > 0),
                requirement("governance ready", governance.get("ready") is True),
                requirement("claim-promotion evidence contract valid", claim_promotion_contract_ready, claim_promotion_contract_evidence),
            ],
        ),
        claim(
            "local_release_review_package",
            "Local release review package",
            "release_review",
            [
                requirement("artifact manifest has no missing files", not release.get("missing_artifacts")),
                requirement("provenance ready", provenance.get("ready_for_release_traceability") is True),
                requirement("human-target projection coverage valid", human_target_projection_ready, {key: release_summary.get(key) for key in human_target_projection_keys}),
                requirement("claim-promotion evidence contract valid", claim_promotion_contract_ready, claim_promotion_contract_evidence),
                requirement("local release marked ready", release.get("release_ready") is True),
            ],
            policy="The current release manifest is an internal review package until all readiness gates pass.",
        ),
    ]

    allowed_claims = [item["claim_id"] for item in claims if item["allowed"]]
    blocked_claims = [item["claim_id"] for item in claims if not item["allowed"]]
    observed_claim_ids = {str(item.get("claim_id")) for item in claims}
    if observed_claim_ids != CANONICAL_CLAIM_IDS:
        raise RuntimeError(
            f"claim policy contract mismatch: observed={sorted(observed_claim_ids)} expected={sorted(CANONICAL_CLAIM_IDS)}"
        )
    report = {
        "policy_version": POLICY_VERSION,
        "local_only": True,
        "claims_allowed": len(allowed_claims),
        "claims_blocked": len(blocked_claims),
        "allowed_claim_ids": allowed_claims,
        "blocked_claim_ids": blocked_claims,
        "claims": claims,
        "global_policy": "Every customer, ordering, IP/FTO, biosecurity, model-quality, and production-tool claim fails closed unless its explicit validator chain is ready.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "claims_allowed": report["claims_allowed"],
        "claims_blocked": report["claims_blocked"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
