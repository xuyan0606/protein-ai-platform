"""Fail-closed WT baseline selection for enzyme engineering claims."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import EnzymeRecord, KineticParameter

_REQUIRED_SELECTOR_FIELDS = (
    "metric",
    "substrate_name",
    "ph",
    "temperature_c",
    "buffer",
    "protein_preparation",
    "batch_id",
)
_WT_VARIANTS = {"WT", "WILD-TYPE", "WILD TYPE", "WILDTYPE"}
_QC_PASSED = {"PASSED", "PASS", "ACCEPTED"}
_BLOCKED_CLAIMS = [
    "improvement_vs_wt",
    "fold_change_vs_wt",
]


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized_text(value: object) -> str:
    return _text(value).lower()


def _same_float(left: object, right: object) -> bool:
    try:
        return abs(float(left) - float(right)) < 1e-9
    except (TypeError, ValueError):
        return False


def _is_wt(variant_name: object, mutations: object) -> bool:
    return _text(variant_name).upper() in _WT_VARIANTS and not (mutations or [])


def _selector_from_inputs(
    *,
    metric: str,
    substrate_name: str,
    ph: float | None,
    temperature_c: float | None,
    buffer: str,
    protein_preparation: str,
    batch_id: str,
) -> dict[str, Any]:
    return {
        "metric": _text(metric),
        "substrate_name": _text(substrate_name),
        "ph": ph,
        "temperature_c": temperature_c,
        "buffer": _text(buffer),
        "protein_preparation": _text(protein_preparation),
        "batch_id": _text(batch_id),
    }


def _selector_missing_fields(selector: dict[str, Any]) -> list[str]:
    missing = []
    for key in _REQUIRED_SELECTOR_FIELDS:
        value = selector.get(key)
        if value is None or _text(value) == "":
            missing.append(key)
    return missing


def _feedback_baseline_candidate(
    record: dict[str, Any],
    selector: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    if not _is_wt(record.get("variant_name"), record.get("mutations")):
        return None, ["explicit_wt_identity_required"]

    assay = record.get("assay_payload") if isinstance(record.get("assay_payload"), dict) else {}
    metrics = record.get("metrics_payload") if isinstance(record.get("metrics_payload"), dict) else {}
    quality = record.get("quality_payload") if isinstance(record.get("quality_payload"), dict) else {}
    metric = selector["metric"]
    value = metrics.get(metric)
    unit = metrics.get(f"{metric}_unit") or assay.get("unit")
    missing = [
        name
        for name, present in {
            "metric_value": value is not None,
            "unit": bool(_text(unit)),
            "qc_status": _text(quality.get("qc_status")).upper() in _QC_PASSED,
            "substrate_name": _normalized_text(assay.get("substrate_name")) == _normalized_text(selector["substrate_name"]),
            "ph": _same_float(assay.get("ph"), selector["ph"]),
            "temperature_c": _same_float(assay.get("temperature_c"), selector["temperature_c"]),
            "buffer": _normalized_text(assay.get("buffer")) == _normalized_text(selector["buffer"]),
            "protein_preparation": (
                _normalized_text(assay.get("protein_preparation"))
                == _normalized_text(selector["protein_preparation"])
            ),
            "batch_id": _normalized_text(assay.get("batch_id")) == _normalized_text(selector["batch_id"]),
        }.items()
        if not present
    ]
    if missing:
        return None, missing

    source_id = record.get("id")
    return {
        "source_id": f"experiment_feedback:{source_id}" if source_id is not None else "experiment_feedback:provided",
        "source_type": "experiment_feedback",
        "value": float(value),
        "unit": _text(unit),
        "metric": metric,
        "condition_key": selector,
        "provenance": {
            "record_id": source_id,
            "project_id": record.get("project_id"),
            "linked_task_id": record.get("linked_task_id"),
            "created_by_user_id": record.get("created_by_user_id"),
        },
    }, []


def _report_contract(
    *,
    status: str,
    missing_fields: list[str],
    blocked_reasons: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the stable claim/report contract consumed by report builders."""

    claim_status = {
        "ready": "SUPPORTED",
        "missing": "MISSING",
        "conflict": "CONFLICTING",
    }.get(status, "MISSING")
    ready = status == "ready"
    if ready:
        assay_required: list[str] = []
        report_action = "allow_exact_condition_wt_comparison"
    elif status == "conflict":
        assay_required = ["resolve_conflicting_exact_condition_wt_baselines"]
        report_action = "block_wt_comparison_until_conflict_resolved"
    else:
        assay_required = ["provide_exact_condition_wt_baseline"]
        report_action = "block_wt_comparison_until_exact_baseline_available"

    claim_context = {
        "requires_wt_baseline": True,
        "claim_status": claim_status,
        "baseline_status": status,
        "blocked_claims": [] if ready else list(_BLOCKED_CLAIMS),
        "assay_required": assay_required,
    }
    report_contract = {
        "schema_version": "wt_baseline_report_contract_v1",
        "status": status,
        "claim_status": claim_status,
        "ready_for_comparison": ready,
        "report_action": report_action,
        "exact_condition_match_required": True,
        "approximate_condition_substitution_allowed": False,
        "nearest_condition_fallback_allowed": False,
        "cross_batch_fallback_allowed": False,
        "cross_preparation_fallback_allowed": False,
        "blocked_claims": [] if ready else list(_BLOCKED_CLAIMS),
        "missing_fields": list(missing_fields),
        "blocked_reasons": list(blocked_reasons),
    }
    return claim_context, report_contract


