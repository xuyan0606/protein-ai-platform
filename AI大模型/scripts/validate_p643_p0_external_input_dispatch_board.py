#!/usr/bin/env python3
"""Validate P643 P0 external-input dispatch board remains fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
P642_VALIDATION = AI_ROOT / "reports" / "p642_p0_external_input_packet_manifest_validation_report.json"
SOURCE_MANIFEST = AI_ROOT / "datasets" / "governance" / "p642_p0_external_input_packet_manifest.jsonl"
BOARD = AI_ROOT / "datasets" / "governance" / "p643_p0_external_input_dispatch_board.jsonl"
REPORT = AI_ROOT / "reports" / "p643_p0_external_input_dispatch_board_report.json"
OUT = AI_ROOT / "reports" / "p643_p0_external_input_dispatch_board_validation_report.json"

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)

ZERO_ROW_FIELDS = (
    "real_input_received_rows",
    "reviewed_decision_written_rows",
    "formal_intake_written_rows",
    "runtime_receipt_written_rows",
)

EXPECTED_WAVES = {
    1: "numbering_and_structure_chain",
    2: "feedback_source_and_plate_feedback",
    3: "license_biosecurity_ip_fto",
    4: "physics_benchmark_training_claim_release",
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
    p642_validation = load_json(P642_VALIDATION)
    source_packets = load_jsonl(SOURCE_MANIFEST)
    report = load_json(REPORT)
    rows = load_jsonl(BOARD)
    failures: list[dict[str, Any]] = []

    def check(condition: bool, name: str, observed: Any, expected: Any) -> None:
        if condition:
            failures.append({"check": name, "observed": observed, "expected": expected})

    check(p642_validation.get("success") is not True, "source_p642_validation_success", p642_validation.get("success"), True)
    check(len(rows) != len(source_packets), "dispatch_rows_match_p642", len(rows), len(source_packets))
    check(report.get("dispatch_rows") != len(rows), "report_dispatch_rows_bound", report.get("dispatch_rows"), len(rows))
    check(report.get("open_blocked_dispatch_rows") != len(rows), "all_dispatch_rows_open_blocked", report.get("open_blocked_dispatch_rows"), len(rows))
    check(report.get("dispatch_ready_rows") != len(rows), "all_dispatch_rows_ready", report.get("dispatch_ready_rows"), len(rows))
    check(report.get("dispatch_wave_count") != len(EXPECTED_WAVES), "dispatch_wave_count", report.get("dispatch_wave_count"), len(EXPECTED_WAVES))
    for field in ZERO_ROW_FIELDS:
        check(report.get(field) != 0, f"{field}_zero", report.get(field), 0)
    check(report.get("p0_unblocked") is not False, "p0_unblocked_false", report.get("p0_unblocked"), False)
    check(report.get("p0_completion_ready") is not False, "p0_completion_ready_false", report.get("p0_completion_ready"), False)
    for field in FALSE_FIELDS:
        check(report.get(field) is not False, f"report_{field}_false", report.get(field), False)

    dispatch_ids = [row.get("dispatch_id") for row in rows]
    check(len(dispatch_ids) != len(set(dispatch_ids)), "dispatch_ids_unique", dispatch_ids, "unique")
    packet_ids = {packet.get("packet_id") for packet in source_packets}
    check({row.get("packet_id") for row in rows} != packet_ids, "packet_ids_exactly_covered", {row.get("packet_id") for row in rows}, packet_ids)
    waves = {row.get("dispatch_wave"): row.get("dispatch_wave_name") for row in rows}
    check(waves != EXPECTED_WAVES, "expected_waves_present", waves, EXPECTED_WAVES)

    orders = [row.get("dispatch_order") for row in rows]
    check(orders != sorted(orders), "dispatch_order_sorted", orders, "ascending")
    for idx, row in enumerate(rows):
        check(row.get("dispatch_status") != "open_blocked_awaiting_external_input", f"row_status_{idx}", row.get("dispatch_status"), "open_blocked_awaiting_external_input")
        check(row.get("dispatch_ready") is not True, f"row_dispatch_ready_{idx}", row.get("dispatch_ready"), True)
        check(row.get("source_packet_status") != "open_blocked_awaiting_external_input", f"source_packet_status_{idx}", row.get("source_packet_status"), "open_blocked_awaiting_external_input")
        check(row.get("source_packet_ready_for_dispatch") is not True, f"source_packet_ready_{idx}", row.get("source_packet_ready_for_dispatch"), True)
        check(row.get("real_input_received") is not False, f"row_real_input_false_{idx}", row.get("real_input_received"), False)
        check(row.get("reviewed_decision_written") is not False, f"row_decision_false_{idx}", row.get("reviewed_decision_written"), False)
        check(row.get("formal_intake_written") is not False, f"row_intake_false_{idx}", row.get("formal_intake_written"), False)
        check(row.get("runtime_receipt_written") is not False, f"row_runtime_false_{idx}", row.get("runtime_receipt_written"), False)
        for field in FALSE_FIELDS:
            check(row.get(field) is not False, f"row_{field}_{idx}", row.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "manifest_id": "P643",
        "dispatch_rows": len(rows),
        "open_blocked_dispatch_rows": sum(1 for row in rows if row.get("dispatch_status") == "open_blocked_awaiting_external_input"),
        "dispatch_ready_rows": sum(1 for row in rows if row.get("dispatch_ready") is True),
        "dispatch_wave_count": len({row.get("dispatch_wave") for row in rows}),
        "real_input_received_rows": sum(1 for row in rows if row.get("real_input_received") is True),
        "reviewed_decision_written_rows": sum(1 for row in rows if row.get("reviewed_decision_written") is True),
        "formal_intake_written_rows": sum(1 for row in rows if row.get("formal_intake_written") is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row.get("runtime_receipt_written") is True),
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
        "policy": "P643 validates dispatch sequencing only; it does not approve or receive any P0 input.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "dispatch_rows": result["dispatch_rows"],
        "open_blocked_dispatch_rows": result["open_blocked_dispatch_rows"],
        "dispatch_wave_count": result["dispatch_wave_count"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
