#!/usr/bin/env python3
"""Validate human decision backlog stays aligned with formal gate state."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BACKLOG_REPORT = AI_ROOT / "reports" / "human_decision_backlog_report.json"
BACKLOG_JSONL = AI_ROOT / "datasets" / "governance" / "human_decision_backlog.jsonl"
FORMAL_BOUNDARY = AI_ROOT / "reports" / "review_draft_formal_boundary_validation_report.json"
CLAIM_POLICY = AI_ROOT / "reports" / "claim_readiness_matrix_fail_closed_policy_validation_report.json"
FEEDBACK_SOURCE_PACKETS = AI_ROOT / "reports" / "experiment_feedback_source_review_packet_report.json"
FEEDBACK_SOURCE_DECISIONS = AI_ROOT / "reports" / "experiment_feedback_source_review_decision_validation_report.json"
PLATE_BACKLOG_REPORT = AI_ROOT / "reports" / "experiment_feedback_plate_intake_backlog_report.json"
OUT = AI_ROOT / "reports" / "human_decision_backlog_fail_closed_consistency_validation_report.json"

EXPECTED_BACKLOG = {
    "human_decision_numbering_semantic_conflict_001": {
        "workstream": "numbering_semantic_conflict_resolution",
        "priority": "P0",
        "required_rows": 0,
        "completed_rows": 0,
        "missing_rows": 0,
    },
    "human_decision_numbering_001": {
        "workstream": "numbering_curation",
        "priority": "P0",
        "required_rows": 475,
        "completed_rows": 4,
        "missing_rows": 471,
        "milestone_required_rows": 100,
        "milestone_missing_rows": 96,
    },
    "human_decision_structure_chain_001": {
        "workstream": "structure_chain_mapping",
        "priority": "P0",
        "required_rows": 500,
        "completed_rows": 34,
        "missing_rows": 466,
    },
    "human_decision_domain_occurrence_001": {
        "workstream": "domain_interval_occurrence_selection",
        "priority": "P1",
        "required_rows": 0,
        "completed_rows": 2,
        "missing_rows": 0,
    },
    "human_decision_feedback_source_001": {
        "workstream": "experiment_feedback_source_review",
        "priority": "P0",
        "required_rows": 0,
        "completed_rows": 0,
        "missing_rows": 0,
    },
    "human_decision_plate_feedback_001": {
        "workstream": "plate_feedback_intake",
        "priority": "P0",
        "required_rows": 50,
        "completed_rows": 0,
        "missing_rows": 50,
    },
    "human_decision_license_001": {
        "workstream": "external_license_review",
        "priority": "P0",
        "required_rows": 19,
        "completed_rows": 0,
        "missing_rows": 19,
    },
    "human_decision_biosecurity_001": {
        "workstream": "biosecurity_screening",
        "priority": "P0",
        "required_rows": 3,
        "completed_rows": 0,
        "missing_rows": 3,
    },
    "human_decision_sequence_ip_fto_001": {
        "workstream": "sequence_ip_fto",
        "priority": "P0",
        "required_rows": 3,
        "completed_rows": 0,
        "missing_rows": 3,
    },
    "human_decision_workstream_acceptance_001": {
        "workstream": "workstream_acceptance",
        "priority": "P1",
        "required_rows": 6,
        "completed_rows": 0,
        "missing_rows": 6,
    },
    "human_decision_operator_actions_001": {
        "workstream": "operator_review_actions",
        "priority": "P1",
        "required_rows": 6,
        "completed_rows": 0,
        "missing_rows": 6,
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate human decision backlog fail-closed consistency")
    parser.add_argument("--backlog-report", type=Path, default=BACKLOG_REPORT)
    parser.add_argument("--backlog-jsonl", type=Path, default=BACKLOG_JSONL)
    parser.add_argument("--formal-boundary", type=Path, default=FORMAL_BOUNDARY)
    parser.add_argument("--claim-policy", type=Path, default=CLAIM_POLICY)
    parser.add_argument("--feedback-source-packets", type=Path, default=FEEDBACK_SOURCE_PACKETS)
    parser.add_argument("--feedback-source-decisions", type=Path, default=FEEDBACK_SOURCE_DECISIONS)
    parser.add_argument("--plate-backlog-report", type=Path, default=PLATE_BACKLOG_REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    backlog = load_json(args.backlog_report)
    rows = load_jsonl(args.backlog_jsonl)
    formal_boundary = load_json(args.formal_boundary)
    claim_policy = load_json(args.claim_policy)
    feedback_source_packets = load_json(args.feedback_source_packets)
    feedback_source_decisions = load_json(args.feedback_source_decisions)
    plate_backlog_report = load_json(args.plate_backlog_report)
    failures: list[dict[str, Any]] = []

    expected_backlog = {backlog_id: dict(expected) for backlog_id, expected in EXPECTED_BACKLOG.items()}
    feedback_required_rows = feedback_source_packets.get("packet_rows")
    feedback_completed_rows = feedback_source_decisions.get("approved_for_feedback_extraction_rows")
    if not isinstance(feedback_required_rows, int) or isinstance(feedback_required_rows, bool) or feedback_required_rows <= 0:
        failures.append({"check": "feedback_source_packet_rows_positive", "observed": feedback_required_rows, "expected": ">0 integer"})
        feedback_required_rows = 0
    if not isinstance(feedback_completed_rows, int) or isinstance(feedback_completed_rows, bool) or feedback_completed_rows < 0 or feedback_completed_rows > feedback_required_rows:
        failures.append({"check": "feedback_source_completed_rows_valid", "observed": feedback_completed_rows, "expected": f"integer in [0,{feedback_required_rows}]"})
        feedback_completed_rows = 0
    if feedback_source_decisions.get("candidate_rows") != feedback_required_rows or feedback_source_decisions.get("missing_source_review_rows") != feedback_required_rows - feedback_completed_rows:
        failures.append({
            "check": "feedback_source_packet_decision_parity",
            "observed": {
                "candidate_rows": feedback_source_decisions.get("candidate_rows"),
                "missing_source_review_rows": feedback_source_decisions.get("missing_source_review_rows"),
            },
            "expected": {
                "candidate_rows": feedback_required_rows,
                "missing_source_review_rows": feedback_required_rows - feedback_completed_rows,
            },
        })
    expected_backlog["human_decision_feedback_source_001"].update({
        "required_rows": feedback_required_rows,
        "completed_rows": feedback_completed_rows,
        "missing_rows": feedback_required_rows - feedback_completed_rows,
    })

    plate_required_rows = plate_backlog_report.get("backlog_rows")
    if not isinstance(plate_required_rows, int) or isinstance(plate_required_rows, bool) or plate_required_rows <= 0:
        failures.append({"check": "plate_backlog_rows_positive", "observed": plate_required_rows, "expected": ">0 integer"})
        plate_required_rows = 0
    for field in ("draft_rows", "packet_rows", "blocked_draft_rows"):
        if plate_backlog_report.get(field) != plate_required_rows:
            failures.append({
                "check": f"plate_{field}_parity",
                "observed": plate_backlog_report.get(field),
                "expected": plate_required_rows,
            })
    if plate_backlog_report.get("ready_for_feedback_intake_rows") != 0 or plate_backlog_report.get("local_intake_rows") != 0:
        failures.append({
            "check": "plate_feedback_intake_remains_closed",
            "observed": {
                "ready_for_feedback_intake_rows": plate_backlog_report.get("ready_for_feedback_intake_rows"),
                "local_intake_rows": plate_backlog_report.get("local_intake_rows"),
            },
            "expected": {
                "ready_for_feedback_intake_rows": 0,
                "local_intake_rows": 0,
            },
        })
    expected_backlog["human_decision_plate_feedback_001"].update({
        "required_rows": plate_required_rows,
        "missing_rows": plate_required_rows,
    })

    by_id = {str(row.get("backlog_id")): row for row in rows}
    expected_ids = set(expected_backlog)
    actual_ids = set(by_id)

    if actual_ids != expected_ids:
        failures.append({
            "check": "backlog_ids_exact",
            "missing_ids": sorted(expected_ids - actual_ids),
            "unexpected_ids": sorted(actual_ids - expected_ids),
        })
    if backlog.get("backlog_items") != len(expected_backlog):
        failures.append({"check": "backlog_items_count", "observed": backlog.get("backlog_items"), "expected": len(expected_backlog)})
    if backlog.get("ready_items") != 0:
        failures.append({"check": "ready_items_zero", "observed": backlog.get("ready_items"), "expected": 0})
    if backlog.get("open_items") != len(expected_backlog):
        failures.append({"check": "open_items_all_backlog_items", "observed": backlog.get("open_items"), "expected": len(expected_backlog)})

    for backlog_id, expected in expected_backlog.items():
        row = by_id.get(backlog_id)
        if not row:
            continue
        row_failures: list[dict[str, Any]] = []
        for field, expected_value in expected.items():
            if row.get(field) != expected_value:
                row_failures.append({"field": field, "observed": row.get(field), "expected": expected_value})
        if row.get("ready") is not False:
            row_failures.append({"field": "ready", "observed": row.get("ready"), "expected": False})
        if not row.get("policy"):
            row_failures.append({"field": "policy", "observed": row.get("policy"), "expected": "non-empty fail-closed policy"})
        if not row.get("next_action"):
            row_failures.append({"field": "next_action", "observed": row.get("next_action"), "expected": "non-empty next action"})
        if row_failures:
            failures.append({"check": "backlog_row_expected_state", "backlog_id": backlog_id, "failures": row_failures})

    expected_total_required = sum(item["required_rows"] for item in expected_backlog.values())
    expected_total_completed = sum(item["completed_rows"] for item in expected_backlog.values())
    expected_total_missing = sum(item["missing_rows"] for item in expected_backlog.values())
    for field, expected_value in {
        "total_required_rows": expected_total_required,
        "total_completed_rows": expected_total_completed,
        "total_missing_rows": expected_total_missing,
    }.items():
        if backlog.get(field) != expected_value:
            failures.append({"check": field, "observed": backlog.get(field), "expected": expected_value})

    if formal_boundary.get("success") is not True or formal_boundary.get("draft_rows_counted_as_formal_decisions") != 0:
        failures.append({
            "check": "formal_boundary_supports_backlog",
            "success": formal_boundary.get("success"),
            "draft_rows_counted_as_formal_decisions": formal_boundary.get("draft_rows_counted_as_formal_decisions"),
        })
    if claim_policy.get("success") is not True or claim_policy.get("blocked_claim_ids") != sorted(claim_policy.get("expected_blocked_claim_ids") or []):
        failures.append({
            "check": "claim_policy_supports_backlog",
            "success": claim_policy.get("success"),
            "blocked_claim_ids": claim_policy.get("blocked_claim_ids"),
            "expected_blocked_claim_ids": claim_policy.get("expected_blocked_claim_ids"),
        })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "backlog_items": len(rows),
        "expected_backlog_items": len(expected_backlog),
        "open_items": backlog.get("open_items"),
        "ready_items": backlog.get("ready_items"),
        "total_required_rows": backlog.get("total_required_rows"),
        "total_completed_rows": backlog.get("total_completed_rows"),
        "total_missing_rows": backlog.get("total_missing_rows"),
        "expected_total_missing_rows": expected_total_missing,
        "feedback_source_required_rows": feedback_required_rows,
        "feedback_source_completed_rows": feedback_completed_rows,
        "plate_feedback_required_rows": plate_required_rows,
        "failures": failures,
        "safe_for_training_pipeline": not failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Human backlog must continue to expose unresolved formal decision gaps. It cannot silently drop human gates while claim/release gates remain blocked.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "backlog_items": report["backlog_items"],
        "open_items": report["open_items"],
        "total_missing_rows": report["total_missing_rows"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
