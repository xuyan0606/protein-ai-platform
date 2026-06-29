"""Tests for publish workflow: report generation + publish service + API."""

from __future__ import annotations

import os
os.environ["USE_SQLITE"] = "true"

import pytest
from unittest.mock import AsyncMock, patch


class TestReportGenerator:
    """Tests for Markdown report generation."""

    def test_basic_report(self):
        from app.services.report_generator import ReportGenerator
        gen = ReportGenerator()
        md = gen.generate_conversation_report(
            project_name="TestProject",
            conversation_title="LipA Analysis",
            user_message="Analyze LipA pH",
            research_notes="Lipase family GH1...",
            plan=[{"tool_name": "predict_properties", "status": "completed", "description": "MW/pI", "duration": 0.3}],
            tool_results=[{"tool_name": "predict_properties", "status": "completed", "result": {"mw": 35.2}}],
            final_report="## Findings\nLipA optimal pH is 8.0",
            citations=[{"pmid": "12345", "title": "Lipase eng", "authors": ["Smith J", "Doe A"], "year": 2024}],
            tags=["pH", "lipase"],
        )
        assert "TestProject" in md
        assert "LipA Analysis" in md
        assert "predict_properties" in md
        assert "PMID:12345" in md
        assert "Smith J et al." in md
        assert md.startswith("---\n")  # YAML front matter

    def test_report_empty_sections(self):
        from app.services.report_generator import ReportGenerator
        gen = ReportGenerator()
        md = gen.generate_conversation_report(
            project_name="Empty",
            conversation_title="Test",
            user_message="test",
            research_notes="",
            plan=[],
            tool_results=[],
            final_report="Simple report",
        )
        assert "Simple report" in md
        assert "参考文献" not in md  # no citations

    def test_batch_summary(self):
        from app.services.report_generator import ReportGenerator
        gen = ReportGenerator()
        md = gen.generate_batch_summary(
            project_name="BatchProject",
            batch_id="b001",
            tool_name="predict_properties",
            sequences=[{"name": "seq1", "sequence": "MKTEWFLCVLAG"}, {"name": "seq2", "sequence": "ACDEFGHIK"}],
            results=[{"mw": 1.5}, {"mw": 1.2}],
        )
        assert "BatchProject" in md
        assert "seq1" in md
        assert "seq2" in md
        assert "predict_properties" in md


class TestPublishServiceUtils:
    """Tests for publish service helper functions."""

    def test_safe_filename_chinese(self):
        from app.services.publish_service import _safe_filename
        assert _safe_filename("脂肪酶pH改造分析报告") == "脂肪酶pH改造分析报告"

    def test_safe_filename_special_chars(self):
        from app.services.publish_service import _safe_filename
        result = _safe_filename("Report: Test/With\\Special <chars>")
        assert "/" not in result
        assert "\\" not in result
        assert "<" not in result

    def test_safe_filename_long(self):
        from app.services.publish_service import _safe_filename
        long_title = "A" * 200
        result = _safe_filename(long_title)
        assert len(result) <= 80

    def test_safe_filename_empty(self):
        from app.services.publish_service import _safe_filename
        result = _safe_filename("!!!")
        assert result == "report"  # fallback


class TestProjectFileModel:
    """Tests for ProjectFile model."""

    def test_model_fields(self):
        from app.models.project import ProjectFile
        columns = {c.name for c in ProjectFile.__table__.columns}
        expected = {
            "id", "project_id", "filename", "object_name", "file_type",
            "file_size", "content_hash", "source", "conversation_id",
            "outline_doc_id", "tags", "created_at", "updated_at",
        }
        assert expected == columns

    def test_conversation_project_id(self):
        from app.models.conversation import Conversation
        assert "project_id" in {c.name for c in Conversation.__table__.columns}
        # Should be nullable (optional association)
        col = Conversation.__table__.columns["project_id"]
        assert col.nullable is True

    def test_project_wiki_fields(self):
        from app.models.project import Project
        columns = {c.name for c in Project.__table__.columns}
        assert "outline_collection_id" in columns
        assert "outline_root_doc_id" in columns
        assert "wiki_auto_publish" in columns


