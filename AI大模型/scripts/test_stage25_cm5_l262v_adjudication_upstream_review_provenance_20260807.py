#!/usr/bin/env python3
"""Run isolated upstream review-provenance regressions for CM5 adjudication."""

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
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_upstream_review_provenance_regression_20260807.json"
PACKET_ID = "stage25_cm5_l262v_discrepancy_adjudication_20260807"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_validator():
    spec = importlib.util.spec_from_file_location("cm5_adjudication_upstream_review_provenance", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decision_document() -> dict:
    return {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_decision_intake",
        "stage": 25,
        "packet_id": PACKET_ID,
        "decisions": [{
            "decision_id": "upstream-provenance-regression-only-decision",
            "packet_id": PACKET_ID,
            "adjudication_decision": "needs_more_info",
            "reviewer": "upstream_provenance_regression_fixture",
            "reviewed_at": "2026-08-07T00:00:00Z",
            "reviewed_source_locator": "isolated-upstream-provenance-regression-fixture",
            "decision_basis": "upstream provenance regression only; not a scientific adjudication",
            "review_notes": "No production review or decision is written.",
            "evidence_artifacts": [],
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


def run_case(module, temp_root: Path, case_id: str, review_validation: dict) -> tuple[int, dict]:
    input_path = temp_root / f"{case_id}.input.json"
    validation_path = temp_root / f"{case_id}.review-validation.json"
    output_path = temp_root / f"{case_id}.report.json"
    write_json(input_path, decision_document())
    write_json(validation_path, review_validation)
    module.INPUT = input_path
    module.REVIEW_VALIDATION = validation_path
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

    with tempfile.TemporaryDirectory(prefix="cm5_adjudication_upstream_provenance_") as temp_dir:
        temp_root = Path(temp_dir)
        review_input = temp_root / "reviews.json"
        receipt_input = temp_root / "receipts.json"
        write_json(review_input, {"reviews": []})
        write_json(receipt_input, {"receipts": []})
        module.REVIEW_INPUT = review_input
        module.RECEIPT_INPUT = receipt_input
        valid_review_sha = sha256_file(review_input)
        valid_receipt_sha = sha256_file(receipt_input)
        base = {
            "intake_valid": True,
            "review_input_sha256": valid_review_sha,
            "receipt_input_sha256": valid_receipt_sha,
            "records": [],
        }

        invalid_intake_rc, invalid_intake_report = run_case(
            module, temp_root, "invalid_upstream_review_intake", dict(base, intake_valid=False)
        )
        stale_review_rc, stale_review_report = run_case(
            module, temp_root, "stale_review_input_sha", dict(base, review_input_sha256="0" * 64)
        )
        stale_receipt_rc, stale_receipt_report = run_case(
            module, temp_root, "stale_receipt_input_sha", dict(base, receipt_input_sha256="f" * 64)
        )

    invalid_checks = failure_checks(invalid_intake_report)
    stale_review_checks = failure_checks(stale_review_report)
    stale_receipt_checks = failure_checks(stale_receipt_report)
    cases = [
        {
            "case_id": "invalid_upstream_review_intake_rejected",
            "observed_return_code": invalid_intake_rc,
            "upstream_review_intake_valid_failure_present": "upstream_review_intake_valid" in invalid_checks,
            "passed": invalid_intake_rc == 1
            and invalid_intake_report.get("intake_valid") is False
            and "upstream_review_intake_valid" in invalid_checks,
        },
        {
            "case_id": "stale_review_input_sha_rejected",
            "observed_return_code": stale_review_rc,
            "upstream_review_input_sha256_live_failure_present": "upstream_review_input_sha256_live" in stale_review_checks,
            "passed": stale_review_rc == 1
            and stale_review_report.get("intake_valid") is False
            and "upstream_review_input_sha256_live" in stale_review_checks,
        },
        {
            "case_id": "stale_receipt_input_sha_rejected",
            "observed_return_code": stale_receipt_rc,
            "upstream_receipt_input_sha256_live_failure_present": "upstream_receipt_input_sha256_live" in stale_receipt_checks,
            "passed": stale_receipt_rc == 1
            and stale_receipt_report.get("intake_valid") is False
            and "upstream_receipt_input_sha256_live" in stale_receipt_checks,
        },
    ]
    real_after = {str(path): sha256_file(path) for path in real_paths}
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_upstream_review_provenance_regression",
        "stage": 25,
        "success": all(case["passed"] for case in cases) and real_before == real_after,
        "case_rows": len(cases),
        "passed_rows": sum(case["passed"] for case in cases),
        "failed_rows": sum(not case["passed"] for case in cases),
        "invalid_upstream_review_intake_rejected_rows": int(cases[0]["passed"]),
        "stale_review_input_sha_rejected_rows": int(cases[1]["passed"]),
        "stale_receipt_input_sha_rejected_rows": int(cases[2]["passed"]),
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
        "policy": "Temporary isolated upstream-provenance regression only. No real review, receipt, decision, or evidence input is modified and CM5 L262V is not adjudicated.",
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
