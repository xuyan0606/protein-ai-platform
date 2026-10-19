from app.services.property_workflow_governance import (
    PropertyWorkflowRouter,
    WorkflowPolicyValidator,
    evaluate_shadow_cases,
)


def test_scheduler_execution_mode_is_distinct_from_registry_async_flag():
    from app.services.scheduler import get_execution_mode
    from app.tools.registry import ToolRegistry

    ToolRegistry.discover()
    assert len(ToolRegistry._tools) == 62
    assert get_execution_mode("gromacs_md") == "async_worker"
    assert get_execution_mode("mutation_priority_score") == "inline_sync"


def test_router_keeps_preservation_constraint_out_of_optimization_targets():
    result = PropertyWorkflowRouter.route("提高热稳定性，但活性不能下降")

    assert result["workflow_id"] == "WF-STABILITY"
    assert result["optimization_targets"] == ["stability"]
    assert result["secondary_properties"] == []
    assert "activity_not_drop" in result["preservation_constraints"]


def test_router_requires_primary_property_when_multiple_goals_are_unordered():
    result = PropertyWorkflowRouter.route("同时提高活性和特异性")

    assert result["status"] == "NEEDS_INPUT"
    assert result["workflow_id"] is None
    assert "primary_property" in result["input_gaps"]


def test_router_accepts_explicit_primary_and_secondary_goal():
    result = PropertyWorkflowRouter.route("主目标提高稳定性，同时提高活性")

    assert result["workflow_id"] == "WF-STABILITY"
    assert result["primary_property"] == "stability"
    assert result["secondary_properties"] == ["activity"]


def test_stability_validator_rejects_forbidden_tool_and_missing_must_step():
    plan = [
        {"step_id": "ST-01", "status": "completed", "tool_id": "intake_review"},
        {"step_id": "ST-06", "status": "completed", "tool_id": "mutation_scan"},
        {"step_id": "ST-07", "status": "completed", "tool_id": "mutation_priority_score"},
        {"step_id": "ST-12", "status": "completed", "tool_id": "report_generator"},
        {"step_id": "X-01", "status": "completed", "tool_id": "diffdock_docking"},
    ]

    result = WorkflowPolicyValidator.validate("WF-STABILITY", plan)

    assert result["status"] == "NEEDS_REVIEW"
    assert "ST-02" in result["missing_must_steps"]
    assert any(item["tool_id"] == "diffdock_docking" for item in result["forbidden_tool_calls"])


def test_stability_validator_accepts_declared_plan_with_optional_skip_reason():
    plan = [
        {"step_id": "ST-01", "status": "completed", "tool_id": "intake_review"},
        {"step_id": "ST-02", "status": "completed", "tool_id": "tool_capability_audit"},
        {"step_id": "ST-03", "status": "completed", "tool_id": "enzyme_identity_profile"},
        {"step_id": "ST-04", "status": "completed", "tool_id": "get_stability_data"},
        {"step_id": "ST-05", "status": "completed", "tool_id": "residue_numbering_gate"},
        {"step_id": "ST-06", "status": "completed", "tool_id": "mutation_scan"},
        {"step_id": "ST-07", "status": "completed", "tool_id": "mutation_priority_score"},
        {"step_id": "ST-08", "status": "skipped", "tool_id": None, "skip_reason": "single_mutant_only"},
        {"step_id": "ST-09", "status": "skipped", "tool_id": None, "skip_reason": "no_structure_requested"},
        {"step_id": "ST-10", "status": "skipped", "tool_id": None, "skip_reason": "no_activity_constraint"},
        {"step_id": "ST-11", "status": "completed", "tool_id": "scientific_claim_gate"},
        {"step_id": "ST-12", "status": "completed", "tool_id": "report_generator"},
    ]

    result = WorkflowPolicyValidator.validate("WF-STABILITY", plan)

    assert result["status"] == "READY"
    assert result["missing_must_steps"] == []
    assert result["forbidden_tool_calls"] == []


