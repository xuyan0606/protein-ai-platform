"""Keep HTTP, registry and Celery budgets consistent for real CPU runtimes."""
import math
import os

DEFAULT_HTTP = {"DDGUN": 180., "COLABFOLD": 300., "EVCOUPLINGS": 180.}
TOOL_PREFIX = {"ddgun_predict": "DDGUN", "colabfold_predict": "COLABFOLD",
               "evcouplings_analyze": "EVCOUPLINGS"}


def service_timeout(prefix: str, default: float) -> float:
    configured = os.getenv(f"{prefix}_SERVICE_TIMEOUT_SECONDS", "").strip()
    if not configured:
        return default
    try:
        value = float(configured)
    except ValueError as exc:
        raise ValueError(f"{prefix}_SERVICE_TIMEOUT_SECONDS must be numeric.") from exc
    if not math.isfinite(value) or not 1 <= value <= 14400:
        raise ValueError(f"{prefix}_SERVICE_TIMEOUT_SECONDS must be between 1 and 14400.")
    return value


def tool_timeout(name: str, default: int) -> int:
    if name == "thermostability_candidate_workflow":
        # Three sequential optional model branches plus ESM, local work and cleanup.
        return max(default, math.ceil(sum(service_timeout(p, d) for p, d in DEFAULT_HTTP.items())) + 600)
    prefix = TOOL_PREFIX.get(name)
    return max(default, math.ceil(service_timeout(prefix, DEFAULT_HTTP[prefix])) + 30) if prefix else default
