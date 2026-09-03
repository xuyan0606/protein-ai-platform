#!/usr/bin/env python3
"""Build fail-closed readiness for Rosetta/PyRosetta/FoldX ddG backends."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_backend_config import ddg_config_display_name, default_ddg_config_path
from ddg_python_module_discovery import module_available


AI_ROOT = Path(__file__).resolve().parents[1]
CONFIG = default_ddg_config_path()
FOREIGN = AI_ROOT / "reports" / "foreign_tool_readiness_report.json"
THERMOMPNN = AI_ROOT / "reports" / "thermompnn_local_source_report.json"
THERMOMPNN_SMOKE = AI_ROOT / "reports" / "thermompnn_venus15b_smoke_report.json"
DDG_EXECUTABLE_PROBE = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
RUNTIME_RECEIPT_VALIDATION = AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json"
RUNTIME_RECEIPT_STATUS = AI_ROOT / "datasets" / "governance" / "ddg_backend_runtime_receipt_status.jsonl"
PHYSICAL_SMOKE_HARNESS = AI_ROOT / "reports" / "ddg_physical_smoke_harness_report.json"
STRUCTURE_MAPPINGS = AI_ROOT / "datasets" / "curation" / "structure_chain_mappings_curated.jsonl"
OUT = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"
CACHE_OUT = AI_ROOT / "cache" / "advanced_features" / "ddg_stability" / "backend_readiness.json"
PHYSICAL_DDG_BACKENDS = {"rosetta", "pyrosetta", "foldx"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tool_rows(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("tool_id")): row
        for row in report.get("tools", [])
        if isinstance(row, dict) and row.get("tool_id")
    }


def rows_by_backend(rows: Any, row_key: str = "backends") -> dict[str, dict[str, Any]]:
    if isinstance(rows, dict):
        rows = rows.get(row_key, [])
    return {
        str(row.get("backend")): row
        for row in rows
        if isinstance(row, dict) and row.get("backend")
    }


def receipt_status_by_backend(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return rows_by_backend(rows, row_key="")


def receipt_ready(backend_id: str, receipt_validation: dict[str, Any], receipt_status: dict[str, dict[str, Any]]) -> bool:
    status = receipt_status.get(backend_id, {})
    if status:
        return (
            bool(status.get("valid"))
            and bool(status.get("approved_for_physical_ddg_runtime"))
            and bool(status.get("ready_for_ddg_smoke"))
            and status.get("receipt_decision") == "approved_runtime_ready"
        )
    return backend_id in set(receipt_validation.get("backends_with_approved_runtime") or [])


def smoke_artifact_ready(backend_id: str, smoke_harness: dict[str, Any], thermompnn_smoke: dict[str, Any]) -> bool:
    if backend_id == "thermompnn":
        return bool((thermompnn_smoke.get("outputs") or {}).get("ready_as_proxy_ddg_artifact"))
    smoke_row = rows_by_backend(smoke_harness).get(backend_id, {})
    return bool(smoke_row.get("physical_smoke_passed")) and bool(smoke_row.get("receipt_smoke_artifact_present"))


def technical_probe_ready(
    backend_id: str,
    executable_probe: dict[str, Any],
    install_ready: bool,
    runtime_ready: bool,
    thermompnn: dict[str, Any],
) -> bool:
    if backend_id == "thermompnn":
        return bool(thermompnn.get("ready_for_local_inference") or thermompnn.get("ready_as_ddg_proxy_backend"))
    probe_row = rows_by_backend(executable_probe, row_key="backend_rows").get(backend_id, {})
    if probe_row:
        return bool(probe_row.get("ready_for_ddg_execution"))
    return bool(install_ready and runtime_ready)


def backend_readiness(
    backend_id: str,
    config: dict[str, Any],
    foreign_tools: dict[str, dict[str, Any]],
    reviewed_structure_rows: int,
    thermompnn: dict[str, Any],
    thermompnn_smoke: dict[str, Any],
    executable_probe: dict[str, Any],
    receipt_validation: dict[str, Any],
    receipt_status: dict[str, dict[str, Any]],
    smoke_harness: dict[str, Any],
) -> dict[str, Any]:
    backend_cfg = (config.get("backends") or {}).get(backend_id) or {}
    tool = foreign_tools.get(backend_cfg.get("tool_id") or backend_id, {})
    enabled = bool(backend_cfg.get("enabled"))
    required_modules = tool.get("python_modules") or {}
    if backend_id == "pyrosetta":
        required_modules = {"pyrosetta": module_available("pyrosetta")}
    module_ready = all(bool(value) for value in required_modules.values())
    if backend_id == "pyrosetta" and not required_modules:
        module_ready = module_available("pyrosetta")
    executables = tool.get("executables") or {}
    executable_ready = all(bool(path) for path in executables.values()) if executables else True
    if backend_id == "foldx" and not executables:
        executable_ready = shutil.which("foldx") is not None
    if backend_id == "rosetta" and not executables:
        executable_ready = bool(shutil.which("cartesian_ddg") or shutil.which("rosetta_scripts"))
    if backend_id == "thermompnn" and not required_modules:
        module_ready = bool(thermompnn.get("runtime_dependency_ready"))
    install_ready = bool(tool.get("install_ready")) or (module_ready and executable_ready)
    license_ready = bool(tool.get("license_ready"))
    runtime_ready = bool(tool.get("runtime_ready"))
    model_weight_ready = bool(tool.get("model_weight_ready", True))
    if backend_id == "thermompnn":
        install_ready = bool(thermompnn.get("runtime_dependency_ready"))
        runtime_ready = bool(tool.get("runtime_ready")) and bool(thermompnn.get("runtime_dependency_ready"))
        model_weight_ready = bool(thermompnn.get("model_weight_ready"))
        data_ready = (
            bool(tool.get("data_ready"))
            and bool(thermompnn.get("source_license_model_ready"))
            and bool((thermompnn_smoke.get("outputs") or {}).get("ready_as_proxy_ddg_artifact"))
        )
    else:
        data_ready = bool(tool.get("data_ready")) and reviewed_structure_rows > 0
    blockers = []
    if not enabled:
        blockers.append(f"backend disabled in {ddg_config_display_name()}")
    if not tool:
        blockers.append("backend not registered in foreign tool readiness")
    if not install_ready:
        blockers.append("runtime package or executable not installed")
    if not license_ready:
        blockers.append("license review not approved")
    if not runtime_ready:
        blockers.append("local runtime not marked ready")
    if not data_ready:
        blockers.append("reviewed structure/mutation data gate not ready for this backend")
    if not model_weight_ready:
        blockers.append("model weights not ready")
    technical_ready = technical_probe_ready(backend_id, executable_probe, install_ready, runtime_ready, thermompnn)
    runtime_receipt_required = backend_id in PHYSICAL_DDG_BACKENDS
    runtime_receipt_ready = receipt_ready(backend_id, receipt_validation, receipt_status) if runtime_receipt_required else False
    bootstrap_smoke_ready = smoke_artifact_ready(backend_id, smoke_harness, thermompnn_smoke)
    production_data_ready = data_ready
    current_ready = (
        enabled
        and license_ready
        and model_weight_ready
        and technical_ready
        and bootstrap_smoke_ready
        and production_data_ready
        and (runtime_receipt_ready if runtime_receipt_required else True)
    )
    ready = current_ready
    return {
        "backend": backend_id,
        "tool_id": backend_cfg.get("tool_id") or backend_id,
        "enabled": enabled,
        "technical_probe_ready": technical_ready,
        "runtime_receipt_required": runtime_receipt_required,
        "runtime_receipt_ready": runtime_receipt_ready,
        "bootstrap_smoke_artifact_ready": bootstrap_smoke_ready,
        "production_data_ready": production_data_ready,
        "current_execution_ready": current_ready,
        "ready_for_execution": ready,
        "install_ready": install_ready,
        "license_ready": license_ready,
        "runtime_ready": runtime_ready,
        "data_ready": data_ready,
        "model_weight_ready": model_weight_ready,
        "executables": executables,
        "python_modules": required_modules,
        "expected_outputs": tool.get("expected_outputs", []),
        "blockers": blockers,
        "license_gate": tool.get("license_gate"),
        "license_type": tool.get("license_type"),
        "commercial_status": tool.get("commercial_status"),
        "references": tool.get("references", []),
        "source_license_model_ready": thermompnn.get("source_license_model_ready") if backend_id == "thermompnn" else None,
        "runtime_dependency_ready": thermompnn.get("runtime_dependency_ready") if backend_id == "thermompnn" else None,
        "local_source_report": "reports/thermompnn_local_source_report.json" if backend_id == "thermompnn" else None,
        "smoke_result_report": "reports/thermompnn_venus15b_smoke_report.json" if backend_id == "thermompnn" else None,
        "smoke_artifact_ready": bool((thermompnn_smoke.get("outputs") or {}).get("ready_as_proxy_ddg_artifact")) if backend_id == "thermompnn" else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ddG backend readiness")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--foreign-readiness", type=Path, default=FOREIGN)
    parser.add_argument("--thermompnn-readiness", type=Path, default=THERMOMPNN)
    parser.add_argument("--thermompnn-smoke", type=Path, default=THERMOMPNN_SMOKE)
    parser.add_argument("--executable-probe", type=Path, default=DDG_EXECUTABLE_PROBE)
    parser.add_argument("--runtime-receipt-validation", type=Path, default=RUNTIME_RECEIPT_VALIDATION)
    parser.add_argument("--runtime-receipt-status", type=Path, default=RUNTIME_RECEIPT_STATUS)
    parser.add_argument("--physical-smoke-harness", type=Path, default=PHYSICAL_SMOKE_HARNESS)
    parser.add_argument("--structure-mappings", type=Path, default=STRUCTURE_MAPPINGS)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--cache-output", type=Path, default=CACHE_OUT)
    args = parser.parse_args()

    config = load_json(args.config)
    foreign = load_json(args.foreign_readiness)
    thermompnn = load_json(args.thermompnn_readiness)
    thermompnn_smoke = load_json(args.thermompnn_smoke)
    executable_probe = load_json(args.executable_probe)
    receipt_validation = load_json(args.runtime_receipt_validation)
    receipt_status = receipt_status_by_backend(load_jsonl(args.runtime_receipt_status))
    smoke_harness = load_json(args.physical_smoke_harness)
    mappings = load_jsonl(args.structure_mappings)
    reviewed_structure_rows = sum(1 for row in mappings if row.get("usable_for_coordinate_features"))
    foreign_tools = tool_rows(foreign)
    backend_ids = list(config.get("backend_priority") or ["rosetta", "pyrosetta", "foldx", "thermompnn"])
    backends = [
        backend_readiness(
            backend_id,
            config,
            foreign_tools,
            reviewed_structure_rows,
            thermompnn,
            thermompnn_smoke,
            executable_probe,
            receipt_validation,
            receipt_status,
            smoke_harness,
        )
        for backend_id in backend_ids
    ]
    executable_backend_ids = {"rosetta", "pyrosetta", "foldx"}
    executable_ready = [row for row in backends if row["backend"] in executable_backend_ids and row["ready_for_execution"]]
    proxy_ready = [row for row in backends if row["backend"] == "thermompnn" and row["ready_for_execution"]]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "adapter_integrated": True,
        "config": str(args.config),
        "foreign_readiness": str(args.foreign_readiness),
        "thermompnn_smoke": str(args.thermompnn_smoke),
        "executable_probe": str(args.executable_probe),
        "runtime_receipt_validation": str(args.runtime_receipt_validation),
        "runtime_receipt_status": str(args.runtime_receipt_status),
        "physical_smoke_harness": str(args.physical_smoke_harness),
        "reviewed_structure_rows": reviewed_structure_rows,
        "negative_ddg_is_stabilizing": bool(config.get("negative_ddg_is_stabilizing", True)),
        "thresholds_kcal_mol": config.get("thresholds_kcal_mol"),
        "backends": backends,
        "technical_probe_ready": any(row["technical_probe_ready"] for row in backends),
        "runtime_receipt_ready": any(row["runtime_receipt_ready"] for row in backends),
        "bootstrap_smoke_artifact_ready": any(row["bootstrap_smoke_artifact_ready"] for row in backends),
        "production_data_ready": any(row["production_data_ready"] for row in backends),
        "current_execution_ready": any(row["current_execution_ready"] for row in backends),
        "technical_probe_ready_count": sum(1 for row in backends if row["technical_probe_ready"]),
        "runtime_receipt_ready_count": sum(1 for row in backends if row["runtime_receipt_ready"]),
        "bootstrap_smoke_artifact_ready_count": sum(1 for row in backends if row["bootstrap_smoke_artifact_ready"]),
        "production_data_ready_count": sum(1 for row in backends if row["production_data_ready"]),
        "current_execution_ready_count": sum(1 for row in backends if row["current_execution_ready"]),
        "ready_backend_count": sum(1 for row in backends if row["ready_for_execution"]),
        "executable_ddg_backend_ready": bool(executable_ready),
        "proxy_ddg_backend_ready": bool(proxy_ready),
        "one_ddg_backend_ready": bool(executable_ready or proxy_ready),
        "artifact_requirements": config.get("artifact_requirements", []),
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "policy": "Adapter contract is integrated, but ddG values require a licensed ready backend and auditable output artifacts.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.cache_output.parent.mkdir(parents=True, exist_ok=True)
    args.cache_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "adapter_integrated": report["adapter_integrated"],
        "ready_backend_count": report["ready_backend_count"],
        "executable_ddg_backend_ready": report["executable_ddg_backend_ready"],
        "proxy_ddg_backend_ready": report["proxy_ddg_backend_ready"],
        "one_ddg_backend_ready": report["one_ddg_backend_ready"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
