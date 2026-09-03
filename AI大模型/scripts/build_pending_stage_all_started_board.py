#!/usr/bin/env python3
"""Build a fail-closed board for starting all pending P26-P31 workstreams."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
TASK_PLAN = AI_ROOT / "task_plan.md"
OUT = AI_ROOT / "reports" / "pending_stage_all_started_board.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "pending_stage_all_started_actions.jsonl"


STAGES: list[dict[str, Any]] = [
    {
        "stage_id": "P26",
        "title": "真实数据解阻第一波",
        "lane": "real_data_unblock",
        "owner": "agent_019fb6e2_a2ed_P26",
        "start_mode": "delegated_agent_started",
        "allowed_now": [
            "inspect numbering, structure cache, and domain interval evidence",
            "build or refresh fail-closed reports and validators",
            "run local validators",
        ],
        "forbidden_now": [
            "write unreviewed formal numbering decisions",
            "promote draft decisions into training labels",
            "claim release readiness",
        ],
    },
    {
        "stage_id": "P27",
        "title": "序列/结构特征生产",
        "lane": "sequence_structure_feature_production",
        "owner": "main_thread_until_agent_slot_available",
        "start_mode": "main_thread_started_agent_queue_blocked_by_concurrency_limit",
        "allowed_now": [
            "refresh MSA/structure/domain/site feature contracts",
            "validate feature-index input-only boundaries",
            "exclude unreviewed coordinates from model-consumable indexes",
        ],
        "forbidden_now": [
            "treat features as labels",
            "open model-quality claims from feature availability alone",
            "release production artifacts",
        ],
    },
    {
        "stage_id": "P28",
        "title": "实验反馈闭环",
        "lane": "experiment_feedback_loop",
        "owner": "main_thread_until_agent_slot_available",
        "start_mode": "main_thread_started_agent_queue_blocked_by_concurrency_limit",
        "allowed_now": [
            "refresh wet-lab authorization worklists and preflight reports",
            "separate candidate rows from authorized training import rows",
            "validate feedback semantics fail-closed",
        ],
        "forbidden_now": [
            "invent human authorization",
            "append numeric candidates into training feedback without approval",
            "convert qualitative observations into numeric training labels",
        ],
    },
    {
        "stage_id": "P29",
        "title": "五头统一模型训练",
        "lane": "five_head_training",
        "owner": "main_thread_until_agent_slot_available",
        "start_mode": "main_thread_started_agent_queue_blocked_by_concurrency_limit",
        "allowed_now": [
            "refresh five-head training execution contract",
            "keep missing head rows visible",
            "run scaffold and baseline regressions",
        ],
        "forbidden_now": [
            "train a claimable top-tier model with zero eligible rows",
            "count feature-only rows as labels",
            "publish trained neural weight claims",
        ],
    },
    {
        "stage_id": "P30",
        "title": "本地平台验收",
        "lane": "local_platform_acceptance",
        "owner": "main_thread_until_agent_slot_available",
        "start_mode": "main_thread_started_agent_queue_blocked_by_concurrency_limit",
        "allowed_now": [
            "refresh local-only release and safety guard validations",
            "run local acceptance evidence checks",
            "keep unresolved blockers visible in the review package",
        ],
        "forbidden_now": [
            "mark release_ready true",
            "claim customer delivery readiness",
            "hide missing benchmark or human-decision blockers",
        ],
    },
    {
        "stage_id": "P31",
        "title": "生产接入评审",
        "lane": "production_integration_review_prep",
        "owner": "main_thread_only_until_explicit_production_authorization",
        "start_mode": "review_preparation_started_no_production_execution",
        "allowed_now": [
            "prepare pre-sync requirement checklist",
            "prepare rollback/smoke-test review material",
            "validate that production execution remains disabled",
        ],
        "forbidden_now": [
            "sync to production",
            "deploy or restart services",
            "run grey release actions",
        ],
    },
]


def task_plan_status(stage_id: str, text: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| {stage_id} "):
            parts = [part.strip() for part in line.strip("|").split("|")]
            if len(parts) >= 2:
                return parts[1]
    return "missing"


def main() -> int:
    plan_text = TASK_PLAN.read_text(encoding="utf-8") if TASK_PLAN.exists() else ""
    rows: list[dict[str, Any]] = []
    for stage in STAGES:
        status = task_plan_status(stage["stage_id"], plan_text)
        row = {
            **stage,
            "task_plan_status": status,
            "started": status == "in_progress" and stage["start_mode"] != "not_started",
            "requires_human_or_external_authorization": stage["stage_id"] in {"P28", "P31"},
            "training_import_allowed": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        }
        rows.append(row)

    failures: list[dict[str, Any]] = []
    for row in rows:
        if row["task_plan_status"] != "in_progress":
            failures.append({
                "stage_id": row["stage_id"],
                "check": "task_plan_status_in_progress",
                "observed": row["task_plan_status"],
                "expected": "in_progress",
            })
        if row["stage_id"] == "P31" and "no_production_execution" not in row["start_mode"]:
            failures.append({
                "stage_id": "P31",
                "check": "production_execution_forbidden",
                "observed": row["start_mode"],
                "expected": "review preparation only",
            })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "stage_count": len(rows),
        "started_stage_count": sum(1 for row in rows if row["started"]),
        "agent_delegated_stage_count": sum(1 for row in rows if row["start_mode"] == "delegated_agent_started"),
        "main_thread_started_stage_count": sum(1 for row in rows if row["start_mode"].startswith("main_thread_started")),
        "review_prep_stage_count": sum(1 for row in rows if row["start_mode"].startswith("review_preparation_started")),
        "rows": rows,
        "failures": failures,
        "success": not failures,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "P26-P31 are started as local fail-closed workstreams only. This board is not a human decision, training import, model-quality claim, production sync, or release approval.",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    JSONL_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSONL_OUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({
        "success": report["success"],
        "stage_count": report["stage_count"],
        "started_stage_count": report["started_stage_count"],
        "agent_delegated_stage_count": report["agent_delegated_stage_count"],
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
