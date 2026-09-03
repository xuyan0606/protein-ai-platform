#!/usr/bin/env python3
"""Read-only environment preflight for local or deployment packaging."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CheckResult:
    label: str
    status: str
    detail: str


def _command_version(command: list[str]) -> tuple[bool, str]:
    executable = shutil.which(command[0])
    if not executable:
        return False, "not found"
    try:
        proc = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        return True, f"installed but version check failed: {exc}"
    first_line = (proc.stdout or "").splitlines()[0] if proc.stdout else executable
    return True, first_line.strip()


def _check_command(label: str, command: list[str], *, required: bool = True) -> CheckResult:
    exists, detail = _command_version(command)
    if exists:
        return CheckResult(label, "ready", detail)
    return CheckResult(label, "missing" if required else "optional", detail)


def _check_path(label: str, path: Path, *, required: bool = True) -> CheckResult:
    if path.exists():
        return CheckResult(label, "ready", str(path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path))
    return CheckResult(label, "missing" if required else "optional", str(path))


def _check_backend_venv() -> CheckResult:
    python = PROJECT_ROOT / "backend" / ".venv" / "bin" / "python"
    if not python.exists():
        return CheckResult("backend.venv", "missing", str(python))
    exists, detail = _command_version([str(python), "--version"])
    return CheckResult("backend.venv", "ready" if exists else "missing", detail)


def _check_frontend_dependencies() -> CheckResult:
    node_modules = PROJECT_ROOT / "frontend" / "node_modules"
    package_lock = PROJECT_ROOT / "frontend" / "package-lock.json"
    if node_modules.exists():
        return CheckResult("frontend.dependencies", "ready", "frontend/node_modules")
    if package_lock.exists():
        return CheckResult("frontend.dependencies", "missing", "Run: cd frontend && npm ci")
    return CheckResult("frontend.dependencies", "missing", "Run: cd frontend && npm install")


def _check_compose_assets() -> list[CheckResult]:
    docker_dir = PROJECT_ROOT / "docker"
    return [
        _check_path("compose.local", docker_dir / "docker-compose.yml"),
        _check_path("compose.aliyun_app", docker_dir / "docker-compose.aliyun-app.yml", required=False),
        _check_path("compose.aliyun_gpu", docker_dir / "docker-compose.aliyun-gpu.yml", required=False),
        _check_path("env.docker", docker_dir / ".env", required=False),
        _check_path("env.docker_example", docker_dir / ".env.example"),
        _check_path("env.aliyun_app_example", docker_dir / ".env.aliyun.app.example", required=False),
        _check_path("env.aliyun_gpu_example", docker_dir / ".env.aliyun.gpu.example", required=False),
    ]


def collect_checks() -> list[CheckResult]:
    checks = [
        _check_command("python", [sys.executable, "--version"]),
        _check_command("node", ["node", "--version"]),
        _check_command("npm", ["npm", "--version"]),
        _check_command("docker", ["docker", "--version"], required=False),
        _check_command("make", ["make", "--version"], required=False),
        _check_backend_venv(),
        _check_frontend_dependencies(),
        _check_path("backend.env_example", PROJECT_ROOT / "backend" / ".env.example"),
        _check_path("deploy_data.root", PROJECT_ROOT / "deploy_data", required=False),
        _check_path("makefile", PROJECT_ROOT / "Makefile"),
        _check_path("deploy_script.aliyun", PROJECT_ROOT / "deploy-aliyun.sh", required=False),
    ]
    checks.extend(_check_compose_assets())
    return checks


def summarize(checks: list[CheckResult]) -> CheckResult:
    missing_required = [check for check in checks if check.status == "missing"]
    if missing_required:
        return CheckResult("summary", "blocked", f"{len(missing_required)} required checks missing")
    optional_missing = [check for check in checks if check.status == "optional"]
    if optional_missing:
        return CheckResult("summary", "ready-with-warnings", f"{len(optional_missing)} optional checks missing")
    return CheckResult("summary", "ready", "environment preflight passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero unless summary is ready")
    args = parser.parse_args()

    checks = collect_checks()
    summary = summarize(checks)
    payload = {
        "project_root": str(PROJECT_ROOT),
        "summary": asdict(summary),
        "checks": [asdict(check) for check in checks],
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for check in checks + [summary]:
            print(f"{check.label}\t{check.status}\t{check.detail}")
    if args.require_ready and summary.status != "ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
