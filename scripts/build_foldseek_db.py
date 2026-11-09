#!/usr/bin/env python3
"""Build a local Foldseek database from curated deploy_data structures.

Examples:
  python scripts/build_foldseek_db.py --kind pdb
  python scripts/build_foldseek_db.py --kind alphafold --source deploy_data/alphafold
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEPLOY_ROOT = PROJECT_ROOT / "deploy_data"
DEFAULT_FOLDSEEK_BINARY = os.getenv("FOLDSEEK_BINARY", "")


def _has_supported_structures(path: Path) -> list[Path]:
    matches: list[Path] = []
    for candidate in sorted(path.rglob("*")):
        if not candidate.is_file():
            continue
        suffixes = candidate.suffixes
        if not suffixes:
            continue
        if suffixes[-1].lower() in {".pdb", ".ent", ".cif"}:
            matches.append(candidate)
            continue
        if len(suffixes) >= 2 and suffixes[-1].lower() == ".gz" and suffixes[-2].lower() in {".pdb", ".ent", ".cif"}:
            matches.append(candidate)
    return matches


def _remove_existing_prefix(target_dir: Path, prefix: str) -> int:
    removed = 0
    for candidate in sorted(target_dir.glob(f"{prefix}*")):
        if candidate.is_dir():
            shutil.rmtree(candidate)
        else:
            candidate.unlink()
        removed += 1
    return removed


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"{' '.join(cmd)} failed: {detail}")


def _resolve_binary(explicit: str) -> str:
    candidates: list[str] = []
    if explicit.strip():
        candidates.append(explicit.strip())
    env_binary = os.getenv("FOLDSEEK_BINARY", "").strip()
    if env_binary:
        candidates.append(env_binary)
    discovered = shutil.which("foldseek")
    if discovered:
        candidates.append(discovered)
    candidates.append(str(Path.home() / "tools" / "foldseek" / "bin" / "foldseek"))

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path.resolve())
        if shutil.which(candidate):
            return shutil.which(candidate) or candidate
    raise SystemExit(
        "Foldseek binary not found. Set FOLDSEEK_BINARY or pass --binary /path/to/foldseek."
    )


def _materialize_symlinks(root: Path) -> int:
    materialized = 0
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_symlink():
            continue
        target = candidate.resolve(strict=False)
        if not target.exists():
            raise FileNotFoundError(f"Broken symlink after createindex: {candidate} -> {candidate.readlink()}")
        candidate.unlink()
        if target.is_dir():
            shutil.copytree(target, candidate)
        else:
            shutil.copy2(target, candidate)
        materialized += 1
    return materialized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("pdb", "alphafold", "custom"), default="pdb", help="Deploy-data structure set to index")
    parser.add_argument("--deploy-root", default=str(DEFAULT_DEPLOY_ROOT), help="deploy_data root")
    parser.add_argument("--source", default="", help="Override source directory containing PDB/mmCIF files")
    parser.add_argument("--target", default="", help="Override target Foldseek DB directory")
    parser.add_argument("--prefix", default="", help="Output DB prefix name, e.g. protein_ai_pdb")
    parser.add_argument("--binary", default=DEFAULT_FOLDSEEK_BINARY, help="Foldseek binary path/name")
    parser.add_argument("--threads", type=int, default=8, help="CPU threads for Foldseek commands")
    parser.add_argument("--tmp-root", default="", help="Optional temp working directory root")
    args = parser.parse_args()

    deploy_root = Path(args.deploy_root).expanduser().resolve()
    source = Path(args.source).expanduser().resolve() if args.source else (deploy_root / args.kind)
    target_dir = Path(args.target).expanduser().resolve() if args.target else (deploy_root / "foldseek" / args.kind)
    prefix = args.prefix.strip() or f"protein_ai_{args.kind}"
    db_prefix = target_dir / prefix
    binary = _resolve_binary(args.binary)

    if not source.exists():
        raise SystemExit(f"Source directory does not exist: {source}")

    structures = _has_supported_structures(source)
    if not structures:
        raise SystemExit(f"No supported structure files found under: {source}")

    target_dir.mkdir(parents=True, exist_ok=True)
    tmp_root = Path(args.tmp_root).expanduser().resolve() if args.tmp_root else (target_dir / ".tmp-build")
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)

    removed = _remove_existing_prefix(target_dir, prefix)
    print(f"Building Foldseek DB kind={args.kind}")
    print(f"Source: {source}")
    print(f"Target directory: {target_dir}")
    print(f"DB prefix: {db_prefix}")
    print(f"Foldseek binary: {binary}")
    print(f"Structures: {len(structures)}")
    print(f"Removed stale prefix entries: {removed}")

    try:
        _run(
            [
                binary,
                "createdb",
                str(source),
                str(db_prefix),
                "--threads",
                str(args.threads),
            ]
        )
        _run(
            [
                binary,
                "createindex",
                str(db_prefix),
                str(tmp_root),
                "--threads",
                str(args.threads),
            ]
        )
        materialized = _materialize_symlinks(target_dir)
    finally:
        if tmp_root.exists():
            shutil.rmtree(tmp_root)

    print(f"Built Foldseek DB: {db_prefix}")
    print(f"Materialized symlinks: {materialized}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
