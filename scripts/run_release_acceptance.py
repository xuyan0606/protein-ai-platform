#!/usr/bin/env python3
"""Run non-destructive release acceptance checks for Protein AI Platform.

Default mode is safe for local and pre-production use:
- upgrade readiness
- bounded acceptance matrix
- deploy package dry-run
- rollback plan generation
- restore drill dry-run when a backup exists

Real rollback, real database restore, live service checks, and long MD/browser
black-box checks remain explicit opt-in.
"""

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


class ReleaseResult:
    def __init__(self, name, category, status, detail, command=None, duration_seconds=0.0, data=None):
        self.name = name
        self.category = category
        self.status = status
        self.detail = detail
        self.command = command
        self.duration_seconds = duration_seconds
        self.data = data

    def as_dict(self):
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "detail": self.detail,
            "command": self.command,
            "duration_seconds": self.duration_seconds,
            "data": self.data,
        }


def _latest_backup():
    backup_dirs = [
        PROJECT_ROOT / "backups",
        PROJECT_ROOT.parent / "backups",
    ]
    backups = []
    for backup_dir in backup_dirs:
        if backup_dir.exists():
            backups.extend(backup_dir.glob("protein_ai_*.dump"))
    backups = sorted(backups)
    return backups[-1] if backups else None


def _latest_deploy_package():
    package_dirs = [
        PROJECT_ROOT / "dist" / "packages",
        PROJECT_ROOT.parent / "releases",
        PROJECT_ROOT.parent / "incoming",
    ]
    packages = []
    for package_dir in package_dirs:
        if package_dir.exists():
            packages.extend(package_dir.glob("protein-ai-platform-*.tar.gz"))
    packages = sorted(packages)
    return packages[-1] if packages else None


def _json_from_output(output):
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _last_line(output, fallback):
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else fallback


def _run_command(name, category, command, parser="text", cwd=PROJECT_ROOT):
    started = time.time()
    proc = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, check=False)
    duration = round(time.time() - started, 2)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    combined = stdout or stderr
    parsed = _json_from_output(stdout) if parser == "json" else None

    status = "passed" if proc.returncode == 0 else "failed"
    detail = _last_line(combined, f"exit={proc.returncode}")

    if name == "upgrade_readiness" and parsed:
        summary = parsed.get("summary") or {}
        summary_status = str(summary.get("status") or "unknown")
        status = "failed" if summary_status == "blocked" else "passed"
        detail = f"{summary_status}: {summary.get('detail', '')}".strip()
    elif name == "acceptance_matrix" and parsed:
        summary = parsed.get("summary") or {}
        failed = int(summary.get("failed") or 0)
        total = int(summary.get("total") or 0)
        status = "failed" if failed else "passed"
        detail = f"{summary.get('status', status)}: {failed} failed / {total} total"
    elif name == "rollback_plan" and parsed:
        summary_status = str(parsed.get("summary") or "unknown")
        status = "failed" if summary_status == "blocked" else "passed"
        blocked = parsed.get("blocked_reasons") or []
        detail = f"{summary_status}; blocked={','.join(blocked) if blocked else 'none'}"

    if proc.returncode != 0 and status != "failed":
        status = "failed"
    if proc.returncode != 0 and not detail.startswith("exit="):
        detail = f"exit={proc.returncode}; {detail}"

    return ReleaseResult(
        name=name,
        category=category,
        status=status,
        detail=detail[:1000],
        command=command,
        duration_seconds=duration,
        data=parsed,
    )


def _plan_result(name, category, command, detail=None):
    return ReleaseResult(
        name=name,
        category=category,
        status="planned",
        detail=detail or "planned only; command not executed",
        command=command,
    )


def _skipped_result(name, category, detail):
    return ReleaseResult(name=name, category=category, status="skipped", detail=detail)


def _blocked_result(name, category, detail, data=None):
    return ReleaseResult(name=name, category=category, status="blocked", detail=detail, data=data)


def _manual_required_result(name, category, detail, data=None):
    return ReleaseResult(name=name, category=category, status="manual_required", detail=detail, data=data)


def _env_value(name):
    value = (os.environ.get(name) or "").strip()
    return value or None


def _production_https_gate(plan_only=False):
    command = [
        sys.executable,
        "scripts/check_production_config.py",
        "--json",
        "--mode",
        "production",
        "--require-production-safe",
        "--env-file",
        "docker/.env",
        "--env-file",
        "docker/.env.aliyun.app",
    ]
    if plan_only:
        return _plan_result("production_https_gate", "security", command, "strict HTTPS production gate planned")
    started = time.time()
    proc = subprocess.run(command, cwd=str(PROJECT_ROOT), text=True, capture_output=True, check=False)
    parsed = _json_from_output(proc.stdout)
    checks = parsed.get("checks", []) if parsed else []
    https = next((item for item in checks if item.get("name") == "PUBLIC_BASE_URL_HTTPS"), None)
    if https and https.get("status") == "ok":
        return ReleaseResult("production_https_gate", "security", "passed", "formal HTTPS production gate passed", command, round(time.time() - started, 2), parsed)
    detail = (https or {}).get("detail") or "formal HTTPS domain/certificate is required before production release"
    return _manual_required_result(
        "production_https_gate",
        "security",
        detail,
        {"missing_inputs": ["formal HTTPS domain", "TLS certificate", "PUBLIC_BASE_URL/FRONTEND_URL/OIDC_ISSUER update"], "config": parsed},
    )


