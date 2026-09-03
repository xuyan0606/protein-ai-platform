#!/usr/bin/env python3
"""Build Stage 25 blocker activation map."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = AI_ROOT / "reports" / "stage25_blocker_activation_map_20260806.json"
BLOCKER_MATRIX = AI_ROOT / "reports" / "stage25_remaining_blocker_closure_matrix_20260806.json"
RERUN_RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def command_names(receipt: dict[str, Any]) -> list[str]:
    return [str(row.get("name")) for row in receipt.get("commands", []) if isinstance(row, dict)]


def main() -> int:
    matrix = load_json(BLOCKER_MATRIX)
    receipt = load_json(RERUN_RECEIPT)
    commands = command_names(receipt)
    blockers = {row["blocker_id"]: row for row in matrix.get("blockers", [])}

    activations = [
        {
            "blocker_id": "stage25_new_paper_fulltext_source_table",
            "trigger_inputs": [
                "legally_obtained_fulltext_or_si_files_placed",
                "source_locator_review_queue_updated",
                "reviewed_extraction_draft_fields_completed",
            ],
            "rerun_commands": commands[:8],
            "expected_flip_fields": [
                "fulltext_intake_status",
                "source_locator_review_ready_count",
                "ready_for_reviewed_extraction_rows",
            ],
            "must_remain_false_until_next_gate": [
                "external_sqlite_mutated",
                "apply_executed",
                "export_safe_released",
                "safe_for_model_claim",
                "release_ready",
            ],
            "current_completion_ready": blockers["stage25_new_paper_fulltext_source_table"]["completion_ready"],
        },
        {
            "blocker_id": "stage25_sqlite_apply",
            "trigger_inputs": [
                "reviewed_source_evidence_ready_for_sqlite_apply",
                "family_importer_allowlist_approval",
                "sqlite_backup_preflight_ok",
            ],
            "rerun_commands": commands[8:15],
            "expected_flip_fields": [
                "ready_to_apply_rows",
                "write_operation_count",
                "paper_insert_count",
            ],
            "must_remain_false_until_next_gate": [
                "export_safe_released",
                "safe_for_model_claim",
                "release_ready",
            ],
            "current_completion_ready": blockers["stage25_sqlite_apply"]["completion_ready"],
        },
        {
            "blocker_id": "stage25_formal_decisions",
            "trigger_inputs": [
                "strict_holdout_formal_review_rows_filled",
                "substrate_identity_formal_review_rows_filled",
                "reviewer_time_basis_acceptance_receipts_present",
            ],
            "rerun_commands": [
                "build_stage25_hard_gate_formal_decision_draft_package",
                "validate_stage25_hard_gate_formal_decision_draft_package",
                "validate_workstream_acceptance_decisions",
            ],
            "expected_flip_fields": [
                "formal_decision_rows_written",
                "bridge_intake_rows_written",
                "accepted_streams",
            ],
            "must_remain_false_until_next_gate": [
                "safe_for_model_claim",
                "release_ready",
            ],
            "current_completion_ready": blockers["stage25_formal_decisions"]["completion_ready"],
        },
        {
            "blocker_id": "stage25_foldx_runtime_receipt",
            "trigger_inputs": [
                "licensed_foldx_executable_present",
                "license_decision_reviewed",
                "probe_and_smoke_artifacts_hashed",
            ],
            "rerun_commands": [
                "validate_stage25_foldx_provision_manifest",
                "build_stage25_foldx_provision_manifest_candidate",
                "validate_stage25_foldx_provision_manifest_candidate",
                "validate_stage25_foldx_runtime_receipt_candidate_drafts",
                "validate_stage25_foldx_benchmark_bridge_isolation",
            ],
            "expected_flip_fields": [
                "ready_for_runtime_receipt_rows",
                "receipt_decision",
                "formal_runtime_receipt_written",
            ],
            "must_remain_false_until_next_gate": [
                "safe_for_model_claim",
                "release_ready",
            ],
            "current_completion_ready": blockers["stage25_foldx_runtime_receipt"]["completion_ready"],
        },
        {
            "blocker_id": "stage25_model_release_claim",
            "trigger_inputs": [
                "benchmark_completion_ready_rows_positive",
                "formal_decisions_accepted",
                "runtime_receipts_approved",
                "release_acceptance_present",
            ],
            "rerun_commands": [
                "validate_stage25_claim_release_consistency",
                "build_local_release_manifest",
                "validate_local_release_manifest_fail_closed_consistency",
                "build_stage25_overall_fail_closed_index",
            ],
            "expected_flip_fields": [
                "safe_for_model_claim",
                "release_ready",
                "customer_delivery_ready",
            ],
            "must_remain_false_until_next_gate": [],
            "current_completion_ready": blockers["stage25_model_release_claim"]["completion_ready"],
        },
    ]

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_blocker_activation_map",
        "stage": 25,
        "activation_rows": len(activations),
        "all_blockers_mapped": len(activations) == matrix.get("blocker_rows"),
        "mapped_blocker_ids": [row["blocker_id"] for row in activations],
        "activation_completion_ready_rows": sum(1 for row in activations if row["current_completion_ready"]),
        "activations": activations,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "activation_rows": report["activation_rows"], "activation_completion_ready_rows": report["activation_completion_ready_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
