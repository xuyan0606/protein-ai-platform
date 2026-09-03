#!/usr/bin/env python3
"""Build an inventory for the Stage 25 local source-drop directory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "datasets" / "governance" / "stage25_source_drop_manifest_20260806.jsonl"
ROOT = AI_ROOT / "datasets" / "source_drops" / "stage25"
OUT = AI_ROOT / "reports" / "stage25_source_drop_inventory_20260806.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise SystemExit(f"{path} contains a non-object row")
        rows.append(row)
    return rows


def main() -> int:
    manifest_rows = load_jsonl(MANIFEST)
    expected_rows = []
    for row in manifest_rows:
        rel = row.get("expected_local_path")
        path = AI_ROOT / str(rel)
        exists = path.exists() and path.is_file()
        expected_rows.append({
            "source_id": row.get("source_id"),
            "pmid": row.get("pmid"),
            "doi": row.get("doi"),
            "required_file_kind": row.get("required_file_kind"),
            "expected_local_path": rel,
            "exists": exists,
            "size_bytes": path.stat().st_size if exists else None,
            "sha256": sha256(path) if exists else None,
        })

    pmids = sorted({str(row.get("pmid")) for row in manifest_rows})
    directory_rows = []
    for pmid in pmids:
        path = ROOT / pmid
        directory_rows.append({
            "pmid": pmid,
            "path": str(path.relative_to(AI_ROOT)),
            "exists": path.exists() and path.is_dir(),
            "file_count": sum(1 for child in path.iterdir() if child.is_file()) if path.exists() and path.is_dir() else 0,
        })

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_source_drop_inventory",
        "stage": 25,
        "source_drop_root": str(ROOT.relative_to(AI_ROOT)),
        "manifest_source_rows": len(manifest_rows),
        "unique_expected_file_path_rows": len({str(row.get("expected_local_path")) for row in expected_rows}),
        "duplicate_expected_file_paths": sorted({
            str(row.get("expected_local_path"))
            for row in expected_rows
            if sum(1 for item in expected_rows if item.get("expected_local_path") == row.get("expected_local_path")) > 1
        }),
        "inventory_generated_from_manifest": True,
        "directory_rows": len(directory_rows),
        "existing_directory_rows": sum(1 for row in directory_rows if row["exists"]),
        "expected_file_rows": len(expected_rows),
        "present_expected_file_rows": sum(1 for row in expected_rows if row["exists"]),
        "missing_expected_file_rows": sum(1 for row in expected_rows if not row["exists"]),
        "ready_for_extraction_rows": 0,
        "ready_for_sqlite_apply_rows": 0,
        "directory_inventory": directory_rows,
        "expected_files": expected_rows,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Directory inventory only. File presence and hashes do not approve source locators, formal decisions, SQLite apply, benchmark intake, model claims, customer delivery, or release.",
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "existing_directory_rows": report["existing_directory_rows"],
        "present_expected_file_rows": report["present_expected_file_rows"],
        "missing_expected_file_rows": report["missing_expected_file_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
