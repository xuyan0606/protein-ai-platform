"""End-to-end planning and reporting regressions for explicit site-design requests."""

import copy
import json

import pytest

from app.core.agent_graph import AgentOrchestrator
from app.tools.registry import ToolRegistry


def tool_result(name, payload):
    return {"tool_name": name, "status": "completed", "result": json.dumps(payload)}


@pytest.fixture
def orchestrator():
    ToolRegistry.discover()
    return AgentOrchestrator()


@pytest.fixture
def planner(orchestrator, monkeypatch):
    structure = {
        "status": "readable", "display_name": "input.pdb", "chain_count": 1,
        "total_residues": 30, "total_atoms": 120, "method": "X-RAY DIFFRACTION",
        "chains": [{"chain_id": "B", "sequence": "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLM",
                    "residue_count": 30, "residue_range": [11, 40]}],
        "nonpolymer_components": [], "disulfide_count": 0,
    }
    structure["coordinate_sequence"] = structure["chains"][0]["sequence"]

    async def preflight(task):
        return copy.deepcopy(structure)

    async def experience(*args):
        return ""

    monkeypatch.setattr(orchestrator, "_build_pdb_preflight_summary", preflight)
    monkeypatch.setattr(orchestrator, "_get_experience_hints", experience)
    monkeypatch.setattr("app.core.agent_graph._structure_runtime_capabilities", lambda: {
        "foldseek": False, "pocket": False, "esm2": False,
    })
    return orchestrator


def site_task():
    return ("提升比活力分析位点\n[Attached files:\n"
            "name: input.pdb, object_name: uploads/user_999/input.pdb]")


async def test_standard_site_request_keeps_function_and_structure_evidence_after_adaptation(planner):
    steps = await planner._plan_cb(site_task(), "", [], analysis_depth="standard")
    names = {step.tool_name for step in steps}
    assert {
        "enzyme_identity_profile", "enzyme_objective_module_plan",
        "build_site_structure_function_features", "mutation_priority_score",
    } <= names
    assert all(step.params.get("chain_id") in (None, "B") for step in steps)


async def test_deep_site_request_does_not_lose_geometry_step_during_adaptation(planner):
    # This coordinate-only tool remains useful without external P2Rank/fpocket.
    steps = await planner._plan_cb(site_task(), "", [], analysis_depth="deep")
    geometry = next((step for step in steps
                     if step.tool_name == "structure_pocket_interface_analysis"), None)
    assert geometry is not None
    assert geometry.params["pdb_object_name"] == "uploads/user_999/input.pdb"
    assert geometry.params.get("chain_scope") == ["B"]


async def test_attachment_pdb_basename_cannot_bind_unverified_reference_identity(planner):
    # Naming an unrelated uploaded construct 1BLI.pdb is not an identity match.
    task = site_task().replace("input.pdb", "1BLI.pdb")
    steps = await planner._plan_cb(task, "", [], analysis_depth="standard")
    parsed = next(step for step in steps if step.tool_name == "structure_search_foldseek")
    assert "pdb_id" not in parsed.params
    profile = next(step for step in steps if step.tool_name == "enzyme_identity_profile")
    assert profile.params["structure_id"] == "uploaded_pdb_coordinate_model"


def candidate_evidence(*, objective_ready=True):
    return [
        tool_result("structure_search_foldseek", {
            "status": "completed", "query_structure": {
                "total_residues": 194, "total_atoms": 1500,
                "chains": [{"chain_id": "A", "residue_count": 194}],
            },
        }),
        tool_result("build_site_structure_function_features", {
            "status": "completed", "features": [{
                "chain_id": "A", "position": 42, "wild_type": "G",
                "rel_sasa": 0.3, "rel_sasa_status": "computed_from_input_pdb",
            }],
        }),
        tool_result("structure_pocket_interface_analysis", {
            "status": "completed", "evidence_level": "GEOMETRY_ONLY",
            "pocket": {"residues": []}, "channels": {"clues": []},
        }),
        tool_result("mutation_priority_score", {
            "candidate_table_status": "ready" if objective_ready else "exploratory_requires_objective_evidence",
            "identity_gate": {
                "status": "passed", "identity_status": "identified",
                "protected_positions_from_profile": [10],
            },
            "objective_gate": {
                "status": "ready" if objective_ready else "blocked",
                "candidate_output_allowed": objective_ready,
                "missing_evidence": [] if objective_ready else ["substrate identity and assay context"],
            },
            "experiment_design_table": [{
                "position": 42, "wild_type": "G", "recommended_mutations": ["G42A"],
                "experiment_priority": "P1" if objective_ready else "P2-探索",
                "candidate_evidence_status": "computational_hypothesis",
                "mutation_logic": "Candidate hypothesis requiring WT comparison",
            }],
        }),
    ]


def test_embedded_ready_gates_do_not_get_a_contradictory_no_candidates_section(orchestrator):
    # Scorer results can carry the already-validated gates without separate cards.
    report = orchestrator._build_fallback_report("提升比活力分析位点", candidate_evidence())
    assert "G42A" in report
    assert "未输出具体位点→替换氨基酸清单" not in report
    assert "正式候选=0" not in report


def test_objective_blocked_rows_do_not_leak_as_site_substitution_suggestions(orchestrator):
    report = orchestrator._build_fallback_report(
        "提升比活力分析位点", candidate_evidence(objective_ready=False),
    )
    assert "G42A" not in report
    assert "正式候选=0" in report
    assert "substrate identity and assay context" in report


def test_llm_old_exploration_heading_cannot_bypass_missing_evidence(orchestrator):
    results = candidate_evidence()[:1]
    report = orchestrator._append_requested_pdb_site_hypotheses(
        "## PDB坐标探索性位点预筛\nG42A improves activity.",
        "提升比活力分析位点", results,
    )
    assert "G42A" not in report
    assert "未输出具体位点→替换氨基酸清单" in report


def test_standalone_blocked_guardrail_overrules_scorer_ready_label(orchestrator):
    results = candidate_evidence()
    results.insert(1, tool_result("enzyme_identity_profile", {
        "identity_status": "identified", "guardrail": {"status": "blocked"},
        "protected_positions": [10],
    }))
    report = orchestrator._build_fallback_report("提升比活力分析位点", results)
    assert "G42A" not in report
    assert "正式候选=0" in report
    assert "能否下单**：不能直接下单" in report


def test_unresolved_embedded_identity_overrules_scorer_ready_label(orchestrator):
    results = candidate_evidence()
    score = json.loads(results[-1]["result"])
    score["identity_gate"] = {"status": "exploratory", "identity_status": "unresolved"}
    results[-1] = tool_result("mutation_priority_score", score)
    report = orchestrator._build_fallback_report("提升比活力分析位点", results)
    assert "G42A" not in report
    assert "正式候选=0" in report
    assert "能否下单**：不能直接下单" in report
