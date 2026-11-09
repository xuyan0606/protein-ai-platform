from app.core.workflows import WorkflowRegistry


def test_p00691_anchor_is_propagated_into_identity_workflow_steps():
    available = {
        "enzyme_input_gate", "annotation_bundle", "blast_search", "catalytic_site_lookup", "enzyme_identity_profile",
        "protein_benchmark", "esmfold_folding", "predict_properties", "disulfide_saltbridge_scan",
        "mutation_scan", "mutation_priority_score", "thermompnn_predict", "gromacs_md",
        "enzyme_assistant_recommend", "enzyme_assistant_build",
        "thermostability_candidate_workflow",
    }
    plan = WorkflowRegistry.build_plan(
        "thermostability", "M" * 100, "P00691 提高热稳定性", available
    )
    assert plan is not None and plan.blocked_reason is None
    identity_steps = [step for step in plan.steps if step["tool_name"] in {"annotation_bundle", "catalytic_site_lookup", "enzyme_identity_profile"}]
    assert identity_steps
    assert all(step["params"]["uniprot_id"] == "P00691" for step in identity_steps)
