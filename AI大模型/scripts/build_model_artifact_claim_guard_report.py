#!/usr/bin/env python3
"""Build a fail-closed inventory for model artifacts and model-claim safety."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "model_artifact_claim_guard_report.json"

MODEL_ARTIFACTS = [
    "prototype/baseline_ranker_model.json",
    "prototype/supervised_mutation_baseline_model.json",
    "prototype/supervised_mutation_enriched_baseline_model.json",
    "prototype/supervised_mutation_verified_baseline_model.json",
    "prototype/site_sequence_feature_baseline_model.json",
    "prototype/repaired_supervised_baseline_model.json",
    "prototype/repaired_supervised_msa_baseline_model.json",
    "prototype/kwb_enzyme_designer_multitask_scaffold.json",
    "prototype/kwb_enzyme_designer_advanced_model.py",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.suffix != ".json":
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def classify_artifact(path: Path, data: dict[str, Any]) -> tuple[str, list[str]]:
    rel_path = rel(path)
    reasons: list[str] = []
    status = str(data.get("status") or "").lower()
    trained_rows = as_int(data.get("trained_on_rows"))
    limitations = " ".join(str(item).lower() for item in data.get("limitations") or [])

    if path.suffix == ".py":
        return "code_scaffold_not_weights", ["python scaffold source, not a serialized trained model"]
    if "scaffold" in rel_path or "scaffold" in status:
        return "scaffold_only_not_trained_weights", ["scaffold artifact only"]
    if status == "blocked_empty_train_split" or trained_rows == 0:
        return "blocked_empty_training_baseline", ["trained_on_rows is 0 or blocked_empty_train_split"]
    if "not a trained neural model" in limitations:
        return "rule_or_baseline_not_neural_weights", ["limitations explicitly say not a trained neural model"]
    if "repaired" not in rel_path:
        reasons.append("legacy or non-strict training source")
    if trained_rows < 100:
        reasons.append("below model-claim row threshold")
    if data.get("safe_for_model_claim") is not True:
        reasons.append("source artifact does not set safe_for_model_claim true")
    return "legacy_baseline_not_claimable", reasons or ["no current claim authorization"]


def build_row(rel_path: str) -> dict[str, Any]:
    path = AI_ROOT / rel_path
    data = load_json(path)
    artifact_class, blocked_reasons = classify_artifact(path, data)
    has_weights_field = isinstance(data.get("weights"), dict)
    row = {
        "path": rel_path,
        "exists": path.exists(),
        "sha256": sha256(path),
        "artifact_class": artifact_class,
        "model": data.get("model") if data else "python_source_scaffold",
        "version": data.get("version") if data else None,
        "status": data.get("status") if data else ("source_code" if path.exists() else "missing"),
        "trained_on_rows": as_int(data.get("trained_on_rows")),
        "training_source": data.get("training_source"),
        "has_weights_field": has_weights_field,
        "trained_neural_weights": False,
        "production_model_artifact": False,
        "claimable_model_artifact": False,
        "safe_for_model_claim_source_field": data.get("safe_for_model_claim"),
        "safe_for_model_claim": False,
        "release_ready": False,
        "blocked_reasons": blocked_reasons,
    }
    if not path.exists():
        row["blocked_reasons"] = ["artifact_missing"]
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Build model artifact claim guard report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    artifacts = [build_row(rel_path) for rel_path in MODEL_ARTIFACTS]
    missing = [row["path"] for row in artifacts if not row["exists"]]
    claimable = [row for row in artifacts if row["claimable_model_artifact"]]
    trained_neural = [row for row in artifacts if row["trained_neural_weights"]]
    production = [row for row in artifacts if row["production_model_artifact"]]

    class_counts: dict[str, int] = {}
    for row in artifacts:
        class_counts[row["artifact_class"]] = class_counts.get(row["artifact_class"], 0) + 1

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not missing,
        "artifact_count": len(artifacts),
        "missing_artifacts": missing,
        "class_counts": class_counts,
        "artifacts": artifacts,
        "claimable_model_artifact_count": len(claimable),
        "trained_neural_weight_artifact_count": len(trained_neural),
        "production_model_artifact_count": len(production),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Existing prototype artifacts are retained for audit and local regression only. "
            "Legacy baselines, empty-train baselines, and scaffolds are not claimable top-tier model weights."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "artifact_count": report["artifact_count"],
        "claimable_model_artifact_count": report["claimable_model_artifact_count"],
        "trained_neural_weight_artifact_count": report["trained_neural_weight_artifact_count"],
        "production_model_artifact_count": report["production_model_artifact_count"],
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
