import asyncio
import json
import pytest
from app.core.agent_graph import AgentOrchestrator, ChatSnapshot, PlanStep
from app.core.agent_graph import _IDENTITY_GATED_CANDIDATE_TOOLS, _OBJECTIVE_GATED_CANDIDATE_TOOLS
from app.tools.registry import ToolRegistry
SEQUENCE = "MKTIIALSYIFCLVFADYKDDDDK"


@pytest.mark.parametrize("sequence,status,code", [
    (SEQUENCE[:-1] + "A", "completed", "M1A"),
    (SEQUENCE, "blocked_missing_model", "M1A"),
    (SEQUENCE, "completed", "K0A"),
    (SEQUENCE, "completed", "M1M"),
])
def test_build_rejects_foreign_blocked_or_invalid_candidates(sequence, status, code):
    from app.core.agent_graph import _assistant_build_candidate_mutations
    scan = PlanStep(1, "mutation_scan", "scan", {"sequence": sequence}, "completed", {
        "status": status, "sequence_length": len(sequence),
        "results": [{"top_stabilizing": [{"mutation": code}]}],
    })
    assert _assistant_build_candidate_mutations([scan], SEQUENCE) == []


def test_build_protection_applies_even_when_priority_step_follows_scan():
    from app.core.agent_graph import _assistant_build_candidate_mutations
    scan = PlanStep(1, "mutation_scan", "scan", {"sequence": SEQUENCE}, "completed", {
        "sequence_length": len(SEQUENCE),
        "results": [{"top_stabilizing": [{"mutation": "K2A"}, {"mutation": "T3V"}]}],
    })
    priority = PlanStep(2, "mutation_priority_score", "rank", {"sequence": SEQUENCE}, "completed", {
        "sequence_length": len(SEQUENCE), "summary": {"never_mutate_positions": [2]},
    })
    assert _assistant_build_candidate_mutations([scan, priority], SEQUENCE) == ["T3V"]


def test_blocked_objective_step_cannot_be_treated_as_absent():
    gate = PlanStep(1, "enzyme_objective_module_plan", "gate", {}, "blocked", {
        "status": "blocked", "candidate_output_allowed": False,
    })
    assert AgentOrchestrator._objective_gate_passed([gate]) is False


async def _collect(stream):
    return [event async for event in stream]


@pytest.mark.parametrize("cached", [False, True])
def test_blocked_tool_is_visible_to_synthesis_and_terminal_contract(monkeypatch, cached):
    agent = AgentOrchestrator()
    AgentOrchestrator._tool_cache.clear()
    step = PlanStep(1, "predict_properties", "properties", {"sequence": SEQUENCE})
    payload = {"status": "blocked_missing_model", "reason": "missing validated model"}
    observed = []
    if cached:
        agent._cache_put(agent._cache_key(step.tool_name, step.params), payload)

    async def route(*args, **kwargs):
        return "analyze"

    async def plan(*args, **kwargs):
        return [step]

    async def execute(*args, **kwargs):
        return payload

    async def synthesize(message, tool_messages, *args, **kwargs):
        observed.append((tool_messages[0]["status"], list(agent._snapshot.execution_trace)))
        return "模型不可用，需要补齐后重试。"

    monkeypatch.setattr(agent, "_route_intent", route)
    monkeypatch.setattr(agent, "_plan_cb", plan)
    monkeypatch.setattr(agent, "_synthesize_sc", synthesize)
    monkeypatch.setattr(ToolRegistry, "execute", execute)
    message = f"分析序列 {SEQUENCE}"
    events = asyncio.run(_collect(agent.stream_chat(
        message, [], agent_control="execute_confirmed",
        confirmed_plan=[{"id": 1, "tool_name": step.tool_name, "description": step.description, "params": step.params}],
        strategy_signature=agent._plan_signature([step]),
        task_fingerprint=agent._task_fingerprint(message, ""),
    )))
    done = json.loads(events[-1])
    assert observed[0][0] == "blocked"
    assert observed[0][1][0]["status"] == "blocked"
    assert done["status"] == "blocked"
    assert done["task_contract"]["final_status"] != "READY"
    AgentOrchestrator._tool_cache.clear()


def test_enzyme_assistant_recommend_is_gated_like_candidate_generation():
    assert "enzyme_assistant_recommend" in _IDENTITY_GATED_CANDIDATE_TOOLS
    assert "enzyme_assistant_recommend" in _OBJECTIVE_GATED_CANDIDATE_TOOLS


