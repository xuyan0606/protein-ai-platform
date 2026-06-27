"""Conversations API — protected CRUD against PostgreSQL."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.conversation import Conversation, Message
from app.models.tool_call import ToolCallRecord

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    tool_calls: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: int
    title: str
    created_at: str | None = None
    updated_at: str | None = None
    messages: list[MessageOut] = []

    model_config = {"from_attributes": True}


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New Conversation", max_length=200, min_length=1)


class UpdateConversationRequest(BaseModel):
    title: str = Field(max_length=200, min_length=1)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """List conversations for the authenticated user."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user["id"])
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    out = []
    for c in conversations:
        # Count messages with a lightweight query
        count_result = await db.execute(
            select(func.count()).select_from(Message).where(
                Message.conversation_id == c.id
            )
        )
        msg_count = count_result.scalar() or 0
        out.append(ConversationOut(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat() if c.created_at else None,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
            message_count=msg_count,
        ))
    return out


@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: CreateConversationRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Create a new conversation for the authenticated user."""
    conv = Conversation(
        user_id=current_user["id"],
        title=req.title,
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return _conv_to_detail(conv, [])


@router.get("/{conv_id}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Get a single conversation with its messages (user-scoped)."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_id, Conversation.user_id == current_user["id"])
        .options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _conv_to_detail(conv)


@router.patch("/{conv_id}", response_model=ConversationDetail)
async def update_conversation(
    conv_id: int,
    req: UpdateConversationRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Rename a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user["id"],
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    conv.title = req.title
    await db.flush()
    await db.refresh(conv)

    # Re-load with messages
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_id)
        .options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one()
    return _conv_to_detail(conv)


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conv_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Delete a conversation (user-scoped)."""
    result = await db.execute(
        delete(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == current_user["id"],
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conv_to_detail(conv: Conversation, messages: list[Message] | None = None) -> ConversationDetail:
    msgs = messages if messages is not None else getattr(conv, 'messages', None) or []
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat() if conv.created_at else None,
        updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                tool_calls=m.tool_calls,
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in msgs
        ],
    )
