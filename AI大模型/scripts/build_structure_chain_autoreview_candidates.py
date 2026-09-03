#!/usr/bin/env python3
"""Build conservative auto-review candidates for structure chain mapping."""

from __future__ import annotations

import argparse
import difflib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DB = AI_ROOT.parent / "backend" / "protein_ai.db"
WORKLIST = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_worklist.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "structure_chain_autoreview_candidates.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_chain_autoreview_candidate_report.json"


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "SEC": "U", "PYL": "O",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def load_sequences(db_path: Path) -> dict[str, str]:
    if not db_path.exists():
        return {}
    with sqlite3.connect(db_path) as conn:
        return {str(row[0]): str(row[1]) for row in conn.execute("SELECT uniprot_id, sequence FROM enzyme_records")}


def pdb_atom_sequence(path: Path, chain_id: str) -> str:
    sequence: list[str] = []
    seen: set[tuple[str, str]] = set()
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("ATOM  "):
                continue
            if (line[21:22].strip() or "_") != chain_id:
                continue
            if line[12:16].strip() != "CA":
                continue
            residue_key = (line[22:26].strip(), line[26:27].strip())
            if residue_key in seen:
                continue
            seen.add(residue_key)
            sequence.append(AA3_TO_1.get(line[17:20].strip().upper(), "X"))
    return "".join(sequence)


def cif_atom_sequence(path: Path, chain_id: str) -> str:
    sequence: list[str] = []
    seen: set[str] = set()
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("ATOM"):
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            atom_name = parts[3]
            residue_name = parts[5]
            chain = parts[6] or "_"
            seq_id = parts[8]
            if chain != chain_id or atom_name != "CA" or seq_id in seen:
                continue
            seen.add(seq_id)
            sequence.append(AA3_TO_1.get(residue_name.upper(), "X"))
    return "".join(sequence)


def atom_sequence(path: Path, chain_id: str) -> str:
    if path.suffix.lower() == ".pdb":
        return pdb_atom_sequence(path, chain_id)
    if path.suffix.lower() == ".cif":
        return cif_atom_sequence(path, chain_id)
    return ""


def header_evidence(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[:260]
    text = "\n".join(lines).upper()
    titles = " ".join(line[10:].strip() for line in lines if line.startswith("TITLE"))
    flags = [token for token in ("ENGINEERED", "MUTATION", "MUTANT", "SEQADV") if token in text]
    return {"header_flags": flags, "title": titles[:240]}


def mismatch_count(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left, right)) + abs(len(left) - len(right))


def classify(atom_seq: str, db_seq: str, flags: list[str]) -> tuple[str, str]:
    if not atom_seq or not db_seq:
        return "blocked_missing_sequence", "keep_unreviewed"
    direct_mismatch = mismatch_count(atom_seq, db_seq)
    identity = difflib.SequenceMatcher(None, atom_seq, db_seq).ratio()
    if atom_seq == db_seq:
        return "exact_sequence_match_candidate", "set_chain_mapping"
    if identity >= 0.97 and flags:
        return "construct_or_mutant_candidate", "set_chain_mapping"
    if identity >= 0.95:
        return "manual_alignment_candidate", "keep_unreviewed"
    if direct_mismatch <= 3 and flags:
        return "construct_or_mutant_candidate", "set_chain_mapping"
    return "blocked_low_sequence_agreement", "keep_unreviewed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure chain auto-review candidates")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    sequences = load_sequences(args.db)
    rows = load_jsonl(args.worklist)
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if row.get("chain_count") != 1 or not row.get("parsed_chain_ids"):
            continue
        path = Path(str(row.get("actual_cache_path") or ""))
        if not path.exists():
            continue
        chain_id = str(row["parsed_chain_ids"][0])
        observed = atom_sequence(path, chain_id)
        reference = sequences.get(str(row.get("uniprot_id") or ""), "")
        evidence = header_evidence(path)
        bucket, suggested_decision = classify(observed, reference, evidence["header_flags"])
        identity = difflib.SequenceMatcher(None, observed, reference).ratio() if observed and reference else 0.0
        if bucket.startswith("blocked"):
            continue
        candidates.append({
            "structure_id": row.get("structure_id"),
            "canonical_uniprot_id": row.get("uniprot_id"),
            "selected_chain_id": chain_id,
            "candidate_bucket": bucket,
            "suggested_decision": suggested_decision,
            "suggested_sequence_to_structure_mapping_status": (
                "exact_sequence_match" if bucket == "exact_sequence_match_candidate"
                else "reviewed_with_construct_or_tags" if bucket == "construct_or_mutant_candidate"
                else "manual_alignment_reviewed"
            ),
            "suggested_residue_numbering_basis": "pdb_author_numbering",
            "sequence_identity_ratio": round(identity, 6),
            "atom_sequence_length": len(observed),
            "reference_sequence_length": len(reference),
            "direct_mismatch_count": mismatch_count(observed, reference) if observed and reference else None,
            "header_flags": evidence["header_flags"],
            "title": evidence["title"],
            "source_refs": [f"PDB:{row.get('structure_id')}", f"UniProt:{row.get('uniprot_id')}", f"PDB_CHAIN:{chain_id}"],
            "confidence": 0.99 if bucket == "exact_sequence_match_candidate" else 0.93 if bucket == "construct_or_mutant_candidate" else 0.75,
            "review_required_before_apply": True,
            "policy": "candidate only; not appended to structure_chain_mapping_decisions.jsonl automatically",
        })
    candidates.sort(key=lambda item: (item["candidate_bucket"], -item["sequence_identity_ratio"], item["structure_id"]))
    write_jsonl(args.output, candidates)
    counts = Counter(item["candidate_bucket"] for item in candidates)
    report = {
        "input_rows": len(rows),
        "candidate_rows": len(candidates),
        "bucket_counts": dict(counts),
        "exact_sequence_match_candidates": counts.get("exact_sequence_match_candidate", 0),
        "construct_or_mutant_candidates": counts.get("construct_or_mutant_candidate", 0),
        "manual_alignment_candidates": counts.get("manual_alignment_candidate", 0),
        "output": str(args.output),
        "policy": "auto-review candidates require human acceptance before they become reviewed chain mapping decisions",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_rows": len(candidates), "bucket_counts": dict(counts), "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
