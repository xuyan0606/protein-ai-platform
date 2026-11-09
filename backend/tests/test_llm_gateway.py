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


async def test_model_not_found_503_skips_retries_and_uses_working_provider(monkeypatch):
    from app.core import llm
    calls = []
    monkeypatch.setattr(llm, '_rate_bucket', SimpleNamespace(consume=lambda tokens: True))
    monkeypatch.setattr(llm, 'candidate_provider_chain', lambda *args: [('kuaPao', 'missing'), ('deepseek', 'working')])
    monkeypatch.setattr(llm, 'get_api_key', lambda provider: 'configured')
    monkeypatch.setattr(llm, 'get_api_base', lambda provider: 'https://example.test/v1')
    monkeypatch.setattr(llm, 'mark_model_unavailable', lambda *args: None)
    monkeypatch.setattr(llm.settings, 'LLM_RETRY_DELAY_SECONDS', 0)
    async def completion(**kwargs):
        calls.append(kwargs['model'])
        if len(calls) == 1 or 'missing' in kwargs['model']:
            raise RuntimeError('503 model_not_found: No available channel for model missing under group auto')
        return {'choices': [{'message': {'content': '完整摘要。'}, 'finish_reason': 'stop'}]}
    monkeypatch.setattr(llm, 'acompletion', completion)
    result = await llm.chat_completion([{'role': 'user', 'content': 'summary'}])
    assert len(calls) == 2
    assert result['choices'][0]['message']['content'] == '完整摘要。'


async def _create_user(session, email: str = "gateway@example.com") -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name="Gateway User",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.parametrize('legacy', [False, True])
async def test_revision_uses_checkpoint_task_after_discussion(session, monkeypatch, legacy):
    from app.api import chat as chat_api
    user = await _create_user(session, 'revision-context@example.com')
    conversation = Conversation(user_id=user.id, title='pending structure')
    session.add(conversation)
    await session.flush()
    cid, uid = conversation.id, user.id
    original = '只分析链 B 的结构质量，仅本地分析，不要BLAST\n[Attached files: name: original.pdb, object_name: uploads/user_7/original.pdb]'
    plan = [{'id': 1, 'tool_name': 'predict_properties', 'params': {}}]
    cp = await persist_strategy_checkpoint(session, user_id=uid, conversation_id=cid,
        project_id=None, task_text=original, task_fingerprint='original-task',
        strategy_signature='original-signature', plan_payload=plan)
    await session.commit()
    captured = {}
    async def fake_stream(message, history, **kwargs):
        captured['message'] = message
        yield json.dumps({'type': 'state', 'waiting_for': 'plan_confirmation', 'plan': plan,
            'strategy_signature': 'revised-signature', 'task_fingerprint': 'revised-task'})
        yield json.dumps({'type': 'done'})
    async def finalize(**kwargs):
        return None
    monkeypatch.setattr(chat_api.orchestrator, 'stream_chat', fake_stream)
    monkeypatch.setattr(chat_api.orchestrator, '_snapshot', SimpleNamespace(raw_plan_payload=plan))
    monkeypatch.setattr(chat_api, '_finalize_chat_response', finalize)
    instruction = '改为分析热稳定性，不设计突变'
    text = '上下文解析不对\n[用户修改策略要求]\n' + instruction if legacy else instruction
    response = await chat_api.stream_chat(chat_api.ChatRequest(message=text,
        conversation_id=cid, agent_control='revise_plan',
        strategy_signature=cp['strategy_signature'], task_fingerprint=cp['task_fingerprint']),
        db=session, current_user={'id': uid})
    frames = [frame async for frame in response.body_iterator]
    assert any('"type": "done"' in frame for frame in frames)
    assert original in captured['message']
    assert instruction in captured['message']
    assert '上下文解析不对' not in captured['message']
    active = (await session.execute(select(StrategyCheckpoint).where(
        StrategyCheckpoint.conversation_id == cid, StrategyCheckpoint.status == 'awaiting_confirmation'))).scalar_one()
    assert active.task_text == captured['message']