def test_assistant_build_receives_only_candidates_that_apply_to_its_sequence():
    priority = PlanStep(1, "mutation_priority_score", "rank", {"sequence": SEQUENCE})
    priority.status = "completed"
    priority.result = {
        "sequence_length": len(SEQUENCE),
        "summary": {"never_mutate_positions": [2]},
        "tier_1_candidates": [
            {"position": 3, "recommended_mutations": [{"mutation": "T3V"}, {"mutation": "X3V"}]},
            {"position": 2, "recommended_mutations": [{"mutation": "K2Q"}]},
        ],
    }
    scan = PlanStep(2, "mutation_scan", "scan", {"sequence": SEQUENCE})
    scan.status = "completed"
    scan.result = {
        "sequence_length": len(SEQUENCE),
        "results": [
            {"top_stabilizing": [{"mutation": "L7A"}, {"mutation": "K7A"}]},
            {"top_stabilizing": [{"mutation": "T3V"}]},
        ],
    }
    stale = PlanStep(3, "mutation_scan", "scan", {"sequence": "MK"})
    stale.status = "completed"
    stale.result = {
        "sequence_length": 2,
        "results": [{"top_stabilizing": [{"mutation": "M1A"}]}],
    }
    build = PlanStep(4, "enzyme_assistant_build", "build", {"sequence": SEQUENCE, "mutations": []})

    AgentOrchestrator._hydrate_step_params(build, [priority, scan, stale])

    # Ranked priority candidates lead; the scan fills the rest. The catalytic
    # position, the mismatched wild-type residue, the malformed code, and the
    # scan of a different sequence never reach the build tool.
    assert build.params["mutations"] == ["T3V", "L7A"]
    assert build.params["mutations_provenance"] == "upstream_candidate_scan"

    # Provenance is orchestration metadata, so it must not fail schema
    # validation when the hydrated step reaches the tool registry.
    ToolRegistry.discover()
    assert ToolRegistry.validate_params(build.tool_name, build.params) == {}


def test_assistant_build_stays_empty_without_usable_candidates():
    scan = PlanStep(1, "mutation_scan", "scan", {"sequence": SEQUENCE})
    scan.status = "completed"
    scan.result = {
        "sequence_length": len(SEQUENCE),
        "results": [{"top_stabilizing": [{"mutation": "A1W"}]}],
    }
    build = PlanStep(2, "enzyme_assistant_build", "build", {"sequence": SEQUENCE, "mutations": []})

    AgentOrchestrator._hydrate_step_params(build, [scan])

    assert build.params["mutations"] == []
    assert "mutations_provenance" not in build.params


