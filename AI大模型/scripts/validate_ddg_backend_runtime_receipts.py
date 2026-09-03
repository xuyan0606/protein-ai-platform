#!/usr/bin/env python3
"""Validate licensed runtime receipts for physical ddG backends fail-closed."""

from __future__ import annotations

import argparse
import json
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_python_module_discovery import module_available


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "governance" / "ddg_backend_runtime_receipts.local.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "governance" / "ddg_backend_runtime_receipts.template.jsonl"
STATUS = AI_ROOT / "datasets" / "governance" / "ddg_backend_runtime_receipt_status.jsonl"
LICENSE_REPORT = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"
PROBE_REPORT = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
REPORT = AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json"
SCHEMA = AI_ROOT / "contracts" / "ddg_backend_runtime_receipt.schema.json"

BACKENDS = ["rosetta", "pyrosetta", "foldx"]
VALID_DECISIONS = {"approved_runtime_ready", "rejected", "needs_more_info"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def path_exists(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    if path.is_absolute():
        try:
            path.relative_to(AI_ROOT)
        except ValueError:
            pass
        return path.exists()
    return (AI_ROOT / path).exists()


def resolve_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else AI_ROOT / path


def file_sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def license_approval_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in report.get("records") or []:
        if isinstance(row, dict) and row.get("review_item_id"):
            result[str(row["review_item_id"])] = row
    return result


def template_rows() -> list[dict[str, Any]]:
    rows = []
    for backend in BACKENDS:
        rows.append({
            "runtime_receipt_id": f"ddg-runtime-receipt-{backend}-001",
            "backend": backend,
            "receipt_decision": "needs_more_info",
            "license_review_item_id": f"foreign_tool:{backend}",
            "license_decision_reviewed": False,
            "install_path": "",
            "executable_paths": [],
            "python_module": "pyrosetta" if backend == "pyrosetta" else "",
            "runtime_version": "",
            "probe_command": "python3 scripts/build_ddg_executable_probe.py",
            "probe_report": "reports/ddg_executable_probe_report.json",
            "probe_evidence_reviewed": False,
            "config_enabled_reviewed": False,
            "smoke_plan_reviewed": False,
            "smoke_artifact_paths": [],
            "smoke_artifact_sha256": {},
            "approved_for_physical_ddg_runtime": False,
            "reviewer": "",
            "reviewed_at": "",
            "review_basis": "",
            "conditions": [],
            "residual_risks": ["template_not_reviewed", "runtime_not_approved"],
            "policy": "Template only; not a license approval, not installation evidence, and not ddG execution.",
        })
    return rows


def probe_backend_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("backend")): row
        for row in report.get("backend_rows") or []
        if isinstance(row, dict) and row.get("backend")
    }


