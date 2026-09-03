import validate_claim_promotion_decisions as validator


def row(**overrides):
    value = {
        "claim_id": "model_quality_claim",
        "promotion_decision": "approved",
        "reviewer": "human-reviewer",
        "reviewed_at": "2026-08-12T00:00:00+08:00",
        "decision_basis": "reviewed evidence",
        "evidence_artifacts": list(validator.REQUIRED_EVIDENCE_ARTIFACTS),
        "validation_reports": list(validator.REQUIRED_VALIDATION_REPORTS),
        "approved_for_promotion": True,
        "residual_risks": [],
    }
    value.update(overrides)
    return value


def reports():
    summary = release_summary()
    return {
        "policy_current": {"success": True},
        "anchor": {"success": True},
        "local_release_guard_coverage": {"success": True},
        "master_readiness": {"success": True},
        "local_release": {"readiness_summary": summary},
    }


def release_summary():
    return {
        **{field: True for field in validator.HUMAN_TARGET_PROJECTION_FIELDS},
        "human_target_source_runtime_ready_sources": 0,
        "human_target_source_unlock_ready_rows": 0,
        "claim_promotion_decision_validation_success": True,
        "claim_promotion_decision_validation_failures": 0,
        "claim_promotion_template_rows": len(validator.TARGET_CLAIM_IDS),
        "claim_promotion_template_matches_expected_contract": True,
        "claim_promotion_target_claim_rows": len(validator.TARGET_CLAIM_IDS),
        "claim_promotion_requirement_name": validator.CLAIM_PROMOTION_REQUIREMENT_NAME,
        "claim_promotion_required_evidence_artifact_count": len(validator.REQUIRED_EVIDENCE_ARTIFACTS),
        "claim_promotion_required_evidence_artifacts": list(validator.REQUIRED_EVIDENCE_ARTIFACTS),
        "claim_promotion_target_claim_rows_with_contract_requirement": len(validator.TARGET_CLAIM_IDS),
        "claim_promotion_target_claim_rows_with_contract_requirement_passed": len(validator.TARGET_CLAIM_IDS),
        "claim_promotion_target_claim_contract_requirement_complete": True,
        "claim_promotion_target_claim_rows_with_contract_requirement_evidence": len(validator.TARGET_CLAIM_IDS),
        "claim_promotion_target_claim_contract_requirement_evidence_complete": True,
        "claim_promotion_required_validation_report_count": len(validator.REQUIRED_VALIDATION_REPORTS),
        "claim_promotion_required_validation_reports": list(validator.REQUIRED_VALIDATION_REPORTS),
        "claim_promotion_decision_rows": 0,
        "claim_promotion_approved_rows": 0,
        "claim_promotion_missing_decisions": len(validator.TARGET_CLAIM_IDS),
        "claim_promotion_decision_success": False,
        "claim_promotion_validation_failures": 0,
    }


def promotion_contract_evidence(summary=None):
    summary = summary or release_summary()
    return {
        field: summary.get(field)
        for field in validator.CLAIM_PROMOTION_CONTRACT_EVIDENCE_FIELDS
    }


def promotion_requirement_coverage(summary=None):
    summary = summary or release_summary()
    return {
        field: summary.get(field)
        for field in validator.CLAIM_PROMOTION_REQUIREMENT_COVERAGE_FIELDS
    }


def ready_claim(**overrides):
    evidence = promotion_contract_evidence()
    coverage = promotion_requirement_coverage()
    value = {
        "ready": True,
        "requirements": [
            {
                "name": validator.CLAIM_PROMOTION_REQUIREMENT_NAME,
                "passed": True,
                "evidence": {
                    "release_summary": dict(evidence),
                    "master_governance_release": dict(evidence),
                    "release_requirement_coverage": dict(coverage),
                    "master_requirement_coverage": dict(coverage),
                },
            }
        ],
    }
    value.update(overrides)
    return value


def target_claims(model_quality_claim=None):
    claims = {
        claim_id: ready_claim()
        for claim_id in validator.TARGET_CLAIM_IDS
    }
    if model_quality_claim is not None:
        claims["model_quality_claim"] = model_quality_claim
    return claims


