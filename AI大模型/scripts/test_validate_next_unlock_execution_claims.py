import validate_next_unlock_execution as validator


CLAIM_IDS = {"internal_design_review_artifacts", "model_quality_claim"}
OTHER_REPORT_KEYS = {
    "numbering",
    "repaired",
    "safe_entry",
    "structure_validation",
    "structure_apply",
    "domain_packets",
    "domain_validation",
    "domain_apply",
    "msa_runtime",
    "msa_cache",
    "feedback",
    "plate_feedback",
    "license",
    "biosecurity",
    "ip_fto",
    "workstream",
    "operator",
}


def packet():
    return {"action_id": "P43-A012", "started": True}


def reports(*, blocked=1, parity=True, all_ready=False, promotion=False, claim_ids=None):
    ids = CLAIM_IDS if claim_ids is None else set(claim_ids)
    blocked_ids = ["model_quality_claim"] if blocked else []
    allowed_ids = sorted(ids - set(blocked_ids))
    values = {key: {} for key in OTHER_REPORT_KEYS}
    values.update({
        "claims": {
            "claims_blocked": blocked,
            "allowed_claim_ids": allowed_ids,
            "blocked_claim_ids": blocked_ids,
        },
        "claim_policy": {
            "success": True,
            "source_parity_success": parity,
            "canonical_claim_ids": sorted(CLAIM_IDS),
            "all_claims_ready": all_ready,
            "not_ready_claim_ids": [] if all_ready else ["model_quality_claim"],
            "promotion_policy_allows_all_claims": promotion,
        },
        "claim_policy_anchor": {"success": True},
        "claim_policy_anchor_regression": {"success": True, "passed_case_count": 8},
        "claim_promotion": {"ready_for_claim_promotion": True},
        "claim_policy_current": {"success": True},
        "claim_policy_current_regression": {"success": True, "passed_case_count": 11},
    })
    return values


def passed_by_name(rows):
    return {row["name"]: row["passed"] for row in rows}


def test_zero_blocked_summary_cannot_bypass_stale_source_parity():
    checks = passed_by_name(validator.completion_checks(packet(), reports(blocked=0, parity=False)))
    assert checks["claim matrix has zero blocked claims"] is True
    assert checks["claim matrix matches current upstream sources"] is False


def test_dynamic_readiness_cannot_bypass_promotion_policy():
    checks = passed_by_name(validator.completion_checks(packet(), reports(blocked=0, all_ready=True, promotion=False)))
    assert checks["all canonical claims are dynamically ready"] is True
    assert checks["promotion policy allows all canonical claims"] is False


def test_missing_canonical_claim_cannot_bypass_zero_blocked_summary():
    checks = passed_by_name(
        validator.completion_checks(
            packet(),
            reports(blocked=0, all_ready=True, promotion=True, claim_ids={"internal_design_review_artifacts"}),
        )
    )
    assert checks["claim matrix has zero blocked claims"] is True
    assert checks["claim matrix has exact canonical claims"] is False


def test_all_explicit_completion_layers_have_a_positive_path():
    checks = validator.completion_checks(packet(), reports(blocked=0, all_ready=True, promotion=True))
    assert checks
    assert all(row["passed"] for row in checks)
