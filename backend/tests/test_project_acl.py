"""Project-level ACL API regression tests."""

import json

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.project import Organization, OrganizationMember, PermissionAudit, ProjectOrganizationGrant
from app.models.user import User


async def _create_user(session, email: str, name: str = "Test User") -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name=name,
    )
    session.add(user)
    await session.flush()
    return user


def _login(client, user: User) -> None:
    client.cookies.clear()
    client.cookies.set("pa_token", create_access_token(user.id))


async def _create_project(client, owner: User, name: str = "ACL Project") -> str:
    _login(client, owner)
    response = await client.post("/api/projects", json={"name": name, "description": "acl"})
    assert response.status_code == 201
    return response.json()["id"]


async def test_owner_can_manage_project_members(client, session):
    owner = await _create_user(session, "acl-owner@example.com", "Owner")
    viewer = await _create_user(session, "acl-viewer@example.com", "Viewer")
    await session.commit()
    project_id = await _create_project(client, owner)

    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": viewer.email, "role": "viewer"},
    )
    assert response.status_code == 201
    member = response.json()
    assert member["email"] == viewer.email
    assert member["role"] == "viewer"

    response = await client.patch(
        f"/api/projects/{project_id}/members/{member['id']}",
        json={"role": "editor"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "editor"

    response = await client.get(f"/api/projects/{project_id}/members")
    assert response.status_code == 200
    assert response.json()[0]["email"] == viewer.email

    response = await client.delete(f"/api/projects/{project_id}/members/{member['id']}")
    assert response.status_code == 204


async def test_viewer_can_read_but_cannot_write_project(client, session):
    owner = await _create_user(session, "acl-owner-read@example.com")
    viewer = await _create_user(session, "acl-viewer-read@example.com")
    await session.commit()
    project_id = await _create_project(client, owner, name="Viewer Read")

    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": viewer.email, "role": "viewer"},
    )
    assert response.status_code == 201

    _login(client, viewer)
    response = await client.get("/api/projects")
    assert response.status_code == 200
    listed = {item["id"]: item for item in response.json()}
    assert listed[project_id]["access_role"] == "viewer"

    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["access_role"] == "viewer"
    assert detail["permissions"]["project.read"] is True
    assert detail["permissions"]["project.update"] is False
    assert detail["permissions"]["project.members.manage"] is False
    assert detail["permissions"]["project.batch.run"] is False

    response = await client.get(f"/api/projects/{project_id}/batch-jobs")
    assert response.status_code == 200

    response = await client.patch(f"/api/projects/{project_id}", json={"name": "Blocked"})
    assert response.status_code == 404

    response = await client.post(
        f"/api/projects/{project_id}/sequences",
        json={"name": "WT", "sequence": "MTEST"},
    )
    assert response.status_code == 404

    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": owner.email, "role": "viewer"},
    )
    assert response.status_code == 404


async def test_editor_can_write_but_cannot_manage_members(client, session):
    owner = await _create_user(session, "acl-owner-edit@example.com")
    editor = await _create_user(session, "acl-editor@example.com")
    await session.commit()
    project_id = await _create_project(client, owner, name="Editor Write")

    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": editor.email, "role": "editor"},
    )
    assert response.status_code == 201

    _login(client, editor)
    response = await client.patch(f"/api/projects/{project_id}", json={"description": "updated"})
    assert response.status_code == 200
    assert response.json()["description"] == "updated"
    assert response.json()["access_role"] == "editor"
    assert response.json()["permissions"]["project.update"] is True
    assert response.json()["permissions"]["project.members.manage"] is False

    response = await client.post(
        f"/api/projects/{project_id}/sequences",
        json={"name": "WT", "sequence": "MTEST"},
    )
    assert response.status_code == 201
    assert response.json()["sequence"] == "MTEST"

    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": owner.email, "role": "viewer"},
    )
    assert response.status_code == 404


