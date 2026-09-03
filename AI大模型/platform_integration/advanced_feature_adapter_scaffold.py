#!/usr/bin/env python3
"""Fail-closed advanced feature adapter scaffold.

Adapters subclass BaseAdvancedFeatureAdapter and implement `run`. This scaffold
only writes blocked/readiness envelopes unless a future adapter is explicitly
implemented with runtime, license and input gates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AdapterContext:
    adapter_id: str
    feature_family: str
    cache_root: Path
    license_ready: bool = False
    runtime_ready: bool = False
    data_ready: bool = False
    model_weight_ready: bool = False


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BaseAdvancedFeatureAdapter:
    """Base interface for future ESM/SaProt/MMseqs2/ddG adapters."""

    def __init__(self, context: AdapterContext):
        self.context = context

    def readiness(self) -> dict[str, Any]:
        ready = all([
            self.context.license_ready,
            self.context.runtime_ready,
            self.context.data_ready,
            self.context.model_weight_ready,
        ])
        return {
            "adapter_id": self.context.adapter_id,
            "feature_family": self.context.feature_family,
            "ready": ready,
            "license_ready": self.context.license_ready,
            "runtime_ready": self.context.runtime_ready,
            "data_ready": self.context.data_ready,
            "model_weight_ready": self.context.model_weight_ready,
        }

    def blocked_envelope(self, case_id: str, reason: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "case_id": case_id,
            "adapter_id": self.context.adapter_id,
            "feature_family": self.context.feature_family,
            "status": "blocked",
            "reason": reason,
            "inputs": inputs or {},
            "outputs": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "local_only": True,
            "input_hash": sha256_text(json.dumps(inputs or {}, sort_keys=True, ensure_ascii=False)),
            "policy": "No feature artifact is produced until license/runtime/data/model gates pass.",
        }
        return payload

    def run(self, case: dict[str, Any]) -> dict[str, Any]:
        ready = self.readiness()
        if not ready["ready"]:
            return self.blocked_envelope(
                str(case.get("case_id") or "unknown"),
                "adapter_not_ready",
                {"readiness": ready},
            )
        raise NotImplementedError("Concrete adapters must implement runtime execution.")


def write_envelope(path: Path, envelope: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
