"""Chat endpoints — SSE streaming with JWT protection and DB persistence."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent import orchestrator
from app.core.database import get_session
from app.core.llm_gateway import get_available_models, llm_gateway
from app.core.security import get_current_user
from app.models.conversation import Conversation, Message
from app.services.project_acl import can_perform_project_action, get_project_access
from app.services.agent_policy import get_agent_strategy_policy
from app.services.strategy_checkpoint import (
    get_active_strategy_checkpoint,
    list_recent_strategy_memory,
    mark_strategy_checkpoint_completed,
    list_strategy_checkpoints,
    persist_strategy_checkpoint,
)

logger = logging.getLogger(__name__)

router = APIRouter()
STREAM_HEARTBEAT_SECONDS = 15.0
SSE_HEARTBEAT_FRAME = ": heartbeat\n\n"


def _checkpoint_for_display(checkpoint: dict[str, Any] | None) -> dict[str, Any] | None:
    if not checkpoint:
        return None
    displayed = dict(checkpoint)
    displayed["task_text"] = orchestrator._display_task_summary(
        str(checkpoint.get("task_text") or "")
    )
    displayed["plan_payload"] = orchestrator._sanitize_plan_for_display(
        checkpoint.get("plan_payload") or []
    )
    return displayed


def _encode_sse(data: str, event: str | None = None) -> str:
    """Encode one SSE frame."""
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    for line in str(data).splitlines() or [""]:
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


async def _iter_with_sse_heartbeat(events, interval: float = STREAM_HEARTBEAT_SECONDS):
    """Yield upstream events, injecting SSE comments while long awaits are pending."""
    pending = asyncio.create_task(events.__anext__())
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield SSE_HEARTBEAT_FRAME
                continue

            try:
                event = pending.result()
            except StopAsyncIteration:
                break

            yield event
            pending = asyncio.create_task(events.__anext__())
    finally:
        if pending and not pending.done():
            pending.cancel()
            with suppress(asyncio.CancelledError):
                await pending


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    project_id: str | None = None  # bind conversation to project for auto-publish
    history: list[dict] = []
    model: str | None = None  # stable model_id exposed by the LLM gateway
    analysis_depth: str | None = None  # fast | standard | deep
    agent_control: str | None = None  # plan_only | execute_confirmed | revise_plan
    confirmed_plan: Any = None
    strategy_signature: str | None = None
    task_fingerprint: str | None = None


def _normalize_analysis_depth(value: str | None) -> str:
    normalized = (value or "standard").strip().lower()
    if normalized not in {"fast", "standard", "deep"}:
        return "standard"
    return normalized


async def _assert_project_write_access(
    db: AsyncSession,
    *,
    project_id: str | None,
    user_id: int | str,
) -> None:
    if not project_id:
        return
    project, access_role = await get_project_access(db, project_id=project_id, user_id=user_id)
    if not project or not can_perform_project_action(access_role, "project.chat.bind"):
        raise HTTPException(status_code=404, detail="Project not found")


async def _load_conversation_history_for_agent(
    db: AsyncSession,
    *,
    conversation_id: int,
    current_message_id: int | None,
    request_history: list[dict],
    limit: int = 12,
) -> list[dict[str, str]]:
    """Merge client history with server-side conversation memory.

    The browser normally sends the visible message list, but that state can be
    empty after refresh, route restore, or cross-device continuation.  The
    backend owns the conversation_id and must provide a durable fallback so
    follow-up turns can still inherit uploaded structures and prior context.
    """
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(role: Any, content: Any) -> None:
        if role not in {"user", "assistant", "system", "tool"}:
            return
        if not isinstance(content, str) or not content.strip():
            return
        key = (str(role), content)
        if key in seen:
            return
        seen.add(key)
        normalized.append({"role": str(role), "content": content})

    db_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.id != current_message_id if current_message_id is not None else True)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    db_messages = list(reversed(db_result.scalars().all()))
    for message in db_messages:
        add(message.role, message.content)

    for item in request_history[-limit:]:
        if not isinstance(item, dict):
            continue
        add(item.get("role"), item.get("content"))

    return normalized[-limit:]


@router.post("/stream")
async def stream_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """SSE streaming chat endpoint — JWT-protected, DB-persisted."""

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message must not be empty")
    await _assert_project_write_access(db, project_id=req.project_id, user_id=current_user["id"])
    analysis_depth = _normalize_analysis_depth(req.analysis_depth)

    # Validate conversation ownership if conversation_id is provided
    conversation: Conversation | None = None
    if req.conversation_id is not None:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == req.conversation_id,
                Conversation.user_id == current_user["id"],
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    # Create a new conversation implicitly if none provided
    if conversation is None:
        conversation = Conversation(
            user_id=current_user["id"],
            title=req.message[:80] if len(req.message) > 80 else req.message,
            project_id=req.project_id,
        )
        db.add(conversation)
        await db.flush()
    elif req.project_id and not conversation.project_id:
        # Bind existing conversation to project
        conversation.project_id = req.project_id
        await db.flush()

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    await db.flush()

    conv_id = conversation.id
    default_title = req.message[:80] if len(req.message) > 80 else req.message
    should_auto_title = conversation.title == default_title

    # Persist the conversation shell and user message before the SSE response starts.
    # If commit is deferred until the streaming response tears down, any commit-time
    # failure surfaces as a truncated chunked response in the browser.
    await db.commit()

    from app.core.metrics import sse_connections_active

    async def event_generator():
        sse_connections_active.inc()
        full_response: list[str] = []
        tool_calls_data: list[dict] = []
        stream_error: str | None = None
        latest_plan_state: dict | None = None
        latest_raw_plan_payload: list[dict] | None = None
        confirmed_checkpoint_id: int | None = None
        try:
            confirmed_plan = req.confirmed_plan
            strategy_signature = req.strategy_signature
            task_fingerprint = req.task_fingerprint
            message_for_orchestrator = req.message
            active_checkpoint = None
            if req.agent_control == "execute_confirmed":
                active_checkpoint = await get_active_strategy_checkpoint(
                    db,
                    user_id=current_user["id"],
                    conversation_id=conv_id,
                )
            if req.agent_control == "execute_confirmed" and active_checkpoint:
                # The server-side active checkpoint is authoritative.  UI state
                # may be stale after refresh/publish actions; do not let a
                # malformed or old client payload block a valid button confirm.
                confirmed_plan = active_checkpoint["plan_payload"]
                strategy_signature = active_checkpoint["strategy_signature"]
                task_fingerprint = active_checkpoint["task_fingerprint"]
                message_for_orchestrator = active_checkpoint["task_text"]
                confirmed_checkpoint_id = int(active_checkpoint["id"])
            elif req.agent_control == "execute_confirmed":
                # No server-side awaiting checkpoint means there is nothing to
                # confirm.  Treat stale browser state as expired instead of
                # validating whatever old plan payload the client still has.
                confirmed_plan = None
                strategy_signature = None
                task_fingerprint = None
            agent_history = await _load_conversation_history_for_agent(
                db,
                conversation_id=conv_id,
                current_message_id=user_msg.id,
                request_history=req.history,
            )
            checkpoint_task_text = req.message
            if (
                req.agent_control != "execute_confirmed"
                and orchestrator._message_requests_continuation(req.message)
            ):
                prior_summary = next(
                    (
                        orchestrator._display_task_summary(item.get("content", ""))
                        for item in reversed(agent_history)
                        if item.get("role") == "user"
                        and not str(item.get("content") or "").startswith(("确认执行", "修改分析策略"))
                    ),
                    "",
                )
                if prior_summary:
                    checkpoint_task_text = (
                        f"{req.message}\n[Prior user request summary: {prior_summary}]"
                    )

            events = orchestrator.stream_chat(
                message_for_orchestrator,
                agent_history,
                model_id=req.model,
                analysis_depth=analysis_depth,
                agent_control=req.agent_control,
                confirmed_plan=confirmed_plan,
                strategy_signature=strategy_signature,
                task_fingerprint=task_fingerprint,
                current_user=current_user,
                audit_session=db,
                conversation_id=conv_id,
                project_id=conversation.project_id,
            )
            async for frame in _iter_with_sse_heartbeat(events, interval=STREAM_HEARTBEAT_SECONDS):
                if frame == SSE_HEARTBEAT_FRAME:
                    yield frame
                    continue

                # Collect text content and tool calls for DB persistence
                event = frame
                if isinstance(event, str):
                    try:
                        parsed = json.loads(event)
                        if parsed.get("type") == "text":
                            content = parsed.get("content", "")
                            if content:
                                full_response.append(str(content))
                        elif parsed.get("type") == "state":
                            if parsed.get("waiting_for") == "plan_confirmation" and parsed.get("plan"):
                                latest_plan_state = parsed
                                raw_payload = getattr(orchestrator._snapshot, "raw_plan_payload", None)
                                if isinstance(raw_payload, list) and raw_payload:
                                    latest_raw_plan_payload = [dict(item) for item in raw_payload if isinstance(item, dict)]
                            for sr in parsed.get("step_results", []):
                                step_id = f"plan-{sr.get('step', 0)}"
                                existing = [t for t in tool_calls_data if t.get("id") == step_id]
                                if not existing:
                                    tool_calls_data.append({
                                        "id": step_id,
                                        "name": sr.get("tool", "unknown"),
                                        "status": sr.get("status", "unknown"),
                                        "duration": sr.get("duration", 0),
                                        "error": sr.get("error"),
                                        "resultPreview": sr.get("result_preview", "")[:2000] if sr.get("result_preview") else None,
                                        "rawResult": sr.get("raw_result") if sr.get("raw_result") else None,
                                    })
                                else:
                                    existing[0]["status"] = sr.get("status", existing[0]["status"])
                                    existing[0]["error"] = sr.get("error", existing[0].get("error"))
                                    if sr.get("result_preview"):
                                        existing[0]["resultPreview"] = sr["result_preview"][:2000]
                                    if sr.get("raw_result"):
                                        existing[0]["rawResult"] = sr["raw_result"]
                        if parsed.get("type") == "done":
                            parsed["conversation_id"] = conv_id
                            event = json.dumps(parsed, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif isinstance(event, dict):
                    content = event.get("content", "")
                    if content:
                        full_response.append(str(content))
                yield _encode_sse(event, "message")

        except Exception as e:
            logger.exception("Chat stream error for conv_id=%d", conv_id)
            stream_error = str(e)
            yield _encode_sse(
                json.dumps({
                    "type": "error",
                    "content": stream_error,
                    "conversation_id": conv_id,
                }),
                "error",
            )
        finally:
            logger.info(
                "Chat stream ending for conv_id=%d — text_chunks=%d, tool_results=%d",
                conv_id,
                len(full_response),
                len(tool_calls_data),
            )
            if (
                stream_error is None
                and req.agent_control != "execute_confirmed"
                and latest_plan_state
                and latest_plan_state.get("strategy_signature")
                and latest_plan_state.get("task_fingerprint")
            ):
                with suppress(Exception):
                    await persist_strategy_checkpoint(
                        db,
                        user_id=current_user["id"],
                        conversation_id=conv_id,
                        project_id=conversation.project_id,
                        task_text=checkpoint_task_text,
                        task_fingerprint=str(latest_plan_state["task_fingerprint"]),
                        strategy_signature=str(latest_plan_state["strategy_signature"]),
                        plan_payload=latest_raw_plan_payload
                        or orchestrator._restore_display_plan_payload(
                            list(latest_plan_state.get("plan") or []),
                            req.message,
                        ),
                        evidence_state={"research_notes_preview": latest_plan_state.get("research_notes") or ""},
                        artifacts={},
                        policy_payload={
                            "analysis_depth": analysis_depth,
                            "agent_control": req.agent_control or "plan_only",
                        },
                    )
                    await db.commit()
            if stream_error is None and confirmed_checkpoint_id is not None:
                with suppress(Exception):
                    execution_summary = orchestrator.get_checkpoint_execution_summary()
                    await mark_strategy_checkpoint_completed(
                        db,
                        checkpoint_id=confirmed_checkpoint_id,
                        user_id=current_user["id"],
                        evidence_state=execution_summary,
                        artifacts=getattr(orchestrator._snapshot, "artifacts", {}) if orchestrator._snapshot else {},
                    )
                    await db.commit()
            task = asyncio.create_task(
                _finalize_chat_response(
                    conversation=conversation,
                    user_message=req.message,
                    full_response=list(full_response),
                    tool_calls_data=[dict(t) for t in tool_calls_data],
                    stream_error=stream_error,
                    should_auto_title=should_auto_title,
                    model_id=req.model,
                )
            )
            with suppress(Exception):
                await asyncio.shield(task)
            sse_connections_active.dec()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/strategy-checkpoints/active")
async def get_active_chat_strategy_checkpoint(
    conversation_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Return the active awaiting strategy checkpoint for a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user["id"],
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    checkpoint = await get_active_strategy_checkpoint(
        db,
        user_id=current_user["id"],
        conversation_id=conversation_id,
    )
    return {
        "checkpoint": _checkpoint_for_display(checkpoint),
        "agent_state": {
            "stage": "done",
            "plan": (
                orchestrator._sanitize_plan_for_display(checkpoint["plan_payload"])
                if checkpoint
                else []
            ),
            "current_step": 0,
            "step_results": [],
            "research_notes": ((checkpoint or {}).get("evidence_state") or {}).get("research_notes_preview", ""),
            "waiting_for": "plan_confirmation" if checkpoint else None,
            "strategy_signature": (checkpoint or {}).get("strategy_signature"),
            "task_fingerprint": (checkpoint or {}).get("task_fingerprint"),
            "next_action": (checkpoint or {}).get("next_action"),
            "artifacts": (checkpoint or {}).get("artifacts") or {},
        } if checkpoint else None,
    }


@router.get("/strategy-checkpoints/history")
async def list_chat_strategy_checkpoints(
    conversation_id: int = Query(..., ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Return revision history for strategy checkpoints in a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user["id"],
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    checkpoints = await list_strategy_checkpoints(
        db,
        user_id=current_user["id"],
        conversation_id=conversation_id,
        limit=limit,
    )
    return {"records": [_checkpoint_for_display(record) for record in checkpoints]}


@router.get("/strategy-checkpoints/recent")
async def list_recent_chat_strategy_memory(
    conversation_id: int | None = Query(default=None, ge=1),
    project_id: str | None = Query(default=None, min_length=1, max_length=16),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Return recent strategy checkpoints for same-project continuation memory."""
    conversation: Conversation | None = None
    if conversation_id is not None:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user["id"],
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    memory_project_id = project_id
    if memory_project_id is None and conversation is not None:
        memory_project_id = conversation.project_id
    scope_type = "conversation"
    if memory_project_id:
        project, access_role = await get_project_access(
            db,
            project_id=memory_project_id,
            user_id=current_user["id"],
        )
        if not project or not can_perform_project_action(access_role, "project.read"):
            raise HTTPException(status_code=404, detail="Project not found")
        scope_type = "project"
    elif conversation_id is None:
        raise HTTPException(status_code=400, detail="conversation_id or project_id is required")

    records = await list_recent_strategy_memory(
        db,
        user_id=current_user["id"],
        conversation_id=conversation_id,
        project_id=memory_project_id,
        limit=limit,
    )
    return {
        "scope": {
            "type": scope_type,
            "conversation_id": conversation_id,
            "project_id": memory_project_id,
        },
        "records": [_checkpoint_for_display(record) for record in records],
    }


