#!/usr/bin/env python3
"""Build a source-bound audit of customer delivery readiness gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CUSTOMER = AI_ROOT / "reports" / "customer_delivery_readiness_report.json"
GOVERNANCE = AI_ROOT / "reports" / "governance_readiness_report.json"
LICENSE = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"
BIOSECURITY = AI_ROOT / "reports" / "biosecurity_readiness_report.json"
BIOSECURITY_DECISIONS = AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json"
IP_FTO = AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json"
HUMAN_LAUNCH = AI_ROOT / "reports" / "human_review_launch_board_report.json"
HUMAN_CLOSEOUT = AI_ROOT / "reports" / "human_review_closeout_board_report.json"
BENCHMARK = AI_ROOT / "reports" / "benchmark_matrix_report.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p479_customer_delivery_readiness_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p479_customer_delivery_readiness_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base(audit_id: str, gap_type: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": "reports/customer_delivery_readiness_report.json",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Customer delivery readiness audit only; readiness blockers do not approve customer delivery, model claims, release, production execution, or training import.",
    }


def blocker_state(
    blocker: str,
    customer: dict[str, Any],
    governance: dict[str, Any],
    license_report: dict[str, Any],
    biosecurity: dict[str, Any],
    biosecurity_decisions: dict[str, Any],
    ip_fto: dict[str, Any],
    human_launch: dict[str, Any],
    human_closeout: dict[str, Any],
    benchmark: dict[str, Any],
    claim_matrix: dict[str, Any],
) -> dict[str, Any]:
    checks = customer.get("checks") or {}
    common = {
        "blocker": blocker,
        "customer_check_passed": checks.get(blocker),
        "customer_ready": customer.get("ready"),
    }
    if blocker in {"data_license_clearance", "tool_license_clearance", "verified_component_customer_delivery_scope"}:
        return common | {
            "decision_rows": license_report.get("decision_rows"),
            "valid_rows": license_report.get("valid_rows"),
            "approved_for_training_rows": license_report.get("approved_for_training_rows"),
            "approved_for_local_evaluation_rows": license_report.get("approved_for_local_evaluation_rows"),
            "approved_for_customer_delivery_rows": license_report.get("approved_for_customer_delivery_rows"),
            "verified_customer_delivery_rows": license_report.get("verified_customer_delivery_rows"),
            "ready_for_training": license_report.get("ready_for_training"),
            "ready_for_customer_delivery": license_report.get("ready_for_customer_delivery"),
            "authorization_status_counts": license_report.get("authorization_status_counts") or {},
            "capability_authorization_counts": license_report.get("capability_authorization_counts") or {},
        }
    if blocker == "ip_fto_review":
        return common | {
            "packet_rows": ip_fto.get("packet_rows"),
            "decision_rows": ip_fto.get("decision_rows"),
            "valid_rows": ip_fto.get("valid_rows"),
            "approved_for_customer_delivery_rows": ip_fto.get("approved_for_customer_delivery_rows"),
            "missing_delivery_decisions": ip_fto.get("missing_delivery_decisions") or [],
            "ready_for_customer_delivery": ip_fto.get("ready_for_customer_delivery"),
        }
    if blocker == "biosecurity_approval":
        return common | {
            "biosecurity_ready_for_ordering": biosecurity.get("ready_for_ordering"),
            "decision_rows": biosecurity_decisions.get("decision_rows"),
            "valid_rows": biosecurity_decisions.get("valid_rows"),
            "approved_for_ordering_rows": biosecurity_decisions.get("approved_for_ordering_rows"),
            "missing_draft_decisions": biosecurity_decisions.get("missing_draft_decisions") or [],
            "decision_ready_for_ordering": biosecurity_decisions.get("ready_for_ordering"),
        }
    if blocker == "human_delivery_approval":
        return common | {
            "launch_rows": human_launch.get("launch_rows"),
            "ready_for_human_review_rows": human_launch.get("ready_for_human_review_rows"),
            "total_packet_rows": human_launch.get("total_packet_rows"),
            "closeout_rows": human_closeout.get("closeout_rows"),
            "awaiting_human_decision_rows": human_closeout.get("awaiting_human_decision_rows"),
            "total_formal_decision_rows": human_closeout.get("total_formal_decision_rows"),
            "completion_ready_rows": human_closeout.get("completion_ready_rows"),
        }
    if blocker == "allowed_claims_review":
        return common | {
            "claims_allowed": claim_matrix.get("claims_allowed"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
            "allowed_claim_ids": claim_matrix.get("allowed_claim_ids") or [],
            "blocked_claim_ids": claim_matrix.get("blocked_claim_ids") or [],
            "customer_sequence_package_blocked": "customer_sequence_package" in set(claim_matrix.get("blocked_claim_ids") or []),
        }
    if blocker == "benchmark_scorecards":
        return common | {
            "ready_for_model_claim": benchmark.get("ready_for_model_claim"),
            "head_count": len(benchmark.get("heads") or []),
            "blocked_heads": [row.get("head") for row in benchmark.get("heads") or [] if row.get("status") != "ready"],
        }
    return common | {
        "governance_ready": governance.get("ready"),
        "governance_blockers": governance.get("blockers") or [],
    }


def main() -> int:
    customer = load_json(CUSTOMER)
    governance = load_json(GOVERNANCE)
    license_report = load_json(LICENSE)
    biosecurity = load_json(BIOSECURITY)
    biosecurity_decisions = load_json(BIOSECURITY_DECISIONS)
    ip_fto = load_json(IP_FTO)
    human_launch = load_json(HUMAN_LAUNCH)
    human_closeout = load_json(HUMAN_CLOSEOUT)
    benchmark = load_json(BENCHMARK)
    claim_matrix = load_json(CLAIM_MATRIX)
    checks = customer.get("checks") or {}
    blockers = list(customer.get("blockers") or [])
    rows: list[dict[str, Any]] = []

    for blocker in blockers:
        source_state = blocker_state(
            blocker,
            customer,
            governance,
            license_report,
            biosecurity,
            biosecurity_decisions,
            ip_fto,
            human_launch,
            human_closeout,
            benchmark,
            claim_matrix,
        )
        rows.append(base(
            f"p479-customer-delivery::{blocker}",
            "customer_delivery_readiness_blocker_gap",
            source_state,
            f"customer delivery blocker remains unresolved: {blocker}",
        ) | {
            "blocker_id": blocker,
            "customer_check_passed": checks.get(blocker),
            "completion_ready": False,
        })

    passed_checks = sum(1 for value in checks.values() if value is True)
    failed_checks = sum(1 for value in checks.values() if value is False)
    rows.append(base(
        "p479-customer-delivery-summary",
        "customer_delivery_readiness_summary_gap",
        {
            "ready": customer.get("ready"),
            "delivery_class": customer.get("delivery_class"),
            "checks": checks,
            "blockers": blockers,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "governance_ready": governance.get("ready"),
            "governance_blockers": governance.get("blockers") or [],
            "license_ready_for_customer_delivery": license_report.get("ready_for_customer_delivery"),
            "ip_fto_ready_for_customer_delivery": ip_fto.get("ready_for_customer_delivery"),
            "biosecurity_ready_for_ordering": biosecurity_decisions.get("ready_for_ordering"),
            "human_closeout_completion_ready_rows": human_closeout.get("completion_ready_rows"),
            "benchmark_ready_for_model_claim": benchmark.get("ready_for_model_claim"),
            "claims_allowed": claim_matrix.get("claims_allowed"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "customer delivery readiness remains blocked and cannot authorize customer sequence packages",
    ) | {
        "ready": False,
        "blocker_count": len(blockers),
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "blocker_audit_rows": len(blockers),
        "summary_audit_rows": 1,
        "ready": False,
        "delivery_class": customer.get("delivery_class"),
        "checks": checks,
        "blockers": blockers,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "governance_ready": governance.get("ready"),
        "license_ready_for_customer_delivery": license_report.get("ready_for_customer_delivery"),
        "license_verified_customer_delivery_rows": license_report.get("verified_customer_delivery_rows"),
        "ip_fto_ready_for_customer_delivery": ip_fto.get("ready_for_customer_delivery"),
        "ip_fto_approved_for_customer_delivery_rows": ip_fto.get("approved_for_customer_delivery_rows"),
        "biosecurity_ready_for_ordering": biosecurity_decisions.get("ready_for_ordering"),
        "biosecurity_approved_for_ordering_rows": biosecurity_decisions.get("approved_for_ordering_rows"),
        "human_closeout_completion_ready_rows": human_closeout.get("completion_ready_rows"),
        "benchmark_ready_for_model_claim": benchmark.get("ready_for_model_claim"),
        "claims_allowed": claim_matrix.get("claims_allowed"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "customer_sequence_package_blocked": "customer_sequence_package" in set(claim_matrix.get("blocked_claim_ids") or []),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p479_customer_delivery_readiness_gap_audit.jsonl",
        "policy": "P479 audit only. Customer delivery readiness remains blocked until all source gates and human approvals pass.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "blocker_audit_rows": report["blocker_audit_rows"],
        "ready": report["ready"],
        "blockers": len(blockers),
        "failed_checks": failed_checks,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
