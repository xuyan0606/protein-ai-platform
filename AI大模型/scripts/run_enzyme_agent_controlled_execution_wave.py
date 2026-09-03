#!/usr/bin/env python3
"""Execute the first authorized local enzyme-agent action wave and write receipts."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl"
OUT = AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_report.json"
KNOW_HOW_OUT = AI_ROOT / "reports" / "enzyme_know_how_retrieval_execution_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".enzyme_agent_controlled_execution_wave.lock"

AUTH_REF = "user_20260731_continue_permission_can_execute_actions_receipts_tools"

ACTION_COMMANDS: dict[str, dict[str, Any]] = {
    "act_numbering_review": {
        "tool_contract_id": "tool_numbering_curation_validate_apply",
        "execution_mode": "manual_only",
        "commands": [
            ["scripts/validate_numbering_curation_decisions.py"],
            ["scripts/apply_numbering_curation.py"],
        ],
        "output_artifacts": [
            "reports/numbering_curation_validation_report.json",
            "reports/numbering_curation_apply_report.json",
        ],
        "validator_artifacts": ["reports/numbering_curation_validation_report.json"],
    },
    "act_structure_chain_mapping": {
        "tool_contract_id": "tool_structure_chain_mapping_validate_apply",
        "execution_mode": "manual_only",
        "commands": [
            ["scripts/validate_structure_chain_mapping_decisions.py"],
            ["scripts/apply_structure_chain_mapping_decisions.py"],
            ["scripts/build_reviewed_structure_graph_features.py"],
            ["scripts/validate_reviewed_structure_graph_features.py"],
        ],
        "output_artifacts": [
            "reports/structure_chain_mapping_decision_validation_report.json",
            "reports/reviewed_structure_graph_feature_report.json",
            "reports/reviewed_structure_graph_validation_report.json",
        ],
        "validator_artifacts": [
            "reports/structure_chain_mapping_decision_validation_report.json",
            "reports/reviewed_structure_graph_validation_report.json",
        ],
    },
    "act_msa_conservation": {
        "tool_contract_id": "tool_msa_mmseqs_cache_validate",
        "execution_mode": "local_script",
        "commands": [
            ["scripts/build_strict_msa_site_features.py"],
            ["scripts/validate_msa_conservation_cache.py"],
        ],
        "output_artifacts": [
            "reports/strict_msa_site_feature_report.json",
            "reports/msa_conservation_cache_validation_report.json",
        ],
        "validator_artifacts": ["reports/msa_conservation_cache_validation_report.json"],
    },
    "act_ddg_proxy_or_physics": {
        "tool_contract_id": "tool_ddg_backend_readiness_probe",
        "execution_mode": "manual_only",
        "commands": [
            ["scripts/build_ddg_executable_probe.py"],
            ["scripts/build_ddg_local_runtime_discovery.py"],
            ["scripts/build_ddg_backend_readiness.py"],
        ],
        "output_artifacts": [
            "reports/ddg_executable_probe_report.json",
            "reports/ddg_local_runtime_discovery_report.json",
            "reports/ddg_backend_readiness_report.json",
        ],
        "validator_artifacts": ["reports/ddg_backend_readiness_report.json"],
        "status_reason": "ddG probe executed; PyRosetta may be locally ready only when formal license/runtime receipt and smoke artifacts are already valid. Training/model/release claims stay closed.",
    },
    "act_wet_lab_feedback_authorization": {
        "tool_contract_id": "tool_wet_lab_feedback_authorization_gate",
        "execution_mode": "manual_only",
        "commands": [
            ["scripts/validate_wet_lab_mutant_library_feedback_authorizations.py"],
            ["scripts/build_wet_lab_mutant_library_feedback_preflight.py"],
        ],
        "output_artifacts": [
            "reports/wet_lab_mutant_library_feedback_authorization_validation_report.json",
            "reports/wet_lab_mutant_library_feedback_preflight_report.json",
        ],
        "validator_artifacts": ["reports/wet_lab_mutant_library_feedback_authorization_validation_report.json"],
    },
    "act_fireprot_candidate_review": {
        "tool_contract_id": "tool_fireprot_reviewed_import_gate",
        "execution_mode": "local_script",
        "commands": [
            ["scripts/validate_fireprot_dedup_review_decisions.py"],
            ["scripts/build_fireprot_reviewed_import_candidates.py"],
        ],
        "output_artifacts": [
            "reports/fireprot_dedup_review_decision_validation_report.json",
            "reports/fireprot_reviewed_import_candidate_report.json",
        ],
        "validator_artifacts": ["reports/fireprot_dedup_review_decision_validation_report.json"],
    },
    "act_benchmark_score_cache": {
        "tool_contract_id": "tool_benchmark_score_cache_validate",
        "execution_mode": "local_script",
        "commands": [
            ["scripts/apply_benchmark_score_cache_intake.py"],
            ["scripts/validate_benchmark_score_cache.py"],
        ],
        "output_artifacts": [
            "reports/benchmark_score_cache_intake_report.json",
            "reports/benchmark_score_cache_validation_report.json",
        ],
        "validator_artifacts": ["reports/benchmark_score_cache_validation_report.json"],
    },
    "act_model_claim_consistency": {
        "tool_contract_id": "tool_model_claim_fail_closed_consistency",
        "execution_mode": "local_script",
        "commands": [["scripts/validate_model_claim_fail_closed_consistency.py"]],
        "output_artifacts": ["reports/model_claim_fail_closed_consistency_report.json"],
        "validator_artifacts": ["reports/model_claim_fail_closed_consistency_report.json"],
    },
    "act_release_guard_links": {
        "tool_contract_id": "tool_local_release_safety_guard_links",
        "execution_mode": "local_script",
        "commands": [
            ["scripts/validate_enzyme_agent_controlled_release_guard_order.py"],
            ["scripts/validate_enzyme_agent_controlled_release_guard_order_regression.py"],
            ["scripts/validate_enzyme_agent_controlled_release_guard_order_current.py"],
            ["scripts/validate_enzyme_agent_controlled_release_guard_order_current_regression.py"],
            ["scripts/validate_enzyme_agent_controlled_release_guard_order_atomicity_regression.py"],
            ["scripts/validate_local_release_consistency_semantic_policy.py"],
            ["scripts/validate_local_release_consistency_semantic_policy_regression.py"],
            ["scripts/validate_local_release_consistency_semantic_policy_current.py"],
            ["scripts/validate_local_release_consistency_semantic_policy_current_regression.py"],
            ["scripts/validate_local_release_consistency_semantic_policy_atomicity_regression.py"],
            ["scripts/validate_local_release_consistency_receipt_atomicity_regression.py"],
            ["scripts/validate_local_release_safety_guard_links_atomicity_regression.py"],
            ["scripts/build_data_lake_manifest.py"],
            ["scripts/validate_data_lake_live_content_integrity.py"],
            ["scripts/build_claim_readiness_matrix.py"],
            ["scripts/validate_claim_readiness_matrix_fail_closed_policy.py"],
            ["scripts/validate_claim_readiness_matrix_fail_closed_policy_current.py"],
            ["scripts/validate_claim_promotion_decisions.py"],
            ["scripts/build_local_release_manifest.py"],
            ["scripts/sync_stage25_operator_docs_dynamic_status.py"],
            ["scripts/validate_stage25_operator_docs_sync_current_receipt.py"],
            ["scripts/build_data_lake_manifest.py"],
            ["scripts/validate_data_lake_live_content_integrity.py"],
            ["scripts/build_claim_readiness_matrix.py"],
            ["scripts/validate_claim_readiness_matrix_fail_closed_policy.py"],
            ["scripts/validate_claim_readiness_matrix_fail_closed_policy_current.py"],
            ["scripts/validate_claim_promotion_decisions.py"],
            ["scripts/build_local_release_manifest.py"],
            ["scripts/validate_local_release_manifest_fail_closed_consistency.py"],
            ["scripts/validate_local_release_consistency_receipt_current.py"],
            ["scripts/validate_local_release_consistency_receipt_current_regression.py"],
            ["scripts/build_data_lake_manifest.py"],
            ["scripts/validate_data_lake_live_content_integrity.py"],
            ["scripts/build_claim_readiness_matrix.py"],
            ["scripts/validate_claim_readiness_matrix_fail_closed_policy.py"],
            ["scripts/validate_claim_readiness_matrix_fail_closed_policy_current.py"],
            ["scripts/validate_claim_promotion_decisions.py"],
            ["scripts/build_local_release_manifest.py"],
            ["scripts/validate_local_release_safety_guard_links.py"],
            ["scripts/build_data_lake_manifest.py"],
            ["scripts/validate_data_lake_live_content_integrity.py"],
        ],
        "output_artifacts": [
            "reports/enzyme_agent_controlled_release_guard_order_validation_report.json",
            "reports/enzyme_agent_controlled_release_guard_order_regression_report.json",
            "reports/enzyme_agent_controlled_release_guard_order_current_validation_report.json",
            "reports/enzyme_agent_controlled_release_guard_order_current_regression_report.json",
            "reports/enzyme_agent_controlled_release_guard_order_atomicity_regression_report.json",
            "reports/local_release_consistency_semantic_policy_validation_report.json",
            "reports/local_release_consistency_semantic_policy_regression_report.json",
            "reports/local_release_consistency_semantic_policy_current_validation_report.json",
            "reports/local_release_consistency_semantic_policy_current_regression_report.json",
            "reports/local_release_consistency_semantic_policy_atomicity_regression_report.json",
            "reports/local_release_consistency_receipt_atomicity_regression_report.json",
            "reports/local_release_safety_guard_links_atomicity_regression_report.json",
            "reports/data_lake_manifest.json",
            "reports/data_lake_live_content_integrity_validation_report.json",
            "reports/claim_readiness_matrix.json",
            "reports/claim_readiness_matrix_fail_closed_policy_validation_report.json",
            "reports/claim_readiness_matrix_fail_closed_policy_current_validation_report.json",
            "reports/claim_promotion_decision_validation_report.json",
            "reports/stage25_operator_docs_dynamic_status_sync_report.json",
            "reports/stage25_operator_docs_sync_current_receipt_validation_report.json",
            "reports/local_release_manifest.json",
            "reports/local_release_manifest_fail_closed_consistency_validation_report.json",
            "reports/local_release_consistency_receipt_current_validation_report.json",
            "reports/local_release_consistency_receipt_current_regression_report.json",
            "reports/local_release_safety_guard_link_validation_report.json",
        ],
        "validator_artifacts": ["reports/local_release_safety_guard_link_validation_report.json"],
    },
    "act_tool_contract_validation": {
        "tool_contract_id": "tool_enzyme_tool_contract_validator",
        "execution_mode": "local_script",
        "commands": [["scripts/validate_enzyme_tool_contracts.py"]],
        "output_artifacts": ["reports/enzyme_tool_contract_validation_report.json"],
        "validator_artifacts": ["reports/enzyme_tool_contract_validation_report.json"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_bytes_atomic(path: Path, payload: bytes, *, prefix: str, fail_before_replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.{prefix}-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        if fail_before_replace:
            raise RuntimeError(f"simulated_{prefix}_failure_before_replace")
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_json_atomic(path: Path, payload: dict[str, Any], *, prefix: str, fail_before_replace: bool = False) -> None:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_bytes_atomic(path, encoded, prefix=prefix, fail_before_replace=fail_before_replace)


def receipt_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode("utf-8")


def acquire_lock(path: Path, timeout_seconds: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            handle.seek(0)
            handle.truncate()
            handle.write(f"pid={os.getpid()}\n")
            handle.flush()
            os.fsync(handle.fileno())
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(0.05)


def commit_receipt_pair(
    receipts_path: Path,
    receipts_payload: bytes,
    report_path: Path,
    report: dict[str, Any],
    *,
    fail_before_receipts_replace: bool = False,
    fail_after_receipts_replace: bool = False,
    fail_before_report_replace: bool = False,
) -> None:
    write_bytes_atomic(receipts_path, receipts_payload, prefix="wave-receipts", fail_before_replace=fail_before_receipts_replace)
    if fail_after_receipts_replace:
        raise RuntimeError("simulated_wave_failure_after_receipts_replace")
    write_json_atomic(report_path, report, prefix="wave-report", fail_before_replace=fail_before_report_replace)


def run_command(command: list[str]) -> dict[str, Any]:
    process = subprocess.run(
        [sys.executable, *command],
        cwd=AI_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": " ".join([sys.executable, *command]),
        "returncode": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
    }


def build_know_how_report(created_at: str) -> dict[str, Any]:
    policy = load_json(AI_ROOT / "reports" / "enzyme_analysis_constraint_policy_report.json")
    report = {
        "created_at": created_at,
        "local_only": True,
        "action_id": "act_know_how_retrieval",
        "source_artifacts": [
            "reports/enzyme_analysis_constraint_policy_report.json",
            "reports/biomni_deep_source_learning_for_kwb_2026_07_31.md",
        ],
        "tool_sequence_steps": len(policy.get("tool_sequence") or []),
        "requires_confirmation": bool((policy.get("tool_call_display") or {}).get("user_confirmation_required_before_execution")),
        "rosetta_status": (policy.get("rosetta_integration_status") or {}).get("status"),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Read-only know-how retrieval summary. It does not execute external tools or approve model claims.",
    }
    write_json_atomic(KNOW_HOW_OUT, report, prefix="know-how")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run controlled enzyme agent execution wave")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-receipts-replace", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fail-after-receipts-replace", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fail-before-report-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    receipts_path = args.receipts.resolve()
    output_path = args.output.resolve()
    lock_path = args.lock_path.resolve()
    lock_handle = acquire_lock(lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "execution_wave_lock_timeout", "output_preserved": output_path.exists(), "receipts_preserved": receipts_path.exists()}, ensure_ascii=False, sort_keys=True))
        return 1

    created_at = datetime.now(timezone.utc).isoformat()
    plan = load_json(AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json")
    actions_by_id = {row.get("action_id"): row for row in plan.get("actions") or []}
    receipts: list[dict[str, Any]] = []
    action_results: list[dict[str, Any]] = []

    know_how = build_know_how_report(created_at)
    know_how_action = actions_by_id.get("act_know_how_retrieval", {})
    receipts.append({
        "receipt_id": "receipt_act_know_how_retrieval_20260731_p175",
        "created_at": created_at,
        "local_only": True,
        "trace_id": "enzyme_agent_trace_20260731_p170",
        "plan_id": plan.get("plan_id"),
        "action_id": "act_know_how_retrieval",
        "tool_contract_id": "tool_enzyme_know_how_retrieval_plan",
        "execution_mode": "read_only",
        "human_confirmation_ref": AUTH_REF,
        "input_artifacts": know_how.get("source_artifacts"),
        "output_artifacts": ["reports/enzyme_know_how_retrieval_execution_report.json"],
        "validator_artifacts": ["reports/enzyme_know_how_retrieval_execution_report.json"],
        "return_status": "executed_passed",
        "writes_formal_decision": False,
        "writes_training_rows": bool(know_how_action.get("writes_training_rows")),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    })
    action_results.append({"action_id": "act_know_how_retrieval", "return_status": "executed_passed", "commands": []})

    for action_id, spec in ACTION_COMMANDS.items():
        command_results = [run_command(command) for command in spec["commands"]]
        all_passed = all(row["returncode"] == 0 for row in command_results)
        return_status = spec.get("force_status") or ("executed_passed" if all_passed else "executed_failed")
        action = actions_by_id.get(action_id, {})
        receipts.append({
            "receipt_id": f"receipt_{action_id}_20260731_p175",
            "created_at": created_at,
            "local_only": True,
            "trace_id": "enzyme_agent_trace_20260731_p170",
            "plan_id": plan.get("plan_id"),
            "action_id": action_id,
            "tool_contract_id": spec["tool_contract_id"],
            "execution_mode": spec["execution_mode"],
            "human_confirmation_ref": AUTH_REF,
            "input_artifacts": action.get("input_artifacts") or [],
            "output_artifacts": spec["output_artifacts"],
            "validator_artifacts": spec["validator_artifacts"],
            "return_status": return_status,
            "writes_formal_decision": False,
            "writes_training_rows": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "status_reason": spec.get("status_reason"),
        })
        action_results.append({
            "action_id": action_id,
            "return_status": return_status,
            "all_commands_passed": all_passed,
            "commands": command_results,
        })

    skipped_actions = [
        {
            "action_id": "act_safe_pipeline",
            "reason": "skipped_to_avoid_recursive_safe_pipeline_execution_inside_safe_pipeline",
            "safe_for_model_claim": False,
        }
    ]
    receipts_payload = receipt_bytes(receipts)
    wave_script = Path(__file__).resolve()
    report = {
        "schema_version": 2,
        "mode": "enzyme-agent-controlled-execution-wave-v2",
        "created_at": created_at,
        "local_only": True,
        "success": all(row["return_status"] != "executed_failed" for row in receipts),
        "wave_script_path": str(wave_script),
        "wave_script_sha256": hashlib.sha256(wave_script.read_bytes()).hexdigest(),
        "receipts_path": str(receipts_path),
        "receipts_sha256": sha256_bytes(receipts_payload),
        "output_path": str(output_path),
        "lock_path": str(lock_path),
        "lock_acquired": True,
        "receipts_atomic_commit": True,
        "report_atomic_commit": True,
        "authorization_ref": AUTH_REF,
        "plan_id": plan.get("plan_id"),
        "executed_receipt_rows": len(receipts),
        "executed_action_ids": [row["action_id"] for row in receipts],
        "executed_passed_rows": sum(1 for row in receipts if row["return_status"] == "executed_passed"),
        "executed_failed_rows": sum(1 for row in receipts if row["return_status"] == "executed_failed"),
        "blocked_rows": sum(1 for row in receipts if row["return_status"] == "blocked"),
        "skipped_actions": skipped_actions,
        "action_results": action_results,
        "receipts": str(receipts_path.relative_to(AI_ROOT)),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Authorized local execution wave. It records receipts for local validators/probes only; it may observe a valid PyRosetta local runtime receipt but does not create training labels, customer delivery approval, model claims, or release readiness.",
    }
    try:
        commit_receipt_pair(
            receipts_path,
            receipts_payload,
            output_path,
            report,
            fail_before_receipts_replace=args.fail_before_receipts_replace,
            fail_after_receipts_replace=args.fail_after_receipts_replace,
            fail_before_report_replace=args.fail_before_report_replace,
        )
    except Exception as exc:
        lock_handle.close()
        print(json.dumps({"success": False, "error": f"execution_wave_commit_failed:{type(exc).__name__}:{exc}", "output": str(output_path)}, ensure_ascii=False, sort_keys=True))
        return 1
    lock_handle.close()
    print(json.dumps({
        "executed_receipt_rows": report["executed_receipt_rows"],
        "executed_passed_rows": report["executed_passed_rows"],
        "executed_failed_rows": report["executed_failed_rows"],
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] and all(
        result.get("all_commands_passed", True)
        or result.get("action_id") == "act_ddg_proxy_or_physics"
        for result in action_results
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