@router.get("/models")
async def list_models(current_user: dict = Depends(get_current_user)):
    """Return available LLM models for the frontend model selector."""
    return get_available_models()


@router.get("/strategy-policy")
async def get_chat_strategy_policy(current_user: dict = Depends(get_current_user)):
    """Return the effective read-only agent strategy governance policy."""
    return get_agent_strategy_policy()


async def _auto_title(
    conversation: Conversation,
    user_message: str,
    model_id: str | None = None,
) -> None:
    """Generate a concise title for the conversation using the LLM.

    Uses a high max_tokens because DeepSeek V4 consumes reasoning tokens
    before producing text output.
    """
    from app.core.database import _async_session_factory
    prompt = [
        {"role": "user", "content": (
            "Write a short title (max 6 words) for a chat about: \""
            + user_message[:200] + "\". Output only the title."
        )},
    ]

    try:
        response = await llm_gateway.complete(
            messages=prompt,
            model_id=model_id,
            max_tokens=1024,
            temperature=0.3,
        )
        title = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        title = title.strip('"\'').strip().split("\n")[0]
        if title and len(title) <= 120:
            conversation.title = title
            async with _async_session_factory() as title_db:
                # Re-attach the conversation to the new session and update
                conv = await title_db.merge(conversation)
                conv.title = title
                await title_db.commit()
            logger.info("Auto-titled conversation %d: %s", conversation.id, title)
    except Exception:
        pass  # Non-critical — keep the default title


