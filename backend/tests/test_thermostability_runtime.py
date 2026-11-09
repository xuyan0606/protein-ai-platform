import hashlib
import json

import pytest

from app.core.workflows import WorkflowRegistry
from app.services.thermostability_workflow import build_screen
from app.services.scheduler import _ensure_tool_registry_ready, get_execution_mode, get_task_profile
from app.tools.registry import ToolRegistry

SEQ = "ACDEG"
SHA = hashlib.sha256(SEQ.encode()).hexdigest()
OBJ = {"endpoint": "tm", "method": "DSC", "ph": 7, "substrate": "none", "buffer": "PBS",
       "cofactors": "none", "min_activity_retention_pct": 80}
ID = {"identity_status": "identified", "guardrail": {"status": "ready"},
      "query": {"sequence_sha256": SHA}, "protected_positions": []}
MODULE = {"status": "ready", "candidate_output_allowed": True, "objective": "thermostability"}


def test_thermal_plan_does_not_force_md_prediction_or_other_large_models():
    ToolRegistry.discover()
    plan = WorkflowRegistry.build_plan("thermostability", SEQ,
        "耐热筛选 A1V thermal_assay: " + json.dumps(OBJ), set(ToolRegistry._tools))
    assert plan.blocked_reason is None
    names = {s["tool_name"] for s in plan.steps}
    assert "thermostability_candidate_workflow" in names
    assert not names & {"gromacs_md", "esmfold_folding", "thermompnn_predict", "interproscan_sequence_submit", "rfdiffusion_design"}
    step = next(s for s in plan.steps if s["tool_name"] == "thermostability_candidate_workflow")
    assert step["params"]["objective"] == OBJ
    assert step["params"]["mutations"] == ["A1V"]
    assert step["params"].get("run_ddgun") is not True


def test_partial_worker_registry_discovers_the_requested_missing_tool(monkeypatch):
    calls = []
    monkeypatch.setattr(ToolRegistry, "_tools", {"blast_search": object()})
    monkeypatch.setattr(ToolRegistry, "discover", lambda: calls.append(True))
    _ensure_tool_registry_ready("ddgun_predict")
    assert calls == [True]
    calls.clear()
    _ensure_tool_registry_ready("blast_search")
    assert calls == []
    assert get_execution_mode("thermostability_candidate_workflow") == "async_worker"
    assert get_task_profile("thermostability_candidate_workflow").time_limit >= 1800


@pytest.mark.parametrize("extra", [
    {"candidate_sources": [None]}, {"candidate_sources": [{"mutations": "A1V"}]},
    {"mapping_rows": [None]}, {"protected_sites": [{"position": "oops"}]},
    {"identity_profile": {**ID, "protected_positions": ["bad"]}},
    {"objective": {**OBJ, "endpoint": "half_life", "temperature_c": 1e8}},
    {"objective": {**OBJ, "endpoint": []}},
])
def test_malformed_evidence_is_a_controlled_non_candidate_outcome(extra):
    data = dict(sequence=SEQ, objective=OBJ, identity_profile=ID, objective_module_plan=MODULE, mutations=["A1V"])
    data.update(extra)
    result = build_screen(**data)
    assert result["status"] in {"blocked", "needs_input"}
    assert result["candidates"] == []


def test_input_sequence_numbering_does_not_imply_known_full_length_boundary():
    result = build_screen(SEQ, OBJ, ID, MODULE, mutations=["A1V"])
    assert result["candidates"][0]["full_length_position"] is None
    assert result["coordinate_system"] == "input_sequence_1based"


def test_ready_module_for_another_objective_does_not_authorize_thermal_candidates():
    result = build_screen(SEQ, OBJ, ID, {**MODULE, "objective": "specific_activity"}, mutations=["A1V"])
    assert result["status"] == "blocked"
    assert "thermostability_objective_module_required" in result["blockers"]


def test_oversized_mutation_position_is_a_rejection_not_an_exception():
    result = build_screen(SEQ, OBJ, ID, MODULE, mutations=["A" + "9" * 5000 + "V"])
    assert result["candidates"] == []
    assert result["rejected"][0]["reasons"] == ["invalid_substitution"]


@pytest.mark.asyncio
async def test_offline_composite_cannot_invoke_any_external_or_model_branch(monkeypatch):
    from app.tools import thermostability_adapters as adapters
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    async def forbidden(*args, **kwargs):
        raise AssertionError("offline must prevent this call")
    monkeypatch.setattr(adapters, "ddgun_predict", forbidden)
    monkeypatch.setattr(adapters, "colabfold_predict", forbidden)
    monkeypatch.setattr(adapters, "evcouplings_analyze", forbidden)
    result = await thermostability_candidate_workflow(SEQ, OBJ, ID, MODULE, mutations=["A1V"],
        offline=True, run_ddgun=True, run_colabfold=True, run_coevolution=True, run_esm=True)
    assert result["candidates"][0]["mutation"] == "A1V"
    assert all(result["branches"][key]["reason"] == "user_execution_constraint"
               for key in ("ddgun", "esm", "colabfold", "coevolution"))


@pytest.mark.asyncio
async def test_explicit_database_ban_also_applies_inside_composite(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    async def forbidden(*args, **kwargs):
        raise AssertionError("explicit database ban must prevent this call")
    monkeypatch.setattr("app.tools.data_lookup.get_stability_data", forbidden)
    result = await thermostability_candidate_workflow(SEQ, OBJ, ID, MODULE, mutations=["A1V"],
        run_database_lookup=True, forbidden_tools=["get_stability_data"])
    assert result["branches"]["database"]["reason"] == "user_execution_constraint"


@pytest.mark.asyncio
@pytest.mark.parametrize("hit", [False, True])
async def test_database_no_hit_does_not_empty_other_sources_and_exact_sequence_hit_adds_union(monkeypatch, hit):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    async def query(uniprot_id):
        return {"status": "ok" if hit else "no_hit", "found": hit, "protein_sequence_sha256": SHA,
                "records": [{"mutation": "D3N", "dtm": 2, "literature_ref": "doi:test"}] if hit else []}
    monkeypatch.setattr("app.tools.data_lookup.get_stability_data", query)
    result = await thermostability_candidate_workflow(SEQ, OBJ, ID, MODULE, mutations=["A1V"],
                    run_database_lookup=True, uniprot_id="P00123")
    assert {r["mutation"] for r in result["candidates"]} == ({"A1V", "D3N"} if hit else {"A1V"})
    if hit:
        known = next(r for r in result["candidates"] if r["mutation"] == "D3N")
        assert "reported_assay_transfer_requires_review" in known["risks"]


@pytest.mark.asyncio
async def test_registered_tool_submit_reaches_guarded_workflow(client, session, monkeypatch):
    from app.models.user import User
    from app.core.security import create_access_token
    user = User(email="thermal-route@example.com", name="Thermal route", role="researcher", hashed_password="test")
    session.add(user)
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    captured = {}
    def dispatch(name, params):
        captured.update(name=name, params=params)
        return "thermal-test-task"
    monkeypatch.setattr("app.api.tools.dispatch_tool", dispatch)
    response = await client.post("/api/tools/thermostability_candidate_workflow/submit", json={"params": {
        "sequence": SEQ, "objective": OBJ, "identity_profile": ID, "objective_module_plan": MODULE,
        "mutations": ["A1V"],
    }})
    assert response.status_code == 200
    assert response.json()["task_id"] == "thermal-test-task"
    result = await ToolRegistry.execute(captured["name"], captured["params"])
    assert result["candidates"][0]["mutation"] == "A1V"
    assert result["sequence_sha256"] == SHA
