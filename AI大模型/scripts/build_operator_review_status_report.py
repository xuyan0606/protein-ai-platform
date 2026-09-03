#!/usr/bin/env python3
"""Build a consolidated status report for human-review decision files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "operator_review_status_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build operator review status report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    queue = load_json(AI_ROOT / "reports" / "operator_review_action_queue_report.json")
    license_validation = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    biosecurity_validation = load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json")
    action_validation = load_json(AI_ROOT / "reports" / "operator_review_action_decision_validation_report.json")
    acceptance_validation = load_json(AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json")
    workstream_gates = load_json(AI_ROOT / "reports" / "workstream_acceptance_gates.json")
    status = {
        "external_license_review": {
            "decision_rows": license_validation.get("decision_rows", 0),
            "valid_rows": license_validation.get("valid_rows", 0),
            "invalid_rows": license_validation.get("invalid_rows", 0),
            "approved_for_training_rows": license_validation.get("approved_for_training_rows", 0),
            "approved_for_local_evaluation_rows": license_validation.get("approved_for_local_evaluation_rows", 0),
            "approved_for_customer_delivery_rows": license_validation.get("approved_for_customer_delivery_rows", 0),
            "ready_for_customer_delivery": bool(license_validation.get("ready_for_customer_delivery")),
        },
        "biosecurity_screening": {
            "decision_rows": biosecurity_validation.get("decision_rows", 0),
            "valid_rows": biosecurity_validation.get("valid_rows", 0),
            "invalid_rows": biosecurity_validation.get("invalid_rows", 0),
            "approved_for_ordering_rows": biosecurity_validation.get("approved_for_ordering_rows", 0),
            "ready_for_ordering": bool(biosecurity_validation.get("ready_for_ordering")),
        },
        "workstream_acceptance": {
            "decision_rows": acceptance_validation.get("decision_rows", 0),
            "valid_rows": acceptance_validation.get("valid_rows", 0),
            "human_accepted_streams": acceptance_validation.get("accepted_streams", 0),
            "accepted_streams": workstream_gates.get("accepted_streams", 0),
            "total_streams": workstream_gates.get("total_streams", 0),
            "all_accepted": bool(workstream_gates.get("all_accepted")),
        },
        "operator_action_completion": {
            "decision_rows": action_validation.get("decision_rows", 0),
            "valid_rows": action_validation.get("valid_rows", 0),
            "invalid_rows": action_validation.get("invalid_rows", 0),
            "completed_rows": action_validation.get("completed_rows", 0),
            "all_actions_completed": bool(action_validation.get("all_actions_completed")),
        },
    }
    blockers = []
    if not status["external_license_review"]["ready_for_customer_delivery"]:
        blockers.append("external data/tool license decisions are incomplete")
    if not status["biosecurity_screening"]["ready_for_ordering"]:
        blockers.append("biosecurity screening decisions are incomplete")
    if not status["workstream_acceptance"]["all_accepted"]:
        blockers.append("workstream acceptance gates are incomplete")
    if not action_validation.get("all_actions_completed"):
        blockers.append("operator review action queue is not completed")
    ready = not blockers

    report = {
        "local_only": True,
        "ready": ready,
        "queue_file": queue.get("queue_file"),
        "action_rows": queue.get("action_rows", 0),
        "completed_action_rows": action_validation.get("completed_rows", 0),
        "status": status,
        "blockers": blockers,
        "policy": "Status report summarizes human-review decisions only; it does not create approvals.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ready": ready, "blockers": len(blockers), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
