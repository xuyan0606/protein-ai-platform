#!/usr/bin/env python3
"""Validate the ddG model-consumption contract fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
READINESS = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"
DIAGNOSTIC = AI_ROOT / "reports" / "ddg_backend_failure_diagnostic_report.json"
PROXY_GUARD = AI_ROOT / "reports" / "ddg_proxy_not_physics_claim_validation_report.json"
SMOKE = AI_ROOT / "reports" / "thermompnn_venus15b_smoke_report.json"
PYROSETTA_SMOKE = AI_ROOT / "reports" / "pyrosetta_physical_smoke_bootstrap_report.json"
RUNTIME_RECEIPT = AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json"
EXECUTABLE_PROBE = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
CONTRACT = AI_ROOT / "reports" / "ddg_model_consumption_contract_report.json"
OUT = AI_ROOT / "reports" / "ddg_model_consumption_contract_validation_report.json"

PHYSICS_BACKENDS = ("rosetta", "pyrosetta", "foldx")
FORBIDDEN_TRUE_FIELDS = (
    "safe_for_model_claim",
    "release_ready",
)
REQUIRED_PROXY_FIELDS = (
    "manual_review",
    "evidence_level",
    "negative_ddg_is_stabilizing",
    "limitations",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


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


def forbidden_true_states(named_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for report_name, report in named_reports.items():
        for path, row in walk_dicts(report):
            for field in FORBIDDEN_TRUE_FIELDS:
                if row.get(field) is True:
                    states.append({"report": report_name, "path": path, "field": field, "value": True})
    return states


def by_backend(rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("backend")): row
        for row in rows
        if isinstance(row, dict) and row.get("backend")
    }


def validate_proxy_rows(rows: Any, failures: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(rows, list):
        rows = []
    row_summaries: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append({"check": "thermompnn_proxy_row_object", "row": index, "observed": type(row).__name__, "expected": "object"})
            continue
        missing = [field for field in REQUIRED_PROXY_FIELDS if field not in row or row.get(field) is None]
        fail_if(bool(missing), failures, "thermompnn_proxy_row_required_fields", {"row": index, "missing": missing}, list(REQUIRED_PROXY_FIELDS))
        fail_if(row.get("backend") != "thermompnn", failures, "thermompnn_proxy_row_backend", {"row": index, "backend": row.get("backend")}, "thermompnn")
        fail_if(row.get("manual_review") is not True, failures, "thermompnn_proxy_row_manual_review", {"row": index, "manual_review": row.get("manual_review")}, True)
        fail_if(row.get("evidence_level") != "computational_proxy", failures, "thermompnn_proxy_row_evidence_level", {"row": index, "evidence_level": row.get("evidence_level")}, "computational_proxy")
        fail_if(row.get("negative_ddg_is_stabilizing") is not True, failures, "thermompnn_proxy_row_direction", {"row": index, "negative_ddg_is_stabilizing": row.get("negative_ddg_is_stabilizing")}, True)
        fail_if(not isinstance(row.get("limitations"), list) or not row.get("limitations"), failures, "thermompnn_proxy_row_limitations", {"row": index, "limitations": row.get("limitations")}, "non-empty list")
        row_summaries.append({
            "mutation": row.get("mutation"),
            "manual_review": row.get("manual_review"),
            "evidence_level": row.get("evidence_level"),
            "has_limitations": isinstance(row.get("limitations"), list) and bool(row.get("limitations")),
        })
    return {"row_count": len(rows), "rows": row_summaries}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ddG model-consumption contract report")
    parser.add_argument("--readiness", type=Path, default=READINESS)
    parser.add_argument("--diagnostic", type=Path, default=DIAGNOSTIC)
    parser.add_argument("--proxy-guard", type=Path, default=PROXY_GUARD)
    parser.add_argument("--smoke", type=Path, default=SMOKE)
    parser.add_argument("--executable-probe", type=Path, default=EXECUTABLE_PROBE)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    paths = {
        "backend_readiness": args.readiness,
        "backend_failure_diagnostic": args.diagnostic,
        "proxy_not_physics_claim_validation": args.proxy_guard,
        "thermompnn_venus15b_smoke": args.smoke,
        "pyrosetta_physical_smoke": PYROSETTA_SMOKE,
        "runtime_receipt_validation": RUNTIME_RECEIPT,
        "executable_probe": args.executable_probe,
        "consumption_contract": args.contract,
    }
    reports = {name: load_json(path) for name, path in paths.items()}
    readiness = reports["backend_readiness"]
    diagnostic = reports["backend_failure_diagnostic"]
    proxy_guard = reports["proxy_not_physics_claim_validation"]
    smoke = reports["thermompnn_venus15b_smoke"]
    pyrosetta_smoke = reports["pyrosetta_physical_smoke"]
    runtime_receipt = reports["runtime_receipt_validation"]
    executable_probe = reports["executable_probe"]
    contract = reports["consumption_contract"]
    failures: list[dict[str, Any]] = []

    missing_reports = [name for name, path in paths.items() if not path.exists()]
    fail_if(bool(missing_reports), failures, "required_reports_present", missing_reports, [])
    empty_reports = [name for name, report in reports.items() if not report]
    fail_if(bool(empty_reports), failures, "required_reports_valid_non_empty_json_objects", empty_reports, [])

    forbidden_states = forbidden_true_states(reports)
    fail_if(bool(forbidden_states), failures, "no_forbidden_true_states_anywhere", forbidden_states, [])

    readiness_by_backend = by_backend(readiness.get("backends"))
    diagnostic_by_backend = by_backend(diagnostic.get("physics_backend_statuses"))
    probe_by_backend = by_backend(executable_probe.get("backend_rows"))
    for backend in PHYSICS_BACKENDS:
        readiness_row = readiness_by_backend.get(backend, {})
        diagnostic_row = diagnostic_by_backend.get(backend, {})
        probe_row = probe_by_backend.get(backend, {})
        expected_ready = backend == "pyrosetta"
        expected_probe_ready = backend in PHYSICS_BACKENDS
        fail_if(readiness_row.get("ready_for_execution") is not expected_ready, failures, f"{backend}_readiness_expected", readiness_row.get("ready_for_execution"), expected_ready)
        fail_if(diagnostic_row.get("ready_for_physics_ddg") is not expected_ready, failures, f"{backend}_diagnostic_physics_expected", diagnostic_row.get("ready_for_physics_ddg"), expected_ready)
        fail_if(probe_row.get("ready_for_ddg_execution") is not expected_probe_ready, failures, f"{backend}_probe_expected", probe_row.get("ready_for_ddg_execution"), expected_probe_ready)

    fail_if(diagnostic.get("physics_ddg_ready") is not False, failures, "diagnostic_physics_ddg_ready_false", diagnostic.get("physics_ddg_ready"), False)
    fail_if(readiness.get("executable_ddg_backend_ready") is not True, failures, "readiness_executable_ddg_backend_ready_true", readiness.get("executable_ddg_backend_ready"), True)
    fail_if(diagnostic.get("executable_ddg_backend_ready") is not False, failures, "diagnostic_executable_ddg_backend_ready_false", diagnostic.get("executable_ddg_backend_ready"), False)
    fail_if(executable_probe.get("executable_ddg_backend_ready") is not True, failures, "probe_executable_ddg_backend_ready_true", executable_probe.get("executable_ddg_backend_ready"), True)
    approved_runtime_backends = sorted(
        str(backend)
        for backend in (runtime_receipt.get("backends_with_approved_runtime") or [])
    )
    fail_if(
        "pyrosetta" not in approved_runtime_backends,
        failures,
        "runtime_receipt_pyrosetta_present",
        approved_runtime_backends,
        "pyrosetta included",
    )
    fail_if(
        not set(approved_runtime_backends).issubset(set(PHYSICS_BACKENDS)),
        failures,
        "runtime_receipt_backends_are_physics_backends",
        approved_runtime_backends,
        list(PHYSICS_BACKENDS),
    )
    fail_if(pyrosetta_smoke.get("physical_smoke_passed") is not True, failures, "pyrosetta_smoke_passed_true", pyrosetta_smoke.get("physical_smoke_passed"), True)
    fail_if(readiness.get("proxy_ddg_backend_ready") is not True, failures, "readiness_proxy_ddg_backend_ready_true", readiness.get("proxy_ddg_backend_ready"), True)
    fail_if(diagnostic.get("proxy_ddg_backend_ready") is not True, failures, "diagnostic_proxy_ddg_backend_ready_true", diagnostic.get("proxy_ddg_backend_ready"), True)
    fail_if(proxy_guard.get("success") is not True, failures, "proxy_guard_success_true", proxy_guard.get("success"), True)
    fail_if(proxy_guard.get("proxy_is_physics") is not False, failures, "proxy_guard_proxy_is_physics_false", proxy_guard.get("proxy_is_physics"), False)

    fail_if(smoke.get("backend") != "thermompnn", failures, "smoke_backend_thermompnn", smoke.get("backend"), "thermompnn")
    fail_if(smoke.get("status") != "completed", failures, "smoke_completed", smoke.get("status"), "completed")
    fail_if(smoke.get("negative_ddg_is_stabilizing") is not True, failures, "smoke_negative_ddg_is_stabilizing_true", smoke.get("negative_ddg_is_stabilizing"), True)
    fail_if((smoke.get("outputs") or {}).get("ready_as_proxy_ddg_artifact") is not True, failures, "smoke_ready_as_proxy_artifact", (smoke.get("outputs") or {}).get("ready_as_proxy_ddg_artifact"), True)
    contract_proxy = contract.get("proxy_ddg_consumption") or {}
    contract_physics = contract.get("physics_ddg_state") or {}
    contract_pyrosetta = contract.get("physics_ddg_consumption") or {}
    source_proxy_rows = (smoke.get("outputs") or {}).get("ddg_table")
    source_proxy_row_count = len(source_proxy_rows) if isinstance(source_proxy_rows, list) else 0
    proxy_summary = validate_proxy_rows(contract_proxy.get("rows"), failures)
    fail_if(source_proxy_row_count != 4, failures, "thermompnn_source_proxy_row_count_four", source_proxy_row_count, 4)
    fail_if(proxy_summary["row_count"] != source_proxy_row_count, failures, "contract_proxy_row_count_matches_smoke", proxy_summary["row_count"], source_proxy_row_count)
    fail_if(contract.get("success") is not True, failures, "contract_source_success_true", contract.get("success"), True)
    fail_if(contract.get("safe_for_training_import") is not False, failures, "contract_safe_for_training_import_false", contract.get("safe_for_training_import"), False)
    fail_if(contract.get("safe_for_model_claim") is not False, failures, "contract_safe_for_model_claim_false", contract.get("safe_for_model_claim"), False)
    fail_if(contract.get("release_ready") is not False, failures, "contract_release_ready_false", contract.get("release_ready"), False)
    fail_if(contract_physics.get("physics_ddg_ready") is not False, failures, "contract_physics_ddg_ready_false", contract_physics.get("physics_ddg_ready"), False)
    fail_if(contract_physics.get("executable_ddg_backend_ready") is not False, failures, "contract_executable_ddg_backend_ready_false", contract_physics.get("executable_ddg_backend_ready"), False)
    fail_if(contract_physics.get("proxy_is_physics") is not False, failures, "contract_proxy_is_physics_false", contract_physics.get("proxy_is_physics"), False)
    fail_if(contract_pyrosetta.get("backend") != "pyrosetta", failures, "contract_pyrosetta_backend", contract_pyrosetta.get("backend"), "pyrosetta")
    fail_if(contract_pyrosetta.get("physics_ready") is not True, failures, "contract_pyrosetta_ready_true", contract_pyrosetta.get("physics_ready"), True)
    fail_if(contract_pyrosetta.get("training_label") is not False, failures, "contract_pyrosetta_training_label_false", contract_pyrosetta.get("training_label"), False)
    fail_if(contract_pyrosetta.get("safe_for_model_claim") is not False, failures, "contract_pyrosetta_safe_for_model_claim_false", contract_pyrosetta.get("safe_for_model_claim"), False)
    fail_if(contract_pyrosetta.get("release_ready") is not False, failures, "contract_pyrosetta_release_ready_false", contract_pyrosetta.get("release_ready"), False)
    fail_if(contract_pyrosetta.get("mutation_row_count") != 1, failures, "contract_pyrosetta_row_count_one", contract_pyrosetta.get("mutation_row_count"), 1)
    fail_if(contract_proxy.get("manual_review_computational_feature") is not True, failures, "contract_manual_review_feature_true", contract_proxy.get("manual_review_computational_feature"), True)
    fail_if(contract_proxy.get("training_label") is not False, failures, "contract_training_label_false", contract_proxy.get("training_label"), False)
    fail_if(contract_proxy.get("safe_for_model_claim") is not False, failures, "contract_proxy_safe_for_model_claim_false", contract_proxy.get("safe_for_model_claim"), False)
    fail_if(contract_proxy.get("release_ready") is not False, failures, "contract_proxy_release_ready_false", contract_proxy.get("release_ready"), False)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "checked_reports": {name: rel(path) for name, path in paths.items()},
        "state_summary": {
            "physics_ddg_ready": diagnostic.get("physics_ddg_ready"),
            "executable_ddg_backend_ready": executable_probe.get("executable_ddg_backend_ready"),
            "proxy_ddg_backend_ready": diagnostic.get("proxy_ddg_backend_ready"),
            "proxy_is_physics": proxy_guard.get("proxy_is_physics"),
            "pyrosetta_physics_rows": contract_pyrosetta.get("mutation_row_count"),
            "thermompnn_proxy_rows": proxy_summary["row_count"],
            "negative_ddg_is_stabilizing": smoke.get("negative_ddg_is_stabilizing"),
        },
        "fail_closed_checks": {
            "forbidden_true_fields": list(FORBIDDEN_TRUE_FIELDS),
            "forbidden_true_states": forbidden_states,
            "required_proxy_row_fields": list(REQUIRED_PROXY_FIELDS),
            "proxy_rows": proxy_summary,
        },
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Fail-closed validation: PyRosetta physics ddG may be ready only through approved receipt and smoke artifacts. "
            "Every PyRosetta/ThermoMPNN row must remain non-training and manual-review; model/release claims stay false."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "physics_ddg_ready": report["state_summary"]["physics_ddg_ready"],
        "executable_ddg_backend_ready": report["state_summary"]["executable_ddg_backend_ready"],
        "proxy_rows": report["state_summary"]["thermompnn_proxy_rows"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
