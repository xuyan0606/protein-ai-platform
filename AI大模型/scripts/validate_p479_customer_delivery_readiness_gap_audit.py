#!/usr/bin/env python3
"""Validate the P479 customer delivery readiness gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CUSTOMER = AI_ROOT / "reports" / "customer_delivery_readiness_report.json"
GOVERNANCE = AI_ROOT / "reports" / "governance_readiness_report.json"
LICENSE = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"
BIOSECURITY_DECISIONS = AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json"
IP_FTO = AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json"
HUMAN_CLOSEOUT = AI_ROOT / "reports" / "human_review_closeout_board_report.json"
BENCHMARK = AI_ROOT / "reports" / "benchmark_matrix_report.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p479_customer_delivery_readiness_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p479_customer_delivery_readiness_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p479_customer_delivery_readiness_gap_audit_validation_report.json"


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
    customer = load_json(CUSTOMER)
    governance = load_json(GOVERNANCE)
    license_report = load_json(LICENSE)
    biosecurity_decisions = load_json(BIOSECURITY_DECISIONS)
    ip_fto = load_json(IP_FTO)
    human_closeout = load_json(HUMAN_CLOSEOUT)
    benchmark = load_json(BENCHMARK)
    claim_matrix = load_json(CLAIM_MATRIX)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    checks = customer.get("checks") or {}
    blockers = list(customer.get("blockers") or [])
    passed_checks = sum(1 for value in checks.values() if value is True)
    failed_checks = sum(1 for value in checks.values() if value is False)
    expected_rows = len(blockers) + 1
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("blocker_audit_rows") != len(blockers), failures, "blocker_audit_rows_bound", report.get("blocker_audit_rows"), len(blockers))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("ready") is not False, failures, "report_ready_false", report.get("ready"), False)
    fail_if(customer.get("ready") is not False, failures, "customer_ready_false", customer.get("ready"), False)
    fail_if(report.get("delivery_class") != customer.get("delivery_class"), failures, "delivery_class_bound", report.get("delivery_class"), customer.get("delivery_class"))
    fail_if(report.get("checks") != checks, failures, "checks_bound", report.get("checks"), checks)
    fail_if(report.get("blockers") != blockers, failures, "blockers_bound", report.get("blockers"), blockers)
    fail_if(report.get("passed_checks") != passed_checks, failures, "passed_checks_bound", report.get("passed_checks"), passed_checks)
    fail_if(report.get("failed_checks") != failed_checks, failures, "failed_checks_bound", report.get("failed_checks"), failed_checks)
    fail_if(report.get("governance_ready") is not False, failures, "governance_ready_false", report.get("governance_ready"), False)
    fail_if(report.get("license_ready_for_customer_delivery") is not False, failures, "license_ready_for_customer_delivery_false", report.get("license_ready_for_customer_delivery"), False)
    fail_if(report.get("license_verified_customer_delivery_rows") != license_report.get("verified_customer_delivery_rows"), failures, "license_verified_customer_delivery_rows_bound", report.get("license_verified_customer_delivery_rows"), license_report.get("verified_customer_delivery_rows"))
    fail_if(report.get("ip_fto_ready_for_customer_delivery") is not False, failures, "ip_fto_ready_for_customer_delivery_false", report.get("ip_fto_ready_for_customer_delivery"), False)
    fail_if(report.get("ip_fto_approved_for_customer_delivery_rows") != ip_fto.get("approved_for_customer_delivery_rows"), failures, "ip_fto_approved_rows_bound", report.get("ip_fto_approved_for_customer_delivery_rows"), ip_fto.get("approved_for_customer_delivery_rows"))
    fail_if(report.get("biosecurity_ready_for_ordering") is not False, failures, "biosecurity_ready_for_ordering_false", report.get("biosecurity_ready_for_ordering"), False)
    fail_if(report.get("biosecurity_approved_for_ordering_rows") != biosecurity_decisions.get("approved_for_ordering_rows"), failures, "biosecurity_approved_rows_bound", report.get("biosecurity_approved_for_ordering_rows"), biosecurity_decisions.get("approved_for_ordering_rows"))
    fail_if(report.get("human_closeout_completion_ready_rows") != human_closeout.get("completion_ready_rows"), failures, "human_closeout_completion_ready_rows_bound", report.get("human_closeout_completion_ready_rows"), human_closeout.get("completion_ready_rows"))
    fail_if(report.get("benchmark_ready_for_model_claim") is not False, failures, "benchmark_ready_for_model_claim_false", report.get("benchmark_ready_for_model_claim"), False)
    fail_if(report.get("claims_allowed") != claim_matrix.get("claims_allowed"), failures, "claims_allowed_bound", report.get("claims_allowed"), claim_matrix.get("claims_allowed"))
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    fail_if(report.get("customer_sequence_package_blocked") is not True, failures, "customer_sequence_package_blocked_true", report.get("customer_sequence_package_blocked"), True)

    seen_blockers: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"customer_delivery_readiness_blocker_gap", "customer_delivery_readiness_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P479 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "customer_delivery_readiness_blocker_gap":
            blocker_id = row.get("blocker_id")
            seen_blockers.append(blocker_id)
            fail_if(blocker_id not in blockers, failures, "blocker_id_known", {"index": idx, "observed": blocker_id}, blockers)
            fail_if(row.get("customer_check_passed") is not False, failures, "blocker_check_false", {"index": idx, "observed": row.get("customer_check_passed")}, False)
            source_state = row.get("source_state") or {}
            fail_if(source_state.get("customer_check_passed") is not False, failures, "source_state_check_false", {"index": idx, "observed": source_state.get("customer_check_passed")}, False)
        if gap_type == "customer_delivery_readiness_summary_gap":
            fail_if(row.get("ready") is not False, failures, "summary_ready_false", row.get("ready"), False)
            fail_if(row.get("blocker_count") != len(blockers), failures, "summary_blocker_count_bound", row.get("blocker_count"), len(blockers))
            fail_if(row.get("passed_checks") != passed_checks, failures, "summary_passed_checks_bound", row.get("passed_checks"), passed_checks)
            fail_if(row.get("failed_checks") != failed_checks, failures, "summary_failed_checks_bound", row.get("failed_checks"), failed_checks)

    fail_if(sorted(seen_blockers) != sorted(blockers), failures, "blockers_exactly_covered", sorted(seen_blockers), sorted(blockers))
    fail_if(seen_types.count("customer_delivery_readiness_blocker_gap") != len(blockers), failures, "blocker_gap_type_count", seen_types.count("customer_delivery_readiness_blocker_gap"), len(blockers))
    fail_if(seen_types.count("customer_delivery_readiness_summary_gap") != 1, failures, "summary_type_count", seen_types.count("customer_delivery_readiness_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "blocker_audit_rows": len(blockers),
        "ready": False,
        "blockers": blockers,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Customer delivery readiness gaps do not authorize customer delivery, claims, release, production execution, or training import.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "blocker_audit_rows": result["blocker_audit_rows"],
        "failed_checks": failed_checks,
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
