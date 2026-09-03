"""Tests for publish workflow: report generation + publish service + API."""

from __future__ import annotations

import os
os.environ["USE_SQLITE"] = "true"

import json
import pytest
from unittest.mock import AsyncMock, patch


class TestReportGenerator:
    """Tests for Markdown report generation."""

    @staticmethod
    def _json_block(md: str, heading: str) -> dict | list:
        text = md.split(f"{heading}\n\n```json\n", 1)[1].split("\n```", 1)[0]
        return json.loads(text)

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

    def test_structured_enzyme_report_is_not_wrapped_by_generic_sections(self):
        from app.services.report_generator import ReportGenerator

        gen = ReportGenerator()
        final_report = "\n".join([
            "# 酶蛋白工程分析报告",
            "",
            "## 任务理解",
            "- 用户目标：提高比活力",
            "",
            "## 输入与结构证据",
            "- 已解析上传结构。",
            "",
            "## 探索性验证建议",
            "- 当前不可直接下单。",
        ])
        md = gen.generate_conversation_report(
            project_name="EnzymeProject",
            conversation_title="HM.pdb 深度分析",
            user_message="提高蛋白比活力",
            research_notes="内部研究背景",
            plan=[{"tool_name": "predict_properties", "status": "completed", "description": "MW/pI", "duration": 0.1}],
            tool_results=[{"tool_name": "predict_properties", "status": "completed", "result": {"mw": 32.7}}],
            final_report=final_report,
        )

        assert "# 酶蛋白工程分析报告" in md
        assert "## 用户提问" not in md
        assert "## 分析报告" not in md
        assert md.index("## 任务理解") < md.index("## 输入与结构证据")
        assert "## 附录：发布与原始执行信息" in md
        assert "### 分析管线" in md

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

    def test_report_includes_evidence_source_status_table(self):
        from app.services.report_generator import ReportGenerator
        gen = ReportGenerator()
        md = gen.generate_conversation_report(
            project_name="EvidenceProject",
            conversation_title="Live evidence",
            user_message="查 UniProt 和 InterPro",
            research_notes="",
            plan=[],
            tool_results=[
                {
                    "tool_name": "sequence_search",
                    "status": "completed",
                    "result": {
                        "status": "completed",
                        "evidence_source": {
                            "source": "UniProt REST",
                            "status": "live",
                            "mode": "uniprotkb_search_rest",
                            "live_query_executed": True,
                        },
                    },
                },
                {
                    "tool_name": "annotation_bundle",
                    "status": "completed",
                    "result": {
                        "evidence_source": {
                            "source": "annotation_bundle",
                            "status": "degraded",
                            "mode": "local_database_or_heuristic_bundle",
                            "live_query_executed": False,
                            "reason": "No live InterPro query.",
                        },
                        "interpro": {
                            "evidence_source": {
                                "source": "InterPro",
                                "status": "degraded",
                                "mode": "local_import_or_heuristic",
                                "live_query_executed": False,
                            }
                        },
                    },
                },
            ],
            final_report="只允许 live 证据写成已联网。",
        )

        assert "## 联网/证据源状态" in md
        assert "| sequence_search | - | live | uniprotkb_search_rest | 是 | UniProt REST |" in md
        assert "| annotation_bundle | - | degraded | local_database_or_heuristic_bundle | 否 | annotation_bundle | No live InterPro query. |" in md
        assert "| annotation_bundle | interpro | degraded | local_import_or_heuristic | 否 | InterPro |" in md

        manifest_text = md.split("## Evidence Manifest\n\n```json\n", 1)[1].split("\n```", 1)[0]
        manifest = json.loads(manifest_text)
        assert manifest == [
            {
                "tool": "sequence_search",
                "subsource": "-",
                "status": "live",
                "mode": "uniprotkb_search_rest",
                "source": "UniProt REST",
                "endpoint": "",
                "checked_at": "",
                "reason": "",
            },
            {
                "tool": "annotation_bundle",
                "subsource": "-",
                "status": "degraded",
                "mode": "local_database_or_heuristic_bundle",
                "source": "annotation_bundle",
                "endpoint": "",
                "checked_at": "",
                "reason": "No live InterPro query.",
            },
            {
                "tool": "annotation_bundle",
                "subsource": "interpro",
                "status": "degraded",
                "mode": "local_import_or_heuristic",
                "source": "InterPro",
                "endpoint": "",
                "checked_at": "",
                "reason": "",
            },
        ]

    def test_report_includes_platform_data_manifest_from_live_manifest(self, tmp_path, monkeypatch):
        from app.services import platform_manifest
        from app.services.report_generator import ReportGenerator

        deploy_root = tmp_path / "deploy_data"
        deploy_root.mkdir()
        (deploy_root / "live_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "data_version": "2026-08-04-demo",
                    "updated_at": "2026-08-04T08:00:00Z",
                    "mode": "plan_only_seed",
                    "expected_datasets": {
                        "pdb": {
                            "source": "RCSB PDB",
                            "version": "2026-08",
                            "checksum": "sha256:pdb",
                        },
                        "annotations": {
                            "source": "UniProt/InterPro",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(platform_manifest.settings, "DEPLOY_DATA_ROOT", str(deploy_root))

        md = ReportGenerator().generate_conversation_report(
            project_name="ManifestProject",
            conversation_title="Version lock",
            user_message="生成报告",
            research_notes="",
            plan=[],
            tool_results=[],
            final_report="报告正文",
        )

        manifest = self._json_block(md, "## Platform/Data Manifest")
        assert manifest == {
            "status": "snapshot",
            "snapshot_scope": "version_and_source_snapshot_only",
            "readiness": "not_asserted",
            "app": {
                "name": "Protein AI Platform",
                "version": "0.1.0",
            },
            "deploy_data_root": str(deploy_root),
            "live_manifest": {
                "path": str(deploy_root / "live_manifest.json"),
                "status": "present",
                "schema_version": 2,
                "data_version": "2026-08-04-demo",
                "updated_at": "2026-08-04T08:00:00Z",
                "mode": "plan_only_seed",
            },
            "expected_datasets": {
                "annotations": {
                    "source": "UniProt/InterPro",
                    "version": "",
                    "checksum": "",
                },
                "pdb": {
                    "source": "RCSB PDB",
                    "version": "2026-08",
                    "checksum": "sha256:pdb",
                },
            },
            "notes": [
                "Manifest records configured versions and sources only; it is not a data-integrity or live-readiness assertion."
            ],
        }

    def test_report_degrades_when_platform_manifest_missing(self, tmp_path, monkeypatch):
        from app.services import platform_manifest
        from app.services.report_generator import ReportGenerator

        deploy_root = tmp_path / "deploy_data"
        deploy_root.mkdir()
        monkeypatch.setattr(platform_manifest.settings, "DEPLOY_DATA_ROOT", str(deploy_root))

        md = ReportGenerator().generate_conversation_report(
            project_name="ManifestProject",
            conversation_title="Missing manifest",
            user_message="生成报告",
            research_notes="",
            plan=[],
            tool_results=[],
            final_report="报告正文仍应生成。",
        )

        manifest = self._json_block(md, "## Platform/Data Manifest")
        assert "报告正文仍应生成。" in md
        assert manifest["status"] == "degraded"
        assert manifest["readiness"] == "not_asserted"
        assert manifest["live_manifest"]["status"] == "missing"
        assert manifest["live_manifest"]["schema_version"] == ""
        assert manifest["expected_datasets"] == {}
        assert "live_manifest.json is missing" in manifest["notes"][0]

    def test_report_includes_literature_live_search_results(self):
        from app.services.report_generator import ReportGenerator

        md = ReportGenerator().generate_conversation_report(
            project_name="LiteratureProject",
            conversation_title="Live literature",
            user_message="查找脂肪酶热稳定性文献",
            research_notes="",
            plan=[],
            tool_results=[
                {
                    "tool_name": "literature_live_search",
                    "status": "completed",
                    "result": {
                        "evidence_source": {
                            "source": "PubMed E-utilities; Crossref REST",
                            "status": "live",
                            "mode": "pubmed_crossref_rest",
                            "endpoint": "https://eutils.ncbi.nlm.nih.gov; https://api.crossref.org",
                            "checked_at": "2026-08-04T00:00:00+00:00",
                        },
                        "results": [
                            {
                                "source": "pubmed",
                                "pmid": "12345",
                                "doi": "10.1000/demo",
                                "title": "Lipase thermostability demo",
                                "published": "2025",
                            },
                            {
                                "source": "crossref",
                                "doi": "10.1000/other",
                                "title": "Crossref enzyme paper",
                                "published": "2024",
                            },
                        ],
                    },
                }
            ],
            final_report="文献结果应以结构化证据呈现。",
        )

        assert "## 参考文献" in md
        assert "### 联网文献证据" in md
        assert "| # | PMID | DOI | 标题 | 来源 | 发表时间 |" in md
        assert "|---|---|---|---|---|---|" in md
        assert "| 1 | 12345 | 10.1000/demo | Lipase thermostability demo | pubmed | 2025 |" in md
        assert "| 2 | - | 10.1000/other | Crossref enzyme paper | crossref | 2024 |" in md

    def test_citation_manifest_deduplicates_citations_and_live_literature(self):
        from app.services.report_generator import ReportGenerator

        md = ReportGenerator().generate_conversation_report(
            project_name="CitationProject",
            conversation_title="Citation export",
            user_message="导出引用",
            research_notes="",
            plan=[],
            tool_results=[
                {
                    "tool_name": "literature_live_search",
                    "status": "completed",
                    "result": {
                        "results": [
                            {
                                "source": "pubmed",
                                "pmid": "111",
                                "doi": "10.1000/demo",
                                "title": "Duplicate DOI should merge",
                                "published": "2025",
                                "url": "https://pubmed.ncbi.nlm.nih.gov/111/",
                            },
                            {
                                "source": "crossref",
                                "doi": "10.2000/unique",
                                "title": "Unique Crossref paper",
                                "published": "2024-01-01",
                                "url": "https://doi.org/10.2000/unique",
                            },
                        ]
                    },
                }
            ],
            final_report="引用清单应结构化导出。",
            citations=[
                {
                    "pmid": "111",
                    "doi": "10.1000/DEMO",
                    "title": "Manual citation title wins",
                    "source": "manual",
                    "year": 2025,
                }
            ],
        )

        manifest = self._json_block(md, "### Citation Manifest")
        assert manifest == [
            {
                "PMID": "111",
                "DOI": "10.1000/demo",
                "title": "Manual citation title wins",
                "source": "manual",
                "year": "2025",
                "url": "https://pubmed.ncbi.nlm.nih.gov/111/",
                "evidence_tool": ["citations", "literature_live_search"],
            },
            {
                "PMID": "",
                "DOI": "10.2000/unique",
                "title": "Unique Crossref paper",
                "source": "crossref",
                "year": "2024",
                "url": "https://doi.org/10.2000/unique",
                "evidence_tool": ["literature_live_search"],
            },
        ]
        assert "### 联网文献证据" in md
        assert "| 1 | 111 | 10.1000/demo | Duplicate DOI should merge | pubmed | 2025 |" in md
        assert "| 2 | - | 10.2000/unique | Unique Crossref paper | crossref | 2024-01-01 |" in md

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

    @pytest.mark.asyncio
    async def test_publish_report_blocks_invalid_structured_enzyme_report_before_db_access(self):
        from app.services.publish_service import ReportQualityGateError, publish_report

        class FailingDB:
            async def get(self, *args, **kwargs):
                raise AssertionError("publish gate should run before DB access")

        invalid_report = "\n".join([
            "# 酶蛋白工程分析报告",
            "",
            "## 任务理解",
            "- 用户目标：提高比活力",
            "",
            "## Objective Module Gate",
            "- 状态：blocked",
            "",
            "## 结论卡片 / 状态摘要",
            "- 旧版结构不允许发布。",
        ])

        with pytest.raises(ReportQualityGateError) as exc:
            await publish_report(
                FailingDB(),
                project_id="proj1",
                title="HM.pdb 分析",
                content=invalid_report,
            )

        message = str(exc.value)
        assert "报告质量门槛未通过" in message
        assert "missing ordered heading: ## 输入与结构证据" in message
        assert "forbidden text present: ## 结论卡片 / 状态摘要" in message

    @pytest.mark.asyncio
    async def test_publish_report_quality_gate_ignores_generic_markdown(self):
        from app.services.publish_service import publish_report

        class FailingDB:
            async def get(self, *args, **kwargs):
                raise ValueError("Project proj1 not found")

        with pytest.raises(ValueError, match="Project proj1 not found"):
            await publish_report(
                FailingDB(),
                project_id="proj1",
                title="普通报告",
                content="# 普通报告\n\n## 用户提问\n\n检索文献",
            )


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
