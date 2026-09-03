"""Sequence-hash identity consistency guard for enzyme workflows."""

from __future__ import annotations

import hashlib
import json
from typing import Any


_IDENTITY_CACHE: dict[str, dict[str, Any]] = {}


def sequence_hash(sequence: str) -> str:
    normalized = "".join(str(sequence or "").upper().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def check_identity_consistency(
    sequence: str,
    profile: dict[str, Any] | None,
    *,
    model_version: str | None = None,
    evidence_version: str | None = None,
) -> dict[str, Any]:
    """Cache identity by sequence/model/evidence and fail closed on conflicts."""
    payload = profile if isinstance(profile, dict) else {}
    seq_hash = sequence_hash(sequence)
    identity = str(
        payload.get("identity_label")
        or payload.get("family")
        or payload.get("enzyme_family")
        or payload.get("identity_status")
        or "unknown"
    ).strip()
    key = json.dumps(
        {"sequence_hash": seq_hash, "model_version": model_version or "", "evidence_version": evidence_version or ""},
        sort_keys=True,
    )
    previous = _IDENTITY_CACHE.get(key)
    conflict = bool(previous and previous.get("identity") not in {identity, "unknown"} and identity != "unknown")
    if not conflict:
        _IDENTITY_CACHE[key] = {
            "identity": identity,
            "model_version": model_version,
            "evidence_version": evidence_version,
            "cache_key": key,
        }
    return {
        "status": "NEEDS_REVIEW" if conflict else "CONSISTENT",
        "sequence_hash": seq_hash,
        "identity": identity,
        "previous_identity": previous.get("identity") if conflict else None,
        "model_version": model_version,
        "evidence_version": evidence_version,
        "reason": "identity conflict for identical sequence" if conflict else "identity cached by sequence hash",
    }


def clear_identity_cache() -> None:
    _IDENTITY_CACHE.clear()
