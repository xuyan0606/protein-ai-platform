"""Regression tests for the read-only external research evidence tool."""

from app.tools.external_research_evidence import external_research_evidence
from app.tools.external_research_evidence import RESEARCH_EVIDENCE_SCOPES
from app.tools.registry import ToolRegistry


def test_external_research_evidence_is_registered_and_read_only():
    tool = ToolRegistry.get_tool("external_research_evidence")
    assert tool is not None
    assert tool.category == "governance"
    assert tool.annotations["read_only"] is True
    assert tool.annotations["training_eligible"] is False
    assert tool.annotations["release_ready"] is False
    assert tuple(tool.parameters["properties"]["scope"]["enum"]) == RESEARCH_EVIDENCE_SCOPES


def test_external_research_evidence_preserves_fail_closed_status():
    result = external_research_evidence()
    assert result["local_only"] is True
    assert result["read_only"] is True
    assert result["model_claim"]["safe_for_model_claim"] is False
    assert result["release"]["release_ready"] is False
    assert result["training"]["cleanroom_kinetics_candidate"]["training_import_written_rows"] == 0
    assert result["training"]["cleanroom_kinetics_candidate"]["training_eligible"] is False
    assert result["training"]["cleanroom_kinetics_candidate"]["validation_success"] is True
    assert "write_training_rows" in result["forbidden_side_effects"]


def test_external_research_evidence_scope_projection():
    result = external_research_evidence("release")
    assert result["scope"] == "release"
    assert result["normalized_result"]["release_ready"] is False


def test_external_research_evidence_exposes_human_target_blocked_sources():
    result = external_research_evidence("human_target")
    human_target = result["normalized_result"]
    assert result["scope"] == "human_target"
    assert human_target["source_runtime_validation_success"] is True
    assert human_target["ready_sources"] == 0
    assert human_target["blocked_sources"] == 7
    assert human_target["split_manifest_validation_success"] is True
    assert len(human_target["split_manifests"]) == 7
    assert human_target["sources"][0]["split_manifest_path"]
    assert human_target["unlock_checklist"]["validation_success"] is True
    assert human_target["unlock_checklist"]["checklist_rows"] == 7
    assert human_target["unlock_checklist"]["ready_to_unlock_rows"] == 0
    assert human_target["unlock_checklist"]["blocked_rows"] == 7
    assert len(human_target["unlock_checklist"]["rows"]) == 7
    assert human_target["unlock_checklist"]["rows"][0]["missing_steps"]
    assert human_target["safe_for_model_claim"] is False
    assert human_target["customer_ready"] is False
    assert human_target["release_ready"] is False
