"""Durable BLAST lifecycle; remote responses are controlled, storage is real."""
import importlib
import json

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

PARAMS = {"sequence": "ACDEFGHIKLMNPQRSTVWY", "database": "nr"}


async def test_waiting_survives_new_session_and_reuses_rid(session, monkeypatch):
    jobs = importlib.import_module("app.services.blast_jobs")
    calls = []

    async def submit(**params):
        calls.append("submit")
        return "RID123", 60

    async def poll(rid, max_results):
        calls.append(rid)
        return None if calls.count(rid) == 1 else [{"accession": "P12345"}]

    monkeypatch.setattr(jobs, "submit_blast", submit)
    monkeypatch.setattr(jobs, "poll_blast", poll)
    first = await jobs.advance_blast_job(session, "restart-task", PARAMS, now=1000)
    assert first["status"] == "waiting"
    assert first["rid"] == "RID123"
    assert first["next_poll_at"] >= 1060
    await session.commit()
    async with AsyncSession(session.bind, expire_on_commit=False) as restarted:
        waiting = await jobs.advance_blast_job(restarted, "restart-task", PARAMS, now=1060)
        assert waiting["status"] == "waiting"
        assert waiting["result"] is None
        await restarted.commit()
    result = await jobs.advance_blast_job(session, "restart-task", PARAMS, now=1120)
    assert result["status"] == "completed"
    assert result["result"]["results_count"] == 1
    assert result["result"]["evidence_status"] == "completed_with_hits"
    assert calls == ["submit", "RID123", "RID123"]


async def test_poll_network_error_preserves_rid_and_retries(session, monkeypatch):
    jobs = importlib.import_module("app.services.blast_jobs")

    async def submit(**params):
        return "RID456", 60

    async def poll(*args):
        raise httpx.ReadTimeout("temporary connection loss")

    monkeypatch.setattr(jobs, "submit_blast", submit)
    monkeypatch.setattr(jobs, "poll_blast", poll)
    await jobs.advance_blast_job(session, "network-task", PARAMS, now=1000)
    job = await jobs.advance_blast_job(session, "network-task", PARAMS, now=1060)
    assert job["status"] == "waiting"
    assert job["rid"] == "RID456"
    assert job["next_poll_at"] >= 1120
    assert job["network_errors"] == 1


async def test_wait_deadline_is_distinct_from_no_hits(session, monkeypatch):
    jobs = importlib.import_module("app.services.blast_jobs")

    async def submit(**params):
        return "RID789", 60

    monkeypatch.setattr(jobs, "submit_blast", submit)
    await jobs.advance_blast_job(session, "deadline-task", PARAMS, now=1000)
    job = await jobs.advance_blast_job(session, "deadline-task", PARAMS, now=100000)
    assert job["status"] == "degraded"
    assert job["result"]["error_code"] == "BLAST_WAIT_EXPIRED"
    assert job["rid"] == "RID789"


