#!/usr/bin/env python3
"""Fail-closed entrypoint for the real KWB five-head production training run."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from train_research_multitask import EXPECTED_HEADS, load_jsonl, run_training as run_training_core


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_training(base: Path) -> dict[str, Any]:
    reports = base / "reports"
    gate_path = reports / "production_model_gate.json"
    if not gate_path.is_file():
        dated = reports / "production_model_gate_20260829.json"
        if dated.is_file():
            gate_path = dated
    gate = _load(gate_path)
    if gate.get("production_ready") is not True:
        result = {
            "status": "blocked_pending_production_gate",
            "training_executed": False,
            "blockers": list(gate.get("blockers") or ["production gate report missing or not ready"]),
        }
    else:
        execution_path = reports / "five_head_training_execution_contract_report.json"
        execution = _load(execution_path)
        if (
            execution.get("training_execution_allowed") is not True
            or int(execution.get("ready_head_count") or 0) != len(EXPECTED_HEADS)
        ):
            result = {
                "status": "blocked_pending_training_execution_contract",
                "training_executed": False,
                "blockers": [
                    "five-head execution contract is missing, inconsistent, or not ready"
                ],
                "execution_contract": str(execution_path),
            }
        else:
            dataset = base / "datasets" / "training" / "five_head_training_labels.jsonl"
            if not dataset.is_file():
                result = {
                    "status": "blocked_missing_training_dataset",
                    "training_executed": False,
                    "blockers": [f"required dataset missing: {dataset}"],
                    "execution_contract": str(execution_path),
                }
            else:
                core = run_training_core(
                    load_jsonl(dataset),
                    mode="research",
                    checkpoint_path=reports / "kwb_enzyme_designer_production.checkpoint.pt",
                )
                if (
                    core.get("training_executed") is not True
                    or set(core.get("trained_heads") or []) != set(EXPECTED_HEADS)
                ):
                    result = {
                        "status": "blocked_training_core_rejected_dataset",
                        "training_executed": False,
                        "blockers": [
                            "training core did not accept all five heads at production thresholds"
                        ],
                        "core_receipt": core,
                    }
                else:
                    result = {
                        **core,
                        "status": "completed_production_training",
                        "artifact_kind": "production_five_head_checkpoint",
                        "dataset": str(dataset),
                        "dataset_sha256": _sha256(dataset),
                        "safe_for_model_claim": False,
                        "release_ready": False,
                        "requires_post_training_validation": True,
                    }
    result.update({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gate_report": str(gate_path),
        "safe_for_model_claim": result.get("safe_for_model_claim") is True,
        "release_ready": result.get("release_ready") is True,
    })
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "production_training_run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = run_training(args.base)
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result["training_executed"] is not True else 0


if __name__ == "__main__":
    raise SystemExit(main())
