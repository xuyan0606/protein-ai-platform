#!/usr/bin/env python3
"""Validate top-tier model execution board semantics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "top_tier_model_execution_board.json"
WORKSTREAMS = AI_ROOT / "datasets" / "governance" / "top_tier_model_workstreams.jsonl"
PACKETS = AI_ROOT / "datasets" / "governance" / "top_tier_model_start_packets.jsonl"
OUT = AI_ROOT / "reports" / "top_tier_model_execution_validation_report.json"


REQUIRED_WORKSTREAMS = {
    "p0_msa_cache_validator",
    "p0_reviewed_structure_graph",
    "p0_proteingym_benchmark_cache",
    "p0_kwb_wet_lab_feedback",
    "p1_boltz2_structure_affinity",
    "p1_thermompnn_stability",
    "p1_plm_structure_representation",
    "p1_catpred_kinetics",
    "p2_ligandmpnn_generation_gate",
    "p2_rfdiffusion2_generation_gate",
    "cross_rosetta_foldx_ddg_backend",
    "cross_license_runtime_weight_gate",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate top-tier execution board")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--workstreams", type=Path, default=WORKSTREAMS)
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    board = load_json(args.board)
    workstreams = load_jsonl(args.workstreams)
    packets = load_jsonl(args.packets)
    failures = []

    ids = {str(row.get("workstream_id")) for row in workstreams}
    missing = sorted(REQUIRED_WORKSTREAMS - ids)
    extra = sorted(ids - REQUIRED_WORKSTREAMS)
    if missing:
        failures.append({"check": "required_workstreams_present", "missing": missing})
    if extra:
        failures.append({"check": "no_unexpected_workstreams", "extra": extra})
    if board.get("total_workstreams") != len(workstreams):
        failures.append({"check": "board_total_matches_workstreams", "expected": len(workstreams), "actual": board.get("total_workstreams")})
    if len(packets) != len(workstreams):
        failures.append({"check": "packet_count_matches_workstreams", "expected": len(workstreams), "actual": len(packets)})
    if any(not row.get("started") for row in workstreams):
        failures.append({"check": "all_workstreams_started"})
    if any(row.get("completion_ready") for row in workstreams):
        failures.append({"check": "no_completion_ready_without_evidence"})
    if board.get("current_readiness", {}).get("current_state_is_top_tier") is not False:
        failures.append({"check": "top_tier_claim_remains_false"})
    if board.get("current_readiness", {}).get("safe_for_model_claim") is not False:
        failures.append({"check": "safe_for_model_claim_remains_false"})
    if board.get("current_readiness", {}).get("release_ready") is not False:
        failures.append({"check": "release_ready_remains_false"})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "validated_workstreams": len(workstreams),
        "validated_packets": len(packets),
        "failed_checks": len(failures),
        "success": not failures,
        "completion_ready_workstreams": sum(1 for row in workstreams if row.get("completion_ready")),
        "started_workstreams": sum(1 for row in workstreams if row.get("started")),
        "blocked_workstreams": sum(1 for row in workstreams if row.get("status") == "started_blocked"),
        "failures": failures,
        "policy": "Validation confirms local starts only; it does not approve external execution or model-quality claims.",
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
