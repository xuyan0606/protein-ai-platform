import pytest
from sqlalchemy import select

from app.models.identity_consistency import IdentityConsistencyRecord
from app.services.identity_consistency_store import (
    get_latest_identity_record,
    persist_identity_record,
)


@pytest.mark.asyncio
async def test_identity_consistency_record_persists_versioned_identity_and_conflict(session):
    from app.models.user import User

    user = User(
        email="identity-store@example.com",
        hashed_password=User.hash_password("password123"),
        name="Identity Store",
    )
    session.add(user)
    await session.flush()

    saved = await persist_identity_record(
        session,
        user_id=user.id,
        sequence_hash="a" * 64,
        model_version="model-v1",
        evidence_version="evidence-v1",
        identity="aspartic protease",
        status="CONSISTENT",
    )
    await session.commit()

    assert saved["sequence_hash"] == "a" * 64
    assert saved["status"] == "CONSISTENT"
    latest = await get_latest_identity_record(
        session,
        user_id=user.id,
        sequence_hash="a" * 64,
        model_version="model-v1",
        evidence_version="evidence-v1",
    )
    assert latest["identity"] == "aspartic protease"
    assert latest["model_version"] == "model-v1"


@pytest.mark.asyncio
async def test_identity_consistency_record_requires_versioned_unique_key(session):
    columns = IdentityConsistencyRecord.__table__.columns.keys()
    assert {"sequence_hash", "model_version", "evidence_version", "identity", "status"} <= set(columns)
    assert any(
        constraint.name == "uq_identity_consistency_versioned"
        for constraint in IdentityConsistencyRecord.__table__.constraints
    )


@pytest.mark.asyncio
async def test_identity_consistency_persistence_is_idempotent_for_same_versioned_identity(session):
    from app.models.user import User

    user = User(
        email="identity-idempotent@example.com",
        hashed_password=User.hash_password("password123"),
        name="Identity Idempotent",
    )
    session.add(user)
    await session.flush()

    kwargs = {
        "user_id": user.id,
        "sequence_hash": "c" * 64,
        "model_version": "model-v1",
        "evidence_version": "evidence-v1",
        "identity": "lipase",
        "status": "CONSISTENT",
    }
    first = await persist_identity_record(session, **kwargs)
    second = await persist_identity_record(session, **kwargs)
    await session.commit()

    assert second["id"] == first["id"]
    rows = (
        await session.execute(
            select(IdentityConsistencyRecord).where(
                IdentityConsistencyRecord.user_id == user.id,
                IdentityConsistencyRecord.sequence_hash == "c" * 64,
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_orchestrator_persists_identity_consistency_result(session):
    from app.core.agent_graph import AgentOrchestrator
    from app.models.user import User

    user = User(
        email="identity-orchestrator@example.com",
        hashed_password=User.hash_password("password123"),
        name="Identity Orchestrator",
    )
    session.add(user)
    await session.flush()
    orchestrator = AgentOrchestrator()

    await orchestrator._persist_identity_consistency(
        "MKTAYIAK",
        {"identity_label": "lipase", "model_version": "m1", "evidence_version": "e1"},
        {"status": "CONSISTENT", "sequence_hash": "b" * 64},
        current_user={"id": user.id},
        audit_session=session,
    )
    await session.commit()

    latest = await get_latest_identity_record(
        session,
        user_id=user.id,
        sequence_hash="b" * 64,
        model_version="m1",
        evidence_version="e1",
    )
    assert latest["identity"] == "lipase"
