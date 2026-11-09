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

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.project import Project, ProjectFile
from app.models.conversation import Conversation, Message
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


def _decode_dict(raw: object) -> dict:
    value = _decode_json(raw)
    return value if isinstance(value, dict) else {}


def _decode_json(raw: object) -> object:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _merge_done_contract(execution: dict, contract: object) -> dict:
    """Normalize the terminal envelope into the report task contract.

    ``done`` is the authoritative record for a streamed turn.  Older rows can
    contain only ``ToolCallRecord`` entries, while newer rows carry the
    workflow metadata at the top level of the done envelope.  Keeping those
    fields separate used to make Wiki previews lose the blocked reason or
    even treat a blocked stream as ready.  Preserve the detailed contract,
    then project missing terminal metadata into it without overwriting a more
    specific workflow decision such as ``NEEDS_INPUT`` or ``NEEDS_REVIEW``.
    """
    merged = dict(contract) if isinstance(contract, dict) else {}
    for key in ("objective", "workflow_id", "blocked_reason", "missing_capabilities"):
        value = execution.get(key)
        if value is None or value == "":
            continue
        current = merged.get(key)
        if current in (None, "", [], {}):
            merged[key] = list(value) if key == "missing_capabilities" and isinstance(value, list) else value

    stream_status = str(execution.get("status") or "").strip().upper()
    if stream_status:
        merged["stream_status"] = stream_status
        if not merged.get("final_status"):
            merged["final_status"] = {
                "COMPLETED": "READY",
                "READY": "READY",
                "BLOCKED": "BLOCKED",
                "FAILED": "FAILED",
            }.get(stream_status, stream_status)
        elif stream_status in {"BLOCKED", "FAILED"} and str(merged.get("final_status")).upper() in {
            "READY", "COMPLETED",
        }:
            # A terminal blocked/failed stream cannot be published as READY.
            merged["final_status"] = stream_status
    if execution.get("type") == "done" or "execution_trace" in execution:
        merged["terminal_source"] = "done_event"
    return merged


def _extract_report_source(
    messages: list[Message],
) -> tuple[str, str, list[dict], list[dict], dict]:
    """Extract the latest user turn and only its assistant execution evidence."""
    messages = sorted(
        enumerate(messages),
        key=lambda pair: (
            _message_order_value(pair[1]),
            int(getattr(pair[1], "id", 0) or pair[0]),
            pair[0],
        ),
    )
    messages = [message for _, message in messages]
    last_user_index = max(
        (index for index, message in enumerate(messages) if message.role == "user"),
        default=-1,
    )
    latest_assistant = next(
        (
            message
            for message in reversed(messages[last_user_index + 1 :])
            if message.role == "assistant" and str(message.content or "").strip()
        ),
        None,
    )
    user_message = (
        str(messages[last_user_index].content or "")
        if last_user_index >= 0
        else ""
    )
    if latest_assistant is None:
        return user_message, "", [], [], {}

    execution_data = _decode_json(latest_assistant.tool_calls)
    execution = execution_data if isinstance(execution_data, dict) else {}
    if isinstance(execution_data, list):
        trace = execution_data
        trace_is_authoritative = False
    else:
        trace = execution.get("execution_trace")
        # An explicit empty trace is authoritative only for the new terminal
        # ``done`` envelope.  Older assistant messages sometimes serialized
        # ``execution_trace: []`` while the normalized ToolCallRecord rows
        # were still the only source of evidence; treating every empty array
        # as terminal would make those legacy reports lose their tool plan.
        trace_is_authoritative = execution.get("type") == "done" and "execution_trace" in execution
    if not isinstance(trace, list):
        trace = execution.get("tool_calls")
        # A done envelope with an explicit but empty/invalid execution trace is
        # still authoritative. Do not resurrect stale normalized rows.
        trace_is_authoritative = trace_is_authoritative or "tool_calls" in execution
    if not isinstance(trace, list):
        trace = []

    if not trace and not trace_is_authoritative:
        # Older conversations may only have normalized ToolCallRecord rows.
        records = sorted(
            getattr(latest_assistant, "tool_call_records", []) or [],
            key=lambda record: getattr(record, "id", 0) or 0,
        )
        for record in records:
            stored = _decode_dict(getattr(record, "result", None))
            trace.append({
                "tool": getattr(record, "tool_name", "unknown"),
                "status": getattr(record, "status", "unknown"),
                "result_preview": stored.get("result_preview"),
                "reason": getattr(record, "error", None),
                "duration": (
                    getattr(record, "duration_ms", None) / 1000
                    if getattr(record, "duration_ms", None) is not None
                    else None
                ),
            })

    plan: list[dict] = []
    tool_results: list[dict] = []
    for item in trace:
        if not isinstance(item, dict):
            continue
        tool_name = item.get("tool") or item.get("tool_name") or "unknown"
        function_data = item.get("function")
        if tool_name == "unknown" and isinstance(function_data, dict):
            tool_name = function_data.get("name") or tool_name
        if tool_name == "unknown":
            tool_name = item.get("name") or tool_name
        raw_result = item.get("raw_result")
        if raw_result is None or raw_result == "":
            raw_result = item.get("result_preview", item.get("result"))
        if (raw_result is None or raw_result == "") and item.get("reason"):
            raw_result = item.get("reason")
        tool_result = {
            "tool_name": str(tool_name),
            "status": str(item.get("status") or "unknown"),
            "result": raw_result,
        }
        if isinstance(item.get("evidence_source"), dict):
            tool_result["evidence_source"] = item["evidence_source"]
        status = _generator._display_tool_status(tool_result)
        tool_result["status"] = status
        tool_results.append(tool_result)
        plan.append({
            "tool_name": str(tool_name),
            "status": status,
            "description": str(item.get("stage_name") or ""),
            "duration": item.get("duration", "?"),
        })

    task_contract = _merge_done_contract(execution, execution.get("task_contract"))
    return user_message, str(latest_assistant.content), plan, tool_results, task_contract


def _message_order_value(message: Message) -> str:
    created_at = getattr(message, "created_at", None)
    if created_at is None:
        return ""
    if hasattr(created_at, "isoformat"):
        return created_at.isoformat()
    return str(created_at)


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

    # Reports may only be generated from this user's conversation attached to
    # the selected project. Load execution rows explicitly for AsyncSession.
    stmt = (
        select(Conversation)
        .where(
            Conversation.id == req.conversation_id,
            Conversation.project_id == project_id,
            Conversation.user_id == user["id"],
        )
        .options(
            selectinload(Conversation.messages).selectinload(Message.tool_call_records)
        )
    )
    result = await session.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    user_msg, assistant_msg, plan, tool_results, task_contract = _extract_report_source(conv.messages)
    if not assistant_msg:
        raise HTTPException(400, "No assistant response found for the latest user message")

    # Generate report
    md = _generator.generate_conversation_report(
        project_name=project.name,
        conversation_title=conv.title or "分析报告",
        user_message=user_msg,
        research_notes="",  # Not stored separately yet
        plan=plan,
        tool_results=tool_results,
        final_report=assistant_msg,
        tags=[],
        task_contract=task_contract,
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
