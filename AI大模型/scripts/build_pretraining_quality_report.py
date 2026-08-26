#!/usr/bin/env python3
"""Build an auditable, unlabeled pretraining quality report."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, pstdev


def stats(values: list[float]) -> dict[str, float]:
    return {"min": min(values), "max": max(values), "mean": mean(values), "stddev": pstdev(values)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize unlabeled sequence pretraining quality")
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--index-validation", type=Path, required=True)
    parser.add_argument("--collision-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    validation = json.loads(args.index_validation.read_text(encoding="utf-8"))
    collisions = json.loads(args.collision_report.read_text(encoding="utf-8"))
    rows = [r for r in summary.get("rows", []) if r.get("status") == "completed_pretraining_only"]
    if not rows:
        raise SystemExit("no completed pretraining rows")
    train = [float(r["final_loss"]) for r in rows]
    valid = [float(r["validation_loss"]) for r in rows]
    best = min(rows, key=lambda r: float(r["validation_loss"]))
    payload = {
        "artifact_kind": "unlabeled_sequence_pretraining_quality_report",
        "batch_count": len(rows),
        "total_sequence_count": sum(int(r.get("sequence_count", 0)) for r in rows),
        "total_steps": sum(int(r.get("steps", 0)) for r in rows),
        "train_loss": stats(train),
        "validation_loss": stats(valid),
        "lowest_validation_loss_batch": best.get("batch"),
        "lowest_validation_loss": float(best["validation_loss"]),
        "index_validation": {
            "success": validation.get("success"),
            "record_count": validation.get("record_count"),
            "duplicate_embedding_records": validation.get("duplicate_embedding_records"),
            "failures": len(validation.get("failures", [])),
        },
        "collision_audit": {
            "collision_group_count": collisions.get("collision_group_count"),
            "collision_record_count": collisions.get("collision_record_count"),
        },
        "interpretation": "Unlabeled masked-amino-acid pretraining and representation integrity only; no supervised or biological performance claim.",
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed_quality_report", "batches": len(rows), "sequences": payload["total_sequence_count"], "best_validation_batch": best.get("batch")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
