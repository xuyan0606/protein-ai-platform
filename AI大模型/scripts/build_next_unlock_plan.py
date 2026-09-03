#!/usr/bin/env python3
"""Build a staged fail-closed plan for the next KWB unlocks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_plan.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_actions.jsonl"
STRICT_ROW_THRESHOLD = 100


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def as_int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def rel(path: str | None) -> str | None:
    if not path:
        return None
    value = Path(path)
    try:
        return str(value.relative_to(AI_ROOT)) if value.is_absolute() else str(value)
    except ValueError:
        return str(value)


def backlog_lookup(backlog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("workstream")): item
        for item in backlog.get("items", [])
        if isinstance(item, dict) and item.get("workstream")
    }


def packet_ids(report: dict[str, Any], limit: int = 4) -> list[str]:
    return [
        str(packet.get("packet_id"))
        for packet in report.get("packet_reports", [])[:limit]
        if isinstance(packet, dict) and packet.get("packet_id")
    ]


def action(
    action_id: str,
    stage_id: str,
    workstream: str,
    priority: str,
    action_type: str,
    target_rows: int,
    source_artifact: str | None,
    decision_input: str | None,
    validator_report: str | None,
    acceptance_check: str,
    policy: str,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "stage_id": stage_id,
        "workstream": workstream,
        "priority": priority,
        "action_type": action_type,
        "target_rows": max(target_rows, 0),
        "source_artifact": source_artifact,
        "decision_input": decision_input,
        "validator_report": validator_report,
        "human_review_required": True,
        "acceptance_check": acceptance_check,
        "policy": policy,
    }


def stage(
    order: int,
    stage_id: str,
    phase: str,
    title: str,
    depends_on: list[str],
    unlock_ready_now: bool,
    current_state: dict[str, Any],
    blockers: list[str],
    actions: list[dict[str, Any]],
    exit_conditions: list[str],
    evidence_reports: list[str],
    policy: str,
) -> dict[str, Any]:
    return {
        "order": order,
        "stage_id": stage_id,
        "phase": phase,
        "title": title,
        "depends_on": depends_on,
        "unlock_ready_now": bool(unlock_ready_now),
        "status": "ready_to_verify" if unlock_ready_now else "blocked",
        "current_state": current_state,
        "blockers": blockers,
        "actions": actions,
        "exit_conditions": exit_conditions,
        "evidence_reports": evidence_reports,
        "policy": policy,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next unlock plan")
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    backlog = load_json(AI_ROOT / "reports" / "human_decision_backlog_report.json")
    claims = load_json(AI_ROOT / "reports" / "claim_readiness_matrix.json")
    master = load_json(AI_ROOT / "reports" / "master_readiness_board.json")
    safe_entry = load_json(AI_ROOT / "reports" / "safe_training_entrypoint_check.json")
    repaired = load_json(AI_ROOT / "reports" / "repaired_supervised_table_report.json")
    multitask = load_json(AI_ROOT / "reports" / "multitask_training_readiness_report.json")
    structure_validation = load_json(AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json")
    structure_apply = load_json(AI_ROOT / "reports" / "structure_chain_mapping_apply_report.json")
    structure_packets = load_json(AI_ROOT / "reports" / "structure_chain_review_packet_report.json")
    domain_apply = load_json(AI_ROOT / "reports" / "domain_interval_apply_report.json")
    domain_packets = load_json(AI_ROOT / "reports" / "domain_interpro_review_packet_report.json")
    msa_runtime = load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json")
    msa_cache_validation = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
    feedback_validation = load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json")
    feedback_plate_validation = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
    feedback_sources = load_json(AI_ROOT / "reports" / "experiment_feedback_source_review_packet_report.json")
    feedback_plate_packets = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_review_packet_report.json")
    license_validation = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    biosecurity_validation = load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json")
    ip_validation = load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json")
    workstream_validation = load_json(AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json")
    operator_validation = load_json(AI_ROOT / "reports" / "operator_review_action_decision_validation_report.json")
    governance = load_json(AI_ROOT / "reports" / "governance_readiness_report.json")
    customer = load_json(AI_ROOT / "reports" / "customer_delivery_readiness_report.json")
    release = load_json(AI_ROOT / "reports" / "local_release_manifest.json")
    benchmark = load_json(AI_ROOT / "reports" / "benchmark_matrix_report.json")

    backlog_items = backlog_lookup(backlog)
    strict_rows = as_int(repaired.get("supervised_rows") or safe_entry.get("rows"))
    strict_missing = max(STRICT_ROW_THRESHOLD - strict_rows, 0)
    numbering = backlog_items.get("numbering_curation", {})
    structure = backlog_items.get("structure_chain_mapping", {})
    domain = backlog_items.get("domain_interval_occurrence_selection", {})
    feedback_source = backlog_items.get("experiment_feedback_source_review", {})
    plate_feedback = backlog_items.get("plate_feedback_intake", {})
    license_item = backlog_items.get("external_license_review", {})
    biosecurity_item = backlog_items.get("biosecurity_screening", {})
    ip_item = backlog_items.get("sequence_ip_fto", {})
    workstream_item = backlog_items.get("workstream_acceptance", {})
    operator_item = backlog_items.get("operator_review_actions", {})

    all_actions: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []

    stage_actions = [
        action(
            "P43-A001",
            "unlock_training_threshold",
            "numbering_curation",
            "P0",
            "review_numbering_decisions",
            min(strict_missing, as_int(numbering.get("missing_rows"))),
            "datasets/curation/numbering_review_packets/",
            "datasets/curation/numbering_curation_decisions.jsonl",
            "reports/numbering_curation_validation_report.json",
            "strict supervised rows >= 100 and safe entrypoint has no failures",
            "Do not promote weak evidence without reviewed canonical/isoform/literature mapping decisions.",
        )
    ]
    all_actions.extend(stage_actions)
    stages.append(stage(
        1,
        "unlock_training_threshold",
        "P26/P29",
        "Reach the strict supervised-row threshold",
        [],
        strict_missing == 0 and safe_entry.get("safe_for_training_pipeline") is True,
        {
            "strict_rows": strict_rows,
            "threshold": STRICT_ROW_THRESHOLD,
            "additional_strict_rows_needed": strict_missing,
            "numbering_missing_rows": numbering.get("missing_rows"),
            "first_packet_ids": packet_ids(load_json(AI_ROOT / "reports" / "numbering_review_packet_report.json")),
        },
        [] if strict_missing == 0 else [
            f"strict supervised rows are {strict_rows}/{STRICT_ROW_THRESHOLD}",
            f"numbering curation still has {numbering.get('missing_rows')} missing reviewed rows",
        ],
        stage_actions,
        [
            "append reviewed numbering decisions only after source evidence is checked",
            "rerun safe pipeline",
            "safe_training_entrypoint_check.rows >= 100",
        ],
        [
            "reports/repaired_supervised_table_report.json",
            "reports/safe_training_entrypoint_check.json",
            "reports/numbering_curation_validation_report.json",
        ],
        "This stage unlocks only the row-count gate; model-quality claims still require heads, benchmarks, and governance.",
    ))

    structure_missing = as_int(structure.get("missing_rows"))
    stage_actions = [
        action(
            "P43-A002",
            "unlock_coordinate_features",
            "structure_chain_mapping",
            "P0",
            "review_chain_mapping_decisions",
            min(25, structure_missing),
            "datasets/curation/structure_chain_review_packets/",
            "datasets/curation/structure_chain_mapping_decisions.jsonl",
            "reports/structure_chain_mapping_decision_validation_report.json",
            "reviewed_chain_mapping_rows increases and invalid_rows remains 0",
            "Parsed coordinate files cannot support residue-level claims until chain and numbering mappings are reviewed.",
        )
    ]
    all_actions.extend(stage_actions)
    stages.append(stage(
        2,
        "unlock_coordinate_features",
        "P26/P27",
        "Expand reviewed structure chain mappings",
        [],
        structure_missing == 0 and as_int(structure_apply.get("usable_for_coordinate_features")) > 0,
        {
            "worklist_rows": structure_validation.get("worklist_rows"),
            "decision_rows": structure_validation.get("decision_rows"),
            "valid_rows": structure_validation.get("valid_rows"),
            "reviewed_chain_mapping_rows": structure_validation.get("reviewed_chain_mapping_rows"),
            "usable_for_coordinate_features": structure_apply.get("usable_for_coordinate_features"),
            "missing_rows": structure_missing,
            "first_packet_ids": packet_ids(structure_packets),
        },
        [] if structure_missing == 0 else [f"structure chain mapping still has {structure_missing} missing reviewed rows"],
        stage_actions,
        [
            "append reviewed chain mapping decisions with confidence >= 0.7",
            "rerun validation and apply scripts",
            "usable coordinate mapping rows increase without invalid decisions",
        ],
        [
            "reports/structure_chain_mapping_decision_validation_report.json",
            "reports/structure_chain_mapping_apply_report.json",
            "reports/structure_chain_review_packet_report.json",
        ],
        "This stage prepares coordinate features; it does not approve model-quality or customer-facing structural conclusions.",
    ))

    domain_missing = as_int(domain.get("missing_rows"))
    stage_actions = [
        action(
            "P43-A003",
            "complete_domain_tail",
            "domain_interval_occurrence_selection",
            "P1",
            "review_domain_occurrence_selection",
            min(75, domain_missing),
            "datasets/curation/domain_interpro_review_packets/",
            "datasets/curation/domain_interval_decisions.jsonl",
            "reports/domain_interval_decision_validation_report.json",
            "unresolved domain rows decrease and usable_for_position_features stays valid",
            "Multi-interval domain evidence needs occurrence selection; do not collapse it automatically.",
        )
    ]
    all_actions.extend(stage_actions)
    stages.append(stage(
        3,
        "complete_domain_tail",
        "P27",
        "Finish unresolved domain occurrence selection",
        [],
        domain_missing == 0,
        {
            "queue_rows": domain_apply.get("queue_rows"),
            "usable_for_position_features": domain_apply.get("usable_for_position_features"),
            "unresolved_rows": domain_packets.get("unresolved_rows"),
            "missing_rows": domain_missing,
            "unresolved_bucket_counts": domain_packets.get("unresolved_bucket_counts"),
            "first_packet_ids": packet_ids(domain_packets),
        },
        [] if domain_missing == 0 else [f"domain occurrence selection still has {domain_missing} unresolved rows"],
        stage_actions,
        [
            "review multi-interval and no-exact Pfam packets",
            "rerun domain interval validation and apply",
            "domain tail missing_rows reaches 0 or explicitly reviewed unresolved rows are preserved",
        ],
        [
            "reports/domain_interpro_review_packet_report.json",
            "reports/domain_interval_decision_validation_report.json",
            "reports/domain_interval_apply_report.json",
        ],
        "Program-reviewed single-interval domain rows can be used locally; unresolved tails still need review.",
    ))

    msa_invalid = as_int(msa_cache_validation.get("invalid_rows"))
    stage_actions = [
        action(
            "P43-A004",
            "unlock_msa_conservation",
            "msa_conservation",
            "P0",
            "provide_msa_runtime_or_validated_cache",
            as_int(msa_cache_validation.get("target_rows_expected") or msa_runtime.get("target_rows")),
            "reports/msa_conservation_manifest.json",
            None,
            "reports/msa_conservation_cache_validation_report.json",
            "msa_runtime_readiness.runtime_ready is true or trusted cache validation ready is true",
            "Do not generate conservation features from single sequences or incomplete cache manifests.",
        )
    ]
    all_actions.extend(stage_actions)
    stages.append(stage(
        4,
        "unlock_msa_conservation",
        "P27",
        "Make MSA/conservation runtime or cache ready",
        ["unlock_training_threshold"],
        msa_runtime.get("runtime_ready") is True and msa_cache_validation.get("ready") is True,
        {
            "target_rows": msa_runtime.get("target_rows"),
            "runtime_ready": msa_runtime.get("runtime_ready"),
            "selected_runtime": msa_runtime.get("selected_runtime"),
            "cache_validation_ready": msa_cache_validation.get("ready"),
            "cache_valid_rows": msa_cache_validation.get("valid_rows"),
            "cache_invalid_rows": msa_invalid,
            "manifest_errors": msa_cache_validation.get("manifest_errors"),
        },
        list(msa_runtime.get("blockers") or []) + list(msa_cache_validation.get("manifest_errors") or []),
        stage_actions,
        [
            "configure local MMseqs2 plus homolog database, start a permitted Docker runtime, or provide trusted cache",
            "cache validation ready is true with checksums and source database metadata",
            "runtime readiness selects a non-null runtime",
        ],
        [
            "reports/msa_runtime_readiness_report.json",
            "reports/msa_conservation_cache_validation_report.json",
            "reports/msa_runtime_command_report.json",
        ],
        "Runtime readiness reads validator results; file counts alone are not sufficient.",
    ))

    feedback_missing = as_int(feedback_source.get("missing_rows"))
    plate_missing = as_int(plate_feedback.get("missing_rows"))
    stage_actions = [
        action(
            "P43-A005",
            "unlock_feedback_loop",
            "experiment_feedback_source_review",
            "P0",
            "transcribe_reviewed_feedback_sources",
            min(25, feedback_missing),
            "datasets/feedback/source_review_packets/",
            "datasets/feedback/experiment_feedback.local.jsonl",
            "reports/experiment_feedback_intake_validation_report.json",
            "training_eligible_rows > 0 with numbering-verified feedback rows",
            "Source review packets are not labels; only schema-valid local feedback rows can enter training.",
        ),
        action(
            "P43-A006",
            "unlock_feedback_loop",
            "plate_feedback_intake",
            "P0",
            "transcribe_plate_feedback_rows",
            min(50, plate_missing),
            rel(feedback_plate_packets.get("packet_file")),
            rel(feedback_plate_validation.get("input")),
            "reports/experiment_feedback_plate_intake_validation_report.json",
            "plate training_eligible_rows > 0 with QC-classified wells",
            "Plate drafts require manual extraction and QC classification before intake.",
        ),
    ]
    all_actions.extend(stage_actions)
    stages.append(stage(
        5,
        "unlock_feedback_loop",
        "P28/P29",
        "Create verified experiment feedback intake",
        ["unlock_training_threshold"],
        as_int(feedback_validation.get("training_eligible_rows")) > 0 and as_int(feedback_plate_validation.get("training_eligible_rows")) > 0,
        {
            "source_packet_rows": feedback_sources.get("packet_rows"),
            "feedback_input_rows": feedback_validation.get("input_rows"),
            "feedback_training_eligible_rows": feedback_validation.get("training_eligible_rows"),
            "plate_packet_rows": feedback_plate_packets.get("plate_review_packet_rows"),
            "plate_input_rows": feedback_plate_validation.get("input_rows"),
            "plate_training_eligible_rows": feedback_plate_validation.get("training_eligible_rows"),
        },
        [
            "experiment feedback intake has 0 eligible rows",
            "plate feedback intake has 0 eligible rows",
        ],
        stage_actions,
        [
            "review source packets and transcribe real KWB wet-lab rows",
            "validate sample IDs, units, conditions, batches, replicates, and QC flags",
            "feedback and plate validators report training_eligible_rows > 0",
        ],
        [
            "reports/experiment_feedback_source_review_packet_report.json",
            "reports/experiment_feedback_intake_validation_report.json",
            "reports/experiment_feedback_plate_intake_validation_report.json",
        ],
        "Feedback rows remain blocked until they are schema-valid, numbering-verified, and QC-classified.",
    ))

    stage_actions = [
        action(
            "P43-A007",
            "unlock_governance_delivery",
            "external_license_review",
            "P0",
            "record_license_decisions",
            as_int(license_item.get("missing_rows")),
            "datasets/governance/external_license_review_packets.jsonl",
            "datasets/governance/external_license_review_decisions.jsonl",
            "reports/external_license_review_decision_validation_report.json",
            "license validator ready for customer delivery",
            "License packets do not grant training, evaluation, or delivery use.",
        ),
        action(
            "P43-A008",
            "unlock_governance_delivery",
            "biosecurity_screening",
            "P0",
            "record_biosecurity_decisions",
            as_int(biosecurity_item.get("missing_rows")),
            "datasets/governance/biosecurity_screening_drafts.jsonl",
            "datasets/governance/biosecurity_screening_decisions.jsonl",
            "reports/biosecurity_screening_decision_validation_report.json",
            "biosecurity validator ready_for_ordering is true",
            "No order-ready output is permitted without explicit screening decisions.",
        ),
        action(
            "P43-A009",
            "unlock_governance_delivery",
            "sequence_ip_fto",
            "P0",
            "record_ip_fto_decisions",
            as_int(ip_item.get("missing_rows")),
            "datasets/curation/sequence_ip_review_packets/",
            "datasets/governance/sequence_ip_fto_decisions.jsonl",
            "reports/sequence_ip_fto_decision_validation_report.json",
            "IP/FTO validator ready_for_customer_delivery is true",
            "The system can prepare packets but cannot issue legal FTO conclusions.",
        ),
        action(
            "P43-A010",
            "unlock_governance_delivery",
            "workstream_acceptance",
            "P1",
            "record_workstream_acceptance",
            as_int(workstream_item.get("missing_rows")),
            "reports/workstream_acceptance_gates.json",
            "datasets/governance/workstream_acceptance_decisions.jsonl",
            "reports/workstream_acceptance_decision_validation_report.json",
            "all workstreams human accepted",
            "Technical readiness alone is not human acceptance.",
        ),
        action(
            "P43-A011",
            "unlock_governance_delivery",
            "operator_review_actions",
            "P1",
            "record_operator_action_completion",
            as_int(operator_item.get("missing_rows")),
            "datasets/governance/operator_review_action_queue.jsonl",
            "datasets/governance/operator_review_action_decisions.jsonl",
            "reports/operator_review_action_decision_validation_report.json",
            "all operator actions completed with evidence",
            "The action queue is not completion evidence.",
        ),
    ]
    all_actions.extend(stage_actions)
    stages.append(stage(
        6,
        "unlock_governance_delivery",
        "P30",
        "Complete governance, delivery, and operator decisions",
        ["unlock_feedback_loop", "unlock_msa_conservation"],
        governance.get("ready") is True and customer.get("ready") is True,
        {
            "governance_ready": governance.get("ready"),
            "customer_delivery_ready": customer.get("ready"),
            "license_decision_rows": license_validation.get("decision_rows"),
            "biosecurity_decision_rows": biosecurity_validation.get("decision_rows"),
            "ip_fto_decision_rows": ip_validation.get("decision_rows"),
            "human_accepted_streams": workstream_validation.get("accepted_streams"),
            "completed_operator_actions": operator_validation.get("completed_rows"),
        },
        list(governance.get("blockers") or []) + list(customer.get("blockers") or []),
        stage_actions,
        [
            "license, biosecurity, IP/FTO, workstream acceptance, and operator action validators are ready",
            "customer delivery readiness is true",
            "local release remains explicitly local-only until all gates pass",
        ],
        [
            "reports/governance_readiness_report.json",
            "reports/customer_delivery_readiness_report.json",
            "reports/operator_review_status_report.json",
        ],
        "This stage can only record validated decisions; it cannot create legal, biosecurity, or operator approvals.",
    ))

    stage_actions = [
        action(
            "P43-A012",
            "unlock_model_claim",
            "model_claim",
            "P2",
            "rerun_claim_matrix_after_upstream_unlocks",
            as_int(claims.get("claims_blocked")),
            "reports/claim_readiness_matrix.json",
            None,
            "reports/claim_readiness_matrix.json",
            "blocked_claims reaches 0 for requested claim scope",
            "No model-quality, ordering, customer, or production-tool claim is allowed until every explicit validator chain is ready.",
        )
    ]
    all_actions.extend(stage_actions)
    stages.append(stage(
        7,
        "unlock_model_claim",
        "P29/P30",
        "Re-evaluate model-quality and release claims",
        [
            "unlock_training_threshold",
            "unlock_coordinate_features",
            "complete_domain_tail",
            "unlock_msa_conservation",
            "unlock_feedback_loop",
            "unlock_governance_delivery",
        ],
        claims.get("claims_blocked") == 0 and release.get("release_ready") is True,
        {
            "claims_allowed": claims.get("claims_allowed"),
            "claims_blocked": claims.get("claims_blocked"),
            "blocked_claim_ids": claims.get("blocked_claim_ids"),
            "multitask_status": multitask.get("status"),
            "missing_head_labels": multitask.get("missing_head_labels"),
            "benchmark_ready_for_model_claim": benchmark.get("ready_for_model_claim"),
            "master_overall_status": master.get("overall_status"),
            "local_release_ready": release.get("release_ready"),
        },
        [f"blocked claims remain: {claims.get('blocked_claim_ids')}"] if claims.get("claims_blocked") else [],
        stage_actions,
        [
            "five-head readiness and benchmark matrix pass",
            "claim matrix has no blocked claim in the requested release scope",
            "local_release_manifest.release_ready is true",
        ],
        [
            "reports/claim_readiness_matrix.json",
            "reports/multitask_training_readiness_report.json",
            "reports/benchmark_matrix_report.json",
            "reports/local_release_manifest.json",
        ],
        "This final stage only re-checks claims after upstream validators pass; it does not override blocked claims.",
    ))

    write_jsonl(args.jsonl, all_actions)
    blocked_stages = [item for item in stages if not item["unlock_ready_now"]]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "planning_artifact_ready": True,
        "capability_unlocks_ready": len(stages) - len(blocked_stages),
        "blocked_unlocks": len(blocked_stages),
        "action_rows": len(all_actions),
        "jsonl": str(args.jsonl),
        "source_reports": [
            "reports/human_decision_backlog_report.json",
            "reports/claim_readiness_matrix.json",
            "reports/master_readiness_board.json",
            "reports/safe_training_entrypoint_check.json",
            "reports/msa_runtime_readiness_report.json",
            "reports/msa_conservation_cache_validation_report.json",
        ],
        "summary": {
            "strict_rows": strict_rows,
            "strict_row_threshold": STRICT_ROW_THRESHOLD,
            "strict_rows_needed": strict_missing,
            "human_backlog_open_items": backlog.get("open_items"),
            "human_backlog_missing_rows": backlog.get("total_missing_rows"),
            "claims_allowed": claims.get("claims_allowed"),
            "claims_blocked": claims.get("claims_blocked"),
            "master_overall_status": master.get("overall_status"),
            "msa_runtime_ready": msa_runtime.get("runtime_ready"),
            "msa_cache_validation_ready": msa_cache_validation.get("ready"),
        },
        "stages": stages,
        "policy": "This plan orders local work and validator checks only; it does not create reviewed decisions, approvals, downloads, deployments, or customer-ready claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "planning_artifact_ready": True,
        "blocked_unlocks": report["blocked_unlocks"],
        "action_rows": report["action_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
