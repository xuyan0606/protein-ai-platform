#!/usr/bin/env python3
"""Validate that an unlabeled pretraining asset remains blocked from release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_gate(selection: dict[str, Any]) -> dict[str, Any]:
    failures = []
    if selection.get("integrity_pass") is not True:
        failures.append("checkpoint_integrity_must_pass")
    if selection.get("safe_for_supervised_training") is not False:
        failures.append("safe_for_supervised_training_must_be_false")
    if selection.get("safe_for_model_claim") is not False:
        failures.append("safe_for_model_claim_must_be_false")
    if selection.get("release_status") != "pretraining_only_not_for_production":
        failures.append("release_status_must_be_pretraining_only_not_for_production")
    return {
        "success": not failures,
        "decision": "blocked_pretraining_only" if not failures else "invalid_fail_closed",
        "release_ready": False,
        "supervised_training_ready": False,
        "failures": failures,
        "policy": "Integrity permits local pretraining use only and never promotes the asset to supervised training or production release.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate pretraining-only release isolation")
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    report = evaluate_gate(selection)
    report.update({
        "artifact_kind": "pretraining_release_isolation_gate",
        "selection_manifest": str(args.selection.resolve()),
        "selected_batch": selection.get("selected_batch"),
        "selected_checkpoint_sha256": selection.get("selected_checkpoint_sha256"),
        "safe_for_model_claim": False,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "decision": report["decision"], "release_ready": False}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
