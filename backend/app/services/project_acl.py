"""Project-level ACL helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import OrganizationMember, PermissionAudit, Project, ProjectMember, ProjectOrganizationGrant
from app.models.user import User

ProjectAccessRole = Literal["owner", "editor", "viewer"]
ProjectAction = Literal[
    "project.read",
    "project.update",
    "project.delete",
    "project.members.read",
    "project.members.manage",
    "project.sequence.create",
    "project.sequence.delete",
    "project.batch.read",
    "project.batch.run",
    "project.wiki.publish",
    "project.file.read",
    "project.file.write",
    "project.chat.bind",
]

ROLE_RANK = {
    "viewer": 1,
    "editor": 2,
    "owner": 3,
}

PROJECT_ACTION_MIN_ROLE: dict[ProjectAction, ProjectAccessRole] = {
    "project.read": "viewer",
    "project.update": "editor",
    "project.delete": "owner",
    "project.members.read": "viewer",
    "project.members.manage": "owner",
    "project.sequence.create": "editor",
    "project.sequence.delete": "editor",
    "project.batch.read": "viewer",
    "project.batch.run": "editor",
    "project.wiki.publish": "editor",
    "project.file.read": "viewer",
    "project.file.write": "editor",
    "project.chat.bind": "editor",
}


@dataclass(frozen=True)
class ProjectMemberView:
    id: str
    project_id: str
    user_id: int
    email: str | None
    name: str | None
    role: str
    created_at: datetime


def can_write(role: str | None) -> bool:
    return ROLE_RANK.get(role or "", 0) >= ROLE_RANK["editor"]


def can_manage(role: str | None) -> bool:
    return role == "owner"


def can_perform_project_action(role: str | None, action: ProjectAction) -> bool:
    """Return whether a project role can perform a named action.

    This keeps viewer/guest read-only behavior explicit and gives future
    organization-level policies one central contract to extend.
    """
    required = PROJECT_ACTION_MIN_ROLE[action]
    return ROLE_RANK.get(role or "", 0) >= ROLE_RANK[required]


def project_policy_matrix(role: str | None) -> dict[str, bool]:
    """Serialize action permissions for API/UI consumers."""
    return {
        action: can_perform_project_action(role, action)
        for action in PROJECT_ACTION_MIN_ROLE
    }


def _max_project_role(*roles: str | None) -> ProjectAccessRole | None:
    best: ProjectAccessRole | None = None
    for role in roles:
        if role not in ROLE_RANK:
            continue
        if best is None or ROLE_RANK[role] > ROLE_RANK[best]:
            best = role  # type: ignore[assignment]
    return best


async def record_permission_audit(
    session: AsyncSession,
    *,
    action: str,
    actor_user_id: int | str | None = None,
    target_user_id: int | str | None = None,
    project_id: str | None = None,
    organization_id: str | None = None,
    role_before: str | None = None,
    role_after: str | None = None,
) -> None:
    """Append a permission audit row without changing authorization outcome."""
    session.add(
        PermissionAudit(
            action=action,
            actor_user_id=int(actor_user_id) if actor_user_id is not None else None,
            target_user_id=int(target_user_id) if target_user_id is not None else None,
            project_id=project_id,
            organization_id=organization_id,
            role_before=role_before,
            role_after=role_after,
        )
    )


async def get_project_access(
    session: AsyncSession,
    *,
    project_id: str,
    user_id: int | str,
) -> tuple[Project | None, ProjectAccessRole | None]:
    """Return the project and current user's effective project role."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        return None, None
    if int(project.user_id) == int(user_id):
        return project, "owner"

    member_result = await session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == int(user_id),
        )
    )
    member = member_result.scalar_one_or_none()
    direct_role: ProjectAccessRole | None = None
    if member is not None:
        direct_role = "editor" if member.role == "editor" else "viewer"

    org_result = await session.execute(
        select(ProjectOrganizationGrant.role)
        .join(OrganizationMember, OrganizationMember.organization_id == ProjectOrganizationGrant.organization_id)
        .where(
            ProjectOrganizationGrant.project_id == project_id,
            OrganizationMember.user_id == int(user_id),
        )
    )
    org_role = _max_project_role(*org_result.scalars().all())
    return project, _max_project_role(direct_role, org_role)


async def list_accessible_projects(session: AsyncSession, *, user_id: int | str) -> list[tuple[Project, ProjectAccessRole]]:
    """Return projects owned by or shared with a user."""
    result = await session.execute(
        select(Project)
        .outerjoin(ProjectMember, ProjectMember.project_id == Project.id)
        .where(or_(Project.user_id == int(user_id), ProjectMember.user_id == int(user_id)))
        .order_by(Project.updated_at.desc())
    )
    projects = result.unique().scalars().all()

    member_result = await session.execute(
        select(ProjectMember).where(ProjectMember.user_id == int(user_id))
    )
    memberships = {member.project_id: member.role for member in member_result.scalars().all()}

    org_project_result = await session.execute(
        select(Project, ProjectOrganizationGrant.role)
        .join(ProjectOrganizationGrant, ProjectOrganizationGrant.project_id == Project.id)
        .join(OrganizationMember, OrganizationMember.organization_id == ProjectOrganizationGrant.organization_id)
        .where(OrganizationMember.user_id == int(user_id))
        .order_by(Project.updated_at.desc())
    )
    org_roles: dict[str, ProjectAccessRole] = {}
    by_id = {project.id: project for project in projects}
    for project, role in org_project_result.all():
        by_id.setdefault(project.id, project)
        org_roles[project.id] = _max_project_role(org_roles.get(project.id), role) or "viewer"

    output: list[tuple[Project, ProjectAccessRole]] = []
    for project in sorted(by_id.values(), key=lambda item: item.updated_at, reverse=True):
        if int(project.user_id) == int(user_id):
            output.append((project, "owner"))
            continue
        direct_role: ProjectAccessRole | None = "editor" if memberships.get(project.id) == "editor" else ("viewer" if project.id in memberships else None)
        role = _max_project_role(direct_role, org_roles.get(project.id))
        if role:
            output.append((project, role))
    return output


async def serialize_project_members(session: AsyncSession, project: Project) -> list[ProjectMemberView]:
    """Return project members enriched with user display fields."""
    member_result = await session.execute(
        select(ProjectMember).where(ProjectMember.project_id == project.id).order_by(ProjectMember.created_at.asc())
    )
    members = list(member_result.scalars().all())
    if not members:
        return []

    user_ids = [member.user_id for member in members]
    result = await session.execute(select(User).where(User.id.in_(user_ids)))
    users = {user.id: user for user in result.scalars().all()}

    return [
        ProjectMemberView(
            id=member.id,
            project_id=member.project_id,
            user_id=member.user_id,
            email=users.get(member.user_id).email if users.get(member.user_id) else None,
            name=users.get(member.user_id).name if users.get(member.user_id) else None,
            role=member.role,
            created_at=member.created_at,
        )
        for member in members
    ]


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Find a user by email without exposing the User ORM import to API modules."""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_display(session: AsyncSession, user_id: int | str) -> tuple[str | None, str | None]:
    """Return email and name for a user id."""
    user = await session.get(User, int(user_id))
    if user is None:
        return None, None
    return user.email, user.name


async def get_user_display_map(session: AsyncSession, user_ids: list[int]) -> dict[int, tuple[str | None, str | None]]:
    """Return email/name display fields keyed by user id."""
    if not user_ids:
        return {}
    result = await session.execute(select(User).where(User.id.in_(user_ids)))
    return {
        user.id: (user.email, user.name)
        for user in result.scalars().all()
    }
