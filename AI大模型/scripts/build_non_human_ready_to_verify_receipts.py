#!/usr/bin/env python3
"""Execute ready-to-verify non-human construction lanes and write receipts."""

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
BOARD = AI_ROOT / "reports" / "non_human_construction_board.json"
RECEIPTS_OUT = AI_ROOT / "datasets" / "governance" / "non_human_ready_to_verify_receipts.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "non_human_ready_to_verify_receipt_report.json"

EXPECTED_READY_COMMANDS = {
    "nhc_ddg_physics_backend": [
        "python3 scripts/build_ddg_backend_readiness.py",
        "python3 scripts/build_ddg_backend_execution_plan.py",
        "python3 scripts/validate_ddg_backend_operator_packets.py",
    ],
    "nhc_msa_conservation_production": [
        "python3 scripts/build_msa_runtime_readiness.py",
        "python3 scripts/validate_msa_conservation_cache.py",
        "python3 scripts/build_strict_msa_site_features.py",
    ],
    "nhc_structure_gnn_features": [
        "python3 scripts/build_reviewed_structure_graph_features.py",
        "python3 scripts/validate_reviewed_structure_graph_features.py",
    ],
    "nhc_data_lake_cache_governance": [
        "python3 scripts/build_data_lake_manifest.py",
        "python3 scripts/build_provenance_graph_report.py",
        "python3 scripts/build_governance_readiness.py",
    ],
}
ALLOWED_READY_IDS = set(EXPECTED_READY_COMMANDS)

P136_OUTPUTS = {
    "datasets/governance/non_human_ready_to_verify_receipts.jsonl",
    "datasets/governance/non_human_ready_to_verify_receipt_status.jsonl",
    "reports/non_human_ready_to_verify_receipt_report.json",
    "reports/non_human_ready_to_verify_receipt_validation_report.json",
}


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


def missing_artifacts_excluding_current_outputs() -> list[str]:
    manifest = load_json(AI_ROOT / "reports" / "data_lake_manifest.json")
    missing = []
    for artifact in manifest.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        path = str(artifact.get("path") or "")
        if not artifact.get("exists") and path not in P136_OUTPUTS:
            missing.append(path)
    return sorted(missing)


