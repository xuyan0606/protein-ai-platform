#!/usr/bin/env python3
"""Run or preview the repository's isolated backend pytest runner.

This mirrors the GitHub Actions ``backend-test`` job locally without
contacting external services or using production database settings.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import importlib.util


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
DEFAULT_PYTHON = BACKEND / ".venv" / "bin" / "python"


def _workflow_contract() -> dict[str, Any]:
    if not WORKFLOW.exists():
        return {"status": "blocked", "reason": "missing_ci_workflow", "path": str(WORKFLOW.relative_to(PROJECT_ROOT))}

    content = WORKFLOW.read_text(encoding="utf-8")
    markers = {
        "backend_test_job": "backend-test:",
        "isolated_sqlite": 'USE_SQLITE: "true"',
        "isolated_test_database": "TEST_DATABASE_URL:",
        "pytest_command": "python -m pytest tests/ -x -v --tb=short",
        "coverage_artifact": "backend-coverage",
    }
    missing = [name for name, marker in markers.items() if marker not in content]
    return {
        "status": "passed" if not missing else "blocked",
        "path": str(WORKFLOW.relative_to(PROJECT_ROOT)),
        "missing_markers": missing,
        "required_markers": list(markers),
    }


def _python_path(value: str | None) -> Path:
    configured = (value or os.getenv("BACKEND_PYTHON") or "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_PYTHON


def _pytest_command(python: Path) -> list[str]:
    command = [
        str(python),
        "-m",
        "pytest",
        "tests/",
        "-x",
        "-v",
        "--tb=short",
    ]
    if importlib.util.find_spec("pytest_cov") is not None:
        command.extend(["--cov=app", "--cov-report=term-missing", "--cov-report=xml"])
    return command


def _emit(payload: dict[str, Any], args: argparse.Namespace) -> int:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        payload["output"] = str(output_path)
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json:
        print(rendered)
    else:
        summary = payload["summary"]
        print(f"pytest_runner\t{summary['status']}\t{summary['detail']}")
        print(f"network_io\t{payload['network_io']}\tdestructive_actions={payload['destructive_actions']}")
        if payload.get("output"):
            print(f"output\t{payload['output']}")
    return 1 if payload["summary"]["status"] in {"failed", "blocked"} else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-only", action="store_true", help="Preview the isolated runner without starting pytest")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--python", dest="python_path", help="Explicit backend Python executable")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    python = _python_path(args.python_path)
    command = _pytest_command(python)
    workflow = _workflow_contract()
    coverage_enabled = any(arg.startswith("--cov=") for arg in command)

    if workflow["status"] != "passed":
        payload = {
            "summary": {
                "status": "blocked",
                "detail": "CI backend-test runner contract is incomplete; execution refused",
                "runner": "local_mirror_of_github_actions_backend_test",
                "workflow_contract": workflow["status"],
            },
            "mode": "plan_only" if args.plan_only else "execute",
            "workflow": workflow,
            "command": command,
            "working_directory": str(BACKEND),
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
        }
        return _emit(payload, args)

    if args.plan_only:
        payload = {
            "summary": {
                "status": "planned",
                "detail": "plan-only; pytest and dependency installation were not executed",
                "runner": "local_mirror_of_github_actions_backend_test",
                "workflow_contract": workflow["status"],
                "coverage": "enabled" if coverage_enabled else "unavailable",
            },
            "mode": "plan_only",
            "workflow": workflow,
            "command": command,
            "working_directory": str(BACKEND),
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
            "coverage": "enabled" if coverage_enabled else "unavailable",
        }
        return _emit(payload, args)

    if not python.exists() or not os.access(python, os.X_OK):
        payload = {
            "summary": {
                "status": "blocked",
                "detail": f"backend Python runner is unavailable: {python}",
                "runner": "local_mirror_of_github_actions_backend_test",
                "workflow_contract": workflow["status"],
                "coverage": "enabled" if coverage_enabled else "unavailable",
            },
            "mode": "execute",
            "workflow": workflow,
            "command": command,
            "working_directory": str(BACKEND),
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
            "coverage": "enabled" if coverage_enabled else "unavailable",
        }
        return _emit(payload, args)

    with tempfile.TemporaryDirectory(prefix="protein-ai-pytest-runner-") as temp_dir:
        child_env = os.environ.copy()
        child_env["USE_SQLITE"] = "true"
        child_env["TEST_DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(temp_dir) / 'runner.db'}"
        for key in ("DATABASE_URL", "ALIYUN_APP_DATABASE_URL", "RDS_DATABASE_URL", "POSTGRES_URL"):
            child_env.pop(key, None)

        process = subprocess.run(
            command,
            cwd=str(BACKEND),
            env=child_env,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_tail = (process.stdout or "").strip().splitlines()[-20:]
        stderr_tail = (process.stderr or "").strip().splitlines()[-20:]
        payload = {
            "summary": {
                "status": "passed" if process.returncode == 0 else "failed",
                "detail": f"pytest exit={process.returncode}",
                "runner": "local_mirror_of_github_actions_backend_test",
                "workflow_contract": workflow["status"],
                "coverage": "enabled" if coverage_enabled else "unavailable",
            },
            "mode": "execute",
            "workflow": workflow,
            "command": command,
            "working_directory": str(BACKEND),
            "exit_code": process.returncode,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
            "coverage": "enabled" if coverage_enabled else "unavailable",
        }
        return _emit(payload, args)


if __name__ == "__main__":
    raise SystemExit(main())
