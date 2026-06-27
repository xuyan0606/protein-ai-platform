"""Tests for Phase 1 (requirements) and Phase 2 (docker-compose/nginx) config validity.

These tests validate configuration file syntax and content without
requiring Docker or network access.
"""

import os
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestRequirementsFiles:
    """Phase 1: requirements split validation."""

    def test_requirements_txt_references_subfiles(self):
        req = PROJECT_ROOT / "backend" / "requirements.txt"
        assert req.exists(), "requirements.txt missing"
        content = req.read_text()
        assert "-r requirements-core.txt" in content
        assert "-r requirements-ml.txt" in content

    def test_requirements_core_exists_and_valid(self):
        core = PROJECT_ROOT / "backend" / "requirements-core.txt"
        assert core.exists(), "requirements-core.txt missing"
        lines = [l.strip() for l in core.read_text().splitlines() if l.strip() and not l.startswith("#")]
        assert len(lines) >= 10, f"requirements-core.txt too short: {len(lines)} packages"

        # Must contain FastAPI
        assert any("fastapi" in l.lower() for l in lines), "FastAPI missing from core"

    def test_requirements_ml_exists_and_valid(self):
        ml = PROJECT_ROOT / "backend" / "requirements-ml.txt"
        assert ml.exists(), "requirements-ml.txt missing"
        lines = [l.strip() for l in ml.read_text().splitlines() if l.strip() and not l.startswith("#")]
        assert len(lines) >= 3, f"requirements-ml.txt too short: {len(lines)} packages"

        # Must contain torch
        assert any("torch" in l.lower() for l in lines), "torch missing from ML"

    def test_requirements_core_no_torch(self):
        """Core requirements must NOT include torch (it goes in ML)."""
        core = PROJECT_ROOT / "backend" / "requirements-core.txt"
        content = core.read_text().lower()
        assert "torch" not in content, "torch should be in requirements-ml.txt, not core"
        assert "rdkit" not in content, "rdkit should be in requirements-ml.txt, not core"

    def test_requirements_prod_references_core(self):
        prod = PROJECT_ROOT / "backend" / "requirements-prod.txt"
        if prod.exists():
            content = prod.read_text()
            assert "-r requirements-core.txt" in content


class TestDockerfiles:
    """Phase 1: Dockerfile validation."""

    def test_worker_dockerfile_has_torch_cpu(self):
        df = PROJECT_ROOT / "docker" / "Dockerfile.worker"
        content = df.read_text()
        assert "--index-url https://download.pytorch.org/whl/cpu" in content, (
            "Worker Dockerfile missing torch CPU wheel install"
        )

    def test_worker_dockerfile_has_rdkit_libs(self):
        df = PROJECT_ROOT / "docker" / "Dockerfile.worker"
        content = df.read_text()
        for lib in ["libxrender1", "libxext6", "libsm6"]:
            assert lib in content, f"Worker Dockerfile missing RDKit lib: {lib}"

    def test_worker_dockerfile_has_model_cache(self):
        df = PROJECT_ROOT / "docker" / "Dockerfile.worker"
        content = df.read_text()
        assert "esm2_t33_650M_UR50D" in content, (
            "Worker Dockerfile should pre-download ESM-2 model"
        )
        assert "COPY --from=builder /root/.cache/torch/hub" in content, (
            "Worker Dockerfile should copy model cache to runtime"
        )

    def test_backend_dockerfile_no_rdkit(self):
        """Backend uses core-only deps (no torch/ML). RDKit libs go in worker."""
        df = PROJECT_ROOT / "docker" / "Dockerfile.backend"
        content = df.read_text()
        # Backend should NOT have RDKit system libs — ML runs on worker
        for lib in ["libxrender1", "libxext6", "libsm6"]:
            assert lib not in content, (
                f"Backend Dockerfile should NOT have {lib} — RDKit runs on worker only"
            )
        # Should use requirements-prod.txt (core only, no torch)
        assert "requirements-prod.txt" in content, (
            "Backend Dockerfile must use requirements-prod.txt (core only)"
        )


