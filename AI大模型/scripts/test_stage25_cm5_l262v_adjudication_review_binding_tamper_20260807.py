#!/usr/bin/env python3
"""Run isolated tamper regressions for CM5 adjudication review binding."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = AI_ROOT / "scripts/validate_stage25_cm5_l262v_adjudication_decision_intake_20260807.py"
REAL_DECISION_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_adjudication_decisions.local.json"
REAL_REVIEW_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_reviews.local.json"
REAL_RECEIPT_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_receipts.local.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_review_binding_tamper_regression_20260807.json"
PACKET_ID = "stage25_cm5_l262v_discrepancy_adjudication_20260807"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_validator():
    spec = importlib.util.spec_from_file_location("cm5_adjudication_review_binding_tamper", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def decision_document(evidence_artifacts: list[dict], outcome: str) -> dict:
    return {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_decision_intake",
        "stage": 25,
        "packet_id": PACKET_ID,
        "decisions": [{
            "decision_id": "tamper-regression-only-decision",
            "packet_id": PACKET_ID,
            "adjudication_decision": outcome,
            "reviewer": "tamper_regression_fixture",
            "reviewed_at": "2026-08-07T00:00:00Z",
            "reviewed_source_locator": "isolated-tamper-regression-fixture",
            "decision_basis": "contract tamper regression only; not a scientific adjudication",
            "review_notes": "No production review or decision is written.",
            "evidence_artifacts": evidence_artifacts,
            "formal_decision_authorized": False,
            "discrepancy_resolved": False,
            "complete_composition_unambiguous": False,
            "reviewed_extraction_completed": False,
            "ready_for_sqlite_apply": False,
            "apply_executed": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        }],
        "policy": "Empty decisions keep formal review, SQLite, and release closed.",
    }


def run_case(module, temp_root: Path, case_id: str, document: dict) -> tuple[int, dict]:
    input_path = temp_root / f"{case_id}.input.json"
    output_path = temp_root / f"{case_id}.report.json"
    write_json(input_path, document)
    module.INPUT = input_path
    module.OUTPUT = output_path
    with contextlib.redirect_stdout(io.StringIO()):
        return_code = module.main()
    return return_code, json.loads(output_path.read_text(encoding="utf-8"))


def failure_checks(report: dict) -> list[str]:
    return [str(item.get("check")) for item in report.get("failures", []) if isinstance(item, dict)]


def main() -> int:
    real_paths = [REAL_DECISION_INPUT, REAL_REVIEW_INPUT, REAL_RECEIPT_INPUT]
    real_before = {str(path): sha256_file(path) for path in real_paths}
    module = load_validator()
    artifact_paths = [
        VALIDATOR_PATH,
        AI_ROOT / "scripts/validate_stage25_cm5_l262v_external_evidence_reviews_20260807.py",
        AI_ROOT / "scripts/test_stage25_cm5_l262v_adjudication_review_binding_20260807.py",
    ]
    relative_paths = [str(path.relative_to(AI_ROOT)) for path in artifact_paths]
    artifact_shas = [sha256_file(path) for path in artifact_paths]

    with tempfile.TemporaryDirectory(prefix="cm5_adjudication_review_binding_tamper_") as temp_dir:
        temp_root = Path(temp_dir)
        review_input = temp_root / "reviews.json"
        receipt_input = temp_root / "receipts.json"
        review_validation = temp_root / "review-validation.json"
        write_json(review_input, {"reviews": ["isolated-tamper-regression-fixture"]})
        write_json(receipt_input, {"receipts": ["isolated-tamper-regression-fixture"]})
        records = [
            {
                "review_id": f"accepted-review-{index}",
                "receipt_id": f"receipt-{index}",
                "request_id": f"request-{index}",
                "slot_id": ["cm5_codon262_primary_raw_trace", "cm5_sequence_pdb_version_reconciliation", "cm5_complete_construct_record"][index - 1],
                "reviewer": f"evidence_reviewer_{index}",
                "reviewed_at": "2026-08-07T00:00:00Z",
                "reviewed_source_locator": "isolated-tamper-regression-fixture",
                "canonical_path": relative_path,
                "artifact_sha256": artifact_sha,
                "valid": True,
                "scientific_sufficiency": "accepted_for_adjudication",
                "supports_adjudication_options": ["reject_L262V_as_sequence_artifact"],
                "errors": [],
            }
            for index, (relative_path, artifact_sha) in enumerate(zip(relative_paths, artifact_shas), 1)
        ]
        write_json(review_validation, {
            "intake_valid": True,
            "review_input_sha256": sha256_file(review_input),
            "receipt_input_sha256": sha256_file(receipt_input),
            "records": records,
        })
        module.REVIEW_INPUT = review_input
        module.RECEIPT_INPUT = receipt_input
        module.REVIEW_VALIDATION = review_validation

        reject_classes = ["raw_trace_or_independent_resequencing", "sequence_pdb_reconciliation"]
        reject_artifacts = [
            {
                "evidence_class": evidence_class,
                "relative_path": relative_paths[index],
                "review_id": records[index]["review_id"],
                "sha256": artifact_shas[index],
            }
            for index, evidence_class in enumerate(reject_classes)
        ]

        forged_sha_artifacts = [dict(row) for row in reject_artifacts]
        forged_sha_artifacts[0]["sha256"] = "0" * 64
        forged_rc, forged_report = run_case(
            module,
            temp_root,
            "forged_artifact_sha",
            decision_document(forged_sha_artifacts, "reject_L262V_as_sequence_artifact"),
        )

        cross_bound_artifacts = [dict(row) for row in reject_artifacts]
        cross_bound_artifacts[0]["review_id"] = records[1]["review_id"]
        cross_bound_artifacts[1]["review_id"] = records[0]["review_id"]
        cross_rc, cross_report = run_case(
            module,
            temp_root,
            "cross_bound_review_paths",
            decision_document(cross_bound_artifacts, "reject_L262V_as_sequence_artifact"),
        )

        confirm_classes = [
            "raw_trace_or_independent_resequencing",
            "sequence_pdb_reconciliation",
            "complete_construct_record",
        ]
        unsupported_artifacts = [
            {
                "evidence_class": evidence_class,
                "relative_path": relative_paths[index],
                "review_id": records[index]["review_id"],
                "sha256": artifact_shas[index],
            }
            for index, evidence_class in enumerate(confirm_classes)
        ]
        unsupported_rc, unsupported_report = run_case(
            module,
            temp_root,
            "unsupported_adjudication_option",
            decision_document(unsupported_artifacts, "confirm_L262V_in_CM5_construct"),
        )

        slot_mismatch_artifacts = [dict(row) for row in reject_artifacts]
        slot_mismatch_artifacts[0]["evidence_class"] = "sequence_pdb_reconciliation"
        slot_mismatch_rc, slot_mismatch_report = run_case(
            module,
            temp_root,
            "slot_evidence_class_mismatch",
            decision_document(slot_mismatch_artifacts, "reject_L262V_as_sequence_artifact"),
        )

        invalid_timestamp_document = decision_document(reject_artifacts, "reject_L262V_as_sequence_artifact")
        invalid_timestamp_document["decisions"][0]["reviewed_at"] = "2026-08-07 00:00:00"
        invalid_timestamp_rc, invalid_timestamp_report = run_case(
            module,
            temp_root,
            "invalid_decision_timestamp",
            invalid_timestamp_document,
        )

    forged_checks = failure_checks(forged_report)
    cross_checks = failure_checks(cross_report)
    unsupported_checks = failure_checks(unsupported_report)
    slot_mismatch_checks = failure_checks(slot_mismatch_report)
    invalid_timestamp_checks = failure_checks(invalid_timestamp_report)
    cases = [
        {
            "case_id": "forged_artifact_sha_rejected",
            "observed_return_code": forged_rc,
            "sha256_live_failure_present": any(check.endswith("sha256_live") for check in forged_checks),
            "sha256_review_match_failure_present": any(check.endswith("sha256_review_match") for check in forged_checks),
            "passed": forged_rc == 1
            and forged_report.get("intake_valid") is False
            and any(check.endswith("sha256_live") for check in forged_checks)
            and any(check.endswith("sha256_review_match") for check in forged_checks),
        },
        {
            "case_id": "cross_bound_review_paths_rejected",
            "observed_return_code": cross_rc,
            "relative_path_review_match_failure_present": any(check.endswith("relative_path_review_match") for check in cross_checks),
            "sha256_review_match_failure_present": any(check.endswith("sha256_review_match") for check in cross_checks),
            "passed": cross_rc == 1
            and cross_report.get("intake_valid") is False
            and any(check.endswith("relative_path_review_match") for check in cross_checks)
            and any(check.endswith("sha256_review_match") for check in cross_checks),
        },
        {
            "case_id": "unsupported_adjudication_option_rejected",
            "observed_return_code": unsupported_rc,
            "review_supports_decision_failure_present": any(check.endswith("review_supports_decision") for check in unsupported_checks),
            "passed": unsupported_rc == 1
            and unsupported_report.get("intake_valid") is False
                and any(check.endswith("review_supports_decision") for check in unsupported_checks),
        },
        {
            "case_id": "slot_evidence_class_mismatch_rejected",
            "observed_return_code": slot_mismatch_rc,
            "slot_class_failure_present": any(check.endswith("evidence_class_slot_compatible") for check in slot_mismatch_checks),
            "passed": slot_mismatch_rc == 1
            and slot_mismatch_report.get("intake_valid") is False
            and any(check.endswith("evidence_class_slot_compatible") for check in slot_mismatch_checks),
        },
        {
            "case_id": "invalid_decision_timestamp_rejected",
            "observed_return_code": invalid_timestamp_rc,
            "reviewed_at_utc_failure_present": any(check.endswith("reviewed_at_utc") for check in invalid_timestamp_checks),
            "passed": invalid_timestamp_rc == 1
            and invalid_timestamp_report.get("intake_valid") is False
            and any(check.endswith("reviewed_at_utc") for check in invalid_timestamp_checks),
        },
    ]
    real_after = {str(path): sha256_file(path) for path in real_paths}
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_review_binding_tamper_regression",
        "stage": 25,
        "success": all(case["passed"] for case in cases) and real_before == real_after,
        "case_rows": len(cases),
        "passed_rows": sum(case["passed"] for case in cases),
        "failed_rows": sum(not case["passed"] for case in cases),
        "forged_sha_rejected_rows": int(cases[0]["passed"]),
        "cross_bound_review_rejected_rows": int(cases[1]["passed"]),
        "unsupported_option_rejected_rows": int(cases[2]["passed"]),
        "slot_class_mismatch_rejected_rows": int(cases[3]["passed"]),
        "invalid_decision_timestamp_rejected_rows": int(cases[4]["passed"]),
        "real_decision_input_mutated": real_before[str(REAL_DECISION_INPUT)] != real_after[str(REAL_DECISION_INPUT)],
        "real_review_input_mutated": real_before[str(REAL_REVIEW_INPUT)] != real_after[str(REAL_REVIEW_INPUT)],
        "real_receipt_input_mutated": real_before[str(REAL_RECEIPT_INPUT)] != real_after[str(REAL_RECEIPT_INPUT)],
        "formal_decision_rows_written": 0,
        "discrepancy_resolved": False,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "cases": cases,
        "policy": "Temporary isolated tamper regression only. Synthetic accepted reviews do not alter real review, receipt, decision, or evidence inputs and do not adjudicate CM5 L262V.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "success": report["success"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
    }, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
