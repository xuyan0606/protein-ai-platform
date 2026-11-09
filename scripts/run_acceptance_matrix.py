#!/usr/bin/env python3
"""Run the platform acceptance matrix with safe defaults.

Default mode is intentionally local and bounded:
- environment preflight
- file/artifact download permission regression tests
- deploy data readiness tests
- MD artifact/parser unit tests
- OSS/S3 configuration compatibility preflight

Long-running or externally dependent checks are opt-in.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


def _project_root():
    pwd = os.environ.get("PWD")
    if pwd:
        candidate = Path(pwd)
        if (candidate / "scripts" / Path(__file__).name).exists():
            return candidate
    return Path(__file__).absolute().parent.parent


PROJECT_ROOT = _project_root()
BACKEND = PROJECT_ROOT / "backend"
DEFAULT_BACKEND_PYTHON = BACKEND / ".venv" / "bin" / "python"


class MatrixResult:
    def __init__(self, name, category, status, detail, command=None, duration_seconds=0.0):
        self.name = name
        self.category = category
        self.status = status
        self.detail = detail
        self.command = command
        self.duration_seconds = duration_seconds

    def as_dict(self):
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "detail": self.detail,
            "command": self.command,
            "duration_seconds": self.duration_seconds,
        }


def _run_command(name, category, command, cwd=PROJECT_ROOT):
    started = time.time()
    proc = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, check=False)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    rendered = _summarize_command_output(stdout, stderr, fallback=f"exit={proc.returncode}")
    if proc.returncode != 0:
        rendered = f"exit={proc.returncode}; {rendered}"
    return MatrixResult(
        name=name,
        category=category,
        status="passed" if proc.returncode == 0 else "failed",
        detail=rendered[:800],
        command=command,
        duration_seconds=round(time.time() - started, 2),
    )


def _summarize_command_output(stdout, stderr, fallback):
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("summary"), dict):
            summary = payload["summary"]
            parts = [str(summary.get("status") or "unknown")]
            for key in ("failed", "blocked", "skipped", "planned", "total"):
                if key in summary:
                    parts.append(f"{key}={summary[key]}")
            return "; ".join(parts)

    detail = (stdout or stderr or "").splitlines()
    return detail[-1] if detail else fallback


def _plan_result(name, category, command, detail=None):
    return MatrixResult(
        name=name,
        category=category,
        status="planned",
        detail=detail or "planned only; command not executed",
        command=command,
    )


def _skipped_result(name, category, detail, command=None):
    return MatrixResult(name=name, category=category, status="skipped", detail=detail, command=command)


def _blocked_result(name, category, detail, command=None):
    return MatrixResult(name=name, category=category, status="blocked", detail=detail, command=command)


def _first_env(*names, **kwargs):
    default = kwargs.get("default", "")
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _backend_python():
    configured = os.getenv("BACKEND_PYTHON", "").strip()
    if configured:
        return configured
    if DEFAULT_BACKEND_PYTHON.exists() and os.access(DEFAULT_BACKEND_PYTHON, os.X_OK):
        return str(DEFAULT_BACKEND_PYTHON)
    return sys.executable


def _oss_compatibility_check():
    endpoint = _first_env("MINIO_ENDPOINT", "ALIYUN_OSS_ENDPOINT", default="localhost:9000")
    secure = _first_env("MINIO_SECURE", "ALIYUN_OSS_SECURE", default="false").lower() in {"1", "true", "yes", "on"}
    region = _first_env("MINIO_REGION", "ALIYUN_OSS_REGION")
    bucket = _first_env("MINIO_BUCKET", "ALIYUN_OSS_BUCKET", default="protein-files")
    local_path = os.getenv("STORAGE_LOCAL_PATH", "./storage").strip()

    issues = []
    if not endpoint:
        issues.append("MINIO_ENDPOINT/ALIYUN_OSS_ENDPOINT is empty")
    parsed = urlparse(endpoint if "://" in endpoint else f"//{endpoint}", scheme="http")
    if not parsed.netloc and not parsed.path:
        issues.append("MINIO_ENDPOINT/ALIYUN_OSS_ENDPOINT is not parseable")
    if secure and endpoint.startswith("localhost"):
        issues.append("MINIO_SECURE=true with localhost endpoint is usually invalid")
    if not bucket:
        issues.append("MINIO_BUCKET/ALIYUN_OSS_BUCKET is empty")
    if region and any(char.isspace() for char in region):
        issues.append("MINIO_REGION contains whitespace")
    if not local_path:
        issues.append("STORAGE_LOCAL_PATH is empty")

    return MatrixResult(
        name="oss_compatibility",
        category="storage",
        status="failed" if issues else "passed",
        detail="; ".join(issues) if issues else "MinIO/S3 env shape is compatible with local and OSS-style endpoints.",
    )


def _oss_minio_e2e_contract_check(require_live):
    command = [_backend_python(), "scripts/smoke_oss_minio_contract.py", "--json"]
    if require_live:
        command.append("--require-live")

    endpoint = _first_env("MINIO_ENDPOINT", "ALIYUN_OSS_ENDPOINT", default="localhost:9000")
    access_key = _first_env("MINIO_ACCESS_KEY", "ALIYUN_OSS_ACCESS_KEY_ID")
    secret_key = _first_env("MINIO_SECRET_KEY", "ALIYUN_OSS_ACCESS_KEY_SECRET")
    bucket = _first_env("MINIO_BUCKET", "ALIYUN_OSS_BUCKET", default="protein-files")
    missing = [
        name
        for name, value in {
            "MINIO_ENDPOINT/ALIYUN_OSS_ENDPOINT": endpoint,
            "MINIO_BUCKET/ALIYUN_OSS_BUCKET": bucket,
            "MINIO_ACCESS_KEY/ALIYUN_OSS_ACCESS_KEY_ID": access_key,
            "MINIO_SECRET_KEY/ALIYUN_OSS_ACCESS_KEY_SECRET": secret_key,
        }.items()
        if not value
    ]
    if missing and require_live:
        return _blocked_result(
            "oss_minio_e2e_contract",
            "storage",
            f"missing live object storage config: {', '.join(missing)}; network object round-trip not executed",
            command,
        )
    if missing:
        return MatrixResult(
            name="oss_minio_e2e_contract",
            category="storage",
            status="planned",
            detail=f"plan-only until live object storage config is provided: {', '.join(missing)}",
            command=command,
        )
    if require_live:
        return _run_command("oss_minio_e2e_contract", "storage", command, cwd=PROJECT_ROOT)
    return MatrixResult(
        name="oss_minio_e2e_contract",
        category="storage",
        status="passed",
        detail="OSS/MinIO E2E contract is configured; network object round-trip intentionally not executed without --require-live.",
        command=command,
    )


def _build_steps(args):
    python = _backend_python()
    steps = [
        ("environment_preflight", "environment", [sys.executable, "scripts/check_environment.py"], PROJECT_ROOT),
        (
            "production_config_gate",
            "security",
            [
                sys.executable,
                "scripts/check_production_config.py",
                "--json",
                "--mode",
                "production",
                "--require-production-safe",
                "--skip-domain-https",
                "--env-file",
                "docker/.env",
                "--env-file",
                "docker/.env.aliyun.app",
            ],
            PROJECT_ROOT,
        ),
        (
            "file_download_permissions",
            "security",
            [
                python,
                "-m",
                "pytest",
                "tests/test_tools_api.py::test_tool_task_polling_records_md_artifact_owner_for_download",
                "tests/test_tools_api.py::test_tool_task_artifact_bundle_download_rejects_other_user",
                "tests/test_tools_api.py::test_file_download_rejects_md_artifact_without_owner_binding",
                "tests/test_tools_api.py::test_file_download_rejects_md_artifact_bound_to_other_user",
                "-q",
            ],
            BACKEND,
        ),
        (
            "md_artifact_whitebox",
            "md",
            [python, "-m", "pytest", "tests/test_gromacs_md_artifacts.py", "-q"],
            BACKEND,
        ),
        (
            "ligand_preprocess_contract",
            "ligand",
            [
                python,
                "-m",
                "pytest",
                "tests/test_tools_api.py::test_ligand_preprocess_preflight_blocks_missing_runtime_without_fake_3d",
                "tests/test_tools_api.py::test_ligand_preprocess_stage_contract_reports_missing_parameters",
                "tests/test_tools_api.py::test_ligand_preprocess_api_call_rejects_async_execution",
                "tests/test_tools_api.py::test_ligand_preprocess_submit_rejects_unowned_object_and_local_path",
                "tests/test_tools_api.py::test_ligand_preprocess_submit_creates_ligand_cpu_audit",
                "tests/test_tools_api.py::test_ligand_task_polling_records_artifact_owner_for_download",
                "-q",
            ],
            BACKEND,
        ),
        (
            "ligand_toolchain_smoke",
            "ligand",
            [python, "scripts/smoke_ligand_toolchain.py", "--json"],
            BACKEND,
        ),
        (
            "enzyme_report_quality_contract",
            "report_quality",
            [
                python,
                "-m",
                "pytest",
                "tests/test_report_quality_contract.py",
                "tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_contract_cases",
                "tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_report_quality_review_uses_checkpoint_step_results_and_report_preview",
                "tests/test_agent_binder.py::TestEnzymeReportQualityEvalSet::test_checkpoint_execution_summary_contains_step_results_and_report_headings",
                "tests/test_agent_binder.py::TestBinderSkillsAndReport::test_plan_confirmation_audits_pdb_plus_fasta_as_consistency_gate",
                "tests/test_agent_binder.py::TestBinderSkillsAndReport::test_plan_confirmation_audits_fasta_plus_uniprot_before_numbering_claims",
                "-q",
            ],
            BACKEND,
        ),
        (
            "tool_capability_audit_gate",
            "report_quality",
            [
                python,
                "-m",
                "pytest",
                "tests/test_data_api.py::TestBenchmarkEndpoints::test_tool_capabilities_endpoint_exposes_scientific_boundaries",
                "tests/test_tools_api.py::test_tool_capability_audit_labels_proxy_and_runtime_gated_tools",
                "-q",
            ],
            BACKEND,
        ),
        (
            "user_isolation_contract",
            "security",
            [
                python,
                "-m",
                "pytest",
                "tests/test_project_acl.py::test_non_member_cannot_discover_project",
                "tests/test_project_acl.py::test_chat_project_binding_requires_write_access",
                "tests/test_publish_api.py::test_shared_project_viewer_can_list_files_but_cannot_write",
                "tests/test_publish_api.py::test_non_member_cannot_list_project_files",
                "tests/test_tools_api.py::test_tool_task_polling_rejects_other_user_task",
                "tests/test_tools_api.py::test_tool_task_audit_rejects_other_user",
                "tests/test_data_api.py::TestBenchmarkEndpoints::test_experiment_feedback_records_go_decision_and_user_isolation",
                "-q",
            ],
            BACKEND,
        ),
        (
            "wiki_checkpoint_contract",
            "wiki",
            [
                python,
                "-m",
                "pytest",
                "tests/test_publish_api.py::test_collection_publish_preserves_active_strategy_checkpoint",
                "tests/test_llm_gateway.py::test_chat_stream_persists_and_restores_strategy_checkpoint",
                "tests/test_llm_gateway.py::test_chat_stream_confirmed_payload_marks_checkpoint_executing",
                "tests/test_llm_gateway.py::test_chat_stream_execute_confirmed_prefers_active_checkpoint_over_stale_client_payload",
                "tests/test_llm_gateway.py::test_chat_stream_execute_confirmed_prefers_active_checkpoint_over_malformed_client_payload",
                "tests/test_llm_gateway.py::test_chat_strategy_checkpoint_active_response_masks_uploaded_object_paths",
                "tests/test_llm_gateway.py::test_chat_strategy_checkpoint_history_returns_revisions",
                "-q",
            ],
            BACKEND,
        ),
        (
            "hm_pdb_deep_quality_gate",
            "report_quality",
            [
                python,
                "-m",
                "pytest",
                "tests/test_hm_pdb_deep_quality_gate.py",
                "-q",
            ],
            BACKEND,
        ),
        (
            "data_admin_readiness",
            "data",
            [
                python,
                "-m",
                "pytest",
                "tests/test_data_api.py::TestBenchmarkEndpoints::test_data_readiness_endpoint_reports_components",
                "tests/test_data_api.py::TestBenchmarkEndpoints::test_admin_data_updates_filter_and_import_dry_run",
                "-q",
            ],
            BACKEND,
        ),
        ("browser_smoke_contract", "frontend", ["node", "frontend/tests/live-contract.mjs", "--json"], PROJECT_ROOT),
    ]
    if args.include_frontend:
        steps.append(("frontend_build", "frontend", ["npm", "run", "build"], PROJECT_ROOT / "frontend"))
    if args.include_browser_smoke:
        steps.append(("browser_public_smoke", "frontend", ["node", "frontend/tests/public-smoke.mjs"], PROJECT_ROOT))
        steps.append(("browser_live_smoke", "frontend", ["node", "frontend/tests/live-smoke.mjs"], PROJECT_ROOT))
    if args.include_ai_blackbox:
        steps.append(
            (
                "ai_chat_blackbox_live",
                "ai",
                [sys.executable, "scripts/smoke_ai_blackbox_live.py", "--json", "--require-live"],
                PROJECT_ROOT,
            )
        )
    if args.include_file_download_e2e:
        steps.append(
            (
                "live_file_download_e2e",
                "storage",
                [sys.executable, "scripts/smoke_file_download_live.py", "--json", "--require-live"],
                PROJECT_ROOT,
            )
        )
    if args.include_benchmark_bundle_live:
        steps.append(
            (
                "benchmark_bundle_head_live",
                "data",
                [sys.executable, "scripts/smoke_benchmark_bundle_live.py", "--json"],
                PROJECT_ROOT,
            )
        )
    if args.include_md_blackbox:
        md_blackbox_args = list(args.md_blackbox_args)
        if md_blackbox_args[:1] == ["--"]:
            md_blackbox_args = md_blackbox_args[1:]
        steps.append(("md_blackbox", "md", [python, "scripts/verify_md_blackbox.py", *md_blackbox_args], BACKEND))
    if args.include_live:
        steps.append(("deploy_live_gate", "data", ["make", "deploy-live-gate"], PROJECT_ROOT))
        steps.append(("backend_smoke_live", "data", ["make", "backend-smoke-live"], PROJECT_ROOT))
    return steps


def _append_optional_gate_markers(args, results):
    def add_unarmed(name, category, detail, command):
        if args.plan_only:
            results.append(_plan_result(name, category, command, detail))
        elif args.fail_closed_external:
            results.append(_blocked_result(name, category, detail, command))
        else:
            results.append(_skipped_result(name, category, detail, command))

    if not args.include_browser_smoke:
        command = ["node", "frontend/tests/live-smoke.mjs"]
        add_unarmed(
            "browser_live_smoke",
            "frontend",
            "browser gate not armed; pass --include-browser-smoke with FRONTEND_BASE_URL",
            command,
        )
    if not args.include_md_blackbox:
        command = [_backend_python(), "scripts/verify_md_blackbox.py"]
        add_unarmed(
            "md_blackbox",
            "md",
            "MD black-box gate not armed; pass --include-md-blackbox with resume inputs or explicit submit permission",
            command,
        )
    if not args.include_ai_blackbox:
        command = [sys.executable, "scripts/smoke_ai_blackbox_live.py", "--json", "--require-live"]
        results.append(
            _skipped_result(
                "ai_chat_blackbox_live",
                "ai",
                "skipped by default; pass --include-ai-blackbox with LIVE_AI_EMAIL/LIVE_AI_PASSWORD for bounded live chat stream checks",
                command,
            )
        )
    if not args.include_file_download_e2e:
        command = [sys.executable, "scripts/smoke_file_download_live.py", "--json", "--require-live"]
        results.append(
            _skipped_result(
                "live_file_download_e2e",
                "storage",
                "skipped by default; pass --include-file-download-e2e with LIVE_AI_EMAIL/LIVE_AI_PASSWORD to upload/download/delete a small file through /api/files",
                command,
            )
        )
    if not args.include_benchmark_bundle_live:
        command = [sys.executable, "scripts/smoke_benchmark_bundle_live.py", "--json"]
        results.append(
            _skipped_result(
                "benchmark_bundle_head_live",
                "data",
                "skipped by default; pass --include-benchmark-bundle-live with FRONTEND_BASE_URL/BACKEND_BASE_URL to validate HEAD and Range without full download",
                command,
            )
        )
    if not args.include_live:
        results.append(
            _skipped_result(
                "deploy_live_gate",
                "data",
                "skipped by default; pass --include-live only on a host with real deploy_data/Foldseek/SIFTS readiness",
                ["make", "deploy-live-gate"],
            )
        )
    if not args.include_oss_e2e:
        results.append(
            _skipped_result(
                "oss_minio_e2e_contract",
                "storage",
                "skipped by default; pass --include-oss-e2e to run the guarded OSS/MinIO object write/read/delete gate",
                [_backend_python(), "scripts/smoke_oss_minio_contract.py", "--json"],
            )
        )


def _summary(results, plan_only):
    failed = sum(1 for result in results if result.status == "failed")
    blocked = sum(1 for result in results if result.status == "blocked")
    skipped = sum(1 for result in results if result.status == "skipped")
    planned = sum(1 for result in results if result.status == "planned")
    if failed:
        status = "failed"
    elif blocked:
        status = "blocked"
    elif plan_only:
        status = "planned"
    elif skipped:
        status = "passed-with-skips"
    elif planned:
        status = "passed-with-plan"
    else:
        status = "passed"
    return {
        "status": status,
        "failed": failed,
        "blocked": blocked,
        "skipped": skipped,
        "planned": planned,
        "total": len(results),
    }


def _render_text(results, summary):
    for result in results:
        command = " ".join(result.command or [])
        suffix = f"\t{command}" if command else ""
        print(f"{result.name}\t{result.status}\t{result.detail}{suffix}")
    print(
        "summary\t"
        f"{summary['status']}\t"
        f"{summary['failed']} failed / {summary['blocked']} blocked / "
        f"{summary['skipped']} skipped / {summary['planned']} planned / {summary['total']} total"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--plan-only", action="store_true", help="Print planned checks without executing commands")
    parser.add_argument("--include-frontend", action="store_true", help="Run frontend production build")
    parser.add_argument("--include-browser-smoke", action="store_true", help="Run Playwright/browser smoke scripts against localhost")
    parser.add_argument("--include-ai-blackbox", action="store_true", help="Run bounded live chat AI black-box scenarios")
    parser.add_argument("--include-file-download-e2e", action="store_true", help="Run live upload/download/delete through /api/files")
    parser.add_argument("--include-benchmark-bundle-live", action="store_true", help="Run live benchmark bundle HEAD and Range smoke")
    parser.add_argument("--include-md-blackbox", action="store_true", help="Run external HTTP MD black-box verification")
    parser.add_argument("--include-live", action="store_true", help="Run live deploy_data/Foldseek/SIFTS gates")
    parser.add_argument("--include-oss-e2e", action="store_true", help="Run guarded OSS/MinIO object write/read/delete E2E gate")
    parser.add_argument(
        "--fail-closed-external",
        action="store_true",
        help="Mark unarmed browser/MD gates blocked instead of skipped when not in plan-only mode",
    )
    parser.add_argument("md_blackbox_args", nargs=argparse.REMAINDER, help="Args passed after --include-md-blackbox")
    args = parser.parse_args()

    steps = _build_steps(args)
    results = []
    for name, category, command, cwd in steps:
        if args.plan_only:
            results.append(_plan_result(name, category, command, detail=str(cwd)))
        else:
            results.append(_run_command(name, category, command, cwd=cwd))
    if args.plan_only:
        results.append(
            _plan_result(
                "oss_compatibility",
                "storage",
                None,
                "planned local MinIO/S3 environment shape preflight",
            )
        )
        if args.include_oss_e2e:
            results.append(
                _plan_result(
                    "oss_minio_e2e_contract",
                    "storage",
                    [_backend_python(), "scripts/smoke_oss_minio_contract.py", "--json"],
                    "planned OSS/MinIO E2E contract; --include-oss-e2e runs guarded object write/read/delete",
                )
            )
        _append_optional_gate_markers(args, results)
    else:
        results.append(_oss_compatibility_check())
        if args.include_oss_e2e:
            results.append(_oss_minio_e2e_contract_check(require_live=True))
        _append_optional_gate_markers(args, results)

    summary = _summary(results, plan_only=args.plan_only)

    payload = {
        "summary": summary,
        "results": [result.as_dict() for result in results],
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _render_text(results, summary)
    return 1 if summary["failed"] or summary["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
