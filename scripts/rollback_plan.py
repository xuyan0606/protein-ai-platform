#!/usr/bin/env python3
"""Generate a safe rollback plan without changing services or databases."""

import argparse
import json
import os
from pathlib import Path

def _project_root():
    pwd = os.environ.get("PWD")
    if pwd:
        candidate = Path(pwd)
        if (candidate / "scripts" / Path(__file__).name).exists():
            return candidate
    return Path(__file__).absolute().parent.parent


PROJECT_ROOT = _project_root()


class RollbackAsset:
    def __init__(self, label, path, exists, detail):
        self.label = label
        self.path = path
        self.exists = exists
        self.detail = detail

    def as_dict(self):
        return {
            "label": self.label,
            "path": self.path,
            "exists": self.exists,
            "detail": self.detail,
        }


class DrillReadiness:
    def __init__(self, name, status, missing_inputs, current_safe_actions, executable_when):
        self.name = name
        self.status = status
        self.missing_inputs = missing_inputs
        self.current_safe_actions = current_safe_actions
        self.executable_when = executable_when

    def as_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "missing_inputs": self.missing_inputs,
            "current_safe_actions": self.current_safe_actions,
            "executable_when": self.executable_when,
        }


def _latest_package():
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
    if not packages:
        return RollbackAsset("deploy_package", None, False, "no package under dist/packages")
    latest = packages[-1]
    checksum = latest.with_suffix(latest.suffix + ".sha256")
    return RollbackAsset(
        "deploy_package",
        str(latest),
        True,
        f"checksum={'yes' if checksum.exists() else 'no'}",
    )


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
    if not backups:
        return RollbackAsset("database_backup", None, False, "no .dump backup under backups")
    latest = backups[-1]
    checksum = latest.with_suffix(latest.suffix + ".sha256")
    return RollbackAsset(
        "database_backup",
        str(latest),
        True,
        f"checksum={'yes' if checksum.exists() else 'no'}",
    )


def _version():
    path = PROJECT_ROOT / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "unknown"


def _env_flag(name):
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "y"}


def _first_value(value, env_name):
    candidate = value if value is not None else os.environ.get(env_name)
    candidate = (candidate or "").strip()
    return candidate or None


def _build_drill_readiness(
    *,
    package_asset: RollbackAsset,
    backup_asset: RollbackAsset,
    maintenance_window_id,
    allow_production_drill,
    offsite_backup_target,
    offsite_restore_target,
    external_storage_restore_target,
    external_storage_backup_ref,
):
    maintenance_missing = []
    if not maintenance_window_id:
        maintenance_missing.append("MAINTENANCE_WINDOW_ID")
    if not allow_production_drill:
        maintenance_missing.append("ALLOW_PRODUCTION_DRILL=true")
    if not package_asset.exists:
        maintenance_missing.append("deploy_package")
    if not backup_asset.exists:
        maintenance_missing.append("database_backup")

    maintenance_gate = {
        "maintenance_window_id": maintenance_window_id,
        "allow_production_drill": allow_production_drill,
        "destructive_steps_executable": not maintenance_missing,
        "missing_inputs": maintenance_missing,
    }

    rollback_missing = list(maintenance_missing)
    offsite_missing = []
    if not backup_asset.exists:
        offsite_missing.append("database_backup")
    if not offsite_backup_target:
        offsite_missing.append("OFFSITE_BACKUP_TARGET")
    if not offsite_restore_target:
        offsite_missing.append("OFFSITE_RESTORE_TARGET")

    storage_missing = []
    if not external_storage_backup_ref:
        storage_missing.append("EXTERNAL_STORAGE_BACKUP_REF")
    if not external_storage_restore_target:
        storage_missing.append("EXTERNAL_STORAGE_RESTORE_TARGET")

    readiness = [
        DrillReadiness(
            name="production_rollback_drill",
            status="manual_required" if rollback_missing else "ready-for-maintenance-window",
            missing_inputs=rollback_missing,
            current_safe_actions=[
                "generate rollback plan",
                "verify backup checksum/list",
                "run restore drill against a temporary database",
            ],
            executable_when=[
                "maintenance window is approved",
                "ALLOW_PRODUCTION_DRILL=true is set for the operator session",
                "rollback package and database backup have both been verified",
            ],
        ),
        DrillReadiness(
            name="offsite_backup_restore_drill",
            status="manual_required" if offsite_missing else "plan-only-ready",
            missing_inputs=offsite_missing,
            current_safe_actions=[
                "verify local backup before upload",
                "document offsite target, object key, checksum, RTO and RPO",
                "restore into an independent temporary/staging target only",
            ],
            executable_when=[
                "offsite target is configured",
                "backup has been copied out of the primary host",
                "restore target is independent from production",
            ],
        ),
        DrillReadiness(
            name="external_storage_restore_validation",
            status="manual_required" if storage_missing else "plan-only-ready",
            missing_inputs=storage_missing,
            current_safe_actions=[
                "list required object prefixes and sample artifact keys",
                "validate credentials with read-only/list-only permissions first",
                "restore into a shadow bucket/prefix before any production path switch",
            ],
            executable_when=[
                "storage backup reference/snapshot is known",
                "restore target bucket or prefix is separate from production",
                "application smoke checks can read restored sample artifacts",
            ],
        ),
    ]
    return maintenance_gate, readiness


