"""Project workspace API — CRUD for projects, sequences, and batch jobs."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.project import Project, ProjectSequence, BatchJob

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


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    sequence_count: int = 0
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
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project = Project(name=body.name, description=body.description, user_id=user["id"])
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


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
    return project


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

    return BatchRunOut(
        job_id=job.id,
        status="completed",
        total=job.total,
        message=f"Batch complete: {job.completed}/{job.total} sequences processed",
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
