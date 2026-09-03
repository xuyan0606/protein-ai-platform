#!/usr/bin/env python3
"""Build an action-level remediation queue for next-unlock blockers."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BLOCKERS = AI_ROOT / "datasets" / "governance" / "next_unlock_blockers.jsonl"
OPERATOR_INDEX = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_index.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_remediation_queue.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_remediation_queue.jsonl"


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


REMEDIATION_TYPE_BY_WORKSTREAM = {
    "numbering_curation": "review_and_record_numbering_decisions",
    "structure_chain_mapping": "review_and_record_structure_chain_mappings",
    "domain_interval_occurrence_selection": "review_and_record_domain_occurrence_selection",
    "msa_conservation": "configure_runtime_or_provide_validated_cache_manifest",
    "experiment_feedback_source_review": "transcribe_schema_valid_feedback_rows",
    "plate_feedback_intake": "transcribe_schema_valid_plate_feedback_rows",
    "external_license_review": "record_legal_license_review_decisions",
    "biosecurity_screening": "record_biosecurity_screening_decisions",
    "sequence_ip_fto": "record_ip_fto_review_decisions",
    "workstream_acceptance": "record_human_workstream_acceptance",
    "operator_review_actions": "record_operator_action_completion_evidence",
    "model_claim": "rerun_claim_matrix_after_upstream_remediation",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def by_action(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("action_id")): row for row in rows if row.get("action_id")}


def severity_for(blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return "none"
    return min((str(row.get("severity") or "low") for row in blockers), key=lambda item: SEVERITY_RANK.get(item, 99))


def ready_to_start(index_row: dict[str, Any]) -> bool:
    if not index_row:
        return False
    template_required = bool(index_row.get("template"))
    template_ready = bool(index_row.get("template_exists")) if template_required else True
    return bool(index_row.get("operator_open_first_exists")) and bool(index_row.get("validator_report_exists")) and template_ready


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next-unlock remediation queue")
    parser.add_argument("--blockers", type=Path, default=BLOCKERS)
    parser.add_argument("--operator-index", type=Path, default=OPERATOR_INDEX)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    blockers = load_jsonl(args.blockers)
    index_rows = load_jsonl(args.operator_index)
    index_by_action = by_action(index_rows)
    blockers_by_action: dict[str, list[dict[str, Any]]] = {}
    for blocker in blockers:
        blockers_by_action.setdefault(str(blocker.get("action_id")), []).append(blocker)

    queue = []
    for action_id, index_row in sorted(index_by_action.items()):
        action_blockers = blockers_by_action.get(action_id, [])
        if not action_blockers:
            continue
        categories = sorted({str(row.get("blocker_category")) for row in action_blockers if row.get("blocker_category")})
        evidence_artifacts = []
        for blocker in action_blockers:
            artifact = blocker.get("next_evidence_artifact")
            if artifact and artifact not in evidence_artifacts:
                evidence_artifacts.append(artifact)
        severity = severity_for(action_blockers)
        row = {
            "remediation_id": f"{action_id}-REMEDIATION",
            "action_id": action_id,
            "stage_id": index_row.get("stage_id"),
            "stage_order": index_row.get("stage_order"),
            "workstream": index_row.get("workstream"),
            "priority": index_row.get("priority"),
            "severity": severity,
            "assigned_role": index_row.get("assigned_role"),
            "queue_status": "open",
            "ready_to_start": ready_to_start(index_row),
            "remediation_type": REMEDIATION_TYPE_BY_WORKSTREAM.get(str(index_row.get("workstream")), "resolve_validator_blockers"),
            "blocker_count": len(action_blockers),
            "blocker_ids": [row.get("blocker_id") for row in action_blockers],
            "blocker_categories": categories,
            "failed_checks": [row.get("failed_check") for row in action_blockers],
            "observed_expected": [
                {
                    "failed_check": row.get("failed_check"),
                    "observed": row.get("observed"),
                    "expected": row.get("expected"),
                }
                for row in action_blockers
            ],
            "operator_open_first": index_row.get("operator_open_first"),
            "decision_input": index_row.get("decision_input"),
            "template": index_row.get("template"),
            "validator_report": index_row.get("validator_report"),
            "next_evidence_artifacts": evidence_artifacts,
            "target_rows": index_row.get("target_rows"),
            "verify_command": index_row.get("verify_command") or "python3 scripts/run_safe_training_pipeline.py",
            "completion_condition": index_row.get("completion_condition"),
            "requires_human_input": True,
            "policy": "Remediation queue only. It does not create reviewed decisions, approvals, capability unlocks, downloads, deployments, syncs, or server restarts.",
        }
        queue.append(row)

    queue.sort(key=lambda row: (
        row.get("stage_order") or 999,
        SEVERITY_RANK.get(str(row.get("severity")), 99),
        str(row.get("priority") or ""),
        row["action_id"],
    ))
    for order, row in enumerate(queue, 1):
        row["execution_order"] = order

    write_jsonl(args.jsonl, queue)

    by_workstream = Counter(str(row.get("workstream")) for row in queue)
    by_severity = Counter(str(row.get("severity")) for row in queue)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_blockers": rel(args.blockers),
        "source_operator_index": rel(args.operator_index),
        "jsonl": rel(args.jsonl),
        "queue_rows": len(queue),
        "open_items": sum(1 for row in queue if row["queue_status"] == "open"),
        "ready_to_start_items": sum(1 for row in queue if row["ready_to_start"]),
        "requires_human_input_items": sum(1 for row in queue if row["requires_human_input"]),
        "critical_items": by_severity.get("critical", 0),
        "high_items": by_severity.get("high", 0),
        "medium_items": by_severity.get("medium", 0),
        "workstream_items": dict(sorted(by_workstream.items())),
        "top_queue": [
            {
                "execution_order": row["execution_order"],
                "remediation_id": row["remediation_id"],
                "workstream": row["workstream"],
                "severity": row["severity"],
                "blocker_count": row["blocker_count"],
                "operator_open_first": row["operator_open_first"],
                "next_evidence_artifacts": row["next_evidence_artifacts"],
            }
            for row in queue[:12]
        ],
        "policy": "This remediation queue is a local planning artifact only; it does not write reviewed decisions, grant approvals, unlock claims, download tools, deploy services, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "queue_rows": report["queue_rows"],
        "ready_to_start_items": report["ready_to_start_items"],
        "open_items": report["open_items"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