class TestDockerCompose:
    """Phase 2: docker-compose.yml hardening validation."""

    @pytest.fixture
    def compose_content(self):
        compose = PROJECT_ROOT / "docker" / "docker-compose.yml"
        return compose.read_text()

    def test_no_public_postgres_port(self, compose_content):
        """Port 5432 should NOT be exposed publicly."""
        # Look for 'ports:' followed by '5432' in the postgres section
        assert '"5432:5432"' not in compose_content, "PostgreSQL port 5432 should not be public"

    def test_no_public_redis_port(self, compose_content):
        assert '"6379:6379"' not in compose_content, "Redis port 6379 should not be public"

    def test_no_public_minio_ports(self, compose_content):
        assert '"9000:9000"' not in compose_content, "MinIO S3 port 9000 should not be public"
        assert '"9001:9001"' not in compose_content, "MinIO console port 9001 should not be public"

    def test_no_public_chromadb_port(self, compose_content):
        assert '"8001:8000"' not in compose_content, "ChromaDB port 8001 should not be public"

    def test_no_public_outline_port(self, compose_content):
        assert '"3001:3001"' not in compose_content, "Outline port 3001 should not be public"

    def test_nginx_has_443(self, compose_content):
        assert '"443:443"' in compose_content, "Nginx should expose port 443 for HTTPS"

    def test_log_rotation_present(self, compose_content):
        assert "max-size" in compose_content, "Log rotation (max-size) missing"
        assert "max-file" in compose_content, "Log rotation (max-file) missing"

    def test_health_checks_present(self, compose_content):
        assert "healthcheck:" in compose_content, "Health checks missing"
        # Should have health checks for backend, worker, frontend
        assert "curl" in compose_content or "wget" in compose_content

    def test_https_cors_origins(self, compose_content):
        """CORS should use HTTPS origins, not HTTP."""
        # Find CORS_ORIGINS lines
        cors_lines = [l for l in compose_content.splitlines() if "CORS_ORIGINS" in l]
        for line in cors_lines:
            if "localhost" not in line:  # Skip dev defaults
                assert "https://" in line, f"CORS should use HTTPS: {line}"

    def test_ssl_volume_mount(self, compose_content):
        assert "./ssl:/etc/nginx/ssl" in compose_content, (
            "Nginx should mount SSL certificate directory"
        )


class TestNginxConfig:
    """Phase 2: nginx.conf validation."""

    @pytest.fixture
    def nginx_content(self):
        conf = PROJECT_ROOT / "docker" / "nginx.conf"
        return conf.read_text()

    def test_https_redirect(self, nginx_content):
        assert "return 301 https://" in nginx_content, "HTTP→HTTPS redirect missing"

    def test_ssl_listen(self, nginx_content):
        assert "listen       443 ssl" in nginx_content, "SSL listener missing"

    def test_tls_protocols(self, nginx_content):
        assert "TLSv1.2" in nginx_content, "TLS 1.2 missing"
        assert "TLSv1.3" in nginx_content, "TLS 1.3 missing"

    def test_security_headers(self, nginx_content):
        assert "Strict-Transport-Security" in nginx_content, "HSTS header missing"
        assert "X-Content-Type-Options" in nginx_content, "X-Content-Type-Options missing"
        assert "X-XSS-Protection" in nginx_content, "X-XSS-Protection missing"

    def test_sse_streaming_preserved(self, nginx_content):
        """SSE proxy_buffering off must still be present for /api/."""
        assert "proxy_buffering        off" in nginx_content, "SSE streaming disabled!"

    def test_ssl_cert_paths(self, nginx_content):
        assert "/etc/nginx/ssl/server.crt" in nginx_content
        assert "/etc/nginx/ssl/server.key" in nginx_content


class TestGetCurrentUserDependency:
    """Regression: get_current_user returns dict, not User model."""

    def test_get_current_user_returns_dict(self):
        """get_current_user return type must be dict.

        Regression test for bug where projects.py used `user: User` type
        annotation which failed with AttributeError because get_current_user
        returns a dict, not a User model.
        """
        from app.core.security import get_current_user
        import inspect

        sig = inspect.signature(get_current_user)
        return_annotation = sig.return_annotation
        # from __future__ import annotations makes this a string
        annotation_str = str(return_annotation).lower()
        assert "dict" in annotation_str, (
            f"get_current_user must return dict, not {return_annotation}"
        )
        assert "user" not in annotation_str, (
            f"get_current_user must NOT return User model, got: {return_annotation}"
        )

    def test_no_user_model_import_in_projects_api(self):
        """projects.py must NOT import User model — user is dict, not ORM."""
        projects_path = Path(__file__).resolve().parent.parent / "app" / "api" / "projects.py"
        content = projects_path.read_text()
        assert "from app.models.user import User" not in content, (
            "projects.py should not import User model — user is a dict from get_current_user"
        )
        assert "user: User" not in content, (
            "projects.py should annotate user as dict, not User"
        )
        # Must use dict access pattern
        assert 'user["id"]' in content, (
            "projects.py must use user[\"id\"] (dict access), not user.id"
        )


class TestSecuritySecrets:
    """Phase 2: Verify secrets are not default/weak values."""

    def test_docker_env_no_default_postgres_password(self):
        env = PROJECT_ROOT / "docker" / ".env"
        if env.exists():
            content = env.read_text()
            assert "POSTGRES_PASSWORD=postgres" not in content, (
                "docker/.env still has default postgres password!"
            )

    def test_docker_env_no_default_minio_password(self):
        env = PROJECT_ROOT / "docker" / ".env"
        if env.exists():
            content = env.read_text()
            assert "MINIO_ROOT_PASSWORD=minioadmin" not in content, (
                "docker/.env still has default minio password!"
            )

    def test_docker_env_no_dev_secret(self):
        env = PROJECT_ROOT / "docker" / ".env"
        if env.exists():
            content = env.read_text()
            assert "dev-secret" not in content, "docker/.env still has dev SECRET_KEY!"
