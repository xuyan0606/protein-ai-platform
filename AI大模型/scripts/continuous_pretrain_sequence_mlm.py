#!/usr/bin/env python3
"""Train one continuous unlabeled MLM checkpoint across all input sequences."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from pretrain_sequence_mlm import AMINO_ACIDS, build_encoder, load_fasta, sha256, split_sequences


def build_epoch_plan(count: int, seed: int) -> list[int]:
    plan = list(range(count))
    random.Random(seed).shuffle(plan)
    return plan


def apply_mask(ids, mask_id, mask_positions):
    masked = ids.clone()
    masked[mask_positions] = mask_id
    return masked, mask_positions


def main() -> int:
    parser = argparse.ArgumentParser(description="Run continuous unlabeled masked amino acid pretraining")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--mask-probability", type=float, default=0.15)
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    args = parser.parse_args()
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "artifact_kind": "continuous_unlabeled_pretraining_only", "safe_for_supervised_training": False, "safe_for_model_claim": False, "release_ready": False, "input": str(args.input.resolve()), "config": vars(args) | {"input": str(args.input.resolve()), "output": str(args.output.resolve())}}
    if not args.input.exists():
        report.update(status="blocked_missing_input", reason="fasta_input_not_found")
    else:
        sequences = load_fasta(args.input, 10**9)
        report.update(input_sha256=sha256(args.input), sequence_count=len(sequences))
        if not sequences:
            report.update(status="blocked_no_valid_sequences", reason="fasta_has_no_valid_protein_sequences")
        else:
            train, validation = split_sequences(sequences, args.validation_fraction, args.seed)
            import torch
            import torch.nn as nn
            random.seed(args.seed); torch.manual_seed(args.seed)
            vocab = sorted(AMINO_ACIDS) + ["<mask>", "<pad>"]
            token_to_id = {t: i for i, t in enumerate(vocab)}
            model = build_encoder(len(vocab)); optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3); loss_fn = nn.CrossEntropyLoss()
            losses = []
            def step(sequence: str) -> float:
                ids = torch.tensor([token_to_id[x] for x in sequence], dtype=torch.long)
                mask = torch.rand(len(ids)) < args.mask_probability
                if not bool(mask.any()): mask[0] = True
                masked, mask = apply_mask(ids, token_to_id["<mask>"], mask)
                loss = loss_fn(model(masked)[mask], ids[mask]); optimizer.zero_grad(); loss.backward(); optimizer.step(); return float(loss.detach())
            for epoch in range(args.epochs):
                for index in build_epoch_plan(len(train), args.seed + epoch):
                    if len(train[index]) >= 2: losses.append(step(train[index]))
            model.eval(); validation_losses = []
            with torch.no_grad():
                for sequence in validation:
                    if len(sequence) >= 2:
                        ids = torch.tensor([token_to_id[x] for x in sequence], dtype=torch.long); mask = torch.rand(len(ids)) < args.mask_probability
                        if not bool(mask.any()): mask[0] = True
                        masked, mask = apply_mask(ids, token_to_id["<mask>"], mask)
                        validation_losses.append(float(loss_fn(model(masked)[mask], ids[mask])))
            checkpoint = args.output.parent / f"{args.output.stem}.checkpoint.pt"; args.output.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"state_dict": model.state_dict(), "vocab": vocab, "config": {"epochs": args.epochs, "seed": args.seed, "mask_probability": args.mask_probability, "validation_fraction": args.validation_fraction}, "sequence_count": len(sequences)}, checkpoint)
            report.update(status="completed_pretraining_only", train_sequence_count=len(train), validation_sequence_count=len(validation), epochs=args.epochs, steps=len(losses), final_loss=round(losses[-1], 6) if losses else None, validation_loss=round(sum(validation_losses)/len(validation_losses), 6) if validation_losses else None, checkpoint_path=str(checkpoint.resolve()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("status", "sequence_count", "steps", "validation_loss", "checkpoint_path")}, ensure_ascii=False))
    return 0 if report.get("status") == "completed_pretraining_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
