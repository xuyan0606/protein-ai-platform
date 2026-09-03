"""Regression tests for the unified LLM gateway and chat model-id interface."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.conversation import Conversation
from app.models.project import Project
from app.models.strategy_checkpoint import StrategyCheckpoint
from app.models.user import User
from app.services.strategy_checkpoint import mark_strategy_checkpoint_completed, persist_strategy_checkpoint


async def _create_user(session, email: str = "gateway@example.com") -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name="Gateway User",
    )
    session.add(user)
    await session.flush()
    return user


def test_llm_gateway_complete_sync_resolves_model_id(monkeypatch):
    from app.core import llm
    from app.core import llm_gateway as gateway_module

    captured: dict = {}

    monkeypatch.setattr(gateway_module, "is_model_available", lambda provider, model: True)

    def fake_chat_completion_sync(messages, **kwargs):
        captured["messages"] = messages
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(llm, "chat_completion_sync", fake_chat_completion_sync)

    result = llm.llm_gateway.complete_sync(
        [{"role": "user", "content": "test unified interface"}],
        model_id="gpt55",
        max_tokens=321,
    )

    assert result == {"ok": True}
    assert captured["provider"] == "kuaPao"
    assert captured["model"] == llm.settings.KUAPAO_MODEL
    assert captured["max_tokens"] == 321


def test_llm_gateway_resolves_kuaipao_sol_model(monkeypatch):
    from app.core import llm
    from app.core import llm_gateway as gateway_module

    captured: dict = {}

    monkeypatch.setattr(gateway_module, "is_model_available", lambda provider, model: True)

    def fake_chat_completion_sync(messages, **kwargs):
        captured["messages"] = messages
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(llm, "chat_completion_sync", fake_chat_completion_sync)

    result = llm.llm_gateway.complete_sync(
        [{"role": "user", "content": "test sol model"}],
        model_id="gpt56-sol",
        max_tokens=123,
    )

    assert result == {"ok": True}
    assert captured["provider"] == "kuaPao"
    assert captured["model"] == llm.settings.KUAPAO_SOL_MODEL
    assert captured["max_tokens"] == 123


def test_llm_gateway_resolves_gpt56_model(monkeypatch):
    from app.core import llm
    from app.core import llm_gateway as gateway_module

    captured: dict = {}

    monkeypatch.setattr(gateway_module, "is_model_available", lambda provider, model: True)

    def fake_chat_completion_sync(messages, **kwargs):
        captured["messages"] = messages
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(llm, "chat_completion_sync", fake_chat_completion_sync)

    result = llm.llm_gateway.complete_sync(
        [{"role": "user", "content": "test gpt56 model"}],
        model_id="gpt56",
        max_tokens=456,
    )

    assert result == {"ok": True}
    assert captured["provider"] == "kuaPao"
    assert captured["model"] == llm.settings.KUAPAO_GPT56_MODEL
    assert captured["max_tokens"] == 456


def test_llm_gateway_resolves_deepseek_v4ro_model(monkeypatch):
    from app.core import llm
    from app.core import llm_gateway as gateway_module

    captured: dict = {}
    monkeypatch.setattr(gateway_module, "is_model_available", lambda provider, model: True)

    def fake_chat_completion_sync(messages, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(llm, "chat_completion_sync", fake_chat_completion_sync)
    result = llm.llm_gateway.complete_sync(
        [{"role": "user", "content": "test deepseek v4ro"}],
        model_id="deepseek-v4ro",
        max_tokens=234,
    )

    assert result == {"ok": True}
    assert captured["provider"] == "deepseek"
    assert captured["model"] == llm.settings.DEEPSEEK_V4RO_MODEL
    assert captured["max_tokens"] == 234


def test_llm_gateway_list_models_reflects_runtime_health(monkeypatch):
    from app.core import llm_gateway as gateway_module

    monkeypatch.setattr(
        gateway_module,
        "is_model_available",
        lambda provider, model: provider == "kuaPao",
    )

    listed = gateway_module.llm_gateway.list_models()
    models = {item["id"]: item for item in listed}

    assert list(models) == ["gpt55", "gpt56", "gpt56-sol", "deepseek-v4ro"]
    assert models["gpt55"]["available"] is True
    assert models["gpt55"]["name"] == "GPT-5.5"
    assert models["gpt55"]["provider"] == "model-relay"
    assert models["gpt55"]["model"] == "gpt-5.5"
    assert models["gpt56"]["available"] is True
    assert models["gpt56"]["name"] == "GPT-5.6"
    assert models["gpt56"]["provider"] == "model-relay"
    assert models["gpt56"]["model"] == "gpt-5.6-terra"
    assert models["gpt56-sol"]["available"] is True
    assert models["gpt56-sol"]["name"] == "GPT-5.6 sol"
    assert models["gpt56-sol"]["provider"] == "model-relay"
    assert models["gpt56-sol"]["model"] == "gpt-5.6-sol"
    assert models["deepseek-v4ro"]["available"] is False
    assert models["deepseek-v4ro"]["name"] == "DeepSeek-v4ro"
    assert models["deepseek-v4ro"]["provider"] == "deepseek"
    assert models["deepseek-v4ro"]["model"] == "DeepSeek-v4ro"
    assert "dashscope" not in models
    assert "miniMax" not in models
    assert all("KuaPao" not in item["name"] for item in models.values())
    public_payload = json.dumps(listed, ensure_ascii=False)
    for hidden_name in ("kuaPao", "KuaPao", "miniMax", "MiniMax", "dashscope", "DashScope", "阿里", "千问"):
        assert hidden_name not in public_payload


def test_candidate_chain_skips_disabled_dashscope(monkeypatch):
    from app.core import llm_policy

    monkeypatch.setattr(llm_policy.settings, "LLM_PROVIDER", "dashscope")
    monkeypatch.setattr(llm_policy.settings, "LLM_MODEL", "qwen3.7-max")
    monkeypatch.setattr(llm_policy.settings, "LLM_FALLBACK_PROVIDER", "dashscope")
    monkeypatch.setattr(llm_policy.settings, "LLM_FALLBACK_MODEL", "qwen-plus")
    monkeypatch.setattr(llm_policy.settings, "LLM_DISABLED_PROVIDERS", "dashscope")
    monkeypatch.setattr(llm_policy.settings, "DASHSCOPE_API_KEY", "configured")
    monkeypatch.setattr(llm_policy.settings, "KUAPAO_API_KEY", "configured")
    monkeypatch.setattr(llm_policy.settings, "DEEPSEEK_API_KEY", "")

    chain = llm_policy.candidate_provider_chain(None, None)

    assert chain
    assert all(provider != "dashscope" for provider, _ in chain)
    assert chain[0] == ("kuaPao", llm_policy.settings.KUAPAO_MODEL)


def test_chat_completion_sync_sets_provider_timeout(monkeypatch):
    from app.core import llm

    captured: dict = {}

    monkeypatch.setattr(llm, "_rate_bucket", SimpleNamespace(consume=lambda tokens: True))
    monkeypatch.setattr(llm, "candidate_provider_chain", lambda provider, model: [("kuaPao", "gpt-5.5")])
    monkeypatch.setattr(llm, "get_api_key", lambda provider: "configured")
    monkeypatch.setattr(llm, "get_api_base", lambda provider: "https://example.test/v1")
    monkeypatch.setattr(llm.settings, "LLM_REQUEST_TIMEOUT", 7)

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(llm, "completion", fake_completion)

    result = llm.chat_completion_sync(
        [{"role": "user", "content": "test timeout"}],
        max_tokens=12,
    )

    assert result == {"ok": True}
    assert captured["timeout"] == 7


async def test_agent_call_llm_has_coroutine_timeout(monkeypatch):
    from app.core import agent_graph

    orchestrator = agent_graph.AgentOrchestrator()
    monkeypatch.setattr(agent_graph.settings, "LLM_REQUEST_TIMEOUT", 0.01)

    def slow_complete_sync(*args, **kwargs):
        time.sleep(0.1)
        return {"ok": True}

    monkeypatch.setattr(agent_graph.llm_gateway, "complete_sync", slow_complete_sync)

    with pytest.raises(asyncio.TimeoutError):
        await orchestrator._call_llm([{"role": "user", "content": "test timeout"}])


async def test_chat_stream_forwards_model_id_to_orchestrator(client, session, monkeypatch):
    from app.api import chat as chat_api

    user = await _create_user(session)
    await session.commit()

    token = create_access_token(subject=user.id)
    captured: dict = {}

    async def fake_stream_chat(user_message, history, model_id=None, **kwargs):
        captured["message"] = user_message
        captured["history"] = history
        captured["model_id"] = model_id
        captured["agent_control"] = kwargs.get("agent_control")
        captured["confirmed_plan"] = kwargs.get("confirmed_plan")
        captured["strategy_signature"] = kwargs.get("strategy_signature")
        captured["task_fingerprint"] = kwargs.get("task_fingerprint")
        yield json.dumps({"type": "text", "content": "hello "}, ensure_ascii=False)
        yield json.dumps({"type": "done"}, ensure_ascii=False)

    async def fake_finalize_chat_response(*args, **kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(chat_api, "_finalize_chat_response", fake_finalize_chat_response)

    response = await client.post(
        "/api/chat/stream",
        json={
            "message": "describe this protein",
            "history": [],
            "model": "gpt55",
            "agent_control": "execute_confirmed",
            "confirmed_plan": [{"id": 1, "tool_name": "predict_properties", "description": "Check", "params": {}}],
            "strategy_signature": "sig123",
            "task_fingerprint": "task123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert captured["message"] == "describe this protein"
    assert captured["history"] == []
    assert captured["model_id"] == "gpt55"
    assert captured["agent_control"] == "execute_confirmed"
    assert captured["confirmed_plan"] is None
    assert captured["strategy_signature"] is None
    assert captured["task_fingerprint"] is None
    assert '"type": "done"' in response.text


async def test_chat_stream_persists_and_restores_strategy_checkpoint(client, session, monkeypatch):
    from app.api import chat as chat_api

    user = await _create_user(session, "checkpoint-api@example.com")
    await session.commit()
    token = create_access_token(subject=user.id)
    calls: list[dict] = []

    async def fake_stream_chat(user_message, history, model_id=None, **kwargs):
        calls.append({
            "message": user_message,
            "agent_control": kwargs.get("agent_control"),
            "confirmed_plan": kwargs.get("confirmed_plan"),
            "strategy_signature": kwargs.get("strategy_signature"),
            "task_fingerprint": kwargs.get("task_fingerprint"),
        })
        if kwargs.get("agent_control") == "execute_confirmed":
            yield json.dumps({"type": "text", "content": "executed"}, ensure_ascii=False)
            yield json.dumps({"type": "done"}, ensure_ascii=False)
            return
        yield json.dumps({
            "type": "state",
            "stage": "done",
            "waiting_for": "plan_confirmation",
            "plan": [{
                "id": 1,
                "tool_name": "predict_properties",
                "description": "Check properties",
                "params": {"sequence": "MKTAYIAKQRQISFVKSHFSRQ"},
                "status": "pending",
            }],
            "strategy_signature": "sig-api-1",
            "task_fingerprint": "task-api-1",
            "research_notes": "preview",
            "current_step": 0,
            "step_results": [],
        }, ensure_ascii=False)
        yield json.dumps({"type": "text", "content": "plan"}, ensure_ascii=False)
        yield json.dumps({"type": "done"}, ensure_ascii=False)

    async def fake_finalize_chat_response(*args, **kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(chat_api, "_finalize_chat_response", fake_finalize_chat_response)

    first = await client.post(
        "/api/chat/stream",
        json={"message": "提高这个酶的比活力 MKTAYIAKQRQISFVKSHFSRQ", "history": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200

    stored = (await session.execute(select(StrategyCheckpoint))).scalars().all()
    assert len(stored) == 1
    assert stored[0].status == "awaiting_confirmation"
    assert stored[0].strategy_signature == "sig-api-1"

    active = await client.get(
        "/api/chat/strategy-checkpoints/active",
        params={"conversation_id": stored[0].conversation_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert active.status_code == 200
    active_payload = active.json()
    assert active_payload["checkpoint"]["strategy_signature"] == "sig-api-1"
    assert active_payload["checkpoint"]["next_action"] == "confirm_execute"
    assert active_payload["agent_state"]["waiting_for"] == "plan_confirmation"
    assert active_payload["agent_state"]["strategy_signature"] == "sig-api-1"
    assert active_payload["agent_state"]["task_fingerprint"] == "task-api-1"
    assert active_payload["agent_state"]["next_action"] == "confirm_execute"
    assert active_payload["agent_state"]["plan"][0]["tool_name"] == "predict_properties"

    second = await client.post(
        "/api/chat/stream",
        json={
            "message": "确认执行上述分析策略",
            "conversation_id": stored[0].conversation_id,
            "history": [],
            "agent_control": "execute_confirmed",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 200
    assert calls[-1]["message"] == "提高这个酶的比活力 MKTAYIAKQRQISFVKSHFSRQ"
    assert calls[-1]["confirmed_plan"][0]["tool_name"] == "predict_properties"
    assert calls[-1]["strategy_signature"] == "sig-api-1"
    assert calls[-1]["task_fingerprint"] == "task-api-1"


async def test_chat_stream_confirmed_payload_marks_checkpoint_executing(client, session, monkeypatch):
    from app.api import chat as chat_api

    user = await _create_user(session, "checkpoint-payload-execute@example.com")
    conversation = Conversation(user_id=user.id, title="checkpoint payload execute")
    session.add(conversation)
    await session.flush()
    plan_payload = [{
        "id": 1,
        "tool_name": "predict_properties",
        "description": "Check properties",
        "params": {"sequence": "MKTAYIAKQRQISFVKSHFSRQ"},
        "status": "pending",
    }]
    stored_checkpoint = await persist_strategy_checkpoint(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        project_id=None,
        task_text="提高这个酶的比活力 MKTAYIAKQRQISFVKSHFSRQ",
        task_fingerprint="task-payload-1",
        strategy_signature="sig-payload-1",
        plan_payload=plan_payload,
    )
    await session.commit()
    token = create_access_token(subject=user.id)

    async def fake_stream_chat(user_message, history, model_id=None, **kwargs):
        assert kwargs.get("agent_control") == "execute_confirmed"
        assert kwargs.get("confirmed_plan") == plan_payload
        assert kwargs.get("strategy_signature") == "sig-payload-1"
        assert kwargs.get("task_fingerprint") == "task-payload-1"
        yield json.dumps({
            "type": "state",
            "stage": "execute",
            "plan": plan_payload,
            "current_step": 1,
            "step_results": [],
        }, ensure_ascii=False)
        yield json.dumps({"type": "text", "content": "executed with payload"}, ensure_ascii=False)
        yield json.dumps({"type": "done"}, ensure_ascii=False)

    async def fake_finalize_chat_response(*args, **kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(chat_api, "_finalize_chat_response", fake_finalize_chat_response)

    response = await client.post(
        "/api/chat/stream",
        json={
            "message": "确认执行上述分析策略",
            "conversation_id": conversation.id,
            "history": [],
            "agent_control": "execute_confirmed",
            "confirmed_plan": plan_payload,
            "strategy_signature": "sig-payload-1",
            "task_fingerprint": "task-payload-1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    refreshed = (
        await session.execute(
            select(StrategyCheckpoint).where(StrategyCheckpoint.id == stored_checkpoint["id"])
        )
    ).scalar_one()
    assert refreshed.status == "completed"
    assert refreshed.confirmed_at is not None
    assert refreshed.executed_at is not None

    active = await client.get(
        "/api/chat/strategy-checkpoints/active",
        params={"conversation_id": conversation.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert active.status_code == 200
    assert active.json()["checkpoint"] is None


async def test_mark_strategy_checkpoint_completed_stores_execution_summary(session):
    user = await _create_user(session, "checkpoint-completed-summary@example.com")
    conversation = Conversation(user_id=user.id, title="checkpoint completed summary")
    session.add(conversation)
    await session.flush()

    stored = await persist_strategy_checkpoint(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        project_id=None,
        task_text="提高这个酶的比活力",
        task_fingerprint="task-completed-summary",
        strategy_signature="sig-completed-summary",
        plan_payload=[{"id": 1, "tool_name": "blast_search", "params": {}}],
    )
    completed = await mark_strategy_checkpoint_completed(
        session,
        checkpoint_id=stored["id"],
        user_id=user.id,
        evidence_state={
            "step_results": [{"tool": "blast_search", "status": "submitted", "result_preview": "task_id=abc"}],
            "final_report_preview": "突变位点探索清单（未放行）",
        },
        artifacts={"handoffs": [{"step": 1}]},
    )

    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["evidence_state"]["step_results"][0]["tool"] == "blast_search"
    assert completed["artifacts"]["handoffs"][0]["step"] == 1


async def test_chat_stream_execute_confirmed_prefers_active_checkpoint_over_stale_client_payload(client, session, monkeypatch):
    from app.api import chat as chat_api

    user = await _create_user(session, "checkpoint-stale-client@example.com")
    conversation = Conversation(user_id=user.id, title="checkpoint stale client")
    session.add(conversation)
    await session.flush()
    active_plan = [{
        "id": 1,
        "tool_name": "predict_properties",
        "description": "Active plan",
        "params": {"sequence": "MKTAYIAKQRQISFVKSHFSRQ"},
        "status": "pending",
    }]
    stale_plan = [{
        "id": 1,
        "tool_name": "mutation_priority_score",
        "description": "Stale plan",
        "params": {"sequence": "M" * 80},
        "status": "pending",
    }]
    stored_checkpoint = await persist_strategy_checkpoint(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        project_id=None,
        task_text="提高这个酶的比活力 MKTAYIAKQRQISFVKSHFSRQ",
        task_fingerprint="task-active-1",
        strategy_signature="sig-active-1",
        plan_payload=active_plan,
    )
    await session.commit()
    token = create_access_token(subject=user.id)
    captured: dict = {}

    async def fake_stream_chat(user_message, history, model_id=None, **kwargs):
        captured["message"] = user_message
        captured["confirmed_plan"] = kwargs.get("confirmed_plan")
        captured["strategy_signature"] = kwargs.get("strategy_signature")
        captured["task_fingerprint"] = kwargs.get("task_fingerprint")
        yield json.dumps({"type": "text", "content": "executed active checkpoint"}, ensure_ascii=False)
        yield json.dumps({"type": "done"}, ensure_ascii=False)

    async def fake_finalize_chat_response(*args, **kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(chat_api, "_finalize_chat_response", fake_finalize_chat_response)

    response = await client.post(
        "/api/chat/stream",
        json={
            "message": "确认执行上述分析策略",
            "conversation_id": conversation.id,
            "history": [],
            "agent_control": "execute_confirmed",
            "confirmed_plan": stale_plan,
            "strategy_signature": "sig-stale-client",
            "task_fingerprint": "task-stale-client",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert captured["message"] == "提高这个酶的比活力 MKTAYIAKQRQISFVKSHFSRQ"
    assert captured["confirmed_plan"] == active_plan
    assert captured["strategy_signature"] == "sig-active-1"
    assert captured["task_fingerprint"] == "task-active-1"
    refreshed = (
        await session.execute(
            select(StrategyCheckpoint).where(StrategyCheckpoint.id == stored_checkpoint["id"])
        )
    ).scalar_one()
    assert refreshed.status == "completed"


async def test_chat_stream_execute_confirmed_prefers_active_checkpoint_over_malformed_client_payload(client, session, monkeypatch):
    from app.api import chat as chat_api

    user = await _create_user(session, "checkpoint-malformed-client@example.com")
    conversation = Conversation(user_id=user.id, title="checkpoint malformed client")
    session.add(conversation)
    await session.flush()
    active_plan = [{
        "id": 1,
        "tool_name": "predict_properties",
        "description": "Active plan",
        "params": {"sequence": "MKTAYIAKQRQISFVKSHFSRQ"},
        "status": "pending",
    }]
    await persist_strategy_checkpoint(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        project_id=None,
        task_text="提高这个酶的比活力 MKTAYIAKQRQISFVKSHFSRQ",
        task_fingerprint="task-active-1",
        strategy_signature="sig-active-1",
        plan_payload=active_plan,
    )
    await session.commit()
    token = create_access_token(subject=user.id)
    captured: dict = {}

    async def fake_stream_chat(user_message, history, model_id=None, **kwargs):
        captured["confirmed_plan"] = kwargs.get("confirmed_plan")
        captured["strategy_signature"] = kwargs.get("strategy_signature")
        captured["task_fingerprint"] = kwargs.get("task_fingerprint")
        yield json.dumps({"type": "text", "content": "executed active checkpoint"}, ensure_ascii=False)
        yield json.dumps({"type": "done"}, ensure_ascii=False)

    async def fake_finalize_chat_response(*args, **kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(chat_api, "_finalize_chat_response", fake_finalize_chat_response)

    response = await client.post(
        "/api/chat/stream",
        json={
            "message": "确认执行上述分析策略",
            "conversation_id": conversation.id,
            "history": [],
            "agent_control": "execute_confirmed",
            "confirmed_plan": {"bad": "shape", "length": 1},
            "strategy_signature": "sig-malformed-client",
            "task_fingerprint": "task-malformed-client",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert captured["confirmed_plan"] == active_plan
    assert captured["strategy_signature"] == "sig-active-1"
    assert captured["task_fingerprint"] == "task-active-1"


async def test_chat_strategy_checkpoint_active_response_masks_uploaded_object_paths(client, session):
    user = await _create_user(session, "checkpoint-display@example.com")
    conversation = Conversation(user_id=user.id, title="checkpoint display")
    session.add(conversation)
    await session.flush()
    await persist_strategy_checkpoint(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        project_id=None,
        task_text="提高蛋白比活力\n\n[Attached files:\nname: HM.pdb, object_name: uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb]",
        task_fingerprint="task-display-1",
        strategy_signature="sig-display-1",
        plan_payload=[{
            "id": 1,
            "tool_name": "structure_search_foldseek",
            "description": "Parse structure",
            "params": {"pdb_object_name": "uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb"},
            "status": "pending",
        }],
    )
    await session.commit()
    token = create_access_token(subject=user.id)

    response = await client.get(
        "/api/chat/strategy-checkpoints/active",
        params={"conversation_id": conversation.id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoint"]["plan_payload"][0]["params"]["pdb_object_name"] == "[uploaded-object]"
    assert payload["agent_state"]["plan"][0]["params"]["pdb_object_name"] == "[uploaded-object]"
    active_raw = json.dumps(payload, ensure_ascii=False)
    assert "uploads/user_2" not in active_raw
    assert "49405" not in active_raw
    assert "download_url" not in active_raw


async def test_chat_strategy_checkpoint_history_returns_revisions(client, session):
    user = await _create_user(session, "checkpoint-history@example.com")
    conversation = Conversation(user_id=user.id, title="checkpoint history")
    session.add(conversation)
    await session.flush()

    await persist_strategy_checkpoint(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        project_id=None,
        task_text="task v1",
        task_fingerprint="task-1",
        strategy_signature="sig-1",
        plan_payload=[{"id": 1, "tool_name": "predict_properties", "description": "v1", "params": {}, "status": "pending"}],
    )
    await persist_strategy_checkpoint(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        project_id=None,
        task_text="task v2",
        task_fingerprint="task-2",
        strategy_signature="sig-2",
        plan_payload=[{"id": 1, "tool_name": "mutation_priority_score", "description": "v2", "params": {}, "status": "pending"}],
    )
    await session.commit()

    token = create_access_token(subject=user.id)
    history = await client.get(
        "/api/chat/strategy-checkpoints/history",
        params={"conversation_id": conversation.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history.status_code == 200
    records = history.json()["records"]
    assert [record["revision"] for record in records] == [2, 1]
    assert records[0]["status"] == "awaiting_confirmation"
    assert records[0]["strategy_signature"] == "sig-2"
    assert records[1]["status"] == "superseded"

    active = await client.get(
        "/api/chat/strategy-checkpoints/active",
        params={"conversation_id": conversation.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert active.status_code == 200
    assert active.json()["checkpoint"]["revision"] == 2


async def test_recent_strategy_memory_uses_project_scope_from_conversation(client, session):
    user = await _create_user(session, "strategy-memory@example.com")
    project = Project(name="Strategy Memory", user_id=user.id)
    session.add(project)
    await session.flush()
    first_conversation = Conversation(user_id=user.id, project_id=project.id, title="first project strategy")
    second_conversation = Conversation(user_id=user.id, project_id=project.id, title="second project strategy")
    session.add_all([first_conversation, second_conversation])
    await session.flush()

    saved = await persist_strategy_checkpoint(
        session,
        user_id=user.id,
        conversation_id=first_conversation.id,
        project_id=project.id,
        task_text="first executed strategy",
        task_fingerprint="task-memory-1",
        strategy_signature="sig-memory-1",
        plan_payload=[{"id": 1, "tool_name": "predict_properties", "description": "v1", "params": {}, "status": "pending"}],
    )
    row = (
        await session.execute(
            select(StrategyCheckpoint).where(StrategyCheckpoint.id == saved["id"])
        )
    ).scalar_one()
    row.status = "executing"
    row.next_action = None
    await session.commit()
    token = create_access_token(subject=user.id)

    response = await client.get(
        "/api/chat/strategy-checkpoints/recent",
        params={"conversation_id": second_conversation.id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == {
        "type": "project",
        "conversation_id": second_conversation.id,
        "project_id": project.id,
    }
    assert [record["strategy_signature"] for record in payload["records"]] == ["sig-memory-1"]
    assert payload["records"][0]["status"] == "executing"


async def test_chat_strategy_policy_endpoint_is_read_only(client, session):
    user = await _create_user(session, "strategy-policy@example.com")
    await session.commit()
    token = create_access_token(subject=user.id)

    response = await client.get(
        "/api/chat/strategy-policy",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"default", "configured", "default_due_to_error"}
    assert "continuation_tokens" in payload["policy"]
    assert "new_task_tokens" in payload["policy"]
    assert payload["policy"]["raw_sequence_history_requires_continuation"] is True


async def test_auto_title_uses_selected_model(monkeypatch):
    from app.api import chat as chat_api

    captured: dict = {}

    async def fake_complete(messages, **kwargs):
        captured["messages"] = messages
        captured.update(kwargs)
        return {"choices": [{"message": {"content": ""}}]}

    monkeypatch.setattr(chat_api.llm_gateway, "complete", fake_complete)

    await chat_api._auto_title(
        SimpleNamespace(id=1, title="default"),
        "analyze this protein",
        model_id="gpt55",
    )

    assert captured["model_id"] == "gpt55"


async def test_chat_stream_injects_heartbeat_during_long_gap(client, session, monkeypatch):
    from app.api import chat as chat_api

    user = await _create_user(session, "heartbeat@example.com")
    await session.commit()

    token = create_access_token(subject=user.id)

    async def fake_stream_chat(user_message, history, model_id=None, **kwargs):
        yield json.dumps({"type": "text", "content": "hello "}, ensure_ascii=False)
        await asyncio.sleep(0.03)
        yield json.dumps({"type": "done"}, ensure_ascii=False)

    async def fake_finalize_chat_response(*args, **kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(chat_api, "_finalize_chat_response", fake_finalize_chat_response)
    monkeypatch.setattr(chat_api, "STREAM_HEARTBEAT_SECONDS", 0.01)

    response = await client.post(
        "/api/chat/stream",
        json={
            "message": "describe this protein",
            "history": [],
            "model": "gpt55",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert ": heartbeat" in response.text
    assert '"type": "done"' in response.text
