"""Regressions reproduced by the 2026-10-20 production acceptance run."""

import json
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("mode", ["async", "sync"])
@pytest.mark.parametrize("error_kind", ["typed", "http401", "invalid_token"])
async def test_model_auth_failure_skips_retries_and_updates_catalog(monkeypatch, mode, error_kind):
    from app.core import llm_policy, llm
    from app.core.llm_gateway import llm_gateway

    monkeypatch.setattr(llm_policy, "_runtime_unavailable_models", set())
    monkeypatch.setattr(llm.settings, "KUAPAO_API_KEY", "test-only-key")
    monkeypatch.setattr(llm.settings, "LLM_DISABLED_PROVIDERS", "")
    monkeypatch.setattr(llm.settings, "LLM_MAX_RETRIES", 3)
    monkeypatch.setattr(llm.settings, "LLM_RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(llm, "_rate_bucket", llm.TokenBucket(capacity=100))
    model = llm.settings.KUAPAO_GPT6_SOL_MODEL
    monkeypatch.setattr(llm, "candidate_provider_chain", lambda *_: [("kuaPao", model)])
    error = llm.AuthenticationError("Invalid token", llm_provider="openai", model=model)
    if error_kind != "typed":
        error = RuntimeError("rejected" if error_kind == "http401" else "Invalid token")
        if error_kind == "http401":
            error.status_code = 401
    attempts = []

    def complete(**kwargs):
        attempts.append(kwargs["model"])
        raise error

    async def acomplete(**kwargs):
        return complete(**kwargs)

    monkeypatch.setattr(llm, "completion", complete)
    monkeypatch.setattr(llm, "acompletion", acomplete)
    with pytest.raises(llm.AllProvidersFailed):
        if mode == "async":
            await llm.chat_completion([{"role": "user", "content": "2+3?"}])
        else:
            llm.chat_completion_sync([{"role": "user", "content": "2+3?"}])
    assert len(attempts) == 1
    catalog = {item["id"]: item for item in llm_gateway.list_models()}
    assert catalog["gpt6-sol"]["available"] is False
    assert ("kuaPao", model) not in llm_policy.candidate_provider_chain("kuaPao", model)


@pytest.mark.parametrize("mode", ["async", "sync"])
@pytest.mark.parametrize("auth_failure", [False, True])
async def test_model_fallback_preserves_transient_retries(monkeypatch, mode, auth_failure):
    from app.core import llm_policy, llm

    monkeypatch.setattr(llm_policy, "_runtime_unavailable_models", set())
    monkeypatch.setattr(llm.settings, "LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(llm.settings, "LLM_RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(llm, "_rate_bucket", llm.TokenBucket(capacity=100))
    monkeypatch.setattr(llm, "candidate_provider_chain", lambda *_: [("kuaPao", "primary"), ("deepseek", "fallback")])
    attempts = []
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="5"))])

    def complete(**kwargs):
        attempts.append(kwargs["model"])
        if kwargs["model"] == "openai/primary":
            if auth_failure:
                raise llm.AuthenticationError("Invalid token", llm_provider="openai", model="primary")
            raise TimeoutError("temporary timeout")
        return response

    async def acomplete(**kwargs):
        return complete(**kwargs)

    monkeypatch.setattr(llm, "completion", complete)
    monkeypatch.setattr(llm, "acompletion", acomplete)
    if mode == "async":
        result = await llm.chat_completion([{"role": "user", "content": "2+3?"}])
    else:
        result = llm.chat_completion_sync([{"role": "user", "content": "2+3?"}])
    assert result.choices[0].message.content == "5"
    assert attempts == ["openai/primary"] * (1 if auth_failure else 2) + ["deepseek/fallback"]


@pytest.mark.parametrize("empty_response", [False, True])
async def test_chat_model_outage_is_visible_without_exposing_credentials(monkeypatch, empty_response):
    from app.core.agent_graph import AgentOrchestrator

    orch = AgentOrchestrator()

    async def unavailable(*args, **kwargs):
        if empty_response:
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="  "))])
        raise RuntimeError("401 Invalid token: private-test-credential")

    monkeypatch.setattr(orch, "_call_llm", unavailable)
    reply = await orch._chat_reply("请用中文回答：2 加 3 等于几？", [])
    assert "模型服务暂不可用" in reply
    assert "private-test-credential" not in reply
    assert "Hello!" not in reply


async def test_followup_preserves_report_facts_during_model_outage(monkeypatch):
    from app.core.agent_graph import AgentOrchestrator

    orch = AgentOrchestrator()

    async def unavailable(*args, **kwargs):
        raise RuntimeError("model offline")

    monkeypatch.setattr(orch, "_call_llm", unavailable)
    history = [
        {"role": "user", "content": "分析这个蛋白的性质"},
        {"role": "assistant", "content": "# 蛋白性质分析报告\n\n- **分子量**：40.13 kDa\n"},
    ]
    events = [json.loads(event) async for event in orch.stream_chat("请总结上面的分析结果", history)]
    reply = "".join(item.get("content", "") for item in events if item["type"] == "text")
    assert "模型服务暂不可用" in reply
    assert "40.13 kDa" in reply
    assert "本次没有运行新工具" in reply
    assert events[-1]["type"] == "done"


@pytest.mark.parametrize("site_status", ["missing", "blocked", "completed"])
def test_geometry_sections_appear_once_and_preserve_evidence(site_status):
    from app.core.agent_graph import AgentOrchestrator

    results = [
        {"tool_name": "ligand_contact_analysis", "status": "completed", "result": {
            "status": "completed", "evidence_level": "GEOMETRY_ONLY",
            "ligand_instances": [{"instance_id": "A:ATP501", "atom_count": 31}],
            "contacts": [{"chain_id": "A", "residue_name": "LYS", "residue_number": 42,
                          "instance_id": "A:ATP501", "distance_angstrom": 3.2, "contact_type": "polar"}],
        }},
        {"tool_name": "structure_pocket_interface_analysis", "status": "completed", "result": {
            "status": "completed", "evidence_level": "GEOMETRY_ONLY",
            "pocket": {"residues": [{"chain_id": "A", "residue_name": "LYS", "residue_number": 42}]},
            "chain_interfaces": [{"chain_ids": ["A", "B"], "min_distance_angstrom": 3.8}],
        }},
    ]
    if site_status != "missing":
        results.append({"tool_name": "build_site_structure_function_features", "status": site_status,
                        "result": {"status": site_status, "features": []}})
    report = AgentOrchestrator()._build_fallback_report("分析这个 PDB 的性质", results)
    assert report.count("## 配体接触几何证据") == 1
    assert report.count("## 口袋、通道与链界面几何线索") == 1
    for fact in ("A:ATP501", "31 atoms", "A:LYS42", "3.2", "A/B", "3.8", "GEOMETRY_ONLY"):
        assert fact in report
    assert "不能证明结合能" in report