def test_template_rows_cover_all_blocked_claims():
    rows = validator.build_template_rows()
    assert [row["claim_id"] for row in rows] == list(validator.TARGET_CLAIM_IDS)
    assert len(rows) == len(validator.TARGET_CLAIM_IDS)
    assert all(row["promotion_decision"] == "needs_more_info" for row in rows)
    assert all(row["approved_for_promotion"] is False for row in rows)


def test_non_object_decision_row_is_rejected_without_crashing():
    assert validator.validate([], {}, reports()) == ["invalid_decision_row"]


def test_invalid_jsonl_decision_row_is_loaded_as_fail_closed_error(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")
    rows = validator.load_jsonl(path)
    assert validator.validate(rows[0], {}, reports()) == ["invalid_decision_json"]


def test_unreadable_jsonl_decision_input_is_fail_closed(tmp_path):
    path = tmp_path / "decisions.jsonl"
    path.write_bytes(b"\xff")
    rows = validator.load_jsonl(path)
    assert validator.validate(rows[0], {}, reports()) == ["unreadable_decision_input"]


def test_missing_jsonl_decision_input_is_fail_closed(tmp_path):
    rows = validator.load_jsonl(tmp_path / "missing.jsonl")
    assert validator.validate(rows[0], {}, reports()) == ["missing_decision_input"]


def test_invalid_source_json_report_is_loaded_as_fail_closed_error(tmp_path):
    path = tmp_path / "source.json"
    path.write_text("{not-json}\n", encoding="utf-8")
    report = validator.load_json(path)
    assert validator.source_report_errors("local_release", report) == ["invalid_source_json_local_release"]


def test_unreadable_source_json_report_is_fail_closed(tmp_path):
    path = tmp_path / "source.json"
    path.write_bytes(b"\xff")
    report = validator.load_json(path)
    assert validator.source_report_errors("local_release", report) == [
        "unreadable_source_json_local_release"
    ]


def test_unreadable_local_release_source_suppresses_derived_summary_error():
    report = {validator.UNREADABLE_JSON_REPORT_KEY: "decode failed"}
    assert validator.local_release_summary_errors(report) == []


def test_missing_source_json_report_is_loaded_as_fail_closed_error(tmp_path):
    report = validator.load_json(tmp_path / "missing.json")
    assert validator.source_report_errors("master_readiness", report) == [
        "missing_source_json_master_readiness"
    ]


def test_non_object_source_json_report_is_loaded_as_fail_closed_error(tmp_path):
    path = tmp_path / "source.json"
    path.write_text("[]\n", encoding="utf-8")
    report = validator.load_json(path)
    assert validator.source_report_errors("claim_matrix", report) == ["invalid_source_json_type_claim_matrix"]


def test_required_source_json_report_success_is_fail_closed():
    assert validator.source_report_errors("master_readiness", {"success": False}) == [
        "source_report_not_success_master_readiness"
    ]


def test_manifest_source_json_report_does_not_require_success_field():
    assert validator.source_report_errors("local_release", {"release_ready": False}) == []


def test_non_object_local_release_readiness_summary_is_fail_closed():
    local_release = {"readiness_summary": []}
    assert validator.local_release_summary(local_release) == {}
    assert validator.local_release_summary_errors(local_release) == ["invalid_local_release_readiness_summary"]


def test_missing_local_release_readiness_summary_is_fail_closed():
    assert validator.local_release_summary({}) == {}
    assert validator.local_release_summary_errors({}) == [
        "missing_local_release_readiness_summary"
    ]


def test_non_list_claim_matrix_claims_is_fail_closed():
    claim_matrix = {"claims": {}}
    assert validator.claim_matrix_claims(claim_matrix) == []
    assert validator.claim_matrix_claims_errors(claim_matrix) == ["invalid_claim_matrix_claims"]


def test_missing_claim_matrix_claims_is_fail_closed():
    assert validator.claim_matrix_claims({}) == []
    assert validator.claim_matrix_claims_errors({}) == ["missing_claim_matrix_claims"]


def test_non_object_claim_matrix_claim_row_is_fail_closed():
    claim_matrix = {"claims": ["bad", {"claim_id": "model_quality_claim"}]}
    assert validator.claim_matrix_claims(claim_matrix) == [{"claim_id": "model_quality_claim"}]
    assert validator.claim_matrix_claims_errors(claim_matrix) == ["invalid_claim_matrix_claim_rows"]


def test_invalid_claim_matrix_claim_id_is_fail_closed():
    claim_matrix = {"claims": [{"claim_id": 123}, {"ready": True}]}
    assert validator.claim_matrix_claims(claim_matrix) == [{"claim_id": 123}, {"ready": True}]
    assert validator.claim_matrix_claims_errors(claim_matrix) == [
        "invalid_claim_matrix_claim_id",
        "invalid_claim_matrix_claim_id",
    ]


def test_duplicate_claim_matrix_claim_id_is_fail_closed():
    claim_matrix = {"claims": [
        {"claim_id": "model_quality_claim"},
        {"claim_id": "model_quality_claim"},
    ]}
    assert validator.claim_matrix_claims_errors(claim_matrix) == ["duplicate_claim_matrix_claim_id"]


def test_missing_claim_matrix_target_claim_is_fail_closed():
    claim_matrix = {
        "claims": [
            {"claim_id": claim_id}
            for claim_id in validator.TARGET_CLAIM_IDS
            if claim_id != "model_quality_claim"
        ]
    }
    assert validator.claim_matrix_claims_errors(claim_matrix) == ["missing_claim_matrix_target_claims"]


def test_non_list_target_claim_requirements_is_fail_closed():
    claims = target_claims({"requirements": {}})
    assert validator.requirement_by_name(claims["model_quality_claim"], validator.CLAIM_PROMOTION_REQUIREMENT_NAME) == {}
    assert validator.claim_requirement_errors(claims) == ["invalid_claim_requirements"]


def test_missing_target_claim_requirements_is_fail_closed():
    claims = target_claims({})
    assert validator.claim_requirement_errors(claims) == [
        "missing_claim_requirements"
    ]


def test_non_object_target_claim_requirement_row_is_fail_closed():
    claims = target_claims({"requirements": ["bad"]})
    assert validator.requirement_by_name(claims["model_quality_claim"], validator.CLAIM_PROMOTION_REQUIREMENT_NAME) == {}
    assert validator.claim_requirement_errors(claims) == ["invalid_claim_requirement_rows"]


def test_missing_target_claim_promotion_requirement_is_fail_closed():
    claims = target_claims({"requirements": []})
    assert validator.claim_requirement_errors(claims) == [
        "missing_claim_promotion_requirement"
    ]


def test_invalid_target_claim_requirement_name_is_fail_closed():
    claim = ready_claim()
    claim["requirements"][0]["name"] = 123
    assert validator.requirement_by_name(claim, validator.CLAIM_PROMOTION_REQUIREMENT_NAME) == {}
    assert validator.claim_requirement_errors(target_claims(claim)) == ["invalid_claim_requirement_name"]


def test_duplicate_target_claim_promotion_requirement_is_fail_closed():
    claim = ready_claim()
    claim["requirements"].append(dict(claim["requirements"][0]))
    assert validator.claim_requirement_errors(target_claims(claim)) == ["duplicate_claim_promotion_requirement"]


def test_missing_claim_promotion_requirement_passed_is_fail_closed():
    claim = ready_claim()
    del claim["requirements"][0]["passed"]
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "missing_claim_promotion_requirement_passed"
    ]


