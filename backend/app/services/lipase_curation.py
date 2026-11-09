"""Service functions for platform-side lipase curation records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lipase_curation import LipaseCurationBatch, LipaseCurationRecord

VALID_SOURCE_TYPES = {"literature", "experiment", "tool_feedback", "manual_note"}
VALID_REVIEW_STATUSES = {"submitted", "triaged", "accepted", "rejected", "needs_more_evidence", "batched", "published"}
ADMIN_REVIEW_STATUSES = {"submitted", "triaged", "accepted", "rejected", "needs_more_evidence"}
VALID_BATCH_STATUSES = {"prepared", "published", "voided"}
LIPASE_CURATION_PUBLISH_CONFIRMATION = "PUBLISH_LIPASE_CURATION_BATCH"


def _serialize_record(record: LipaseCurationRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "source_type": record.source_type,
        "status": record.status,
        "created_by_user_id": record.created_by_user_id,
        "reviewed_by_user_id": record.reviewed_by_user_id,
        "paper_key": record.paper_key,
        "title": record.title,
        "doi": record.doi,
        "pmid": record.pmid,
        "enzyme_name": record.enzyme_name,
        "mutation_code": record.mutation_code,
        "position": record.position,
        "linked_task_id": record.linked_task_id,
        "evidence_payload": record.evidence_payload,
        "feedback_payload": record.feedback_payload,
        "notes": record.notes,
        "reviewer_notes": record.reviewer_notes,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
    }


def _serialize_batch(batch: LipaseCurationBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "batch_key": batch.batch_key,
        "status": batch.status,
        "created_by_user_id": batch.created_by_user_id,
        "published_by_user_id": batch.published_by_user_id,
        "source_type": batch.source_type,
        "record_ids": batch.record_ids,
        "manifest": batch.manifest,
        "export_payload": batch.export_payload,
        "confirmation_token": batch.confirmation_token,
        "reviewer_notes": batch.reviewer_notes,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "published_at": batch.published_at.isoformat() if batch.published_at else None,
    }


def _build_export_payload(records: list[LipaseCurationRecord], *, source_type: str | None = None) -> dict[str, Any]:
    serialized = [_serialize_record(record) for record in records]
    return {
        "source": "protein_ai_platform_lipase_curation_queue",
        "target": "kwb_lipase_db_manual_import",
        "read_only_source_db": True,
        "source_type": source_type,
        "record_count": len(serialized),
        "records": serialized,
        "required_manual_steps": [
            "review accepted records against source literature or experiment notebook",
            "prepare a curated lipase.db import patch outside the live read-only database",
            "run integrity_check and foreign_key_check on the staged SQLite copy",
            "replace production lipase.db only through an approved release window",
        ],
    }


def _build_batch_manifest(records: list[LipaseCurationRecord], *, source_type: str | None = None) -> dict[str, Any]:
    mutation_codes = sorted({record.mutation_code for record in records if record.mutation_code})
    paper_keys = sorted({record.paper_key for record in records if record.paper_key})
    linked_task_ids = sorted({record.linked_task_id for record in records if record.linked_task_id})
    return {
        "record_count": len(records),
        "source_type": source_type,
        "mutation_codes": mutation_codes,
        "paper_keys": paper_keys,
        "linked_task_ids": linked_task_ids,
        "status_policy": "accepted records are batched for manual import; publish does not mutate lipase.db",
    }


def normalize_source_type(source_type: str) -> str:
    normalized = (source_type or "").strip().lower()
    if normalized not in VALID_SOURCE_TYPES:
        raise ValueError(f"source_type must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}")
    return normalized


def normalize_review_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized not in VALID_REVIEW_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(VALID_REVIEW_STATUSES))}")
    return normalized


def normalize_admin_review_status(status: str) -> str:
    normalized = normalize_review_status(status)
    if normalized not in ADMIN_REVIEW_STATUSES:
        raise ValueError("batched/published statuses are controlled by curation batch workflow")
    return normalized


def _normalize_batch_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized not in VALID_BATCH_STATUSES:
        raise ValueError(f"batch status must be one of: {', '.join(sorted(VALID_BATCH_STATUSES))}")
    return normalized


async def create_lipase_curation_record(
    session: AsyncSession,
    *,
    user_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    record = LipaseCurationRecord(
        source_type=normalize_source_type(str(payload.get("source_type") or "")),
        status="submitted",
        created_by_user_id=user_id,
        paper_key=payload.get("paper_key"),
        title=payload.get("title"),
        doi=payload.get("doi"),
        pmid=payload.get("pmid"),
        enzyme_name=payload.get("enzyme_name"),
        mutation_code=payload.get("mutation_code"),
        position=payload.get("position"),
        linked_task_id=payload.get("linked_task_id"),
        evidence_payload=payload.get("evidence_payload"),
        feedback_payload=payload.get("feedback_payload"),
        notes=payload.get("notes"),
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return _serialize_record(record)


async def list_lipase_curation_records(
    session: AsyncSession,
    *,
    status: str | None = None,
    source_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(LipaseCurationRecord).order_by(LipaseCurationRecord.created_at.desc(), LipaseCurationRecord.id.desc())
    if status:
        stmt = stmt.where(LipaseCurationRecord.status == normalize_review_status(status))
    if source_type:
        stmt = stmt.where(LipaseCurationRecord.source_type == normalize_source_type(source_type))
    result = await session.execute(stmt.limit(max(1, min(int(limit or 100), 500))))
    return [_serialize_record(record) for record in result.scalars().all()]


async def update_lipase_curation_review(
    session: AsyncSession,
    *,
    record_id: int,
    reviewer_user_id: int,
    status: str,
    reviewer_notes: str | None = None,
) -> dict[str, Any] | None:
    result = await session.execute(select(LipaseCurationRecord).where(LipaseCurationRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record is None:
        return None
    record.status = normalize_admin_review_status(status)
    record.reviewed_by_user_id = reviewer_user_id
    record.reviewer_notes = reviewer_notes
    record.reviewed_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(record)
    return _serialize_record(record)


async def preview_lipase_curation_batch(
    session: AsyncSession,
    *,
    record_ids: list[int] | None = None,
    source_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    records = await _select_batchable_records(session, record_ids=record_ids, source_type=source_type, limit=limit)
    return {
        "status": "planned",
        "dry_run": True,
        "manifest": _build_batch_manifest(records, source_type=source_type),
        "export_payload": _build_export_payload(records, source_type=source_type),
        "confirmation_token": LIPASE_CURATION_PUBLISH_CONFIRMATION,
    }


async def create_lipase_curation_batch(
    session: AsyncSession,
    *,
    user_id: int,
    record_ids: list[int] | None = None,
    source_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    records = await _select_batchable_records(session, record_ids=record_ids, source_type=source_type, limit=limit)
    if not records:
        raise ValueError("no accepted curation records are available for batching")

    batch_key = f"lipase-curation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    batch = LipaseCurationBatch(
        batch_key=batch_key,
        status="prepared",
        created_by_user_id=user_id,
        source_type=source_type,
        record_ids=[record.id for record in records],
        manifest=_build_batch_manifest(records, source_type=source_type),
        export_payload=_build_export_payload(records, source_type=source_type),
        confirmation_token=LIPASE_CURATION_PUBLISH_CONFIRMATION,
    )
    session.add(batch)
    for record in records:
        record.status = "batched"
    await session.flush()
    await session.refresh(batch)
    return _serialize_batch(batch)


async def list_lipase_curation_batches(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(LipaseCurationBatch).order_by(LipaseCurationBatch.created_at.desc(), LipaseCurationBatch.id.desc())
    if status:
        stmt = stmt.where(LipaseCurationBatch.status == _normalize_batch_status(status))
    result = await session.execute(stmt.limit(max(1, min(int(limit or 100), 500))))
    return [_serialize_batch(batch) for batch in result.scalars().all()]


async def publish_lipase_curation_batch(
    session: AsyncSession,
    *,
    batch_id: int,
    user_id: int,
    confirmation: str,
    reviewer_notes: str | None = None,
) -> dict[str, Any] | None:
    result = await session.execute(select(LipaseCurationBatch).where(LipaseCurationBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if batch is None:
        return None
    if batch.status != "prepared":
        raise ValueError("only prepared lipase curation batches can be published")
    if confirmation != batch.confirmation_token:
        raise ValueError(f"confirmation must be {batch.confirmation_token}")

    records_result = await session.execute(
        select(LipaseCurationRecord).where(LipaseCurationRecord.id.in_(batch.record_ids))
    )
    for record in records_result.scalars().all():
        record.status = "published"
    batch.status = "published"
    batch.published_by_user_id = user_id
    batch.reviewer_notes = reviewer_notes
    batch.published_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(batch)
    return _serialize_batch(batch)


async def _select_batchable_records(
    session: AsyncSession,
    *,
    record_ids: list[int] | None = None,
    source_type: str | None = None,
    limit: int = 100,
) -> list[LipaseCurationRecord]:
    stmt = select(LipaseCurationRecord).where(LipaseCurationRecord.status == "accepted")
    if record_ids:
        requested_ids = sorted({int(record_id) for record_id in record_ids})
        if not requested_ids:
            raise ValueError("record_ids must contain at least one record id")
        stmt = stmt.where(LipaseCurationRecord.id.in_(requested_ids))
    if source_type:
        stmt = stmt.where(LipaseCurationRecord.source_type == normalize_source_type(source_type))
    result = await session.execute(
        stmt.order_by(LipaseCurationRecord.reviewed_at.asc(), LipaseCurationRecord.id.asc()).limit(max(1, min(int(limit or 100), 500)))
    )
    records = list(result.scalars().all())
    if record_ids:
        found_ids = {record.id for record in records}
        missing_or_unaccepted = [record_id for record_id in requested_ids if record_id not in found_ids]
        if missing_or_unaccepted:
            raise ValueError(
                "record_ids must all refer to accepted curation records; "
                f"missing_or_unaccepted={missing_or_unaccepted}"
            )
    return records
