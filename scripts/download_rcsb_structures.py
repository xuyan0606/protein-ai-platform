#!/usr/bin/env python3
"""Download PDB/mmCIF structure files from the official RCSB file service.

Examples:
  python scripts/download_rcsb_structures.py --ids 4HHB,1TIM --format cif
  python scripts/download_rcsb_structures.py --id-file ./pdb_ids.txt --format pdb --gzip
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "deploy_data" / "pdb"
RCSB_FILE_BASE = "https://files.rcsb.org/download"
VALID_FORMATS = {"pdb", "cif"}


def _parse_ids(raw_ids: str | None, id_file: str | None) -> list[str]:
    values: list[str] = []
    if raw_ids:
        values.extend(part.strip() for part in raw_ids.replace("\n", ",").split(","))
    if id_file:
        text = Path(id_file).expanduser().read_text(encoding="utf-8")
        values.extend(part.strip() for part in text.replace("\n", ",").split(","))
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        normalized = value.upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def _gunzip_in_place(path: Path) -> Path:
    if path.suffix != ".gz":
        return path
    target = path.with_suffix("")
    with gzip.open(path, "rb") as src:
        with target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    path.unlink()
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma-separated PDB IDs, e.g. 4HHB,1TIM")
    parser.add_argument("--id-file", help="Text file with PDB IDs separated by commas or newlines")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Download directory")
    parser.add_argument("--format", default="cif", choices=sorted(VALID_FORMATS), help="Structure file format")
    parser.add_argument("--gzip", action="store_true", help="Keep downloaded .gz archives instead of extracting them")
    args = parser.parse_args()

    ids = _parse_ids(args.ids, args.id_file)
    if not ids:
        print("No PDB IDs provided. Use --ids or --id-file.", file=sys.stderr)
        return 1

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for pdb_id in ids:
        suffix = f".{args.format}.gz"
        url = f"{RCSB_FILE_BASE}/{pdb_id}{suffix}"
        archive_path = output / f"{pdb_id}{suffix}"
        try:
            _download(url, archive_path)
            final_path = archive_path if args.gzip else _gunzip_in_place(archive_path)
            print(f"OK {pdb_id} -> {final_path}")
        except urllib.error.HTTPError as exc:
            failures.append(f"{pdb_id}: HTTP {exc.code}")
            if archive_path.exists():
                archive_path.unlink()
        except Exception as exc:
            failures.append(f"{pdb_id}: {exc}")
            if archive_path.exists():
                archive_path.unlink()

    if failures:
        print("Failed downloads:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
