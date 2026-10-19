#!/usr/bin/env python3
"""Read-only upgrade readiness report for Protein AI Platform."""

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

from check_environment import collect_checks, summarize
from check_model_selection_alignment import check_alignment


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class UpgradeCheck:
    def __init__(self, label, status, detail, data=None):
        self.label = label
        self.status = status
        self.detail = detail
        self.data = data

    def as_dict(self):
        return {
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "data": self.data,
        }


def _run_subprocess(command, cwd=PROJECT_ROOT, timeout=10):
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )
    except Exception:
        return None
    return proc


def _git(args):
    proc = _run_subprocess(["git"] + list(args), timeout=10)
    if proc is None:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _git_check():
    revision = _git(["rev-parse", "--short", "HEAD"])
    dirty = _git(["status", "--short"])
    if revision is None:
        return UpgradeCheck("git", "warning", "git revision unavailable")
    status = "manual_required" if dirty else "ok"
    detail = f"revision={revision}; dirty_files={len(dirty.splitlines()) if dirty else 0}"
    return UpgradeCheck("git", status, detail, {"revision": revision, "dirty": bool(dirty)})


def _project_version():
    version_path = PROJECT_ROOT / "VERSION"
    if not version_path.exists():
        return "unknown"
    return version_path.read_text(encoding="utf-8").strip() or "unknown"


def _project_version_check():
    version = _project_version()
    status = "critical" if version == "unknown" else "ok"
    return UpgradeCheck("project.version", status, f"version={version}", {"version": version})


def _model_selection_check():
    failures = check_alignment(PROJECT_ROOT)
    return UpgradeCheck(
        "model.selection",
        "critical" if failures else "ok",
        "mismatches=" + (",".join(failures) if failures else "none"),
        {"expected_model_id": "gpt6-sol", "expected_native_model": "gpt-6-sol", "failures": failures},
    )


def _frontend_version_check():
    package_path = PROJECT_ROOT / "frontend" / "package.json"
    if not package_path.exists():
        return UpgradeCheck("frontend.version", "critical", "frontend/package.json missing")
    data = json.loads(package_path.read_text(encoding="utf-8"))
    version = str(data.get("version") or "unknown")
    project_version = _project_version()
    status = "warning" if version in {"0.0.0", "unknown"} or version != project_version else "ok"
    detail = f"version={version}; project_version={project_version}"
    return UpgradeCheck("frontend.version", status, detail, {"version": version, "project_version": project_version})


