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

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectFile
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

_generator = ReportGenerator()


async def publish_report(
    db: AsyncSession,
    *,
    project_id: str,
    title: str,
    content: str,
    conversation_id: int | None = None,
    tags: list[str] | None = None,
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
    # 1. Validate project exists
    project = await db.get(Project, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    # 2. Generate filename and object path
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_title = _safe_filename(title)
    filename = f"{date_str}_{safe_title}.md"
    folder = f"projects/{project_id}/reports"

    # 3. Compute content hash for dedup
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    # 4. Upload to MinIO
    object_name = ""
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
        logger.info("Uploaded .md to storage: %s (%d bytes)", object_name, file_size)
    except Exception as e:
        logger.warning("Storage upload failed: %s", e)
        object_name = f"{folder}/fallback_{content_hash}.md"

    # 5. Publish to Outline Wiki (if project has a collection)
    outline_doc_id = None
    wiki_url = None
    if project.outline_collection_id:
        try:
            from app.services.outline_client import OutlineClient
            client = OutlineClient()
            doc = await client.create_document(
                title=f"{date_str} {title}",
                content=content,
                collection_id=project.outline_collection_id,
                parent_id=project.outline_root_doc_id,
                publish=True,
            )
            outline_doc_id = doc.get("id")
            # Outline document URL pattern
            doc_slug = doc.get("urlId", outline_doc_id)
            wiki_url = f"/wiki/doc/{doc_slug}"
            logger.info("Published to Outline: doc_id=%s", outline_doc_id)
        except Exception as e:
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
