"""P3-2 experiment feedback import contract tests."""

from __future__ import annotations

from app.core.security import create_access_token
from app.models.user import User
from app.services.experiment_feedback import build_experiment_feedback_import_contract


async def _create_user(session, email: str) -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name=email.split("@")[0],
    )
    session.add(user)
    await session.flush()
    return user


def test_import_contract_blocks_training_without_qc_replicates_conditions_or_formal_decision():
    contract = build_experiment_feedback_import_contract(
        {
            "variant_name": "A10V",
            "mutations": ["A10V"],
            "assay_payload": {"assay_type": "specific_activity"},
            "metrics_payload": {"total_activity_fold_vs_wt": 1.8},
            "quality_payload": {},
            "interpretation_payload": {},
        }
    )

    assert contract["schema_version"] == "experiment_feedback_import_v1"
    assert contract["training_eligible"] is False
    assert contract["qc_status"] == "missing"
    assert contract["replicate_count"] is None
    assert contract["formal_decision"] == "missing"
    assert "qc_status_passed" in contract["missing_for_training"]
    assert "replicate_count_at_least_2" in contract["missing_for_training"]
    assert "complete_assay_condition_key" in contract["missing_for_training"]
    assert "formal_decision" in contract["missing_for_training"]
    assert contract["claim_eligibility"]["stability"] is False


def test_import_contract_allows_training_and_stability_claim_only_with_full_quality():
    contract = build_experiment_feedback_import_contract(
        {
            "variant_name": "A10V",
            "mutations": ["A10V"],
            "assay_payload": {
                "assay_type": "specific_activity",
                "substrate": "pNP-C8",
                "ph": 7.0,
                "temperature_c": 37,
                "buffer": "50 mM phosphate",
                "sample_type": "purified_enzyme",
            },
            "metrics_payload": {
                "specific_activity_fold_vs_wt": 1.25,
                "tm_delta_c": 2.1,
                "soluble_expression_pct_wt": 95,
            },
            "quality_payload": {"qc_status": "passed", "replicate_count": 3},
            "interpretation_payload": {"decision": "go"},
        }
    )

    assert contract["training_eligible"] is True
    assert contract["missing_for_training"] == []
    assert contract["metric_groups"]["activity"] is True
    assert contract["metric_groups"]["stability"] is True
    assert contract["claim_eligibility"]["activity"] is True
    assert contract["claim_eligibility"]["stability"] is True
    assert contract["condition_key"]["substrate"] == "pNP-C8"


async def test_experiment_feedback_api_returns_import_contract(client, session):
    owner = await _create_user(session, "feedback-import-contract@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(owner.id))

    response = await client.post(
        "/api/data/experiment-feedback",
        json={
            "enzyme_name": "KWB lipase",
            "variant_name": "A10V",
            "parent_variant": "WT",
            "mutations": ["A10V"],
            "assay_payload": {
                "assay_type": "specific_activity",
                "substrate": "pNP-C8",
                "ph": 7.0,
                "temperature_c": 37,
                "buffer": "50 mM phosphate",
                "sample_type": "purified_enzyme",
            },
            "metrics_payload": {
                "specific_activity_fold_vs_wt": 1.25,
                "tm_delta_c": 2.1,
                "soluble_expression_pct_wt": 95,
            },
            "quality_payload": {"qc_status": "passed", "replicate_count": 3},
        },
    )

    assert response.status_code == 200
    contract = response.json()["record"]["interpretation_payload"]["import_contract"]
    assert contract["schema_version"] == "experiment_feedback_import_v1"
    assert contract["training_eligible"] is True
    assert contract["claim_eligibility"]["stability"] is True
