#!/usr/bin/env python3
"""Prepare deterministic batches for resumable unlabeled sequence pretraining."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pretrain_sequence_mlm import load_fasta, sha256


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare resumable sequence pretraining batches")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=512)
    args = parser.parse_args()
    if args.batch_size < 1:
        raise SystemExit("batch-size must be >= 1")
    sequences = load_fasta(args.input, 10**9)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    batches = []
    for batch_index, start in enumerate(range(0, len(sequences), args.batch_size)):
        batch = sequences[start:start + args.batch_size]
        path = args.output_dir / f"batch_{batch_index:04d}.fasta"
        with path.open("w", encoding="utf-8") as handle:
            for item_index, sequence in enumerate(batch):
                handle.write(f">batch={batch_index}|sequence={start + item_index}\n{sequence}\n")
        batches.append({
            "batch_index": batch_index,
            "path": str(path.resolve()),
            "sequence_count": len(batch),
            "sha256": sha256(path),
        })
    manifest = {
        "artifact_kind": "unlabeled_sequence_pretraining_batch_manifest",
        "input": str(args.input.resolve()),
        "input_sha256": sha256(args.input),
        "sequence_count": len(sequences),
        "batch_size": args.batch_size,
        "batch_count": len(batches),
        "batches": batches,
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed_batch_manifest", "sequence_count": len(sequences), "batch_count": len(batches), "manifest": str(manifest_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
