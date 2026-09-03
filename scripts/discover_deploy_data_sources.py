#!/usr/bin/env python3
"""Discover likely local data sources that could be staged into deploy_data."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEARCH_ROOT = PROJECT_ROOT.parent.parent.parent
SUPPORTED_SUFFIXES = {".json", ".csv", ".tsv", ".pdb", ".cif", ".m8"}
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "Library",
}
SKIP_PATH_PARTS = {
    "deploy_data",
    "backend",
    "storage",
    "uploads",
    "node_modules",
    ".git",
    ".venv",
}
DEMO_PATH_MARKERS = {
    "fixtures/local_annotations",
    "fixtures/structure_smoke",
}


@dataclass
class Candidate:
    category: str
    path: str
    reason: str


def _should_skip(path: Path) -> bool:
    return path.name in SKIP_DIR_NAMES


def _classify(path: Path) -> Candidate | None:
    text = str(path).lower()
    name = path.name.lower()

    if path.suffix.lower() not in SUPPORTED_SUFFIXES and not path.is_dir():
        return None

    if any(part in SKIP_PATH_PARTS for part in path.parts):
        return None

    if any(marker in text for marker in DEMO_PATH_MARKERS):
        return None

    if "sifts" in text and path.suffix.lower() in {".json", ".csv", ".tsv"}:
        return Candidate("sifts", str(path), "path/name suggests SIFTS mapping export")

    if any(token in text for token in ("interpro", "signalp", "mcsa")) and path.suffix.lower() in {".json", ".csv", ".tsv"}:
        return Candidate("annotations", str(path), "path/name suggests annotation export")

    if name == "metadata.json" and "annotation" in text:
        return Candidate("annotations", str(path), "annotation metadata file")

    if "foldseek" in text and path.suffix.lower() in {".m8", ".pdb", ".cif", ".json"}:
        return Candidate("foldseek_reference", str(path), "path/name suggests Foldseek reference or result")

    if "alphafold" in text and path.suffix.lower() in {".pdb", ".cif", ".json"}:
        return Candidate("alphafold_reference", str(path), "path/name suggests AlphaFold structure/metadata")

    if any(token in text for token in ("rcsb", "pdb")) and path.suffix.lower() == ".pdb":
        return Candidate("pdb_reference", str(path), "PDB structure candidate")

    return None


def _discover(root: Path, limit: int) -> list[Candidate]:
    matches: list[Candidate] = []
    for path in root.rglob("*"):
        if _should_skip(path):
            continue
        if not path.is_file():
            continue
        candidate = _classify(path)
        if candidate is None:
            continue
        matches.append(candidate)
        if len(matches) >= limit:
            break
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_SEARCH_ROOT), help="Root directory to scan")
    parser.add_argument("--limit", type=int, default=200, help="Maximum number of matches to report")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    results = _discover(root, max(1, int(args.limit)))

    if args.json:
        print(json.dumps([asdict(item) for item in results], ensure_ascii=True, indent=2))
        return 0

    if not results:
        print(f"No candidate data sources found under {root}")
        return 0

    print(f"Candidate data sources under {root}:")
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for item in results:
        grouped[item.category].append(item)
    for category in sorted(grouped):
        for item in grouped[category]:
            print(f"{item.category}\t{item.path}\t{item.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
