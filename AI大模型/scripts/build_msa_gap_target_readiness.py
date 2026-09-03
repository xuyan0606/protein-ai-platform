#!/usr/bin/env python3
"""Prepare real local FASTA inputs for feature-coverage MSA gaps."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

AI_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
GAPS = AI_ROOT / "datasets" / "features" / "feature_coverage_gap_queue.jsonl"
FASTA = AI_ROOT / "datasets" / "curation" / "msa_inputs" / "coverage_gap_targets.fasta"
REPORT = AI_ROOT / "reports" / "msa_gap_target_readiness_report.json"
EXECUTORS = ("mmseqs", "mafft", "clustalo", "hhblits", "jackhmmer", "foldseek")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def wrap(sequence: str, width: int = 80) -> str:
    return "\n".join(sequence[index:index + width] for index in range(0, len(sequence), width))


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare MSA gap targets")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--gaps", type=Path, default=GAPS)
    parser.add_argument("--fasta", type=Path, default=FASTA)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    ids = sorted({str(row.get("uniprot_id")) for row in load_jsonl(args.gaps) if row.get("uniprot_id")})
    sequences: dict[str, str] = {}
    if ids and args.db.exists():
        placeholders = ",".join("?" for _ in ids)
        with sqlite3.connect(args.db) as conn:
            sequences = {
                str(row[0]): str(row[1])
                for row in conn.execute(
                    f"SELECT uniprot_id, sequence FROM enzyme_records WHERE uniprot_id IN ({placeholders})",
                    ids,
                ).fetchall()
                if row[1]
            }
    missing = [uniprot_id for uniprot_id in ids if uniprot_id not in sequences]
    args.fasta.parent.mkdir(parents=True, exist_ok=True)
    args.fasta.write_text(
        "".join(f">{uniprot_id}\n{wrap(sequences[uniprot_id])}\n" for uniprot_id in ids if uniprot_id in sequences),
        encoding="utf-8",
    )
    available = {name: shutil.which(name) for name in EXECUTORS}
    available = {name: path for name, path in available.items() if path}
    report = {
        "local_only": True,
        "gap_target_count": len(ids),
        "sequence_ready_count": len(sequences),
        "missing_sequence_targets": missing,
        "fasta": str(args.fasta.relative_to(AI_ROOT)),
        "available_executors": available,
        "executor_status": "available" if available else "unavailable",
        "msa_generated": False,
        "conservation_generated": False,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "next_action": "run a trusted MSA/conservation workflow when an approved executor and database are available",
        "policy": "Real sequence preparation only; this report does not create MSA, conservation values, labels, or approvals.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
