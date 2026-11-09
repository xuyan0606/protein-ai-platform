"""Stable evidence objects used by scientific report producers.

The module is deliberately independent of persistence and rendering layers so
that every producer applies the same conservative completion rules.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


class EvidenceType(str, Enum):
    EXPERIMENTAL_FACT = "experimental_fact"
    DATABASE_EVIDENCE = "database_evidence"
    COMPUTED_RESULT = "computed_result"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"


EVIDENCE_TYPES = frozenset(item.value for item in EvidenceType)

# These statuses are intentionally shared with asynchronous tool results.  A
# producer may add metadata, but it must not invent a second terminal state.
EVIDENCE_STATUSES = frozenset(
    {
        "completed",
        "completed_no_hit",
        "completed_with_hits",
        "waiting",
        "submitted",
        "failed",
        "not_run",
        "not_available",
    }
)
_COMPLETE_STATUSES = frozenset({"completed", "completed_no_hit", "completed_with_hits"})
_STATUS_LABELS = {
    "completed": "已完成",
    "completed_no_hit": "已完成（无命中）",
    "completed_with_hits": "已完成（有命中）",
    "waiting": "等待/未完成",
    "submitted": "等待/未完成",
    "failed": "失败",
    "not_run": "未运行",
    "not_available": "不可用",
}


def normalize_evidence_status(status: str | Any) -> dict[str, Any]:
    """Validate a status and expose the only safe completion decision."""
    value = getattr(status, "value", status)
    value = str(value).strip().lower()
    if value not in EVIDENCE_STATUSES:
        raise ValueError(f"unsupported evidence status: {value}")
    return {
        "status": value,
        "is_complete": value in _COMPLETE_STATUSES,
        "render_status": _STATUS_LABELS[value],
    }


@dataclass(frozen=True)
class EvidenceRecord(Mapping[str, Any]):
    """Immutable, mapping-compatible evidence record."""

    evidence_type: str
    status: str
    source: str | None
    derived_from: tuple[str, ...]
    value: Any
    is_complete: bool
    render_status: str

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type,
            "status": self.status,
            "source": self.source,
            "derived_from": list(self.derived_from),
            "value": self.value,
            "is_complete": self.is_complete,
            "render_status": self.render_status,
        }


def make_evidence_record(
    *,
    evidence_type: str | EvidenceType,
    status: str,
    source: str | None = None,
    derived_from: Sequence[str] | str | None = None,
    value: Any = None,
) -> EvidenceRecord:
    """Build a validated evidence record.

    Inferences and hypotheses are claims derived from other evidence.  They
    therefore require at least one stable upstream identifier even when their
    status is not complete.
    """
    type_value = getattr(evidence_type, "value", evidence_type)
    type_value = str(type_value).strip()
    if type_value not in EVIDENCE_TYPES:
        raise ValueError(f"unsupported evidence type: {type_value}")

    normalized = normalize_evidence_status(status)
    if derived_from is None:
        parents: tuple[str, ...] = ()
    elif isinstance(derived_from, str):
        parents = (derived_from,) if derived_from.strip() else ()
    else:
        parents = tuple(str(item).strip() for item in derived_from if str(item).strip())
    if type_value in {EvidenceType.INFERENCE.value, EvidenceType.HYPOTHESIS.value} and not parents:
        raise ValueError(f"{type_value} evidence requires derived_from")

    return EvidenceRecord(
        evidence_type=type_value,
        status=normalized["status"],
        source=str(source) if source is not None else None,
        derived_from=parents,
        value=value,
        is_complete=normalized["is_complete"],
        render_status=normalized["render_status"],
    )
