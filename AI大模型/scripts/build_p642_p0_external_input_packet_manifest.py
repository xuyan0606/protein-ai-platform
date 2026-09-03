#!/usr/bin/env python3
"""Build P0 external-input packet manifests from the P641 closeout plan."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P641_PLAN = AI_ROOT / "datasets" / "governance" / "p641_p0_today_closeout_plan.jsonl"
P641_REPORT = AI_ROOT / "reports" / "p641_p0_today_closeout_plan_report.json"
P641_VALIDATION = AI_ROOT / "reports" / "p641_p0_today_closeout_plan_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p642_p0_external_input_packet_manifest.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p642_p0_external_input_packet_manifest_report.json"
OUT_MD = AI_ROOT / "reports" / "p0_external_input_packet_manifest.md"

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def packet_category(row: dict[str, Any]) -> str:
    input_type = str(row.get("input_type") or "")
    if "license" in input_type:
        return "legal_license"
    if row.get("workstream") in {"biosecurity_screening", "sequence_ip_fto"}:
        return "governance_decision"
    if "runtime" in input_type:
        return "runtime_receipt"
    if "scorecard" in input_type or row.get("workstream") == "benchmark_scorecard":
        return "benchmark_review"
    if "training" in input_type or row.get("workstream") == "five_head_training":
        return "training_readiness"
    if "qc" in input_type or "feedback" in str(row.get("workstream")):
        return "wet_lab_feedback"
    return "human_review"


def packet_from_row(row: dict[str, Any]) -> dict[str, Any]:
    packet_id = f"p642::{row.get('plan_item_id')}"
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet_id": packet_id,
        "plan_item_id": row.get("plan_item_id"),
        "priority": row.get("priority"),
        "workstream": row.get("workstream"),
        "packet_category": packet_category(row),
        "required_input_type": row.get("input_type"),
        "status": "open_blocked_awaiting_external_input",
        "current_state": row.get("current_state"),
        "operator_next_action": row.get("next_action"),
        "acceptance_condition": row.get("completion_condition"),
        "source_refs": row.get("source_refs") or [],
        "source_plan_status": row.get("status"),
        "requires_human_or_external_input": True,
        "packet_ready_for_dispatch": True,
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
            "P642 packets are routing manifests for real external or human input. "
            "They do not create approvals, reviewed decisions, formal intake, runtime receipts, "
            "training labels, model claims, customer delivery, release approval, or production authorization."
        ),
    }


def main() -> int:
    p641_report = load_json(P641_REPORT)
    p641_validation = load_json(P641_VALIDATION)
    p641_rows = load_jsonl(P641_PLAN)
    packets = [packet_from_row(row) for row in p641_rows]
    categories = sorted({packet["packet_category"] for packet in packets})
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "manifest_id": "P642",
        "source_plan": "datasets/governance/p641_p0_today_closeout_plan.jsonl",
        "source_report": "reports/p641_p0_today_closeout_plan_report.json",
        "source_validation_report": "reports/p641_p0_today_closeout_plan_validation_report.json",
        "source_plan_rows": len(p641_rows),
        "source_plan_validation_success": p641_validation.get("success"),
        "source_p0_local_closeout_package_ready": p641_report.get("p0_local_closeout_package_ready"),
        "source_p0_unblocked": p641_report.get("p0_unblocked"),
        "packet_rows": len(packets),
        "open_blocked_packet_rows": sum(1 for packet in packets if packet["status"] == "open_blocked_awaiting_external_input"),
        "packet_ready_for_dispatch_rows": sum(1 for packet in packets if packet["packet_ready_for_dispatch"] is True),
        "real_input_received_rows": sum(1 for packet in packets if packet["real_input_received"] is True),
        "reviewed_decision_written_rows": sum(1 for packet in packets if packet["reviewed_decision_written"] is True),
        "formal_intake_written_rows": sum(1 for packet in packets if packet["formal_intake_written"] is True),
        "runtime_receipt_written_rows": sum(1 for packet in packets if packet["runtime_receipt_written"] is True),
        "categories": categories,
        "manifest_jsonl": "datasets/governance/p642_p0_external_input_packet_manifest.jsonl",
        "packet_manifest_md": "reports/p0_external_input_packet_manifest.md",
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": "P642 routes required P0 inputs only; all gates remain fail-closed until real inputs validate.",
    }
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n" for packet in packets),
        encoding="utf-8",
    )
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P0 External Input Packet Manifest",
        "",
        "Status: open blocked; packets are ready for dispatch, not approval.",
        "",
        "| Packet | Workstream | Category | Required input |",
        "| --- | --- | --- | --- |",
    ]
    for packet in packets:
        lines.append(
            f"| {packet['plan_item_id']} | {packet['workstream']} | {packet['packet_category']} | {packet['required_input_type']} |"
        )
    lines.extend([
        "",
        "All model, training, customer, release and production gates remain false.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest_id": "P642",
        "packet_rows": len(packets),
        "open_blocked_packet_rows": report["open_blocked_packet_rows"],
        "real_input_received_rows": 0,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