class TestProjectWikiInit:
    """Tests for project creation with auto-wiki initialization."""

    def test_overview_template(self):
        """Test the project overview Markdown template."""
        from app.api.projects import _project_overview_template
        from app.models.project import Project

        project = Project(id="test123", name="脂肪酶改造", description="测试项目描述")
        md = _project_overview_template(project)
        assert "# 脂肪酶改造" in md
        assert "测试项目描述" in md
        assert "分析报告" in md
        assert "批量结果" in md

    def test_overview_template_no_description(self):
        from app.api.projects import _project_overview_template
        from app.models.project import Project

        project = Project(id="test456", name="NoDesc", description=None)
        md = _project_overview_template(project)
        assert "暂无描述" in md

    @pytest.mark.asyncio
    async def test_init_wiki_outline_unavailable(self):
        """When Outline is down, project should still be created (graceful degradation)."""
        from app.api.projects import _init_project_wiki
        from app.models.project import Project

        project = Project(id="test789", name="Test", description="desc", wiki_auto_publish=True)

        # Mock a fake async session
        session = AsyncMock()

        with patch("app.services.outline_client.get_outline_client", side_effect=Exception("Outline down")):
            # Should NOT raise — graceful degradation
            await _init_project_wiki(project, session)

        # Wiki fields should remain None
        assert project.outline_collection_id is None
        assert project.outline_root_doc_id is None

    @pytest.mark.asyncio
    async def test_init_wiki_success(self):
        """When Outline is available, wiki fields should be populated."""
        from app.api.projects import _init_project_wiki
        from app.models.project import Project

        project = Project(id="testwiki", name="WikiProject", description="test", wiki_auto_publish=True)
        session = AsyncMock()

        mock_client = AsyncMock()
        mock_client.create_collection.return_value = {"id": "col_123"}
        mock_client.create_document.return_value = {"id": "doc_456"}

        with patch("app.services.outline_client.get_outline_client", return_value=mock_client):
            await _init_project_wiki(project, session)

        assert project.outline_collection_id == "col_123"
        assert project.outline_root_doc_id == "doc_456"
        mock_client.create_collection.assert_called_once()
        mock_client.create_document.assert_called_once()


class TestChatAutoPublish:
    """Tests for the chat auto-publish flow."""

    @pytest.mark.asyncio
    async def test_auto_publish_no_project(self):
        """Auto-publish should skip when conversation has no project_id."""
        from app.api.chat import _auto_publish_wiki
        from app.models.conversation import Conversation

        conv = Conversation(id=1, user_id=1, project_id=None, title="Test")
        result = await _auto_publish_wiki(None, conv, "test message", ["response"])
        assert result is None

    @pytest.mark.asyncio
    async def test_auto_publish_no_final_report(self):
        """Auto-publish should skip when agent produced no final_report."""
        from app.api.chat import _auto_publish_wiki
        from app.models.conversation import Conversation
        from unittest.mock import MagicMock

        conv = Conversation(id=1, user_id=1, project_id="proj1", title="Test")

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_snapshot_data.return_value = {
            "stage": "done",
            "final_report": "",
            "research_notes": "",
            "plan": [],
            "step_results": [],
        }

        # Mock DB session to return a project with wiki_auto_publish=True
        from app.models.project import Project
        mock_project = Project(id="proj1", name="Test", wiki_auto_publish=True)

        with patch("app.core.database._async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = AsyncMock(return_value=mock_project)
            mock_factory.return_value = mock_session

            result = await _auto_publish_wiki(mock_orchestrator, conv, "test", ["resp"])

        assert result is None  # No final_report → skip

    @pytest.mark.asyncio
    async def test_auto_publish_wiki_disabled(self):
        """Auto-publish should skip when project wiki_auto_publish is False."""
        from app.api.chat import _auto_publish_wiki
        from app.models.conversation import Conversation
        from app.models.project import Project
        from unittest.mock import MagicMock

        conv = Conversation(id=1, user_id=1, project_id="proj1", title="Test")

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_snapshot_data.return_value = {
            "stage": "done",
            "final_report": "Some report content",
            "research_notes": "Research",
            "plan": [],
            "step_results": [],
        }

        mock_project = Project(id="proj1", name="Test", wiki_auto_publish=False)

        with patch("app.core.database._async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = AsyncMock(return_value=mock_project)
            mock_factory.return_value = mock_session

            result = await _auto_publish_wiki(mock_orchestrator, conv, "test", ["resp"])

        assert result is None  # wiki disabled → skip


class TestAlembicMigration:
    """Verify migration files exist and are properly structured."""

    def test_wiki_migration_exists(self):
        import pathlib
        migration_file = pathlib.Path(__file__).parent.parent / "alembic" / "versions" / "a3f7c9e2b1d4_add_wiki_knowledgebase_schema.py"
        assert migration_file.exists(), f"Migration file not found: {migration_file}"
        content = migration_file.read_text()
        assert 'revision: str = "a3f7c9e2b1d4"' in content
        assert 'down_revision: Union[str, None] = "8eb683a67e73"' in content
        assert "def upgrade" in content
        assert "def downgrade" in content
        assert "project_files" in content
        assert "conversations" in content
        assert "outline_collection_id" in content

    def test_chat_request_has_project_id(self):
        """ChatRequest schema should accept project_id."""
        from app.api.chat import ChatRequest
        req = ChatRequest(message="test", project_id="abc123")
        assert req.project_id == "abc123"

    def test_project_create_has_wiki_auto_publish(self):
        """ProjectCreate schema should accept wiki_auto_publish."""
        from app.api.projects import ProjectCreate
        body = ProjectCreate(name="Test", wiki_auto_publish=True)
        assert body.wiki_auto_publish is True
        # Default should be True
        body2 = ProjectCreate(name="Test")
        assert body2.wiki_auto_publish is True
