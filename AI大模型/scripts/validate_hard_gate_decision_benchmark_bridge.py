#!/usr/bin/env python3
"""Validate the hard-gate decision-to-benchmark bridge."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT_IN = AI_ROOT / "reports/hard_gate_decision_benchmark_bridge_report.json"
STRICT_DECISIONS = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl"
SUBSTRATE_DECISIONS = AI_ROOT / "datasets/curation/substrate_identity_review_decisions.jsonl"
OUT = AI_ROOT / "reports/hard_gate_decision_benchmark_bridge_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else AI_ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate hard-gate benchmark bridge")
    parser.add_argument("--report-in", type=Path, default=REPORT_IN)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    report = load_json(args.report_in)
    strict_decisions = load_jsonl(STRICT_DECISIONS)
    substrate_decisions = load_jsonl(SUBSTRATE_DECISIONS)
    failures: list[dict[str, Any]] = []
    strict_approvals = sum(1 for row in strict_decisions if row.get("decision") == "approve_strict_holdout")
    substrate_approvals = sum(1 for row in substrate_decisions if row.get("decision") == "approve_reviewed_substrate_identity")

    if report.get("strict_formal_approved_rows") > strict_approvals:
        failures.append({"check": "strict_approved_rows_not_more_than_decisions", "observed": report.get("strict_formal_approved_rows"), "decisions": strict_approvals})
    if report.get("substrate_formal_approved_rows") > substrate_approvals:
        failures.append({"check": "substrate_approved_rows_not_more_than_decisions", "observed": report.get("substrate_formal_approved_rows"), "decisions": substrate_approvals})
    if strict_approvals == 0 and (report.get("strict") or {}).get("intake_written") is not False:
        failures.append({"check": "strict_zero_approval_no_intake", "observed": report.get("strict")})
    if substrate_approvals == 0 and (report.get("substrate") or {}).get("intake_written") is not False:
        failures.append({"check": "substrate_zero_approval_no_intake", "observed": report.get("substrate")})
    if report.get("training_import_written_rows") != 0:
        failures.append({"check": "training_import_zero", "observed": report.get("training_import_written_rows")})
    if report.get("safe_for_model_claim") is not False or report.get("release_ready") is not False:
        failures.append({"check": "claim_release_false", "safe_for_model_claim": report.get("safe_for_model_claim"), "release_ready": report.get("release_ready")})
    if report.get("intake_rows_written") != 0:
        failures.append({"check": "bridge_must_not_write_intake_in_current_pre_review_lane", "observed": report.get("intake_rows_written")})
    for lane_name in ("strict", "substrate"):
        lane = report.get(lane_name) or {}
        if lane.get("intake_written") is not False:
            continue
        if lane.get("dataset_rows", 0) != 0:
            failures.append({"check": f"{lane_name}_blocked_lane_must_have_zero_dataset_rows", "observed": lane.get("dataset_rows")})
    for lane_name in ("strict", "substrate"):
        lane = report.get(lane_name) or {}
        for artifact_key in ("dataset", "split_definition", "scorecard", "metric_report"):
            artifact = lane.get(artifact_key) or {}
            path = resolve(artifact.get("path"))
            if path and path.exists():
                failures.append({"check": f"{lane_name}_blocked_lane_must_not_materialize_{artifact_key}", "observed": str(path)})

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "strict_decision_rows": len(strict_decisions),
        "substrate_decision_rows": len(substrate_decisions),
        "strict_approval_rows": strict_approvals,
        "substrate_approval_rows": substrate_approvals,
        "intake_rows_written": report.get("intake_rows_written"),
        "training_import_written_rows": report.get("training_import_written_rows"),
        "safe_for_model_claim": False,
        "release_ready": False,
        "failures": failures,
        "policy": "Bridge validation confirms no benchmark intake is written without complete formal decisions.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "intake_rows_written": validation["intake_rows_written"], "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
