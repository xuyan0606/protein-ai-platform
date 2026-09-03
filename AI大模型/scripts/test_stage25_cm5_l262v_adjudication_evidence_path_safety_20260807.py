#!/usr/bin/env python3
"""Run isolated path-safety regressions for CM5 adjudication evidence."""

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
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_evidence_path_safety_regression_20260807.json"
PACKET_ID = "stage25_cm5_l262v_discrepancy_adjudication_20260807"
OUTCOME = "reject_L262V_as_sequence_artifact"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_validator():
    spec = importlib.util.spec_from_file_location("cm5_adjudication_evidence_path_safety", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decision_document(evidence_artifacts: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_decision_intake",
        "stage": 25,
        "packet_id": PACKET_ID,
        "decisions": [{
            "decision_id": "path-safety-regression-only-decision",
            "packet_id": PACKET_ID,
            "adjudication_decision": OUTCOME,
            "reviewer": "path_safety_regression_fixture",
            "reviewed_at": "2026-08-07T00:00:00Z",
            "reviewed_source_locator": "isolated-path-safety-regression-fixture",
            "decision_basis": "path-safety contract regression only; not a scientific adjudication",
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


def checks(report: dict) -> list[str]:
    return [str(item.get("check")) for item in report.get("failures", []) if isinstance(item, dict)]


def main() -> int:
    real_paths = [REAL_DECISION_INPUT, REAL_REVIEW_INPUT, REAL_RECEIPT_INPUT]
    real_before = {str(path): sha256_file(path) for path in real_paths}
    module = load_validator()
    artifact_paths = [
        VALIDATOR_PATH,
        AI_ROOT / "scripts/validate_stage25_cm5_l262v_external_evidence_reviews_20260807.py",
    ]
    relative_paths = [str(path.relative_to(AI_ROOT)) for path in artifact_paths]
    artifact_shas = [sha256_file(path) for path in artifact_paths]

    with tempfile.TemporaryDirectory(prefix="cm5_adjudication_evidence_path_safety_") as temp_dir:
        temp_root = Path(temp_dir)
        review_input = temp_root / "reviews.json"
        receipt_input = temp_root / "receipts.json"
        review_validation = temp_root / "review-validation.json"
        write_json(review_input, {"reviews": ["isolated-path-safety-regression-fixture"]})
        write_json(receipt_input, {"receipts": ["isolated-path-safety-regression-fixture"]})
        records = [
            {
                "review_id": f"accepted-review-{index}",
                "receipt_id": f"receipt-{index}",
                "request_id": f"request-{index}",
                "slot_id": ["cm5_codon262_primary_raw_trace", "cm5_sequence_pdb_version_reconciliation"][index - 1],
                "reviewer": f"evidence_reviewer_{index}",
                "reviewed_at": "2026-08-07T00:00:00Z",
                "reviewed_source_locator": "isolated-path-safety-regression-fixture",
                "canonical_path": relative_path,
                "artifact_sha256": artifact_sha,
                "valid": True,
                "scientific_sufficiency": "accepted_for_adjudication",
                "supports_adjudication_options": [OUTCOME],
                "errors": [],
            }
            for index, (relative_path, artifact_sha) in enumerate(zip(relative_paths, artifact_shas), 1)
        ]
        missing_relative_path = "reports/__missing_cm5_path_safety_artifact__.json"
        missing_sha = "f" * 64
        records.append({
            "review_id": "accepted-review-missing",
            "receipt_id": "receipt-missing",
            "request_id": "request-missing",
            "slot_id": "cm5_codon262_primary_raw_trace",
            "reviewer": "evidence_reviewer_missing",
            "reviewed_at": "2026-08-07T00:00:00Z",
            "reviewed_source_locator": "isolated-path-safety-regression-fixture",
            "canonical_path": missing_relative_path,
            "artifact_sha256": missing_sha,
            "valid": True,
            "scientific_sufficiency": "accepted_for_adjudication",
            "supports_adjudication_options": [OUTCOME],
            "errors": [],
        })
        write_json(review_validation, {
            "intake_valid": True,
            "review_input_sha256": sha256_file(review_input),
            "receipt_input_sha256": sha256_file(receipt_input),
            "records": records,
        })
        module.REVIEW_INPUT = review_input
        module.RECEIPT_INPUT = receipt_input
        module.REVIEW_VALIDATION = review_validation

        duplicate_review_artifacts = [
            {
                "evidence_class": "raw_trace_or_independent_resequencing",
                "relative_path": relative_paths[0],
                "review_id": records[0]["review_id"],
                "sha256": artifact_shas[0],
            },
            {
                "evidence_class": "sequence_pdb_reconciliation",
                "relative_path": relative_paths[0],
                "review_id": records[0]["review_id"],
                "sha256": artifact_shas[0],
            },
        ]
        duplicate_rc, duplicate_report = run_case(
            module, temp_root, "duplicate_review_id", decision_document(duplicate_review_artifacts)
        )

        unsafe_path_artifacts = [
            {
                "evidence_class": "raw_trace_or_independent_resequencing",
                "relative_path": "../outside-workspace-artifact.json",
                "review_id": records[0]["review_id"],
                "sha256": artifact_shas[0],
            },
            {
                "evidence_class": "sequence_pdb_reconciliation",
                "relative_path": relative_paths[1],
                "review_id": records[1]["review_id"],
                "sha256": artifact_shas[1],
            },
        ]
        unsafe_rc, unsafe_report = run_case(
            module, temp_root, "unsafe_relative_path", decision_document(unsafe_path_artifacts)
        )

        missing_artifacts = [
            {
                "evidence_class": "raw_trace_or_independent_resequencing",
                "relative_path": missing_relative_path,
                "review_id": "accepted-review-missing",
                "sha256": missing_sha,
            },
            {
                "evidence_class": "sequence_pdb_reconciliation",
                "relative_path": relative_paths[1],
                "review_id": records[1]["review_id"],
                "sha256": artifact_shas[1],
            },
        ]
        missing_rc, missing_report = run_case(
            module, temp_root, "missing_artifact", decision_document(missing_artifacts)
        )

    duplicate_checks = checks(duplicate_report)
    unsafe_checks = checks(unsafe_report)
    missing_checks = checks(missing_report)
    cases = [
        {
            "case_id": "duplicate_review_id_rejected",
            "observed_return_code": duplicate_rc,
            "review_id_unique_failure_present": any(check.endswith("review_id_unique") for check in duplicate_checks),
            "passed": duplicate_rc == 1
            and duplicate_report.get("intake_valid") is False
            and any(check.endswith("review_id_unique") for check in duplicate_checks),
        },
        {
            "case_id": "unsafe_relative_path_rejected",
            "observed_return_code": unsafe_rc,
            "safe_relative_path_failure_present": any(check.endswith("safe_relative_path") for check in unsafe_checks),
            "passed": unsafe_rc == 1
            and unsafe_report.get("intake_valid") is False
            and any(check.endswith("safe_relative_path") for check in unsafe_checks),
        },
        {
            "case_id": "missing_artifact_rejected",
            "observed_return_code": missing_rc,
            "present_failure_present": any(check.endswith(".present") for check in missing_checks),
            "passed": missing_rc == 1
            and missing_report.get("intake_valid") is False
            and any(check.endswith(".present") for check in missing_checks),
        },
    ]
    real_after = {str(path): sha256_file(path) for path in real_paths}
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_evidence_path_safety_regression",
        "stage": 25,
        "success": all(case["passed"] for case in cases) and real_before == real_after,
        "case_rows": len(cases),
        "passed_rows": sum(case["passed"] for case in cases),
        "failed_rows": sum(not case["passed"] for case in cases),
        "duplicate_review_id_rejected_rows": int(cases[0]["passed"]),
        "unsafe_relative_path_rejected_rows": int(cases[1]["passed"]),
        "missing_artifact_rejected_rows": int(cases[2]["passed"]),
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
        "policy": "Temporary isolated path-safety regression only. No real review, receipt, decision, or evidence input is modified and CM5 L262V is not adjudicated.",
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
