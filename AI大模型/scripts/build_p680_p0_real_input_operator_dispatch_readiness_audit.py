#!/usr/bin/env python3
"""Build an operator-dispatch readiness audit for P0 real-input lanes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets" / "governance" / "p677_p0_real_input_completion_checklist.jsonl"
FRESHNESS = AI_ROOT / "datasets" / "governance" / "p679_p0_real_input_status_freshness_audit.jsonl"
FRESHNESS_VALIDATION = AI_ROOT / "reports" / "p679_p0_real_input_status_freshness_audit_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p680_p0_real_input_operator_dispatch_readiness_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p680_p0_real_input_operator_dispatch_readiness_audit_report.json"
OUT_MD = AI_ROOT / "reports" / "p680_p0_real_input_operator_dispatch_readiness_audit.md"

FALSE_FLAGS = {
    "real_input_received": False,
    "formal_validator_passed": False,
    "completion_ready": False,
    "p0_unblocked": False,
    "operator_dispatch_sent": False,
    "operator_acknowledged": False,
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


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    checklist_rows = load_jsonl(CHECKLIST)
    freshness_rows = [row for row in load_jsonl(FRESHNESS) if row.get("lane") != "summary"]
    freshness_validation = load_json(FRESHNESS_VALIDATION)
    checklist_by_lane = {str(row.get("lane")): row for row in checklist_rows}
    freshness_by_lane = {str(row.get("lane")): row for row in freshness_rows}
    audits: list[dict[str, Any]] = []
    dispatch_ready_rows = 0
    for checklist in sorted(checklist_rows, key=lambda row: int(row.get("priority") or 0)):
        lane = str(checklist.get("lane") or "")
        freshness = freshness_by_lane.get(lane, {})
        required_contract = {
            "formal_target_file": checklist.get("formal_target_file"),
            "template_or_reference_file": checklist.get("template_or_reference_file"),
            "source_work_file": checklist.get("source_work_file"),
            "primary_validator_command": checklist.get("primary_validator_command"),
            "first_operator_action": checklist.get("first_operator_action"),
            "completion_condition": checklist.get("completion_condition"),
            "required_fields": checklist.get("required_fields"),
        }
        contract_complete = all(value not in (None, "", []) for value in required_contract.values())
        freshness_current = freshness.get("freshness_audit_status") == "current_source_bound"
        dispatch_ready = contract_complete and freshness_current
        dispatch_ready_rows += int(dispatch_ready)
        audits.append({
            "audit_id": f"p680::{lane}",
            "created_at": created_at,
            "lane": lane,
            "priority": checklist.get("priority"),
            "checklist_id": checklist.get("checklist_id"),
            "freshness_audit_id": freshness.get("audit_id"),
            "freshness_audit_status": freshness.get("freshness_audit_status"),
            "freshness_current": freshness_current,
            "dispatch_contract_complete": contract_complete,
            "dispatch_ready": dispatch_ready,
            "dispatch_status": "blocked_operator_input_required" if dispatch_ready else "blocked_dispatch_contract_incomplete",
            "required_dispatch_contract": required_contract,
            "formal_target_file": checklist.get("formal_target_file"),
            "primary_validator_command": checklist.get("primary_validator_command"),
            "first_operator_action": checklist.get("first_operator_action"),
            "completion_condition": checklist.get("completion_condition"),
            "blocker": "dispatch readiness does not mean dispatch sent, operator acknowledged, real input received, or completion approved",
            "policy": "Operator dispatch readiness audit only. It cannot send work, write inputs, approve decisions, import labels, assert claims, release, or authorize production.",
            **FALSE_FLAGS,
        })

    summary = {
        "audit_id": "p680::summary",
        "created_at": created_at,
        "lane": "summary",
        "source_checklist_rows": len(checklist_rows),
        "source_freshness_rows": len(freshness_rows),
        "source_freshness_validation_success": freshness_validation.get("success"),
        "audit_rows": len(audits) + 1,
        "dispatch_readiness_rows": len(audits),
        "dispatch_ready_rows": dispatch_ready_rows,
        "dispatch_contract_incomplete_rows": len(audits) - dispatch_ready_rows,
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "dispatch_status": "blocked_operator_input_required" if dispatch_ready_rows == len(audits) else "blocked_dispatch_contract_incomplete",
        "blocker": "operator packet contracts are locally ready, but no dispatch or human response has occurred",
        "policy": "P680 is a readiness audit only and cannot create operator dispatch or downstream authorization.",
        **FALSE_FLAGS,
    }
    audits.append(summary)
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in audits), encoding="utf-8")

    report = {
        "created_at": created_at,
        "local_only": True,
        "audit_rows": len(audits),
        "dispatch_readiness_rows": len(checklist_rows),
        "dispatch_ready_rows": dispatch_ready_rows,
        "dispatch_contract_incomplete_rows": len(checklist_rows) - dispatch_ready_rows,
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "source_freshness_validation_success": freshness_validation.get("success"),
        "dispatch_status": "blocked_operator_input_required" if dispatch_ready_rows == len(checklist_rows) else "blocked_dispatch_contract_incomplete",
        "real_input_received": False,
        "formal_validator_passed": False,
        "completion_ready": False,
        "p0_unblocked": False,
        "operator_dispatch_sent": False,
        "operator_acknowledged": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "policy": "P680 confirms local dispatch readiness only; it does not send or approve anything.",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P680 P0 real-input operator dispatch readiness audit",
        "",
        f"- audit_rows: `{len(audits)}`",
        f"- dispatch_readiness_rows: `{len(checklist_rows)}`",
        f"- dispatch_ready_rows: `{dispatch_ready_rows}`",
        "- operator_dispatch_sent_rows: `0`",
        "- operator_acknowledged_rows: `0`",
        "- completion_ready_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Priority | Lane | Dispatch status |",
        "|---:|---|---|",
    ]
    for row in audits[:-1]:
        lines.append(f"| {row['priority']} | {row['lane']} | `{row['dispatch_status']}` |")
    lines.extend([
        "",
        "Dispatch-ready means the local packet contract is complete. It does not mean a task was sent, acknowledged, completed, or approved.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": len(audits),
        "dispatch_readiness_rows": len(checklist_rows),
        "dispatch_ready_rows": dispatch_ready_rows,
        "operator_dispatch_sent_rows": 0,
        "completion_ready_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
