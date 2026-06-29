"""Tests for publish workflow: report generation + publish service + API."""

from __future__ import annotations

import os
os.environ["USE_SQLITE"] = "true"

import pytest


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
