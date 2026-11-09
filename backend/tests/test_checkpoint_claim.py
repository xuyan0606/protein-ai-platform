"""Exactly-once confirmation and explicit structure model scope regressions."""
import pytest
from app.models.conversation import Conversation
from app.models.user import User
from app.services.strategy_checkpoint import persist_strategy_checkpoint, mark_strategy_checkpoint_executing


@pytest.mark.parametrize("terminal", ["executing", "completed", "superseded"])
async def test_checkpoint_claim_cannot_be_repeated_or_revive_terminal_state(session, terminal):
    user = User(email="claim@example.com", hashed_password=User.hash_password("password123"), name="Claim QA")
    session.add(user)
    await session.flush()
    conv = Conversation(user_id=user.id, title="claim")
    session.add(conv)
    await session.flush()
    saved = await persist_strategy_checkpoint(session, user_id=user.id, conversation_id=conv.id,
        project_id=None, task_text="quality", task_fingerprint="fp", strategy_signature="sig", plan_payload=[])
    await session.commit()
    first = await mark_strategy_checkpoint_executing(session, checkpoint_id=saved["id"], user_id=user.id)
    await session.commit()
    assert first["status"] == "executing"
    from app.models.strategy_checkpoint import StrategyCheckpoint
    row = await session.get(StrategyCheckpoint, saved["id"])
    row.status = terminal
    await session.commit()
    second = await mark_strategy_checkpoint_executing(session, checkpoint_id=saved["id"], user_id=user.id)
    assert second is None
    await session.refresh(row)
    assert row.status == terminal


def test_report_discloses_first_model_scope():
    from app.core.agent_graph import AgentOrchestrator
    orch = AgentOrchestrator()
    report = orch._build_fallback_report("仅本地检查结构质量", [{
        "tool_name": "structure_search_foldseek", "status": "completed", "result": {
            "status": "completed", "backend": "input_parser", "search_executed": False,
            "query_structure": {"chain_count": 1, "total_residues": 46, "total_atoms": 327,
                "model_scope": {"selected_model": 3, "available_models": [3, 9], "policy": "first_model"}}
        }}])
    assert "模型 3" in report
    assert "3, 9" in report
    assert "未进行集合平均" in report


async def test_two_sessions_that_read_same_revision_only_one_claims(session, engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.services.strategy_checkpoint import get_active_strategy_checkpoint
    user = User(email="two-claims@example.com", hashed_password=User.hash_password("password123"), name="Claim QA")
    session.add(user)
    await session.flush()
    conv = Conversation(user_id=user.id, title="concurrent claims")
    session.add(conv)
    await session.flush()
    uid, cid = user.id, conv.id
    await persist_strategy_checkpoint(session, user_id=uid, conversation_id=cid,
        project_id=None, task_text="quality", task_fingerprint="fp", strategy_signature="sig", plan_payload=[])
    await session.commit()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as first, factory() as second:
        a = await get_active_strategy_checkpoint(first, user_id=uid, conversation_id=cid)
        b = await get_active_strategy_checkpoint(second, user_id=uid, conversation_id=cid)
        assert a["id"] == b["id"]
        claimed = await mark_strategy_checkpoint_executing(first, checkpoint_id=a["id"], user_id=uid)
        await first.commit()
        lost = await mark_strategy_checkpoint_executing(second, checkpoint_id=b["id"], user_id=uid)
        await second.commit()
        assert claimed is not None
        assert lost is None
