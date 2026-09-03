#!/usr/bin/env python3
"""Build a fail-closed P0 real-input formal intake dry-run guard from P685."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P685_ROUTING = AI_ROOT / "datasets" / "governance" / "p685_p0_real_input_response_decision_routing.jsonl"
P685_REPORT = AI_ROOT / "reports" / "p685_p0_real_input_response_decision_routing_report.json"
P685_VALIDATION = AI_ROOT / "reports" / "p685_p0_real_input_response_decision_routing_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p686_p0_real_input_formal_intake_dry_run_guard.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p686_p0_real_input_formal_intake_dry_run_guard_report.json"
OUT_MD = AI_ROOT / "reports" / "p686_p0_real_input_formal_intake_dry_run_guard.md"

FALSE_FLAGS = {
    "operator_dispatch_sent": False,
    "operator_acknowledged": False,
    "external_input_acknowledged": False,
    "receive_preflight_executed": False,
    "response_payload_present": False,
    "response_received": False,
    "response_validated": False,
    "real_input_received": False,
    "evidence_payload_present": False,
    "evidence_quarantined": False,
    "evidence_released": False,
    "evidence_promoted_to_decision": False,
    "decision_route_executed": False,
    "routed_to_formal_review": False,
    "formal_intake_dry_run_executed": False,
    "formal_intake_dry_run_passed": False,
    "formal_validator_passed": False,
    "reviewed_decision_written": False,
    "formal_intake_written": False,
    "runtime_receipt_written": False,
    "training_label_written": False,
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


def zero_counts() -> dict[str, int]:
    return {f"{field}_rows": 0 for field in FALSE_FLAGS}


def guard_row(row: dict[str, Any], created_at: str) -> dict[str, Any]:
    return {
        "formal_intake_dry_run_id": f"p686::{row.get('lane')}",
        "formal_intake_dry_run_order": row.get("decision_routing_order"),
        "created_at": created_at,
        "local_only": True,
        "lane": row.get("lane"),
        "priority": row.get("priority"),
        "source_decision_routing_id": row.get("decision_routing_id"),
        "source_evidence_quarantine_id": row.get("source_evidence_quarantine_id"),
        "source_schema_contract_id": row.get("source_schema_contract_id"),
        "source_receive_preflight_id": row.get("source_receive_preflight_id"),
        "source_bundle_id": row.get("source_bundle_id"),
        "source_checklist_id": row.get("source_checklist_id"),
        "formal_intake_dry_run_status": "open_empty_formal_intake_dry_run_guard",
        "formal_intake_dry_run_open": True,
        "formal_intake_dry_run_empty": True,
        "formal_intake_dry_run_blocked": True,
        "formal_target_file": row.get("formal_target_file"),
        "source_work_file": row.get("source_work_file"),
        "template_or_reference_file": row.get("template_or_reference_file"),
        "expected_response_fields": row.get("expected_response_fields") or [],
        "response_envelope_required_fields": row.get("response_envelope_required_fields") or [],
        "validator_command": row.get("validator_command"),
        "operator_action": row.get("operator_action"),
        "completion_condition": row.get("completion_condition"),
        "dry_run_blocker": "No routed evidence has been approved for intake; formal intake dry run must remain unexecuted.",
        "policy": (
            "P686 records empty formal intake dry-run guard rows only. It does not execute intake, write "
            "formal decisions, create runtime receipts or training labels, or approve model claims, release, "
            "delivery, or production."
        ),
        **FALSE_FLAGS,
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    p685_report = load_json(P685_REPORT)
    p685_validation = load_json(P685_VALIDATION)
    source_rows = load_jsonl(P685_ROUTING)
    lane_rows = sorted(
        (row for row in source_rows if row.get("lane") != "summary"),
        key=lambda row: int(row.get("decision_routing_order") or 0),
    )
    guard_rows = [guard_row(row, created_at) for row in lane_rows]
    summary = {
        "formal_intake_dry_run_id": "p686::summary",
        "formal_intake_dry_run_order": len(guard_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_decision_routing_rows": p685_report.get("decision_routing_rows"),
        "source_p685_validation_success": p685_validation.get("success"),
        "formal_intake_dry_run_rows": len(guard_rows),
        "open_formal_intake_dry_run_rows": sum(1 for row in guard_rows if row["formal_intake_dry_run_open"] is True),
        "empty_formal_intake_dry_run_rows": sum(1 for row in guard_rows if row["formal_intake_dry_run_empty"] is True),
        "blocked_formal_intake_dry_run_rows": sum(1 for row in guard_rows if row["formal_intake_dry_run_blocked"] is True),
        "formal_intake_dry_run_status": "open_empty_formal_intake_dry_run_guard" if guard_rows else "blocked_missing_source_routing",
        "blocker": "Formal intake dry run is open, but no routed evidence or real input is present.",
        "policy": "P686 is a local formal intake dry-run guard only; it does not receive or approve P0 input.",
        **zero_counts(),
        **FALSE_FLAGS,
    }
    output_rows = guard_rows + [summary]

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_routing": "datasets/governance/p685_p0_real_input_response_decision_routing.jsonl",
        "source_report": "reports/p685_p0_real_input_response_decision_routing_report.json",
        "source_validation_report": "reports/p685_p0_real_input_response_decision_routing_validation_report.json",
        "source_decision_routing_rows": p685_report.get("decision_routing_rows"),
        "source_p685_validation_success": p685_validation.get("success"),
        "formal_intake_dry_run_rows": len(guard_rows),
        "audit_rows": len(output_rows),
        "open_formal_intake_dry_run_rows": summary["open_formal_intake_dry_run_rows"],
        "empty_formal_intake_dry_run_rows": summary["empty_formal_intake_dry_run_rows"],
        "blocked_formal_intake_dry_run_rows": summary["blocked_formal_intake_dry_run_rows"],
        "formal_intake_dry_run_status": summary["formal_intake_dry_run_status"],
        "preflight_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "policy": "P686 binds empty formal intake dry-run guard rows; all gates remain fail-closed.",
        **zero_counts(),
        **FALSE_FLAGS,
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P686 P0 real-input formal intake dry-run guard",
        "",
        "Status: formal intake dry-run guard is open and empty; no routed evidence has been approved for intake.",
        "",
        f"- formal_intake_dry_run_rows: `{len(guard_rows)}`",
        f"- open_formal_intake_dry_run_rows: `{summary['open_formal_intake_dry_run_rows']}`",
        "- formal_intake_dry_run_executed_rows: `0`",
        "- formal_intake_dry_run_passed_rows: `0`",
        "- formal_intake_written_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Formal target | Status |",
        "|---:|---|---|---|",
    ]
    for row in guard_rows:
        lines.append(
            f"| {row['formal_intake_dry_run_order']} | {row['lane']} | `{row['formal_target_file']}` | "
            f"`{row['formal_intake_dry_run_status']}` |"
        )
    lines.extend([
        "",
        "This guard shell does not execute intake, write formal decisions, import labels, assert claims, release, or authorize production.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "formal_intake_dry_run_rows": len(guard_rows),
        "open_formal_intake_dry_run_rows": summary["open_formal_intake_dry_run_rows"],
        "formal_intake_dry_run_executed_rows": 0,
        "formal_intake_written_rows": 0,
        "response_received_rows": 0,
        "real_input_received_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
