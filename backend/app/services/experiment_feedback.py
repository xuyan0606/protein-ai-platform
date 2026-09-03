"""Wet-lab feedback storage and analysis helpers."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment_feedback import ExperimentFeedbackRecord


MUTATION_RE = re.compile(r"^[A-Z][0-9]+[A-Z]$")
VALID_DECISIONS = {"go", "watch", "no_go"}
FEEDBACK_IMPORT_SCHEMA_VERSION = "experiment_feedback_import_v1"
_QC_PASSED = {"PASSED", "PASS", "ACCEPTED"}
CATALYTIC_METRICS = (
    "specific_activity_fold_vs_wt",
    "kcat_fold_vs_wt",
    "catalytic_efficiency_fold_vs_wt",
    "kcat_km_fold_vs_wt",
)
STABILITY_METRICS = ("tm_delta_c", "half_life_fold_vs_wt", "residual_activity_after_challenge_pct")
EXPRESSION_METRICS = (
    "soluble_expression_pct_wt",
    "secreted_expression_pct_wt",
    "total_protein_fold_vs_wt",
    "total_activity_fold_vs_wt",
)
KINETIC_METRICS = (
    "kcat",
    "km",
    "kcat_km",
    "kcat_per_km",
    "catalytic_efficiency",
    "kcat_fold_vs_wt",
    "kcat_km_fold_vs_wt",
    "catalytic_efficiency_fold_vs_wt",
)
PH_PROFILE_METRICS = (
    "ph_activity_curve",
    "ph_stability_curve",
    "optimal_ph",
    "activity_by_ph",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _record_to_dict(record: ExperimentFeedbackRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "created_by_user_id": record.created_by_user_id,
        "project_id": record.project_id,
        "linked_task_id": record.linked_task_id,
        "enzyme_name": record.enzyme_name,
        "variant_name": record.variant_name,
        "parent_variant": record.parent_variant,
        "mutations": record.mutations,
        "assay_payload": record.assay_payload,
        "metrics_payload": record.metrics_payload,
        "quality_payload": record.quality_payload,
        "interpretation_payload": record.interpretation_payload,
        "notes": record.notes,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def normalize_mutations(values: list[str] | None) -> list[str]:
    mutations = []
    for raw in values or []:
        code = str(raw).strip().upper()
        if not code:
            continue
        if not MUTATION_RE.match(code):
            raise ValueError(f"Invalid mutation code: {raw}")
        mutations.append(code)
    return sorted(dict.fromkeys(mutations), key=lambda item: int(re.search(r"[0-9]+", item).group(0)))


def _metric_number(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fold_improved(metrics: dict[str, Any], keys: tuple[str, ...], threshold: float = 1.15) -> bool:
    return any(
        value is not None and value >= threshold
        for value in (_metric_number(metrics, key) for key in keys)
    )


def _has_any_metric(metrics: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(_metric_number(metrics, key) is not None for key in keys)


def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _has_metric_value(metrics: dict[str, Any], keys: tuple[str, ...]) -> bool:
    for key in keys:
        value = metrics.get(key)
        if isinstance(value, (list, dict)) and value:
            return True
        if value not in (None, ""):
            return True
    return False


def _replicate_count(quality: dict[str, Any], assay: dict[str, Any]) -> int | None:
    value = _first_present(
        quality,
        ("replicate_count", "replicates", "n", "biological_replicates"),
    )
    if value is None:
        value = _first_present(assay, ("replicate_count", "replicates", "n"))
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _qc_status(quality: dict[str, Any]) -> str:
    raw = _text(_first_present(quality, ("qc_status", "qc", "quality_status"))).upper()
    if raw in _QC_PASSED:
        return "passed"
    if raw in {"FAILED", "FAIL", "REJECTED"}:
        return "failed"
    return "missing"


def _assay_condition_key(assay: dict[str, Any]) -> dict[str, Any]:
    return {
        "assay_type": _first_present(assay, ("assay_type", "assay")),
        "substrate": _first_present(assay, ("substrate", "substrate_name")),
        "ph": assay.get("ph"),
        "temperature_c": assay.get("temperature_c"),
        "buffer": assay.get("buffer"),
        "sample_type": _first_present(assay, ("sample_type", "protein_preparation")),
    }


def build_experiment_feedback_import_contract(payload: dict[str, Any]) -> dict[str, Any]:
    """Describe whether a feedback row is importable for learning or claims."""
    assay = payload.get("assay_payload") or {}
    metrics = payload.get("metrics_payload") or {}
    quality = payload.get("quality_payload") or {}
    interpretation = payload.get("interpretation_payload") or {}
    condition_key = _assay_condition_key(assay if isinstance(assay, dict) else {})
    metrics = metrics if isinstance(metrics, dict) else {}
    quality = quality if isinstance(quality, dict) else {}
    interpretation = interpretation if isinstance(interpretation, dict) else {}

    metric_groups = {
        "activity": _has_metric_value(metrics, CATALYTIC_METRICS + ("activity_retention_pct", "activity_fold_vs_wt")),
        "kinetics": _has_metric_value(metrics, KINETIC_METRICS),
        "stability": _has_metric_value(metrics, STABILITY_METRICS),
        "ph_profile": _has_metric_value(metrics, PH_PROFILE_METRICS),
        "expression": _has_metric_value(metrics, EXPRESSION_METRICS),
    }
    missing_condition_fields = [
        key
        for key in ("assay_type", "substrate", "ph", "temperature_c", "buffer", "sample_type")
        if condition_key.get(key) in (None, "")
    ]
    replicate_count = _replicate_count(quality, assay if isinstance(assay, dict) else {})
    qc_status = _qc_status(quality)
    formal_decision = _text(
        interpretation.get("formal_decision")
        or interpretation.get("decision")
        or payload.get("formal_decision")
    ).lower()
    has_formal_decision = formal_decision in VALID_DECISIONS

    missing_for_training: list[str] = []
    if qc_status != "passed":
        missing_for_training.append("qc_status_passed")
    if replicate_count is None or replicate_count < 2:
        missing_for_training.append("replicate_count_at_least_2")
    if missing_condition_fields:
        missing_for_training.append("complete_assay_condition_key")
    if not has_formal_decision:
        missing_for_training.append("formal_decision")
    if not any(metric_groups.values()):
        missing_for_training.append("measured_metric")

    stability_claim_eligible = (
        qc_status == "passed"
        and replicate_count is not None
        and replicate_count >= 2
        and metric_groups["stability"]
        and not missing_condition_fields
    )
    training_eligible = not missing_for_training

    return {
        "schema_version": FEEDBACK_IMPORT_SCHEMA_VERSION,
        "condition_key": condition_key,
        "metric_groups": metric_groups,
        "qc_status": qc_status,
        "replicate_count": replicate_count,
        "formal_decision": formal_decision if has_formal_decision else "missing",
        "training_eligible": training_eligible,
        "claim_eligibility": {
            "activity": training_eligible and metric_groups["activity"],
            "kinetics": training_eligible and metric_groups["kinetics"],
            "stability": stability_claim_eligible,
            "ph_profile": training_eligible and metric_groups["ph_profile"],
            "expression": training_eligible and metric_groups["expression"],
        },
        "missing_condition_fields": missing_condition_fields,
        "missing_for_training": missing_for_training,
        "boundary": (
            "No QC, replicate, complete assay condition, formal decision, or measured metric means "
            "the feedback can be stored for audit but must not be used for model training or upgraded claims."
        ),
    }


def _purified_enzyme_evidence(assay: dict[str, Any]) -> bool:
    """Only classify an increase as catalytic when the assay is protein-normalized."""
    sample_type = str(
        assay.get("sample_type")
        or assay.get("protein_preparation")
        or assay.get("normalization_basis")
        or ""
    ).strip().lower()
    return sample_type in {
        "purified",
        "purified_enzyme",
        "purified protein",
        "specific_activity",
        "protein_normalized",
        "kinetic_assay",
    }


def _classify_effect(
    assay: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Separate catalytic, stability-mediated, and expression-mediated gains.

    The service intentionally returns ``unresolved`` when only total activity is
    known.  A broth or lysate activity increase is not evidence for an improved
    catalytic constant.
    """
    purified = _purified_enzyme_evidence(assay)
    catalytic_measured = _has_any_metric(metrics, CATALYTIC_METRICS)
    catalytic_improved = _fold_improved(metrics, CATALYTIC_METRICS)
    stability_measured = _has_any_metric(metrics, STABILITY_METRICS)
    stability_improved = (
        (_metric_number(metrics, "tm_delta_c") or 0) >= 2
        or (_metric_number(metrics, "half_life_fold_vs_wt") or 0) >= 1.2
        or (_metric_number(metrics, "residual_activity_after_challenge_pct") or 0) >= 80
    )
    expression_measured = _has_any_metric(metrics, EXPRESSION_METRICS)
    expression_improved = _fold_improved(metrics, EXPRESSION_METRICS)
    total_activity_improved = (_metric_number(metrics, "total_activity_fold_vs_wt") or 0) >= 1.15

    if purified and catalytic_measured and catalytic_improved:
        primary = "catalytic"
        confidence = "supported"
    elif total_activity_improved and expression_improved and not catalytic_improved:
        primary = "expression_mediated"
        confidence = "supported" if expression_measured else "tentative"
    elif total_activity_improved and stability_improved and not catalytic_improved:
        primary = "stability_mediated"
        confidence = "supported" if stability_measured else "tentative"
    elif total_activity_improved and not catalytic_measured:
        primary = "unresolved_total_activity"
        confidence = "insufficient"
    else:
        primary = "unresolved"
        confidence = "insufficient"

    missing = []
    if not (purified and catalytic_measured):
        missing.append("purified_specific_activity_or_kinetics")
    if not stability_measured:
        missing.append("tm_or_process_relevant_half_life")
    if not expression_measured:
        missing.append("soluble_or_secreted_expression_measurement")

    return {
        "primary_effect": primary,
        "confidence": confidence,
        "supports_catalytic_gain": primary == "catalytic",
        "supports_stability_gain": primary == "stability_mediated" or stability_improved,
        "supports_expression_gain": primary == "expression_mediated" or expression_improved,
        "assay_is_protein_normalized": purified,
        "missing_disambiguation_measurements": missing,
    }


