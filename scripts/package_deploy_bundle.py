#!/usr/bin/env python3
"""Create a deployable source bundle for Protein AI Platform.

The bundle intentionally excludes secrets, local dependencies, generated data,
runtime storage, logs, databases, and large deploy_data assets by default.
"""

import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_EXCLUDES = (
    ".git",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".coverage",
    ".agents",
    ".ruff_cache",
    ".mypy_cache",
    ".DS_Store",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.db",
    "*.sqlite3",
    "*.pem",
    "*.pdb",
    "*.zvec",
    "node_modules",
    ".venv",
    ".venv*",
    "venv",
    "venv*",
    ".tox",
    "*.egg-info",
    "dist",
    "build",
    "storage",
    "backups",
    "logs",
    "docker/volumes",
    "frontend/test-results",
    "frontend/dist",
    "backend/.env",
    "backend/.env.deploy-data",
    "backend/.env.production",
    "backend/.env.*.prepared",
    "backend/data",
    "docker/.env",
    "docker/.env.deploy-data",
    "docker/.env.aliyun.app",
    "docker/.env.aliyun.gpu",
    "docker/.env.*.bak-*",
    "docker/.env.*.prepared",
    "docker/ssl/*.key",
    "docker/ssl/*.crt",
    "deploy_data",
)

ALLOWED_ROOT_DIRS = {
    ".github",
    "backend",
    "docker",
    "docs",
    "frontend",
    "scripts",
}

ALLOWED_ROOT_FILES = {
    ".dockerignore",
    ".gitignore",
    "RELEASE-MANIFEST.json",
    "VERSION",
    "deploy-aliyun.sh",
    "Makefile",
    "README.md",
    "RELEASE-MANIFEST.json",
}


class BundleFile:
    def __init__(self, path: Path, archive_path: str, size_bytes: int) -> None:
        self.path = path
        self.archive_path = archive_path
        self.size_bytes = size_bytes


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_revision(root: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except Exception:
        return None
    revision = result.stdout.strip()
    return revision or None


def _matches(pattern: str, rel_posix: str, name: str) -> bool:
    parts = rel_posix.split("/")
    if "/" not in pattern:
        if any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return (
        fnmatch.fnmatch(rel_posix, pattern)
        or fnmatch.fnmatch(name, pattern)
        or rel_posix == pattern
        or rel_posix.startswith(f"{pattern}/")
    )


def _is_excluded(path: Path, root: Path, excludes: Iterable[str]) -> bool:
    rel_posix = path.relative_to(root).as_posix()
    name = path.name
    return any(_matches(pattern, rel_posix, name) for pattern in excludes)


def _is_allowed(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if len(rel.parts) == 1:
        return rel.parts[0] in ALLOWED_ROOT_FILES or rel.parts[0] in ALLOWED_ROOT_DIRS
    return rel.parts[0] in ALLOWED_ROOT_DIRS


def collect_files(root: Path, *, include_deploy_data: bool, extra_excludes: Iterable[str]) -> List[BundleFile]:
    excludes = list(DEFAULT_EXCLUDES)
    if include_deploy_data:
        excludes = [item for item in excludes if item != "deploy_data"]
    excludes.extend(extra_excludes)

    files = []  # type: List[BundleFile]
    for path in sorted(root.rglob("*")):
        if path == root:
            continue
        if not _is_allowed(path, root):
            continue
        if _is_excluded(path, root, excludes):
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            continue
        rel_posix = path.relative_to(root).as_posix()
        files.append(
            BundleFile(
                path=path,
                archive_path=f"protein-ai-platform/{rel_posix}",
                size_bytes=path.stat().st_size,
            )
        )
    return files


def _manifest(root: Path, files: List[BundleFile], *, include_deploy_data: bool) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "name": "protein-ai-platform",
        "created_at": now,
        "git_revision": _git_revision(root),
        "include_deploy_data": include_deploy_data,
        "file_count": len(files),
        "total_size_bytes": sum(item.size_bytes for item in files),
        "default_excludes": list(DEFAULT_EXCLUDES),
        "entrypoints": {
            "preflight": "make package-preflight",
            "local_docker": "make docker-up",
            "aliyun_app": "./deploy-aliyun.sh app",
            "aliyun_gpu": "./deploy-aliyun.sh gpu",
        },
    }


def create_bundle(root: Path, output_dir: Path, files: List[BundleFile], manifest: Dict[str, Any]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    revision = manifest.get("git_revision") or "nogit"
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / f"protein-ai-platform-{timestamp}-{revision}.tar.gz"

    with tarfile.open(bundle_path, "w:gz") as tar:
        manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
        info = tarfile.TarInfo("protein-ai-platform/PACKAGE-MANIFEST.json")
        info.size = len(manifest_bytes)
        info.mtime = int(datetime.now(timezone.utc).timestamp())
        tar.addfile(info, io.BytesIO(manifest_bytes))

        for item in files:
            tar.add(item.path, arcname=item.archive_path, recursive=False)

    digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    checksum_path = bundle_path.with_suffix(bundle_path.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {bundle_path.name}\n", encoding="utf-8")
    return bundle_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a deployable Protein AI Platform source bundle.")
    parser.add_argument("--output-dir", default="dist/packages", help="Directory for generated tar.gz bundles.")
    parser.add_argument("--include-deploy-data", action="store_true", help="Include deploy_data/. Disabled by default.")
    parser.add_argument("--exclude", action="append", default=[], help="Additional exclude pattern. May be passed more than once.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be packaged without writing a tarball.")
    args = parser.parse_args()

    root = _repo_root()
    files = collect_files(root, include_deploy_data=args.include_deploy_data, extra_excludes=args.exclude)
    manifest = _manifest(root, files, include_deploy_data=args.include_deploy_data)

    print(f"root\t{root}")
    print(f"files\t{manifest['file_count']}")
    print(f"size_bytes\t{manifest['total_size_bytes']}")
    print(f"include_deploy_data\t{str(args.include_deploy_data).lower()}")

    if args.dry_run:
        for item in files[:20]:
            print(f"include\t{item.archive_path}\t{item.size_bytes}")
        if len(files) > 20:
            print(f"include\t... {len(files) - 20} more files")
        print("summary\tdry-run")
        return 0

    bundle_path = create_bundle(root, Path(args.output_dir), files, manifest)
    print(f"bundle\t{bundle_path}")
    print(f"checksum\t{bundle_path}.sha256")
    print("summary\tcreated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
