#!/usr/bin/env python3
"""Build an all-started board for the current P26-P31 pending backlog."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "p26_p31_pending_backlog_all_started_board.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "p26_p31_pending_backlog_all_started_actions.jsonl"


def load_json(rel: str) -> dict[str, Any]:
    path = AI_ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(rel: str) -> list[dict[str, Any]]:
    path = AI_ROOT / rel
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    human_backlog = load_json("reports/human_decision_backlog_fail_closed_consistency_validation_report.json")
    plate_backlog = load_json("reports/experiment_feedback_plate_intake_backlog_report.json")
    gap_report = load_json("reports/feature_coverage_gap_queue_report.json")
    gap_validation = load_json("reports/feature_coverage_gap_queue_validation_report.json")
    gap_rows = load_jsonl("datasets/features/feature_coverage_gap_queue.jsonl")
    five_head = load_json("reports/five_head_training_execution_contract_report.json")
    workstream = load_json("reports/workstream_acceptance_gates.json")
    local_release = load_json("reports/local_release_manifest.json")
    claim_matrix = load_json("reports/claim_readiness_matrix.json")

    plate_rows = int(plate_backlog.get("backlog_rows") or 0)
    human_missing = int(human_backlog.get("total_missing_rows") or 0)
    ready_head_count = int(five_head.get("ready_head_count") or 0)

    actions = [
        action("P26", "P26-B001", "numbering formal reviewed decisions", "started_blocked_human_review", "formal reviewed numbering decisions remain insufficient", {"human_backlog_total_missing_rows": human_missing}, "continue review packets; do not auto-write formal decisions", True),
        action("P26", "P26-B002", "unreviewed structure chain rows", "started_blocked_human_review", "unreviewed chain mappings cannot be promoted", {"human_backlog_total_missing_rows": human_missing}, "keep chain review queue open until reviewed rows exist", True),
        action("P26", "P26-B003", "plate backlog formal intake", "started_blocked_human_review", "plate rows lack formal intake approval", {"plate_backlog_rows": plate_rows, "ready_for_feedback_intake_rows": plate_backlog.get("ready_for_feedback_intake_rows")}, "continue plate intake review through formal schema", True),
        action("P26", "P26-B004", "human backlog total gap", "started_blocked_human_review", "human decision backlog remains open", {"human_backlog_total_missing_rows": human_missing, "human_backlog_open_items": human_backlog.get("open_items")}, "keep human gates visible and fail-closed", True),
    ]

    for idx, gap in enumerate(gap_rows, start=1):
        actions.append(action(
            "P27",
            f"P27-GAP-{idx:03d}",
            f"{gap.get('head')} input feature coverage gap for {gap.get('protein_group_id')}",
            "started_gap_remediation_queued",
            "input feature coverage gap is queued but does not authorize labels or training",
            {
                "gap_id": gap.get("gap_id"),
                "head": gap.get("head"),
                "protein_group_id": gap.get("protein_group_id"),
                "missing_input_feature_families": gap.get("missing_input_feature_families"),
                "gap_validation_success": gap_validation.get("success"),
            },
            "refresh input-feature evidence only; do not create labels",
            False,
        ))

    actions.extend([
        action("P28", "P28-B001", "numeric wet-lab authorization fields", "started_blocked_human_authorization", "numeric candidates require authorization/QC/reviewer/date/basis", {"human_backlog_total_missing_rows": human_missing}, "wait for explicit human authorization rows before preflight", True),
        action("P28", "P28-B002", "plate schema and formal intake", "started_blocked_human_review", "plate rows lack required schema fields and formal intake review", {"plate_backlog_rows": plate_rows}, "keep plate review workspace separate from local intake", True),
        action("P28", "P28-B003", "16B/4G parent sequence intake", "started_blocked_external_source", "parent sequence intake remains unresolved", {"human_backlog_total_missing_rows": human_missing}, "wait for reviewed parent sequence/source/version evidence", True),
        action("P29", "P29-B001", "five-head training execution", "started_blocked_data_gate", "five-head execution contract is not trainable", {"training_execution_allowed": five_head.get("training_execution_allowed")}, "refresh contract only; do not train", False),
        action("P29", "P29-B002", "ready head count", "started_blocked_data_gate", "no head is ready for claimable training", {"ready_head_count": ready_head_count}, "keep per-head missing row counts visible", False),
        action("P29", "P29-B003", "training import", "started_blocked_training_import", "training import remains disabled by execution gates", {"safe_for_training_import": five_head.get("safe_for_training_import"), "training_execution_allowed": five_head.get("training_execution_allowed")}, "do not import labels without reviewed authorization and thresholds", True),
        action("P29", "P29-B004", "benchmark and model-claim gates", "started_blocked_model_claim", "benchmark/model-claim gates remain false", {"claims_blocked": claim_matrix.get("claims_blocked")}, "run only fail-closed validators and scaffolds", False),
        action("P30", "P30-B001", "workstream human acceptance", "started_blocked_human_acceptance", "human workstream acceptance is incomplete", {"accepted_streams": workstream.get("accepted_streams"), "total_streams": workstream.get("total_streams")}, "keep acceptance gates open-blocked", True),
        action("P30", "P30-B002", "customer/license/biosecurity/IP-FTO", "started_blocked_governance", "external delivery gates remain unresolved", {"human_backlog_total_missing_rows": human_missing}, "wait for formal governance decisions", True),
        action("P30", "P30-B003", "release package", "started_guarded_release", "release_ready remains false", {"release_ready": local_release.get("release_ready")}, "refresh local release evidence without marking release ready", False),
        action("P31", "P31-B001", "review preparation only", "review_preparation_started_no_production_execution", "production authorization is absent", {"explicit_production_authorization_present": False}, "prepare pre-sync checklist only", True),
        action("P31", "P31-B002", "production authorization", "started_blocked_production_authorization", "no user production authorization", {"production_execution_allowed": False}, "do not sync/deploy/restart", True),
        action("P31", "P31-B003", "sync deploy restart grey release", "started_blocked_production_execution", "production execution remains forbidden", {"release_ready": local_release.get("release_ready")}, "keep production actions disabled", True),
    ])

    report = {
        "created_at": created_at,
        "local_only": True,
        "stage_ids": ["P26", "P27", "P28", "P29", "P30", "P31"],
        "static_pending_action_count": 17,
        "p27_gap_action_count": len(gap_rows),
        "source_gap_count": gap_report.get("gap_count"),
        "source_gap_validation_success": gap_validation.get("success") is True,
        "action_count": len(actions),
        "started_action_count": sum(1 for row in actions if row["started"] is True),
        "requires_human_or_external_input_count": sum(1 for row in actions if row["requires_human_or_external_input"] is True),
        "actions": actions,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "All current P26-P31 pending backlog items are started locally only. This board authorizes no formal decisions, training import, model claim, production action, or release.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    JSONL_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSONL_OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in actions), encoding="utf-8")
    print(json.dumps({
        "action_count": report["action_count"],
        "started_action_count": report["started_action_count"],
        "p27_gap_action_count": report["p27_gap_action_count"],
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
