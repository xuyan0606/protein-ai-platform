#!/usr/bin/env python3
"""Validate report-level positive claim gates remain quarantined."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "report_positive_claim_gate_quarantine_validation_report.json"

RISKY_TRUE_FIELDS = {
    "approved_for_ordering",
    "customer_delivery_ready",
    "model_quality_ready",
    "ready_for_customer_delivery",
    "ready_for_model_claim",
    "ready_for_ordering",
    "ready_for_training_import",
    "release_ready",
    "safe_for_model_claim",
    "safe_for_training_import",
    "training_unlocked",
}

ALLOWLIST_TRUE_PATHS = {
    # Target-state documentation is allowed to describe the desired future state.
    ("reports/model_quality_unlock_requirements_report.json", "requirements[0].target_state.safe_for_model_claim"),
    # Numeric wet-lab feedback import is a local training-import gate only, not a model/release claim.
    ("reports/feedback_training_import_semantic_guard_report.json", "safe_for_training_import"),
    ("reports/feedback_training_import_semantic_guard_validation_report.json", "safe_for_training_import"),
    ("reports/activity_risk_formal_label_decision_report.json", "safe_for_training_import"),
    ("reports/activity_risk_formal_label_decision_validation_report.json", "safe_for_training_import"),
    ("reports/activity_risk_training_import_label_report.json", "safe_for_training_import"),
    ("reports/activity_risk_training_import_label_validation_report.json", "safe_for_training_import"),
    ("reports/five_head_training_execution_contract_report.json", "training_label_import.safe_for_training_import"),
    ("reports/training_label_import_contract_report.json", "safe_for_training_import"),
    ("reports/training_label_import_contract_validation_report.json", "safe_for_training_import"),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def walk_json(value: Any, path: str = "") -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in RISKY_TRUE_FIELDS and child is True:
                hits.append((child_path, key))
            hits.extend(walk_json(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            hits.extend(walk_json(child, f"{path}[{idx}]"))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate report-level positive claim gate quarantine")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    scanned_reports: dict[str, dict[str, Any]] = {}
    allowlisted_hits: list[dict[str, Any]] = []
    risky_true_hits: list[dict[str, Any]] = []

    for path in sorted((AI_ROOT / "reports").rglob("*.json")):
        rel_path = str(path.relative_to(AI_ROOT))
        try:
            data = load_json(path)
        except Exception as exc:  # pragma: no cover - malformed reports are surfaced as failures.
            failures.append({"check": "report_json_parseable", "file": rel_path, "error": str(exc)})
            continue
        hits = walk_json(data)
        scanned_reports[rel_path] = {"risky_true_hits": len(hits)}
        for json_path, field in hits:
            hit = {"file": rel_path, "json_path": json_path, "field": field}
            risky_true_hits.append(hit)
            if (rel_path, json_path) in ALLOWLIST_TRUE_PATHS:
                allowlisted_hits.append(hit)
            else:
                failures.append({
                    "check": "no_unreviewed_report_positive_claim_gate",
                    **hit,
                    "observed": True,
                    "expected": "false unless explicitly allowlisted as non-current-state documentation",
                })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "scanned_report_count": len(scanned_reports),
        "scanned_reports": scanned_reports,
        "risky_true_fields": sorted(RISKY_TRUE_FIELDS),
        "risky_true_hit_count": len(risky_true_hits),
        "allowlisted_true_hit_count": len(allowlisted_hits),
        "disallowed_true_hit_count": sum(1 for failure in failures if failure.get("check") == "no_unreviewed_report_positive_claim_gate"),
        "risky_true_hits": risky_true_hits,
        "allowlisted_true_hits": allowlisted_hits,
        "failures": failures,
        "safe_for_training_pipeline": not failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Report-level training, model-claim and release gates must remain false. Allowed true values must be explicit non-current-state documentation, not readiness claims.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "scanned_report_count": report["scanned_report_count"],
        "risky_true_hit_count": report["risky_true_hit_count"],
        "disallowed_true_hit_count": report["disallowed_true_hit_count"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
