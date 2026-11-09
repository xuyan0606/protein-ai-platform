"""BLAST audits must advance without a browser polling task status."""

from sqlalchemy.ext.asyncio import AsyncSession
import pytest

from app.models.user import User
from app.services import blast_jobs as jobs
from app.services.tool_task_audit import list_task_audits, record_task_submitted

PARAMS = {"sequence": "ACDEFGHIKLMNPQRSTVWY", "database": "nr"}


async def seed_owner(session):
    user = User(email="blast-audit@example.com", hashed_password="unused", name="QA")
    session.add(user)
    await session.commit()
    return user.id


async def submit_audit(session, uid):
    await record_task_submitted(session, task_id="audit-blast", user_id=uid, tool_name="blast_search",
                                params=PARAMS, queue="default", soft_time_limit=100, time_limit=120)
    await session.commit()


async def stored_audit(session, uid):
    async with AsyncSession(session.bind, expire_on_commit=False) as reader:
        rows = await list_task_audits(reader, user_id=uid)
        assert len(rows) == 1
        return rows[0]


@pytest.mark.parametrize("outcome", ["completed", "degraded", "failed", "canceled"])
async def test_worker_updates_persistent_audit_without_status_poll(session, monkeypatch, outcome):
    uid = await seed_owner(session)
    await submit_audit(session, uid)

    async def submit(**params):
        return "AUDITRID", 60

    async def poll(*args):
        if outcome == "failed":
            raise RuntimeError("NCBI remote failed")
        return []

    monkeypatch.setattr(jobs, "submit_blast", submit)
    monkeypatch.setattr(jobs, "poll_blast", poll)
    await jobs.advance_blast_job(session, "audit-blast", PARAMS, now=1000)
    waiting = await stored_audit(session, uid)
    assert (waiting["status"], waiting["stage"]) == ("waiting", "ncbi_waiting")
    assert waiting["terminal_recorded_at"] is None
    if outcome == "canceled":
        await jobs.cancel_blast_job(session, "audit-blast")
    else:
        await jobs.advance_blast_job(session, "audit-blast", PARAMS,
                                     now=100000 if outcome == "degraded" else 1060)
    audit = await stored_audit(session, uid)
    assert audit["status"] == outcome
    assert audit["progress"] == 100
    assert audit["terminal_recorded_at"] is not None
    if outcome in {"degraded", "failed"}:
        assert audit["error"]
        assert audit["result_summary"]["status"] == outcome


async def test_late_submission_audit_uses_existing_terminal_job(session, monkeypatch):
    uid = await seed_owner(session)

    async def submit(**params):
        raise RuntimeError("submission rejected")

    monkeypatch.setattr(jobs, "submit_blast", submit)
    # Dispatch occurs before submission audit is committed by the API.
    await jobs.advance_blast_job(session, "audit-blast", PARAMS, now=1000)
    await submit_audit(session, uid)
    audit = await stored_audit(session, uid)
    assert audit["status"] == "failed"
    assert audit["terminal_recorded_at"]


async def test_resume_clears_old_audit_terminal_state_and_keeps_rid(client, session, monkeypatch):
    from app.core.security import create_access_token
    from app.services import scheduler

    uid = await seed_owner(session)
    await submit_audit(session, uid)

    async def submit(**params):
        return "RESUMERID", 60

    monkeypatch.setattr(jobs, "submit_blast", submit)
    await jobs.advance_blast_job(session, "audit-blast", PARAMS, now=1000)
    await jobs.advance_blast_job(session, "audit-blast", PARAMS, now=100000)
    before = await stored_audit(session, uid)
    assert before["status"] == "degraded"
    monkeypatch.setattr(scheduler.run_tool_task, "apply_async", lambda **kwargs: None)
    client.cookies.set("pa_token", create_access_token(uid))
    response = await client.post("/api/tools/tasks/audit-blast/resume")
    assert response.status_code == 200
    assert response.json()["rid"] == "RESUMERID"
    audit = await stored_audit(session, uid)
    assert audit["status"] == "waiting"
    assert audit["error"] is None
    assert audit["terminal_recorded_at"] is None
    assert audit["result_summary"] is None
