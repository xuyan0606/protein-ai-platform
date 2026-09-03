#!/usr/bin/env python3
"""Build a local readiness report for foreign protein-design tools."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from ddg_python_module_discovery import module_available


AI_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = AI_ROOT / "config" / "foreign_tool_registry.local.example.json"
OUT = AI_ROOT / "reports" / "foreign_tool_readiness_report.json"
ADAPTER_STUB_OUT = AI_ROOT / "prototype" / "external_tool_adapter_matrix.json"
LICENSE_REPORT = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"
RUNTIME_RECEIPT_REPORT = AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json"
PYROSETTA_INSTALL_PROBE = AI_ROOT / "reports" / "pyrosetta_local_install_probe_report.json"
PYROSETTA_SMOKE = AI_ROOT / "reports" / "pyrosetta_physical_smoke_bootstrap_report.json"
DDG_EXECUTABLE_PROBE = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
FOLDX_BOOTSTRAP = AI_ROOT / "reports" / "foldx_physical_smoke_bootstrap_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def status_from_parts(tool: dict[str, Any], install_ready: bool, license_ready: bool, runtime_ready: bool, data_ready: bool, model_weight_ready: bool) -> tuple[str, str]:
    license_gate = tool.get("license_gate")
    if license_gate == "non_commercial_or_restricted" or tool.get("commercial_status") == "restricted":
        status = "blocked_by_license"
    elif not install_ready:
        status = "not_installed"
    elif not license_ready:
        status = "blocked_by_license_review"
    elif not runtime_ready or not data_ready or not model_weight_ready:
        status = "blocked_by_runtime_or_data"
    else:
        status = "ready_for_local_evaluation"
    if status == "ready_for_local_evaluation":
        panel_status = "ready"
    elif status == "not_installed":
        panel_status = "not_installed"
    elif status == "blocked_by_license_review":
        panel_status = "license_review_required"
    else:
        panel_status = "restricted"
    return status, panel_status


def approved_local_eval(report: dict[str, Any], review_item_id: str) -> bool:
    record = license_record(report, review_item_id)
    return bool(record and record.get("valid") is True and record.get("approved_for_local_evaluation") is True)


def license_record(report: dict[str, Any], review_item_id: str) -> dict[str, Any] | None:
    for row in report.get("records") or []:
        if (
            isinstance(row, dict)
            and row.get("review_item_id") == review_item_id
        ):
            return row
    return None


def authorization_overlay(report: dict[str, Any], review_item_id: str) -> dict[str, Any]:
    record = license_record(report, review_item_id) or {}
    capabilities = record.get("capability_authorizations") if isinstance(record.get("capability_authorizations"), dict) else {}
    return {
        "authorization_source": record.get("authorization_source"),
        "authorization_status": record.get("authorization_status"),
        "verification_required": record.get("verification_required"),
        "verification_status": record.get("verification_status"),
        "capability_authorizations": {
            "commercial_evaluation": capabilities.get("commercial_evaluation", "pending"),
            "training_import": capabilities.get("training_import", "pending"),
            "customer_delivery": capabilities.get("customer_delivery", "pending"),
            "service_hosting": capabilities.get("service_hosting", "pending"),
            "publication": capabilities.get("publication", "pending"),
        },
        "verified_license_clearance": record.get("authorization_status") == "verified",
    }


def with_pyrosetta_evidence(row: dict[str, Any], tool: dict[str, Any], evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if row.get("tool_id") != "pyrosetta":
        return row
    license_ready = approved_local_eval(evidence["license"], "foreign_tool:pyrosetta")
    install_probe = evidence["install_probe"]
    runtime_receipt = evidence["runtime_receipt"]
    smoke = evidence["smoke"]
    install_ready = bool(row.get("install_ready")) or ((install_probe.get("import_probe") or {}).get("succeeded") is True)
    runtime_ready = "pyrosetta" in set(runtime_receipt.get("backends_with_approved_runtime") or [])
    data_ready = smoke.get("physical_smoke_passed") is True and bool(smoke.get("smoke_artifact_sha256"))
    model_weight_ready = bool(row.get("model_weight_ready", True))
    status, panel_status = status_from_parts(tool, install_ready, license_ready, runtime_ready, data_ready, model_weight_ready)
    updated = dict(row)
    updated.update({
        **authorization_overlay(evidence["license"], "foreign_tool:pyrosetta"),
        "status": status,
        "panel_status": panel_status,
        "ready_for_local_evaluation": status == "ready_for_local_evaluation",
        "install_ready": install_ready,
        "runtime_ready": runtime_ready,
        "license_ready": license_ready,
        "data_ready": data_ready,
        "pyrosetta_formal_license_decision": license_ready,
        "pyrosetta_import_probe_succeeded": (install_probe.get("import_probe") or {}).get("succeeded") is True,
        "pyrosetta_runtime_receipt_approved": runtime_ready,
        "pyrosetta_physical_smoke_passed": data_ready,
        "allowed_use": "Platform workflows are not non-commercial-only. Current PyRosetta component authorization is self_attested for technical evaluation and computed-feature validation; verified delivery/release still require license-scope evidence.",
        "forbidden_use": "Do not represent self_attested authorization as verified clearance; do not mark customer delivery, service hosting, publication, release, or training-label import ready without separate verified gates.",
    })
    return updated


def with_rosetta_evidence(row: dict[str, Any], tool: dict[str, Any], evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if row.get("tool_id") != "rosetta":
        return row
    license_ready = approved_local_eval(evidence["license"], "foreign_tool:rosetta")
    probe = evidence["ddg_probe"]
    install_ready = bool(row.get("install_ready")) or probe.get("rosetta_executable_found") is True
    runtime_ready = bool(row.get("runtime_ready")) or any(
        backend.get("backend") == "rosetta" and backend.get("executable_with_version_probe_succeeded") is True
        for backend in probe.get("backend_rows") or []
        if isinstance(backend, dict)
    )
    data_ready = bool(row.get("data_ready"))
    model_weight_ready = bool(row.get("model_weight_ready", True))
    status, panel_status = status_from_parts(tool, install_ready, license_ready, runtime_ready, data_ready, model_weight_ready)
    updated = dict(row)
    updated.update({
        **authorization_overlay(evidence["license"], "foreign_tool:rosetta"),
        "status": status,
        "panel_status": panel_status,
        "ready_for_local_evaluation": status == "ready_for_local_evaluation",
        "install_ready": install_ready,
        "runtime_ready": runtime_ready,
        "license_ready": license_ready,
        "data_ready": data_ready,
        "rosetta_formal_license_decision": license_ready,
        "rosetta_executable_probe_found": probe.get("rosetta_executable_found") is True,
        "rosetta_version_probe_succeeded": runtime_ready,
        "allowed_use": "Platform workflows are not non-commercial-only. Current Rosetta component authorization is self_attested for technical runtime probe and smoke preparation; verified delivery/release still require license-scope evidence.",
        "forbidden_use": "Do not represent self_attested authorization as verified clearance; do not mark customer delivery, service hosting, publication, release, or training-label import ready without separate verified gates.",
    })
    return updated


def with_foldx_evidence(row: dict[str, Any], tool: dict[str, Any], evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if row.get("tool_id") != "foldx":
        return row
    license_ready = approved_local_eval(evidence["license"], "foreign_tool:foldx")
    probe = evidence["ddg_probe"]
    bootstrap = evidence["foldx_bootstrap"]
    install_ready = bool(row.get("install_ready")) or probe.get("foldx_executable_found") is True
    runtime_ready = bool(row.get("runtime_ready")) or bootstrap.get("help_probe_succeeded") is True
    data_ready = bool(row.get("data_ready"))
    model_weight_ready = bool(row.get("model_weight_ready", True))
    status, panel_status = status_from_parts(tool, install_ready, license_ready, runtime_ready, data_ready, model_weight_ready)
    executables = dict(row.get("executables") or {})
    configured_paths = dict(row.get("configured_executable_paths") or {})
    probe_path = None
    for backend in probe.get("backend_rows") or []:
        if isinstance(backend, dict) and backend.get("backend") == "foldx":
            probe_path = backend.get("executable_path") or backend.get("configured_executable_path")
            if not probe_path:
                candidates = [
                    candidate
                    for candidate in backend.get("candidate_executables") or []
                    if isinstance(candidate, dict) and candidate.get("found") is True
                ]
                preferred = next(
                    (candidate for candidate in candidates if candidate.get("version_probe_succeeded") is True),
                    candidates[0] if candidates else {},
                )
                probe_path = preferred.get("path")
            break
    if probe_path:
        executables["foldx"] = str(probe_path)
        configured_paths.setdefault("foldx", str(probe_path))
    missing_executables = [name for name, path in executables.items() if not path]
    updated = dict(row)
    updated.update({
        **authorization_overlay(evidence["license"], "foreign_tool:foldx"),
        "status": status,
        "panel_status": panel_status,
        "ready_for_local_evaluation": status == "ready_for_local_evaluation",
        "install_ready": install_ready,
        "runtime_ready": runtime_ready,
        "license_ready": license_ready,
        "data_ready": data_ready,
        "executables": executables,
        "configured_executable_paths": configured_paths,
        "missing_executables": missing_executables,
        "foldx_formal_license_decision": license_ready,
        "foldx_executable_probe_found": probe.get("foldx_executable_found") is True,
        "foldx_help_probe_succeeded": bootstrap.get("help_probe_succeeded") is True,
        "foldx_physical_smoke_passed": bootstrap.get("physical_smoke_passed") is True,
        "allowed_use": "Current FoldX component authorization is self_attested for local technical probing and personal-learning evaluation; verified delivery/release still require license-scope evidence.",
        "forbidden_use": "Do not represent self_attested FoldX authorization as verified clearance; do not mark customer delivery, service hosting, publication, release, or training-label import ready without separate verified gates.",
    })
    return updated


def readiness_for(tool: dict[str, Any]) -> dict[str, Any]:
    configured_paths = tool.get("required_executable_paths", {}) or {}
    executables = {
        name: (
            str(AI_ROOT / configured_paths[name])
            if configured_paths.get(name) and (AI_ROOT / configured_paths[name]).exists()
            else shutil.which(name)
        )
        for name in tool.get("required_executables", [])
    }
    modules = {
        name: module_available(name)
        for name in tool.get("required_python_modules", [])
    }
    missing_executables = [name for name, path in executables.items() if not path]
    missing_modules = [name for name, present in modules.items() if not present]
    license_gate = tool.get("license_gate")
    install_ready = not missing_executables and not missing_modules
    runtime_ready = bool(tool.get("mac_local_ready") or tool.get("linux_cpu_ready") or tool.get("linux_cuda_ready"))
    license_ready = bool(tool.get("license_ready", license_gate == "commercial_evaluation_allowed"))
    data_ready = bool(tool.get("data_ready", not tool.get("data_requirements")))
    model_weight_ready = bool(tool.get("model_weight_ready", True))
    status, panel_status = status_from_parts(tool, install_ready, license_ready, runtime_ready, data_ready, model_weight_ready)
    return {
        "tool_id": tool.get("tool_id"),
        "display_name": tool.get("display_name"),
        "category": tool.get("category"),
        "recommended_priority": tool.get("recommended_priority"),
        "license_gate": license_gate,
        "license_type": tool.get("license_type"),
        "license_evidence_url": tool.get("license_evidence_url"),
        "weight_terms_url": tool.get("weight_terms_url"),
        "commercial_status": tool.get("commercial_status"),
        "status": status,
        "panel_status": panel_status,
        "ready_for_local_evaluation": status == "ready_for_local_evaluation",
        "install_ready": install_ready,
        "runtime_ready": runtime_ready,
        "license_ready": license_ready,
        "data_ready": data_ready,
        "model_weight_ready": model_weight_ready,
        "runtime_requirements": tool.get("runtime_requirements", {}),
        "data_requirements": tool.get("data_requirements", []),
        "mac_local_ready": tool.get("mac_local_ready"),
        "linux_cpu_ready": tool.get("linux_cpu_ready"),
        "linux_cuda_ready": tool.get("linux_cuda_ready"),
        "executables": executables,
        "configured_executable_paths": configured_paths,
        "python_modules": modules,
        "missing_executables": missing_executables,
        "missing_python_modules": missing_modules,
        "expected_outputs": tool.get("expected_outputs", []),
        "allowed_use": tool.get("allowed_use"),
        "forbidden_use": tool.get("forbidden_use"),
        "references": tool.get("references", []),
    }


def adapter_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": "KWB-EnzymeDesigner",
        "surface": "external_tool_adapter_matrix",
        "local_only": True,
        "policy": "Adapters are evidence providers. Missing or restricted tools fail closed.",
        "adapters": [
            {
                "tool_id": row["tool_id"],
                "category": row["category"],
                "adapter_status": row["status"],
                "panel_status": row["panel_status"],
                "license_gate": row["license_gate"],
                "install_ready": row["install_ready"],
                "runtime_ready": row["runtime_ready"],
                "license_ready": row["license_ready"],
                "authorization_status": row.get("authorization_status"),
                "verification_required": row.get("verification_required"),
                "capability_authorizations": row.get("capability_authorizations"),
                "data_ready": row["data_ready"],
                "model_weight_ready": row["model_weight_ready"],
                "expected_outputs": row["expected_outputs"],
                "kwb_usage": (
                    "blocked"
                    if row["status"] != "ready_for_local_evaluation"
                    else "local_evaluation_only"
                ),
            }
            for row in sorted(rows, key=lambda item: (item.get("recommended_priority") or 999, item["tool_id"]))
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build foreign tool readiness report")
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--adapter-matrix", type=Path, default=ADAPTER_STUB_OUT)
    args = parser.parse_args()

    registry = load_json(args.registry)
    tools = registry.get("tools", [])
    evidence = {
        "license": load_json(LICENSE_REPORT),
        "runtime_receipt": load_json(RUNTIME_RECEIPT_REPORT),
        "install_probe": load_json(PYROSETTA_INSTALL_PROBE),
        "smoke": load_json(PYROSETTA_SMOKE),
        "ddg_probe": load_json(DDG_EXECUTABLE_PROBE),
        "foldx_bootstrap": load_json(FOLDX_BOOTSTRAP),
    }
    rows = [
        with_foldx_evidence(with_rosetta_evidence(with_pyrosetta_evidence(readiness_for(tool), tool, evidence), tool, evidence), tool, evidence)
        for tool in tools
    ]
    counts: dict[str, int] = {}
    panel_counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        panel_counts[row["panel_status"]] = panel_counts.get(row["panel_status"], 0) + 1
    report = {
        "local_only": True,
        "registry": str(args.registry),
        "evidence_inputs": {
            "license_report": str(LICENSE_REPORT),
            "runtime_receipt_report": str(RUNTIME_RECEIPT_REPORT),
            "pyrosetta_install_probe": str(PYROSETTA_INSTALL_PROBE),
            "pyrosetta_smoke": str(PYROSETTA_SMOKE),
            "ddg_executable_probe": str(DDG_EXECUTABLE_PROBE),
            "foldx_bootstrap": str(FOLDX_BOOTSTRAP),
        },
        "tool_rows": len(rows),
        "status_counts": counts,
        "panel_status_counts": panel_counts,
        "ready_for_local_evaluation": sum(1 for row in rows if row["ready_for_local_evaluation"]),
        "split_readiness_counts": {
            "install_ready": sum(1 for row in rows if row["install_ready"]),
            "runtime_ready": sum(1 for row in rows if row["runtime_ready"]),
            "license_ready": sum(1 for row in rows if row["license_ready"]),
            "data_ready": sum(1 for row in rows if row["data_ready"]),
            "model_weight_ready": sum(1 for row in rows if row["model_weight_ready"]),
        },
        "authorization_status_counts": {
            "self_attested": sum(1 for row in rows if row.get("authorization_status") == "self_attested"),
            "pending_verification": sum(1 for row in rows if row.get("authorization_status") == "pending_verification"),
            "verified": sum(1 for row in rows if row.get("authorization_status") == "verified"),
        },
        "verified_license_clearance_tools": [
            row["tool_id"]
            for row in rows
            if row.get("verified_license_clearance") is True
        ],
        "self_attested_capability_tools": {
            capability: [
                row["tool_id"]
                for row in rows
                if row.get("authorization_status") == "self_attested"
                and (row.get("capability_authorizations") or {}).get(capability) == "allowed"
            ]
            for capability in ["commercial_evaluation", "training_import", "customer_delivery", "service_hosting", "publication"]
        },
        "commercial_evaluation_allowed_tools": [
            row["tool_id"]
            for row in rows
            if row["license_gate"] == "commercial_evaluation_allowed"
        ],
        "license_review_required_tools": [
            row["tool_id"]
            for row in rows
            if row["license_gate"] == "license_review_required"
        ],
        "restricted_tools": [
            row["tool_id"]
            for row in rows
            if row["license_gate"] == "non_commercial_or_restricted"
        ],
        "tools": rows,
        "policy": "No external model is invoked here. Platform policy is not non-commercial-only; readiness separates technical install/runtime from self_attested versus verified component authorization and delivery/release gates.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.adapter_matrix.parent.mkdir(parents=True, exist_ok=True)
    args.adapter_matrix.write_text(json.dumps(adapter_matrix(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "tool_rows": report["tool_rows"],
        "ready_for_local_evaluation": report["ready_for_local_evaluation"],
        "status_counts": report["status_counts"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
