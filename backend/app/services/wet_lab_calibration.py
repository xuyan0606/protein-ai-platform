"""Wet-lab calibration summaries built from recorded experiment feedback."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy_checkpoint import WetLabCalibrationRun
from app.services.experiment_feedback import list_experiment_feedback_records, summarize_feedback_records


def _calibration_to_dict(row: WetLabCalibrationRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "project_id": row.project_id,
        "enzyme_name": row.enzyme_name,
        "objective": row.objective,
        "assay_key": row.assay_key,
        "dataset_fingerprint": row.dataset_fingerprint,
        "feedback_record_ids": row.feedback_record_ids,
        "measured_variant_count": row.measured_variant_count,
        "go_count": row.go_count,
        "watch_count": row.watch_count,
        "no_go_count": row.no_go_count,
        "hit_rate": row.hit_rate,
        "data_quality_grade": row.data_quality_grade,
        "evidence_level": row.evidence_level,
        "calibration_payload": row.calibration_payload,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _record_decision(record: dict[str, Any]) -> str:
    decision = ((record.get("interpretation_payload") or {}).get("decision") or "watch")
    return str(decision).lower()


def _assay_key(record: dict[str, Any]) -> str:
    assay = record.get("assay_payload") or {}
    parts = [
        assay.get("assay_type") or assay.get("metric") or "unspecified_assay",
        assay.get("substrate") or assay.get("substrate_name") or "unspecified_substrate",
        assay.get("ph") or assay.get("pH") or "unspecified_pH",
        assay.get("temperature_c") or assay.get("temperature") or "unspecified_temp",
    ]
    return "|".join(str(part).strip() for part in parts)


def _dataset_fingerprint(records: list[dict[str, Any]], objective: str, assay_key: str | None) -> str:
    rows = []
    for record in records:
        rows.append({
            "id": record.get("id"),
            "variant_name": record.get("variant_name"),
            "mutations": record.get("mutations"),
            "decision": _record_decision(record),
            "assay_key": _assay_key(record),
        })
    raw = json.dumps(
        {"objective": objective, "assay_key": assay_key, "records": rows},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_calibration_summary(records: list[dict[str, Any]], *, objective: str, assay_key: str | None = None) -> dict[str, Any]:
    scoped = [record for record in records if not assay_key or _assay_key(record) == assay_key]
    summary = summarize_feedback_records(scoped)
    decisions = summary.get("decision_counts") or {}
    measured_count = len(scoped)
    go_count = int(decisions.get("go") or 0)
    watch_count = int(decisions.get("watch") or 0)
    no_go_count = int(decisions.get("no_go") or 0)
    hit_rate = round(go_count / measured_count, 4) if measured_count else None

    assay_keys = sorted({_assay_key(record) for record in scoped})
    has_consistent_assay = len(assay_keys) == 1
    if measured_count >= 12 and has_consistent_assay:
        data_quality_grade = "project_calibrated"
        evidence_level = "wet_lab_calibrated"
    elif measured_count >= 3:
        data_quality_grade = "feedback_supported"
        evidence_level = "wet_lab_feedback"
    elif measured_count > 0:
        data_quality_grade = "insufficient_small_n"
        evidence_level = "computational_hypothesis_with_feedback"
    else:
        data_quality_grade = "insufficient"
        evidence_level = "computational_hypothesis"

    return {
        "objective": objective,
        "assay_key": assay_key,
        "dataset_fingerprint": _dataset_fingerprint(scoped, objective, assay_key),
        "feedback_record_ids": [int(record["id"]) for record in scoped if record.get("id") is not None],
        "measured_variant_count": measured_count,
        "go_count": go_count,
        "watch_count": watch_count,
        "no_go_count": no_go_count,
        "hit_rate": hit_rate,
        "data_quality_grade": data_quality_grade,
        "evidence_level": evidence_level,
        "assay_keys": assay_keys,
        "promotion_rule": (
            "wet_lab_calibrated requires >=12 measured variants under one comparable assay; "
            "smaller datasets remain feedback-supported or exploratory."
        ),
        "summary": summary,
    }


async def create_wet_lab_calibration_run(
    session: AsyncSession,
    *,
    user_id: int,
    project_id: str | None = None,
    enzyme_name: str | None = None,
    objective: str = "multi_objective",
    assay_key: str | None = None,
    include_all_users: bool = False,
) -> dict[str, Any]:
    records = await list_experiment_feedback_records(
        session,
        user_id=user_id,
        project_id=project_id,
        enzyme_name=enzyme_name,
        include_all_users=include_all_users,
        limit=1000,
    )
    summary = build_calibration_summary(records, objective=objective, assay_key=assay_key)
    existing_query = select(WetLabCalibrationRun).where(
        WetLabCalibrationRun.user_id == user_id,
        WetLabCalibrationRun.objective == objective,
        WetLabCalibrationRun.dataset_fingerprint == summary["dataset_fingerprint"],
    )
    if project_id is None:
        existing_query = existing_query.where(WetLabCalibrationRun.project_id.is_(None))
    else:
        existing_query = existing_query.where(WetLabCalibrationRun.project_id == project_id)
    existing = (await session.execute(existing_query)).scalar_one_or_none()
    if existing:
        return _calibration_to_dict(existing)

    row = WetLabCalibrationRun(
        user_id=user_id,
        project_id=project_id,
        enzyme_name=enzyme_name,
        objective=objective,
        assay_key=assay_key,
        dataset_fingerprint=summary["dataset_fingerprint"],
        feedback_record_ids=summary["feedback_record_ids"],
        measured_variant_count=summary["measured_variant_count"],
        go_count=summary["go_count"],
        watch_count=summary["watch_count"],
        no_go_count=summary["no_go_count"],
        hit_rate=summary["hit_rate"],
        data_quality_grade=summary["data_quality_grade"],
        evidence_level=summary["evidence_level"],
        calibration_payload=summary,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return _calibration_to_dict(row)


async def list_wet_lab_calibration_runs(
    session: AsyncSession,
    *,
    user_id: int,
    project_id: str | None = None,
    enzyme_name: str | None = None,
    objective: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = select(WetLabCalibrationRun).where(WetLabCalibrationRun.user_id == user_id)
    if project_id:
        query = query.where(WetLabCalibrationRun.project_id == project_id)
    if enzyme_name:
        query = query.where(WetLabCalibrationRun.enzyme_name == enzyme_name)
    if objective:
        query = query.where(WetLabCalibrationRun.objective == objective)
    query = query.order_by(WetLabCalibrationRun.created_at.desc()).limit(limit)
    rows = (await session.execute(query)).scalars().all()
    return [_calibration_to_dict(row) for row in rows]