def test_assistant_build_without_candidates_is_skipped_not_stage_blocking(monkeypatch):
    ToolRegistry.discover()
    AgentOrchestrator._tool_cache.clear()
    agent = AgentOrchestrator()
    calls = []

    async def route(*args, **kwargs):
        return "analyze"

    async def plan(*args, **kwargs):
        agent._snapshot.workflow_id = "enzyme_thermostability_runtime"
        return [
            PlanStep(
                1, "enzyme_identity_profile", "identify", {"sequence": SEQUENCE},
                stage_id=1, stage_name="identity_and_baseline",
            ),
            PlanStep(
                2, "enzyme_objective_module_plan", "objective", {"objective": "stability"},
                stage_id=1, stage_name="identity_and_baseline",
            ),
            PlanStep(6, "structure_search_foldseek", "structure", {"sequence": SEQUENCE}),
            PlanStep(7, "residue_mapping_sifts", "mapping", {}),
            PlanStep(8, "residue_numbering_gate", "numbering", {}),
            PlanStep(
                3, "mutation_scan", "scan", {"sequence": SEQUENCE},
                stage_id=2, stage_name="stability_evidence_core",
            ),
            PlanStep(
                4, "enzyme_assistant_build", "build", {"sequence": SEQUENCE, "mutations": []},
                stage_id=2, stage_name="stability_evidence_core",
            ),
            PlanStep(
                5, "protein_benchmark", "report", {"query_sequence": SEQUENCE},
                stage_id=3, stage_name="delivery_evidence",
            ),
        ]

    async def execute(name, params):
        calls.append((name, dict(params)))
        if name == "enzyme_identity_profile":
            return {"identity_status": "identified", "guardrail": {"status": "ready"}}
        if name == "enzyme_objective_module_plan":
            return {"status": "ready", "candidate_output_allowed": True}
        if name == "structure_search_foldseek":
            return {"status": "completed", "query_structure": {"chain_count": 1}}
        if name == "residue_mapping_sifts":
            return {"status": "completed", "found": True}
        if name == "residue_numbering_gate":
            return {"status": "allowed"}
        if name == "mutation_scan":
            return {"sequence_length": len(SEQUENCE), "results": [{"top_stabilizing": [{"mutation": "A1W"}]}]}
        if name == "protein_benchmark":
            return {"status": "completed", "summary": "benchmark"}
        raise AssertionError(f"{name} must not execute without usable candidates")

    async def synthesize(*args, **kwargs):
        return "Deterministic report"

    monkeypatch.setattr(agent, "_route_intent", route)
    monkeypatch.setattr(agent, "_plan_cb", plan)
    monkeypatch.setattr(agent, "_synthesize_sc", synthesize)
    monkeypatch.setattr(ToolRegistry, "execute", execute)

    async def execute_confirmed_plan():
        message = f"提高热稳定性 {SEQUENCE}"
        agent._snapshot = ChatSnapshot(stage="plan")
        frozen = await plan()
        for index, step in enumerate(frozen, 1):
            step.id = index
        return await _collect(agent.stream_chat(
            message, [], agent_control="execute_confirmed",
            confirmed_plan=[{"id": step.id, "tool_name": step.tool_name, "description": step.description, "params": step.params} for step in frozen],
            strategy_signature=agent._plan_signature(frozen),
            task_fingerprint=agent._task_fingerprint(message, ""),
        ))

    asyncio.run(execute_confirmed_plan())

    assert [name for name, _ in calls] == [
        "enzyme_identity_profile",
        "enzyme_objective_module_plan",
        "structure_search_foldseek", "residue_mapping_sifts", "residue_numbering_gate",
        "mutation_scan",
        "protein_benchmark",
    ]
    build_trace = next(
        item for item in agent._snapshot.execution_trace
        if item.get("tool") == "enzyme_assistant_build"
    )
    assert build_trace["status"] == "skipped"
    assert "no completed upstream scan" in build_trace["result_preview"]