async def test_stale_revision_identity_does_not_rewrite_newer_checkpoint(session, monkeypatch):
    from fastapi import HTTPException
    from app.api import chat as chat_api
    user = await _create_user(session, 'stale-revision@example.com')
    conversation = Conversation(user_id=user.id, title='newer strategy')
    session.add(conversation)
    await session.flush()
    cid, uid = conversation.id, user.id
    cp = await persist_strategy_checkpoint(session, user_id=uid, conversation_id=cid,
        project_id=None, task_text='newer task', task_fingerprint='newer-task',
        strategy_signature='newer-signature', plan_payload=[{'id': 1}])
    await session.commit()
    with pytest.raises(HTTPException) as exc:
        await chat_api.stream_chat(chat_api.ChatRequest(message='改为热稳定性',
            conversation_id=cid, agent_control='revise_plan', strategy_signature='old-signature'),
            db=session, current_user={'id': uid})
    assert exc.value.status_code == 409
    row = await session.get(StrategyCheckpoint, cp['id'])
    assert row.status == 'awaiting_confirmation' and row.task_text == 'newer task'


@pytest.mark.parametrize('message', [
    '分析新文件 [Attached files: object_name: uploads/user_7/new.pdb]',
    '分析新序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY',
    '你只会执行工具吗',
    '旧问题\n[用户修改策略要求]\n你分析对还是不对',
])
def test_revision_preserves_new_input_or_discussion_scope(message):
    from app.api.chat import _revision_task_text
    assert _revision_task_text(message, {'task_text': 'unrelated original task'}) == message


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
    from dataclasses import replace
    from app.core import llm_gateway as gateway_module
    from app.core import llm_registry as registry_module

    # Relay routing may use private deployment aliases unrelated to the public
    # product label. Exercise that boundary independently of this shell's env.
    candidates = [
        replace(entry, model=f"MiniMax-private-route-{index}")
        for index, entry in enumerate(gateway_module.MODEL_REGISTRY)
    ]
    monkeypatch.setattr(gateway_module, "MODEL_REGISTRY", candidates)
    monkeypatch.setattr(registry_module, "MODEL_REGISTRY", candidates)
    health_checks = []

    def check_private_route(provider, model):
        health_checks.append((provider, model))
        return provider == "kuaPao"

    monkeypatch.setattr(
        gateway_module,
        "is_model_available",
        check_private_route,
    )

    listed = gateway_module.llm_gateway.list_models()
    models = {item["id"]: item for item in listed}

    assert list(models) == [
        "claude-fable-5",
        "gpt55",
        "gpt56",
        "gpt56-sol",
        "gpt6-sol",
        "deepseek-v4ro",
        "deepseek-chat",
    ]
    assert models["claude-fable-5"]["available"] is True
    assert models["claude-fable-5"]["name"] == "Claude Fable 5"
    assert models["claude-fable-5"]["provider"] == "model-relay"
    assert models["claude-fable-5"]["model"] == "claude-fable-5"
    # Keep the shipped route default contract separate from the public product
    # identity; environment overrides must not become public metadata.
    from app.core.config import Settings

    assert Settings.model_fields["ANTHROPIC_MODEL"].default == "claude-fable-5-1"
    assert models["gpt55"]["available"] is True
    assert models["gpt55"]["name"] == "GPT-5.5"
    assert models["gpt55"]["provider"] == "model-relay"
    assert models["gpt55"]["model"] == "gpt55"
    assert models["gpt56"]["available"] is True
    assert models["gpt56"]["name"] == "GPT-5.6"
    assert models["gpt56"]["provider"] == "model-relay"
    assert models["gpt56"]["model"] == "gpt56"
    assert models["gpt56-sol"]["available"] is True
    assert models["gpt56-sol"]["name"] == "GPT-5.6 sol"
    assert models["gpt56-sol"]["provider"] == "model-relay"
    assert models["gpt56-sol"]["model"] == "gpt56-sol"
    assert models["gpt6-sol"]["available"] is True
    assert models["gpt6-sol"]["name"] == "GPT-6-sol"
    assert models["gpt6-sol"]["provider"] == "model-relay"
    assert models["gpt6-sol"]["model"] == "gpt6-sol"
    assert models["deepseek-v4ro"]["available"] is False
    assert models["deepseek-v4ro"]["name"] == "DeepSeek-v4ro"
    assert models["deepseek-v4ro"]["provider"] == "deepseek"
    assert models["deepseek-v4ro"]["model"] == "deepseek-v4ro"
    assert models["deepseek-chat"]["available"] is False
    assert models["deepseek-chat"]["name"] == "DeepSeek"
    assert models["deepseek-chat"]["model"] == "deepseek-chat"
    assert health_checks == [(entry.provider, entry.model) for entry in candidates]
    # Resolution still returns the private route and honors its health; public
    # serialization must not rewrite backend routing or its health cache key.
    for entry in candidates:
        resolved = gateway_module.llm_gateway.resolve(entry.id)
        assert resolved is (entry if entry.provider == "kuaPao" else None)
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
    # The registry's first kuaPao entry is Claude Fable 5, so it leads the
    # fallback chain ahead of the plain kuaPao model.
    assert chain[0] == ("kuaPao", llm_policy.settings.ANTHROPIC_MODEL)


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
        running = await session.get(StrategyCheckpoint, stored_checkpoint["id"], populate_existing=True)
        assert running.status == "executing", "Claim must be durable before tools start"
        assert not session.dirty
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


