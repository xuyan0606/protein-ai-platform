#!/usr/bin/env python3
"""Build the fail-closed ddG model-consumption contract report."""

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
OUT = AI_ROOT / "reports" / "ddg_model_consumption_contract_report.json"

PHYSICS_BACKENDS = ("rosetta", "pyrosetta", "foldx")
FORBIDDEN_TRUE_FIELDS = (
    "safe_for_model_claim",
    "release_ready",
)


def load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, "missing_file"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"invalid_json:{type(exc).__name__}"
    if not isinstance(value, dict):
        return {}, "top_level_not_object"
    return value, None


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


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


def backend_rows(report: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    rows = report.get(key)
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("backend")): row
        for row in rows
        if isinstance(row, dict) and row.get("backend")
    }


def normalized_proxy_row(row: dict[str, Any]) -> dict[str, Any]:
    """Expose an explicit manual-review field without changing the source smoke report."""
    return {
        "mutation": row.get("mutation"),
        "wild_type": row.get("wild_type"),
        "mutant": row.get("mutant"),
        "canonical_position": row.get("canonical_position"),
        "backend": row.get("backend"),
        "ddg_pred_kcal_mol": row.get("ddg_pred_kcal_mol"),
        "threshold_class": row.get("threshold_class"),
        "manual_review": row.get("manual_review", row.get("manual_review_required")),
        "evidence_level": row.get("evidence_level"),
        "negative_ddg_is_stabilizing": row.get("negative_ddg_is_stabilizing"),
        "limitations": row.get("limitations"),
        "proxy_is_physics": False,
        "training_label": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def normalized_pyrosetta_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    table_rows = ((report.get("ddg_table") or {}).get("rows") or [])
    rows: list[dict[str, Any]] = []
    if not isinstance(table_rows, list):
        return rows
    for row in table_rows:
        if not isinstance(row, dict):
            continue
        rows.append({
            "backend": "pyrosetta",
            "structure_id": row.get("structure_id"),
            "mutation": row.get("mutation"),
            "chain_id": row.get("chain_id"),
            "pdb_position": row.get("pdb_position"),
            "wild_type": row.get("wild_type"),
            "mutant": row.get("mutant"),
            "ddg_reu": row.get("ddg_reu"),
            "ddg_units": "REU",
            "manual_review": True,
            "evidence_level": "computational_physics_runtime_smoke",
            "negative_ddg_is_stabilizing": (report.get("ddg_table") or {}).get("negative_ddg_is_stabilizing"),
            "limitations": [
                "single-mutation runtime smoke only",
                "Rosetta Energy Units are not wet-lab kcal/mol labels",
                "not training-import eligible without separate reviewed label authorization",
            ],
            "training_label": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ddG model-consumption contract report")
    parser.add_argument("--readiness", type=Path, default=READINESS)
    parser.add_argument("--diagnostic", type=Path, default=DIAGNOSTIC)
    parser.add_argument("--proxy-guard", type=Path, default=PROXY_GUARD)
    parser.add_argument("--smoke", type=Path, default=SMOKE)
    parser.add_argument("--executable-probe", type=Path, default=EXECUTABLE_PROBE)
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
    }
    loaded: dict[str, dict[str, Any]] = {}
    input_errors: list[dict[str, str]] = []
    for name, path in paths.items():
        report, error = load_json(path)
        loaded[name] = report
        if error:
            input_errors.append({"report": name, "path": rel(path), "error": error})

    readiness = loaded["backend_readiness"]
    diagnostic = loaded["backend_failure_diagnostic"]
    proxy_guard = loaded["proxy_not_physics_claim_validation"]
    smoke = loaded["thermompnn_venus15b_smoke"]
    pyrosetta_smoke = loaded["pyrosetta_physical_smoke"]
    runtime_receipt = loaded["runtime_receipt_validation"]
    executable_probe = loaded["executable_probe"]
    forbidden_states = forbidden_true_states(loaded)

    smoke_rows = ((smoke.get("outputs") or {}).get("ddg_table") or [])
    if not isinstance(smoke_rows, list):
        smoke_rows = []
    proxy_rows = [normalized_proxy_row(row) for row in smoke_rows if isinstance(row, dict)]
    pyrosetta_rows = normalized_pyrosetta_rows(pyrosetta_smoke)
    readiness_by_backend = backend_rows(readiness, "backends")
    diagnostic_by_backend = backend_rows(diagnostic, "physics_backend_statuses")

    physics_backend_states = [
        {
            "backend": backend,
            "readiness_ready_for_execution": readiness_by_backend.get(backend, {}).get("ready_for_execution"),
            "diagnostic_ready_for_physics_ddg": diagnostic_by_backend.get(backend, {}).get("ready_for_physics_ddg"),
            "blockers": readiness_by_backend.get(backend, {}).get("blockers") or [],
        }
        for backend in PHYSICS_BACKENDS
    ]
    required_row_fields = [
        "manual_review",
        "evidence_level",
        "negative_ddg_is_stabilizing",
        "limitations",
    ]
    rows_have_manual_review_evidence = all(
        all(row.get(field) is not None for field in required_row_fields)
        and row.get("manual_review") is True
        and row.get("evidence_level") == "computational_proxy"
        and row.get("negative_ddg_is_stabilizing") is True
        and isinstance(row.get("limitations"), list)
        and bool(row.get("limitations"))
        for row in proxy_rows
    )

    physics_ddg_ready = (
        readiness.get("physics_ddg_ready") is True
        and diagnostic.get("physics_ddg_ready") is True
    )
    executable_ddg_backend_ready = diagnostic.get("executable_ddg_backend_ready") is True
    proxy_ready = (
        readiness.get("proxy_ddg_backend_ready") is True
        and diagnostic.get("proxy_ddg_backend_ready") is True
        and proxy_guard.get("proxy_is_physics") is False
        and proxy_guard.get("success") is True
        and smoke.get("status") == "completed"
        and smoke.get("backend") == "thermompnn"
        and smoke.get("outputs", {}).get("ready_as_proxy_ddg_artifact") is True
    )
    pyrosetta_physics_ready = (
        "pyrosetta" in set(runtime_receipt.get("backends_with_approved_runtime") or [])
        and pyrosetta_smoke.get("physical_smoke_passed") is True
        and len(pyrosetta_rows) == 1
    )
    source_state_valid = (
        not input_errors
        and not forbidden_states
        and proxy_ready
        and pyrosetta_physics_ready
        and len(proxy_rows) == 4
        and rows_have_manual_review_evidence
        and smoke.get("negative_ddg_is_stabilizing") is True
    )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "contract_id": "ddg_model_consumption_contract",
        "success": source_state_valid,
        "checked_reports": {name: rel(path) for name, path in paths.items()},
        "input_errors": input_errors,
        "source_forbidden_true_states": forbidden_states,
        "physics_ddg_state": {
            "physics_ddg_ready": physics_ddg_ready,
            "executable_ddg_backend_ready": executable_ddg_backend_ready,
            "physics_backends": physics_backend_states,
            "proxy_is_physics": False,
        },
        "physics_ddg_consumption": {
            "backend": "pyrosetta",
            "physics_ready": pyrosetta_physics_ready,
            "manual_review_computational_feature": True,
            "manual_review_required": True,
            "training_label": False,
            "training_label_source": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "evidence_level": "computational_physics_runtime_smoke",
            "ddg_units": "REU",
            "mutation_row_count": len(pyrosetta_rows),
            "artifact_paths": pyrosetta_smoke.get("smoke_artifact_paths") or [],
            "artifact_sha256": pyrosetta_smoke.get("smoke_artifact_sha256") or {},
            "rows": pyrosetta_rows,
        },
        "proxy_ddg_consumption": {
            "backend": "thermompnn",
            "proxy_ready": proxy_ready,
            "proxy_is_physics": False,
            "manual_review_computational_feature": True,
            "manual_review_required": True,
            "training_label": False,
            "training_label_source": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "negative_ddg_is_stabilizing": smoke.get("negative_ddg_is_stabilizing"),
            "evidence_level": "computational_proxy",
            "mutation_row_count": len(proxy_rows),
            "required_row_fields": required_row_fields,
            "rows_have_manual_review_evidence": rows_have_manual_review_evidence,
            "rows": proxy_rows,
        },
        "allowed_consumption": [
            "PyRosetta computational physics runtime-smoke feature with manual review",
            "manual-review computational feature",
            "hypothesis prioritization pending human review",
        ],
        "prohibited_consumption": [
            "training label",
            "model claim",
            "release decision",
            "customer delivery without separate approval",
        ],
        "negative_protection_contract": {
            "physics_ddg_ready_requires_pyrosetta_receipt_and_smoke": True,
            "executable_ddg_backend_ready_requires_pyrosetta_receipt_and_smoke": True,
            "proxy_is_physics_must_be_false": True,
            "safe_for_model_claim_must_be_false": True,
            "release_ready_must_be_false": True,
            "thermompnn_rows_require_manual_review_evidence": True,
            "pyrosetta_rows_not_training_labels": True,
        },
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "PyRosetta smoke output is computational physics runtime evidence only, and ThermoMPNN ddG values are proxy evidence only. "
            "Neither source may be consumed as a wet-lab training label, model claim, release decision, or customer-delivery approval."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "proxy_rows": len(proxy_rows),
        "physics_ddg_ready": physics_ddg_ready,
        "executable_ddg_backend_ready": executable_ddg_backend_ready,
        "proxy_is_physics": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
