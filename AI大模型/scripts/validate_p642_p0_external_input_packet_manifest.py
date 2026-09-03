#!/usr/bin/env python3
"""Validate P642 P0 external-input packet manifests remain fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P641_VALIDATION = AI_ROOT / "reports" / "p641_p0_today_closeout_plan_validation_report.json"
MANIFEST = AI_ROOT / "datasets" / "governance" / "p642_p0_external_input_packet_manifest.jsonl"
REPORT = AI_ROOT / "reports" / "p642_p0_external_input_packet_manifest_report.json"
OUT = AI_ROOT / "reports" / "p642_p0_external_input_packet_manifest_validation_report.json"

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


def main() -> int:
    source_validation = load_json(P641_VALIDATION)
    report = load_json(REPORT)
    packets = load_jsonl(MANIFEST)
    failures: list[dict[str, Any]] = []

    def check(condition: bool, name: str, observed: Any, expected: Any) -> None:
        if condition:
            failures.append({"check": name, "observed": observed, "expected": expected})

    check(source_validation.get("success") is not True, "source_p641_validation_success", source_validation.get("success"), True)
    check(len(packets) != source_validation.get("plan_rows"), "packet_rows_match_p641", len(packets), source_validation.get("plan_rows"))
    check(report.get("packet_rows") != len(packets), "report_packet_rows_bound", report.get("packet_rows"), len(packets))
    check(report.get("open_blocked_packet_rows") != len(packets), "all_packets_open_blocked", report.get("open_blocked_packet_rows"), len(packets))
    check(report.get("packet_ready_for_dispatch_rows") != len(packets), "all_packets_dispatch_ready", report.get("packet_ready_for_dispatch_rows"), len(packets))
    check(report.get("real_input_received_rows") != 0, "real_input_received_zero", report.get("real_input_received_rows"), 0)
    check(report.get("reviewed_decision_written_rows") != 0, "reviewed_decision_written_zero", report.get("reviewed_decision_written_rows"), 0)
    check(report.get("formal_intake_written_rows") != 0, "formal_intake_written_zero", report.get("formal_intake_written_rows"), 0)
    check(report.get("runtime_receipt_written_rows") != 0, "runtime_receipt_written_zero", report.get("runtime_receipt_written_rows"), 0)
    check(report.get("p0_unblocked") is not False, "p0_unblocked_false", report.get("p0_unblocked"), False)
    check(report.get("p0_completion_ready") is not False, "p0_completion_ready_false", report.get("p0_completion_ready"), False)
    for field in FALSE_FIELDS:
        check(report.get(field) is not False, f"report_{field}_false", report.get(field), False)
    ids = [packet.get("packet_id") for packet in packets]
    check(len(ids) != len(set(ids)), "packet_ids_unique", ids, "unique")
    for idx, packet in enumerate(packets):
        check(packet.get("status") != "open_blocked_awaiting_external_input", f"packet_status_{idx}", packet.get("status"), "open_blocked_awaiting_external_input")
        check(packet.get("packet_ready_for_dispatch") is not True, f"packet_dispatch_ready_{idx}", packet.get("packet_ready_for_dispatch"), True)
        check(packet.get("real_input_received") is not False, f"packet_real_input_false_{idx}", packet.get("real_input_received"), False)
        check(packet.get("reviewed_decision_written") is not False, f"packet_decision_false_{idx}", packet.get("reviewed_decision_written"), False)
        check(packet.get("formal_intake_written") is not False, f"packet_intake_false_{idx}", packet.get("formal_intake_written"), False)
        check(packet.get("runtime_receipt_written") is not False, f"packet_runtime_false_{idx}", packet.get("runtime_receipt_written"), False)
        for field in FALSE_FIELDS:
            check(packet.get(field) is not False, f"packet_{field}_{idx}", packet.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "manifest_id": "P642",
        "packet_rows": len(packets),
        "open_blocked_packet_rows": sum(1 for packet in packets if packet.get("status") == "open_blocked_awaiting_external_input"),
        "real_input_received_rows": sum(1 for packet in packets if packet.get("real_input_received") is True),
        "reviewed_decision_written_rows": sum(1 for packet in packets if packet.get("reviewed_decision_written") is True),
        "formal_intake_written_rows": sum(1 for packet in packets if packet.get("formal_intake_written") is True),
        "runtime_receipt_written_rows": sum(1 for packet in packets if packet.get("runtime_receipt_written") is True),
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": "P642 validates packet routing only; it does not approve any P0 input.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "packet_rows": result["packet_rows"],
        "open_blocked_packet_rows": result["open_blocked_packet_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