def test_declared_tool_policy_blocks_forbidden_tool_before_confirmation():
    result = WorkflowPolicyValidator.validate_declared_tools(
        "WF-STABILITY", ["enzyme_identity_profile", "diffdock_docking"]
    )

    assert result["status"] == "NEEDS_REVIEW"
    assert result["forbidden_tool_calls"] == ["diffdock_docking"]


def test_property_workflow_catalogs_allow_only_their_declared_tools():
    activity = WorkflowPolicyValidator.validate_declared_tools(
        "WF-ACTIVITY", ["mutation_priority_score", "diffdock_docking"]
    )
    specificity = WorkflowPolicyValidator.validate_declared_tools(
        "WF-SPECIFICITY", ["mutation_priority_score", "ligandmpnn_design"]
    )
    expression = WorkflowPolicyValidator.validate_declared_tools(
        "WF-EXPRESSION", ["soluble_mpnn_design", "signal_peptide_predict"]
    )
    ph = WorkflowPolicyValidator.validate_declared_tools(
        "WF-PH", ["get_kinetic_params", "mutation_epistasis_check"]
    )

    assert activity["status"] == "READY"
    assert specificity["status"] == "READY"
    assert expression["status"] == "READY"
    assert ph["status"] == "READY"


def test_property_workflow_catalogs_fail_closed_for_unknown_or_forbidden_tools():
    unknown = WorkflowPolicyValidator.validate_declared_tools(
        "WF-ACTIVITY", ["mutation_priority_score", "unregistered_experiment_tool"]
    )
    forbidden = WorkflowPolicyValidator.validate_declared_tools(
        "WF-EXPRESSION", ["soluble_mpnn_design", "diffdock_docking"]
    )

    assert unknown["status"] == "NEEDS_REVIEW"
    assert unknown["unknown_tool_calls"] == ["unregistered_experiment_tool"]
    assert forbidden["status"] == "NEEDS_REVIEW"
    assert forbidden["forbidden_tool_calls"] == ["diffdock_docking"]


def test_shadow_route_endpoint_is_registered_without_dispatching_tools():
    from app.main import app

    route = next(item for item in app.routes if item.path == "/api/tools/workflows/shadow-route")
    assert "POST" in route.methods


def test_shadow_comparison_reports_forbidden_legacy_tools_without_blocking():
    from app.services.property_workflow_governance import compare_legacy_plan

    result = compare_legacy_plan(
        "提高热稳定性，但活性不能下降",
        ["enzyme_identity_profile", "mutation_scan", "diffdock_docking"],
    )

    assert result["mode"] == "shadow"
    assert result["route"]["workflow_id"] == "WF-STABILITY"
    assert result["observed_tool_count"] == 3
    assert result["forbidden_tools"] == ["diffdock_docking"]
    assert result["dispatch_blocked"] is False


def test_agent_state_exposes_shadow_route_without_changing_plan():
    import json

    from app.core.agent_graph import AgentOrchestrator, ChatSnapshot

    orch = AgentOrchestrator()
    orch._snapshot = ChatSnapshot(
        stage="plan",
        plan=[{"id": 1, "tool_name": "mutation_scan"}],
        workflow_shadow={"mode": "shadow", "dispatch_blocked": False},
    )
    payload = json.loads(orch._emit_state())

    assert payload["plan"] == [{"id": 1, "tool_name": "mutation_scan"}]
    assert payload["workflow_shadow"]["dispatch_blocked"] is False


def test_shadow_case_evaluator_requires_target_and_constraint_precision():
    cases = [
        {"id": "stability", "message": "提高热稳定性，但活性不能下降", "workflow_id": "WF-STABILITY"},
        {"id": "ph", "message": "提高目标 pH 下活性", "workflow_id": "WF-PH"},
        {"id": "activity", "message": "提高催化效率", "workflow_id": "WF-ACTIVITY"},
        {"id": "specificity", "message": "提高底物特异性", "workflow_id": "WF-SPECIFICITY"},
        {"id": "expression", "message": "提高可溶性表达", "workflow_id": "WF-EXPRESSION"},
        {"id": "ambiguous", "message": "同时提高活性和特异性", "status": "NEEDS_INPUT"},
    ]

    report = evaluate_shadow_cases(cases)

    assert report["case_count"] == 6
    assert report["passed"] == 6
    assert report["failed"] == 0
    assert report["constraint_leak_count"] == 0


