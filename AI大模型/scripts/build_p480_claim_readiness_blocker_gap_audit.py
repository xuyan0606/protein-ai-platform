#!/usr/bin/env python3
"""Build a source-bound audit of claim readiness blocker gaps."""

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
MASTER = AI_ROOT / "reports" / "master_readiness_board.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p480_claim_readiness_blocker_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p480_claim_readiness_blocker_gap_audit_report.json"


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
        "source_report": "reports/claim_readiness_matrix.json",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Claim readiness blocker audit only; blocked claim rows do not approve training, model claims, customer delivery, release, ordering, legal clearance, or production execution.",
    }


def main() -> int:
    claim_matrix = load_json(CLAIM_MATRIX)
    claim_policy = load_json(CLAIM_POLICY)
    claim_policy_current = load_json(CLAIM_POLICY_CURRENT)
    claim_policy_current_regression = load_json(CLAIM_POLICY_CURRENT_REGRESSION)
    local_release = load_json(LOCAL_RELEASE)
    customer_delivery = load_json(CUSTOMER_DELIVERY)
    master = load_json(MASTER)
    claims = [row for row in claim_matrix.get("claims") or [] if isinstance(row, dict)]
    blocked_claim_ids = list(claim_matrix.get("blocked_claim_ids") or [])
    blocked_claims = [row for row in claims if row.get("claim_id") in set(blocked_claim_ids)]
    readiness_summary = local_release.get("readiness_summary") or {}
    rows: list[dict[str, Any]] = []

    for claim in blocked_claims:
        claim_id = claim.get("claim_id")
        rows.append(base(
            f"p480-claim-readiness::{claim_id}",
            "claim_readiness_blocker_gap",
            {
                "claim_id": claim_id,
                "label": claim.get("label"),
                "scope": claim.get("scope"),
                "ready": claim.get("ready"),
                "allowed": claim.get("allowed"),
                "status": claim.get("status"),
                "missing_requirements": claim.get("missing_requirements") or [],
                "requirement_count": len(claim.get("requirements") or []),
                "policy": claim.get("policy"),
                "local_release_ready": local_release.get("release_ready"),
                "customer_delivery_ready": customer_delivery.get("ready"),
                "master_overall_status": readiness_summary.get("master_overall_status") or master.get("overall_status"),
            },
            f"claim remains blocked and cannot be promoted: {claim_id}",
        ) | {
            "claim_id": claim_id,
            "scope": claim.get("scope"),
            "status": claim.get("status"),
            "missing_requirement_count": len(claim.get("missing_requirements") or []),
            "allowed": False,
            "ready": False,
            "completion_ready": False,
        })

    rows.append(base(
        "p480-claim-readiness-summary",
        "claim_readiness_blocker_summary_gap",
        {
            "claims_allowed": claim_matrix.get("claims_allowed"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
            "allowed_claim_ids": claim_matrix.get("allowed_claim_ids") or [],
            "blocked_claim_ids": blocked_claim_ids,
            "policy_success": claim_policy.get("success"),
            "policy_failures": claim_policy.get("failures"),
            "policy_current_success": claim_policy_current.get("success"),
            "policy_current_failure_count": claim_policy_current.get("failure_count"),
            "policy_current_regression_success": claim_policy_current_regression.get("success"),
            "policy_current_regression_failed_rows": claim_policy_current_regression.get("failed_rows"),
            "local_release_ready": local_release.get("release_ready"),
            "customer_delivery_ready": customer_delivery.get("ready"),
            "master_overall_status": readiness_summary.get("master_overall_status") or master.get("overall_status"),
            "ready_streams": readiness_summary.get("ready_streams"),
            "total_streams": readiness_summary.get("total_streams"),
        },
        "claim readiness matrix still blocks all high-risk claims and cannot authorize downstream gates",
    ) | {
        "claims_allowed": claim_matrix.get("claims_allowed"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "blocked_claim_rows": len(blocked_claims),
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "blocked_claim_rows": len(blocked_claims),
        "summary_audit_rows": 1,
        "claims_allowed": claim_matrix.get("claims_allowed"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "allowed_claim_ids": claim_matrix.get("allowed_claim_ids") or [],
        "blocked_claim_ids": blocked_claim_ids,
        "policy_success": claim_policy.get("success"),
        "policy_failure_count": len(claim_policy.get("failures") or []),
        "policy_current_success": claim_policy_current.get("success"),
        "policy_current_failure_count": claim_policy_current.get("failure_count"),
        "policy_current_regression_success": claim_policy_current_regression.get("success"),
        "policy_current_regression_failed_rows": claim_policy_current_regression.get("failed_rows"),
        "local_release_ready": local_release.get("release_ready"),
        "customer_delivery_ready_source": customer_delivery.get("ready"),
        "master_overall_status": readiness_summary.get("master_overall_status") or master.get("overall_status"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p480_claim_readiness_blocker_gap_audit.jsonl",
        "policy": "P480 audit only. Blocked claim rows remain fail-closed until explicit source requirements and promotion decisions pass.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "blocked_claim_rows": report["blocked_claim_rows"],
        "claims_allowed": report["claims_allowed"],
        "claims_blocked": report["claims_blocked"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
