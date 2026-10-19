"""Append a traceable BLAST evidence supplement without mutating prior reports."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.models.domain import KVStore
from app.services.analysis_recompute import build_recompute_decision, persist_recompute_snapshot


def _has_task(message: Message, task_id: str) -> bool:
    try:
        calls = json.loads(message.tool_calls or "[]")
    except (TypeError, ValueError):
        return False
    for call in calls if isinstance(calls, list) else []:
        if not isinstance(call, dict):
            continue
        for field in ("rawResult", "raw_result", "resultPreview", "result_preview", "result"):
            value = call.get(field)
            try:
                value = json.loads(value) if isinstance(value, str) else value
            except ValueError:
                continue
            if isinstance(value, dict) and value.get("task_id") == task_id:
                return True
    return False


async def create_blast_report_revision(session: AsyncSession, *, user_id: int, conversation_id: int, task: dict) -> dict:
    decision = build_recompute_decision(analysis_fingerprint=None, tool_results=[task], requested=True)
    if task.get("tool_name") != "blast_search" or decision["status"] != "recompute_ready":
        raise ValueError("BLAST_RESULT_NOT_READY: usable completed evidence is required")
    # Serializes concurrent clicks for this conversation, including idempotency lookup.
    conversation = (await session.execute(select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user_id).with_for_update())).scalar_one_or_none()
    if not conversation:
        raise ValueError("CONVERSATION_NOT_FOUND")
    messages = list((await session.execute(select(Message).where(
        Message.conversation_id == conversation_id, Message.role == "assistant").order_by(Message.id))).scalars())
    base = next((m for m in messages if _has_task(m, task["task_id"])), None)
    if not base:
        raise ValueError("TASK_NOT_IN_CONVERSATION: the task must belong to this report")
    key = f"blast-revision:{user_id}:{conversation_id}:{task['task_id']}:{decision['evidence_snapshot_fingerprint']}"
    previous = await session.get(KVStore, key)
    if previous:
        return json.loads(previous.value)
    fingerprint = hashlib.sha256(base.content.encode()).hexdigest()
    decision = build_recompute_decision(analysis_fingerprint=fingerprint, tool_results=[task], requested=True)
    snapshot = await persist_recompute_snapshot(session, user_id=user_id, conversation_id=conversation_id,
                                              decision=decision, task_snapshot=[task])
    result = task["result"]
    hits = result.get("results") or []
    evidence_status = str(
        result.get("evidence_status")
        or ("completed_with_hits" if hits else "completed_no_hit")
    )
    def cell(value):
        # Remote annotations cannot inject Markdown, links or HTML into a report.
        import html
        return html.escape(str(value if value is not None else "—")).replace("|", "&#124;").replace("\n", " ").replace("\r", " ").replace("[", "&#91;").replace("]", "&#93;").replace("`", "&#96;")
    content = ["## 同源证据更新报告", "", f"生成时间：{datetime.now(UTC).isoformat()}",
               f"原报告编号：{base.id}；证据快照：{snapshot['snapshot_id']}",
               "", "### 本次新增结果", "",
               f"数据库：{cell(result.get('database'))}；NCBI 任务：{cell(result.get('rid') or task['task_id'])}。",
               f"搜索已完成，状态={cell(evidence_status)}，返回 {len(hits)} 个命中。", ""]
    if hits:
        content += ["| 序列编号 | 注释 | 一致性 (%) | E-value |", "| --- | --- | --- | --- |"]
        for hit in hits:
            content.append("| " + " | ".join(cell(hit.get(k)) for k in
                ("accession", "definition", "best_identity_percent", "best_e_value")) + " |")
    else:
        content.append("在本次数据库和搜索参数下未检出命中；不能外推为不存在同源蛋白。")
    content += ["", "### 对原报告的影响", "",
                "原报告中本任务的‘等待搜索结果’状态已由本版的完成结果补充。原报告作为历史版本保留。",
                "本版更新同源搜索证据。序列相似性不能直接证明酶功能、突变收益或实验性能；候选排序及相关结论仍需结合覆盖度、编号映射和实验验证重新分析。"]
    revision = Message(conversation_id=conversation_id, role="assistant", content="\n".join(content),
        tool_calls=json.dumps([{"id": f"blast-revision-{task['task_id']}", "name": "blast_search", "status": "completed",
                                "evidence_status": evidence_status,
                                "rawResult": json.dumps(result), "resultPreview": json.dumps(result)}]))
    session.add(revision)
    conversation.updated_at = datetime.now(UTC)
    await session.flush()
    receipt = {"message_id": revision.id, "base_message_id": base.id, "conversation_id": conversation_id,
               "snapshot_id": snapshot["snapshot_id"], "evidence_snapshot_fingerprint": decision["evidence_snapshot_fingerprint"]}
    session.add(KVStore(key=key, value=json.dumps(receipt)))
    await session.flush()
    return receipt
