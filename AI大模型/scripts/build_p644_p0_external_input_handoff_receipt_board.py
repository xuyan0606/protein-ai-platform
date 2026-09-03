#!/usr/bin/env python3
"""Build a fail-closed P0 external-input handoff receipt board from P643 dispatch rows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P643_BOARD = AI_ROOT / "datasets" / "governance" / "p643_p0_external_input_dispatch_board.jsonl"
P643_REPORT = AI_ROOT / "reports" / "p643_p0_external_input_dispatch_board_report.json"
P643_VALIDATION = AI_ROOT / "reports" / "p643_p0_external_input_dispatch_board_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p644_p0_external_input_handoff_receipt_board.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p644_p0_external_input_handoff_receipt_board_report.json"
OUT_MD = AI_ROOT / "reports" / "p0_external_input_handoff_receipt_board.md"

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)

CHANNEL_BY_WAVE = {
    1: "curation_review_channel",
    2: "feedback_review_channel",
    3: "governance_review_channel",
    4: "technical_gate_review_channel",
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


def handoff_row(row: dict[str, Any]) -> dict[str, Any]:
    wave = int(row.get("dispatch_wave") or 0)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "handoff_id": f"p644::{row.get('plan_item_id')}",
        "dispatch_id": row.get("dispatch_id"),
        "packet_id": row.get("packet_id"),
        "plan_item_id": row.get("plan_item_id"),
        "priority": row.get("priority"),
        "workstream": row.get("workstream"),
        "packet_category": row.get("packet_category"),
        "required_input_type": row.get("required_input_type"),
        "dispatch_wave": wave,
        "dispatch_wave_name": row.get("dispatch_wave_name"),
        "dispatch_order": row.get("dispatch_order"),
        "handoff_channel": CHANNEL_BY_WAVE.get(wave, "unclassified_review_channel"),
        "handoff_status": "prepared_not_sent_open_blocked",
        "source_dispatch_status": row.get("dispatch_status"),
        "source_dispatch_ready": row.get("dispatch_ready"),
        "operator_next_action": row.get("operator_next_action"),
        "acceptance_condition": row.get("acceptance_condition"),
        "source_refs": row.get("source_refs") or [],
        "handoff_prepared": True,
        "handoff_sent": False,
        "operator_acknowledged": False,
        "external_input_acknowledged": False,
        "real_input_received": False,
        "reviewed_decision_written": False,
        "formal_intake_written": False,
        "runtime_receipt_written": False,
        "model_claim_allowed": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": (
            "P644 records local handoff preparation only. It does not send packets, confirm receipt, "
            "receive external input, write reviewed decisions, write formal intake, write runtime receipts, "
            "import training labels, approve model claims, approve release, or authorize production execution."
        ),
    }


def main() -> int:
    p643_report = load_json(P643_REPORT)
    p643_validation = load_json(P643_VALIDATION)
    dispatch_rows = load_jsonl(P643_BOARD)
    rows = [handoff_row(row) for row in dispatch_rows]
    rows.sort(key=lambda row: (row["dispatch_wave"], row["dispatch_order"]))
    channel_counts: dict[str, int] = {}
    for row in rows:
        channel = str(row["handoff_channel"])
        channel_counts[channel] = channel_counts.get(channel, 0) + 1

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "manifest_id": "P644",
        "source_board": "datasets/governance/p643_p0_external_input_dispatch_board.jsonl",
        "source_report": "reports/p643_p0_external_input_dispatch_board_report.json",
        "source_validation_report": "reports/p643_p0_external_input_dispatch_board_validation_report.json",
        "source_dispatch_rows": p643_report.get("dispatch_rows"),
        "source_dispatch_validation_success": p643_validation.get("success"),
        "handoff_rows": len(rows),
        "prepared_handoff_rows": sum(1 for row in rows if row["handoff_prepared"] is True),
        "open_blocked_handoff_rows": sum(1 for row in rows if row["handoff_status"] == "prepared_not_sent_open_blocked"),
        "handoff_channel_count": len({row["handoff_channel"] for row in rows}),
        "channel_counts": channel_counts,
        "handoff_sent_rows": sum(1 for row in rows if row["handoff_sent"] is True),
        "operator_acknowledged_rows": sum(1 for row in rows if row["operator_acknowledged"] is True),
        "external_input_acknowledged_rows": sum(1 for row in rows if row["external_input_acknowledged"] is True),
        "real_input_received_rows": sum(1 for row in rows if row["real_input_received"] is True),
        "reviewed_decision_written_rows": sum(1 for row in rows if row["reviewed_decision_written"] is True),
        "formal_intake_written_rows": sum(1 for row in rows if row["formal_intake_written"] is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row["runtime_receipt_written"] is True),
        "handoff_jsonl": "datasets/governance/p644_p0_external_input_handoff_receipt_board.jsonl",
        "handoff_board_md": "reports/p0_external_input_handoff_receipt_board.md",
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": "P644 records handoff preparation only; all P0 gates remain fail-closed.",
    }

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P0 External Input Handoff Receipt Board",
        "",
        "Status: prepared locally, not sent, not acknowledged, no external input received.",
        "",
        "| Channel | Plan item | Workstream | Status |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row['handoff_channel']} | {row['plan_item_id']} | {row['workstream']} | {row['handoff_status']} |")
    lines.extend([
        "",
        "This board does not create packet delivery confirmation, human decision, formal intake, runtime receipt, training import, model claim, release approval, or production authorization.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest_id": "P644",
        "handoff_rows": len(rows),
        "prepared_handoff_rows": report["prepared_handoff_rows"],
        "handoff_sent_rows": 0,
        "real_input_received_rows": 0,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
