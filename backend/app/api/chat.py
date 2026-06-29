"""Chat endpoints — SSE streaming with JWT protection and DB persistence."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent import orchestrator
from app.core.database import get_session
from app.core.llm import get_available_models, MODEL_REGISTRY
from app.core.security import get_current_user
from app.models.conversation import Conversation, Message

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    project_id: str | None = None  # bind conversation to project for auto-publish
    history: list[dict] = []
    model: str | None = None  # model id from the registry (e.g. "deepseek", "kuaPao")


@router.post("/stream")
async def stream_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """SSE streaming chat endpoint — JWT-protected, DB-persisted."""

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message must not be empty")

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

    # Resolve model id → (provider, model) for the orchestrator
    llm_provider: str | None = None
    llm_model: str | None = None
    if req.model:
        for m in MODEL_REGISTRY:
            if m.id == req.model and m.available:
                llm_provider = m.provider
                llm_model = m.model
                break

    from app.core.metrics import sse_connections_active

    async def event_generator():
        sse_connections_active.inc()
        full_response: list[str] = []
        tool_calls_data: list[dict] = []
        stream_error: str | None = None
        try:
            async for event in orchestrator.stream_chat(
                req.message, req.history,
                provider=llm_provider, model=llm_model,
            ):
                # Collect text content and tool calls for DB persistence
                if isinstance(event, str):
                    try:
                        parsed = json.loads(event)
                        if parsed.get("type") == "text":
                            content = parsed.get("content", "")
                            if content:
                                full_response.append(str(content))
                        elif parsed.get("type") == "state":
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
                                    })
                                else:
                                    existing[0]["status"] = sr.get("status", existing[0]["status"])
                                    existing[0]["error"] = sr.get("error", existing[0].get("error"))
                                    if sr.get("result_preview"):
                                        existing[0]["resultPreview"] = sr["result_preview"][:2000]
                        if parsed.get("type") == "done":
                            parsed["conversation_id"] = conv_id
                            event = json.dumps(parsed, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif isinstance(event, dict):
                    content = event.get("content", "")
                    if content:
                        full_response.append(str(content))
                yield {"event": "message", "data": event}

            # Auto-title after successful completion
            if conversation.title == req.message[:80]:
                await _auto_title(conversation, req.message, db)
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "title",
                        "conversation_id": conv_id,
                        "title": conversation.title,
                    }),
                }

            # Auto-publish to Wiki if conversation belongs to a project with wiki_auto_publish
            publish_result = await _auto_publish_wiki(
                orchestrator, conversation, req.message, full_response,
            )
            if publish_result:
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "published",
                        "conversation_id": conv_id,
                        **publish_result,
                    }, ensure_ascii=False),
                }

        except Exception as e:
            logger.exception("Chat stream error for conv_id=%d", conv_id)
            stream_error = str(e)
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "content": stream_error,
                    "conversation_id": conv_id,
                }),
            }
        finally:
            # Always persist partial results — survives client disconnect, errors, and completion
            # IMPORTANT: Use a fresh session because EventSourceResponse returns immediately,
            # causing the request-scoped session (get_session) to commit & close before the
            # event generator finishes. We must save the assistant message in a separate session.
            full_text = "".join(full_response)
            logger.info("Chat stream ending for conv_id=%d — text_chunks=%d, tool_results=%d",
                       conv_id, len(full_response), len(tool_calls_data))
            if full_text.strip() or tool_calls_data:
                try:
                    content = full_text.strip() if full_text.strip() else "*[Tool execution results]*"
                    if stream_error:
                        content += f"\n\n*[Stream interrupted: {stream_error}]*"
                    from app.core.database import _async_session_factory
                    async with _async_session_factory() as save_db:
                        async with save_db.begin_nested():
                            assistant_msg = Message(
                                conversation_id=conv_id,
                                role="assistant",
                                content=content,
                                tool_calls=json.dumps(tool_calls_data, ensure_ascii=False) if tool_calls_data else None,
                            )
                            save_db.add(assistant_msg)
                            await save_db.flush()
                        await save_db.commit()
                except Exception:
                    logger.exception("Failed to persist assistant message for conv_id=%d", conv_id)

            sse_connections_active.dec()

    return EventSourceResponse(event_generator())


@router.get("/models")
async def list_models():
    """Return available LLM models for the frontend model selector."""
    return get_available_models()


async def _auto_title(conversation: Conversation, user_message: str, db: AsyncSession) -> None:
    """Generate a concise title for the conversation using the LLM.

    Uses a high max_tokens because DeepSeek V4 consumes reasoning tokens
    before producing text output.
    """
    from app.core.database import _async_session_factory
    from app.core.llm import chat_completion

    prompt = [
        {"role": "user", "content": (
            "Write a short title (max 6 words) for a chat about: \""
            + user_message[:200] + "\". Output only the title."
        )},
    ]

    try:
        response = await chat_completion(
            messages=prompt,
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
