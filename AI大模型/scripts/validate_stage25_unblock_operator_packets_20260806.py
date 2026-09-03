#!/usr/bin/env python3
"""Validate Stage 25 unblock operator packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKETS = AI_ROOT / "datasets" / "governance" / "stage25_unblock_operator_packets_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_unblock_operator_packet_validation_20260806.json"


EXPECTED_PACKET_IDS = {
    "stage25_unblock_source_39743673_20260806",
    "stage25_unblock_source_42134585_20260806",
    "stage25_unblock_source_42235695_20260806",
    "stage25_unblock_source_42248057_20260806",
    "stage25_unblock_foldx_runtime_20260806",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not PACKETS.exists(), failures, "packets_exist", "missing", str(PACKETS))
    rows = load_jsonl(PACKETS) if PACKETS.exists() else []
    packet_ids = {str(row.get("packet_id")) for row in rows}
    fail_if(packet_ids != EXPECTED_PACKET_IDS, failures, "packet_ids", sorted(packet_ids), sorted(EXPECTED_PACKET_IDS))
    fail_if(len(rows) != 5, failures, "packet_count", len(rows), 5)

    source_packets = [row for row in rows if row.get("packet_type") == "source_acquisition_unblock"]
    foldx_packets = [row for row in rows if row.get("packet_type") == "foldx_runtime_provision_unblock"]
    fail_if(len(source_packets) != 4, failures, "source_packet_count", len(source_packets), 4)
    fail_if(len(foldx_packets) != 1, failures, "foldx_packet_count", len(foldx_packets), 1)

    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(not row.get("required_files"), failures, f"{prefix}.required_files_present", row.get("required_files"), "non-empty")
        fail_if(not row.get("required_extractions"), failures, f"{prefix}.required_extractions_present", row.get("required_extractions"), "non-empty")
        fail_if(not str(row.get("acceptance_validator_needed") or "").strip(), failures, f"{prefix}.acceptance_validator_needed_present", row.get("acceptance_validator_needed"), "non-empty")
        fail_if(not str(row.get("next_operator_action") or "").strip(), failures, f"{prefix}.next_operator_action_present", row.get("next_operator_action"), "non-empty")
        for flag in ("ready_for_sqlite_apply", "ready_for_family_importer", "safe_for_model_claim", "release_ready"):
            if flag in row:
                fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
        for file_row in row.get("required_files") or []:
            fail_if(file_row.get("required") is not True, failures, f"{prefix}.required_files.required_true", file_row, "required=true")

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_unblock_operator_packet_validation",
        "stage": 25,
        "packets_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "packet_rows": len(rows),
        "source_acquisition_packets": len(source_packets),
        "foldx_runtime_packets": len(foldx_packets),
        "ready_for_sqlite_apply": False,
        "ready_for_family_importer": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "release_ready": False,
        "safe_for_model_claim": False,
        "benchmark_ready_for_model_claim": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "packets_valid": report["packets_valid"], "failure_count": report["failure_count"], "packet_rows": report["packet_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["packets_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
