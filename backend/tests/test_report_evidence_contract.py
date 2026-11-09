import pytest

from app.services.report_evidence_contract import (
    EVIDENCE_TYPES,
    EvidenceType,
    make_evidence_record,
    normalize_evidence_status,
)


def test_evidence_types_are_fixed_to_the_five_report_categories():
    assert tuple(item.value for item in EvidenceType) == (
        "experimental_fact",
        "database_evidence",
        "computed_result",
        "inference",
        "hypothesis",
    )
    assert EVIDENCE_TYPES == frozenset(item.value for item in EvidenceType)


@pytest.mark.parametrize("status", ["waiting", "failed", "not_run"])
def test_non_terminal_statuses_cannot_render_as_complete(status):
    record = make_evidence_record(
        evidence_type="database_evidence",
        status=status,
        source="NCBI",
    )
    assert record["status"] == status
    assert record["is_complete"] is False
    assert normalize_evidence_status(status)["is_complete"] is False


def test_inference_and_hypothesis_require_derived_from():
    with pytest.raises(ValueError, match="derived_from"):
        make_evidence_record(evidence_type="inference", status="completed")
    with pytest.raises(ValueError, match="derived_from"):
        make_evidence_record(evidence_type="hypothesis", status="completed")

    record = make_evidence_record(
        evidence_type="inference",
        status="completed",
        derived_from=["evidence-1"],
    )
    assert record["derived_from"] == ["evidence-1"]
    assert record["is_complete"] is True


def test_unknown_type_and_status_are_rejected():
    with pytest.raises(ValueError):
        make_evidence_record(evidence_type="opinion", status="completed")
    with pytest.raises(ValueError):
        make_evidence_record(evidence_type="computed_result", status="maybe")
