#!/usr/bin/env python3
"""Validate the training label import contract fail closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = AI_ROOT / "reports" / "training_label_import_contract_report.json"
OUT = AI_ROOT / "reports" / "training_label_import_contract_validation_report.json"

INPUTS = {
    "strict_supervised_jsonl": "datasets/curated/enzyme_mutation_supervised_repaired_verified.jsonl",
    "claim_eligible_jsonl": "datasets/curated/enzyme_mutation_supervised_claim_eligible.jsonl",
    "label_provenance_audit": "reports/label_provenance_audit_report.json",
    "fireprot_reviewed_import_candidate": "reports/fireprot_reviewed_import_candidate_report.json",
    "wet_lab_feedback_preflight": "reports/wet_lab_mutant_library_feedback_preflight_report.json",
    "feedback_training_import_semantic_guard": "reports/feedback_training_import_semantic_guard_report.json",
    "activity_risk_training_import_labels": "datasets/training/activity_risk_training_import_labels.jsonl",
    "activity_risk_training_import_label_validation": "reports/activity_risk_training_import_label_validation_report.json",
}

EXPECTED_CURRENT_STATE = {
    "strict_supervised_jsonl_rows": 0,
    "claim_eligible_jsonl_rows": 0,
    "label_provenance_strict_rows": 0,
    "label_provenance_claim_eligible_rows": 0,
    "fireprot_ready_for_training_import_rows": 0,
    "wet_lab_ready_for_training_import_rows": 0,
}

REQUIRED_EVIDENCE = ("reviewed", "source", "provenance", "authorization")
SENSITIVE_CONTRACT_SOURCES = {
    "strict_supervised_repaired_verified_jsonl",
    "claim_eligible_supervised_jsonl",
    "label_provenance_audit",
    "fireprot_reviewed_import_candidates",
    "wet_lab_feedback_preflight",
    "numeric_feedback_training_import_semantic_guard",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def count_jsonl_rows(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    rows = 0
    invalid = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows += 1
        try:
            json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
    return rows, invalid


def fail_if(
    condition: bool,
    failures: list[dict[str, Any]],
    check: str,
    observed: Any,
    expected: Any,
) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def source_contracts_by_id(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    contracts = contract.get("source_contracts")
    if not isinstance(contracts, list):
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for item in contracts:
        if isinstance(item, dict) and isinstance(item.get("source_id"), str):
            by_id[item["source_id"]] = item
    return by_id


def observed_state(paths: dict[str, Path], reports: dict[str, dict[str, Any]]) -> dict[str, int]:
    strict_rows, _strict_invalid = count_jsonl_rows(paths["strict_supervised_jsonl"])
    claim_rows, _claim_invalid = count_jsonl_rows(paths["claim_eligible_jsonl"])
    provenance = reports["label_provenance_audit"]
    fireprot = reports["fireprot_reviewed_import_candidate"]
    wet_lab = reports["wet_lab_feedback_preflight"]
    feedback = reports["feedback_training_import_semantic_guard"]
    return {
        "strict_supervised_jsonl_rows": strict_rows,
        "claim_eligible_jsonl_rows": claim_rows,
        "label_provenance_strict_rows": as_int(provenance.get("strict_rows")),
        "label_provenance_claim_eligible_rows": as_int(provenance.get("claim_eligible_rows")),
        "fireprot_ready_for_training_import_rows": as_int(fireprot.get("ready_for_training_import_rows")),
        "fireprot_reviewed_import_candidate_rows": as_int(fireprot.get("reviewed_import_candidate_rows")),
        "wet_lab_preflight_rows": as_int(wet_lab.get("preflight_rows")),
        "wet_lab_ready_for_training_import_rows": as_int(wet_lab.get("ready_for_training_import_rows")),
        "wet_lab_authorized_candidate_rows": as_int(wet_lab.get("authorized_candidate_rows")),
        "numeric_feedback_training_import_eligible_rows": as_int(
            feedback.get("numeric_training_import_eligible")
        ),
        "feedback_guard_strict_supervised_rows": as_int(feedback.get("strict_supervised_rows")),
        "feedback_guard_claim_eligible_rows": as_int(feedback.get("claim_eligible_rows")),
        "activity_risk_training_import_written_rows": count_jsonl_rows(
            paths["activity_risk_training_import_labels"]
        )[0],
        "activity_risk_training_import_validated_written_rows": as_int(
            reports["activity_risk_training_import_label_validation"].get("training_import_written_rows")
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate training label import contract report")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    contract = load_json(args.contract)
    paths = {name: AI_ROOT / rel for name, rel in INPUTS.items()}
    reports = {
        name: load_json(path)
        for name, path in paths.items()
        if name not in {
            "strict_supervised_jsonl",
            "claim_eligible_jsonl",
            "activity_risk_training_import_labels",
        }
    }

    failures: list[dict[str, Any]] = []
    fail_if(not contract, failures, "contract_report_present", str(args.contract), "existing JSON report")

    missing_inputs = [rel for name, rel in INPUTS.items() if not paths[name].exists()]
    empty_required_reports = [
        INPUTS[name]
        for name, data in reports.items()
        if not data
    ]
    fail_if(bool(missing_inputs), failures, "required_inputs_present", missing_inputs, [])
    fail_if(bool(empty_required_reports), failures, "required_json_reports_non_empty", empty_required_reports, [])

    strict_rows, strict_invalid = count_jsonl_rows(paths["strict_supervised_jsonl"])
    claim_rows, claim_invalid = count_jsonl_rows(paths["claim_eligible_jsonl"])
    fail_if(strict_invalid != 0, failures, "strict_jsonl_valid", strict_invalid, 0)
    fail_if(claim_invalid != 0, failures, "claim_eligible_jsonl_valid", claim_invalid, 0)

    current_state = observed_state(paths, reports)
    reported_state = contract.get("observed_current_state") if isinstance(contract.get("observed_current_state"), dict) else {}
    for key, value in current_state.items():
        fail_if(
            as_int(reported_state.get(key)) != value,
            failures,
            f"reported_{key}_matches_input",
            reported_state.get(key),
            value,
        )

    for key, expected in EXPECTED_CURRENT_STATE.items():
        fail_if(
            current_state.get(key) != expected,
            failures,
            f"current_{key}_is_expected_zero_state",
            current_state.get(key),
            expected,
        )

    fail_if(
        strict_rows != as_int(reports["label_provenance_audit"].get("strict_rows")),
        failures,
        "strict_jsonl_rows_match_label_provenance_audit",
        {"jsonl": strict_rows, "label_provenance_audit": reports["label_provenance_audit"].get("strict_rows")},
        "equal values",
    )
    fail_if(
        claim_rows != as_int(reports["label_provenance_audit"].get("claim_eligible_rows")),
        failures,
        "claim_jsonl_rows_match_label_provenance_audit",
        {
            "jsonl": claim_rows,
            "label_provenance_audit": reports["label_provenance_audit"].get("claim_eligible_rows"),
        },
        "equal values",
    )

    input_true_claim_release_flags = []
    for report_name, report in reports.items():
        for key in ("safe_for_model_claim", "release_ready"):
            if report.get(key) is True:
                input_true_claim_release_flags.append({"report": report_name, "field": key, "observed": True})
    fail_if(
        input_true_claim_release_flags,
        failures,
        "input_reports_have_no_true_model_claim_release_flags",
        input_true_claim_release_flags,
        [],
    )

    for key in ("safe_for_model_claim", "release_ready"):
        fail_if(contract.get(key) is True, failures, f"contract_{key}_false", True, False)

    totals = contract.get("contract_totals") if isinstance(contract.get("contract_totals"), dict) else {}
    expected_training_rows = current_state["numeric_feedback_training_import_eligible_rows"]
    expected_written_rows = current_state["activity_risk_training_import_written_rows"]
    fail_if(
        expected_written_rows != expected_training_rows,
        failures,
        "activity_risk_written_rows_match_numeric_eligible_rows",
        expected_written_rows,
        expected_training_rows,
    )
    fail_if(
        current_state["activity_risk_training_import_validated_written_rows"] != expected_written_rows,
        failures,
        "activity_risk_written_rows_match_validation_report",
        current_state["activity_risk_training_import_validated_written_rows"],
        expected_written_rows,
    )
    fail_if(as_int(totals.get("training_import_eligible_rows")) != expected_training_rows, failures, "contract_total_training_import_eligible_rows_matches_numeric_feedback", totals.get("training_import_eligible_rows"), expected_training_rows)
    fail_if(as_int(totals.get("counted_as_trainable_rows")) != expected_training_rows, failures, "contract_total_counted_as_trainable_rows_matches_numeric_feedback", totals.get("counted_as_trainable_rows"), expected_training_rows)
    fail_if(
        as_int(totals.get("training_import_eligible_label_sources")) != (1 if expected_training_rows > 0 else 0),
        failures,
        "contract_total_training_import_eligible_label_sources_matches_numeric_feedback",
        totals.get("training_import_eligible_label_sources"),
        1 if expected_training_rows > 0 else 0,
    )
    fail_if(
        contract.get("safe_for_training_import") is not (expected_training_rows > 0 and not missing_inputs),
        failures,
        "contract_safe_for_training_import_matches_numeric_feedback",
        contract.get("safe_for_training_import"),
        expected_training_rows > 0 and not missing_inputs,
    )
    fail_if(
        as_int(contract.get("training_import_written_rows")) != expected_written_rows,
        failures,
        "contract_training_import_written_rows_matches_artifact",
        contract.get("training_import_written_rows"),
        expected_written_rows,
    )
    fail_if(
        as_int(contract.get("training_import_validated_written_rows")) != expected_written_rows,
        failures,
        "contract_training_import_validated_written_rows_matches_artifact",
        contract.get("training_import_validated_written_rows"),
        expected_written_rows,
    )

    contracts = source_contracts_by_id(contract)
    fail_if(
        set(contracts) != SENSITIVE_CONTRACT_SOURCES,
        failures,
        "all_sensitive_sources_have_contracts",
        sorted(contracts),
        sorted(SENSITIVE_CONTRACT_SOURCES),
    )

    for source_id, item in contracts.items():
        counted_rows = as_int(item.get("counted_as_trainable_rows"))
        reported_rows = as_int(item.get("reported_ready_or_eligible_rows"))
        evidence = item.get("evidence_observed") if isinstance(item.get("evidence_observed"), dict) else {}
        missing_evidence = [key for key in REQUIRED_EVIDENCE if evidence.get(key) is not True]
        is_sensitive_source = source_id in SENSITIVE_CONTRACT_SOURCES
        if source_id == "numeric_feedback_training_import_semantic_guard":
            fail_if(item.get("training_import_eligible_label_source") is not (expected_training_rows > 0), failures, f"{source_id}_training_import_flag_matches_source", item.get("training_import_eligible_label_source"), expected_training_rows > 0)
            fail_if(counted_rows != expected_training_rows, failures, f"{source_id}_counted_trainable_rows_match_source", counted_rows, expected_training_rows)
        else:
            fail_if(item.get("training_import_eligible_label_source") is True, failures, f"{source_id}_not_marked_training_import_eligible", True, False)
            fail_if(counted_rows != 0, failures, f"{source_id}_counted_trainable_rows_zero", counted_rows, 0)
        fail_if(
            is_sensitive_source and (counted_rows > 0 or item.get("training_import_eligible_label_source") is True) and missing_evidence,
            failures,
            f"{source_id}_positive_trainable_count_requires_all_evidence",
            {"counted_rows": counted_rows, "missing_evidence": missing_evidence},
            {"counted_rows": 0, "missing_evidence": []},
        )
        fail_if(
            is_sensitive_source and reported_rows > 0 and counted_rows > 0 and missing_evidence,
            failures,
            f"{source_id}_reported_ready_rows_not_trainable_without_all_evidence",
            {"reported_ready_or_eligible_rows": reported_rows, "missing_evidence": missing_evidence},
            {"reported_ready_or_eligible_rows": 0, "missing_evidence": []},
        )

    source_expected_rows = {
        "strict_supervised_repaired_verified_jsonl": strict_rows,
        "claim_eligible_supervised_jsonl": claim_rows,
        "label_provenance_audit": current_state["label_provenance_strict_rows"]
        + current_state["label_provenance_claim_eligible_rows"],
        "fireprot_reviewed_import_candidates": current_state["fireprot_reviewed_import_candidate_rows"],
        "wet_lab_feedback_preflight": current_state["wet_lab_preflight_rows"],
        "numeric_feedback_training_import_semantic_guard": current_state[
            "numeric_feedback_training_import_eligible_rows"
        ],
    }
    source_expected_ready_rows = {
        "strict_supervised_repaired_verified_jsonl": strict_rows,
        "claim_eligible_supervised_jsonl": claim_rows,
        "label_provenance_audit": current_state["label_provenance_claim_eligible_rows"],
        "fireprot_reviewed_import_candidates": current_state["fireprot_ready_for_training_import_rows"],
        "wet_lab_feedback_preflight": current_state["wet_lab_ready_for_training_import_rows"],
        "numeric_feedback_training_import_semantic_guard": current_state[
            "numeric_feedback_training_import_eligible_rows"
        ],
    }
    for source_id, expected_rows in source_expected_rows.items():
        item = contracts.get(source_id, {})
        fail_if(
            as_int(item.get("observed_rows")) != expected_rows,
            failures,
            f"{source_id}_observed_rows_match_source",
            item.get("observed_rows"),
            expected_rows,
        )
        fail_if(
            as_int(item.get("reported_ready_or_eligible_rows")) != source_expected_ready_rows[source_id],
            failures,
            f"{source_id}_ready_rows_match_source",
            item.get("reported_ready_or_eligible_rows"),
            source_expected_ready_rows[source_id],
        )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "contract": str(args.contract),
        "checked_inputs": INPUTS,
        "current_state": current_state,
        "expected_current_state": EXPECTED_CURRENT_STATE,
        "contract_totals": totals,
        "training_import_written_rows": expected_written_rows,
        "input_true_claim_release_flags": input_true_claim_release_flags,
        "failures": failures,
        "success": not failures,
        "safe_for_training_import": expected_training_rows > 0 and not missing_inputs,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Validation is fail-closed: any strict, claim-eligible, reviewed import, preflight, "
            "or feedback row counted as trainable must have reviewed/source/provenance/authorization "
            "evidence. safe_for_training_import may become true only for numeric feedback rows that "
            "match the semantic guard; safe_for_model_claim and release_ready must remain false."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "strict_supervised_rows": current_state["strict_supervised_jsonl_rows"],
        "claim_eligible_rows": current_state["claim_eligible_jsonl_rows"],
        "fireprot_ready_for_training_import_rows": current_state["fireprot_ready_for_training_import_rows"],
        "wet_lab_preflight_rows": current_state["wet_lab_preflight_rows"],
        "numeric_feedback_training_import_eligible_rows": current_state[
            "numeric_feedback_training_import_eligible_rows"
        ],
        "training_import_eligible_rows": as_int(totals.get("training_import_eligible_rows")),
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
