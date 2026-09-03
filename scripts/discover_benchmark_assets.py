#!/usr/bin/env python3
"""Discover locally available files that may belong to a benchmark case.

Example:
  python3 scripts/discover_benchmark_assets.py --case-id venus-15b --search-root /Users/xuyan/科为博
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "benchmark_cases"
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "foldseek",
}
STRUCTURE_EXTENSIONS = {".pdb", ".ent", ".cif"}
ALPHAFOLD_HINTS = ("af-", "alphafold", "predicted_aligned_error", "pae")
MAPPING_HINTS = ("sifts", "mapping", "residue")
ANNOTATION_HINTS = ("interpro", "signalp", "mcsa", "annotation")
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".md", ".txt"}


def _load_case(case_id: str) -> dict[str, object]:
    fixture = FIXTURE_ROOT / f"{case_id.replace('-', '_')}.json"
    if not fixture.exists():
        raise SystemExit(f"Benchmark fixture not found: {fixture}")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid fixture JSON: {fixture}")
    return payload


def _relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _keyword_score(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in lowered)


def _classify(path: Path) -> str | None:
    name = path.name.lower()
    suffixes = [part.lower() for part in path.suffixes]
    if any(token in name for token in ALPHAFOLD_HINTS):
        return "alphafold"
    if any(token in name for token in MAPPING_HINTS):
        return "sifts"
    if any(token in name for token in ANNOTATION_HINTS):
        return "annotations"
    if suffixes and suffixes[-1] in STRUCTURE_EXTENSIONS:
        return "structures"
    if suffixes and suffixes[-1] in DOCUMENT_EXTENSIONS:
        return "reference_docs"
    return None


def _walk_files(search_root: Path):
    for candidate in search_root.rglob("*"):
        if any(part in SKIP_DIRS for part in candidate.parts):
            continue
        if candidate.is_file():
            yield candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True, help="Benchmark case id, e.g. venus-15b")
    parser.add_argument(
        "--search-root",
        action="append",
        default=[],
        help="Root directory to scan. Can be specified multiple times.",
    )
    args = parser.parse_args()

    case = _load_case(args.case_id)
    paths = case.get("paths")
    if not isinstance(paths, dict):
        raise SystemExit("Fixture missing 'paths'")

    search_roots = [Path(item).expanduser().resolve() for item in args.search_root] or [PROJECT_ROOT]
    keywords = [str(item).strip().lower() for item in case.get("keywords", []) if str(item).strip()]
    keywords.extend(
        text.lower()
        for text in (
            str(case.get("id", "")).strip(),
            str(case.get("program", "")).strip(),
            str(case.get("protein_name", "")).strip(),
        )
        if text
    )
    keywords = sorted(set(keywords))

    buckets: dict[str, list[dict[str, object]]] = {
        "structures": [],
        "alphafold": [],
        "sifts": [],
        "annotations": [],
        "reference_docs": [],
    }

    for root in search_roots:
        if not root.exists():
            continue
        for candidate in _walk_files(root):
            score = _keyword_score(candidate.name, keywords) + _keyword_score(str(candidate.parent), keywords)
            if score <= 0:
                continue
            category = _classify(candidate)
            if category is None:
                continue
            buckets[category].append(
                {
                    "path": str(candidate),
                    "project_relative_path": _relative_to_project(candidate),
                    "size_bytes": candidate.stat().st_size,
                    "score": score,
                }
            )

    for category in buckets:
        buckets[category].sort(key=lambda item: (-int(item["score"]), str(item["path"])))

    report = {
        "case_id": args.case_id,
        "keywords": keywords,
        "search_roots": [str(root) for root in search_roots],
        "counts": {category: len(items) for category, items in buckets.items()},
        "results": buckets,
    }

    report_path = PROJECT_ROOT / str(paths.get("discovery_report_file", "")).strip()
    if not report_path.name:
        raise SystemExit("Fixture missing paths.discovery_report_file")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote discovery report: {report_path}")
    print(json.dumps(report["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
