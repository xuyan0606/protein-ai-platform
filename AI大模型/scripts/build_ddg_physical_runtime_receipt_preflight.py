#!/usr/bin/env python3
"""Build fail-closed preflight rows for physical ddG runtime receipts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
READINESS = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"
OPERATOR_REPORT = AI_ROOT / "reports" / "ddg_backend_operator_packet_report.json"
DISCOVERY_REPORT = AI_ROOT / "reports" / "ddg_local_runtime_discovery_report.json"
RUNTIME_RECEIPTS = AI_ROOT / "datasets" / "governance" / "ddg_backend_runtime_receipts.local.jsonl"
OPERATOR_PACKETS = AI_ROOT / "datasets" / "governance" / "ddg_backend_operator_packets.jsonl"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json"
EXECUTABLE_PROBE = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
OUTPUT_JSONL = AI_ROOT / "datasets" / "governance" / "ddg_physical_runtime_receipt_preflight.jsonl"
OUTPUT_REPORT = AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight_report.json"
OUTPUT_MD = AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight.md"

PHYSICAL_BACKENDS = ["rosetta", "pyrosetta", "foldx"]
PROHIBITED_ACTIONS = [
    "do_not_install_or_enable_unapproved_rosetta_pyrosetta_or_foldx",
    "do_not_write_unreviewed_formal_runtime_receipt",
    "do_not_execute_unreceipted_rosetta_pyrosetta_or_foldx",
    "do_not_import_computed_ddg_as_training_label",
    "do_not_set_model_or_release_claims_from_runtime_smoke",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def rows_by_backend(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("backend")): row
        for row in rows
        if isinstance(row, dict) and row.get("backend")
    }


def receipt_rows_by_backend(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {backend: [] for backend in PHYSICAL_BACKENDS}
    for row in rows:
        backend = str(row.get("backend") or "")
        if backend in result:
            result[backend].append(row)
    return result


def readiness_by_backend(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return rows_by_backend([
        row for row in report.get("backends", []) if isinstance(row, dict)
    ])


def expected_install_targets(backend: str, ready_row: dict[str, Any], packet: dict[str, Any]) -> list[str]:
    action = packet.get("operator_install_action") or {}
    targets = action.get("expected_probe_targets") or []
    if targets:
        return [str(target) for target in targets]
    if backend == "pyrosetta":
        return ["pyrosetta Python module"]
    executables = ready_row.get("executables") or {}
    return [str(name) for name in executables] or (["foldx", "FoldX"] if backend == "foldx" else [])


def observed_install_evidence(backend: str, ready_row: dict[str, Any], packet: dict[str, Any], receipts: list[dict[str, Any]]) -> dict[str, Any]:
    probe = packet.get("probe_observation") or {}
    receipt_install_paths = [row.get("install_path") for row in receipts if row.get("install_path")]
    receipt_executable_paths = [
        path
        for row in receipts
        for path in (row.get("executable_paths") or [])
        if path
    ]
    receipt_modules = [row.get("python_module") for row in receipts if row.get("python_module")]
    if backend == "pyrosetta":
        return {
            "evidence_type": "python_module",
            "expected": expected_install_targets(backend, ready_row, packet),
            "python_module_available": probe.get("python_module_available"),
            "receipt_python_modules": receipt_modules,
            "receipt_install_paths": receipt_install_paths,
        }
    return {
        "evidence_type": "install_path_or_executable_path",
        "expected": expected_install_targets(backend, ready_row, packet),
        "executable_found": probe.get("executable_found"),
        "receipt_install_paths": receipt_install_paths,
        "receipt_executable_paths": receipt_executable_paths,
    }


def missing_install_items(backend: str, install_evidence: dict[str, Any]) -> list[str]:
    if backend == "pyrosetta":
        missing = []
        if not install_evidence.get("python_module_available"):
            missing.append("pyrosetta_module_available")
        if not install_evidence.get("receipt_python_modules"):
            missing.append("runtime_receipt_python_module")
        if not install_evidence.get("receipt_install_paths"):
            missing.append("runtime_receipt_install_path_or_environment")
        return missing
    missing = []
    if not install_evidence.get("executable_found"):
        missing.append("executable_found_on_path")
    if not install_evidence.get("receipt_install_paths"):
        missing.append("runtime_receipt_install_path")
    if not install_evidence.get("receipt_executable_paths"):
        missing.append("runtime_receipt_executable_paths")
    return missing


def latest_receipt_summary(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    approved = [
        row for row in receipts
        if row.get("receipt_decision") == "approved_runtime_ready"
        and row.get("approved_for_physical_ddg_runtime") is True
    ]
    return {
        "receipt_rows": len(receipts),
        "approved_runtime_receipt_rows": len(approved),
        "runtime_receipt_ids": [row.get("runtime_receipt_id") for row in receipts if row.get("runtime_receipt_id")],
        "decisions": [row.get("receipt_decision") for row in receipts if row.get("receipt_decision")],
        "missing": len(approved) == 0,
        "missing_evidence": [] if approved else ["approved_runtime_receipt"],
    }


def smoke_missing_items(artifact_requirements: list[Any], receipts: list[dict[str, Any]], ready_row: dict[str, Any]) -> list[str]:
    smoke_reviewed = any(row.get("smoke_plan_reviewed") is True for row in receipts)
    smoke_artifact_paths_present = any(row.get("smoke_artifact_paths") for row in receipts)
    smoke_artifact_sha256_present = any(row.get("smoke_artifact_sha256") for row in receipts)
    receipt_artifact_ready = smoke_artifact_paths_present and smoke_artifact_sha256_present
    smoke_ready = ready_row.get("smoke_artifact_ready") is True or receipt_artifact_ready
    missing = []
    if not smoke_reviewed:
        missing.append("runtime_receipt_smoke_plan_reviewed")
    if not smoke_artifact_paths_present:
        missing.append("runtime_receipt_smoke_artifact_paths")
    if not smoke_artifact_sha256_present:
        missing.append("runtime_receipt_smoke_artifact_sha256")
    if not smoke_ready:
        missing.extend(str(item) for item in artifact_requirements)
    return missing


def build_backend_row(
    backend: str,
    created_at: str,
    readiness_report: dict[str, Any],
    discovery_report: dict[str, Any],
    ready_row: dict[str, Any],
    packet: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    artifact_requirements = readiness_report.get("artifact_requirements") or []
    probe = packet.get("probe_observation") or {}
    install_evidence = observed_install_evidence(backend, ready_row, packet, receipts)
    install_missing = missing_install_items(backend, install_evidence)
    receipt_summary = latest_receipt_summary(receipts)
    license_missing = []
    if not ready_row.get("license_ready"):
        license_missing.append("approved_license_review")
    if not any(row.get("license_decision_reviewed") is True for row in receipts):
        license_missing.append("runtime_receipt_license_decision_reviewed")
    config_missing = []
    if not ready_row.get("enabled"):
        config_missing.append("backend_enabled_in_config")
    if not any(row.get("config_enabled_reviewed") is True for row in receipts):
        config_missing.append("runtime_receipt_config_enabled_reviewed")
    probe_missing = []
    if not probe.get("ready_for_ddg_execution"):
        probe_missing.append("ready_for_ddg_execution_probe")
    if not any(row.get("probe_evidence_reviewed") is True for row in receipts):
        probe_missing.append("runtime_receipt_probe_evidence_reviewed")
    if backend == "pyrosetta" and not probe.get("python_module_available"):
        probe_missing.append("pyrosetta_module_probe")
    if backend != "pyrosetta" and not probe.get("executable_found"):
        probe_missing.append("executable_probe")
    smoke_missing = smoke_missing_items(artifact_requirements, receipts, ready_row)

    missing_categories = [
        name
        for name, items in [
            ("license", license_missing),
            ("install_path_or_module", install_missing),
            ("config_enabled", config_missing),
            ("probe", probe_missing),
            ("smoke_artifact", smoke_missing),
            ("approved_runtime_receipt", receipt_summary["missing_evidence"]),
        ]
        if items
    ]
    evidence_complete = not any([
        license_missing,
        install_missing,
        config_missing,
        probe_missing,
        smoke_missing,
        receipt_summary["missing_evidence"],
    ])
    ready_to_submit_formal_receipt = evidence_complete
    ready_to_run_physical_ddg_smoke = evidence_complete and bool(ready_row.get("ready_for_execution"))
    return {
        "preflight_id": f"P145-ddg-physical-runtime-receipt-preflight-{backend}",
        "created_at": created_at,
        "backend": backend,
        "status": "blocked_missing_preflight_evidence" if missing_categories else "runtime_receipt_validated_ready",
        "fail_closed": True,
        "ready_to_write_formal_runtime_receipt": ready_to_submit_formal_receipt,
        "ready_to_enable_config": evidence_complete and bool(ready_row.get("enabled")),
        "ready_to_run_physical_ddg_smoke": ready_to_run_physical_ddg_smoke,
        "ready_for_safe_pipeline_manifest": False,
        "license": {
            "ready": bool(ready_row.get("license_ready")),
            "license_gate": ready_row.get("license_gate") or packet.get("license_gate"),
            "license_type": ready_row.get("license_type") or packet.get("license_type"),
            "commercial_status": ready_row.get("commercial_status") or packet.get("commercial_status"),
            "license_decision_input": packet.get("license_decision_input"),
            "missing": bool(license_missing),
            "missing_evidence": license_missing,
        },
        "install_path_or_module": {
            "ready": bool(ready_row.get("install_ready")) and not install_missing,
            "install_ready_from_readiness": bool(ready_row.get("install_ready")),
            "evidence": install_evidence,
            "missing": bool(install_missing),
            "missing_evidence": install_missing,
        },
        "config_enabled": {
            "ready": bool(ready_row.get("enabled")) and not config_missing,
            "enabled_in_config": bool(ready_row.get("enabled")),
            "config_target": packet.get("config_target") or readiness_report.get("config"),
            "missing": bool(config_missing),
            "missing_evidence": config_missing,
        },
        "probe": {
            "ready": bool(probe.get("ready_for_ddg_execution")) and not probe_missing,
            "ready_for_ddg_execution": bool(probe.get("ready_for_ddg_execution")),
            "executable_found": probe.get("executable_found"),
            "python_module_available": probe.get("python_module_available"),
            "probe_blockers": probe.get("blockers") or [],
            "runtime_probe_command": packet.get("runtime_probe_command"),
            "missing": bool(probe_missing),
            "missing_evidence": probe_missing,
        },
        "smoke_artifact": {
            "ready": not smoke_missing,
            "required_artifacts": artifact_requirements,
            "smoke_artifact_ready_from_readiness": ready_row.get("smoke_artifact_ready"),
            "missing": bool(smoke_missing),
            "missing_evidence": smoke_missing,
        },
        "runtime_receipt": receipt_summary,
        "operator_packet": {
            "present": bool(packet),
            "packet_id": packet.get("packet_id"),
            "completion_ready": bool(packet.get("completion_ready")),
            "requires_human_input": bool(packet.get("requires_human_input", True)),
            "runtime_receipt_input": packet.get("runtime_receipt_input"),
            "runtime_receipt_template": packet.get("runtime_receipt_template"),
            "runtime_receipt_validator_command": packet.get("runtime_receipt_validator_command"),
        },
        "local_runtime_discovery": {
            "report": "reports/ddg_local_runtime_discovery_report.json",
            "candidate_rows": discovery_report.get("candidate_rows"),
            "ready_for_runtime_receipt_rows": discovery_report.get("ready_for_runtime_receipt_rows"),
            "ready_for_ddg_execution_rows": discovery_report.get("ready_for_ddg_execution_rows"),
            "rosetta_candidate_rows": discovery_report.get("rosetta_candidate_rows"),
            "foldx_candidate_rows": discovery_report.get("foldx_candidate_rows"),
            "pyrosetta_module_available": discovery_report.get("pyrosetta_module_available"),
        },
        "thermompnn_proxy_allowed_for_this_preflight": False,
        "physics_ddg_ready": ready_to_run_physical_ddg_smoke,
        "missing_categories": missing_categories,
        "readiness_blockers": ready_row.get("blockers") or packet.get("readiness_blockers") or [],
        "prohibited_actions": PROHIBITED_ACTIONS,
        "policy": "Preflight status only. A ready backend has reviewed license/config/probe/receipt/smoke evidence, but computed ddG remains non-training computational evidence and does not open model/release claims.",
    }


def md_bool_missing(row: dict[str, Any], key: str) -> str:
    section = row[key]
    return "missing" if section.get("missing") else "present"


def build_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# P145 ddG Physical Runtime Receipt Preflight",
        "",
        f"Created: `{report['created_at']}`",
        "",
        "This is a fail-closed scaffold. It does not install Rosetta/PyRosetta/FoldX, enable config, write a formal runtime receipt, run a physical ddG smoke job, or connect the safe pipeline/manifest.",
        "",
        "## Summary",
        "",
        f"- Physical backend rows: {report['physical_backend_rows']}",
        f"- Runtime receipt rows: {report['runtime_receipt_rows']}",
        f"- Missing license rows: {report['missing_license_rows']}",
        f"- Missing install path/module rows: {report['missing_install_path_or_module_rows']}",
        f"- Missing config-enabled rows: {report['missing_config_enabled_rows']}",
        f"- Missing probe rows: {report['missing_probe_rows']}",
        f"- Missing smoke artifact rows: {report['missing_smoke_artifact_rows']}",
        f"- Ready to write formal receipt rows: {report['ready_to_write_formal_runtime_receipt_rows']}",
        "",
        "| Backend | License | Install path/module | Config enabled | Probe | Smoke artifact | Status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {backend} | {license} | {install} | {config} | {probe} | {smoke} | {status} |".format(
                backend=row["backend"],
                license=md_bool_missing(row, "license"),
                install=md_bool_missing(row, "install_path_or_module"),
                config=md_bool_missing(row, "config_enabled"),
                probe=md_bool_missing(row, "probe"),
                smoke=md_bool_missing(row, "smoke_artifact"),
                status=row["status"],
            )
        )
    lines.extend(["", "## Backend Details", ""])
    for row in rows:
        lines.extend([
            f"### {row['backend']}",
            "",
            f"- License missing: {', '.join(row['license']['missing_evidence']) or 'none'}",
            f"- Install path/module missing: {', '.join(row['install_path_or_module']['missing_evidence']) or 'none'}",
            f"- Config enabled missing: {', '.join(row['config_enabled']['missing_evidence']) or 'none'}",
            f"- Probe missing: {', '.join(row['probe']['missing_evidence']) or 'none'}",
            f"- Smoke artifact missing: {', '.join(row['smoke_artifact']['missing_evidence']) or 'none'}",
            f"- Runtime receipt missing: {', '.join(row['runtime_receipt']['missing_evidence']) or 'none'}",
            "",
        ])
    lines.extend([
        "## Policy",
        "",
        "Blocked actions: " + ", ".join(PROHIBITED_ACTIONS),
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ddG physical runtime receipt preflight")
    parser.add_argument("--readiness", type=Path, default=READINESS)
    parser.add_argument("--operator-report", type=Path, default=OPERATOR_REPORT)
    parser.add_argument("--discovery-report", type=Path, default=DISCOVERY_REPORT)
    parser.add_argument("--runtime-receipts", type=Path, default=RUNTIME_RECEIPTS)
    parser.add_argument("--operator-packets", type=Path, default=OPERATOR_PACKETS)
    parser.add_argument("--receipt-validation", type=Path, default=RECEIPT_VALIDATION)
    parser.add_argument("--executable-probe", type=Path, default=EXECUTABLE_PROBE)
    parser.add_argument("--output-jsonl", type=Path, default=OUTPUT_JSONL)
    parser.add_argument("--output-report", type=Path, default=OUTPUT_REPORT)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    args = parser.parse_args()

    readiness_report = load_json(args.readiness)
    operator_report = load_json(args.operator_report)
    discovery_report = load_json(args.discovery_report)
    receipts = load_jsonl(args.runtime_receipts)
    operator_packets = load_jsonl(args.operator_packets)
    receipt_validation = load_json(args.receipt_validation)
    executable_probe = load_json(args.executable_probe)
    ready_rows = readiness_by_backend(readiness_report)
    packets = rows_by_backend(operator_packets)
    receipts_by_backend = receipt_rows_by_backend(receipts)
    created_at = datetime.now(timezone.utc).isoformat()

    rows = [
        build_backend_row(
            backend,
            created_at,
            readiness_report,
            discovery_report,
            ready_rows.get(backend, {}),
            packets.get(backend, {}),
            receipts_by_backend.get(backend, []),
        )
        for backend in PHYSICAL_BACKENDS
    ]
    ready_backend_names = [row["backend"] for row in rows if row["ready_to_run_physical_ddg_smoke"]]
    blocked_backend_names = [row["backend"] for row in rows if not row["ready_to_run_physical_ddg_smoke"]]
    all_physical_backends_ready = not blocked_backend_names
    report = {
        "created_at": created_at,
        "local_only": True,
        "task_id": "P145",
        "physical_backend_rows": len(rows),
        "runtime_receipt_rows": len(receipts),
        "operator_packet_rows": len(operator_packets),
        "operator_report_packet_rows": operator_report.get("packet_rows"),
        "runtime_discovery_candidate_rows": discovery_report.get("candidate_rows"),
        "runtime_discovery_ready_for_receipt_rows": discovery_report.get("ready_for_runtime_receipt_rows"),
        "runtime_discovery_ready_for_execution_rows": discovery_report.get("ready_for_ddg_execution_rows"),
        "runtime_receipt_validation_approved_rows": receipt_validation.get("approved_runtime_rows"),
        "runtime_receipt_validation_ready_for_smoke_rows": receipt_validation.get("ready_for_ddg_smoke_rows"),
        "executable_probe_physics_ddg_ready": executable_probe.get("physics_ddg_ready"),
        "executable_probe_version_probe_succeeded_rows": executable_probe.get("version_probe_succeeded_rows"),
        "missing_license_rows": sum(1 for row in rows if row["license"]["missing"]),
        "missing_install_path_or_module_rows": sum(1 for row in rows if row["install_path_or_module"]["missing"]),
        "missing_config_enabled_rows": sum(1 for row in rows if row["config_enabled"]["missing"]),
        "missing_probe_rows": sum(1 for row in rows if row["probe"]["missing"]),
        "missing_smoke_artifact_rows": sum(1 for row in rows if row["smoke_artifact"]["missing"]),
        "approved_runtime_receipt_rows": sum(row["runtime_receipt"]["approved_runtime_receipt_rows"] for row in rows),
        "ready_to_write_formal_runtime_receipt_rows": sum(1 for row in rows if row["ready_to_write_formal_runtime_receipt"]),
        "ready_to_enable_config_rows": sum(1 for row in rows if row["ready_to_enable_config"]),
        "ready_to_run_physical_ddg_smoke_rows": sum(1 for row in rows if row["ready_to_run_physical_ddg_smoke"]),
        "ready_for_safe_pipeline_manifest_rows": 0,
        "per_backend_physics_ready_rows": len(ready_backend_names),
        "ready_physical_backends": ready_backend_names,
        "blocked_physical_backends": blocked_backend_names,
        "all_physical_backends_ready": all_physical_backends_ready,
        "physical_ddg_lane_capability_status": "ready" if all_physical_backends_ready else "blocked",
        "physics_ddg_ready": all_physical_backends_ready,
        "executable_ddg_backend_ready": all_physical_backends_ready,
        "proxy_is_physics": False,
        "thermompnn_proxy_satisfies_physical_ddg_preflight": False,
        "safe_pipeline_manifest_connected": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "inputs": {
            "readiness": str(args.readiness),
            "operator_report": str(args.operator_report),
            "discovery_report": str(args.discovery_report),
            "runtime_receipts": str(args.runtime_receipts),
            "operator_packets": str(args.operator_packets),
            "receipt_validation": str(args.receipt_validation),
            "executable_probe": str(args.executable_probe),
        },
        "outputs": {
            "jsonl": str(args.output_jsonl),
            "report": str(args.output_report),
            "markdown": str(args.output_md),
        },
        "backends": rows,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "policy": "Fail-closed preflight status. PyRosetta may be ready only when reviewed license/config/probe/runtime receipt and checksumed smoke artifacts are present; model/release/training gates remain false.",
    }

    write_jsonl(args.output_jsonl, rows)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(build_markdown(report, rows), encoding="utf-8")
    print(json.dumps({
        "physical_backend_rows": report["physical_backend_rows"],
        "runtime_receipt_rows": report["runtime_receipt_rows"],
        "missing_license_rows": report["missing_license_rows"],
        "missing_install_path_or_module_rows": report["missing_install_path_or_module_rows"],
        "missing_config_enabled_rows": report["missing_config_enabled_rows"],
        "missing_probe_rows": report["missing_probe_rows"],
        "missing_smoke_artifact_rows": report["missing_smoke_artifact_rows"],
        "ready_to_write_formal_runtime_receipt_rows": report["ready_to_write_formal_runtime_receipt_rows"],
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