class WTBaselineRegistry:
    """Resolve only fully specified WT baselines under exactly matching conditions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve(
        self,
        *,
        uniprot_id: str,
        metric: str,
        substrate_name: str,
        ph: float | None,
        temperature_c: float | None,
        buffer: str,
        protein_preparation: str,
        batch_id: str,
        feedback_records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        selector = _selector_from_inputs(
            metric=metric,
            substrate_name=substrate_name,
            ph=ph,
            temperature_c=temperature_c,
            buffer=buffer,
            protein_preparation=protein_preparation,
            batch_id=batch_id,
        )
        missing_fields = _selector_missing_fields(selector)
        enzyme = (
            await self.session.execute(
                select(EnzymeRecord).where(EnzymeRecord.uniprot_id == _text(uniprot_id))
            )
        ).scalar_one_or_none()
        if enzyme is None:
            blocked_reasons = ["unknown_local_enzyme"]
            claim_context, report_contract = _report_contract(
                status="missing",
                missing_fields=["uniprot_id"],
                blocked_reasons=blocked_reasons,
            )
            return {
                "schema_version": "wt_baseline_registry_v1",
                "status": "missing",
                "selector": {"uniprot_id": _text(uniprot_id), **selector},
                "baseline": None,
                "candidate_count": 0,
                "missing_fields": ["uniprot_id"],
                "blocked_reasons": blocked_reasons,
                "provenance": {"read_only": True, "network_used": False, "sources_consulted": []},
                "claim_context": claim_context,
                "report_contract": report_contract,
                "report_boundary": (
                    "Only explicit WT records under the exact requested conditions are eligible. "
                    "No nearest-condition, cross-batch, or cross-preparation fallback is used."
                ),
            }

        kinetic_rows = (
            await self.session.execute(
                select(KineticParameter).where(KineticParameter.enzyme_id == enzyme.id)
            )
        ).scalars().all()
        accepted: list[dict[str, Any]] = []
        rejected_reasons: set[str] = set()
        for row in kinetic_rows:
            if not _is_wt(row.mutant, []):
                rejected_reasons.add("kinetic_row_not_explicit_wt")
                continue
            if _normalized_text(row.param_type) != _normalized_text(selector["metric"]):
                continue
            row_missing = [
                name
                for name, present in {
                    "unit": bool(_text(row.unit)),
                    "literature_ref": bool(_text(row.literature_ref)),
                    "substrate_name": _normalized_text(row.substrate_name) == _normalized_text(selector["substrate_name"]),
                    "ph": _same_float(row.ph, selector["ph"]),
                    "temperature_c": _same_float(row.temperature_c, selector["temperature_c"]),
                    "buffer": False,
                    "protein_preparation": False,
                    "batch_id": False,
                }.items()
                if not present
            ]
            if row_missing:
                rejected_reasons.update(f"kinetic_{name}_missing_or_mismatch" for name in row_missing)
                continue
            accepted.append(
                {
                    "source_id": f"kinetic_parameter:{row.id}",
                    "source_type": "kinetic_parameter",
                    "value": row.value,
                    "unit": _text(row.unit),
                    "metric": row.param_type,
                    "condition_key": selector,
                    "provenance": {
                        "source_db": row.source_db,
                        "literature_ref": row.literature_ref,
                    },
                }
            )

        for record in feedback_records or []:
            if not isinstance(record, dict):
                continue
            candidate, reasons = _feedback_baseline_candidate(record, selector)
            if candidate is not None:
                accepted.append(candidate)
            else:
                rejected_reasons.update(f"feedback_{reason}" for reason in reasons)

        if missing_fields:
            status = "missing"
            blocked_reasons = ["selector_incomplete"]
        elif not accepted:
            status = "missing"
            blocked_reasons = ["no_exact_wt_baseline_under_requested_conditions"]
        else:
            distinct_values = {(candidate["value"], candidate["unit"]) for candidate in accepted}
            if len(distinct_values) > 1:
                status = "conflict"
                blocked_reasons = ["incompatible_exact_condition_wt_baselines"]
            else:
                status = "ready"
                blocked_reasons = []

        claim_context, report_contract = _report_contract(
            status=status,
            missing_fields=missing_fields,
            blocked_reasons=blocked_reasons,
        )

        return {
            "schema_version": "wt_baseline_registry_v1",
            "status": status,
            "selector": {"uniprot_id": enzyme.uniprot_id, **selector},
            "baseline": accepted[0] if status == "ready" else None,
            "candidate_count": len(accepted),
            "candidates": accepted if status == "conflict" else [],
            "missing_fields": missing_fields,
            "blocked_reasons": blocked_reasons,
            "rejected_reasons": sorted(rejected_reasons),
            "provenance": {
                "read_only": True,
                "network_used": False,
                "sources_consulted": ["kinetic_parameters", "provided_scoped_experiment_feedback"],
            },
            "claim_context": claim_context,
            "report_contract": report_contract,
            "report_boundary": (
                "Only explicit WT records under the exact requested metric, substrate, pH, "
                "temperature, buffer, preparation, and batch are eligible. No median, nearest "
                "condition, cross-batch, or cross-preparation fallback is used."
            ),
        }