async def test_project_policy_matrix_preserves_guest_readonly_boundary(client, session):
    owner = await _create_user(session, "acl-owner-policy@example.com")
    viewer = await _create_user(session, "acl-viewer-policy@example.com")
    editor = await _create_user(session, "acl-editor-policy@example.com")
    await session.commit()
    project_id = await _create_project(client, owner, name="Policy Matrix")

    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": viewer.email, "role": "viewer"},
    )
    assert response.status_code == 201
    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": editor.email, "role": "editor"},
    )
    assert response.status_code == 201

    _login(client, viewer)
    response = await client.get("/api/projects")
    assert response.status_code == 200
    viewer_project = next(item for item in response.json() if item["id"] == project_id)
    assert viewer_project["permissions"]["project.read"] is True
    assert viewer_project["permissions"]["project.file.read"] is True
    assert viewer_project["permissions"]["project.file.write"] is False
    assert viewer_project["permissions"]["project.chat.bind"] is False

    _login(client, editor)
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    editor_permissions = response.json()["permissions"]
    assert editor_permissions["project.sequence.create"] is True
    assert editor_permissions["project.batch.run"] is True
    assert editor_permissions["project.members.manage"] is False

    _login(client, owner)
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    owner_permissions = response.json()["permissions"]
    assert owner_permissions["project.delete"] is True
    assert owner_permissions["project.members.manage"] is True


async def test_organization_grant_inherits_project_access(client, session):
    owner = await _create_user(session, "acl-org-owner@example.com")
    org_member = await _create_user(session, "acl-org-member@example.com")
    await session.commit()
    project_id = await _create_project(client, owner, name="Org Shared")

    organization = Organization(name="R&D Team", owner_user_id=owner.id)
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=org_member.id, role="member"))
    session.add(
        ProjectOrganizationGrant(
            project_id=project_id,
            organization_id=organization.id,
            role="viewer",
            created_by_user_id=owner.id,
        )
    )
    await session.commit()

    _login(client, org_member)
    response = await client.get("/api/projects")
    assert response.status_code == 200
    listed = {item["id"]: item for item in response.json()}
    assert listed[project_id]["access_role"] == "viewer"
    assert listed[project_id]["permissions"]["project.read"] is True
    assert listed[project_id]["permissions"]["project.update"] is False

    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["access_role"] == "viewer"

    response = await client.post(
        f"/api/projects/{project_id}/sequences",
        json={"name": "Blocked", "sequence": "MTEST"},
    )
    assert response.status_code == 404


async def test_organization_editor_grant_allows_write_and_direct_role_precedence(client, session):
    owner = await _create_user(session, "acl-org-owner-edit@example.com")
    org_member = await _create_user(session, "acl-org-editor@example.com")
    await session.commit()
    project_id = await _create_project(client, owner, name="Org Editor")

    organization = Organization(name="Engineering", owner_user_id=owner.id)
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=org_member.id, role="member"))
    session.add(
        ProjectOrganizationGrant(
            project_id=project_id,
            organization_id=organization.id,
            role="editor",
            created_by_user_id=owner.id,
        )
    )
    await session.commit()

    _login(client, org_member)
    response = await client.patch(f"/api/projects/{project_id}", json={"description": "org edit"})
    assert response.status_code == 200
    assert response.json()["access_role"] == "editor"
    assert response.json()["permissions"]["project.update"] is True
    assert response.json()["permissions"]["project.members.manage"] is False


async def test_project_member_changes_create_permission_audits(client, session):
    owner = await _create_user(session, "acl-audit-owner@example.com")
    viewer = await _create_user(session, "acl-audit-viewer@example.com")
    await session.commit()
    project_id = await _create_project(client, owner, name="Audit Project")

    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": viewer.email, "role": "viewer"},
    )
    assert response.status_code == 201
    member_id = response.json()["id"]

    response = await client.patch(
        f"/api/projects/{project_id}/members/{member_id}",
        json={"role": "editor"},
    )
    assert response.status_code == 200

    response = await client.delete(f"/api/projects/{project_id}/members/{member_id}")
    assert response.status_code == 204

    await session.flush()
    audits = (
        await session.execute(
            select(PermissionAudit).where(PermissionAudit.project_id == project_id).order_by(PermissionAudit.created_at.asc())
        )
    ).scalars().all()
    assert [audit.action for audit in audits] == [
        "project_member.upsert",
        "project_member.update",
        "project_member.delete",
    ]
    assert audits[0].role_before is None
    assert audits[0].role_after == "viewer"
    assert audits[1].role_before == "viewer"
    assert audits[1].role_after == "editor"
    assert audits[2].role_before == "editor"
    assert audits[2].role_after is None


