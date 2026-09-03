#!/usr/bin/env python3
"""Validate the P480 claim readiness blocker gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
CLAIM_POLICY = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_validation_report.json"
CLAIM_POLICY_CURRENT = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_validation_report.json"
CLAIM_POLICY_CURRENT_REGRESSION = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_current_regression_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CUSTOMER_DELIVERY = AI_ROOT / "reports" / "customer_delivery_readiness_report.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p480_claim_readiness_blocker_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p480_claim_readiness_blocker_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p480_claim_readiness_blocker_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    claim_matrix = load_json(CLAIM_MATRIX)
    claim_policy = load_json(CLAIM_POLICY)
    claim_policy_current = load_json(CLAIM_POLICY_CURRENT)
    claim_policy_current_regression = load_json(CLAIM_POLICY_CURRENT_REGRESSION)
    local_release = load_json(LOCAL_RELEASE)
    customer_delivery = load_json(CUSTOMER_DELIVERY)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    claims = [row for row in claim_matrix.get("claims") or [] if isinstance(row, dict)]
    blocked_claim_ids = list(claim_matrix.get("blocked_claim_ids") or [])
    allowed_claim_ids = list(claim_matrix.get("allowed_claim_ids") or [])
    blocked_claims = [row for row in claims if row.get("claim_id") in set(blocked_claim_ids)]
    failures: list[dict[str, Any]] = []
    expected_rows = len(blocked_claims) + 1

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("blocked_claim_rows") != len(blocked_claims), failures, "blocked_claim_rows_bound", report.get("blocked_claim_rows"), len(blocked_claims))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("claims_allowed") != claim_matrix.get("claims_allowed"), failures, "claims_allowed_bound", report.get("claims_allowed"), claim_matrix.get("claims_allowed"))
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(report.get("allowed_claim_ids") != allowed_claim_ids, failures, "allowed_claim_ids_bound", report.get("allowed_claim_ids"), allowed_claim_ids)
    fail_if(report.get("blocked_claim_ids") != blocked_claim_ids, failures, "blocked_claim_ids_bound", report.get("blocked_claim_ids"), blocked_claim_ids)
    fail_if(report.get("policy_success") is not True, failures, "policy_success_true", report.get("policy_success"), True)
    fail_if(report.get("policy_failure_count") != len(claim_policy.get("failures") or []), failures, "policy_failure_count_bound", report.get("policy_failure_count"), len(claim_policy.get("failures") or []))
    fail_if(report.get("policy_current_success") is not True, failures, "policy_current_success_true", report.get("policy_current_success"), True)
    fail_if(report.get("policy_current_failure_count") != claim_policy_current.get("failure_count"), failures, "policy_current_failure_count_bound", report.get("policy_current_failure_count"), claim_policy_current.get("failure_count"))
    fail_if(report.get("policy_current_regression_success") is not True, failures, "policy_current_regression_success_true", report.get("policy_current_regression_success"), True)
    fail_if(report.get("policy_current_regression_failed_rows") != claim_policy_current_regression.get("failed_rows"), failures, "policy_current_regression_failed_rows_bound", report.get("policy_current_regression_failed_rows"), claim_policy_current_regression.get("failed_rows"))
    fail_if(report.get("local_release_ready") is not False, failures, "local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(report.get("customer_delivery_ready_source") is not False, failures, "customer_delivery_ready_source_false", report.get("customer_delivery_ready_source"), False)
    fail_if(claim_matrix.get("claims_allowed") != 1, failures, "claims_allowed_one", claim_matrix.get("claims_allowed"), 1)
    fail_if(claim_matrix.get("claims_blocked") != len(blocked_claims), failures, "claims_blocked_exact", claim_matrix.get("claims_blocked"), len(blocked_claims))
    fail_if(allowed_claim_ids != ["internal_design_review_artifacts"], failures, "only_internal_design_review_allowed", allowed_claim_ids, ["internal_design_review_artifacts"])

    blocked_by_id = {row.get("claim_id"): row for row in blocked_claims}
    seen_claim_ids: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"claim_readiness_blocker_gap", "claim_readiness_blocker_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P480 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "claim_readiness_blocker_gap":
            claim_id = row.get("claim_id")
            seen_claim_ids.append(claim_id)
            source = blocked_by_id.get(claim_id, {})
            fail_if(claim_id not in blocked_by_id, failures, "claim_id_blocked", {"index": idx, "observed": claim_id}, sorted(blocked_by_id))
            fail_if(row.get("scope") != source.get("scope"), failures, "claim_scope_bound", {"index": idx, "observed": row.get("scope")}, source.get("scope"))
            fail_if(row.get("status") != "blocked", failures, "claim_status_blocked", {"index": idx, "observed": row.get("status")}, "blocked")
            fail_if(row.get("allowed") is not False, failures, "claim_allowed_false", {"index": idx, "observed": row.get("allowed")}, False)
            fail_if(row.get("ready") is not False, failures, "claim_ready_false", {"index": idx, "observed": row.get("ready")}, False)
            fail_if(row.get("missing_requirement_count") != len(source.get("missing_requirements") or []), failures, "missing_requirement_count_bound", {"index": idx, "observed": row.get("missing_requirement_count")}, len(source.get("missing_requirements") or []))
        if gap_type == "claim_readiness_blocker_summary_gap":
            fail_if(row.get("claims_allowed") != claim_matrix.get("claims_allowed"), failures, "summary_claims_allowed_bound", row.get("claims_allowed"), claim_matrix.get("claims_allowed"))
            fail_if(row.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "summary_claims_blocked_bound", row.get("claims_blocked"), claim_matrix.get("claims_blocked"))
            fail_if(row.get("blocked_claim_rows") != len(blocked_claims), failures, "summary_blocked_claim_rows_bound", row.get("blocked_claim_rows"), len(blocked_claims))

    fail_if(sorted(seen_claim_ids) != sorted(blocked_claim_ids), failures, "blocked_claims_exactly_covered", sorted(seen_claim_ids), sorted(blocked_claim_ids))
    fail_if(seen_types.count("claim_readiness_blocker_gap") != len(blocked_claims), failures, "claim_gap_type_count", seen_types.count("claim_readiness_blocker_gap"), len(blocked_claims))
    fail_if(seen_types.count("claim_readiness_blocker_summary_gap") != 1, failures, "summary_type_count", seen_types.count("claim_readiness_blocker_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "blocked_claim_rows": len(blocked_claims),
        "claims_allowed": claim_matrix.get("claims_allowed"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "blocked_claim_ids": blocked_claim_ids,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Blocked claim rows remain non-authorizing until source requirements and promotion decisions pass.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "blocked_claim_rows": result["blocked_claim_rows"],
        "claims_blocked": result["claims_blocked"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
