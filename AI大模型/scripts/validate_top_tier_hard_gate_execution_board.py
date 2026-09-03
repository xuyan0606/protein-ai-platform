#!/usr/bin/env python3
"""Validate top-tier hard-gate execution board semantics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "top_tier_hard_gate_execution_board.json"
ACTIONS = AI_ROOT / "datasets" / "governance" / "top_tier_hard_gate_execution_actions.jsonl"
OUT = AI_ROOT / "reports" / "top_tier_hard_gate_execution_validation_report.json"

REQUIRED_GATES = {
    "HTG-001-reviewed-numbering-real-labels",
    "HTG-002-wet-lab-training-eligible-feedback",
    "HTG-003-benchmark-scorecard-claim-cache",
    "HTG-004-physical-ddg-runtime",
    "HTG-005-substrate-fit-label-source",
    "HTG-006-structure-feature-expansion",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate top-tier hard-gate execution board")
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--actions", type=Path, default=ACTIONS)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    board = load_json(args.board)
    actions = load_jsonl(args.actions)
    failures: list[dict[str, Any]] = []

    gate_ids = {str(row.get("gate_id")) for row in actions}
    missing = sorted(REQUIRED_GATES - gate_ids)
    extra = sorted(gate_ids - REQUIRED_GATES)
    if missing:
        failures.append({"check": "required_gates_present", "missing": missing})
    if extra:
        failures.append({"check": "no_unexpected_gates", "extra": extra})
    if board.get("gate_count") != len(actions):
        failures.append({"check": "board_gate_count_matches_actions", "expected": len(actions), "actual": board.get("gate_count")})
    if board.get("blocked_gates") != len(actions):
        failures.append({"check": "all_gates_remain_blocked", "expected": len(actions), "actual": board.get("blocked_gates")})
    if board.get("ready_gates") != 0:
        failures.append({"check": "ready_gates_zero", "actual": board.get("ready_gates")})
    if board.get("safe_for_training_import") is not False:
        failures.append({"check": "safe_for_training_import_false"})
    if board.get("safe_for_model_claim") is not False:
        failures.append({"check": "safe_for_model_claim_false"})
    if board.get("release_ready") is not False:
        failures.append({"check": "release_ready_false"})

    for row in actions:
        gate_id = str(row.get("gate_id"))
        if row.get("status") != "blocked":
            failures.append({"check": "action_status_blocked", "gate_id": gate_id, "actual": row.get("status")})
        for field in ("training_unlocked", "model_claim_allowed", "release_ready"):
            if row.get(field) is not False:
                failures.append({"check": f"{field}_false", "gate_id": gate_id, "actual": row.get(field)})
        if not row.get("evidence_artifacts"):
            failures.append({"check": "evidence_artifacts_present", "gate_id": gate_id})
        if not row.get("next_actions"):
            failures.append({"check": "next_actions_present", "gate_id": gate_id})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "board": rel(args.board),
        "actions": rel(args.actions),
        "validated_gate_rows": len(actions),
        "failed_checks": len(failures),
        "success": not failures,
        "blocked_gate_rows": sum(1 for row in actions if row.get("status") == "blocked"),
        "model_claim_allowed_rows": sum(1 for row in actions if row.get("model_claim_allowed") is True),
        "release_ready_rows": sum(1 for row in actions if row.get("release_ready") is True),
        "failures": failures,
        "policy": "Validator only. It checks fail-closed semantics and does not create decisions, approvals, labels, claims, downloads, or deployments.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "validated_gate_rows": report["validated_gate_rows"],
        "failed_checks": report["failed_checks"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
