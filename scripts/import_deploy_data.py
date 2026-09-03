#!/usr/bin/env python3
"""Stage real data sources into the standard deploy_data layout.

Supports copying or symlinking source files/directories into:
  deploy_data/annotations
  deploy_data/sifts
  deploy_data/pdb
  deploy_data/alphafold
  deploy_data/foldseek/{pdb,alphafold,custom}
  deploy_data/smoke/query.pdb
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "deploy_data"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _copy_or_link(src: Path, dst: Path, symlink: bool) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Source does not exist: {src}")

    if dst.exists() or dst.is_symlink():
        _remove_existing(dst)

    if symlink:
        dst.symlink_to(src, target_is_directory=src.is_dir())
        return

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        _ensure_dir(dst.parent)
        shutil.copy2(src, dst)


def _stage(src: str | None, dst: Path, symlink: bool, manifest: dict[str, object], label: str) -> None:
    if not src:
        return
    source = Path(src).expanduser().resolve()
    _copy_or_link(source, dst, symlink)
    manifest[label] = {
        "source": str(source),
        "target": str(dst),
        "mode": "symlink" if symlink else "copy",
        "kind": "directory" if source.is_dir() else "file",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Target deploy_data root")
    parser.add_argument("--annotations", help="Source directory or file for annotations")
    parser.add_argument("--sifts", help="Source directory or file for SIFTS mappings")
    parser.add_argument("--pdb", help="Source directory or file for curated PDB structures")
    parser.add_argument("--alphafold", help="Source directory or file for curated AlphaFold structures")
    parser.add_argument("--foldseek-root", help="Source directory to stage into deploy_data/foldseek")
    parser.add_argument("--foldseek-pdb", help="Source directory for foldseek/pdb")
    parser.add_argument("--foldseek-alphafold", help="Source directory for foldseek/alphafold")
    parser.add_argument("--foldseek-custom", help="Source directory for foldseek/custom")
    parser.add_argument("--smoke-pdb", help="Source PDB file for smoke/query.pdb")
    parser.add_argument("--symlink", action="store_true", help="Create symlinks instead of copying")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    manifest: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_root": str(output),
        "entries": {},
    }

    annotations_dir = output / "annotations"
    sifts_dir = output / "sifts"
    pdb_dir = output / "pdb"
    alphafold_dir = output / "alphafold"
    foldseek_dir = output / "foldseek"
    smoke_file = output / "smoke" / "query.pdb"

    for path in (
        annotations_dir,
        sifts_dir,
        pdb_dir,
        alphafold_dir,
        foldseek_dir / "pdb",
        foldseek_dir / "alphafold",
        foldseek_dir / "custom",
        smoke_file.parent,
    ):
        _ensure_dir(path)

    entries = manifest["entries"]
    assert isinstance(entries, dict)

    _stage(args.annotations, annotations_dir, args.symlink, entries, "annotations")
    _stage(args.sifts, sifts_dir, args.symlink, entries, "sifts")
    _stage(args.pdb, pdb_dir, args.symlink, entries, "pdb")
    _stage(args.alphafold, alphafold_dir, args.symlink, entries, "alphafold")

    if args.foldseek_root:
        _stage(args.foldseek_root, foldseek_dir, args.symlink, entries, "foldseek_root")
    else:
        _stage(args.foldseek_pdb, foldseek_dir / "pdb", args.symlink, entries, "foldseek_pdb")
        _stage(args.foldseek_alphafold, foldseek_dir / "alphafold", args.symlink, entries, "foldseek_alphafold")
        _stage(args.foldseek_custom, foldseek_dir / "custom", args.symlink, entries, "foldseek_custom")

    _stage(args.smoke_pdb, smoke_file, args.symlink, entries, "smoke_pdb")

    manifest_path = output / "import-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"Staged deploy_data root: {output}")
    print(f"Manifest: {manifest_path}")
    if not entries:
        print("No sources were provided. Nothing was staged.")
    else:
        for name, entry in entries.items():
            assert isinstance(entry, dict)
            print(f"- {name}: {entry['mode']} {entry['source']} -> {entry['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
