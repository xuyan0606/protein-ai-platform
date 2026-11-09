from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_aliyun_compose_uses_digest_injection_variables():
    app = (PROJECT_ROOT / "docker/docker-compose.aliyun-app.yml").read_text(encoding="utf-8")
    gpu = (PROJECT_ROOT / "docker/docker-compose.aliyun-gpu.yml").read_text(encoding="utf-8")
    assert "${BACKEND_IMAGE:-protein-ai-backend:aliyun}" in app
    assert "${FRONTEND_IMAGE:-protein-ai-frontend:aliyun}" in app
    assert "${LIGAND_WORKER_IMAGE:-protein-ai-ligand-worker:aliyun}" in app
    assert "${MD_WORKER_IMAGE:-protein-ai-backend:aliyun}" in gpu
    assert "${LIGAND_WORKER_IMAGE:-protein-ai-ligand-worker:aliyun}" in gpu


def test_deploy_script_requires_manifest_and_checks_runtime_images():
    script = (PROJECT_ROOT / "deploy-aliyun.sh").read_text(encoding="utf-8")
    assert 'REQUIRE_RELEASE_MANIFEST="${REQUIRE_RELEASE_MANIFEST:-1}"' in script
    assert "verify --offline --manifest" in script
    assert "check_report_version_alignment.py" in script
    assert "--offline" in script
    assert "--require-compose-file" in script
    assert "verify_runtime_image" in script
    assert "Runtime image mismatch" in script
    assert "build is disabled for a manifest release" in script
    assert "backup_chroma_before_upgrade" in script
    assert '"$SCRIPT_DIR/scripts/backup_chroma_volume.sh"' in script
    assert "Chroma volume backup failed; release update aborted" in script
    assert script.index("backup_chroma_before_upgrade\n        if release_manifest_active") < script.index('compose_cmd pull md-worker')


def test_install_script_checks_manifest_before_switching_current():
    script = (PROJECT_ROOT / "scripts/install_release_bundle.sh").read_text(encoding="utf-8")
    assert 'REQUIRE_RELEASE_MANIFEST="${REQUIRE_RELEASE_MANIFEST:-1}"' in script
    assert "tar -tzf \"$BUNDLE_PATH\" | grep -Fxq \"$manifest_member\"" in script
    assert "verify --offline" in script
    assert "check_report_version_alignment.py" in script
    assert "--offline" in script
    assert script.index("verify --offline") < script.index('ln -sfn "$project_dir" "$DEPLOY_ROOT/current"')
    assert "ALLOW_LEGACY_RELEASE=1" in script


def test_package_manifest_is_allowed_in_release_bundle():
    script = (PROJECT_ROOT / "scripts/package_deploy_bundle.py").read_text(encoding="utf-8")
    assert '"RELEASE-MANIFEST.json"' in script


def test_chromadb_server_is_pinned_to_backend_client_version():
    requirements = (PROJECT_ROOT / "backend/requirements-core.txt").read_text(encoding="utf-8")
    assert "chromadb==0.6.3" in requirements
    for compose_name in ("docker-compose.yml", "docker-compose.dev.yml", "docker-compose.aliyun-app.yml"):
        compose = (PROJECT_ROOT / "docker" / compose_name).read_text(encoding="utf-8")
        assert "image: chromadb/chroma:0.6.3" in compose
        assert "chromadb/chroma:latest" not in compose
