"""Tests for fail-closed WT baseline selection."""

from __future__ import annotations

from app.models.domain import EnzymeRecord, KineticParameter
from app.services.wt_baseline_registry import WTBaselineRegistry


async def _seed_enzyme(session):
    enzyme = EnzymeRecord(
        uniprot_id="WTBASE1",
        entry_name="WTBASE1_TEST",
        sequence="MSTNPKPQRKTK",
        seq_length=12,
        protein_name="WT baseline test enzyme",
    )
    session.add(enzyme)
    await session.flush()
    session.add(
        KineticParameter(
            enzyme_id=enzyme.id,
            source_db="brenda",
            param_type="specific_activity",
            substrate_name="starch",
            value=12.0,
            unit="U/mg",
            ph=5.0,
            temperature_c=50.0,
            mutant="wild-type",
            literature_ref="PMID:1",
        )
    )
    await session.commit()


def _selector():
    return {
        "uniprot_id": "WTBASE1",
        "metric": "specific_activity",
        "substrate_name": "starch",
        "ph": 5.0,
        "temperature_c": 50.0,
        "buffer": "sodium acetate",
        "protein_preparation": "purified_enzyme",
        "batch_id": "B-01",
    }


async def test_registry_rejects_kinetic_row_without_preparation_and_batch(session):
    await _seed_enzyme(session)

    payload = await WTBaselineRegistry(session).resolve(**_selector())

    assert payload["status"] == "missing"
    assert payload["baseline"] is None
    assert "no_exact_wt_baseline_under_requested_conditions" in payload["blocked_reasons"]
    assert "kinetic_buffer_missing_or_mismatch" in payload["rejected_reasons"]
    assert payload["claim_context"]["claim_status"] == "MISSING"
    assert payload["report_contract"]["status"] == "missing"
    assert payload["report_contract"]["ready_for_comparison"] is False
    assert payload["report_contract"]["exact_condition_match_required"] is True
    assert payload["report_contract"]["approximate_condition_substitution_allowed"] is False
    assert payload["report_contract"]["nearest_condition_fallback_allowed"] is False


async def test_registry_accepts_exact_qc_passed_wt_feedback(session):
    await _seed_enzyme(session)
    selector = _selector()
    payload = await WTBaselineRegistry(session).resolve(
        **selector,
        feedback_records=[
            {
                "id": 71,
                "variant_name": "WT",
                "mutations": [],
                "project_id": "PTEST",
                "assay_payload": {
                    "substrate_name": "starch",
                    "ph": 5.0,
                    "temperature_c": 50.0,
                    "buffer": "sodium acetate",
                    "protein_preparation": "purified_enzyme",
                    "batch_id": "B-01",
                },
                "metrics_payload": {
                    "specific_activity": 12.0,
                    "specific_activity_unit": "U/mg",
                },
                "quality_payload": {"qc_status": "passed"},
            }
        ],
    )

    assert payload["status"] == "ready"
    assert payload["baseline"]["source_id"] == "experiment_feedback:71"
    assert payload["baseline"]["condition_key"]["batch_id"] == "B-01"
    assert payload["claim_context"]["claim_status"] == "SUPPORTED"
    assert payload["report_contract"]["status"] == "ready"
    assert payload["report_contract"]["ready_for_comparison"] is True
    assert payload["report_contract"]["blocked_claims"] == []


async def test_registry_conflicts_on_incompatible_exact_wt_feedback(session):
    await _seed_enzyme(session)
    records = []
    for record_id, value in ((1, 12.0), (2, 15.0)):
        records.append(
            {
                "id": record_id,
                "variant_name": "wild-type",
                "mutations": [],
                "assay_payload": {
                    "substrate_name": "starch",
                    "ph": 5.0,
                    "temperature_c": 50.0,
                    "buffer": "sodium acetate",
                    "protein_preparation": "purified_enzyme",
                    "batch_id": "B-01",
                },
                "metrics_payload": {
                    "specific_activity": value,
                    "specific_activity_unit": "U/mg",
                },
                "quality_payload": {"qc_status": "passed"},
            }
        )

    payload = await WTBaselineRegistry(session).resolve(**_selector(), feedback_records=records)

    assert payload["status"] == "conflict"
    assert payload["baseline"] is None
    assert payload["candidate_count"] == 2
    assert payload["claim_context"]["claim_status"] == "CONFLICTING"
    assert payload["report_contract"]["status"] == "conflict"
    assert payload["report_contract"]["ready_for_comparison"] is False
    assert payload["report_contract"]["report_action"] == "block_wt_comparison_until_conflict_resolved"
    assert payload["report_contract"]["cross_batch_fallback_allowed"] is False


async def test_registry_unknown_enzyme_emits_complete_missing_report_contract(session):
    payload = await WTBaselineRegistry(session).resolve(**_selector())

    assert payload["status"] == "missing"
    assert payload["claim_context"]["claim_status"] == "MISSING"
    assert payload["report_contract"]["status"] == "missing"
    assert payload["report_contract"]["missing_fields"] == ["uniprot_id"]
    assert payload["report_contract"]["blocked_claims"] == [
        "improvement_vs_wt",
        "fold_change_vs_wt",
    ]


async def test_tool_emits_same_report_contract(session):
    from app.tools.wt_baseline_registry import wt_baseline_registry

    await _seed_enzyme(session)
    payload = await wt_baseline_registry(**_selector(), _session=session)

    assert payload["report_contract"]["schema_version"] == "wt_baseline_report_contract_v1"
    assert payload["report_contract"]["status"] == payload["status"]
    assert payload["claim_context"]["baseline_status"] == payload["status"]
    assert payload["provenance"]["read_only"] is True
    assert payload["provenance"]["network_used"] is False
