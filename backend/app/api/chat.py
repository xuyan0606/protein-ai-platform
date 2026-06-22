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
        )
        db.add(conversation)
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
        try:
            async for event in orchestrator.stream_chat(
                req.message, req.history,
                provider=llm_provider, model=llm_model,
            ):
                if isinstance(event, dict):
                    content = event.get("content", "")
                    if content:
                        full_response.append(str(content))
                # Inject conversation_id into done events so the frontend can persist
                if isinstance(event, str):
                    try:
                        parsed = json.loads(event)
                        if parsed.get("type") == "done":
                            parsed["conversation_id"] = conv_id
                            event = json.dumps(parsed, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        pass
                yield {"event": "message", "data": event}

            # After streaming completes, save assistant message to DB
            full_text = "".join(full_response)
            if full_text.strip():
                async with db.begin_nested():
                    assistant_msg = Message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=full_text,
                    )
                    db.add(assistant_msg)
                    await db.flush()

            # Generate a descriptive title after the first exchange
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

        except Exception as e:
            logger.exception("Chat stream error for conv_id=%d", conv_id)
            partial = "".join(full_response)
            try:
                async with db.begin_nested():
                    error_msg = Message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=partial + f"\n\n*[Error: {e}]*" if partial else f"*[Error: {e}]*",
                    )
                    db.add(error_msg)
                    await db.flush()
            except Exception:
                pass

            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "content": str(e),
                    "conversation_id": conv_id,
                }),
            }
        finally:
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
            await db.flush()
            logger.info("Auto-titled conversation %d: %s", conversation.id, title)
    except Exception:
        pass  # Non-critical — keep the default title
