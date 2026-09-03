#!/usr/bin/env python3
"""Build a local operator-dispatch bundle from the P680 readiness audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P680_AUDIT = AI_ROOT / "datasets" / "governance" / "p680_p0_real_input_operator_dispatch_readiness_audit.jsonl"
P680_VALIDATION = AI_ROOT / "reports" / "p680_p0_real_input_operator_dispatch_readiness_audit_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p681_p0_real_input_operator_dispatch_bundle.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p681_p0_real_input_operator_dispatch_bundle_report.json"
OUT_MD = AI_ROOT / "reports" / "p681_p0_real_input_operator_dispatch_bundle.md"

FALSE_FLAGS = {
    "operator_dispatch_sent": False,
    "operator_acknowledged": False,
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


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    source_rows = load_jsonl(P680_AUDIT)
    p680_validation = load_json(P680_VALIDATION)
    lane_rows = sorted(
        (row for row in source_rows if row.get("lane") != "summary"),
        key=lambda row: int(row.get("priority") or 0),
    )
    bundle_rows: list[dict[str, Any]] = []
    for order, row in enumerate(lane_rows, start=1):
        contract = row.get("required_dispatch_contract") or {}
        bundle_rows.append({
            "bundle_id": f"p681::{row.get('lane')}",
            "bundle_order": order,
            "created_at": created_at,
            "local_only": True,
            "lane": row.get("lane"),
            "priority": row.get("priority"),
            "source_audit_id": row.get("audit_id"),
            "source_checklist_id": row.get("checklist_id"),
            "source_freshness_audit_id": row.get("freshness_audit_id"),
            "dispatch_bundle_status": "ready_for_manual_dispatch_blocked",
            "dispatch_ready": row.get("dispatch_ready") is True,
            "operator_action": row.get("first_operator_action"),
            "formal_target_file": row.get("formal_target_file"),
            "source_work_file": contract.get("source_work_file"),
            "template_or_reference_file": contract.get("template_or_reference_file"),
            "required_fields": contract.get("required_fields"),
            "validator_command": row.get("primary_validator_command"),
            "completion_condition": row.get("completion_condition"),
            "blocker": "Manual dispatch bundle is prepared locally; no task has been sent and no response has been received.",
            "policy": "P681 packages P680 instructions for manual use only. It cannot send, receive, approve, import, claim, release, or authorize production.",
            **FALSE_FLAGS,
        })

    summary = {
        "bundle_id": "p681::summary",
        "bundle_order": len(bundle_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_p680_validation_success": p680_validation.get("success"),
        "bundle_rows": len(bundle_rows),
        "manual_dispatch_bundle_ready_rows": sum(1 for row in bundle_rows if row["dispatch_ready"]),
        "dispatch_bundle_status": "ready_for_manual_dispatch_blocked" if bundle_rows and all(row["dispatch_ready"] for row in bundle_rows) else "blocked_source_readiness",
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "blocker": "The bundle is locally prepared, but manual dispatch and operator response remain outstanding.",
        "policy": "P681 is a local operator-dispatch bundle only; it does not create dispatch, response, approval, intake, training, claim, release, or production authorization.",
        **FALSE_FLAGS,
    }
    output_rows = bundle_rows + [summary]
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_audit": "datasets/governance/p680_p0_real_input_operator_dispatch_readiness_audit.jsonl",
        "source_validation_report": "reports/p680_p0_real_input_operator_dispatch_readiness_audit_validation_report.json",
        "bundle_rows": len(bundle_rows),
        "audit_rows": len(output_rows),
        "manual_dispatch_bundle_ready_rows": summary["manual_dispatch_bundle_ready_rows"],
        "dispatch_bundle_status": summary["dispatch_bundle_status"],
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "real_input_received_rows": 0,
        "formal_validator_passed_rows": 0,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "operator_dispatch_sent": False,
        "operator_acknowledged": False,
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
        "bundle_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "policy": "P681 prepares a local manual-dispatch bundle; it does not send or approve anything.",
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# P681 P0 real-input operator dispatch bundle",
        "",
        "Status: locally prepared for manual use; dispatch remains blocked until an operator performs the action.",
        "",
        f"- bundle_rows: `{len(bundle_rows)}`",
        f"- manual_dispatch_bundle_ready_rows: `{summary['manual_dispatch_bundle_ready_rows']}`",
        "- operator_dispatch_sent_rows: `0`",
        "- operator_acknowledged_rows: `0`",
        "- completion_ready_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Formal target | Validator | Status |",
        "|---:|---|---|---|---|",
    ]
    for row in bundle_rows:
        lines.append(
            f"| {row['bundle_order']} | {row['lane']} | `{row['formal_target_file']}` | "
            f"`{row['validator_command']}` | `{row['dispatch_bundle_status']}` |"
        )
    lines.extend([
        "",
        "This bundle is a local execution aid. It does not send work, receive input, write formal decisions, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "bundle_rows": len(bundle_rows),
        "manual_dispatch_bundle_ready_rows": summary["manual_dispatch_bundle_ready_rows"],
        "operator_dispatch_sent_rows": 0,
        "operator_acknowledged_rows": 0,
        "completion_ready_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
