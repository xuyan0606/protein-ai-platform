from __future__ import annotations


def test_pdb_only_plan_is_explicitly_planned_and_detects_engineered_mutations():
    from app.services.wet_lab_report_contract import build_wet_lab_plan, render_wet_lab_plan_markdown

    plan = build_wet_lab_plan(structure_data={
        "query_structure": {
            "engineered_mutations": [{
                "chain_id": "A", "reference_residue_aa": "E", "reference_position": 142,
                "pdb_residue_aa": "A", "pdb_residue_no": 142,
            }]
        }
    })

    assert plan["schema_version"] == "wet_lab_plan_v1"
    assert plan["status"] == "planned"
    assert plan["evidence_status"] == "not_available"
    assert plan["observed_results_available"] is False
    assert any("A:E142A" in str(item.get("mutation_annotation")) for item in plan["constructs"])
    markdown = render_wet_lab_plan_markdown(plan)
    assert "## 湿实验验证计划" in markdown
    assert "Go / Watch / No-Go" in markdown
    assert "已完成结果=False" in markdown


def test_plan_without_mutation_annotation_does_not_invent_one():
    from app.services.wet_lab_report_contract import build_wet_lab_plan

    plan = build_wet_lab_plan()
    pdb = next(item for item in plan["constructs"] if item["id"] == "PDB_CONSTRUCT")
    assert pdb["mutation_annotation"] == ["突变需核对"]
    assert all(item["status"] == "planned" for item in plan["qc_assays"] + plan["functional_assays"] + plan["stability_assays"])
    assert "β-1,4-mannan" not in str(plan["functional_assays"])
    assert "3 次独立生物重复" in plan["assay_design"]["replicates"]


def test_mannan_substrate_is_conditional_on_pdb_annotation():
    from app.services.wet_lab_report_contract import build_wet_lab_plan

    mannan = build_wet_lab_plan(structure_data={"query_structure": {"compound_annotation": {"molecule": "endo-beta-1,4-mannanase"}}})
    amylase = build_wet_lab_plan(structure_data={"query_structure": {"compound_annotation": {"molecule": "alpha-amylase"}}})
    assert "β-1,4-mannan" in mannan["functional_assays"][0]["name"]
    assert "β-1,4-mannan" not in amylase["functional_assays"][0]["name"]


def test_7dvj_style_construct_matrix_keeps_wt_and_e142a_separate():
    from app.services.wet_lab_report_contract import build_wet_lab_plan, render_wet_lab_plan_markdown

    plan = build_wet_lab_plan(structure_data={
        "query_structure": {
            "compound_annotation": {
                "molecule": "STRUCTURE OF BETA-MANNANASE BAMAN113A WITH MANNOBIOSE",
            },
            "engineered_mutations": [{
                "chain_id": "A",
                "reference_residue_aa": "E",
                "reference_position": 142,
                "pdb_residue_aa": "A",
                "pdb_residue_no": 142,
            }],
        }
    })

    by_id = {item["id"]: item for item in plan["constructs"]}
    assert set(("WT", "PDB_CONSTRUCT", "BACK_MUTATION_IF_NEEDED", "NEGATIVE_CONTROL")) <= set(by_id)
    assert by_id["PDB_CONSTRUCT"]["mutation_annotation"] == ["A:E142A"]
    assert by_id["WT"]["status"] == "planned"
    assert "β-1,4-mannan" in plan["functional_assays"][0]["name"]
    assert plan["observed_results_available"] is False
    markdown = render_wet_lab_plan_markdown(plan)
    assert "WT" in markdown and "A:E142A" in markdown and "BACK_MUTATION_IF_NEEDED" in markdown
    assert "提高活性" not in markdown
    assert "已验证候选" not in markdown