def test_router_does_not_start_workflow_for_explanation_question():
    result = PropertyWorkflowRouter.route("热稳定性是什么意思？")

    assert result["intent"] == "NON_EXECUTION"
    assert result["status"] == "NOT_APPLICABLE"
    assert result["workflow_id"] is None


def test_router_handles_explicit_exclusion_and_preservation_direction():
    result = PropertyWorkflowRouter.route("不要优化活性，只提高稳定性，表达量保持不变")

    assert result["workflow_id"] == "WF-STABILITY"
    assert result["optimization_targets"] == ["stability"]
    assert result["preservation_constraints"] == ["activity_not_optimize", "expression_not_drop"]


def test_evaluator_checks_expected_route_fields_not_only_workflow():
    report = evaluate_shadow_cases([{
        "id": "wrong_primary",
        "message": "提高催化效率",
        "workflow_id": "WF-ACTIVITY",
        "primary_property": "stability",
    }])

    assert report["failed"] == 1
    assert report["results"][0]["failures"] == ["primary_property"]


async def test_shadow_route_http_endpoint_is_authenticated_and_tool_free(client, session):
    from app.core.security import create_access_token
    from app.models.user import User

    anonymous = await client.post(
        "/api/tools/workflows/shadow-route",
        json={"message": "提高热稳定性，但活性不能下降"},
    )
    assert anonymous.status_code == 401

    user = User(
        email="workflow-shadow@example.com",
        hashed_password=User.hash_password("password123"),
        name="Workflow Shadow",
    )
    session.add(user)
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.post(
        "/api/tools/workflows/shadow-route",
        json={"message": "提高热稳定性，但活性不能下降"},
    )

    assert response.status_code == 200
    assert response.json()["route"]["workflow_id"] == "WF-STABILITY"
    assert response.json()["dispatch_performed"] is False


async def test_chat_sse_emits_shadow_route_without_tool_dispatch(monkeypatch):
    import json

    from app.core.agent_graph import AgentOrchestrator
    from app.tools.registry import ToolRegistry

    async def fail_execute(*args, **kwargs):
        raise AssertionError("shadow routing must not dispatch tools")

    orchestrator = AgentOrchestrator()
    monkeypatch.setattr(ToolRegistry, "execute", fail_execute)
    events = []
    async for raw in orchestrator.stream_chat(
        "帮我改造这个酶提高热稳定性，但活性不能下降",
        [],
        agent_control="plan_only",
    ):
        events.append(json.loads(raw))

    states = [event for event in events if event.get("type") == "state"]
    assert states
    assert states[0]["workflow_shadow"]["workflow_id"] == "WF-STABILITY"
    assert states[-1]["waiting_for"] == "clarification"
    assert events[-1]["type"] == "done"


async def test_shadow_audit_persists_redacted_route_and_is_user_scoped(session):
    from app.models.user import User
    from app.services.property_workflow_audit import list_shadow_audits, persist_shadow_audit

    owner = User(email="shadow-owner@example.com", hashed_password=User.hash_password("password123"), name="Owner")
    intruder = User(email="shadow-intruder@example.com", hashed_password=User.hash_password("password123"), name="Intruder")
    session.add_all([owner, intruder])
    await session.flush()
    message = "提高热稳定性 MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"

    row = await persist_shadow_audit(
        session,
        user_id=owner.id,
        conversation_id=None,
        project_id=None,
        message=message,
        shadow={"mode": "shadow", "route": PropertyWorkflowRouter.route(message), "observed_tools": ["mutation_scan"], "forbidden_tools": []},
    )

    assert row["message_fingerprint"]
    assert row["workflow_id"] == "WF-STABILITY"
    assert "MKTVRQ" not in str(row)
    assert len(await list_shadow_audits(session, user_id=owner.id)) == 1
    assert await list_shadow_audits(session, user_id=intruder.id) == []


