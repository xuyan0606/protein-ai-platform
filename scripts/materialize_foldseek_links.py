#!/usr/bin/env python3
"""Replace Foldseek DB symlinks with real files for portable deploy_data mounts."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = PROJECT_ROOT / "deploy_data" / "foldseek"


def _resolve_target(link: Path) -> Path:
    target = link.resolve(strict=False)
    if not target.exists():
        raise FileNotFoundError(f"Broken symlink: {link} -> {link.readlink()}")
    return target


def _materialize(link: Path) -> str:
    target = _resolve_target(link)
    link.unlink()
    if target.is_dir():
        shutil.copytree(target, link)
        return "directory"
    shutil.copy2(target, link)
    return "file"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Foldseek root to scan")
    parser.add_argument("--dry-run", action="store_true", help="Report links without modifying them")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Foldseek root does not exist: {root}")

    links = sorted(path for path in root.rglob("*") if path.is_symlink())
    if not links:
        print(f"No Foldseek symlinks found under {root}")
        return 0

    print(f"Found {len(links)} Foldseek symlink(s) under {root}")
    materialized = 0
    for link in links:
        target = _resolve_target(link)
        rel = link.relative_to(root)
        target_text = str(link.readlink())
        if args.dry_run:
            print(f"DRY-RUN {rel} -> {target_text}")
            continue
        kind = _materialize(link)
        materialized += 1
        print(f"MATERIALIZED {rel} ({kind}) from {target}")

    if args.dry_run:
        print("Dry run only. Re-run without --dry-run to replace the links.")
    else:
        print(f"Materialized {materialized} Foldseek symlink(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
