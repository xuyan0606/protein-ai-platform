#!/usr/bin/env python3
"""Validate next operator packet validation-order coverage for new human decision chain."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
PACKET = AI_ROOT / "reports" / "next_release_operator_decision_packet_20260805.md"
OUT = AI_ROOT / "reports" / "next_operator_packet_validation_order_validation_report_20260806.json"
EXPECTED_CHAIN = [
    "scripts/build_human_decision_backlog.py",
    "scripts/validate_human_decision_backlog_fail_closed_consistency.py",
    "scripts/build_human_decision_reviewer_input_package_20260806.py",
    "scripts/build_human_decision_pending_row_index_20260806.py",
    "scripts/build_human_decision_review_batches_20260806.py",
    "scripts/validate_human_decision_review_batches_20260806.py",
    "scripts/build_human_decision_priority_queue_20260806.py",
    "scripts/build_human_decision_batch_session_board_20260806.py",
    "scripts/validate_human_decision_batch_session_board_20260806.py",
    "scripts/build_human_decision_release_blocker_matrix_20260806.py",
    "scripts/build_human_decision_next_closeout_package_20260806.py",
    "scripts/build_human_decision_first_assignment_wave_20260806.py",
    "scripts/validate_human_decision_first_assignment_wave_20260806.py",
    "scripts/validate_local_release_human_decision_control_plane_20260806.py",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    text = args.packet.read_text(encoding="utf-8")
    observed = re.findall(r"python3\s+(scripts/[A-Za-z0-9_./-]+\.py)", text)
    failures = []
    for script in EXPECTED_CHAIN:
        if script not in observed:
            failures.append({"check": "script_present", "script": script})
    positions = [observed.index(script) for script in EXPECTED_CHAIN if script in observed]
    if positions != sorted(positions):
        failures.append({"check": "human_decision_chain_order", "observed_positions": positions})
    report = {
        "schema_version": 1,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "expected_chain": EXPECTED_CHAIN,
        "observed_human_decision_chain_positions": positions,
        "release_ready": False,
        "safe_for_model_claim": False,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "failure_count": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
