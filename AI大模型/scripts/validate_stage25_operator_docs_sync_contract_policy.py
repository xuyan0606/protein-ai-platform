#!/usr/bin/env python3
"""Independently pin the Stage 25 operator-doc sync contract policy."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE = AI_ROOT / "scripts" / "stage25_operator_docs_sync_contract.py"
OUTPUT = AI_ROOT / "reports" / "stage25_operator_docs_sync_contract_policy_validation_report.json"
EXPECTED_VERSION = "stage25-operator-docs-sync-v4"
EXPECTED_SEMANTIC_PROJECTION_VERSION = "stage25-operator-docs-semantic-projection-v3"
EXPECTED_OUTPUT_PATH_ID = "ai:reports/stage25_operator_docs_dynamic_status_sync_report.json"
EXPECTED_LOCK_PATH_ID = "ai:reports/.stage25_operator_docs_sync.lock"
EXPECTED_TARGET_SPECS = (
    ("next", "ai:reports/next_operator_packet_20260806.md"),
    ("daily", "platform:docs/manuals/2026-08-06-daily-report.md"),
)
EXPECTED_SLOTS = ("latest-release", "core-counts", "data-lake", "human-backlog", "post-source")
EXPECTED_UPSTREAM_INPUT_SPECS = (
    ("sync_script", "ai:scripts/sync_stage25_operator_docs_dynamic_status.py", "implementation"),
    ("sync_contract", "ai:scripts/stage25_operator_docs_sync_contract.py", "implementation"),
    ("runner_contract", "ai:scripts/run_stage25_fail_closed_validation_20260806.py", "code_contract"),
    ("overall_contract", "ai:scripts/build_stage25_overall_fail_closed_index_20260806.py", "code_contract"),
    ("handoff_contract", "ai:scripts/build_stage25_handoff_bundle_manifest_20260806.py", "code_contract"),
    ("local_release", "ai:reports/local_release_manifest.json", "status_report"),
    ("data_lake", "ai:reports/data_lake_manifest.json", "status_report"),
    ("live_integrity", "ai:reports/data_lake_live_content_integrity_validation_report.json", "status_report"),
    ("human_backlog", "ai:reports/human_decision_backlog_fail_closed_consistency_validation_report.json", "status_report"),
    ("safety_guard_contract", "ai:scripts/validate_local_release_safety_guard_links.py", "code_contract"),
    ("approved_apply", "enzyme_db:stage25_approved_apply_report_20260806.json", "external_status_report"),
    ("approved_apply_validation", "enzyme_db:stage25_approved_apply_report_validation_20260806.json", "external_status_report"),
    ("post_source_receipt", "ai:reports/stage25_post_source_drop_rerun_receipt_20260806.json", "status_report"),
    ("post_source_validation", "ai:reports/stage25_post_source_drop_rerun_receipt_validation_20260806.json", "status_report"),
    ("post_source_dry_run", "ai:reports/stage25_post_source_drop_rerun_dry_run_audit_validation_20260806.json", "status_report"),
)
EXPECTED_SEMANTIC_PROJECTION_SPECS = (
    ("local_release", ("artifact_count", "release_ready")),
    ("data_lake", ("source_artifact_rows", "artifact_rows", "unique_path_rows", "deduplicated_input_rows", "duplicate_input_path_rows")),
    ("live_integrity", ("success", "failure_count", "artifact_rows", "strict_verified_rows", "volatile_existence_only_rows", "missing_rows", "unsafe_path_rows", "size_mismatch_rows", "sha256_mismatch_rows", "row_mismatch_rows")),
    ("human_backlog", ("success", "open_items", "total_required_rows", "total_completed_rows", "total_missing_rows", "safe_for_model_claim", "release_ready")),
    ("post_source_receipt", ("command_rows", "command_contract_sha256", "sqlite_write_command_rows", "rerun_ready", "safe_for_model_claim", "release_ready")),
    ("post_source_validation", ("command_rows", "command_contract_valid", "failure_count", "receipt_valid", "sqlite_write_command_rows", "safe_for_model_claim", "release_ready")),
    ("post_source_dry_run", ("audit_valid", "command_rows", "command_contract_sha256", "sqlite_write_command_rows", "commands_executed", "outputs_freshness_verified", "rerun_completion_receipted", "ready_for_source_drop_rerun", "safe_for_model_claim", "release_ready")),
)
EXPECTED_SEMANTIC_PROJECTION_TEST_VECTOR_SHA256 = "e9bd090aba163342dd6587fb229deca7eed2993e09eba1f4ec0415f340630797"
EXPECTED_CONTRACT_SHA256 = "5bd2721fd12b10d35394d789a8eebea6debb5bc46d9a5a02e18e6dca19bd2cc2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("stage25_operator_docs_sync_policy_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load contract module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_marker_specs() -> list[dict[str, str]]:
    return [
        {
            "namespace": namespace,
            "slot": slot,
            "marker": f"<!-- stage25-sync:{slot} -->",
            "target_path_id": path_id,
        }
        for namespace, path_id in EXPECTED_TARGET_SPECS
        for slot in EXPECTED_SLOTS
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 25 operator-doc sync contract policy")
    parser.add_argument("--contract-module", type=Path, default=CONTRACT_MODULE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    module: ModuleType | None = None
    contract: dict[str, Any] = {}
    if not args.contract_module.is_file():
        failures.append({"check": "contract_module_exists", "observed": str(args.contract_module), "expected": "file"})
    else:
        try:
            module = load_module(args.contract_module)
            contract = module.policy_contract()
        except Exception as exc:
            failures.append({"check": "contract_module_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})

    checks = (
        ("contract_version_exact", getattr(module, "CONTRACT_VERSION", None) if module else None, EXPECTED_VERSION),
        ("output_path_exact", getattr(module, "OUTPUT_PATH_ID", None) if module else None, EXPECTED_OUTPUT_PATH_ID),
        ("lock_path_exact", getattr(module, "LOCK_PATH_ID", None) if module else None, EXPECTED_LOCK_PATH_ID),
        ("target_specs_exact", tuple(getattr(module, "TARGET_SPECS", ())) if module else (), EXPECTED_TARGET_SPECS),
        ("slot_specs_exact", tuple(getattr(module, "SLOTS", ())) if module else (), EXPECTED_SLOTS),
        ("marker_specs_exact", module.marker_specs() if module else [], expected_marker_specs()),
        ("upstream_input_specs_exact", tuple(getattr(module, "UPSTREAM_INPUT_SPECS", ())) if module else (), EXPECTED_UPSTREAM_INPUT_SPECS),
        ("semantic_projection_version_exact", getattr(module, "SEMANTIC_PROJECTION_VERSION", None) if module else None, EXPECTED_SEMANTIC_PROJECTION_VERSION),
        ("semantic_projection_specs_exact", tuple(getattr(module, "SEMANTIC_PROJECTION_SPECS", ())) if module else (), EXPECTED_SEMANTIC_PROJECTION_SPECS),
        ("semantic_projection_test_vector_sha256_exact", contract.get("semantic_projection_test_vector_sha256"), EXPECTED_SEMANTIC_PROJECTION_TEST_VECTOR_SHA256),
        ("test_vector_contract_sha256_exact", contract.get("sha256"), EXPECTED_CONTRACT_SHA256),
        ("test_vector_target_rows_exact", contract.get("target_rows"), 2),
        ("test_vector_slot_rows_exact", contract.get("slot_rows"), 5),
        ("test_vector_marker_rows_exact", contract.get("marker_rows"), 10),
        ("test_vector_upstream_rows_exact", contract.get("upstream_input_rows"), 15),
        ("test_vector_semantic_projection_rows_exact", contract.get("semantic_projection_rows"), 7),
    )
    for check, observed, expected in checks:
        if observed != expected:
            failures.append({"check": check, "observed": observed, "expected": expected})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "contract_module_path": str(args.contract_module.resolve()),
        "contract_module_sha256": sha256(args.contract_module) if args.contract_module.is_file() else None,
        "expected_contract_version": EXPECTED_VERSION,
        "expected_output_path_id": EXPECTED_OUTPUT_PATH_ID,
        "expected_lock_path_id": EXPECTED_LOCK_PATH_ID,
        "expected_target_specs": [list(row) for row in EXPECTED_TARGET_SPECS],
        "expected_slots": list(EXPECTED_SLOTS),
        "expected_marker_specs": expected_marker_specs(),
        "expected_upstream_input_specs": [list(row) for row in EXPECTED_UPSTREAM_INPUT_SPECS],
        "expected_semantic_projection_version": EXPECTED_SEMANTIC_PROJECTION_VERSION,
        "expected_semantic_projection_specs": [
            {"role": role, "fields": list(fields)}
            for role, fields in EXPECTED_SEMANTIC_PROJECTION_SPECS
        ],
        "expected_semantic_projection_test_vector_sha256": EXPECTED_SEMANTIC_PROJECTION_TEST_VECTOR_SHA256,
        "expected_contract_sha256": EXPECTED_CONTRACT_SHA256,
        "observed_contract": contract,
        "failure_count": len(failures),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Independent constants pin the sync contract; this report does not authorize document, SQLite, model, release, or production actions.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "failure_count": report["failure_count"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
