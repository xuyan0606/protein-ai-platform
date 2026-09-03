#!/usr/bin/env python3
"""Prove that forged promotion and downstream gate states fail closed."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "ready_to_verify_promotion_board.json"
OUTPUT = AI_ROOT / "reports" / "ready_to_verify_promotion_safety_regression_report.json"
VALIDATOR = AI_ROOT / "scripts" / "validate_ready_to_verify_promotion_board.py"
PROTECTED_INPUTS = [
    BOARD,
    AI_ROOT / "datasets" / "governance" / "top_tier_model_ready_to_verify_receipts.jsonl",
    AI_ROOT / "datasets" / "governance" / "non_human_ready_to_verify_receipts.jsonl",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mutate_row(board: dict[str, Any], audit_id: str, mutate: Callable[[dict[str, Any]], None]) -> None:
    row = next(item for item in board.get("rows") or [] if item.get("audit_id") == audit_id)
    mutate(row)


def main() -> int:
    baseline = json.loads(BOARD.read_text(encoding="utf-8"))
    before = {str(path): sha256(path) for path in PROTECTED_INPUTS}
    cases: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        (
            "forged_ddg_local_completion",
            lambda board: mutate_row(
                board,
                "non_human:nhc_ddg_physics_backend",
                lambda row: row.update({
                    "local_artifact_completion_checks_met": True,
                    "promotion_status": "verified_local_artifact_only",
                    "remaining_blockers": [],
                }),
            ),
        ),
        (
            "forged_wet_lab_local_completion",
            lambda board: mutate_row(
                board,
                "top_tier:p0_kwb_wet_lab_feedback",
                lambda row: row.update({"local_artifact_completion_checks_met": True}),
            ),
        ),
        (
            "forged_automatic_promotion",
            lambda board: mutate_row(
                board,
                "non_human:nhc_structure_gnn_features",
                lambda row: row.update({"automatic_promotion_allowed": True}),
            ),
        ),
        (
            "forged_model_claim",
            lambda board: mutate_row(
                board,
                "non_human:nhc_data_lake_cache_governance",
                lambda row: row.update({"safe_for_model_claim": True}),
            ),
        ),
        (
            "forged_release_ready",
            lambda board: mutate_row(
                board,
                "top_tier:p0_reviewed_structure_graph",
                lambda row: row.update({"release_ready": True}),
            ),
        ),
    ]

    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="promotion-safety-") as temp_dir:
        temp_root = Path(temp_dir)
        for index, (case_id, mutate) in enumerate(cases, start=1):
            tampered = copy.deepcopy(baseline)
            mutate(tampered)
            board_path = temp_root / f"case-{index}.json"
            report_path = temp_root / f"case-{index}-validation.json"
            board_path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(VALIDATOR), "--board", str(board_path), "--output", str(report_path)],
                cwd=AI_ROOT,
                text=True,
                capture_output=True,
                timeout=120,
            )
            validation = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
            rejected = process.returncode != 0 and int(validation.get("failure_count") or 0) > 0
            results.append({
                "case_id": case_id,
                "tamper_rejected": rejected,
                "validator_returncode": process.returncode,
                "failure_count": int(validation.get("failure_count") or 0),
            })

    after = {str(path): sha256(path) for path in PROTECTED_INPUTS}
    real_inputs_mutated = before != after
    passed = sum(row["tamper_rejected"] for row in results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": passed == len(results) and not real_inputs_mutated,
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "real_inputs_mutated": real_inputs_mutated,
        "results": results,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Regression uses temporary board copies only and must not mutate receipts or the canonical promotion board.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(OUTPUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
