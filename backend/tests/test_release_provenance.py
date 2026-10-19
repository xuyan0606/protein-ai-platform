import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "release_provenance.py"
SPEC = importlib.util.spec_from_file_location("release_provenance", SCRIPT_PATH)
release_provenance = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(release_provenance)


SERVICES = ("backend", "frontend", "worker", "md-worker", "ligand-worker")
IMAGES = [f"{service}=registry.example/{service}@sha256:{'a' * 64}" for service in SERVICES]


def init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "release-test@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Release Test"], cwd=tmp_path, check=True)
    for relative, content in {
        "docker-compose.yml": "services: {}\n",
        "prod.env": "LLM_MODEL=gpt-6-sol\nAPI_TOKEN=never-print-this\nPUBLIC_BASE_URL=https://example.invalid\n",
        "backend/app/core/config.py": 'LLM_MODEL: str = "gpt-6-sol"\nKUAPAO_GPT6_SOL_MODEL: str = "gpt-6-sol"\n',
        "backend/app/core/llm_registry.py": 'id="gpt6-sol"\nmodel=settings.KUAPAO_GPT6_SOL_MODEL\n',
        "frontend/src/stores/chat.ts": "return saved || 'gpt6-sol'\nm.id === 'gpt6-sol' && m.available\n",
        "frontend/src/components/chat/ChatInput.tsx": "currentModel?.name || 'GPT-6-sol'\n",
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    return tmp_path


def build(root: Path, **kwargs):
    options = {
        "images": IMAGES,
        "compose_files": ["docker-compose.yml"],
        "env_files": ["prod.env"],
    }
    options.update(kwargs)
    return release_provenance.build_manifest(
        root=root,
        release_id="test-release-001",
        **options,
    )


def test_manifest_records_commit_immutable_images_and_only_env_hash(tmp_path):
    root = init_repo(tmp_path)
    payload = build(root)
    encoded = json.dumps(payload)
    assert payload["source"]["worktree_clean"] is True
    assert payload["images"]["backend"]["immutable_ref"].endswith("@sha256:" + "a" * 64)
    assert "never-print-this" not in encoded
    assert payload["compose"]["env_non_secret_sha256"]
    assert release_provenance._validate_manifest(payload) == []


def test_manifest_rejects_mutable_tagged_image_refs(tmp_path):
    root = init_repo(tmp_path)
    images = [f"{service}=protein-ai-{service}:aliyun" for service in SERVICES]
    with pytest.raises(release_provenance.ManifestError, match="pinned by @sha256"):
        build(root, images=images)


def test_manifest_creation_rejects_dirty_source_by_default(tmp_path):
    root = init_repo(tmp_path)
    (root / "docker-compose.yml").write_text("services: {frontend: {}}\n", encoding="utf-8")
    with pytest.raises(release_provenance.ManifestError, match="worktree is dirty"):
        build(root)


def test_verifier_detects_source_compose_and_environment_drift(tmp_path):
    root = init_repo(tmp_path)
    payload = build(root)
    manifest = root / "release-manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    result = release_provenance.verify_manifest(root=root, manifest_path=manifest, images=IMAGES, env_files=["prod.env"])
    assert result["status"] == "verified"

    (root / "docker-compose.yml").write_text("services: {frontend: {image: changed}}\n", encoding="utf-8")
    (root / "prod.env").write_text("LLM_MODEL=gpt-5.5\nAPI_TOKEN=changed-secret\nPUBLIC_BASE_URL=https://example.invalid\n", encoding="utf-8")
    result = release_provenance.verify_manifest(root=root, manifest_path=manifest, images=IMAGES, env_files=["prod.env"])
    assert result["status"] == "blocked"
    assert "compose source hash mismatch: docker-compose.yml" in result["failures"]
    assert "non-secret environment fingerprint mismatch" in result["failures"]


def test_verifier_rejects_image_digest_mismatch(tmp_path):
    root = init_repo(tmp_path)
    manifest = root / "release-manifest.json"
    manifest.write_text(json.dumps(build(root)), encoding="utf-8")
    changed_images = [IMAGES[0].replace("a" * 64, "b" * 64), *IMAGES[1:]]
    result = release_provenance.verify_manifest(root=root, manifest_path=manifest, images=changed_images)
    assert result["status"] == "blocked"
    assert "image digest set differs from manifest" in result["failures"]


def test_compose_environment_renders_only_digest_pinned_values(tmp_path):
    root = init_repo(tmp_path)
    manifest = root / "release-manifest.json"
    manifest.write_text(json.dumps(build(root)), encoding="utf-8")
    result = subprocess.run(
        [
            "python3", str(SCRIPT_PATH), "--root", str(root), "compose-env",
            "--manifest", str(manifest),
        ],
        check=True, capture_output=True, text=True,
    )
    assert "BACKEND_IMAGE=registry.example/backend@sha256:" in result.stdout
    assert "API_TOKEN" not in result.stdout
    assert "never-print-this" not in result.stdout


def test_verifier_requires_the_active_compose_file(tmp_path):
    root = init_repo(tmp_path)
    manifest = root / "release-manifest.json"
    manifest.write_text(json.dumps(build(root)), encoding="utf-8")
    result = release_provenance.verify_manifest(
        root=root, manifest_path=manifest, required_compose_file="other-compose.yml", offline=True,
    )
    assert result["status"] == "blocked"
    assert any("compose file is not bound by manifest" in failure for failure in result["failures"])
