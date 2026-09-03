#!/usr/bin/env python3
"""Audit DBREF-backed structure-chain mappings.

This handles fragment and multi-chain structures where the source database
already identifies one target chain. A row is promotable only when the selected
chain has a PDB DBREF entry to the same UniProt accession and the observed CA
sequence matches the DBREF UniProt interval, allowing only substitutions that
are explicitly listed in PDB SEQADV.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from build_structure_chain_autoreview_candidates import DB, atom_sequence, load_sequences


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_worklist.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_decisions.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "structure_chain_dbref_evidence_audit.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_chain_dbref_evidence_audit_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def parse_dbrefs(path: Path, chain_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("DBREF "):
            continue
        parts = line.split()
        if len(parts) < 10 or parts[2] != chain_id or parts[5] != "UNP":
            continue
        try:
            rows.append({
                "pdb_start": int(parts[3]),
                "pdb_end": int(parts[4]),
                "uniprot_id": parts[6],
                "uniprot_start": int(parts[8]),
                "uniprot_end": int(parts[9]),
                "source_ref": line.strip(),
            })
        except ValueError:
            continue
    return rows


def parse_seqadv(path: Path, chain_id: str) -> dict[int, str]:
    evidence: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("SEQADV"):
            continue
        chain = line[16:17].strip() or "_"
        if chain != chain_id:
            continue
        try:
            pos = int(line[18:22])
        except ValueError:
            continue
        if pos > 0:
            evidence[pos] = line.strip()
    return evidence


def sequence_differences(observed: str, reference: str, uniprot_start: int) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    common = min(len(observed), len(reference))
    for idx in range(common):
        if observed[idx] != reference[idx]:
            differences.append({
                "kind": "substitution_or_construct_difference",
                "position": uniprot_start + idx,
                "observed": observed[idx],
                "reference": reference[idx],
            })
    if len(reference) > len(observed):
        for idx in range(len(observed), len(reference)):
            differences.append({
                "kind": "missing_residue_within_dbref_interval",
                "position": uniprot_start + idx,
                "observed": "",
                "reference": reference[idx],
            })
    elif len(observed) > len(reference):
        for idx in range(len(reference), len(observed)):
            differences.append({
                "kind": "extra_observed_residue_outside_dbref_interval",
                "position": uniprot_start + idx,
                "observed": observed[idx],
                "reference": "",
            })
    return differences


def missing_ranges_for_dbref(start: int, end: int, sequence_length: int) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    if start > 1:
        ranges.append({
            "start_pos": 1,
            "end_pos": start - 1,
            "basis": "PDB_DBREF_UNIPROT_SUBRANGE_EXCLUDED",
        })
    if sequence_length and end < sequence_length:
        ranges.append({
            "start_pos": end + 1,
            "end_pos": sequence_length,
            "basis": "PDB_DBREF_UNIPROT_SUBRANGE_EXCLUDED",
        })
    return ranges


def audit_row(row: dict[str, Any], sequences: dict[str, str], decided_ids: set[str]) -> dict[str, Any]:
    structure_id = str(row.get("structure_id") or "").upper()
    chain_ids = row.get("db_chain_ids") or []
    parsed_chain_ids = row.get("parsed_chain_ids") or []
    selected_chain = str(chain_ids[0]) if len(chain_ids) == 1 else ""
    path = Path(str(row.get("actual_cache_path") or ""))
    reference = sequences.get(str(row.get("uniprot_id") or ""), "")
    dbrefs = parse_dbrefs(path, selected_chain) if path.exists() and selected_chain else []
    matching_dbrefs = [item for item in dbrefs if item["uniprot_id"] == row.get("uniprot_id")]
    observed = atom_sequence(path, selected_chain) if path.exists() and selected_chain in parsed_chain_ids else ""
    seqadv = parse_seqadv(path, selected_chain) if path.exists() and selected_chain else {}

    dbref = matching_dbrefs[0] if matching_dbrefs else None
    differences: list[dict[str, Any]] = []
    explained: list[dict[str, Any]] = []
    unexplained: list[dict[str, Any]] = []
    reference_segment = ""
    if dbref and reference:
        reference_segment = reference[dbref["uniprot_start"] - 1: dbref["uniprot_end"]]
        differences = sequence_differences(observed, reference_segment, dbref["uniprot_start"])
        for diff in differences:
            pos = int(diff["position"])
            if diff["kind"] == "substitution_or_construct_difference" and pos in seqadv:
                explained.append({**diff, "evidence": seqadv[pos]})
            else:
                unexplained.append(diff)

    strict_promotable = (
        structure_id not in decided_ids
        and len(chain_ids) == 1
        and selected_chain in parsed_chain_ids
        and bool(dbref)
        and bool(observed)
        and bool(reference_segment)
        and len(observed) == len(reference_segment)
        and len(differences) <= 6
        and not unexplained
        and bool(row.get("is_reviewed_uniprot"))
    )
    status = "strict_dbref_interval_explained" if strict_promotable else "requires_manual_review"
    return {
        "structure_id": structure_id,
        "canonical_uniprot_id": row.get("uniprot_id"),
        "selected_chain_id": selected_chain or None,
        "audit_status": status,
        "strict_auto_promotable_for_chain_mapping": strict_promotable,
        "already_decided": structure_id in decided_ids,
        "chain_count": row.get("chain_count"),
        "db_chain_ids": chain_ids,
        "parsed_chain_ids": parsed_chain_ids,
        "dbref": dbref,
        "observed_sequence_length": len(observed),
        "reference_segment_length": len(reference_segment),
        "canonical_sequence_length": len(reference),
        "difference_rows": len(differences),
        "explained_difference_rows": len(explained),
        "unexplained_difference_rows": len(unexplained),
        "explained_differences": explained[:20],
        "unexplained_differences": unexplained[:20],
        "missing_residue_ranges": (
            missing_ranges_for_dbref(dbref["uniprot_start"], dbref["uniprot_end"], len(reference))
            if dbref else []
        ),
        "source_refs": [
            f"PDB:{structure_id}",
            f"UniProt:{row.get('uniprot_id')}",
            f"PDB_CHAIN:{selected_chain}",
            f"PDB_DBREF:{dbref['source_ref']}" if dbref else "PDB_DBREF:missing",
        ],
        "policy": "DBREF audit only. A strict candidate still needs an explicit reviewed decision row before apply.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build DBREF evidence audit for structure chain mappings")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.worklist)
    decided_ids = {str(row.get("structure_id") or "").upper() for row in load_jsonl(args.decisions)}
    sequences = load_sequences(args.db)
    audited = [audit_row(row, sequences, decided_ids) for row in rows]
    write_jsonl(args.output, audited)

    status_counts = Counter(row["audit_status"] for row in audited)
    promotable = [row for row in audited if row["strict_auto_promotable_for_chain_mapping"]]
    report = {
        "worklist_rows": len(rows),
        "audit_rows": len(audited),
        "status_counts": dict(status_counts),
        "strict_auto_promotable_rows": len(promotable),
        "strict_auto_promotable_structure_ids": [row["structure_id"] for row in promotable],
        "output": str(args.output),
        "policy": "Strict DBREF interval promotable means the selected chain is backed by a same-UniProt DBREF interval and sequence differences are fully explained; it does not unlock mutation numbering, wet-lab labels, ddG, benchmark, production, or model-quality claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": len(audited),
        "strict_auto_promotable_rows": len(promotable),
        "strict_auto_promotable_structure_ids": report["strict_auto_promotable_structure_ids"][:40],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
