import hashlib
import json
from pathlib import Path

from app.services.model_artifact_registry import evaluate_production_gate, load_manifest
from app.tools.ph_opt_predict import ph_opt_predict


def test_model_manifest_requires_hash_and_held_out_validation(tmp_path: Path):
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"checkpoint")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        "name": "demo", "version": "1", "sha256": digest,
        "artifact_path": str(artifact), "task": "tm",
        "applicability_domain": {"species": "test"}, "metrics": {"rmse": 1.2},
        "units": "degC", "uncertainty_method": "ensemble",
        "validation": {"held_out": False}, "approved": False,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert load_manifest(path)["status"] == "blocked_missing_held_out_validation"
    manifest["validation"]["held_out"] = True
    manifest["approved"] = True
    manifest["production_evidence"] = {
        "row_level_conditions": "fixture rows",
        "unit_and_method": "degC / DSC",
        "license": "commercial redistribution grant",
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert load_manifest(path)["status"] == "ready"


def test_research_manifest_requires_explicit_research_scope(tmp_path: Path):
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"research")
    manifest = {
        "name": "research", "version": "1", "sha256": hashlib.sha256(b"research").hexdigest(),
        "artifact_path": str(artifact), "task": "km", "applicability_domain": "research",
        "metrics": {}, "units": "M", "uncertainty_method": "residual",
        "validation": {"held_out": True}, "approved": False, "execution_scope": "research_only",
    }
    path = tmp_path / "research.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert load_manifest(path)["status"] == "blocked_model_not_approved"
    assert load_manifest(path, allow_research=True)["status"] == "ready"


def test_research_manifest_does_not_bypass_production_scope(tmp_path: Path):
    artifact = tmp_path / "research.bin"
    artifact.write_bytes(b"research")
    manifest = {
        "name": "research", "version": "1", "sha256": hashlib.sha256(b"research").hexdigest(),
        "artifact_path": str(artifact), "task": "tm", "applicability_domain": "research",
        "metrics": {"rmse": 1.0}, "units": "degC", "uncertainty_method": "residual",
        "validation": {"held_out": True}, "approved": False,
        "execution_scope": "research_only",
    }
    path = tmp_path / "research-production-blocked.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert load_manifest(path)["status"] == "blocked_model_not_approved"
    assert load_manifest(path, allow_research=True)["status"] == "ready"


def test_all_approved_tasks_require_production_evidence(tmp_path: Path):
    artifact = tmp_path / "ph.bin"
    artifact.write_bytes(b"structure-pka")
    manifest = {
        "name": "structure-pka", "version": "1", "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "artifact_path": str(artifact), "task": "ph", "applicability_domain": "validated structures",
        "metrics": {"rmse": 0.4}, "units": "pKa", "uncertainty_method": "ensemble",
        "validation": {"held_out": True}, "approved": True,
    }
    path = tmp_path / "ph.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = load_manifest(path)
    assert result["status"] == "blocked_missing_production_evidence"
    assert set(result["missing_evidence"]) == {"row_level_conditions", "unit_and_method", "license"}


def test_production_gate_reports_all_missing_evidence(tmp_path: Path):
    artifact = tmp_path / "research.bin"
    artifact.write_bytes(b"research")
    manifest = {
        "name": "research", "version": "1", "sha256": hashlib.sha256(b"research").hexdigest(),
        "artifact_path": str(artifact), "task": "tm", "applicability_domain": "research",
        "metrics": {}, "units": "degC", "uncertainty_method": "residual",
        "validation": {"held_out": True}, "approved": False, "execution_scope": "research_only",
    }
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = evaluate_production_gate(path)
    assert result["status"] == "blocked"
    assert "license" in result["missing"]
    assert "production_execution_scope" in result["missing"]


def test_production_gate_allows_complete_candidate_manifest(tmp_path: Path):
    artifact = tmp_path / "candidate.bin"
    artifact.write_bytes(b"validated-candidate")
    validation = {"status": "completed", "source_dataset_sha256": "a" * 64, "rows": 10, "conditions_required": ["temperature"], "metrics": {"rmse": 1.0, "mae": 0.5, "n": 10}, "independent_reviewer": {"name": "A", "organization": "Lab", "report_uri": "report", "signature": "sig"}}
    validation_path = tmp_path / "validation.json"; validation_path.write_text(json.dumps(validation), encoding="utf-8")
    manifest = {
        "name": "candidate", "version": "prod-1", "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "artifact_path": str(artifact), "task": "tm", "applicability_domain": "validated domain",
        "metrics": {"rmse": 1.0}, "units": "degC", "uncertainty_method": "held-out residual",
        "validation": {"held_out": True}, "approved": True, "execution_scope": "production",
        "production_evidence": {
            "row_level_conditions": "audited rows",
            "unit_and_method": "degC / DSC",
            "license": "commercial redistribution grant",
            "independent_validation": "external validation report",
            "independent_validation_manifest": str(validation_path),
            "approval_record": "change-control approval CR-1",
        },
    }
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = evaluate_production_gate(path)
    assert result["status"] == "eligible"
    assert result["version"] == "prod-1"






def test_production_candidate_is_blocked_in_research_scope(monkeypatch, tmp_path: Path):
    artifact = tmp_path / "candidate.bin"; artifact.write_bytes(b"candidate")
    manifest = {
        "name": "candidate", "version": "prod-1", "sha256": hashlib.sha256(b"candidate").hexdigest(),
        "artifact_path": str(artifact), "task": "tm", "applicability_domain": "validated",
        "metrics": {}, "units": "degC", "uncertainty_method": "residual", "validation": {"held_out": True},
        "approved": True, "execution_scope": "production", "production_registration": "candidate",
        "production_evidence": {"row_level_conditions": "x", "unit_and_method": "x", "license": "x", "independent_validation": "x", "approval_record": "x"},
    }
    path = tmp_path / "candidate.json"; path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("TM_MODEL_MANIFEST", str(path)); monkeypatch.setenv("MODEL_EXECUTION_SCOPE", "research_only")
    from app.services.model_artifact_registry import configured_model
    assert configured_model("tm")["status"] == "blocked_production_candidate_in_research_scope"


def test_ph_engine_remains_degraded_without_explicit_runtime(monkeypatch):
    monkeypatch.delenv("PH_ENGINE_BIN", raising=False)
    result = ph_opt_predict("ACDEH", structure_pdb="ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C")
    assert result["status"] == "degraded_structure_engine_unavailable"
    assert result["predicted_optimal_ph"] is None


def test_configured_production_model_cannot_bypass_promotion_gate(monkeypatch, tmp_path):
    from app.services.model_artifact_registry import configured_model
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"checkpoint")
    manifest = {
        "name": "demo", "version": "1", "sha256": hashlib.sha256(b"checkpoint").hexdigest(),
        "artifact_path": str(artifact), "task": "tm", "applicability_domain": "test",
        "metrics": {}, "units": "degC", "uncertainty_method": "ensemble",
        "validation": {"held_out": True}, "approved": True,
        "production_evidence": {"row_level_conditions": "rows", "unit_and_method": "DSC", "license": "grant"},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setenv("TM_MODEL_MANIFEST", str(path))
    monkeypatch.setenv("MODEL_EXECUTION_SCOPE", "production")
    assert evaluate_production_gate(path)["status"] == "blocked"
    assert configured_model("tm")["status"] != "ready"
    manifest["task"] = "km"
    monkeypatch.setenv("MODEL_EXECUTION_SCOPE", "research_only")
    path.write_text(json.dumps(manifest))
    assert configured_model("tm")["status"] == "blocked_model_task_mismatch"
