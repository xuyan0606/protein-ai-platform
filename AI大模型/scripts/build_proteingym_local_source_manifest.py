#!/usr/bin/env python3
"""Build local source manifest for the downloaded ProteinGym repository."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = AI_ROOT / "cache" / "external" / "ProteinGym"
FILES_OUT = AI_ROOT / "datasets" / "benchmark" / "proteingym_local_source_files.jsonl"
MANIFEST_OUT = AI_ROOT / "reports" / "proteingym_local_source_manifest.json"
REPORT_OUT = AI_ROOT / "reports" / "proteingym_local_source_report.json"


IMPORTANT_REL_PATHS = [
    "LICENSE",
    "README.md",
    "config.json",
    "reference_files/DMS_substitutions.csv",
    "reference_files/DMS_indels.csv",
    "reference_files/clinical_substitutions.csv",
    "reference_files/clinical_indels.csv",
    "reference_files/reference_files_description.md",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_lines(path: Path) -> int | None:
    if not path.is_file() or path.suffix.lower() not in {".csv", ".md", ".txt", ".json", ".py", ".sh"}:
        return None
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ProteinGym local source manifest")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--files-output", type=Path, default=FILES_OUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    files = []
    missing_important = []
    if args.source_root.exists():
        for path in sorted(item for item in args.source_root.rglob("*") if item.is_file()):
            rel = str(path.relative_to(AI_ROOT))
            files.append({
                "path": rel,
                "relative_to_source": str(path.relative_to(args.source_root)),
                "size_bytes": path.stat().st_size,
                "suffix": path.suffix.lower(),
                "sha256": sha256(path),
                "rows": count_lines(path),
            })
    for rel_path in IMPORTANT_REL_PATHS:
        if not (args.source_root / rel_path).exists():
            missing_important.append(rel_path)

    suffix_counts = Counter(row["suffix"] or "<none>" for row in files)
    benchmark_files = [row for row in files if row["relative_to_source"].startswith("benchmarks/")]
    reference_files = [row for row in files if row["relative_to_source"].startswith("reference_files/")]
    license_path = args.source_root / "LICENSE"
    license_text_head = ""
    if license_path.exists():
        license_text_head = "\n".join(license_path.read_text(encoding="utf-8", errors="replace").splitlines()[:3])

    manifest = {
        "manifest_id": "kwb_proteingym_local_source_manifest",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_name": "ProteinGym",
        "source_url": "https://github.com/OATML-Markslab/ProteinGym",
        "source_root": str(args.source_root.relative_to(AI_ROOT) if args.source_root.is_absolute() else args.source_root),
        "download_method": "github_codeload_zip_main_branch",
        "downloaded_to_local_cache": args.source_root.exists(),
        "license_path": "cache/external/ProteinGym/LICENSE",
        "license_text_head": license_text_head,
        "file_index": str(args.files_output.relative_to(AI_ROOT) if args.files_output.is_absolute() else args.files_output),
        "file_count": len(files),
        "benchmark_file_count": len(benchmark_files),
        "reference_file_count": len(reference_files),
        "missing_important_files": missing_important,
        "safe_for_model_claim": False,
        "policy": "Downloaded source/reference package only. It is not a KWB benchmark scorecard, training label source, or customer-delivery approval.",
    }
    report = {
        "created_at": manifest["created_at"],
        "local_only": True,
        "source_present": args.source_root.exists(),
        "source_root": manifest["source_root"],
        "file_count": len(files),
        "benchmark_file_count": len(benchmark_files),
        "reference_file_count": len(reference_files),
        "suffix_counts": dict(suffix_counts),
        "missing_important_files": missing_important,
        "ready_as_external_source_evidence": args.source_root.exists() and not missing_important,
        "ready_as_kwb_scorecard": False,
        "safe_for_model_claim": False,
        "manifest": str(args.manifest.relative_to(AI_ROOT) if args.manifest.is_absolute() else args.manifest),
        "file_index": manifest["file_index"],
        "policy": manifest["policy"],
    }
    write_jsonl(args.files_output, files)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_present": report["source_present"],
        "file_count": report["file_count"],
        "benchmark_file_count": report["benchmark_file_count"],
        "ready_as_external_source_evidence": report["ready_as_external_source_evidence"],
        "ready_as_kwb_scorecard": report["ready_as_kwb_scorecard"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["source_present"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
