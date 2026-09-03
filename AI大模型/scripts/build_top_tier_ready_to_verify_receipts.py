#!/usr/bin/env python3
"""Execute ready-to-verify top-tier model lanes and write fail-closed receipts."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "top_tier_model_execution_board.json"
RECEIPTS_OUT = AI_ROOT / "datasets" / "governance" / "top_tier_model_ready_to_verify_receipts.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "top_tier_model_ready_to_verify_receipt_report.json"

EXPECTED_READY_COMMANDS = {
    "cross_rosetta_foldx_ddg_backend": [
        "python3 scripts/validate_external_license_review_decisions.py",
        "python3 scripts/build_pyrosetta_local_install_probe.py",
        "python3 scripts/validate_pyrosetta_local_install_probe.py",
        "python3 scripts/build_ddg_executable_probe.py",
        "python3 scripts/build_pyrosetta_physical_smoke_bootstrap.py",
        "python3 scripts/validate_ddg_backend_runtime_receipts.py",
        "python3 scripts/build_foreign_tool_readiness.py",
        "python3 scripts/build_ddg_backend_readiness.py",
        "python3 scripts/build_ddg_model_consumption_contract_report.py",
        "python3 scripts/validate_ddg_model_consumption_contract_report.py",
    ],
    "p0_kwb_wet_lab_feedback": [
        "python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
        "python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py",
        "python3 scripts/validate_experiment_feedback_intake.py",
        "python3 scripts/build_feedback_training_import_semantic_guard.py",
        "python3 scripts/validate_feedback_training_import_semantic_guard.py",
    ],
    "p0_reviewed_structure_graph": [
        "python3 scripts/build_reviewed_structure_graph_features.py",
        "python3 scripts/validate_reviewed_structure_graph_features.py",
    ],
}
ALLOWED_READY_IDS = set(EXPECTED_READY_COMMANDS)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def run_command(command: str) -> dict[str, Any]:
    args = shlex.split(command)
    if not args or args[0] != "python3":
        return {
            "command": command,
            "returncode": 127,
            "ok": False,
            "stdout": "",
            "stderr": "unsupported command; only python3 script commands are allowed",
        }
    process = subprocess.run(
        [sys.executable, *args[1:]],
        cwd=AI_ROOT,
        text=True,
        capture_output=True,
        timeout=600,
    )
    return {
        "command": command,
        "returncode": process.returncode,
        "ok": process.returncode == 0,
        "stdout": truncate(process.stdout.strip()),
        "stderr": truncate(process.stderr.strip()),
    }


def evidence_for(workstream_id: str) -> dict[str, Any]:
    if workstream_id == "cross_rosetta_foldx_ddg_backend":
        license_validation = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
        install_probe = load_json(AI_ROOT / "reports" / "pyrosetta_local_install_probe_report.json")
        install_validation = load_json(AI_ROOT / "reports" / "pyrosetta_local_install_probe_validation_report.json")
        executable_probe = load_json(AI_ROOT / "reports" / "ddg_executable_probe_report.json")
        smoke = load_json(AI_ROOT / "reports" / "pyrosetta_physical_smoke_bootstrap_report.json")
        runtime_receipt = load_json(AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json")
        ddg_readiness = load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json")
        consumption = load_json(AI_ROOT / "reports" / "ddg_model_consumption_contract_report.json")
        physics_state = consumption.get("physics_ddg_state") if isinstance(consumption.get("physics_ddg_state"), dict) else {}
        pyrosetta_license_row = next(
            (
                row
                for row in license_validation.get("records") or []
                if isinstance(row, dict) and row.get("review_item_id") == "foreign_tool:pyrosetta"
            ),
            {},
        )
        checks = {
            "pyrosetta_license_decision_valid": int(license_validation.get("valid_rows") or 0) > 0,
            "pyrosetta_local_evaluation_approved": pyrosetta_license_row.get("valid") is True and pyrosetta_license_row.get("approved_for_local_evaluation") is True,
            "pyrosetta_install_import_succeeded": (install_probe.get("import_probe") or {}).get("succeeded") is True,
            "pyrosetta_install_validation_success": install_validation.get("success") is True,
            "pyrosetta_module_available": executable_probe.get("pyrosetta_module_available") is True,
            "pyrosetta_smoke_passed": smoke.get("physical_smoke_passed") is True,
            "pyrosetta_smoke_artifacts_complete": len(smoke.get("smoke_artifact_sha256") or {}) >= 5,
            "runtime_receipt_approved": int(runtime_receipt.get("approved_runtime_rows") or 0) > 0,
            "runtime_receipt_physics_fail_closed": runtime_receipt.get("physics_ddg_ready") is False,
            "ddg_backend_executable_ready": ddg_readiness.get("executable_ddg_backend_ready") is True,
            "ddg_consumption_physics_fail_closed": physics_state.get("physics_ddg_ready") is False,
            "safe_for_model_claim_remains_false": consumption.get("safe_for_model_claim") is False and ddg_readiness.get("safe_for_model_claim") is False,
        }
        return {
            "evidence_type": "top_tier_pyrosetta_physical_ddg_runtime_receipt",
            "checks": checks,
            "metrics": {
                "approved_runtime_rows": runtime_receipt.get("approved_runtime_rows"),
                "ready_backend_count": ddg_readiness.get("ready_backend_count"),
                "pyrosetta_smoke_artifact_count": len(smoke.get("smoke_artifact_sha256") or {}),
                "rosetta_executable_found": executable_probe.get("rosetta_executable_found"),
                "foldx_executable_found": executable_probe.get("foldx_executable_found"),
                "pyrosetta_module_available": executable_probe.get("pyrosetta_module_available"),
            },
        }
    if workstream_id == "p0_kwb_wet_lab_feedback":
        authorization = load_json(
            AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json"
        )
        preflight = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_preflight_report.json")
        feedback_intake = load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json")
        semantic_guard = load_json(AI_ROOT / "reports" / "feedback_training_import_semantic_guard_report.json")
        checks = {
            "authorization_rows_gt_0": int(authorization.get("authorization_rows") or 0) > 0,
            "authorized_candidate_rows_gt_0": int(authorization.get("authorized_candidate_rows") or 0) > 0,
            "preflight_rows_gt_0": int(preflight.get("preflight_rows") or 0) > 0,
            "numeric_training_import_eligible_gt_0": int(
                semantic_guard.get("numeric_training_import_eligible") or 0
            ) > 0,
            "experiment_feedback_intake_valid": feedback_intake.get("success") is True
            or int(feedback_intake.get("invalid_rows") or 0) == 0,
            "strict_training_rows_remain_zero": count_jsonl(
                AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
            )
            == 0,
            "claim_rows_remain_zero": count_jsonl(
                AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_claim_eligible.jsonl"
            )
            == 0,
            "safe_for_model_claim_remains_false": semantic_guard.get("safe_for_model_claim") is False
            and preflight.get("safe_for_model_claim") is not True,
        }
        return {
            "evidence_type": "top_tier_kwb_wet_lab_feedback_receipt",
            "checks": checks,
            "metrics": {
                "authorization_rows": authorization.get("authorization_rows"),
                "authorized_candidate_rows": authorization.get("authorized_candidate_rows"),
                "preflight_rows": preflight.get("preflight_rows"),
                "numeric_training_import_eligible": semantic_guard.get("numeric_training_import_eligible"),
                "experiment_feedback_valid_rows": feedback_intake.get("valid_rows"),
                "strict_training_rows": count_jsonl(
                    AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
                ),
            },
        }
    if workstream_id == "p0_reviewed_structure_graph":
        feature_report = load_json(AI_ROOT / "reports" / "reviewed_structure_graph_feature_report.json")
        validation = load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json")
        feature_path = AI_ROOT / "datasets" / "features" / "reviewed_structure_graph_features.jsonl"
        strict_table = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
        checks = {
            "reviewed_structure_graph_ready": validation.get("ready_for_coordinate_feature_use") is True,
            "valid_graph_rows_gt_0": int(validation.get("valid_rows") or 0) > 0,
            "invalid_graph_rows_eq_0": int(validation.get("invalid_rows") or 0) == 0,
            "feature_table_exists": feature_path.exists(),
            "feature_table_rows_gt_0": count_jsonl(feature_path) > 0,
            "strict_training_rows_remain_zero": count_jsonl(strict_table) == 0,
            "safe_for_model_claim_remains_false": validation.get("safe_for_model_claim") is False
            and feature_report.get("safe_for_model_claim") is False,
        }
        return {
            "evidence_type": "top_tier_reviewed_structure_graph_receipt",
            "checks": checks,
            "metrics": {
                "graph_rows": feature_report.get("graph_rows"),
                "valid_graph_rows": validation.get("valid_rows"),
                "feature_table_rows": count_jsonl(feature_path),
                "strict_training_rows": count_jsonl(strict_table),
            },
        }
    return {"evidence_type": "unknown", "checks": {"known_workstream": False}, "metrics": {}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build top-tier ready-to-verify receipts")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--receipts-output", type=Path, default=RECEIPTS_OUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    board = load_json(args.board)
    board_rows = [row for row in board.get("rows", []) if isinstance(row, dict)]
    ready_rows = [row for row in board_rows if row.get("status") == "started_ready_to_verify"]
    blocked_rows = [row for row in board_rows if row.get("status") == "started_blocked"]
    ready_ids = {str(row.get("workstream_id")) for row in ready_rows}
    blocked_ids = {str(row.get("workstream_id")) for row in blocked_rows}
    failures: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    created_at = datetime.now(timezone.utc).isoformat()

    unexpected_ready_ids = ready_ids - ALLOWED_READY_IDS
    if unexpected_ready_ids:
        failures.append({
            "check": "ready_to_verify_ids_within_top_tier_allowlist",
            "allowed": sorted(ALLOWED_READY_IDS),
            "unexpected": sorted(unexpected_ready_ids),
        })

    for row in sorted(ready_rows, key=lambda item: str(item.get("workstream_id") or "")):
        workstream_id = str(row.get("workstream_id"))
        commands = EXPECTED_READY_COMMANDS.get(workstream_id, [])
        command_results = [run_command(command) for command in commands] if workstream_id in ALLOWED_READY_IDS else []
        evidence = evidence_for(workstream_id)
        commands_ok = bool(command_results) and all(result.get("ok") for result in command_results)
        evidence_ok = all(bool(value) for value in (evidence.get("checks") or {}).values())
        receipts.append({
            "created_at": created_at,
            "local_only": True,
            "workstream_id": workstream_id,
            "title": row.get("title"),
            "source_status": row.get("status"),
            "verification_status": "verification_passed" if commands_ok and evidence_ok else "verification_failed",
            "commands_ok": commands_ok,
            "evidence_ok": evidence_ok,
            "command_results": command_results,
            "evidence": evidence,
            "completion_ready": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "blocked_lanes_executed": False,
            "policy": "Top-tier receipt verifies local evidence for an allowed ready-to-verify lane only; it is not a model-quality, release, production, license, or training approval.",
        })

    receipt_ids = {str(row.get("workstream_id")) for row in receipts}
    blocked_executed = bool(receipt_ids & blocked_ids)
    verification_passed = sum(1 for row in receipts if row.get("verification_status") == "verification_passed")
    command_rows = sum(len(row.get("command_results") or []) for row in receipts)
    all_commands_ok = all(result.get("ok") for row in receipts for result in (row.get("command_results") or []))
    all_evidence_ok = all(row.get("evidence_ok") for row in receipts)
    success = not failures and receipt_ids == ready_ids and all_commands_ok and all_evidence_ok and not blocked_executed

    write_jsonl(args.receipts_output, receipts)
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_board": str(args.board.relative_to(AI_ROOT)),
        "receipts": str(args.receipts_output.relative_to(AI_ROOT)),
        "allowed_ready_to_verify_workstreams": sorted(ALLOWED_READY_IDS),
        "board_ready_to_verify_workstreams": sorted(ready_ids),
        "board_blocked_workstreams": sorted(blocked_ids),
        "receipt_rows": len(receipts),
        "command_rows": command_rows,
        "verification_passed_workstreams": verification_passed,
        "verification_failed_workstreams": len(receipts) - verification_passed,
        "blocked_workstreams_not_executed": not blocked_executed,
        "all_commands_ok": all_commands_ok,
        "all_evidence_ok": all_evidence_ok,
        "success": success,
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Only top-tier board started_ready_to_verify lanes within the allowlist are executed. Blocked lanes remain blocked; no training, external install, production sync, or model-quality claim is approved.",
        "rows": receipts,
    }
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": success,
        "receipt_rows": len(receipts),
        "verification_passed_workstreams": verification_passed,
        "command_rows": command_rows,
        "output": str(args.report_output),
    }, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
