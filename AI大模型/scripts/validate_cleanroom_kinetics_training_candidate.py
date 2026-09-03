#!/usr/bin/env python3
"""Validate the clean-room kinetics candidate report fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT_REPORT = AI_ROOT / "reports" / "cleanroom_kinetics_training_candidate_report.json"
OUTPUT_REPORT = AI_ROOT / "reports" / "cleanroom_kinetics_training_candidate_validation_report.json"


def path_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def add_failure(
    failures: list[dict[str, Any]],
    check: str,
    observed: Any,
    expected: Any,
) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_input_profile(
    failures: list[dict[str, Any]],
    name: str,
    profile: Any,
) -> None:
    if not isinstance(profile, dict):
        failures.append({"check": f"{name}_profile_is_object", "observed": type(profile).__name__, "expected": "dict"})
        return
    add_failure(failures, f"{name}_parse_errors_empty", profile.get("parse_errors"), [])
    add_failure(failures, f"{name}_training_eligible_true_rows_zero", profile.get("training_eligible_true_rows"), 0)
    add_failure(
        failures,
        f"{name}_training_import_written_true_rows_zero",
        profile.get("training_import_written_true_rows"),
        0,
    )
    add_failure(
        failures,
        f"{name}_ready_for_training_import_true_rows_zero",
        profile.get("ready_for_training_import_true_rows"),
        0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a clean-room kinetics training candidate report")
    parser.add_argument("--report", type=Path, default=INPUT_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT_REPORT)
    args = parser.parse_args()

    report = load_json(args.report)
    failures: list[dict[str, Any]] = []
    if not report:
        failures.append({"check": "input_report_exists_and_is_object", "observed": "missing_or_invalid", "expected": "object"})
    else:
        add_failure(
            failures,
            "schema_version",
            report.get("schema_version"),
            "cleanroom_kinetics_training_candidate.v1",
        )
        add_failure(failures, "local_only", report.get("local_only"), True)
        add_failure(failures, "training_import_written_rows_zero", report.get("training_import_written_rows"), 0)
        add_failure(failures, "training_eligible_false", report.get("training_eligible"), False)
        add_failure(failures, "training_eligible_rows_zero", report.get("training_eligible_rows"), 0)
        add_failure(failures, "formal_training_rows_zero", report.get("formal_training_rows"), 0)
        add_failure(failures, "ready_for_training_import_rows_zero", report.get("ready_for_training_import_rows"), 0)
        add_failure(failures, "ready_for_training_import_false", report.get("ready_for_training_import"), False)
        add_failure(failures, "training_output_written_false", report.get("training_output_written"), False)
        add_failure(failures, "training_output_path_empty", report.get("training_output_path"), None)
        add_failure(failures, "safe_for_training_import_false", report.get("safe_for_training_import"), False)
        add_failure(failures, "safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
        add_failure(failures, "release_ready_false", report.get("release_ready"), False)

        source_contract = report.get("source_contract")
        expected_contract = {
            "normalizer_training_eligible_false": True,
            "normalizer_rows_training_eligible_zero": True,
            "summarizer_training_eligible_false": True,
            "summarizer_training_eligible_rows_zero": True,
        }
        if not isinstance(source_contract, dict):
            failures.append({"check": "source_contract_is_object", "observed": type(source_contract).__name__, "expected": "dict"})
        else:
            for key, expected in expected_contract.items():
                add_failure(failures, f"source_contract_{key}", source_contract.get(key), expected)

        source_scripts = report.get("source_scripts")
        if not isinstance(source_scripts, dict):
            failures.append({"check": "source_scripts_is_object", "observed": type(source_scripts).__name__, "expected": "dict"})
        else:
            for name in ("normalizer", "summarizer"):
                profile = source_scripts.get(name)
                if not isinstance(profile, dict):
                    failures.append({"check": f"{name}_source_profile_is_object", "observed": type(profile).__name__, "expected": "dict"})
                    continue
                add_failure(failures, f"{name}_source_exists", profile.get("exists"), True)
                checks = profile.get("checks")
                if not isinstance(checks, dict):
                    failures.append({"check": f"{name}_source_checks_is_object", "observed": type(checks).__name__, "expected": "dict"})
                    continue
                for check_name, observed in checks.items():
                    add_failure(failures, f"{name}_source_check_{check_name}", observed, True)

        validate_input_profile(failures, "normalized_input", report.get("normalized_input"))
        validate_input_profile(failures, "summary_input", report.get("summary_input"))
        add_failure(failures, "training_candidate_rows_non_negative", report.get("training_candidate_rows") >= 0 if isinstance(report.get("training_candidate_rows"), int) else False, True)
        add_failure(failures, "replicate_summary_candidate_rows_non_negative", report.get("replicate_summary_candidate_rows") >= 0 if isinstance(report.get("replicate_summary_candidate_rows"), int) else False, True)

    validation = {
        "schema_version": "cleanroom_kinetics_training_candidate_validation.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_report": path_text(args.report),
        "success": not failures,
        "training_import_written_rows": 0,
        "training_eligible": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "failures": failures,
        "policy": (
            "Validation is fail-closed. A passing validation confirms only "
            "that the candidate report preserves the training boundary; it "
            "does not authorize training import."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": validation["success"],
                "training_import_written_rows": validation["training_import_written_rows"],
                "training_eligible": validation["training_eligible"],
                "failures": len(failures),
                "output": path_text(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
