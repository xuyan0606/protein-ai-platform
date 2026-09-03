#!/usr/bin/env python3
"""Audit whether structure-chain candidate differences are explained by PDB evidence."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from build_structure_chain_autoreview_candidates import DB, atom_sequence, load_sequences


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "curation" / "structure_chain_autoreview_candidates.jsonl"
WORKLIST = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_worklist.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "structure_chain_evidence_audit.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_chain_evidence_audit_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


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


def parse_missing_residues(path: Path, chain_id: str) -> dict[int, str]:
    evidence: dict[int, str] = {}
    pattern = re.compile(r"^REMARK 465\s+([A-Z]{3})\s+(\S)\s+(-?\d+)")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if not match or match.group(2) != chain_id:
            continue
        pos = int(match.group(3))
        if pos > 0:
            evidence[pos] = line.strip()
    return evidence


def position_differences(observed: str, reference: str) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    common = min(len(observed), len(reference))
    for idx in range(common):
        if observed[idx] != reference[idx]:
            differences.append({
                "kind": "substitution_or_construct_difference",
                "position": idx + 1,
                "observed": observed[idx],
                "reference": reference[idx],
            })
    if len(reference) > len(observed):
        for idx in range(len(observed), len(reference)):
            differences.append({
                "kind": "missing_residue",
                "position": idx + 1,
                "observed": "",
                "reference": reference[idx],
            })
    elif len(observed) > len(reference):
        for idx in range(len(reference), len(observed)):
            differences.append({
                "kind": "extra_observed_residue",
                "position": idx + 1,
                "observed": observed[idx],
                "reference": "",
            })
    return differences


def audit_candidate(row: dict[str, Any], worklist_by_id: dict[str, dict[str, Any]], sequences: dict[str, str]) -> dict[str, Any]:
    structure_id = str(row.get("structure_id") or "").upper()
    chain_id = str(row.get("selected_chain_id") or "")
    worklist_row = worklist_by_id.get(structure_id) or {}
    path = Path(str(worklist_row.get("actual_cache_path") or ""))
    reference = sequences.get(str(worklist_row.get("uniprot_id") or ""), "")
    observed = atom_sequence(path, chain_id) if path.exists() and chain_id else ""
    seqadv = parse_seqadv(path, chain_id) if path.exists() and chain_id else {}
    missing = parse_missing_residues(path, chain_id) if path.exists() and chain_id else {}
    differences = position_differences(observed, reference) if observed and reference else []

    explained = []
    unexplained = []
    for diff in differences:
        pos = int(diff["position"])
        if diff["kind"] == "missing_residue" and pos in missing:
            explained.append({**diff, "evidence": missing[pos]})
        elif diff["kind"] == "substitution_or_construct_difference" and pos in seqadv:
            explained.append({**diff, "evidence": seqadv[pos]})
        else:
            unexplained.append(diff)

    strict_auto_promotable = (
        row.get("candidate_bucket") in {"exact_sequence_match_candidate", "construct_or_mutant_candidate"}
        and bool(observed)
        and bool(reference)
        and not unexplained
        and len(differences) <= 5
        and path.exists()
        and worklist_row.get("chain_count") == 1
    )
    status = "strict_pdb_evidence_explained" if strict_auto_promotable else "requires_manual_review"
    return {
        "structure_id": structure_id,
        "canonical_uniprot_id": worklist_row.get("uniprot_id"),
        "selected_chain_id": chain_id,
        "candidate_bucket": row.get("candidate_bucket"),
        "audit_status": status,
        "strict_auto_promotable_for_chain_mapping": strict_auto_promotable,
        "observed_sequence_length": len(observed),
        "reference_sequence_length": len(reference),
        "difference_rows": len(differences),
        "explained_difference_rows": len(explained),
        "unexplained_difference_rows": len(unexplained),
        "seqadv_positions": sorted(seqadv),
        "missing_residue_positions": sorted(missing),
        "explained_differences": explained[:20],
        "unexplained_differences": unexplained[:20],
        "source_refs": row.get("source_refs") or [],
        "policy": "Audit only. A strict candidate still needs an explicit reviewed decision row before apply.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure chain evidence audit")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    worklist_by_id = {str(row.get("structure_id") or "").upper(): row for row in load_jsonl(args.worklist)}
    sequences = load_sequences(args.db)
    rows = [audit_candidate(row, worklist_by_id, sequences) for row in candidates]
    write_jsonl(args.output, rows)

    status_counts = Counter(row["audit_status"] for row in rows)
    promotable = [row for row in rows if row["strict_auto_promotable_for_chain_mapping"]]
    report = {
        "candidate_rows": len(candidates),
        "audit_rows": len(rows),
        "status_counts": dict(status_counts),
        "strict_auto_promotable_rows": len(promotable),
        "strict_auto_promotable_structure_ids": [row["structure_id"] for row in promotable],
        "output": str(args.output),
        "policy": "Strict auto-promotable means PDB evidence explains chain differences; it does not unlock mutation numbering, wet-lab labels, ddG, benchmark, production, or model-quality claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": len(rows),
        "strict_auto_promotable_rows": len(promotable),
        "strict_auto_promotable_structure_ids": report["strict_auto_promotable_structure_ids"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
