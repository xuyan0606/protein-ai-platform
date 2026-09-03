import hashlib
import json
from pathlib import Path

from validate_production_model_package import validate_manifest


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()


def _manifest(root: Path, *, tamper_weight: bool = False) -> Path:
    weight_content = "real-neural-weight-bytes"
    weight = root / "weights" / "enzyme.safetensors"
    weight_sha = _write(weight, weight_content)
    if tamper_weight:
        weight_sha = "0" * 64
    refs = {}
    for key, filename in {
        "feature_contract": "feature.json",
        "training": "training.json",
        "evaluation": "evaluation.json",
        "release": "release.json",
    }.items():
        path = root / "evidence" / filename
        refs[key] = {"path": str(path.relative_to(root)), "sha256": _write(path, f"{key}-evidence")}
    entrypoint = _write(root / "inference.py", "def predict(payload):\n    return payload\n")
    manifest = {
        "schema_version": "production_model_package_v1",
        "status": "candidate",
        "model": {"name": "KWB-EnzymeDesigner", "version": "3.0.0"},
        "inference_entrypoint": {"path": "inference.py", "symbol": "predict", "sha256": entrypoint},
        "weights": [{"path": "weights/enzyme.safetensors", "sha256": weight_sha, "size_bytes": weight.stat().st_size, "artifact_type": "neural_weights"}],
        **refs,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_missing_manifest_is_blocked(tmp_path):
    result = validate_manifest(tmp_path / "missing.json")
    assert result["status"] == "blocked_missing_manifest"
    assert result["production_model_artifact"] is False


def test_valid_package_requires_real_files_and_hashes(tmp_path):
    manifest = _manifest(tmp_path)
    result = validate_manifest(manifest)
    assert result["status"] == "validated"
    assert result["production_model_artifact"] is True
    assert result["artifact_count"] == 6
    assert result["failures"] == []


def test_weight_hash_mismatch_blocks_package(tmp_path):
    result = validate_manifest(_manifest(tmp_path, tamper_weight=True))
    assert result["status"] == "blocked_invalid"
    assert result["production_model_artifact"] is False
    assert any("sha256" in failure for failure in result["failures"])