@pytest.mark.parametrize('identity', [
    {'strategy_signature': 'sig-stale-client', 'task_fingerprint': 'task-stale-client'},
    {'strategy_signature': 'sig-stale-client', 'task_fingerprint': 'task-active-1'},
    {'strategy_signature': 'sig-active-1', 'task_fingerprint': 'task-stale-client'},
])
@pytest.mark.parametrize('control', ['execute_confirmed', ' EXECUTE_CONFIRMED ', 'Execute_Confirmed'])
async def test_chat_stream_execute_confirmed_rejects_stale_client_checkpoint(client, session, monkeypatch, identity, control):
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
            "agent_control": control,
            "confirmed_plan": stale_plan,
            **identity,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert not captured, "Stale confirmation must not launch the revised plan"
    refreshed = await session.get(StrategyCheckpoint, stored_checkpoint["id"], populate_existing=True)
    assert refreshed.status == "awaiting_confirmation"


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
            "strategy_signature": "sig-active-1",
            "task_fingerprint": "task-active-1",
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


@pytest.mark.parametrize('action', ['delete', 'rename', 'unchanged'])
async def test_delayed_auto_title_respects_conversation_lifecycle(session, engine, monkeypatch, action):
    from sqlalchemy import delete, update
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.api import chat as chat_api
    from app.core import database

    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database, '_async_session_factory', factory)
    user = await _create_user(session, 'delayed-title@example.com')
    conversation = Conversation(user_id=user.id, title='original', project_id=None)
    session.add(conversation)
    await session.commit()
    conversation_id = conversation.id
    session.expunge(conversation)

    async def delayed_complete(**kwargs):
        async with factory() as other:
            if action == 'delete':
                await other.execute(delete(Conversation).where(Conversation.id == conversation_id))
            elif action == 'rename':
                await other.execute(update(Conversation).where(Conversation.id == conversation_id).values(title='user title'))
            await other.commit()
        return {'choices': [{'message': {'content': 'generated title'}}]}

    monkeypatch.setattr(chat_api.llm_gateway, 'complete', delayed_complete)
    await chat_api._auto_title(conversation, 'original', model_id='gpt55')
    async with factory() as verify:
        saved = await verify.get(Conversation, conversation_id)
        if action == 'delete':
            assert saved is None
        else:
            assert saved.title == ('user title' if action == 'rename' else 'generated title')


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


