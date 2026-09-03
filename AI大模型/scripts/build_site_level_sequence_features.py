#!/usr/bin/env python3
"""Build site-level sequence-window features for verified mutation labels."""

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
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_verified.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_site_sequence_features.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "site_sequence_feature_report.json"

HYDROPHOBIC = set("AILMFWYV")
POLAR = set("STNQYC")
CHARGED = set("DEKRH")
POSITIVE = set("KRH")
NEGATIVE = set("DE")
SPECIAL = set("GP")
AROMATIC = set("FYW")
AA_GROUPS = {
    "hydrophobic": HYDROPHOBIC,
    "polar": POLAR,
    "charged": CHARGED,
    "positive": POSITIVE,
    "negative": NEGATIVE,
    "special": SPECIAL,
    "aromatic": AROMATIC,
}


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


def aa_group(aa: str) -> str:
    for group, members in AA_GROUPS.items():
        if aa in members:
            return group
    return "other"


def window(sequence: str, pos: int, radius: int) -> str:
    start = max(1, pos - radius)
    end = min(len(sequence), pos + radius)
    return sequence[start - 1:end].upper()


def composition_features(seq_window: str, prefix: str) -> dict[str, float | int]:
    length = len(seq_window)
    counts = Counter(seq_window)
    output: dict[str, float | int] = {f"{prefix}_length": length}
    for name, members in AA_GROUPS.items():
        count = sum(counts[aa] for aa in members)
        output[f"{prefix}_{name}_count"] = count
        output[f"{prefix}_{name}_fraction"] = round(count / length, 6) if length else 0.0
    output[f"{prefix}_glycine_count"] = counts["G"]
    output[f"{prefix}_proline_count"] = counts["P"]
    output[f"{prefix}_cysteine_count"] = counts["C"]
    return output


def substitution_features(wt: str, mutant: str) -> dict[str, bool | str]:
    wt_group = aa_group(wt)
    mutant_group = aa_group(mutant)
    return {
        "wt_group": wt_group,
        "mutant_group": mutant_group,
        "same_biochemical_group": wt_group == mutant_group,
        "hydrophobicity_class_change": (wt in HYDROPHOBIC) != (mutant in HYDROPHOBIC),
        "charge_class_change": (wt in CHARGED) != (mutant in CHARGED),
        "aromatic_class_change": (wt in AROMATIC) != (mutant in AROMATIC),
        "special_residue_change": (wt in SPECIAL) != (mutant in SPECIAL),
    }


def enrich(row: dict[str, Any], sequence: str) -> dict[str, Any]:
    output = dict(row)
    pos = int(row["mutation_position"])
    wt = str(row["wild_type"]).upper()
    mutant = str(row["mutant"]).upper()
    for radius in (5, 10):
        seq_window = window(sequence, pos, radius)
        output.update(composition_features(seq_window, f"window_{radius}"))
    output.update(substitution_features(wt, mutant))
    output.update({
        "distance_to_n_terminus": pos - 1,
        "distance_to_c_terminus": len(sequence) - pos,
        "near_n_terminus_20": pos <= 20,
        "near_c_terminus_20": len(sequence) - pos < 20,
        "site_level_feature_scope": "sequence_window_verified_numbering",
    })
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build verified site-level sequence features")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    uniprot_ids = sorted({row.get("uniprot_id") for row in rows if row.get("uniprot_id")})
    with connect_ro(args.db) as conn:
        sequences = load_sequences(conn, uniprot_ids)
    enriched = [
        enrich(row, sequences[row["uniprot_id"]])
        for row in rows
        if row.get("uniprot_id") in sequences and row.get("numbering_verified_by_sequence")
    ]
    write_jsonl(args.output, enriched)
    report = {
        "rows": len(enriched),
        "groups": len({row.get("group_key") for row in enriched}),
        "label_distribution": dict(Counter(row["label_decision"] for row in enriched)),
        "output": str(args.output),
        "scope": "verified labels only; unverified numbering excluded",
        "modeling_note": "too few rows for model-quality claims; intended to validate site-level feature generation",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(enriched), "groups": report["groups"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
