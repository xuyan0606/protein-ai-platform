#!/usr/bin/env python3
"""Research-only masked multi-task trainer for KWB-EnzymeDesigner.

The smoke mode proves the code path only. The research mode enforces per-head
sample, replicate, and independent-group thresholds. Neither mode creates a
production-eligible or model-claim-eligible artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTIVITY_RISK = AI_ROOT / "datasets" / "training" / "activity_risk_training_import_labels.jsonl"
DEFAULT_OUTPUT = AI_ROOT / "reports" / "research_multitask_training_run.json"
EXPECTED_HEADS = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)
DEFAULT_MINIMUM_SAMPLES = 100
DEFAULT_MINIMUM_GROUPS = 10
DEFAULT_MINIMUM_REPLICATES = 3
LABEL_OR_NEAR_LABEL_FEATURE_FIELDS = frozenset(
    {
        "activity_relative_to_wt",
        "activity_risk_label",
        "label_value",
        "label_decision",
        "label_ddg",
        "label_stability_delta_tm_c",
        "substrate_fit_label",
        "assay_success",
    }
)
DEFAULT_FEATURE_SCHEMA = (
    "canonical_position_scaled",
    "ph_scaled",
    "enzyme_identity_hash",
    "wt_aa_hash",
    "mutant_aa_hash",
    "metric_or_assay_hash",
)


def stable_fraction(value: Any) -> float:
    digest = hashlib.sha256(str(value or "").encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / float(2**32 - 1)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def row_group(row: dict[str, Any]) -> str:
    explicit_group = row.get("group_id")
    if explicit_group not in (None, ""):
        return str(explicit_group)
    identity = [
        f"{key}={row[key]}"
        for key in ("project_id", "enzyme_id", "uniprot_id", "mutation")
        if row.get(key) not in (None, "")
    ]
    if identity:
        return "|".join(identity)
    return f"ungrouped-{stable_fraction(json.dumps(row, sort_keys=True, default=str)):.12f}"


def row_replicate(row: dict[str, Any]) -> str | None:
    for key in ("replicate_id", "replicate_group_id"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def row_label(row: dict[str, Any]) -> str | None:
    for key in (
        "label_value",
        "label_decision",
        "activity_risk_label",
        "assay_success",
        "substrate_fit_label",
        "label_stability_delta_tm_c",
        "label_ddg",
    ):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def feature_schema_hash(schema: list[str]) -> str:
    payload = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def numeric_features(row: dict[str, Any]) -> tuple[list[float], list[str]]:
    """Return numeric features and their schema, excluding label/near-label fields."""
    explicit = row.get("features")
    if isinstance(explicit, dict):
        schema = sorted(
            key
            for key in explicit
            if key not in LABEL_OR_NEAR_LABEL_FEATURE_FIELDS
        )
        values = [as_float(explicit[key]) for key in schema]
        if values:
            return values, schema
    mutation = str(row.get("mutation") or "")
    position_match = re.search(r"(\d+)", mutation)
    position = as_float(row.get("canonical_position"))
    if not position and position_match:
        position = float(position_match.group(1))
    schema = list(DEFAULT_FEATURE_SCHEMA)
    values = [
        position / 2000.0,
        as_float(row.get("ph")) / 14.0,
        stable_fraction(row.get("enzyme_id") or row.get("uniprot_id")),
        stable_fraction(mutation[:1]),
        stable_fraction(mutation[-1:] if mutation else ""),
        stable_fraction(row.get("metric") or row.get("assay_type")),
    ]
    return values, schema


def normalize_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    normalized = []
    unknown = set()
    for row in rows:
        head = str(row.get("head") or "")
        if head not in EXPECTED_HEADS:
            if head:
                unknown.add(head)
            continue
        label = row_label(row)
        if label is None:
            continue
        features, schema = numeric_features(row)
        normalized.append(
            {
                "head": head,
                "label": label,
                "group": row_group(row),
                "replicate": row_replicate(row),
                "features": features,
                "feature_schema": schema,
            }
        )
    return normalized, sorted(unknown)


def align_feature_rows(rows: list[dict[str, Any]]) -> list[str]:
    """Align heterogeneous feature vectors to one name-based union schema."""
    schema = sorted(
        {
            field
            for row in rows
            for field in row.get("feature_schema") or []
        }
    )
    for row in rows:
        values_by_field = dict(zip(row.get("feature_schema") or [], row.get("features") or []))
        row["features"] = [as_float(values_by_field.get(field)) for field in schema]
        row["feature_schema"] = list(schema)
    return schema


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_training_input_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    canonical_rows = [
        {
            "head": row["head"],
            "label": row["label"],
            "group": row["group"],
            "replicate": row["replicate"],
            "feature_schema": row["feature_schema"],
            "features": row["features"],
        }
        for row in rows
    ]
    return {
        "schema_version": "kwb_five_head_training_input_v1",
        "normalized_label_row_count": len(rows),
        "head_label_rows": {
            head: sum(1 for row in rows if row["head"] == head)
            for head in EXPECTED_HEADS
        },
        "group_count": len({row["group"] for row in rows}),
        "explicit_replicate_count": len(
            {row["replicate"] for row in rows if row["replicate"] is not None}
        ),
        "feature_schema": list(rows[0]["feature_schema"]) if rows else [],
        "canonical_rows_sha256": canonical_sha256(canonical_rows),
        "label_fields_excluded_from_features": sorted(LABEL_OR_NEAR_LABEL_FEATURE_FIELDS),
    }


def head_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metrics = {}
    for head in EXPECTED_HEADS:
        selected = [row for row in rows if row["head"] == head]
        groups = {row["group"] for row in selected}
        replicates = {row["replicate"] for row in selected if row["replicate"] is not None}
        metrics[head] = {
            "sample_count": len(selected),
            "group_count": len(groups),
            "replicate_count": len(replicates),
            "class_count": len({row["label"] for row in selected}),
        }
    return metrics


def eligible_heads(
    metrics: dict[str, dict[str, Any]],
    *,
    mode: str,
    minimum_samples: int,
    minimum_groups: int,
    minimum_replicates: int,
) -> list[str]:
    if mode == "smoke":
        return [head for head in EXPECTED_HEADS if metrics[head]["sample_count"] > 0]
    return [
        head
        for head in EXPECTED_HEADS
        if metrics[head]["sample_count"] >= minimum_samples
        and metrics[head]["group_count"] >= minimum_groups
        and metrics[head]["replicate_count"] >= minimum_replicates
    ]


def split_by_group(
    rows: list[dict[str, Any]],
    *,
    validation_fraction: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups = sorted({row["group"] for row in rows})
    shuffled = list(groups)
    random.Random(seed).shuffle(shuffled)
    validation_group_count = min(
        max(0, len(groups) - 1),
        max(0, int(len(groups) * validation_fraction)),
    )
    validation_groups = set(shuffled[:validation_group_count])
    train = [row for row in rows if row["group"] not in validation_groups]
    validation = [row for row in rows if row["group"] in validation_groups]
    return train, validation


def pad_features(rows: list[dict[str, Any]]) -> int:
    input_dim = max((len(row["features"]) for row in rows), default=1)
    for row in rows:
        row["features"] = row["features"] + [0.0] * (input_dim - len(row["features"]))
    return input_dim


def run_training(
    source_rows: list[dict[str, Any]],
    *,
    mode: str = "research",
    minimum_samples: int = DEFAULT_MINIMUM_SAMPLES,
    minimum_groups: int = DEFAULT_MINIMUM_GROUPS,
    minimum_replicates: int = DEFAULT_MINIMUM_REPLICATES,
    validation_fraction: float = 0.2,
    hidden_dim: int = 32,
    epochs: int = 3,
    seed: int = 20260903,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    if mode not in {"research", "smoke"}:
        raise ValueError("mode must be research or smoke")
    rows, unknown_heads = normalize_rows(source_rows)
    feature_schema = align_feature_rows(rows)
    training_input_manifest = build_training_input_manifest(rows)
    training_input_manifest_sha256 = canonical_sha256(training_input_manifest)
    metrics = head_metrics(rows)
    trainable = eligible_heads(
        metrics,
        mode=mode,
        minimum_samples=minimum_samples,
        minimum_groups=minimum_groups,
        minimum_replicates=minimum_replicates,
    )
    report: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "artifact_kind": (
            "research_multitask_smoke_only"
            if mode == "smoke"
            else "research_multitask_checkpoint"
        ),
        "source_row_count": len(source_rows),
        "normalized_label_row_count": len(rows),
        "head_metrics": metrics,
        "unknown_heads": unknown_heads,
        "trained_heads": [],
        "training_executed": False,
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "excluded_feature_fields": sorted(LABEL_OR_NEAR_LABEL_FEATURE_FIELDS),
        "feature_schema": feature_schema,
        "feature_schema_sha256": feature_schema_hash(feature_schema),
        "training_input_manifest": training_input_manifest,
        "training_input_manifest_sha256": training_input_manifest_sha256,
        "thresholds": {
            "minimum_samples": minimum_samples,
            "minimum_groups": minimum_groups,
            "minimum_replicates": minimum_replicates,
        },
        "policy": (
            "Research and smoke artifacts are isolated from production. Missing labels are "
            "masked, label/near-label fields are excluded from numeric features, and each "
            "head is gated independently."
        ),
    }
    if not rows or not any(metrics[head]["sample_count"] for head in EXPECTED_HEADS):
        report.update(status="blocked_no_trainable_heads")
        return report
    if not trainable:
        report.update(status="blocked_head_thresholds_not_met")
        return report

    selected = [row for row in rows if row["head"] in trainable]
    input_dim = pad_features(selected)
    train_rows, validation_rows = split_by_group(
        selected,
        validation_fraction=validation_fraction,
        seed=seed,
    )
    train_groups = {row["group"] for row in train_rows}
    validation_groups = {row["group"] for row in validation_rows}
    report["split"] = {
        "strategy": "group_holdout",
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "train_groups": len(train_groups),
        "validation_groups": len(validation_groups),
        "group_overlap_count": len(train_groups & validation_groups),
    }

    import torch
    import torch.nn as nn

    class KWBMultiTaskModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.GELU(),
                nn.LayerNorm(hidden_dim),
            )
            self.heads = nn.ModuleDict(
                {
                    head: nn.Linear(
                        hidden_dim,
                        max(2, metrics[head]["class_count"]),
                    )
                    for head in trainable
                }
            )

        def forward(self, features, head: str):
            return self.heads[head](self.encoder(features))

    labels_by_head = {
        head: {
            label: index
            for index, label in enumerate(
                sorted({row["label"] for row in selected if row["head"] == head})
            )
        }
        for head in trainable
    }
    random.seed(seed)
    torch.manual_seed(seed)
    model = KWBMultiTaskModel()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    losses = []
    for epoch in range(epochs):
        plan = list(range(len(train_rows)))
        random.Random(seed + epoch).shuffle(plan)
        for index in plan:
            row = train_rows[index]
            features = torch.tensor([row["features"]], dtype=torch.float32)
            target = torch.tensor([labels_by_head[row["head"]][row["label"]]], dtype=torch.long)
            loss = loss_fn(model(features, row["head"]), target)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach()))

    validation_losses = []
    model.eval()
    with torch.no_grad():
        for row in validation_rows:
            features = torch.tensor([row["features"]], dtype=torch.float32)
            target = torch.tensor([labels_by_head[row["head"]][row["label"]]], dtype=torch.long)
            validation_losses.append(float(loss_fn(model(features, row["head"]), target)))

    checkpoint_path = checkpoint_path or (
        AI_ROOT / "reports" / f"research_multitask_{mode}.checkpoint.pt"
    )
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "input_dim": input_dim,
            "hidden_dim": hidden_dim,
            "trained_heads": trainable,
            "labels_by_head": labels_by_head,
            "feature_schema": feature_schema,
            "excluded_feature_fields": sorted(LABEL_OR_NEAR_LABEL_FEATURE_FIELDS),
            "feature_schema_sha256": feature_schema_hash(feature_schema),
            "training_input_manifest_sha256": training_input_manifest_sha256,
            "mode": mode,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        checkpoint_path,
    )
    report.update(
        status="completed_smoke_only" if mode == "smoke" else "completed_research_only",
        training_executed=True,
        trained_heads=trainable,
        epochs=epochs,
        steps=len(losses),
        final_loss=round(losses[-1], 6) if losses else None,
        validation_loss=(
            round(sum(validation_losses) / len(validation_losses), 6)
            if validation_losses
            else None
        ),
        checkpoint_path=str(checkpoint_path.resolve()),
        checkpoint_sha256=file_sha256(checkpoint_path),
        checkpoint_receipt={
            "path": str(checkpoint_path.resolve()),
            "sha256": file_sha256(checkpoint_path),
            "size_bytes": checkpoint_path.stat().st_size,
            "training_input_manifest_sha256": training_input_manifest_sha256,
            "feature_schema_sha256": feature_schema_hash(feature_schema),
        },
    )
    return report


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run research-only KWB multi-task training")
    parser.add_argument("--mode", choices=("research", "smoke"), default="research")
    parser.add_argument("--activity-risk", type=Path, default=DEFAULT_ACTIVITY_RISK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260903)
    args = parser.parse_args()
    rows = load_jsonl(args.activity_risk)
    result = run_training(
        rows,
        mode=args.mode,
        checkpoint_path=args.checkpoint,
        epochs=args.epochs,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "training_executed": result["training_executed"],
                "trained_heads": result["trained_heads"],
                "safe_for_model_claim": False,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["training_executed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
