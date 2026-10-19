from app.core.security import create_access_token
from app.models.conversation import Conversation
from app.models.project import Project, ProjectFile, ProjectMember
from app.models.user import User
from app.services.strategy_checkpoint import get_active_strategy_checkpoint, persist_strategy_checkpoint


async def _create_user(session, email: str = "publish@example.com") -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name="Publish User",
    )
    session.add(user)
    await session.flush()
    return user


async def test_collection_publish_creates_auto_workspace_and_returns_result(client, session, monkeypatch):
    from app.api import publish as publish_api

    user = await _create_user(session)
    await session.commit()

    token = create_access_token(user.id)
    captured: dict = {}

    async def fake_publish_report(
        db,
        *,
        project_id,
        title,
        content,
        conversation_id=None,
        tags=None,
        collection_id=None,
        parent_document_id=None,
        source="manual",
    ):
        captured.update(
            {
                "project_id": project_id,
                "title": title,
                "content": content,
                "conversation_id": conversation_id,
                "collection_id": collection_id,
                "parent_document_id": parent_document_id,
                "source": source,
            }
        )
        return {
            "file_id": "file-1",
            "filename": "report.md",
            "object_name": "projects/auto/report.md",
            "outline_doc_id": "doc-1",
            "wiki_url": "/wiki/doc/doc-1",
            "file_size": 128,
        }

    monkeypatch.setattr(publish_api.publish_service, "publish_report", fake_publish_report)

    response = await client.post(
        "/api/wiki/publish",
        json={
            "title": "测试报告",
            "content": "# Report\n\nbody",
            "collection_id": "collection-123",
            "parent_document_id": "parent-456",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == "file-1"
    assert body["outline_doc_id"] == "doc-1"
    assert captured["collection_id"] == "collection-123"
    assert captured["parent_document_id"] == "parent-456"
    assert captured["source"] == "manual"
    assert captured["project_id"]


async def test_collection_publish_preserves_active_strategy_checkpoint(client, session, monkeypatch):
    from app.api import publish as publish_api

    user = await _create_user(session, "publish-checkpoint@example.com")
    conversation = Conversation(user_id=user.id, title="checkpoint publish")
    session.add(conversation)
    await session.flush()
    await persist_strategy_checkpoint(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        project_id=None,
        task_text="提高这个酶的比活力 MKTAYIAKQRQISFVKSHFSRQ",
        task_fingerprint="task-wiki-publish-1",
        strategy_signature="sig-wiki-publish-1",
        plan_payload=[{
            "id": 1,
            "tool_name": "predict_properties",
            "description": "Check properties",
            "params": {"sequence": "MKTAYIAKQRQISFVKSHFSRQ"},
            "status": "pending",
        }],
    )
    await session.commit()

    async def fake_publish_report(
        db,
        *,
        project_id,
        title,
        content,
        conversation_id=None,
        tags=None,
        collection_id=None,
        parent_document_id=None,
        source="manual",
    ):
        assert conversation_id == conversation.id
        return {
            "file_id": "file-checkpoint",
            "filename": "checkpoint.md",
            "object_name": "projects/wiki/checkpoint.md",
            "outline_doc_id": "doc-checkpoint",
            "wiki_url": "/wiki/doc/doc-checkpoint",
            "file_size": len(content),
        }

    monkeypatch.setattr(publish_api.publish_service, "publish_report", fake_publish_report)
    token = create_access_token(user.id)

    response = await client.post(
        "/api/wiki/publish",
        json={
            "title": "checkpoint survives publish",
            "content": "# Checkpoint\n\nbody",
            "conversation_id": conversation.id,
            "collection_id": "collection-checkpoint",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    active = await get_active_strategy_checkpoint(session, user_id=user.id, conversation_id=conversation.id)
    assert active is not None
    assert active["status"] == "awaiting_confirmation"
    assert active["strategy_signature"] == "sig-wiki-publish-1"
    assert active["task_fingerprint"] == "task-wiki-publish-1"


async def test_collection_publish_requires_collection_id(client, session):
    response = await client.post(
        "/api/wiki/publish",
        json={
            "title": "测试报告",
            "content": "# Report\n\nbody",
        },
    )

    assert response.status_code == 401


async def test_wiki_collection_auth_failure_is_actionable(client, session, monkeypatch):
    from app.api import publish as publish_api
    from app.services.outline_client import OutlineAuthenticationError

    user = await _create_user(session, "wiki-auth-failure@example.com")
    await session.commit()

    class FakeOutlineClient:
        async def list_collections(self):
            raise OutlineAuthenticationError("expired")

    monkeypatch.setattr("app.services.outline_client.get_outline_client", lambda: FakeOutlineClient())
    token = create_access_token(user.id)
    response = await client.get("/api/wiki/collections", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 503
    assert "认证已失效" in response.json()["detail"]


async def test_wiki_publish_auth_failure_is_actionable(client, session, monkeypatch):
    from app.api import publish as publish_api
    from app.services.outline_client import OutlineAuthenticationError

    user = await _create_user(session, "wiki-publish-auth-failure@example.com")
    await session.commit()

    async def reject_publish(*_args, **_kwargs):
        raise OutlineAuthenticationError("expired")

    monkeypatch.setattr(publish_api.publish_service, "publish_report", reject_publish)
    token = create_access_token(user.id)
    response = await client.post(
        "/api/wiki/publish",
        json={"title": "Test", "content": "# Test", "collection_id": "collection-1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert "认证已失效" in response.json()["detail"]


async def test_shared_project_viewer_can_list_files_but_cannot_write(client, session, monkeypatch):
    from app.api import publish as publish_api

    owner = await _create_user(session, "publish-owner@example.com")
    viewer = await _create_user(session, "publish-viewer@example.com")
    project = Project(name="Shared Files", user_id=owner.id)
    session.add(project)
    await session.flush()
    file_record = ProjectFile(
        project_id=project.id,
        filename="report.md",
        object_name="projects/shared/report.md",
        file_type="md",
        file_size=12,
        source="manual",
    )
    session.add(file_record)
    session.add(ProjectMember(project_id=project.id, user_id=viewer.id, role="viewer"))
    await session.commit()
    client.cookies.set("pa_token", create_access_token(viewer.id))

    response = await client.get(f"/api/projects/{project.id}/files")
    assert response.status_code == 200
    assert response.json()[0]["filename"] == "report.md"

    response = await client.delete(f"/api/projects/{project.id}/files/{file_record.id}")
    assert response.status_code == 404

    called = False

    async def fake_publish_report(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(publish_api.publish_service, "publish_report", fake_publish_report)

    response = await client.post(
        f"/api/projects/{project.id}/publish",
        json={"title": "Blocked", "content": "# blocked"},
    )
    assert response.status_code == 404
    assert called is False


async def test_shared_project_editor_can_publish(client, session, monkeypatch):
    from app.api import publish as publish_api

    owner = await _create_user(session, "publish-editor-owner@example.com")
    editor = await _create_user(session, "publish-editor@example.com")
    project = Project(name="Editor Publish", user_id=owner.id)
    session.add(project)
    await session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=editor.id, role="editor"))
    await session.commit()
    client.cookies.set("pa_token", create_access_token(editor.id))

    captured: dict = {}

    async def fake_publish_report(
        db,
        *,
        project_id,
        title,
        content,
        conversation_id=None,
        tags=None,
        collection_id=None,
        parent_document_id=None,
        source="manual",
    ):
        captured.update({"project_id": project_id, "title": title, "source": source})
        return {
            "file_id": "file-editor",
            "filename": "editor.md",
            "object_name": "projects/editor/report.md",
            "outline_doc_id": None,
            "wiki_url": None,
            "file_size": len(content),
        }

    monkeypatch.setattr(publish_api.publish_service, "publish_report", fake_publish_report)

    response = await client.post(
        f"/api/projects/{project.id}/publish",
        json={"title": "Editor Report", "content": "# editor"},
    )

    assert response.status_code == 200
    assert response.json()["file_id"] == "file-editor"
    assert captured == {"project_id": project.id, "title": "Editor Report", "source": "manual"}


async def test_project_publish_returns_400_for_report_quality_gate(client, session, monkeypatch):
    from app.api import publish as publish_api
    from app.services.publish_service import ReportQualityGateError
    from app.services.report_quality_contract import ReportQualityViolation

    owner = await _create_user(session, "publish-quality-owner@example.com")
    project = Project(name="Quality Gate", user_id=owner.id)
    session.add(project)
    await session.commit()
    client.cookies.set("pa_token", create_access_token(owner.id))

    async def fake_publish_report(*args, **kwargs):
        raise ReportQualityGateError([
            ReportQualityViolation(
                code="missing_ordered_heading",
                message="missing ordered heading: ## 输入与结构证据",
            )
        ])

    monkeypatch.setattr(publish_api.publish_service, "publish_report", fake_publish_report)

    response = await client.post(
        f"/api/projects/{project.id}/publish",
        json={
            "title": "质量不合格报告",
            "content": "# 酶蛋白工程分析报告\n\n## 任务理解\n\n## Objective Module Gate",
        },
    )

    assert response.status_code == 400
    assert "报告质量门槛未通过" in response.json()["detail"]
    assert "## 输入与结构证据" in response.json()["detail"]


async def test_non_member_cannot_list_project_files(client, session):
    owner = await _create_user(session, "publish-private-owner@example.com")
    intruder = await _create_user(session, "publish-private-intruder@example.com")
    project = Project(name="Private Files", user_id=owner.id)
    session.add(project)
    await session.commit()
    client.cookies.set("pa_token", create_access_token(intruder.id))

    response = await client.get(f"/api/projects/{project.id}/files")

    assert response.status_code == 404