def test_non_boolean_claim_promotion_requirement_passed_is_fail_closed():
    claim = ready_claim()
    claim["requirements"][0]["passed"] = "true"
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_requirement_passed"
    ]


def test_missing_claim_promotion_requirement_evidence_is_fail_closed():
    claim = ready_claim()
    del claim["requirements"][0]["evidence"]
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "missing_claim_promotion_requirement_evidence"
    ]


def test_non_object_claim_promotion_requirement_evidence_is_fail_closed():
    claim = ready_claim()
    claim["requirements"][0]["evidence"] = []
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_requirement_evidence"
    ]


def test_non_object_claim_promotion_release_summary_evidence_is_fail_closed():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["release_summary"] = []
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_release_summary_evidence"
    ]


def test_non_object_claim_promotion_master_governance_evidence_is_fail_closed():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["master_governance_release"] = []
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_master_governance_evidence"
    ]


def test_missing_claim_promotion_release_summary_evidence_is_fail_closed():
    claim = ready_claim()
    del claim["requirements"][0]["evidence"]["release_summary"]
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "missing_claim_promotion_release_summary_evidence"
    ]


def test_missing_claim_promotion_master_governance_evidence_is_fail_closed():
    claim = ready_claim()
    del claim["requirements"][0]["evidence"]["master_governance_release"]
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "missing_claim_promotion_master_governance_evidence"
    ]


