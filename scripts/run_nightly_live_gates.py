#!/usr/bin/env python3
"""Run nightly live gates with opt-in controls for mutating checks."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _project_root():
    pwd = os.environ.get("PWD")
    if pwd:
        candidate = Path(pwd)
        if (candidate / "scripts" / Path(__file__).name).exists():
            return candidate
    return Path(__file__).absolute().parent.parent


PROJECT_ROOT = _project_root()


class GateResult:
    def __init__(self, name, status, detail, command=None, duration_seconds=0.0):
        self.name = name
        self.status = status
        self.detail = detail
        self.command = command
        self.duration_seconds = duration_seconds

    def as_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "command": self.command,
            "duration_seconds": self.duration_seconds,
        }


def _run(name, command, cwd=PROJECT_ROOT):
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=False,
    )
    duration = round(time.time() - started, 2)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    detail = _summarize(stdout or stderr, "exit=%s" % proc.returncode)
    if proc.returncode != 0:
        detail = "exit=%s; %s" % (proc.returncode, detail)
    if proc.returncode == 0:
        status = "passed"
    elif _is_environment_blocker(stdout or stderr):
        status = "blocked"
    else:
        status = "failed"
    return GateResult(name, status, detail[:800], command, duration)


def _is_environment_blocker(output):
    rendered = str(output or "").lower()
    markers = (
        "cannot reach",
        "could not reach",
        "econnrefused",
        "connect eperm",
        "target page, context or browser has been closed",
        "browsertype.launch",
        "no http response",
        "node.js v",
    )
    return any(marker in rendered for marker in markers)


def _summarize(output, fallback):
    try:
        payload = json.loads(output)
    except Exception:
        payload = None
    if isinstance(payload, dict):
        summary = payload.get("summary")
        if isinstance(summary, dict):
            parts = [str(summary.get("status") or "unknown")]
            for key in ("failed", "blocked", "skipped", "planned", "total"):
                if key in summary:
                    parts.append("%s=%s" % (key, summary[key]))
            return "; ".join(parts)
        if payload.get("status"):
            return str(payload.get("status"))
    lines = [line.strip() for line in str(output).splitlines() if line.strip()]
    return lines[-1] if lines else fallback


def _skipped(name, detail, command=None):
    return GateResult(name, "skipped", detail, command)


def _has_live_login():
    return bool((os.environ.get("LIVE_AI_EMAIL") or "").strip() and (os.environ.get("LIVE_AI_PASSWORD") or "").strip())


def _has_md_blackbox_inputs(args):
    task_id = (args.md_blackbox_task_id or os.environ.get("MD_BLACKBOX_TASK_ID") or "").strip()
    email = (args.md_blackbox_email or os.environ.get("MD_BLACKBOX_EMAIL") or os.environ.get("LIVE_AI_EMAIL") or "").strip()
    password = (os.environ.get("MD_BLACKBOX_PASSWORD") or os.environ.get("LIVE_AI_PASSWORD") or "").strip()
    allow_submit = args.md_blackbox_allow_submit or (os.environ.get("ALLOW_MD_BLACKBOX_SUBMIT") or "").strip().lower() in {"1", "true", "yes", "on"}
    return bool((task_id and email and password) or (allow_submit and password))


def build_gates(args):
    base_url = args.frontend_base_url or os.environ.get("FRONTEND_BASE_URL") or "http://120.27.108.138"
    env = os.environ.copy()
    env["FRONTEND_BASE_URL"] = base_url
    os.environ.update({"FRONTEND_BASE_URL": base_url})

    gates = [
        (
            "production_config",
            [
                sys.executable,
                "scripts/check_production_config.py",
                "--json",
                "--mode",
                "production",
                "--require-production-safe",
                "--skip-domain-https",
                "--env-file",
                "docker/.env.aliyun.app",
            ],
        ),
        ("http_smoke", ["node", "frontend/tests/http-smoke.mjs"]),
        ("public_browser_smoke", ["node", "frontend/tests/public-smoke.mjs"]),
        ("live_browser_smoke", ["node", "frontend/tests/live-smoke.mjs"]),
        ("benchmark_bundle_head_live", [sys.executable, "scripts/smoke_benchmark_bundle_live.py", "--json"]),
        (
            "acceptance_matrix_live_readonly",
            [
                sys.executable,
                "scripts/run_acceptance_matrix.py",
                "--json",
                "--include-browser-smoke",
                "--include-benchmark-bundle-live",
            ],
        ),
    ]

    if args.include_admin_oidc_tools:
        gates.append(("admin_oidc_tools_live", [sys.executable, "scripts/smoke_admin_oidc_tools_live.py", "--json", "--require-live"]))
    if args.include_ai_blackbox:
        gates.append(("ai_chat_blackbox_live", [sys.executable, "scripts/smoke_ai_blackbox_live.py", "--json", "--require-live"]))
    if args.include_file_download_e2e:
        gates.append(("file_download_e2e_live", [sys.executable, "scripts/smoke_file_download_live.py", "--json", "--require-live"]))
    if args.include_oss_e2e:
        gates.append((
            "oss_minio_e2e_contract",
            [
                sys.executable,
                "scripts/smoke_oss_minio_contract.py",
                "--json",
                "--require-live",
                "--env-file",
                "docker/.env.aliyun.app",
            ],
        ))
    if args.include_md_blackbox:
        command = [sys.executable, "backend/scripts/verify_md_blackbox.py", "--base-url", base_url]
        if args.md_blackbox_task_id:
            command.extend(["--task-id", args.md_blackbox_task_id])
        if args.md_blackbox_email:
            command.extend(["--email", args.md_blackbox_email])
        if args.md_blackbox_allow_submit:
            command.append("--allow-submit")
        gates.append(("md_blackbox_live_e2e", command))
    return gates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--frontend-base-url")
    parser.add_argument("--include-admin-oidc-tools", action="store_true")
    parser.add_argument("--include-ai-blackbox", action="store_true")
    parser.add_argument("--include-file-download-e2e", action="store_true")
    parser.add_argument("--include-oss-e2e", action="store_true")
    parser.add_argument("--include-md-blackbox", action="store_true")
    parser.add_argument("--md-blackbox-task-id")
    parser.add_argument("--md-blackbox-email")
    parser.add_argument("--md-blackbox-allow-submit", action="store_true")
    parser.add_argument(
        "--fail-closed-external",
        action="store_true",
        help="Mark missing live account/MD inputs blocked instead of skipped when not in plan-only mode",
    )
    args = parser.parse_args()

    results = []
    for name, command in build_gates(args):
        if args.plan_only:
            results.append(GateResult(name, "planned", "planned only; command not executed", command))
        elif name in {"ai_chat_blackbox_live", "file_download_e2e_live"} and not _has_live_login():
            if args.fail_closed_external:
                results.append(GateResult(name, "blocked", "LIVE_AI_EMAIL/LIVE_AI_PASSWORD missing; fail-closed gate not executed", command))
            else:
                results.append(_skipped(name, "LIVE_AI_EMAIL/LIVE_AI_PASSWORD missing; mutating account gate not executed", command))
        elif name == "md_blackbox_live_e2e" and not _has_md_blackbox_inputs(args):
            if args.fail_closed_external:
                results.append(GateResult(name, "blocked", "MD black-box resume/submission inputs missing; fail-closed gate not executed", command))
            else:
                results.append(_skipped(name, "MD black-box resume/submission inputs missing; long-task gate not executed", command))
        else:
            results.append(_run(name, command))

    if not args.include_admin_oidc_tools:
        results.append(_skipped("admin_oidc_tools_live", "opt-in only; pass --include-admin-oidc-tools"))
    if not args.include_ai_blackbox:
        results.append(_skipped("ai_chat_blackbox_live", "opt-in only; pass --include-ai-blackbox with live account env"))
    if not args.include_file_download_e2e:
        results.append(_skipped("file_download_e2e_live", "opt-in only; pass --include-file-download-e2e with live account env"))
    if not args.include_oss_e2e:
        results.append(_skipped("oss_minio_e2e_contract", "opt-in only; pass --include-oss-e2e with object storage env"))
    if not args.include_md_blackbox:
        if args.fail_closed_external:
            results.append(GateResult(
                "md_blackbox_live_e2e",
                "blocked",
                "MD black-box gate not armed; pass --include-md-blackbox with resume inputs or explicit submit permission",
            ))
        else:
            results.append(_skipped("md_blackbox_live_e2e", "opt-in only; pass --include-md-blackbox with resume inputs or --md-blackbox-allow-submit"))

    failed = sum(1 for result in results if result.status == "failed")
    blocked = sum(1 for result in results if result.status == "blocked")
    skipped = sum(1 for result in results if result.status == "skipped")
    planned = sum(1 for result in results if result.status == "planned")
    if failed:
        status = "failed"
    elif blocked:
        status = "blocked"
    elif planned:
        status = "planned"
    elif skipped:
        status = "passed-with-skips"
    else:
        status = "passed"
    summary = {"status": status, "failed": failed, "blocked": blocked, "skipped": skipped, "planned": planned, "total": len(results)}
    payload = {
        "summary": summary,
        "results": [result.as_dict() for result in results],
        "secrets_printed": False,
        "destructive_actions": "not_executed",
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for result in results:
            print("%s\t%s\t%s" % (result.name, result.status, result.detail))
        print("summary\t%s\t%s failed / %s skipped / %s planned / %s total" % (
            summary["status"], failed, skipped, planned, summary["total"]
        ))
    return 1 if failed or blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
