#!/usr/bin/env python3
"""Validate non-human construction board semantics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "non_human_construction_board.json"
WORKSTREAMS = AI_ROOT / "datasets" / "governance" / "non_human_construction_workstreams.jsonl"
PACKETS = AI_ROOT / "datasets" / "governance" / "non_human_construction_start_packets.jsonl"
OUT = AI_ROOT / "reports" / "non_human_construction_validation_report.json"


REQUIRED_WORKSTREAMS = {
    "nhc_ddg_physics_backend",
    "nhc_benchmark_scorecards",
    "nhc_five_head_training",
    "nhc_msa_conservation_production",
    "nhc_structure_gnn_features",
    "nhc_wet_lab_feedback_loop",
    "nhc_data_lake_cache_governance",
    "nhc_production_platform_services",
    "nhc_safety_compliance_gates",
    "nhc_advanced_model_adapters",
    "nhc_active_learning_loop",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate non-human construction board")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--workstreams", type=Path, default=WORKSTREAMS)
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    board = load_json(args.board)
    workstreams = load_jsonl(args.workstreams)
    packets = load_jsonl(args.packets)
    failures: list[dict[str, Any]] = []

    ids = {str(row.get("workstream_id")) for row in workstreams}
    missing = sorted(REQUIRED_WORKSTREAMS - ids)
    extra = sorted(ids - REQUIRED_WORKSTREAMS)
    if missing:
        failures.append({"check": "required_workstreams_present", "missing": missing})
    if extra:
        failures.append({"check": "no_unexpected_workstreams", "extra": extra})
    if board.get("total_workstreams") != len(workstreams):
        failures.append({"check": "board_total_matches_workstreams", "expected": len(workstreams), "actual": board.get("total_workstreams")})
    if board.get("started_workstreams") != len(workstreams):
        failures.append({"check": "all_workstreams_started", "expected": len(workstreams), "actual": board.get("started_workstreams")})
    if len(packets) != len(workstreams):
        failures.append({"check": "packet_count_matches_workstreams", "expected": len(workstreams), "actual": len(packets)})
    if any(not row.get("started") for row in workstreams):
        failures.append({"check": "workstream_started_flags"})
    if any(row.get("completion_ready") for row in workstreams):
        failures.append({"check": "no_completion_ready_without_final_evidence"})
    if any(row.get("automatic_external_execution_allowed") for row in workstreams):
        failures.append({"check": "no_automatic_external_execution"})
    if (board.get("current_readiness") or {}).get("safe_for_model_claim") is not False:
        failures.append({"check": "safe_for_model_claim_remains_false"})
    if board.get("completion_ready_workstreams") != 0:
        failures.append({"check": "no_completion_ready_workstreams"})
    if not all(str(row.get("status") or "").startswith("started_") for row in workstreams):
        failures.append({"check": "status_is_started_variant"})
    for packet in packets:
        if not packet.get("manual_approval_required_for_external_install_or_production"):
            failures.append({"check": "packet_manual_approval_gate", "packet_id": packet.get("packet_id")})
        if not packet.get("safe_local_commands"):
            failures.append({"check": "packet_has_safe_local_commands", "packet_id": packet.get("packet_id")})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "validated_workstreams": len(workstreams),
        "validated_packets": len(packets),
        "ready_to_verify_workstreams": board.get("started_ready_to_verify_workstreams"),
        "blocked_workstreams": board.get("started_blocked_workstreams"),
        "completion_ready_workstreams": board.get("completion_ready_workstreams"),
        "failed_checks": len(failures),
        "success": not failures,
        "failures": failures,
        "policy": "Validation proves construction lanes are started and fail closed; it does not approve external installs, production, delivery, or model-quality claims.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "validated_workstreams": report["validated_workstreams"],
        "failed_checks": report["failed_checks"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
