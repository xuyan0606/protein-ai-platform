#!/usr/bin/env python3
"""Run isolated regressions for CM5 adjudication-to-review binding."""

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
REAL_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_adjudication_decisions.local.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_review_binding_regression_20260807.json"
PACKET_ID = "stage25_cm5_l262v_discrepancy_adjudication_20260807"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_validator():
    spec = importlib.util.spec_from_file_location("cm5_adjudication_review_binding_regression", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def decision_document(evidence_artifacts: list[dict], outcome: str = "reject_L262V_as_sequence_artifact") -> dict:
    return {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_decision_intake",
        "stage": 25,
        "packet_id": PACKET_ID,
        "decisions": [{
            "decision_id": "regression-only-decision",
            "packet_id": PACKET_ID,
            "adjudication_decision": outcome,
            "reviewer": "regression_fixture",
            "reviewed_at": "2026-08-07T00:00:00Z",
            "reviewed_source_locator": "isolated-regression-fixture",
            "decision_basis": "contract regression only; not a scientific adjudication",
            "review_notes": "No production decision is written.",
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


def main() -> int:
    real_input_before = sha256_file(REAL_INPUT)
    module = load_validator()
    artifact_paths = [VALIDATOR_PATH, AI_ROOT / "scripts/validate_stage25_cm5_l262v_external_evidence_reviews_20260807.py"]
    relative_paths = [str(path.relative_to(AI_ROOT)) for path in artifact_paths]
    artifact_shas = [sha256_file(path) for path in artifact_paths]

    with tempfile.TemporaryDirectory(prefix="cm5_adjudication_review_binding_") as temp_dir:
        temp_root = Path(temp_dir)
        review_input = temp_root / "reviews.json"
        receipt_input = temp_root / "receipts.json"
        review_validation = temp_root / "review-validation.json"
        write_json(review_input, {"reviews": ["isolated-regression-fixture"]})
        write_json(receipt_input, {"receipts": ["isolated-regression-fixture"]})
        records = [
            {
                "review_id": f"accepted-review-{index}",
                "receipt_id": f"receipt-{index}",
                "request_id": f"request-{index}",
                "slot_id": ["cm5_codon262_primary_raw_trace", "cm5_sequence_pdb_version_reconciliation"][index - 1],
                "reviewer": f"evidence_reviewer_{index}",
                "reviewed_at": "2026-08-07T00:00:00Z",
                "reviewed_source_locator": "isolated-regression-fixture",
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

        bound_artifacts = [
            {
                "evidence_class": evidence_class,
                "relative_path": relative_path,
                "review_id": record["review_id"],
                "sha256": artifact_sha,
            }
            for evidence_class, relative_path, artifact_sha, record in zip(
                ["raw_trace_or_independent_resequencing", "sequence_pdb_reconciliation"],
                relative_paths,
                artifact_shas,
                records,
            )
        ]
        bound_rc, bound_report = run_case(module, temp_root, "accepted_review_binding", decision_document(bound_artifacts))

        unreviewed_artifacts = [dict(row, review_id=f"unreviewed-{index}") for index, row in enumerate(bound_artifacts, 1)]
        unreviewed_rc, unreviewed_report = run_case(module, temp_root, "unreviewed_raw_paths", decision_document(unreviewed_artifacts))

        needs_more_info_rc, needs_more_info_report = run_case(
            module,
            temp_root,
            "needs_more_info_empty_evidence",
            decision_document([], outcome="needs_more_info"),
        )

    unreviewed_checks = [str(item.get("check")) for item in unreviewed_report.get("failures", [])]
    cases = [
        {
            "case_id": "accepted_review_binding",
            "observed_return_code": bound_rc,
            "review_bound_evidence_rows": bound_report.get("review_bound_evidence_rows"),
            "unreviewed_evidence_artifact_rows": bound_report.get("unreviewed_evidence_artifact_rows"),
            "passed": bound_rc == 0 and bound_report.get("valid_decision_rows") == 1 and bound_report.get("review_bound_evidence_rows") == 2 and bound_report.get("unreviewed_evidence_artifact_rows") == 0,
        },
        {
            "case_id": "unreviewed_raw_paths_rejected",
            "observed_return_code": unreviewed_rc,
            "accepted_review_failure_present": any(check.endswith("accepted_review_id") for check in unreviewed_checks),
            "unreviewed_evidence_artifact_rows": unreviewed_report.get("unreviewed_evidence_artifact_rows"),
            "passed": unreviewed_rc == 1 and unreviewed_report.get("intake_valid") is False and any(check.endswith("accepted_review_id") for check in unreviewed_checks) and unreviewed_report.get("unreviewed_evidence_artifact_rows") == 2,
        },
        {
            "case_id": "needs_more_info_without_evidence",
            "observed_return_code": needs_more_info_rc,
            "needs_more_info_rows": needs_more_info_report.get("needs_more_info_rows"),
            "passed": needs_more_info_rc == 0 and needs_more_info_report.get("valid_decision_rows") == 1 and needs_more_info_report.get("needs_more_info_rows") == 1,
        },
    ]
    real_input_after = sha256_file(REAL_INPUT)
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_review_binding_regression",
        "stage": 25,
        "success": all(case["passed"] for case in cases) and real_input_before == real_input_after,
        "case_rows": len(cases),
        "passed_rows": sum(case["passed"] for case in cases),
        "failed_rows": sum(not case["passed"] for case in cases),
        "real_decision_input_mutated": real_input_before != real_input_after,
        "formal_decision_rows_written": 0,
        "discrepancy_resolved": False,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "cases": cases,
        "policy": "Temporary isolated contract regression only. Synthetic accepted reviews do not alter real review, receipt, decision, or evidence inputs and do not adjudicate CM5 L262V.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "success": report["success"], "case_rows": report["case_rows"], "passed_rows": report["passed_rows"]}, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
