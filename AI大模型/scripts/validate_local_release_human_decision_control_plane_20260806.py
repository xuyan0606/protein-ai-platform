#!/usr/bin/env python3
"""Validate human-decision control-plane fields in the local release manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = AI_ROOT / "reports" / "local_release_manifest.json"
DEFAULT_REPORT = AI_ROOT / "reports" / "local_release_human_decision_control_plane_validation_report_20260806.json"
PENDING_INDEX = AI_ROOT / "reports" / "human_decision_pending_row_index_20260806.json"
REVIEW_BATCHES = AI_ROOT / "reports" / "human_decision_review_batches_20260806.json"
PRIORITY_QUEUE = AI_ROOT / "reports" / "human_decision_priority_queue_20260806.json"
SESSION_BOARD = AI_ROOT / "reports" / "human_decision_batch_session_board_20260806.json"
RELEASE_BLOCKERS = AI_ROOT / "reports" / "human_decision_release_blocker_matrix_20260806.json"
CLOSEOUT_PACKAGE = AI_ROOT / "reports" / "human_decision_next_closeout_package_20260806.json"
FIRST_ASSIGNMENT = AI_ROOT / "reports" / "human_decision_first_assignment_wave_20260806.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    manifest = load_json(args.manifest)
    pending_index = load_json(PENDING_INDEX)
    sources = {
        "review_batches": load_json(REVIEW_BATCHES),
        "priority_queue": load_json(PRIORITY_QUEUE),
        "session_board": load_json(SESSION_BOARD),
        "release_blockers": load_json(RELEASE_BLOCKERS),
        "closeout_package": load_json(CLOSEOUT_PACKAGE),
        "first_assignment": load_json(FIRST_ASSIGNMENT),
    }
    summary = manifest.get("readiness_summary") or {}
    failures = []
    pending_index_rows = pending_index.get("indexed_rows")
    if not isinstance(pending_index_rows, int) or isinstance(pending_index_rows, bool) or pending_index_rows <= 0:
        failures.append({"check": "pending_index_rows_positive_integer", "observed": pending_index_rows, "expected": ">0 integer"})
    if summary.get("human_decision_pending_index_rows") != pending_index_rows:
        failures.append({"check": "human_decision_pending_index_rows", "observed": summary.get("human_decision_pending_index_rows"), "expected": pending_index_rows})
    source_summaries = {name: payload.get("summary") or {} for name, payload in sources.items()}
    dynamic_expected = {
        "human_decision_pending_index_rows": pending_index_rows,
        "human_decision_review_batch_count": source_summaries["review_batches"].get("batch_count"),
        "human_decision_priority_queue_p0_batches": source_summaries["priority_queue"].get("p0_batch_count"),
        "human_decision_batch_session_count": source_summaries["session_board"].get("session_count"),
        "human_decision_release_blocker_rows": source_summaries["release_blockers"].get("rows"),
        "human_decision_next_closeout_target_blockers": source_summaries["closeout_package"].get("target_blockers"),
        "human_decision_first_assignment_count": source_summaries["first_assignment"].get("assignment_count"),
        "human_decision_first_assignment_target_rows": source_summaries["first_assignment"].get("target_rows"),
    }
    for key, expected in dynamic_expected.items():
        if not isinstance(expected, int) or isinstance(expected, bool) or expected <= 0:
            failures.append({"check": f"{key}_source_positive_integer", "observed": expected, "expected": ">0 integer"})
        if summary.get(key) != expected:
            failures.append({"check": key, "observed": summary.get(key), "expected": expected})
    for source_name, source_summary in source_summaries.items():
        for field, expected in (("formal_decision_rows_written", 0), ("release_ready", False), ("safe_for_model_claim", False)):
            if source_summary.get(field) != expected:
                failures.append({"check": f"{source_name}.{field}", "observed": source_summary.get(field), "expected": expected})
    for flag in (
        "human_decision_review_batches_validation_success",
        "human_decision_batch_session_validation_success",
        "human_decision_first_assignment_validation_success",
    ):
        if summary.get(flag) is not True:
            failures.append({"check": flag, "observed": summary.get(flag), "expected": True})
    if manifest.get("release_ready") is not False:
        failures.append({"check": "release_ready", "observed": manifest.get("release_ready"), "expected": False})
    if summary.get("customer_delivery_ready") not in (None, False):
        failures.append({"check": "customer_delivery_ready", "observed": summary.get("customer_delivery_ready"), "expected": False})

    report = {
        "schema_version": 1,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "release_ready": False,
        "safe_for_model_claim": False,
        "validated_fields": sorted(dynamic_expected),
        "dynamic_expected": dynamic_expected,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "failure_count": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
