import json
from pathlib import Path

from build_general_enzyme_dataset_manifest import build_manifest


def test_manifest_stays_blocked_when_audit_has_errors(tmp_path: Path):
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"status": "blocked_quality_check", "training_import_allowed": False}), encoding="utf-8")
    result = build_manifest(audit)
    assert result["status"] == "blocked"
    assert result["training_import_allowed"] is False


def test_manifest_records_research_scope(tmp_path: Path):
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"status": "passed", "training_import_allowed": True, "row_count": 10}), encoding="utf-8")
    result = build_manifest(audit)
    assert result["execution_scope"] == "research_only"
    assert result["production_registration"] == "forbidden"
