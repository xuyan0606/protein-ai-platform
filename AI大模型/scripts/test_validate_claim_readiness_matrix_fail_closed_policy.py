import copy

import validate_claim_readiness_matrix_fail_closed_policy as validator


def matrix():
    claims = [
        {
            "claim_id": "internal_design_review_artifacts",
            "ready": True,
            "allowed": True,
            "status": "allowed",
            "missing_requirements": [],
            "requirements": [{"name": "source ready", "passed": True}],
        },
        {
            "claim_id": "model_quality_claim",
            "ready": False,
            "allowed": False,
            "status": "blocked",
            "missing_requirements": ["source ready"],
            "requirements": [{"name": "source ready", "passed": False}],
        },
    ]
    return {
        "local_only": True,
        "claims_allowed": 1,
        "claims_blocked": 1,
        "allowed_claim_ids": ["internal_design_review_artifacts"],
        "blocked_claim_ids": ["model_quality_claim"],
        "claims": claims,
        "global_policy": "fail closed",
    }


def test_exact_matrix_has_source_parity():
    expected = matrix()
    assert validator.source_parity_failures(copy.deepcopy(expected), expected) == []


def test_requirement_passed_tamper_breaks_source_parity():
    expected = matrix()
    actual = copy.deepcopy(expected)
    actual["claims"][1]["requirements"][0]["passed"] = True
    failures = validator.source_parity_failures(actual, expected)
    assert any(item["check"] == "source_parity_claim_row" for item in failures)


def test_missing_requirement_tamper_breaks_source_parity():
    expected = matrix()
    actual = copy.deepcopy(expected)
    actual["claims"][1]["missing_requirements"] = []
    failures = validator.source_parity_failures(actual, expected)
    assert any(item["check"] == "source_parity_claim_row" for item in failures)


def test_claim_deletion_breaks_source_parity():
    expected = matrix()
    actual = copy.deepcopy(expected)
    actual["claims"].pop()
    failures = validator.source_parity_failures(actual, expected)
    assert any(item["check"] == "source_parity_claim_ids" for item in failures)


def test_summary_tamper_breaks_source_parity():
    expected = matrix()
    actual = copy.deepcopy(expected)
    actual["claims_blocked"] = 0
    failures = validator.source_parity_failures(actual, expected)
    assert any(item["check"] == "source_parity_claims_blocked" for item in failures)
