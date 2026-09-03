#!/usr/bin/env python3
"""Build a fail-closed launch board for human review packets."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "datasets" / "governance" / "human_review_launch_board.jsonl"
REPORT = AI_ROOT / "reports" / "human_review_launch_board_report.json"


LANES = [
    {
        "lane_id": "numbering_curation",
        "operator_open_first": "datasets/curation/batches/p0/p0_batch_001.decision_review_template.jsonl",
        "prepared_report": "reports/numbering_decision_review_batch_report.json",
        "validation_report": "reports/numbering_decision_review_batch_validation_report.json",
        "formal_decision_target": "datasets/curation/numbering_curation_decisions.jsonl",
        "formal_validator": "python3 scripts/validate_numbering_curation_decisions.py",
        "human_action": "review source mutation numbering and write reviewed numbering decisions only after evidence checks",
        "priority": 1,
    },
    {
        "lane_id": "plate_feedback_intake",
        "operator_open_first": "datasets/feedback/plate_review_packets/feedback_plate_review_priority_001.jsonl",
        "prepared_report": "reports/experiment_feedback_plate_review_packet_report.json",
        "validation_report": "reports/experiment_feedback_plate_intake_validation_report.json",
        "formal_decision_target": "datasets/feedback/experiment_feedback_plate.local.jsonl",
        "formal_validator": "python3 scripts/validate_experiment_feedback_plate_intake.py",
        "human_action": "extract plate/well/replicate rows, verify QC and numbering, then write schema-valid feedback rows",
        "priority": 2,
    },
    {
        "lane_id": "strict_holdout",
        "operator_open_first": "datasets/curation/kwb_venus15b_strict_holdout_review_packets.jsonl",
        "prepared_report": "reports/hard_gate_review_packet_report.json",
        "validation_report": "reports/hard_gate_review_packet_validation_report.json",
        "formal_decision_target": "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl",
        "formal_validator": "python3 scripts/validate_hard_gate_review_packets.py",
        "human_action": "review 3 strict-holdout packets and record source, numbering, leakage, and wet-lab evidence with acceptance receipts",
        "priority": 3,
    },
    {
        "lane_id": "substrate_identity",
        "operator_open_first": "datasets/curation/substrate_identity_review_packets.jsonl",
        "prepared_report": "reports/hard_gate_review_packet_report.json",
        "validation_report": "reports/hard_gate_review_packet_validation_report.json",
        "formal_decision_target": "datasets/curation/substrate_identity_review_decisions.jsonl",
        "formal_validator": "python3 scripts/validate_hard_gate_review_packets.py",
        "human_action": "review 9 substrate packets and record identity, condition, protocol, scope, representation, and acceptance receipts",
        "priority": 4,
    },
    {
        "lane_id": "external_license_review",
        "operator_open_first": "datasets/governance/external_license_review_missing_checklist.jsonl",
        "prepared_report": "reports/external_license_review_missing_checklist_report.json",
        "validation_report": "reports/external_license_review_missing_checklist_validation_report.json",
        "formal_decision_target": "datasets/governance/external_license_review_decisions.jsonl",
        "formal_validator": "python3 scripts/validate_external_license_review_decisions.py",
        "human_action": "write verified license decisions or needs_more_info rows from legal/source evidence",
        "priority": 5,
    },
    {
        "lane_id": "sequence_ip_fto",
        "operator_open_first": "datasets/curation/sequence_ip_review_packets/sequence_ip_review_internal_labels_001.jsonl",
        "prepared_report": "reports/sequence_ip_review_packet_report.json",
        "validation_report": "reports/sequence_ip_review_packet_validation_report.json",
        "formal_decision_target": "datasets/governance/sequence_ip_fto_decisions.jsonl",
        "formal_validator": "python3 scripts/validate_sequence_ip_fto_decisions.py",
        "human_action": "perform prior-art/FTO review and write explicit legal decision rows",
        "priority": 6,
    },
    {
        "lane_id": "biosecurity_screening",
        "operator_open_first": "datasets/governance/biosecurity_screening_drafts.jsonl",
        "prepared_report": "reports/biosecurity_screening_draft_report.json",
        "validation_report": "reports/biosecurity_screening_draft_validation_report.json",
        "formal_decision_target": "datasets/governance/biosecurity_screening_decisions.jsonl",
        "formal_validator": "python3 scripts/validate_biosecurity_screening_decisions.py",
        "human_action": "submit or record screening evidence and write explicit human biosecurity decisions",
        "priority": 7,
    },
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def rel_exists(rel_path: str) -> bool:
    return (AI_ROOT / rel_path).exists()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build human review launch board")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for lane in LANES:
        validation = load_json(AI_ROOT / lane["validation_report"])
        prepared = load_json(AI_ROOT / lane["prepared_report"])
        packet_rows = int(prepared.get("template_rows") or count_jsonl(AI_ROOT / lane["operator_open_first"]))
        missing_materials = [
            path for path in [
                lane["operator_open_first"],
                lane["prepared_report"],
                lane["validation_report"],
                lane["formal_decision_target"],
            ]
            if not rel_exists(path)
        ]
        rows.append({
            "launch_id": f"human-review-launch::{lane['lane_id']}",
            "lane_id": lane["lane_id"],
            "priority": lane["priority"],
            "status": "ready_for_human_review" if packet_rows > 0 and not missing_materials else "blocked_missing_materials",
            "operator_open_first": lane["operator_open_first"],
            "prepared_report": lane["prepared_report"],
            "validation_report": lane["validation_report"],
            "formal_decision_target": lane["formal_decision_target"],
            "formal_validator": lane["formal_validator"],
            "packet_rows": packet_rows,
            "prepared_report_summary": {
                key: prepared.get(key)
                for key in [
                    "packet_rows",
                    "draft_rows",
                    "checklist_rows",
                    "worklist_rows",
                    "template_rows",
                    "plate_review_packet_rows",
                    "missing_decision_rows",
                    "reviewed_fto_rows",
                    "approved_for_ordering_rows",
                ]
                if key in prepared
            },
            "validation_success": validation.get("success"),
            "missing_materials": missing_materials,
            "human_action": lane["human_action"],
            "completion_condition": "formal decision/intake file is populated by a human reviewer and the formal validator passes",
            "requires_human_input": True,
            "completion_ready": False,
            "policy": "Launch-board row only. It does not write formal decisions, approve license/IP/biosecurity/customer delivery, or unlock release/model claims.",
        })

    rows.sort(key=lambda row: row["priority"])
    write_jsonl(args.output, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "launch_rows": len(rows),
        "ready_for_human_review_rows": sum(1 for row in rows if row["status"] == "ready_for_human_review"),
        "blocked_missing_materials_rows": sum(1 for row in rows if row["status"] == "blocked_missing_materials"),
        "total_packet_rows": sum(row["packet_rows"] for row in rows),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(rows),
        "jsonl": str(args.output),
        "policy": "Human review launch board only. It coordinates review and does not grant approvals or readiness.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "launch_rows": report["launch_rows"],
        "ready_for_human_review_rows": report["ready_for_human_review_rows"],
        "total_packet_rows": report["total_packet_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
