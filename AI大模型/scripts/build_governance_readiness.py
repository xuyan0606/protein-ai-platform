#!/usr/bin/env python3
"""Build governance readiness across data, tools, provenance, TEVV, and claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "governance_readiness_report.json"
EXTERNAL_REGISTRY = AI_ROOT / "config" / "external_data_source_registry.local.example.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def exists(rel: str) -> bool:
    return (AI_ROOT / rel).exists()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build governance readiness report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    external_registry = load_json(EXTERNAL_REGISTRY)
    external_registry_validation = load_json(AI_ROOT / "reports" / "external_data_source_registry_validation_report.json")
    foreign_tools = load_json(AI_ROOT / "reports" / "foreign_tool_readiness_report.json")
    license_packets = load_json(AI_ROOT / "reports" / "external_license_review_packet_report.json")
    license_decisions = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    provenance = load_json(AI_ROOT / "reports" / "provenance_graph_report.json")
    benchmark = load_json(AI_ROOT / "reports" / "benchmark_matrix_report.json")
    biosecurity = load_json(AI_ROOT / "reports" / "biosecurity_readiness_report.json")
    ip_decisions = load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json")
    master = load_json(AI_ROOT / "reports" / "master_readiness_board.json")
    license_sources = [
        source.get("source_name")
        for source in external_registry.get("sources", [])
        if source.get("commercial_use_status") not in {"commercial_use_allowed", "public_domain"}
    ]
    blockers = []
    if license_sources:
        blockers.append("external data source commercial/redistribution review is incomplete")
    if not external_registry_validation.get("ready"):
        blockers.append("external data source registry validation is not ready")
    if foreign_tools.get("ready_for_local_evaluation", 0) == 0:
        blockers.append("no external tool is fully ready for local evaluation")
    if not license_decisions.get("ready_for_customer_delivery"):
        blockers.append("verified external data/tool customer-delivery authorization scope is not ready")
    if not provenance.get("ready_for_release_traceability"):
        blockers.append("provenance graph is not ready")
    if not benchmark.get("ready_for_model_claim"):
        blockers.append("head-level benchmark matrix is not ready for model claims")
    if not biosecurity.get("ready_for_ordering"):
        blockers.append("biosecurity/order approval is not ready")
    if not ip_decisions.get("ready_for_customer_delivery"):
        blockers.append("sequence IP/FTO decisions are not ready for customer delivery")
    if master.get("overall_status") != "ready_for_model_claim":
        blockers.append("master readiness board is blocked for model claim")
    report = {
        "local_only": True,
        "ready": False,
        "components": {
            "model_cards_present": bool(list((AI_ROOT / "model_cards").glob("*.md"))),
            "head_model_card_template_present": exists("model_cards/KWB-EnzymeDesigner-heads.template.md"),
            "external_data_source_registry_present": exists("config/external_data_source_registry.local.example.json"),
            "external_data_source_rows": len(external_registry.get("sources", [])),
            "external_data_source_registry_valid_rows": external_registry_validation.get("valid_rows"),
            "external_data_source_registry_ready_sources": external_registry_validation.get("ready_sources"),
            "external_data_source_registry_ready": external_registry_validation.get("ready"),
            "external_data_sources_requiring_review": license_sources,
            "foreign_tool_split_readiness": foreign_tools.get("split_readiness_counts", {}),
            "license_review_packet_rows": license_packets.get("packet_rows"),
            "license_review_decision_rows": license_decisions.get("decision_rows"),
            "license_review_valid_decision_rows": license_decisions.get("valid_rows"),
            "license_review_approved_for_training": license_decisions.get("approved_for_training_rows"),
            "license_review_approved_for_local_evaluation": license_decisions.get("approved_for_local_evaluation_rows"),
            "license_review_approved_for_delivery": license_decisions.get("approved_for_customer_delivery_rows"),
            "license_review_authorization_status_counts": license_decisions.get("authorization_status_counts", {}),
            "license_review_capability_authorization_counts": license_decisions.get("capability_authorization_counts", {}),
            "license_review_verified_customer_delivery_rows": license_decisions.get("verified_customer_delivery_rows"),
            "license_review_ready_for_delivery": license_decisions.get("ready_for_customer_delivery"),
            "provenance_ready": bool(provenance.get("ready_for_release_traceability")),
            "benchmark_ready_for_model_claim": bool(benchmark.get("ready_for_model_claim")),
            "biosecurity_ready_for_ordering": bool(biosecurity.get("ready_for_ordering")),
            "sequence_ip_fto_decision_rows": ip_decisions.get("decision_rows"),
            "sequence_ip_fto_approved_for_delivery": ip_decisions.get("approved_for_customer_delivery_rows"),
            "sequence_ip_fto_ready_for_delivery": ip_decisions.get("ready_for_customer_delivery"),
        },
        "allowed_claims": [
            "local-only engineering readiness artifacts exist",
            "strict supervised training remains gated by reviewed labels",
            "external tools and data sources fail closed until license/runtime/data gates pass",
            "platform policy supports commercial evaluation, training import, customer delivery, service hosting and publication workflows when component/project authorization gates pass",
        ],
        "forbidden_claims": [
            "customer-deliverable model quality",
            "freedom-to-operate or patent clearance",
            "synthesis/order approval",
            "wet-lab activity or stability labels inferred from predicted/reference data",
        ],
        "blockers": blockers,
        "policy": "Governance must pass independently of training smoke tests before P30 release claims. Platform policy is not a default non-commercial ban; third-party component scopes are tracked as self_attested, pending_verification, or verified.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ready": report["ready"], "blockers": len(blockers), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