async def test_sse_disconnect_commits_checkpoint_and_releases_transaction(session, monkeypatch):
    import anyio
    from app.api import chat as chat_api

    user = await _create_user(session, 'disconnect-cleanup@example.com')
    await session.commit()
    raw_plan = [{'id': 1, 'tool_name': 'predict_properties', 'description': 'baseline',
                 'params': {'sequence': 'ACDEFGHIKLMNPQRSTVWY'}}]

    async def fake_stream(*args, **kwargs):
        yield json.dumps({'type': 'state', 'waiting_for': 'plan_confirmation',
                          'plan': raw_plan, 'strategy_signature': 'test-signature',
                          'task_fingerprint': 'test-fingerprint'})
        yield json.dumps({'type': 'done'})

    async def finalize(**kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, 'stream_chat', fake_stream)
    monkeypatch.setattr(chat_api.orchestrator, '_snapshot', SimpleNamespace(raw_plan_payload=raw_plan))
    monkeypatch.setattr(chat_api, '_finalize_chat_response', finalize)
    response = await chat_api.stream_chat(
        chat_api.ChatRequest(message='分析此序列', agent_control='plan_only'),
        db=session, current_user={'id': user.id},
    )
    # A client can disconnect as soon as done arrives; teardown must still
    # release the request session without creating a duplicate revision.
    with anyio.CancelScope() as client_scope:
        async for frame in response.body_iterator:
            if '"type": "done"' in frame:
                client_scope.cancel()
                await response.body_iterator.aclose()
                break
    assert not session.in_transaction()
    checkpoint = (await session.execute(select(StrategyCheckpoint).where(
        StrategyCheckpoint.user_id == user.id,
    ))).scalar_one()
    assert checkpoint.strategy_signature == 'test-signature'


@pytest.mark.parametrize('control', ['revise_plan', 'execute_confirmed'])
async def test_sse_done_has_durable_checkpoint_before_client_next_action(session, monkeypatch, control):
    from app.api import chat as chat_api
    from app.services.strategy_checkpoint import get_active_strategy_checkpoint

    user = await _create_user(session, 'done-checkpoint@example.com')
    conversation = Conversation(user_id=user.id, title='durable strategy')
    session.add(conversation)
    await session.flush()
    cid, uid = conversation.id, user.id
    plan = [{'id': 1, 'tool_name': 'predict_properties', 'description': 'baseline',
             'params': {'sequence': 'ACDEFGHIKLMNPQRSTVWY'}}]
    old = await persist_strategy_checkpoint(
        session, user_id=uid, conversation_id=cid, project_id=None,
        task_text='old task', task_fingerprint='old-task', strategy_signature='old-signature',
        plan_payload=plan,
    )
    await session.commit()

    async def fake_stream(*args, **kwargs):
        if control == 'revise_plan':
            yield json.dumps({'type': 'state', 'waiting_for': 'plan_confirmation', 'plan': plan,
                              'strategy_signature': 'new-signature', 'task_fingerprint': 'new-task'})
            yield json.dumps({'type': 'text', 'content': '已完成结构预读；后续工具尚未执行。'})
        yield json.dumps({'type': 'done'})

    async def finalize(**kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, 'stream_chat', fake_stream)
    monkeypatch.setattr(chat_api.orchestrator, '_snapshot', SimpleNamespace(raw_plan_payload=plan))
    monkeypatch.setattr(chat_api, '_finalize_chat_response', finalize)
    response = await chat_api.stream_chat(
        chat_api.ChatRequest(message='update or confirm', conversation_id=cid, agent_control=control),
        db=session, current_user={'id': uid},
    )
    done_seen = False
    try:
        async for frame in response.body_iterator:
            if '"type": "done"' not in frame:
                continue
            done_seen = True
            # Inspect while the generator is suspended at done, before teardown.
            if control == 'revise_plan':
                active = await get_active_strategy_checkpoint(session, user_id=uid, conversation_id=cid)
                assert active['strategy_signature'] == 'new-signature'
                assert active['evidence_state']['plan_confirmation_text'] == '已完成结构预读；后续工具尚未执行。'
            else:
                row = await session.get(StrategyCheckpoint, old['id'])
                assert row.status == 'completed'
            break
    finally:
        await response.body_iterator.aclose()
    assert done_seen
    history = (await session.execute(select(StrategyCheckpoint).where(
        StrategyCheckpoint.conversation_id == cid,
    ))).scalars().all()
    assert len(history) == (2 if control == 'revise_plan' else 1)


