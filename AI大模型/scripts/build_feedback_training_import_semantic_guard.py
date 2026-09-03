#!/usr/bin/env python3
"""Build a fail-closed semantic guard for feedback training import.

The guard separates qualitative feedback eligibility from numeric supervised
label import eligibility. It is read-only and never writes training labels.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "feedback_training_import_semantic_guard_report.json"

REPORTS = {
    "experiment_feedback_intake_validation": "reports/experiment_feedback_intake_validation_report.json",
    "wet_lab_mutant_library_feedback_authorization_validation": "reports/wet_lab_mutant_library_feedback_authorization_validation_report.json",
    "wet_lab_mutant_library_feedback_preflight": "reports/wet_lab_mutant_library_feedback_preflight_report.json",
    "wet_lab_mutant_library_feedback_intake_apply_plan": "reports/wet_lab_mutant_library_feedback_intake_apply_plan_report.json",
    "safe_training_entrypoint_check": "reports/safe_training_entrypoint_check.json",
    "label_provenance_audit": "reports/label_provenance_audit_report.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def supported_numeric_training_import_rows(
    experiment_feedback: dict[str, Any],
    apply_plan: dict[str, Any],
) -> int:
    """Rows that a real source report says are numeric import candidates now.

    Existing experiment feedback may contain schema-valid numeric labels.
    Wet-lab mutant-library candidates are counted only after the apply plan marks
    them ready for training import. Authorization and preflight consistency is
    checked separately so this remains conservative but not source-blind.
    """

    return as_int(experiment_feedback.get("numeric_training_eligible_rows")) + as_int(
        apply_plan.get("ready_for_training_import_rows")
    )


def consistent_strict_rows(safe_entry: dict[str, Any], provenance: dict[str, Any]) -> int:
    safe_rows = as_int(safe_entry.get("rows"))
    provenance_rows = as_int(provenance.get("strict_rows"))
    return safe_rows if safe_rows == provenance_rows else 0


def consistent_claim_rows(safe_entry: dict[str, Any], provenance: dict[str, Any]) -> int:
    safe_rows = as_int(safe_entry.get("claim_eligible_rows"))
    provenance_rows = as_int(provenance.get("claim_eligible_rows"))
    return safe_rows if safe_rows == provenance_rows else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build feedback training import semantic guard")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    paths = {name: AI_ROOT / rel for name, rel in REPORTS.items()}
    reports = {name: load_json(path) for name, path in paths.items()}
    missing_reports = [REPORTS[name] for name, data in reports.items() if not data]

    experiment_feedback = reports["experiment_feedback_intake_validation"]
    authorization = reports["wet_lab_mutant_library_feedback_authorization_validation"]
    preflight = reports["wet_lab_mutant_library_feedback_preflight"]
    apply_plan = reports["wet_lab_mutant_library_feedback_intake_apply_plan"]
    safe_entry = reports["safe_training_entrypoint_check"]
    provenance = reports["label_provenance_audit"]

    qualitative_rows = as_int(experiment_feedback.get("qualitative_training_eligible_rows"))
    numeric_rows = supported_numeric_training_import_rows(experiment_feedback, apply_plan)
    strict_rows = consistent_strict_rows(safe_entry, provenance)
    claim_rows = consistent_claim_rows(safe_entry, provenance)

    consistency_failures: list[dict[str, Any]] = []
    if missing_reports:
        consistency_failures.append({"check": "required_source_reports_present", "missing": missing_reports})

    wet_lab_ready_values = {
        "authorization_ready_for_training_import_rows": as_int(authorization.get("ready_for_training_import_rows")),
        "preflight_ready_for_training_import_rows": as_int(preflight.get("ready_for_training_import_rows")),
        "apply_plan_ready_for_training_import_rows": as_int(apply_plan.get("ready_for_training_import_rows")),
    }
    if len(set(wet_lab_ready_values.values())) > 1:
        consistency_failures.append({
            "check": "wet_lab_training_import_rows_consistent",
            "observed": wet_lab_ready_values,
        })

    wet_lab_claim_values = {
        "authorization_claim_eligible_rows_now": as_int(authorization.get("claim_eligible_rows_now")),
        "preflight_claim_eligible_rows_now": as_int(preflight.get("claim_eligible_rows_now")),
        "apply_plan_claim_eligible_rows_now": as_int(apply_plan.get("claim_eligible_rows_now")),
    }
    if len(set(wet_lab_claim_values.values())) > 1:
        consistency_failures.append({
            "check": "wet_lab_claim_eligible_rows_consistent",
            "observed": wet_lab_claim_values,
        })

    if as_int(safe_entry.get("rows")) != as_int(provenance.get("strict_rows")):
        consistency_failures.append({
            "check": "strict_rows_match_safe_entry_and_label_provenance",
            "safe_training_entrypoint_rows": safe_entry.get("rows"),
            "label_provenance_strict_rows": provenance.get("strict_rows"),
        })

    if as_int(safe_entry.get("claim_eligible_rows")) != as_int(provenance.get("claim_eligible_rows")):
        consistency_failures.append({
            "check": "claim_eligible_rows_match_safe_entry_and_label_provenance",
            "safe_training_entrypoint_claim_eligible_rows": safe_entry.get("claim_eligible_rows"),
            "label_provenance_claim_eligible_rows": provenance.get("claim_eligible_rows"),
        })

    semantic_rows = {
        "qualitative_feedback_eligible": qualitative_rows,
        "numeric_training_import_eligible": numeric_rows,
        "strict_supervised_rows": strict_rows,
        "claim_eligible_rows": claim_rows,
    }
    eligibility_flags = {
        "qualitative_feedback_eligible": qualitative_rows > 0,
        "numeric_training_import_eligible": numeric_rows > 0,
        "strict_supervised_rows": strict_rows > 0,
        "claim_eligible_rows": claim_rows > 0,
    }

    safe_for_training_import = not consistency_failures and numeric_rows > 0
    safe_for_model_claim = not consistency_failures and strict_rows > 0 and claim_rows > 0

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_reports": REPORTS,
        "missing_reports": missing_reports,
        "semantic_rows": semantic_rows,
        "qualitative_feedback_eligible": qualitative_rows,
        "numeric_training_import_eligible": numeric_rows,
        "strict_supervised_rows": strict_rows,
        "claim_eligible_rows": claim_rows,
        "eligibility_flags": eligibility_flags,
        "source_report_support": {
            "experiment_feedback_qualitative_training_eligible_rows": qualitative_rows,
            "experiment_feedback_numeric_training_eligible_rows": as_int(
                experiment_feedback.get("numeric_training_eligible_rows")
            ),
            "wet_lab_ready_for_training_import_rows": wet_lab_ready_values,
            "wet_lab_claim_eligible_rows_now": wet_lab_claim_values,
            "safe_training_entrypoint_rows": as_int(safe_entry.get("rows")),
            "safe_training_entrypoint_claim_eligible_rows": as_int(safe_entry.get("claim_eligible_rows")),
            "label_provenance_strict_rows": as_int(provenance.get("strict_rows")),
            "label_provenance_claim_eligible_rows": as_int(provenance.get("claim_eligible_rows")),
        },
        "consistency_failures": consistency_failures,
        "safe_for_training_import": safe_for_training_import,
        "safe_for_model_claim": safe_for_model_claim,
        "release_ready": False,
        "success": not consistency_failures,
        "policy": (
            "qualitative_feedback_eligible is not a supervised label import allowance. "
            "numeric_training_import_eligible requires numeric source support; strict_supervised_rows and "
            "claim_eligible_rows must be supported by safe_training_entrypoint_check and label_provenance_audit. "
            "This guard is read-only and never writes datasets/feedback or training labels."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "qualitative_feedback_eligible": qualitative_rows,
        "numeric_training_import_eligible": numeric_rows,
        "strict_supervised_rows": strict_rows,
        "claim_eligible_rows": claim_rows,
        "safe_for_training_import": safe_for_training_import,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not consistency_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
