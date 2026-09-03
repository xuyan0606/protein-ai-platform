import json

from build_production_model_package import build_manifest


def test_package_builder_blocks_without_real_artifacts(tmp_path):
    result = build_manifest(tmp_path)
    assert result["status"] == "blocked_pending_production_gate"
    assert result["production_model_artifact"] is False


def test_package_builder_requires_all_evidence_files(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "weights.safetensors").write_bytes(b"real-placeholder-is-not-enough")
    (model / "inference.py").write_text("def predict(x): return x\n")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "production_model_gate_20260829.json").write_text(json.dumps({"production_ready": True}))
    result = build_manifest(tmp_path, model_dir=model)
    assert result["status"] == "blocked_missing_evidence"
    assert result["production_model_artifact"] is False
