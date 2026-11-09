"""Platform/data manifest snapshot helpers for report exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, settings
from app.core.version import PROJECT_VERSION


SNAPSHOT_SCOPE = "version_and_source_snapshot_only"
READINESS_ASSERTION = "not_asserted"


def _empty(value: Any) -> Any:
    return value if value is not None else ""


def _dataset_snapshot(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raw = {}
    return {
        "source": str(_empty(raw.get("source"))),
        "version": str(_empty(raw.get("version") or raw.get("data_version") or raw.get("source_version"))),
        "checksum": str(_empty(raw.get("checksum") or raw.get("sha256") or raw.get("content_hash"))),
    }


def collect_platform_manifest(deploy_data_root: str | Path | None = None) -> dict[str, Any]:
    """Return a deterministic platform/data source snapshot.

    This records application and data-source versions for report reproducibility.
    It deliberately does not assert that the staged data layer is complete or
    live-ready.
    """

    root = Path(deploy_data_root or settings.DEPLOY_DATA_ROOT or PROJECT_ROOT / "deploy_data").expanduser()
    manifest_path = root / "live_manifest.json"
    payload: dict[str, Any] | None = None
    notes: list[str] = []

    root_exists = root.exists()
    if not root_exists:
        status = "blocked"
        manifest_status = "missing"
        notes.append("deploy_data root is missing; platform/data source snapshot is incomplete.")
    elif not manifest_path.exists():
        status = "degraded"
        manifest_status = "missing"
        notes.append("deploy_data/live_manifest.json is missing; report records app version and deploy_data path only.")
    else:
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, dict) else {}
            status = "snapshot"
            manifest_status = "present"
            notes.append(
                "Manifest records configured versions and sources only; it is not a data-integrity or live-readiness assertion."
            )
        except (OSError, json.JSONDecodeError) as exc:
            status = "degraded"
            manifest_status = "unreadable"
            notes.append(f"deploy_data/live_manifest.json could not be read as JSON: {exc}")

    payload = payload or {}
    expected = payload.get("expected_datasets") if isinstance(payload.get("expected_datasets"), dict) else {}
    expected_datasets = {
        str(name): _dataset_snapshot(expected[name])
        for name in sorted(expected)
    }

    return {
        "status": status,
        "snapshot_scope": SNAPSHOT_SCOPE,
        "readiness": READINESS_ASSERTION,
        "app": {
            "name": settings.APP_NAME,
            "version": PROJECT_VERSION,
        },
        "deploy_data_root": str(root),
        "live_manifest": {
            "path": str(manifest_path),
            "status": manifest_status,
            "schema_version": _empty(payload.get("schema_version")),
            "data_version": _empty(payload.get("data_version")),
            "updated_at": _empty(payload.get("updated_at")),
            "mode": _empty(payload.get("mode")),
        },
        "expected_datasets": expected_datasets,
        "notes": notes,
    }
