"""Focused tests for the additive P2-2 mutation objective score contract."""

from __future__ import annotations

from app.tools.mutation_priority_score import mutation_priority_score


def _ready_identity(protected_positions: list[int] | None = None) -> dict:
    return {
        "identity_status": "identified",
        "guardrail": {"status": "ready"},
        "protected_positions": protected_positions or [],
    }


def _ready_objective() -> dict:
    return {"status": "ready", "candidate_output_allowed": True}


async def test_objective_score_contract_is_structured_and_unknown_is_fail_closed():
    result = await mutation_priority_score(
        sequence="MKTIIALSYIFCLVFADYKDDDDK" * 3,
        engineering_goal="activity",
        objective_signals=["activity", "thermostability", "specificity"],
        identity_profile=_ready_identity(),
        objective_module_plan=_ready_objective(),
        include_lipase_evidence=False,
    )

    contract = result["objective_score_contract"]
    assert contract["schema_version"] == "mutation_objective_score_v1"
    assert contract["multi_objective"] is True
    assert contract["aggregation"] == "none"
    assert contract["score_components"]["activity_score"]["unknown_policy"] == "null_and_block"

    row = result["all_positions"][0]
    score = row["objective_score"]
    assert {
        "activity_score",
        "stability_score",
        "specificity_score",
        "ph_profile_score",
        "expression_score",
        "risk_score",
        "evidence_level",
        "assay_required",
    } <= set(score)
    assert set(score["score_components"]) == {
        "activity_score",
        "stability_score",
        "specificity_score",
        "ph_profile_score",
        "expression_score",
        "risk_score",
    }
    assert score["specificity_score"] is None
    assert score["decision"] == "blocked"
    assert "specificity_score_unknown" in score["blocking_reason"]
    assert score["assay_required"]
    assert score["no_composite_score"] is True
    candidate_rows = result["tier_1_candidates"] + result["tier_2_candidates"]
    assert candidate_rows
    assert all("objective_score" in candidate for candidate in candidate_rows)
    assert result["experiment_design_table"]
    assert all("objective_score" in row for row in result["experiment_design_table"])


async def test_protected_high_risk_objective_score_blocks_without_changing_legacy_tier():
    result = await mutation_priority_score(
        sequence="A" * 20,
        active_site_positions=[10],
        engineering_goal="activity",
        identity_profile=_ready_identity([10]),
        objective_module_plan=_ready_objective(),
        include_lipase_evidence=False,
    )

    protected = next(row for row in result["all_positions"] if row["position"] == 10)
    score = protected["objective_score"]
    assert protected["composite_priority"] == 0.0
    assert protected["tier"] == 3
    assert protected["is_protected"] is True
    assert score["risk_score"] == 10.0
    assert score["decision"] == "blocked"
    assert "protected_catalytic_or_functional_position" in score["blocking_reason"]
    assert score["evidence_level"] == "blocked"
    assert result["tier_1_candidates"] or result["tier_2_candidates"] or result["experiment_design_table"] == []


async def test_candidate_table_generation_contract_tracks_structured_inputs_and_statuses():
    result = await mutation_priority_score(
        sequence="MKTIIALSYIFCLVFADYKDDDDK" * 3,
        engineering_goal="activity",
        objective_signals=["activity", "thermostability"],
        identity_profile=_ready_identity([12]),
        objective_module_plan=_ready_objective(),
        active_site_positions=[12],
        include_lipase_evidence=False,
        site_structure_features=[
            {
                "position": 12,
                "is_protected": True,
                "rel_sasa_status": "computed_from_input_pdb",
                "pocket_channel_interface_status": "unknown_not_computed",
            }
        ],
    )

    generation = result["candidate_table_generation"]
    assert generation["schema_version"] == "candidate_table_generation_v1"
    assert generation["input_contracts"]["residue_feature_table"] == "site_structure_function_features_v1"
    assert generation["input_contracts"]["objective_score"] == "mutation_objective_score_v1"
    assert generation["selection_policy"]["legacy_rank_reused"] is True
    assert generation["selection_policy"]["aggregation"] == "none"
    assert generation["experiment_design_policy"]["schema_version"] == "experiment_design_schedulability_policy_v1"
    assert generation["experiment_design_policy"]["excluded_candidate_statuses"] == ["blocked"]
    assert generation["experiment_design_policy"]["excluded_priorities"] == ["No-Go"]
    assert generation["experiment_design_policy"]["blocked_rows_remain_traceable"] == "all_positions"
    assert generation["row_contract"]["status_values"] == ["high_confidence", "exploratory", "blocked"]
    assert generation["output_groups"]["blocked"] >= 1

    protected = next(row for row in result["all_positions"] if row["position"] == 12)
    assert protected["candidate_status"] == "blocked"
    p2_contract = result["p2_engineering_scorecard_contract"]
    assert p2_contract["schema_version"] == "p2_engineering_scorecard_contract_v1"
    assert p2_contract["input_contracts"] == {
        "residue_feature_table": "site_structure_function_features_v1",
        "objective_score": "mutation_objective_score_v1",
        "candidate_table_generation": "candidate_table_generation_v1",
    }
    assert "single_total_objective_score" in p2_contract["must_not_claim"]
    assert "blocked" in p2_contract["candidate_statuses"]
    candidate_rows = result["tier_1_candidates"] + result["tier_2_candidates"]
    assert candidate_rows
    assert all(row["candidate_status"] in {"high_confidence", "exploratory"} for row in candidate_rows)
    assert all(row["candidate_status"] != "blocked" for row in result["experiment_design_table"])


