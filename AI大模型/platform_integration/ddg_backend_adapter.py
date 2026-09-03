#!/usr/bin/env python3
"""Fail-closed adapter contract for Rosetta/PyRosetta/FoldX ddG backends."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT / "scripts"))
from ddg_backend_config import default_ddg_config_path  # noqa: E402

CONFIG = default_ddg_config_path()
READINESS = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def sha256_text(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def classify_ddg(ddg_kcal_mol: float, thresholds: dict[str, Any]) -> dict[str, Any]:
    if ddg_kcal_mol < float((thresholds.get("stabilizing") or {}).get("max", -1.0)):
        return {"band": "stabilizing", "decision": "stabilizing_hypothesis", "manual_review_required": False}
    if ddg_kcal_mol <= float((thresholds.get("near_neutral_manual_review") or {}).get("max", 1.0)):
        return {"band": "near_neutral_manual_review", "decision": "manual_review", "manual_review_required": True}
    if ddg_kcal_mol <= float((thresholds.get("destabilizing_watch") or {}).get("max", 2.0)):
        return {"band": "destabilizing_watch", "decision": "watch", "manual_review_required": True}
    return {"band": "destabilizing_no_go", "decision": "no_go", "manual_review_required": True}


class DDGBackendAdapter:
    """Adapter facade. Execution remains blocked until readiness says a backend is ready."""

    def __init__(self, config_path: Path = CONFIG, readiness_path: Path = READINESS):
        self.config = load_json(config_path)
        self.readiness = load_json(readiness_path)

    def select_backend(self, requested_backend: str | None = None) -> dict[str, Any]:
        backends = {
            str(row.get("backend")): row
            for row in self.readiness.get("backends", [])
            if isinstance(row, dict) and row.get("backend")
        }
        if requested_backend:
            return backends.get(requested_backend, {"backend": requested_backend, "ready_for_execution": False})
        for backend in self.config.get("backend_priority") or []:
            row = backends.get(backend)
            if row and row.get("ready_for_execution"):
                return row
        for backend in self.config.get("backend_priority") or []:
            if backend in backends:
                return backends[backend]
        return {"backend": "none", "ready_for_execution": False, "blockers": ["no ddG backend configured"]}

    def build_envelope(self, request: dict[str, Any], requested_backend: str | None = None) -> dict[str, Any]:
        backend = self.select_backend(requested_backend)
        ready = bool(backend.get("ready_for_execution"))
        status = "ready_to_execute" if ready else "blocked"
        reason = "" if ready else "; ".join(backend.get("blockers") or ["ddG backend is not ready"])
        return {
            "case_id": str(request.get("case_id") or "unknown"),
            "backend": backend.get("backend") or "none",
            "status": status,
            "negative_ddg_is_stabilizing": bool(self.config.get("negative_ddg_is_stabilizing", True)),
            "inputs": {
                "structure_id": request.get("structure_id"),
                "structure_path": request.get("structure_path"),
                "structure_sha256": request.get("structure_sha256"),
                "chain_id": request.get("chain_id"),
                "mutations": request.get("mutations") or [],
                "request_hash": sha256_text(request),
            },
            "outputs": {},
            "artifacts": {},
            "manual_review_required": True,
            "local_only": True,
            "reason": reason,
            "limitations": [
                "This adapter does not fabricate ddG values.",
                "Rosetta/PyRosetta/FoldX require license and runtime evidence before execution.",
                "Predicted ddG must not be treated as wet-lab stability feedback.",
            ],
        }


def build_blocked_envelope(request: dict[str, Any], requested_backend: str | None = None) -> dict[str, Any]:
    return DDGBackendAdapter().build_envelope(request, requested_backend=requested_backend)
