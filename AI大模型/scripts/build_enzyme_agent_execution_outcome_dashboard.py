#!/usr/bin/env python3
"""Build a truthful outcome dashboard for receipted enzyme-agent executions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_outcome_dashboard.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "enzyme_agent_execution_outcome_dashboard_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def action_outcome(action_id: str, receipt_status: str | None, reports: dict[str, dict[str, Any]]) -> tuple[str, str, list[str], bool]:
    blockers: list[str] = []
    if action_id == "act_know_how_retrieval":
        return "engineering_evidence_ready", "read_only_know_how_retrieved", blockers, True
    if action_id == "act_numbering_review":
        numbering = reports["numbering_validation"]
        supervised_rows = count_jsonl(AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl")
        if numbering.get("valid_rows", 0) < 100 or supervised_rows < 100:
            blockers.extend(["reviewed_numbering_rows_below_100", "strict_real_supervised_rows_below_100"])
        return "hard_gate_still_blocked", "formal_numbering_validation_ran_but_insufficient_for_training_claim", blockers, False
    if action_id == "act_structure_chain_mapping":
        graph = reports["reviewed_structure_graph_validation"]
        if graph.get("ready_for_coordinate_feature_use") is True:
            return "partial_feature_gate_ready", "reviewed_structure_graph_feature_path_ready", blockers, True
        blockers.append("reviewed_structure_graph_not_ready")
        return "hard_gate_still_blocked", "structure_graph_validation_not_ready", blockers, False
    if action_id == "act_msa_conservation":
        msa = reports["msa_validation"]
        strict_msa_rows = count_jsonl(AI_ROOT / "datasets" / "curated" / "enzyme_mutation_strict_msa_site_features.jsonl")
        if msa.get("ready") is True and strict_msa_rows == 0:
            blockers.append("msa_cache_ready_but_no_strict_real_source_training_rows")
            return "partial_feature_gate_ready", "msa_cache_valid_but_join_has_zero_training_rows", blockers, True
        if msa.get("ready") is True:
            return "partial_feature_gate_ready", "msa_cache_and_strict_join_ready", blockers, True
        blockers.append("msa_cache_not_ready")
        return "hard_gate_still_blocked", "msa_cache_validation_not_ready", blockers, False
    if action_id == "act_ddg_proxy_or_physics":
        ddg_probe = reports["ddg_probe"]
        ddg_ready = reports["ddg_readiness"]
        if ddg_probe.get("executable_ddg_backend_ready") is not True:
            blockers.extend(["rosetta_executable_not_found", "foldx_executable_not_found", "pyrosetta_module_unavailable"])
            return "physical_ddg_not_ready", "probe_executed_but_rosetta_pyrosetta_foldx_not_integrated", blockers, False
        if ddg_ready.get("executable_ddg_backend_ready") is True:
            return "physics_ddg_runtime_ready", "physical_ddg_backend_ready", blockers, True
        blockers.append("executable_ddg_backend_not_ready")
        return "physical_ddg_not_ready", "ddg_backend_readiness_false", blockers, False
    if action_id == "act_wet_lab_feedback_authorization":
        feedback = reports["wet_lab_authorization"]
        if feedback.get("authorized_candidate_rows", 0) == 0:
            blockers.append("wet_lab_feedback_authorization_rows_zero")
            return "hard_gate_still_blocked", "authorization_gate_ran_but_no_rows_authorized", blockers, False
        if feedback.get("ready_for_feedback_intake_rows", 0) == 0:
            blockers.append("wet_lab_feedback_intake_rows_zero")
        return "wet_lab_authorization_ready", "wet_lab_authorization_rows_present_and_validated", blockers, True
    if action_id == "act_fireprot_candidate_review":
        fireprot = reports["fireprot_reviewed_import"]
        if fireprot.get("ready_for_training_import_rows", 0) == 0:
            blockers.append("fireprot_reviewed_import_rows_zero")
        return "hard_gate_still_blocked", "fireprot_review_gate_ran_but_no_training_import_rows", blockers, False
    if action_id == "act_benchmark_score_cache":
        benchmark = reports["benchmark_validation"]
        if benchmark.get("ready_for_model_claim") is not True:
            blockers.append("benchmark_score_cache_not_ready_for_model_claim")
        return "benchmark_gate_still_blocked", "benchmark_validation_ran_but_heads_ready_zero", blockers, False
    if action_id == "act_model_claim_consistency":
        model_claim = reports["model_claim_consistency"]
        if model_claim.get("success") is True:
            return "safety_guard_ready", "model_claim_fail_closed_consistency_passed", blockers, True
        blockers.append("model_claim_fail_closed_consistency_failed")
        return "safety_guard_failed", "model_claim_consistency_failed", blockers, False
    if action_id == "act_release_guard_links":
        release_guard = reports["release_guard_links"]
        if release_guard.get("success") is True:
            return "safety_guard_ready", "release_safety_guard_links_passed", blockers, True
        blockers.append("release_safety_guard_links_failed")
        return "safety_guard_failed", "release_guard_validation_failed", blockers, False
    if action_id == "act_tool_contract_validation":
        tool_contract = reports["tool_contract_validation"]
        if tool_contract.get("success") is True:
            return "safety_guard_ready", "tool_contract_validation_passed", blockers, True
        blockers.append("tool_contract_validation_failed")
        return "safety_guard_failed", "tool_contract_validation_failed", blockers, False
    if action_id == "act_safe_pipeline":
        return "skipped_by_policy", "skipped_to_avoid_recursive_safe_pipeline_execution", blockers, False
    if receipt_status == "executed_passed":
        return "engineering_evidence_ready", "execution_passed_without_specific_outcome_rule", blockers, True
    if receipt_status == "executed_failed":
        blockers.append("execution_failed")
        return "execution_failed", "execution_failed_without_specific_outcome_rule", blockers, False
    return "not_executed", "no_execution_receipt", blockers, False


def main() -> int:
    parser = argparse.ArgumentParser(description="Build enzyme agent execution outcome dashboard")
    parser.add_argument("--output-jsonl", type=Path, default=OUT_JSONL)
    parser.add_argument("--output-report", type=Path, default=OUT_REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    eligibility = load_jsonl(AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_eligibility_matrix.jsonl")
    receipts = load_jsonl(AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl")
    receipts_by_action = {row.get("action_id"): row for row in receipts}
    reports = {
        "numbering_validation": load_json(AI_ROOT / "reports" / "numbering_curation_validation_report.json"),
        "reviewed_structure_graph_validation": load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json"),
        "msa_validation": load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json"),
        "ddg_probe": load_json(AI_ROOT / "reports" / "ddg_executable_probe_report.json"),
        "ddg_readiness": load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json"),
        "wet_lab_authorization": load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"),
        "fireprot_reviewed_import": load_json(AI_ROOT / "reports" / "fireprot_reviewed_import_candidate_report.json"),
        "benchmark_validation": load_json(AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json"),
        "model_claim_consistency": load_json(AI_ROOT / "reports" / "model_claim_fail_closed_consistency_report.json"),
        "release_guard_links": load_json(AI_ROOT / "reports" / "local_release_safety_guard_link_validation_report.json"),
        "tool_contract_validation": load_json(AI_ROOT / "reports" / "enzyme_tool_contract_validation_report.json"),
    }

    rows: list[dict[str, Any]] = []
    for entry in eligibility:
        action_id = entry.get("action_id")
        receipt = receipts_by_action.get(action_id) or {}
        outcome_class, outcome_summary, blockers, engineering_ready = action_outcome(
            str(action_id),
            receipt.get("return_status"),
            reports,
        )
        hard_gate_unlocked = outcome_class in {
            "wet_lab_authorization_ready",
            "physics_ddg_runtime_ready",
            "benchmark_ready_for_model_claim",
        }
        rows.append({
            "created_at": created_at,
            "local_only": True,
            "action_id": action_id,
            "title": entry.get("title"),
            "classification": entry.get("classification"),
            "receipt_present": entry.get("receipt_present"),
            "receipt_status": entry.get("receipt_status"),
            "execution_status": entry.get("execution_status"),
            "outcome_class": outcome_class,
            "outcome_summary": outcome_summary,
            "engineering_ready": engineering_ready,
            "hard_gate_unlocked": hard_gate_unlocked,
            "remaining_blockers": blockers,
            "writes_formal_decision": False,
            "writes_training_rows": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        })

    outcome_counts: dict[str, int] = {}
    for row in rows:
        outcome = row["outcome_class"]
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

    formal_counts = {
        "numbering_curation_decisions": count_jsonl(AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"),
        "structure_chain_mapping_decisions": count_jsonl(AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_decisions.jsonl"),
        "wet_lab_feedback_authorizations": count_jsonl(AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"),
        "strict_repaired_supervised_rows": count_jsonl(AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"),
        "claim_eligible_rows": count_jsonl(AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_claim_eligible.jsonl"),
    }
    report = {
        "created_at": created_at,
        "local_only": True,
        "action_rows": len(rows),
        "receipt_present_rows": sum(1 for row in rows if row["receipt_present"]),
        "executed_passed_rows": sum(1 for row in rows if row["receipt_status"] == "executed_passed"),
        "executed_failed_rows": sum(1 for row in rows if row["receipt_status"] == "executed_failed"),
        "engineering_ready_rows": sum(1 for row in rows if row["engineering_ready"]),
        "hard_gate_unlocked_rows": sum(1 for row in rows if row["hard_gate_unlocked"]),
        "outcome_counts": outcome_counts,
        "formal_counts": formal_counts,
        "rosetta_pyrosetta_foldx_physics_ddg_ready": bool(reports["ddg_probe"].get("executable_ddg_backend_ready")),
        "thermompnn_proxy_ready": bool(reports["ddg_readiness"].get("proxy_ddg_backend_ready")),
        "benchmark_ready_for_model_claim": bool(reports["benchmark_validation"].get("ready_for_model_claim")),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "dashboard": str(args.output_jsonl.relative_to(AI_ROOT)),
        "policy": "Outcome dashboard interprets receipted execution results. It is not a formal decision file, training import, physics ddG artifact, model claim, or release approval.",
    }
    write_jsonl(args.output_jsonl, rows)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "action_rows": report["action_rows"],
        "engineering_ready_rows": report["engineering_ready_rows"],
        "hard_gate_unlocked_rows": report["hard_gate_unlocked_rows"],
        "safe_for_model_claim": False,
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