async def test_p2_scorecard_is_partial_without_residue_feature_table():
    result = await mutation_priority_score(
        sequence="MKTIIALSYIFCLVFADYKDDDDK" * 3,
        engineering_goal="activity",
        objective_signals=["activity", "thermostability"],
        identity_profile=_ready_identity(),
        objective_module_plan=_ready_objective(),
        include_lipase_evidence=False,
    )

    p2_contract = result["p2_engineering_scorecard_contract"]
    assert p2_contract["status"] == "partial"
    assert p2_contract["component_status"]["residue_feature_table"] == "missing"
    assert "residue_feature_table_not_provided" in p2_contract["blocked_reasons"]
    assert p2_contract["report_action"] == "show_p2_partial_contract_and_required_inputs"


async def test_structure_neighbor_evidence_is_carried_into_candidate_rows_without_changing_scores():
    result = await mutation_priority_score(
        sequence="MKTIIALSYIFCLVFADYKDDDDK" * 3,
        engineering_goal="activity",
        identity_profile=_ready_identity(),
        objective_module_plan=_ready_objective(),
        include_lipase_evidence=False,
        site_structure_features=[
            {
                "position": 5,
                "wild_type": "A",
                "structure_feature_status": "available",
                "nearest_catalytic_distance_ca_angstrom": 4.0,
                "contact_count_ca_8a": 3,
                "ca_contact_environment": "sparse_ca_neighborhood",
                "nearest_ca_neighbor_distance_angstrom": 3.25,
                "nearest_ca_neighbor_position": 6,
                "nearest_ca_neighbor_pdb_position": "A:6",
                "rel_sasa_status": "computed_from_input_pdb",
            }
        ],
    )

    row = next(item for item in result["all_positions"] if item["position"] == 5)
    assert row["nearest_ca_neighbor_distance_angstrom"] == 3.25
    assert row["nearest_ca_neighbor_position"] == 6
    assert row["nearest_ca_neighbor_pdb_position"] == "A:6"
    assert "最近CA邻居位点6距离 3.25 A" in row["logic"]
    assert row["objective_score"]["decision"] in {"blocked", "watch", "explore", "go"}


async def test_candidate_feature_completeness_lists_missing_p2_evidence_without_changing_ranking():
    result = await mutation_priority_score(
        sequence="MKTIIALSYIFCLVFADYKDDDDK" * 3,
        engineering_goal="activity",
        identity_profile=_ready_identity(),
        objective_module_plan=_ready_objective(),
        include_lipase_evidence=False,
        site_structure_features=[
            {
                "position": 5,
                "wild_type": "A",
                "structure_feature_status": "available",
                "nearest_ca_neighbor_distance_angstrom": 3.25,
                "secondary_structure": "helix",
                "rel_sasa": 0.42,
                "rel_sasa_status": "computed_from_input_pdb",
                "nonpolymer_proximity_status": "computed_from_input_pdb",
                "backbone_torsion_status": "computed_from_input_pdb",
                "pocket_channel_interface_status": "unknown_not_computed",
            }
        ],
    )

    row = next(item for item in result["all_positions"] if item["position"] == 5)
    completeness = row["feature_completeness"]
    assert completeness["schema_version"] == "candidate_feature_completeness_v1"
    assert completeness["status"] == "partial"
    assert "ca_geometry" in completeness["available_features"]
    assert "rel_sasa" in completeness["available_features"]
    assert "pocket_channel_interface_not_computed" in completeness["missing_feature_reasons"]
    assert "conservation_not_available" in completeness["missing_feature_reasons"]
    assert "ddg_or_packing_not_available" in completeness["missing_feature_reasons"]
    assert "md_rmsf_not_available" in completeness["missing_feature_reasons"]
    assert row["missing_feature_reasons"] == completeness["missing_feature_reasons"]
    assert row["composite_priority"] >= 0
    structure_gap = result["p2_structure_feature_gap_summary"]
    assert structure_gap["schema_version"] == "p2_structure_feature_gap_summary_v1"
    assert structure_gap["status"] == "partial"
    assert structure_gap["report_action"] == "show_structure_feature_gap_summary_beside_candidate_rows"
    assert "pocket_channel_interface_not_computed" in structure_gap["missing_feature_reason_counts"]
    assay_gap = result["p2_objective_assay_gap_summary"]
    assert assay_gap["schema_version"] == "p2_objective_assay_gap_summary_v1"
    assert assay_gap["status"] == "partial"
    assert assay_gap["project_feedback_readiness"]["status"] == "not_provided"
    assert assay_gap["report_action"] == "show_objective_assay_gaps_beside_project_feedback_readiness"

    readiness = result["p2_candidate_readiness_summary"]
    assert readiness["schema_version"] == "p2_candidate_readiness_summary_v1"
    assert readiness["status"] == "partial"
    assert readiness["candidate_table_status"] == result["candidate_table_status"]
    assert readiness["all_position_count"] == result["summary"]["total_positions"]
    assert readiness["missing_feature_reason_counts"]["pocket_channel_interface_not_computed"] >= 1
    assert readiness["missing_feature_reason_counts"]["conservation_not_available"] >= 1
    assert readiness["missing_feature_reason_counts"]["ddg_or_packing_not_available"] >= 1
    assert readiness["missing_feature_reason_counts"]["md_rmsf_not_available"] >= 1
    assert readiness["report_action"] == "show_missing_p2_evidence_before_candidate_claims"
    assert "wet_lab_validated_candidate_from_completeness_summary" in readiness["must_not_claim"]
    objective_readiness = result["p2_objective_score_readiness_summary"]
    assert objective_readiness["schema_version"] == "p2_objective_score_readiness_summary_v1"
    assert objective_readiness["status"] == "partial"
    assert objective_readiness["objective_row_count"] == result["summary"]["total_positions"]
    assert objective_readiness["unknown_component_counts"]["specificity_score"] >= 1
    assert objective_readiness["unknown_component_counts"]["ph_profile_score"] >= 1
    assert objective_readiness["aggregation"] == "none"
    assert objective_readiness["no_composite_score"] is True
    assert objective_readiness["report_action"] == "show_unknown_objective_components_before_candidate_claims"
    assert "single_total_objective_score" in objective_readiness["must_not_claim"]

    candidate_rows = result["tier_1_candidates"] + result["tier_2_candidates"]
    if candidate_rows:
        candidate = next((item for item in candidate_rows if item["position"] == 5), candidate_rows[0])
        assert "feature_completeness" in candidate
        assert "missing_feature_reasons" in candidate


