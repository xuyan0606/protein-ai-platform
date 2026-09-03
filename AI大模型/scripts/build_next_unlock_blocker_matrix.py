#!/usr/bin/env python3
"""Build a fail-closed blocker matrix for next-unlock actions."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
COMPLETION_STATUS = AI_ROOT / "datasets" / "governance" / "next_unlock_completion_status.jsonl"
OPERATOR_INDEX = AI_ROOT / "datasets" / "governance" / "next_unlock_operator_index.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "next_unlock_blocker_matrix.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "next_unlock_blockers.jsonl"


CATEGORY_BY_CHECK = {
    "numbering valid rows meet action target": "reviewed_numbering_rows",
    "strict supervised rows meet model-claim threshold": "strict_training_rows",
    "reviewed chain mapping rows meet action target": "reviewed_structure_chain_rows",
    "usable coordinate feature mappings meet action target": "coordinate_feature_rows",
    "domain unresolved rows reduced by action target": "domain_occurrence_selection",
    "MSA runtime or trusted cache is ready": "msa_runtime_or_cache",
    "MSA cache manifest has no manifest errors": "msa_cache_manifest",
    "feedback training eligible rows present": "experiment_feedback_intake",
    "plate feedback training eligible rows present": "plate_feedback_intake",
    "license decisions cover all packets": "license_decision_coverage",
    "license decisions ready for customer delivery": "license_delivery_readiness",
    "biosecurity drafts all decided": "biosecurity_decision_coverage",
    "biosecurity ready for ordering": "biosecurity_ordering_readiness",
    "IP/FTO delivery candidates all decided": "ip_fto_decision_coverage",
    "IP/FTO ready for customer delivery": "ip_fto_delivery_readiness",
    "all workstreams human accepted": "workstream_human_acceptance",
    "all operator actions completed": "operator_action_completion",
    "claim matrix has zero blocked claims": "claim_readiness",
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


def evidence_artifact(index_row: dict[str, Any]) -> str | None:
    return (
        index_row.get("decision_input")
        or index_row.get("template")
        or index_row.get("operator_open_first")
        or index_row.get("validator_report")
    )


def blocker_severity(priority: str | None, stage_order: int | None) -> str:
    if priority == "P0":
        return "critical"
    if priority == "P1" or (stage_order is not None and stage_order <= 3):
        return "high"
    return "medium"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next-unlock blocker matrix")
    parser.add_argument("--completion-status", type=Path, default=COMPLETION_STATUS)
    parser.add_argument("--operator-index", type=Path, default=OPERATOR_INDEX)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    status_rows = load_jsonl(args.completion_status)
    index_by_action = by_action(load_jsonl(args.operator_index))

    rows = []
    for status in status_rows:
        action_id = str(status.get("action_id"))
        index_row = index_by_action.get(action_id, {})
        checks = status.get("checks") or []
        failed_checks = [check for check in checks if not check.get("passed")]
        for offset, check in enumerate(failed_checks, 1):
            stage_order = status.get("stage_order") or index_row.get("stage_order")
            priority = status.get("priority") or index_row.get("priority")
            rows.append({
                "blocker_id": f"{action_id}-B{offset:03d}",
                "action_id": action_id,
                "stage_id": status.get("stage_id") or index_row.get("stage_id"),
                "stage_order": stage_order,
                "workstream": status.get("workstream") or index_row.get("workstream"),
                "priority": priority,
                "severity": blocker_severity(priority, stage_order),
                "assigned_role": status.get("assigned_role") or index_row.get("assigned_role"),
                "status": "open",
                "blocker_category": CATEGORY_BY_CHECK.get(str(check.get("name")), "validator_check"),
                "failed_check": check.get("name"),
                "observed": check.get("observed"),
                "expected": check.get("expected"),
                "operator_open_first": index_row.get("operator_open_first"),
                "decision_input": index_row.get("decision_input"),
                "template": index_row.get("template"),
                "validator_report": index_row.get("validator_report") or status.get("validator_report"),
                "next_evidence_artifact": evidence_artifact(index_row),
                "verify_command": index_row.get("verify_command") or "python3 scripts/run_safe_training_pipeline.py",
                "completion_condition": index_row.get("completion_condition"),
                "policy": "Blocker row only. It does not create reviewed decisions, approvals, capability unlocks, downloads, deployments, syncs, or server restarts.",
            })

    rows.sort(key=lambda row: (row.get("stage_order") or 999, row["action_id"], row["blocker_id"]))
    write_jsonl(args.jsonl, rows)

    by_workstream = Counter(str(row.get("workstream")) for row in rows)
    by_stage = Counter(str(row.get("stage_id")) for row in rows)
    by_severity = Counter(str(row.get("severity")) for row in rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_completion_status": rel(args.completion_status),
        "source_operator_index": rel(args.operator_index),
        "jsonl": rel(args.jsonl),
        "action_rows": len(status_rows),
        "blocked_actions": sum(1 for row in status_rows if not row.get("completion_ready")),
        "completion_ready_actions": sum(1 for row in status_rows if row.get("completion_ready")),
        "blocker_rows": len(rows),
        "critical_blockers": by_severity.get("critical", 0),
        "high_blockers": by_severity.get("high", 0),
        "medium_blockers": by_severity.get("medium", 0),
        "workstream_blockers": dict(sorted(by_workstream.items())),
        "stage_blockers": dict(sorted(by_stage.items())),
        "top_blockers": [
            {
                "blocker_id": row["blocker_id"],
                "action_id": row["action_id"],
                "workstream": row["workstream"],
                "failed_check": row["failed_check"],
                "observed": row["observed"],
                "expected": row["expected"],
                "next_evidence_artifact": row["next_evidence_artifact"],
            }
            for row in rows[:18]
        ],
        "policy": "This blocker matrix is a local evidence-gap index only; it does not write reviewed decisions, grant approvals, unlock claims, download tools, deploy services, sync files, or restart servers.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "blocker_rows": report["blocker_rows"],
        "critical_blockers": report["critical_blockers"],
        "high_blockers": report["high_blockers"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