def evidence_for(workstream_id: str) -> dict[str, Any]:
    if workstream_id == "nhc_ddg_physics_backend":
        readiness = load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json")
        runtime_receipt = load_json(AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json")
        smoke = load_json(AI_ROOT / "reports" / "pyrosetta_physical_smoke_bootstrap_report.json")
        operator_packet_validation = load_json(AI_ROOT / "reports" / "ddg_backend_operator_packet_validation_report.json")
        checks = {
            "executable_ddg_backend_ready": readiness.get("executable_ddg_backend_ready") is True,
            "pyrosetta_runtime_receipt_approved": int(runtime_receipt.get("approved_runtime_rows") or 0) > 0,
            "runtime_receipt_physics_fail_closed": runtime_receipt.get("physics_ddg_ready") is False,
            "pyrosetta_smoke_passed": smoke.get("physical_smoke_passed") is True,
            "pyrosetta_smoke_artifacts_complete": len(smoke.get("smoke_artifact_sha256") or {}) >= 5,
            "pyrosetta_operator_ready_for_execution": int(operator_packet_validation.get("ready_for_execution_now_rows") or 0) > 0,
            "safe_for_model_claim_remains_false": readiness.get("safe_for_model_claim") is False and runtime_receipt.get("safe_for_model_claim") is False,
        }
        return {
            "evidence_type": "pyrosetta_physical_ddg_runtime_feature_receipt",
            "checks": checks,
            "metrics": {
                "ready_backend_count": readiness.get("ready_backend_count"),
                "approved_runtime_rows": runtime_receipt.get("approved_runtime_rows"),
                "pyrosetta_smoke_artifact_count": len(smoke.get("smoke_artifact_sha256") or {}),
                "operator_valid_rows": operator_packet_validation.get("valid_status_rows"),
                "operator_ready_for_execution_now_rows": operator_packet_validation.get("ready_for_execution_now_rows"),
            },
        }
    if workstream_id == "nhc_msa_conservation_production":
        runtime = load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json")
        cache = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
        strict_features = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_strict_msa_site_features.jsonl"
        checks = {
            "msa_runtime_ready": runtime.get("runtime_ready") is True,
            "homolog_database_ready": bool((runtime.get("homolog_database") or {}).get("ready")),
            "msa_cache_ready": cache.get("ready") is True,
            "msa_cache_valid_rows_gt_0": int(cache.get("valid_rows") or 0) > 0,
            "msa_cache_invalid_rows_eq_0": int(cache.get("invalid_rows") or 0) == 0,
            "strict_msa_feature_table_exists": strict_features.exists(),
            "strict_msa_feature_rows_gt_0": count_jsonl(strict_features) > 0,
        }
        return {
            "evidence_type": "msa_conservation_feature_receipt",
            "checks": checks,
            "metrics": {
                "msa_target_rows": runtime.get("target_rows"),
                "msa_cache_valid_rows": cache.get("valid_rows"),
                "strict_msa_feature_rows": count_jsonl(strict_features),
            },
        }
    if workstream_id == "nhc_structure_gnn_features":
        graph = load_json(AI_ROOT / "reports" / "reviewed_structure_graph_feature_report.json")
        validation = load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json")
        feature_path = AI_ROOT / "datasets" / "features" / "reviewed_structure_graph_features.jsonl"
        checks = {
            "reviewed_structure_graph_ready": validation.get("ready_for_coordinate_feature_use") is True,
            "valid_graph_rows_gt_0": int(validation.get("valid_rows") or 0) > 0,
            "invalid_graph_rows_eq_0": int(validation.get("invalid_rows") or 0) == 0,
            "feature_table_exists": feature_path.exists(),
            "feature_table_rows_gt_0": count_jsonl(feature_path) > 0,
            "safe_for_model_claim_remains_false": validation.get("safe_for_model_claim") is False and graph.get("safe_for_model_claim") is False,
        }
        return {
            "evidence_type": "structure_graph_feature_receipt",
            "checks": checks,
            "metrics": {
                "graph_rows": graph.get("graph_rows"),
                "valid_graph_rows": validation.get("valid_rows"),
                "feature_table_rows": count_jsonl(feature_path),
            },
        }
    if workstream_id == "nhc_data_lake_cache_governance":
        local_release = load_json(AI_ROOT / "reports" / "local_release_manifest.json")
        governance = load_json(AI_ROOT / "reports" / "governance_readiness_report.json")
        provenance = load_json(AI_ROOT / "reports" / "provenance_graph_report.json")
        non_p136_missing = missing_artifacts_excluding_current_outputs()
        checks = {
            "data_lake_manifest_has_no_non_p136_missing_artifacts": not non_p136_missing,
            "local_release_missing_artifacts_empty_or_only_current_outputs": all(
                path in P136_OUTPUTS for path in (local_release.get("missing_artifacts") or [])
            ),
            "provenance_ready": bool((local_release.get("readiness_summary") or {}).get("provenance_ready")),
            "provenance_graph_exists": bool(provenance.get("entity_count")),
            "governance_report_exists": bool(governance),
            "release_ready_remains_false": local_release.get("release_ready") is False,
        }
        return {
            "evidence_type": "data_governance_receipt",
            "checks": checks,
            "metrics": {
                "non_p136_missing_artifacts": len(non_p136_missing),
                "artifact_count": local_release.get("artifact_count"),
                "provenance_entity_count": provenance.get("entity_count"),
            },
        }
    return {"evidence_type": "unknown", "checks": {"known_workstream": False}, "metrics": {}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build non-human ready-to-verify receipts")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--receipts-output", type=Path, default=RECEIPTS_OUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    board = load_json(args.board)
    rows = [row for row in board.get("rows", []) if isinstance(row, dict)]
    ready_rows = [row for row in rows if row.get("status") == "started_ready_to_verify"]
    blocked_rows = [row for row in rows if row.get("status") == "started_blocked"]
    receipts: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    created_at = datetime.now(timezone.utc).isoformat()

    ready_ids = {str(row.get("workstream_id")) for row in ready_rows}
    unexpected_ready_ids = ready_ids - ALLOWED_READY_IDS
    if unexpected_ready_ids:
        failures.append({
            "check": "ready_to_verify_ids_within_allowlist",
            "allowed": sorted(ALLOWED_READY_IDS),
            "unexpected": sorted(unexpected_ready_ids),
        })

    for row in sorted(ready_rows, key=lambda item: int(item.get("execution_order") or 0)):
        workstream_id = str(row.get("workstream_id"))
        expected_commands = EXPECTED_READY_COMMANDS.get(workstream_id, [])
        commands = [str(command) for command in row.get("safe_local_commands") or []]
        if commands != expected_commands:
            failures.append({"check": "safe_local_commands_match_allowlist", "workstream_id": workstream_id})
            command_results = []
        else:
            command_results = [run_command(command) for command in commands]
        evidence = evidence_for(workstream_id)
        commands_ok = all(result.get("ok") for result in command_results)
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
            "safe_for_model_claim": False,
            "release_ready": False,
            "blocked_lanes_executed": False,
            "policy": "Receipt verifies local ready-to-verify commands and evidence only; it is not a model-quality, release, production, license, or ordering approval.",
        })

    blocked_ids = {str(row.get("workstream_id")) for row in blocked_rows}
    receipt_ids = {str(row.get("workstream_id")) for row in receipts}
    blocked_executed = bool(receipt_ids & blocked_ids)
    verification_passed = sum(1 for row in receipts if row.get("verification_status") == "verification_passed")
    command_rows = sum(len(row.get("command_results") or []) for row in receipts)
    all_commands_ok = all(result.get("ok") for row in receipts for result in (row.get("command_results") or []))
    all_evidence_ok = all(row.get("evidence_ok") for row in receipts)
    success = not failures and len(receipts) == len(ready_ids) and all_commands_ok and all_evidence_ok and not blocked_executed

    write_jsonl(args.receipts_output, receipts)
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_board": str(args.board.relative_to(AI_ROOT)),
        "receipts": str(args.receipts_output.relative_to(AI_ROOT)),
        "allowed_ready_to_verify_workstreams": sorted(ALLOWED_READY_IDS),
        "board_ready_to_verify_workstreams": sorted(ready_ids),
        "receipt_rows": len(receipts),
        "command_rows": command_rows,
        "verification_passed_workstreams": verification_passed,
        "verification_failed_workstreams": len(receipts) - verification_passed,
        "blocked_workstreams_not_executed": not blocked_executed,
        "all_commands_ok": all_commands_ok,
        "all_evidence_ok": all_evidence_ok,
        "success": success,
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Only board started_ready_to_verify lanes within the allowlist are executed. Blocked lanes remain blocked; no external install, production sync, or model-quality claim is approved.",
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
