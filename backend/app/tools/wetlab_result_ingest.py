"""Validate and normalize wet-lab measurements for iterative design."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.tools.registry import ToolRegistry


ALLOWED_METRICS = {"activity", "kcat", "km", "kcat_km", "tm", "half_life", "residual_activity", "expression_yield", "secretion_yield", "optimal_ph"}


def validate_wetlab_result(
    sample_id: str,
    metric: str,
    value: float,
    unit: str,
    condition: dict[str, Any] | None = None,
    sequence_id: str | None = None,
    replicate: int | None = None,
    quality: str = "unreviewed",
    notes: str | None = None,
) -> dict[str, Any]:
    """Validate one measurement and return a provenance-preserving record."""
    sample = sample_id.strip()
    metric_key = metric.strip().lower()
    unit_key = unit.strip()
    if not sample:
        raise ValueError("INVALID_SAMPLE_ID: sample_id must not be empty")
    if metric_key not in ALLOWED_METRICS:
        raise ValueError(f"INVALID_METRIC: choose one of {sorted(ALLOWED_METRICS)}")
    if not unit_key:
        raise ValueError("INVALID_UNIT: unit must not be empty")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("INVALID_VALUE: value must be finite")
    if replicate is not None and replicate < 1:
        raise ValueError("INVALID_REPLICATE: replicate must be >= 1")
    if quality not in {"unreviewed", "reviewed", "rejected"}:
        raise ValueError("INVALID_QUALITY: use unreviewed, reviewed, or rejected")
    return {
        "sample_id": sample,
        "sequence_id": sequence_id.strip() if sequence_id else None,
        "metric": metric_key,
        "value": float(value),
        "unit": unit_key,
        "condition": condition or {},
        "replicate": replicate,
        "quality": quality,
        "notes": notes,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "training_import_allowed": quality == "reviewed",
        "status": "accepted_for_review" if quality != "rejected" else "rejected",
    }


def wetlab_result_ingest(
    sample_id: str,
    metric: str,
    value: float,
    unit: str,
    condition: dict[str, Any] | None = None,
    sequence_id: str | None = None,
    replicate: int | None = None,
    quality: str = "unreviewed",
    notes: str | None = None,
) -> dict[str, Any]:
    """Validate tool input; authenticated API calls persist the returned record."""
    return validate_wetlab_result(
        sample_id=sample_id,
        metric=metric,
        value=value,
        unit=unit,
        condition=condition,
        sequence_id=sequence_id,
        replicate=replicate,
        quality=quality,
        notes=notes,
    )


ToolRegistry.register(
    name="wetlab_result_ingest",
    description="Validate and normalize one wet-lab measurement for experiment-to-design feedback; does not silently promote data to training.",
    parameters={
        "type": "object",
        "properties": {
            "sample_id": {"type": "string"},
            "metric": {"type": "string", "enum": sorted(ALLOWED_METRICS)},
            "value": {"type": "number"},
            "unit": {"type": "string"},
            "condition": {"type": "object"},
            "sequence_id": {"type": "string"},
            "replicate": {"type": "integer", "minimum": 1},
            "quality": {"type": "string", "enum": ["unreviewed", "reviewed", "rejected"], "default": "unreviewed"},
            "notes": {"type": "string"},
        },
        "required": ["sample_id", "metric", "value", "unit"],
    },
    handler=wetlab_result_ingest,
    category="feedback",
    timeout_seconds=30,
)