async def test_shadow_audit_api_lists_only_current_user(client, session):
    from app.core.security import create_access_token
    from app.models.user import User
    from app.services.property_workflow_audit import persist_shadow_audit

    owner = User(email="shadow-api-owner@example.com", hashed_password=User.hash_password("password123"), name="Owner")
    other = User(email="shadow-api-other@example.com", hashed_password=User.hash_password("password123"), name="Other")
    session.add_all([owner, other])
    await session.flush()
    await persist_shadow_audit(session, user_id=owner.id, conversation_id=None, project_id=None, message="提高稳定性", shadow={"route": PropertyWorkflowRouter.route("提高稳定性")})
    await persist_shadow_audit(session, user_id=other.id, conversation_id=None, project_id=None, message="提高活性", shadow={"route": PropertyWorkflowRouter.route("提高活性")})
    await session.commit()
    client.cookies.set("pa_token", create_access_token(owner.id))

    response = await client.get("/api/tools/workflows/shadow-audits")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["audits"][0]["workflow_id"] == "WF-STABILITY"


async def test_plan_only_chat_persists_one_redacted_shadow_audit(session, monkeypatch):
    import json

    from app.core.agent_graph import AgentOrchestrator, PlanStep
    from app.models.user import User
    from app.services.property_workflow_audit import list_shadow_audits

    user = User(email="shadow-chat-owner@example.com", hashed_password=User.hash_password("password123"), name="Owner")
    session.add(user)
    await session.flush()
    orchestrator = AgentOrchestrator()

    async def empty_research(*args, **kwargs):
        return ""

    async def one_safe_plan(message, *args, **kwargs):
        return [PlanStep(1, "predict_properties", "baseline", {"sequence": "MKTVRQERLKSIVRILERSK"})]

    monkeypatch.setattr(orchestrator, "_research_pi", empty_research)
    monkeypatch.setattr(orchestrator, "_plan_cb", one_safe_plan)
    events = []
    async for raw in orchestrator.stream_chat(
        "提高热稳定性 MKTVRQERLKSIVRILERSK",
        [],
        current_user={"id": user.id},
        audit_session=session,
        agent_control="plan_only",
    ):
        events.append(json.loads(raw))

    audits = await list_shadow_audits(session, user_id=user.id)
    assert len(audits) == 1
    assert audits[0]["workflow_id"] == "WF-STABILITY"
    assert "MKTVRQ" not in str(audits[0])
    assert any(event.get("type") == "state" and event.get("workflow_shadow", {}).get("mode") == "shadow" for event in events)


async def test_runtime_gate_blocks_missing_enzyme_input_before_planning(monkeypatch):
    import json

    from app.core.agent_graph import AgentOrchestrator

    orchestrator = AgentOrchestrator()

    async def fail_plan(*args, **kwargs):
        raise AssertionError("intake gate must prevent planning")

    monkeypatch.setattr(orchestrator, "_plan_cb", fail_plan)
    events = [json.loads(raw) async for raw in orchestrator.stream_chat("提高比活力", [], agent_control="plan_only")]

    states = [event for event in events if event.get("type") == "state"]
    assert states[-1]["task_contract"]["intake_status"] == "WAITING_FOR_USER_INPUT"
    assert states[-1]["task_contract"]["final_status"] == "NEEDS_INPUT"
    assert states[-1]["waiting_for"] == "clarification"


async def test_runtime_gate_answers_concept_question_before_planning(monkeypatch):
    import json

    from app.core.agent_graph import AgentOrchestrator

    orchestrator = AgentOrchestrator()

    async def fail_plan(*args, **kwargs):
        raise AssertionError("non-execution question must prevent planning")

    async def plain_reply(*args, **kwargs):
        return "热稳定性是酶在温度压力下保持构象和活性的能力。"

    monkeypatch.setattr(orchestrator, "_plan_cb", fail_plan)
    monkeypatch.setattr(orchestrator, "_chat_reply", plain_reply)
    events = [json.loads(raw) async for raw in orchestrator.stream_chat("热稳定性是什么意思？", [], agent_control="plan_only")]

    states = [event for event in events if event.get("type") == "state"]
    assert states[-1]["task_contract"]["intent"] == "NON_EXECUTION"
    assert states[-1]["task_contract"]["trace"] == []
    assert events[-1]["type"] == "done"