def validate(row: dict[str, Any], license_records: dict[str, dict[str, Any]], probe_rows: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    required = [
        "runtime_receipt_id",
        "backend",
        "receipt_decision",
        "license_review_item_id",
        "license_decision_reviewed",
        "install_path",
        "executable_paths",
        "python_module",
        "runtime_version",
        "probe_command",
        "probe_report",
        "probe_evidence_reviewed",
        "config_enabled_reviewed",
        "smoke_plan_reviewed",
        "smoke_artifact_paths",
        "smoke_artifact_sha256",
        "approved_for_physical_ddg_runtime",
        "reviewer",
        "reviewed_at",
        "review_basis",
        "conditions",
        "residual_risks",
    ]
    for field in required:
        if field not in row:
            errors.append(f"missing_{field}")

    backend = str(row.get("backend") or "")
    if backend not in BACKENDS:
        errors.append("invalid_backend")
    if row.get("receipt_decision") not in VALID_DECISIONS:
        errors.append("invalid_receipt_decision")

    for flag in [
        "license_decision_reviewed",
        "probe_evidence_reviewed",
        "config_enabled_reviewed",
        "smoke_plan_reviewed",
        "approved_for_physical_ddg_runtime",
    ]:
        if not isinstance(row.get(flag), bool):
            errors.append(f"invalid_{flag}")

    executable_paths = row.get("executable_paths")
    if not isinstance(executable_paths, list):
        errors.append("invalid_executable_paths")
        executable_paths = []
    if row.get("conditions") is not None and not isinstance(row.get("conditions"), list):
        errors.append("invalid_conditions")
    if row.get("residual_risks") is not None and not isinstance(row.get("residual_risks"), list):
        errors.append("invalid_residual_risks")
    smoke_artifact_paths = row.get("smoke_artifact_paths")
    if not isinstance(smoke_artifact_paths, list):
        errors.append("invalid_smoke_artifact_paths")
        smoke_artifact_paths = []
    smoke_artifact_sha256 = row.get("smoke_artifact_sha256")
    if not isinstance(smoke_artifact_sha256, dict):
        errors.append("invalid_smoke_artifact_sha256")
        smoke_artifact_sha256 = {}

    license_id = str(row.get("license_review_item_id") or "")
    expected_license_id = f"foreign_tool:{backend}"
    if license_id != expected_license_id:
        errors.append("license_review_item_id_mismatch")
    if backend not in BACKENDS and str(backend).lower() == "thermompnn":
        errors.append("thermompnn_proxy_not_allowed_as_physical_runtime_receipt")
    license_record = license_records.get(license_id)
    license_local_eval_approved = bool(license_record and license_record.get("approved_for_local_evaluation"))

    probe_row = probe_rows.get(backend, {})
    receipt_approved = row.get("receipt_decision") == "approved_runtime_ready"
    if receipt_approved:
        for field in ["runtime_version", "reviewer", "reviewed_at", "review_basis"]:
            if row.get(field) in (None, "", []):
                errors.append(f"approval_missing_{field}")
        if row.get("approved_for_physical_ddg_runtime") is not True:
            errors.append("approval_missing_approved_for_physical_ddg_runtime")
        if row.get("license_decision_reviewed") is not True:
            errors.append("approval_missing_license_decision_reviewed")
        if not license_local_eval_approved:
            errors.append("license_not_approved_for_local_evaluation")
        if row.get("config_enabled_reviewed") is not True:
            errors.append("approval_missing_config_enabled_reviewed")
        if row.get("probe_evidence_reviewed") is not True:
            errors.append("approval_missing_probe_evidence_reviewed")
        if row.get("smoke_plan_reviewed") is not True:
            errors.append("approval_missing_smoke_plan_reviewed")
        if not smoke_artifact_paths:
            errors.append("approval_missing_smoke_artifact_paths")
        if not smoke_artifact_sha256:
            errors.append("approval_missing_smoke_artifact_sha256")
        for artifact in smoke_artifact_paths:
            artifact_path = resolve_path(artifact)
            if artifact_path is None or not artifact_path.exists() or not artifact_path.is_file():
                errors.append("approved_runtime_smoke_artifact_missing")
                continue
            expected = smoke_artifact_sha256.get(str(artifact))
            observed = file_sha256(artifact_path)
            if not expected:
                errors.append("approved_runtime_smoke_artifact_sha256_missing")
            elif observed != str(expected).lower():
                errors.append("approved_runtime_smoke_artifact_sha256_mismatch")
        if row.get("residual_risks"):
            errors.append("approval_with_residual_risks")
        if backend in {"rosetta", "foldx"}:
            if not any(path_exists(path) for path in executable_paths):
                errors.append("approved_runtime_executable_path_missing")
            if not bool(probe_row.get("executable_found")):
                errors.append("probe_did_not_find_executable")
        if backend == "pyrosetta":
            module = str(row.get("python_module") or "pyrosetta")
            if not module_available(module, [row.get("install_path")]):
                errors.append("approved_runtime_python_module_missing")
            if not bool(probe_row.get("python_module_available")):
                errors.append("probe_did_not_find_python_module")
    else:
        if row.get("approved_for_physical_ddg_runtime") is True:
            errors.append("non_approved_receipt_sets_runtime_approval")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ddG backend runtime receipts")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--status-output", type=Path, default=STATUS)
    parser.add_argument("--license-report", type=Path, default=LICENSE_REPORT)
    parser.add_argument("--probe-report", type=Path, default=PROBE_REPORT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--schema", type=Path, default=SCHEMA)
    args = parser.parse_args()

    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, template_rows())

    receipts = load_jsonl(args.input)
    license_records = license_approval_map(load_json(args.license_report))
    probe_rows = probe_backend_map(load_json(args.probe_report))
    status_rows: list[dict[str, Any]] = []
    errors = Counter()
    seen_receipts = set()
    duplicate_receipts = set()
    for row in receipts:
        receipt_id = str(row.get("runtime_receipt_id") or "")
        if receipt_id in seen_receipts:
            duplicate_receipts.add(receipt_id)
        seen_receipts.add(receipt_id)
        row_errors = validate(row, license_records, probe_rows)
        errors.update(row_errors)
        approved = row.get("receipt_decision") == "approved_runtime_ready" and not row_errors
        status_rows.append({
            "runtime_receipt_id": row.get("runtime_receipt_id"),
            "backend": row.get("backend"),
            "receipt_decision": row.get("receipt_decision"),
            "valid": not row_errors,
            "approved_for_physical_ddg_runtime": approved,
            "ready_to_enable_backend": approved,
            "ready_for_ddg_smoke": approved,
            "errors": row_errors,
            "policy": "Receipt validation only; does not modify config, run ddG, or approve model claims.",
        })

    if duplicate_receipts:
        errors.update({"duplicate_runtime_receipt_id": len(duplicate_receipts)})
        for row in status_rows:
            if str(row.get("runtime_receipt_id")) in duplicate_receipts:
                row["valid"] = False
                row["approved_for_physical_ddg_runtime"] = False
                row["ready_to_enable_backend"] = False
                row["ready_for_ddg_smoke"] = False
                row["errors"].append("duplicate_runtime_receipt_id")

    valid_rows = sum(1 for row in status_rows if row["valid"])
    approved_rows = sum(1 for row in status_rows if row["approved_for_physical_ddg_runtime"])
    write_jsonl(args.status_output, status_rows)
    approved_backends = sorted({str(row["backend"]) for row in status_rows if row["approved_for_physical_ddg_runtime"]})
    missing_backend_receipts = [backend for backend in BACKENDS if backend not in approved_backends]
    all_physical_backends_ready = not missing_backend_receipts
    any_backend_runtime_ready = approved_rows > 0
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "input": str(args.input),
        "template": str(args.template),
        "schema": str(args.schema),
        "status_output": str(args.status_output),
        "receipt_rows": len(receipts),
        "valid_receipt_rows": valid_rows,
        "invalid_receipt_rows": len(status_rows) - valid_rows,
        "approved_runtime_rows": approved_rows,
        "ready_to_enable_backend_rows": sum(1 for row in status_rows if row["ready_to_enable_backend"]),
        "ready_for_ddg_smoke_rows": sum(1 for row in status_rows if row["ready_for_ddg_smoke"]),
        "per_backend_runtime_ready_rows": approved_rows,
        "any_backend_runtime_ready": any_backend_runtime_ready,
        "all_physical_backends_ready": all_physical_backends_ready,
        "missing_backend_runtime_receipts": missing_backend_receipts,
        "physical_ddg_lane_capability_status": "ready" if all_physical_backends_ready else "blocked",
        "physics_ddg_ready": all_physical_backends_ready,
        "executable_ddg_backend_ready": all_physical_backends_ready,
        "thermompnn_proxy_receipt_allowed": False,
        "fail_closed_hard_gates": [
            "backend_must_be_rosetta_pyrosetta_or_foldx",
            "license_decision_must_be_reviewed_and_approved_for_local_evaluation",
            "runtime_probe_evidence_must_be_reviewed",
            "backend_config_enablement_must_be_reviewed",
            "physical_ddg_smoke_artifacts_must_exist_with_sha256",
            "approved_receipt_must_have_zero_residual_risks",
        ],
        "backends_with_approved_runtime": approved_backends,
        "license_local_evaluation_approved_items": sorted(
            item_id for item_id, row in license_records.items() if row.get("approved_for_local_evaluation")
        ),
        "error_counts": dict(errors),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Physical ddG runtime is ready only for backends with explicit license review, installed executable/module evidence, reviewed config, probe evidence, and checksumed smoke artifacts. This does not create training labels, model-claim readiness, customer delivery readiness, or release readiness.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt_rows": report["receipt_rows"],
        "approved_runtime_rows": report["approved_runtime_rows"],
        "ready_to_enable_backend_rows": report["ready_to_enable_backend_rows"],
        "ready_for_ddg_smoke_rows": report["ready_for_ddg_smoke_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