def test_assistant_build_executes_with_hydrated_candidates(monkeypatch):
    ToolRegistry.discover()
    AgentOrchestrator._tool_cache.clear()
    agent = AgentOrchestrator()
    calls = []

    async def route(*args, **kwargs):
        return "analyze"

    async def plan(*args, **kwargs):
        agent._snapshot.workflow_id = "enzyme_thermostability_runtime"
        return [
            PlanStep(
                1, "enzyme_identity_profile", "identify", {"sequence": SEQUENCE},
                stage_id=1, stage_name="identity_and_baseline",
            ),
            PlanStep(
                2, "enzyme_objective_module_plan", "objective", {"objective": "stability"},
                stage_id=1, stage_name="identity_and_baseline",
            ),
            PlanStep(6, "structure_search_foldseek", "structure", {"sequence": SEQUENCE}),
            PlanStep(7, "residue_mapping_sifts", "mapping", {}),
            PlanStep(8, "residue_numbering_gate", "numbering", {}),
            PlanStep(
                3, "mutation_scan", "scan", {"sequence": SEQUENCE},
                stage_id=2, stage_name="stability_evidence_core",
            ),
            PlanStep(
                4, "enzyme_assistant_build", "build", {"sequence": SEQUENCE, "mutations": []},
                stage_id=2, stage_name="stability_evidence_core",
            ),
            PlanStep(
                5, "protein_benchmark", "report", {"query_sequence": SEQUENCE},
                stage_id=3, stage_name="delivery_evidence",
            ),
        ]

    async def execute(name, params):
        calls.append((name, dict(params)))
        if name == "enzyme_identity_profile":
            return {"identity_status": "identified", "guardrail": {"status": "ready"}}
        if name == "enzyme_objective_module_plan":
            return {"status": "ready", "candidate_output_allowed": True}
        if name == "structure_search_foldseek":
            return {"status": "completed", "query_structure": {"chain_count": 1}}
        if name == "residue_mapping_sifts":
            return {"status": "completed", "found": True}
        if name == "residue_numbering_gate":
            return {"status": "allowed"}
        if name == "mutation_scan":
            return {"sequence_length": len(SEQUENCE), "results": [{"top_stabilizing": [{"mutation": "T3V"}]}]}
        if name == "enzyme_assistant_build":
            return {"status": "ok", "mutant_protein": "MKVIIALSYIFCLVFADYKDDDDK"}
        if name == "protein_benchmark":
            return {"status": "completed", "summary": "benchmark"}
        raise AssertionError(f"unexpected tool call: {name}")

    async def synthesize(*args, **kwargs):
        return "Deterministic report"

    monkeypatch.setattr(agent, "_route_intent", route)
    monkeypatch.setattr(agent, "_plan_cb", plan)
    monkeypatch.setattr(agent, "_synthesize_sc", synthesize)
    monkeypatch.setattr(ToolRegistry, "execute", execute)

    async def execute_confirmed_plan():
        message = f"提高热稳定性 {SEQUENCE}"
        agent._snapshot = ChatSnapshot(stage="plan")
        frozen = await plan()
        for index, step in enumerate(frozen, 1):
            step.id = index
        return await _collect(agent.stream_chat(
            message, [], agent_control="execute_confirmed",
            confirmed_plan=[{"id": step.id, "tool_name": step.tool_name, "description": step.description, "params": step.params} for step in frozen],
            strategy_signature=agent._plan_signature(frozen),
            task_fingerprint=agent._task_fingerprint(message, ""),
        ))

    asyncio.run(execute_confirmed_plan())

    assert [name for name, _ in calls] == [
        "enzyme_identity_profile",
        "enzyme_objective_module_plan",
        "structure_search_foldseek", "residue_mapping_sifts", "residue_numbering_gate",
        "mutation_scan",
        "enzyme_assistant_build",
        "protein_benchmark",
    ]
    build_params = next(params for name, params in calls if name == "enzyme_assistant_build")
    assert build_params["mutations"] == ["T3V"]
    assert build_params["mutations_provenance"] == "upstream_candidate_scan"
    build_trace = next(
        item for item in agent._snapshot.execution_trace
        if item.get("tool") == "enzyme_assistant_build"
    )
    assert build_trace["status"] == "completed"


def test_early_intake_completion_persists_needs_input_task_contract():
    agent = AgentOrchestrator()
    events = asyncio.run(_collect(agent.stream_chat(
        "提高热稳定性",
        [],
        agent_control="plan_only",
    )))
    done = next(event for event in reversed(events) if '"type": "done"' in event)
    payload = json.loads(done)

    assert payload["task_contract"]["intent"] == "NEW_TASK"
    assert payload["task_contract"]["final_status"] == "NEEDS_INPUT"
    assert payload["task_contract"]["input_gaps"] == ["enzyme_sequence_or_structure_or_accession"]

    # Every terminal event must expose the same envelope, including early
    # intake exits.  Wiki/history restoration consumes these fields directly.
    assert payload["type"] == "done"
    assert payload["status"] == "blocked"
    assert payload["blocked_reason"]
    assert payload["objective"] == payload["task_contract"]["primary_property"]
    assert payload["workflow_id"] is None
    assert payload["missing_capabilities"] == []
    assert payload["execution_trace"] == []


def test_done_event_serializes_snapshot_terminal_fields_consistently():
    agent = AgentOrchestrator()
    agent._snapshot = ChatSnapshot(
        stage="done",
        objective="specific_activity",
        workflow_id="enzyme_specific_activity_runtime_v1",
        blocked_reason="missing WT baseline",
        missing_capabilities=["specific_activity_baseline"],
        execution_trace=[{
            "step": 1,
            "tool": "enzyme_objective_module_plan",
            "status": "blocked",
            "reason": "missing WT baseline",
        }],
        task_contract={
            "intent": "NEW_TASK",
            "primary_property": "specific_activity",
            "final_status": "NEEDS_REVIEW",
        },
    )

    payload = json.loads(agent._emit_done_event())

    assert payload == {
        "type": "done",
        "status": "blocked",
        "blocked_reason": "missing WT baseline",
        "objective": "specific_activity",
        "workflow_id": "enzyme_specific_activity_runtime_v1",
        "missing_capabilities": ["specific_activity_baseline"],
        "task_contract": agent._snapshot.task_contract,
        "execution_trace": agent._snapshot.execution_trace,
    }