async def test_complete_xml_without_hits_is_completed_not_waiting(monkeypatch):
    blast = importlib.import_module("app.tools.blast_search")

    async def get(self, url, **kwargs):
        return httpx.Response(200, text='<BlastOutput><BlastOutput_iterations><Iteration><Iteration_hits/></Iteration></BlastOutput_iterations></BlastOutput>', request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    poll = getattr(blast, "poll_blast", None)
    assert poll is not None, "BLAST needs a reusable one-request result retrieval function"
    assert await poll("RID0", 10) == []


def test_blast_result_status_distinguishes_waiting_failure_and_terminal_no_hit():
    blast = importlib.import_module("app.tools.blast_search")
    no_hit = blast._result_payload(seq="ACDEFGHIKL", program="blastp", database="nr", hits=[], status="completed")
    waiting = blast._result_payload(seq="ACDEFGHIKL", program="blastp", database="nr", hits=[], status="waiting")
    failed = blast._result_payload(seq="ACDEFGHIKL", program="blastp", database="nr", hits=[], status="failed")
    with_hit = blast._result_payload(seq="ACDEFGHIKL", program="blastp", database="nr", hits=[{"accession": "P1"}], status="completed")
    assert no_hit["evidence_status"] == "completed_no_hit"
    assert waiting["evidence_status"] == "waiting"
    assert failed["evidence_status"] == "failed"
    assert with_hit["evidence_status"] == "completed_with_hits"


async def test_report_revision_preserves_original_and_is_idempotent(session):
    from app.models.user import User
    from app.models.conversation import Conversation, Message
    reports = importlib.import_module("app.services.blast_report_revision")
    user = User(email="blast-revision@example.com", hashed_password="unused", name="QA")
    session.add(user)
    await session.flush()
    conversation = Conversation(user_id=user.id, title="BLAST test")
    session.add(conversation)
    await session.flush()
    original = Message(conversation_id=conversation.id, role="assistant", content="原报告：等待同源搜索。",
                       tool_calls=json.dumps([{"name": "blast_search", "rawResult": json.dumps({"task_id": "report-task"})}]))
    session.add(original)
    await session.flush()
    task = {"task_id": "report-task", "tool_name": "blast_search", "status": "completed", "result": {
        "status": "completed", "database": "nr", "results_count": 1,
        "results": [{"accession": "P12345", "definition": "test protein", "best_identity_percent": 90, "best_e_value": 1e-20}],
        "evidence_source": {"status": "live", "live_query_executed": True}}}
    result = await reports.create_blast_report_revision(session, user_id=user.id, conversation_id=conversation.id, task=task)
    again = await reports.create_blast_report_revision(session, user_id=user.id, conversation_id=conversation.id, task=task)
    assert original.content == "原报告：等待同源搜索。"
    assert result["message_id"] != original.id
    assert result["message_id"] == again["message_id"]
    revised = await session.get(Message, result["message_id"])
    assert "P12345" in revised.content
    assert result["snapshot_id"]


async def test_report_revision_rejects_waiting_and_foreign_conversation(session):
    reports = importlib.import_module("app.services.blast_report_revision")
    with pytest.raises(ValueError):
        await reports.create_blast_report_revision(session, user_id=123, conversation_id=999,
            task={"task_id": "pending", "tool_name": "blast_search", "status": "waiting", "result": None})

@pytest.mark.parametrize('state', ['waiting', 'submitting', 'retry', 'retrying'])
def test_background_states_remain_pending_evidence(state):
    from app.services.analysis_recompute import build_recompute_decision
    decision = build_recompute_decision(analysis_fingerprint=None, requested=True,
        tool_results=[{'task_id': 'pending', 'tool_name': 'blast_search', 'status': state, 'result': None}])
    assert decision['status'] == 'tasks_not_terminal'


async def test_cancel_before_worker_prevents_submission(session, monkeypatch):
    jobs = importlib.import_module('app.services.blast_jobs')
    async def unexpected(**params):
        pytest.fail('Canceled task must never submit to NCBI')
    monkeypatch.setattr(jobs, 'submit_blast', unexpected)
    await jobs.cancel_blast_job(session, 'canceled-before-start')
    job = await jobs.advance_blast_job(session, 'canceled-before-start', PARAMS, now=1000)
    assert job['status'] == 'canceled'


async def test_cancel_during_submission_preserves_cancel_and_rid(session, monkeypatch):
    jobs = importlib.import_module('app.services.blast_jobs')
    async def submit(**params):
        await jobs.cancel_blast_job(session, 'cancel-during-submit')
        return 'SAVEDRID', 60
    monkeypatch.setattr(jobs, 'submit_blast', submit)
    job = await jobs.advance_blast_job(session, 'cancel-during-submit', PARAMS, now=1000)
    assert job['status'] == 'canceled'
    assert job['rid'] == 'SAVEDRID'


@pytest.mark.parametrize('remote_state', ['FAILED', 'UNKNOWN'])
async def test_remote_expired_is_terminal_failure(monkeypatch, remote_state):
    blast = importlib.import_module('app.tools.blast_search')
    async def get(self, url, **kwargs):
        return httpx.Response(200, text=f'Status={remote_state}', request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    with pytest.raises(RuntimeError):
        await blast.poll_blast('RID', 10)


@pytest.mark.parametrize('response', [httpx.Response(429, headers={'Retry-After': '180'}), httpx.Response(500), httpx.Response(200, text='<BlastOutput>broken')])
async def test_poll_transient_response_retries(session, monkeypatch, response):
    jobs = importlib.import_module('app.services.blast_jobs')
    async def submit(**params):
        return 'TRANSIENT', 60
    async def get(self, url, **kwargs):
        response.request = httpx.Request('GET', url)
        return response
    monkeypatch.setattr(jobs, 'submit_blast', submit)
    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    await jobs.advance_blast_job(session, 'transient', PARAMS, now=1000)
    job = await jobs.advance_blast_job(session, 'transient', PARAMS, now=1060)
    assert job['status'] == 'waiting'
    assert job['rid'] == 'TRANSIENT'
    assert job['network_errors'] == 1
    assert job['next_poll_at'] >= 1180

async def test_api_sql_status_resume_and_ownership_after_cache_expiry(client, session, monkeypatch):
    from app.models.user import User
    from app.models.tool_call import ToolTaskAudit
    from app.core.security import create_access_token
    from app.services.tool_task_store import record_tool_task_owner
    jobs = importlib.import_module('app.services.blast_jobs')
    scheduler = importlib.import_module('app.services.scheduler')
    user = User(email='blast-api@example.com', hashed_password='unused', name='QA')
    other = User(email='blast-other@example.com', hashed_password='unused', name='Other')
    session.add_all([user, other]); await session.flush()
    uid, other_id = user.id, other.id
    session.add(ToolTaskAudit(task_id='api-blast', user_id=uid, tool_name='blast_search', status='submitted'))
    await session.commit()
    async def submit(**params):
        return 'APIRID', 60
    monkeypatch.setattr(jobs, 'submit_blast', submit)
    await jobs.advance_blast_job(session, 'api-blast', PARAMS, now=1000)
    client.cookies.set('pa_token', create_access_token(uid))
    # No Redis owner entry: durable SQL ownership must still grant only this user.
    response = await client.get('/api/tools/tasks/api-blast')
    assert response.status_code == 200
    assert response.json()['status'] == 'waiting'
    assert response.json()['result'] is None
    assert response.json()['rid'] == 'APIRID'
    denied = await client.post('/api/tools/tasks/api-blast/report-revision', json={'conversation_id': 1})
    assert denied.status_code == 409
    client.cookies.set('pa_token', create_access_token(other_id))
    assert (await client.get('/api/tools/tasks/api-blast')).status_code == 403
    assert (await client.post('/api/tools/tasks/api-blast/resume')).status_code == 403
    client.cookies.set('pa_token', create_access_token(uid))
    await jobs.advance_blast_job(session, 'api-blast', PARAMS, now=100000)
    queued = []
    monkeypatch.setattr(scheduler.run_tool_task, 'apply_async', lambda **kw: queued.append(kw))
    resumed = await client.post('/api/tools/tasks/api-blast/resume')
    assert resumed.status_code == 200
    assert resumed.json()['rid'] == 'APIRID'
    assert queued[0]['task_id'] == 'api-blast'
    assert (await client.post('/api/tools/tasks/api-blast/resume')).status_code == 409
    # Cancel and queued retry must never resurrect this RID.
    await record_tool_task_owner('api-blast', uid, 'blast_search')
    monkeypatch.setattr(importlib.import_module('app.api.tools'), 'cancel_task', lambda _: True)
    assert (await client.post('/api/tools/tasks/api-blast/cancel')).status_code == 200
    job = await jobs.advance_blast_job(session, 'api-blast', PARAMS)
    assert job['status'] == 'canceled'
    assert (await client.post('/api/tools/tasks/api-blast/resume')).status_code == 409


def test_worker_retry_preserves_id_and_is_not_swallowed(monkeypatch):
    from celery.exceptions import Retry
    scheduler = importlib.import_module('app.services.scheduler')
    jobs = importlib.import_module('app.services.blast_jobs')
    task = scheduler.run_tool_task
    assert task.max_retries is None, "Celery retry(None) otherwise falls back to its default three attempts"
    calls = []
    async def step(task_id, params):
        calls.append(task_id)
        return {'status': 'waiting', 'next_poll_at': 9999999999}
    def retry(**kw):
        assert kw['max_retries'] is None
        raise Retry()
    monkeypatch.setattr(jobs, 'run_worker_blast_step', step)
    monkeypatch.setattr(task, 'update_state', lambda **kw: None)
    monkeypatch.setattr(task, 'retry', retry)
    task.push_request(id='stable-worker-id')
    try:
        with pytest.raises(Retry):
            task.run('blast_search', PARAMS)
    finally:
        task.pop_request()
    assert calls == ['stable-worker-id']

async def test_completed_revision_api_persists_and_rejects_unrelated_conversation(client, session):
    from app.models.user import User
    from app.models.conversation import Conversation, Message
    from app.models.domain import KVStore
    from app.models.tool_call import ToolTaskAudit
    from app.core.security import create_access_token
    user = User(email='report-api@example.com', hashed_password='unused', name='QA')
    session.add(user); await session.flush()
    uid = user.id
    conv = Conversation(user_id=uid, title='Original')
    unrelated = Conversation(user_id=uid, title='Unrelated')
    session.add_all([conv, unrelated]); await session.flush()
    cid, other_cid = conv.id, unrelated.id
    original = Message(conversation_id=cid, role='assistant', content='Original immutable report',
        tool_calls=json.dumps([{'name':'blast_search', 'rawResult':json.dumps({'task_id':'report-api'})}]))
    session.add_all([original, ToolTaskAudit(task_id='report-api', user_id=uid, tool_name='blast_search', status='completed'),
        KVStore(key='blast-job:report-api', value=json.dumps({'task_id':'report-api','status':'completed','rid':'APIREPORT',
            'result':{'status':'completed','database':'swissprot','rid':'APIREPORT','results':[
                {'accession':'P12345','definition':"enzyme's <script>alert(1)</script>|[bad](https://evil.example)", 'best_identity_percent':95,'best_e_value':'1e-30'}],
                'evidence_source':{'status':'live','live_query_executed':True}}}))])
    await session.commit()
    client.cookies.set('pa_token', create_access_token(uid))
    invalid = await client.post('/api/tools/tasks/report-api/report-revision', json={'conversation_id':other_cid})
    assert invalid.status_code == 409
    response = await client.post('/api/tools/tasks/report-api/report-revision', json={'conversation_id':cid})
    assert response.status_code == 200
    receipt = response.json()
    await session.commit()
    again = await client.post('/api/tools/tasks/report-api/report-revision', json={'conversation_id':cid})
    assert again.status_code == 200
    assert again.json()['message_id'] == receipt['message_id']
    saved = await client.get(f'/api/conversations/{cid}')
    assert saved.status_code == 200
    msgs = saved.json()['messages']
    assert len(msgs) == 2
    assert msgs[0]['content'] == 'Original immutable report'
    assert 'P12345' in msgs[1]['content']
    assert '<script>' not in msgs[1]['content']
    assert '[bad]' not in msgs[1]['content']
