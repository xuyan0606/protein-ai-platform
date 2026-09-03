#!/usr/bin/env python3
"""Validate feedback training import semantics fail closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GUARD = AI_ROOT / "reports" / "feedback_training_import_semantic_guard_report.json"
OUT = AI_ROOT / "reports" / "feedback_training_import_semantic_guard_validation_report.json"

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


def fail_if(
    condition: bool,
    failures: list[dict[str, Any]],
    check: str,
    observed: Any,
    expected: Any,
) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def positive_flag(guard: dict[str, Any], key: str) -> bool:
    flags = guard.get("eligibility_flags") if isinstance(guard.get("eligibility_flags"), dict) else {}
    return bool(flags.get(key))


def supported_counts(reports: dict[str, dict[str, Any]]) -> dict[str, int]:
    experiment_feedback = reports["experiment_feedback_intake_validation"]
    apply_plan = reports["wet_lab_mutant_library_feedback_intake_apply_plan"]
    safe_entry = reports["safe_training_entrypoint_check"]
    provenance = reports["label_provenance_audit"]

    safe_strict_rows = as_int(safe_entry.get("rows"))
    provenance_strict_rows = as_int(provenance.get("strict_rows"))
    safe_claim_rows = as_int(safe_entry.get("claim_eligible_rows"))
    provenance_claim_rows = as_int(provenance.get("claim_eligible_rows"))

    return {
        "qualitative_feedback_eligible": as_int(experiment_feedback.get("qualitative_training_eligible_rows")),
        "numeric_training_import_eligible": as_int(experiment_feedback.get("numeric_training_eligible_rows"))
        + as_int(apply_plan.get("ready_for_training_import_rows")),
        "strict_supervised_rows": safe_strict_rows if safe_strict_rows == provenance_strict_rows else 0,
        "claim_eligible_rows": safe_claim_rows if safe_claim_rows == provenance_claim_rows else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate feedback training import semantic guard")
    parser.add_argument("--guard", type=Path, default=GUARD)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    guard = load_json(args.guard)
    paths = {name: AI_ROOT / rel for name, rel in REPORTS.items()}
    reports = {name: load_json(path) for name, path in paths.items()}
    missing_reports = [REPORTS[name] for name, data in reports.items() if not data]
    failures: list[dict[str, Any]] = []

    if not guard:
        failures.append({"check": "guard_report_present", "observed": str(args.guard), "expected": "existing JSON report"})

    fail_if(bool(missing_reports), failures, "source_reports_present", missing_reports, [])

    source_counts = supported_counts(reports)
    observed_counts = {
        "qualitative_feedback_eligible": as_int(guard.get("qualitative_feedback_eligible")),
        "numeric_training_import_eligible": as_int(guard.get("numeric_training_import_eligible")),
        "strict_supervised_rows": as_int(guard.get("strict_supervised_rows")),
        "claim_eligible_rows": as_int(guard.get("claim_eligible_rows")),
    }
    semantic_rows = guard.get("semantic_rows") if isinstance(guard.get("semantic_rows"), dict) else {}

    for key, expected_count in source_counts.items():
        fail_if(
            observed_counts[key] != expected_count,
            failures,
            f"{key}_matches_source_support",
            observed_counts[key],
            expected_count,
        )
        fail_if(
            as_int(semantic_rows.get(key)) != expected_count,
            failures,
            f"semantic_rows_{key}_matches_source_support",
            semantic_rows.get(key),
            expected_count,
        )

    # Critical fail-closed checks: positive numeric/strict/claim signals require
    # independent source-report support and cannot be inferred from qualitative feedback.
    for key in ["numeric_training_import_eligible", "strict_supervised_rows", "claim_eligible_rows"]:
        source_supported = source_counts[key] > 0
        observed_positive = observed_counts[key] > 0
        flag_positive = positive_flag(guard, key)
        fail_if(
            observed_positive and not source_supported,
            failures,
            f"{key}_positive_only_when_source_supported",
            observed_counts[key],
            0,
        )
        fail_if(
            flag_positive and not source_supported,
            failures,
            f"{key}_flag_true_only_when_source_supported",
            flag_positive,
            False,
        )

    fail_if(
        positive_flag(guard, "qualitative_feedback_eligible") != (source_counts["qualitative_feedback_eligible"] > 0),
        failures,
        "qualitative_feedback_eligible_flag_matches_source_support",
        positive_flag(guard, "qualitative_feedback_eligible"),
        source_counts["qualitative_feedback_eligible"] > 0,
    )

    source_values = {
        "experiment_feedback_training_eligible_rows": as_int(
            reports["experiment_feedback_intake_validation"].get("training_eligible_rows")
        ),
        "experiment_feedback_qualitative_training_eligible_rows": as_int(
            reports["experiment_feedback_intake_validation"].get("qualitative_training_eligible_rows")
        ),
        "experiment_feedback_numeric_training_eligible_rows": as_int(
            reports["experiment_feedback_intake_validation"].get("numeric_training_eligible_rows")
        ),
        "authorization_ready_for_training_import_rows": as_int(
            reports["wet_lab_mutant_library_feedback_authorization_validation"].get("ready_for_training_import_rows")
        ),
        "preflight_ready_for_training_import_rows": as_int(
            reports["wet_lab_mutant_library_feedback_preflight"].get("ready_for_training_import_rows")
        ),
        "apply_plan_ready_for_training_import_rows": as_int(
            reports["wet_lab_mutant_library_feedback_intake_apply_plan"].get("ready_for_training_import_rows")
        ),
        "safe_training_entrypoint_rows": as_int(reports["safe_training_entrypoint_check"].get("rows")),
        "safe_training_entrypoint_claim_eligible_rows": as_int(
            reports["safe_training_entrypoint_check"].get("claim_eligible_rows")
        ),
        "label_provenance_strict_rows": as_int(reports["label_provenance_audit"].get("strict_rows")),
        "label_provenance_claim_eligible_rows": as_int(
            reports["label_provenance_audit"].get("claim_eligible_rows")
        ),
    }

    fail_if(
        source_values["authorization_ready_for_training_import_rows"]
        != source_values["preflight_ready_for_training_import_rows"]
        or source_values["preflight_ready_for_training_import_rows"]
        != source_values["apply_plan_ready_for_training_import_rows"],
        failures,
        "wet_lab_training_import_rows_consistent",
        {
            "authorization": source_values["authorization_ready_for_training_import_rows"],
            "preflight": source_values["preflight_ready_for_training_import_rows"],
            "apply_plan": source_values["apply_plan_ready_for_training_import_rows"],
        },
        "all equal",
    )

    fail_if(
        source_values["safe_training_entrypoint_rows"] != source_values["label_provenance_strict_rows"],
        failures,
        "strict_rows_supported_by_safe_entrypoint_and_label_provenance",
        {
            "safe_training_entrypoint_rows": source_values["safe_training_entrypoint_rows"],
            "label_provenance_strict_rows": source_values["label_provenance_strict_rows"],
        },
        "equal values",
    )
    fail_if(
        source_values["safe_training_entrypoint_claim_eligible_rows"]
        != source_values["label_provenance_claim_eligible_rows"],
        failures,
        "claim_rows_supported_by_safe_entrypoint_and_label_provenance",
        {
            "safe_training_entrypoint_claim_eligible_rows": source_values[
                "safe_training_entrypoint_claim_eligible_rows"
            ],
            "label_provenance_claim_eligible_rows": source_values["label_provenance_claim_eligible_rows"],
        },
        "equal values",
    )

    fail_if(
        guard.get("safe_for_training_import") is not (source_counts["numeric_training_import_eligible"] > 0 and not failures),
        failures,
        "safe_for_training_import_matches_numeric_source_support",
        guard.get("safe_for_training_import"),
        source_counts["numeric_training_import_eligible"] > 0 and not failures,
    )
    fail_if(
        guard.get("safe_for_model_claim") is not (
            source_counts["strict_supervised_rows"] > 0 and source_counts["claim_eligible_rows"] > 0 and not failures
        ),
        failures,
        "safe_for_model_claim_matches_strict_and_claim_source_support",
        guard.get("safe_for_model_claim"),
        source_counts["strict_supervised_rows"] > 0 and source_counts["claim_eligible_rows"] > 0 and not failures,
    )
    fail_if(guard.get("release_ready") is not False, failures, "release_ready_false", guard.get("release_ready"), False)
    fail_if(guard.get("policy") is None, failures, "policy_present", None, "non-empty policy text")

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_reports": {"guard": str(args.guard), **REPORTS},
        "source_values": source_values,
        "source_supported_counts": source_counts,
        "observed_guard_counts": observed_counts,
        "qualitative_feedback_eligible": observed_counts["qualitative_feedback_eligible"],
        "numeric_training_import_eligible": observed_counts["numeric_training_import_eligible"],
        "strict_supervised_rows": observed_counts["strict_supervised_rows"],
        "claim_eligible_rows": observed_counts["claim_eligible_rows"],
        "current_expected": {
            "qualitative_feedback_eligible": 1,
            "numeric_training_import_eligible": source_counts["numeric_training_import_eligible"],
            "strict_supervised_rows": 0,
            "claim_eligible_rows": 0,
            "numeric_training_import_source_supported": source_counts["numeric_training_import_eligible"] > 0,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        },
        "failures": failures,
        "success": not failures,
        "safe_for_training_import": guard.get("safe_for_training_import") is True and not failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Validation is fail-closed: numeric_training_import_eligible, strict_supervised_rows, "
            "and claim_eligible_rows may be positive or true only when the independent source reports support them. "
            "qualitative_training_eligible_rows must not be interpreted as supervised label import eligibility."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "qualitative_feedback_eligible": observed_counts["qualitative_feedback_eligible"],
        "numeric_training_import_eligible": observed_counts["numeric_training_import_eligible"],
        "strict_supervised_rows": observed_counts["strict_supervised_rows"],
        "claim_eligible_rows": observed_counts["claim_eligible_rows"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
