from pathlib import Path

from app.services.remediation_readiness import collect_remediation_readiness


def test_remediation_readiness_is_explicitly_operator_gated():
    result = collect_remediation_readiness(Path(__file__).resolve().parents[2])

    assert result["schema_version"] == "remediation-readiness-v1"
    assert result["status"] == "ready_for_operator"
    assert "operator_approval_required" in result["blockers"]
    assert result["tool_baseline"]["catalog_tool_count"] >= 55
    assert result["operator_actions"]
