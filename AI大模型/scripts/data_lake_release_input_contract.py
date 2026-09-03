#!/usr/bin/env python3
"""Canonical non-cyclic data-lake contract used by local release gates."""

from __future__ import annotations

import hashlib
import json
from typing import Any


CONTRACT_VERSION = "data-lake-release-input-v1"
RELEASE_INPUT_EXCLUDED_PATHS = {
    "reports/safe_training_pipeline_run.json",
    "reports/data_lake_live_content_integrity_validation_report.json",
    "reports/local_release_manifest.json",
    "reports/local_release_manifest_fail_closed_consistency_validation_report.json",
    "reports/local_release_safety_guard_link_validation_report.json",
}


def build_release_input_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = [row for row in manifest.get("artifacts") or [] if isinstance(row, dict)]
    included = [row for row in artifacts if row.get("path") not in RELEASE_INPUT_EXCLUDED_PATHS]
    excluded = sorted(
        str(row.get("path")) for row in artifacts if row.get("path") in RELEASE_INPUT_EXCLUDED_PATHS
    )
    payload = {
        "version": CONTRACT_VERSION,
        "root": manifest.get("root"),
        "artifacts": included,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "version": CONTRACT_VERSION,
        "sha256": digest,
        "artifact_rows": len(included),
        "excluded_paths": excluded,
    }
