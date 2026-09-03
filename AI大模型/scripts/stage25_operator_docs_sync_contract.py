#!/usr/bin/env python3
"""Canonical contract and provenance helpers for Stage 25 operator-doc sync."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "stage25-operator-docs-sync-v4"
SEMANTIC_PROJECTION_VERSION = "stage25-operator-docs-semantic-projection-v3"
AI_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = AI_ROOT.parent
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")

OUTPUT_PATH_ID = "ai:reports/stage25_operator_docs_dynamic_status_sync_report.json"
LOCK_PATH_ID = "ai:reports/.stage25_operator_docs_sync.lock"
TARGET_SPECS = (
    ("next", "ai:reports/next_operator_packet_20260806.md"),
    ("daily", "platform:docs/manuals/2026-08-06-daily-report.md"),
)
SLOTS = ("latest-release", "core-counts", "data-lake", "human-backlog", "post-source")
UPSTREAM_INPUT_SPECS = (
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
SEMANTIC_PROJECTION_SPECS = (
    ("local_release", ("artifact_count", "release_ready")),
    (
        "data_lake",
        (
            "source_artifact_rows",
            "artifact_rows",
            "unique_path_rows",
            "deduplicated_input_rows",
            "duplicate_input_path_rows",
        ),
    ),
    (
        "live_integrity",
        (
            "success",
            "failure_count",
            "artifact_rows",
            "strict_verified_rows",
            "volatile_existence_only_rows",
            "missing_rows",
            "unsafe_path_rows",
            "size_mismatch_rows",
            "sha256_mismatch_rows",
            "row_mismatch_rows",
        ),
    ),
    (
        "human_backlog",
        (
            "success",
            "open_items",
            "total_required_rows",
            "total_completed_rows",
            "total_missing_rows",
            "safe_for_model_claim",
            "release_ready",
        ),
    ),
    (
        "post_source_receipt",
        ("command_rows", "command_contract_sha256", "sqlite_write_command_rows", "rerun_ready", "safe_for_model_claim", "release_ready"),
    ),
    (
        "post_source_validation",
        ("command_rows", "command_contract_valid", "failure_count", "receipt_valid", "sqlite_write_command_rows", "safe_for_model_claim", "release_ready"),
    ),
    (
        "post_source_dry_run",
        ("audit_valid", "command_rows", "command_contract_sha256", "sqlite_write_command_rows", "commands_executed", "outputs_freshness_verified", "rerun_completion_receipted", "ready_for_source_drop_rerun", "safe_for_model_claim", "release_ready"),
    ),
)


def resolve_path(
    path_id: str,
    *,
    ai_root: Path = AI_ROOT,
    platform_root: Path | None = None,
    enzyme_db_root: Path = ENZYME_DB_ROOT,
) -> Path:
    effective_platform_root = platform_root or ai_root.parent
    prefix, separator, relative = path_id.partition(":")
    if not separator or not relative:
        raise ValueError(f"invalid contract path id: {path_id}")
    roots = {
        "ai": ai_root,
        "platform": effective_platform_root,
        "enzyme_db": enzyme_db_root,
    }
    if prefix not in roots:
        raise ValueError(f"unknown contract path prefix: {prefix}")
    return (roots[prefix] / relative).resolve()


def marker_for(slot: str) -> str:
    return f"<!-- stage25-sync:{slot} -->"


def marker_specs() -> list[dict[str, str]]:
    return [
        {"namespace": namespace, "slot": slot, "marker": marker_for(slot), "target_path_id": path_id}
        for namespace, path_id in TARGET_SPECS
        for slot in SLOTS
    ]


def policy_payload() -> dict[str, Any]:
    return {
        "version": CONTRACT_VERSION,
        "output_path_id": OUTPUT_PATH_ID,
        "lock_path_id": LOCK_PATH_ID,
        "targets": [
            {"namespace": namespace, "path_id": path_id}
            for namespace, path_id in TARGET_SPECS
        ],
        "slots": list(SLOTS),
        "markers": marker_specs(),
        "upstream_inputs": [
            {"role": role, "path_id": path_id, "kind": kind}
            for role, path_id, kind in UPSTREAM_INPUT_SPECS
        ],
        "semantic_projection_version": SEMANTIC_PROJECTION_VERSION,
        "semantic_projections": [
            {"role": role, "fields": list(fields)}
            for role, fields in SEMANTIC_PROJECTION_SPECS
        ],
        "semantic_projection_test_vector_sha256": semantic_projection_test_vector_sha256(),
    }


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def policy_contract() -> dict[str, Any]:
    payload = policy_payload()
    return {
        "version": CONTRACT_VERSION,
        "sha256": canonical_sha256(payload),
        "target_rows": len(TARGET_SPECS),
        "slot_rows": len(SLOTS),
        "marker_rows": len(marker_specs()),
        "upstream_input_rows": len(UPSTREAM_INPUT_SPECS),
        "semantic_projection_rows": len(SEMANTIC_PROJECTION_SPECS),
        "semantic_projection_version": SEMANTIC_PROJECTION_VERSION,
        "semantic_projection_test_vector_sha256": semantic_projection_test_vector_sha256(),
        "payload": payload,
    }


def semantic_projection_fields(role: str) -> tuple[str, ...] | None:
    return dict(SEMANTIC_PROJECTION_SPECS).get(role)


def semantic_projection(role: str, payload: dict[str, Any]) -> dict[str, Any]:
    fields = semantic_projection_fields(role)
    if fields is None:
        raise ValueError(f"role is not semantic-projection bound: {role}")
    missing = [field for field in fields if field not in payload]
    if missing:
        raise ValueError(f"missing semantic projection fields for {role}: {missing}")
    return {field: payload[field] for field in fields}


def semantic_projection_test_vector_sha256() -> str:
    vector = {
        "local_release": {"artifact_count": 7, "release_ready": False, "created_at": "ignored"},
        "data_lake": {
            "source_artifact_rows": 9,
            "artifact_rows": 7,
            "unique_path_rows": 7,
            "deduplicated_input_rows": 2,
            "duplicate_input_path_rows": 2,
            "artifacts": ["ignored"],
        },
        "live_integrity": {
            "success": True,
            "failure_count": 0,
            "artifact_rows": 7,
            "strict_verified_rows": 5,
            "volatile_existence_only_rows": 2,
            "missing_rows": 0,
            "unsafe_path_rows": 0,
            "size_mismatch_rows": 0,
            "sha256_mismatch_rows": 0,
            "row_mismatch_rows": 0,
            "created_at": "ignored",
        },
        "human_backlog": {
            "success": True,
            "open_items": 2,
            "total_required_rows": 9,
            "total_completed_rows": 3,
            "total_missing_rows": 6,
            "safe_for_model_claim": False,
            "release_ready": False,
            "created_at": "ignored",
            "failures": ["ignored"],
        },
        "post_source_receipt": {
            "command_rows": 62,
            "command_contract_sha256": "ignored",
            "sqlite_write_command_rows": 0,
            "rerun_ready": True,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        "post_source_validation": {
            "command_rows": 62,
            "command_contract_valid": True,
            "failure_count": 0,
            "receipt_valid": True,
            "sqlite_write_command_rows": 0,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        "post_source_dry_run": {
            "audit_valid": True,
            "command_rows": 62,
            "command_contract_sha256": "ignored",
            "sqlite_write_command_rows": 0,
            "commands_executed": False,
            "outputs_freshness_verified": False,
            "rerun_completion_receipted": False,
            "ready_for_source_drop_rerun": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
    }
    payload = {
        "version": SEMANTIC_PROJECTION_VERSION,
        "rows": [
            {
                "role": role,
                "fields": list(fields),
                "projection": semantic_projection(role, vector[role]),
            }
            for role, fields in SEMANTIC_PROJECTION_SPECS
        ],
    }
    return canonical_sha256(payload)


def build_provenance(
    *,
    ai_root: Path = AI_ROOT,
    platform_root: Path | None = None,
    enzyme_db_root: Path = ENZYME_DB_ROOT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for role, path_id, kind in UPSTREAM_INPUT_SPECS:
        path = resolve_path(
            path_id,
            ai_root=ai_root,
            platform_root=platform_root,
            enzyme_db_root=enzyme_db_root,
        )
        if not path.is_file():
            failures.append({
                "check": "provenance_input_exists",
                "role": role,
                "path_id": path_id,
                "path": str(path),
                "expected": "file",
            })
            continue
        content = path.read_bytes()
        row: dict[str, Any] = {
            "role": role,
            "kind": kind,
            "path_id": path_id,
            "path": str(path),
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        projection_fields = semantic_projection_fields(role)
        if projection_fields is None:
            row["freshness_mode"] = "file_sha256"
        else:
            try:
                source_payload = json.loads(content)
                if not isinstance(source_payload, dict):
                    raise ValueError("semantic projection source must be a JSON object")
                projection = semantic_projection(role, source_payload)
            except Exception as exc:
                failures.append({
                    "check": "semantic_projection_source_valid",
                    "role": role,
                    "path_id": path_id,
                    "path": str(path),
                    "observed": f"{type(exc).__name__}:{exc}",
                    "expected": "JSON object with exact projection fields",
                })
                continue
            row.update({
                "freshness_mode": "semantic_projection",
                "projection_version": SEMANTIC_PROJECTION_VERSION,
                "projection_fields": list(projection_fields),
                "projection": projection,
                "projection_sha256": canonical_sha256(projection),
            })
        rows.append(row)
    return rows, failures


def provenance_sha256(rows: list[dict[str, Any]]) -> str:
    stable_rows = [
        _freshness_digest_row(row)
        for row in rows
    ]
    return canonical_sha256(stable_rows)


def observed_provenance_sha256(rows: list[dict[str, Any]]) -> str:
    return canonical_sha256(rows)


def _freshness_digest_row(row: dict[str, Any]) -> dict[str, Any]:
    base = {
        "role": row.get("role"),
        "kind": row.get("kind"),
        "path_id": row.get("path_id"),
        "path": row.get("path"),
        "freshness_mode": row.get("freshness_mode"),
    }
    if row.get("freshness_mode") == "semantic_projection":
        return {
            **base,
            "projection_version": row.get("projection_version"),
            "projection_fields": row.get("projection_fields"),
            "projection": row.get("projection"),
            "projection_sha256": row.get("projection_sha256"),
        }
    return {
        **base,
        "size_bytes": row.get("size_bytes"),
        "sha256": row.get("sha256"),
    }
