#!/usr/bin/env python3
"""Build a fail-closed start board for remaining P26-P31 work items."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "p26_p31_remaining_build_start_board.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "p26_p31_remaining_build_start_actions.jsonl"


def load_json(rel: str) -> dict[str, Any]:
    path = AI_ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def action(
    stage_id: str,
    action_id: str,
    title: str,
    status: str,
    blocker: str,
    source_state: dict[str, Any],
    next_action: str,
    requires_human_or_external_input: bool,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "action_id": action_id,
        "title": title,
        "started": True,
        "status": status,
        "blocker": blocker,
        "source_state": source_state,
        "next_action": next_action,
        "requires_human_or_external_input": requires_human_or_external_input,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
    }


def main() -> int:
    human_backlog = load_json("reports/human_decision_backlog_fail_closed_consistency_validation_report.json")
    plate_backlog = load_json("reports/experiment_feedback_plate_intake_backlog_report.json")
    structure_chain = load_json("reports/structure_chain_mapping_decision_validation_report.json")
    structure_graph = load_json("reports/reviewed_structure_graph_validation_report.json")
    feature_contract = load_json("reports/structure_feature_model_contract_report.json")
    feature_coverage = load_json("reports/feature_coverage_by_head_group_report.json")
    feature_coverage_validation = load_json("reports/feature_coverage_by_head_group_validation_report.json")
    five_head = load_json("reports/five_head_training_execution_contract_report.json")
    claim_promotion = load_json("reports/claim_promotion_decision_validation_report.json")
    local_release = load_json("reports/local_release_manifest.json")
    workstream = load_json("reports/workstream_acceptance_gates.json")

    plate_rows = int(plate_backlog.get("backlog_rows") or 0)
    human_missing = int(human_backlog.get("total_missing_rows") or 0)
    reviewed_chain_rows = int(
        structure_chain.get("valid_rows")
        or structure_chain.get("decision_rows")
        or structure_graph.get("valid_rows")
        or 0
    )
    ready_head_count = int(five_head.get("ready_head_count") or 0)

    actions = [
        action("P26", "P26-A001", "numbering formal reviewed decisions below threshold", "started_blocked_human_review", "formal reviewed numbering decisions remain insufficient", {"human_backlog_total_missing_rows": human_missing}, "continue numbering review packets without auto-writing formal decisions", True),
        action("P26", "P26-A002", "unreviewed structure chain rows remain", "started_blocked_human_review", "unreviewed chain mappings cannot enter reviewed graph features", {"reviewed_chain_rows": reviewed_chain_rows}, "keep chain mapping review queue open and source-bound", True),
        action("P26", "P26-A003", "plate backlog not formally intaken", "started_blocked_human_review", "plate rows lack formal intake approval", {"plate_backlog_rows": plate_rows, "ready_for_feedback_intake_rows": plate_backlog.get("ready_for_feedback_intake_rows")}, "review plate rows only through formal intake workflow", True),
        action("P26", "P26-A004", "human backlog total gap remains", "started_blocked_human_review", "human decision backlog remains open", {"human_backlog_total_missing_rows": human_missing, "human_backlog_open_items": human_backlog.get("open_items")}, "keep all human gates visible until reviewed decisions exist", True),
        action("P27", "P27-A001", "feature input-only boundary", "started_guarded", "features must not become labels", {"feature_contract_safe_for_model_claim": feature_contract.get("safe_for_model_claim")}, "refresh feature contracts after upstream source changes", False),
        action("P27", "P27-A002", "unreviewed coordinates and numbering excluded", "started_guarded", "unreviewed coordinates/numbering cannot enter training labels", {"reviewed_chain_rows": reviewed_chain_rows}, "continue excluding unreviewed feature rows from model-consumable labels", False),
        action("P27", "P27-A003", "feature coverage by head and protein group", "started_completion_ready_fail_closed_audit", "coverage audit is complete but does not unlock training or model claims", {"coverage_rows": feature_coverage.get("coverage_row_count"), "protein_group_count": feature_coverage.get("protein_group_count"), "validation_success": feature_coverage_validation.get("success"), "ready_head_count": ready_head_count}, "keep head/group feature coverage refreshed after upstream feature index changes", False),
        action("P28", "P28-A001", "numeric wet-lab authorization fields missing", "started_blocked_human_authorization", "12 numeric candidates require authorization/QC/reviewer/date/basis", {"human_backlog_total_missing_rows": human_missing}, "wait for explicit authorization rows before preflight", True),
        action("P28", "P28-A002", "plate schema and formal intake incomplete", "started_blocked_human_review", "plate rows lack required schema fields and formal intake review", {"plate_backlog_rows": plate_rows}, "keep plate review workspace separate from local intake", True),
        action("P28", "P28-A003", "16B/4G parent sequence intake incomplete", "started_blocked_external_source", "parent sequence intake remains unresolved", {"human_backlog_total_missing_rows": human_missing}, "wait for reviewed parent sequence/source/version evidence", True),
        action("P29", "P29-A001", "five-head training blocked", "started_blocked_data_gate", "five-head execution contract is not trainable", {"training_execution_allowed": five_head.get("training_execution_allowed")}, "refresh contract only; do not train", False),
        action("P29", "P29-A002", "ready head count remains zero", "started_blocked_data_gate", "no head is ready for claimable training", {"ready_head_count": ready_head_count}, "keep per-head missing row counts visible", False),
        action("P29", "P29-A003", "training import forbidden", "started_blocked_training_import", "training import remains disabled", {"training_import_allowed": False}, "do not import labels without reviewed authorization", True),
        action("P29", "P29-A004", "benchmark and model-claim gates closed", "started_blocked_model_claim", "benchmark/model-claim gates remain false", {"claim_promotion_ready": claim_promotion.get("ready_for_claim_promotion")}, "run only fail-closed validators and scaffolds", False),
        action("P30", "P30-A001", "workstream acceptance incomplete", "started_blocked_human_acceptance", "human workstream acceptance is incomplete", {"accepted_streams": workstream.get("accepted_streams"), "total_streams": workstream.get("total_streams")}, "keep acceptance gates open-blocked", True),
        action("P30", "P30-A002", "customer/license/biosecurity/IP-FTO blocked", "started_blocked_governance", "external delivery gates remain unresolved", {"human_backlog_total_missing_rows": human_missing}, "wait for formal governance decisions", True),
        action("P30", "P30-A003", "release package fail-closed", "started_guarded_release", "release_ready remains false", {"release_ready": local_release.get("release_ready")}, "refresh local release evidence without marking release ready", False),
        action("P31", "P31-A001", "review preparation only", "review_preparation_started_no_production_execution", "production authorization is absent", {"explicit_production_authorization_present": False}, "prepare pre-sync checklist only", True),
        action("P31", "P31-A002", "production authorization absent", "started_blocked_production_authorization", "no user production authorization", {"production_execution_allowed": False}, "do not sync/deploy/restart", True),
        action("P31", "P31-A003", "sync deploy restart grey release forbidden", "started_blocked_production_execution", "production execution remains forbidden", {"release_ready": local_release.get("release_ready")}, "keep production actions disabled", True),
    ]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "stage_ids": ["P26", "P27", "P28", "P29", "P30", "P31"],
        "action_count": len(actions),
        "started_action_count": sum(1 for row in actions if row["started"] is True),
        "requires_human_or_external_input_count": sum(1 for row in actions if row["requires_human_or_external_input"] is True),
        "actions": actions,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Remaining P26-P31 work items are started as local fail-closed workstreams only; this board authorizes no formal decisions, training import, model claim, production action, or release.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    JSONL_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSONL_OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in actions), encoding="utf-8")
    print(json.dumps({
        "action_count": report["action_count"],
        "started_action_count": report["started_action_count"],
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
