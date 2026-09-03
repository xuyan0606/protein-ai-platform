#!/usr/bin/env python3
"""Build today's source-bound P0 closeout plan without opening any gate."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p641_p0_today_closeout_plan.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p641_p0_today_closeout_plan_report.json"
OUT_CHECKLIST = AI_ROOT / "reports" / "p0_today_closeout_operator_checklist.md"

SOURCES = {
    "human_decision_backlog": "reports/human_decision_backlog_report.json",
    "five_head_training": "reports/five_head_training_execution_contract_report.json",
    "model_quality": "reports/model_quality_hard_gate_contract_report.json",
    "claim_readiness": "reports/claim_readiness_matrix.json",
    "benchmark": "reports/benchmark_score_cache_validation_report.json",
    "ddg": "reports/ddg_backend_failure_diagnostic_report.json",
    "wet_lab": "reports/wet_lab_feedback_authorization_contract_report.json",
    "governance": "reports/governance_readiness_report.json",
    "biosecurity": "reports/biosecurity_readiness_report.json",
    "ip_fto": "reports/sequence_ip_fto_decision_validation_report.json",
    "safe_pipeline": "reports/safe_training_pipeline_run.json",
    "release": "reports/local_release_manifest.json",
}

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)


def load_json(relative_path: str) -> dict[str, Any]:
    path = AI_ROOT / relative_path
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def source_state(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    backlog = reports["human_decision_backlog"]
    training = reports["five_head_training"]
    model = reports["model_quality"]
    benchmark = reports["benchmark"]
    ddg = reports["ddg"]
    wet_lab = reports["wet_lab"]
    governance = reports["governance"]
    biosecurity = reports["biosecurity"]
    ip_fto = reports["ip_fto"]
    pipeline = reports["safe_pipeline"]
    release = reports["release"]
    return {
        "human_decision_total_missing_rows": backlog.get("total_missing_rows"),
        "human_decision_open_items": backlog.get("open_items"),
        "human_decision_ready_items": backlog.get("ready_items"),
        "ready_head_count": training.get("ready_head_count"),
        "total_head_training_rows": training.get("total_head_training_rows"),
        "training_execution_allowed": training.get("training_execution_allowed"),
        "training_import_eligible_rows": model.get("training_import_eligible_rows"),
        "wetlab_authorized_rows": model.get("wetlab_authorized_rows"),
        "wetlab_preflight_rows": model.get("wetlab_preflight_rows"),
        "wetlab_import_rows": model.get("wetlab_import_rows"),
        "physics_ddg_ready": ddg.get("physics_ddg_ready"),
        "physical_ddg_lane_capability_status": ddg.get("physical_ddg_lane_capability_status"),
        "benchmark_rows": benchmark.get("benchmark_rows"),
        "benchmark_valid_rows": benchmark.get("valid_rows"),
        "benchmark_invalid_rows": benchmark.get("invalid_rows"),
        "benchmark_heads_ready": benchmark.get("heads_ready"),
        "benchmark_ready_for_model_claim": benchmark.get("ready_for_model_claim"),
        "governance_ready": governance.get("ready"),
        "biosecurity_ready_for_ordering": biosecurity.get("ready_for_ordering"),
        "ip_fto_ready_for_customer_delivery": ip_fto.get("ready_for_customer_delivery"),
        "safe_pipeline_success": pipeline.get("success"),
        "safe_pipeline_steps_run": pipeline.get("steps_run"),
        "safe_pipeline_failed_steps": pipeline.get("failed_steps"),
        "local_release_ready": release.get("release_ready"),
        "local_release_artifact_count": release.get("artifact_count"),
    }


def item(
    item_id: str,
    priority: str,
    workstream: str,
    input_type: str,
    current: str,
    next_action: str,
    completion_condition: str,
    source_refs: list[str],
) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "plan_item_id": item_id,
        "priority": priority,
        "workstream": workstream,
        "input_type": input_type,
        "status": "blocked_awaiting_real_input",
        "current_state": current,
        "next_action": next_action,
        "completion_condition": completion_condition,
        "source_refs": source_refs,
        "requires_human_or_external_input": True,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": (
            "This is an execution plan and source-bound audit only. It does not create "
            "reviewed decisions, source approval, training labels, model claims, customer "
            "delivery, release approval, deployment, sync, restart, or production authorization."
        ),
    }


def main() -> int:
    reports = {name: load_json(path) for name, path in SOURCES.items()}
    state = source_state(reports)
    rows = [
        item(
            "P0-01",
            "P0",
            "numbering_curation",
            "human_decision",
            "471 numbering rows remain open; ready items are 0.",
            "Review the existing numbering packets and append only verified canonical, isoform, or literature mapping decisions.",
            "Each row has a validated reviewed decision, evidence reference, reviewer, and canonical WT check; no draft is counted.",
            ["reports/human_decision_backlog_report.json", "datasets/curation/numbering_curation_decisions.jsonl"],
        ),
        item(
            "P0-02",
            "P0",
            "structure_chain_mapping",
            "human_decision",
            "466 structure-chain rows remain open.",
            "Review chain packets with biological chain, numbering basis, UniProt match, and confidence.",
            "Reviewed chain decisions validate and produce only the permitted coordinate feature rows.",
            ["reports/human_decision_backlog_report.json", "datasets/curation/structure_chain_mapping_decisions.jsonl"],
        ),
        item(
            "P0-03",
            "P0",
            "experiment_feedback_source_review",
            "human_decision",
            "181 source-review rows remain open.",
            "Approve only genuine wet-lab or historical sources before schema transcription.",
            "Source-review decisions validate and only approved, numbered, QC-supported rows enter the next preflight.",
            ["reports/human_decision_backlog_report.json", "datasets/feedback/experiment_feedback_source_review_decisions.local.jsonl"],
        ),
        item(
            "P0-04",
            "P0",
            "plate_feedback_intake",
            "human_decision_and_qc",
            "56 plate-feedback rows remain open; formal intake remains 0.",
            "Review plate/well provenance, replicate and QC fields, then prepare the controlled intake.",
            "Every row has reviewed provenance, QC classification, replicate evidence, and passes intake validation.",
            ["reports/human_decision_backlog_report.json", "reports/experiment_feedback_plate_intake_validation_report.json"],
        ),
        item(
            "P0-05",
            "P0",
            "external_license_review",
            "legal_or_license_decision",
            "19 license decisions remain open; governance is not ready.",
            "Record explicit scope, redistribution, commercial-use, version, and reviewer decisions.",
            "All required license rows validate and the resulting scope is reflected in the release policy.",
            ["reports/human_decision_backlog_report.json", "reports/governance_readiness_report.json"],
        ),
        item(
            "P0-06",
            "P0",
            "biosecurity_screening",
            "human_decision",
            "Biosecurity decision validation is false; approved-for-ordering rows are 0.",
            "Record screening reference, use/customer scope, reviewer, and decision.",
            "The biosecurity validator reports ready-for-ordering only after explicit reviewed decisions.",
            ["reports/biosecurity_readiness_report.json", "datasets/governance/biosecurity_screening_decisions.jsonl"],
        ),
        item(
            "P0-07",
            "P0",
            "sequence_ip_fto",
            "human_decision",
            "IP/FTO decision rows are 0; customer-delivery approval rows are 0.",
            "Review prior-art evidence, jurisdictions, FTO conclusion, and delivery scope.",
            "All sequence candidates have validated IP/FTO decisions and delivery scope remains policy-compliant.",
            ["reports/sequence_ip_fto_decision_validation_report.json", "datasets/governance/sequence_ip_fto_decisions.jsonl"],
        ),
        item(
            "P0-08",
            "P0",
            "five_head_training",
            "real_training_data_and_qc",
            "ready_head_count=0; training execution is false; five heads lack minimum eligible data.",
            "Do not train yet. First close real label, replicate, group, benchmark, and feedback gates for every head.",
            "All five heads meet minimum real, receipted, QC-supported rows and the training contract explicitly allows execution.",
            ["reports/five_head_training_execution_contract_report.json", "reports/model_quality_hard_gate_contract_report.json"],
        ),
        item(
            "P0-09",
            "P0",
            "physics_ddg_runtime",
            "license_runtime_and_receipt",
            "Physical ddG lane is blocked; proxy ddG is not physics ddG.",
            "Complete only with approved runtime/license/config/input evidence and a fresh backend receipt; no new job is authorized by this plan.",
            "The physical ddG readiness report is true for the required lane and all expected artifacts validate.",
            ["reports/ddg_backend_failure_diagnostic_report.json", "reports/ddg_backend_readiness_report.json"],
        ),
        item(
            "P0-10",
            "P0",
            "benchmark_scorecard",
            "source_scorecard_and_review",
            "15 benchmark rows exist, 13 are valid, 2 are invalid, and model-claim readiness is false.",
            "Resolve the two invalid benchmark rows and complete the required head-level scorecards and review.",
            "The benchmark validator reports all required scorecards valid and claim readiness remains independently gated.",
            ["reports/benchmark_score_cache_validation_report.json", "reports/benchmark_coverage_dashboard_validation_report.json"],
        ),
        item(
            "P0-11",
            "P0",
            "claim_promotion_and_release",
            "human_decision_and_release_evidence",
            "Nine claim-promotion decisions are missing; local release remains false.",
            "Keep all claims blocked until evidence, governance, model quality, and release conditions are independently satisfied.",
            "Claim-promotion validator reports explicit reviewed decisions and local release validator reports ready only when every prerequisite passes.",
            ["reports/claim_readiness_matrix.json", "reports/claim_promotion_decision_validation_report.json", "reports/local_release_manifest.json"],
        ),
    ]
    plan_report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "plan_id": "P641",
        "plan_title": "P0 today closeout plan",
        "p0_local_closeout_package_ready": True,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "local_actions_completed_today": [
            "source-bound P0 blocker inventory",
            "operator action and completion-condition mapping",
            "fail-closed authorization boundary",
            "validator and safe-pipeline integration",
            "knowledge-base synchronization",
        ],
        "plan_rows": len(rows),
        "p0_rows": len(rows),
        "blocked_rows": len(rows),
        "requires_human_or_external_input_rows": sum(
            1 for row in rows if row["requires_human_or_external_input"]
        ),
        "source_state": state,
        "source_reports": SOURCES,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": (
            "P641 closes the local P0 planning and audit surface only. It cannot manufacture "
            "human decisions, external evidence, physical runtime receipts, training authorization, "
            "model claims, customer delivery, release approval, deployment, sync, restart, or production execution."
        ),
    }
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    OUT_REPORT.write_text(json.dumps(plan_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checklist = [
        "# P0 今日收口操作清单",
        "",
        "日期：2026-08-20",
        "",
        "结论：本地 P0 收口包已建立；P0 解锁、训练、模型声明、客户交付、release 和生产执行仍关闭。",
        "",
        "执行顺序：",
        "1. 先完成 P0-01/P0-02 编号与结构链人工审核。",
        "2. 再完成 P0-03/P0-04 反馈来源审核、QC 和正式 intake 前置。",
        "3. 并行处理 P0-05/P0-07 的 license、IP/FTO 和 P0-06 biosecurity 决策。",
        "4. 只有真实输入回填并通过 validator 后，才重新评估 P0-08/P0-10/P0-11。",
        "5. P0-09 物理 ddG 继续保持 fail-closed；proxy 不得当作 physics。",
        "",
        "禁止事项：",
        "- 不把 candidate、draft、receipt、ready-to-verify 或 validation success 当作 approval。",
        "- 不手写 reviewed decision、训练标签、正式 feedback intake 或 release/production 授权。",
        "- 不在缺少真实输入时运行新的 Rosetta/FoldX/PyRosetta 任务。",
        "",
        f"计划行数：{len(rows)}；当前全部 blocked；P0 解锁：false。",
    ]
    OUT_CHECKLIST.write_text("\n".join(checklist) + "\n", encoding="utf-8")
    print(json.dumps({
        "plan_id": "P641",
        "plan_rows": len(rows),
        "p0_local_closeout_package_ready": True,
        "p0_unblocked": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
