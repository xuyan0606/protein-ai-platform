#!/usr/bin/env python3
"""Build a local review worklist for structure chain mapping.

This produces candidate structure-to-UniProt mapping rows only. It does not
decide chain mappings and must not unlock structure-dependent conclusions.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DB = AI_ROOT.parent / "backend" / "protein_ai.db"
STRUCTURES = AI_ROOT / "datasets" / "curation" / "structure_coordinate_features.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_worklist.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_chain_mapping_worklist_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def parse_json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def load_pdb_mappings(db_path: Path, pdb_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not db_path.exists() or not pdb_ids:
        return {}
    placeholders = ",".join("?" for _ in pdb_ids)
    sql = f"""
        SELECT
            p.pdb_id,
            p.method,
            p.resolution,
            p.chain_ids,
            e.uniprot_id,
            e.seq_length,
            e.protein_name,
            e.is_reviewed
        FROM pdb_structures p
        JOIN enzyme_records e ON e.id = p.enzyme_id
        WHERE UPPER(p.pdb_id) IN ({placeholders})
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, sorted(pdb_ids)).fetchall()
    mappings = {}
    for row in rows:
        mappings[str(row["pdb_id"]).upper()] = {
            "pdb_id": row["pdb_id"],
            "method": row["method"],
            "resolution": row["resolution"],
            "db_chain_ids": parse_json_list(row["chain_ids"]),
            "uniprot_id": row["uniprot_id"],
            "seq_length": row["seq_length"],
            "protein_name": row["protein_name"],
            "is_reviewed_uniprot": bool(row["is_reviewed"]),
        }
    return mappings


def review_bucket(row: dict[str, Any]) -> str:
    if not row["db_mapping_found"]:
        return "missing_db_mapping"
    if row["chain_count"] > 1:
        return "multi_chain_needs_selection"
    if not row["db_chain_ids"]:
        return "missing_db_chain_ids"
    if row["ca_atoms_close_to_sequence_length"]:
        return "single_chain_ca_length_close"
    return "single_chain_ca_length_mismatch"


def resolution_sort_key(value: Any) -> float:
    try:
        resolution = float(value)
    except (TypeError, ValueError):
        return 99.0
    return resolution if resolution > 0 else 99.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure chain mapping review worklist")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--structures", type=Path, default=STRUCTURES)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    structures = load_jsonl(args.structures)
    pdb_ids = {str(row.get("structure_id")).upper() for row in structures if row.get("structure_id")}
    db_by_pdb = load_pdb_mappings(args.db, pdb_ids)

    worklist = []
    for row in structures:
        structure_id = str(row.get("structure_id") or "").upper()
        db_row = db_by_pdb.get(structure_id, {})
        seq_length = db_row.get("seq_length") or 0
        ca_atoms = row.get("ca_atoms") or 0
        tolerance = max(5, int(seq_length * 0.05)) if seq_length else 0
        ca_close = bool(seq_length and abs(ca_atoms - seq_length) <= tolerance)
        item = {
            "structure_id": structure_id,
            "source": row.get("source"),
            "actual_format": row.get("actual_format"),
            "actual_cache_path": row.get("actual_cache_path"),
            "sha256": row.get("sha256"),
            "db_mapping_found": bool(db_row),
            "uniprot_id": db_row.get("uniprot_id"),
            "protein_name": db_row.get("protein_name"),
            "is_reviewed_uniprot": db_row.get("is_reviewed_uniprot"),
            "seq_length": seq_length,
            "method": db_row.get("method"),
            "resolution": db_row.get("resolution"),
            "db_chain_ids": db_row.get("db_chain_ids") or [],
            "parsed_chain_ids": sorted((row.get("residue_count_by_chain") or {}).keys()),
            "chain_count": row.get("chain_count") or 0,
            "ca_atoms": ca_atoms,
            "residue_count_total": row.get("residue_count_total"),
            "residue_count_by_chain": row.get("residue_count_by_chain") or {},
            "ca_atoms_close_to_sequence_length": ca_close,
            "length_delta_ca_minus_sequence": (ca_atoms - seq_length) if seq_length else None,
            "review_bucket": "",
            "review_priority_notes": [],
            "required_review_checks": [
                "confirm biological chain for this UniProt accession",
                "confirm sequence-to-structure residue numbering and missing residue ranges",
                "confirm insertion codes, engineered tags, ligands, and hetero residues before using distances",
                "write reviewed chain mapping only after source confirmation",
            ],
            "policy": "candidate only; not_a_chain_mapping_decision; not_structure_conclusion_ready",
        }
        item["review_bucket"] = review_bucket(item)
        if item["is_reviewed_uniprot"]:
            item["review_priority_notes"].append("reviewed_uniprot")
        if item["ca_atoms_close_to_sequence_length"]:
            item["review_priority_notes"].append("length_close")
        if item["method"] == "X-RAY DIFFRACTION":
            item["review_priority_notes"].append("xray")
        worklist.append(item)

    bucket_order = {
        "single_chain_ca_length_close": 0,
        "multi_chain_needs_selection": 1,
        "single_chain_ca_length_mismatch": 2,
        "missing_db_chain_ids": 3,
        "missing_db_mapping": 4,
    }
    worklist.sort(
        key=lambda item: (
            bucket_order.get(item["review_bucket"], 9),
            0 if item.get("is_reviewed_uniprot") else 1,
            abs(item["length_delta_ca_minus_sequence"]) if item.get("length_delta_ca_minus_sequence") is not None else 999,
            resolution_sort_key(item.get("resolution")),
            item.get("chain_count") or 0,
            item.get("uniprot_id") or "",
            item["structure_id"],
        )
    )
    for index, item in enumerate(worklist, start=1):
        item["review_rank"] = index

    write_jsonl(args.output, worklist)
    bucket_counts = Counter(item["review_bucket"] for item in worklist)
    report = {
        "input_structure_rows": len(structures),
        "worklist_rows": len(worklist),
        "db_mapping_rows": sum(1 for item in worklist if item["db_mapping_found"]),
        "unique_uniprot_ids": len({item.get("uniprot_id") for item in worklist if item.get("uniprot_id")}),
        "bucket_counts": dict(bucket_counts),
        "single_chain_close_candidates": bucket_counts.get("single_chain_ca_length_close", 0),
        "multi_chain_needs_selection": bucket_counts.get("multi_chain_needs_selection", 0),
        "missing_db_mapping": bucket_counts.get("missing_db_mapping", 0),
        "output": str(args.output),
        "policy": "worklist is not a reviewed chain mapping and cannot unlock structure conclusions",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "worklist_rows": report["worklist_rows"],
        "bucket_counts": report["bucket_counts"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
