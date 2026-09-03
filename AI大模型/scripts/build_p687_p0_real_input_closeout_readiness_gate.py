#!/usr/bin/env python3
"""Build a fail-closed P0 real-input closeout readiness gate from P686."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P686_GUARD = AI_ROOT / "datasets" / "governance" / "p686_p0_real_input_formal_intake_dry_run_guard.jsonl"
P686_REPORT = AI_ROOT / "reports" / "p686_p0_real_input_formal_intake_dry_run_guard_report.json"
P686_VALIDATION = AI_ROOT / "reports" / "p686_p0_real_input_formal_intake_dry_run_guard_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p687_p0_real_input_closeout_readiness_gate.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p687_p0_real_input_closeout_readiness_gate_report.json"
OUT_MD = AI_ROOT / "reports" / "p687_p0_real_input_closeout_readiness_gate.md"

FALSE_FLAGS = {
    "queue_dequeued": False,
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
    "closeout_ready": False,
    "completion_ready_observed": False,
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


def gate_row(row: dict[str, Any], created_at: str) -> dict[str, Any]:
    return {
        "closeout_gate_id": f"p687::{row.get('lane')}",
        "closeout_gate_order": row.get("formal_intake_dry_run_order"),
        "created_at": created_at,
        "local_only": True,
        "lane": row.get("lane"),
        "priority": row.get("priority"),
        "source_formal_intake_dry_run_id": row.get("formal_intake_dry_run_id"),
        "source_decision_routing_id": row.get("source_decision_routing_id"),
        "source_evidence_quarantine_id": row.get("source_evidence_quarantine_id"),
        "source_schema_contract_id": row.get("source_schema_contract_id"),
        "source_receive_preflight_id": row.get("source_receive_preflight_id"),
        "source_bundle_id": row.get("source_bundle_id"),
        "source_checklist_id": row.get("source_checklist_id"),
        "closeout_gate_status": "open_empty_closeout_readiness_gate",
        "closeout_gate_open": True,
        "closeout_gate_empty": True,
        "closeout_gate_blocked": True,
        "formal_target_file": row.get("formal_target_file"),
        "source_work_file": row.get("source_work_file"),
        "template_or_reference_file": row.get("template_or_reference_file"),
        "expected_response_fields": row.get("expected_response_fields") or [],
        "response_envelope_required_fields": row.get("response_envelope_required_fields") or [],
        "validator_command": row.get("validator_command"),
        "operator_action": row.get("operator_action"),
        "completion_condition": row.get("completion_condition"),
        "closeout_blocker": (
            "Formal intake dry run has not executed or passed; closeout readiness cannot be observed."
        ),
        "policy": (
            "P687 records empty closeout readiness gate rows only. It does not execute formal intake, "
            "observe completion, write runtime receipts or training labels, or approve model claims, "
            "release, delivery, or production."
        ),
        **FALSE_FLAGS,
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    p686_report = load_json(P686_REPORT)
    p686_validation = load_json(P686_VALIDATION)
    source_rows = load_jsonl(P686_GUARD)
    lane_rows = sorted(
        (row for row in source_rows if row.get("lane") != "summary"),
        key=lambda row: int(row.get("formal_intake_dry_run_order") or 0),
    )
    gate_rows = [gate_row(row, created_at) for row in lane_rows]
    summary = {
        "closeout_gate_id": "p687::summary",
        "closeout_gate_order": len(gate_rows) + 1,
        "created_at": created_at,
        "local_only": True,
        "lane": "summary",
        "source_formal_intake_dry_run_rows": p686_report.get("formal_intake_dry_run_rows"),
        "source_p686_validation_success": p686_validation.get("success"),
        "closeout_gate_rows": len(gate_rows),
        "open_closeout_gate_rows": sum(1 for row in gate_rows if row["closeout_gate_open"] is True),
        "empty_closeout_gate_rows": sum(1 for row in gate_rows if row["closeout_gate_empty"] is True),
        "blocked_closeout_gate_rows": sum(1 for row in gate_rows if row["closeout_gate_blocked"] is True),
        "closeout_gate_status": (
            "open_empty_closeout_readiness_gate" if gate_rows else "blocked_missing_source_dry_run"
        ),
        "blocker": "Formal intake dry run remains unexecuted; closeout readiness is not observed.",
        "policy": "P687 is a local closeout readiness gate only; it does not receive or approve P0 input.",
        **zero_counts(),
        **FALSE_FLAGS,
    }
    output_rows = gate_rows + [summary]

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    report = {
        "created_at": created_at,
        "local_only": True,
        "source_jsonl": "datasets/governance/p686_p0_real_input_formal_intake_dry_run_guard.jsonl",
        "source_report": "reports/p686_p0_real_input_formal_intake_dry_run_guard_report.json",
        "source_validation_report": "reports/p686_p0_real_input_formal_intake_dry_run_guard_validation_report.json",
        "source_formal_intake_dry_run_rows": p686_report.get("formal_intake_dry_run_rows"),
        "source_p686_validation_success": p686_validation.get("success"),
        "closeout_gate_rows": len(gate_rows),
        "audit_rows": len(output_rows),
        "open_closeout_gate_rows": summary["open_closeout_gate_rows"],
        "empty_closeout_gate_rows": summary["empty_closeout_gate_rows"],
        "blocked_closeout_gate_rows": summary["blocked_closeout_gate_rows"],
        "closeout_gate_status": summary["closeout_gate_status"],
        "artifact_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "artifact_md": str(OUT_MD.relative_to(AI_ROOT)),
        "policy": "P687 binds empty closeout readiness gate rows; all gates remain fail-closed.",
        **zero_counts(),
        **FALSE_FLAGS,
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P687 P0 real-input closeout readiness gate",
        "",
        "Status: closeout readiness gate is open and empty; formal intake dry run has not executed or passed.",
        "",
        f"- closeout_gate_rows: `{len(gate_rows)}`",
        f"- open_closeout_gate_rows: `{summary['open_closeout_gate_rows']}`",
        "- formal_intake_dry_run_executed_rows: `0`",
        "- formal_intake_dry_run_passed_rows: `0`",
        "- formal_intake_written_rows: `0`",
        "- closeout_ready_rows: `0`",
        "- completion_ready_observed_rows: `0`",
        "- completion_ready_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Order | Lane | Formal target | Status |",
        "|---:|---|---|---|",
    ]
    for row in gate_rows:
        lines.append(
            f"| {row['closeout_gate_order']} | {row['lane']} | `{row['formal_target_file']}` | "
            f"`{row['closeout_gate_status']}` |"
        )
    lines.extend(
        [
            "",
            "This gate shell does not execute intake, observe completion, import labels, assert claims, release, or authorize production.",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "closeout_gate_rows": len(gate_rows),
                "open_closeout_gate_rows": summary["open_closeout_gate_rows"],
                "formal_intake_dry_run_executed_rows": 0,
                "formal_intake_dry_run_passed_rows": 0,
                "formal_intake_written_rows": 0,
                "closeout_ready_rows": 0,
                "completion_ready_observed_rows": 0,
                "completion_ready_rows": 0,
                "response_received_rows": 0,
                "real_input_received_rows": 0,
                "release_ready": False,
                "output": str(OUT_REPORT),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
