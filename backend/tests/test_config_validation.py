"""Tests for Phase 1 (requirements) and Phase 2 (docker-compose/nginx) config validity.

These tests validate configuration file syntax and content without
requiring Docker or network access.
"""

import os
import re
import subprocess
import sys
import json
import importlib.util
import gzip
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def isolated_remaining_backlog_root(monkeypatch, tmp_path):
    monkeypatch.setenv("REMAINING_BACKLOG_DEPLOY_ROOT", str(tmp_path / "empty-deploy-data"))


def test_alembic_environment_imports_identity_and_strategy_models():
    env_text = (PROJECT_ROOT / "backend" / "alembic" / "env.py").read_text()
    assert "app.models.strategy_checkpoint" in env_text
    assert "app.models.identity_consistency" in env_text


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

    def test_release_bundle_installer_preserves_top_level_project_dir(self):
        package_script = PROJECT_ROOT / "scripts" / "package_deploy_bundle.py"
        install_script = PROJECT_ROOT / "scripts" / "install_release_bundle.sh"
        readme = PROJECT_ROOT / "README.md"
        aliyun_doc = PROJECT_ROOT / "docs" / "aliyun-live-environment-prep-2026-07-16.md"
        dockerignore = PROJECT_ROOT / ".dockerignore"

        package_content = package_script.read_text()
        install_content = install_script.read_text()
        assert 'archive_path=f"protein-ai-platform/{rel_posix}"' in package_content
        assert '"protein-ai-platform/PACKAGE-MANIFEST.json"' in package_content
        assert 'root_name" = "protein-ai-platform"' in install_content
        assert 'project_dir="$release_dir/protein-ai-platform"' in install_content
        assert 'docker-compose.aliyun-app.yml' in install_content
        assert 'old_current/docker/ssl' in install_content
        assert "backend/alembic/" not in dockerignore.read_text()
        assert "/releases/<release>/protein-ai-platform" in readme.read_text()
        assert "/releases/<timestamp>/protein-ai-platform" in aliyun_doc.read_text()

    def test_release_bundle_excludes_virtualenv_recovery_dirs(self, tmp_path):
        package_script = PROJECT_ROOT / "scripts" / "package_deploy_bundle.py"
        spec = importlib.util.spec_from_file_location("package_deploy_bundle", package_script)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["package_deploy_bundle"] = module
        spec.loader.exec_module(module)

        (tmp_path / "backend" / "app").mkdir(parents=True)
        (tmp_path / "backend" / "app" / "main.py").write_text("print('ok')\n")
        (tmp_path / "backend" / ".venv.broken-20260720T1430" / "bin").mkdir(parents=True)
        (tmp_path / "backend" / ".venv.broken-20260720T1430" / "bin" / "python").write_text("")
        (tmp_path / "backend" / "venv-old" / "bin").mkdir(parents=True)
        (tmp_path / "backend" / "venv-old" / "bin" / "python").write_text("")
        (tmp_path / "frontend" / "node_modules" / "vite").mkdir(parents=True)
        (tmp_path / "frontend" / "node_modules" / "vite" / "index.js").write_text("")
        (tmp_path / "Makefile").write_text("help:\n")

        files = module.collect_files(tmp_path, include_deploy_data=False, extra_excludes=[])
        archived = {item.archive_path for item in files}

        assert "protein-ai-platform/backend/app/main.py" in archived
        assert all(".venv" not in path for path in archived)
        assert all("venv-old" not in path for path in archived)
        assert all("node_modules" not in path for path in archived)

    def test_release_bundle_includes_version_provenance_files(self, tmp_path):
        package_script = PROJECT_ROOT / "scripts" / "package_deploy_bundle.py"
        spec = importlib.util.spec_from_file_location("package_deploy_bundle_provenance", package_script)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        (tmp_path / "VERSION").write_text("0.1.0\n")
        (tmp_path / "RELEASE-MANIFEST.json").write_text("{}\n")
        (tmp_path / "backend").mkdir()
        files = module.collect_files(tmp_path, include_deploy_data=False, extra_excludes=[])
        archived = {item.archive_path for item in files}

        assert "protein-ai-platform/VERSION" in archived
        assert "protein-ai-platform/RELEASE-MANIFEST.json" in archived

    def test_alembic_env_bypasses_configparser_for_percent_encoded_urls(self):
        env_py = PROJECT_ROOT / "backend" / "alembic" / "env.py"
        content = env_py.read_text()
        assert "create_async_engine(settings.DATABASE_URL" in content
        assert "url=url," in content
        assert 'set_main_option("sqlalchemy.url"' not in content

    def test_structure_smoke_script_exists(self):
        script = PROJECT_ROOT / "backend" / "scripts" / "smoke_structure_data.py"
        content = script.read_text()
        assert "SIFTS_MAPPING_PATH" in content
        assert "SIFTS_SMOKE_USE_DEMO" in content
        assert "FOLDSEEK_SMOKE_USE_DEMO" in content
        assert "FOLDSEEK_API_URL" in content
        assert "FOLDSEEK_BINARY" in content

    def test_md_topology_smoke_script_reports_runtime_status(self):
        script = PROJECT_ROOT / "backend" / "scripts" / "smoke_md_topology.py"
        content = script.read_text()
        assert "_validate_pdb_topology" in content
        assert "--require-live" in content
        assert "GROMACS pdb2gmx topology precheck" in content
        assert "DEFAULT_SMOKE_PDB_CANDIDATES" in content
        assert "deploy_data" in content and "smoke" in content and "query.pdb" in content

        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=PROJECT_ROOT / "backend",
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["name"] == "md_topology_smoke"
        assert payload["summary"]["status"] in {"validated", "validated_with_warnings", "blocked", "unavailable"}
        assert "topology_validated" in payload["summary"]

    def test_ligand_toolchain_smoke_script_reports_sdf_and_runtime_status(self):
        script = PROJECT_ROOT / "backend" / "scripts" / "smoke_ligand_toolchain.py"
        content = script.read_text()
        assert "Structure2D_COMPOUND_CID_5478883.sdf" in content
        assert "OpenBabel" in content
        assert "AutoDock Vina" in content
        assert "ACPYPE/Antechamber" in content
        assert "--require-live" in content
        assert 'topology_ready = bool(tools["acpype"]["available"])' in content

        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=PROJECT_ROOT / "backend",
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["name"] == "ligand_toolchain_smoke"
        assert payload["summary"]["input_sdf_exists"] is True
        assert payload["summary"]["is_2d_sdf"] is True
        assert payload["summary"]["atom_count"] == 111
        assert payload["summary"]["bond_count"] == 110
        assert payload["summary"]["status"] in {"ready", "blocked_toolchain_missing"}
        assert "openbabel" in payload["tools"]
        assert "vina" in payload["tools"]
        assert "gromacs" in payload["tools"]

    def test_ligand_preprocess_tool_is_registered_for_async_execution(self):
        registry = PROJECT_ROOT / "backend" / "app" / "tools" / "registry.py"
        scheduler = PROJECT_ROOT / "backend" / "app" / "services" / "scheduler.py"
        audit = PROJECT_ROOT / "backend" / "app" / "services" / "tool_task_audit.py"
        registry_content = registry.read_text()
        scheduler_content = scheduler.read_text()
        audit_content = audit.read_text()
        assert "app.tools.ligand_preprocess" in registry_content
        assert '"ligand_preprocess"' in scheduler_content
        assert 'queue="ligand_cpu"' in scheduler_content
        assert '"sdf_data"' in audit_content

    def test_redis_settings_support_authenticated_cloud_url(self):
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        try:
            from app.core.config import Settings
        finally:
            try:
                sys.path.remove(str(PROJECT_ROOT / "backend"))
            except ValueError:
                pass

        settings = Settings(
            REDIS_HOST="r-test.redis.rds.aliyuncs.com",
            REDIS_PORT=6379,
            REDIS_DB=2,
            REDIS_USERNAME="dms_user_1",
            REDIS_PASSWORD="6(PPvF&mOzxT#Ziy",
        )

        assert settings.REDIS_URL == (
            "redis://dms_user_1:6%28PPvF%26mOzxT%23Ziy@r-test.redis.rds.aliyuncs.com:6379/2"
        )

    def test_manual_screenshot_capture_assets_are_wired(self):
        script = PROJECT_ROOT / "scripts" / "capture_manual_screenshots.mjs"
        makefile = PROJECT_ROOT / "Makefile"
        manual = PROJECT_ROOT / "docs" / "manuals" / "screenshot-operation-placeholder-manual.md"
        manifest = PROJECT_ROOT / "docs" / "manuals" / "screenshots" / "manifest.json"
        drill_record = PROJECT_ROOT / "docs" / "manuals" / "drill-records" / "2026-07-10-local-screenshot-ligand-gate.md"

        script_content = script.read_text()
        assert "chromium.launch" in script_content
        assert "docs/manuals/screenshots" in script_content
        assert "SHOT-DATA-004" in script_content
        assert "SHOT-OPS-001" in script_content
        assert "manual-screenshots" in makefile.read_text()
        manual_content = manual.read_text()
        assert "scripts/capture_manual_screenshots.mjs" in manual_content
        assert "data-experiment-feedback.png" in manual_content
        assert manifest.exists()
        manifest_payload = json.loads(manifest.read_text())
        assert manifest_payload["screenshots"]
        assert any(item["id"] == "SHOT-DATA-004" for item in manifest_payload["screenshots"])
        drill_content = drill_record.read_text()
        assert "DRILL-20260710-LOCAL-001" in drill_content
        assert "blocked_toolchain_missing" in drill_content

    def test_remaining_backlog_readiness_aggregates_external_gates(self):
        script = PROJECT_ROOT / "scripts" / "check_remaining_backlog_readiness.py"
        makefile = PROJECT_ROOT / "Makefile"
        task_plan = PROJECT_ROOT / "task_plan.md"
        content = script.read_text()
        assert "network_io" in content
        assert "destructive_actions" in content
        assert "local_capable" in content
        assert "external_dependency" in content
        assert "real_deploy_data" in content
        assert "gpu_gromacs_md_live" in content
        assert "ligand_runtime_live" in content
        assert "oss_minio_live_e2e" in content
        assert "admin_authenticated_screenshots" in content
        assert "maintenance_window_drills" in content
        assert "SCREENSHOT_EMAIL" in content
        assert "MAINTENANCE_WINDOW_ID" in content

        task_plan_content = task_plan.read_text()
        assert "MD 科学参数层第四层第二批第七步" in task_plan_content
        assert "底物/配体预处理与对接层第二步第二批" in task_plan_content
        assert "自动化测试增强第二层" in task_plan_content
        assert "封装交付层第三层第二批" in task_plan_content
        assert "产品化文档第二层第二批剩余部分" in task_plan_content
        assert "绑定正式域名和 HTTPS 证书" in task_plan_content

        make_content = makefile.read_text()
        assert "remaining-backlog-readiness" in make_content
        assert "remaining-backlog-readiness-json" in make_content

        baseline_env = os.environ.copy()
        for key in (
            "MINIO_ENDPOINT",
            "MINIO_BUCKET",
            "MINIO_ACCESS_KEY",
            "MINIO_SECRET_KEY",
            "MINIO_REGION",
            "ALIYUN_OSS_ENDPOINT",
            "ALIYUN_OSS_REGION",
            "ALIYUN_OSS_BUCKET",
            "ALIYUN_OSS_ACCESS_KEY_ID",
            "ALIYUN_OSS_ACCESS_KEY_SECRET",
        ):
            baseline_env.pop(key, None)

        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=PROJECT_ROOT,
            env=baseline_env,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["summary"]["network_io"] == "not_executed"
        assert payload["summary"]["destructive_actions"] == "not_executed"
        assert payload["summary"]["bucket_counts"] == {
            "external_dependency": 7,
            "local_capable": 2,
        }
        # A local code test cannot assume the Docker daemon and a prebuilt
        # ligand image are available. Preserve that live gate's actual result.
        ligand = next(item for item in payload["results"] if item["name"] == "ligand_runtime_live")
        assert ligand["status"] in {"ready", "external_required"}
        assert payload["summary"]["counts"] == (
            {"external_required": 6, "ready": 3} if ligand["status"] == "ready"
            else {"external_required": 7, "ready": 2}
        )
        names = {item["name"] for item in payload["results"]}
        assert "real_deploy_data" in names
        assert "gpu_gromacs_md_live" in names
        assert "ligand_runtime_live" in names
        assert "oss_minio_live_e2e" in names
        assert "admin_authenticated_screenshots" in names
        assert "maintenance_window_drills" in names
        assert "md_blackbox_live_e2e" in names
        assert "remote_pytest_runner" in names

        by_name = {item["name"]: item for item in payload["results"]}
        assert by_name["real_deploy_data"]["bucket"] == "local_capable"
        assert by_name["gpu_gromacs_md_live"]["bucket"] == "external_dependency"
        assert by_name["ligand_runtime_live"]["bucket"] == "external_dependency"
        assert by_name["oss_minio_live_e2e"]["bucket"] == "external_dependency"
        assert by_name["admin_authenticated_screenshots"]["bucket"] == "external_dependency"
        assert by_name["maintenance_window_drills"]["bucket"] == "external_dependency"
        assert by_name["md_blackbox_live_e2e"]["bucket"] == "external_dependency"
        assert by_name["remote_pytest_runner"]["bucket"] == "local_capable"
        assert by_name["remote_pytest_runner"]["status"] == "ready"
        assert ".github/workflows/ci.yml" in by_name["remote_pytest_runner"]["source"]
        assert "scripts/run_pytest_runner.py" in by_name["remote_pytest_runner"]["source"]

        ready_env = os.environ.copy()
        ready_env.update(
            {
                "ALIYUN_OSS_ENDPOINT": "oss-cn-hangzhou-internal.aliyuncs.com",
                "ALIYUN_OSS_REGION": "cn-hangzhou",
                "ALIYUN_OSS_BUCKET": "protein-ai-files",
                "ALIYUN_OSS_ACCESS_KEY_ID": "test-access-key",
                "ALIYUN_OSS_ACCESS_KEY_SECRET": "test-secret-key",
            }
        )
        for key in ("MINIO_ENDPOINT", "MINIO_BUCKET", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_REGION"):
            ready_env.pop(key, None)
        ready_result = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=PROJECT_ROOT,
            env=ready_env,
            capture_output=True,
            text=True,
            check=True,
        )
        ready_payload = json.loads(ready_result.stdout)
        ready_by_name = {item["name"]: item for item in ready_payload["results"]}
        assert ready_payload["summary"]["network_io"] == "not_executed"
        assert ready_by_name["oss_minio_live_e2e"]["status"] == "ready"
        assert ready_by_name["oss_minio_live_e2e"]["bucket"] == "local_capable"
        assert "--include-oss-e2e" in ready_by_name["oss_minio_live_e2e"]["next_actions"][0]

        text_result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT,
            env=baseline_env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "本机可做" in text_result.stdout
        assert "外部依赖" in text_result.stdout
        assert "real_deploy_data" in text_result.stdout
        assert "gpu_gromacs_md_live" in text_result.stdout

    def test_remaining_backlog_external_input_validator_is_fail_closed(self, tmp_path):
        packet_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_external_input_packet.py"
        validator = PROJECT_ROOT / "scripts" / "validate_remaining_backlog_external_inputs.py"
        makefile = PROJECT_ROOT / "Makefile"
        packet_path = tmp_path / "packet.json"
        packet_md_path = tmp_path / "packet.md"
        template_path = tmp_path / "values.template.json"
        report_path = tmp_path / "report.json"

        assert validator.exists()
        validator_content = validator.read_text()
        assert "network_io" in validator_content
        assert "destructive_actions" in validator_content
        assert "secrets_printed" in validator_content
        assert "secret_reference" in validator_content

        make_content = makefile.read_text()
        assert "remaining-backlog-input-template" in make_content
        assert "remaining-backlog-input-validate" in make_content

        subprocess.run(
            [
                sys.executable,
                str(packet_script),
                "--output-json",
                str(packet_path),
                "--output-md",
                str(packet_md_path),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        result = subprocess.run(
            [
                sys.executable,
                str(validator),
                "--packet",
                str(packet_path),
                "--values",
                str(template_path),
                "--output",
                str(report_path),
                "--write-template",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        stdout_payload = json.loads(result.stdout)
        packet_payload = json.loads(packet_path.read_text())
        pending_count = packet_payload["item_count"]
        p1_count = packet_payload["priority_summary"]["P1"]["item_count"]
        assert stdout_payload["network_io"] == "not_executed"
        assert stdout_payload["destructive_actions"] == "not_executed"
        assert stdout_payload["secrets_printed"] is False
        assert stdout_payload["all_inputs_present"] is False
        assert stdout_payload["item_count"] == pending_count
        assert stdout_payload["priority_summary"]["P0"]["item_count"] == 4
        assert stdout_payload["priority_summary"]["P0"]["missing_input_rows"] == 4
        assert stdout_payload["priority_summary"]["P1"]["item_count"] == p1_count
        assert stdout_payload["priority_summary"]["P1"]["missing_input_rows"] == p1_count

        template_payload = json.loads(template_path.read_text())
        assert template_payload["mode"] == "operator_supplied_values_template"
        assert template_payload["priority_summary"]["P0"]["item_count"] == 4
        assert template_payload["items"]["admin_authenticated_screenshots"]["SCREENSHOT_PASSWORD_secret_reference"] == "<secret-reference-only>"
        assert "remote_pytest_runner" not in template_payload["items"]

        report_payload = json.loads(report_path.read_text())
        assert report_payload["mode"] == "read_only_external_input_validation"
        assert report_payload["network_io"] == "not_executed"
        assert report_payload["destructive_actions"] == "not_executed"
        assert report_payload["secrets_printed"] is False
        assert report_payload["item_count"] == pending_count
        assert report_payload["ready_to_run_rows"] == 0
        assert report_payload["missing_input_rows"] == pending_count
        assert report_payload["priority_summary"]["P0"]["items"] == [
            "formal_domain_https",
            "gpu_gromacs_md_live",
            "md_blackbox_live_e2e",
            "oss_minio_live_e2e",
        ]
        assert report_payload["priority_summary"]["P1"]["missing_input_rows"] == p1_count
        assert report_payload["all_inputs_present"] is False
        by_name = {item["name"]: item for item in report_payload["items"]}
        assert by_name["formal_domain_https"]["priority"] == "P0"
        assert by_name["admin_authenticated_screenshots"]["priority"] == "P1"
        assert "credential_secret_reference" in by_name["md_blackbox_live_e2e"]["missing_fields"]
        assert "## Priority Summary" in packet_md_path.read_text(encoding="utf-8")
        assert "SCREENSHOT_PASSWORD_secret_reference" in by_name["admin_authenticated_screenshots"]["secret_reference_fields"]

    def test_remaining_backlog_execution_plan_is_redacted_and_armed_by_inputs(self, tmp_path):
        packet_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_external_input_packet.py"
        plan_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_gate_execution_plan.py"
        makefile = PROJECT_ROOT / "Makefile"
        packet_path = tmp_path / "packet.json"
        packet_md_path = tmp_path / "packet.md"
        values_path = tmp_path / "values.json"
        output_json = tmp_path / "plan.json"
        output_md = tmp_path / "plan.md"

        assert plan_script.exists()
        assert "remaining-backlog-execution-plan" in makefile.read_text()
        script_content = plan_script.read_text()
        assert "network_io" in script_content
        assert "destructive_actions" in script_content
        assert "secrets_printed" in script_content
        assert "COMMAND_TEMPLATES" in script_content

        subprocess.run(
            [
                sys.executable,
                str(packet_script),
                "--output-json",
                str(packet_path),
                "--output-md",
                str(packet_md_path),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        values_path.write_text(
            json.dumps(
                {
                    "items": {
                        "admin_authenticated_screenshots": {
                            "SCREENSHOT_EMAIL_secret_reference": "op://protein-ai/admin/email",
                            "SCREENSHOT_PASSWORD_secret_reference": "op://protein-ai/admin/password",
                            "FRONTEND_BASE_URL": "https://protein.example.com",
                        },
                        "remote_pytest_runner": {
                            "ci_workflow_or_runner_image": ".github/workflows/ci.yml backend-test",
                            "trigger_policy": "pull_request_and_manual_dispatch",
                            "coverage_artifact_access": "github-actions-artifact",
                            "local_backfill_runner_path": "scripts/run_pytest_runner.py",
                        },
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                str(plan_script),
                "--packet",
                str(packet_path),
                "--values",
                str(values_path),
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        stdout_payload = json.loads(result.stdout)
        assert stdout_payload["network_io"] == "not_executed"
        assert stdout_payload["destructive_actions"] == "not_executed"
        assert stdout_payload["secrets_printed"] is False
        assert stdout_payload["armed_rows"] == 1
        assert stdout_payload["blocked_rows"] == json.loads(packet_path.read_text())["item_count"] - 1

        plan_text = output_json.read_text()
        assert "op://protein-ai" not in plan_text
        assert "<secret-reference-provided>" in plan_text
        plan_payload = json.loads(plan_text)
        by_name = {item["name"]: item for item in plan_payload["items"]}
        assert by_name["admin_authenticated_screenshots"]["armed"] is True
        assert "FRONTEND_BASE_URL=" in by_name["admin_authenticated_screenshots"]["command_plan"][1]
        assert "remote_pytest_runner" not in by_name
        assert by_name["formal_domain_https"]["armed"] is False
        assert "formal_domain" in by_name["formal_domain_https"]["missing_fields"]
        assert "op://protein-ai" not in output_md.read_text()

    def test_remaining_backlog_operator_dispatch_checklist_is_role_oriented_and_read_only(self, tmp_path):
        packet_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_external_input_packet.py"
        validator = PROJECT_ROOT / "scripts" / "validate_remaining_backlog_external_inputs.py"
        plan_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_gate_execution_plan.py"
        dispatch_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_operator_dispatch_checklist.py"
        dispatch_validator = PROJECT_ROOT / "scripts" / "validate_remaining_backlog_operator_dispatch_checklist.py"
        makefile = PROJECT_ROOT / "Makefile"
        packet_path = tmp_path / "packet.json"
        packet_md_path = tmp_path / "packet.md"
        values_path = tmp_path / "values.json"
        validation_path = tmp_path / "validation.json"
        plan_path = tmp_path / "plan.json"
        plan_md_path = tmp_path / "plan.md"
        dispatch_path = tmp_path / "dispatch.json"
        dispatch_md_path = tmp_path / "dispatch.md"

        assert dispatch_script.exists()
        assert dispatch_validator.exists()
        make_content = makefile.read_text()
        assert "remaining-backlog-dispatch-checklist" in make_content
        assert "remaining-backlog-dispatch-checklist-validate" in make_content

        subprocess.run(
            [
                sys.executable,
                str(packet_script),
                "--output-json",
                str(packet_path),
                "--output-md",
                str(packet_md_path),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(validator),
                "--packet",
                str(packet_path),
                "--values",
                str(values_path),
                "--output",
                str(validation_path),
                "--write-template",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(plan_script),
                "--packet",
                str(packet_path),
                "--values",
                str(values_path),
                "--output-json",
                str(plan_path),
                "--output-md",
                str(plan_md_path),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        result = subprocess.run(
            [
                sys.executable,
                str(dispatch_script),
                "--packet",
                str(packet_path),
                "--validation",
                str(validation_path),
                "--execution-plan",
                str(plan_path),
                "--output-json",
                str(dispatch_path),
                "--output-md",
                str(dispatch_md_path),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        stdout_payload = json.loads(result.stdout)
        assert stdout_payload["network_io"] == "not_executed"
        assert stdout_payload["destructive_actions"] == "not_executed"
        assert stdout_payload["secrets_printed"] is False
        assert stdout_payload["live_commands_included"] is False
        expected_count = json.loads(packet_path.read_text())["item_count"]
        assert stdout_payload["item_count"] == expected_count
        assert stdout_payload["blocked_rows"] == expected_count
        assert stdout_payload["armed_rows"] == 0

        payload = json.loads(dispatch_path.read_text())
        assert payload["mode"] == "read_only_remaining_backlog_operator_dispatch_checklist"
        assert payload["lane_count"] == len(payload["lanes"])
        assert payload["lane_count"] >= 5
        lanes = {lane["lane"]: lane for lane in payload["lanes"]}
        assert "infra_dns_tls" in lanes
        assert "md_runtime" in lanes
        assert set(lanes["md_runtime"]["items"]) == {"gpu_gromacs_md_live", "md_blackbox_live_e2e"}
        by_name = {item["name"]: item for item in payload["items"]}
        assert by_name["admin_authenticated_screenshots"]["lane"] == "qa_admin"
        assert by_name["admin_authenticated_screenshots"]["live_command_plan_included"] is False
        assert "SCREENSHOT_PASSWORD_secret_reference" in by_name["admin_authenticated_screenshots"]["secret_reference_fields"]
        assert "op://protein-ai" not in dispatch_path.read_text()
        assert "op://protein-ai" not in dispatch_md_path.read_text()

        validation_result = subprocess.run(
            [
                sys.executable,
                str(dispatch_validator),
                "--checklist",
                str(dispatch_path),
                "--packet",
                str(packet_path),
                "--validation",
                str(validation_path),
                "--execution-plan",
                str(plan_path),
                "--output",
                str(tmp_path / "dispatch-validation.json"),
                "--require-success",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        validation_stdout = json.loads(validation_result.stdout)
        assert validation_stdout["success"] is True
        assert validation_stdout["failure_count"] == 0
        assert validation_stdout["source_bound_current"] is True

        tampered_payload = json.loads(dispatch_path.read_text())
        tampered_payload["items"][0]["leaked_secret_reference"] = "op://protein-ai/admin/password"
        tampered_path = tmp_path / "dispatch-tampered.json"
        tampered_path.write_text(json.dumps(tampered_payload, ensure_ascii=False), encoding="utf-8")
        tampered_result = subprocess.run(
            [
                sys.executable,
                str(dispatch_validator),
                "--checklist",
                str(tampered_path),
                "--packet",
                str(packet_path),
                "--validation",
                str(validation_path),
                "--execution-plan",
                str(plan_path),
                "--output",
                str(tmp_path / "dispatch-tampered-validation.json"),
                "--require-success",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert tampered_result.returncode == 1
        tampered_stdout = json.loads(tampered_result.stdout)
        assert tampered_stdout["success"] is False
        assert tampered_stdout["failure_count"] >= 1

    def test_remaining_backlog_operator_packet_manifest_tracks_packet_freshness(self, tmp_path):
        readiness_script = PROJECT_ROOT / "scripts" / "check_remaining_backlog_readiness.py"
        packet_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_external_input_packet.py"
        validator = PROJECT_ROOT / "scripts" / "validate_remaining_backlog_external_inputs.py"
        plan_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_gate_execution_plan.py"
        dispatch_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_operator_dispatch_checklist.py"
        dispatch_validator = PROJECT_ROOT / "scripts" / "validate_remaining_backlog_operator_dispatch_checklist.py"
        manifest_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_operator_packet_manifest.py"
        summary_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_go_no_go_summary.py"
        tickets_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_execution_tickets.py"
        tickets_validator = PROJECT_ROOT / "scripts" / "validate_remaining_backlog_execution_tickets.py"
        p0_status_export_script = PROJECT_ROOT / "scripts" / "build_p0_p4_status_export.py"
        bridge_script = PROJECT_ROOT / "scripts" / "build_p0_p4_backlog_ticket_bridge.py"
        bridge_validator = PROJECT_ROOT / "scripts" / "validate_p0_p4_backlog_ticket_bridge.py"
        makefile = PROJECT_ROOT / "Makefile"
        manuals = tmp_path / "docs" / "manuals"
        scripts_dir = tmp_path / "scripts"
        manuals.mkdir(parents=True)
        scripts_dir.mkdir()

        packet_json = manuals / "remaining-backlog-external-input-packet.json"
        packet_md = manuals / "remaining-backlog-external-input-packet.md"
        values_json = manuals / "remaining-backlog-external-input-values.template.json"
        validation_json = manuals / "remaining-backlog-external-input-validation-report.json"
        plan_json = manuals / "remaining-backlog-gate-execution-plan.json"
        plan_md = manuals / "remaining-backlog-gate-execution-plan.md"
        dispatch_json = manuals / "remaining-backlog-operator-dispatch-checklist.json"
        dispatch_md = manuals / "remaining-backlog-operator-dispatch-checklist.md"
        dispatch_validation = manuals / "remaining-backlog-operator-dispatch-checklist-validation-report.json"
        p0_status_json = manuals / "p0-p4-status-export.json"
        p0_status_md = manuals / "p0-p4-status-export.md"
        bridge_json = manuals / "p0-p4-backlog-ticket-bridge.json"
        bridge_md = manuals / "p0-p4-backlog-ticket-bridge.md"
        bridge_validation = manuals / "p0-p4-backlog-ticket-bridge-validation-report.json"
        manifest_json = manuals / "remaining-backlog-operator-packet-manifest.json"
        summary_json = manuals / "remaining-backlog-go-no-go-summary.json"
        summary_md = manuals / "remaining-backlog-go-no-go-summary.md"
        tickets_json = manuals / "remaining-backlog-execution-tickets.json"
        tickets_md = manuals / "remaining-backlog-execution-tickets.md"
        tickets_validation = manuals / "remaining-backlog-execution-tickets-validation-report.json"

        make_content = makefile.read_text()
        assert "remaining-backlog-operator-packet-manifest" in make_content
        assert "remaining-backlog-operator-packet-manifest-check" in make_content
        assert "remaining-backlog-execution-tickets" in make_content
        assert "remaining-backlog-execution-tickets-validate" in make_content
        refresh_target = make_content.split("remaining-backlog-operator-packet-refresh:\n", 1)[1].split("\n\np2-p3-p4-roadmap:", 1)[0]
        refresh_commands = [
            line.removeprefix("\t$(MAKE) ")
            for line in refresh_target.splitlines()
            if line.startswith("\t$(MAKE) ")
        ]
        refresh_steps = [
            "p2-p3-p4-roadmap",
            "p0-p4-gap-audit",
            "p0-p4-status-export",
            "remaining-backlog-input-template",
            "remaining-backlog-readiness-json",
            "remaining-backlog-input-packet",
            "remaining-backlog-input-validate",
            "remaining-backlog-execution-plan",
            "remaining-backlog-dispatch-checklist",
            "remaining-backlog-dispatch-checklist-validate",
            "remaining-backlog-operator-packet-manifest",
            "remaining-backlog-go-no-go-summary",
            "remaining-backlog-execution-tickets",
            "remaining-backlog-execution-tickets-validate",
            "p0-p4-backlog-ticket-bridge",
            "p0-p4-backlog-ticket-bridge-validate",
            "remaining-backlog-operator-packet-manifest",
            "remaining-backlog-operator-packet-manifest-check",
        ]
        assert refresh_commands == refresh_steps

        subprocess.run(
            [
                sys.executable,
                str(packet_script),
                "--output-json",
                str(packet_json),
                "--output-md",
                str(packet_md),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(validator),
                "--packet",
                str(packet_json),
                "--values",
                str(values_json),
                "--output",
                str(validation_json),
                "--write-template",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(plan_script),
                "--packet",
                str(packet_json),
                "--values",
                str(values_json),
                "--output-json",
                str(plan_json),
                "--output-md",
                str(plan_md),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(dispatch_script),
                "--packet",
                str(packet_json),
                "--validation",
                str(validation_json),
                "--execution-plan",
                str(plan_json),
                "--output-json",
                str(dispatch_json),
                "--output-md",
                str(dispatch_md),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(dispatch_validator),
                "--checklist",
                str(dispatch_json),
                "--packet",
                str(packet_json),
                "--validation",
                str(validation_json),
                "--execution-plan",
                str(plan_json),
                "--output",
                str(dispatch_validation),
                "--require-success",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        for placeholder in [p0_status_json, p0_status_md, bridge_json, bridge_md, bridge_validation]:
            placeholder.write_text("{}\n", encoding="utf-8")

        for source in [
            readiness_script,
            packet_script,
            validator,
            plan_script,
            dispatch_script,
            dispatch_validator,
            manifest_script,
            summary_script,
            tickets_script,
            tickets_validator,
            p0_status_export_script,
            bridge_script,
            bridge_validator,
        ]:
            (scripts_dir / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        tmp_summary_script = scripts_dir / summary_script.name
        tmp_tickets_script = scripts_dir / tickets_script.name
        tmp_tickets_validator = scripts_dir / tickets_validator.name
        tmp_manifest_script = scripts_dir / manifest_script.name

        subprocess.run(
            [
                sys.executable,
                str(tmp_summary_script),
                "--input-validation",
                str(validation_json),
                "--execution-plan",
                str(plan_json),
                "--dispatch-checklist",
                str(dispatch_json),
                "--dispatch-validation",
                str(dispatch_validation),
                "--operator-manifest",
                str(manifest_json),
                "--output-json",
                str(summary_json),
                "--output-md",
                str(summary_md),
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        tickets_result = subprocess.run(
            [
                sys.executable,
                str(tmp_tickets_script),
                "--dispatch",
                str(dispatch_json),
                "--go-no-go",
                str(summary_json),
                "--output-json",
                str(tickets_json),
                "--output-md",
                str(tickets_md),
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        tickets_stdout = json.loads(tickets_result.stdout)
        expected_count = json.loads(packet_json.read_text())["item_count"]
        assert tickets_stdout["ticket_count"] == expected_count
        assert tickets_stdout["blocked_ticket_count"] == expected_count
        assert tickets_stdout["armed_ticket_count"] == 0
        assert tickets_stdout["live_gate_execution_allowed"] is False
        tickets_payload = json.loads(tickets_json.read_text(encoding="utf-8"))
        assert tickets_payload["mode"] == "read_only_remaining_backlog_execution_tickets"
        assert tickets_payload["network_io"] == "not_executed"
        assert tickets_payload["destructive_actions"] == "not_executed"
        assert tickets_payload["secrets_printed"] is False
        assert tickets_payload["command_execution_allowed"] is False
        assert tickets_payload["live_gate_execution_allowed"] is False
        assert {ticket["name"] for ticket in tickets_payload["tickets"]} >= {
            "formal_domain_https",
            "gpu_gromacs_md_live",
            "md_blackbox_live_e2e",
            "oss_minio_live_e2e",
        }
        tickets_validation_result = subprocess.run(
            [
                sys.executable,
                str(tmp_tickets_validator),
                "--tickets",
                str(tickets_json),
                "--dispatch",
                str(dispatch_json),
                "--go-no-go",
                str(summary_json),
                "--output",
                str(tickets_validation),
                "--require-success",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        tickets_validation_stdout = json.loads(tickets_validation_result.stdout)
        assert tickets_validation_stdout["success"] is True
        assert tickets_validation_stdout["failure_count"] == 0
        assert tickets_validation_stdout["source_bound_current"] is True

        tampered_tickets = json.loads(tickets_json.read_text(encoding="utf-8"))
        tampered_tickets["tickets"][0]["leaked_secret_reference"] = "op://protein-ai/admin/password"
        tampered_tickets_path = manuals / "remaining-backlog-execution-tickets-tampered.json"
        tampered_tickets_path.write_text(json.dumps(tampered_tickets, ensure_ascii=False), encoding="utf-8")
        tampered_tickets_result = subprocess.run(
            [
                sys.executable,
                str(tmp_tickets_validator),
                "--tickets",
                str(tampered_tickets_path),
                "--dispatch",
                str(dispatch_json),
                "--go-no-go",
                str(summary_json),
                "--output",
                str(manuals / "remaining-backlog-execution-tickets-tampered-validation-report.json"),
                "--require-success",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert tampered_tickets_result.returncode == 1
        tampered_tickets_stdout = json.loads(tampered_tickets_result.stdout)
        assert tampered_tickets_stdout["success"] is False
        assert tampered_tickets_stdout["failure_count"] >= 1

        result = subprocess.run(
            [
                sys.executable,
                str(tmp_manifest_script),
                "--output",
                str(manifest_json),
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        stdout_payload = json.loads(result.stdout)
        assert stdout_payload["status"] == "ready-for-operator-review"
        assert stdout_payload["file_count"] == 32
        assert stdout_payload["missing_files"] == []
        assert stdout_payload["dispatch_validation_success"] is True
        assert stdout_payload["source_bound_current"] is True

        manifest_payload = json.loads(manifest_json.read_text())
        assert manifest_payload["mode"] == "read_only_remaining_backlog_operator_packet_manifest"
        assert manifest_payload["network_io"] == "not_executed"
        assert manifest_payload["destructive_actions"] == "not_executed"
        assert manifest_payload["secrets_printed"] is False
        assert manifest_payload["live_gate_execution_allowed"] is False
        assert manifest_payload["summary"]["status"] == "ready-for-operator-review"
        assert len([row for row in manifest_payload["files"] if row["sha256"]]) == 32

        check_result = subprocess.run(
            [
                sys.executable,
                str(tmp_manifest_script),
                "--output",
                str(manifest_json),
                "--check",
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        check_payload = json.loads(check_result.stdout)
        assert check_payload["status"] == "current"
        assert check_payload["stale_sections"] == []

        dispatch_md.write_text(dispatch_md.read_text(encoding="utf-8") + "\n# stale\n", encoding="utf-8")
        stale_result = subprocess.run(
            [
                sys.executable,
                str(tmp_manifest_script),
                "--output",
                str(manifest_json),
                "--check",
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert stale_result.returncode == 1
        stale_payload = json.loads(stale_result.stdout)
        assert stale_payload["status"] == "stale-or-missing"
        assert "files" in stale_payload["stale_sections"]

    def test_remaining_backlog_go_no_go_summary_defers_until_inputs_are_ready(self, tmp_path):
        readiness_script = PROJECT_ROOT / "scripts" / "check_remaining_backlog_readiness.py"
        packet_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_external_input_packet.py"
        validator = PROJECT_ROOT / "scripts" / "validate_remaining_backlog_external_inputs.py"
        plan_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_gate_execution_plan.py"
        dispatch_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_operator_dispatch_checklist.py"
        dispatch_validator = PROJECT_ROOT / "scripts" / "validate_remaining_backlog_operator_dispatch_checklist.py"
        manifest_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_operator_packet_manifest.py"
        summary_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_go_no_go_summary.py"
        tickets_script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_execution_tickets.py"
        tickets_validator = PROJECT_ROOT / "scripts" / "validate_remaining_backlog_execution_tickets.py"
        p0_status_export_script = PROJECT_ROOT / "scripts" / "build_p0_p4_status_export.py"
        bridge_script = PROJECT_ROOT / "scripts" / "build_p0_p4_backlog_ticket_bridge.py"
        bridge_validator = PROJECT_ROOT / "scripts" / "validate_p0_p4_backlog_ticket_bridge.py"
        makefile = PROJECT_ROOT / "Makefile"
        manuals = tmp_path / "docs" / "manuals"
        scripts_dir = tmp_path / "scripts"
        manuals.mkdir(parents=True)
        scripts_dir.mkdir()

        packet_json = manuals / "remaining-backlog-external-input-packet.json"
        packet_md = manuals / "remaining-backlog-external-input-packet.md"
        values_json = manuals / "remaining-backlog-external-input-values.template.json"
        validation_json = manuals / "remaining-backlog-external-input-validation-report.json"
        plan_json = manuals / "remaining-backlog-gate-execution-plan.json"
        plan_md = manuals / "remaining-backlog-gate-execution-plan.md"
        dispatch_json = manuals / "remaining-backlog-operator-dispatch-checklist.json"
        dispatch_md = manuals / "remaining-backlog-operator-dispatch-checklist.md"
        dispatch_validation = manuals / "remaining-backlog-operator-dispatch-checklist-validation-report.json"
        p0_status_json = manuals / "p0-p4-status-export.json"
        p0_status_md = manuals / "p0-p4-status-export.md"
        bridge_json = manuals / "p0-p4-backlog-ticket-bridge.json"
        bridge_md = manuals / "p0-p4-backlog-ticket-bridge.md"
        bridge_validation = manuals / "p0-p4-backlog-ticket-bridge-validation-report.json"
        manifest_json = manuals / "remaining-backlog-operator-packet-manifest.json"
        summary_json = manuals / "remaining-backlog-go-no-go-summary.json"
        summary_md = manuals / "remaining-backlog-go-no-go-summary.md"
        tickets_json = manuals / "remaining-backlog-execution-tickets.json"
        tickets_md = manuals / "remaining-backlog-execution-tickets.md"
        tickets_validation = manuals / "remaining-backlog-execution-tickets-validation-report.json"

        make_content = makefile.read_text()
        assert "remaining-backlog-go-no-go-summary" in make_content
        assert "remaining-backlog-execution-tickets" in make_content
        assert "remaining-backlog-execution-tickets-validate" in make_content

        subprocess.run(
            [
                sys.executable,
                str(packet_script),
                "--output-json",
                str(packet_json),
                "--output-md",
                str(packet_md),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(validator),
                "--packet",
                str(packet_json),
                "--values",
                str(values_json),
                "--output",
                str(validation_json),
                "--write-template",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(plan_script),
                "--packet",
                str(packet_json),
                "--values",
                str(values_json),
                "--output-json",
                str(plan_json),
                "--output-md",
                str(plan_md),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(dispatch_script),
                "--packet",
                str(packet_json),
                "--validation",
                str(validation_json),
                "--execution-plan",
                str(plan_json),
                "--output-json",
                str(dispatch_json),
                "--output-md",
                str(dispatch_md),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(dispatch_validator),
                "--checklist",
                str(dispatch_json),
                "--packet",
                str(packet_json),
                "--validation",
                str(validation_json),
                "--execution-plan",
                str(plan_json),
                "--output",
                str(dispatch_validation),
                "--require-success",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        for placeholder in [p0_status_json, p0_status_md, bridge_json, bridge_md, bridge_validation]:
            placeholder.write_text("{}\n", encoding="utf-8")

        for source in [
            readiness_script,
            packet_script,
            validator,
            plan_script,
            dispatch_script,
            dispatch_validator,
            manifest_script,
            summary_script,
            tickets_script,
            tickets_validator,
            p0_status_export_script,
            bridge_script,
            bridge_validator,
        ]:
            (scripts_dir / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        tmp_manifest_script = scripts_dir / manifest_script.name
        tmp_summary_script = scripts_dir / summary_script.name
        tmp_tickets_script = scripts_dir / tickets_script.name
        tmp_tickets_validator = scripts_dir / tickets_validator.name

        summary_result = subprocess.run(
            [
                sys.executable,
                str(tmp_summary_script),
                "--input-validation",
                str(validation_json),
                "--execution-plan",
                str(plan_json),
                "--dispatch-validation",
                str(dispatch_validation),
                "--operator-manifest",
                str(manifest_json),
                "--output-json",
                str(summary_json),
                "--output-md",
                str(summary_md),
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        summary_payload = json.loads(summary_result.stdout)
        summary_report = json.loads(summary_json.read_text(encoding="utf-8"))
        packet_payload = json.loads(packet_json.read_text(encoding="utf-8"))
        pending_count = packet_payload["item_count"]
        p1_items = packet_payload["priority_summary"]["P1"]["items"]
        assert summary_payload["decision"] == "defer_waiting_for_external_inputs"
        assert summary_payload["ready_for_live_gate_execution"] is False
        assert summary_payload["missing_input_rows"] == pending_count
        assert summary_payload["armed_rows"] == 0
        assert summary_payload["blocked_rows"] == pending_count
        assert summary_payload["priority_summary"]["P0"]["item_count"] == 4
        assert summary_payload["priority_summary"]["P0"]["blocked_rows"] == 4
        assert summary_payload["priority_summary"]["P0"]["items"] == [
            "formal_domain_https",
            "gpu_gromacs_md_live",
            "md_blackbox_live_e2e",
            "oss_minio_live_e2e",
        ]
        assert summary_payload["priority_summary"]["P1"]["item_count"] == len(p1_items)
        assert summary_payload["priority_summary"]["P1"]["blocked_rows"] == len(p1_items)
        assert summary_payload["priority_summary"]["P1"]["items"] == p1_items
        assert summary_payload["operator_packet_manifest"]["current"] is False
        assert "external_input_validation" in summary_payload["blocking_items"]
        assert "gate_execution_plan" in summary_payload["blocking_items"]
        assert summary_report["mode"] == "read_only_remaining_backlog_go_no_go_summary"
        assert summary_report["network_io"] == "not_executed"
        assert summary_report["destructive_actions"] == "not_executed"
        assert summary_report["secrets_printed"] is False
        assert summary_report["live_gate_execution_allowed"] is False
        summary_md_text = summary_md.read_text(encoding="utf-8")
        assert "## Priority Summary" in summary_md_text
        assert "formal_domain_https" in summary_md_text
        assert "operator_packet_manifest" in summary_md_text

        tickets_result = subprocess.run(
            [
                sys.executable,
                str(tmp_tickets_script),
                "--dispatch",
                str(dispatch_json),
                "--go-no-go",
                str(summary_json),
                "--output-json",
                str(tickets_json),
                "--output-md",
                str(tickets_md),
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        tickets_payload = json.loads(tickets_result.stdout)
        assert tickets_payload["ticket_count"] == pending_count
        assert tickets_payload["blocked_ticket_count"] == pending_count
        assert tickets_payload["armed_ticket_count"] == 0
        assert tickets_payload["priority_summary"]["P0"]["ticket_count"] == 4
        assert tickets_payload["priority_summary"]["P0"]["blocked_ticket_count"] == 4
        assert tickets_payload["priority_summary"]["P1"]["ticket_count"] == len(p1_items)
        assert tickets_payload["priority_summary"]["P1"]["blocked_ticket_count"] == len(p1_items)
        assert tickets_payload["live_gate_execution_allowed"] is False
        tickets_report = json.loads(tickets_json.read_text(encoding="utf-8"))
        assert tickets_report["priority_summary"]["P0"]["items"] == [
            "formal_domain_https",
            "gpu_gromacs_md_live",
            "md_blackbox_live_e2e",
            "oss_minio_live_e2e",
        ]
        assert "## Priority Summary" in tickets_md.read_text(encoding="utf-8")
        tickets_validation_result = subprocess.run(
            [
                sys.executable,
                str(tmp_tickets_validator),
                "--tickets",
                str(tickets_json),
                "--dispatch",
                str(dispatch_json),
                "--go-no-go",
                str(summary_json),
                "--output",
                str(tickets_validation),
                "--require-success",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        tickets_validation_payload = json.loads(tickets_validation_result.stdout)
        assert tickets_validation_payload["success"] is True
        assert tickets_validation_payload["failure_count"] == 0

        subprocess.run(
            [
                sys.executable,
                str(tmp_manifest_script),
                "--output",
                str(manifest_json),
                "--json",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_lipase_db_readonly_service_and_api_are_wired(self):
        config = PROJECT_ROOT / "backend" / "app" / "core" / "config.py"
        service = PROJECT_ROOT / "backend" / "app" / "services" / "lipase_db_status.py"
        curation_service = PROJECT_ROOT / "backend" / "app" / "services" / "lipase_curation.py"
        curation_model = PROJECT_ROOT / "backend" / "app" / "models" / "lipase_curation.py"
        data_api = PROJECT_ROOT / "backend" / "app" / "api" / "data.py"
        frontend_api = PROJECT_ROOT / "frontend" / "src" / "lib" / "api.ts"
        frontend_report = PROJECT_ROOT / "frontend" / "src" / "lib" / "report.ts"
        data_page = PROJECT_ROOT / "frontend" / "src" / "pages" / "DataBrowser.tsx"
        pdb_page = PROJECT_ROOT / "frontend" / "src" / "pages" / "PDBUploadPage.tsx"
        project_detail_page = PROJECT_ROOT / "frontend" / "src" / "pages" / "ProjectDetailPage.tsx"
        project_list_page = PROJECT_ROOT / "frontend" / "src" / "pages" / "ProjectListPage.tsx"
        pdb_card = PROJECT_ROOT / "frontend" / "src" / "components" / "analysis" / "PDBAnalysisCard.tsx"
        mutation_score_card = PROJECT_ROOT / "frontend" / "src" / "components" / "analysis" / "MutationScoreCard.tsx"
        mutation_priority_score_tool = PROJECT_ROOT / "backend" / "app" / "tools" / "mutation_priority_score.py"

        assert "LIPASE_DB_PATH" in config.read_text()
        service_content = service.read_text()
        curation_service_content = curation_service.read_text()
        curation_model_content = curation_model.read_text()
        assert "mode=ro" in service_content
        assert "immutable=1" in service_content
        assert "collect_lipase_db_status" in service_content
        assert "list_lipase_papers" in service_content
        assert "search_lipase_evidence" in service_content
        assert "build_lipase_evidence_context" in service_content
        assert "LipaseCurationRecord" in curation_model_content
        assert "LipaseCurationBatch" in curation_model_content
        assert "create_lipase_curation_record" in curation_service_content
        assert "create_lipase_curation_batch" in curation_service_content
        assert "publish_lipase_curation_batch" in curation_service_content
        assert "update_lipase_curation_review" in curation_service_content
        data_api_content = data_api.read_text()
        assert '"/lipase/status"' in data_api_content
        assert '"/lipase/search"' in data_api_content
        assert '"/lipase/evidence-context"' in data_api_content
        assert '"/lipase/papers"' in data_api_content
        assert '"/lipase/papers/{paper_key}"' in data_api_content
        assert '"/lipase/variants"' in data_api_content
        assert '"/lipase/gaps"' in data_api_content
        assert '"/lipase/curation-records"' in data_api_content
        assert '"/lipase/curation-records/{record_id}/review"' in data_api_content
        assert '"/lipase/curation-batches"' in data_api_content
        assert '"/lipase/curation-batches/{batch_id}/publish"' in data_api_content
        assert '"/experiment-feedback"' in data_api_content
        assert '"/experiment-feedback/summary"' in data_api_content
        frontend_api_content = frontend_api.read_text()
        data_page_content = data_page.read_text()
        pdb_page_content = pdb_page.read_text()
        project_detail_content = project_detail_page.read_text()
        project_list_content = project_list_page.read_text()
        pdb_card_content = pdb_card.read_text()
        mutation_score_card_content = mutation_score_card.read_text()
        mutation_priority_score_content = mutation_priority_score_tool.read_text()
        assert "getLipaseDbStatus" in frontend_api_content
        assert "getLipasePaperDetail" in frontend_api_content
        assert "getLipaseEvidenceContext" in frontend_api_content
        assert "submitLipaseCurationRecord" in frontend_api_content
        assert "listLipaseCurationRecords" in frontend_api_content
        assert "reviewLipaseCurationRecord" in frontend_api_content
        assert "createLipaseCurationBatch" in frontend_api_content
        assert "publishLipaseCurationBatch" in frontend_api_content
        assert "searchLipaseEvidence" in frontend_api_content
        assert "submitExperimentFeedback" in frontend_api_content
        assert "listExperimentFeedback" in frontend_api_content
        assert "summarizeExperimentFeedback" in frontend_api_content
        assert "planExperimentFeedbackIteration" in frontend_api_content
        assert "runMutationEpistasisCheck" in frontend_api_content
        assert "required_action_contract" in frontend_api_content
        assert "p4_closed_loop_readiness" in frontend_api_content
        report_content = frontend_report.read_text()
        assert "renderMutationEpistasis" in report_content
        assert "mutation_epistasis" in report_content
        assert "mutation_epistasis_check_report_contract_v1" in report_content
        assert "distance_source" in report_content
        assert "must_not_claim" in report_content
        assert "renderAnalysisScope" in report_content
        assert "Analysis Scope" in report_content
        assert "analysis_scope" in report_content
        assert "schema_version" in report_content
        assert "hash_input_policy" in report_content
        assert "scientific_boundary" in report_content
        assert "generated_at" in report_content
        assert "scope_hash" in report_content
        assert "defaultReportFilename" in report_content
        assert "scope-${scopeHash}" in report_content
        assert "filename || defaultReportFilename(type, data)" in report_content
        assert "feedback_record_fingerprint" in report_content
        assert "validated_mutation_fingerprint" in report_content
        assert "renderProjectDbtlTrace" in report_content
        assert "project_dbtl_trace" in report_content
        assert "Project Memory Readiness" in report_content
        assert "dbtl_project_memory_readiness_v1" in report_content
        assert "projectMemoryReadiness" in report_content
        assert "formal_dbtl_tables_exist" in report_content
        assert "Feedback Readiness" in report_content
        assert "dbtl_feedback_readiness_summary_v1" in report_content
        assert "feedbackReadiness" in report_content
        assert "wet_lab_validated_by_trace_summary" in report_content
        assert "dbtl_required_action_contract_v1" in report_content
        assert "summary.required_action_contract" in report_content
        assert "item.category" in report_content
        assert "item.priority" in report_content
        assert "P4 Closed Loop Readiness" in report_content
        assert "p4_closed_loop_readiness_v1" in report_content
        assert "p4_active_learning_batch_contract_v1" in report_content
        assert "p4_model_calibration_registry_contract_v1" in report_content
        assert "p4_manufacturing_constraint_schema_v1" in report_content
        assert "active_learning_batch_contract" in report_content
        assert "summary.p4_closed_loop_readiness" in report_content
        assert "model_retrained" in report_content
        assert "renderCandidateFeatureCompleteness" in report_content
        assert "candidate_feature_completeness_v1" in report_content
        assert "p2_candidate_readiness_summary_v1" in report_content
        assert "p2_candidate_readiness_summary" in report_content
        assert "p2_objective_score_readiness_summary_v1" in report_content
        assert "p2_objective_score_readiness_summary" in report_content
        assert "experiment_design_schedulability_policy_v1" in report_content
        assert "Experiment Design Policy" in report_content
        assert "blocked_rows_remain_traceable" in report_content
        assert "top_unknown_components" in report_content
        assert "Objective Readiness Summary" in report_content
        assert "top_missing_feature_reasons" in report_content
        assert "feature_completeness" in report_content
        assert "missing_feature_reasons" in report_content
        assert "P2 Evidence" in report_content
        assert "CandidateFeatureCompleteness" in mutation_score_card_content
        assert "candidate_feature_completeness_v1" in mutation_score_card_content
        assert "p2_candidate_readiness_summary_v1" in mutation_score_card_content
        assert "p2_candidate_readiness_summary" in mutation_score_card_content
        assert "p2_objective_score_readiness_summary_v1" in mutation_score_card_content
        assert "p2_objective_score_readiness_summary" in mutation_score_card_content
        assert "experiment_design_schedulability_policy_v1" in mutation_score_card_content
        assert "experimentDesignPolicy" in mutation_score_card_content
        assert "排单门控" in mutation_score_card_content
        assert "top_unknown_components" in mutation_score_card_content
        assert "目标分量 readiness" in mutation_score_card_content
        assert "top_missing_feature_reasons" in mutation_score_card_content
        assert "feature_completeness" in mutation_score_card_content
        assert "missing_feature_reasons" in mutation_score_card_content
        assert "getMissingFeatureReasons" in mutation_score_card_content
        assert "P2证据覆盖" in mutation_score_card_content
        assert "pocket_channel_interface_status" in mutation_score_card_content
        assert "_p2_candidate_readiness_summary" in mutation_priority_score_content
        assert "p2_candidate_readiness_summary_v1" in mutation_priority_score_content
        assert "_p2_objective_score_readiness_summary" in mutation_priority_score_content
        assert "p2_objective_score_readiness_summary_v1" in mutation_priority_score_content
        assert "_is_experiment_design_schedulable" in mutation_priority_score_content
        assert "experiment_design_schedulability_policy_v1" in mutation_priority_score_content
        assert "blocked_rows_remain_traceable" in mutation_priority_score_content
        assert "show_unknown_objective_components_before_candidate_claims" in mutation_priority_score_content
        assert "show_missing_p2_evidence_before_candidate_claims" in mutation_priority_score_content
        assert "wet_lab_validated_candidate_from_completeness_summary" in mutation_priority_score_content
        assert "renderFeedbackIterationPlan" in report_content
        assert "feedback_iteration_plan" in report_content
        assert "next_round_combination_evidence_contract_v1" in report_content
        assert "must_not_claim_training_or_wet_lab_validation" in report_content
        assert "LipaseDbCard" in data_page_content
        assert "LipaseEvidenceBrowser" in data_page_content
        assert "LipasePaperDetailPanel" in data_page_content
        assert "ExperimentFeedbackPanel" in data_page_content
        assert "湿实验反馈录入" in data_page_content
        assert "运行组合上位性检查" in data_page_content
        assert "生成下一轮设计预览" in data_page_content
        assert "按项目 ID 过滤" in data_page_content
        assert "全部可见项目" in data_page_content
        assert "当前范围:" in data_page_content
        assert "api.getProjects()" in data_page_content
        assert "project_id" in data_page_content
        assert "project_id: projectFilter.trim() || null" in data_page_content
        assert "项目 ${selectedProject ? selectedProject.name : projectFilter.trim() || '未绑定'}" in data_page_content
        assert "setEpistasisResult(null)" in data_page_content
        assert "setIterationPlan(null)" in data_page_content
        assert "if (loading || validatedMutations.length < 2) return" in data_page_content
        assert "if (loading || records.length === 0) return" in data_page_content
        assert "disabled={loading || validatedMutations.length < 2 || epistasisLoading}" in data_page_content
        assert "disabled={loading || records.length === 0 || iterationPlanLoading}" in data_page_content
        assert "FeedbackAnalysisScope" in data_page_content
        assert "buildAnalysisScopeSnapshot" in data_page_content
        assert "stableScopeHash" in data_page_content
        assert "schema_version: 'feedback_analysis_scope_v1'" in data_page_content
        assert "hash_input_policy: 'stable_json_scope_without_generated_at_or_scope_hash'" in data_page_content
        assert "scientific_boundary: 'audit_metadata_not_scientific_or_wet_lab_evidence'" in data_page_content
        assert "Scope Schema" in data_page_content
        assert "Hash Policy" in data_page_content
        assert "Scope Boundary" in data_page_content
        assert "反馈池指纹" in data_page_content
        assert "单点池指纹" in data_page_content
        assert "break-words font-medium" in data_page_content
        assert "generated_at: new Date().toISOString()" in data_page_content
        assert "scope_hash: stableScopeHash(scopeKey)" in data_page_content
        assert "feedbackRecordFingerprint" in data_page_content
        assert "validatedMutationFingerprint" in data_page_content
        assert "Array.from(new Set(validatedFeedbackRecords.map((record) => record.mutations[0]).filter(Boolean))).sort((left, right) => left.localeCompare(right))" in data_page_content
        assert "records.map((record) => String(record.id)).sort((left, right) => left.localeCompare(right)).join('|')" in data_page_content
        assert "feedback_record_fingerprint" in data_page_content
        assert "validated_mutation_fingerprint" in data_page_content
        assert "analysisScopeKeyRef.current !== requestScopeKey" in data_page_content
        assert "analysis_scope: scope" in data_page_content
        assert "AnalysisScopeSummary" in data_page_content
        assert "epistasisDistanceGraph" in data_page_content
        assert "epistasisDistances" in data_page_content
        assert "epistasisMechanismTags" in data_page_content
        assert "epistasisSameRegions" in data_page_content
        assert "IterationPlanCard" in data_page_content
        assert "combination_evidence_contract" in data_page_content
        assert "downloadReport('feedback_iteration_plan'" in data_page_content
        assert "EpistasisResultCard" in data_page_content
        assert "downloadReport('mutation_epistasis'" in data_page_content
        assert "结构距离" in data_page_content
        assert "机制标签" in data_page_content
        assert "同一区域" in data_page_content
        assert "parseStructuralDistances" in data_page_content
        assert "parseMechanismTags" in data_page_content
        assert "parseSameRegionGroups" in data_page_content
        assert "combination_evidence_contract" in project_detail_content
        assert "Combination contract" in project_detail_content
        assert "downloadReport('project_dbtl_trace'" in project_detail_content
        assert "ProjectMemoryReadinessPanel" in project_detail_content
        assert "Project Memory Readiness" in project_detail_content
        assert "dbtl_project_memory_readiness_v1" in project_detail_content
        assert "dbtlTrace.trace_summary.project_memory_readiness" in project_detail_content
        assert "FeedbackReadinessPanel" in project_detail_content
        assert "Feedback Readiness" in project_detail_content
        assert "dbtl_feedback_readiness_summary_v1" in project_detail_content
        assert "dbtlTrace.trace_summary.feedback_readiness" in project_detail_content
        assert "P4ClosedLoopReadinessPanel" in project_detail_content
        assert "P4 Closed Loop Readiness" in project_detail_content
        assert "dbtlTrace.trace_summary.p4_closed_loop_readiness" in project_detail_content
        assert "active_learning_batch_contract" in project_detail_content
        assert "model_calibration_registry_contract" in project_detail_content
        assert "manufacturing_constraint_contract" in project_detail_content
        assert "action.priority" in project_detail_content
        assert "action.category" in project_detail_content
        assert "next_round_structural_distance_source" in project_list_content
        assert "next_round_combination_evidence_status" in project_list_content
        assert "combination evidence:" in project_list_content
        assert "p4_status" in project_list_content
        assert "p4_blocked_gate_count" in project_list_content
        assert "P4 blocked gates:" in project_list_content
        assert "P4 ${dbtlStatus[proj.id].p4_status}" in project_list_content
        assert "project_memory_readiness" in frontend_api_content
        assert "dbtl_project_memory_readiness_v1" in frontend_api_content
        assert "feedback_readiness" in frontend_api_content
        assert "dbtl_feedback_readiness_summary_v1" in frontend_api_content
        assert "p4_active_learning_batch_contract_v1" in frontend_api_content
        assert "p4_model_calibration_registry_contract_v1" in frontend_api_content
        assert "p4_manufacturing_constraint_schema_v1" in frontend_api_content
        assert "runLipaseEvidenceOverlay" in pdb_page_content
        assert "lipaseNumberingConfirmed" in pdb_page_content
        assert "Lipase evidence" in pdb_card_content

    def test_matvenus_feedback_tools_are_registered_and_wired(self):
        registry = PROJECT_ROOT / "backend" / "app" / "tools" / "registry.py"
        agent_roles = PROJECT_ROOT / "backend" / "app" / "core" / "agent_roles.py"
        feedback_service = PROJECT_ROOT / "backend" / "app" / "services" / "experiment_feedback.py"
        feedback_model = PROJECT_ROOT / "backend" / "app" / "models" / "experiment_feedback.py"
        migration = PROJECT_ROOT / "backend" / "alembic" / "versions" / "9c8d7e6f5a41_add_experiment_feedback_records.py"

        assert "app.tools.mutation_epistasis_check" in registry.read_text()
        assert "app.tools.residue_numbering_gate" in registry.read_text()
        agent_content = agent_roles.read_text()
        assert "mutation_epistasis_check" in agent_content
        assert "residue_numbering_gate" in agent_content
        service_content = feedback_service.read_text()
        model_content = feedback_model.read_text()
        assert "analyze_feedback_payload" in service_content
        assert "summarize_feedback_records" in service_content
        assert "ExperimentFeedbackRecord" in model_content
        assert "experiment_feedback_records" in migration.read_text()

    def test_dockerignore_keeps_backend_smoke_scripts(self):
        dockerignore = PROJECT_ROOT / ".dockerignore"
        content = dockerignore.read_text()
        assert "backend/scripts/" in content
        assert "!backend/scripts/" in content
        assert "!backend/scripts/*.py" in content

    def test_prepare_deploy_data_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "prepare_deploy_data.py"
        content = script.read_text()
        assert "deploy_data" in content
        assert "--with-demo" in content
        assert "--overwrite-demo" in content
        assert "--write-manifest" in content
        assert "expected_datasets" in content

    def test_check_deploy_data_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "check_deploy_data.py"
        content = script.read_text()
        assert "--require-live" in content
        assert "--plan-only" in content
        assert "live-data-ready" in content
        assert "demo-data-only" in content
        assert "materialize_foldseek_links.py" in content
        assert "FOLDSEEK_API_URL" in content
        assert "structure_smoke_readiness.py" in content
        assert "version_comparison" in content
        assert "missing_items" in content
        assert "planned_commands" in content

        result = subprocess.run(
            [sys.executable, str(script), "--plan-only", "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        by_label = {item["label"]: item for item in payload}
        assert "pdb" in by_label
        assert "alphafold" in by_label
        assert "foldseek" in by_label
        assert "version_comparison" in by_label
        assert "dry_run" in by_label
        assert by_label["dry_run"]["status"] == "planned"
        assert by_label["dry_run"]["planned_commands"]
        assert "missing_items" in by_label["summary"]
        assert "next_actions" in by_label["summary"]

    def test_import_deploy_data_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "import_deploy_data.py"
        content = script.read_text()
        assert "import-manifest.json" in content
        assert "--annotations" in content
        assert "--foldseek-root" in content
        assert "--symlink" in content

    def test_discover_deploy_data_sources_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "discover_deploy_data_sources.py"
        content = script.read_text()
        assert "deploy_data" in content
        assert "--root" in content
        assert "alphafold" in content.lower()
        assert "sifts" in content.lower()

    def test_write_deploy_env_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "write_deploy_env.py"
        content = script.read_text()
        assert ".env.deploy-data" in content
        assert "DEPLOY_DATA_HOST_PATH" in content
        assert "FOLDSEEK_API_URL" in content

    def test_makefile_contains_deploy_shortcuts(self):
        makefile = PROJECT_ROOT / "Makefile"
        content = makefile.read_text()
        assert "acceptance-matrix" in content
        assert "pytest-runner" in content
        assert "pytest-runner-plan" in content
        assert "pytest-runner-json" in content
        assert "acceptance-matrix-fail-closed" in content
        assert "nightly-live-gates-fail-closed" in content
        assert "backend-md-blackbox-plan" in content
        assert "browser-smoke-plan" in content
        assert "deploy-preflight" in content
        assert "deploy-demo-check" in content
        assert "check-deploy-data" in content
        assert "discover-deploy-data" in content
        assert "materialize-foldseek-db" in content
        assert "backend-readiness" in content
        assert "backend-live-gate" in content
        assert "deploy-live-gate" in content
        assert "docker-backend-smoke-live" in content
        assert "docker-backend-live-gate" in content
        assert "docker-backend-rebuild-and-smoke" in content
        assert "docker-up-with-deploy-env" in content
        assert "docker-config-aliyun-app" in content
        assert "docker-up-aliyun-app" in content
        assert "docker-config-aliyun-gpu" in content
        assert "docker-up-aliyun-gpu" in content
        assert "BACKEND_DEPLOY_ENV" in content
        assert "deploy-data-update-plan" in content
        assert "deploy-data-update-json" in content
        assert "backend-md-topology-smoke" in content
        assert "backend-md-topology-live-gate" in content
        assert "backend-ligand-toolchain-smoke" in content
        assert "backend-ligand-toolchain-live-gate" in content
        assert "docker-config-ligand-worker" in content
        assert "docker-build-ligand-worker" in content
        assert "config --quiet" in content

    def test_acceptance_matrix_script_plan_includes_risk_gates(self):
        script = PROJECT_ROOT / "scripts" / "run_acceptance_matrix.py"
        content = script.read_text()
        assert "--include-md-blackbox" in content
        assert "--include-browser-smoke" in content
        assert "--include-ai-blackbox" in content
        assert "--include-file-download-e2e" in content
        assert "--include-benchmark-bundle-live" in content
        assert "oss_compatibility" in content
        assert "--include-oss-e2e" in content
        assert "oss_minio_e2e_contract" in content
        assert "ai_chat_blackbox_live" in content
        assert "live_file_download_e2e" in content
        assert "benchmark_bundle_head_live" in content
        assert "blocked" in content
        assert "skipped" in content
        assert "file_download_permissions" in content
        assert "ligand_preprocess_contract" in content
        assert "ligand_toolchain_smoke" in content
        assert "enzyme_report_quality_contract" in content
        assert "tool_capability_audit_gate" in content
        assert "user_isolation_contract" in content
        assert "wiki_checkpoint_contract" in content
        assert "hm_pdb_deep_quality_gate" in content
        assert "browser_smoke_contract" in content

        result = subprocess.run(
            [sys.executable, str(script), "--plan-only", "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        names = {item["name"] for item in payload["results"]}
        by_name = {item["name"]: item for item in payload["results"]}
        production_config_command = by_name["production_config_gate"]["command"]
        assert production_config_command.count("--env-file") == 2
        assert "docker/.env" in production_config_command
        assert "docker/.env.aliyun.app" in production_config_command
        assert "file_download_permissions" in names
        assert "md_artifact_whitebox" in names
        assert "ligand_preprocess_contract" in names
        assert "ligand_toolchain_smoke" in names
        assert "enzyme_report_quality_contract" in names
        assert "tool_capability_audit_gate" in names
        assert "user_isolation_contract" in names
        assert "wiki_checkpoint_contract" in names
        assert "hm_pdb_deep_quality_gate" in names
        assert "data_admin_readiness" in names
        assert "oss_compatibility" in names
        assert "browser_smoke_contract" in names
        assert "browser_live_smoke" in names
        assert "ai_chat_blackbox_live" in names
        assert "live_file_download_e2e" in names
        assert "benchmark_bundle_head_live" in names
        assert "md_blackbox" in names
        assert "deploy_live_gate" in names
        assert "oss_minio_e2e_contract" in names
        assert "browser_live_smoke" in names
        statuses = {item["name"]: item["status"] for item in payload["results"]}
        assert statuses["browser_live_smoke"] == "planned"
        assert statuses["ai_chat_blackbox_live"] == "skipped"
        assert statuses["live_file_download_e2e"] == "skipped"
        assert statuses["benchmark_bundle_head_live"] == "skipped"
        assert statuses["md_blackbox"] == "planned"
        assert statuses["deploy_live_gate"] == "skipped"
        assert statuses["oss_minio_e2e_contract"] == "skipped"
        assert payload["summary"]["status"] == "planned"
        assert payload["summary"]["planned"] >= 2
        assert payload["summary"]["skipped"] >= 5

        opt_in = subprocess.run(
            [
                sys.executable,
                str(script),
                "--plan-only",
                "--include-browser-smoke",
                "--include-ai-blackbox",
                "--include-file-download-e2e",
                "--include-benchmark-bundle-live",
                "--include-md-blackbox",
                "--include-live",
                "--include-oss-e2e",
                "--json",
                "--",
                "--timeout-seconds",
                "30",
                "--poll-interval",
                "3",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        opt_in_payload = json.loads(opt_in.stdout)
        opt_in_statuses = {item["name"]: item["status"] for item in opt_in_payload["results"]}
        assert opt_in_statuses["browser_public_smoke"] == "planned"
        assert opt_in_statuses["browser_live_smoke"] == "planned"
        assert opt_in_statuses["ai_chat_blackbox_live"] == "planned"
        assert opt_in_statuses["live_file_download_e2e"] == "planned"
        assert opt_in_statuses["benchmark_bundle_head_live"] == "planned"
        assert opt_in_statuses["md_blackbox"] == "planned"
        assert opt_in_statuses["deploy_live_gate"] == "planned"
        assert opt_in_statuses["backend_smoke_live"] == "planned"
        assert opt_in_statuses["oss_minio_e2e_contract"] == "planned"
        opt_in_by_name = {item["name"]: item for item in opt_in_payload["results"]}
        md_command = opt_in_by_name["md_blackbox"]["command"]
        assert "--timeout-seconds" in md_command
        assert "--poll-interval" in md_command
        assert "--" not in md_command

        spec = importlib.util.spec_from_file_location("run_acceptance_matrix", script)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        fail_closed_results = []
        module._append_optional_gate_markers(
            SimpleNamespace(
                plan_only=False,
                fail_closed_external=True,
                include_browser_smoke=False,
                include_md_blackbox=False,
                include_ai_blackbox=True,
                include_file_download_e2e=True,
                include_benchmark_bundle_live=True,
                include_live=True,
                include_oss_e2e=True,
            ),
            fail_closed_results,
        )
        fail_closed_statuses = {item.name: item.status for item in fail_closed_results}
        assert fail_closed_statuses["browser_live_smoke"] == "blocked"
        assert fail_closed_statuses["md_blackbox"] == "blocked"
        assert module._summary(fail_closed_results, plan_only=False)["status"] == "blocked"

    def test_pytest_runner_plan_is_local_and_fail_closed(self):
        script = PROJECT_ROOT / "scripts" / "run_pytest_runner.py"
        content = script.read_text(encoding="utf-8")
        assert "backend-test" in content
        assert "--cov=app" in content
        assert "USE_SQLITE" in content
        assert "TEST_DATABASE_URL" in content

        result = subprocess.run(
            [sys.executable, str(script), "--plan-only", "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["summary"]["status"] == "planned"
        assert payload["summary"]["runner"] == "local_mirror_of_github_actions_backend_test"
        assert payload["network_io"] == "not_executed"
        assert payload["destructive_actions"] == "not_executed"
        assert payload["workflow"]["status"] == "passed"
        assert payload["coverage"] in {"enabled", "unavailable"}
        assert payload["command"][0].endswith("backend/.venv/bin/python")
        assert payload["command"][1:4] == ["-m", "pytest", "tests/"]

    def test_md_blackbox_plan_only_is_fail_closed_without_submit_or_task(self):
        script = PROJECT_ROOT / "backend" / "scripts" / "verify_md_blackbox.py"
        content = script.read_text(encoding="utf-8")
        assert "--plan-only" in content
        assert "--require-inputs" in content
        assert "network_io" in content
        assert "not_executed" in content

        env = os.environ.copy()
        for key in (
            "MD_BLACKBOX_TASK_ID",
            "MD_BLACKBOX_EMAIL",
            "MD_BLACKBOX_PASSWORD",
            "LIVE_AI_EMAIL",
            "LIVE_AI_PASSWORD",
            "ALLOW_MD_BLACKBOX_SUBMIT",
        ):
            env.pop(key, None)
        result = subprocess.run(
            [sys.executable, str(script), "--plan-only", "--require-inputs", "--json"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        assert result.returncode == 1
        assert payload["summary"]["status"] == "blocked"
        assert "--allow-submit or ALLOW_MD_BLACKBOX_SUBMIT=true" in payload["summary"]["missing_inputs"]
        assert payload["network_io"] == "not_executed"
        assert payload["destructive_actions"] == "not_executed"

    def test_md_blackbox_resume_requires_explicit_password(self):
        script = PROJECT_ROOT / "backend" / "scripts" / "verify_md_blackbox.py"
        env = os.environ.copy()
        for key in ("MD_BLACKBOX_EMAIL", "MD_BLACKBOX_PASSWORD", "LIVE_AI_EMAIL", "LIVE_AI_PASSWORD"):
            env.pop(key, None)
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--plan-only",
                "--require-inputs",
                "--task-id",
                "existing-task-id",
                "--email",
                "operator@example.com",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        assert result.returncode == 1
        assert payload["summary"]["status"] == "blocked"
        assert "--password or MD_BLACKBOX_PASSWORD/LIVE_AI_PASSWORD" in payload["summary"]["missing_inputs"]
        assert payload["network_io"] == "not_executed"

    def test_frontend_live_contract_is_non_browser_and_uses_codex_port_range(self):
        script = PROJECT_ROOT / "frontend" / "tests" / "live-contract.mjs"
        content = script.read_text()
        assert "FRONTEND_BASE_URL" in content
        assert "4200" in content
        assert "4299" in content
        assert "public-smoke.mjs" in content
        assert "live-smoke.mjs" in content
        assert "http-smoke.mjs" in content
        assert "--plan-only" in content

        result = subprocess.run(
            ["node", str(script), "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["base_url"] == "http://127.0.0.1:4200"
        assert payload["summary"]["status"] == "passed"
        names = {item["name"] for item in payload["results"]}
        assert "frontend_base_url" in names
        assert "browser_public_smoke_contract" in names
        assert "browser_live_smoke_contract" in names
        assert "http_smoke_contract" in names
        assert "plan_only_contract" in names

        plan = subprocess.run(
            ["node", str(script), "--plan-only", "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        plan_payload = json.loads(plan.stdout)
        assert plan_payload["plan_only"] is True
        assert plan_payload["summary"]["status"] == "passed"

    def test_oss_minio_contract_script_is_plan_only_without_network_io(self):
        script = PROJECT_ROOT / "scripts" / "smoke_oss_minio_contract.py"
        content = script.read_text()
        assert "does not create buckets" in content
        assert "--require-live" in content
        assert "drills/oss-minio-e2e" in content
        assert "network_io" in content

        env = os.environ.copy()
        env.pop("MINIO_ACCESS_KEY", None)
        env.pop("MINIO_SECRET_KEY", None)
        env.pop("ALIYUN_OSS_ACCESS_KEY_ID", None)
        env.pop("ALIYUN_OSS_ACCESS_KEY_SECRET", None)
        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["summary"]["network_io"] == "not_executed"
        assert payload["summary"]["status"] in {"planned", "blocked"}
        names = {item["name"] for item in payload["results"]}
        assert "oss_minio_endpoint" in names
        assert "oss_minio_bucket" in names
        assert "oss_minio_credentials" in names

    def test_oss_minio_contract_accepts_aliyun_oss_env_aliases(self):
        script = PROJECT_ROOT / "scripts" / "smoke_oss_minio_contract.py"
        env = os.environ.copy()
        for key in ("MINIO_ENDPOINT", "MINIO_BUCKET", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_REGION"):
            env.pop(key, None)
        env.update(
            {
                "ALIYUN_OSS_ENDPOINT": "oss-cn-hangzhou-internal.aliyuncs.com",
                "ALIYUN_OSS_REGION": "cn-hangzhou",
                "ALIYUN_OSS_BUCKET": "protein-ai-files",
                "ALIYUN_OSS_ACCESS_KEY_ID": "test-access-key",
                "ALIYUN_OSS_ACCESS_KEY_SECRET": "test-secret-key",
            }
        )

        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(result.stdout)
        assert payload["summary"]["network_io"] == "not_executed"
        assert payload["summary"]["status"] == "passed"

    def test_release_acceptance_script_plan_includes_delivery_gates(self):
        script = PROJECT_ROOT / "scripts" / "run_release_acceptance.py"
        content = script.read_text()
        assert "check_upgrade_readiness.py" in content
        assert "run_acceptance_matrix.py" in content
        assert "package_deploy_bundle.py" in content
        assert "rollback_plan.py" in content
        assert "restore_drill.sh" in content
        assert "--include-backup-verify" in content
        assert "production_https_gate" in content
        assert "formal HTTPS domain" in content
        assert "real_rollback" in content
        assert "deploy_package" in content

        makefile = PROJECT_ROOT / "Makefile"
        make_content = makefile.read_text()
        assert "release-acceptance" in make_content
        assert "release-acceptance-json" in make_content
        assert "release-acceptance-plan" in make_content

        result = subprocess.run(
            [sys.executable, str(script), "--plan-only", "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        names = {item["name"] for item in payload["results"]}
        assert "upgrade_readiness" in names
        assert "acceptance_matrix" in names
        assert "package_deploy_bundle_dry_run" in names
        assert "rollback_plan" in names
        assert "restore_drill_dry_run" in names
        assert "production_https_gate" in names
        assert payload["safety"]["real_restore"] is False
        assert payload["safety"]["real_rollback"] is False

        restore_drill = PROJECT_ROOT / "scripts" / "restore_drill.sh"
        restore_content = restore_drill.read_text()
        assert "Refusing unsafe drill database name after env load" in restore_content
        assert 'DRILL_DB" == "$MAIN_DB' in restore_content

    def test_release_manual_gate_input_validator_is_read_only(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "validate_release_manual_gate_inputs.py"
        template = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-inputs.template.json"
        output = tmp_path / "release-manual-gate-report.json"
        content = script.read_text(encoding="utf-8")
        assert "network_io" in content
        assert "destructive_actions" in content
        assert "run_release_acceptance.py" in content
        assert "--include-backup-verify" in content
        assert "--backup-verify-compose" in content
        assert template.exists()

        incomplete = subprocess.run(
            [
                sys.executable,
                str(script),
                "--values",
                str(template),
                "--output",
                str(output),
                "--require-complete",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert incomplete.returncode == 1
        incomplete_payload = json.loads(incomplete.stdout)
        assert incomplete_payload["status"] == "manual_required"
        assert incomplete_payload["missing_gate_count"] == 3

        values = tmp_path / "release-manual-gate-values.json"
        values.write_text(
            json.dumps(
                {
                    "required_inputs": {
                        "production_rollback_drill_gate": {
                            "MAINTENANCE_WINDOW_ID": "MW-20260817-001",
                            "ALLOW_PRODUCTION_DRILL": True,
                        },
                        "offsite_backup_restore_drill_gate": {
                            "OFFSITE_BACKUP_TARGET": "oss://backup/protein_ai_20260817.dump",
                            "OFFSITE_RESTORE_TARGET": "staging-restore-db",
                        },
                        "external_storage_restore_validation_gate": {
                            "EXTERNAL_STORAGE_BACKUP_REF": "oss-snapshot-20260817",
                            "EXTERNAL_STORAGE_RESTORE_TARGET": "oss://restore-shadow/protein-ai/",
                        },
                    },
                    "options": {"BACKUP_VERIFY_COMPOSE": True},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        complete = subprocess.run(
            [
                sys.executable,
                str(script),
                "--values",
                str(values),
                "--output",
                str(output),
                "--require-complete",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        complete_payload = json.loads(complete.stdout)
        report_payload = json.loads(output.read_text(encoding="utf-8"))
        assert complete_payload["status"] == "ready"
        assert report_payload["network_io"] == "not_executed"
        assert report_payload["destructive_actions"] == "not_executed"
        assert report_payload["secrets_printed"] is False
        command = report_payload["final_acceptance_command"]
        assert "--maintenance-window-id" in command
        assert "--allow-production-drill" in command
        assert "--offsite-backup-target" in command
        assert "--external-storage-restore-target" in command

    def test_release_manual_gate_evidence_validator_is_read_only(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "validate_release_manual_gate_evidence.py"
        template = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-evidence-inputs.template.json"
        output = tmp_path / "release-manual-gate-evidence-report.json"
        content = script.read_text(encoding="utf-8")
        assert "network_io" in content
        assert "destructive_actions" in content
        assert "ready_for_go" in content
        assert "production_path_switched" in content
        assert template.exists()

        incomplete = subprocess.run(
            [
                sys.executable,
                str(script),
                "--values",
                str(template),
                "--output",
                str(output),
                "--require-go",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert incomplete.returncode == 1
        incomplete_payload = json.loads(incomplete.stdout)
        incomplete_report = json.loads(output.read_text(encoding="utf-8"))
        assert incomplete_payload["status"] == "manual_required"
        assert incomplete_payload["ready_for_go"] is False
        assert "release_acceptance" in incomplete_payload["missing_sections"]
        assert incomplete_report["network_io"] == "not_executed"
        assert incomplete_report["destructive_actions"] == "not_executed"
        assert incomplete_report["secrets_printed"] is False

        values = tmp_path / "release-manual-gate-evidence-values.json"
        values.write_text(
            json.dumps(
                {
                    "release": {
                        "release_date": "2026-08-17",
                        "release_owner": "release-owner",
                        "reviewer": "release-reviewer",
                        "business_owner": "business-owner",
                        "maintenance_window_id": "MW-20260817-001",
                        "release_package": "dist/packages/protein-ai-platform.tar.gz",
                        "release_package_sha256_evidence": "docs/manuals/drill-records/sha256.txt",
                        "database_backup": "backups/protein_ai_20260817.dump",
                        "database_backup_sha256_evidence": "docs/manuals/drill-records/backup.sha256.txt",
                        "evidence_archive_dir": "docs/manuals/drill-records/2026-08-17-release/",
                    },
                    "release_acceptance": {
                        "status": "passed",
                        "failed": 0,
                        "blocked": 0,
                        "manual_required": 0,
                        "skipped": 0,
                        "json_output_path": "docs/manuals/drill-records/release-acceptance.json",
                    },
                    "gates": {
                        "production_rollback_drill_gate": {
                            "status": "passed",
                            "maintenance_window_id": "MW-20260817-001",
                            "authorization_evidence_path": "docs/manuals/drill-records/maintenance-approval.md",
                            "rollback_plan_path": "docs/manuals/drill-records/rollback-plan.json",
                            "restore_drill_path": "docs/manuals/drill-records/restore-drill.txt",
                            "backup_verify_path": "docs/manuals/drill-records/backup-verify.txt",
                            "pg_restore_list_path": "docs/manuals/drill-records/pg-restore-list.txt",
                            "conclusion": "passed",
                        },
                        "offsite_backup_restore_drill_gate": {
                            "status": "passed",
                            "backup_target": "oss://redacted-backup/protein_ai_20260817.dump",
                            "restore_target": "staging-independent-restore-db",
                            "copy_evidence_path": "docs/manuals/drill-records/offsite-copy.txt",
                            "checksum_evidence_path": "docs/manuals/drill-records/offsite-sha256.txt",
                            "restore_evidence_path": "docs/manuals/drill-records/offsite-restore.txt",
                            "application_readonly_smoke_path": "docs/manuals/drill-records/offsite-smoke.txt",
                            "conclusion": "passed",
                        },
                        "external_storage_restore_validation_gate": {
                            "status": "passed",
                            "backup_ref": "oss-snapshot-20260817",
                            "restore_target": "oss://shadow-restore/protein-ai/",
                            "shadow_restore_evidence_path": "docs/manuals/drill-records/shadow-restore.txt",
                            "sample_object_read_evidence_path": "docs/manuals/drill-records/sample-read.txt",
                            "application_readonly_smoke_path": "docs/manuals/drill-records/storage-smoke.txt",
                            "production_path_switched": False,
                            "conclusion": "passed",
                        },
                    },
                    "decision": {
                        "automatic_failed_zero": True,
                        "automatic_blocked_zero": True,
                        "maintenance_evidence_complete": True,
                        "offsite_restore_evidence_complete": True,
                        "external_storage_evidence_complete": True,
                        "rollback_path_ready": True,
                        "approvals_complete": True,
                        "final_decision": "go",
                        "release_owner_signature": "release-owner / 2026-08-17T10:00:00Z",
                        "reviewer_signature": "release-reviewer / 2026-08-17T10:05:00Z",
                        "business_owner_signature": "business-owner / 2026-08-17T10:10:00Z",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        complete = subprocess.run(
            [
                sys.executable,
                str(script),
                "--values",
                str(values),
                "--output",
                str(output),
                "--require-go",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        complete_payload = json.loads(complete.stdout)
        complete_report = json.loads(output.read_text(encoding="utf-8"))
        assert complete_payload["status"] == "ready-for-go"
        assert complete_payload["evidence_complete"] is True
        assert complete_payload["ready_for_go"] is True
        assert complete_report["final_decision"] == "go"
        assert complete_report["missing_sections"] == []

        schema = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-evidence.schema.json"
        example = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-evidence.example.json"
        schema_payload = json.loads(schema.read_text(encoding="utf-8"))
        example_payload = json.loads(example.read_text(encoding="utf-8"))
        assert "production_path_switched" in json.dumps(schema_payload)
        assert example_payload["example_only"] is True
        example_result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--values",
                str(example),
                "--output",
                str(output),
                "--require-go",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        example_summary = json.loads(example_result.stdout)
        assert example_result.returncode == 1
        assert example_summary["status"] == "defer"
        assert example_summary["ready_for_go"] is False

    def test_release_decision_summary_and_worktree_manifest_are_read_only(self, tmp_path):
        summary_script = PROJECT_ROOT / "scripts" / "build_release_go_no_go_summary.py"
        worktree_script = PROJECT_ROOT / "scripts" / "build_release_worktree_manifest.py"
        summary_json = tmp_path / "go-no-go.json"
        summary_md = tmp_path / "go-no-go.md"
        worktree_json = tmp_path / "worktree.json"

        for script in (summary_script, worktree_script):
            content = script.read_text(encoding="utf-8")
            assert "network_io" in content
            assert "destructive_actions" in content
            assert "secrets_printed" in content

        summary_result = subprocess.run(
            [
                sys.executable,
                str(summary_script),
                "--output-json",
                str(summary_json),
                "--output-md",
                str(summary_md),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        summary_payload = json.loads(summary_result.stdout)
        summary_report = json.loads(summary_json.read_text(encoding="utf-8"))
        assert summary_payload["status"] == "manual_required"
        assert summary_payload["ready_for_go_review"] is False
        assert "manual_gate_inputs" in summary_payload["blocking_items"]
        assert summary_report["production_deployed"] is False
        assert "manual_gate_evidence" in summary_md.read_text(encoding="utf-8")
        assert "check_production_config.py" in summary_script.read_text(encoding="utf-8")
        assert "--require-production-safe" in summary_script.read_text(encoding="utf-8")

        placeholder_env = tmp_path / ".env.aliyun.app"
        placeholder_env.write_text(
            "\n".join([
                "DEBUG=false",
                "SECRET_KEY=this-is-a-long-random-test-secret-value",
                "OIDC_CLIENT_SECRET=this-is-a-long-oidc-test-secret",
                "ALIYUN_APP_DATABASE_URL=postgresql+asyncpg://CHANGE_ME_USER:CHANGE_ME_PASSWORD@pg.example.com:5432/protein_ai",
                "ALIYUN_REDIS_HOST=CHANGE_ME_REDIS_ENDPOINT",
                "ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou-internal.aliyuncs.com",
                "ALIYUN_OSS_BUCKET=protein-ai-files",
                "ALIYUN_OSS_ACCESS_KEY_ID=test-access-key",
                "ALIYUN_OSS_ACCESS_KEY_SECRET=this-is-a-long-storage-secret",
                "LLM_PROVIDER=kuaPao",
                "KUAPAO_API_KEY=test-llm-key",
                "PUBLIC_BASE_URL=http://120.27.108.138",
                "OUTLINE_API_TOKEN=ol_api_12345678901234567890123456789012345678",
                "OUTLINE_API_URL=http://outline:3001/api",
            ]),
            encoding="utf-8",
        )
        isolated_env = os.environ.copy()
        for key in (
            "DATABASE_URL",
            "ALIYUN_APP_DATABASE_URL",
            "REDIS_URL",
            "REDIS_HOST",
            "ALIYUN_REDIS_APP_URL",
            "ALIYUN_REDIS_HOST",
            "MINIO_ENDPOINT",
            "MINIO_BUCKET",
            "MINIO_ACCESS_KEY",
            "MINIO_SECRET_KEY",
            "ALIYUN_OSS_ENDPOINT",
            "ALIYUN_OSS_BUCKET",
            "ALIYUN_OSS_ACCESS_KEY_ID",
            "ALIYUN_OSS_ACCESS_KEY_SECRET",
            "LLM_PROVIDER",
            "KUAPAO_API_KEY",
        ):
            isolated_env.pop(key, None)

        blocked_summary = subprocess.run(
            [
                sys.executable,
                str(summary_script),
                "--production-env-file",
                str(placeholder_env),
                "--output-json",
                str(tmp_path / "go-no-go-placeholder.json"),
                "--output-md",
                str(tmp_path / "go-no-go-placeholder.md"),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            env=isolated_env,
            capture_output=True,
            text=True,
            check=True,
        )
        blocked_payload = json.loads(blocked_summary.stdout)
        assert "production_config_gate" in blocked_payload["blocking_items"]

        worktree_result = subprocess.run(
            [
                sys.executable,
                str(worktree_script),
                "--output",
                str(worktree_json),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        worktree_payload = json.loads(worktree_result.stdout)
        worktree_report = json.loads(worktree_json.read_text(encoding="utf-8"))
        assert worktree_payload["network_io"] == "not_executed"
        assert worktree_payload["destructive_actions"] == "not_executed"
        assert worktree_report["mode"] == "read_only_release_worktree_manifest"
        assert isinstance(worktree_report["files"], list)

    def test_release_operator_packet_manifest_is_read_only(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "build_release_operator_packet_manifest.py"
        output = tmp_path / "operator-packet-manifest.json"
        content = script.read_text(encoding="utf-8")
        assert "network_io" in content
        assert "destructive_actions" in content
        assert "release-operator-packet-2026-08-17.md" in content
        assert "validate_release_manual_gate_inputs.py" in content

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--output",
                str(output),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(result.stdout)
        manifest = json.loads(output.read_text(encoding="utf-8"))
        assert payload["status"] == "ready-for-operator-review"
        assert payload["network_io"] == "not_executed"
        assert payload["destructive_actions"] == "not_executed"
        assert manifest["release_status"]["production_deployed"] is False
        assert manifest["release_status"]["manual_required"] == 3
        by_label = {row["label"]: row for row in manifest["files"]}
        assert by_label["operator_packet"]["sha256"]
        assert by_label["manual_gate_input_validator"]["exists"] is True
        assert by_label["manual_gate_evidence_inputs_template"]["exists"] is True
        assert by_label["manual_gate_evidence_schema"]["exists"] is True
        assert by_label["manual_gate_evidence_example"]["exists"] is True
        assert by_label["manual_gate_evidence_validator"]["sha256"]
        assert by_label["go_no_go_summary_builder"]["sha256"]
        assert by_label["worktree_manifest_builder"]["sha256"]

        check_result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--output",
                str(output),
                "--check",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        check_payload = json.loads(check_result.stdout)
        assert check_payload["status"] == "current"
        assert check_payload["network_io"] == "not_executed"
        assert check_payload["destructive_actions"] == "not_executed"

        manifest["files"][0]["sha256"] = "stale"
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        stale_result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--output",
                str(output),
                "--check",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        stale_payload = json.loads(stale_result.stdout)
        assert stale_result.returncode == 1
        assert stale_payload["status"] == "stale-or-missing"
        assert stale_payload["reason"] == "manifest_differs_from_current_packet"
        assert "files" in stale_payload["stale_sections"]

        output.unlink()
        missing_result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--output",
                str(output),
                "--check",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        missing_payload = json.loads(missing_result.stdout)
        assert missing_result.returncode == 1
        assert missing_payload["status"] == "stale-or-missing"
        assert missing_payload["reason"] == "manifest_missing"

        output.write_text("{not-json", encoding="utf-8")
        invalid_result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--output",
                str(output),
                "--check",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        invalid_payload = json.loads(invalid_result.stdout)
        assert invalid_result.returncode == 1
        assert invalid_payload["status"] == "stale-or-missing"
        assert invalid_payload["reason"] == "manifest_invalid_json"

    def test_verify_backup_accepts_legacy_absolute_checksum_paths(self, tmp_path):
        backup_file = tmp_path / "protein_ai_legacy.sql.gz"
        with gzip.open(backup_file, "wb") as fh:
            fh.write(b"-- legacy plain SQL backup smoke\n")
        digest = hashlib.sha256(backup_file.read_bytes()).hexdigest()
        checksum_file = backup_file.with_suffix(backup_file.suffix + ".sha256")
        checksum_file.write_text(f"{digest}  /Users/old/path/{backup_file.name}\n")

        result = subprocess.run(
            [str(PROJECT_ROOT / "scripts" / "verify_backup.sh"), str(backup_file)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        assert "checksum\tok" in result.stdout
        assert "legacy-path" in result.stdout
        assert "summary\tok\tbackup verification passed" in result.stdout

    def test_deploy_data_update_script_plan_is_safe(self):
        script = PROJECT_ROOT / "scripts" / "run_deploy_data_update.py"
        content = script.read_text()
        assert "refresh_live_deploy_data.py" in content
        assert "--plan-only" in content
        assert "deploy_data/updates" in content
        assert "schedule_hint" in content

        result = subprocess.run(
            [sys.executable, str(script), "--plan-only", "--json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["summary"]["status"] == "planned"
        assert payload["summary"]["executed"] is False
        names = {item["name"] for item in payload["results"]}
        assert "refresh_live_deploy_data" in names
        assert "check_deploy_data" in names
        assert "schedule_hint" in names

    def test_productization_manuals_exist(self):
        manuals = PROJECT_ROOT / "docs" / "manuals"
        acceptance = manuals / "productization-acceptance-manual.md"
        drill = manuals / "drill-record-template.md"
        admin = manuals / "admin-manual.md"
        data_import = manuals / "data-import-manual.md"
        ligand_workflow = manuals / "ligand-docking-md-workflow.md"
        external_infra = manuals / "external-infrastructure-acceptance-checklist.md"
        release_handoff = manuals / "release-handoff-2026-08-17.md"
        release_operator_packet = manuals / "release-operator-packet-2026-08-17.md"
        release_manual_gate_template = manuals / "release-manual-gate-inputs.template.json"
        release_manual_gate_evidence = manuals / "release-manual-gate-evidence-template.md"
        release_manual_gate_evidence_inputs = manuals / "release-manual-gate-evidence-inputs.template.json"
        acceptance_content = acceptance.read_text(encoding="utf-8")
        drill_content = drill.read_text(encoding="utf-8")
        admin_content = admin.read_text(encoding="utf-8")
        data_import_content = data_import.read_text(encoding="utf-8")
        ligand_workflow_content = ligand_workflow.read_text(encoding="utf-8")
        external_infra_content = external_infra.read_text(encoding="utf-8")
        release_handoff_content = release_handoff.read_text(encoding="utf-8")
        release_operator_packet_content = release_operator_packet.read_text(encoding="utf-8")
        evidence_content = release_manual_gate_evidence.read_text(encoding="utf-8")
        assert "make release-acceptance" in acceptance_content
        assert "TEST_DATABASE_URL" in acceptance_content
        assert "external-infrastructure-acceptance-checklist.md" in acceptance_content
        assert "release-handoff-2026-08-17.md" in acceptance_content
        assert "release-operator-packet-2026-08-17.md" in acceptance_content
        assert "make release-manual-gate-template" in acceptance_content
        assert "make release-manual-gate-validate" in acceptance_content
        assert "make release-manual-gate-evidence-template" in acceptance_content
        assert "make release-manual-gate-evidence-validate" in acceptance_content
        assert "make release-go-no-go-summary" in acceptance_content
        assert "make release-worktree-manifest" in acceptance_content
        assert "make release-operator-packet-manifest" in acceptance_content
        assert "make release-operator-packet-manifest-check" in acceptance_content
        assert "release-manual-gate-evidence-template.md" in acceptance_content
        assert "project.chat.bind" in acceptance_content
        assert "OPS_ALERT_WEBHOOK_ENABLED" in acceptance_content
        assert "deploy_data/pdb/1QHP.cif" in acceptance_content
        assert "make verify-backup BACKUP_FILE=..." in drill_content
        assert "productization-acceptance-manual.md" in admin_content
        assert "make deploy-data-update-plan" in data_import_content
        assert "deploy_data/updates/deploy_data_update_" in data_import_content
        assert "2D SDF" in ligand_workflow_content
        assert "make backend-ligand-toolchain-live-gate" in ligand_workflow_content
        assert "ACPYPE/Antechamber" in ligand_workflow_content
        assert "正式域名 + HTTPS + OIDC Callback" in external_infra_content
        assert "GPU/GROMACS 节点" in external_infra_content
        assert "MAINTENANCE_WINDOW_ID" in external_infra_content
        assert "OFFSITE_BACKUP_TARGET" in external_infra_content
        assert "EXTERNAL_STORAGE_BACKUP_REF" in external_infra_content
        assert "PDB | 每周" in external_infra_content
        assert "pending" in external_infra_content
        assert "passed-with-manual-gates" in release_handoff_content
        assert "manual_required" in release_handoff_content
        assert "release-operator-packet-2026-08-17.md" in release_handoff_content
        assert "make release-manual-gate-validate" in release_handoff_content
        assert "make release-manual-gate-evidence-validate" in release_handoff_content
        assert "make release-go-no-go-summary" in release_handoff_content
        assert "make release-worktree-manifest" in release_handoff_content
        assert "make release-operator-packet-manifest-check" in release_handoff_content
        assert "release-manual-gate-evidence-template.md" in release_handoff_content
        assert "manual_required" in release_operator_packet_content
        assert "make release-manual-gate-validate" in release_operator_packet_content
        assert "make release-manual-gate-evidence-template" in release_operator_packet_content
        assert "make release-manual-gate-evidence-validate" in release_operator_packet_content
        assert "make release-go-no-go-summary" in release_operator_packet_content
        assert "make release-worktree-manifest" in release_operator_packet_content
        assert "make release-operator-packet-manifest" in release_operator_packet_content
        assert "make release-operator-packet-manifest-check" in release_operator_packet_content
        assert "release-operator-packet-manifest-2026-08-17.json" in release_operator_packet_content
        assert "failed=0 / blocked=0" in release_operator_packet_content
        assert "shadow bucket/prefix" in release_operator_packet_content
        assert "go/no-go/defer" in release_operator_packet_content
        assert "MAINTENANCE_WINDOW_ID" in evidence_content
        assert "OFFSITE_BACKUP_TARGET" in evidence_content
        assert "EXTERNAL_STORAGE_BACKUP_REF" in evidence_content
        assert "release acceptance JSON" in evidence_content
        assert "go / no-go / defer" in evidence_content
        assert "make release-manual-gate-evidence-template" in evidence_content
        assert "make release-manual-gate-evidence-validate" in evidence_content
        assert "release-manual-gate-evidence.schema.json" in evidence_content
        assert "release-manual-gate-evidence.example.json" in evidence_content
        template_payload = json.loads(release_manual_gate_template.read_text(encoding="utf-8"))
        assert "required_inputs" in template_payload
        assert "production_rollback_drill_gate" in template_payload["required_inputs"]
        evidence_template_payload = json.loads(release_manual_gate_evidence_inputs.read_text(encoding="utf-8"))
        assert "release_acceptance" in evidence_template_payload
        assert "external_storage_restore_validation_gate" in evidence_template_payload["gates"]

    def test_ci_pytest_uses_isolated_test_database_url(self):
        workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        conftest = PROJECT_ROOT / "backend" / "tests" / "conftest.py"
        workflow_content = workflow.read_text(encoding="utf-8")
        conftest_content = conftest.read_text(encoding="utf-8")

        assert "TEST_DATABASE_URL" in workflow_content
        assert "test_protein_ai_ci_${{ github.run_id }}_${{ github.job }}.db" in workflow_content
        assert 'os.environ.get("TEST_DATABASE_URL"' in conftest_content

    def test_deploy_aliyun_script_is_role_based(self):
        script = PROJECT_ROOT / "deploy-aliyun.sh"
        content = script.read_text()
        assert "docker-compose.aliyun-app.yml" in content
        assert "docker-compose.aliyun-gpu.yml" in content
        assert "./deploy-aliyun.sh app" in content
        assert "./deploy-aliyun.sh gpu" in content
        assert ".env.aliyun.app" in content
        assert ".env.aliyun.gpu" in content

    def test_materialize_foldseek_links_script_exists(self):
        script = PROJECT_ROOT / "scripts" / "materialize_foldseek_links.py"
        content = script.read_text()
        assert "Foldseek" in content
        assert "--dry-run" in content
        assert "symlink" in content

    def test_structure_smoke_readiness_script_exists(self):
        script = PROJECT_ROOT / "backend" / "scripts" / "structure_smoke_readiness.py"
        content = script.read_text()
        assert "--require-live" in content
        assert "live-ready" in content
        assert "demo-ready" in content
        assert "live_annotations" in content
        assert "deploy_data_root" in content
        assert "smoke_structure_data.py" in content

    def test_structure_smoke_demo_fixture_exists(self):
        fixture = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "structure_smoke" / "1abc.json"
        assert fixture.exists(), "Bundled structure smoke demo mapping fixture missing"

    def test_env_example_contains_structure_smoke_vars(self):
        env_example = PROJECT_ROOT / "backend" / ".env.example"
        content = env_example.read_text()
        assert "DEPLOY_DATA_ROOT" in content
        assert "LOCAL_ANNOTATION_FIXTURE_PATH" in content
        assert "SIFTS_SMOKE_USE_DEMO" in content
        assert "FOLDSEEK_SMOKE_USE_DEMO" in content
        assert "STRUCTURE_SMOKE_PDB_FILE" in content

    def test_env_example_contains_object_storage_secure_vars(self):
        env_example = PROJECT_ROOT / "backend" / ".env.example"
        content = env_example.read_text()
        assert "MINIO_SECURE" in content
        assert "MINIO_REGION" in content
        assert "REDIS_HOST" in content
        assert "REDIS_PORT" in content
        assert "REDIS_DB" in content
        assert "OPS_SLOW_REQUEST_THRESHOLD_SECONDS" in content
        assert "OPS_ALERT_WEBHOOK_ENABLED" in content
        assert "OPS_ALERT_WEBHOOK_URL" in content
        assert "OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS" in content
        assert "OPS_ALERT_WEBHOOK_RETRY_ATTEMPTS" in content
        assert "OPS_ALERT_SILENCE_SECONDS" in content
        assert "OPS_ALERT_ESCALATE_AFTER_COUNT" in content

    def test_aliyun_managed_env_examples_exist(self):
        app_env = PROJECT_ROOT / "docker" / ".env.aliyun.app.example"
        gpu_env = PROJECT_ROOT / "docker" / ".env.aliyun.gpu.example"
        app_content = app_env.read_text()
        gpu_content = gpu_env.read_text()
        assert "ALIYUN_APP_DATABASE_URL" in app_content
        assert "ALIYUN_OSS_ENDPOINT" in app_content
        assert "ALIYUN_OUTLINE_DATABASE_URL" in app_content
        assert "OUTLINE_FORCE_HTTPS" in app_content
        assert "change-me-64-char-hex-outline-secret-key" in app_content
        assert "OUTLINE_API_TOKEN=" in app_content
        assert "OUTLINE_API_URL=http://outline:3001/api" in app_content
        assert "ALIYUN_APP_DATABASE_URL" in gpu_content
        assert "GPU_DEVICE_REQUEST" in gpu_content
        assert "CELERY_LIGAND_WORKER_CONCURRENCY" in gpu_content
        assert "GROMACS_BIN" in gpu_content

    def test_init_deployment_generates_outline_hex_secrets(self):
        script = PROJECT_ROOT / "scripts" / "init_deployment.py"
        content = script.read_text()
        assert "def _random_hex" in content
        assert '"OUTLINE_SECRET_KEY": _random_hex(32)' in content
        assert '"OUTLINE_UTILS_SECRET": _random_hex(32)' in content

    def test_structure_smoke_demo_modes_execute(self):
        script = PROJECT_ROOT / "backend" / "scripts" / "smoke_structure_data.py"
        env = os.environ.copy()
        env["SIFTS_SMOKE_USE_DEMO"] = "1"
        env["FOLDSEEK_SMOKE_USE_DEMO"] = "1"
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT / "backend",
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        combined = f"{result.stdout}\n{result.stderr}"
        assert "PASS sifts:" in combined
        assert "PASS foldseek-demo:" in combined

    def test_structure_smoke_readiness_reports_demo_ready(self):
        script = PROJECT_ROOT / "backend" / "scripts" / "structure_smoke_readiness.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT / "backend",
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "demo_sifts\tready\t" in result.stdout
        assert "deploy_data_root\tready\t" in result.stdout
        assert "live_foldseek_http\tmissing\t" in result.stdout
        assert "live_foldseek_cli\tmissing\t" in result.stdout
        assert "summary\tdemo-ready\t" in result.stdout

    def test_structure_smoke_autodiscovers_deploy_data_root(self, tmp_path):
        script = PROJECT_ROOT / "backend" / "scripts" / "smoke_structure_data.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "sifts").mkdir(parents=True)
        (deploy_root / "smoke").mkdir(parents=True)
        fixture = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "structure_smoke" / "1abc.json"
        (deploy_root / "sifts" / "1abc.json").write_text(fixture.read_text(), encoding="utf-8")
        (deploy_root / "smoke" / "query.pdb").write_text(
            "HEADER    AUTODISCOVERY TEST\n"
            "ATOM      1  N   MET A   1      11.104  13.207  12.411  1.00 20.00           N\n"
            "ATOM      2  N   ALA A   2      13.101  14.650  12.778  1.00 20.00           N\nEND\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["DEPLOY_DATA_ROOT"] = str(deploy_root)
        env["SIFTS_SMOKE_PDB_ID"] = "1abc"
        env["FOLDSEEK_SMOKE_USE_DEMO"] = "1"
        env.pop("SIFTS_MAPPING_PATH", None)
        env.pop("STRUCTURE_SMOKE_PDB_FILE", None)

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT / "backend",
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        combined = f"{result.stdout}\n{result.stderr}"
        assert "PASS sifts:" in combined
        assert "PASS foldseek-demo:" in combined

    def test_structure_smoke_infers_sifts_pdb_id_from_local_mapping_filename(self, tmp_path):
        script = PROJECT_ROOT / "backend" / "scripts" / "smoke_structure_data.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "sifts").mkdir(parents=True)
        (deploy_root / "smoke").mkdir(parents=True)
        fixture = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "structure_smoke" / "1abc.json"
        (deploy_root / "sifts" / "1abc.json").write_text(fixture.read_text(), encoding="utf-8")
        (deploy_root / "smoke" / "query.pdb").write_text(
            "HEADER    AUTODISCOVERY TEST\n"
            "ATOM      1  N   MET A   1      11.104  13.207  12.411  1.00 20.00           N\n"
            "ATOM      2  N   ALA A   2      13.101  14.650  12.778  1.00 20.00           N\nEND\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["DEPLOY_DATA_ROOT"] = str(deploy_root)
        env["FOLDSEEK_SMOKE_USE_DEMO"] = "1"
        env.pop("SIFTS_MAPPING_PATH", None)
        env.pop("SIFTS_SMOKE_PDB_ID", None)

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT / "backend",
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        combined = f"{result.stdout}\n{result.stderr}"
        assert "PASS sifts:" in combined
        assert "PASS foldseek-demo:" in combined

    def test_structure_smoke_prefers_real_sifts_mapping_over_demo_fixture(self, tmp_path):
        script = PROJECT_ROOT / "backend" / "scripts" / "smoke_structure_data.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "sifts").mkdir(parents=True)
        (deploy_root / "smoke").mkdir(parents=True)
        fixture = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "structure_smoke" / "1abc.json"
        (deploy_root / "sifts" / "1abc.json").write_text(fixture.read_text(), encoding="utf-8")
        (deploy_root / "sifts" / "realcase.json").write_text(
            json.dumps(
                {
                    "mappings": [
                        {
                            "pdb_id": "realcase",
                            "chain_id": "A",
                            "pdb_residue_no": 1,
                            "uniprot_id": "P00000",
                            "uniprot_position": 1,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (deploy_root / "smoke" / "query.pdb").write_text(
            "HEADER    AUTODISCOVERY REAL TEST\nATOM      1  N   MET A   1      11.104  13.207  12.411  1.00 20.00           N\nEND\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["DEPLOY_DATA_ROOT"] = str(deploy_root)
        env["FOLDSEEK_SMOKE_USE_DEMO"] = "1"
        env.pop("SIFTS_MAPPING_PATH", None)
        env.pop("SIFTS_SMOKE_PDB_ID", None)

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT / "backend",
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        combined = f"{result.stdout}\n{result.stderr}"
        assert "PASS sifts:" in combined
        assert "realcase.json" in combined

    def test_structure_smoke_readiness_autodiscovers_deploy_data_root(self, tmp_path):
        script = PROJECT_ROOT / "backend" / "scripts" / "structure_smoke_readiness.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "sifts").mkdir(parents=True)
        (deploy_root / "foldseek" / "pdb").mkdir(parents=True)
        (deploy_root / "annotations").mkdir(parents=True)
        (deploy_root / "smoke").mkdir(parents=True)
        (deploy_root / "sifts" / "real_mapping.json").write_text("[]", encoding="utf-8")
        (deploy_root / "annotations" / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "annotations" / "metadata.json").write_text(
            '{"default_source_db":"real_annotations"}',
            encoding="utf-8",
        )
        (deploy_root / "foldseek" / "pdb" / "db.index").write_text("demo", encoding="utf-8")
        (deploy_root / "smoke" / "query.pdb").write_text("HEADER    READINESS TEST\nEND\n", encoding="utf-8")

        env = os.environ.copy()
        env["DEPLOY_DATA_ROOT"] = str(deploy_root)
        env["FOLDSEEK_BINARY"] = "/bin/echo"

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT / "backend",
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "deploy_data_root\tready\t" in result.stdout
        assert "live_sifts\tready\t" in result.stdout
        assert "live_annotations\tready\t" in result.stdout
        assert "live_query_pdb\tready\t" in result.stdout
        assert "live_foldseek_cli\tmissing\t" in result.stdout
        assert "placeholder_binary_rejected" in result.stdout
        assert "summary\tdemo-ready\t" in result.stdout

    def test_structure_smoke_readiness_marks_demo_assets_as_demo_ready(self, tmp_path):
        script = PROJECT_ROOT / "backend" / "scripts" / "structure_smoke_readiness.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "sifts").mkdir(parents=True)
        (deploy_root / "foldseek" / "pdb").mkdir(parents=True)
        (deploy_root / "annotations").mkdir(parents=True)
        (deploy_root / "smoke").mkdir(parents=True)
        (deploy_root / "sifts" / "1abc.json").write_text("[]", encoding="utf-8")
        (deploy_root / "annotations" / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "annotations" / "metadata.json").write_text(
            '{"default_source_db":"local_demo"}',
            encoding="utf-8",
        )
        (deploy_root / "foldseek" / "pdb" / "db.index").write_text("demo", encoding="utf-8")
        (deploy_root / "smoke" / "query.pdb").write_text("HEADER    READINESS TEST\nEND\n", encoding="utf-8")

        env = os.environ.copy()
        env["DEPLOY_DATA_ROOT"] = str(deploy_root)
        env["FOLDSEEK_BINARY"] = "/bin/echo"

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT / "backend",
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "live_sifts\tdemo\t" in result.stdout
        assert "live_annotations\tdemo\t" in result.stdout
        assert "live_foldseek_cli\tmissing\t" in result.stdout
        assert "placeholder_binary_rejected" in result.stdout
        assert "summary\tdemo-ready\t" in result.stdout

    def test_structure_smoke_readiness_require_live_fails_for_demo_assets(self, tmp_path):
        script = PROJECT_ROOT / "backend" / "scripts" / "structure_smoke_readiness.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "sifts").mkdir(parents=True)
        (deploy_root / "foldseek" / "pdb").mkdir(parents=True)
        (deploy_root / "annotations").mkdir(parents=True)
        (deploy_root / "smoke").mkdir(parents=True)
        (deploy_root / "sifts" / "1ABC.json").write_text("[]", encoding="utf-8")
        (deploy_root / "annotations" / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "annotations" / "metadata.json").write_text(
            '{"default_source_db":"local_demo"}',
            encoding="utf-8",
        )
        (deploy_root / "foldseek" / "pdb" / "db.index").write_text("demo", encoding="utf-8")
        (deploy_root / "smoke" / "query.pdb").write_text("HEADER\nEND\n", encoding="utf-8")

        env = os.environ.copy()
        env["DEPLOY_DATA_ROOT"] = str(deploy_root)
        env["FOLDSEEK_BINARY"] = "/bin/echo"

        result = subprocess.run(
            [sys.executable, str(script), "--require-live"],
            cwd=PROJECT_ROOT / "backend",
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "summary\tdemo-ready\t" in result.stdout

    def test_structure_smoke_readiness_requires_nonempty_foldseek_db(self, tmp_path):
        script = PROJECT_ROOT / "backend" / "scripts" / "structure_smoke_readiness.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "sifts").mkdir(parents=True)
        (deploy_root / "annotations").mkdir(parents=True)
        (deploy_root / "smoke").mkdir(parents=True)
        (deploy_root / "foldseek" / "pdb").mkdir(parents=True)
        (deploy_root / "sifts" / "real_mapping.json").write_text("[]", encoding="utf-8")
        (deploy_root / "annotations" / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "smoke" / "query.pdb").write_text("HEADER\nEND\n", encoding="utf-8")

        env = os.environ.copy()
        env["DEPLOY_DATA_ROOT"] = str(deploy_root)
        env["FOLDSEEK_BINARY"] = "/bin/echo"

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT / "backend",
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "live_foldseek_cli\tmissing\t" in result.stdout
        assert "summary\tdemo-ready\t" in result.stdout

    def test_prepare_deploy_data_with_demo(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "prepare_deploy_data.py"
        output_root = tmp_path / "deploy_data"
        result = subprocess.run(
            [sys.executable, str(script), "--output", str(output_root), "--with-demo"],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert (output_root / "annotations" / "base.json").exists()
        assert (output_root / "sifts" / "1abc.json").exists()
        assert (output_root / "smoke" / "query.pdb").exists()
        assert "Demo assets copied" in result.stdout

    def test_import_deploy_data_stages_sources(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "import_deploy_data.py"
        sources = tmp_path / "sources"
        annotations_src = sources / "annotations"
        sifts_src = sources / "sifts"
        foldseek_src = sources / "foldseek"
        smoke_src = sources / "query.pdb"
        (annotations_src).mkdir(parents=True)
        (sifts_src).mkdir(parents=True)
        (foldseek_src / "pdb").mkdir(parents=True)
        (annotations_src / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (sifts_src / "1abc.json").write_text("[]", encoding="utf-8")
        (foldseek_src / "pdb" / "db.index").write_text("demo", encoding="utf-8")
        smoke_src.write_text("HEADER\nEND\n", encoding="utf-8")

        output_root = tmp_path / "deploy_data"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--output",
                str(output_root),
                "--annotations",
                str(annotations_src),
                "--sifts",
                str(sifts_src),
                "--foldseek-root",
                str(foldseek_src),
                "--smoke-pdb",
                str(smoke_src),
            ],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert (output_root / "annotations" / "base.json").exists()
        assert (output_root / "sifts" / "1abc.json").exists()
        assert (output_root / "foldseek" / "pdb" / "db.index").exists()
        assert (output_root / "smoke" / "query.pdb").exists()
        assert (output_root / "import-manifest.json").exists()
        assert "Staged deploy_data root" in result.stdout

    def test_write_deploy_env_generates_override_files(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "write_deploy_env.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "annotations").mkdir(parents=True)
        (deploy_root / "annotations" / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "sifts").mkdir(parents=True)
        (deploy_root / "sifts" / "1abc.json").write_text("[]", encoding="utf-8")
        (deploy_root / "foldseek").mkdir(parents=True)
        (deploy_root / "lipase").mkdir(parents=True)
        (deploy_root / "lipase" / "lipase.db").write_bytes(b"sqlite-format-placeholder")
        (deploy_root / "smoke").mkdir(parents=True)
        (deploy_root / "smoke" / "query.pdb").write_text("HEADER\nEND\n", encoding="utf-8")

        backend_out = tmp_path / "backend.env"
        docker_out = tmp_path / "docker.env"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--deploy-root",
                str(deploy_root),
                "--backend-out",
                str(backend_out),
                "--docker-out",
                str(docker_out),
                "--foldseek-api-url",
                "http://foldseek.local/search",
            ],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        backend_content = backend_out.read_text()
        docker_content = docker_out.read_text()
        assert "DEPLOY_DATA_ROOT=" in backend_content
        assert "LOCAL_ANNOTATION_FIXTURE_PATH=" in backend_content
        assert "SIFTS_MAPPING_PATH=" in backend_content
        assert "FOLDSEEK_DATABASE_ROOT=" in backend_content
        assert "STRUCTURE_SMOKE_PDB_FILE=" in backend_content
        assert "LIPASE_DB_PATH=" in backend_content
        assert "FOLDSEEK_API_URL=http://foldseek.local/search" in backend_content
        assert "DEPLOY_DATA_HOST_PATH=" in docker_content
        assert "LIPASE_DB_PATH=/app/deploy_data/lipase/lipase.db" in docker_content
        assert "FOLDSEEK_API_URL=http://foldseek.local/search" in docker_content
        assert "Wrote backend overrides" in result.stdout

    def test_check_deploy_data_reports_partial_and_ready(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "check_deploy_data.py"
        deploy_root = tmp_path / "deploy_data"
        deploy_root.mkdir(parents=True)

        partial = subprocess.run(
            [sys.executable, str(script), "--root", str(deploy_root)],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "annotations\tmissing\t" in partial.stdout
        assert "summary\tpartial\t" in partial.stdout
        assert "deploy_data/live_manifest.json" in partial.stdout

        (deploy_root / "live_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "data_version": "test-live",
                    "updated_at": "2026-07-09",
                    "required_live_components": ["annotations", "sifts", "pdb", "alphafold", "foldseek", "smoke_query"],
                    "pdb_ids": ["1ABC"],
                    "uniprot_ids": ["P12345"],
                    "download_pae_json": True,
                    "expected_datasets": {
                        "annotations": {"expected_count": 2},
                        "foldseek": {"expected_subdatabases": ["pdb", "alphafold"]},
                    },
                }
            ),
            encoding="utf-8",
        )

        (deploy_root / "annotations").mkdir()
        (deploy_root / "annotations" / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "annotations" / "interpro.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "annotations" / "metadata.json").write_text(
            '{"default_source_db":"real_annotations"}',
            encoding="utf-8",
        )
        (deploy_root / "sifts").mkdir()
        (deploy_root / "sifts" / "1ABC.json").write_text("[]", encoding="utf-8")
        (deploy_root / "pdb").mkdir()
        (deploy_root / "pdb" / "1ABC.cif").write_text("data_1ABC\n", encoding="utf-8")
        (deploy_root / "alphafold").mkdir()
        (deploy_root / "alphafold" / "AF-P12345-F1-model_v1.cif").write_text("data_AF\n", encoding="utf-8")
        (deploy_root / "alphafold" / "AF-P12345-F1-predicted_aligned_error_v1.json").write_text("{}", encoding="utf-8")
        (deploy_root / "foldseek" / "pdb").mkdir(parents=True)
        (deploy_root / "foldseek" / "pdb" / "db.index").write_text("demo", encoding="utf-8")
        (deploy_root / "foldseek" / "alphafold").mkdir(parents=True)
        (deploy_root / "foldseek" / "alphafold" / "db.index").write_text("demo", encoding="utf-8")
        (deploy_root / "smoke").mkdir()
        (deploy_root / "smoke" / "query.pdb").write_text("HEADER\nEND\n", encoding="utf-8")

        ready = subprocess.run(
            [sys.executable, str(script), "--root", str(deploy_root)],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "annotations\tready\t" in ready.stdout
        assert "sifts\tready\t" in ready.stdout
        assert "pdb\tready\t" in ready.stdout
        assert "alphafold\tready\t" in ready.stdout
        assert "foldseek\tready\t" in ready.stdout
        assert "smoke_query\tready\t" in ready.stdout
        assert "summary\tlive-data-ready\t" in ready.stdout

    def test_check_deploy_data_flags_nonportable_foldseek_symlinks(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "check_deploy_data.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "annotations").mkdir(parents=True)
        (deploy_root / "annotations" / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "annotations" / "metadata.json").write_text(
            '{"default_source_db":"real_annotations"}',
            encoding="utf-8",
        )
        (deploy_root / "sifts").mkdir()
        (deploy_root / "sifts" / "real_mapping.json").write_text("[]", encoding="utf-8")
        foldseek_pdb = deploy_root / "foldseek" / "pdb"
        foldseek_pdb.mkdir(parents=True)
        target = tmp_path / "outside.index"
        target.write_text("real", encoding="utf-8")
        (foldseek_pdb / "db.index").write_text("demo", encoding="utf-8")
        (foldseek_pdb / "db_ss_h").symlink_to(target)
        (deploy_root / "smoke").mkdir()
        (deploy_root / "smoke" / "query.pdb").write_text("HEADER\nEND\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(script), "--root", str(deploy_root)],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "foldseek\tpartial\tnon-portable symlinks detected:" in result.stdout
        assert "summary\tpartial\t" in result.stdout

    def test_materialize_foldseek_links_replaces_symlinks(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "materialize_foldseek_links.py"
        foldseek_root = tmp_path / "foldseek"
        foldseek_root.mkdir()
        target = tmp_path / "db.target"
        target.write_text("payload", encoding="utf-8")
        link = foldseek_root / "db.link"
        link.symlink_to(target)

        result = subprocess.run(
            [sys.executable, str(script), "--root", str(foldseek_root)],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert link.exists()
        assert not link.is_symlink()
        assert link.read_text(encoding="utf-8") == "payload"
        assert "Materialized 1 Foldseek symlink" in result.stdout

    def test_check_deploy_data_reports_demo_only(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "check_deploy_data.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "annotations").mkdir(parents=True)
        (deploy_root / "annotations" / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "annotations" / "metadata.json").write_text(
            '{"default_source_db":"local_demo"}',
            encoding="utf-8",
        )
        (deploy_root / "sifts").mkdir()
        (deploy_root / "sifts" / "1abc.json").write_text("[]", encoding="utf-8")
        (deploy_root / "smoke").mkdir()
        (deploy_root / "smoke" / "query.pdb").write_text("HEADER\nEND\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(script), "--root", str(deploy_root)],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "annotations\tdemo\t" in result.stdout
        assert "sifts\tdemo\t" in result.stdout
        assert "summary\tdemo-data-only\t" in result.stdout

    def test_check_deploy_data_require_live_fails_for_demo_assets(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "check_deploy_data.py"
        deploy_root = tmp_path / "deploy_data"
        (deploy_root / "annotations").mkdir(parents=True)
        (deploy_root / "annotations" / "base.json").write_text('{"records":[]}', encoding="utf-8")
        (deploy_root / "annotations" / "metadata.json").write_text(
            '{"default_source_db":"local_demo"}',
            encoding="utf-8",
        )
        (deploy_root / "sifts").mkdir()
        (deploy_root / "sifts" / "1abc.json").write_text("[]", encoding="utf-8")
        (deploy_root / "foldseek" / "pdb").mkdir(parents=True)
        (deploy_root / "foldseek" / "pdb" / "db.index").write_text("demo", encoding="utf-8")
        (deploy_root / "smoke").mkdir()
        (deploy_root / "smoke" / "query.pdb").write_text("HEADER\nEND\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(script), "--root", str(deploy_root), "--require-live"],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "summary\tdemo-data-only\t" in result.stdout

    def test_discover_deploy_data_sources_finds_expected_candidates(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "discover_deploy_data_sources.py"
        root = tmp_path / "workspace"
        (root / "exports" / "annotations").mkdir(parents=True)
        (root / "exports" / "sifts").mkdir(parents=True)
        (root / "exports" / "foldseek").mkdir(parents=True)
        (root / "exports" / "alphafold").mkdir(parents=True)
        (root / "exports" / "annotations" / "interpro.json").write_text("{}", encoding="utf-8")
        (root / "exports" / "sifts" / "real_mapping.json").write_text("[]", encoding="utf-8")
        (root / "exports" / "foldseek" / "alis_pdb100.m8").write_text("", encoding="utf-8")
        (root / "exports" / "alphafold" / "A0A1.pdb").write_text("HEADER\nEND\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(script), "--root", str(root)],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "annotations\t" in result.stdout
        assert "sifts\t" in result.stdout
        assert "foldseek_reference\t" in result.stdout
        assert "alphafold_reference\t" in result.stdout


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

    def test_backend_dockerfile_selects_foldseek_by_arch(self):
        df = PROJECT_ROOT / "docker" / "Dockerfile.backend"
        content = df.read_text()
        assert "ARG TARGETARCH" in content
        assert "foldseek-linux-arm64.tar.gz" in content
        assert "foldseek-linux-avx2.tar.gz" in content

    def test_ligand_worker_dockerfile_has_chemistry_runtime(self):
        df = PROJECT_ROOT / "docker" / "Dockerfile.ligand-worker"
        content = df.read_text()
        assert "openbabel" in content
        assert "autodock-vina" in content
        assert "gromacs" in content
        assert "acpype" in content
        assert "rdkit" in content
        assert "antechamber" in content
        assert "parmchk2" in content
        assert "AMBERHOME" in content
        assert "LIGAND_RUNTIME_BOUNDARY" in content
        assert "ligand-runtime-check" in content
        assert "--require-live" in content
        assert "--queues=ligand_cpu" in content
        assert "requirements-prod.txt" in content
        assert '"ligand_topology": tools["acpype"]["available"]' in content

    def test_aliyun_ligand_worker_dockerfile_is_backend_overlay(self):
        df = PROJECT_ROOT / "docker" / "Dockerfile.ligand-worker.aliyun"
        content = df.read_text()
        assert "FROM protein-ai-backend:aliyun" in content
        assert "openbabel" in content
        assert "autodock-vina" in content
        assert "acpype" in content
        assert "rdkit" in content
        assert "AMBERHOME" in content
        assert "antechamber" in content
        assert "parmchk2" in content
        assert "teLeap" in content
        assert "libhdf4-0" in content
        assert "libhdf5-hl-310" in content
        assert "libzip5" in content
        assert "libcrypto.so.3.bundled" in content
        assert "mirrors.aliyun.com/debian" in content
        assert "mirrors.aliyun.com/pypi/simple" in content
        assert "ligand-runtime-check" in content
        assert "COPY --chown=appuser:appuser backend/ /app/" in content
        assert "--queues=ligand_cpu" in content

    def test_ligand_runtime_check_requires_tleap_loadable(self):
        script = PROJECT_ROOT / "docker" / "ligand-runtime-check.py"
        content = script.read_text()
        assert "teLeap" in content
        assert "require_all=True" in content
        assert "error while loading shared libraries" in content
        assert "command_checks" in content
        assert "scientific_smoke_status" in content
        assert "runtime_capability_only" in content


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
        # Should have health checks for backend, workers, frontend
        assert "curl" in compose_content or "wget" in compose_content

    def test_md_worker_queue_isolated(self, compose_content):
        assert "md-worker:" in compose_content, "Dedicated md-worker service missing"
        assert "--queues=md_cpu" in compose_content, "md-worker must consume md_cpu queue"
        assert "CELERY_MD_WORKER_CONCURRENCY" in compose_content, "md-worker concurrency env missing"

    def test_ligand_worker_queue_isolated(self, compose_content):
        assert "ligand-worker:" in compose_content, "Dedicated ligand-worker service missing"
        assert "Dockerfile.ligand-worker" in compose_content, "ligand-worker must use dedicated chemistry runtime"
        assert "--queues=ligand_cpu" in compose_content, "ligand-worker must consume ligand_cpu queue"
        assert "CELERY_LIGAND_WORKER_CONCURRENCY" in compose_content, "ligand-worker concurrency env missing"
        assert "LIGAND_RUNTIME_BOUNDARY: ligand_worker_only" in compose_content
        assert "LIGAND_RUNTIME_CHECK: /usr/local/bin/ligand-runtime-check" in compose_content
        assert "AMBERHOME: ${AMBERHOME:-/opt/ambertools}" in compose_content
        assert "ligand_scratch:/app/storage" in compose_content

    def test_deploy_data_mount_present_for_app_services(self, compose_content):
        assert "DEPLOY_DATA_ROOT: /app/deploy_data" in compose_content
        assert "${DEPLOY_DATA_HOST_PATH:-../deploy_data}:/app/deploy_data:ro" in compose_content
        assert "- .env.deploy-data" in compose_content

    def test_default_worker_stays_on_default_queue(self, compose_content):
        assert "--queues=default" in compose_content, "default worker must stay on default queue"
        assert "CELERY_DEFAULT_WORKER_CONCURRENCY" in compose_content, "default worker concurrency env missing"

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

    def test_aliyun_app_compose_uses_managed_services(self):
        compose = PROJECT_ROOT / "docker" / "docker-compose.aliyun-app.yml"
        content = compose.read_text()
        assert "ALIYUN_APP_DATABASE_URL" in content
        assert "ALIYUN_REDIS_HOST" in content
        assert "ALIYUN_OSS_ENDPOINT" in content
        assert "FORCE_HTTPS: ${OUTLINE_FORCE_HTTPS:-false}" in content
        assert "ligand-worker:" in content
        assert "protein-ai-ligand-worker:aliyun" in content
        assert "--queues=ligand_cpu" in content
        assert "md-worker:" in content
        assert "--queues=md_cpu" in content
        assert "Dockerfile.ligand-worker.aliyun" in content
        assert "LIGAND_RUNTIME_CHECK: /usr/local/bin/ligand-runtime-check" in content
        assert "\n  postgres:\n" not in content
        assert "\n  minio:\n" not in content
        assert "\n  redis:\n" not in content

    def test_aliyun_gpu_compose_only_runs_md_worker(self):
        compose = PROJECT_ROOT / "docker" / "docker-compose.aliyun-gpu.yml"
        content = compose.read_text()
        assert "md-worker:" in content
        assert "ligand-worker:" in content
        assert "--queues=md_cpu" in content
        assert "--queues=ligand_cpu" in content
        assert "Dockerfile.ligand-worker.aliyun" in content
        assert "LIGAND_RUNTIME_BOUNDARY: ligand_worker_only" in content
        assert "LIGAND_RUNTIME_CHECK: /usr/local/bin/ligand-runtime-check" in content
        assert "GPU_DEVICE_REQUEST" in content
        assert "\n  frontend:\n" not in content
        assert "\n  backend:\n" not in content


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

    def test_top_level_wiki_navigation_returns_spa(self, nginx_content):
        """Top-level /wiki/* documents must hit SPA auth before Outline."""
        assert "$wiki_spa_document" in nginx_content
        assert "~^document:/wiki/(home|search)$" in nginx_content
        assert "~^document:/wiki/(doc|collection)/" in nginx_content
        assert "error_page 418 = @frontend_spa" in nginx_content
        assert "error_page 418 = @frontend_spa_tls" in nginx_content
        assert "proxy_pass http://$frontend_host/index.html" in nginx_content

    def test_outline_native_routes_proxy_to_backend(self, nginx_content):
        """Embedded Outline documents use root routes because /wiki subpaths break Outline SPA routing."""
        assert "^/(doc|collection|search|settings|archive|drafts|trash|templates|share|s)(/|$)" in nginx_content
        assert "proxy_pass http://$backend_host$request_uri" in nginx_content

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


class TestProductionConfigGate:
    def test_production_config_script_redacts_secrets_and_allows_ip_stage(self, tmp_path):
        env_file = tmp_path / ".env.production"
        env_file.write_text(
            "\n".join([
                "DEBUG=false",
                "SECRET_KEY=this-is-a-long-random-test-secret-value",
                "OIDC_CLIENT_SECRET=this-is-a-long-oidc-test-secret",
                "ALIYUN_APP_DATABASE_URL=postgresql+asyncpg://user:pass@pg.example.com:5432/protein_ai",
                "ALIYUN_REDIS_HOST=redis.example.com",
                "ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou-internal.aliyuncs.com",
                "ALIYUN_OSS_BUCKET=protein-ai-files",
                "ALIYUN_OSS_ACCESS_KEY_ID=test-access-key",
                "ALIYUN_OSS_ACCESS_KEY_SECRET=this-is-a-long-storage-secret",
                "LLM_PROVIDER=kuaPao",
                "KUAPAO_API_KEY=test-llm-key",
                "PUBLIC_BASE_URL=http://120.27.108.138",
                "OUTLINE_API_TOKEN=ol_api_12345678901234567890123456789012345678",
                "OUTLINE_API_URL=http://outline:3001/api",
            ]),
            encoding="utf-8",
        )

        isolated_env = os.environ.copy()
        for key in (
            "DEBUG",
            "SECRET_KEY",
            "OIDC_CLIENT_SECRET",
            "DATABASE_URL",
            "ALIYUN_APP_DATABASE_URL",
            "REDIS_URL",
            "REDIS_HOST",
            "ALIYUN_REDIS_APP_URL",
            "ALIYUN_REDIS_HOST",
            "MINIO_ENDPOINT",
            "MINIO_BUCKET",
            "MINIO_ACCESS_KEY",
            "MINIO_SECRET_KEY",
            "ALIYUN_OSS_ENDPOINT",
            "ALIYUN_OSS_BUCKET",
            "ALIYUN_OSS_ACCESS_KEY_ID",
            "ALIYUN_OSS_ACCESS_KEY_SECRET",
            "LLM_PROVIDER",
            "KUAPAO_API_KEY",
            "PUBLIC_BASE_URL",
            "FRONTEND_URL",
            "OIDC_ISSUER",
            "OIDC_PRIVATE_KEY_PATH",
            "OIDC_PUBLIC_KEY_PATH",
            "OUTLINE_API_TOKEN",
            "OUTLINE_API_URL",
        ):
            isolated_env.pop(key, None)

        proc = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "check_production_config.py"),
                "--json",
                "--mode",
                "production",
                "--skip-domain-https",
                "--env-file",
                str(env_file),
            ],
            cwd=PROJECT_ROOT,
            env=isolated_env,
            text=True,
            capture_output=True,
            check=False,
        )

        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        assert payload["summary"]["critical"] == 0
        assert payload["secrets_printed"] is False
        assert "this-is-a-long-storage-secret" not in proc.stdout
        assert "this-is-a-long-random-test-secret-value" not in proc.stdout

    def test_production_config_blocks_missing_outline_api_token(self, tmp_path):
        env_file = tmp_path / ".env.production"
        env_file.write_text(
            "\n".join([
                "DEBUG=false",
                "SECRET_KEY=this-is-a-long-random-test-secret-value",
                "OIDC_CLIENT_SECRET=this-is-a-long-oidc-test-secret",
                "ALIYUN_APP_DATABASE_URL=postgresql+asyncpg://user:pass@pg.example.com:5432/protein_ai",
                "ALIYUN_REDIS_HOST=redis.example.com",
                "ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou-internal.aliyuncs.com",
                "ALIYUN_OSS_BUCKET=protein-ai-files",
                "ALIYUN_OSS_ACCESS_KEY_ID=test-access-key",
                "ALIYUN_OSS_ACCESS_KEY_SECRET=this-is-a-long-storage-secret",
                "LLM_PROVIDER=kuaPao",
                "KUAPAO_API_KEY=test-llm-key",
                "PUBLIC_BASE_URL=http://120.27.108.138",
            ]),
            encoding="utf-8",
        )

        isolated_env = os.environ.copy()
        for key in ("OUTLINE_API_TOKEN", "OUTLINE_API_URL"):
            isolated_env.pop(key, None)

        proc = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "check_production_config.py"),
                "--json",
                "--mode",
                "production",
                "--skip-domain-https",
                "--env-file",
                str(env_file),
            ],
            cwd=PROJECT_ROOT,
            env=isolated_env,
            text=True,
            capture_output=True,
            check=False,
        )

        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        outline_check = next(item for item in payload["checks"] if item["name"] == "OUTLINE_API_TOKEN")
        assert outline_check["status"] == "critical"
        assert payload["secrets_printed"] is False

    def test_production_config_blocks_change_me_placeholders(self, tmp_path):
        env_file = tmp_path / ".env.production"
        env_file.write_text(
            "\n".join([
                "DEBUG=false",
                "SECRET_KEY=this-is-a-long-random-test-secret-value",
                "OIDC_CLIENT_SECRET=this-is-a-long-oidc-test-secret",
                "ALIYUN_APP_DATABASE_URL=postgresql+asyncpg://CHANGE_ME_USER:CHANGE_ME_PASSWORD@pg.example.com:5432/protein_ai",
                "ALIYUN_REDIS_HOST=CHANGE_ME_REDIS_ENDPOINT",
                "ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou-internal.aliyuncs.com",
                "ALIYUN_OSS_BUCKET=protein-ai-files",
                "ALIYUN_OSS_ACCESS_KEY_ID=CHANGE_ME_ACCESS_KEY",
                "ALIYUN_OSS_ACCESS_KEY_SECRET=this-is-a-long-storage-secret",
                "LLM_PROVIDER=kuaPao",
                "KUAPAO_API_KEY=CHANGE_ME_LLM_KEY",
                "PUBLIC_BASE_URL=http://120.27.108.138",
                "OUTLINE_API_TOKEN=ol_api_12345678901234567890123456789012345678",
                "OUTLINE_API_URL=http://outline:3001/api",
            ]),
            encoding="utf-8",
        )

        isolated_env = os.environ.copy()
        for key in (
            "DATABASE_URL",
            "ALIYUN_APP_DATABASE_URL",
            "REDIS_URL",
            "REDIS_HOST",
            "ALIYUN_REDIS_APP_URL",
            "ALIYUN_REDIS_HOST",
            "MINIO_ENDPOINT",
            "MINIO_BUCKET",
            "MINIO_ACCESS_KEY",
            "MINIO_SECRET_KEY",
            "ALIYUN_OSS_ENDPOINT",
            "ALIYUN_OSS_BUCKET",
            "ALIYUN_OSS_ACCESS_KEY_ID",
            "ALIYUN_OSS_ACCESS_KEY_SECRET",
            "LLM_PROVIDER",
            "KUAPAO_API_KEY",
        ):
            isolated_env.pop(key, None)

        proc = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "check_production_config.py"),
                "--json",
                "--mode",
                "production",
                "--skip-domain-https",
                "--env-file",
                str(env_file),
            ],
            cwd=PROJECT_ROOT,
            env=isolated_env,
            text=True,
            capture_output=True,
            check=False,
        )

        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        checks = {item["name"]: item for item in payload["checks"]}
        assert checks["DATABASE_URL"]["status"] == "critical"
        assert checks["REDIS"]["status"] == "critical"
        assert checks["OBJECT_STORAGE"]["status"] == "critical"
        assert checks["LLM_PROVIDER_KEY"]["status"] == "critical"
        assert payload["summary"]["critical"] >= 4
        assert "CHANGE_ME_PASSWORD" not in proc.stdout
        assert payload["secrets_printed"] is False

    def test_production_config_prefers_managed_oss_over_shadowed_minio_defaults(self, tmp_path):
        env_file = tmp_path / ".env.production"
        env_file.write_text(
            "\n".join([
                "DEBUG=false",
                "SECRET_KEY=this-is-a-long-random-test-secret-value",
                "OIDC_CLIENT_SECRET=this-is-a-long-oidc-test-secret",
                "ALIYUN_APP_DATABASE_URL=postgresql+asyncpg://user:pass@pg.example.com:5432/protein_ai",
                "ALIYUN_REDIS_HOST=redis.example.com",
                "MINIO_ENDPOINT=localhost:9000",
                "MINIO_BUCKET=protein-files",
                "MINIO_ACCESS_KEY=minioadmin",
                "MINIO_SECRET_KEY=change-me-minio-password",
                "ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou-internal.aliyuncs.com",
                "ALIYUN_OSS_BUCKET=protein-ai-files",
                "ALIYUN_OSS_ACCESS_KEY_ID=test-access-key",
                "ALIYUN_OSS_ACCESS_KEY_SECRET=this-is-a-long-storage-secret",
                "LLM_PROVIDER=kuapao",
                "KUAPAO_API_KEY=test-llm-key",
                "PUBLIC_BASE_URL=http://120.27.108.138",
                "OUTLINE_API_TOKEN=ol_api_12345678901234567890123456789012345678",
                "OUTLINE_API_URL=http://outline:3001/api",
            ]),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "check_production_config.py"),
                "--json", "--mode", "production", "--skip-domain-https",
                "--env-file", str(env_file),
            ],
            cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
        )
        assert proc.returncode == 0
        payload = json.loads(proc.stdout)
        checks = {item["name"]: item for item in payload["checks"]}
        assert checks["OBJECT_STORAGE"]["status"] == "ok"

    def test_production_config_blocks_public_http_without_explicit_skip(self, tmp_path):
        env_file = tmp_path / ".env.production"
        env_file.write_text(
            "\n".join([
                "DEBUG=false",
                "SECRET_KEY=this-is-a-long-random-test-secret-value",
                "OIDC_CLIENT_SECRET=this-is-a-long-oidc-test-secret",
                "DATABASE_URL=postgresql+asyncpg://user:pass@pg.example.com:5432/protein_ai",
                "REDIS_URL=redis://redis.example.com:6379/0",
                "MINIO_ENDPOINT=localhost:9000",
                "MINIO_BUCKET=protein-files",
                "MINIO_ACCESS_KEY=test-access-key",
                "MINIO_SECRET_KEY=this-is-a-long-storage-secret",
                "LLM_PROVIDER=kuapao",
                "KUAPAO_API_KEY=test-llm-key",
                "PUBLIC_BASE_URL=http://120.27.108.138",
                "OUTLINE_API_TOKEN=ol_api_12345678901234567890123456789012345678",
                "OUTLINE_API_URL=http://outline:3001/api",
            ]),
            encoding="utf-8",
        )
        strict = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "check_production_config.py"),
                "--json", "--mode", "production", "--require-production-safe",
                "--env-file", str(env_file),
            ], cwd=PROJECT_ROOT, env={"PATH": os.environ.get("PATH", "")}, text=True, capture_output=True, check=False,
        )
        strict_payload = json.loads(strict.stdout)
        strict_checks = {item["name"]: item for item in strict_payload["checks"]}
        assert strict.returncode == 1
        assert strict_checks["PUBLIC_BASE_URL_HTTPS"]["status"] == "critical"

        prepared = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "check_production_config.py"),
                "--json", "--mode", "production", "--require-production-safe", "--skip-domain-https",
                "--env-file", str(env_file),
            ], cwd=PROJECT_ROOT, env={"PATH": os.environ.get("PATH", "")}, text=True, capture_output=True, check=False,
        )
        assert prepared.returncode == 0

    def test_acceptance_and_nightly_include_production_config_gate(self):
        acceptance = (PROJECT_ROOT / "scripts" / "run_acceptance_matrix.py").read_text(encoding="utf-8")
        upgrade = (PROJECT_ROOT / "scripts" / "check_upgrade_readiness.py").read_text(encoding="utf-8")
        nightly = (PROJECT_ROOT / "scripts" / "run_nightly_live_gates.py").read_text(encoding="utf-8")
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        assert "production_config_gate" in acceptance
        assert "check_production_config.py" in acceptance
        assert "--require-production-safe" in acceptance
        assert "docker/.env" in acceptance
        assert "docker/.env.aliyun.app" in acceptance
        assert "check_production_config.py" in upgrade
        assert 'PROJECT_ROOT / "docker" / ".env"' in upgrade
        assert 'PROJECT_ROOT / "docker" / ".env.aliyun.app"' in upgrade
        assert "production_config" in nightly
        assert "--require-production-safe" in nightly
        assert "nightly-live-gates" in makefile
        assert "production-config-gate-json" in makefile
        assert "--require-production-safe" in makefile

    def test_p2_p3_p4_roadmap_is_read_only_and_fail_closed(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "build_p2_p3_p4_roadmap.py"
        output_json = tmp_path / "p2-p3-p4-roadmap.json"
        output_md = tmp_path / "p2-p3-p4-roadmap.md"
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        assert "p2-p3-p4-roadmap" in makefile
        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "network_io" in content
        assert "destructive_actions" in content
        assert "live_gate_execution_allowed" in content
        assert "P4 is defined as production-grade closed-loop operation" in content
        assert "p4_closed_loop_readiness_v1" in content
        assert "p4_active_learning_batch_contract_v1" in content
        assert "p4_model_calibration_registry_contract_v1" in content
        assert "p4_manufacturing_constraint_schema_v1" in content
        assert "p2_candidate_readiness_summary_v1" in content
        assert "p2_objective_score_readiness_summary_v1" in content
        assert "p2_structure_feature_gap_summary_v1" in content
        assert "p2_objective_assay_gap_summary_v1" in content
        assert "experiment_design_schedulability_policy_v1" in content
        assert "dbtl_project_memory_readiness_v1" in content
        assert "dbtl_feedback_readiness_summary_v1" in content
        assert "dbtl_readiness_bridge_v1" in content
        assert "p4_operator_review_contract_v1" in content

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        stdout_payload = json.loads(result.stdout)
        payload = json.loads(output_json.read_text(encoding="utf-8"))
        assert stdout_payload["network_io"] == "not_executed"
        assert payload["mode"] == "read_only_p2_p3_p4_roadmap"
        assert payload["network_io"] == "not_executed"
        assert payload["destructive_actions"] == "not_executed"
        assert payload["secrets_printed"] is False
        assert payload["live_gate_execution_allowed"] is False
        assert payload["phase_summary"]["P2"]["ready_local_contract"] == 3
        assert payload["phase_summary"]["P3"]["ready_local_contract"] == 2
        assert payload["phase_summary"]["P4"]["ready_local_contract"] == 1
        by_name = {item["name"]: item for item in payload["items"]}
        assert by_name["objective_score_contract"]["status"] == "ready_local_contract"
        assert "single objective total score" in by_name["objective_score_contract"]["must_not_claim"]
        assert "p2_objective_score_readiness_summary_v1" in by_name["objective_score_contract"]["evidence_tokens"]
        assert "p2_candidate_readiness_summary_v1" in by_name["candidate_table_generation_contract"]["evidence_tokens"]
        assert "experiment_design_schedulability_policy_v1" in by_name["candidate_table_generation_contract"]["evidence_tokens"]
        assert "dbtl_project_memory_readiness_v1" in by_name["dbtl_trace_contract"]["evidence_tokens"]
        assert "dbtl_feedback_readiness_summary_v1" in by_name["feedback_import_and_next_round_contract"]["evidence_tokens"]
        assert by_name["industrial_closed_loop_readiness"]["status"] == "ready_local_contract"
        assert "p4_active_learning_batch_contract_v1" in by_name["industrial_closed_loop_readiness"]["evidence_tokens"]
        assert "p4_model_calibration_registry_contract_v1" in by_name["industrial_closed_loop_readiness"]["evidence_tokens"]
        assert "p4_manufacturing_constraint_schema_v1" in by_name["industrial_closed_loop_readiness"]["evidence_tokens"]
        assert "model is retrained" in by_name["industrial_closed_loop_readiness"]["must_not_claim"]
        md = output_md.read_text(encoding="utf-8")
        assert "P2/P3/P4 Roadmap" in md
        assert "p2_candidate_readiness_summary_v1" in md
        assert "p2_objective_score_readiness_summary_v1" in md
        assert "p2_structure_feature_gap_summary_v1" in md
        assert "p2_objective_assay_gap_summary_v1" in md
        assert "experiment_design_schedulability_policy_v1" in md
        assert "dbtl_project_memory_readiness_v1" in md
        assert "dbtl_feedback_readiness_summary_v1" in md
        assert "dbtl_readiness_bridge_v1" in md
        assert "p4_operator_review_contract_v1" in md
        assert "p4_active_learning_batch_contract_v1" in md
        assert "p4_model_calibration_registry_contract_v1" in md
        assert "p4_manufacturing_constraint_schema_v1" in md
        assert "industrial_closed_loop_readiness" in md

    def test_p0_p4_gap_audit_is_read_only_and_source_bound(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "build_p0_p4_gap_audit.py"
        output_json = tmp_path / "p0-p4-gap-audit.json"
        output_md = tmp_path / "p0-p4-gap-audit.md"
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        assert "p0-p4-gap-audit" in makefile
        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "read_only_p0_p4_gap_audit" in content
        assert "network_io" in content
        assert "destructive_actions" in content
        assert "live_gate_execution_allowed" in content
        assert "specified_mutation_reviews" in content
        assert "reaction_profile_v1" in content
        assert "wt_baseline_registry_v1" in content
        assert "p4_active_learning_batch_contract_v1" in content
        assert "covered_by_contract_status_export" in content
        assert "STATUS_EXPORT_COVERED_LOCAL_GAPS" in content
        assert "open_local_gap_count" in content

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        stdout_payload = json.loads(result.stdout)
        payload = json.loads(output_json.read_text(encoding="utf-8"))
        assert stdout_payload["network_io"] == "not_executed"
        assert payload["mode"] == "read_only_p0_p4_gap_audit"
        assert payload["network_io"] == "not_executed"
        assert payload["destructive_actions"] == "not_executed"
        assert payload["secrets_printed"] is False
        assert payload["live_gate_execution_allowed"] is False
        assert set(payload["phase_summary"]) == {"P0", "P1", "P2", "P3", "P4"}
        assert payload["phase_summary"]["P0"]["ready_local_contract"] == 4
        assert payload["phase_summary"]["P1"]["ready_local_contract"] == 4
        assert payload["phase_summary"]["P2"]["ready_local_contract"] == 3
        assert payload["phase_summary"]["P3"]["ready_local_contract"] == 2
        assert payload["phase_summary"]["P4"]["ready_local_contract"] == 1
        assert payload["phase_summary"]["P0"]["covered_local_gap_count"] >= 1
        assert "open_local_gap_count" in payload["phase_summary"]["P2"]
        # The optional live ligand image gate depends on the host runtime.
        assert payload["remaining_backlog_summary"]["counts"]["external_required"] in {6, 7}
        by_name = {item["name"]: item for item in payload["items"]}
        assert "specified_mutation_reviews" in by_name["specified_mutation_review"]["evidence_tokens"]
        assert "unified_numbering_registry_v1" in by_name["numbering_registry"]["evidence_tokens"]
        assert "reaction_profile_v1" in by_name["reaction_profile"]["evidence_tokens"]
        assert "wt_baseline_registry_v1" in by_name["wt_baseline_registry"]["evidence_tokens"]
        assert "p4_active_learning_batch_contract_v1" in by_name["industrial_closed_loop_readiness"]["evidence_tokens"]
        assert (
            by_name["residue_feature_table_contract"]["local_gap_status"]["covered"][0]["status"]
            == "covered_by_contract_status_export"
        )
        md = output_md.read_text(encoding="utf-8")
        assert "P0-P4 Gap Audit" in md
        assert "specified_mutation_review" in md
        assert "catalytic_mechanism_profile" in md
        assert "Covered local gaps" in md
        assert "Remaining External Backlog" in md
        assert "live gates have run" in md

    def test_p0_p4_status_export_is_read_only_and_consumes_gap_audit(self, tmp_path):
        script = PROJECT_ROOT / "scripts" / "build_p0_p4_status_export.py"
        gap_script = PROJECT_ROOT / "scripts" / "build_p0_p4_gap_audit.py"
        input_json = tmp_path / "p0-p4-gap-audit.json"
        input_md = tmp_path / "p0-p4-gap-audit.md"
        output_json = tmp_path / "p0-p4-status-export.json"
        output_md = tmp_path / "p0-p4-status-export.md"
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        assert "p0-p4-status-export" in makefile
        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "p0_p4_status_export_v1" in content
        assert "p0_p4_status_export_contract_v1" in content
        assert "read_only_p0_p4_status_export" in content
        assert "must_label_ready_local_contract_as_not_live_complete" in content
        assert "must_keep_external_required_blocked" in content
        assert "open_local_gaps_are_read_from_gap_audit" in content
        assert "p0_p4_contract_status_export_v1" in content
        assert "contract_status_items" in content
        assert "approval_required" in content

        subprocess.run(
            [
                sys.executable,
                str(gap_script),
                "--output-json",
                str(input_json),
                "--output-md",
                str(input_md),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--input-json",
                str(input_json),
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        stdout_payload = json.loads(result.stdout)
        payload = json.loads(output_json.read_text(encoding="utf-8"))
        assert stdout_payload["schema_version"] == "p0_p4_status_export_v1"
        assert stdout_payload["network_io"] == "not_executed"
        assert payload["mode"] == "read_only_p0_p4_status_export"
        assert payload["network_io"] == "not_executed"
        assert payload["destructive_actions"] == "not_executed"
        assert payload["secrets_printed"] is False
        assert payload["live_gate_execution_allowed"] is False
        assert payload["status_export_contract"]["schema_version"] == "p0_p4_status_export_contract_v1"
        assert payload["status_export_contract"]["must_label_ready_local_contract_as_not_live_complete"] is True
        assert payload["status_export_contract"]["must_keep_external_required_blocked"] is True
        assert payload["status_export_contract"]["open_local_gaps_are_read_from_gap_audit"] is True
        assert [row["phase"] for row in payload["phase_status"]] == ["P0", "P1", "P2", "P3", "P4"]
        assert all(row["status"] == "ready_local_contract" for row in payload["phase_status"])
        assert all("covered_local_gap_count" in row for row in payload["phase_status"])
        assert len(payload["contract_status_items"]) == 14
        contracts = {item["contract_name"]: item for item in payload["contract_status_items"]}
        for name in [
            "residue_feature_table_contract",
            "objective_score_contract",
            "candidate_table_generation_contract",
            "dbtl_trace_contract",
            "feedback_import_and_next_round_contract",
            "industrial_closed_loop_readiness",
        ]:
            assert contracts[name]["read_only"] is True
            assert contracts[name]["approval_required"] is True
            assert contracts[name]["capability_boundary"]["ready_local_contract_is_not_live_complete"] is True
            assert contracts[name]["capability_boundary"]["may_train_model"] is False
            assert contracts[name]["capability_boundary"]["may_run_live_gate"] is False
        assert "p2_structure_feature_gap_summary_v1" in contracts["residue_feature_table_contract"]["evidence_tokens"]
        assert "p2_objective_assay_gap_summary_v1" in contracts["objective_score_contract"]["evidence_tokens"]
        assert "dbtl_readiness_bridge_v1" in contracts["dbtl_trace_contract"]["evidence_tokens"]
        assert "p4_operator_review_contract_v1" in contracts["industrial_closed_loop_readiness"]["evidence_tokens"]
        assert contracts["industrial_closed_loop_readiness"]["approval_state"] == "blocked_until_explicit_review"
        assert payload["status_export_contract"]["contract_status_items_are_source_bound"] is True
        assert payload["status_export_contract"]["covered_followups_do_not_clear_external_blockers"] is True
        assert payload["status_export_contract"]["local_followups_are_not_capability_completion"] is True
        # Six, not seven: ligand_runtime_live is ready via the ligand worker image.
        assert payload["remaining_backlog_summary"]["counts"]["external_required"] in {6, 7}
        assert "formal_domain_https" in payload["external_followups"]
        assert "ready local contract means production complete" in payload["must_not_claim"]
        md = output_md.read_text(encoding="utf-8")
        assert "P0-P4 Status Export" in md
        assert "Phase Status" in md
        assert "Contract Status Items" in md
        assert "industrial_closed_loop_readiness" in md
        assert "ready local contract must not be described as live complete" in md
        assert "formal_domain_https" in md

    def test_p0_p4_backlog_ticket_bridge_is_source_bound_and_explicit(self, tmp_path):
        bridge_script = PROJECT_ROOT / "scripts" / "build_p0_p4_backlog_ticket_bridge.py"
        validator_script = PROJECT_ROOT / "scripts" / "validate_p0_p4_backlog_ticket_bridge.py"
        status_export = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-status-export.json"
        execution_tickets = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-execution-tickets.json"
        go_no_go = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-go-no-go-summary.json"
        output_json = tmp_path / "p0-p4-backlog-ticket-bridge.json"
        output_md = tmp_path / "p0-p4-backlog-ticket-bridge.md"
        validation_report = tmp_path / "p0-p4-backlog-ticket-bridge-validation-report.json"
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        assert "p0-p4-backlog-ticket-bridge" in makefile
        assert "p0-p4-backlog-ticket-bridge-validate" in makefile
        result = subprocess.run(
            [
                sys.executable,
                str(bridge_script),
                "--status-export",
                str(status_export),
                "--execution-tickets",
                str(execution_tickets),
                "--go-no-go",
                str(go_no_go),
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
                "--json",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        stdout = json.loads(result.stdout)
        payload = json.loads(output_json.read_text(encoding="utf-8"))
        assert stdout["contract_count"] == 14
        assert stdout["ticket_count"] == 7
        assert payload["mode"] == "read_only_p0_p4_backlog_ticket_bridge"
        assert payload["network_io"] == "not_executed"
        assert payload["destructive_actions"] == "not_executed"
        assert payload["secrets_printed"] is False
        assert payload["live_gate_execution_allowed"] is False
        assert payload["bridge_contract"]["source_bound"] is True
        assert payload["bridge_contract"]["ticket_links_are_explicit_not_keyword_inferred"] is True
        assert payload["contract_counts"] == {
            "total": 14,
            "linked": 0,
            "partially_linked": 10,
            "contract_followup_only": 4,
        }
        contracts = {row["contract_name"]: row for row in payload["contracts"]}
        assert contracts["numbering_registry"]["ticket_link_status"] == "contract_followup_only"
        assert contracts["site_structure_function_mvp"]["ticket_link_status"] == "partially_linked"
        assert "validated pocket/channel/interface calculator" in contracts["site_structure_function_mvp"]["uncovered_blockers"]
        tickets = {row["ticket_id"]: row for row in payload["tickets"]}
        assert tickets["RB-002-gpu_gromacs_md_live"]["linked_contracts"]
        assert tickets["RB-004-ligand_runtime_live"]["contract_impact_status"] == "operator_ticket_only"
        assert "source_status_export" in payload
        assert payload["source_status_export"]["sha256"]
        assert "Contract To Ticket" in output_md.read_text(encoding="utf-8")
        assert "contract_followup_only" in output_md.read_text(encoding="utf-8")

        validation = subprocess.run(
            [
                sys.executable,
                str(validator_script),
                "--bridge",
                str(output_json),
                "--status-export",
                str(status_export),
                "--execution-tickets",
                str(execution_tickets),
                "--go-no-go",
                str(go_no_go),
                "--output",
                str(validation_report),
                "--require-success",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        validation_stdout = json.loads(validation.stdout)
        assert validation_stdout["success"] is True
        assert validation_stdout["failure_count"] == 0
        assert validation_stdout["source_bound_current"] is True

        tampered = dict(payload)
        tampered["contracts"] = list(payload["contracts"])
        tampered["contracts"][0] = dict(tampered["contracts"][0])
        tampered["contracts"][0]["uncovered_blockers"] = []
        tampered_path = tmp_path / "tampered-bridge.json"
        tampered_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
        tampered_result = subprocess.run(
            [
                sys.executable,
                str(validator_script),
                "--bridge",
                str(tampered_path),
                "--status-export",
                str(status_export),
                "--execution-tickets",
                str(execution_tickets),
                "--go-no-go",
                str(go_no_go),
                "--output",
                str(tmp_path / "tampered-validation.json"),
                "--require-success",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert tampered_result.returncode == 1
        assert json.loads(tampered_result.stdout)["success"] is False
