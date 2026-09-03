#!/usr/bin/env python3
"""Build a source-bound audit of local release blocked capability gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
LOCAL_RELEASE_CONSISTENCY = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
SAFETY_GUARD = AI_ROOT / "reports" / "local_release_safety_guard_link_validation_report.json"
GUARD_COVERAGE = AI_ROOT / "reports" / "local_release_guard_coverage_validation_report.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
CUSTOMER_DELIVERY = AI_ROOT / "reports" / "customer_delivery_readiness_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p481_local_release_blocked_capability_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p481_local_release_blocked_capability_gap_audit_report.json"


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
        "source_report": "reports/local_release_manifest.json",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Local release blocked-capability audit only; local release manifests and review packages do not approve training, model claims, customer delivery, ordering, legal clearance, external tool production use, or production execution.",
    }


def capability_source_state(capability: str, release: dict[str, Any], claim_matrix: dict[str, Any], customer: dict[str, Any]) -> dict[str, Any]:
    summary = release.get("readiness_summary") or {}
    common = {
        "capability": capability,
        "release_ready": release.get("release_ready"),
        "blocked_capabilities": release.get("blocked_capabilities") or [],
        "artifact_count": release.get("artifact_count"),
        "master_overall_status": summary.get("master_overall_status"),
    }
    if capability == "model_quality_claim":
        return common | {
            "safe_for_model_claim": summary.get("safe_for_model_claim"),
            "claim_matrix_blocked_claims": summary.get("claim_matrix_blocked_claims"),
            "model_quality_claim_blocked": "model_quality_claim" in set(claim_matrix.get("blocked_claim_ids") or []),
            "benchmark_ready_for_model_claim": summary.get("benchmark_ready_for_model_claim"),
            "five_head_ready_heads": summary.get("five_head_training_execution_ready_heads"),
        }
    if capability == "customer_delivery":
        return common | {
            "customer_delivery_ready": summary.get("customer_delivery_ready"),
            "customer_delivery_source_ready": customer.get("ready"),
            "customer_sequence_package_blocked": "customer_sequence_package" in set(claim_matrix.get("blocked_claim_ids") or []),
            "p479_failed_checks": summary.get("p479_customer_delivery_readiness_gap_audit_failed_checks"),
        }
    if capability == "approved_for_ordering":
        return common | {
            "biosecurity_ready_for_ordering": summary.get("biosecurity_ready_for_ordering"),
            "biosecurity_decision_ready_for_ordering": summary.get("biosecurity_decision_ready_for_ordering"),
            "approved_for_ordering_blocked": "approved_for_ordering" in set(claim_matrix.get("blocked_claim_ids") or []),
        }
    if capability == "IP/FTO conclusion":
        return common | {
            "sequence_ip_fto_decision_rows": summary.get("sequence_ip_fto_decision_rows"),
            "sequence_ip_fto_approved_for_delivery": summary.get("sequence_ip_fto_approved_for_delivery"),
            "sequence_ip_fto_ready_for_delivery": summary.get("sequence_ip_fto_ready_for_delivery"),
            "ip_fto_cleared_blocked": "ip_fto_cleared" in set(claim_matrix.get("blocked_claim_ids") or []),
        }
    if capability == "external tool production use":
        return common | {
            "license_ready_for_customer_delivery": summary.get("license_ready_for_customer_delivery"),
            "governance_ready": summary.get("governance_ready"),
            "external_tool_production_use_blocked": "external_tool_production_use" in set(claim_matrix.get("blocked_claim_ids") or []),
        }
    return common | {
        "advanced_model_safe_for_model_claim": summary.get("advanced_model_safe_for_model_claim"),
        "advanced_model_feature_contract_safe_for_model_claim": summary.get("advanced_model_feature_contract_safe_for_model_claim"),
        "mcp_wrapper_staging_production_allowed_rows": summary.get("mcp_wrapper_staging_production_allowed_rows"),
    }


def main() -> int:
    release = load_json(LOCAL_RELEASE)
    consistency = load_json(LOCAL_RELEASE_CONSISTENCY)
    safety_guard = load_json(SAFETY_GUARD)
    guard_coverage = load_json(GUARD_COVERAGE)
    claim_matrix = load_json(CLAIM_MATRIX)
    customer = load_json(CUSTOMER_DELIVERY)
    blocked_capabilities = list(release.get("blocked_capabilities") or [])
    rows: list[dict[str, Any]] = []

    for capability in blocked_capabilities:
        rows.append(base(
            f"p481-local-blocked-capability::{capability}",
            "local_release_blocked_capability_gap",
            capability_source_state(capability, release, claim_matrix, customer),
            f"local release capability remains blocked: {capability}",
        ) | {
            "capability": capability,
            "blocked": True,
            "completion_ready": False,
        })

    rows.append(base(
        "p481-local-blocked-capability-summary",
        "local_release_blocked_capability_summary_gap",
        {
            "release_ready": release.get("release_ready"),
            "blocked_capabilities": blocked_capabilities,
            "artifact_count": release.get("artifact_count"),
            "missing_artifacts": release.get("missing_artifacts") or [],
            "consistency_success": consistency.get("success"),
            "consistency_failures": consistency.get("failure_count"),
            "safety_guard_success": safety_guard.get("success"),
            "safety_guard_failures": safety_guard.get("failure_count"),
            "guard_coverage_success": guard_coverage.get("success"),
            "guard_coverage_failures": guard_coverage.get("failure_count"),
            "claims_allowed": claim_matrix.get("claims_allowed"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "local release remains blocked and cannot authorize customer, model, ordering, legal, external-tool, or production capabilities",
    ) | {
        "blocked_capability_count": len(blocked_capabilities),
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "blocked_capability_rows": len(blocked_capabilities),
        "summary_audit_rows": 1,
        "blocked_capabilities": blocked_capabilities,
        "release_ready_source": release.get("release_ready"),
        "artifact_count": release.get("artifact_count"),
        "missing_artifacts": release.get("missing_artifacts") or [],
        "consistency_success": consistency.get("success"),
        "consistency_failure_count": consistency.get("failure_count"),
        "safety_guard_success": safety_guard.get("success"),
        "safety_guard_failure_count": safety_guard.get("failure_count"),
        "guard_coverage_success": guard_coverage.get("success"),
        "guard_coverage_failure_count": guard_coverage.get("failure_count"),
        "claims_allowed": claim_matrix.get("claims_allowed"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p481_local_release_blocked_capability_gap_audit.jsonl",
        "policy": "P481 audit only. Blocked local-release capabilities remain fail-closed until their source gates and formal decisions pass.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "blocked_capability_rows": report["blocked_capability_rows"],
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
