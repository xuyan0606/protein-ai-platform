"""Parsed model metadata must survive the summary boundary."""
import asyncio
import pytest

from app.api import pdb


@pytest.mark.asyncio
async def test_stalled_summary_returns_status_and_cancels_provider(monkeypatch):
    cancelled = asyncio.Event()
    async def complete(**kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    monkeypatch.setattr(pdb.llm_gateway, 'complete', complete)
    monkeypatch.setattr(pdb, 'PDB_SUMMARY_TIMEOUT_SECONDS', 0.01, raising=False)
    result = await asyncio.wait_for(pdb._summarize_pdb_analysis({'chains': []}, None), 0.2)
    assert result == {'summary_status': 'timeout'}
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_unknown_summary_model_uses_resolved_fallback_id(monkeypatch):
    async def complete(**kwargs):
        assert kwargs['model_id'] == 'deepseek-chat'
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': '模型质量不能证明热稳定性。'}}]}
    monkeypatch.setattr(pdb.llm_gateway, 'complete', complete)
    result = await pdb._summarize_pdb_analysis({'chains': []}, 'unknown-model')
    assert result['summary_model_id'] == 'deepseek-chat'
    assert result['ai_summary'] == '模型质量不能证明热稳定性。'


@pytest.mark.asyncio
async def test_summary_receives_known_model_quality_metadata(monkeypatch):
    captured = {}
    async def complete(**kwargs):
        captured.update(kwargs)
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': '模型摘要。'}}]}
    monkeypatch.setattr(pdb.llm_gateway, 'complete', complete)
    result = await pdb._summarize_pdb_analysis({
        'method': 'THEORETICAL MODEL (SWISS-MODEL SERVER)', 'chains': [],
        'theoretical_model': {'source': 'SWISS-MODEL', 'gmqe': 0.99, 'templates': []},
        'b_factor_semantics': 'model_quality_per_residue_score',
        'b_factor_scope': 'local quality score, not thermostability'}, 'claude-fable-5')
    prompt = captured['messages'][-1]['content']
    assert 'gmqe' in prompt and '0.99' in prompt
    assert 'model_quality_per_residue_score' in prompt
    assert result['ai_summary'] == '模型摘要。'


@pytest.mark.asyncio
async def test_truncated_summary_is_not_published_as_complete(monkeypatch):
    async def complete(**kwargs):
        return {'choices': [{'finish_reason': 'length', 'message': {'content': 'B-factor字段（均值'}}]}
    monkeypatch.setattr(pdb.llm_gateway, 'complete', complete)
    result = await pdb._summarize_pdb_analysis({'chains': []}, 'claude-fable-5')
    assert not result.get('ai_summary')
    assert result['summary_status'] == 'truncated_not_used'


@pytest.mark.asyncio
@pytest.mark.parametrize('finish_reason', ['length', 'max_tokens'])
async def test_summary_recovers_from_truncation(monkeypatch, finish_reason):
    responses = iter([
        {'choices': [{'finish_reason': finish_reason, 'message': {'content': '字段（均值'}}]},
        {'choices': [{'finish_reason': 'stop', 'message': {'content': '模型 GMQE 为 0.99，仅为模型质量估计。'}}]},
    ])
    async def complete(**kwargs):
        return next(responses)
    monkeypatch.setattr(pdb.llm_gateway, 'complete', complete)
    result = await pdb._summarize_pdb_analysis({
        'chains': [], 'theoretical_model': {'gmqe': 0.99}}, 'claude-fable-5')
    assert result['ai_summary'] == '模型 GMQE 为 0.99，仅为模型质量估计。'
    assert result['summary_model_id'] == 'claude-fable-5'


@pytest.mark.asyncio
async def test_summary_retry_failure_preserves_truncation_status(monkeypatch):
    responses = iter([
        {'choices': [{'finish_reason': 'length', 'message': {'content': '字段（均值'}}]},
        RuntimeError('temporary upstream failure'),
    ])
    async def complete(**kwargs):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(pdb.llm_gateway, 'complete', complete)
    result = await pdb._summarize_pdb_analysis({'chains': []}, 'claude-fable-5')
    assert not result.get('ai_summary')
    assert result['summary_status'] == 'truncated_not_used'
