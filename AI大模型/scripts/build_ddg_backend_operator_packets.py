#!/usr/bin/env python3
"""Build operator packets for physical ddG backend unlocks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_backend_config import ddg_config_display_name, default_ddg_config_path

AI_ROOT = Path(__file__).resolve().parents[1]
CONFIG = default_ddg_config_path()
READINESS = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"
PROBE = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
OUTPUT = AI_ROOT / "datasets" / "governance" / "ddg_backend_operator_packets.jsonl"
REPORT = AI_ROOT / "reports" / "ddg_backend_operator_packet_report.json"

PHYSICAL_BACKENDS = ["rosetta", "pyrosetta", "foldx"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def backend_by_id(readiness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("backend")): row
        for row in readiness.get("backends", [])
        if isinstance(row, dict) and row.get("backend")
    }


def probe_by_id(probe: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("backend")): row
        for row in probe.get("backend_rows", [])
        if isinstance(row, dict) and row.get("backend")
    }


def install_action(backend: str) -> dict[str, Any]:
    if backend == "rosetta":
        return {
            "install_source": "RosettaCommons licensed distribution",
            "operator_note": "Download/install only after license review. Add cartesian_ddg and rosetta_scripts to PATH or config.",
            "expected_probe_targets": ["cartesian_ddg", "rosetta_scripts", "rosetta_scripts.default.macosclangrelease"],
            "network_or_license_required": True,
        }
    if backend == "pyrosetta":
        return {
            "install_source": "PyRosetta licensed package/channel",
            "operator_note": "Install only after PyRosetta license review. Python module must import in the selected runtime.",
            "expected_probe_targets": ["pyrosetta Python module"],
            "network_or_license_required": True,
        }
    return {
        "install_source": "FoldX licensed binary distribution",
        "operator_note": "Download/install only after FoldX license review. Add foldx/FoldX executable to PATH or config.",
        "expected_probe_targets": ["foldx", "FoldX"],
        "network_or_license_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ddG backend operator packets")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--readiness", type=Path, default=READINESS)
    parser.add_argument("--probe", type=Path, default=PROBE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    config = load_json(args.config)
    readiness = load_json(args.readiness)
    probe = load_json(args.probe)
    ready_by_backend = backend_by_id(readiness)
    probe_rows = probe_by_id(probe)
    backend_config = config.get("backends") or {}

    packets: list[dict[str, Any]] = []
    for order, backend in enumerate(PHYSICAL_BACKENDS, start=1):
        ready_row = ready_by_backend.get(backend, {})
        probe_row = probe_rows.get(backend, {})
        cfg = backend_config.get(backend) or {}
        packets.append({
            "packet_id": f"ddg-backend-unlock-{backend}-001",
            "execution_order": order,
            "workstream": "physical_ddg_backend_unlock",
            "backend": backend,
            "status": "started_blocked",
            "enabled_in_config": bool(cfg.get("enabled")),
            "ready_for_execution_now": bool(ready_row.get("ready_for_execution")),
            "install_ready": bool(ready_row.get("install_ready")),
            "license_ready": bool(ready_row.get("license_ready")),
            "runtime_ready": bool(ready_row.get("runtime_ready")),
            "data_ready": bool(ready_row.get("data_ready")),
            "model_weight_ready": bool(ready_row.get("model_weight_ready", True)),
            "probe_observation": {
                "executable_found": probe_row.get("executable_found"),
                "python_module_available": probe_row.get("python_module_available"),
                "ready_for_ddg_execution": probe_row.get("ready_for_ddg_execution"),
                "blockers": probe_row.get("blockers") or [],
            },
            "readiness_blockers": ready_row.get("blockers") or [],
            "license_gate": ready_row.get("license_gate") or "license_review_required",
            "license_type": ready_row.get("license_type"),
            "commercial_status": ready_row.get("commercial_status"),
            "references": ready_row.get("references") or [],
            "operator_install_action": install_action(backend),
            "config_target": ddg_config_display_name(args.config),
            "license_decision_input": "datasets/governance/external_license_review_decisions.jsonl",
            "license_validator_command": "python3 scripts/validate_external_license_review_decisions.py",
            "runtime_receipt_input": "datasets/governance/ddg_backend_runtime_receipts.local.jsonl",
            "runtime_receipt_template": "datasets/governance/ddg_backend_runtime_receipts.template.jsonl",
            "runtime_receipt_validator_command": "python3 scripts/validate_ddg_backend_runtime_receipts.py",
            "local_runtime_discovery_report": "reports/ddg_local_runtime_discovery_report.json",
            "local_runtime_discovery_command": "python3 scripts/build_ddg_local_runtime_discovery.py",
            "runtime_probe_command": "python3 scripts/build_ddg_executable_probe.py",
            "readiness_command": "python3 scripts/build_ddg_backend_readiness.py",
            "execution_plan_command": "python3 scripts/build_ddg_backend_execution_plan.py",
            "smoke_artifact_requirements": config.get("artifact_requirements") or [],
            "ddg_direction_policy": {
                "negative_ddg_is_stabilizing": bool(config.get("negative_ddg_is_stabilizing", True)),
                "thresholds_kcal_mol": config.get("thresholds_kcal_mol"),
            },
            "completion_condition": "License decision approved, backend enabled, executable/module found, runtime/data gates ready, then a separate ddG smoke job produces auditable artifacts.",
            "requires_human_input": True,
            "completion_ready": False,
            "safe_for_model_claim": False,
            "policy": "Operator packet only; not a license approval, not an installation, not a ddG run, not model-quality readiness, and not release approval.",
        })

    write_jsonl(args.output, packets)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet_rows": len(packets),
        "physical_backend_rows": len(PHYSICAL_BACKENDS),
        "ready_for_execution_now_rows": sum(1 for row in packets if row["ready_for_execution_now"]),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(packets),
        "rosetta_packet_ready": any(row["backend"] == "rosetta" and row["ready_for_execution_now"] for row in packets),
        "pyrosetta_packet_ready": any(row["backend"] == "pyrosetta" and row["ready_for_execution_now"] for row in packets),
        "foldx_packet_ready": any(row["backend"] == "foldx" and row["ready_for_execution_now"] for row in packets),
        "output": str(args.output),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Packets define the manual unlock path for physical ddG backends; they do not approve licenses or execute Rosetta/PyRosetta/FoldX.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "packet_rows": report["packet_rows"],
        "ready_for_execution_now_rows": report["ready_for_execution_now_rows"],
        "completion_ready_rows": report["completion_ready_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
