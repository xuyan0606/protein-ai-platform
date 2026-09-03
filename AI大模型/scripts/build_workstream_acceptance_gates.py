#!/usr/bin/env python3
"""Build acceptance gates for every started local workstream."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "workstream_acceptance_gates.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build workstream acceptance gates")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    external_registry = load_json(AI_ROOT / "reports" / "external_data_source_registry_validation_report.json")
    license_decisions = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    structure_apply = load_json(AI_ROOT / "reports" / "structure_chain_mapping_apply_report.json")
    structure_validation = load_json(AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json")
    msa_runtime = load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json")
    msa_cache = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
    plate_validation = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
    customer_delivery = load_json(AI_ROOT / "reports" / "customer_delivery_readiness_report.json")
    active_learning = load_json(AI_ROOT / "reports" / "active_learning_trial_readiness_report.json")
    acceptance_decisions = load_json(AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json")
    accepted_stream_ids = set(acceptance_decisions.get("accepted_stream_ids") or [])

    def gate(stream: str, technical_ready: bool, extra: dict[str, Any], acceptance_requires: list[str]) -> dict[str, Any]:
        human_accepted = stream in accepted_stream_ids
        return {
            "stream": stream,
            "technical_ready": technical_ready,
            "human_accepted": human_accepted,
            "accepted": bool(technical_ready and human_accepted),
            **extra,
            "acceptance_requires": acceptance_requires,
        }

    gates = [
        gate(
            "external_data_sources",
            bool(external_registry.get("ready") and license_decisions.get("ready_for_training")),
            {
                "registry_ready": external_registry.get("ready"),
                "license_ready_for_training": license_decisions.get("ready_for_training"),
                "ready_sources": external_registry.get("ready_sources"),
                "license_decision_rows": license_decisions.get("decision_rows"),
            },
            ["source version", "retrieved_at", "commercial clearance", "redistribution clearance", "attribution policy", "human acceptance decision"],
        ),
        gate(
            "structure_chain_mapping",
            bool(
                structure_validation.get("invalid_rows") == 0
                and (structure_apply.get("usable_for_coordinate_features") or 0) > 0
            ),
            {
                "current_candidates": load_json(AI_ROOT / "reports" / "structure_chain_autoreview_candidate_report.json").get("candidate_rows"),
                "draft_rows": load_json(AI_ROOT / "reports" / "structure_chain_autoreview_decision_draft_report.json").get("draft_rows"),
                "accepted_rows": load_json(AI_ROOT / "reports" / "structure_chain_autoreview_decision_draft_report.json").get("accepted_rows"),
                "valid_decision_rows": structure_validation.get("valid_rows"),
                "usable_for_coordinate_features": structure_apply.get("usable_for_coordinate_features"),
            },
            ["human copied reviewed rows into structure_chain_mapping_decisions.jsonl", "validation passes", "apply produces usable coordinate rows", "human acceptance decision"],
        ),
        gate(
            "msa_conservation",
            bool(msa_runtime.get("runtime_ready") and msa_cache.get("ready")),
            {
                "runtime_ready": msa_runtime.get("runtime_ready"),
                "cache_validation_ready": msa_cache.get("ready"),
            },
            ["MMseqs2 or equivalent runtime", "homolog database or trusted cache", "cache validator ready", "human acceptance decision"],
        ),
        gate(
            "plate_feedback",
            bool((plate_validation.get("training_eligible_rows") or 0) > 0),
            {
                "current_review_rows": load_json(AI_ROOT / "reports" / "experiment_feedback_plate_review_packet_report.json").get("plate_review_packet_rows"),
                "training_eligible_rows": plate_validation.get("training_eligible_rows"),
            },
            ["manual source extraction", "schema-valid plate/well rows", "reviewed QC", "numbering verification", "human acceptance decision"],
        ),
        gate(
            "biosecurity_customer_delivery",
            bool(customer_delivery.get("ready")),
            {
                "customer_delivery_ready": customer_delivery.get("ready"),
            },
            ["biosecurity screening", "IP/FTO review", "data/tool license clearance", "human delivery approval", "human acceptance decision"],
        ),
        gate(
            "active_learning",
            bool(active_learning.get("ready")),
            {
                "active_learning_ready": active_learning.get("ready"),
            },
            ["training-ready heads", "benchmark scorecards", "plate feedback", "human approval", "budget approval", "human acceptance decision"],
        ),
    ]
    report = {
        "local_only": True,
        "acceptance_decision_rows": acceptance_decisions.get("decision_rows", 0),
        "human_accepted_streams": len(accepted_stream_ids),
        "accepted_streams": sum(1 for item in gates if item["accepted"]),
        "total_streams": len(gates),
        "all_accepted": all(item["accepted"] for item in gates),
        "gates": gates,
        "policy": "Started workstreams are not accepted capabilities; every gate must pass before model, delivery, or experiment claims.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accepted_streams": report["accepted_streams"], "total_streams": report["total_streams"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
