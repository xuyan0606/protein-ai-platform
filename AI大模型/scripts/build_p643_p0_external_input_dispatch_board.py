#!/usr/bin/env python3
"""Build a P0 external-input dispatch board from P642 packets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P642_MANIFEST = AI_ROOT / "datasets" / "governance" / "p642_p0_external_input_packet_manifest.jsonl"
P642_REPORT = AI_ROOT / "reports" / "p642_p0_external_input_packet_manifest_report.json"
P642_VALIDATION = AI_ROOT / "reports" / "p642_p0_external_input_packet_manifest_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p643_p0_external_input_dispatch_board.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p643_p0_external_input_dispatch_board_report.json"
OUT_MD = AI_ROOT / "reports" / "p0_external_input_dispatch_board.md"

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)

WAVE_BY_WORKSTREAM = {
    "numbering_curation": (1, "numbering_and_structure_chain"),
    "structure_chain_mapping": (1, "numbering_and_structure_chain"),
    "experiment_feedback_source_review": (2, "feedback_source_and_plate_feedback"),
    "plate_feedback_intake": (2, "feedback_source_and_plate_feedback"),
    "external_license_review": (3, "license_biosecurity_ip_fto"),
    "biosecurity_screening": (3, "license_biosecurity_ip_fto"),
    "sequence_ip_fto": (3, "license_biosecurity_ip_fto"),
    "physics_ddg_runtime": (4, "physics_benchmark_training_claim_release"),
    "benchmark_scorecard": (4, "physics_benchmark_training_claim_release"),
    "five_head_training": (4, "physics_benchmark_training_claim_release"),
    "claim_promotion_and_release": (4, "physics_benchmark_training_claim_release"),
}

ORDER_BY_WORKSTREAM = {
    "numbering_curation": 10,
    "structure_chain_mapping": 20,
    "experiment_feedback_source_review": 30,
    "plate_feedback_intake": 40,
    "external_license_review": 50,
    "biosecurity_screening": 60,
    "sequence_ip_fto": 70,
    "physics_ddg_runtime": 80,
    "benchmark_scorecard": 90,
    "five_head_training": 100,
    "claim_promotion_and_release": 110,
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


def dispatch_row(packet: dict[str, Any]) -> dict[str, Any]:
    workstream = str(packet.get("workstream") or "")
    wave, wave_name = WAVE_BY_WORKSTREAM.get(workstream, (99, "unclassified"))
    dispatch_order = ORDER_BY_WORKSTREAM.get(workstream, 999)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "dispatch_id": f"p643::{packet.get('plan_item_id')}",
        "packet_id": packet.get("packet_id"),
        "plan_item_id": packet.get("plan_item_id"),
        "priority": packet.get("priority"),
        "workstream": workstream,
        "packet_category": packet.get("packet_category"),
        "required_input_type": packet.get("required_input_type"),
        "dispatch_wave": wave,
        "dispatch_wave_name": wave_name,
        "dispatch_order": dispatch_order,
        "dispatch_ready": True,
        "dispatch_status": "open_blocked_awaiting_external_input",
        "source_packet_status": packet.get("status"),
        "source_packet_ready_for_dispatch": packet.get("packet_ready_for_dispatch"),
        "operator_next_action": packet.get("operator_next_action"),
        "acceptance_condition": packet.get("acceptance_condition"),
        "source_refs": packet.get("source_refs") or [],
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
            "P643 is a dispatch sequencing board for P642 packets only. "
            "It does not receive real inputs, write reviewed decisions, write formal intake, "
            "write runtime receipts, import training labels, approve claims, approve release, "
            "or authorize production execution."
        ),
    }


def main() -> int:
    p642_report = load_json(P642_REPORT)
    p642_validation = load_json(P642_VALIDATION)
    packets = load_jsonl(P642_MANIFEST)
    rows = sorted((dispatch_row(packet) for packet in packets), key=lambda row: (row["dispatch_wave"], row["dispatch_order"]))
    wave_counts: dict[str, int] = {}
    for row in rows:
        key = f"wave_{row['dispatch_wave']}::{row['dispatch_wave_name']}"
        wave_counts[key] = wave_counts.get(key, 0) + 1

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "manifest_id": "P643",
        "source_manifest": "datasets/governance/p642_p0_external_input_packet_manifest.jsonl",
        "source_report": "reports/p642_p0_external_input_packet_manifest_report.json",
        "source_validation_report": "reports/p642_p0_external_input_packet_manifest_validation_report.json",
        "source_packet_rows": p642_report.get("packet_rows"),
        "source_packet_validation_success": p642_validation.get("success"),
        "dispatch_rows": len(rows),
        "open_blocked_dispatch_rows": sum(1 for row in rows if row["dispatch_status"] == "open_blocked_awaiting_external_input"),
        "dispatch_ready_rows": sum(1 for row in rows if row["dispatch_ready"] is True),
        "dispatch_wave_count": len({row["dispatch_wave"] for row in rows}),
        "wave_counts": wave_counts,
        "real_input_received_rows": sum(1 for row in rows if row["real_input_received"] is True),
        "reviewed_decision_written_rows": sum(1 for row in rows if row["reviewed_decision_written"] is True),
        "formal_intake_written_rows": sum(1 for row in rows if row["formal_intake_written"] is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row["runtime_receipt_written"] is True),
        "dispatch_jsonl": "datasets/governance/p643_p0_external_input_dispatch_board.jsonl",
        "dispatch_board_md": "reports/p0_external_input_dispatch_board.md",
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": "P643 sequences P0 input dispatch only; all P0 gates remain fail-closed.",
    }

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P0 External Input Dispatch Board",
        "",
        "Status: open blocked. Dispatch order is routing only, not approval.",
        "",
        "| Wave | Plan item | Workstream | Category | Required input |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['dispatch_wave']} {row['dispatch_wave_name']} | {row['plan_item_id']} | "
            f"{row['workstream']} | {row['packet_category']} | {row['required_input_type']} |"
        )
    lines.extend([
        "",
        "No real input, reviewed decision, formal intake, runtime receipt, training import, model claim, release approval, or production authorization is created by this board.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest_id": "P643",
        "dispatch_rows": len(rows),
        "open_blocked_dispatch_rows": report["open_blocked_dispatch_rows"],
        "dispatch_wave_count": report["dispatch_wave_count"],
        "real_input_received_rows": 0,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