async def test_admin_can_manage_organizations_and_query_permission_audits(client, session):
    admin = await _create_user(session, "acl-org-admin@example.com", "Org Admin")
    member = await _create_user(session, "acl-org-api-member@example.com", "Org Member")
    admin.role = "admin"
    await session.commit()

    _login(client, admin)
    response = await client.post("/api/projects/admin/organizations", json={"name": "API Team"})
    assert response.status_code == 201
    organization = response.json()
    organization_id = organization["id"]
    assert organization["name"] == "API Team"
    assert organization["members"][0]["email"] == admin.email
    assert organization["members"][0]["role"] == "admin"

    response = await client.post(
        f"/api/projects/admin/organizations/{organization_id}/members",
        json={"email": member.email, "role": "member"},
    )
    assert response.status_code == 201
    org_member = response.json()
    assert org_member["email"] == member.email
    assert org_member["role"] == "member"

    response = await client.patch(
        f"/api/projects/admin/organizations/{organization_id}/members/{org_member['id']}",
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    response = await client.get("/api/projects/admin/organizations")
    assert response.status_code == 200
    listed = {item["id"]: item for item in response.json()["organizations"]}
    assert listed[organization_id]["members"][1]["email"] == member.email
    assert listed[organization_id]["members"][1]["role"] == "admin"

    response = await client.get(f"/api/projects/admin/permission-audits?organization_id={organization_id}")
    assert response.status_code == 200
    actions = [item["action"] for item in response.json()["audits"]]
    assert "organization.create" in actions
    assert "organization_member.upsert" in actions
    assert "organization_member.update" in actions


async def test_project_owner_can_grant_organization_access_via_api(client, session):
    admin = await _create_user(session, "acl-grant-admin@example.com", "Grant Admin")
    owner = await _create_user(session, "acl-grant-owner@example.com", "Grant Owner")
    org_member = await _create_user(session, "acl-grant-member@example.com", "Grant Member")
    admin.role = "admin"
    await session.commit()

    _login(client, admin)
    response = await client.post("/api/projects/admin/organizations", json={"name": "Granted Team"})
    assert response.status_code == 201
    organization_id = response.json()["id"]
    response = await client.post(
        f"/api/projects/admin/organizations/{organization_id}/members",
        json={"email": org_member.email, "role": "member"},
    )
    assert response.status_code == 201

    project_id = await _create_project(client, owner, name="Org Grant API")
    response = await client.post(
        f"/api/projects/{project_id}/organization-grants",
        json={"organization_id": organization_id, "role": "viewer"},
    )
    assert response.status_code == 201
    grant = response.json()
    assert grant["organization_name"] == "Granted Team"
    assert grant["role"] == "viewer"

    _login(client, org_member)
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["access_role"] == "viewer"
    response = await client.patch(f"/api/projects/{project_id}", json={"description": "blocked"})
    assert response.status_code == 404

    _login(client, owner)
    response = await client.patch(
        f"/api/projects/{project_id}/organization-grants/{grant['id']}",
        json={"role": "editor"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "editor"

    _login(client, org_member)
    response = await client.patch(f"/api/projects/{project_id}", json={"description": "allowed"})
    assert response.status_code == 200
    assert response.json()["description"] == "allowed"

    _login(client, owner)
    response = await client.delete(f"/api/projects/{project_id}/organization-grants/{grant['id']}")
    assert response.status_code == 204

    _login(client, org_member)
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 404


async def test_non_owner_cannot_manage_project_organization_grants(client, session):
    admin = await _create_user(session, "acl-grant-admin-block@example.com", "Grant Admin")
    owner = await _create_user(session, "acl-grant-owner-block@example.com", "Grant Owner")
    editor = await _create_user(session, "acl-grant-editor-block@example.com", "Grant Editor")
    admin.role = "admin"
    await session.commit()

    _login(client, admin)
    response = await client.post("/api/projects/admin/organizations", json={"name": "Blocked Team"})
    assert response.status_code == 201
    organization_id = response.json()["id"]

    project_id = await _create_project(client, owner, name="Grant Boundary")
    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": editor.email, "role": "editor"},
    )
    assert response.status_code == 201

    _login(client, editor)
    response = await client.post(
        f"/api/projects/{project_id}/organization-grants",
        json={"organization_id": organization_id, "role": "viewer"},
    )
    assert response.status_code == 404


async def test_admin_can_grant_organization_access_to_any_project(client, session):
    admin = await _create_user(session, "acl-admin-global-grant@example.com", "Global Admin")
    owner = await _create_user(session, "acl-admin-grant-owner@example.com", "Project Owner")
    org_member = await _create_user(session, "acl-admin-grant-member@example.com", "Org Member")
    admin.role = "admin"
    await session.commit()

    project_id = await _create_project(client, owner, name="Admin Grant Project")

    _login(client, admin)
    response = await client.post("/api/projects/admin/organizations", json={"name": "Admin Granted Team"})
    assert response.status_code == 201
    organization_id = response.json()["id"]
    response = await client.post(
        f"/api/projects/admin/organizations/{organization_id}/members",
        json={"email": org_member.email, "role": "member"},
    )
    assert response.status_code == 201

    response = await client.post(
        f"/api/projects/{project_id}/organization-grants",
        json={"organization_id": organization_id, "role": "viewer"},
    )
    assert response.status_code == 201
    assert response.json()["project_id"] == project_id

    _login(client, org_member)
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["access_role"] == "viewer"


async def test_non_member_cannot_discover_project(client, session):
    owner = await _create_user(session, "acl-owner-private@example.com")
    intruder = await _create_user(session, "acl-intruder@example.com")
    await session.commit()
    project_id = await _create_project(client, owner, name="Private Project")

    _login(client, intruder)
    response = await client.get("/api/projects")
    assert response.status_code == 200
    assert all(item["id"] != project_id for item in response.json())

    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 404

    response = await client.get(f"/api/projects/{project_id}/batch-jobs")
    assert response.status_code == 404


async def test_chat_project_binding_requires_write_access(client, session, monkeypatch):
    from app.api import chat as chat_api

    owner = await _create_user(session, "acl-chat-owner@example.com")
    viewer = await _create_user(session, "acl-chat-viewer@example.com")
    editor = await _create_user(session, "acl-chat-editor@example.com")
    await session.commit()
    project_id = await _create_project(client, owner, name="Chat ACL")

    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": viewer.email, "role": "viewer"},
    )
    assert response.status_code == 201
    response = await client.post(
        f"/api/projects/{project_id}/members",
        json={"email": editor.email, "role": "editor"},
    )
    assert response.status_code == 201

    called = False

    async def fake_stream_chat(*args, **kwargs):
        nonlocal called
        called = True
        yield json.dumps({"type": "done"}, ensure_ascii=False)

    async def fake_finalize_chat_response(*args, **kwargs):
        return None

    monkeypatch.setattr(chat_api.orchestrator, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(chat_api, "_finalize_chat_response", fake_finalize_chat_response)

    _login(client, viewer)
    response = await client.post(
        "/api/chat/stream",
        json={"message": "viewer should not bind", "project_id": project_id},
    )
    assert response.status_code == 404
    assert called is False

    _login(client, editor)
    response = await client.post(
        "/api/chat/stream",
        json={"message": "editor can bind", "project_id": project_id},
    )
    assert response.status_code == 200
    assert called is True
