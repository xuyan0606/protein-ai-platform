"""Project workspace API — CRUD for projects, sequences, and batch jobs."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.project import Project, ProjectSequence, BatchJob

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SeqCreate(BaseModel):
    name: str
    sequence: str
    notes: str | None = None


class SeqOut(BaseModel):
    id: str
    name: str
    sequence: str
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchOut(BaseModel):
    id: str
    status: str
    total: int
    completed: int
    results: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    user_id: int
    sequences: list[SeqOut] = []
    batch_jobs: list[BatchOut] = []
    outline_collection_id: str | None = None
    outline_root_doc_id: str | None = None
    wiki_auto_publish: bool = False
    file_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    sequence_count: int = 0
    file_count: int = 0
    wiki_ready: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ProjectListOut])
async def list_projects(
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    stmt = select(Project).where(Project.user_id == user["id"]).order_by(Project.updated_at.desc())
    result = await session.execute(stmt)
    projects = result.scalars().all()
    return [
        ProjectListOut(
            id=p.id,
            name=p.name,
            description=p.description,
            sequence_count=len(p.sequences),
            file_count=len(p.files) if p.files else 0,
            wiki_ready=bool(p.outline_collection_id),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Project name")
    description: str | None = Field(None, max_length=5000)
    wiki_auto_publish: bool = Field(True, description="Auto-publish reports to Outline Wiki")


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project = Project(
        name=body.name,
        description=body.description,
        user_id=user["id"],
        wiki_auto_publish=body.wiki_auto_publish,
    )
    session.add(project)
    await session.flush()
    await session.refresh(project)

    # Auto-create Outline Wiki Collection + root page
    await _init_project_wiki(project, session)

    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        user_id=project.user_id,
        sequences=[],
        batch_jobs=[],
        outline_collection_id=project.outline_collection_id,
        outline_root_doc_id=project.outline_root_doc_id,
        wiki_auto_publish=project.wiki_auto_publish,
        file_count=0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


async def _init_project_wiki(project: Project, session: AsyncSession) -> None:
    """Create an Outline Collection + root overview page for a new project.

    Graceful degradation: if Outline is unreachable or unconfigured, the
    project is still created — only the wiki fields remain None.
    """
    try:
        from app.services.outline_client import get_outline_client
        client = get_outline_client()

        # 1. Create collection
        collection = await client.create_collection(
            name=project.name,
            description=project.description or f"酶蛋白AI平台项目: {project.name}",
        )
        collection_id = collection.get("id")
        if not collection_id:
            logger.warning("Outline returned empty collection id for project %s", project.id)
            return

        # 2. Create root overview page
        root_content = _project_overview_template(project)
        doc = await client.create_document(
            title="项目概述",
            content=root_content,
            collection_id=collection_id,
            publish=True,
        )
        root_doc_id = doc.get("id")

        # 3. Persist wiki IDs
        project.outline_collection_id = collection_id
        project.outline_root_doc_id = root_doc_id
        await session.flush()

        logger.info(
            "Wiki initialized for project %s: collection=%s, root_doc=%s",
            project.id, collection_id, root_doc_id,
        )
    except Exception as e:
        logger.warning("Outline unavailable, skipping wiki init for project %s: %s", project.id, e)
        # Non-fatal — project is still usable without wiki


def _project_overview_template(project: Project) -> str:
    """Generate the root overview page Markdown for a new project."""
    from datetime import datetime
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


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user["id"])
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        user_id=project.user_id,
        sequences=[SeqOut.model_validate(s) for s in project.sequences],
        batch_jobs=[BatchOut.model_validate(b) for b in project.batch_jobs],
        outline_collection_id=project.outline_collection_id,
        outline_root_doc_id=project.outline_root_doc_id,
        wiki_auto_publish=project.wiki_auto_publish,
        file_count=len(project.files) if project.files else 0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user["id"])
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    await session.flush()
    await session.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user["id"])
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    await session.delete(project)


# ---------------------------------------------------------------------------
# Sequence management within a project
# ---------------------------------------------------------------------------

@router.post("/{project_id}/sequences", response_model=SeqOut, status_code=201)
async def add_sequence(
    project_id: str,
    body: SeqCreate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    proj = await session.get(Project, project_id)
    if not proj or proj.user_id != user["id"]:
        raise HTTPException(404, "Project not found")
    seq = ProjectSequence(project_id=project_id, name=body.name, sequence=body.sequence.upper(), notes=body.notes)
    session.add(seq)
    await session.flush()
    await session.refresh(seq)
    return seq


@router.delete("/{project_id}/sequences/{seq_id}", status_code=204)
async def remove_sequence(
    project_id: str,
    seq_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    proj = await session.get(Project, project_id)
    if not proj or proj.user_id != user["id"]:
        raise HTTPException(404, "Project not found")
    seq = await session.get(ProjectSequence, seq_id)
    if not seq or seq.project_id != project_id:
        raise HTTPException(404, "Sequence not found")
    await session.delete(seq)


# ---------------------------------------------------------------------------
# Batch run
# ---------------------------------------------------------------------------

class BatchRunRequest(BaseModel):
    tool: str = Field(description="Tool name to run: protein_benchmark, mutation_priority_score, etc.")
    params: dict = Field(default_factory=dict, description="Additional params to pass to the tool")


class BatchRunOut(BaseModel):
    job_id: str
    status: str
    total: int
    message: str


@router.post("/{project_id}/batch-run", response_model=BatchRunOut)
async def batch_run(
    project_id: str,
    body: BatchRunRequest,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    proj = await session.get(Project, project_id)
    if not proj or proj.user_id != user["id"]:
        raise HTTPException(404, "Project not found")

    if not proj.sequences:
        raise HTTPException(400, "No sequences in project")

    # Create batch job
    job = BatchJob(
        project_id=project_id,
        status="pending",
        total=len(proj.sequences),
        completed=0,
    )
    session.add(job)
    await session.flush()

    # Run tool for each sequence synchronously (MVP — no Celery/Redis)
    results = []
    for s in proj.sequences:
        try:
            result = await _run_tool(body.tool, s.sequence, body.params)
            results.append({
                "sequence_name": s.name,
                "sequence_id": s.id,
                "status": "completed",
                "result": result,
            })
        except Exception as e:
            results.append({
                "sequence_name": s.name,
                "sequence_id": s.id,
                "status": "failed",
                "error": str(e),
            })

    job.status = "completed"
    job.completed = job.total
    job.results = {"tool": body.tool, "items": results}
    await session.flush()

    # Auto-publish batch results to wiki if enabled
    published_files = []
    if proj.wiki_auto_publish and proj.outline_collection_id:
        published_files = await _publish_batch_wiki(
            session, proj, job, body.tool, results,
        )

    return BatchRunOut(
        job_id=job.id,
        status="completed",
        total=job.total,
        message=f"Batch complete: {job.completed}/{job.total} sequences processed"
                + (f" ({len(published_files)} reports published to wiki)" if published_files else ""),
    )


@router.get("/{project_id}/batch-jobs", response_model=list[BatchOut])
async def list_batch_jobs(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    stmt = select(BatchJob).where(BatchJob.project_id == project_id).order_by(BatchJob.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Batch auto-publish to wiki
# ---------------------------------------------------------------------------

async def _publish_batch_wiki(
    session: AsyncSession,
    project: Project,
    job: BatchJob,
    tool_name: str,
    results: list[dict],
) -> list[dict]:
    """Publish batch results to wiki: per-sequence .md + summary page.

    Returns list of published file info dicts.
    """
    from app.services.report_generator import ReportGenerator
    from app.services.publish_service import publish_report

    generator = ReportGenerator()
    published = []
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Collect sequences for the summary report
    seq_list = []
    for s in project.sequences:
        seq_list.append({"name": s.name, "sequence": s.sequence})

    # 1. Per-sequence reports
    for r in results:
        if r["status"] != "completed":
            continue
        seq_name = r["sequence_name"]
        title = f"{date_str} {seq_name} — {tool_name}"

        # Generate individual .md report
        md = generator.generate_conversation_report(
            project_name=project.name,
            conversation_title=f"{seq_name} 批量分析结果",
            user_message=f"批量分析: {tool_name} 对 {seq_name}",
            research_notes="",
            plan=[{"tool_name": tool_name, "status": "completed",
                   "description": f"批量分析 {seq_name}", "duration": "?"}],
            tool_results=[{"tool_name": tool_name, "status": "completed",
                           "result": r.get("result", {})}],
            final_report=f"## {seq_name}\n\n工具 `{tool_name}` 分析结果：\n```json\n"
                         + __import__("json").dumps(r.get("result", {}), ensure_ascii=False, default=str)[:2000]
                         + "\n```",
            tags=["batch", tool_name, seq_name],
        )

        try:
            result = await publish_report(
                session,
                project_id=project.id,
                title=title,
                content=md,
                source="batch",
            )
            published.append({"filename": title, **result})
        except Exception as e:
            logger.warning("Failed to publish batch report for %s: %s", seq_name, e)

    # 2. Summary report
    summary_title = f"{date_str} Batch-{job.id[:6]} {tool_name} 汇总"
    summary_md = generator.generate_batch_summary(
        project_name=project.name,
        batch_id=job.id,
        tool_name=tool_name,
        sequences=seq_list,
        results=[r.get("result", r.get("error", "")) for r in results],
    )

    try:
        summary_result = await publish_report(
            session,
            project_id=project.id,
            title=summary_title,
            content=summary_md,
            source="batch",
            tags=["batch", "summary", tool_name],
        )
        published.append({"filename": summary_title, **summary_result})
    except Exception as e:
        logger.warning("Failed to publish batch summary: %s", e)

    return published


# ---------------------------------------------------------------------------
# Tool runner (inline — reuses tool registry)
# ---------------------------------------------------------------------------

async def _run_tool(tool_name: str, sequence: str, extra_params: dict) -> dict:
    from app.tools.registry import ToolRegistry

    tool = ToolRegistry.get_tool(tool_name)
    if not tool:
        raise ValueError(f"Unknown tool: {tool_name}")

    # Build params from tool schema
    params = dict(extra_params)
    properties = tool.parameters.get("properties", {})

    # Auto-fill sequence param
    for key, prop in properties.items():
        if key not in params:
            if key in ("sequence", "query_sequence"):
                params[key] = sequence
            elif prop.get("default") is not None:
                params[key] = prop["default"]

    # Call the tool handler
    import asyncio
    handler = tool.handler
    if asyncio.iscoroutinefunction(handler):
        return await handler(**params)
    return handler(**params)