def test_claim_promotion_release_summary_evidence_fields_are_exact():
    claim = ready_claim()
    del claim["requirements"][0]["evidence"]["release_summary"]["claim_promotion_template_rows"]
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_release_summary_evidence_fields"
    ]


def test_claim_promotion_master_governance_evidence_fields_are_exact():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["master_governance_release"]["extra"] = True
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_master_governance_evidence_fields"
    ]


def test_claim_promotion_release_summary_evidence_list_fields_are_lists():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["release_summary"]["claim_promotion_required_evidence_artifacts"] = "reports/claim_readiness_matrix.json"
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_release_summary_evidence_lists"
    ]


def test_claim_promotion_master_governance_evidence_list_fields_are_lists():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["master_governance_release"]["claim_promotion_required_validation_reports"] = {}
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_master_governance_evidence_lists"
    ]


def test_claim_promotion_release_summary_required_evidence_artifacts_are_exact():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["release_summary"]["claim_promotion_required_evidence_artifacts"] = list(
        reversed(validator.REQUIRED_EVIDENCE_ARTIFACTS)
    )
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_release_summary_required_evidence_artifacts"
    ]


def test_claim_promotion_master_governance_required_validation_reports_are_exact():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["master_governance_release"]["claim_promotion_required_validation_reports"] = [
        *validator.REQUIRED_VALIDATION_REPORTS,
        "reports/extra.json",
    ]
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_master_governance_required_validation_reports"
    ]


def test_claim_promotion_release_summary_scalar_types_are_checked():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["release_summary"]["claim_promotion_decision_validation_success"] = "true"
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_release_summary_evidence_scalar_types"
    ]


def test_claim_promotion_master_governance_scalar_types_are_checked():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["master_governance_release"]["claim_promotion_target_claim_rows"] = "9"
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_master_governance_evidence_scalar_types"
    ]


def test_claim_promotion_release_summary_evidence_must_be_source_bound():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["release_summary"]["claim_promotion_template_rows"] = 8
    assert validator.claim_requirement_errors(target_claims(claim), release_summary()) == [
        "invalid_claim_promotion_release_summary_evidence_source_binding"
    ]


def test_claim_promotion_master_governance_evidence_must_be_source_bound():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["master_governance_release"]["claim_promotion_missing_decisions"] = 8
    assert validator.claim_requirement_errors(target_claims(claim), release_summary()) == [
        "invalid_claim_promotion_master_governance_evidence_source_binding"
    ]


def test_non_object_claim_promotion_release_requirement_coverage_is_fail_closed():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["release_requirement_coverage"] = []
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_release_requirement_coverage"
    ]


def test_non_object_claim_promotion_master_requirement_coverage_is_fail_closed():
    claim = ready_claim()
    claim["requirements"][0]["evidence"]["master_requirement_coverage"] = []
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_master_requirement_coverage"
    ]


def test_missing_claim_promotion_release_requirement_coverage_is_fail_closed():
    claim = ready_claim()
    del claim["requirements"][0]["evidence"]["release_requirement_coverage"]
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "missing_claim_promotion_release_requirement_coverage"
    ]


