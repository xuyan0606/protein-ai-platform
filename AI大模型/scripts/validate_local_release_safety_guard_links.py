#!/usr/bin/env python3
"""Validate local release links all core safety guard reports."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
OUT = AI_ROOT / "reports" / "local_release_safety_guard_link_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".local_release_safety_guard_links.lock"
CONSISTENCY_RECEIPT = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
CONSISTENCY_VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_manifest_fail_closed_consistency.py"
CONSISTENCY_LOCK = AI_ROOT / "reports" / ".local_release_manifest_fail_closed_consistency.lock"
CONSISTENCY_CURRENT = AI_ROOT / "reports" / "local_release_consistency_receipt_current_validation_report.json"
CONSISTENCY_CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_consistency_receipt_current.py"
CONSISTENCY_CURRENT_REGRESSION = AI_ROOT / "reports" / "local_release_consistency_receipt_current_regression_report.json"
CONSISTENCY_CURRENT_REGRESSION_SCRIPT = AI_ROOT / "scripts" / "validate_local_release_consistency_receipt_current_regression.py"
CONSISTENCY_SEMANTIC_CONTRACT = AI_ROOT / "scripts" / "local_release_consistency_receipt_contract.py"
CONSISTENCY_SEMANTIC_POLICY = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json"
CONSISTENCY_SEMANTIC_POLICY_REGRESSION = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_regression_report.json"

REQUIRED_GUARD_LINKS = {
    "no_pseudo_strict_training_leakage_validation_report": "reports/no_pseudo_strict_training_leakage_validation_report.json",
    "model_claim_fail_closed_consistency_report": "reports/model_claim_fail_closed_consistency_report.json",
    "top_tier_model_ready_to_verify_receipt_validation": "reports/top_tier_model_ready_to_verify_receipt_validation_report.json",
    "review_draft_formal_boundary_validation_report": "reports/review_draft_formal_boundary_validation_report.json",
    "no_review_draft_training_leakage_validation_report": "reports/no_review_draft_training_leakage_validation_report.json",
    "draft_namespace_isolation_validation_report": "reports/draft_namespace_isolation_validation_report.json",
    "no_unreviewed_positive_gate_flags_validation_report": "reports/no_unreviewed_positive_gate_flags_validation_report.json",
    "report_positive_claim_gate_quarantine_validation_report": "reports/report_positive_claim_gate_quarantine_validation_report.json",
    "claim_readiness_matrix_fail_closed_policy_validation_report": "reports/claim_readiness_matrix_fail_closed_policy_validation_report.json",
    "claim_readiness_policy_anchor_validation_report": "reports/claim_readiness_policy_anchor_validation_report.json",
    "claim_readiness_policy_anchor_regression_report": "reports/claim_readiness_policy_anchor_regression_report.json",
    "claim_promotion_decision_validation_report": "reports/claim_promotion_decision_validation_report.json",
    "claim_readiness_matrix_fail_closed_policy_current_validation_report": "reports/claim_readiness_matrix_fail_closed_policy_current_validation_report.json",
    "claim_readiness_matrix_fail_closed_policy_current_regression_report": "reports/claim_readiness_matrix_fail_closed_policy_current_regression_report.json",
    "human_decision_backlog_fail_closed_consistency_validation_report": "reports/human_decision_backlog_fail_closed_consistency_validation_report.json",
    "human_review_release_consistency_validation_report": "reports/human_review_release_consistency_validation_report.json",
    "operator_work_receipt_manifest_consistency_validation_report": "reports/operator_work_receipt_manifest_consistency_validation_report.json",
    "local_release_manifest_fail_closed_consistency_validation_report": "reports/local_release_manifest_fail_closed_consistency_validation_report.json",
    "local_release_consistency_receipt_atomicity_regression": "reports/local_release_consistency_receipt_atomicity_regression_report.json",
    "local_release_consistency_receipt_current": "reports/local_release_consistency_receipt_current_validation_report.json",
    "local_release_consistency_receipt_current_regression": "reports/local_release_consistency_receipt_current_regression_report.json",
    "local_release_consistency_semantic_policy_validation": "reports/local_release_consistency_semantic_policy_validation_report.json",
    "local_release_consistency_semantic_policy_regression": "reports/local_release_consistency_semantic_policy_regression_report.json",
    "local_release_consistency_semantic_policy_current": "reports/local_release_consistency_semantic_policy_current_validation_report.json",
    "local_release_consistency_semantic_policy_current_regression": "reports/local_release_consistency_semantic_policy_current_regression_report.json",
    "local_release_consistency_semantic_policy_atomicity_regression": "reports/local_release_consistency_semantic_policy_atomicity_regression_report.json",
    "ready_to_verify_promotion_validation": "reports/ready_to_verify_promotion_validation_report.json",
    "ready_to_verify_promotion_safety_regression": "reports/ready_to_verify_promotion_safety_regression_report.json",
    "ready_to_verify_promotion_release_summary_regression": "reports/local_release_promotion_summary_safety_regression_report.json",
    "data_lake_artifact_integrity_regression": "reports/data_lake_artifact_integrity_regression_report.json",
    "local_release_high_risk_summary_safety_regression": "reports/local_release_high_risk_summary_safety_regression_report.json",
    "local_release_high_risk_coverage_safety_regression": "reports/local_release_high_risk_coverage_safety_regression_report.json",
    "data_lake_live_content_integrity_validation": "reports/data_lake_live_content_integrity_validation_report.json",
    "data_lake_live_content_integrity_regression": "reports/data_lake_live_content_integrity_regression_report.json",
    "data_lake_volatile_exemption_safety_regression": "reports/data_lake_volatile_exemption_safety_regression_report.json",
    "local_release_live_integrity_binding_regression": "reports/local_release_live_integrity_binding_regression_report.json",
    "data_lake_release_input_contract_policy_validation": "reports/data_lake_release_input_contract_policy_validation_report.json",
    "data_lake_release_input_contract_policy_regression": "reports/data_lake_release_input_contract_policy_regression_report.json",
    "local_release_contract_policy_binding_regression": "reports/local_release_contract_policy_binding_regression_report.json",
    "stage25_operator_docs_dynamic_status_sync": "reports/stage25_operator_docs_dynamic_status_sync_report.json",
    "stage25_operator_docs_sync_contract_policy_validation": "reports/stage25_operator_docs_sync_contract_policy_validation_report.json",
    "stage25_operator_docs_sync_contract_policy_regression": "reports/stage25_operator_docs_sync_contract_policy_regression_report.json",
    "stage25_operator_docs_sync_current_receipt_validation": "reports/stage25_operator_docs_sync_current_receipt_validation_report.json",
    "stage25_operator_docs_dynamic_status_sync_regression_current": "reports/stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json",
    "stage25_operator_docs_dynamic_status_sync_regression_current_regression": "reports/stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json",
    "stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression": "reports/stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression_report.json",
    "safe_training_pipeline_receipt_atomicity_regression": "reports/safe_training_pipeline_receipt_atomicity_regression_report.json",
    "stage25_fail_closed_validation_current_receipt_validation": "reports/stage25_fail_closed_validation_current_receipt_validation_report.json",
    "stage25_fail_closed_validation_current_receipt_regression": "reports/stage25_fail_closed_validation_current_receipt_regression_report.json",
    "stage25_post_source_drop_rerun_receipt_validation": "reports/stage25_post_source_drop_rerun_receipt_validation_20260806.json",
    "stage25_post_source_drop_rerun_receipt_regression": "reports/stage25_post_source_drop_rerun_receipt_regression_20260806.json",
    "stage25_post_source_drop_rerun_validation_current": "reports/stage25_post_source_drop_rerun_validation_current_20260810.json",
    "stage25_post_source_drop_rerun_validation_current_regression": "reports/stage25_post_source_drop_rerun_validation_current_regression_20260810.json",
    "stage25_post_source_drop_rerun_independent_policy": "reports/stage25_post_source_drop_rerun_independent_policy_validation_20260810.json",
    "stage25_post_source_drop_rerun_independent_policy_regression": "reports/stage25_post_source_drop_rerun_independent_policy_regression_20260810.json",
    "stage25_post_source_drop_rerun_independent_policy_current": "reports/stage25_post_source_drop_rerun_independent_policy_current_20260810.json",
    "stage25_post_source_drop_rerun_independent_policy_current_regression": "reports/stage25_post_source_drop_rerun_independent_policy_current_regression_20260810.json",
    "safe_training_pipeline_bootstrap_release_consistency_regression": "reports/safe_training_pipeline_bootstrap_release_consistency_regression_report.json",
    "enzyme_agent_controlled_release_guard_order_validation_report": "reports/enzyme_agent_controlled_release_guard_order_validation_report.json",
    "enzyme_agent_controlled_release_guard_order_regression_report": "reports/enzyme_agent_controlled_release_guard_order_regression_report.json",
    "enzyme_agent_controlled_release_guard_order_current_validation_report": "reports/enzyme_agent_controlled_release_guard_order_current_validation_report.json",
    "enzyme_agent_controlled_release_guard_order_current_regression_report": "reports/enzyme_agent_controlled_release_guard_order_current_regression_report.json",
    "enzyme_agent_controlled_release_guard_order_atomicity_regression_report": "reports/enzyme_agent_controlled_release_guard_order_atomicity_regression_report.json",
    "enzyme_agent_controlled_execution_wave_pair_atomicity_regression_report": "reports/enzyme_agent_controlled_execution_wave_pair_atomicity_regression_report.json",
    "enzyme_agent_execution_receipt_proof_current_validation_report": "reports/enzyme_agent_execution_receipt_proof_current_validation_report.json",
    "enzyme_agent_execution_receipt_proof_current_regression_report": "reports/enzyme_agent_execution_receipt_proof_current_regression_report.json",
    "local_release_safety_guard_links_atomicity_regression_report": "reports/local_release_safety_guard_links_atomicity_regression_report.json",
    "local_release_safety_guard_links_current_regression_atomicity_regression_report": "reports/local_release_safety_guard_links_current_regression_atomicity_regression_report.json",
    "stage25_remaining_blocker_cross_binding_validation_report": "reports/stage25_remaining_blocker_cross_binding_validation_report.json",
    "stage25_remaining_blocker_cross_binding_regression_report": "reports/stage25_remaining_blocker_cross_binding_regression_report.json",
}

REQUIRED_SUMMARY_TRUE_FIELDS = {
    "model_claim_fail_closed_consistency_success",
    "top_tier_model_ready_receipt_validation_success",
    "review_draft_formal_boundary_success",
    "no_review_draft_training_leakage_success",
    "draft_namespace_isolation_success",
    "no_unreviewed_positive_gate_flags_success",
    "report_positive_claim_gate_quarantine_success",
    "claim_matrix_fail_closed_policy_success",
    "claim_policy_anchor_success",
    "claim_policy_anchor_regression_success",
    "claim_promotion_decision_validation_success",
    "claim_matrix_policy_current_success",
    "claim_matrix_policy_current_regression_success",
    "human_decision_backlog_fail_closed_consistency_success",
    "human_review_release_consistency_success",
    "operator_work_receipt_manifest_consistency_success",
    "local_release_fail_closed_consistency_success",
    "local_release_fail_closed_consistency_receipt_atomic_commit",
    "local_release_fail_closed_consistency_lock_acquired",
    "local_release_consistency_receipt_atomicity_regression_success",
    "local_release_consistency_receipt_current_success",
    "local_release_consistency_receipt_current_regression_success",
    "local_release_consistency_semantic_policy_success",
    "local_release_consistency_semantic_policy_regression_success",
    "local_release_consistency_semantic_policy_current_success",
    "local_release_consistency_semantic_policy_current_regression_success",
    "local_release_consistency_semantic_policy_atomicity_regression_success",
    "ready_to_verify_promotion_validation_success",
    "ready_to_verify_promotion_regression_success",
    "ready_to_verify_promotion_release_summary_regression_success",
    "data_lake_artifact_integrity_regression_success",
    "local_release_high_risk_summary_regression_success",
    "local_release_high_risk_coverage_regression_success",
    "data_lake_live_content_integrity_success",
    "data_lake_live_content_integrity_regression_success",
    "data_lake_volatile_exemption_regression_success",
    "local_release_live_integrity_binding_regression_success",
    "release_input_contract_policy_success",
    "release_input_contract_policy_regression_success",
    "local_release_contract_policy_binding_regression_success",
    "stage25_operator_docs_dynamic_sync_success",
    "stage25_operator_docs_sync_contract_policy_success",
    "stage25_operator_docs_sync_contract_policy_regression_success",
    "stage25_operator_docs_sync_current_receipt_success",
    "stage25_operator_docs_dynamic_sync_regression_current_success",
    "stage25_operator_docs_dynamic_sync_regression_current_regression_success",
    "stage25_operator_docs_dynamic_sync_regression_atomicity_success",
    "safe_training_pipeline_receipt_atomicity_regression_success",
    "stage25_fail_closed_validation_current_receipt_validation_success",
    "stage25_fail_closed_validation_current_receipt_regression_success",
    "stage25_post_source_drop_rerun_receipt_validation_success",
    "stage25_post_source_drop_rerun_receipt_regression_success",
    "stage25_post_source_drop_rerun_validation_current_success",
    "stage25_post_source_drop_rerun_validation_current_regression_success",
    "stage25_post_source_drop_rerun_independent_policy_success",
    "stage25_post_source_drop_rerun_independent_policy_regression_success",
    "stage25_post_source_drop_rerun_independent_policy_current_success",
    "stage25_post_source_drop_rerun_independent_policy_current_regression_success",
    "safe_training_pipeline_bootstrap_release_regression_success",
    "enzyme_agent_release_guard_order_success",
    "enzyme_agent_release_guard_order_regression_success",
    "enzyme_agent_release_guard_order_current_success",
    "enzyme_agent_release_guard_order_current_regression_success",
    "enzyme_agent_release_guard_order_atomicity_regression_success",
    "enzyme_agent_execution_wave_pair_atomicity_regression_success",
    "enzyme_agent_execution_receipt_proof_current_success",
    "enzyme_agent_execution_receipt_proof_current_regression_success",
    "local_release_safety_guard_links_atomicity_regression_success",
    "local_release_safety_guard_links_current_regression_atomicity_regression_success",
    "stage25_remaining_blocker_cross_binding_success",
    "stage25_remaining_blocker_cross_binding_regression_success",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_json_snapshot(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, None
    payload = path.read_bytes()
    return json.loads(payload.decode("utf-8")), hashlib.sha256(payload).hexdigest()


def acquire_lock(path: Path, timeout_seconds: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(0.05)


def write_json_atomic(path: Path, payload: dict[str, Any], *, fail_before_replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.safety-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        if fail_before_replace:
            raise RuntimeError("simulated_safety_guard_receipt_failure_before_replace")
        os.replace(temp_path, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def build_receipt_provenance(*, release_path: Path, release_sha256: str | None, data_lake_path: Path, data_lake_sha256: str | None, consistency_path: Path, consistency_sha256: str | None, output_path: Path, lock_path: Path) -> dict[str, Any]:
    script = Path(__file__).resolve()
    return {
        "validator_script_path": str(script),
        "validator_script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "release_path": str(release_path.resolve()),
        "release_sha256": release_sha256,
        "data_lake_path": str(data_lake_path.resolve()),
        "data_lake_sha256": data_lake_sha256,
        "consistency_receipt_path": str(consistency_path.resolve()),
        "consistency_receipt_sha256": consistency_sha256,
        "output_path": str(output_path.resolve()),
        "lock_path": str(lock_path.resolve()),
        "lock_acquired": True,
        "atomic_commit": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local release safety guard links")
    parser.add_argument("--release", type=Path, default=RELEASE)
    parser.add_argument("--data-lake", type=Path, default=DATA_LAKE)
    parser.add_argument("--consistency-receipt", type=Path, default=CONSISTENCY_RECEIPT)
    parser.add_argument("--mode-check-only", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.mode_check_only:
        if args.output.resolve() == OUT.resolve():
            print(json.dumps({"success": False, "error": "mode_check_only_requires_noncanonical_output"}, ensure_ascii=False))
            return 1
        defer_safe_pipeline_terminal = os.environ.get("KWB_DEFER_SAFE_PIPELINE_TERMINAL") == "1"
        consistency_receipt = load_json(args.consistency_receipt)
        failures = []
        if consistency_receipt.get("safe_pipeline_terminal_deferred") is not defer_safe_pipeline_terminal:
            failures.append({
                "check": "safe_pipeline_terminal_mode_exact",
                "receipt_path": str(args.consistency_receipt),
                "observed": consistency_receipt.get("safe_pipeline_terminal_deferred"),
                "expected": defer_safe_pipeline_terminal,
            })
        report = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "local_only": True,
            "success": not failures,
            "mode_check_only": True,
            "safe_training_pipeline_terminal_deferred": defer_safe_pipeline_terminal,
            "consistency_receipt_path": str(args.consistency_receipt.resolve()),
            "consistency_receipt_terminal_deferred": consistency_receipt.get("safe_pipeline_terminal_deferred"),
            "failures": failures,
            "safe_for_training_pipeline": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Isolated terminal-mode parity check only; this output cannot serve as the canonical safety guard receipt.",
        }
        write_json_atomic(args.output, report, fail_before_replace=args.fail_before_replace)
        print(json.dumps({"success": report["success"], "mode_check_only": True, "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
        return 0 if not failures else 1

    lock_handle = acquire_lock(args.lock_path, args.lock_timeout_seconds)
    if lock_handle is None:
        print(json.dumps({"success": False, "error": "safety_guard_lock_timeout", "output_preserved": args.output.exists()}, ensure_ascii=False))
        return 1
    release, release_sha256 = load_json_snapshot(args.release)
    data_lake, data_lake_sha256 = load_json_snapshot(args.data_lake)
    summary = release.get("readiness_summary") or {}
    artifact_by_path = {
        artifact.get("path"): artifact
        for artifact in data_lake.get("artifacts") or []
        if artifact.get("path")
    }
    failures: list[dict[str, Any]] = []
    checked_links: list[dict[str, Any]] = []
    defer_safe_pipeline_terminal = os.environ.get("KWB_DEFER_SAFE_PIPELINE_TERMINAL") == "1"
    consistency_receipt, consistency_receipt_sha256 = load_json_snapshot(args.consistency_receipt)

    for key, rel in sorted(REQUIRED_GUARD_LINKS.items()):
        observed = release.get(key)
        path = AI_ROOT / rel
        data_lake_artifact = artifact_by_path.get(rel)
        if key == "local_release_manifest_fail_closed_consistency_validation_report" and args.consistency_receipt != CONSISTENCY_RECEIPT:
            guard_report = consistency_receipt
        else:
            guard_report = load_json(path)
        if "success" in guard_report:
            report_success = guard_report.get("success") is True
        else:
            report_success = (
                guard_report.get("safe_for_training_pipeline") is True
                and guard_report.get("invalid_artifacts", 0) == 0
                and guard_report.get("safe_for_model_claim") is False
                and guard_report.get("release_ready") is False
            )
        link_status = {
            "manifest_key": key,
            "path": rel,
            "release_link_present": observed == rel,
            "file_exists": path.exists(),
            "data_lake_artifact_present": bool(data_lake_artifact),
            "data_lake_artifact_exists": bool(data_lake_artifact and data_lake_artifact.get("exists")),
            "report_success": report_success,
            "terminal_deferred": key == "safe_training_pipeline_run" and defer_safe_pipeline_terminal,
        }
        checked_links.append(link_status)

        if observed != rel:
            failures.append({"check": "release_link_present", "key": key, "observed": observed, "expected": rel})
        if not path.exists():
            failures.append({"check": "guard_report_file_exists", "key": key, "path": rel})
        if not data_lake_artifact:
            failures.append({"check": "data_lake_artifact_present", "key": key, "path": rel})
        elif data_lake_artifact.get("exists") is not True:
            failures.append({"check": "data_lake_artifact_exists", "key": key, "path": rel, "observed": data_lake_artifact.get("exists")})
        stage25_current_deferred = defer_safe_pipeline_terminal and key.startswith("stage25_fail_closed_validation_current_receipt_")
        safe_current_regression_deferred = defer_safe_pipeline_terminal and key == "safe_training_pipeline_current_receipt_regression"
        consistency_current_deferred = defer_safe_pipeline_terminal and key == "local_release_consistency_receipt_current"
        if report_success is not True and not (key == "safe_training_pipeline_run" and defer_safe_pipeline_terminal) and not stage25_current_deferred and not safe_current_regression_deferred and not consistency_current_deferred:
            failures.append({"check": "guard_report_success_true", "key": key, "path": rel, "observed": guard_report.get("success")})

    for field in sorted(REQUIRED_SUMMARY_TRUE_FIELDS):
        if field == "safe_training_pipeline_success" and defer_safe_pipeline_terminal:
            continue
        if defer_safe_pipeline_terminal and field.startswith("stage25_fail_closed_validation_current_receipt_"):
            continue
        if defer_safe_pipeline_terminal and field.startswith("safe_training_pipeline_current_receipt_"):
            continue
        if defer_safe_pipeline_terminal and field == "local_release_consistency_receipt_current_success":
            continue
        if summary.get(field) is not True:
            failures.append({"check": "release_summary_success_true", "field": field, "observed": summary.get(field), "expected": True})

    if consistency_receipt.get("safe_pipeline_terminal_deferred") is not defer_safe_pipeline_terminal:
        failures.append({
            "check": "safe_pipeline_terminal_mode_exact",
            "receipt_path": str(args.consistency_receipt),
            "observed": consistency_receipt.get("safe_pipeline_terminal_deferred"),
            "expected": defer_safe_pipeline_terminal,
        })

    expected_consistency_contract = {
        "schema_version": 2,
        "mode": "local_release_manifest_fail_closed_consistency",
        "validator_script_path": str(CONSISTENCY_VALIDATOR.resolve()),
        "validator_script_sha256": hashlib.sha256(CONSISTENCY_VALIDATOR.read_bytes()).hexdigest() if CONSISTENCY_VALIDATOR.is_file() else None,
        "release_path": str(RELEASE.resolve()),
        "data_lake_path": str(DATA_LAKE.resolve()),
        "live_integrity_path": str((AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json").resolve()),
        "contract_policy_path": str((AI_ROOT / "reports" / "data_lake_release_input_contract_policy_validation_report.json").resolve()),
        "semantic_policy_path": str(CONSISTENCY_SEMANTIC_POLICY.resolve()),
        "output_path": str(args.consistency_receipt.resolve()),
        "lock_path": str(CONSISTENCY_LOCK.resolve()),
        "lock_acquired": True,
        "receipt_atomic_commit": True,
    }
    for field, expected in expected_consistency_contract.items():
        if consistency_receipt.get(field) != expected:
            failures.append({"check": "local_release_consistency_receipt_contract", "field": field, "observed": consistency_receipt.get(field), "expected": expected})
    for field in ("release_sha256", "data_lake_sha256", "live_integrity_sha256", "contract_policy_sha256", "semantic_policy_sha256"):
        value = consistency_receipt.get(field)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            failures.append({"check": "local_release_consistency_snapshot_sha256_valid", "field": field, "observed": value, "expected": "64 lowercase hex chars"})

    current_consistency = load_json(CONSISTENCY_CURRENT)
    expected_current_receipt_sha = hashlib.sha256(CONSISTENCY_RECEIPT.read_bytes()).hexdigest() if CONSISTENCY_RECEIPT.is_file() else None
    expected_current_contract = {
        "schema_version": 1,
        "mode": "local_release_consistency_receipt_current",
        "receipt_path": str(CONSISTENCY_RECEIPT.resolve()),
        "receipt_sha256": expected_current_receipt_sha,
        "validator_script_path": str(CONSISTENCY_VALIDATOR.resolve()),
        "validator_script_sha256": hashlib.sha256(CONSISTENCY_VALIDATOR.read_bytes()).hexdigest() if CONSISTENCY_VALIDATOR.is_file() else None,
        "semantic_contract_module_path": str(CONSISTENCY_SEMANTIC_CONTRACT.resolve()),
        "semantic_contract_module_sha256": hashlib.sha256(CONSISTENCY_SEMANTIC_CONTRACT.read_bytes()).hexdigest() if CONSISTENCY_SEMANTIC_CONTRACT.is_file() else None,
        "semantic_policy_path": str(CONSISTENCY_SEMANTIC_POLICY.resolve()),
        "semantic_policy_sha256": hashlib.sha256(CONSISTENCY_SEMANTIC_POLICY.read_bytes()).hexdigest() if CONSISTENCY_SEMANTIC_POLICY.is_file() else None,
        "current_validator_script_path": str(CONSISTENCY_CURRENT_VALIDATOR.resolve()),
        "current_validator_script_sha256": hashlib.sha256(CONSISTENCY_CURRENT_VALIDATOR.read_bytes()).hexdigest() if CONSISTENCY_CURRENT_VALIDATOR.is_file() else None,
        "current_output_path": str(CONSISTENCY_CURRENT.resolve()),
        "current_lock_path": str(CONSISTENCY_LOCK.resolve()),
        "current_atomic_commit": True,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    for field, expected in expected_current_contract.items():
        if current_consistency.get(field) != expected:
            failures.append({"check": "local_release_consistency_current_contract", "field": field, "observed": current_consistency.get(field), "expected": expected})
    if not defer_safe_pipeline_terminal and (current_consistency.get("success") is not True or current_consistency.get("failure_count") != 0 or current_consistency.get("failures") not in ([], None)):
        failures.append({"check": "local_release_consistency_current_success", "observed": {"success": current_consistency.get("success"), "failure_count": current_consistency.get("failure_count"), "failures": current_consistency.get("failures")}, "expected": {"success": True, "failure_count": 0, "failures": []}})
    if not isinstance(current_consistency.get("semantic_inputs_sha256"), str) or len(current_consistency.get("semantic_inputs_sha256") or "") != 64:
        failures.append({"check": "local_release_consistency_current_semantic_digest", "observed": current_consistency.get("semantic_inputs_sha256"), "expected": "64 lowercase hex chars"})

    current_regression = load_json(CONSISTENCY_CURRENT_REGRESSION)
    expected_current_regression_path = str(CONSISTENCY_CURRENT_REGRESSION_SCRIPT.resolve())
    expected_current_regression_sha = hashlib.sha256(CONSISTENCY_CURRENT_REGRESSION_SCRIPT.read_bytes()).hexdigest() if CONSISTENCY_CURRENT_REGRESSION_SCRIPT.is_file() else None
    if current_regression.get("success") is not True or current_regression.get("failure_count") != 0 or current_regression.get("case_count") != 16 or current_regression.get("passed_case_count") != 16 or current_regression.get("failed_case_count") != 0 or current_regression.get("isolated_fixture") is not True or current_regression.get("real_inputs_mutated") is not False or current_regression.get("post_consistency_drift_allowed") is not True:
        failures.append({"check": "local_release_consistency_current_regression_success", "observed": {"success": current_regression.get("success"), "failure_count": current_regression.get("failure_count"), "case_count": current_regression.get("case_count"), "passed_case_count": current_regression.get("passed_case_count"), "failed_case_count": current_regression.get("failed_case_count"), "isolated_fixture": current_regression.get("isolated_fixture"), "real_inputs_mutated": current_regression.get("real_inputs_mutated"), "post_consistency_drift_allowed": current_regression.get("post_consistency_drift_allowed")}, "expected": {"success": True, "failure_count": 0, "case_count": 16, "passed_case_count": 16, "failed_case_count": 0, "isolated_fixture": True, "real_inputs_mutated": False, "post_consistency_drift_allowed": True}})
    if current_regression.get("regression_script_path") != expected_current_regression_path or current_regression.get("regression_script_sha256") != expected_current_regression_sha or current_regression.get("current_validator_script_path") != str(CONSISTENCY_CURRENT_VALIDATOR.resolve()) or current_regression.get("current_validator_script_sha256") != (hashlib.sha256(CONSISTENCY_CURRENT_VALIDATOR.read_bytes()).hexdigest() if CONSISTENCY_CURRENT_VALIDATOR.is_file() else None):
        failures.append({"check": "local_release_consistency_current_regression_scripts_current", "observed": {"regression_path": current_regression.get("regression_script_path"), "regression_sha256": current_regression.get("regression_script_sha256"), "current_validator_path": current_regression.get("current_validator_script_path"), "current_validator_sha256": current_regression.get("current_validator_script_sha256")}, "expected": {"regression_path": expected_current_regression_path, "regression_sha256": expected_current_regression_sha, "current_validator_path": str(CONSISTENCY_CURRENT_VALIDATOR.resolve()), "current_validator_sha256": hashlib.sha256(CONSISTENCY_CURRENT_VALIDATOR.read_bytes()).hexdigest() if CONSISTENCY_CURRENT_VALIDATOR.is_file() else None}})

    if release.get("release_ready") is not False:
        failures.append({"check": "release_ready_false", "observed": release.get("release_ready"), "expected": False})
    if release.get("local_only") is not True:
        failures.append({"check": "local_only_true", "observed": release.get("local_only"), "expected": True})

    provenance = build_receipt_provenance(release_path=args.release, release_sha256=release_sha256, data_lake_path=args.data_lake, data_lake_sha256=data_lake_sha256, consistency_path=args.consistency_receipt, consistency_sha256=consistency_receipt_sha256, output_path=args.output, lock_path=args.lock_path)
    report = {
        "schema_version": 2,
        "mode": "local-release-safety-guard-links-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **provenance,
        "local_only": True,
        "success": not failures,
        "guard_link_count": len(REQUIRED_GUARD_LINKS),
        "safe_training_pipeline_terminal_deferred": defer_safe_pipeline_terminal,
        "consistency_receipt_terminal_deferred": consistency_receipt.get("safe_pipeline_terminal_deferred"),
        "checked_guard_links": checked_links,
        "checked_summary_success_fields": sorted(REQUIRED_SUMMARY_TRUE_FIELDS),
        "failures": failures,
        "safe_for_training_pipeline": not failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Core safety guard reports must be explicitly linked in the local release manifest and present in the data lake before the package can be used for internal review. This does not make the release production-ready.",
    }
    write_json_atomic(args.output, report, fail_before_replace=args.fail_before_replace)
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    lock_handle.close()
    print(json.dumps({
        "success": report["success"],
        "guard_link_count": report["guard_link_count"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