def _read_py_assignment(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            if node.value is None:
                return None
            return ast.literal_eval(node.value)
    return None


def _alembic_check():
    versions_dir = PROJECT_ROOT / "backend" / "alembic" / "versions"
    if not versions_dir.exists():
        return UpgradeCheck("alembic", "critical", "backend/alembic/versions missing")
    revisions = {}
    down_revisions = set()
    errors = []
    for path in sorted(versions_dir.glob("*.py")):
        try:
            revision = _read_py_assignment(path, "revision")
            down_revision = _read_py_assignment(path, "down_revision")
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if isinstance(revision, str):
            revisions[revision] = {"file": path.name, "down_revision": down_revision}
        if isinstance(down_revision, str):
            down_revisions.add(down_revision)
        elif isinstance(down_revision, (tuple, list)):
            down_revisions.update(str(item) for item in down_revision if item)

    heads = sorted(set(revisions) - down_revisions)
    status = "critical" if errors else "warning" if len(heads) != 1 else "ok"
    detail = f"revisions={len(revisions)}; heads={','.join(heads) if heads else 'none'}"
    return UpgradeCheck(
        "alembic",
        status,
        detail,
        {"heads": heads, "revision_count": len(revisions), "errors": errors},
    )


def _env_files_check():
    paths = {
        "docker.env": PROJECT_ROOT / "docker" / ".env",
        "docker.env_example": PROJECT_ROOT / "docker" / ".env.example",
        "docker.env_deploy_data": PROJECT_ROOT / "docker" / ".env.deploy-data",
        "aliyun.app": PROJECT_ROOT / "docker" / ".env.aliyun.app",
        "aliyun.gpu": PROJECT_ROOT / "docker" / ".env.aliyun.gpu",
    }
    existing = {label: path.exists() for label, path in paths.items()}
    required_missing = [label for label in ("docker.env", "docker.env_example") if not existing[label]]
    status = "critical" if required_missing else "warning" if not existing["docker.env_deploy_data"] else "ok"
    detail = ", ".join(f"{label}={'yes' if exists else 'no'}" for label, exists in existing.items())
    return UpgradeCheck("env.files", status, detail, existing)


def _package_check():
    package_dir = PROJECT_ROOT / "dist" / "packages"
    packages = sorted(package_dir.glob("protein-ai-platform-*.tar.gz")) if package_dir.exists() else []
    if not packages:
        return UpgradeCheck("deploy.package", "warning", "no local package found under dist/packages")
    latest = packages[-1]
    checksum = latest.with_suffix(latest.suffix + ".sha256")
    status = "ok" if checksum.exists() else "warning"
    return UpgradeCheck(
        "deploy.package",
        status,
        f"latest={latest.relative_to(PROJECT_ROOT)}; checksum={'yes' if checksum.exists() else 'no'}",
        {"latest": str(latest), "checksum": str(checksum) if checksum.exists() else None},
    )


def _production_config_check():
    script = PROJECT_ROOT / "scripts" / "check_production_config.py"
    if not script.exists():
        return UpgradeCheck("production.config", "critical", "scripts/check_production_config.py missing")
    command = [
        sys.executable,
        str(script),
        "--json",
        "--mode",
        "production",
        "--skip-domain-https",
    ]
    for env_file in (
        PROJECT_ROOT / "docker" / ".env",
        PROJECT_ROOT / "docker" / ".env.aliyun.app",
    ):
        if env_file.exists():
            command.extend(["--env-file", str(env_file)])
    try:
        proc = _run_subprocess(command, timeout=15)
        if proc is None:
            raise RuntimeError("subprocess failed to start")
    except Exception as exc:
        return UpgradeCheck("production.config", "critical", f"config validator failed to run: {exc}")
    if proc.returncode != 0:
        return UpgradeCheck("production.config", "critical", "production config validator returned non-zero")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return UpgradeCheck("production.config", "critical", "production config validator returned invalid JSON")
    summary = payload.get("summary") or {}
    checks = payload.get("checks") or []
    critical = int(summary.get("critical") or 0)
    warning = int(summary.get("warning") or 0)
    status = "critical" if critical else "warning" if warning else "ok"
    detail = f"{summary.get('status', 'unknown')}; critical={critical}; warning={warning}; checks={len(checks)}"
    return UpgradeCheck("production.config", status, detail, {"summary": summary, "secrets_printed": False})


def _release_provenance_check():
    """Expose immutable release provenance without printing environment secrets."""
    manifest_value = str(os.environ.get("RELEASE_MANIFEST", "")).strip()
    manifest_path = Path(manifest_value) if manifest_value else PROJECT_ROOT / "RELEASE-MANIFEST.json"
    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path
    if not manifest_path.exists():
        return UpgradeCheck(
            "release.provenance",
            "manual_required",
            "release manifest missing; production deployment must provide RELEASE-MANIFEST.json",
            {"manifest": str(manifest_path), "verified": False},
        )
    try:
        from release_provenance import verify_manifest

        result = verify_manifest(root=PROJECT_ROOT, manifest_path=manifest_path)
    except Exception as exc:
        return UpgradeCheck(
            "release.provenance",
            "critical",
            f"release manifest verification failed: {type(exc).__name__}",
            {"manifest": str(manifest_path), "verified": False},
        )
    status = "ok" if result.get("status") == "verified" else "critical"
    return UpgradeCheck(
        "release.provenance",
        status,
        "verified immutable release" if status == "ok" else "release provenance drift detected",
        {
            "manifest": str(manifest_path),
            "verified": status == "ok",
            "release_id": result.get("release_id"),
            "failures": result.get("failures", []),
        },
    )


def _report_version_alignment_check():
    manifest_value = str(os.environ.get("RELEASE_MANIFEST", "")).strip()
    manifest_path = Path(manifest_value) if manifest_value else PROJECT_ROOT / "RELEASE-MANIFEST.json"
    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path
    if not manifest_path.exists():
        return UpgradeCheck(
            "release.alignment",
            "manual_required",
            "release manifest missing; report, wet-lab, model, and frontend alignment not verifiable",
            {"manifest": str(manifest_path), "verified": False},
        )
    try:
        from check_report_version_alignment import check_alignment as check_report_alignment

        result = check_report_alignment(root=PROJECT_ROOT, manifest_path=manifest_path)
    except Exception as exc:
        return UpgradeCheck(
            "release.alignment",
            "critical",
            f"release alignment check failed: {type(exc).__name__}",
            {"manifest": str(manifest_path), "verified": False},
        )
    status = "ok" if result.get("status") == "verified" else "critical"
    return UpgradeCheck(
        "release.alignment",
        status,
        "report and frontend versions aligned" if status == "ok" else "release alignment drift detected",
        {"manifest": str(manifest_path), "verified": status == "ok", "failures": result.get("failures", [])},
    )


def collect_upgrade_checks():
    env_summary = summarize(collect_checks())
    checks = [
        _git_check(),
        _project_version_check(),
        _model_selection_check(),
        _frontend_version_check(),
        _alembic_check(),
        _env_files_check(),
        _package_check(),
        _production_config_check(),
        _release_provenance_check(),
        _report_version_alignment_check(),
        UpgradeCheck("environment", "ok" if env_summary.status == "ready" else "warning", env_summary.detail),
    ]
    return checks


def _summary(checks):
    critical = [check for check in checks if check.status == "critical"]
    warning = [check for check in checks if check.status == "warning"]
    manual_required = [check for check in checks if check.status == "manual_required"]
    if critical:
        return UpgradeCheck("summary", "blocked", f"{len(critical)} critical checks")
    if warning:
        return UpgradeCheck("summary", "ready-with-warnings", f"{len(warning)} warning checks")
    if manual_required:
        return UpgradeCheck("summary", "ready-with-manual-gates", f"{len(manual_required)} manual gate checks")
    return UpgradeCheck("summary", "ready", "upgrade readiness passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero unless summary is ready")
    args = parser.parse_args()

    checks = collect_upgrade_checks()
    summary = _summary(checks)
    payload = {
        "project_root": str(PROJECT_ROOT),
        "checks": [check.as_dict() for check in checks],
        "summary": summary.as_dict(),
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
