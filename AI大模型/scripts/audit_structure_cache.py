#!/usr/bin/env python3
"""Audit local structure cache readiness for coordinate-level features."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
REPORT_OUT = AI_ROOT / "reports" / "structure_cache_audit_report.json"


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def candidate_paths(raw_path: str, extra_roots: list[Path]) -> list[Path]:
    path = Path(raw_path)
    if path.is_absolute():
        candidates = [path]
    else:
        candidates = [
            PROJECT_ROOT / path,
            PROJECT_ROOT / "backend" / path,
            PROJECT_ROOT / "deploy_data" / path,
            AI_ROOT / path,
            AI_ROOT / "cache" / "structures" / path,
        ]
        candidates.extend(root / path for root in extra_roots)
    expanded = []
    for candidate in candidates:
        expanded.append(candidate)
        if candidate.suffix.lower() == ".pdb":
            expanded.append(candidate.with_suffix(".cif"))
        elif candidate.suffix.lower() == ".cif":
            expanded.append(candidate.with_suffix(".pdb"))
    seen = []
    for candidate in expanded:
        if candidate not in seen:
            seen.append(candidate)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local PDB/mmCIF structure cache")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=REPORT_OUT)
    parser.add_argument("--sample-size", type=int, default=2000)
    parser.add_argument("--extra-root", type=Path, action="append", default=[])
    args = parser.parse_args()

    with connect_ro(args.db) as conn:
        totals = {
            "pdb_structures": conn.execute("SELECT COUNT(*) FROM pdb_structures").fetchone()[0],
            "pdb_paths": conn.execute(
                "SELECT COUNT(*) FROM pdb_structures WHERE pdb_file_path IS NOT NULL AND pdb_file_path != ''"
            ).fetchone()[0],
            "alphafold_structures": conn.execute("SELECT COUNT(*) FROM alphafold_structures").fetchone()[0],
            "alphafold_cif_paths": conn.execute(
                "SELECT COUNT(*) FROM alphafold_structures WHERE cif_path IS NOT NULL AND cif_path != ''"
            ).fetchone()[0],
        }
        pdb_rows = conn.execute(
            """
            SELECT pdb_id, pdb_file_path
            FROM pdb_structures
            WHERE pdb_file_path IS NOT NULL AND pdb_file_path != ''
            LIMIT ?
            """,
            (args.sample_size,),
        ).fetchall()
        af_rows = conn.execute(
            """
            SELECT e.uniprot_id, af.cif_path
            FROM alphafold_structures af
            JOIN enzyme_records e ON e.id = af.enzyme_id
            WHERE af.cif_path IS NOT NULL AND af.cif_path != ''
            LIMIT ?
            """,
            (args.sample_size,),
        ).fetchall()

    samples: list[dict[str, Any]] = []
    existing_count = 0
    suffix_counts = Counter()
    root_hits = Counter()
    for row in pdb_rows:
        raw = row["pdb_file_path"]
        suffix_counts[Path(raw).suffix.lower() or "no_suffix"] += 1
        candidates = candidate_paths(raw, args.extra_root)
        existing = [path for path in candidates if path.exists()]
        if existing:
            existing_count += 1
            root_hits[str(existing[0].parent)] += 1
        if len(samples) < 20:
            samples.append({
                "type": "pdb",
                "id": row["pdb_id"],
                "raw_path": raw,
                "exists": bool(existing),
                "first_candidate": str(candidates[0]),
            })

    af_existing_count = 0
    for row in af_rows:
        raw = row["cif_path"]
        suffix_counts[Path(raw).suffix.lower() or "no_suffix"] += 1
        candidates = candidate_paths(raw, args.extra_root)
        existing = [path for path in candidates if path.exists()]
        if existing:
            af_existing_count += 1
            root_hits[str(existing[0].parent)] += 1
        if len(samples) < 40:
            samples.append({
                "type": "alphafold",
                "id": row["uniprot_id"],
                "raw_path": raw,
                "exists": bool(existing),
                "first_candidate": str(candidates[0]),
            })

    report = {
        "project_root": str(PROJECT_ROOT),
        "totals": totals,
        "sample_size": args.sample_size,
        "pdb_sample_existing": existing_count,
        "alphafold_sample_existing": af_existing_count,
        "suffix_counts_sample": dict(suffix_counts),
        "root_hits_sample": dict(root_hits),
        "samples": samples,
        "coordinate_features_ready": existing_count > 0 or af_existing_count > 0,
        "next_steps": [
            "materialize PDB/mmCIF files into one of the candidate roots",
            "store absolute structure cache root in local-only config",
            "verify chain mapping before coordinate-level feature extraction",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "pdb_sample_existing": existing_count,
        "alphafold_sample_existing": af_existing_count,
        "coordinate_features_ready": report["coordinate_features_ready"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
