#!/usr/bin/env python3
"""Non-cyclic semantic contract for local-release consistency receipts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

try:
    from data_lake_release_input_contract import build_release_input_contract
except ModuleNotFoundError:
    from scripts.data_lake_release_input_contract import build_release_input_contract


CONTRACT_VERSION = "local-release-consistency-semantic-input-v1"
INPUT_ROLES = ("release", "data_lake", "live_integrity", "contract_policy", "semantic_policy")

DATA_LAKE_SEMANTIC_EXCLUDED_PATHS = frozenset({
    "reports/local_release_consistency_receipt_current_validation_report.json",
    "reports/local_release_consistency_receipt_current_regression_report.json",
    "reports/local_release_safety_guard_links_current_validation_report.json",
    "reports/local_release_safety_guard_links_current_regression_report.json",
})

RELEASE_SUMMARY_NORMALIZED_FIELDS = (
    "data_lake_live_content_integrity_release_input_contract_sha256",
    "data_lake_live_content_integrity_release_input_artifact_rows",
    "data_lake_live_content_integrity_release_input_excluded_paths",
)

LIVE_NORMALIZED_FIELDS = (
    "release_input_contract_sha256",
    "release_input_artifact_rows",
    "release_input_excluded_paths",
)

RELEASE_SUMMARY_EXCLUDED_FIELDS = frozenset({
    "local_release_fail_closed_consistency_success",
    "local_release_fail_closed_consistency_failures",
    "local_release_fail_closed_consistency_release_ready",
    "local_release_fail_closed_consistency_artifact_count",
    "local_release_fail_closed_consistency_receipt_atomic_commit",
    "local_release_fail_closed_consistency_lock_acquired",
    "local_release_safety_guard_link_success",
    "local_release_safety_guard_link_failures",
    "local_release_safety_guard_link_count",
    "local_release_consistency_receipt_current_success",
    "local_release_consistency_receipt_current_failures",
    "local_release_consistency_receipt_current_regression_success",
    "local_release_consistency_receipt_current_regression_failed_rows",
})

LIVE_FIELDS = (
    "success",
    "failure_count",
    "local_only",
    "validated_root",
    "validated_manifest_path",
    "release_input_contract_version",
    "release_input_contract_sha256",
    "release_input_artifact_rows",
    "release_input_excluded_paths",
    "artifact_rows",
    "strict_verified_rows",
    "volatile_existence_only_rows",
    "configured_volatile_existence_only_paths",
    "volatile_existence_only_paths",
    "missing_rows",
    "unsafe_path_rows",
    "size_mismatch_rows",
    "sha256_mismatch_rows",
    "row_mismatch_rows",
    "safe_for_model_claim",
    "release_ready",
)

CONTRACT_POLICY_FIELDS = (
    "success",
    "failure_count",
    "contract_module_path",
    "contract_module_sha256",
    "expected_contract_version",
    "expected_excluded_paths",
    "expected_test_vector_sha256",
    "safe_for_model_claim",
    "release_ready",
)

SEMANTIC_POLICY_FIELDS = (
    "success",
    "failure_count",
    "policy_script_path",
    "policy_script_sha256",
    "contract_module_path",
    "contract_module_sha256",
    "expected_contract_version",
    "expected_input_roles",
    "expected_data_lake_semantic_excluded_paths",
    "expected_release_summary_normalized_fields",
    "expected_live_normalized_fields",
    "expected_release_summary_excluded_fields",
    "expected_live_projection_fields",
    "expected_contract_policy_projection_fields",
    "expected_canonical_policy_sha256",
    "expected_test_vector_sha256",
    "expected_shared_contract_test_vector_sha256",
    "observed_policy_payload",
    "observed_canonical_policy_sha256",
    "observed_test_vector_sha256",
    "observed_shared_contract_test_vector_sha256",
    "safe_for_model_claim",
    "release_ready",
)


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require_fields(role: str, payload: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise ValueError(f"missing semantic projection fields for {role}: {missing}")
    return {field: payload[field] for field in fields}


def release_projection(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("readiness_summary")
    if not isinstance(summary, dict):
        raise ValueError("release readiness_summary must be an object")
    required_top_level = ("release_ready", "local_only", "artifact_count", "missing_artifacts", "blocked_capabilities")
    projected = require_fields("release", payload, required_top_level)
    projected["readiness_summary"] = {
        key: value
        for key, value in summary.items()
        if key not in RELEASE_SUMMARY_EXCLUDED_FIELDS
    }
    return projected


def data_lake_projection(payload: dict[str, Any]) -> dict[str, Any]:
    metadata_fields = (
        "root",
        "source_artifact_rows",
        "artifact_rows",
        "unique_path_rows",
        "deduplicated_input_rows",
        "duplicate_input_path_rows",
        "duplicate_input_paths",
    )
    projected = require_fields("data_lake", payload, metadata_fields)
    semantic_manifest = dict(payload)
    semantic_manifest["artifacts"] = [
        row for row in payload.get("artifacts") or []
        if isinstance(row, dict) and row.get("path") not in DATA_LAKE_SEMANTIC_EXCLUDED_PATHS
    ]
    projected["release_input_contract"] = build_release_input_contract(semantic_manifest)
    return projected


def live_integrity_projection(payload: dict[str, Any]) -> dict[str, Any]:
    return require_fields("live_integrity", payload, LIVE_FIELDS)


def contract_policy_projection(payload: dict[str, Any]) -> dict[str, Any]:
    return require_fields("contract_policy", payload, CONTRACT_POLICY_FIELDS)


def semantic_policy_projection(payload: dict[str, Any]) -> dict[str, Any]:
    return require_fields("semantic_policy", payload, SEMANTIC_POLICY_FIELDS)


def semantic_projection(role: str, payload: dict[str, Any]) -> dict[str, Any]:
    builders = {
        "release": release_projection,
        "data_lake": data_lake_projection,
        "live_integrity": live_integrity_projection,
        "contract_policy": contract_policy_projection,
        "semantic_policy": semantic_policy_projection,
    }
    if role not in builders:
        raise ValueError(f"unknown semantic input role: {role}")
    return builders[role](payload)


def build_semantic_inputs(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if set(payloads) != set(INPUT_ROLES):
        raise ValueError(f"semantic input roles must equal {list(INPUT_ROLES)}")
    projected_data_lake = data_lake_projection(payloads["data_lake"])
    normalized_release_input = projected_data_lake["release_input_contract"]
    normalized_values = {
        "release_input_contract_sha256": normalized_release_input["sha256"],
        "release_input_artifact_rows": normalized_release_input["artifact_rows"],
        "release_input_excluded_paths": normalized_release_input["excluded_paths"],
    }
    rows = []
    for role in INPUT_ROLES:
        if role == "data_lake":
            projection = projected_data_lake
        else:
            projection = semantic_projection(role, payloads[role])
        if role == "live_integrity":
            for field in LIVE_NORMALIZED_FIELDS:
                projection[field] = normalized_values[field]
        elif role == "release":
            summary = projection["readiness_summary"]
            for release_field, live_field in zip(RELEASE_SUMMARY_NORMALIZED_FIELDS, LIVE_NORMALIZED_FIELDS):
                summary[release_field] = normalized_values[live_field]
        rows.append({
            "role": role,
            "projection": projection,
            "projection_sha256": canonical_sha256(projection),
        })
    digest_payload = {"version": CONTRACT_VERSION, "rows": rows}
    return {
        "contract_version": CONTRACT_VERSION,
        "input_rows": len(rows),
        "rows": rows,
        "sha256": canonical_sha256(digest_payload),
    }


def test_vector_sha256() -> str:
    release_summary = {
        "stable_flag": True,
        "stable_count": 7,
        **{field: "excluded" for field in RELEASE_SUMMARY_EXCLUDED_FIELDS},
    }
    vector = {
        "release": {
            "release_ready": False,
            "local_only": True,
            "artifact_count": 7,
            "missing_artifacts": [],
            "blocked_capabilities": ["model_quality_claim"],
            "readiness_summary": release_summary,
            "created_at": "ignored",
        },
        "data_lake": {
            "root": "/fixture",
            "source_artifact_rows": 3,
            "artifact_rows": 2,
            "unique_path_rows": 2,
            "deduplicated_input_rows": 1,
            "duplicate_input_path_rows": 1,
            "duplicate_input_paths": ["a"],
            "artifacts": [
                {"path": "a", "exists": True, "sha256": "1" * 64},
                {"path": "reports/local_release_manifest.json", "exists": True, "sha256": "2" * 64},
            ],
            "created_at": "ignored",
        },
        "live_integrity": {
            **{field: 0 for field in LIVE_FIELDS},
            "success": True,
            "local_only": True,
            "validated_root": "/fixture",
            "validated_manifest_path": "/fixture/manifest.json",
            "release_input_contract_version": "data-lake-release-input-v1",
            "release_input_contract_sha256": "3" * 64,
            "release_input_excluded_paths": [],
            "configured_volatile_existence_only_paths": [],
            "volatile_existence_only_paths": [],
            "safe_for_model_claim": False,
            "release_ready": False,
            "created_at": "ignored",
            "validated_manifest_sha256": "ignored",
        },
        "contract_policy": {
            "success": True,
            "failure_count": 0,
            "contract_module_path": "/fixture/contract.py",
            "contract_module_sha256": "4" * 64,
            "expected_contract_version": "data-lake-release-input-v1",
            "expected_excluded_paths": [],
            "expected_test_vector_sha256": "5" * 64,
            "safe_for_model_claim": False,
            "release_ready": False,
            "created_at": "ignored",
        },
        "semantic_policy": {
            **{field: False for field in SEMANTIC_POLICY_FIELDS},
            "success": True,
            "failure_count": 0,
            "policy_script_path": "/fixture/policy.py",
            "policy_script_sha256": "6" * 64,
            "contract_module_path": "/fixture/contract.py",
            "contract_module_sha256": "4" * 64,
            "expected_contract_version": CONTRACT_VERSION,
            "expected_input_roles": list(INPUT_ROLES),
            "expected_data_lake_semantic_excluded_paths": sorted(DATA_LAKE_SEMANTIC_EXCLUDED_PATHS),
            "expected_release_summary_normalized_fields": list(RELEASE_SUMMARY_NORMALIZED_FIELDS),
            "expected_live_normalized_fields": list(LIVE_NORMALIZED_FIELDS),
            "expected_release_summary_excluded_fields": sorted(RELEASE_SUMMARY_EXCLUDED_FIELDS),
            "expected_live_projection_fields": list(LIVE_FIELDS),
            "expected_contract_policy_projection_fields": list(CONTRACT_POLICY_FIELDS),
            "expected_canonical_policy_sha256": "7" * 64,
            "expected_test_vector_sha256": "8" * 64,
            "expected_shared_contract_test_vector_sha256": "9" * 64,
            "observed_policy_payload": {},
            "observed_canonical_policy_sha256": "7" * 64,
            "observed_test_vector_sha256": "8" * 64,
            "observed_shared_contract_test_vector_sha256": "9" * 64,
            "safe_for_model_claim": False,
            "release_ready": False,
            "created_at": "ignored",
        },
    }
    return build_semantic_inputs(vector)["sha256"]
