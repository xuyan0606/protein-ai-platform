"""Project workspace API — CRUD for projects, sequences, and batch jobs."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user, require_admin
from app.models.project import (
    BatchJob,
    Organization,
    OrganizationMember,
    PermissionAudit,
    Project,
    ProjectMember,
    ProjectOrganizationGrant,
    ProjectSequence,
)
from app.services.project_acl import (
    find_user_by_email,
    get_project_access,
    get_user_display,
    get_user_display_map,
    list_accessible_projects,
    can_perform_project_action,
    project_policy_matrix,
    record_permission_audit,
    serialize_project_members,
)
from app.services.dbtl_trace import build_dbtl_trace

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


def _clean_project_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Project name cannot be empty")
    if "<" in cleaned or ">" in cleaned:
        raise ValueError("Project name cannot contain angle brackets")
    return cleaned


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_project_name(value)


class ProjectMemberOut(BaseModel):
    id: str
    project_id: str
    user_id: int
    email: str | None = None
    name: str | None = None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


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
    access_role: str = "owner"
    permissions: dict[str, bool] = {}
    members: list[ProjectMemberOut] = []
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
    access_role: str = "owner"
    permissions: dict[str, bool] = {}
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectMemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")


class ProjectMemberUpdate(BaseModel):
    role: str = Field(pattern="^(viewer|editor)$")


class OrganizationMemberOut(BaseModel):
    id: str
    organization_id: str
    user_id: int
    email: str | None = None
    name: str | None = None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectOrganizationGrantOut(BaseModel):
    id: str
    project_id: str
    project_name: str | None = None
    organization_id: str
    organization_name: str | None = None
    role: str
    created_by_user_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationOut(BaseModel):
    id: str
    name: str
    owner_user_id: int
    members: list[OrganizationMemberOut] = []
    project_grants: list[ProjectOrganizationGrantOut] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationListOut(BaseModel):
    count: int
    organizations: list[OrganizationOut]


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class OrganizationMemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = Field(default="member", pattern="^(member|admin)$")


class OrganizationMemberUpdate(BaseModel):
    role: str = Field(pattern="^(member|admin)$")


class ProjectOrganizationGrantCreate(BaseModel):
    organization_id: str = Field(min_length=1, max_length=32)
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")


class ProjectOrganizationGrantUpdate(BaseModel):
    role: str = Field(pattern="^(viewer|editor)$")


class PermissionAuditOut(BaseModel):
    id: str
    action: str
    actor_user_id: int | None = None
    target_user_id: int | None = None
    project_id: str | None = None
    organization_id: str | None = None
    role_before: str | None = None
    role_after: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PermissionAuditListOut(BaseModel):
    count: int
    audits: list[PermissionAuditOut]


async def _serialize_members(session: AsyncSession, project: Project) -> list[ProjectMemberOut]:
    members = await serialize_project_members(session, project)
    return [
        ProjectMemberOut(
            id=member.id,
            project_id=member.project_id,
            user_id=member.user_id,
            email=member.email,
            name=member.name,
            role=member.role,
            created_at=member.created_at,
        )
        for member in members
    ]


async def _project_out(session: AsyncSession, project: Project, access_role: str) -> ProjectOut:
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
        access_role=access_role,
        permissions=project_policy_matrix(access_role),
        members=await _serialize_members(session, project),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


async def _serialize_organization_members(
    session: AsyncSession,
    organization_id: str,
) -> list[OrganizationMemberOut]:
    result = await session.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.created_at.asc())
    )
    members = list(result.scalars().all())
    if not members:
        return []
    users = await get_user_display_map(session, [member.user_id for member in members])
    return [
        OrganizationMemberOut(
            id=member.id,
            organization_id=member.organization_id,
            user_id=member.user_id,
            email=users.get(member.user_id, (None, None))[0],
            name=users.get(member.user_id, (None, None))[1],
            role=member.role,
            created_at=member.created_at,
        )
        for member in members
    ]


async def _serialize_project_organization_grants(
    session: AsyncSession,
    *,
    project_id: str | None = None,
    organization_id: str | None = None,
) -> list[ProjectOrganizationGrantOut]:
    stmt = select(ProjectOrganizationGrant)
    if project_id:
        stmt = stmt.where(ProjectOrganizationGrant.project_id == project_id)
    if organization_id:
        stmt = stmt.where(ProjectOrganizationGrant.organization_id == organization_id)
    result = await session.execute(stmt.order_by(ProjectOrganizationGrant.created_at.asc()))
    grants = list(result.scalars().all())
    if not grants:
        return []

    project_result = await session.execute(select(Project).where(Project.id.in_([grant.project_id for grant in grants])))
    projects = {item.id: item for item in project_result.scalars().all()}
    organization_result = await session.execute(
        select(Organization).where(Organization.id.in_([grant.organization_id for grant in grants]))
    )
    organizations = {item.id: item for item in organization_result.scalars().all()}
    return [
        ProjectOrganizationGrantOut(
            id=grant.id,
            project_id=grant.project_id,
            project_name=projects.get(grant.project_id).name if projects.get(grant.project_id) else None,
            organization_id=grant.organization_id,
            organization_name=organizations.get(grant.organization_id).name if organizations.get(grant.organization_id) else None,
            role=grant.role,
            created_by_user_id=grant.created_by_user_id,
            created_at=grant.created_at,
        )
        for grant in grants
    ]


async def _organization_out(session: AsyncSession, organization: Organization) -> OrganizationOut:
    return OrganizationOut(
        id=organization.id,
        name=organization.name,
        owner_user_id=organization.owner_user_id,
        members=await _serialize_organization_members(session, organization.id),
        project_grants=await _serialize_project_organization_grants(session, organization_id=organization.id),
        created_at=organization.created_at,
    )


async def _get_project_for_grant_management(
    session: AsyncSession,
    *,
    project_id: str,
    user: dict,
) -> tuple[Project | None, str | None]:
    if user.get("role") == "admin":
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        return project, "owner" if project else None
    return await get_project_access(session, project_id=project_id, user_id=user["id"])


# ---------------------------------------------------------------------------
# Organization and permission audit management
# ---------------------------------------------------------------------------

@router.get("/admin/organizations", response_model=OrganizationListOut)
async def list_admin_organizations(
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(require_admin),
):
    """List organizations for the admin console."""
    bounded_limit = max(1, min(limit, 500))
    result = await session.execute(select(Organization).order_by(Organization.created_at.desc()).limit(bounded_limit))
    organizations = [
        await _organization_out(session, organization)
        for organization in result.scalars().all()
    ]
    return OrganizationListOut(count=len(organizations), organizations=organizations)


@router.post("/admin/organizations", response_model=OrganizationOut, status_code=201)
async def create_admin_organization(
    body: OrganizationCreate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(require_admin),
):
    """Create an organization and add the creator as org admin."""
    organization = Organization(name=body.name.strip(), owner_user_id=user["id"])
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user["id"], role="admin"))
    await record_permission_audit(
        session,
        action="organization.create",
        actor_user_id=user["id"],
        organization_id=organization.id,
        role_after="admin",
    )
    await session.flush()
    await session.refresh(organization)
    return await _organization_out(session, organization)


@router.post("/admin/organizations/{organization_id}/members", response_model=OrganizationMemberOut, status_code=201)
async def add_admin_organization_member(
    organization_id: str,
    body: OrganizationMemberCreate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(require_admin),
):
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")
    target = await find_user_by_email(session, body.email)
    if target is None:
        raise HTTPException(404, "User not found")

    result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == target.id,
        )
    )
    member = result.scalar_one_or_none()
    role_before = member.role if member is not None else None
    if member is None:
        member = OrganizationMember(organization_id=organization_id, user_id=target.id, role=body.role)
        session.add(member)
    else:
        member.role = body.role
    await record_permission_audit(
        session,
        action="organization_member.upsert",
        actor_user_id=user["id"],
        target_user_id=target.id,
        organization_id=organization_id,
        role_before=role_before,
        role_after=body.role,
    )
    await session.flush()
    await session.refresh(member)
    return OrganizationMemberOut(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        email=target.email,
        name=target.name,
        role=member.role,
        created_at=member.created_at,
    )


@router.patch("/admin/organizations/{organization_id}/members/{member_id}", response_model=OrganizationMemberOut)
async def update_admin_organization_member(
    organization_id: str,
    member_id: str,
    body: OrganizationMemberUpdate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(require_admin),
):
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")
    member = await session.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise HTTPException(404, "Organization member not found")
    role_before = member.role
    member.role = body.role
    await record_permission_audit(
        session,
        action="organization_member.update",
        actor_user_id=user["id"],
        target_user_id=member.user_id,
        organization_id=organization_id,
        role_before=role_before,
        role_after=body.role,
    )
    await session.flush()
    await session.refresh(member)
    email, name = await get_user_display(session, member.user_id)
    return OrganizationMemberOut(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        email=email,
        name=name,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/admin/organizations/{organization_id}/members/{member_id}", status_code=204)
async def remove_admin_organization_member(
    organization_id: str,
    member_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(require_admin),
):
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")
    member = await session.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise HTTPException(404, "Organization member not found")
    if int(member.user_id) == int(organization.owner_user_id):
        raise HTTPException(400, "Organization owner cannot be removed")
    await record_permission_audit(
        session,
        action="organization_member.delete",
        actor_user_id=user["id"],
        target_user_id=member.user_id,
        organization_id=organization_id,
        role_before=member.role,
        role_after=None,
    )
    await session.delete(member)


@router.get("/admin/permission-audits", response_model=PermissionAuditListOut)
async def list_admin_permission_audits(
    limit: int = 100,
    action: str | None = None,
    project_id: str | None = None,
    organization_id: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(require_admin),
):
    """List permission changes for the admin console."""
    bounded_limit = max(1, min(limit, 500))
    stmt = select(PermissionAudit)
    if action:
        stmt = stmt.where(PermissionAudit.action == action)
    if project_id:
        stmt = stmt.where(PermissionAudit.project_id == project_id)
    if organization_id:
        stmt = stmt.where(PermissionAudit.organization_id == organization_id)
    result = await session.execute(stmt.order_by(PermissionAudit.created_at.desc()).limit(bounded_limit))
    audits = [PermissionAuditOut.model_validate(item) for item in result.scalars().all()]
    return PermissionAuditListOut(count=len(audits), audits=audits)


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ProjectListOut])
async def list_projects(
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    projects = await list_accessible_projects(session, user_id=user["id"])
    return [
        ProjectListOut(
            id=p.id,
            name=p.name,
            description=p.description,
            sequence_count=len(p.sequences),
            file_count=len(p.files) if p.files else 0,
            wiki_ready=bool(p.outline_collection_id),
            access_role=access_role,
            permissions=project_policy_matrix(access_role),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p, access_role in projects
    ]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Project name")
    description: str | None = Field(None, max_length=5000)
    wiki_auto_publish: bool = Field(True, description="Auto-publish reports to Outline Wiki")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_project_name(value)


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

    return await _project_out(session, project, "owner")


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
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not project or not access_role:
        raise HTTPException(404, "Project not found")
    return await _project_out(session, project, access_role)


@router.get("/{project_id}/dbtl/trace")
async def get_project_dbtl_trace(
    project_id: str,
    round_key: str | None = Query(default=None, min_length=1),
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    """Return a read-only DBTL trace for a project the caller can read."""
    project, access_role = await get_project_access(
        session,
        project_id=project_id,
        user_id=user["id"],
    )
    if not project or not can_perform_project_action(access_role, "project.read"):
        raise HTTPException(404, "Project not found")
    return await build_dbtl_trace(session, project_id=project_id, round_key=round_key)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not project or not can_perform_project_action(access_role, "project.update"):
        raise HTTPException(404, "Project not found")
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    await session.flush()
    await session.refresh(project)
    return await _project_out(session, project, access_role)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not project or not can_perform_project_action(access_role, "project.delete"):
        raise HTTPException(404, "Project not found")
    await session.delete(project)


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
async def list_project_members(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not project or not can_perform_project_action(access_role, "project.members.read"):
        raise HTTPException(404, "Project not found")
    return await _serialize_members(session, project)


@router.post("/{project_id}/members", response_model=ProjectMemberOut, status_code=201)
async def add_project_member(
    project_id: str,
    body: ProjectMemberCreate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not project or not can_perform_project_action(access_role, "project.members.manage"):
        raise HTTPException(404, "Project not found")

    target = await find_user_by_email(session, body.email)
    if target is None:
        raise HTTPException(404, "User not found")
    if int(target.id) == int(project.user_id):
        raise HTTPException(400, "Project owner is already the owner")

    existing_result = await session.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == target.id)
    )
    member = existing_result.scalar_one_or_none()
    role_before = member.role if member is not None else None
    if member is None:
        member = ProjectMember(project_id=project_id, user_id=target.id, role=body.role)
        session.add(member)
    else:
        member.role = body.role
    await record_permission_audit(
        session,
        action="project_member.upsert",
        actor_user_id=user["id"],
        target_user_id=target.id,
        project_id=project_id,
        role_before=role_before,
        role_after=body.role,
    )
    await session.flush()
    await session.refresh(member)
    return ProjectMemberOut(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        email=target.email,
        name=target.name,
        role=member.role,
        created_at=member.created_at,
    )


@router.patch("/{project_id}/members/{member_id}", response_model=ProjectMemberOut)
async def update_project_member(
    project_id: str,
    member_id: str,
    body: ProjectMemberUpdate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not project or not can_perform_project_action(access_role, "project.members.manage"):
        raise HTTPException(404, "Project not found")
    member = await session.get(ProjectMember, member_id)
    if not member or member.project_id != project_id:
        raise HTTPException(404, "Project member not found")
    role_before = member.role
    member.role = body.role
    await record_permission_audit(
        session,
        action="project_member.update",
        actor_user_id=user["id"],
        target_user_id=member.user_id,
        project_id=project_id,
        role_before=role_before,
        role_after=body.role,
    )
    await session.flush()
    await session.refresh(member)
    email, name = await get_user_display(session, member.user_id)
    return ProjectMemberOut(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        email=email,
        name=name,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/{project_id}/members/{member_id}", status_code=204)
async def remove_project_member(
    project_id: str,
    member_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not project or not can_perform_project_action(access_role, "project.members.manage"):
        raise HTTPException(404, "Project not found")
    member = await session.get(ProjectMember, member_id)
    if not member or member.project_id != project_id:
        raise HTTPException(404, "Project member not found")
    await record_permission_audit(
        session,
        action="project_member.delete",
        actor_user_id=user["id"],
        target_user_id=member.user_id,
        project_id=project_id,
        role_before=member.role,
        role_after=None,
    )
    await session.delete(member)


@router.get("/{project_id}/organization-grants", response_model=list[ProjectOrganizationGrantOut])
async def list_project_organization_grants(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await _get_project_for_grant_management(session, project_id=project_id, user=user)
    if not project or not can_perform_project_action(access_role, "project.members.manage"):
        raise HTTPException(404, "Project not found")
    return await _serialize_project_organization_grants(session, project_id=project_id)


@router.post("/{project_id}/organization-grants", response_model=ProjectOrganizationGrantOut, status_code=201)
async def add_project_organization_grant(
    project_id: str,
    body: ProjectOrganizationGrantCreate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await _get_project_for_grant_management(session, project_id=project_id, user=user)
    if not project or not can_perform_project_action(access_role, "project.members.manage"):
        raise HTTPException(404, "Project not found")
    organization = await session.get(Organization, body.organization_id)
    if organization is None:
        raise HTTPException(404, "Organization not found")

    result = await session.execute(
        select(ProjectOrganizationGrant).where(
            ProjectOrganizationGrant.project_id == project_id,
            ProjectOrganizationGrant.organization_id == body.organization_id,
        )
    )
    grant = result.scalar_one_or_none()
    role_before = grant.role if grant is not None else None
    if grant is None:
        grant = ProjectOrganizationGrant(
            project_id=project_id,
            organization_id=body.organization_id,
            role=body.role,
            created_by_user_id=user["id"],
        )
        session.add(grant)
    else:
        grant.role = body.role
    await record_permission_audit(
        session,
        action="project_organization_grant.upsert",
        actor_user_id=user["id"],
        project_id=project_id,
        organization_id=body.organization_id,
        role_before=role_before,
        role_after=body.role,
    )
    await session.flush()
    await session.refresh(grant)
    serialized = await _serialize_project_organization_grants(session, project_id=project_id)
    return next(item for item in serialized if item.id == grant.id)


@router.patch("/{project_id}/organization-grants/{grant_id}", response_model=ProjectOrganizationGrantOut)
async def update_project_organization_grant(
    project_id: str,
    grant_id: str,
    body: ProjectOrganizationGrantUpdate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await _get_project_for_grant_management(session, project_id=project_id, user=user)
    if not project or not can_perform_project_action(access_role, "project.members.manage"):
        raise HTTPException(404, "Project not found")
    grant = await session.get(ProjectOrganizationGrant, grant_id)
    if grant is None or grant.project_id != project_id:
        raise HTTPException(404, "Organization grant not found")
    role_before = grant.role
    grant.role = body.role
    await record_permission_audit(
        session,
        action="project_organization_grant.update",
        actor_user_id=user["id"],
        project_id=project_id,
        organization_id=grant.organization_id,
        role_before=role_before,
        role_after=body.role,
    )
    await session.flush()
    await session.refresh(grant)
    serialized = await _serialize_project_organization_grants(session, project_id=project_id)
    return next(item for item in serialized if item.id == grant.id)


@router.delete("/{project_id}/organization-grants/{grant_id}", status_code=204)
async def remove_project_organization_grant(
    project_id: str,
    grant_id: str,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    project, access_role = await _get_project_for_grant_management(session, project_id=project_id, user=user)
    if not project or not can_perform_project_action(access_role, "project.members.manage"):
        raise HTTPException(404, "Project not found")
    grant = await session.get(ProjectOrganizationGrant, grant_id)
    if grant is None or grant.project_id != project_id:
        raise HTTPException(404, "Organization grant not found")
    await record_permission_audit(
        session,
        action="project_organization_grant.delete",
        actor_user_id=user["id"],
        project_id=project_id,
        organization_id=grant.organization_id,
        role_before=grant.role,
        role_after=None,
    )
    await session.delete(grant)


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
    proj, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not proj or not can_perform_project_action(access_role, "project.sequence.create"):
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
    proj, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not proj or not can_perform_project_action(access_role, "project.sequence.delete"):
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
    proj, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not proj or not can_perform_project_action(access_role, "project.batch.run"):
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
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    if not project or not can_perform_project_action(access_role, "project.batch.read"):
        raise HTTPException(404, "Project not found")
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