def test_missing_claim_promotion_master_requirement_coverage_is_fail_closed():
    claim = ready_claim()
    del claim["requirements"][0]["evidence"]["master_requirement_coverage"]
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "missing_claim_promotion_master_requirement_coverage"
    ]


def test_claim_promotion_release_requirement_coverage_fields_are_exact():
    claim = ready_claim()
    evidence = claim["requirements"][0]["evidence"]
    evidence["release_requirement_coverage"] = promotion_requirement_coverage()
    del evidence["release_requirement_coverage"]["claim_promotion_target_claim_contract_requirement_complete"]
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_release_requirement_coverage_fields"
    ]


def test_claim_promotion_master_requirement_coverage_fields_are_exact():
    claim = ready_claim()
    evidence = claim["requirements"][0]["evidence"]
    evidence["master_requirement_coverage"] = promotion_requirement_coverage()
    evidence["master_requirement_coverage"]["extra"] = True
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_master_requirement_coverage_fields"
    ]


def test_claim_promotion_release_requirement_coverage_scalar_types_are_checked():
    claim = ready_claim()
    evidence = claim["requirements"][0]["evidence"]
    evidence["release_requirement_coverage"] = promotion_requirement_coverage()
    evidence["release_requirement_coverage"]["claim_promotion_requirement_name"] = 9
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_release_requirement_coverage_scalar_types"
    ]


def test_claim_promotion_master_requirement_coverage_scalar_types_are_checked():
    claim = ready_claim()
    evidence = claim["requirements"][0]["evidence"]
    evidence["master_requirement_coverage"] = promotion_requirement_coverage()
    evidence["master_requirement_coverage"][
        "claim_promotion_target_claim_rows_with_contract_requirement_passed"
    ] = True
    assert validator.claim_requirement_errors(target_claims(claim)) == [
        "invalid_claim_promotion_master_requirement_coverage_scalar_types"
    ]


def test_claim_promotion_release_requirement_coverage_must_be_source_bound():
    claim = ready_claim()
    evidence = claim["requirements"][0]["evidence"]
    evidence["release_requirement_coverage"][
        "claim_promotion_target_claim_rows_with_contract_requirement"
    ] = 8
    assert validator.claim_requirement_errors(target_claims(claim), release_summary()) == [
        "invalid_claim_promotion_release_requirement_coverage_source_binding"
    ]


def test_claim_promotion_master_requirement_coverage_must_be_source_bound():
    claim = ready_claim()
    evidence = claim["requirements"][0]["evidence"]
    evidence["master_requirement_coverage"][
        "claim_promotion_target_claim_rows_with_contract_requirement_evidence"
    ] = 8
    assert validator.claim_requirement_errors(target_claims(claim), release_summary()) == [
        "invalid_claim_promotion_master_requirement_coverage_source_binding"
    ]


def test_claim_promotion_evidence_coverage_requires_auxiliary_coverage():
    claim = ready_claim()
    del claim["requirements"][0]["evidence"]["release_requirement_coverage"]
    assert not validator.promotion_requirement_evidence_valid(
        claim["requirements"][0],
        release_summary(),
    )


def test_invalid_path_string_is_missing_not_crashing():
    assert validator.exists_rel("reports/bad\x00path.json") is False


