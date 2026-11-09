#!/usr/bin/env python3
"""Orchestrate one deploy_data update run from a live manifest.

The script is safe by default when used with --plan-only. Real execution calls
refresh_live_deploy_data.py, then records a run manifest under deploy_data/updates
for admin UI/readiness history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEPLOY_ROOT = PROJECT_ROOT / "deploy_data"
DEFAULT_MANIFEST = DEFAULT_DEPLOY_ROOT / "live_manifest.json"
DEFAULT_UPDATES_DIR = DEFAULT_DEPLOY_ROOT / "updates"


@dataclass
class UpdatePlan:
    name: str
    status: str
    detail: str
    command: list[str] | None = None


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Manifest must be a JSON object: {path}")
    return payload


def _string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key) or []
    if not isinstance(value, list):
        raise SystemExit(f"Manifest field '{key}' must be a JSON array")
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _refresh_command(args: argparse.Namespace, manifest_path: Path, deploy_root: Path) -> list[str]:
    command = [
        sys.executable,
        "scripts/refresh_live_deploy_data.py",
        "--manifest",
        str(manifest_path),
        "--deploy-root",
        str(deploy_root),
    ]
    if args.skip_downloads:
        command.append("--skip-downloads")
    if args.verify:
        command.append("--verify")
    if args.docker_verify:
        command.append("--docker-verify")
    return command


def _check_command(deploy_root: Path) -> list[str]:
    return [sys.executable, "scripts/check_deploy_data.py", "--root", str(deploy_root), "--json"]


def _build_plan(args: argparse.Namespace, manifest_path: Path, deploy_root: Path, manifest: dict[str, Any]) -> list[UpdatePlan]:
    pdb_ids = _string_list(manifest, "pdb_ids")
    uniprot_ids = _string_list(manifest, "uniprot_ids")
    return [
        UpdatePlan(
            name="manifest",
            status="ready",
            detail=f"{len(pdb_ids)} pdb_ids, {len(uniprot_ids)} uniprot_ids",
            command=None,
        ),
        UpdatePlan(
            name="refresh_live_deploy_data",
            status="planned",
            detail="download/build/write env/check chain",
            command=_refresh_command(args, manifest_path, deploy_root),
        ),
        UpdatePlan(
            name="check_deploy_data",
            status="planned",
            detail="machine-readable deploy_data readiness check",
            command=_check_command(deploy_root),
        ),
        UpdatePlan(
            name="schedule_hint",
            status="manual",
            detail="cron example: 0 3 * * 0 cd PROJECT_ROOT && python3 scripts/run_deploy_data_update.py --manifest deploy_data/live_manifest.json",
            command=None,
        ),
    ]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(PROJECT_ROOT), capture_output=True, text=True, check=False)


def _write_update_manifest(
    path: Path,
    *,
    status: str,
    started_at: str,
    duration_seconds: float,
    manifest_path: Path,
    deploy_root: Path,
    refresh_command: list[str],
    refresh_result: subprocess.CompletedProcess[str] | None,
    readiness: Any,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "component": "deploy_data",
        "status": status,
        "version": _utc_stamp(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started_at,
        "duration_seconds": duration_seconds,
        "manifest": str(manifest_path),
        "deploy_root": str(deploy_root),
        "command": refresh_command,
        "returncode": refresh_result.returncode if refresh_result else None,
        "stdout_tail": (refresh_result.stdout or "").splitlines()[-20:] if refresh_result else [],
        "stderr_tail": (refresh_result.stderr or "").splitlines()[-20:] if refresh_result else [],
        "readiness": readiness,
    }
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _render_text(plan: list[UpdatePlan]) -> None:
    for item in plan:
        command = " ".join(item.command or [])
        suffix = f"\t{command}" if command else ""
        print(f"{item.name}\t{item.status}\t{item.detail}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="JSON manifest with pdb_ids/uniprot_ids")
    parser.add_argument("--deploy-root", default=str(DEFAULT_DEPLOY_ROOT), help="deploy_data root")
    parser.add_argument("--updates-dir", default=str(DEFAULT_UPDATES_DIR), help="Directory for update run manifests")
    parser.add_argument("--skip-downloads", action="store_true", help="Reuse existing downloaded files")
    parser.add_argument("--verify", action="store_true", help="Run host live gates after refresh")
    parser.add_argument("--docker-verify", action="store_true", help="Run Docker live gates after refresh")
    parser.add_argument("--plan-only", action="store_true", help="Print plan without executing commands")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    deploy_root = Path(args.deploy_root).expanduser().resolve()
    updates_dir = Path(args.updates_dir).expanduser().resolve()
    manifest = _read_manifest(manifest_path)
    plan = _build_plan(args, manifest_path, deploy_root, manifest)

    if args.plan_only:
        payload = {
            "project_root": str(PROJECT_ROOT),
            "deploy_root": str(deploy_root),
            "manifest": str(manifest_path),
            "summary": {"status": "planned", "executed": False},
            "results": [asdict(item) for item in plan],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=True, indent=2))
        else:
            _render_text(plan)
        return 0

    started_at = datetime.now(timezone.utc).isoformat()
    started = time.time()
    refresh_command = _refresh_command(args, manifest_path, deploy_root)
    refresh_result = _run(refresh_command)
    readiness: Any = None
    status = "completed" if refresh_result.returncode == 0 else "failed"

    if refresh_result.returncode == 0:
        check_result = _run(_check_command(deploy_root))
        try:
            readiness = json.loads(check_result.stdout)
        except json.JSONDecodeError:
            readiness = {"parse_error": True, "stdout": check_result.stdout[-4000:]}
        if check_result.returncode != 0:
            status = "failed"
    else:
        check_result = None

    duration = round(time.time() - started, 2)
    output_manifest = updates_dir / f"deploy_data_update_{_utc_stamp()}.json"
    _write_update_manifest(
        output_manifest,
        status=status,
        started_at=started_at,
        duration_seconds=duration,
        manifest_path=manifest_path,
        deploy_root=deploy_root,
        refresh_command=refresh_command,
        refresh_result=refresh_result,
        readiness=readiness,
    )

    if args.json:
        print(json.dumps({
            "summary": {"status": status, "executed": True},
            "update_manifest": str(output_manifest),
            "refresh_returncode": refresh_result.returncode,
            "check_returncode": check_result.returncode if check_result else None,
        }, ensure_ascii=True, indent=2))
    else:
        print(f"deploy_data_update\t{status}\t{output_manifest}")
        if refresh_result.stdout:
            print(refresh_result.stdout.strip())
        if refresh_result.stderr:
            print(refresh_result.stderr.strip(), file=sys.stderr)
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
