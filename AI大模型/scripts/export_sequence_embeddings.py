#!/usr/bin/env python3
"""Export mean sequence embeddings from a self-supervised checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import torch

from pretrain_sequence_mlm import build_encoder, load_fasta, sha256


def main() -> int:
    parser = argparse.ArgumentParser(description="Export unlabeled protein sequence embeddings")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-sequences", type=int, default=256)
    args = parser.parse_args()

    if not args.input.exists() or not args.checkpoint.exists():
        raise SystemExit("input FASTA and checkpoint are required")
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    vocab = checkpoint["vocab"]
    token_to_id = {token: index for index, token in enumerate(vocab)}
    hidden_dim = int(checkpoint.get("config", {}).get("hidden_dim", 32))
    kernel_size = int(checkpoint.get("config", {}).get("kernel_size", 3))
    model = build_encoder(len(vocab), hidden_dim=hidden_dim, kernel_size=kernel_size)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    sequences = load_fasta(args.input, args.max_sequences)
    records = []
    for index, sequence in enumerate(sequences):
        ids = torch.tensor([token_to_id[token] for token in sequence], dtype=torch.long)
        with torch.no_grad():
            vector = model.encode(ids).tolist()
        records.append({"sequence_index": index, "length": len(sequence), "embedding": [round(float(x), 8) for x in vector]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact_kind": "unlabeled_sequence_embedding",
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
        "input": str(args.input.resolve()),
        "input_sha256": sha256(args.input),
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "embedding_dimension": hidden_dim,
        "records": records,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed_embedding_export", "records": len(records), "dimension": payload["embedding_dimension"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