async def test_runtime_gate_keeps_continuation_out_of_planning(monkeypatch):
    import json

    from app.core.agent_graph import AgentOrchestrator

    orchestrator = AgentOrchestrator()

    async def fail_plan(*args, **kwargs):
        raise AssertionError("follow-up must not restart planning")

    async def follow_up_reply(*args, **kwargs):
        return "我将沿用上一轮的热稳定性目标解释。"

    monkeypatch.setattr(orchestrator, "_plan_cb", fail_plan)
    monkeypatch.setattr(orchestrator, "_chat_reply", follow_up_reply)
    history = [{"role": "user", "content": "提高这个酶的热稳定性，序列：MKTIIALSYIFCLVFADYKDDDDK"}]
    events = [json.loads(raw) async for raw in orchestrator.stream_chat("继续", history, agent_control="plan_only")]

    states = [event for event in events if event.get("type") == "state"]
    assert states[-1]["task_contract"]["intent"] == "FOLLOW_UP"
    assert states[-1]["task_contract"]["workflow_id"] == "WF-STABILITY"


async def test_execution_trace_is_exposed_in_task_contract(monkeypatch):
    import json

    from app.core.agent_graph import AgentOrchestrator, PlanStep
    from app.tools.registry import ToolRegistry

    orchestrator = AgentOrchestrator()

    async def fake_plan(*args, **kwargs):
        return [PlanStep(1, "predict_properties", "baseline", {"sequence": "MKTIIALSYIFCLVFADYKDDDDK"})]

    async def fake_execute(*args, **kwargs):
        return {"status": "completed", "prediction": "diagnostic"}

    monkeypatch.setattr(orchestrator, "_plan_cb", fake_plan)
    monkeypatch.setattr(ToolRegistry, "execute", fake_execute)
    confirmed_plan = [{
        "id": 1,
        "tool_name": "predict_properties",
        "description": "baseline",
        "params": {"sequence": "MKTIIALSYIFCLVFADYKDDDDK"},
    }]
    strategy_signature = orchestrator._plan_signature(confirmed_plan)
    events = [json.loads(raw) async for raw in orchestrator.stream_chat(
        "提高热稳定性 MKTIIALSYIFCLVFADYKDDDDK", [], agent_control="execute_confirmed",
        confirmed_plan=confirmed_plan,
        strategy_signature=strategy_signature,
    )]

    states = [event for event in events if event.get("type") == "state"]
    trace = states[-1]["task_contract"]["trace"]
    assert trace
    assert trace[0]["tool_id"] == "predict_properties"


async def test_tool_failure_is_explicitly_degraded_and_recorded(monkeypatch):
    import json

    from app.core.agent_graph import AgentOrchestrator
    from app.tools.registry import ToolRegistry

    orchestrator = AgentOrchestrator()

    async def fail_execute(*args, **kwargs):
        raise RuntimeError("structure service unavailable")

    monkeypatch.setattr(ToolRegistry, "execute", fail_execute)
    monkeypatch.setattr(orchestrator, "_cache_get", lambda key: None)
    confirmed_plan = [{
        "id": 1,
        "tool_name": "predict_properties",
        "description": "baseline",
        "params": {"sequence": "MKTIIALSYIFCLVFADYKDDDDK"},
    }]
    events = [json.loads(raw) async for raw in orchestrator.stream_chat(
        "提高热稳定性 MKTIIALSYIFCLVFADYKDDDDK", [], agent_control="execute_confirmed",
        confirmed_plan=confirmed_plan,
        strategy_signature=orchestrator._plan_signature(confirmed_plan),
    )]

    states = [event for event in events if event.get("type") == "state"]
    contract = states[-1]["task_contract"]
    assert contract["trace"][0]["status"] == "failed"
    assert contract["fallback_trace"][0]["primary_tool"] == "predict_properties"
    assert contract["fallback_trace"][0]["fallback_level"] == "DEGRADED"
    text = "".join(event.get("content", "") for event in events if event.get("type") == "text")
    assert "降级提示" in text
