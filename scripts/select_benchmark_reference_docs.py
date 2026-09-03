#!/usr/bin/env python3
"""Select and stage reference documents for a benchmark case from discovery results.

Example:
  python3 scripts/select_benchmark_reference_docs.py --case-id venus-15b
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "benchmark_cases"
ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx", ".md", ".txt"}


def _load_case(case_id: str) -> dict[str, object]:
    fixture = FIXTURE_ROOT / f"{case_id.replace('-', '_')}.json"
    if not fixture.exists():
        raise SystemExit(f"Benchmark fixture not found: {fixture}")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid fixture JSON: {fixture}")
    return payload


def _is_allowed(path: Path) -> bool:
    return path.suffix.lower() in ALLOWED_SUFFIXES


def _selection_weight(path: Path, score: int, keywords: list[str]) -> tuple[int, int, int, str]:
    text = str(path).lower()
    direct_hits = sum(1 for keyword in keywords if keyword in text)
    name_hits = sum(1 for keyword in keywords if keyword in path.name.lower())
    return (score, name_hits, direct_hits, str(path))


def _safe_name(path: Path) -> str:
    stem = path.stem.replace("/", "_").replace(" ", "_")
    suffix = path.suffix.lower()
    return f"{stem}{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True, help="Benchmark case id, e.g. venus-15b")
    parser.add_argument("--limit", type=int, default=8, help="Maximum number of docs to stage")
    parser.add_argument("--max-size-mb", type=int, default=8, help="Skip single files larger than this size")
    args = parser.parse_args()

    case = _load_case(args.case_id)
    paths = case.get("paths")
    if not isinstance(paths, dict):
        raise SystemExit("Fixture missing 'paths'")

    discovery_report = PROJECT_ROOT / str(paths.get("discovery_report_file", ""))
    target_root = PROJECT_ROOT / str(paths.get("incoming_reference_docs_dir", ""))
    manifest_path = target_root / "selected_manifest.json"
    auto_selected_root = target_root / "auto_selected"
    source_bundle_dir = PROJECT_ROOT / str(paths.get("source_bundle_dir", ""))

    if not discovery_report.exists():
        raise SystemExit(f"Discovery report not found: {discovery_report}")

    payload = json.loads(discovery_report.read_text(encoding="utf-8"))
    results = payload.get("results", {})
    if not isinstance(results, dict):
        raise SystemExit(f"Invalid discovery report: {discovery_report}")

    keywords = [str(item).lower() for item in case.get("keywords", []) if str(item).strip()]
    target_root.mkdir(parents=True, exist_ok=True)
    auto_selected_root.mkdir(parents=True, exist_ok=True)

    max_size_bytes = args.max_size_mb * 1024 * 1024
    candidates: list[tuple[tuple[int, int, int, str], Path, dict[str, object]]] = []
    for item in results.get("reference_docs", []):
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path", "")))
        if not path.exists() or not path.is_file() or not _is_allowed(path):
            continue
        if source_bundle_dir in path.parents:
            continue
        if target_root in path.parents:
            continue
        size_bytes = int(item.get("size_bytes", 0) or 0)
        if size_bytes <= 0 or size_bytes > max_size_bytes:
            continue
        score = int(item.get("score", 0) or 0)
        weight = _selection_weight(path, score, keywords)
        candidates.append((weight, path, item))

    candidates.sort(reverse=True)
    selected: list[dict[str, object]] = []
    seen_names: set[str] = set()
    seen_sources: set[str] = set()

    for _, path, item in candidates:
        if len(selected) >= args.limit:
            break
        normalized_name = _safe_name(path)
        if normalized_name in seen_names or str(path) in seen_sources:
            continue
        target = auto_selected_root / normalized_name
        shutil.copy2(path, target)
        seen_names.add(normalized_name)
        seen_sources.add(str(path))
        selected.append(
            {
                "source_path": str(path),
                "staged_path": str(target),
                "score": int(item.get("score", 0) or 0),
                "size_bytes": int(item.get("size_bytes", 0) or 0),
            }
        )

    manifest = {
        "case_id": args.case_id,
        "limit": args.limit,
        "max_size_mb": args.max_size_mb,
        "selected_count": len(selected),
        "selected": selected,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Selected docs: {len(selected)}")
    print(f"Manifest: {manifest_path}")
    for item in selected:
        print(item["source_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
