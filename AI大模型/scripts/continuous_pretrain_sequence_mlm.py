#!/usr/bin/env python3
"""Train one continuous unlabeled MLM checkpoint across all input sequences."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from pretrain_sequence_mlm import AMINO_ACIDS, build_encoder, sha256


def build_epoch_plan(count: int, seed: int) -> list[int]:
    plan = list(range(count))
    random.Random(seed).shuffle(plan)
    return plan


def validate_learning_rate(value: float) -> float:
    if value <= 0:
        raise ValueError("learning_rate must be positive")
    return value


def parse_learning_rate(value: str) -> float:
    return validate_learning_rate(float(value))


def validate_hidden_dim(value: int) -> int:
    if value <= 0:
        raise ValueError("hidden_dim must be positive")
    return value


def parse_hidden_dim(value: str) -> int:
    return validate_hidden_dim(int(value))


def parse_kernel_size(value: str) -> int:
    kernel_size = int(value)
    if kernel_size <= 0 or kernel_size % 2 == 0:
        raise ValueError("kernel_size must be a positive odd integer")
    return kernel_size


def parse_residual(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError("residual must be true or false")
    return normalized == "true"


def apply_mask(ids, mask_id, mask_positions):
    masked = ids.clone()
    masked[mask_positions] = mask_id
    return masked, mask_positions


def load_fasta_records(path: Path) -> list[tuple[str, str]]:
    records = []
    header = ""
    current = []

    def append_record() -> None:
        sequence = "".join(current).upper().replace("-", "")
        if sequence and set(sequence) <= AMINO_ACIDS:
            source = next((part.split("=", 1)[1] for part in header.split("|") if part.startswith("source=")), header)
            records.append((source, sequence))

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header:
                append_record()
            header = line[1:]
            current = []
        else:
            current.append(line)
    if header:
        append_record()
    return records


def split_grouped_records(records: list[tuple[str, str]], validation_fraction: float, seed: int):
    if not 0.0 <= validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in [0, 1)")
    groups = {}
    for group, sequence in records:
        groups.setdefault(group, []).append((group, sequence))
    group_names = list(groups)
    random.Random(seed).shuffle(group_names)
    target = int(len(records) * validation_fraction)
    validation_groups = set()
    validation_count = 0
    for group in group_names[:-1]:
        if validation_count >= target:
            break
        validation_groups.add(group)
        validation_count += len(groups[group])
    train = [record for record in records if record[0] not in validation_groups]
    validation = [record for record in records if record[0] in validation_groups]
    return train, validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run continuous unlabeled masked amino acid pretraining")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--mask-probability", type=float, default=0.15)
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    parser.add_argument("--learning-rate", type=parse_learning_rate, default=1e-3)
    parser.add_argument("--hidden-dim", type=parse_hidden_dim, default=32)
    parser.add_argument("--kernel-size", type=parse_kernel_size, default=3)
    parser.add_argument("--residual", type=parse_residual, default=False)
    args = parser.parse_args()
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "artifact_kind": "continuous_unlabeled_pretraining_only", "safe_for_supervised_training": False, "safe_for_model_claim": False, "release_ready": False, "input": str(args.input.resolve()), "config": vars(args) | {"input": str(args.input.resolve()), "output": str(args.output.resolve())}}
    if not args.input.exists():
        report.update(status="blocked_missing_input", reason="fasta_input_not_found")
    else:
        records = load_fasta_records(args.input)
        sequences = [sequence for _, sequence in records]
        report.update(input_sha256=sha256(args.input), sequence_count=len(sequences))
        if not sequences:
            report.update(status="blocked_no_valid_sequences", reason="fasta_has_no_valid_protein_sequences")
        else:
            train_records, validation_records = split_grouped_records(records, args.validation_fraction, args.seed)
            train = [sequence for _, sequence in train_records]
            validation = [sequence for _, sequence in validation_records]
            train_sources = {source for source, _ in train_records}
            validation_sources = {source for source, _ in validation_records}
            import torch
            import torch.nn as nn
            random.seed(args.seed); torch.manual_seed(args.seed)
            vocab = sorted(AMINO_ACIDS) + ["<mask>", "<pad>"]
            token_to_id = {t: i for i, t in enumerate(vocab)}
            model = build_encoder(len(vocab), hidden_dim=args.hidden_dim, kernel_size=args.kernel_size, residual=args.residual); optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate); loss_fn = nn.CrossEntropyLoss()
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
            torch.save({"state_dict": model.state_dict(), "vocab": vocab, "config": {"epochs": args.epochs, "seed": args.seed, "mask_probability": args.mask_probability, "validation_fraction": args.validation_fraction, "learning_rate": args.learning_rate, "hidden_dim": args.hidden_dim, "kernel_size": args.kernel_size, "residual": args.residual}, "sequence_count": len(sequences)}, checkpoint)
            report.update(status="completed_pretraining_only", split_strategy="source_group_holdout", train_sequence_count=len(train), validation_sequence_count=len(validation), train_source_count=len(train_sources), validation_source_count=len(validation_sources), source_overlap_count=len(train_sources & validation_sources), epochs=args.epochs, steps=len(losses), final_loss=round(losses[-1], 6) if losses else None, validation_loss=round(sum(validation_losses)/len(validation_losses), 6) if validation_losses else None, checkpoint_path=str(checkpoint.resolve()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("status", "sequence_count", "steps", "validation_loss", "checkpoint_path")}, ensure_ascii=False))
    return 0 if report.get("status") == "completed_pretraining_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
