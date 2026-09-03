#!/usr/bin/env python3
"""Build ddG backend failure diagnostic with proxy-not-physics separation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "ddg_backend_failure_diagnostic_report.json"

CONTROLLED_WAVE = AI_ROOT / "reports" / "enzyme_agent_controlled_execution_wave_report.json"
EXECUTABLE_PROBE = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
RUNTIME_DISCOVERY = AI_ROOT / "reports" / "ddg_local_runtime_discovery_report.json"
READINESS = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"
PREFLIGHT_JSON_CANDIDATES = [
    AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight.json",
    AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight_report.json",
]
PREFLIGHT_MD = AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight.md"
LICENSE_VALIDATION = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"
RECEIPT_VALIDATION = AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json"

PHYSICAL_BACKENDS = ["rosetta", "pyrosetta", "foldx"]
PROHIBITED_ACTIONS = [
    "do_not_install_or_download_unapproved_ddg_backends",
    "do_not_enable_unapproved_ddg_backend_config",
    "do_not_generate_fake_delta_delta_g_results",
    "do_not_write_unreviewed_formal_decision",
    "do_not_write_training_labels",
    "do_not_set_release_ready_true",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def first_existing_json(paths: list[Path]) -> tuple[Path | None, dict[str, Any]]:
    for path in paths:
        if path.exists():
            return path, load_json(path)
    return None, {}


def by_backend(rows: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if isinstance(row, dict) and row.get("backend"):
            result[str(row["backend"])] = row
    return result


def ddg_action_from_wave(report: dict[str, Any]) -> dict[str, Any]:
    for row in report.get("action_results") or []:
        if isinstance(row, dict) and row.get("action_id") == "act_ddg_proxy_or_physics":
            return row
    return {}


def command_summary(action: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for command in action.get("commands") or []:
        if not isinstance(command, dict):
            continue
        rows.append({
            "command": command.get("command"),
            "returncode": command.get("returncode"),
            "stdout": command.get("stdout"),
            "stderr": command.get("stderr"),
        })
    return rows


def bool_value(value: Any) -> bool:
    return value is True


def missing_input_names(input_presence: dict[str, bool]) -> list[str]:
    return sorted(name for name, present in input_presence.items() if not present)


def physical_backend_status(
    backend: str,
    readiness_row: dict[str, Any],
    probe_row: dict[str, Any],
    preflight_row: dict[str, Any],
) -> dict[str, Any]:
    ready_from_readiness = bool_value(readiness_row.get("ready_for_execution"))
    ready_from_probe = bool_value(probe_row.get("ready_for_ddg_execution"))
    ready_from_preflight = (
        bool_value(preflight_row.get("ready_to_write_formal_runtime_receipt"))
        and bool_value(preflight_row.get("ready_to_run_physical_ddg_smoke"))
    )
    ready_for_physics_ddg = ready_from_readiness and ready_from_probe and ready_from_preflight
    blockers = []
    blockers.extend(str(item) for item in readiness_row.get("blockers") or [])
    blockers.extend(str(item) for item in probe_row.get("blockers") or [])
    blockers.extend(str(item) for item in preflight_row.get("missing_categories") or [])
    blockers = sorted(set(blockers))
    return {
        "backend": backend,
        "backend_family": "physics_ddg",
        "ready_for_physics_ddg": ready_for_physics_ddg,
        "ready_from_readiness": ready_from_readiness,
        "ready_from_probe": ready_from_probe,
        "ready_from_receipt_preflight": ready_from_preflight,
        "enabled_in_config": bool_value(readiness_row.get("enabled")) or bool_value(probe_row.get("enabled_in_config")),
        "install_ready": bool_value(readiness_row.get("install_ready")),
        "license_ready": bool_value(readiness_row.get("license_ready")),
        "runtime_ready": bool_value(readiness_row.get("runtime_ready")),
        "data_ready": bool_value(readiness_row.get("data_ready")),
        "executable_found": probe_row.get("executable_found"),
        "python_module_available": probe_row.get("python_module_available"),
        "receipt_preflight_status": preflight_row.get("status"),
        "receipt_missing_categories": preflight_row.get("missing_categories") or [],
        "blockers": blockers,
    }


def thermompnn_status(readiness_rows: dict[str, dict[str, Any]], readiness_report: dict[str, Any]) -> dict[str, Any]:
    row = readiness_rows.get("thermompnn", {})
    proxy_ready = bool_value(readiness_report.get("proxy_ddg_backend_ready")) and bool_value(row.get("ready_for_execution"))
    return {
        "backend": "thermompnn",
        "backend_family": "proxy_ddg",
        "proxy_ready": proxy_ready,
        "proxy_ddg_backend_ready": bool_value(readiness_report.get("proxy_ddg_backend_ready")),
        "proxy_is_physics": False,
        "physics_ddg_ready": False,
        "ready_for_execution": bool_value(row.get("ready_for_execution")),
        "license_ready": bool_value(row.get("license_ready")),
        "runtime_ready": bool_value(row.get("runtime_ready")),
        "data_ready": bool_value(row.get("data_ready")),
        "model_weight_ready": bool_value(row.get("model_weight_ready")),
        "expected_outputs": row.get("expected_outputs") or [],
        "source_license_model_ready": row.get("source_license_model_ready"),
        "runtime_dependency_ready": row.get("runtime_dependency_ready"),
        "smoke_artifact_ready": row.get("smoke_artifact_ready"),
        "policy": "ThermoMPNN readiness is proxy/baseline evidence only and is not Rosetta/PyRosetta/FoldX physics ddG.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ddG backend failure diagnostic")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    controlled_wave = load_json(CONTROLLED_WAVE)
    executable_probe = load_json(EXECUTABLE_PROBE)
    runtime_discovery = load_json(RUNTIME_DISCOVERY)
    readiness = load_json(READINESS)
    preflight_path, preflight_json = first_existing_json(PREFLIGHT_JSON_CANDIDATES)
    preflight_md = load_text(PREFLIGHT_MD)
    license_validation = load_json(LICENSE_VALIDATION)
    receipt_validation = load_json(RECEIPT_VALIDATION)

    readiness_rows = by_backend(readiness.get("backends"))
    probe_rows = by_backend(executable_probe.get("backend_rows"))
    preflight_rows = by_backend(preflight_json.get("backends"))
    physical_statuses = [
        physical_backend_status(
            backend,
            readiness_rows.get(backend, {}),
            probe_rows.get(backend, {}),
            preflight_rows.get(backend, {}),
        )
        for backend in PHYSICAL_BACKENDS
    ]
    physical_ready_backend_count = sum(1 for row in physical_statuses if row["ready_for_physics_ddg"])

    readiness_executable_ready = bool_value(readiness.get("executable_ddg_backend_ready"))
    probe_executable_ready = bool_value(executable_probe.get("executable_ddg_backend_ready"))
    discovery_execution_rows = int(runtime_discovery.get("ready_for_ddg_execution_rows") or 0)
    preflight_ready_smoke_rows = int(preflight_json.get("ready_to_run_physical_ddg_smoke_rows") or 0)
    approved_runtime_receipt_rows = int(preflight_json.get("approved_runtime_receipt_rows") or 0)
    preflight_all_physical_backends_ready = bool_value(preflight_json.get("all_physical_backends_ready"))
    executable_ddg_backend_ready = (
        readiness_executable_ready
        and probe_executable_ready
        and discovery_execution_rows > 0
        and physical_ready_backend_count > 0
        and preflight_all_physical_backends_ready
    )
    physics_ddg_ready = (
        executable_ddg_backend_ready
        and approved_runtime_receipt_rows >= len(PHYSICAL_BACKENDS)
        and preflight_ready_smoke_rows >= len(PHYSICAL_BACKENDS)
    )
    thermompnn = thermompnn_status(readiness_rows, readiness)
    ddg_action = ddg_action_from_wave(controlled_wave)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "diagnostic_id": "ddg_backend_failed_receipt_proxy_not_physics_guard",
        "inputs": {
            "controlled_wave": rel(CONTROLLED_WAVE),
            "executable_probe": rel(EXECUTABLE_PROBE),
            "runtime_discovery": rel(RUNTIME_DISCOVERY),
            "readiness": rel(READINESS),
            "preflight_json": rel(preflight_path) if preflight_path else None,
            "preflight_md": rel(PREFLIGHT_MD) if PREFLIGHT_MD.exists() else None,
            "license_validation": rel(LICENSE_VALIDATION),
            "receipt_validation": rel(RECEIPT_VALIDATION),
        },
        "input_presence": {
            "controlled_wave": CONTROLLED_WAVE.exists(),
            "executable_probe": EXECUTABLE_PROBE.exists(),
            "runtime_discovery": RUNTIME_DISCOVERY.exists(),
            "readiness": READINESS.exists(),
            "preflight_json": preflight_path is not None,
            "preflight_md": bool(preflight_md),
            "license_validation": LICENSE_VALIDATION.exists(),
            "receipt_validation": RECEIPT_VALIDATION.exists(),
        },
        "ddg_action_receipt": {
            "action_id": "act_ddg_proxy_or_physics",
            "return_status": ddg_action.get("return_status"),
            "all_commands_passed": ddg_action.get("all_commands_passed"),
            "commands": command_summary(ddg_action),
            "diagnostic_status": "failed_physics_receipt_but_proxy_ready",
        },
        "source_flags": {
            "readiness_executable_ddg_backend_ready": readiness.get("executable_ddg_backend_ready"),
            "probe_executable_ddg_backend_ready": executable_probe.get("executable_ddg_backend_ready"),
            "runtime_discovery_ready_for_ddg_execution_rows": runtime_discovery.get("ready_for_ddg_execution_rows"),
            "preflight_ready_to_run_physical_ddg_smoke_rows": preflight_json.get("ready_to_run_physical_ddg_smoke_rows"),
            "preflight_approved_runtime_receipt_rows": preflight_json.get("approved_runtime_receipt_rows"),
            "preflight_all_physical_backends_ready": preflight_json.get("all_physical_backends_ready"),
            "preflight_physical_ddg_lane_capability_status": preflight_json.get("physical_ddg_lane_capability_status"),
            "license_approved_for_local_evaluation_rows": license_validation.get("approved_for_local_evaluation_rows"),
            "receipt_validation_approved_runtime_rows": receipt_validation.get("approved_runtime_rows"),
            "receipt_validation_ready_for_ddg_smoke_rows": receipt_validation.get("ready_for_ddg_smoke_rows"),
            "readiness_proxy_ddg_backend_ready": readiness.get("proxy_ddg_backend_ready"),
            "readiness_one_ddg_backend_ready": readiness.get("one_ddg_backend_ready"),
        },
        "executable_ddg_backend_ready": executable_ddg_backend_ready,
        "physics_ddg_ready": physics_ddg_ready,
        "physics_backend_ready_count": physical_ready_backend_count,
        "physics_backend_statuses": physical_statuses,
        "all_physical_backends_ready": preflight_all_physical_backends_ready,
        "physical_ddg_lane_capability_status": "ready" if physics_ddg_ready else "blocked",
        "physics_ddg_status": "ready" if physics_ddg_ready else "not_ready",
        "physics_ddg_not_ready_reason": (
            None if physics_ddg_ready else "Rosetta/PyRosetta/FoldX have no executable/module-ready, license-approved, "
            "config-reviewed, receipt-approved, smoke-ready physical ddG runtime."
        ),
        "physics_ddg_blocker_summary": {
            "missing_inputs": missing_input_names({
                "controlled_wave": CONTROLLED_WAVE.exists(),
                "executable_probe": EXECUTABLE_PROBE.exists(),
                "runtime_discovery": RUNTIME_DISCOVERY.exists(),
                "readiness": READINESS.exists(),
                "preflight_json": preflight_path is not None,
                "preflight_md": bool(preflight_md),
                "license_validation": LICENSE_VALIDATION.exists(),
                "receipt_validation": RECEIPT_VALIDATION.exists(),
            }),
            "license_approved_for_local_evaluation_rows": int(license_validation.get("approved_for_local_evaluation_rows") or 0),
            "runtime_receipt_approved_rows": int(receipt_validation.get("approved_runtime_rows") or 0),
            "runtime_receipt_ready_for_smoke_rows": int(receipt_validation.get("ready_for_ddg_smoke_rows") or 0),
            "executable_probe_version_probe_succeeded_rows": int(executable_probe.get("version_probe_succeeded_rows") or 0),
            "runtime_discovery_ready_for_execution_rows": discovery_execution_rows,
            "preflight_ready_to_run_physical_ddg_smoke_rows": preflight_ready_smoke_rows,
        },
        "thermompnn_proxy": thermompnn,
        "proxy_ddg_backend_ready": thermompnn["proxy_ready"],
        "proxy_is_physics": False,
        "ready_backend_count": readiness.get("ready_backend_count"),
        "one_ddg_backend_ready": readiness.get("one_ddg_backend_ready"),
        "receipt_failure": {
            "failed_receipt_diagnostic": not physics_ddg_ready,
            "formal_runtime_receipt_written": approved_runtime_receipt_rows > 0,
            "runtime_receipt_rows": preflight_json.get("runtime_receipt_rows"),
            "approved_runtime_receipt_rows": approved_runtime_receipt_rows,
            "receipt_validator_approved_runtime_rows": receipt_validation.get("approved_runtime_rows"),
            "receipt_validator_ready_for_smoke_rows": receipt_validation.get("ready_for_ddg_smoke_rows"),
            "ready_to_write_formal_runtime_receipt_rows": preflight_json.get("ready_to_write_formal_runtime_receipt_rows"),
            "missing_license_rows": preflight_json.get("missing_license_rows"),
            "missing_install_path_or_module_rows": preflight_json.get("missing_install_path_or_module_rows"),
            "missing_config_enabled_rows": preflight_json.get("missing_config_enabled_rows"),
            "missing_probe_rows": preflight_json.get("missing_probe_rows"),
            "missing_smoke_artifact_rows": preflight_json.get("missing_smoke_artifact_rows"),
        },
        "preflight_markdown_evidence": {
            "path": rel(PREFLIGHT_MD) if PREFLIGHT_MD.exists() else None,
            "read": bool(preflight_md),
            "line_count": len(preflight_md.splitlines()) if preflight_md else 0,
            "contains_fail_closed_scaffold_text": "fail-closed scaffold" in preflight_md,
        },
        "guardrails": {
            "safe_for_model_claim": False,
            "ready_for_model_claim": False,
            "safe_for_training_import": False,
            "release_ready": False,
            "ddg_fake_results_generated": False,
            "unapproved_config_enable_changed": False,
            "unreviewed_formal_decision_written": False,
            "formal_runtime_receipt_written": approved_runtime_receipt_rows > 0,
            "training_labels_written": False,
            "prohibited_actions": PROHIBITED_ACTIONS,
        },
        "policy": "Executable physics ddG requires Rosetta/PyRosetta/FoldX runtime evidence. A ready PyRosetta runtime remains computational physics evidence only; ThermoMPNN remains proxy-only and training/model/release gates stay false.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "executable_ddg_backend_ready": report["executable_ddg_backend_ready"],
        "physics_ddg_ready": report["physics_ddg_ready"],
        "proxy_ddg_backend_ready": report["proxy_ddg_backend_ready"],
        "proxy_is_physics": report["proxy_is_physics"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
