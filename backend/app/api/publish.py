"""Publish API — manual publish to Wiki + knowledge base file management.

Endpoints:
  POST /api/projects/{project_id}/publish   — publish a report (manual)
  GET  /api/projects/{project_id}/files     — list project files
  GET  /api/projects/{project_id}/files/{file_id}/download — download file
  DELETE /api/projects/{project_id}/files/{file_id} — delete file
  PATCH /api/conversations/{id}/project     — bind conversation to project
  GET  /api/projects/{project_id}/conversations — list project conversations
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.project import Project, ProjectFile
from app.models.conversation import Conversation
from app.services import publish_service
from app.services.report_generator import ReportGenerator

router = APIRouter(tags=["publish"])  # mounted under /api/projects
conv_router = APIRouter(tags=["publish"])  # mounted under /api
_generator = ReportGenerator()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PublishRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200_000)  # up to 200KB markdown
    conversation_id: int | None = None
    tags: list[str] | None = None


class PublishResponse(BaseModel):
    file_id: str
    filename: str
    object_name: str
    outline_doc_id: str | None = None
    wiki_url: str | None = None
    file_size: int


class FileOut(BaseModel):
    id: str
    filename: str
    object_name: str
    file_type: str
    file_size: int
    source: str
    conversation_id: int | None = None
    outline_doc_id: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class BindProjectRequest(BaseModel):
    project_id: str | None = None  # None = unbind


class GenerateReportRequest(BaseModel):
    """Generate a .md report from conversation data (preview before publish)."""
    conversation_id: int


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

@router.post("/{project_id}/publish", response_model=PublishResponse)
async def publish_to_wiki(
    project_id: str,
    req: PublishRequest,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Manually publish a Markdown report to Wiki + knowledge base."""
    # Verify project ownership
    project = await session.get(Project, project_id)
    if not project or project.user_id != user["id"]:
        raise HTTPException(404, "Project not found")

    result = await publish_service.publish_report(
        session,
        project_id=project_id,
        title=req.title,
        content=req.content,
        conversation_id=req.conversation_id,
        tags=req.tags,
        source="manual",
    )
    return PublishResponse(**result)


# ---------------------------------------------------------------------------
# File management
# ---------------------------------------------------------------------------

@router.get("/{project_id}/files", response_model=list[FileOut])
async def list_files(
    project_id: str,
    file_type: str | None = None,
    source: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """List files in a project's knowledge base."""
    project = await session.get(Project, project_id)
    if not project or project.user_id != user["id"]:
        raise HTTPException(404, "Project not found")

    files = await publish_service.list_project_files(
        session, project_id, file_type=file_type, source=source,
    )
    return files


@router.get("/{project_id}/files/{file_id}/download")
async def download_file(
    project_id: str,
    file_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Download a file from the project knowledge base."""
    project = await session.get(Project, project_id)
    if not project or project.user_id != user["id"]:
        raise HTTPException(404, "Project not found")

    file_record = await session.get(ProjectFile, file_id)
    if not file_record or file_record.project_id != project_id:
        raise HTTPException(404, "File not found")

    try:
        from app.services.storage import download_file as storage_download
        data = await storage_download(file_record.object_name)
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{file_record.filename}"'},
        )
    except Exception as e:
        raise HTTPException(500, f"Download failed: {e}")


@router.get("/{project_id}/files/{file_id}/content")
async def get_file_content(
    project_id: str,
    file_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Get raw Markdown content of a file (for editor preview)."""
    project = await session.get(Project, project_id)
    if not project or project.user_id != user["id"]:
        raise HTTPException(404, "Project not found")

    file_record = await session.get(ProjectFile, file_id)
    if not file_record or file_record.project_id != project_id:
        raise HTTPException(404, "File not found")

    try:
        from app.services.storage import download_file as storage_download
        data = await storage_download(file_record.object_name)
        return Response(content=data, media_type="text/markdown; charset=utf-8")
    except Exception as e:
        raise HTTPException(500, f"Read failed: {e}")


@router.delete("/{project_id}/files/{file_id}")
async def delete_file(
    project_id: str,
    file_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Delete a file from the project knowledge base."""
    project = await session.get(Project, project_id)
    if not project or project.user_id != user["id"]:
        raise HTTPException(404, "Project not found")

    ok = await publish_service.delete_project_file(session, project_id, file_id)
    if not ok:
        raise HTTPException(404, "File not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Report generation (preview before publish)
# ---------------------------------------------------------------------------

@router.post("/{project_id}/generate-report")
async def generate_report(
    project_id: str,
    req: GenerateReportRequest,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Generate a Markdown report from a conversation (returns preview, doesn't publish)."""
    project = await session.get(Project, project_id)
    if not project or project.user_id != user["id"]:
        raise HTTPException(404, "Project not found")

    conv = await session.get(Conversation, req.conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # Get messages
    stmt = select(Conversation).where(Conversation.id == req.conversation_id)
    result = await session.execute(stmt)
    conv = result.scalar_one()

    # Extract user message and assistant response
    user_msg = ""
    assistant_msg = ""
    tool_calls_data = []
    for msg in conv.messages:
        if msg.role == "user" and not user_msg:
            user_msg = msg.content
        elif msg.role == "assistant":
            assistant_msg = msg.content
            if msg.tool_calls:
                import json
                try:
                    tool_calls_data = json.loads(msg.tool_calls)
                except Exception:
                    pass

    if not assistant_msg:
        raise HTTPException(400, "No assistant response found in conversation")

    # Generate report
    md = _generator.generate_conversation_report(
        project_name=project.name,
        conversation_title=conv.title or "分析报告",
        user_message=user_msg,
        research_notes="",  # Not stored separately yet
        plan=[{"tool_name": tc.get("name", "?"), "status": "completed", "description": "", "duration": "?"}
              for tc in tool_calls_data] if tool_calls_data else [],
        tool_results=[],
        final_report=assistant_msg,
        tags=[],
    )

    return {
        "title": conv.title or "分析报告",
        "content": md,
        "conversation_id": conv.id,
    }


# ---------------------------------------------------------------------------
# Conversation ↔ Project binding
# ---------------------------------------------------------------------------

@conv_router.patch("/conversations/{conversation_id}/project")
async def bind_conversation_to_project(
    conversation_id: int,
    req: BindProjectRequest,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Bind or unbind a conversation to a project."""
    conv = await session.get(Conversation, conversation_id)
    if not conv or conv.user_id != user["id"]:
        raise HTTPException(404, "Conversation not found")

    if req.project_id:
        project = await session.get(Project, req.project_id)
        if not project or project.user_id != user["id"]:
            raise HTTPException(404, "Project not found")
        conv.project_id = req.project_id
    else:
        conv.project_id = None

    await session.commit()
    return {"ok": True, "project_id": conv.project_id}


@router.get("/{project_id}/conversations")
async def list_project_conversations(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """List conversations belonging to a project."""
    project = await session.get(Project, project_id)
    if not project or project.user_id != user["id"]:
        raise HTTPException(404, "Project not found")

    stmt = (
        select(Conversation)
        .where(Conversation.project_id == project_id, Conversation.user_id == user["id"])
        .order_by(Conversation.updated_at.desc())
    )
    result = await session.execute(stmt)
    conversations = result.scalars().all()

    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in conversations
    ]
