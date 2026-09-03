#!/usr/bin/env python3
"""Validate the unified Stage 25 external-input readiness board."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "stage25_external_input_readiness_board_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_external_input_readiness_board_validation_20260806.json"
BUILDER = AI_ROOT / "scripts" / "build_stage25_external_input_readiness_board_20260806.py"
EXPECTED_BLOCKERS = {
    "stage25_new_paper_fulltext_source_table",
    "stage25_foldx_runtime_receipt",
    "stage25_formal_decisions",
    "stage25_model_release_claim",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def load_builder():
    spec = importlib.util.spec_from_file_location("stage25_external_input_builder_for_validation", BUILDER)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load builder: {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not BOARD.exists(), failures, "board_exists", "missing", str(BOARD))
    board = load_json(BOARD) if BOARD.exists() else {}
    rows = board.get("rows") if isinstance(board.get("rows"), list) else []
    category_counts = board.get("category_counts") if isinstance(board.get("category_counts"), dict) else {}
    blocker_ids = {str(row.get("blocker_id")) for row in rows if isinstance(row, dict)}
    builder = load_builder()
    source_validation = builder.load_json(builder.SOURCE_VALIDATION)
    foldx_rows = builder.load_jsonl(builder.FOLDX_CANDIDATES)
    strict_rows = builder.load_jsonl(builder.STRICT_DRAFTS)
    substrate_rows = builder.load_jsonl(builder.SUBSTRATE_DRAFTS)
    workstream_validation = builder.load_json(builder.WORKSTREAM_VALIDATION)
    expected_ids_by_category = {
        "new_paper_source_drop": {str(row.get("source_id")) for row in source_validation.get("source_status") or []},
        "foldx_runtime_provision": {str(row.get("provision_id")) for row in foldx_rows},
        "strict_holdout_formal_decision": {str(row.get("review_key")) for row in strict_rows},
        "substrate_identity_formal_decision": {str(row.get("review_key")) for row in substrate_rows},
        "workstream_acceptance_decision": {str(stream) for stream in workstream_validation.get("expected_streams") or []},
    }
    expected_category_counts = {category: len(ids) for category, ids in expected_ids_by_category.items()}
    expected_input_rows = sum(expected_category_counts.values())

    fail_if(board.get("mode") != "stage25_external_input_readiness_board", failures, "mode", board.get("mode"), "stage25_external_input_readiness_board")
    fail_if(board.get("stage") != 25, failures, "stage", board.get("stage"), 25)
    fail_if(expected_input_rows <= 0, failures, "expected_input_rows_positive", expected_input_rows, ">0")
    fail_if(board.get("input_rows") != expected_input_rows, failures, "input_rows", board.get("input_rows"), expected_input_rows)
    fail_if(len(rows) != expected_input_rows, failures, "rows_len", len(rows), expected_input_rows)
    fail_if(category_counts != expected_category_counts, failures, "category_counts", category_counts, expected_category_counts)
    for category, expected_ids in expected_ids_by_category.items():
        observed_ids = {str(row.get("input_id")) for row in rows if isinstance(row, dict) and row.get("category") == category}
        fail_if(observed_ids != expected_ids, failures, f"category_ids.{category}", sorted(observed_ids), sorted(expected_ids))
    fail_if(not EXPECTED_BLOCKERS.issubset(blocker_ids), failures, "expected_blockers_present", sorted(blocker_ids), sorted(EXPECTED_BLOCKERS))
    fail_if(board.get("completion_ready_rows") != 0, failures, "completion_ready_rows_zero", board.get("completion_ready_rows"), 0)
    fail_if(board.get("missing_or_needs_more_info_rows") != expected_input_rows, failures, "missing_or_needs_more_info_rows", board.get("missing_or_needs_more_info_rows"), expected_input_rows)
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(not row.get("input_id"), failures, f"{prefix}.input_id", row.get("input_id"), "non-empty")
        fail_if(row.get("completion_ready") is not False, failures, f"{prefix}.completion_ready_false", row.get("completion_ready"), False)
        fail_if(not row.get("next_action"), failures, f"{prefix}.next_action", row.get("next_action"), "non-empty")
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(board.get(flag) is not False, failures, f"{flag}_false", board.get(flag), False)
    fail_if(board.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", board.get("formal_decision_rows_written"), 0)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_external_input_readiness_board_validation",
        "stage": 25,
        "board_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "input_rows": len(rows),
        "category_counts": category_counts,
        "source_category_counts": expected_category_counts,
        "source_ids_exact": all(
            {str(row.get("input_id")) for row in rows if isinstance(row, dict) and row.get("category") == category} == expected_ids
            for category, expected_ids in expected_ids_by_category.items()
        ),
        "completion_ready_rows": board.get("completion_ready_rows"),
        "missing_or_needs_more_info_rows": board.get("missing_or_needs_more_info_rows"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "board_valid": validation["board_valid"],
        "failure_count": validation["failure_count"],
        "input_rows": validation["input_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if validation["board_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
