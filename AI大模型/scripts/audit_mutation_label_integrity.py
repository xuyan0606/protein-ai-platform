#!/usr/bin/env python3
"""Audit mutation label integrity before supervised model training."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_enriched.jsonl"
AUDITED_OUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_audited.jsonl"
VERIFIED_OUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_verified.jsonl"
WEAK_OUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_weak_evidence.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "mutation_label_integrity_report.json"


MUTATION_RE = re.compile(r"^([A-Z])([0-9]{1,6})([A-Z])$")


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def load_sequences(conn: sqlite3.Connection, uniprot_ids: list[str]) -> dict[str, str]:
    if not uniprot_ids:
        return {}
    placeholders = ",".join("?" for _ in uniprot_ids)
    rows = conn.execute(
        f"SELECT uniprot_id, sequence FROM enzyme_records WHERE uniprot_id IN ({placeholders})",
        uniprot_ids,
    ).fetchall()
    return {row["uniprot_id"]: row["sequence"] for row in rows}


def load_stability_metadata(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          id,
          literature_ref,
          source_db,
          method,
          ddg,
          dtm,
          ph,
          temperature_c
        FROM stability_records
        """
    ).fetchall()
    return {
        f"stability:{row['id']}": dict(row)
        for row in rows
    }


def table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def count_domain_rows(conn: sqlite3.Connection) -> tuple[int, int]:
    total = table_count(conn, "domain_architecture")
    invalid = int(
        conn.execute(
            "SELECT COUNT(*) FROM domain_architecture WHERE start_pos <= 0 OR end_pos <= 0 OR end_pos < start_pos"
        ).fetchone()[0]
    )
    return total, invalid


def count_pdb_paths(conn: sqlite3.Connection) -> tuple[int, int]:
    paths = [
        row[0]
        for row in conn.execute(
            "SELECT pdb_file_path FROM pdb_structures WHERE pdb_file_path IS NOT NULL AND pdb_file_path != ''"
        ).fetchall()
    ]
    existing = 0
    for value in paths:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.exists():
            existing += 1
    return len(paths), existing


def audit_row(row: dict[str, Any], sequences: dict[str, str], stability_metadata: dict[str, dict[str, Any]]) -> dict[str, Any]:
    flags: list[str] = []
    mutation = str(row.get("mutation") or "").upper()
    match = MUTATION_RE.match(mutation)
    parsed_wt = parsed_mut = None
    parsed_pos = None
    if not match:
        flags.append("invalid_mutation_code")
    else:
        parsed_wt, parsed_pos_text, parsed_mut = match.groups()
        parsed_pos = int(parsed_pos_text)
        if row.get("wild_type") and str(row["wild_type"]).upper() != parsed_wt:
            flags.append("wild_type_disagrees_with_mutation_code")
        if row.get("mutant") and str(row["mutant"]).upper() != parsed_mut:
            flags.append("mutant_disagrees_with_mutation_code")
        if row.get("mutation_position") and int(row["mutation_position"]) != parsed_pos:
            flags.append("position_disagrees_with_mutation_code")

    sequence = sequences.get(row.get("uniprot_id") or "")
    if not sequence:
        flags.append("missing_current_sequence")
    elif parsed_pos is None or parsed_pos < 1 or parsed_pos > len(sequence):
        flags.append("position_out_of_current_sequence_range")
    else:
        current_wt = sequence[parsed_pos - 1].upper()
        if parsed_wt != current_wt:
            flags.append("wild_type_mismatch_current_sequence")

    verified = not flags
    output = dict(row)
    metadata = stability_metadata.get(str(row.get("record_id"))) or {}
    output.update({
        "numbering_verified_by_sequence": verified,
        "integrity_flags": flags,
        "current_sequence_residue": (
            sequence[parsed_pos - 1].upper()
            if sequence and parsed_pos is not None and 1 <= parsed_pos <= len(sequence)
            else None
        ),
        "literature_ref": metadata.get("literature_ref"),
        "label_method": metadata.get("method"),
        "curation_status": "verified_supervised_label" if verified else "weak_evidence_needs_numbering_curation",
        "usable_as_supervised_label": verified,
        "usable_as_weak_evidence": not verified,
    })
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit mutation label sequence integrity")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--audited-output", type=Path, default=AUDITED_OUT)
    parser.add_argument("--verified-output", type=Path, default=VERIFIED_OUT)
    parser.add_argument("--weak-output", type=Path, default=WEAK_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    uniprot_ids = sorted({row.get("uniprot_id") for row in rows if row.get("uniprot_id")})
    with connect_ro(args.db) as conn:
        sequences = load_sequences(conn, uniprot_ids)
        stability_metadata = load_stability_metadata(conn)
        domain_total, domain_invalid = count_domain_rows(conn)
        pdb_paths_total, pdb_paths_existing = count_pdb_paths(conn)

    audited = [audit_row(row, sequences, stability_metadata) for row in rows]
    verified = [row for row in audited if row["numbering_verified_by_sequence"]]
    weak = [row for row in audited if not row["numbering_verified_by_sequence"]]
    flag_counts = Counter(flag for row in audited for flag in row["integrity_flags"])
    label_distribution_verified = Counter(row["label_decision"] for row in verified)

    write_jsonl(args.audited_output, audited)
    write_jsonl(args.verified_output, verified)
    write_jsonl(args.weak_output, weak)
    report = {
        "rows": len(audited),
        "verified_rows": len(verified),
        "weak_evidence_rows": len(weak),
        "verified_ratio": round(len(verified) / len(audited), 4) if audited else 0,
        "verified_groups": len({row.get("group_key") for row in verified}),
        "label_distribution_verified": dict(label_distribution_verified),
        "integrity_flag_counts": dict(flag_counts),
        "domain_architecture": {
            "rows": domain_total,
            "invalid_interval_rows": domain_invalid,
            "usable_for_position_features": domain_total > 0 and domain_invalid < domain_total,
        },
        "pdb_paths": {
            "rows_with_paths": pdb_paths_total,
            "existing_local_files": pdb_paths_existing,
            "usable_for_coordinate_features": pdb_paths_existing > 0,
        },
        "audited_output": str(args.audited_output),
        "verified_output": str(args.verified_output),
        "weak_output": str(args.weak_output),
        "decision": "blocked_for_supervised_claim" if len(verified) < 100 else "usable_for_small_experiment",
        "next_steps": [
            "build UniProt isoform/version mapping for stability labels",
            "repair or re-import domain architecture start/end coordinates",
            "materialize local PDB/mmCIF files or connect read-only structure cache",
            "treat unverified labels as weak evidence, not supervised labels",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows": report["rows"],
        "verified_rows": report["verified_rows"],
        "verified_ratio": report["verified_ratio"],
        "decision": report["decision"],
        "verified_output": str(args.verified_output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
