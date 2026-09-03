#!/usr/bin/env python3
"""Build an evaluation-only strict-holdout candidate audit for Venus-15B.

The artifact is deliberately separate from the core strict supervised table.
It uses only real local wet-lab candidate rows and records sequence/PDB/source
receipts, but never writes training labels or changes model-claim gates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AI_ROOT / "Venus-15B淀粉酶项目"
SEQ_PATH = PROJECT_ROOT / "淀粉酶15B序列.txt"
PDB_PATH = PROJECT_ROOT / "15B-AAP-noCa.pdb"
BACKGROUND_PATH = PROJECT_ROOT / "淀粉酶背景.txt"
CANDIDATES = AI_ROOT / "datasets/feedback/wet_lab_mutant_library_feedback_candidates.jsonl"
SUMMARY = AI_ROOT / "酶改造突变体库-湿实验数据/15B_database-提高低pH条件下酶活及稳定性/01_突变体总体判断总表.csv"
OUT_DIR = AI_ROOT / "cache/advanced_features/benchmarks/kwb_venus15b_strict_holdout_candidate"
DATASET_OUT = OUT_DIR / "dataset.jsonl"
REPORT_OUT = AI_ROOT / "reports/kwb_venus15b_strict_holdout_candidate_audit_report.json"

MUTATION_RE = re.compile(r"^([A-Z])([0-9]+)([A-Z])$")
AA3 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def clean_sequence(path: Path) -> str:
    return "".join(ch for ch in path.read_text(encoding="utf-8") if ch.isalpha()).upper()


def pdb_chain_sequence(path: Path, chain: str = "A") -> dict[int, str]:
    residues: dict[int, str] = {}
    for line in path.read_text(errors="ignore").splitlines():
        if not line.startswith(("ATOM  ", "HETATM")) or line[21:22] != chain:
            continue
        try:
            residues[int(line[22:26])] = AA3.get(line[17:20].strip(), "X")
        except (ValueError, IndexError):
            continue
    return residues


def load_summary(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            variant = str(row.get("突变体") or "")
            if variant and "+" not in variant and MUTATION_RE.fullmatch(variant):
                # Prefer the strongest explicit project judgement when a variant
                # appears in several batches.
                previous = rows.get(variant)
                if previous is None or str(row.get("置信度等级") or "") > str(previous.get("置信度等级") or ""):
                    rows[variant] = row
    return rows


def candidate_label(judgement: str) -> str:
    if "正向" in judgement:
        return "go"
    if "负向" in judgement:
        return "watch"
    return "watch"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Venus-15B strict-holdout candidate audit")
    parser.add_argument("--output", type=Path, default=DATASET_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    sequence = clean_sequence(SEQ_PATH)
    pdb_residues = pdb_chain_sequence(PDB_PATH)
    candidates = load_jsonl(CANDIDATES)
    summary = load_summary(SUMMARY)

    selected = [
        row for row in candidates
        if row.get("source_project") == "15B"
        and row.get("numeric_training_candidate") is True
        and row.get("numbering_verified") is True
        and row.get("primary_analysis_recommended") is True
        and len(row.get("mutation_set") or []) == 1
    ]
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        by_variant[str(row["mutation_set"][0])].append(row)

    rows: list[dict[str, Any]] = []
    blockers = Counter()
    for variant, evidence_rows in sorted(by_variant.items()):
        match = MUTATION_RE.fullmatch(variant)
        if not match:
            blockers["invalid_mutation_syntax"] += 1
            continue
        wt, pos_text, mutant = match.groups()
        pos = int(pos_text)
        sequence_residue = sequence[pos - 1] if 1 <= pos <= len(sequence) else None
        pdb_residue = pdb_residues.get(pos)
        numbering_pass = sequence_residue == wt and pdb_residue == wt
        judgement = str((summary.get(variant) or {}).get("总体效应判断") or "")
        label = candidate_label(judgement)
        row_blockers = []
        if not numbering_pass:
            row_blockers.append("sequence_or_pdb_wild_type_mismatch")
        if not judgement:
            row_blockers.append("missing_project_summary_judgement")
        row_blockers.append("formal_review_and_strict_import_authorization_missing")
        blockers.update(row_blockers)
        rows.append({
            "benchmark_record_id": f"kwb_venus15b_strict_candidate::{variant}",
            "project_id": "15B",
            "variant": variant,
            "mutation": variant,
            "wild_type": wt,
            "canonical_position": pos,
            "mutant": mutant,
            "sequence_residue": sequence_residue,
            "pdb_chain": "A",
            "pdb_residue": pdb_residue,
            "numbering_verified_by_sequence": sequence_residue == wt,
            "numbering_verified_by_pdb": pdb_residue == wt,
            "numbering_cross_check_passed": numbering_pass,
            "candidate_label": label,
            "label_basis": "15B project overall judgement; candidate only",
            "project_overall_judgement": judgement,
            "measurement_evidence_rows": [
                {
                    "feedback_candidate_id": item.get("feedback_candidate_id"),
                    "measurement_id": item.get("measurement_id"),
                    "metric_code": item.get("metric_code"),
                    "raw_value_numeric": item.get("raw_value_numeric"),
                    "vs_control_ratio": item.get("vs_control_ratio"),
                    "source_file": item.get("source_file"),
                    "source_row_index": item.get("source_row_index"),
                }
                for item in evidence_rows
            ],
            "source_receipts": {
                "candidate_jsonl": {
                    "path": str(CANDIDATES.relative_to(AI_ROOT)),
                    "sha256": sha256(CANDIDATES),
                },
                "project_summary_csv": {
                    "path": str(SUMMARY.relative_to(AI_ROOT)),
                    "sha256": sha256(SUMMARY),
                },
                "parent_sequence": {"path": str(SEQ_PATH.relative_to(AI_ROOT)), "sha256": sha256(SEQ_PATH)},
                "structure": {"path": str(PDB_PATH.relative_to(AI_ROOT)), "sha256": sha256(PDB_PATH)},
                "background": {"path": str(BACKGROUND_PATH.relative_to(AI_ROOT)), "sha256": sha256(BACKGROUND_PATH)},
            },
            "blockers": row_blockers,
            "strict_holdout_eligible_now": False,
            "training_import_eligible_now": False,
            "safe_for_model_claim": False,
            "policy": "Real local wet-lab evidence candidate. This artifact never updates the core strict table or training labels.",
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "project_id": "15B",
        "parent_sequence_length": len(sequence),
        "pdb_chain_a_residue_count": len(pdb_residues),
        "sequence_pdb_exact_match": len(sequence) == len(pdb_residues) and all(pdb_residues.get(i) == sequence[i - 1] for i in range(1, len(sequence) + 1)),
        "selected_numeric_candidate_rows": len(selected),
        "candidate_variant_rows": len(rows),
        "candidate_variants": [row["variant"] for row in rows],
        "strict_holdout_rows_written": 0,
        "training_import_written_rows": 0,
        "formal_reviewed_decision_rows": 0,
        "strict_candidate_artifact": str(args.output.relative_to(AI_ROOT)),
        "blocker_counts": dict(blockers),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "The Venus-15B sequence/PDB cross-check is complete, but formal data authorization and strict supervised import remain separate gates.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_variant_rows": len(rows), "strict_holdout_rows_written": 0, "sequence_pdb_exact_match": report["sequence_pdb_exact_match"], "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
