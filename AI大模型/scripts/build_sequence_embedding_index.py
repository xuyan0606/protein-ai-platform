#!/usr/bin/env python3
"""Build a provenance-preserving embedding index from a directory of FASTA files."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import torch

from pretrain_sequence_mlm import build_encoder, load_fasta, sha256


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an unlabeled sequence embedding index")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-sequences-per-file", type=int, default=129)
    args = parser.parse_args()
    if not args.input_dir.is_dir() or not args.checkpoint.exists():
        raise SystemExit("input directory and checkpoint are required")

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    vocab = checkpoint["vocab"]
    token_to_id = {token: index for index, token in enumerate(vocab)}
    hidden_dim = int(checkpoint.get("config", {}).get("hidden_dim", 32))
    kernel_size = int(checkpoint.get("config", {}).get("kernel_size", 3))
    model = build_encoder(len(vocab), hidden_dim=hidden_dim, kernel_size=kernel_size)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    files = sorted(args.input_dir.glob("*.fasta"))
    records = []
    for path in files:
        source_hash = sha256(path)
        for sequence_index, sequence in enumerate(load_fasta(path, args.max_sequences_per_file)):
            ids = torch.tensor([token_to_id[token] for token in sequence], dtype=torch.long)
            with torch.no_grad():
                vector = model.encode(ids).tolist()
            records.append({
                "source_file": str(path.resolve()),
                "source_sha256": source_hash,
                "sequence_index": sequence_index,
                "length": len(sequence),
                "embedding": [round(float(x), 8) for x in vector],
            })
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact_kind": "unlabeled_sequence_embedding_index",
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
        "input_dir": str(args.input_dir.resolve()),
        "file_count": len(files),
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "embedding_dimension": hidden_dim,
        "record_count": len(records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed_embedding_index", "file_count": len(files), "record_count": len(records), "dimension": payload["embedding_dimension"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
