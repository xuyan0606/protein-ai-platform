import pytest

import app.tools.kwb_enzyme_designer as designer
from app.tools.registry import ToolRegistry


def test_production_model_tool_is_registered():
    tool = ToolRegistry.get_tool("kwb_enzyme_designer")
    assert tool is not None
    assert tool.parameters["required"] == ["sequence", "engineering_goal"]


def test_production_model_tool_fails_closed_without_gate():
    result = designer.kwb_enzyme_designer(sequence="ACDEFGHIKLMNPQRSTVWY", engineering_goal="activity")
    assert result["status"] == "blocked_pending_production_gate"
    assert result["capability_status"] == "production_model_gate"
    assert result["production_ready"] is False
    assert result["candidates"] == []
    assert result["input_sha256"]
    assert result["failure_reason"]
    assert result["runtime"]["inference_executed"] is False


def test_production_model_tool_rejects_invalid_sequence():
    with pytest.raises(ValueError, match="sequence"):
        designer.kwb_enzyme_designer(sequence="ACD123", engineering_goal="activity")


def test_gate_pass_without_validated_package_stays_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(designer, "PRODUCTION_GATE_REPORT", tmp_path / "gate.json")
    monkeypatch.setattr(designer, "MODEL_PACKAGE_MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(designer, "MODEL_PACKAGE_VALIDATION", tmp_path / "validation.json")
    (tmp_path / "gate.json").write_text('{"production_ready": true}')
    (tmp_path / "manifest.json").write_text('{"status": "validated", "inference_entrypoint": "inference.py"}')
    (tmp_path / "validation.json").write_text('{"status": "blocked_invalid", "production_model_artifact": false}')
    result = designer.kwb_enzyme_designer(sequence="ACDEFGHIKLMNPQRSTVWY", engineering_goal="activity")
    assert result["status"] == "blocked_missing_model_package"
    assert result["runtime"]["inference_executed"] is False
