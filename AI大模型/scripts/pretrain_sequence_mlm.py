#!/usr/bin/env python3
"""Self-supervised masked-amino-acid pretraining entrypoint.

This path consumes unlabeled FASTA only. Its artifacts are pretraining artifacts,
not supervised mutation labels and not evidence for model-quality claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = AI_ROOT / "datasets" / "curation" / "msa_inputs" / "msa_targets.fasta"
DEFAULT_OUT = AI_ROOT / "reports" / "sequence_mlm_pretraining_run.json"
AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")


def build_encoder(vocab_size: int):
    import torch
    import torch.nn as nn

    class SequenceEncoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, 32)
            self.position = nn.Embedding(512, 32)
            self.context = nn.Conv1d(32, 32, kernel_size=3, padding=1)
            self.output = nn.Linear(32, vocab_size)

        def forward(self, ids):
            positions = torch.arange(ids.shape[0], device=ids.device).clamp(max=511)
            hidden = self.embedding(ids) + self.position(positions)
            hidden = self.context(hidden.transpose(0, 1).unsqueeze(0)).squeeze(0).transpose(0, 1)
            return self.output(hidden)

        def encode(self, ids):
            positions = torch.arange(ids.shape[0], device=ids.device).clamp(max=511)
            hidden = self.embedding(ids) + self.position(positions)
            hidden = self.context(hidden.transpose(0, 1).unsqueeze(0)).squeeze(0).transpose(0, 1)
            return hidden.mean(dim=0)

    return SequenceEncoder()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_fasta(path: Path, limit: int) -> list[str]:
    sequences: list[str] = []
    current: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current:
                sequences.append("".join(current).upper().replace("-", ""))
                current = []
            continue
        current.append(line)
    if current:
        sequences.append("".join(current).upper().replace("-", ""))
    valid = [sequence for sequence in sequences if sequence and set(sequence) <= AMINO_ACIDS]
    return valid[:limit]


def split_sequences(sequences: list[str], validation_fraction: float, seed: int) -> tuple[list[str], list[str]]:
    if not 0.0 <= validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in [0, 1)")
    indices = list(range(len(sequences)))
    random.Random(seed).shuffle(indices)
    validation_count = min(len(sequences) - 1, max(0, int(len(sequences) * validation_fraction)))
    validation = [sequences[index] for index in indices[:validation_count]]
    train = [sequences[index] for index in indices[validation_count:]]
    return train, validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run self-supervised masked amino acid pretraining")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-sequences", type=int, default=256)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--mask-probability", type=float, default=0.15)
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    args = parser.parse_args()

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task": "masked_amino_acid_self_supervised_pretraining",
        "artifact_kind": "pretraining_only",
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "input": str(args.input.resolve()),
        "config": {
            "max_sequences": args.max_sequences,
            "seed": args.seed,
            "epochs": args.epochs,
            "mask_probability": args.mask_probability,
            "validation_fraction": args.validation_fraction,
        },
    }

    if not args.input.exists():
        report.update(status="blocked_missing_input", reason="fasta_input_not_found", sequence_count=0)
    else:
        report["input_sha256"] = sha256(args.input)
        sequences = load_fasta(args.input, args.max_sequences)
        report["sequence_count"] = len(sequences)
        report["sequence_lengths"] = {
            "min": min(map(len, sequences), default=0),
            "max": max(map(len, sequences), default=0),
        }
        if not sequences:
            report.update(status="blocked_no_valid_sequences", reason="fasta_has_no_valid_protein_sequences")
        else:
            train_sequences, validation_sequences = split_sequences(sequences, args.validation_fraction, args.seed)
            report["train_sequence_count"] = len(train_sequences)
            report["validation_sequence_count"] = len(validation_sequences)
            try:
                import torch  # type: ignore
                import torch.nn as nn  # type: ignore
            except ImportError as exc:
                report.update(
                    status="blocked_missing_runtime",
                    reason="torch_required_for_masked_amino_acid_training",
                    missing_dependency=str(exc),
                )
            else:
                random.seed(args.seed)
                torch.manual_seed(args.seed)
                vocab = sorted(AMINO_ACIDS) + ["<mask>", "<pad>"]
                token_to_id = {token: index for index, token in enumerate(vocab)}
                model = build_encoder(len(vocab))
                optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
                loss_fn = nn.CrossEntropyLoss()
                losses: list[float] = []
                def masked_loss(sequence: str) -> object:
                    ids = torch.tensor([token_to_id[token] for token in sequence], dtype=torch.long)
                    mask = torch.rand(len(ids)) < args.mask_probability
                    if not bool(mask.any()):
                        mask[0] = True
                    masked = ids.clone()
                    masked[mask] = token_to_id["<mask>"]
                    logits = model(masked)
                    return loss_fn(logits[mask], ids[mask])

                for _ in range(args.epochs):
                    for sequence in train_sequences:
                        if len(sequence) < 2:
                            continue
                        loss = masked_loss(sequence)
                        optimizer.zero_grad()
                        loss.backward()
                        optimizer.step()
                        losses.append(float(loss.detach()))
                model.eval()
                validation_losses = []
                with torch.no_grad():
                    for sequence in validation_sequences:
                        if len(sequence) >= 2:
                            validation_losses.append(float(masked_loss(sequence)))
                report.update(
                    status="completed_pretraining_only",
                    steps=len(losses),
                    final_loss=round(losses[-1], 6) if losses else None,
                    validation_loss=round(sum(validation_losses) / len(validation_losses), 6) if validation_losses else None,
                    checkpoint_path=str((args.output.parent / f"{args.output.stem}.checkpoint.pt").resolve()),
                    torch_version=torch.__version__,
                )
                args.output.parent.mkdir(parents=True, exist_ok=True)
                torch.save({"state_dict": model.state_dict(), "vocab": vocab, "config": report["config"]}, report["checkpoint_path"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report.get(k) for k in ("status", "reason", "sequence_count", "steps", "final_loss", "output")}, ensure_ascii=False))
    return 0 if report["status"] == "completed_pretraining_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
