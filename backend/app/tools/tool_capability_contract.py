"""Shared capability contract for computational biology tools.

The contract is intentionally evidence-first: real runtime/checkpoint/log fields
must be supplied by the actual runtime path, never invented by proxy tools.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

CAPABILITY_STATUSES = {"real_runtime", "external_service", "proxy", "blocked"}


def input_sha256(payload: Any) -> str:
    """Return a stable SHA-256 digest for tool inputs."""
    if isinstance(payload, bytes):
        data = payload
    elif isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def empty_artifact_manifest() -> dict[str, Any]:
    return {"version": 1, "total_count": 0, "total_size": 0, "groups": {}, "counts": {}}


def build_capability_contract(
    *,
    capability_status: str,
    model: str | None = None,
    version: str | None = None,
    checkpoint_or_weight: str | None = None,
    input_payload: Any = None,
    runtime: dict[str, Any] | None = None,
    logs: list[dict[str, Any]] | None = None,
    artifact_manifest: dict[str, Any] | None = None,
    license_class: str | None = None,
    commercial_use_status: str | None = None,
    scientific_boundary: str | dict[str, Any] | None = None,
    failure_reason: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the unified capability contract required by report-facing tools."""
    if capability_status not in CAPABILITY_STATUSES:
        raise ValueError(f"Unsupported capability_status: {capability_status}")
    return {
        "capability_status": capability_status,
        "model": model,
        "version": version,
        "checkpoint_or_weight": checkpoint_or_weight,
        "input_sha256": input_sha256(input_payload) if input_payload is not None else None,
        "runtime": runtime,
        "logs": logs or [],
        "artifact_manifest": artifact_manifest or empty_artifact_manifest(),
        "license_class": license_class,
        "commercial_use_status": commercial_use_status,
        "scientific_boundary": scientific_boundary,
        "failure_reason": failure_reason,
    }


def merge_capability_contract(result: dict[str, Any], **contract_kwargs: Any) -> dict[str, Any]:
    """Return a result with top-level contract fields applied."""
    contract = build_capability_contract(**contract_kwargs)
    return {**result, **contract}
