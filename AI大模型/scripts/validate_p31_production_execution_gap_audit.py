#!/usr/bin/env python3
"""Validate the P31 production execution gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PENDING_ACTIONS = AI_ROOT / "datasets" / "governance" / "p26_p31_pending_backlog_all_started_actions.jsonl"
ACTIVE_MATRIX = AI_ROOT / "datasets" / "governance" / "active_stage_execution_matrix.jsonl"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CUSTOMER = AI_ROOT / "reports" / "customer_delivery_readiness_report.json"
GOVERNANCE = AI_ROOT / "reports" / "governance_readiness_report.json"
OPERATOR_STATUS = AI_ROOT / "reports" / "operator_review_status_report.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p31_production_execution_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p31_production_execution_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p31_production_execution_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def claim_row(matrix: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for row in matrix.get("claims") or []:
        if isinstance(row, dict) and row.get("claim_id") == claim_id:
            return row
    return {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    pending_rows = [row for row in load_jsonl(PENDING_ACTIONS) if row.get("stage_id") == "P31"]
    active_rows = [row for row in load_jsonl(ACTIVE_MATRIX) if row.get("stage_id") == "P31"]
    release = load_json(LOCAL_RELEASE)
    customer = load_json(CUSTOMER)
    governance = load_json(GOVERNANCE)
    operator = load_json(OPERATOR_STATUS)
    claims = load_json(CLAIM_MATRIX)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    release_claim = claim_row(claims, "local_release_review_package")
    summary = release.get("readiness_summary") if isinstance(release.get("readiness_summary"), dict) else {}
    operator_completion = (operator.get("status") or {}).get("operator_action_completion") or {}
    failures: list[dict[str, Any]] = []

    expected_rows = len(pending_rows) + len(active_rows) + 1
    fail_if(len(pending_rows) != 3, failures, "pending_action_rows_three", len(pending_rows), 3)
    fail_if(len(active_rows) != 1, failures, "active_stage_rows_one", len(active_rows), 1)
    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("pending_action_rows") != len(pending_rows), failures, "pending_action_rows_bound", report.get("pending_action_rows"), len(pending_rows))
    fail_if(report.get("active_stage_rows") != len(active_rows), failures, "active_stage_rows_bound", report.get("active_stage_rows"), len(active_rows))
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(release.get("release_ready") is not False, failures, "source_release_ready_false", release.get("release_ready"), False)
    fail_if(report.get("customer_delivery_ready") is not False, failures, "customer_delivery_ready_false", report.get("customer_delivery_ready"), False)
    fail_if(customer.get("ready") is not False, failures, "source_customer_ready_false", customer.get("ready"), False)
    fail_if(report.get("governance_ready") is not False, failures, "governance_ready_false", report.get("governance_ready"), False)
    fail_if(governance.get("ready") is not False, failures, "source_governance_ready_false", governance.get("ready"), False)
    fail_if(report.get("operator_review_ready") is not False, failures, "operator_review_ready_false", report.get("operator_review_ready"), False)
    fail_if(operator.get("ready") is not False, failures, "source_operator_ready_false", operator.get("ready"), False)
    fail_if(report.get("operator_completed_action_rows") != operator_completion.get("completed_rows"), failures, "operator_completed_rows_bound", report.get("operator_completed_action_rows"), operator_completion.get("completed_rows"))
    fail_if(report.get("operator_all_actions_completed") is not False, failures, "operator_all_actions_completed_false", report.get("operator_all_actions_completed"), False)
    fail_if(report.get("claim_matrix_blocked_claims") != claims.get("claims_blocked"), failures, "claim_matrix_blocked_claims_bound", report.get("claim_matrix_blocked_claims"), claims.get("claims_blocked"))
    fail_if(report.get("local_release_review_package_ready") is not False, failures, "release_claim_ready_false", report.get("local_release_review_package_ready"), False)
    fail_if(report.get("local_release_review_package_allowed") is not False, failures, "release_claim_allowed_false", report.get("local_release_review_package_allowed"), False)
    fail_if(release_claim.get("ready") is not False or release_claim.get("allowed") is not False, failures, "source_release_claim_blocked", {"ready": release_claim.get("ready"), "allowed": release_claim.get("allowed")}, {"ready": False, "allowed": False})
    fail_if(report.get("active_stage_execution_matrix_production_execution_allowed") is not False, failures, "active_stage_production_allowed_false", report.get("active_stage_execution_matrix_production_execution_allowed"), False)
    fail_if(summary.get("active_stage_execution_matrix_production_execution_allowed") is not False, failures, "source_active_stage_production_allowed_false", summary.get("active_stage_execution_matrix_production_execution_allowed"), False)

    seen_types = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"p31_pending_production_action", "p31_active_stage_execution_gate", "p31_release_and_production_summary"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P31 gap type")
        for field in (
            "training_import_allowed",
            "safe_for_training_import",
            "safe_for_model_claim",
            "customer_delivery_ready",
            "release_ready",
            "production_execution_allowed",
            "sync_allowed",
            "deploy_allowed",
            "restart_allowed",
            "grey_release_allowed",
            "completion_ready",
        ):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "p31_pending_production_action":
            source = next((item for item in pending_rows if item.get("action_id") == row.get("action_id")), {})
            fail_if(row.get("status") != source.get("status"), failures, "pending_status_bound", {"index": idx, "observed": row.get("status")}, source.get("status"))
            fail_if(source.get("production_execution_allowed") is not False, failures, "pending_source_production_allowed_false", {"index": idx, "observed": source.get("production_execution_allowed")}, False)
        if gap_type == "p31_active_stage_execution_gate":
            source = active_rows[0] if active_rows else {}
            fail_if(row.get("stage_status") != source.get("status"), failures, "active_stage_status_bound", {"index": idx, "observed": row.get("stage_status")}, source.get("status"))
            fail_if(source.get("production_execution_allowed") is not False, failures, "active_stage_source_production_allowed_false", {"index": idx, "observed": source.get("production_execution_allowed")}, False)
        if gap_type == "p31_release_and_production_summary":
            fail_if(row.get("local_release_review_package_ready") is not False, failures, "summary_release_claim_ready_false", row.get("local_release_review_package_ready"), False)
            fail_if(row.get("local_release_review_package_allowed") is not False, failures, "summary_release_claim_allowed_false", row.get("local_release_review_package_allowed"), False)

    fail_if(seen_types.count("p31_pending_production_action") != len(pending_rows), failures, "pending_audit_type_count", seen_types.count("p31_pending_production_action"), len(pending_rows))
    fail_if(seen_types.count("p31_active_stage_execution_gate") != len(active_rows), failures, "active_audit_type_count", seen_types.count("p31_active_stage_execution_gate"), len(active_rows))
    fail_if(seen_types.count("p31_release_and_production_summary") != 1, failures, "summary_audit_type_count", seen_types.count("p31_release_and_production_summary"), 1)
    for field in (
        "training_import_allowed",
        "safe_for_training_import",
        "safe_for_model_claim",
        "customer_delivery_ready_for_release",
        "release_ready",
        "production_execution_allowed",
        "sync_allowed",
        "deploy_allowed",
        "restart_allowed",
        "grey_release_allowed",
    ):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "pending_action_rows": len(pending_rows),
        "active_stage_rows": len(active_rows),
        "operator_completed_action_rows": operator_completion.get("completed_rows"),
        "claim_matrix_blocked_claims": claims.get("claims_blocked"),
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "sync_allowed": False,
        "deploy_allowed": False,
        "restart_allowed": False,
        "grey_release_allowed": False,
        "policy": "Validation only. P31 production execution remains blocked and does not authorize sync, deploy, restart, grey release, or release.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "audit_rows": validation["audit_rows"],
        "pending_action_rows": validation["pending_action_rows"],
        "active_stage_rows": validation["active_stage_rows"],
        "production_execution_allowed": False,
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