@pytest.mark.parametrize('failure', [TypeError, RuntimeError])
async def test_sse_checkpoint_save_failure_emits_error_without_done(session, monkeypatch, failure):
    from app.api import chat as chat_api

    user = await _create_user(session, 'failed-checkpoint@example.com')
    await session.commit()
    uid = user.id
    plan = [{'id': 1, 'tool_name': 'predict_properties', 'description': 'baseline',
             'params': {'sequence': 'ACDEFGHIKLMNPQRSTVWY'}}]

    async def fake_stream(*args, **kwargs):
        yield json.dumps({'type': 'state', 'waiting_for': 'plan_confirmation', 'plan': plan,
                          'strategy_signature': 'new-signature', 'task_fingerprint': 'new-task'})
        yield json.dumps({'type': 'done'})

    async def fail_save(*args, **kwargs):
        raise failure('checkpoint save failed')

    async def finalize(**kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, 'stream_chat', fake_stream)
    monkeypatch.setattr(chat_api, 'persist_strategy_checkpoint', fail_save)
    monkeypatch.setattr(chat_api, '_finalize_chat_response', finalize)
    response = await chat_api.stream_chat(
        chat_api.ChatRequest(message='plan task', agent_control='plan_only'),
        db=session, current_user={'id': uid},
    )
    frames = [frame async for frame in response.body_iterator]
    assert any('"type": "error"' in frame for frame in frames)
    assert not any('"type": "done"' in frame for frame in frames)
    assert not session.in_transaction()


async def test_chat_requests_keep_snapshot_and_finalization_isolated(client, session, monkeypatch):
    from app.api import chat as chat_api
    from app.core.agent_graph import AgentOrchestrator, ChatSnapshot

    user = await _create_user(session, 'request-isolation@example.com')
    await session.commit()
    instances, finalized = [], []

    async def stream(self, message, history, **kwargs):
        instances.append(self)
        self._snapshot = ChatSnapshot(stage='done', final_report=message)
        yield json.dumps({'type': 'text', 'content': message})
        yield json.dumps({'type': 'done'})

    async def finalize(**kwargs):
        finalized.append(kwargs['request_agent'])

    # Earlier gateway tests patch the singleton method; monkeypatch restoration
    # can leave a bound instance attribute shadowing this class-level stub.
    if 'stream_chat' in vars(chat_api.orchestrator):
        monkeypatch.delattr(chat_api.orchestrator, 'stream_chat')
    monkeypatch.setattr(type(chat_api.orchestrator), 'stream_chat', stream)
    monkeypatch.setattr(chat_api, '_finalize_chat_response', finalize)
    headers = {'Authorization': 'Bearer ' + create_access_token(subject=user.id)}
    for text in ['quality request', 'thermal request']:
        response = await client.post('/api/chat/stream', json={'message': text}, headers=headers)
        assert response.status_code == 200
    assert len(instances) == 2 and instances[0] is not instances[1]
    assert all(instance is not chat_api.orchestrator for instance in instances)
    assert finalized == instances
    assert [agent._snapshot.final_report for agent in instances] == ['quality request', 'thermal request']


async def test_deferred_wiki_uses_own_request_snapshot(monkeypatch):
    from app.api import chat as chat_api

    request_agent = chat_api.orchestrator.for_request()
    captured = []

    async def publish(agent, *args):
        captured.append(agent)

    monkeypatch.setattr(chat_api, '_auto_publish_wiki', publish)
    await chat_api._finalize_chat_response(
        conversation=SimpleNamespace(id=1), user_message='quality', full_response=[],
        tool_calls_data=[], stream_error=None, should_auto_title=False, request_agent=request_agent,
    )
    assert captured == [request_agent]
