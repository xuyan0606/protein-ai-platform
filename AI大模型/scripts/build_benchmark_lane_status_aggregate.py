#!/usr/bin/env python3
"""Aggregate benchmark-lane pre-review, bridge, and cache state."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PREREVIEW = AI_ROOT / "reports/benchmark_lane_machine_prereview_report.json"
BRIDGE = AI_ROOT / "reports/hard_gate_decision_benchmark_bridge_report.json"
BRIDGE_VALIDATION = AI_ROOT / "reports/hard_gate_decision_benchmark_bridge_validation_report.json"
OUT = AI_ROOT / "reports/benchmark_lane_status_aggregate_report.json"


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate benchmark lane state")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    prereview = load(PREREVIEW)
    bridge = load(BRIDGE)
    validation = load(BRIDGE_VALIDATION)
    strict_pre = (prereview.get("lanes") or {}).get("strict_mutation_holdout") or {}
    substrate_pre = (prereview.get("lanes") or {}).get("reviewed_substrate_identity_set") or {}
    lanes = {
        "kwb_strict_mutation_holdout": {
            "machine_pre_review_status": strict_pre.get("machine_status", "missing"),
            "formal_approved_rows": bridge.get("strict_formal_approved_rows", 0),
            "bridge_status": (bridge.get("strict") or {}).get("status", "missing"),
            "cache_status": "ready" if (bridge.get("strict") or {}).get("intake_written") else "blocked",
        },
        "reviewed_substrate_identity_set": {
            "machine_pre_review_status": substrate_pre.get("machine_status", "missing"),
            "formal_approved_rows": bridge.get("substrate_formal_approved_rows", 0),
            "bridge_status": (bridge.get("substrate") or {}).get("status", "missing"),
            "cache_status": "ready" if (bridge.get("substrate") or {}).get("intake_written") else "blocked",
        },
    }
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked" if any(item["cache_status"] == "blocked" for item in lanes.values()) else "ready_for_local_benchmark_use",
        "lanes": lanes,
        "bridge_validation_success": validation.get("success", False),
        "training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "claim_release_gate": "closed",
        "policy": "Aggregate status is local lane bookkeeping only. Human decisions, training import, model claims, and release remain closed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "bridge_validation_success": report["bridge_validation_success"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
