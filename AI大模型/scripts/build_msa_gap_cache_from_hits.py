#!/usr/bin/env python3
"""Build isolated MSA/conservation artifacts for coverage-gap targets."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE = AI_ROOT / "scripts" / "build_msa_conservation_from_mmseqs_hits.py"
SPEC = importlib.util.spec_from_file_location("msa_builder", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build isolated MSA gap cache")
    parser.add_argument("--fasta", type=Path, default=AI_ROOT / "datasets/curation/msa_inputs/coverage_gap_targets.fasta")
    parser.add_argument("--hits", type=Path, default=AI_ROOT / "cache/msa/coverage_gap_hits.m8")
    parser.add_argument("--msa-root", type=Path, default=AI_ROOT / "cache/msa/coverage_gap")
    parser.add_argument("--conservation-root", type=Path, default=AI_ROOT / "datasets/curation/msa_conservation_gap")
    parser.add_argument("--intake", type=Path, default=AI_ROOT / "datasets/curation/msa_gap_trusted_cache_intake.local.jsonl")
    parser.add_argument("--report", type=Path, default=AI_ROOT / "reports/msa_gap_cache_build_report.json")
    parser.add_argument("--max-hits", type=int, default=128)
    args = parser.parse_args()

    sequences = MODULE.parse_fasta(args.fasta)
    hits_by_query = MODULE.load_hits(args.hits)
    intake = []
    missing = []
    for uniprot_id in sorted(sequences):
        hits = hits_by_query.get(uniprot_id, [])
        if not hits:
            missing.append(uniprot_id)
            continue
        intake.append(MODULE.build_cache_for_target(
            uniprot_id, sequences[uniprot_id], hits, args.max_hits,
            args.msa_root, args.conservation_root,
            "UniProtKB/Swiss-Prot", "UniProtKB/Swiss-Prot Release 2026_02 of 10-Jun-2026",
        ))
    args.intake.parent.mkdir(parents=True, exist_ok=True)
    args.intake.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in intake), encoding="utf-8")
    report = {
        "local_only": True,
        "target_rows": len(sequences),
        "targets_with_hits": len(intake),
        "targets_missing_hits": missing,
        "raw_hit_rows": sum(len(rows) for rows in hits_by_query.values()),
        "max_hits_per_target": args.max_hits,
        "intake": str(args.intake.relative_to(AI_ROOT)),
        "msa_root": str(args.msa_root.relative_to(AI_ROOT)),
        "conservation_root": str(args.conservation_root.relative_to(AI_ROOT)),
        "ready_for_manual_intake_review": len(intake) == len(sequences) and bool(sequences),
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Isolated real MMseqs2 Swiss-Prot alignment stack; final trusted-cache validator and human review remain authoritative.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
