#!/usr/bin/env python3
"""Build a consolidated local action queue for human/operator review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GATES = AI_ROOT / "reports" / "workstream_acceptance_gates.json"
OUT = AI_ROOT / "datasets" / "governance" / "operator_review_action_queue.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "operator_review_action_queue_report.json"

REQUIRED_REVIEW_INPUTS = {
    "external_data_sources": {
        "evidence": ["datasets/governance/external_license_review_decisions.jsonl"],
        "validation": ["reports/external_license_review_decision_validation_report.json"],
    },
    "structure_chain_mapping": {
        "evidence": ["datasets/curation/structure_chain_mapping_decisions.jsonl"],
        "validation": ["reports/structure_chain_mapping_decision_validation_report.json"],
    },
    "msa_conservation": {
        "evidence": ["datasets/curation/msa_trusted_cache_intake.local.jsonl"],
        "validation": ["reports/msa_conservation_cache_validation_report.json"],
    },
    "plate_feedback": {
        "evidence": ["datasets/feedback/experiment_feedback_plate.local.jsonl"],
        "validation": ["reports/experiment_feedback_plate_intake_validation_report.json"],
    },
    "biosecurity_customer_delivery": {
        "evidence": [
            "datasets/governance/biosecurity_screening_decisions.jsonl",
            "datasets/governance/external_license_review_decisions.jsonl",
            "datasets/governance/sequence_ip_fto_decisions.jsonl",
        ],
        "validation": [
            "reports/biosecurity_screening_decision_validation_report.json",
            "reports/customer_delivery_readiness_report.json",
            "reports/external_license_review_decision_validation_report.json",
            "reports/sequence_ip_fto_decision_validation_report.json",
        ],
    },
    "active_learning": {
        "evidence": ["reports/active_learning_trial_readiness_report.json"],
        "validation": ["reports/active_learning_trial_readiness_validation_report.json"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build operator review action queue")
    parser.add_argument("--gates", type=Path, default=GATES)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    gates = load_json(args.gates).get("gates", [])
    rows: list[dict[str, Any]] = []
    for index, gate in enumerate(gates, start=1):
        stream = str(gate.get("stream") or "")
        requirements = REQUIRED_REVIEW_INPUTS.get(stream, {"evidence": [], "validation": []})
        rows.append({
            "action_id": f"review_action_{index:03d}",
            "stream": stream,
            "priority": "P0" if stream in {"structure_chain_mapping", "plate_feedback", "external_data_sources"} else "P1",
            "status": "not_started",
            "acceptance_requires": gate.get("acceptance_requires", []),
            "suggested_next_artifacts": {
                "external_data_sources": "datasets/governance/external_license_review_packets.jsonl",
                "structure_chain_mapping": "datasets/curation/structure_chain_autoreview_decision_drafts/structure_chain_autoreview_acceptance_001.decision_acceptance.draft.jsonl",
                "msa_conservation": "datasets/curation/msa_runtime_commands.jsonl",
                "plate_feedback": "datasets/feedback/plate_review_packets/feedback_plate_review_priority_001.jsonl",
                "biosecurity_customer_delivery": "datasets/governance/biosecurity_screening_drafts.jsonl",
                "active_learning": "reports/active_learning_trial_readiness_report.json",
            }.get(stream),
            "required_evidence_artifacts": requirements["evidence"],
            "required_validation_reports": requirements["validation"],
            "done_definition": "human-reviewed evidence is written to the proper reviewed input file and the corresponding validator passes",
            "policy": "operator queue only; it does not grant readiness",
        })
    write_jsonl(args.output, rows)
    report = {
        "local_only": True,
        "action_rows": len(rows),
        "completed_rows": 0,
        "queue_file": str(args.output),
        "ready": False,
        "policy": "Actions organize review work; completion requires separate reviewed artifacts and validators.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"action_rows": len(rows), "completed_rows": 0, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
