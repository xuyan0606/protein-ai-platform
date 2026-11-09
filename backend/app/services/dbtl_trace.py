"""Read-only DBTL trace aggregation for project workspaces."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment_feedback import ExperimentFeedbackRecord
from app.models.strategy_checkpoint import StrategyCheckpoint, WetLabCalibrationRun
from app.services.experiment_feedback import build_experiment_feedback_import_contract
from app.tools.feedback_iteration_planner import feedback_iteration_planner


TRACE_SCHEMA_VERSION = "dbtl_trace_v1"
PROJECT_MODEL_SCHEMA_VERSION = "dbtl_project_model_v1"
LEARNING_READINESS_SCHEMA_VERSION = "dbtl_learning_readiness_v1"
TRACE_SUMMARY_SCHEMA_VERSION = "dbtl_trace_summary_v1"
UNKNOWN = "unknown"

_ROUND_KEYS = {"round_key", "round", "round_id"}
_VARIANT_KEYS = {"variant_key", "variant_name", "variant"}
_PREDICTION_KEYS = {"prediction", "prediction_payload", "prediction_result"}
_DECISION_KEYS = {"decision", "final_decision"}
_FORMAL_DECISION_KEYS = {"formal_decision", "formal_decision_payload"}
_WT_STATUS_KEYS = {"wt_baseline_status", "baseline_status"}


def _is_json_container(value: Any) -> bool:
    return isinstance(value, (dict, list))


def _walk_values(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).strip().lower(), child
            yield from _walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child)


def _first_explicit(payloads: Iterable[Any], keys: set[str]) -> Any:
    for payload in payloads:
        if not _is_json_container(payload):
            continue
        for key, value in _walk_values(payload):
            if key in keys and value not in (None, ""):
                return value
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _key_or_unknown(value: Any) -> str:
    text = _text(value)
    return text if text else UNKNOWN


def _metadata(
    payloads: Iterable[Any],
) -> dict[str, Any]:
    payload_list = list(payloads)
    return {
        "round_key": _key_or_unknown(_first_explicit(payload_list, _ROUND_KEYS)),
        "variant_key": _key_or_unknown(_first_explicit(payload_list, _VARIANT_KEYS)),
        "prediction": _first_explicit(payload_list, _PREDICTION_KEYS),
        "decision": _first_explicit(payload_list, _DECISION_KEYS),
        "formal_decision": _first_explicit(payload_list, _FORMAL_DECISION_KEYS),
        "wt_baseline_status": _first_explicit(payload_list, _WT_STATUS_KEYS),
    }


def _round_matches(value: str, requested: str | None) -> bool:
    return requested is None or value == requested


def _normalise_status(value: Any) -> str:
    text = _text(value).lower().replace("-", "_").replace(" ", "_")
    if text in {"ready", "supported", "pass", "passed"}:
        return "ready"
    if text in {"missing", "blocked", "unavailable"}:
        return "missing"
    if text in {"conflict", "conflicting"}:
        return "conflict"
    return UNKNOWN


def _append_unique(values: list[Any], value: Any) -> None:
    if value not in values:
        values.append(value)


def _is_wild_type_record(record: ExperimentFeedbackRecord) -> bool:
    """Only explicit WT rows without mutations can establish WT linkage."""
    variant_name = _text(record.variant_name).upper()
    return variant_name in {"WT", "WILD-TYPE", "WILD TYPE", "WILDTYPE"} and not record.mutations


def _merge_decisions(values: list[str]) -> str:
    distinct = [value for value in OrderedDict.fromkeys(values) if value != UNKNOWN]
    if len(distinct) == 1:
        return distinct[0]
    return UNKNOWN


def _new_variant(variant_key: str) -> dict[str, Any]:
    return {
        "variant_key": variant_key,
        "parent_variant": UNKNOWN,
        "prediction": {},
        "decision": UNKNOWN,
        "feedback_record_ids": [],
        "checkpoint_ids": [],
        "calibration_run_ids": [],
        "_decisions": [],
        "_prediction_values": [],
    }


def _merge_prediction(variant: dict[str, Any], prediction: Any) -> None:
    if prediction in (None, ""):
        return
    _append_unique(variant["_prediction_values"], prediction)
    if not variant["prediction"]:
        variant["prediction"] = dict(prediction) if isinstance(prediction, dict) else {"value": prediction}
    elif isinstance(variant["prediction"], dict) and isinstance(prediction, dict):
        for key, value in prediction.items():
            variant["prediction"].setdefault(key, value)


def _finalize_variant(variant: dict[str, Any]) -> dict[str, Any]:
    decisions = [value for value in variant.pop("_decisions") if value]
    variant["decision"] = _merge_decisions(decisions) if decisions else UNKNOWN
    prediction_values = variant.pop("_prediction_values")
    if len(prediction_values) > 1:
        variant["predictions"] = prediction_values
    return variant


def _formal_decision_entry(
    value: Any,
    *,
    source_type: str,
    source_id: int,
    decided_by_user_id: int | None = None,
) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        entry = dict(value)
        decision = entry.get("decision") or entry.get("final_decision") or UNKNOWN
    else:
        entry = {"decision": value}
        decision = value
    entry["decision"] = _key_or_unknown(decision)
    entry["source_type"] = source_type
    entry["source_id"] = source_id
    if decided_by_user_id is not None:
        entry.setdefault("decided_by_user_id", decided_by_user_id)
    return entry


def _build_formal_decision(entries: list[dict[str, Any]]) -> dict[str, Any]:
    if not entries:
        return {
            "decision": UNKNOWN,
            "basis": [],
            "source_ids": [],
            "status": UNKNOWN,
        }

    decisions = [entry["decision"] for entry in entries]
    decision = _merge_decisions(decisions)
    first = dict(entries[0])
    first["decision"] = decision
    first["source_ids"] = [entry["source_id"] for entry in entries]
    first["basis"] = first.get("basis") if isinstance(first.get("basis"), list) else []
    first["status"] = "explicit" if decision != UNKNOWN else "conflict"
    first.pop("source_type", None)
    first.pop("source_id", None)
    return first


def _build_project_model_contract(
    *,
    project_id: str,
    discovered_rounds: list[str],
    wt_baseline_status: str,
    wt_feedback_ids: list[int],
    variants: list[dict[str, Any]],
    calibration_summaries: list[dict[str, Any]],
    formal_decision: dict[str, Any],
) -> dict[str, Any]:
    feedback_ids: list[int] = []
    prediction_count = 0
    decision_count = 0
    for variant in variants:
        for record_id in variant.get("feedback_record_ids", []):
            _append_unique(feedback_ids, record_id)
        if variant.get("prediction"):
            prediction_count += 1
        if variant.get("decision") not in {None, "", UNKNOWN}:
            decision_count += 1

    missing_entities: list[str] = []
    if not discovered_rounds:
        missing_entities.append("round")
    if wt_baseline_status != "ready":
        missing_entities.append("ready_wt_baseline")
    if not variants:
        missing_entities.append("variant")
    if prediction_count == 0:
        missing_entities.append("prediction")
    if not feedback_ids:
        missing_entities.append("experiment_feedback")
    if formal_decision.get("decision") in {None, "", UNKNOWN}:
        missing_entities.append("formal_decision")

    return {
        "schema_version": PROJECT_MODEL_SCHEMA_VERSION,
        "project_id": project_id,
        "status": "partial" if variants or discovered_rounds or feedback_ids else "empty",
        "read_only": True,
        "entities": {
            "project": {"status": "observed", "project_id": project_id},
            "rounds": [
                {"round_key": round_item, "status": "observed"}
                for round_item in discovered_rounds
            ],
            "wt_baseline": {
                "status": wt_baseline_status,
                "feedback_record_ids": wt_feedback_ids,
                "calibration_run_count": len(calibration_summaries),
            },
            "variants": [
                {
                    "variant_key": variant.get("variant_key") or UNKNOWN,
                    "parent_variant": variant.get("parent_variant") or UNKNOWN,
                    "feedback_record_ids": variant.get("feedback_record_ids", []),
                    "checkpoint_ids": variant.get("checkpoint_ids", []),
                    "calibration_run_ids": variant.get("calibration_run_ids", []),
                    "has_prediction": bool(variant.get("prediction")),
                    "decision": variant.get("decision") or UNKNOWN,
                }
                for variant in variants
            ],
            "predictions": {
                "count": prediction_count,
                "source": "strategy_checkpoints",
            },
            "experiment_feedback": {
                "count": len(feedback_ids),
                "record_ids": feedback_ids,
            },
            "formal_decision": {
                "decision": formal_decision.get("decision") or UNKNOWN,
                "status": formal_decision.get("status") or UNKNOWN,
                "source_ids": formal_decision.get("source_ids", []),
            },
        },
        "counts": {
            "rounds": len(discovered_rounds),
            "variants": len(variants),
            "predictions": prediction_count,
            "variant_decisions": decision_count,
            "feedback_records": len(feedback_ids),
            "calibration_runs": len(calibration_summaries),
        },
        "missing_entities": missing_entities,
        "boundary": (
            "This is a read-only DBTL trace contract over existing records. "
            "It does not create Project/Round/Variant/Prediction tables, infer missing decisions, "
            "or promote chat context to formal experiment memory."
        ),
    }


def _feedback_payload(record: ExperimentFeedbackRecord) -> dict[str, Any]:
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
    }


def _build_learning_readiness(records: list[ExperimentFeedbackRecord]) -> dict[str, Any]:
    contracts: list[dict[str, Any]] = []
    missing_counts: dict[str, int] = {}
    claim_counts: dict[str, int] = {}
    for record in records:
        contract = build_experiment_feedback_import_contract(_feedback_payload(record))
        contracts.append({"record_id": record.id, **contract})
        for reason in contract.get("missing_for_training", []):
            missing_counts[reason] = missing_counts.get(reason, 0) + 1
        claim_eligibility = contract.get("claim_eligibility")
        if isinstance(claim_eligibility, dict):
            for claim, eligible in claim_eligibility.items():
                if eligible:
                    claim_counts[str(claim)] = claim_counts.get(str(claim), 0) + 1

    training_eligible_ids = [
        item["record_id"]
        for item in contracts
        if item.get("training_eligible") is True
    ]
    status = (
        "ready"
        if len(training_eligible_ids) >= 12
        else "feedback_present_not_training_ready"
        if records
        else "missing_feedback"
    )
    return {
        "schema_version": LEARNING_READINESS_SCHEMA_VERSION,
        "status": status,
        "record_count": len(records),
        "training_eligible_count": len(training_eligible_ids),
        "training_eligible_record_ids": training_eligible_ids,
        "claim_eligible_counts": claim_counts,
        "missing_for_training_counts": missing_counts,
        "record_contracts": contracts,
        "promotion_rule": "Project learning readiness requires >=12 training-eligible feedback records under compatible objective/assay scope.",
        "boundary": (
            "Feedback records remain auditable even when not training-eligible. "
            "This summary does not train a model or upgrade candidate claims."
        ),
    }


def _top_counts(counts: dict[str, int], *, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
    ]


_ACTION_META = {
    "create_or_select_round": ("data_entry", "P1"),
    "record_qc_passed_wt_baseline": ("assay_qc", "P0"),
    "import_experiment_feedback": ("data_entry", "P0"),
    "record_formal_decision": ("formal_decision", "P1"),
    "complete_feedback_import_contract": ("assay_qc", "P0"),
    "validate_single_mutants_before_combination": ("combination_gate", "P0"),
}


def _required_action(action: str, *, reason: str, blocks: list[str], **extra: Any) -> dict[str, Any]:
    category, priority = _ACTION_META.get(action, ("general", "P2"))
    return {
        "action": action,
        "category": category,
        "priority": priority,
        "reason": reason,
        "blocks": blocks,
        **extra,
    }


def _required_action_contract(actions: list[dict[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for action in actions:
        category = str(action.get("category") or "general")
        priority = str(action.get("priority") or "P2")
        by_category[category] = by_category.get(category, 0) + 1
        by_priority[priority] = by_priority.get(priority, 0) + 1
    return {
        "schema_version": "dbtl_required_action_contract_v1",
        "status": "action_required" if actions else "no_action_required",
        "action_count": len(actions),
        "by_category": dict(sorted(by_category.items())),
        "by_priority": dict(sorted(by_priority.items())),
        "allowed_categories": [
            "assay_qc",
            "combination_gate",
            "data_entry",
            "formal_decision",
            "general",
        ],
        "allowed_priorities": ["P0", "P1", "P2"],
        "read_only": True,
        "boundary": (
            "Required actions are machine-readable follow-up categories for operators and agents. "
            "They do not create records, execute assays, train models, or approve candidate promotion."
        ),
    }


def _project_memory_readiness(project_model: dict[str, Any]) -> dict[str, Any]:
    counts = project_model.get("counts") if isinstance(project_model.get("counts"), dict) else {}
    missing_entities = set(project_model.get("missing_entities") or [])
    entity_status = {
        "round": {
            "status": "missing" if "round" in missing_entities else "ready",
            "count": counts.get("rounds", 0),
        },
        "ready_wt_baseline": {
            "status": "missing" if "ready_wt_baseline" in missing_entities else "ready",
            "count": len(((project_model.get("entities") or {}).get("wt_baseline") or {}).get("feedback_record_ids", [])),
        },
        "variant": {
            "status": "missing" if "variant" in missing_entities else "ready",
            "count": counts.get("variants", 0),
        },
        "prediction": {
            "status": "missing" if "prediction" in missing_entities else "ready",
            "count": counts.get("predictions", 0),
        },
        "experiment_feedback": {
            "status": "missing" if "experiment_feedback" in missing_entities else "ready",
            "count": counts.get("feedback_records", 0),
        },
        "formal_decision": {
            "status": "missing" if "formal_decision" in missing_entities else "ready",
            "count": 0 if "formal_decision" in missing_entities else 1,
        },
    }
    missing = [
        name for name, value in entity_status.items()
        if value["status"] != "ready"
    ]
    ready_count = len(entity_status) - len(missing)
    if ready_count == len(entity_status):
        status = "ready"
    elif ready_count > 0:
        status = "partial"
    else:
        status = "empty"
    return {
        "schema_version": "dbtl_project_memory_readiness_v1",
        "status": status,
        "read_only": True,
        "entity_status": entity_status,
        "ready_entity_count": ready_count,
        "missing_entity_count": len(missing),
        "missing_entities": missing,
        "readiness_fraction": round(ready_count / len(entity_status), 3),
        "source_contract": project_model.get("schema_version") or PROJECT_MODEL_SCHEMA_VERSION,
        "required_entities": list(entity_status.keys()),
        "must_not_claim": [
            "formal_dbtl_tables_exist",
            "project_memory_rows_created",
            "trace_has_trained_model",
            "missing_entities_inferred_as_ready",
        ],
        "boundary": (
            "Project memory readiness is a read-only rollup over the DBTL project model contract. "
            "It does not create formal Project/Round/Variant/Prediction tables, infer missing entities, "
            "or train a model."
        ),
    }


def _feedback_readiness_summary(learning_readiness: dict[str, Any]) -> dict[str, Any]:
    record_contracts = learning_readiness.get("record_contracts")
    if not isinstance(record_contracts, list):
        record_contracts = []

    qc_status_counts: dict[str, int] = {}
    formal_decision_counts: dict[str, int] = {}
    assay_condition_counts = {"complete": 0, "missing": 0}
    replicate_counts = {"ready": 0, "missing_or_insufficient": 0}
    measured_metric_counts = {"present": 0, "missing": 0}

    for contract in record_contracts:
        if not isinstance(contract, dict):
            continue
        qc_status = str(contract.get("qc_status") or UNKNOWN)
        qc_status_counts[qc_status] = qc_status_counts.get(qc_status, 0) + 1

        formal_decision = str(contract.get("formal_decision") or "missing")
        formal_decision_counts[formal_decision] = formal_decision_counts.get(formal_decision, 0) + 1

        missing_condition_fields = contract.get("missing_condition_fields")
        if isinstance(missing_condition_fields, list) and not missing_condition_fields:
            assay_condition_counts["complete"] += 1
        else:
            assay_condition_counts["missing"] += 1

        replicate_count = contract.get("replicate_count")
        if isinstance(replicate_count, int | float) and replicate_count >= 2:
            replicate_counts["ready"] += 1
        else:
            replicate_counts["missing_or_insufficient"] += 1

        metric_groups = contract.get("metric_groups")
        has_metric = any(metric_groups.values()) if isinstance(metric_groups, dict) else False
        measured_metric_counts["present" if has_metric else "missing"] += 1

    record_count = int(learning_readiness.get("record_count") or 0)
    training_eligible_count = int(learning_readiness.get("training_eligible_count") or 0)
    claim_eligible_counts = learning_readiness.get("claim_eligible_counts")
    if not isinstance(claim_eligible_counts, dict):
        claim_eligible_counts = {}
    missing_for_training_counts = learning_readiness.get("missing_for_training_counts")
    if not isinstance(missing_for_training_counts, dict):
        missing_for_training_counts = {}

    if record_count <= 0:
        status = "missing_feedback"
    elif training_eligible_count >= 12:
        status = "ready_for_learning_review"
    elif training_eligible_count > 0:
        status = "partial_training_batch"
    else:
        status = "feedback_present_not_training_ready"

    return {
        "schema_version": "dbtl_feedback_readiness_summary_v1",
        "status": status,
        "read_only": True,
        "source_contract": learning_readiness.get("schema_version") or LEARNING_READINESS_SCHEMA_VERSION,
        "record_count": record_count,
        "training_eligible_count": training_eligible_count,
        "training_batch_minimum": 12,
        "top_missing_for_training": _top_counts(missing_for_training_counts),
        "missing_for_training_counts": dict(sorted(missing_for_training_counts.items())),
        "claim_eligible_counts": dict(sorted(claim_eligible_counts.items())),
        "assay_qc_summary": {
            "qc_status_counts": dict(sorted(qc_status_counts.items())),
            "formal_decision_counts": dict(sorted(formal_decision_counts.items())),
            "assay_condition_counts": assay_condition_counts,
            "replicate_counts": replicate_counts,
            "measured_metric_counts": measured_metric_counts,
        },
        "next_round_constraint_status": (
            "feedback_ready_for_learning_review"
            if training_eligible_count >= 12
            else "blocked_by_feedback_import_contract"
        ),
        "must_not_claim": [
            "model_trained",
            "wet_lab_validated_by_trace_summary",
            "claims_promoted_without_qc_replicates_conditions_and_formal_decision",
            "next_round_design_approved_by_feedback_summary",
        ],
        "boundary": (
            "Feedback readiness is a read-only rollup of existing feedback import contracts. "
            "It does not import records, train models, upgrade wet-lab claims, or approve next-round designs."
        ),
    }


def _readiness_bridge(
    *,
    project_model: dict[str, Any],
    learning_readiness: dict[str, Any],
    next_round_library_design: dict[str, Any],
) -> dict[str, Any]:
    project_memory_readiness = _project_memory_readiness(project_model)
    feedback_readiness = _feedback_readiness_summary(learning_readiness)
    combination_contract = next_round_library_design.get("combination_evidence_contract")
    if not isinstance(combination_contract, dict):
        combination_contract = {}
    return {
        "schema_version": "dbtl_readiness_bridge_v1",
        "status": (
            "ready"
            if project_memory_readiness.get("status") == "ready"
            and feedback_readiness.get("status") == "ready_for_learning_review"
            and combination_contract.get("status") in {"ready", "ready_for_pair_test"}
            else "partial"
        ),
        "read_only": True,
        "project_memory_readiness_status": project_memory_readiness.get("status") or UNKNOWN,
        "feedback_readiness_status": feedback_readiness.get("status") or UNKNOWN,
        "next_round_constraint_status": feedback_readiness.get("next_round_constraint_status") or UNKNOWN,
        "combination_evidence_status": combination_contract.get("status") or UNKNOWN,
        "downstream_status_views": [
            "project_memory_readiness",
            "feedback_readiness",
            "next_round_constraints",
        ],
        "required_actions": [
            action for action in (
                "create_or_select_round" if project_memory_readiness.get("status") != "ready" else None,
                "complete_feedback_import_contract" if feedback_readiness.get("status") != "ready_for_learning_review" else None,
                "validate_single_mutants_before_combination" if combination_contract.get("status") not in {"ready", "ready_for_pair_test"} else None,
            )
            if action
        ],
        "must_not_claim": [
            "formal_dbtl_tables_exist",
            "learning_ready_without_feedback_readiness",
            "next_round_design_ready_without_singleton_and_structure_evidence",
        ],
        "boundary": (
            "The readiness bridge is a read-only SOP/status view contract that exposes project memory, "
            "feedback readiness, and next-round constraints together. It does not create DBTL tables, "
            "approve learning, or upgrade wet-lab claims."
        ),
    }


def _p4_active_learning_batch_contract(learning_readiness: dict[str, Any]) -> dict[str, Any]:
    training_eligible_ids = learning_readiness.get("training_eligible_record_ids")
    if not isinstance(training_eligible_ids, list):
        training_eligible_ids = []
    training_eligible_count = int(learning_readiness.get("training_eligible_count") or 0)
    status = (
        "ready_for_operator_review"
        if training_eligible_count >= 12
        else "blocked_insufficient_training_feedback"
    )
    return {
        "schema_version": "p4_active_learning_batch_contract_v1",
        "status": status,
        "read_only": True,
        "batch_policy": {
            "minimum_training_eligible_records": 12,
            "requires_compatible_objective_assay_scope": True,
            "requires_dataset_fingerprint": True,
            "requires_human_review_before_execution": True,
        },
        "observed": {
            "training_eligible_count": training_eligible_count,
            "training_eligible_record_ids": training_eligible_ids,
            "learning_status": learning_readiness.get("status") or UNKNOWN,
        },
        "blocked_reasons": []
        if training_eligible_count >= 12
        else ["training_eligible_feedback_records_below_minimum"],
        "must_not_claim": [
            "active_learning_batch_executed",
            "model_training_started",
            "candidate_policy_updated",
        ],
        "boundary": (
            "This contract only checks whether a future active-learning batch could be reviewed. "
            "It does not create datasets, train models, update ranking policy, or schedule experiments."
        ),
    }


def _p4_operator_review_contract(
    *,
    formal_decision: dict[str, Any],
    p4_readiness: dict[str, Any],
) -> dict[str, Any]:
    live_gate_status = (p4_readiness.get("gates") or {}).get("live_gate_approval", {})
    review_status = "recorded" if formal_decision.get("status") == "explicit" else "not_recorded"
    status = "blocked_missing_operator_review" if review_status != "recorded" or live_gate_status.get("status") != "ready" else "ready"
    return {
        "schema_version": "p4_operator_review_contract_v1",
        "status": status,
        "read_only": True,
        "observed": {
            "formal_decision_status": formal_decision.get("status") or UNKNOWN,
            "formal_decision": formal_decision.get("decision") or UNKNOWN,
            "live_gate_status": live_gate_status.get("status") or UNKNOWN,
        },
        "required_review_fields": [
            "operator_user_id",
            "review_timestamp",
            "maintenance_window",
            "gate_scope",
            "decision",
            "basis",
        ],
        "blocked_reasons": [] if status == "ready" else ["operator_review_not_recorded", "live_gate_approval_not_ready"],
        "must_not_claim": [
            "live_gate_approved",
            "operator_review_recorded_when_missing",
            "production_loop_running",
        ],
        "boundary": (
            "The operator review contract exposes the approval boundary for live gates. "
            "It does not approve the gate, schedule runtime actions, or mutate project records."
        ),
    }


def _p4_model_calibration_registry_contract(project_model: dict[str, Any]) -> dict[str, Any]:
    counts = project_model.get("counts") if isinstance(project_model.get("counts"), dict) else {}
    calibration_runs = int(counts.get("calibration_runs") or 0)
    status = "ready_read_only_registry" if calibration_runs > 0 else "missing_calibration_run"
    return {
        "schema_version": "p4_model_calibration_registry_contract_v1",
        "status": status,
        "read_only": True,
        "required_registry_fields": [
            "calibration_run_id",
            "objective",
            "assay_key",
            "dataset_fingerprint",
            "measured_variant_count",
            "data_quality_grade",
            "evidence_level",
        ],
        "observed": {
            "calibration_runs": calibration_runs,
            "project_model_status": project_model.get("status") or UNKNOWN,
        },
        "blocked_reasons": [] if calibration_runs > 0 else ["no_calibration_run_observed"],
        "must_not_claim": [
            "model_calibrated_for_production",
            "model_retrained",
            "calibration_registry_approves_candidate_claims",
        ],
        "boundary": (
            "The calibration registry contract describes traceability for observed calibration summaries. "
            "It does not retrain, recalibrate, approve production use, or promote wet-lab claims."
        ),
    }


def _p4_manufacturing_constraint_contract(next_round_library_design: dict[str, Any]) -> dict[str, Any]:
    manufacturing_constraints = next_round_library_design.get("manufacturing_constraints")
    if not isinstance(manufacturing_constraints, dict):
        manufacturing_constraints = {}
    observed_status = manufacturing_constraints.get("status") or UNKNOWN
    status = "ready_for_operator_review" if observed_status == "ready" else "blocked_missing_process_constraints"
    return {
        "schema_version": "p4_manufacturing_constraint_schema_v1",
        "status": status,
        "read_only": True,
        "required_constraint_fields": [
            "expression_host",
            "secretion_or_solubility_constraint",
            "process_temperature_range",
            "process_ph_range",
            "substrate_or_feedstock_scope",
            "scale_up_owner_review",
            "manufacturing_assay_scope",
        ],
        "observed": {
            "manufacturing_constraints_status": observed_status,
            "available_fields": sorted(manufacturing_constraints.keys()),
        },
        "blocked_reasons": [] if observed_status == "ready" else ["manufacturing_constraints_not_ready"],
        "must_not_claim": [
            "manufacturing_constraints_validated",
            "scale_up_ready",
            "process_window_verified",
        ],
        "boundary": (
            "The manufacturing constraint schema is a readiness checklist for process-owner review. "
            "It does not validate manufacturing constraints, approve scale-up, or change candidate ranking."
        ),
    }


def _p4_closed_loop_readiness(
    *,
    project_model: dict[str, Any],
    learning_readiness: dict[str, Any],
    next_round_library_design: dict[str, Any],
    formal_decision: dict[str, Any],
    required_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    training_eligible_count = int(learning_readiness.get("training_eligible_count") or 0)
    combination_contract = next_round_library_design.get("combination_evidence_contract")
    if not isinstance(combination_contract, dict):
        combination_contract = {}
    manufacturing_constraints = next_round_library_design.get("manufacturing_constraints")
    if not isinstance(manufacturing_constraints, dict):
        manufacturing_constraints = {}

    gates = {
        "active_learning_batch": {
            "status": "ready" if training_eligible_count >= 12 else "blocked",
            "requires": ["training_eligible_feedback_records>=12", "compatible_objective_assay_scope"],
            "observed": {"training_eligible_feedback_records": training_eligible_count},
        },
        "model_calibration_registry": {
            "status": "ready" if (project_model.get("counts") or {}).get("calibration_runs", 0) > 0 else "blocked",
            "requires": ["calibration_run", "dataset_fingerprint", "quality_grade"],
            "observed": {"calibration_runs": (project_model.get("counts") or {}).get("calibration_runs", 0)},
        },
        "combination_evidence_gate": {
            "status": (
                "ready"
                if combination_contract.get("status") in {"ready", "ready_for_pair_test"}
                else "blocked"
            ),
            "requires": ["validated_singletons", "pair_or_structure_evidence", "higher_order_requires_positive_pair_data"],
            "observed": {"combination_evidence_status": combination_contract.get("status") or UNKNOWN},
        },
        "manufacturing_constraints": {
            "status": "ready" if manufacturing_constraints.get("status") == "ready" else "blocked",
            "requires": ["expression_or_process_constraints", "scale_up_owner_review", "formulation_or_process_assay_scope"],
            "observed": {"status": manufacturing_constraints.get("status") or UNKNOWN},
        },
        "live_gate_approval": {
            "status": "blocked",
            "requires": ["explicit_operator_approval", "maintenance_window", "go_no_go_review"],
            "observed": {"approval": "not_requested_by_trace"},
        },
    }
    blocked = [
        name
        for name, gate in gates.items()
        if gate["status"] != "ready"
    ]
    status = "ready_for_operator_review" if not blocked and formal_decision.get("status") == "explicit" else "blocked"
    return {
        "schema_version": "p4_closed_loop_readiness_v1",
        "status": status,
        "read_only": True,
        "active_learning_batch_contract": _p4_active_learning_batch_contract(learning_readiness),
        "model_calibration_registry_contract": _p4_model_calibration_registry_contract(project_model),
        "manufacturing_constraint_contract": _p4_manufacturing_constraint_contract(next_round_library_design),
        "operator_review_contract": _p4_operator_review_contract(
            formal_decision=formal_decision,
            p4_readiness={
                "gates": gates,
            },
        ),
        "gates": gates,
        "blocked_gates": blocked,
        "required_action_count": len(required_actions),
        "must_not_claim": [
            "active_learning_batch_executed",
            "model_retrained",
            "manufacturing_constraints_validated",
            "live_gate_approved",
        ],
        "boundary": (
            "P4 readiness is a production closed-loop review contract. It does not train models, "
            "schedule assays, execute live gates, approve manufacturing constraints, or mutate project records."
        ),
    }


def _build_trace_summary(
    *,
    project_model: dict[str, Any],
    learning_readiness: dict[str, Any],
    next_round_library_design: dict[str, Any],
    formal_decision: dict[str, Any],
) -> dict[str, Any]:
    missing_entities = list(project_model.get("missing_entities") or [])
    learning_status = _key_or_unknown(learning_readiness.get("status"))
    next_round_status = _key_or_unknown(next_round_library_design.get("status"))
    next_round_structural_distance_source = _key_or_unknown(
        next_round_library_design.get("structural_distance_source")
    )
    next_round_combination_evidence_status = _key_or_unknown(
        (next_round_library_design.get("combination_evidence_contract") or {}).get("status")
    )
    training_eligible_count = int(learning_readiness.get("training_eligible_count") or 0)
    variant_count = int((project_model.get("counts") or {}).get("variants") or 0)

    required_actions: list[dict[str, Any]] = []
    if "round" in missing_entities:
        required_actions.append(
            _required_action(
                "create_or_select_round",
                reason="No observed DBTL round is available in the selected scope.",
                blocks=["round_scoped_trace", "next_round_planning"],
            )
        )
    if "ready_wt_baseline" in missing_entities:
        required_actions.append(
            _required_action(
                "record_qc_passed_wt_baseline",
                reason="A matched WT baseline is required before improvement claims can be upgraded.",
                blocks=["baseline_dependent_claims", "training_use"],
            )
        )
    if "experiment_feedback" in missing_entities:
        required_actions.append(
            _required_action(
                "import_experiment_feedback",
                reason="No experiment feedback records are linked to this trace scope.",
                blocks=["learning_readiness", "next_round_design"],
            )
        )
    if "formal_decision" in missing_entities:
        required_actions.append(
            _required_action(
                "record_formal_decision",
                reason="Go/Watch/No-Go has not been resolved as a formal project decision.",
                blocks=["claim_upgrade", "project_memory_closure"],
            )
        )
    if learning_status != "ready":
        required_actions.append(
            _required_action(
                "complete_feedback_import_contract",
                reason="Feedback records are not yet sufficient for training or claim promotion.",
                blocks=["training", "model_upgrade_claims"],
                top_missing_reasons=_top_counts(
                    learning_readiness.get("missing_for_training_counts") or {}
                ),
            )
        )
    if next_round_status in {"blocked_no_validated_singletons", "not_available", UNKNOWN}:
        required_actions.append(
            _required_action(
                "validate_single_mutants_before_combination",
                reason="Controlled pair or higher-order library design requires validated single-mutant evidence first.",
                blocks=["controlled_pair_library", "higher_order_library"],
            )
        )

    if not required_actions and training_eligible_count >= 12:
        status = "ready_for_learning_review"
    elif variant_count or learning_readiness.get("record_count"):
        status = "partial_action_required"
    else:
        status = "missing_project_memory"

    return {
        "schema_version": TRACE_SUMMARY_SCHEMA_VERSION,
        "status": status,
        "project_memory_status": project_model.get("status") or UNKNOWN,
        "project_memory_readiness": _project_memory_readiness(project_model),
        "feedback_readiness": _feedback_readiness_summary(learning_readiness),
        "readiness_bridge": _readiness_bridge(
            project_model=project_model,
            learning_readiness=learning_readiness,
            next_round_library_design=next_round_library_design,
        ),
        "learning_status": learning_status,
        "next_round_status": next_round_status,
        "next_round_structural_distance_source": next_round_structural_distance_source,
        "next_round_combination_evidence_status": next_round_combination_evidence_status,
        "formal_decision_status": formal_decision.get("status") or UNKNOWN,
        "counts": {
            "rounds": (project_model.get("counts") or {}).get("rounds", 0),
            "variants": variant_count,
            "feedback_records": (project_model.get("counts") or {}).get("feedback_records", 0),
            "training_eligible_feedback_records": training_eligible_count,
        },
        "missing_entities": missing_entities,
        "top_missing_for_training": _top_counts(
            learning_readiness.get("missing_for_training_counts") or {}
        ),
        "required_actions": required_actions,
        "required_action_contract": _required_action_contract(required_actions),
        "p4_closed_loop_readiness": _p4_closed_loop_readiness(
            project_model=project_model,
            learning_readiness=learning_readiness,
            next_round_library_design=next_round_library_design,
            formal_decision=formal_decision,
            required_actions=required_actions,
        ),
        "report_contract": {
            "show_project_model": True,
            "show_learning_readiness": True,
            "show_next_round_library_design": bool(next_round_library_design),
            "must_label_computational_outputs_as_hypothesis": True,
            "must_not_claim_training_or_wet_lab_validation": True,
        },
        "boundary": (
            "This summary is a read-only DBTL trace digest for reports and agents. "
            "It does not train a model, create project memory rows, resolve formal decisions, "
            "or upgrade computational hypotheses to wet-lab claims."
        ),
    }


async def build_dbtl_trace(
    session: AsyncSession,
    *,
    project_id: str,
    round_key: str | None = None,
) -> dict[str, Any]:
    """Aggregate existing DBTL records without mutating the session or database."""
    checkpoints = (
        await session.execute(
            select(StrategyCheckpoint)
            .where(StrategyCheckpoint.project_id == project_id)
            .order_by(StrategyCheckpoint.created_at.asc(), StrategyCheckpoint.id.asc())
        )
    ).scalars().all()
    feedback_records = (
        await session.execute(
            select(ExperimentFeedbackRecord)
            .where(ExperimentFeedbackRecord.project_id == project_id)
            .order_by(ExperimentFeedbackRecord.created_at.asc(), ExperimentFeedbackRecord.id.asc())
        )
    ).scalars().all()
    calibration_runs = (
        await session.execute(
            select(WetLabCalibrationRun)
            .where(WetLabCalibrationRun.project_id == project_id)
            .order_by(WetLabCalibrationRun.created_at.asc(), WetLabCalibrationRun.id.asc())
        )
    ).scalars().all()

    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    formal_entries: list[dict[str, Any]] = []
    discovered_rounds: list[str] = []
    wt_statuses: list[str] = []
    wt_feedback_ids: list[int] = []
    feedback_ids_by_project = {record.id for record in feedback_records}
    calibration_summaries: list[dict[str, Any]] = []
    scoped_feedback_records: list[ExperimentFeedbackRecord] = []

    for checkpoint in checkpoints:
        metadata = _metadata(
            [
                checkpoint.plan_payload,
                checkpoint.evidence_state,
                checkpoint.artifacts,
                checkpoint.policy_payload,
            ]
        )
        if not _round_matches(metadata["round_key"], round_key):
            continue
        if metadata["round_key"] != UNKNOWN:
            _append_unique(discovered_rounds, metadata["round_key"])

        variant_key = metadata["variant_key"]
        variant = variants.setdefault(variant_key, _new_variant(variant_key))
        _append_unique(variant["checkpoint_ids"], checkpoint.id)
        _merge_prediction(variant, metadata["prediction"])
        variant["_decisions"].append(_key_or_unknown(metadata["decision"]))
        if isinstance(metadata["formal_decision"], (dict, str, int, float)):
            entry = _formal_decision_entry(
                metadata["formal_decision"],
                source_type="strategy_checkpoint",
                source_id=checkpoint.id,
                decided_by_user_id=checkpoint.user_id,
            )
            if entry:
                formal_entries.append(entry)

    for record in feedback_records:
        metadata = _metadata(
            [
                record.assay_payload,
                record.metrics_payload,
                record.quality_payload,
                record.interpretation_payload,
            ]
        )
        if not _round_matches(metadata["round_key"], round_key):
            continue
        scoped_feedback_records.append(record)
        if metadata["round_key"] != UNKNOWN:
            _append_unique(discovered_rounds, metadata["round_key"])
        if _is_wild_type_record(record):
            _append_unique(wt_feedback_ids, record.id)
            if metadata["wt_baseline_status"] is not None:
                wt_statuses.append(_normalise_status(metadata["wt_baseline_status"]))

        variant_key = metadata["variant_key"]
        if variant_key == UNKNOWN:
            variant_key = _key_or_unknown(record.variant_name)
        variant = variants.setdefault(variant_key, _new_variant(variant_key))
        if record.parent_variant:
            variant["parent_variant"] = record.parent_variant
        _append_unique(variant["feedback_record_ids"], record.id)
        _merge_prediction(variant, metadata["prediction"])
        decision = metadata["decision"]
        if decision is None:
            decision = (record.interpretation_payload or {}).get("decision")
        variant["_decisions"].append(_key_or_unknown(decision))
        if isinstance(metadata["formal_decision"], (dict, str, int, float)):
            entry = _formal_decision_entry(
                metadata["formal_decision"],
                source_type="experiment_feedback",
                source_id=record.id,
                decided_by_user_id=record.created_by_user_id,
            )
            if entry:
                formal_entries.append(entry)

    for run in calibration_runs:
        metadata = _metadata([run.calibration_payload])
        if not _round_matches(metadata["round_key"], round_key):
            continue
        if metadata["round_key"] != UNKNOWN:
            _append_unique(discovered_rounds, metadata["round_key"])
        if metadata["wt_baseline_status"] is not None:
            wt_statuses.append(_normalise_status(metadata["wt_baseline_status"]))
        linked_feedback_ids: list[int] = []
        unresolved_feedback_ids: list[int] = []
        for record_id in list(run.feedback_record_ids or []):
            target = (
                linked_feedback_ids
                if record_id in feedback_ids_by_project
                else unresolved_feedback_ids
            )
            _append_unique(target, record_id)
        summary = {
            "id": run.id,
            "objective": run.objective,
            "assay_key": run.assay_key,
            "dataset_fingerprint": run.dataset_fingerprint,
            "feedback_record_ids": linked_feedback_ids,
            "unresolved_feedback_record_ids": unresolved_feedback_ids,
            "data_quality_grade": run.data_quality_grade,
            "evidence_level": run.evidence_level,
            "measured_variant_count": run.measured_variant_count,
            "go_count": run.go_count,
            "watch_count": run.watch_count,
            "no_go_count": run.no_go_count,
        }
        calibration_summaries.append(summary)
        for variant in variants.values():
            if any(record_id in summary["feedback_record_ids"] for record_id in variant["feedback_record_ids"]):
                _append_unique(variant["calibration_run_ids"], run.id)

    if round_key is not None:
        resolved_round_key = round_key
    elif len(discovered_rounds) == 1:
        resolved_round_key = discovered_rounds[0]
    else:
        resolved_round_key = UNKNOWN

    explicit_statuses = [status for status in wt_statuses if status != UNKNOWN]
    if len(set(explicit_statuses)) == 1:
        baseline_status = explicit_statuses[0]
    elif explicit_statuses:
        baseline_status = "conflict"
    else:
        baseline_status = UNKNOWN

    finalized_variants = [_finalize_variant(variant) for variant in variants.values()]

    formal_decision = _build_formal_decision(formal_entries)
    next_round_plan = await feedback_iteration_planner(
        [_feedback_payload(record) for record in scoped_feedback_records],
        objective="multi_objective",
    )

    project_model = _build_project_model_contract(
        project_id=project_id,
        discovered_rounds=discovered_rounds,
        wt_baseline_status=baseline_status,
        wt_feedback_ids=wt_feedback_ids,
        variants=finalized_variants,
        calibration_summaries=calibration_summaries,
        formal_decision=formal_decision,
    )
    learning_readiness = _build_learning_readiness(scoped_feedback_records)
    next_round_library_design = next_round_plan.get("next_round_library_design", {})

    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "project_id": project_id,
        "round_key": resolved_round_key,
        "project_model": project_model,
        "learning_readiness": learning_readiness,
        "next_round_library_design": next_round_library_design,
        "trace_summary": _build_trace_summary(
            project_model=project_model,
            learning_readiness=learning_readiness,
            next_round_library_design=next_round_library_design,
            formal_decision=formal_decision,
        ),
        "wt_baseline": {
            "status": baseline_status,
            "feedback_record_ids": wt_feedback_ids,
            "calibration_runs": calibration_summaries,
        },
        "variants": finalized_variants,
        "formal_decision": formal_decision,
    }