async def _finalize_chat_response(
    conversation: Conversation,
    user_message: str,
    full_response: list[str],
    tool_calls_data: list[dict],
    stream_error: str | None,
    should_auto_title: bool,
    model_id: str | None = None,
) -> None:
    """Persist results and run slow post-processing after the SSE closes."""
    content = "".join(full_response).strip()
    if content or tool_calls_data:
        if not content:
            content = "*[Tool execution results]*"
        if stream_error:
            content += f"\n\n*[Stream interrupted: {stream_error}]*"

        try:
            from app.core.database import _async_session_factory

            async with _async_session_factory() as save_db:
                async with save_db.begin_nested():
                    assistant_msg = Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=content,
                        tool_calls=json.dumps(tool_calls_data, ensure_ascii=False) if tool_calls_data else None,
                    )
                    save_db.add(assistant_msg)
                    await save_db.flush()
                await save_db.commit()
        except Exception:
            logger.exception("Failed to persist assistant message for conv_id=%d", conversation.id)

    if should_auto_title:
        await _auto_title(conversation, user_message, model_id=model_id)

    publish_result = await _auto_publish_wiki(
        orchestrator, conversation, user_message, full_response,
    )
    if publish_result:
        logger.info(
            "Deferred auto-publish finished for conv=%d: file=%s",
            conversation.id,
            publish_result.get("file_id"),
        )


