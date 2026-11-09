"""A valid direct channel must remain selectable when the relay is unavailable."""
from __future__ import annotations

from app.core import llm_gateway, llm_policy


def test_direct_deepseek_is_selectable_with_disabled_relay(monkeypatch):
    monkeypatch.setattr(llm_policy.settings, 'LLM_DISABLED_PROVIDERS', 'kuaPao,dashscope')
    monkeypatch.setattr(llm_policy.settings, 'DEEPSEEK_API_KEY', 'test-configured')
    monkeypatch.setattr(llm_policy.settings, 'KUAPAO_API_KEY', 'test-invalid-relay')
    monkeypatch.setattr(llm_policy, '_runtime_unavailable_models', set())

    selected = llm_gateway.llm_gateway.resolve('deepseek-chat')

    assert selected is not None
    assert selected.provider == 'deepseek'
    assert selected.model == llm_policy.settings.DEEPSEEK_MODEL
    assert selected.name == 'DeepSeek'
    listed = {row['id']: row for row in llm_gateway.llm_gateway.list_models()}
    assert listed['deepseek-chat']['available'] is True
    assert listed['gpt6-sol']['available'] is False
    assert llm_gateway.llm_gateway.resolve('gpt6-sol') is None


def test_empty_native_model_is_unavailable_even_with_valid_credential(monkeypatch):
    monkeypatch.setattr(llm_policy.settings, 'LLM_DISABLED_PROVIDERS', '')
    monkeypatch.setattr(llm_policy.settings, 'DEEPSEEK_API_KEY', 'test-configured')
    monkeypatch.setattr(llm_policy, '_runtime_unavailable_models', set())

    assert llm_policy.is_model_available('deepseek', '') is False
    assert llm_policy.is_model_available('deepseek', '   ') is False


def test_fallback_skips_unset_native_model(monkeypatch):
    monkeypatch.setattr(llm_policy.settings, 'LLM_PROVIDER', 'deepseek')
    monkeypatch.setattr(llm_policy.settings, 'LLM_MODEL', 'deepseek-flash')
    monkeypatch.setattr(llm_policy.settings, 'LLM_FALLBACK_PROVIDER', 'deepseek')
    monkeypatch.setattr(llm_policy.settings, 'LLM_FALLBACK_MODEL', '')
    monkeypatch.setattr(llm_policy.settings, 'LLM_DISABLED_PROVIDERS', 'kuaPao,dashscope')
    monkeypatch.setattr(llm_policy.settings, 'DEEPSEEK_API_KEY', 'test-configured')
    monkeypatch.setattr(llm_policy, '_runtime_unavailable_models', set())
    monkeypatch.setattr(llm_policy, 'MODEL_REGISTRY', [])

    assert llm_policy.candidate_provider_chain(None, None) == [('deepseek', 'deepseek-flash')]
