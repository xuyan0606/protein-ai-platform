#!/usr/bin/env python3
"""Build Stage 25 remaining blocker closure matrix."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = AI_ROOT.parents[1] / "酶数据库"
SOURCE_READINESS = AI_ROOT / "reports" / "stage25_source_drop_extraction_readiness_candidate_validation_20260806.json"
FULLTEXT_INTAKE = ENZYME_DB_ROOT / "fulltext_intake_validation_report_20260806.json"
LOCATOR_QUEUE = ENZYME_DB_ROOT / "fulltext_source_locator_review_queue_validation_report_20260806.json"
FAMILY_PLAN = AI_ROOT / "reports" / "stage25_family_apply_transaction_plan_validation_20260806.json"
HARD_GATE_DRAFTS = AI_ROOT / "reports" / "stage25_hard_gate_formal_decision_draft_package_validation_20260806.json"
FOLDX_DRAFT = AI_ROOT / "reports" / "stage25_foldx_runtime_receipt_candidate_draft_validation_20260806.json"
CLAIM_RELEASE = AI_ROOT / "reports" / "stage25_claim_release_consistency_validation_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_remaining_blocker_closure_matrix_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def main() -> int:
    source = load_json(SOURCE_READINESS)
    fulltext = load_json(FULLTEXT_INTAKE)
    locator_queue = load_json(LOCATOR_QUEUE)
    family = load_json(FAMILY_PLAN)
    hard_gate = load_json(HARD_GATE_DRAFTS)
    foldx = load_json(FOLDX_DRAFT)
    claim = load_json(CLAIM_RELEASE)
    blockers = [
        {
            "blocker_id": "stage25_new_paper_fulltext_source_table",
            "status": "blocked",
            "current_receipt": str(SOURCE_READINESS),
            "observed": {
                "fulltext_intake_status": fulltext.get("status"),
                "fulltext_intake_failures": fulltext.get("failure_count"),
                "source_locator_queue_status": locator_queue.get("status"),
                "source_locator_review_ready_count": locator_queue.get("review_ready_count"),
                "candidate_rows": source.get("candidate_rows"),
                "ready_for_reviewed_extraction_rows": source.get("ready_for_reviewed_extraction_rows"),
                "ready_for_sqlite_apply_rows": source.get("ready_for_sqlite_apply_rows"),
            },
            "closure_condition": "Place legally obtained files in 酶数据库/incoming/fulltext or canonical AI大模型 source-drop paths, rerun intake/source-drop/reviewed-extraction validators, then require reviewed extraction and source locators before any SQLite apply.",
            "external_input_required": True,
            "machine_path_ready": True,
            "completion_ready": False,
        },
        {
            "blocker_id": "stage25_sqlite_apply",
            "status": "blocked",
            "current_receipt": str(FAMILY_PLAN),
            "observed": {
                "plan_rows": family.get("plan_rows"),
                "ready_to_apply_rows": family.get("ready_to_apply_rows"),
                "write_operation_count": family.get("write_operation_count"),
            },
            "closure_condition": "Source evidence and allowlist approval must close before family transaction plans may emit write operations.",
            "external_input_required": True,
            "machine_path_ready": True,
            "completion_ready": False,
        },
        {
            "blocker_id": "stage25_formal_decisions",
            "status": "blocked",
            "current_receipt": str(HARD_GATE_DRAFTS),
            "observed": {
                "strict_draft_rows": hard_gate.get("strict_draft_rows"),
                "substrate_draft_rows": hard_gate.get("substrate_draft_rows"),
                "formal_decision_rows_written": hard_gate.get("formal_decision_rows_written"),
                "bridge_intake_rows_written": hard_gate.get("bridge_intake_rows_written"),
            },
            "closure_condition": "Human reviewer must fill formal decision rows with reviewer/time/basis/acceptance receipts; drafts alone do not close this blocker.",
            "external_input_required": True,
            "machine_path_ready": True,
            "completion_ready": False,
        },
        {
            "blocker_id": "stage25_foldx_runtime_receipt",
            "status": "blocked",
            "current_receipt": str(FOLDX_DRAFT),
            "observed": {
                "receipt_decision": foldx.get("receipt_decision"),
                "ready_for_runtime_receipt_rows": foldx.get("ready_for_runtime_receipt_rows"),
                "formal_runtime_receipt_written": foldx.get("formal_runtime_receipt_written"),
            },
            "closure_condition": "Provide licensed FoldX executable, license review, config/probe review and smoke artifacts before writing a formal runtime receipt.",
            "external_input_required": True,
            "machine_path_ready": True,
            "completion_ready": False,
        },
        {
            "blocker_id": "stage25_model_release_claim",
            "status": "blocked",
            "current_receipt": str(CLAIM_RELEASE),
            "observed": {
                "safe_for_model_claim": claim.get("safe_for_model_claim"),
                "release_ready": claim.get("release_ready"),
                "customer_delivery_ready": claim.get("customer_delivery_ready"),
                "benchmark_completion_ready_rows": claim.get("benchmark_completion_ready_rows"),
            },
            "closure_condition": "Benchmark/formal decision/runtime/release governance gates must close before model or release claims may open.",
            "external_input_required": True,
            "machine_path_ready": True,
            "completion_ready": False,
        },
    ]
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_remaining_blocker_closure_matrix",
        "stage": 25,
        "matrix_valid": True,
        "blocker_rows": len(blockers),
        "completion_ready_rows": 0,
        "machine_path_ready_rows": sum(1 for row in blockers if row["machine_path_ready"]),
        "external_input_required_rows": sum(1 for row in blockers if row["external_input_required"]),
        "blockers": blockers,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "blocker_rows": report["blocker_rows"], "completion_ready_rows": report["completion_ready_rows"], "machine_path_ready_rows": report["machine_path_ready_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
