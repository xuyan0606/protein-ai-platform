"""Publish service — saves .md reports to MinIO + Outline Wiki + ProjectFile DB.

Manual publish flow (user-initiated):
  1. User edits report in frontend Markdown editor
  2. User clicks "发布到Wiki"
  3. Frontend calls POST /api/projects/{id}/publish
  4. This service: upload to MinIO → publish to Outline → create ProjectFile record

Graceful degradation:
  - Outline unavailable → still saves to MinIO, outline_doc_id = None
  - MinIO unavailable → saves to local fallback, still creates ProjectFile record
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectFile
from app.services.report_quality_contract import validate_publishable_enzyme_report
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

_generator = ReportGenerator()
_AUTO_WIKI_WORKSPACE_NAME = "知识库发布区"
_AUTO_WIKI_WORKSPACE_DESC = "系统自动创建，用于未绑定项目的 Wiki 发布归档。"


class ReportQualityGateError(ValueError):
    """Raised when a structured enzyme report is not publishable."""

    def __init__(self, violations: list):
        self.violations = violations
        details = "；".join(str(item.message) for item in violations)
        super().__init__(f"报告质量门槛未通过：{details}")


async def ensure_wiki_publish_project(
    db: AsyncSession,
    *,
    user_id: int,
    collection_id: str | None = None,
) -> Project:
    """Get or create the lightweight workspace used for collection-only wiki publishing."""
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id, Project.name == _AUTO_WIKI_WORKSPACE_NAME)
        .order_by(Project.created_at.asc())
    )
    project = result.scalars().first()

    if project is None:
        project = Project(
            name=_AUTO_WIKI_WORKSPACE_NAME,
            description=_AUTO_WIKI_WORKSPACE_DESC,
            user_id=user_id,
            wiki_auto_publish=False,
            outline_collection_id=collection_id,
        )
        db.add(project)
        await db.flush()
        logger.info("Created auto wiki publish workspace for user %s: %s", user_id, project.id)

    if collection_id and project.outline_collection_id != collection_id:
        project.outline_collection_id = collection_id
        project.outline_root_doc_id = None
        await db.flush()

    return project


async def ensure_project_wiki(
    db: AsyncSession,
    project: Project,
) -> Project:
    """Ensure the project has an Outline collection + root doc.

    Existing projects created while Outline API auth was broken may have
    no collection/root IDs. Repair them lazily on first publish or tree load.
    """
    from app.services.outline_client import OutlineClient

    client = OutlineClient()
    collection_id = project.outline_collection_id
    if not collection_id:
        collection = await client.create_collection(
            name=project.name,
            description=project.description or f"酶蛋白AI平台项目: {project.name}",
        )
        collection_id = collection.get("id")
        if not collection_id:
            raise ValueError(f"Outline returned empty collection id for project {project.id}")
        project.outline_collection_id = collection_id

    if not project.outline_root_doc_id:
        root_content = _project_overview_template(project)
        doc = await client.create_document(
            title="项目概述",
            content=root_content,
            collection_id=collection_id,
            publish=True,
        )
        root_doc_id = doc.get("id")
        if not root_doc_id:
            raise ValueError(f"Outline returned empty root doc id for project {project.id}")
        project.outline_root_doc_id = root_doc_id

    await db.flush()
    logger.info(
        "Wiki lazily initialized for project %s: collection=%s, root_doc=%s",
        project.id,
        project.outline_collection_id,
        project.outline_root_doc_id,
    )
    return project


async def publish_report(
    db: AsyncSession,
    *,
    project_id: str,
    title: str,
    content: str,
    conversation_id: int | None = None,
    tags: list[str] | None = None,
    collection_id: str | None = None,
    parent_document_id: str | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    """Publish a Markdown report: MinIO + Outline + DB record.

    Args:
        db: Async DB session
        project_id: Target project ID
        title: Report title (used for filename + Outline doc title)
        content: Full Markdown content (may include YAML front matter)
        conversation_id: Source conversation (optional)
        tags: Tags for categorization
        source: Origin — "manual", "agent", "batch"

    Returns:
        dict with file_id, object_name, outline_doc_id, wiki_url
    """
    violations = validate_publishable_enzyme_report(content)
    if violations:
        raise ReportQualityGateError(violations)

    # 1. Validate project exists
    project = await db.get(Project, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    # Manual publish can explicitly target an existing Outline collection.
    # When a collection is selected in the UI, keep the project bound to that
    # collection for subsequent publishes instead of auto-creating a new one.
    if collection_id:
        if project.outline_collection_id != collection_id:
            project.outline_collection_id = collection_id
            project.outline_root_doc_id = None
            await db.flush()
    elif not project.outline_collection_id:
        project = await ensure_project_wiki(db, project)

    # 2. Generate filename and object path
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_title = _safe_filename(title)
    filename = f"{date_str}_{safe_title}.md"
    folder = f"projects/{project_id}/reports"

    # 3. Compute content hash for dedup
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    # 4. Upload to MinIO
    object_name = ""
    storage_uploaded = False
    file_size = len(content.encode("utf-8"))
    try:
        from app.services.storage import upload_file
        result = await upload_file(
            data=content.encode("utf-8"),
            filename=filename,
            content_type="text/markdown",
            folder=folder,
        )
        object_name = result.get("object_name", "")
        storage_uploaded = bool(object_name)
        logger.info("Uploaded .md to storage: %s (%d bytes)", object_name, file_size)
    except Exception as e:
        logger.warning("Storage upload failed: %s", e)
        object_name = f"{folder}/fallback_{content_hash}.md"

    # 5. Publish to Outline Wiki (if project has a collection)
    outline_doc_id = None
    wiki_url = None
    target_collection_id = collection_id or project.outline_collection_id
    if target_collection_id:
        try:
            from app.services.outline_client import OutlineClient
            client = OutlineClient()
            doc = await client.create_document(
                title=f"{date_str} {title}",
                content=content,
                collection_id=target_collection_id,
                parent_id=parent_document_id,
                publish=True,
            )
            outline_doc_id = doc.get("id")
            if not outline_doc_id:
                from app.services.outline_client import OutlineUnavailableError
                raise OutlineUnavailableError("Outline returned no document ID")
            # Outline document URL pattern
            doc_slug = doc.get("urlId", outline_doc_id)
            wiki_url = f"/wiki/doc/{doc_slug}"
            logger.info("Published to Outline: doc_id=%s", outline_doc_id)
        except Exception as e:
            if source == "manual":
                if storage_uploaded:
                    try:
                        from app.services.storage import delete_file
                        await delete_file(object_name)
                    except Exception as cleanup_error:
                        logger.warning("Storage cleanup after Wiki publish failure failed: %s", cleanup_error)
                from app.services.outline_client import OutlineAuthenticationError, OutlineUnavailableError
                if isinstance(e, (OutlineAuthenticationError, OutlineUnavailableError)):
                    raise
                raise OutlineUnavailableError("Outline document publish failed") from e
            logger.warning("Outline publish failed (file still saved): %s", e)

    # 6. Create ProjectFile record
    import uuid
    file_record = ProjectFile(
        id=uuid.uuid4().hex[:16],
        project_id=project_id,
        filename=filename,
        object_name=object_name,
        file_type="md",
        file_size=file_size,
        content_hash=content_hash,
        source=source,
        conversation_id=conversation_id,
        outline_doc_id=outline_doc_id,
        tags=__import__("json").dumps(tags or [], ensure_ascii=False),
    )
    db.add(file_record)
    await db.commit()

    return {
        "file_id": file_record.id,
        "filename": filename,
        "object_name": object_name,
        "outline_doc_id": outline_doc_id,
        "wiki_url": wiki_url,
        "file_size": file_size,
    }


async def list_project_files(
    db: AsyncSession,
    project_id: str,
    file_type: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """List files in a project with optional filters."""
    from sqlalchemy import select

    stmt = select(ProjectFile).where(ProjectFile.project_id == project_id)
    if file_type:
        stmt = stmt.where(ProjectFile.file_type == file_type)
    if source:
        stmt = stmt.where(ProjectFile.source == source)
    stmt = stmt.order_by(ProjectFile.created_at.desc())

    result = await db.execute(stmt)
    files = result.scalars().all()

    return [
        {
            "id": f.id,
            "filename": f.filename,
            "object_name": f.object_name,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "source": f.source,
            "conversation_id": f.conversation_id,
            "outline_doc_id": f.outline_doc_id,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


async def delete_project_file(db: AsyncSession, project_id: str, file_id: str) -> bool:
    """Delete a project file from DB + storage."""
    file_record = await db.get(ProjectFile, file_id)
    if not file_record or file_record.project_id != project_id:
        return False

    # Delete from storage
    try:
        from app.services.storage import delete_file
        await delete_file(file_record.object_name)
    except Exception as e:
        logger.warning("Storage delete failed: %s", e)

    await db.delete(file_record)
    await db.commit()
    return True


def _safe_filename(title: str) -> str:
    """Convert a title to a safe filename component."""
    import re
    # Remove non-alphanumeric except Chinese/underscore/hyphen
    safe = re.sub(r'[^\w一-鿿-]', '_', title)
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe[:80] or "report"


def _project_overview_template(project: Project) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    desc = project.description or "（暂无描述）"
    return (
        f"# {project.name}\n\n"
        f"> 创建时间：{now} | 序列数：0\n\n"
        f"## 项目描述\n\n{desc}\n\n"
        f"## 蛋白序列\n\n"
        f"_（添加序列后在此显示）_\n\n"
        f"## 分析报告\n\n"
        f"_（AI分析完成后自动更新）_\n\n"
        f"## 批量结果\n\n"
        f"_（批量任务完成后自动更新）_\n"
    )
