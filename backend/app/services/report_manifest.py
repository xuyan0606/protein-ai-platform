"""Reproducibility manifest helpers for report generation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


_SENSITIVE_KEY_PARTS = (
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "secret",
    "password",
)
_SENSITIVE_STRING_RE = re.compile(
    r"(?i)(bearer\s+)[^\s,;]+|((?:token|api[_-]?key|authorization|cookie|password|secret)\s*[=:]\s*)[^&\s,;]+"
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _public(value: Any) -> Any:
    """Return JSON-safe public metadata, dropping secret-bearing fields."""
    if isinstance(value, Mapping):
        return {
            str(key): _public(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if not _is_sensitive_key(str(key))
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_public(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return _SENSITIVE_STRING_RE.sub(lambda match: f"{match.group(1) or match.group(2)}[REDACTED]", value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)


def _sha256(value: bytes | str | Path) -> str:
    if isinstance(value, Path):
        value = value.read_bytes()
    elif isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def build_report_manifest(
    *,
    inputs: Mapping[str, bytes | str | Path] | None = None,
    report_schema_version: str,
    tools: Any = (),
    models: Any = (),
    databases: Any = (),
    runtime: Mapping[str, Any] | None = None,
    generated_at: str,
    revision: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic, non-secret report manifest.

    Input values are represented only by a SHA-256 digest and logical name.
    All source metadata is recursively filtered by key before serialization.
    """
    input_rows = [
        {"name": str(name), "sha256": _sha256(value)}
        for name, value in sorted((inputs or {}).items(), key=lambda pair: str(pair[0]))
    ]
    manifest: dict[str, Any] = {
        "manifest_version": 1,
        "report_schema_version": str(report_schema_version),
        "inputs": input_rows,
        "tools": _public(tools),
        "models": _public(models),
        "databases": _public(databases),
        "runtime": _public(runtime or {}),
        "generated_at": str(generated_at),
    }
    if revision is not None:
        manifest["revision"] = str(revision)
    return manifest


def manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Hash canonical JSON so equivalent manifests always share one digest."""
    payload = json.dumps(_public(manifest), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
