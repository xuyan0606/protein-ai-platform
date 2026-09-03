#!/usr/bin/env python3
"""Build a live status board for P677 P0 real-input completion checklist rows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets" / "governance" / "p677_p0_real_input_completion_checklist.jsonl"
P677_VALIDATION = AI_ROOT / "reports" / "p677_p0_real_input_completion_checklist_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p678_p0_real_input_live_status_board.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p678_p0_real_input_live_status_board_report.json"
OUT_MD = AI_ROOT / "reports" / "p678_p0_real_input_live_status_board.md"

FALSE_FLAGS = {
    "real_input_received": False,
    "formal_validator_passed": False,
    "completion_ready": False,
    "p0_unblocked": False,
    "training_import_allowed": False,
    "safe_for_training_import": False,
    "safe_for_model_claim": False,
    "customer_delivery_ready": False,
    "release_ready": False,
    "production_execution_allowed": False,
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def target_line_count(targets: str) -> int | None:
    if ";" in targets:
        return None
    path = AI_ROOT / targets
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def status_for_lane(lane: str) -> dict[str, Any]:
    if lane == "plate_feedback":
        report = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
        return {
            "validator_report": "reports/experiment_feedback_plate_intake_validation_report.json",
            "observed": {
                "input_rows": report.get("input_rows"),
                "valid_rows": report.get("valid_rows"),
                "training_eligible_rows": report.get("training_eligible_rows"),
                "ready_for_training": report.get("ready_for_training"),
            },
            "status": "blocked_no_formal_plate_intake_rows",
            "blocker": "formal plate intake remains empty; P676 worksheet rows are not formal reviewed intake",
        }
    if lane == "strict_holdout":
        report = load_json(AI_ROOT / "reports" / "kwb_strict_mutation_holdout_benchmark_report.json")
        validation = load_json(AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json")
        return {
            "validator_report": "reports/benchmark_score_cache_validation_report.json",
            "observed": {
                "strict_holdout_dataset_rows": report.get("dataset_rows"),
                "benchmark_valid_rows": validation.get("valid_rows"),
                "benchmark_invalid_rows": validation.get("invalid_rows"),
                "benchmark_error_counts": validation.get("error_counts"),
                "ready_for_model_claim": validation.get("ready_for_model_claim"),
            },
            "status": "blocked_strict_holdout_dataset_empty",
            "blocker": "strict holdout benchmark has zero dataset rows and score-cache validation still reports missing benchmark status",
        }
    if lane == "substrate_identity":
        validation = load_json(AI_ROOT / "reports" / "substrate_identity_evidence_candidate_validation_report.json")
        return {
            "validator_report": "reports/substrate_identity_evidence_candidate_validation_report.json",
            "observed": {
                "candidate_valid_rows": validation.get("valid_rows"),
                "reviewed_rows": validation.get("reviewed_rows"),
                "training_import_written_rows": validation.get("training_import_written_rows"),
                "safe_for_model_claim": validation.get("safe_for_model_claim"),
            },
            "status": "blocked_no_reviewed_substrate_decisions",
            "blocker": "candidate substrate evidence is valid but no reviewed substrate identity decision rows exist",
        }
    if lane == "numbering_curation":
        validation = load_json(AI_ROOT / "reports" / "numbering_curation_validation_report.json")
        decisions = load_jsonl(AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl")
        decision_counts: dict[str, int] = {}
        for row in decisions:
            key = str(row.get("decision") or "missing")
            decision_counts[key] = decision_counts.get(key, 0) + 1
        accepted = decision_counts.get("map_to_canonical", 0)
        return {
            "validator_report": "reports/numbering_curation_validation_report.json",
            "observed": {
                "decision_rows": validation.get("decision_rows"),
                "active_decision_rows": validation.get("active_decision_rows"),
                "valid_rows": validation.get("valid_rows"),
                "invalid_rows": validation.get("invalid_rows"),
                "decision_counts": decision_counts,
                "accepted_canonical_mapping_rows": accepted,
            },
            "status": "blocked_no_accepted_canonical_mapping",
            "blocker": "formal numbering decisions validate, but current active decisions are reject/weak decisions rather than accepted canonical mappings",
        }
    if lane == "governance":
        license_report = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
        ip_report = load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json")
        bio_report = load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json")
        return {
            "validator_report": "reports/external_license_review_decision_validation_report.json;reports/sequence_ip_fto_decision_validation_report.json;reports/biosecurity_screening_decision_validation_report.json",
            "observed": {
                "license_decision_rows": license_report.get("decision_rows"),
                "verified_customer_delivery_rows": license_report.get("verified_customer_delivery_rows"),
                "license_ready_for_customer_delivery": license_report.get("ready_for_customer_delivery"),
                "ip_decision_rows": ip_report.get("decision_rows"),
                "ip_approved_for_customer_delivery_rows": ip_report.get("approved_for_customer_delivery_rows"),
                "ip_ready_for_customer_delivery": ip_report.get("ready_for_customer_delivery"),
                "biosecurity_decision_rows": bio_report.get("decision_rows"),
                "biosecurity_ready_for_ordering": bio_report.get("ready_for_ordering"),
            },
            "status": "blocked_governance_formal_decisions_incomplete",
            "blocker": "delivery/production governance remains blocked by missing verified license/IP/FTO/biosecurity decisions",
        }
    return {
        "validator_report": None,
        "observed": {},
        "status": "blocked_unknown_lane",
        "blocker": "lane is not recognized by P678 live status board",
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    checklist = load_jsonl(CHECKLIST)
    p677_validation = load_json(P677_VALIDATION)
    rows: list[dict[str, Any]] = []
    for item in checklist:
        lane = str(item.get("lane") or "")
        status = status_for_lane(lane)
        target = str(item.get("formal_target_file") or "")
        rows.append({
            "status_id": f"p678::{lane}",
            "created_at": created_at,
            "checklist_id": item.get("checklist_id"),
            "handoff_id": item.get("handoff_id"),
            "lane": lane,
            "priority": item.get("priority"),
            "formal_target_file": target,
            "target_nonempty_lines": target_line_count(target),
            "validator_report": status["validator_report"],
            "live_status": status["status"],
            "blocker": status["blocker"],
            "observed": status["observed"],
            "next_required_action": item.get("first_operator_action"),
            "completion_condition": item.get("completion_condition"),
            "policy": "Live status board only. Formal files and validators decide completion; this board cannot promote downstream state.",
            **FALSE_FLAGS,
        })
    rows.sort(key=lambda row: int(row.get("priority") or 0))
    write_jsonl(OUT_JSONL, rows)

    report = {
        "created_at": created_at,
        "local_only": True,
        "source_checklist_rows": len(checklist),
        "source_checklist_validation_success": p677_validation.get("success"),
        "status_rows": len(rows),
        "blocked_status_rows": len(rows),
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "status_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "p0_unblocked": False,
        "completion_ready": False,
        "policy": "P678 binds the completion checklist to current formal target/validator state and remains fail-closed.",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P678 P0 real-input live status board",
        "",
        f"- status_rows: `{len(rows)}`",
        f"- blocked_status_rows: `{len(rows)}`",
        "- completion_ready_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Priority | Lane | Live status | Blocker |",
        "|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['priority']} | {row['lane']} | `{row['live_status']}` | {row['blocker']} |")
    lines.extend([
        "",
        "This board does not write formal input, reviewed decisions, training labels, model claims, release approval, or production authorization.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status_rows": len(rows),
        "blocked_status_rows": len(rows),
        "completion_ready_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
