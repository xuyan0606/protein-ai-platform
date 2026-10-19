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

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.project import Project, ProjectFile
from app.models.conversation import Conversation
from app.services import publish_service
from app.services.project_acl import can_perform_project_action, get_project_access
from app.services.report_generator import ReportGenerator
from app.services.outline_client import OutlineAuthenticationError, OutlineUnavailableError

router = APIRouter(tags=["publish"])  # mounted under /api/projects
conv_router = APIRouter(tags=["publish"])  # mounted under /api
_generator = ReportGenerator()


async def _require_project_access(
    session: AsyncSession,
    *,
    project_id: str,
    user_id: int | str,
    write: bool = False,
) -> tuple[Project, str]:
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user_id)
    if not project or not can_perform_project_action(access_role, "project.read"):
        raise HTTPException(404, "Project not found")
    if write and not can_perform_project_action(access_role, "project.wiki.publish"):
        raise HTTPException(404, "Project not found")
    return project, access_role


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PublishRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200_000)  # up to 200KB markdown
    conversation_id: int | None = None
    tags: list[str] | None = None
    collection_id: str | None = None
    parent_document_id: str | None = None


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


class WikiCollectionOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    url: str | None = None
    document_count: int | None = None


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
    await _require_project_access(session, project_id=project_id, user_id=user["id"], write=True)

    try:
        result = await publish_service.publish_report(
            session,
            project_id=project_id,
            title=req.title,
            content=req.content,
            conversation_id=req.conversation_id,
            tags=req.tags,
            collection_id=req.collection_id,
            parent_document_id=req.parent_document_id,
            source="manual",
        )
    except publish_service.ReportQualityGateError as e:
        raise HTTPException(400, str(e)) from e
    except OutlineAuthenticationError as e:
        raise HTTPException(503, "Wiki 服务认证已失效，请联系管理员轮换 Outline API key") from e
    except OutlineUnavailableError as e:
        raise HTTPException(503, "Wiki 服务暂时不可用，请稍后重试") from e
    return PublishResponse(**result)


