"""Read-only runtime readiness checks for local model-backed tools."""

from __future__ import annotations

import importlib.util
from typing import Any


def collect_model_runtime_readiness() -> dict[str, Any]:
    """Report import-level ESM-2 prerequisites without downloading models."""
    missing = [name for name in ("torch", "transformers") if importlib.util.find_spec(name) is None]
    return {
        "schema_version": "model-runtime-readiness-v1",
        "esm2": {
            "status": "ready_for_smoke" if not missing else "blocked",
            "missing_dependencies": missing,
            "action": "run local ESM-2 smoke test" if not missing else "install missing runtime dependencies in the target environment",
            "weights_checked": False,
        },
    }
