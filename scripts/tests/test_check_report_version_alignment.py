from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_report_version_alignment.py"
SPEC = importlib.util.spec_from_file_location("report_alignment", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _fixture(tmp_path: Path, *, alignment: dict | None = None, rollback: dict | None = None) -> tuple[Path, Path]:
    (tmp_path / "backend/app/services").mkdir(parents=True)
    (tmp_path / "backend/app/services/report_generator.py").write_text('REPORT_SCHEMA_VERSION = "1.1"\n', encoding="utf-8")
    (tmp_path / "backend/app/core").mkdir(parents=True)
    (tmp_path / "backend/app/core/config.py").write_text('LLM_MODEL: str = "gpt-6-sol"\nKUAPAO_GPT6_SOL_MODEL: str = "gpt-6-sol"\n', encoding="utf-8")
    (tmp_path / "backend/app/core/llm_registry.py").write_text('id="gpt6-sol"\nmodel=settings.KUAPAO_GPT6_SOL_MODEL\n', encoding="utf-8")
    (tmp_path / "frontend/src/stores").mkdir(parents=True)
    (tmp_path / "frontend/src/stores/chat.ts").write_text("return saved || 'gpt6-sol'\nm.id === 'gpt6-sol' && m.available\n", encoding="utf-8")
    (tmp_path / "frontend/src/components/chat").mkdir(parents=True)
    (tmp_path / "frontend/src/components/chat/ChatInput.tsx").write_text("currentModel?.name || 'GPT-6-sol'\n", encoding="utf-8")
    (tmp_path / "frontend/dist").mkdir(parents=True)
    (tmp_path / "frontend/dist/index.js").write_text("bundle", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    images = {name: {"immutable_ref": f"registry/{name}@sha256:{'a'*64}", "digest": f"sha256:{'a'*64}"} for name in ("backend", "frontend", "worker", "md-worker", "ligand-worker")}
    compose = tmp_path / "compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    payload = {"manifest_version": 1, "release_id": "release-001", "created_at": "2026-10-17T00:00:00Z", "source": {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip(), "git_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=tmp_path, text=True).strip(), "worktree_clean": True}, "compose": {"files": [{"path": "compose.yml", "sha256": __import__('hashlib').sha256(compose.read_bytes()).hexdigest()}], "env_non_secret_sha256": __import__('hashlib').sha256(b'').hexdigest()}, "images": images, "rollback": rollback, "alignment": alignment}
    manifest = tmp_path / "RELEASE-MANIFEST.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest, tmp_path


def _image_args(digest: str) -> list[str]:
    return [
        f"{name}=registry/{name}@{digest}"
        for name in ("backend", "frontend", "worker", "md-worker", "ligand-worker")
    ]


def test_alignment_blocks_missing_alignment_and_rollback(tmp_path):
    manifest, root = _fixture(tmp_path)
    result = MODULE.check_alignment(root=root, manifest_path=manifest)
    assert result["status"] == "blocked"
    assert "manifest alignment section is missing" in result["failures"]
    assert "rollback target is missing" in result["failures"]


def test_alignment_blocks_schema_and_bundle_drift(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.js").write_text("different", encoding="utf-8")
    alignment = {"report_schema_version": "1.0", "wet_lab_schema_version": "wet_lab_plan_v0", "frontend_bundle_sha256": "0" * 64}
    rollback = {"target_release_id": "previous-001", "manifest_sha256": "a" * 64}
    manifest, root = _fixture(tmp_path, alignment=alignment, rollback=rollback)
    result = MODULE.check_alignment(root=root, manifest_path=manifest, frontend_bundle=bundle)
    assert result["status"] == "blocked"
    assert any("report schema differs" in item for item in result["failures"])
    assert any("wet-lab schema differs" in item for item in result["failures"])
    assert "frontend bundle hash differs from release manifest" in result["failures"]


def test_alignment_offline_verifies_extracted_release_without_git(tmp_path):
    import hashlib

    digest = hashlib.sha256()
    digest.update(b"index.js")
    digest.update(b"bundle")
    alignment = {
        "report_schema_version": "1.1",
        "wet_lab_schema_version": "wet_lab_plan_v1",
        "frontend_bundle_sha256": digest.hexdigest(),
    }
    rollback = {"target_release_id": "previous-001", "manifest_sha256": "a" * 64}
    manifest, root = _fixture(tmp_path, alignment=alignment, rollback=rollback)
    shutil.rmtree(root / ".git")
    result = MODULE.check_alignment(root=root, manifest_path=manifest, offline=True)
    assert result["status"] == "verified"


def test_alignment_blocks_git_revision_drift(tmp_path):
    alignment = {
        "report_schema_version": "1.1",
        "wet_lab_schema_version": "wet_lab_plan_v1",
        "frontend_bundle_sha256": __import__("hashlib").sha256(b"index.jsbundle").hexdigest(),
    }
    rollback = {"target_release_id": "previous-001", "manifest_sha256": "a" * 64}
    manifest, root = _fixture(tmp_path, alignment=alignment, rollback=rollback)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["source"]["git_commit"] = "b" * 40
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = MODULE.check_alignment(root=root, manifest_path=manifest)

    assert result["status"] == "blocked"
    assert "git commit differs from manifest" in result["failures"]


def test_alignment_blocks_model_selection_drift(tmp_path):
    alignment = {
        "report_schema_version": "1.1",
        "wet_lab_schema_version": "wet_lab_plan_v1",
        "frontend_bundle_sha256": __import__("hashlib").sha256(b"index.jsbundle").hexdigest(),
    }
    rollback = {"target_release_id": "previous-001", "manifest_sha256": "a" * 64}
    manifest, root = _fixture(tmp_path, alignment=alignment, rollback=rollback)
    (root / "backend/app/core/config.py").write_text(
        'LLM_MODEL: str = "gpt-5.6"\nKUAPAO_GPT6_SOL_MODEL: str = "gpt-5.6"\n',
        encoding="utf-8",
    )

    result = MODULE.check_alignment(root=root, manifest_path=manifest)

    assert result["status"] == "blocked"
    assert any("model selection mismatch" in item for item in result["failures"])


def test_alignment_blocks_runtime_image_digest_drift(tmp_path):
    alignment = {
        "report_schema_version": "1.1",
        "wet_lab_schema_version": "wet_lab_plan_v1",
        "frontend_bundle_sha256": __import__("hashlib").sha256(b"index.jsbundle").hexdigest(),
    }
    rollback = {"target_release_id": "previous-001", "manifest_sha256": "a" * 64}
    manifest, root = _fixture(tmp_path, alignment=alignment, rollback=rollback)

    result = MODULE.check_alignment(
        root=root,
        manifest_path=manifest,
        images=_image_args("sha256:" + "b" * 64),
    )

    assert result["status"] == "blocked"
    assert "image digest set differs from manifest" in result["failures"]
