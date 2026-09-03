#!/usr/bin/env python3
"""Validate physical ddG backend operator packets fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKETS = AI_ROOT / "datasets" / "governance" / "ddg_backend_operator_packets.jsonl"
STATUS = AI_ROOT / "datasets" / "governance" / "ddg_backend_operator_packet_status.jsonl"
REPORT = AI_ROOT / "reports" / "ddg_backend_operator_packet_validation_report.json"
EXPECTED_BACKENDS = {"rosetta", "pyrosetta", "foldx"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def exists_rel(rel: Any) -> bool:
    if not isinstance(rel, str) or not rel:
        return False
    path = Path(rel)
    if path.is_absolute():
        try:
            path.relative_to(AI_ROOT)
        except ValueError:
            return False
        return path.exists()
    return (AI_ROOT / path).exists()


def validate(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "packet_id",
        "execution_order",
        "workstream",
        "backend",
        "status",
        "enabled_in_config",
        "ready_for_execution_now",
        "license_ready",
        "runtime_ready",
        "data_ready",
        "probe_observation",
        "readiness_blockers",
        "license_gate",
        "operator_install_action",
        "config_target",
        "license_decision_input",
        "license_validator_command",
        "runtime_receipt_input",
        "runtime_receipt_template",
        "runtime_receipt_validator_command",
        "local_runtime_discovery_report",
        "local_runtime_discovery_command",
        "runtime_probe_command",
        "readiness_command",
        "execution_plan_command",
        "smoke_artifact_requirements",
        "ddg_direction_policy",
        "completion_condition",
        "requires_human_input",
        "completion_ready",
        "safe_for_model_claim",
        "policy",
    ]
    for field in required:
        if field not in row:
            errors.append(f"missing_{field}")
    backend = str(row.get("backend") or "")
    if backend not in EXPECTED_BACKENDS:
        errors.append("unexpected_backend")
    if row.get("workstream") != "physical_ddg_backend_unlock":
        errors.append("invalid_workstream")
    if row.get("status") != "started_blocked":
        errors.append("status_not_started_blocked")
    if row.get("requires_human_input") is not True:
        errors.append("requires_human_input_not_true")
    if row.get("completion_ready") is not False:
        errors.append("completion_ready_not_false")
    if row.get("safe_for_model_claim") is not False:
        errors.append("safe_for_model_claim_not_false")
    expected_ready_for_execution = all(
        row.get(field) is True
        for field in ("enabled_in_config", "license_ready", "runtime_ready", "data_ready")
    )
    if row.get("ready_for_execution_now") is not expected_ready_for_execution:
        errors.append("ready_for_execution_now_state_mismatch")
    if not exists_rel(row.get("config_target")):
        errors.append("config_target_missing")
    if not exists_rel(row.get("license_decision_input")):
        errors.append("license_decision_input_missing")
    if not exists_rel(row.get("runtime_receipt_input")):
        errors.append("runtime_receipt_input_missing")
    if not exists_rel(row.get("runtime_receipt_template")):
        errors.append("runtime_receipt_template_missing")
    if not exists_rel(row.get("local_runtime_discovery_report")):
        errors.append("local_runtime_discovery_report_missing")
    expected_commands = {
        "license_validator_command": "python3 scripts/validate_external_license_review_decisions.py",
        "runtime_receipt_validator_command": "python3 scripts/validate_ddg_backend_runtime_receipts.py",
        "local_runtime_discovery_command": "python3 scripts/build_ddg_local_runtime_discovery.py",
        "runtime_probe_command": "python3 scripts/build_ddg_executable_probe.py",
        "readiness_command": "python3 scripts/build_ddg_backend_readiness.py",
        "execution_plan_command": "python3 scripts/build_ddg_backend_execution_plan.py",
    }
    for field, expected in expected_commands.items():
        if row.get(field) != expected:
            errors.append(f"invalid_{field}")
    direction = row.get("ddg_direction_policy")
    if not isinstance(direction, dict) or direction.get("negative_ddg_is_stabilizing") is not True:
        errors.append("invalid_ddg_direction_policy")
    if not isinstance(row.get("smoke_artifact_requirements"), list) or not row.get("smoke_artifact_requirements"):
        errors.append("missing_smoke_artifact_requirements")
    install = row.get("operator_install_action")
    if not isinstance(install, dict) or install.get("network_or_license_required") is not True:
        errors.append("operator_install_action_not_license_gated")
    policy = str(row.get("policy") or "").lower()
    for phrase in ["not a license approval", "not an installation", "not a ddg run", "not model-quality readiness"]:
        if phrase not in policy:
            errors.append("policy_missing_fail_closed_language")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ddG backend operator packets")
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--status-output", type=Path, default=STATUS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    packets = load_jsonl(args.packets)
    status_rows: list[dict[str, Any]] = []
    errors = Counter()
    seen_backends = set()
    seen_packet_ids = set()
    duplicate_packet_ids = set()
    for row in packets:
        packet_id = str(row.get("packet_id"))
        if packet_id in seen_packet_ids:
            duplicate_packet_ids.add(packet_id)
        seen_packet_ids.add(packet_id)
        seen_backends.add(str(row.get("backend") or ""))
        row_errors = validate(row)
        errors.update(row_errors)
        status_rows.append({
            "record_type": "ddg_backend_operator_packet",
            "record_id": row.get("packet_id"),
            "backend": row.get("backend"),
            "valid": not row_errors,
            "ready_for_execution_now": bool(row.get("ready_for_execution_now")),
            "completion_ready": False,
            "requires_human_input": True,
            "errors": row_errors,
            "policy": "Validation only; not license approval, not installation, not ddG execution, and not model claim readiness.",
        })

    global_errors = []
    if seen_backends != EXPECTED_BACKENDS:
        errors.update({"backend_set_mismatch": 1})
        global_errors.append("backend_set_mismatch")
    if duplicate_packet_ids:
        errors.update({"duplicate_packet_id": len(duplicate_packet_ids)})
        global_errors.append("duplicate_packet_id")
    if len(packets) != len(EXPECTED_BACKENDS):
        errors.update({"packet_count_mismatch": 1})
        global_errors.append("packet_count_mismatch")
    if global_errors:
        for row in status_rows:
            row["valid"] = False
            row["errors"].extend(global_errors)

    valid_rows = sum(1 for row in status_rows if row["valid"])
    invalid_rows = len(status_rows) - valid_rows
    write_jsonl(args.status_output, status_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet_rows": len(packets),
        "status_rows": len(status_rows),
        "valid_status_rows": valid_rows,
        "invalid_status_rows": invalid_rows,
        "all_operator_packets_valid": invalid_rows == 0,
        "ready_for_execution_now_rows": sum(1 for row in status_rows if row["ready_for_execution_now"]),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "backends": sorted(seen_backends),
        "expected_backends": sorted(EXPECTED_BACKENDS),
        "error_counts": dict(errors),
        "status_output": str(args.status_output),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Valid operator packets only confirm local unlock instructions are coherent; physical ddG remains blocked until license/runtime/smoke gates pass.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status_rows": report["status_rows"],
        "valid_status_rows": report["valid_status_rows"],
        "invalid_status_rows": report["invalid_status_rows"],
        "ready_for_execution_now_rows": report["ready_for_execution_now_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
