#!/usr/bin/env python3
"""Validate the wet-lab feedback authorization consumption contract fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = AI_ROOT / "reports" / "wet_lab_feedback_authorization_contract_report.json"
DEFAULT_OUTPUT = AI_ROOT / "reports" / "wet_lab_feedback_authorization_contract_validation_report.json"

REPORTS = {
    "candidate_report": "reports/wet_lab_mutant_library_feedback_candidate_report.json",
    "authorization_report": "reports/wet_lab_mutant_library_feedback_authorization_validation_report.json",
    "preflight_report": "reports/wet_lab_mutant_library_feedback_preflight_report.json",
    "apply_plan_report": "reports/wet_lab_mutant_library_feedback_intake_apply_plan_report.json",
    "duplicate_audit_report": "reports/wet_lab_feedback_apply_duplicate_audit_report.json",
    "duplicate_audit_validation_report": "reports/wet_lab_feedback_apply_duplicate_audit_validation_report.json",
    "semantic_guard_report": "reports/feedback_training_import_semantic_guard_report.json",
}

JSONL = {
    "candidate_rows": "datasets/feedback/wet_lab_mutant_library_feedback_candidates.jsonl",
    "authorization_rows": "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
    "preflight_rows": "datasets/feedback/wet_lab_mutant_library_feedback_preflight.jsonl",
    "apply_plan_rows": "datasets/feedback/wet_lab_mutant_library_feedback_intake_apply_plan.jsonl",
    "duplicate_audit_rows": "datasets/feedback/wet_lab_feedback_apply_duplicate_audit.jsonl",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def display_path(path: Path) -> str:
    if path.is_absolute():
        try:
            return str(path.relative_to(AI_ROOT))
        except ValueError:
            return str(path)
    return str(path)


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    nonempty = 0
    invalid = 0
    if not path.exists():
        return rows, nonempty, invalid
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        nonempty += 1
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if not isinstance(value, dict):
            invalid += 1
            continue
        rows.append(value)
    return rows, nonempty, invalid


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


def truthy_key_paths(value: Any, wanted: set[str], path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key in wanted and child is True:
                found.append(child_path)
            found.extend(truthy_key_paths(child, wanted, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(truthy_key_paths(child, wanted, f"{path}[{index}]"))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab feedback authorization consumption contract")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    contract = load_json(args.report)
    report_paths = {name: AI_ROOT / path for name, path in REPORTS.items()}
    jsonl_paths = {name: AI_ROOT / path for name, path in JSONL.items()}
    reports = {name: load_json(path) for name, path in report_paths.items()}
    jsonl_data = {name: load_jsonl(path) for name, path in jsonl_paths.items()}
    rows = {name: value[0] for name, value in jsonl_data.items()}
    line_counts = {name: value[1] for name, value in jsonl_data.items()}
    invalid_counts = {name: value[2] for name, value in jsonl_data.items()}
    failures: list[dict[str, Any]] = []

    candidate_report = reports["candidate_report"]
    authorization_report = reports["authorization_report"]
    preflight_report = reports["preflight_report"]
    apply_plan_report = reports["apply_plan_report"]
    duplicate_audit_report = reports["duplicate_audit_report"]
    duplicate_audit_validation_report = reports["duplicate_audit_validation_report"]
    semantic_guard_report = reports["semantic_guard_report"]
    source_values = {
        "wet_lab_candidate_rows": as_int(candidate_report.get("candidate_rows")),
        "numeric_training_candidate_rows": as_int(candidate_report.get("numeric_training_candidate_rows")),
        "authorization_rows": as_int(authorization_report.get("authorization_rows")),
        "authorized_rows": as_int(authorization_report.get("authorized_rows")),
        "preflight_rows": as_int(preflight_report.get("preflight_rows")),
        "apply_plan_rows": as_int(apply_plan_report.get("apply_plan_rows")),
        "ready_for_training_import_rows": max(
            as_int(authorization_report.get("ready_for_training_import_rows")),
            as_int(preflight_report.get("ready_for_training_import_rows")),
            as_int(apply_plan_report.get("ready_for_training_import_rows")),
        ),
        "claim_eligible_rows_now": max(
            as_int(authorization_report.get("claim_eligible_rows_now")),
            as_int(preflight_report.get("claim_eligible_rows_now")),
            as_int(apply_plan_report.get("claim_eligible_rows_now")),
        ),
    }

    fail_if(not contract, failures, "contract_report_present", str(args.report), "existing JSON report")
    fail_if(bool([name for name, path in report_paths.items() if not path.exists()]), failures, "source_reports_present", [str(path) for path in report_paths.values() if not path.exists()], [])
    fail_if(bool([name for name, path in jsonl_paths.items() if not path.exists()]), failures, "source_jsonl_present", [str(path) for path in jsonl_paths.values() if not path.exists()], [])

    fail_if(source_values["wet_lab_candidate_rows"] != 445, failures, "source_wet_lab_candidate_rows_current", source_values["wet_lab_candidate_rows"], 445)
    fail_if(source_values["numeric_training_candidate_rows"] != 12, failures, "source_numeric_training_candidate_rows_current", source_values["numeric_training_candidate_rows"], 12)
    for key in (
        "authorization_rows",
        "authorized_rows",
        "preflight_rows",
        "apply_plan_rows",
        "ready_for_training_import_rows",
        "claim_eligible_rows_now",
    ):
        observed = (contract.get("source_values") or {}).get(key)
        fail_if(observed != source_values[key], failures, f"contract_{key}_matches_sources", observed, source_values[key])

    expected_jsonl_rows = {
        "candidate_rows": source_values["wet_lab_candidate_rows"],
        "authorization_rows": source_values["authorization_rows"],
        "preflight_rows": source_values["preflight_rows"],
        "apply_plan_rows": source_values["apply_plan_rows"],
    }
    for key, expected in expected_jsonl_rows.items():
        fail_if(line_counts[key] != expected, failures, f"{key}_jsonl_row_count", line_counts[key], expected)
        fail_if(invalid_counts[key] != 0, failures, f"{key}_jsonl_valid", invalid_counts[key], 0)
        profile = (contract.get("jsonl_rows") or {}).get(key) or {}
        fail_if(profile.get("rows") != line_counts[key], failures, f"{key}_profile_rows_match", profile.get("rows"), line_counts[key])
        fail_if(profile.get("invalid_json_rows") != invalid_counts[key], failures, f"{key}_profile_invalid_rows_match", profile.get("invalid_json_rows"), invalid_counts[key])

    candidate_rows = rows["candidate_rows"]
    numeric_candidate_ids = {
        str(row.get("feedback_candidate_id"))
        for row in candidate_rows
        if row.get("numeric_training_candidate") is True
    }
    fail_if(len(candidate_rows) != 445, failures, "candidate_jsonl_rows_445", len(candidate_rows), 445)
    fail_if(len(numeric_candidate_ids) != 12, failures, "numeric_candidate_ids_12", len(numeric_candidate_ids), 12)
    fail_if(
        any(row.get("ready_for_feedback_intake") is True for row in candidate_rows),
        failures,
        "candidates_not_ready_for_feedback_intake",
        True,
        False,
    )
    fail_if(
        any(row.get("claim_eligible_now") is True for row in candidate_rows),
        failures,
        "candidates_not_claim_eligible",
        True,
        False,
    )

    authorization_rows = rows["authorization_rows"]
    authorized_ids = {
        str(row.get("feedback_candidate_id"))
        for row in authorization_rows
        if row.get("authorization_decision") == "approved_for_feedback_intake"
        or row.get("authorized_for_feedback_intake") is True
    }
    valid_authorized_rows = as_int(authorization_report.get("authorized_rows"))
    fail_if(len(authorization_rows) != source_values["authorization_rows"], failures, "authorization_report_matches_jsonl", len(authorization_rows), source_values["authorization_rows"])
    fail_if(valid_authorized_rows > len(authorization_rows), failures, "authorized_rows_not_invented_from_candidates", valid_authorized_rows, f"<= {len(authorization_rows)}")
    fail_if(valid_authorized_rows > len(numeric_candidate_ids), failures, "authorized_rows_not_greater_than_numeric_candidates", valid_authorized_rows, f"<= {len(numeric_candidate_ids)}")
    fail_if(len(authorized_ids) != valid_authorized_rows, failures, "authorized_ids_match_authorized_rows", len(authorized_ids), valid_authorized_rows)
    fail_if(bool(authorized_ids - numeric_candidate_ids), failures, "authorized_ids_are_numeric_candidates", sorted(authorized_ids - numeric_candidate_ids), [])
    fail_if(valid_authorized_rows > source_values["authorization_rows"], failures, "authorized_rows_supported_by_authorization_rows", valid_authorized_rows, f"<= {source_values['authorization_rows']}")

    preflight_rows = rows["preflight_rows"]
    apply_plan_rows = rows["apply_plan_rows"]
    fail_if(len(preflight_rows) > valid_authorized_rows, failures, "preflight_rows_not_greater_than_authorized_rows", len(preflight_rows), f"<= {valid_authorized_rows}")
    fail_if(len(apply_plan_rows) > valid_authorized_rows, failures, "apply_plan_rows_not_greater_than_authorized_rows", len(apply_plan_rows), f"<= {valid_authorized_rows}")
    fail_if(source_values["preflight_rows"] > source_values["authorized_rows"], failures, "reported_preflight_not_greater_than_authorized", source_values["preflight_rows"], f"<= {source_values['authorized_rows']}")
    fail_if(source_values["apply_plan_rows"] > source_values["authorized_rows"], failures, "reported_apply_plan_not_greater_than_authorized", source_values["apply_plan_rows"], f"<= {source_values['authorized_rows']}")
    fail_if(
        line_counts["duplicate_audit_rows"] != source_values["preflight_rows"],
        failures,
        "duplicate_audit_rows_match_preflight",
        line_counts["duplicate_audit_rows"],
        source_values["preflight_rows"],
    )
    fail_if(
        as_int(duplicate_audit_report.get("safe_to_append_rows")) != 0,
        failures,
        "duplicate_audit_safe_to_append_rows_zero",
        duplicate_audit_report.get("safe_to_append_rows"),
        0,
    )
    fail_if(
        as_int(duplicate_audit_report.get("training_import_eligible_from_apply_plan_rows")) != 0,
        failures,
        "duplicate_audit_training_import_rows_zero",
        duplicate_audit_report.get("training_import_eligible_from_apply_plan_rows"),
        0,
    )
    fail_if(
        duplicate_audit_validation_report.get("success") is not True,
        failures,
        "duplicate_audit_validation_success",
        duplicate_audit_validation_report.get("success"),
        True,
    )

    for name, source in reports.items():
        paths = truthy_key_paths(
            source,
            {"ready_for_training_import", "claim_eligible", "safe_for_model_claim", "release_ready"},
            name,
        )
        fail_if(bool(paths), failures, f"{name}_forbidden_positive_flags", paths, [])
    paths = truthy_key_paths(
        contract,
        {"ready_for_training_import", "claim_eligible", "safe_for_model_claim", "release_ready"},
        "contract",
    )
    fail_if(bool(paths), failures, "contract_forbidden_positive_flags", paths, [])

    fail_if(
        as_int(semantic_guard_report.get("numeric_training_import_eligible")) > valid_authorized_rows,
        failures,
        "semantic_guard_numeric_import_not_greater_than_authorized",
        semantic_guard_report.get("numeric_training_import_eligible"),
        f"<= {valid_authorized_rows}",
    )
    fail_if(as_int(semantic_guard_report.get("claim_eligible_rows")) != 0, failures, "semantic_guard_claim_rows_zero", semantic_guard_report.get("claim_eligible_rows"), 0)
    fail_if(semantic_guard_report.get("safe_for_model_claim") is not False, failures, "semantic_guard_model_claim_false", semantic_guard_report.get("safe_for_model_claim"), False)
    fail_if(semantic_guard_report.get("release_ready") is not False, failures, "semantic_guard_release_ready_false", semantic_guard_report.get("release_ready"), False)

    fail_if(contract.get("success") is not True, failures, "contract_success_true", contract.get("success"), True)
    fail_if(contract.get("source_state_matches_expected") is not True, failures, "contract_source_state_matches_expected", contract.get("source_state_matches_expected"), True)
    fail_if((contract.get("safety_flags") or {}).get("safe_for_model_claim") is not False, failures, "contract_safe_for_model_claim_false", (contract.get("safety_flags") or {}).get("safe_for_model_claim"), False)
    fail_if((contract.get("safety_flags") or {}).get("release_ready") is not False, failures, "contract_release_ready_false", (contract.get("safety_flags") or {}).get("release_ready"), False)

    validation = {
        "report_id": "wet_lab_feedback_authorization_contract_validation_report",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "checked_report": display_path(args.report),
        "checked_source_reports": REPORTS,
        "checked_source_jsonl": JSONL,
        "current_state": source_values,
        "candidate_rows": len(candidate_rows),
        "jsonl_row_counts": line_counts,
        "candidate_jsonl_rows": line_counts["candidate_rows"],
        "authorization_jsonl_rows": line_counts["authorization_rows"],
        "preflight_jsonl_rows": line_counts["preflight_rows"],
        "apply_plan_jsonl_rows": line_counts["apply_plan_rows"],
        "jsonl_invalid_row_counts": invalid_counts,
        "numeric_training_candidate_rows": len(numeric_candidate_ids),
        "authorization_rows": len(authorization_rows),
        "authorized_rows": valid_authorized_rows,
        "preflight_rows": len(preflight_rows),
        "apply_plan_rows": len(apply_plan_rows),
        "ready_for_training_import_rows": source_values["ready_for_training_import_rows"],
        "claim_eligible_rows_now": source_values["claim_eligible_rows_now"],
        "duplicate_audit_already_represented_rows": as_int(duplicate_audit_report.get("already_represented_rows")),
        "duplicate_audit_new_feedback_only_rows": as_int(duplicate_audit_report.get("new_feedback_only_rows")),
        "duplicate_audit_safe_to_append_rows": as_int(duplicate_audit_report.get("safe_to_append_rows")),
        "duplicate_audit_training_import_rows": as_int(
            duplicate_audit_report.get("training_import_eligible_from_apply_plan_rows")
        ),
        "negative_protection_checks": {
            "authorizations_are_explicit_rows": valid_authorized_rows <= len(authorization_rows),
            "numeric_candidates_not_counted_as_authorized": valid_authorized_rows <= len(authorization_rows),
            "preflight_not_greater_than_authorized": len(preflight_rows) <= valid_authorized_rows,
            "apply_plan_not_greater_than_authorized": len(apply_plan_rows) <= valid_authorized_rows,
            "duplicate_audit_blocks_reappend": as_int(duplicate_audit_report.get("safe_to_append_rows")) == 0,
            "positive_ready_claim_or_release_flags_fail_validation": True,
        },
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Fail-closed validation: candidate presence and numeric candidate counts never authorize consumption. "
            "Any positive ready_for_training_import, claim_eligible, safe_for_model_claim, or release_ready signal, "
            "any preflight/apply count above authorized rows, or any authorization count unsupported by actual "
            "authorization rows fails validation."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "numeric_training_candidate_rows": len(numeric_candidate_ids),
        "authorization_rows": len(authorization_rows),
        "authorized_rows": valid_authorized_rows,
        "preflight_rows": len(preflight_rows),
        "apply_plan_rows": len(apply_plan_rows),
        "ready_for_training_import_rows": source_values["ready_for_training_import_rows"],
        "claim_eligible_rows_now": source_values["claim_eligible_rows_now"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
