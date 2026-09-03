#!/usr/bin/env python3
"""Build an expected local structure cache manifest without downloading files."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
OUTPUT = AI_ROOT / "reports" / "structure_cache_expected_manifest.json"


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def candidate_paths(path_text: str) -> list[Path]:
    path = Path(path_text)
    candidates = [path] if path.is_absolute() else [
        PROJECT_ROOT / path,
        PROJECT_ROOT / "backend" / path,
        PROJECT_ROOT / "deploy_data" / path,
        AI_ROOT / path,
        AI_ROOT / "cache" / "structures" / path,
    ]
    expanded = []
    for candidate in candidates:
        expanded.append(candidate)
        if candidate.suffix.lower() == ".pdb":
            expanded.append(candidate.with_suffix(".cif"))
        elif candidate.suffix.lower() == ".cif":
            expanded.append(candidate.with_suffix(".pdb"))
    return expanded


def status_for(path_text: str) -> str:
    return "present" if any(path.exists() for path in candidate_paths(path_text)) else "missing"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build expected structure cache manifest")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    with connect_ro(args.db) as conn:
        pdb_rows = conn.execute(
            """
            SELECT pdb_id, pdb_file_path
            FROM pdb_structures
            WHERE pdb_file_path IS NOT NULL AND pdb_file_path != ''
            ORDER BY pdb_id
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
        af_rows = conn.execute(
            """
            SELECT e.uniprot_id, af.cif_path
            FROM alphafold_structures af
            JOIN enzyme_records e ON e.id = af.enzyme_id
            WHERE af.cif_path IS NOT NULL AND af.cif_path != ''
            ORDER BY e.uniprot_id
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()

    entries: list[dict[str, Any]] = []
    for row in pdb_rows:
        raw_path = row["pdb_file_path"]
        entries.append({
            "structure_id": row["pdb_id"],
            "source": "pdb",
            "expected_path": raw_path,
            "sha256": None,
            "status": status_for(raw_path),
            "chain_mapping_required": True,
        })
    for row in af_rows:
        raw_path = row["cif_path"]
        entries.append({
            "structure_id": row["uniprot_id"],
            "source": "alphafold",
            "expected_path": raw_path,
            "sha256": None,
            "status": status_for(raw_path),
            "chain_mapping_required": True,
        })
    manifest = {
        "local_only": True,
        "cache_roots": [
            {
                "name": "project_root",
                "path": str(PROJECT_ROOT),
                "read_only": True,
            },
            {
                "name": "local_structure_cache",
                "path": str(AI_ROOT / "cache" / "structures"),
                "read_only": False,
            }
        ],
        "entries": entries,
        "summary": {
            "entries": len(entries),
            "present": sum(1 for row in entries if row["status"] == "present"),
            "missing": sum(1 for row in entries if row["status"] == "missing"),
            "note": "This manifest is an expected local cache plan; it does not download files.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