def build_plan(
    mode,
    package,
    backup,
    maintenance_window_id=None,
    allow_production_drill=False,
    offsite_backup_target=None,
    offsite_restore_target=None,
    external_storage_restore_target=None,
    external_storage_backup_ref=None,
):
    package_asset = RollbackAsset("deploy_package", package, bool(package and Path(package).exists()), "user-selected") if package else _latest_package()
    backup_asset = RollbackAsset("database_backup", backup, bool(backup and Path(backup).exists()), "user-selected") if backup else _latest_backup()
    blocked = [asset.label for asset in (package_asset, backup_asset) if not asset.exists]
    backup_ref = backup_asset.path or "backups/protein_ai_YYYYMMDDTHHMMSSZ.dump"
    package_ref = package_asset.path or "dist/packages/protein-ai-platform-YYYYMMDDTHHMMSSZ.tar.gz"
    maintenance_gate, drill_readiness = _build_drill_readiness(
        package_asset=package_asset,
        backup_asset=backup_asset,
        maintenance_window_id=maintenance_window_id,
        allow_production_drill=allow_production_drill,
        offsite_backup_target=offsite_backup_target,
        offsite_restore_target=offsite_restore_target,
        external_storage_restore_target=external_storage_restore_target,
        external_storage_backup_ref=external_storage_backup_ref,
    )

    steps = [
        {
            "name": "freeze_traffic",
            "command": "put upstream/load-balancer into maintenance mode",
            "destructive": False,
        },
        {
            "name": "verify_backup",
            "command": f"make verify-backup BACKUP_FILE={backup_ref}",
            "destructive": False,
        },
        {
            "name": "restore_drill",
            "command": f"make restore-drill BACKUP_FILE={backup_ref}",
            "destructive": False,
        },
        {
            "name": "stop_current_services",
            "command": "cd docker && docker compose --env-file .env --env-file .env.deploy-data down",
            "destructive": True,
        },
        {
            "name": "restore_database",
            "command": f"./scripts/restore.sh --yes {backup_ref}",
            "destructive": True,
        },
        {
            "name": "redeploy_previous_package",
            "command": f"extract {package_ref} to release directory and restart compose/deploy role={mode}",
            "destructive": True,
        },
        {
            "name": "post_rollback_checks",
            "command": "python3 scripts/check_environment.py && python3 scripts/check_upgrade_readiness.py",
            "destructive": False,
        },
    ]
    return {
        "project_root": str(PROJECT_ROOT),
        "current_version": _version(),
        "mode": mode,
        "summary": "blocked" if blocked else "ready-for-manual-review",
        "blocked_reasons": blocked,
        "assets": [package_asset.as_dict(), backup_asset.as_dict()],
        "maintenance_gate": maintenance_gate,
        "drill_readiness": [item.as_dict() for item in drill_readiness],
        "steps": steps,
        "safety_notes": [
            "This script is read-only and does not execute rollback.",
            "Real restore is destructive; run verify-backup and restore-drill first.",
            "Do not run restore.sh against production without an approved maintenance window.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["local", "aliyun-app", "aliyun-gpu"], default="local")
    parser.add_argument("--package", help="Rollback deploy package tar.gz")
    parser.add_argument("--backup", help="Rollback database .dump")
    parser.add_argument("--maintenance-window-id", default=_first_value(None, "MAINTENANCE_WINDOW_ID"))
    parser.add_argument("--allow-production-drill", action="store_true", default=_env_flag("ALLOW_PRODUCTION_DRILL"))
    parser.add_argument("--offsite-backup-target", default=_first_value(None, "OFFSITE_BACKUP_TARGET"))
    parser.add_argument("--offsite-restore-target", default=_first_value(None, "OFFSITE_RESTORE_TARGET"))
    parser.add_argument("--external-storage-restore-target", default=_first_value(None, "EXTERNAL_STORAGE_RESTORE_TARGET"))
    parser.add_argument("--external-storage-backup-ref", default=_first_value(None, "EXTERNAL_STORAGE_BACKUP_REF"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan = build_plan(
        args.mode,
        args.package,
        args.backup,
        maintenance_window_id=args.maintenance_window_id,
        allow_production_drill=args.allow_production_drill,
        offsite_backup_target=args.offsite_backup_target,
        offsite_restore_target=args.offsite_restore_target,
        external_storage_restore_target=args.external_storage_restore_target,
        external_storage_backup_ref=args.external_storage_backup_ref,
    )
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print(f"summary\t{plan['summary']}")
        print(f"mode\t{plan['mode']}")
        print(f"current_version\t{plan['current_version']}")
        for asset in plan["assets"]:
            print(f"asset\t{asset['label']}\t{'ok' if asset['exists'] else 'missing'}\t{asset['path'] or '-'}\t{asset['detail']}")
        gate = plan["maintenance_gate"]
        gate_status = "ready" if gate["destructive_steps_executable"] else "blocked"
        missing_gate = ",".join(gate["missing_inputs"]) if gate["missing_inputs"] else "none"
        print(f"maintenance_gate\t{gate_status}\twindow={gate['maintenance_window_id'] or '-'}\tmissing={missing_gate}")
        for drill in plan["drill_readiness"]:
            missing = ",".join(drill["missing_inputs"]) if drill["missing_inputs"] else "none"
            print(f"drill\t{drill['name']}\t{drill['status']}\tmissing={missing}")
        for step in plan["steps"]:
            flag = "destructive" if step["destructive"] else "safe"
            print(f"step\t{step['name']}\t{flag}\t{step['command']}")
        for note in plan["safety_notes"]:
            print(f"safety_note\t{note}")
    return 1 if plan["summary"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
