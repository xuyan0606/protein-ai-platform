"""Service functions for simple-enzyme metadata policy curation records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enzyme_metadata_curation import EnzymeMetadataCurationBatch, EnzymeMetadataCurationRecord
from app.services.enzyme_evidence_db import (
    POLICY_DECISION_CONFIRMATION_TOKEN,
    SIMPLE_ENZYME_DATABASES,
    preview_simple_enzyme_policy_decision_batch,
)

VALID_RECORD_STATUSES = {"queued", "triaged", "accepted", "rejected", "needs_more_evidence", "batched", "archived"}
ADMIN_RECORD_STATUSES = {"queued", "triaged", "accepted", "rejected", "needs_more_evidence"}
VALID_BATCH_STATUSES = {"prepared", "archived", "voided"}


def _serialize_record(record: EnzymeMetadataCurationRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "family": record.family,
        "paper_id": record.paper_id,
        "record_type": record.record_type,
        "status": record.status,
        "created_by_user_id": record.created_by_user_id,
        "reviewed_by_user_id": record.reviewed_by_user_id,
        "decision": record.decision,
        "source_identifier": record.source_identifier,
        "source_manifest_path": record.source_manifest_path,
        "decision_payload": record.decision_payload,
        "reviewer_notes": record.reviewer_notes,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
    }


def _serialize_batch(batch: EnzymeMetadataCurationBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "batch_key": batch.batch_key,
        "status": batch.status,
        "created_by_user_id": batch.created_by_user_id,
        "archived_by_user_id": batch.archived_by_user_id,
        "family": batch.family,
        "record_type": batch.record_type,
        "record_ids": batch.record_ids,
        "manifest": batch.manifest,
        "export_payload": batch.export_payload,
        "confirmation_token": batch.confirmation_token,
        "reviewer_notes": batch.reviewer_notes,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "archived_at": batch.archived_at.isoformat() if batch.archived_at else None,
    }


def _normalize_family(family: str) -> str:
    normalized = (family or "").strip()
    if normalized not in SIMPLE_ENZYME_DATABASES:
        raise ValueError(f"family must be one of: {', '.join(sorted(SIMPLE_ENZYME_DATABASES))}")
    return normalized


def _normalize_record_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized not in VALID_RECORD_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(VALID_RECORD_STATUSES))}")
    return normalized


def _normalize_admin_record_status(status: str) -> str:
    normalized = _normalize_record_status(status)
    if normalized not in ADMIN_RECORD_STATUSES:
        raise ValueError("batched/archived statuses are controlled by curation batch workflow")
    return normalized


def _normalize_batch_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized not in VALID_BATCH_STATUSES:
        raise ValueError(f"batch status must be one of: {', '.join(sorted(VALID_BATCH_STATUSES))}")
    return normalized


def _record_identity(record: dict[str, Any]) -> tuple[str, str, str]:
    family = str(record.get("family") or "").strip()
    paper_id = str(record.get("paper_id") or "").strip()
    record_type = str(record.get("record_type") or "").strip()
    if not family or not paper_id or not record_type:
        raise ValueError("policy decision records require family, paper_id, and record_type")
    return family, paper_id, record_type


def _source_identifier(record: dict[str, Any]) -> str | None:
    for key in ("source_identifier", "version_of_record_doi", "preprint_doi", "doi", "pmid"):
        value = record.get(key)
        if value:
            return str(value)
    return None


async def materialize_enzyme_metadata_policy_decisions(
    session: AsyncSession,
    *,
    family: str,
    user_id: int,
    limit: int = 100,
    dry_run: bool = True,
) -> dict[str, Any]:
    normalized_family = _normalize_family(family)
    preview = preview_simple_enzyme_policy_decision_batch(normalized_family, limit=limit)
    records = list(preview.get("export_payload", {}).get("records") or [])
    existing_result = await session.execute(
        select(
            EnzymeMetadataCurationRecord.family,
            EnzymeMetadataCurationRecord.paper_id,
            EnzymeMetadataCurationRecord.record_type,
        ).where(EnzymeMetadataCurationRecord.family == normalized_family)
    )
    existing = {tuple(row) for row in existing_result.all()}
    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for raw_record in records:
        source_record = dict(raw_record)
        record_family, paper_id, record_type = _record_identity(source_record)
        identity = (record_family, paper_id, record_type)
        if identity in existing:
            skipped.append({"family": record_family, "paper_id": paper_id, "record_type": record_type, "reason": "already_materialized"})
            continue
        planned.append(source_record)

    if not dry_run:
        for source_record in planned:
            record_family, paper_id, record_type = _record_identity(source_record)
            session.add(
                EnzymeMetadataCurationRecord(
                    family=record_family,
                    paper_id=paper_id,
                    record_type=record_type,
                    status="queued",
                    created_by_user_id=user_id,
                    decision=source_record.get("decision"),
                    source_identifier=_source_identifier(source_record),
                    source_manifest_path=source_record.get("manifest_path"),
                    decision_payload=source_record,
                )
            )
        await session.flush()

    return {
        "status": "planned" if dry_run else "materialized",
        "dry_run": dry_run,
        "family": normalized_family,
        "source": "simple_enzyme_policy_decision_sidecar",
        "read_only_source_db": True,
        "sqlite_mutated": False,
        "export_safe_released": False,
        "planned_count": len(planned),
        "skipped_count": len(skipped),
        "planned_records": planned,
        "skipped_records": skipped,
        "manifest": {
            "record_count": len(records),
            "record_types": sorted({str(record.get("record_type")) for record in records if record.get("record_type")}),
            "status_policy": "materialization writes only platform curation rows; external SQLite DBs remain read-only",
        },
    }


async def list_enzyme_metadata_curation_records(
    session: AsyncSession,
    *,
    family: str | None = None,
    status: str | None = None,
    record_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(EnzymeMetadataCurationRecord).order_by(
        EnzymeMetadataCurationRecord.created_at.desc(),
        EnzymeMetadataCurationRecord.id.desc(),
    )
    if family:
        stmt = stmt.where(EnzymeMetadataCurationRecord.family == _normalize_family(family))
    if status:
        stmt = stmt.where(EnzymeMetadataCurationRecord.status == _normalize_record_status(status))
    if record_type:
        stmt = stmt.where(EnzymeMetadataCurationRecord.record_type == record_type.strip())
    result = await session.execute(stmt.limit(max(1, min(int(limit or 100), 500))))
    return [_serialize_record(record) for record in result.scalars().all()]


async def update_enzyme_metadata_curation_review(
    session: AsyncSession,
    *,
    record_id: int,
    reviewer_user_id: int,
    status: str,
    reviewer_notes: str | None = None,
) -> dict[str, Any] | None:
    result = await session.execute(
        select(EnzymeMetadataCurationRecord).where(EnzymeMetadataCurationRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    record.status = _normalize_admin_record_status(status)
    record.reviewed_by_user_id = reviewer_user_id
    record.reviewer_notes = reviewer_notes
    record.reviewed_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(record)
    return _serialize_record(record)


def _build_batch_manifest(
    records: list[EnzymeMetadataCurationRecord],
    *,
    family: str | None = None,
    record_type: str | None = None,
) -> dict[str, Any]:
    families = sorted({record.family for record in records})
    record_types = sorted({record.record_type for record in records})
    paper_ids = sorted({record.paper_id for record in records})
    return {
        "record_count": len(records),
        "family": family,
        "record_type": record_type,
        "families": families,
        "record_types": record_types,
        "paper_ids": paper_ids,
        "status_policy": (
            "accepted metadata decisions are archived for manual upgrade planning; archive does not mutate external SQLite"
        ),
    }


def _single_value(values: set[str]) -> str | None:
    return next(iter(values)) if len(values) == 1 else None


def _build_export_payload(
    records: list[EnzymeMetadataCurationRecord],
    *,
    family: str | None = None,
    record_type: str | None = None,
) -> dict[str, Any]:
    serialized = [_serialize_record(record) for record in records]
    return {
        "source": "protein_ai_platform_enzyme_metadata_curation_queue",
        "target": "manual_family_specific_metadata_upgrade_script",
        "family": family,
        "record_type": record_type,
        "read_only_source_db": True,
        "sqlite_mutated": False,
        "export_safe_released": False,
        "record_count": len(serialized),
        "records": serialized,
        "required_manual_steps": [
            "review accepted records against live DOI/PubMed/Crossref/Europe PMC evidence",
            "prepare a family-specific SQLite upgrade script only for strongly confirmed citation identities",
            "run dry-run -> backup -> apply -> PRAGMA integrity_check before any external SQLite mutation",
            "keep patent/preprint/boundary rows out of export-safe until a separate release decision is recorded",
        ],
    }


async def _select_batchable_records(
    session: AsyncSession,
    *,
    record_ids: list[int] | None = None,
    family: str | None = None,
    record_type: str | None = None,
    limit: int = 100,
) -> list[EnzymeMetadataCurationRecord]:
    stmt = select(EnzymeMetadataCurationRecord).where(EnzymeMetadataCurationRecord.status == "accepted")
    if record_ids:
        requested_ids = sorted({int(record_id) for record_id in record_ids})
        if not requested_ids:
            raise ValueError("record_ids must contain at least one record id")
        stmt = stmt.where(EnzymeMetadataCurationRecord.id.in_(requested_ids))
    if family:
        stmt = stmt.where(EnzymeMetadataCurationRecord.family == _normalize_family(family))
    if record_type:
        stmt = stmt.where(EnzymeMetadataCurationRecord.record_type == record_type.strip())
    result = await session.execute(
        stmt.order_by(EnzymeMetadataCurationRecord.reviewed_at.asc(), EnzymeMetadataCurationRecord.id.asc()).limit(
            max(1, min(int(limit or 100), 500))
        )
    )
    records = list(result.scalars().all())
    if record_ids:
        found_ids = {record.id for record in records}
        missing_or_unaccepted = [record_id for record_id in requested_ids if record_id not in found_ids]
        if missing_or_unaccepted:
            raise ValueError(
                "record_ids must all refer to accepted metadata curation records; "
                f"missing_or_unaccepted={missing_or_unaccepted}"
            )
    return records


async def preview_enzyme_metadata_curation_batch(
    session: AsyncSession,
    *,
    record_ids: list[int] | None = None,
    family: str | None = None,
    record_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    records = await _select_batchable_records(session, record_ids=record_ids, family=family, record_type=record_type, limit=limit)
    batch_family = family or _single_value({record.family for record in records})
    batch_record_type = record_type or _single_value({record.record_type for record in records})
    return {
        "status": "planned",
        "dry_run": True,
        "manifest": _build_batch_manifest(records, family=batch_family, record_type=batch_record_type),
        "export_payload": _build_export_payload(records, family=batch_family, record_type=batch_record_type),
        "confirmation_token": POLICY_DECISION_CONFIRMATION_TOKEN,
    }


async def create_enzyme_metadata_curation_batch(
    session: AsyncSession,
    *,
    user_id: int,
    record_ids: list[int] | None = None,
    family: str | None = None,
    record_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    records = await _select_batchable_records(session, record_ids=record_ids, family=family, record_type=record_type, limit=limit)
    if not records:
        raise ValueError("no accepted metadata curation records are available for batching")

    batch_family = family or _single_value({record.family for record in records})
    batch_record_type = record_type or _single_value({record.record_type for record in records})
    batch_key = f"enzyme-metadata-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    batch = EnzymeMetadataCurationBatch(
        batch_key=batch_key,
        status="prepared",
        created_by_user_id=user_id,
        family=batch_family,
        record_type=batch_record_type,
        record_ids=[record.id for record in records],
        manifest=_build_batch_manifest(records, family=batch_family, record_type=batch_record_type),
        export_payload=_build_export_payload(records, family=batch_family, record_type=batch_record_type),
        confirmation_token=POLICY_DECISION_CONFIRMATION_TOKEN,
    )
    session.add(batch)
    for record in records:
        record.status = "batched"
    await session.flush()
    await session.refresh(batch)
    return _serialize_batch(batch)


async def list_enzyme_metadata_curation_batches(
    session: AsyncSession,
    *,
    status: str | None = None,
    family: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(EnzymeMetadataCurationBatch).order_by(
        EnzymeMetadataCurationBatch.created_at.desc(),
        EnzymeMetadataCurationBatch.id.desc(),
    )
    if status:
        stmt = stmt.where(EnzymeMetadataCurationBatch.status == _normalize_batch_status(status))
    if family:
        stmt = stmt.where(EnzymeMetadataCurationBatch.family == _normalize_family(family))
    result = await session.execute(stmt.limit(max(1, min(int(limit or 100), 500))))
    return [_serialize_batch(batch) for batch in result.scalars().all()]


async def archive_enzyme_metadata_curation_batch(
    session: AsyncSession,
    *,
    batch_id: int,
    user_id: int,
    confirmation: str,
    reviewer_notes: str | None = None,
) -> dict[str, Any] | None:
    result = await session.execute(select(EnzymeMetadataCurationBatch).where(EnzymeMetadataCurationBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if batch is None:
        return None
    if batch.status != "prepared":
        raise ValueError("only prepared metadata curation batches can be archived")
    if confirmation != batch.confirmation_token:
        raise ValueError(f"confirmation must be {batch.confirmation_token}")

    records_result = await session.execute(
        select(EnzymeMetadataCurationRecord).where(EnzymeMetadataCurationRecord.id.in_(batch.record_ids))
    )
    for record in records_result.scalars().all():
        record.status = "archived"
    batch.status = "archived"
    batch.archived_by_user_id = user_id
    batch.reviewer_notes = reviewer_notes
    batch.archived_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(batch)
    return _serialize_batch(batch)