def _acceptance_command(args):
    command = [sys.executable, "scripts/run_acceptance_matrix.py", "--json"]
    if args.include_frontend:
        command.append("--include-frontend")
    if args.include_browser_smoke:
        command.append("--include-browser-smoke")
    if args.include_md_blackbox:
        command.append("--include-md-blackbox")
    if args.include_live:
        command.append("--include-live")
    if args.md_blackbox_arg:
        command.extend(args.md_blackbox_arg)
    return command


def _build_steps(args):
    rollback_command = [sys.executable, "scripts/rollback_plan.py", "--json"]
    if args.maintenance_window_id:
        rollback_command.extend(["--maintenance-window-id", args.maintenance_window_id])
    if args.allow_production_drill:
        rollback_command.append("--allow-production-drill")
    if args.offsite_backup_target:
        rollback_command.extend(["--offsite-backup-target", args.offsite_backup_target])
    if args.offsite_restore_target:
        rollback_command.extend(["--offsite-restore-target", args.offsite_restore_target])
    if args.external_storage_restore_target:
        rollback_command.extend(["--external-storage-restore-target", args.external_storage_restore_target])
    if args.external_storage_backup_ref:
        rollback_command.extend(["--external-storage-backup-ref", args.external_storage_backup_ref])
    return [
        (
            "upgrade_readiness",
            "upgrade",
            [sys.executable, "scripts/check_upgrade_readiness.py", "--json"],
            "json",
        ),
        ("acceptance_matrix", "testing", _acceptance_command(args), "json"),
        (
            "package_deploy_bundle_dry_run",
            "packaging",
            [sys.executable, "scripts/package_deploy_bundle.py", "--dry-run"],
            "text",
        ),
        ("rollback_plan", "rollback", rollback_command, "json"),
    ]


def _gate_result(
    *,
    name: str,
    category: str,
    required,
    safe_actions,
    ready_detail,
):
    missing = [label for label, value in required.items() if not value]
    data = {
        "required_inputs": required,
        "missing_inputs": missing,
        "current_safe_actions": safe_actions,
    }
    if missing:
        return _manual_required_result(name, category, f"manual inputs required: {', '.join(missing)}", data)
    return ReleaseResult(name=name, category=category, status="planned", detail=ready_detail, data=data)


def run_release_acceptance(args):
    results = []
    results.append(_production_https_gate(plan_only=args.plan_only))
    for name, category, command, parser in _build_steps(args):
        if args.plan_only:
            results.append(_plan_result(name, category, command))
        else:
            results.append(_run_command(name, category, command, parser=parser))

    backup = Path(args.backup_file).expanduser() if args.backup_file else _latest_backup()
    deploy_package = _latest_deploy_package()
    if backup:
        restore_command = ["./scripts/restore_drill.sh", "--dry-run", str(backup)]
        if args.plan_only:
            results.append(_plan_result("restore_drill_dry_run", "backup", restore_command))
        else:
            results.append(_run_command("restore_drill_dry_run", "backup", restore_command))

        verify_command = ["./scripts/verify_backup.sh"]
        if args.backup_verify_compose:
            verify_command.append("--compose")
        verify_command.append(str(backup))
        if args.include_backup_verify:
            if args.plan_only:
                results.append(_plan_result("backup_verify", "backup", verify_command))
            else:
                results.append(_run_command("backup_verify", "backup", verify_command))
        else:
            results.append(
                _skipped_result(
                    "backup_verify",
                    "backup",
                    "skipped by default; pass --include-backup-verify to run pg_restore/checksum verification",
                )
            )
    else:
        results.append(_skipped_result("restore_drill_dry_run", "backup", "no backup file found"))
        results.append(_skipped_result("backup_verify", "backup", "no backup file found"))

    results.append(
        _gate_result(
            name="production_rollback_drill_gate",
            category="maintenance",
            required={
                "MAINTENANCE_WINDOW_ID": args.maintenance_window_id,
                "ALLOW_PRODUCTION_DRILL=true": args.allow_production_drill,
                "deploy_package": str(deploy_package) if deploy_package else None,
                "backup_file": str(backup) if backup else None,
            },
            safe_actions=[
                "review rollback_plan output",
                "run backup verification",
                "run restore drill against a temporary database",
            ],
            ready_detail="ready for manual execution inside the approved maintenance window; no destructive action executed here",
        )
    )
    results.append(
        _gate_result(
            name="offsite_backup_restore_drill_gate",
            category="backup",
            required={
                "backup_file": str(backup) if backup else None,
                "OFFSITE_BACKUP_TARGET": args.offsite_backup_target,
                "OFFSITE_RESTORE_TARGET": args.offsite_restore_target,
            },
            safe_actions=[
                "verify local backup checksum and pg_restore list",
                "copy backup to offsite target with checksum metadata",
                "restore from offsite copy into an independent temporary/staging target",
            ],
            ready_detail="ready to execute against the configured offsite target; this acceptance run remains plan-only",
        )
    )
    results.append(
        _gate_result(
            name="external_storage_restore_validation_gate",
            category="storage",
            required={
                "EXTERNAL_STORAGE_BACKUP_REF": args.external_storage_backup_ref,
                "EXTERNAL_STORAGE_RESTORE_TARGET": args.external_storage_restore_target,
            },
            safe_actions=[
                "enumerate required object prefixes and sample artifact keys",
                "restore into a shadow bucket or prefix",
                "run application smoke checks against restored sample artifacts before any production path switch",
            ],
            ready_detail="ready for plan-only validation against a separate restore target; no storage path switch executed here",
        )
    )

    return results


