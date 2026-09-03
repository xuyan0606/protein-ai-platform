#!/usr/bin/env python3
"""Build fail-closed customer delivery readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "customer_delivery_readiness_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build customer delivery readiness report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    governance = load_json(AI_ROOT / "reports" / "governance_readiness_report.json")
    biosecurity = load_json(AI_ROOT / "reports" / "biosecurity_readiness_report.json")
    license_decisions = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    biosecurity_decisions = load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json")
    ip_decisions = load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json")
    human_review_launch = load_json(AI_ROOT / "reports" / "human_review_launch_board_report.json")
    human_review_closeout = load_json(AI_ROOT / "reports" / "human_review_closeout_board_report.json")
    benchmark = load_json(AI_ROOT / "reports" / "benchmark_matrix_report.json")
    checks = {
        "data_license_clearance": bool(license_decisions.get("ready_for_training")),
        "tool_license_clearance": bool(license_decisions.get("ready_for_customer_delivery")),
        "self_attested_component_authorization_recorded": bool(
            (license_decisions.get("authorization_status_counts") or {}).get("self_attested")
        ),
        "verified_component_customer_delivery_scope": bool(license_decisions.get("ready_for_customer_delivery")),
        "ip_fto_review": bool(ip_decisions.get("ready_for_customer_delivery")),
        "biosecurity_approval": bool(biosecurity.get("ready_for_ordering") and biosecurity_decisions.get("ready_for_ordering")),
        "model_data_provenance": bool(governance.get("components", {}).get("provenance_ready")),
        "human_delivery_approval": False,
        "allowed_claims_review": False,
        "benchmark_scorecards": bool(benchmark.get("ready_for_model_claim")),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    report = {
        "local_only": True,
        "ready": False,
        "delivery_class": "platform_delivery_workflow_supported_but_not_ready",
        "checks": checks,
        "blockers": blockers,
        "ip_fto_summary": {
            "packet_rows": ip_decisions.get("packet_rows"),
            "decision_rows": ip_decisions.get("decision_rows"),
            "valid_rows": ip_decisions.get("valid_rows"),
            "approved_for_customer_delivery_rows": ip_decisions.get("approved_for_customer_delivery_rows"),
            "ready_for_customer_delivery": ip_decisions.get("ready_for_customer_delivery"),
        },
        "license_scope_summary": {
            "authorization_status_counts": license_decisions.get("authorization_status_counts", {}),
            "capability_authorization_counts": license_decisions.get("capability_authorization_counts", {}),
            "self_attested_commercial_evaluation_rows": license_decisions.get("self_attested_commercial_evaluation_rows"),
            "verified_customer_delivery_rows": license_decisions.get("verified_customer_delivery_rows"),
            "ready_for_customer_delivery": license_decisions.get("ready_for_customer_delivery"),
        },
        "human_review_prepared_summary": {
            "launch_rows": human_review_launch.get("launch_rows"),
            "ready_for_human_review_rows": human_review_launch.get("ready_for_human_review_rows"),
            "total_packet_rows": human_review_launch.get("total_packet_rows"),
            "closeout_rows": human_review_closeout.get("closeout_rows"),
            "awaiting_human_decision_rows": human_review_closeout.get("awaiting_human_decision_rows"),
            "total_formal_decision_rows": human_review_closeout.get("total_formal_decision_rows"),
            "completion_ready_rows": human_review_closeout.get("completion_ready_rows"),
            "policy": "Prepared human-review packets help route review work but do not satisfy delivery gates.",
        },
        "allowed_claims": [
            "internal local readiness pipeline exists",
            "current outputs are design/review artifacts only",
            "platform can run customer-delivery workflow after verified component scope, IP/FTO, biosecurity, benchmark, provenance and human delivery gates pass",
        ],
        "forbidden_claims": [
            "customer-ready sequence package",
            "approved_for_ordering",
            "IP/FTO cleared",
            "biosecurity screened",
            "validated wet-lab performance guarantee",
        ],
        "policy": "Customer-facing sequence packages are not platform-forbidden by default, but require verified component/customer-delivery authorization plus IP/FTO, biosecurity, provenance, benchmark, and human approval gates.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ready": False, "blockers": len(blockers), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
