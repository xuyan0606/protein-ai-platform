#!/usr/bin/env python3
"""Validate Stage 25 FoldX runtime receipt candidate drafts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DRAFTS = AI_ROOT / "datasets" / "governance" / "stage25_foldx_runtime_receipt_candidate_drafts_20260806.jsonl"
PROVISION_REPORT = AI_ROOT / "reports" / "stage25_foldx_provision_manifest_validation_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_foldx_runtime_receipt_candidate_draft_validation_20260806.json"

EXPECTED_ID = "ddg-runtime-receipt-foldx-stage25-20260806-001"
EXPECTED_RISKS = {
    "provision_not_ready",
    "license_not_reviewed",
    "runtime_not_approved",
    "smoke_evidence_missing",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not DRAFTS.exists(), failures, "draft_file_exists", "missing", str(DRAFTS))
    fail_if(not PROVISION_REPORT.exists(), failures, "provision_report_exists", "missing", str(PROVISION_REPORT))
    rows = load_jsonl(DRAFTS) if DRAFTS.exists() else []
    provision = load_json(PROVISION_REPORT) if PROVISION_REPORT.exists() else {}

    fail_if(len(rows) != 1, failures, "draft_row_count", len(rows), 1)
    row = rows[0] if rows else {}
    fail_if(row.get("runtime_receipt_id") != EXPECTED_ID, failures, "runtime_receipt_id", row.get("runtime_receipt_id"), EXPECTED_ID)
    fail_if(row.get("stage") != 25, failures, "stage", row.get("stage"), 25)
    fail_if(row.get("backend") != "foldx", failures, "backend", row.get("backend"), "foldx")
    fail_if(row.get("receipt_decision") != "needs_more_info", failures, "receipt_decision", row.get("receipt_decision"), "needs_more_info")
    fail_if(row.get("all_provision_ready") is not False, failures, "all_provision_ready_false", row.get("all_provision_ready"), False)
    fail_if(int(provision.get("ready_for_runtime_receipt_rows") or 0) < 1, failures, "provision_ready_rows_at_least_binary", provision.get("ready_for_runtime_receipt_rows"), ">=1")
    fail_if(provision.get("all_foldx_provision_ready") is not False, failures, "all_foldx_provision_ready_false", provision.get("all_foldx_provision_ready"), False)
    for flag in (
        "license_decision_reviewed",
        "probe_evidence_reviewed",
        "config_enabled_reviewed",
        "smoke_plan_reviewed",
        "approved_for_physical_ddg_runtime",
        "formal_runtime_receipt_written",
        "safe_for_model_claim",
        "release_ready",
    ):
        fail_if(row.get(flag) is not False, failures, f"{flag}_false", row.get(flag), False)
    for field in ("install_path", "runtime_version", "reviewer", "reviewed_at", "review_basis"):
        fail_if(str(row.get(field) or "") != "", failures, f"{field}_empty", row.get(field), "")
    for field in ("executable_paths", "smoke_artifact_paths"):
        fail_if(row.get(field) != [], failures, f"{field}_empty", row.get(field), [])
    fail_if(row.get("smoke_artifact_sha256") != {}, failures, "smoke_artifact_sha256_empty", row.get("smoke_artifact_sha256"), {})
    fail_if(set(row.get("residual_risks") or []) != EXPECTED_RISKS, failures, "residual_risks", sorted(row.get("residual_risks") or []), sorted(EXPECTED_RISKS))
    policy = str(row.get("policy") or "")
    for term in ("not a formal ddG runtime receipt", "license approval", "model claim"):
        fail_if(term not in policy, failures, f"policy_contains.{term}", policy, f"contains {term}")

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_foldx_runtime_receipt_candidate_draft_validation",
        "stage": 25,
        "drafts_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "draft_rows": len(rows),
        "receipt_decision": row.get("receipt_decision"),
        "ready_for_runtime_receipt_rows": provision.get("ready_for_runtime_receipt_rows"),
        "formal_runtime_receipt_written": False,
        "approved_for_physical_ddg_runtime": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "drafts_valid": report["drafts_valid"], "failure_count": report["failure_count"], "receipt_decision": report["receipt_decision"], "formal_runtime_receipt_written": report["formal_runtime_receipt_written"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["drafts_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
