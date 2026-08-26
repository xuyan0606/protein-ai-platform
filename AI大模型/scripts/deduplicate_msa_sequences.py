#!/usr/bin/env python3
"""Build a provenance-preserving deduplicated FASTA from MSA FASTA files."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pretrain_sequence_mlm import load_fasta, sha256


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate unlabeled MSA sequences")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-fasta", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--max-sequences-per-file", type=int, default=129)
    args = parser.parse_args()
    seen: dict[str, dict] = {}
    total = 0
    files = sorted(args.input_dir.glob("*.fasta"))
    for path in files:
        for sequence_index, sequence in enumerate(load_fasta(path, args.max_sequences_per_file)):
            total += 1
            key = hashlib.sha256(sequence.encode()).hexdigest()
            seen.setdefault(key, {"sequence": sequence, "source_file": str(path.resolve()), "source_sha256": sha256(path), "sequence_index": sequence_index})
    args.output_fasta.parent.mkdir(parents=True, exist_ok=True)
    with args.output_fasta.open("w", encoding="utf-8") as handle:
        for index, item in enumerate(seen.values()):
            handle.write(f">dedup_{index}|source={Path(item['source_file']).name}|source_index={item['sequence_index']}\n")
            sequence = item["sequence"]
            for start in range(0, len(sequence), 80):
                handle.write(sequence[start:start + 80] + "\n")
    report = {
        "artifact_kind": "unlabeled_msa_deduplicated_fasta",
        "input_dir": str(args.input_dir.resolve()),
        "file_count": len(files),
        "input_sequence_count": total,
        "unique_sequence_count": len(seen),
        "duplicate_sequence_count": total - len(seen),
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
        "output_fasta": str(args.output_fasta.resolve()),
        "output_fasta_sha256": sha256(args.output_fasta),
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("file_count", "input_sequence_count", "unique_sequence_count", "duplicate_sequence_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
