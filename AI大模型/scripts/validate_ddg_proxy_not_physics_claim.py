#!/usr/bin/env python3
"""Validate ThermoMPNN proxy readiness is not claimed as physics ddG."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = AI_ROOT / "reports" / "ddg_backend_failure_diagnostic_report.json"
OUT = AI_ROOT / "reports" / "ddg_proxy_not_physics_claim_validation_report.json"

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

PHYSICAL_BACKENDS = {"rosetta", "pyrosetta", "foldx"}


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


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def by_backend(rows: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if isinstance(row, dict) and row.get("backend"):
            result[str(row["backend"])] = row
    return result


def walk_dicts(value: Any, path: str = "$") -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        rows.append((path, value))
        for key, child in value.items():
            rows.extend(walk_dicts(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(walk_dicts(child, f"{path}[{index}]"))
    return rows


def contradictory_executable_physics_states(named_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    contradictions: list[dict[str, Any]] = []
    for report_name, report in named_reports.items():
        for path, row in walk_dicts(report):
            if row.get("executable_ddg_backend_ready") is False and row.get("physics_ddg_ready") is True:
                contradictions.append({
                    "report": report_name,
                    "path": path,
                    "executable_ddg_backend_ready": False,
                    "physics_ddg_ready": True,
                })
    return contradictions


def ddg_action_from_wave(report: dict[str, Any]) -> dict[str, Any]:
    for row in report.get("action_results") or []:
        if isinstance(row, dict) and row.get("action_id") == "act_ddg_proxy_or_physics":
            return row
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ddG proxy-not-physics claim guard")
    parser.add_argument("--diagnostic", type=Path, default=DIAGNOSTIC)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    diagnostic = load_json(args.diagnostic)
    controlled_wave = load_json(CONTROLLED_WAVE)
    executable_probe = load_json(EXECUTABLE_PROBE)
    runtime_discovery = load_json(RUNTIME_DISCOVERY)
    readiness = load_json(READINESS)
    preflight_path, preflight_json = first_existing_json(PREFLIGHT_JSON_CANDIDATES)
    preflight_md = load_text(PREFLIGHT_MD)
    license_validation = load_json(LICENSE_VALIDATION)

    failures: list[dict[str, Any]] = []
    warnings: list[str] = []
    checked_reports = {
        "diagnostic": diagnostic,
        "controlled_wave": controlled_wave,
        "executable_probe": executable_probe,
        "runtime_discovery": runtime_discovery,
        "readiness": readiness,
        "preflight_json": preflight_json,
        "license_validation": license_validation,
    }

    for name, report in checked_reports.items():
        if name != "preflight_json" and not report:
            failures.append({"check": "required_report_present", "report": name, "observed": False, "expected": True})
    if preflight_path is None and not preflight_md:
        failures.append({"check": "preflight_json_or_md_present", "observed": False, "expected": True})
    if preflight_path is None and preflight_md:
        warnings.append("preflight_json_missing_used_markdown_only")

    contradictions = contradictory_executable_physics_states(checked_reports)
    if contradictions:
        failures.append({
            "check": "no_executable_false_physics_true_state",
            "observed": contradictions,
            "expected": "No object may set executable_ddg_backend_ready=false with physics_ddg_ready=true.",
        })

    # The lane is intentionally stricter than single-backend readiness: proxy
    # readiness must never be promoted to physical ddG, and the physical lane
    # remains blocked until all required runtime receipts are present.
    fail_if(diagnostic.get("executable_ddg_backend_ready") is not False, failures, "diagnostic_executable_ddg_backend_ready_false", diagnostic.get("executable_ddg_backend_ready"), False)
    fail_if(diagnostic.get("physics_ddg_ready") is not False, failures, "diagnostic_physics_ddg_ready_false", diagnostic.get("physics_ddg_ready"), False)
    fail_if(readiness.get("executable_ddg_backend_ready") is not True, failures, "readiness_executable_ddg_backend_ready_true", readiness.get("executable_ddg_backend_ready"), True)
    fail_if(executable_probe.get("executable_ddg_backend_ready") is not True, failures, "probe_executable_ddg_backend_ready_true", executable_probe.get("executable_ddg_backend_ready"), True)
    fail_if(int(runtime_discovery.get("ready_for_ddg_execution_rows") or 0) != 1, failures, "runtime_discovery_ready_for_execution_one", runtime_discovery.get("ready_for_ddg_execution_rows"), 1)

    readiness_rows = by_backend(readiness.get("backends"))
    probe_rows = by_backend(executable_probe.get("backend_rows"))
    diagnostic_physics_rows = by_backend(diagnostic.get("physics_backend_statuses"))
    for backend in sorted(PHYSICAL_BACKENDS):
        ready_row = readiness_rows.get(backend, {})
        probe_row = probe_rows.get(backend, {})
        diag_row = diagnostic_physics_rows.get(backend, {})
        expected_ready = backend == "pyrosetta"
        expected_probe_ready = backend in PHYSICAL_BACKENDS
        fail_if(ready_row.get("ready_for_execution") is not expected_ready, failures, f"{backend}_readiness_expected", ready_row.get("ready_for_execution"), expected_ready)
        fail_if(probe_row.get("ready_for_ddg_execution") is not expected_probe_ready, failures, f"{backend}_probe_expected", probe_row.get("ready_for_ddg_execution"), expected_probe_ready)
        fail_if(diag_row.get("ready_for_physics_ddg") is not expected_ready, failures, f"{backend}_diagnostic_physics_expected", diag_row.get("ready_for_physics_ddg"), expected_ready)

    thermompnn = diagnostic.get("thermompnn_proxy") or {}
    thermompnn_readiness = readiness_rows.get("thermompnn", {})
    fail_if(readiness.get("proxy_ddg_backend_ready") is not True, failures, "readiness_proxy_ddg_backend_ready_true", readiness.get("proxy_ddg_backend_ready"), True)
    fail_if(thermompnn_readiness.get("ready_for_execution") is not True, failures, "thermompnn_ready_for_execution_true", thermompnn_readiness.get("ready_for_execution"), True)
    fail_if(diagnostic.get("proxy_ddg_backend_ready") is not True, failures, "diagnostic_proxy_ddg_backend_ready_true", diagnostic.get("proxy_ddg_backend_ready"), True)
    fail_if(diagnostic.get("proxy_is_physics") is not False, failures, "diagnostic_proxy_is_physics_false", diagnostic.get("proxy_is_physics"), False)
    fail_if(thermompnn.get("proxy_is_physics") is not False, failures, "thermompnn_proxy_is_physics_false", thermompnn.get("proxy_is_physics"), False)
    fail_if(thermompnn.get("physics_ddg_ready") is not False, failures, "thermompnn_physics_ddg_ready_false", thermompnn.get("physics_ddg_ready"), False)

    fail_if(int(preflight_json.get("approved_runtime_receipt_rows") or 0) < 1, failures, "preflight_approved_runtime_receipts_at_least_one", preflight_json.get("approved_runtime_receipt_rows"), ">=1")
    fail_if(int(preflight_json.get("ready_to_run_physical_ddg_smoke_rows") or 0) < 1, failures, "preflight_ready_to_run_physical_ddg_smoke_at_least_one", preflight_json.get("ready_to_run_physical_ddg_smoke_rows"), ">=1")
    fail_if(int(preflight_json.get("ready_to_enable_config_rows") or 0) < 1, failures, "preflight_ready_to_enable_config_at_least_one", preflight_json.get("ready_to_enable_config_rows"), ">=1")
    fail_if(int(license_validation.get("approved_for_local_evaluation_rows") or 0) < 1, failures, "license_local_eval_approvals_at_least_one", license_validation.get("approved_for_local_evaluation_rows"), ">=1")
    fail_if(preflight_json.get("physics_ddg_ready") is not False, failures, "preflight_physics_ddg_ready_false", preflight_json.get("physics_ddg_ready"), False)
    blocked_physical_backends = set(preflight_json.get("blocked_physical_backends") or [])
    fail_if("foldx" not in blocked_physical_backends, failures, "preflight_foldx_blocked_backend_tracked", sorted(blocked_physical_backends), "contains foldx")

    ddg_action = ddg_action_from_wave(controlled_wave)
    if ddg_action:
        fail_if(ddg_action.get("all_commands_passed") is not True, failures, "controlled_wave_ddg_probe_commands_passed", ddg_action.get("all_commands_passed"), True)

    guardrails = diagnostic.get("guardrails") or {}
    for field in [
        "safe_for_model_claim",
        "ready_for_model_claim",
        "safe_for_training_import",
        "release_ready",
        "ddg_fake_results_generated",
        "unapproved_config_enable_changed",
        "unreviewed_formal_decision_written",
        "training_labels_written",
    ]:
        fail_if(guardrails.get(field) is not False, failures, f"guardrail_{field}_false", guardrails.get(field), False)
    fail_if(guardrails.get("formal_runtime_receipt_written") is not True, failures, "guardrail_formal_runtime_receipt_written_true", guardrails.get("formal_runtime_receipt_written"), True)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "checked_reports": {
            "diagnostic": rel(args.diagnostic),
            "controlled_wave": rel(CONTROLLED_WAVE),
            "executable_probe": rel(EXECUTABLE_PROBE),
            "runtime_discovery": rel(RUNTIME_DISCOVERY),
            "readiness": rel(READINESS),
            "preflight_json": rel(preflight_path) if preflight_path else None,
            "preflight_md": rel(PREFLIGHT_MD) if PREFLIGHT_MD.exists() else None,
            "license_validation": rel(LICENSE_VALIDATION),
        },
        "executable_ddg_backend_ready": diagnostic.get("executable_ddg_backend_ready"),
        "physics_ddg_ready": diagnostic.get("physics_ddg_ready"),
        "proxy_ddg_backend_ready": diagnostic.get("proxy_ddg_backend_ready"),
        "proxy_is_physics": diagnostic.get("proxy_is_physics"),
        "physical_backends_checked": sorted(PHYSICAL_BACKENDS),
        "thermompnn_proxy_ready": thermompnn.get("proxy_ready"),
        "contradictory_executable_physics_states": contradictions,
        "failures": failures,
        "warnings": warnings,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed validator. PyRosetta may satisfy physical ddG only through approved runtime receipt and smoke artifacts; ThermoMPNN proxy readiness remains proxy-only and cannot satisfy physics ddG.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "executable_ddg_backend_ready": report["executable_ddg_backend_ready"],
        "physics_ddg_ready": report["physics_ddg_ready"],
        "proxy_ddg_backend_ready": report["proxy_ddg_backend_ready"],
        "proxy_is_physics": report["proxy_is_physics"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
