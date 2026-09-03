#!/usr/bin/env python3
"""Reconcile wet-lab authorization/apply-plan rows with local feedback import.

This report makes the two current counters explicit:
- wet_lab apply/import rows remain zero because no append executor is authorized.
- numeric local feedback rows are six because P197 manually added activity rows.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = AI_ROOT / "reports" / "wet_lab_feedback_import_reconciliation_report.json"

SOURCES = {
    "authorization": "reports/wet_lab_mutant_library_feedback_authorization_validation_report.json",
    "preflight": "reports/wet_lab_mutant_library_feedback_preflight_report.json",
    "apply_plan": "reports/wet_lab_mutant_library_feedback_intake_apply_plan_report.json",
    "duplicate_audit": "reports/wet_lab_feedback_apply_duplicate_audit_report.json",
    "experiment_feedback": "reports/experiment_feedback_intake_validation_report.json",
    "semantic_guard": "reports/feedback_training_import_semantic_guard_report.json",
    "training_import_contract": "reports/training_label_import_contract_report.json",
    "model_quality": "reports/model_quality_hard_gate_contract_report.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab feedback import reconciliation report")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    reports = {name: load_json(AI_ROOT / rel) for name, rel in SOURCES.items()}
    missing_sources = [rel for name, rel in SOURCES.items() if not reports[name]]

    authorization = reports["authorization"]
    preflight = reports["preflight"]
    apply_plan = reports["apply_plan"]
    duplicate_audit = reports["duplicate_audit"]
    experiment_feedback = reports["experiment_feedback"]
    semantic_guard = reports["semantic_guard"]
    training_import_contract = reports["training_import_contract"]
    model_quality = reports["model_quality"]

    counts = {
        "wetlab_authorized_rows": as_int(authorization.get("authorized_rows")),
        "wetlab_preflight_rows": as_int(preflight.get("preflight_rows")),
        "wetlab_apply_plan_rows": as_int(apply_plan.get("apply_plan_rows")),
        "wetlab_applied_rows": as_int(apply_plan.get("applied_rows")),
        "wetlab_ready_for_training_import_rows": as_int(apply_plan.get("ready_for_training_import_rows")),
        "duplicate_already_represented_rows": as_int(duplicate_audit.get("already_represented_rows")),
        "duplicate_new_feedback_only_rows": as_int(duplicate_audit.get("new_feedback_only_rows")),
        "duplicate_safe_to_append_rows": as_int(duplicate_audit.get("safe_to_append_rows")),
        "duplicate_training_import_from_apply_plan_rows": as_int(
            duplicate_audit.get("training_import_eligible_from_apply_plan_rows")
        ),
        "local_feedback_numeric_training_eligible_rows": as_int(
            experiment_feedback.get("numeric_training_eligible_rows")
        ),
        "semantic_numeric_training_import_eligible_rows": as_int(
            semantic_guard.get("numeric_training_import_eligible")
        ),
        "contract_training_import_eligible_rows": as_int(
            (training_import_contract.get("contract_totals") or {}).get("training_import_eligible_rows")
        ),
        "model_quality_training_import_eligible_rows": as_int(
            model_quality.get("training_import_eligible_rows")
        ),
        "strict_supervised_rows": as_int(model_quality.get("strict_supervised_rows")),
        "claim_eligible_rows": as_int(model_quality.get("claim_eligible_rows")),
    }

    consistency_failures: list[dict[str, Any]] = []
    if missing_sources:
        consistency_failures.append({"check": "source_reports_present", "missing": missing_sources})
    if counts["wetlab_authorized_rows"] != counts["wetlab_preflight_rows"]:
        consistency_failures.append({
            "check": "authorized_rows_match_preflight_rows",
            "observed": {
                "authorized": counts["wetlab_authorized_rows"],
                "preflight": counts["wetlab_preflight_rows"],
            },
        })
    if counts["wetlab_preflight_rows"] != counts["wetlab_apply_plan_rows"]:
        consistency_failures.append({
            "check": "preflight_rows_match_apply_plan_rows",
            "observed": {
                "preflight": counts["wetlab_preflight_rows"],
                "apply_plan": counts["wetlab_apply_plan_rows"],
            },
        })
    expected_numeric = counts["local_feedback_numeric_training_eligible_rows"] + counts[
        "duplicate_training_import_from_apply_plan_rows"
    ]
    if counts["semantic_numeric_training_import_eligible_rows"] != expected_numeric:
        consistency_failures.append({
            "check": "semantic_numeric_rows_equal_local_feedback_plus_apply_plan_training_rows",
            "observed": counts["semantic_numeric_training_import_eligible_rows"],
            "expected": expected_numeric,
        })
    for key in ("contract_training_import_eligible_rows", "model_quality_training_import_eligible_rows"):
        if counts[key] != counts["semantic_numeric_training_import_eligible_rows"]:
            consistency_failures.append({
                "check": f"{key}_matches_semantic_numeric_rows",
                "observed": counts[key],
                "expected": counts["semantic_numeric_training_import_eligible_rows"],
            })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_reports": SOURCES,
        "missing_sources": missing_sources,
        "counts": counts,
        "wet_lab_import_rows_explanation": {
            "wetlab_applied_rows": counts["wetlab_applied_rows"],
            "why_zero": [
                "apply_plan is read-only and never appends experiment_feedback.local.jsonl",
                "duplicate audit found six activity rows already represented in local feedback",
                "two remaining thermal-retention percent rows are feedback-only until a reviewed stability target rule exists",
            ],
        },
        "numeric_training_import_explanation": {
            "numeric_training_import_eligible_rows": counts["semantic_numeric_training_import_eligible_rows"],
            "source": "experiment_feedback.local numeric activity rows plus zero apply-plan training rows",
            "local_feedback_numeric_rows": counts["local_feedback_numeric_training_eligible_rows"],
            "apply_plan_training_rows": counts["duplicate_training_import_from_apply_plan_rows"],
        },
        "consistency_failures": consistency_failures,
        "success": not consistency_failures,
        "numeric_training_import_source_supported": (
            counts["semantic_numeric_training_import_eligible_rows"] > 0 and not consistency_failures
        ),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "wet_lab import/apply counters and local numeric feedback counters are intentionally separate. "
            "This reconciliation is read-only and cannot authorize append, training execution, model claim, or release."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": report["success"],
                "wetlab_applied_rows": counts["wetlab_applied_rows"],
                "numeric_training_import_eligible_rows": counts["semantic_numeric_training_import_eligible_rows"],
                "safe_for_model_claim": report["safe_for_model_claim"],
                "release_ready": report["release_ready"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