async def _auto_publish_wiki(
    orchestrator,
    conversation: Conversation,
    user_message: str,
    full_response: list[str],
) -> dict | None:
    """Auto-publish agent report to project Wiki if conditions are met.

    Conditions:
    - Conversation must have a project_id
    - Project must have wiki_auto_publish = True
    - Agent must have produced a final_report (not general chat or empty plan)

    Returns publish result dict or None if skipped/failed.
    """
    if not conversation.project_id:
        return None

    from app.core.database import _async_session_factory
    from app.models.project import Project

    try:
        async with _async_session_factory() as pub_db:
            project = await pub_db.get(Project, conversation.project_id)
            if not project or not project.wiki_auto_publish:
                return None

            # Get snapshot data from orchestrator
            snapshot = orchestrator.get_snapshot_data()
            if not snapshot or not snapshot.get("final_report"):
                return None

            # Generate markdown report
            from app.services.report_generator import ReportGenerator
            generator = ReportGenerator()
            report_content = generator.generate_conversation_report(
                project_name=project.name,
                conversation_title=conversation.title or "分析报告",
                user_message=user_message,
                research_notes=snapshot.get("research_notes", ""),
                plan=snapshot.get("plan", []),
                tool_results=snapshot.get("step_results", []),
                final_report=snapshot["final_report"],
            )

            # Publish via publish_service
            from app.services.publish_service import publish_report
            result = await publish_report(
                pub_db,
                project_id=project.id,
                title=conversation.title or "分析报告",
                content=report_content,
                conversation_id=conversation.id,
                source="agent",
            )

            logger.info(
                "Auto-published wiki for conv=%d project=%s: file=%s",
                conversation.id, project.id, result.get("file_id"),
            )
            return result

    except Exception as e:
        logger.warning(
            "Auto-publish failed for conv=%d: %s", conversation.id, e,
        )
        return None
