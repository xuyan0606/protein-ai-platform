#!/usr/bin/env python3
"""Aggregate read-only readiness for backlog items that still need live inputs.

This script does not download data, contact storage, build containers, run MD,
or mutate deployment state. It reuses existing local smoke/contract scripts and
adds operator-facing checks for credentials, maintenance windows, and evidence
that cannot be produced on a developer laptop.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEPLOY_ROOT = PROJECT_ROOT / "deploy_data"
SCREENSHOT_MANIFEST = PROJECT_ROOT / "docs" / "manuals" / "screenshots" / "manifest.json"
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
ADMIN_SCREENSHOT_ID = "SHOT-ADMIN-001"


class BacklogItem:
    def __init__(
        self,
        name,
        status,
        bucket,
        detail,
        missing_requirements=None,
        next_actions=None,
        source=None,
    ):
        self.name = name
        self.status = status
        self.bucket = bucket
        self.detail = detail
        self.missing_requirements = missing_requirements or []
        self.next_actions = next_actions or []
        self.source = source

    def as_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "bucket": self.bucket,
            "detail": self.detail,
            "missing_requirements": self.missing_requirements,
            "next_actions": self.next_actions,
            "source": self.source,
        }


def _backend_python() -> str:
    configured = os.getenv("BACKEND_PYTHON", "").strip()
    if configured:
        return configured
    candidate = PROJECT_ROOT / "backend" / ".venv" / "bin" / "python"
    return str(candidate if candidate.exists() else sys.executable)


def _run_json(
    command: List[str],
    *,
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[Any], Optional[str]]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
    except OSError as exc:
        return None, str(exc)
    if result.returncode != 0 and not result.stdout.strip():
        return None, (result.stderr or result.stdout).strip() or f"exit_code={result.returncode}"
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError as exc:
        preview = (result.stdout or result.stderr).strip().replace("\n", " ")[:240]
        return None, f"invalid json: {exc}; output={preview}"


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_env_file(path: Path) -> Dict[str, str]:
    values = {}  # type: Dict[str, str]
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_values(env_file: Optional[Path]) -> Dict[str, str]:
    if env_file is not None:
        return _load_env_file(env_file)
    return {key: value for key, value in os.environ.items() if value is not None}


def _first_value(values: Dict[str, str], *names: str) -> str:
    for name in names:
        value = str(values.get(name) or "").strip()
        if value:
            return value
    return ""


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _ci_workflow_has_backend_pytest() -> bool:
    if not CI_WORKFLOW.is_file():
        return False
    content = CI_WORKFLOW.read_text(encoding="utf-8", errors="replace")
    return (
        "backend-test:" in content
        and "python -m pytest tests/" in content
        and "Upload coverage report" in content
    )


def _python_too_old_error(error):
    rendered = str(error or "")
    return "future feature annotations is not defined" in rendered or "invalid syntax" in rendered and "from __future__ import annotations" in rendered


def _check_deploy_data(deploy_root: Path) -> BacklogItem:
    payload, error = _run_json(
        [sys.executable, "scripts/check_deploy_data.py", "--root", str(deploy_root), "--json"],
        cwd=PROJECT_ROOT,
    )
    if _python_too_old_error(error):
        return BacklogItem(
            "real_deploy_data",
            "external_required",
            "local_capable",
            "deploy_data readiness needs Python 3.7+ or a container runner on this host",
            missing_requirements=["Python 3.7+ runner for scripts/check_deploy_data.py"],
            next_actions=["Run the readiness script from a modern Python environment or backend container."],
            source=error,
        )
    if error or not isinstance(payload, list):
        return BacklogItem(
            "real_deploy_data",
            "blocked",
            "local_capable",
            "deploy_data readiness script could not be evaluated",
            missing_requirements=["check_deploy_data.py JSON output"],
            next_actions=["Run python3 scripts/check_deploy_data.py --json and fix the reported error."],
            source=error,
        )
    summary = next((item for item in payload if isinstance(item, dict) and item.get("label") == "summary"), {})
    raw_status = str(summary.get("status") or "unknown")
    missing = [str(item) for item in summary.get("missing_items") or []]
    next_actions = [str(item) for item in summary.get("next_actions") or []]
    if raw_status == "live-data-ready":
        status = "ready"
        detail = "deploy_data has live annotations/SIFTS/PDB/AlphaFold/Foldseek/smoke query coverage"
        next_actions = []
    elif raw_status in {"demo-data-only", "partial", "empty"}:
        status = "external_required"
        detail = str(summary.get("detail") or "real deploy_data inputs are not yet complete")
    else:
        status = "blocked"
        detail = str(summary.get("detail") or f"unexpected deploy_data summary status={raw_status}")
    return BacklogItem(
        "real_deploy_data",
        status,
        "local_capable",
        detail,
        missing_requirements=missing,
        next_actions=[]
        if status == "ready"
        else next_actions
        or [
            "Stage real annotations, SIFTS, PDB/AlphaFold structures, Foldseek DBs, and deploy_data/live_manifest.json."
        ],
        source="scripts/check_deploy_data.py",
    )


def _check_domain_https(values: Dict[str, str]) -> BacklogItem:
    public_url = _first_value(values, "PUBLIC_BASE_URL", "FRONTEND_URL", "OIDC_ISSUER").rstrip("/")
    if not public_url:
        return BacklogItem(
            "formal_domain_https",
            "external_required",
            "external_dependency",
            "formal domain cutover has not started because PUBLIC_BASE_URL is missing",
            missing_requirements=["PUBLIC_BASE_URL", "DNS A/CNAME record", "TLS certificate"],
            next_actions=[
                "Choose the production domain and point DNS to the app ECS public IP or load balancer.",
                "Set PUBLIC_BASE_URL/FRONTEND_URL/OIDC_ISSUER to the HTTPS domain and rerun production-config-gate without --skip-domain-https.",
            ],
            source="docker/.env.aliyun.app",
        )

    parsed = urlparse(public_url)
    host = parsed.hostname or ""
    is_ip = all(part.isdigit() for part in host.split(".") if part) and host.count(".") == 3
    is_local = host in {"localhost", "127.0.0.1"}
    if parsed.scheme == "https" and host and not is_ip and not is_local:
        return BacklogItem(
            "formal_domain_https",
            "planned",
            "external_dependency",
            "PUBLIC_BASE_URL already points at an HTTPS domain; run full production config and browser gates after certificate deployment",
            next_actions=[
                "Run python3 scripts/check_production_config.py --mode production --require-production-safe --env-file docker/.env.aliyun.app.",
                "Run FRONTEND_BASE_URL=<https-domain> python3 scripts/run_nightly_live_gates.py --json.",
            ],
            source="docker/.env.aliyun.app",
        )

    return BacklogItem(
        "formal_domain_https",
        "external_required",
        "external_dependency",
        f"current public URL is {public_url}; formal HTTPS domain cutover still needs DNS and certificate inputs",
        missing_requirements=["formal HTTPS domain", "TLS certificate", "PUBLIC_BASE_URL/FRONTEND_URL/OIDC_ISSUER update"],
        next_actions=[
            "Bind a formal domain and certificate, then remove --skip-domain-https from production config gate.",
            "After cutover, rerun http/public/live/admin gates against the HTTPS domain.",
        ],
        source="docker/.env.aliyun.app",
    )


def _check_md_topology() -> BacklogItem:
    payload, error = _run_json(
        [_backend_python(), "scripts/smoke_md_topology.py", "--json"],
        cwd=PROJECT_ROOT / "backend",
    )
    if _python_too_old_error(error):
        return BacklogItem(
            "gpu_gromacs_md_live",
            "external_required",
            "external_dependency",
            "MD topology smoke needs Python 3.7+ or a backend container runner on this host",
            missing_requirements=["Python 3.7+ runner", "NVIDIA/GROMACS runtime"],
            next_actions=["Run backend/scripts/smoke_md_topology.py from the backend container or GPU/GROMACS node."],
            source=error,
        )
    if error or not isinstance(payload, dict):
        return BacklogItem(
            "gpu_gromacs_md_live",
            "blocked",
            "external_dependency",
            "MD topology smoke could not run",
            missing_requirements=["backend/scripts/smoke_md_topology.py JSON output"],
            next_actions=["Run make backend-md-topology-smoke and inspect the error."],
            source=error,
        )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary.get("topology_validated"):
        return BacklogItem(
            "gpu_gromacs_md_live",
            "ready",
            "external_dependency",
            "GROMACS pdb2gmx topology precheck validates on this host",
            source="backend/scripts/smoke_md_topology.py",
        )
    error_code = str(summary.get("error_code") or summary.get("status") or "unknown")
    return BacklogItem(
        "gpu_gromacs_md_live",
        "external_required",
        "external_dependency",
        f"GROMACS topology live gate is not available on this host: {error_code}",
        missing_requirements=["NVIDIA/GROMACS runtime", "real WT/mutant PDB inputs", "long-running MD worker capacity"],
        next_actions=[
            "Provision the Aliyun GPU/GROMACS node, then run make backend-md-topology-live-gate.",
            "After topology validation, submit real WT/mutant replicate batches and summarize ranking reports.",
        ],
        source="backend/scripts/smoke_md_topology.py",
    )


def _check_ligand_toolchain() -> BacklogItem:
    payload, error = _run_json(
        [_backend_python(), "scripts/smoke_ligand_toolchain.py", "--json"],
        cwd=PROJECT_ROOT / "backend",
    )
    if _python_too_old_error(error):
        return BacklogItem(
            "ligand_runtime_live",
            "external_required",
            "external_dependency",
            "ligand toolchain smoke needs Python 3.7+ or a backend/ligand container runner on this host",
            missing_requirements=["Python 3.7+ runner", "ligand worker runtime"],
            next_actions=["Run backend/scripts/smoke_ligand_toolchain.py from the ligand worker container or modern Python environment."],
            source=error,
        )
    if error or not isinstance(payload, dict):
        return BacklogItem(
            "ligand_runtime_live",
            "blocked",
            "external_dependency",
            "ligand toolchain smoke could not run",
            missing_requirements=["backend/scripts/smoke_ligand_toolchain.py JSON output"],
            next_actions=["Run make backend-ligand-toolchain-smoke and inspect the error."],
            source=error,
        )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary.get("status") == "ready":
        return BacklogItem(
            "ligand_runtime_live",
            "ready",
            "external_dependency",
            "2D SDF, conformer/PDBQT/Vina/topology/GROMACS prerequisites are ready",
            source="backend/scripts/smoke_ligand_toolchain.py",
        )

    # The host may intentionally omit chemistry binaries while the dedicated
    # worker image carries the complete runtime. Reuse that image's read-only
    # self-check before reporting a false external blocker.
    runtime_image = os.getenv("LIGAND_RUNTIME_IMAGE", "protein-ai-ligand-worker:aliyun").strip()
    runtime_payload = None
    runtime_error = None
    if runtime_image and summary.get("input_sdf_exists") and summary.get("is_2d_sdf"):
        runtime_payload, runtime_error = _run_json(
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "--entrypoint",
                "/usr/local/bin/ligand-runtime-check",
                runtime_image,
            ],
            cwd=PROJECT_ROOT,
        )
        if isinstance(runtime_payload, dict) and runtime_payload.get("status") == "ready":
            return BacklogItem(
                "ligand_runtime_live",
                "ready",
                "external_dependency",
                "dedicated ligand worker image provides the complete chemistry/GROMACS runtime",
                next_actions=[],
                source=f"{runtime_image}:/usr/local/bin/ligand-runtime-check",
            )

    missing = [str(item) for item in summary.get("missing_requirements") or []]
    next_actions = [
        "Install or build the ligand worker runtime with OpenBabel or RDKit, AutoDock Vina, ACPYPE/AmberTools, and GROMACS.",
        "Then run make backend-ligand-toolchain-live-gate.",
    ]
    if runtime_image:
        next_actions.append(
            f"Or build {runtime_image} and rerun the read-only readiness check."
        )
    if error:
        missing.append("backend/scripts/smoke_ligand_toolchain.py JSON output")
    return BacklogItem(
        "ligand_runtime_live",
        "external_required",
        "external_dependency",
        "ligand preprocessing/docking/topology runtime is not complete on this host",
        missing_requirements=missing,
        next_actions=next_actions,
        source=runtime_image if runtime_payload is not None else (runtime_error or "backend/scripts/smoke_ligand_toolchain.py"),
    )


def _check_oss_minio_contract(values: Dict[str, str], runtime_env: Optional[Dict[str, str]] = None) -> BacklogItem:
    effective_env = os.environ if runtime_env is None else runtime_env
    smoke_env = None if runtime_env is None else {k: v for k, v in runtime_env.items() if v is not None}
    payload, error = _run_json(
        [sys.executable, "scripts/smoke_oss_minio_contract.py", "--json"],
        cwd=PROJECT_ROOT,
        env=smoke_env,
    )
    if _python_too_old_error(error):
        return BacklogItem(
            "oss_minio_live_e2e",
            "external_required",
            "external_dependency",
            "OSS/MinIO contract smoke needs Python 3.7+ or a container runner on this host",
            missing_requirements=["Python 3.7+ runner", "live object storage credentials"],
            next_actions=["Run scripts/smoke_oss_minio_contract.py from a modern Python environment or backend container."],
            source=error,
        )
    if error or not isinstance(payload, dict):
        return BacklogItem(
            "oss_minio_live_e2e",
            "blocked",
            "external_dependency",
            "OSS/MinIO contract script could not run",
            missing_requirements=["scripts/smoke_oss_minio_contract.py JSON output"],
            next_actions=["Run python3 scripts/smoke_oss_minio_contract.py --json and inspect the error."],
            source=error,
        )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    credentials_ready = bool(
        _first_value(effective_env, "MINIO_ACCESS_KEY", "ALIYUN_OSS_ACCESS_KEY_ID")
        and _first_value(effective_env, "MINIO_SECRET_KEY", "ALIYUN_OSS_ACCESS_KEY_SECRET")
    )
    if summary.get("status") == "passed" and credentials_ready:
        return BacklogItem(
            "oss_minio_live_e2e",
            "ready",
            "local_capable",
            "OSS/MinIO config is complete; full opt-in object write/read/delete gate is available via --require-live",
            next_actions=[
                "Rerun python3 scripts/run_acceptance_matrix.py --include-oss-e2e when a fresh live storage proof is needed."
            ],
            source="scripts/smoke_oss_minio_contract.py",
        )
    status = "external_required"
    detail = "OSS/MinIO E2E gate is available, but endpoint credentials or live bucket permission are not present in this shell"
    missing = ["MINIO_ACCESS_KEY/MINIO_SECRET_KEY or ALIYUN_OSS_ACCESS_KEY_ID/ALIYUN_OSS_ACCESS_KEY_SECRET", "live bucket permission"]
    return BacklogItem(
        "oss_minio_live_e2e",
        status,
        "external_dependency",
        detail,
        missing_requirements=missing,
        next_actions=[
            "Set live OSS/MinIO endpoint and credentials in the deployment environment.",
            "Run python3 scripts/smoke_oss_minio_contract.py --json --require-live or acceptance matrix --include-oss-e2e.",
        ],
        source="scripts/smoke_oss_minio_contract.py",
    )


def _check_md_blackbox_live(values: Dict[str, str]) -> BacklogItem:
    task_id = _first_value(values, "MD_BLACKBOX_TASK_ID")
    email = _first_value(values, "MD_BLACKBOX_EMAIL", "LIVE_AI_EMAIL")
    password = _first_value(values, "MD_BLACKBOX_PASSWORD", "LIVE_AI_PASSWORD")
    allow_submit = _first_value(values, "ALLOW_MD_BLACKBOX_SUBMIT").lower() in {"1", "true", "yes", "on"}
    base_url = _first_value(values, "FRONTEND_BASE_URL", "PUBLIC_BASE_URL") or "http://120.27.108.138"
    command = "backend/scripts/verify_md_blackbox.py --base-url %s" % base_url

    if task_id and email and password:
        return BacklogItem(
            "md_blackbox_live_e2e",
            "planned",
            "external_dependency",
            "existing MD task resume inputs are present; live poll/download verifier can run without submitting a new task",
            next_actions=[
                "Run BACKEND_PYTHON=backend/.venv/bin/python python backend/scripts/verify_md_blackbox.py --base-url %s --task-id $MD_BLACKBOX_TASK_ID --email $MD_BLACKBOX_EMAIL --password $MD_BLACKBOX_PASSWORD." % base_url
            ],
            source=command,
        )

    if allow_submit and password and (PROJECT_ROOT / "deploy_data" / "smoke" / "query.pdb").exists():
        return BacklogItem(
            "md_blackbox_live_e2e",
            "planned",
            "external_dependency",
            "MD black-box submission gate is armed; it will create/upload/submit/poll a real MD task when executed",
            next_actions=[
                "Run python backend/scripts/verify_md_blackbox.py --base-url %s with live credentials during a long-task validation window." % base_url
            ],
            source=command,
        )

    missing = []
    if not task_id:
        missing.append("MD_BLACKBOX_TASK_ID for resume or ALLOW_MD_BLACKBOX_SUBMIT=true for new submission")
    if not email and task_id:
        missing.append("MD_BLACKBOX_EMAIL/LIVE_AI_EMAIL")
    if not password:
        missing.append("MD_BLACKBOX_PASSWORD/LIVE_AI_PASSWORD")
    if allow_submit and not (PROJECT_ROOT / "deploy_data" / "smoke" / "query.pdb").exists():
        missing.append("deploy_data/smoke/query.pdb")
    return BacklogItem(
        "md_blackbox_live_e2e",
        "external_required",
        "external_dependency",
        "MD black-box long-task gate is available but not armed; no live MD task was submitted",
        missing_requirements=missing,
        next_actions=[
            "Prefer resume mode first: set MD_BLACKBOX_TASK_ID plus live account credentials for an existing completed/running task.",
            "For a fresh long-task proof, set ALLOW_MD_BLACKBOX_SUBMIT=true and run during a validation window.",
        ],
        source=command,
    )


def _check_remote_test_runner(values: Dict[str, str]) -> BacklogItem:
    runner_image = _first_value(values, "REMOTE_TEST_RUNNER_IMAGE", "TEST_RUNNER_IMAGE")
    ci_url = _first_value(values, "CI_TEST_RUNNER_URL", "CI_PIPELINE_URL")
    if runner_image or ci_url:
        return BacklogItem(
            "remote_pytest_runner",
            "ready",
            "local_capable",
            "dedicated remote/CI pytest runner is configured outside the production runtime image",
            next_actions=["Run the configured test runner against the deployed source tree before the next code sync."],
            source=runner_image or ci_url,
        )

    if _ci_workflow_has_backend_pytest():
        runner_script = PROJECT_ROOT / "scripts" / "run_pytest_runner.py"
        if runner_script.exists():
            plan, plan_error = _run_json([sys.executable, str(runner_script), "--plan-only", "--json"], cwd=PROJECT_ROOT)
            if isinstance(plan, dict) and (plan.get("summary") or {}).get("status") == "planned":
                return BacklogItem(
                    "remote_pytest_runner",
                    "ready",
                    "local_capable",
                    "GitHub Actions backend-test and local fail-closed mirror runner are present outside the production runtime image",
                    next_actions=[],
                    source=f"{CI_WORKFLOW}; {runner_script}",
                )
            return BacklogItem(
                "remote_pytest_runner",
                "external_required",
                "local_capable",
                "GitHub Actions backend-test exists, but the local mirror runner contract is not ready",
                missing_requirements=["passing make pytest-runner-plan"],
                next_actions=["Run make pytest-runner-plan and fix the reported contract blocker."],
                source=plan_error or str(runner_script),
            )
        return BacklogItem(
            "remote_pytest_runner",
            "planned",
            "local_capable",
            "repository already defines a dedicated GitHub Actions backend pytest runner outside the production runtime image",
            next_actions=["Use the existing backend-test workflow as the remote test runner, or mirror it in a dedicated CI job before the next code sync."],
            source=str(CI_WORKFLOW),
        )

    local_pytest, error = _run_json([_backend_python(), "-c", "import pytest, json; print(json.dumps({'pytest': pytest.__version__}))"], cwd=PROJECT_ROOT / "backend")
    if isinstance(local_pytest, dict) and local_pytest.get("pytest"):
        return BacklogItem(
            "remote_pytest_runner",
            "external_required",
            "local_capable",
            "local backend pytest is available, but production backend image intentionally lacks pytest; remote full tests still need a separate runner",
            missing_requirements=["REMOTE_TEST_RUNNER_IMAGE or CI_TEST_RUNNER_URL"],
            next_actions=[
                "Create a non-production test-runner image or CI job with backend test dependencies.",
                "Do not install pytest into the production backend image just to run live regression tests.",
            ],
            source="backend/.venv",
        )

    return BacklogItem(
        "remote_pytest_runner",
        "external_required",
        "local_capable",
        "neither local pytest nor a remote test-runner configuration is available",
        missing_requirements=["backend pytest environment", "REMOTE_TEST_RUNNER_IMAGE or CI_TEST_RUNNER_URL"],
        next_actions=["Repair backend/.venv or provide a dedicated remote test-runner image."],
        source=error,
    )


def _check_admin_screenshot() -> BacklogItem:
    manifest = _load_json(SCREENSHOT_MANIFEST)
    screenshots = manifest.get("screenshots") if isinstance(manifest.get("screenshots"), list) else []
    admin_items = [item for item in screenshots if isinstance(item, dict) and item.get("id") == ADMIN_SCREENSHOT_ID]
    has_credentials = bool(os.getenv("SCREENSHOT_EMAIL") and os.getenv("SCREENSHOT_PASSWORD"))
    final_url = str(admin_items[0].get("final_url") or "") if admin_items else ""
    if admin_items and has_credentials and "/admin" in final_url and "/login" not in final_url:
        return BacklogItem(
            "admin_authenticated_screenshots",
            "ready",
            "external_dependency",
            "admin screenshot manifest contains authenticated admin page evidence",
            source=str(SCREENSHOT_MANIFEST),
        )
    missing = []
    if not admin_items:
        missing.append("SHOT-ADMIN-001 manifest entry")
    if not has_credentials:
        missing.extend(["SCREENSHOT_EMAIL", "SCREENSHOT_PASSWORD"])
    if final_url and "/login" in final_url:
        missing.append("authenticated /admin final_url")
    return BacklogItem(
        "admin_authenticated_screenshots",
        "external_required",
        "external_dependency",
        "admin screenshots still require an authenticated admin session",
        missing_requirements=missing,
        next_actions=[
            "Provide admin screenshot credentials through SCREENSHOT_EMAIL/SCREENSHOT_PASSWORD.",
            "Rerun make manual-screenshots FRONTEND_BASE_URL=http://127.0.0.1:4203 and verify /admin final_url.",
        ],
        source=str(SCREENSHOT_MANIFEST),
    )


def _check_maintenance_drills() -> BacklogItem:
    window_id = os.getenv("MAINTENANCE_WINDOW_ID", "").strip()
    allow_drill = os.getenv("ALLOW_PRODUCTION_DRILL", "").strip().lower() in {"1", "true", "yes", "on"}
    remote_backup_target = os.getenv("REMOTE_BACKUP_TARGET", "").strip() or os.getenv("OFFSITE_BACKUP_TARGET", "").strip()
    external_restore_target = os.getenv("EXTERNAL_STORAGE_RESTORE_TARGET", "").strip()
    missing = []  # type: List[str]
    if not window_id:
        missing.append("MAINTENANCE_WINDOW_ID")
    if not allow_drill:
        missing.append("ALLOW_PRODUCTION_DRILL=true")
    if not remote_backup_target:
        missing.append("REMOTE_BACKUP_TARGET or OFFSITE_BACKUP_TARGET")
    if not external_restore_target:
        missing.append("EXTERNAL_STORAGE_RESTORE_TARGET")
    if not missing:
        return BacklogItem(
            "maintenance_window_drills",
            "planned",
            "external_dependency",
            "maintenance window markers are present; real rollback/offsite/restore drills still require explicit operator execution",
            next_actions=["Run release acceptance with live restore/rollback flags during the approved maintenance window."],
        )
    return BacklogItem(
        "maintenance_window_drills",
        "external_required",
        "external_dependency",
        "real rollback, offsite backup, and external storage restore drills need an approved maintenance window",
        missing_requirements=missing,
        next_actions=[
            "Schedule a maintenance window and set MAINTENANCE_WINDOW_ID plus ALLOW_PRODUCTION_DRILL=true.",
            "Provide offsite backup and external storage restore targets before running live drills.",
        ],
    )


def collect(
    deploy_root: Path,
    values: Dict[str, str],
    runtime_env: Optional[Dict[str, str]] = None,
) -> List[BacklogItem]:
    return [
        _check_domain_https(values),
        _check_deploy_data(deploy_root),
        _check_md_topology(),
        _check_md_blackbox_live(values),
        _check_ligand_toolchain(),
        _check_oss_minio_contract(values, runtime_env=runtime_env),
        _check_admin_screenshot(),
        _check_maintenance_drills(),
        _check_remote_test_runner(values),
    ]


def _summary(items: List[BacklogItem]) -> Dict[str, Any]:
    counts = {}  # type: Dict[str, int]
    bucket_counts = {}  # type: Dict[str, int]
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
        bucket_counts[item.bucket] = bucket_counts.get(item.bucket, 0) + 1
    if counts.get("blocked"):
        status = "blocked"
    elif counts.get("external_required"):
        status = "external_required"
    elif counts.get("planned"):
        status = "planned"
    else:
        status = "ready"
    return {
        "status": status,
        "counts": counts,
        "total": len(items),
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "bucket_counts": bucket_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deploy-root", default=str(DEFAULT_DEPLOY_ROOT), help="deploy_data root to inspect")
    parser.add_argument("--env-file", default=str(PROJECT_ROOT / "docker" / ".env.aliyun.app"), help="Deployment env file used for domain/URL readiness")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero unless every backlog item is ready")
    parser.add_argument("--require-ligand-ready", action="store_true", help="Exit non-zero unless ligand_runtime_live is ready")
    args = parser.parse_args()

    deploy_root = Path(args.deploy_root).expanduser().resolve()
    env_file = Path(args.env_file).expanduser().resolve() if args.env_file else None
    values = _load_values(env_file)
    items = collect(deploy_root, values, runtime_env=None)
    summary = _summary(items)
    payload = {"summary": summary, "results": [item.as_dict() for item in items]}

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        bucket_titles = {
            "local_capable": "本机可做",
            "external_dependency": "外部依赖",
        }
        grouped = {key: [] for key in bucket_titles}  # type: Dict[str, List[BacklogItem]]
        for item in items:
            grouped.setdefault(item.bucket, []).append(item)
        for bucket in ("local_capable", "external_dependency"):
            print(bucket_titles[bucket])
            bucket_items = grouped.get(bucket, [])
            if not bucket_items:
                print("  - 无")
                continue
            for item in bucket_items:
                suffixes = []  # type: List[str]
                if item.missing_requirements:
                    suffixes.append(f"missing={','.join(item.missing_requirements[:8])}")
                if item.next_actions:
                    suffixes.append(f"next={item.next_actions[0]}")
                suffix = f"\t{'; '.join(suffixes)}" if suffixes else ""
                print(f"  - {item.name}\t{item.status}\t{item.detail}{suffix}")
            print()
        counts = ", ".join(f"{key}={value}" for key, value in sorted(summary["counts"].items()))
        bucket_counts = ", ".join(f"{key}={value}" for key, value in sorted(summary["bucket_counts"].items()))
        print(
            "summary\t"
            f"{summary['status']}\t"
            f"{counts or 'ready=0'}; {bucket_counts or 'local_capable=0'}; network_io=not_executed; destructive_actions=not_executed"
        )

    ligand_ready = next(
        (item.get("status") == "ready" for item in payload["results"] if item.get("name") == "ligand_runtime_live"),
        False,
    )
    if (args.require_ready and summary["status"] != "ready") or (args.require_ligand_ready and not ligand_ready):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