def _summary(results, plan_only):
    failed = sum(1 for result in results if result.status == "failed")
    blocked = sum(1 for result in results if result.status == "blocked")
    manual_required = sum(1 for result in results if result.status == "manual_required")
    skipped = sum(1 for result in results if result.status == "skipped")
    if failed:
        status = "failed"
    elif plan_only and blocked:
        status = "planned-with-blockers"
    elif blocked:
        status = "blocked"
    elif plan_only:
        status = "planned"
    elif manual_required:
        status = "passed-with-manual-gates"
    elif skipped:
        status = "passed-with-skips"
    else:
        status = "passed"
    return {
        "status": status,
        "failed": failed,
        "blocked": blocked,
        "manual_required": manual_required,
        "skipped": skipped,
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
        f"{summary['manual_required']} manual_required / {summary['skipped']} skipped / {summary['total']} total"
    )
    print("manual_next\tUse rollback_plan steps only during an approved maintenance window.")
    print("manual_next\tProvide MAINTENANCE_WINDOW_ID and ALLOW_PRODUCTION_DRILL=true before a production rollback drill.")
    print("manual_next\tProvide OFFSITE_BACKUP_TARGET/OFFSITE_RESTORE_TARGET for offsite backup drill.")
    print("manual_next\tProvide EXTERNAL_STORAGE_BACKUP_REF/EXTERNAL_STORAGE_RESTORE_TARGET for external storage restore validation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--plan-only", action="store_true", help="Print planned checks without executing commands")
    parser.add_argument("--include-frontend", action="store_true", help="Include frontend production build in acceptance matrix")
    parser.add_argument("--include-browser-smoke", action="store_true", help="Include browser smoke checks against localhost")
    parser.add_argument("--include-md-blackbox", action="store_true", help="Include HTTP MD black-box verification")
    parser.add_argument("--include-live", action="store_true", help="Include live deploy_data/backend gates")
    parser.add_argument("--include-backup-verify", action="store_true", help="Run backup checksum and pg_restore list verification")
    parser.add_argument("--backup-verify-compose", action="store_true", help="Run backup verification inside docker compose postgres")
    parser.add_argument("--backup-file", help="Backup file used for restore drill and optional verification")
    parser.add_argument("--maintenance-window-id", default=_env_value("MAINTENANCE_WINDOW_ID"))
    parser.add_argument("--allow-production-drill", action="store_true", default=(os.environ.get("ALLOW_PRODUCTION_DRILL") or "").lower() in {"1", "true", "yes", "y"})
    parser.add_argument("--offsite-backup-target", default=_env_value("OFFSITE_BACKUP_TARGET"))
    parser.add_argument("--offsite-restore-target", default=_env_value("OFFSITE_RESTORE_TARGET"))
    parser.add_argument("--external-storage-backup-ref", default=_env_value("EXTERNAL_STORAGE_BACKUP_REF"))
    parser.add_argument("--external-storage-restore-target", default=_env_value("EXTERNAL_STORAGE_RESTORE_TARGET"))
    parser.add_argument("--md-blackbox-arg", action="append", default=[], help="Extra arg passed to run_acceptance_matrix")
    args = parser.parse_args()

    results = run_release_acceptance(args)
    summary = _summary(results, plan_only=args.plan_only)
    payload = {
        "project_root": str(PROJECT_ROOT),
        "summary": summary,
        "results": [result.as_dict() for result in results],
        "safety": {
            "destructive_actions": "not_executed",
            "real_restore": False,
            "real_rollback": False,
            "backup_verify_default": False,
            "maintenance_window_required_for_destructive_steps": True,
            "offsite_backup_drill_default": "manual gate",
            "external_storage_restore_default": "manual gate",
        },
        "manual_next": [
            "Review rollback_plan output before any production rollback.",
            "Provide MAINTENANCE_WINDOW_ID and ALLOW_PRODUCTION_DRILL=true before a production rollback drill.",
            "Provide OFFSITE_BACKUP_TARGET and OFFSITE_RESTORE_TARGET before an offsite backup restore drill.",
            "Provide EXTERNAL_STORAGE_BACKUP_REF and EXTERNAL_STORAGE_RESTORE_TARGET before external storage restore validation.",
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _render_text(results, summary)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
