#!/usr/bin/env python3
"""Evaluate unlabeled MLM reconstruction on a fixed, source-group holdout."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import torch
import torch.nn as nn

from continuous_pretrain_sequence_mlm import apply_mask, load_fasta_records, split_grouped_records
from pretrain_sequence_mlm import AMINO_ACIDS, build_encoder, sha256


def build_mask(length: int, probability: float, generator: torch.Generator) -> torch.Tensor:
    mask = torch.rand(length, generator=generator) < probability
    if not bool(mask.any()):
        mask[0] = True
    return mask


def uniform_amino_acid_loss() -> float:
    return math.log(len(AMINO_ACIDS))


def evaluate_model(model, validation_records, token_to_id, repeats: int, seed: int, mask_probability: float):
    loss_fn = nn.CrossEntropyLoss()
    losses = []
    accuracies = []
    masked_tokens = 0
    for repeat in range(repeats):
        generator = torch.Generator().manual_seed(seed + repeat)
        total_loss = total_correct = total_count = 0.0
        with torch.no_grad():
            for _, sequence in validation_records:
                ids = torch.tensor([token_to_id[x] for x in sequence], dtype=torch.long)
                mask = build_mask(len(ids), mask_probability, generator)
                masked, mask = apply_mask(ids, token_to_id["<mask>"], mask)
                logits = model(masked)[mask]
                targets = ids[mask]
                total_loss += float(loss_fn(logits, targets)) * int(mask.sum())
                total_correct += float((logits.argmax(dim=-1) == targets).sum())
                total_count += int(mask.sum())
        losses.append(total_loss / total_count if total_count else 0.0)
        accuracies.append(total_correct / total_count if total_count else 0.0)
        masked_tokens += int(total_count)
    mean_loss = sum(losses) / len(losses)
    return {"losses": losses, "mean_loss": mean_loss, "perplexity": math.exp(mean_loss), "masked_token_accuracy": sum(accuracies) / len(accuracies), "masked_token_count": masked_tokens}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a pretraining-only sequence MLM checkpoint")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--mask-probability", type=float, default=0.15)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    args = parser.parse_args()
    if not args.input.is_file() or not args.checkpoint.is_file():
        raise SystemExit("input and checkpoint are required")
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    vocab = checkpoint["vocab"]; token_to_id = {token: i for i, token in enumerate(vocab)}
    hidden_dim = int(checkpoint.get("config", {}).get("hidden_dim", 32))
    kernel_size = int(checkpoint.get("config", {}).get("kernel_size", 3))
    model = build_encoder(len(vocab), hidden_dim=hidden_dim, kernel_size=kernel_size); model.load_state_dict(checkpoint["state_dict"]); model.eval()
    records = load_fasta_records(args.input)
    _, validation_records = split_grouped_records(records, args.validation_fraction, args.seed)
    trained = evaluate_model(model, validation_records, token_to_id, args.repeats, args.seed, args.mask_probability)
    torch.manual_seed(args.seed)
    random_model = build_encoder(len(vocab), hidden_dim=hidden_dim, kernel_size=kernel_size).eval()
    random_baseline = evaluate_model(random_model, validation_records, token_to_id, args.repeats, args.seed, args.mask_probability)
    report = {"artifact_kind":"unlabeled_sequence_mlm_evaluation","status":"completed_evaluation_only","input_sha256":sha256(args.input),"checkpoint_sha256":sha256(args.checkpoint),"hidden_dim":hidden_dim,"kernel_size":kernel_size,"split_strategy":"source_group_holdout","validation_sequence_count":len(validation_records),"validation_source_count":len({s for s,_ in validation_records}),"source_overlap_count":0,"repeats":args.repeats,**trained,"random_initialization_baseline":random_baseline,"training_delta":{"loss_reduction":random_baseline["mean_loss"]-trained["mean_loss"],"accuracy_gain":trained["masked_token_accuracy"]-random_baseline["masked_token_accuracy"]},"uniform_amino_acid_baseline_loss":uniform_amino_acid_loss(),"safe_for_supervised_training":False,"safe_for_model_claim":False,"release_ready":False}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status":report["status"],"validation_sequences":report["validation_sequence_count"],"mean_loss":round(report["mean_loss"],6),"perplexity":round(report["perplexity"],6),"masked_token_accuracy":round(report["masked_token_accuracy"],6),"random_baseline_loss":round(random_baseline["mean_loss"],6),"random_baseline_accuracy":round(random_baseline["masked_token_accuracy"],6)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