@conv_router.post("/wiki/publish", response_model=PublishResponse)
async def publish_to_collection(
    req: PublishRequest,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Publish directly to a selected Wiki collection without requiring project selection."""
    if not req.collection_id:
        raise HTTPException(400, "请选择 Wiki collection")

    if req.conversation_id is not None:
        conv = await session.get(Conversation, req.conversation_id)
        if not conv or conv.user_id != user["id"]:
            raise HTTPException(404, "Conversation not found")

    project = await publish_service.ensure_wiki_publish_project(
        session,
        user_id=user["id"],
        collection_id=req.collection_id,
    )

    try:
        result = await publish_service.publish_report(
            session,
            project_id=project.id,
            title=req.title,
            content=req.content,
            conversation_id=req.conversation_id,
            tags=req.tags,
            collection_id=req.collection_id,
            parent_document_id=req.parent_document_id,
            source="manual",
        )
    except publish_service.ReportQualityGateError as e:
        raise HTTPException(400, str(e)) from e
    except OutlineAuthenticationError as e:
        raise HTTPException(503, "Wiki 服务认证已失效，请联系管理员轮换 Outline API key") from e
    except OutlineUnavailableError as e:
        raise HTTPException(503, "Wiki 服务暂时不可用，请稍后重试") from e
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
    await _require_project_access(session, project_id=project_id, user_id=user["id"])

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
    await _require_project_access(session, project_id=project_id, user_id=user["id"])

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
    await _require_project_access(session, project_id=project_id, user_id=user["id"])

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
    await _require_project_access(session, project_id=project_id, user_id=user["id"], write=True)

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
    project, _ = await _require_project_access(session, project_id=project_id, user_id=user["id"], write=True)

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
        await _require_project_access(session, project_id=req.project_id, user_id=user["id"], write=True)
        conv.project_id = req.project_id
    else:
        conv.project_id = None

    await session.commit()
    return {"ok": True, "project_id": conv.project_id}


# ---------------------------------------------------------------------------
# Wiki tree (Outline proxy)
# ---------------------------------------------------------------------------

@conv_router.get("/wiki/collections", response_model=list[WikiCollectionOut])
async def list_wiki_collections(
    user: dict = Depends(get_current_user),
):
    """List existing Outline collections the backend API token can access."""
    try:
        from app.services.outline_client import (
            OutlineAuthenticationError,
            OutlineUnavailableError,
            get_outline_client,
        )

        client = get_outline_client()
        collections = await client.list_collections()
        return [
            WikiCollectionOut(
                id=item.get("id"),
                name=item.get("name") or "Untitled",
                description=item.get("description"),
                url=item.get("url"),
                document_count=item.get("documentCount"),
            )
            for item in collections
            if item.get("id")
        ]
    except OutlineAuthenticationError as e:
        logger.error("Outline authentication failed while listing collections: %s", e)
        raise HTTPException(503, "Wiki 服务认证已失效，请联系管理员轮换 Outline API key") from e
    except OutlineUnavailableError as e:
        logger.warning("Outline unavailable while listing collections: %s", e)
        raise HTTPException(503, "Wiki 服务暂时不可用，请稍后重试") from e
    except Exception as e:
        logger.warning("Failed to list wiki collections for user %s: %s", user["id"], e)
        raise HTTPException(502, "加载 Wiki collection 失败")


@conv_router.get("/wiki/collections/{collection_id}/tree")
async def get_collection_tree(
    collection_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the Outline document tree for an existing collection."""
    try:
        from app.services.outline_client import (
            OutlineAuthenticationError,
            OutlineUnavailableError,
            get_outline_client,
        )

        client = get_outline_client()
        docs = await client.get_collection_tree(collection_id)

        tree = []

        def walk(nodes: list[dict], parent_id: str | None = None):
            for doc in nodes:
                doc_id = doc.get("id")
                tree.append({
                    "id": doc_id,
                    "title": doc.get("title", "Untitled"),
                    "parent_id": parent_id,
                    "url_id": doc.get("urlId"),
                    "updated_at": doc.get("updatedAt"),
                    "emoji": doc.get("emoji"),
                })
                walk(doc.get("children", []) or [], doc_id)

        walk(docs)
        return {
            "collection_id": collection_id,
            "root_doc_id": None,
            "documents": tree,
        }
    except OutlineAuthenticationError as e:
        logger.error("Outline authentication failed while loading collection %s: %s", collection_id, e)
        raise HTTPException(503, "Wiki 服务认证已失效，请联系管理员轮换 Outline API key") from e
    except OutlineUnavailableError as e:
        logger.warning("Outline unavailable while loading collection %s: %s", collection_id, e)
        raise HTTPException(503, "Wiki 服务暂时不可用，请稍后重试") from e
    except Exception as e:
        logger.warning(
            "Failed to load wiki tree for collection %s user %s: %s",
            collection_id,
            user["id"],
            e,
        )
        raise HTTPException(502, "加载知识库目录树失败")

@router.get("/{project_id}/wiki/tree")
async def get_wiki_tree(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Get the Outline document tree for a project's wiki collection."""
    project, access_role = await _require_project_access(session, project_id=project_id, user_id=user["id"])

    try:
        if not project.outline_collection_id:
            if not can_perform_project_action(access_role, "project.wiki.publish"):
                return {
                    "collection_id": None,
                    "root_doc_id": None,
                    "documents": [],
                    "error": "项目尚未初始化 Wiki，viewer 仅可读取已有知识库",
                }
            project = await publish_service.ensure_project_wiki(session, project)
        from app.services.outline_client import get_outline_client
        client = get_outline_client()
        docs = await client.get_collection_tree(project.outline_collection_id)

        # Flatten Outline's nested tree into parent-linked nodes for the frontend.
        tree = []
        def walk(nodes: list[dict], parent_id: str | None = None):
            for doc in nodes:
                doc_id = doc.get("id")
                tree.append({
                    "id": doc_id,
                    "title": doc.get("title", "Untitled"),
                    "parent_id": parent_id,
                    "url_id": doc.get("urlId"),
                    "updated_at": doc.get("updatedAt"),
                    "emoji": doc.get("emoji"),
                })
                walk(doc.get("children", []) or [], doc_id)

        walk(docs)

        return {
            "collection_id": project.outline_collection_id,
            "root_doc_id": project.outline_root_doc_id,
            "documents": tree,
        }
    except OutlineAuthenticationError as e:
        raise HTTPException(503, "Wiki 服务认证已失效，请联系管理员轮换 Outline API key") from e
    except OutlineUnavailableError as e:
        raise HTTPException(503, "Wiki 服务暂时不可用，请稍后重试") from e
    except Exception as e:
        logger.warning("Outline wiki tree failed for project %s: %s", project_id, e)
        return {
            "collection_id": project.outline_collection_id,
            "root_doc_id": project.outline_root_doc_id,
            "documents": [],
            "error": "知识库目录暂时加载失败，请先发布到根目录",
        }


@router.get("/{project_id}/wiki/pages/{doc_id}")
async def get_wiki_page(
    project_id: str,
    doc_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Get a single Outline document's content (Markdown text)."""
    project, _ = await _require_project_access(session, project_id=project_id, user_id=user["id"])

    if not project.outline_collection_id:
        raise HTTPException(400, "Project has no wiki collection")

    try:
        from app.services.outline_client import get_outline_client
        data = await get_outline_client().get_document(doc_id)
        if data.get("collectionId") != project.outline_collection_id:
            raise HTTPException(404, "Wiki document not found")
        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "text": data.get("text", ""),
            "updated_at": data.get("updatedAt"),
            "url_id": data.get("urlId"),
        }
    except (OutlineAuthenticationError, OutlineUnavailableError) as e:
        detail = "Wiki 服务认证已失效，请联系管理员轮换 Outline API key" if isinstance(e, OutlineAuthenticationError) else "Wiki 服务暂时不可用，请稍后重试"
        raise HTTPException(503, detail) from e


# ---------------------------------------------------------------------------
# Conversation listing
# ---------------------------------------------------------------------------

@router.get("/{project_id}/conversations")
async def list_project_conversations(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """List conversations belonging to a project."""
    await _require_project_access(session, project_id=project_id, user_id=user["id"])

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