async def test_pdb_coordinate_hypotheses_remain_visible_when_identity_and_assay_gates_are_blocked():
    sequence = "DTTITQNQTGYDNGYFYSFWTDAPGTVSMTLHSGGSYSTSWRNTGNFVAGKGWSTGGRRTVTYNASFNPSGNAYLTLYGWTRNPLVEYYIVESWGTYRPTGTYKGTVTTDGGTYDIYETWRYNAPSIEGTRTFQQFWSVRQQKRTSGTITIGNHFDAWARAGMNLGSHDYQIMATEGYQSSGSSTVSISEGGNP"
    features = [
        {
            "position": position,
            "wild_type": sequence[position - 1],
            "structure_feature_status": "available",
            "rel_sasa": 0.7,
            "rel_sasa_status": "computed_from_input_pdb",
            "contact_count_ca_8a": 5,
            "pocket_channel_interface_status": "unknown_not_computed",
        }
        for position in range(1, len(sequence) + 1)
    ]
    result = await mutation_priority_score(
        sequence=sequence,
        engineering_goal="activity",
        objective_signals=["activity"],
        sequence_provenance="pdb_coordinate_derived",
        identity_profile={"identity_status": "unresolved", "protected_positions": [54, 154]},
        objective_module_plan={
            "status": "blocked",
            "objective": "specific_activity",
            "candidate_output_allowed": False,
            "missing_evidence": ["substrate and protein-normalized assay are missing"],
        },
        site_structure_features=features,
        include_lipase_evidence=False,
    )

    assert result["identity_gate"]["status"] == "exploratory"
    assert result["candidate_table_status"] == "blocked_by_identity_gate"
    assert result["candidate_table_boundary"]["mode"] == "exploratory"
    candidates = result["tier_2_candidates"]
    assert candidates, "a clear activity objective plus a bound PDB coordinate frame should yield reviewable hypotheses"
    assert result["tier_1_candidates"] == []
    assert all(row["candidate_status"] == "exploratory" for row in candidates)
    assert all(row["candidate_evidence_status"] == "computational_hypothesis" for row in candidates)
    assert all(row["recommended_mutations"] for row in candidates)
    assert all(row["position"] not in {54, 154} for row in candidates)
    assert all(row["experiment_priority"] == "P2-探索" for row in candidates)
    assert result["candidate_decision"]["candidate_output_allowed"] is False
    assert result["experiment_design_table"] == []


async def test_identity_blocked_without_bound_structure_keeps_candidate_output_empty():
    result = await mutation_priority_score(
        sequence="MKTIIALSYIFCLVFADYKDDDDK" * 3,
        engineering_goal="activity",
        objective_signals=["activity"],
        identity_profile={"identity_status": "unresolved"},
        objective_module_plan={"status": "blocked", "candidate_output_allowed": False},
        include_lipase_evidence=False,
    )

    assert result["candidate_table_status"] == "blocked_by_identity_gate"
    assert result["tier_1_candidates"] == []
    assert result["tier_2_candidates"] == []
    assert result["experiment_design_table"] == []