def analyze_feedback_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a conservative interpretation for wet-lab phenotype data."""
    assay = payload.get("assay_payload") or {}
    metrics = payload.get("metrics_payload") or {}
    quality = payload.get("quality_payload") or {}
    mutations = normalize_mutations(payload.get("mutations") or [])

    activity_retention = _metric_number(metrics, "activity_retention_pct")
    activity_fold = _metric_number(metrics, "activity_fold_vs_wt")
    tm_delta = _metric_number(metrics, "tm_delta_c")
    soluble_expression = _metric_number(metrics, "soluble_expression_pct_wt")
    sec_monomer = _metric_number(quality, "sec_monomer_pct")

    positive: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []

    if activity_retention is not None:
        if activity_retention >= 80:
            positive.append("activity_retention_ok")
        elif activity_retention < 50:
            blockers.append("activity_retention_low")
        else:
            warnings.append("activity_retention_partial")
    if activity_fold is not None and activity_fold >= 1.2:
        positive.append("activity_improved")
    if tm_delta is not None:
        if tm_delta >= 2:
            positive.append("tm_improved")
        elif tm_delta <= -2:
            warnings.append("tm_decreased")
    if soluble_expression is not None:
        if soluble_expression >= 80:
            positive.append("soluble_expression_ok")
        elif soluble_expression < 50:
            blockers.append("soluble_expression_low")
        else:
            warnings.append("soluble_expression_partial")
    if sec_monomer is not None:
        if sec_monomer >= 90:
            positive.append("sec_monomer_ok")
        elif sec_monomer < 70:
            blockers.append("aggregation_risk")
        else:
            warnings.append("sec_monomer_partial")
    if quality.get("degradation_observed") is True:
        warnings.append("degradation_observed")

    effect_classification = _classify_effect(assay, metrics)
    if effect_classification["primary_effect"] == "unresolved_total_activity":
        warnings.append("total_activity_not_specific_activity")

    if blockers:
        decision = "no_go"
    elif warnings:
        decision = "watch"
    elif positive:
        decision = "go"
    else:
        decision = "watch"
        warnings.append("insufficient_metrics")

    strategy = "collect_more_data"
    if decision == "go" and len(mutations) == 1:
        strategy = "eligible_for_combination_design"
    elif decision == "go":
        strategy = "use_as_validated_parent_or_compare_epistasis"
    elif decision == "watch":
        strategy = "repeat_or_add_missing_qc_before_combination"
    elif decision == "no_go":
        strategy = "do_not_combine_without_rescue_rationale"

    return {
        "decision": decision,
        "positive_flags": positive,
        "warning_flags": warnings,
        "blocker_flags": blockers,
        "strategy": strategy,
        "evidence_level": "wet_lab_feedback",
        "effect_classification": effect_classification,
        "required_next_measurements": [
            item
            for item, present in {
                "activity_retention_pct_or_kinetics": activity_retention is not None or activity_fold is not None,
                "tm_or_half_life": tm_delta is not None or metrics.get("half_life") is not None,
                "soluble_expression": soluble_expression is not None,
                "sec_monomer_pct": sec_monomer is not None,
            }.items()
            if not present
        ],
        "import_contract": build_experiment_feedback_import_contract(
            {
                **payload,
                "mutations": mutations,
                "interpretation_payload": {
                    **(payload.get("interpretation_payload") or {}),
                    "decision": (payload.get("interpretation_payload") or {}).get("decision") or decision,
                },
            }
        ),
    }


async def create_experiment_feedback_record(
    session: AsyncSession,
    *,
    user_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    mutations = normalize_mutations(payload.get("mutations") or [])
    variant_name = str(payload.get("variant_name") or "").strip()
    if not variant_name:
        raise ValueError("variant_name is required")
    if not mutations and variant_name.upper() != "WT":
        raise ValueError("mutations are required unless variant_name is WT")

    interpretation = analyze_feedback_payload({**payload, "mutations": mutations})
    user_interpretation = payload.get("interpretation_payload") or {}
    interpretation = {**interpretation, **user_interpretation}
    if interpretation.get("decision") not in VALID_DECISIONS:
        raise ValueError("interpretation decision must be go, watch, or no_go")

    record = ExperimentFeedbackRecord(
        created_by_user_id=user_id,
        project_id=payload.get("project_id"),
        linked_task_id=payload.get("linked_task_id"),
        enzyme_name=payload.get("enzyme_name"),
        variant_name=variant_name,
        parent_variant=payload.get("parent_variant"),
        mutations=mutations,
        assay_payload=payload.get("assay_payload"),
        metrics_payload=payload.get("metrics_payload"),
        quality_payload=payload.get("quality_payload"),
        interpretation_payload=interpretation,
        notes=payload.get("notes"),
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return _record_to_dict(record)


async def list_experiment_feedback_records(
    session: AsyncSession,
    *,
    user_id: int,
    project_id: str | None = None,
    enzyme_name: str | None = None,
    decision: str | None = None,
    include_all_users: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = select(ExperimentFeedbackRecord).order_by(ExperimentFeedbackRecord.created_at.desc()).limit(limit)
    if not include_all_users:
        query = query.where(ExperimentFeedbackRecord.created_by_user_id == user_id)
    if project_id:
        query = query.where(ExperimentFeedbackRecord.project_id == project_id)
    if enzyme_name:
        query = query.where(ExperimentFeedbackRecord.enzyme_name == enzyme_name)
    rows = (await session.execute(query)).scalars().all()
    records = [_record_to_dict(row) for row in rows]
    if decision:
        records = [
            row for row in records
            if (row.get("interpretation_payload") or {}).get("decision") == decision
        ]
    return records


def summarize_feedback_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    decisions: dict[str, int] = {"go": 0, "watch": 0, "no_go": 0}
    validated_single_mutants: list[dict[str, Any]] = []
    blockers: dict[str, int] = {}
    warnings: dict[str, int] = {}
    effect_counts: dict[str, int] = {}
    disambiguation_needed: dict[str, int] = {}

    for record in records:
        interp = record.get("interpretation_payload") or {}
        decision = interp.get("decision") or "watch"
        decisions[decision] = decisions.get(decision, 0) + 1
        if decision == "go" and len(record.get("mutations") or []) == 1:
            validated_single_mutants.append({
                "variant_name": record.get("variant_name"),
                "mutation": record["mutations"][0],
                "metrics": record.get("metrics_payload") or {},
                "quality": record.get("quality_payload") or {},
            })
        for flag in interp.get("blocker_flags") or []:
            blockers[flag] = blockers.get(flag, 0) + 1
        for flag in interp.get("warning_flags") or []:
            warnings[flag] = warnings.get(flag, 0) + 1
        effect = (interp.get("effect_classification") or {}).get("primary_effect") or "unresolved"
        effect_counts[effect] = effect_counts.get(effect, 0) + 1
        for item in (interp.get("effect_classification") or {}).get("missing_disambiguation_measurements") or []:
            disambiguation_needed[item] = disambiguation_needed.get(item, 0) + 1

    next_strategy = "collect_more_single_mutant_data"
    if len(validated_single_mutants) >= 2:
        next_strategy = "run_epistasis_check_before_combination"
    elif validated_single_mutants:
        next_strategy = "validate_one_more_orthogonal_single_mutant"

    return {
        "count": len(records),
        "decision_counts": decisions,
        "validated_single_mutants": validated_single_mutants,
        "blocker_counts": blockers,
        "warning_counts": warnings,
        "effect_classification_counts": effect_counts,
        "disambiguation_measurement_counts": disambiguation_needed,
        "next_strategy": next_strategy,
    }