def test_approved_claim_rejects_invalid_path_string_without_crashing():
    errors = validator.validate(
        row(evidence_artifacts=["reports/bad\x00path.json"]),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "missing_evidence_artifacts_paths" in errors


def test_approved_claim_rejects_non_string_evidence_artifacts_without_crashing():
    errors = validator.validate(
        row(evidence_artifacts=[{}]),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "approved_invalid_evidence_artifact_entries" in errors


def test_approved_claim_rejects_non_string_validation_reports_without_crashing():
    errors = validator.validate(
        row(validation_reports=[{}]),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "approved_invalid_validation_report_entries" in errors


def test_non_string_decision_claim_id_is_fail_closed_without_stringifying():
    errors = validator.validate(
        row(claim_id=123),
        {"123": ready_claim()},
        reports(),
    )
    assert "invalid_claim_id" in errors
    assert "unknown_or_non_high_risk_claim" in errors


def test_non_string_decision_review_metadata_is_fail_closed():
    errors = validator.validate(
        row(reviewer={}, reviewed_at=123, decision_basis=[]),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "invalid_reviewer" in errors
    assert "invalid_reviewed_at" in errors
    assert "invalid_decision_basis" in errors


def test_decision_evidence_artifact_entries_must_be_strings():
    errors = validator.validate(
        row(
            promotion_decision="blocked",
            approved_for_promotion=False,
            evidence_artifacts=[{}],
        ),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "invalid_evidence_artifacts_entries" in errors
    assert "missing_evidence_artifacts_paths" not in errors


def test_decision_validation_report_entries_must_be_strings():
    errors = validator.validate(
        row(
            promotion_decision="blocked",
            approved_for_promotion=False,
            validation_reports=[123],
        ),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "invalid_validation_reports_entries" in errors
    assert "missing_validation_reports_paths" not in errors


def test_decision_residual_risk_entries_must_be_strings():
    errors = validator.validate(
        row(
            promotion_decision="blocked",
            approved_for_promotion=False,
            residual_risks=[{}],
        ),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "invalid_residual_risks_entries" in errors


def test_approved_claim_requires_dynamic_readiness():
    errors = validator.validate(row(), {"model_quality_claim": {"ready": False}}, reports())
    assert "approved_claim_not_dynamically_ready" in errors


def test_approved_claim_requires_promotion_evidence_requirement():
    errors = validator.validate(row(), {"model_quality_claim": {"ready": True, "requirements": []}}, reports())
    assert "approved_claim_missing_promotion_evidence_requirement" in errors


def test_approved_claim_requires_release_promotion_contract():
    bad_reports = reports()
    bad_reports["local_release"]["readiness_summary"]["claim_promotion_required_validation_report_count"] = 5
    errors = validator.validate(row(), {"model_quality_claim": ready_claim()}, bad_reports)
    assert "approved_release_promotion_contract_not_valid" in errors


def test_approved_claim_requires_release_promotion_evidence_coverage():
    bad_reports = reports()
    bad_reports["local_release"]["readiness_summary"]["claim_promotion_target_claim_contract_requirement_evidence_complete"] = False
    errors = validator.validate(row(), {"model_quality_claim": ready_claim()}, bad_reports)
    assert "approved_release_promotion_contract_not_valid" in errors


def test_approved_claim_requires_release_required_evidence_artifact_count():
    bad_reports = reports()
    bad_reports["local_release"]["readiness_summary"]["claim_promotion_required_evidence_artifact_count"] = 2
    errors = validator.validate(row(), {"model_quality_claim": ready_claim()}, bad_reports)
    assert "approved_release_promotion_contract_not_valid" in errors


def test_approved_claim_requires_release_required_evidence_artifacts():
    bad_reports = reports()
    bad_reports["local_release"]["readiness_summary"]["claim_promotion_required_evidence_artifacts"] = [
        "reports/claim_readiness_matrix.json",
        "reports/local_release_manifest.json",
    ]
    errors = validator.validate(row(), {"model_quality_claim": ready_claim()}, bad_reports)
    assert "approved_release_promotion_contract_not_valid" in errors


def test_approved_claim_requires_source_bound_promotion_evidence():
    claim = ready_claim()
    requirement = claim["requirements"][0]
    requirement["evidence"]["master_governance_release"]["claim_promotion_required_validation_report_count"] = 5
    errors = validator.validate(row(), {"model_quality_claim": claim}, reports())
    assert "approved_claim_promotion_evidence_not_source_bound" in errors


def test_approved_claim_rejects_unknown_existing_claim(tmp_path):
    (tmp_path / "evidence.json").write_text("{}\n", encoding="utf-8")
    errors = validator.validate(
        row(claim_id="forged_claim"),
        {"forged_claim": {"ready": True}},
        reports(),
        tmp_path,
    )
    assert "unknown_or_non_high_risk_claim" in errors


def test_approved_claim_requires_current_anchor_and_policy():
    errors = validator.validate(
        row(),
        {"model_quality_claim": ready_claim()},
        {
            **reports(),
            "policy_current": {"success": False},
            "anchor": {"success": False},
        },
    )
    assert "approved_claim_policy_current_not_valid" in errors
    assert "approved_claim_policy_anchor_not_valid" in errors


def test_approved_claim_requires_human_target_projection_chain():
    bad_reports = reports()
    bad_reports["local_release"]["readiness_summary"]["human_target_projection_unlock_report_valid"] = False
    bad_reports["local_release"]["readiness_summary"]["human_target_source_unlock_ready_rows"] = 1
    errors = validator.validate(
        row(),
        {"model_quality_claim": ready_claim()},
        bad_reports,
    )
    assert "approved_human_target_projection_chain_not_valid" in errors
    assert "approved_human_target_unlock_rows_not_fail_closed" in errors


def test_approved_claim_requires_release_coverage_and_master_validation():
    errors = validator.validate(
        row(),
        {"model_quality_claim": ready_claim()},
        {
            **reports(),
            "local_release_guard_coverage": {"success": False},
            "master_readiness": {"success": False},
        },
    )
    assert "approved_local_release_guard_coverage_not_valid" in errors
    assert "approved_master_readiness_validation_not_valid" in errors


def test_approved_claim_rejects_extra_validation_report():
    errors = validator.validate(
        row(validation_reports=[*validator.REQUIRED_VALIDATION_REPORTS, "reports/forged_extra_validation_report.json"]),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "approved_unexpected_validation_reports" in errors


def test_approved_claim_rejects_duplicate_validation_report_with_omission():
    bad_reports = list(validator.REQUIRED_VALIDATION_REPORTS)
    bad_reports[-1] = bad_reports[0]
    errors = validator.validate(
        row(validation_reports=bad_reports),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "approved_missing_required_validation_reports" in errors
    assert "approved_duplicate_validation_reports" in errors


def test_approved_claim_rejects_validation_report_order_drift():
    bad_reports = list(reversed(validator.REQUIRED_VALIDATION_REPORTS))
    errors = validator.validate(
        row(validation_reports=bad_reports),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "approved_validation_reports_wrong_order" in errors


def test_approved_claim_rejects_unrelated_existing_evidence_artifact():
    errors = validator.validate(
        row(evidence_artifacts=[*validator.REQUIRED_EVIDENCE_ARTIFACTS, "reports/unrelated_evidence.json"]),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "approved_unexpected_evidence_artifacts" in errors


def test_approved_claim_rejects_duplicate_evidence_artifact_with_omission():
    bad_artifacts = list(validator.REQUIRED_EVIDENCE_ARTIFACTS)
    bad_artifacts[-1] = bad_artifacts[0]
    errors = validator.validate(
        row(evidence_artifacts=bad_artifacts),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "approved_missing_required_evidence_artifacts" in errors
    assert "approved_duplicate_evidence_artifacts" in errors


def test_approved_claim_rejects_evidence_artifact_order_drift():
    bad_artifacts = list(reversed(validator.REQUIRED_EVIDENCE_ARTIFACTS))
    errors = validator.validate(
        row(evidence_artifacts=bad_artifacts),
        {"model_quality_claim": ready_claim()},
        reports(),
    )
    assert "approved_evidence_artifacts_wrong_order" in errors


def test_non_approved_row_cannot_set_approval_flag():
    errors = validator.validate(
        row(promotion_decision="blocked", approved_for_promotion=True),
        {"model_quality_claim": {"ready": False}},
        reports(),
    )
    assert "non_approved_decision_with_approval_flag" in errors


def test_approved_claim_accepts_complete_fixture(tmp_path):
    for path in validator.REQUIRED_EVIDENCE_ARTIFACTS:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}\n", encoding="utf-8")
    for path in validator.REQUIRED_VALIDATION_REPORTS:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}\n", encoding="utf-8")
    assert validator.validate(
        row(),
        {"model_quality_claim": ready_claim()},
        reports(),
        tmp_path,
    ) == []
