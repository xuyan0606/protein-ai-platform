#!/usr/bin/env python3
"""Run isolated upstream packet-provenance regressions for CM5 adjudication."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = AI_ROOT / "scripts/validate_stage25_cm5_l262v_adjudication_decision_intake_20260807.py"
REAL_PACKET = AI_ROOT / "datasets/governance/stage25_cm5_l262v_discrepancy_adjudication_packet_20260807.jsonl"
REAL_PACKET_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_discrepancy_adjudication_packet_validation_20260807.json"
REAL_DECISION_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_adjudication_decisions.local.json"
REAL_REVIEW_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_reviews.local.json"
REAL_RECEIPT_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_receipts.local.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_upstream_packet_provenance_regression_20260807.json"
PACKET_ID = "stage25_cm5_l262v_discrepancy_adjudication_20260807"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def load_validator():
    spec = importlib.util.spec_from_file_location("cm5_adjudication_upstream_packet_provenance", VALIDATOR_PATH)
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
            "decision_id": "packet-provenance-regression-only-decision",
            "packet_id": PACKET_ID,
            "adjudication_decision": "needs_more_info",
            "reviewer": "packet_provenance_regression_fixture",
            "reviewed_at": "2026-08-07T00:00:00Z",
            "reviewed_source_locator": "isolated-packet-provenance-regression-fixture",
            "decision_basis": "packet provenance regression only; not a scientific adjudication",
            "review_notes": "No production packet, review, or decision is written.",
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


def run_case(module, temp_root: Path, case_id: str, packet: dict, packet_validation: dict) -> tuple[int, dict]:
    input_path = temp_root / f"{case_id}.input.json"
    packet_path = temp_root / f"{case_id}.packet.jsonl"
    validation_path = temp_root / f"{case_id}.packet-validation.json"
    output_path = temp_root / f"{case_id}.report.json"
    write_json(input_path, decision_document())
    write_jsonl(packet_path, [packet])
    write_json(validation_path, packet_validation)
    module.INPUT = input_path
    module.PACKET = packet_path
    module.PACKET_VALIDATION = validation_path
    module.OUTPUT = output_path
    with contextlib.redirect_stdout(io.StringIO()):
        return_code = module.main()
    return return_code, json.loads(output_path.read_text(encoding="utf-8"))


def failure_checks(report: dict) -> list[str]:
    return [str(item.get("check")) for item in report.get("failures", []) if isinstance(item, dict)]


def main() -> int:
    real_paths = [REAL_PACKET, REAL_PACKET_VALIDATION, REAL_DECISION_INPUT, REAL_REVIEW_INPUT, REAL_RECEIPT_INPUT]
    real_before = {str(path): sha256_file(path) for path in real_paths}
    packet_rows = [json.loads(line) for line in REAL_PACKET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(packet_rows) != 1 or not isinstance(packet_rows[0], dict):
        raise RuntimeError("real adjudication packet must contain exactly one object row")
    real_packet = packet_rows[0]
    module = load_validator()

    with tempfile.TemporaryDirectory(prefix="cm5_adjudication_upstream_packet_provenance_") as temp_dir:
        temp_root = Path(temp_dir)
        review_input = temp_root / "reviews.json"
        receipt_input = temp_root / "receipts.json"
        review_validation = temp_root / "review-validation.json"
        write_json(review_input, {"reviews": []})
        write_json(receipt_input, {"receipts": []})
        write_json(review_validation, {
            "intake_valid": True,
            "review_input_sha256": sha256_file(review_input),
            "receipt_input_sha256": sha256_file(receipt_input),
            "records": [],
        })
        module.REVIEW_INPUT = review_input
        module.RECEIPT_INPUT = receipt_input
        module.REVIEW_VALIDATION = review_validation

        valid_packet_validation = {"packet_valid": True, "review_fields_empty": True}
        invalid_packet_rc, invalid_packet_report = run_case(
            module,
            temp_root,
            "invalid_packet_validation",
            copy.deepcopy(real_packet),
            {"packet_valid": False, "review_fields_empty": True},
        )
        nonempty_review_rc, nonempty_review_report = run_case(
            module,
            temp_root,
            "upstream_review_fields_nonempty",
            copy.deepcopy(real_packet),
            {"packet_valid": True, "review_fields_empty": False},
        )
        drifted_packet = copy.deepcopy(real_packet)
        options = drifted_packet.get("allowed_adjudication_options")
        if not isinstance(options, list) or len(options) < 2:
            raise RuntimeError("real packet must expose at least two allowed adjudication options")
        drifted_packet["allowed_adjudication_options"] = options[:-1]
        decision_set_rc, decision_set_report = run_case(
            module,
            temp_root,
            "allowed_decision_set_drift",
            drifted_packet,
            valid_packet_validation,
        )

    invalid_checks = failure_checks(invalid_packet_report)
    nonempty_checks = failure_checks(nonempty_review_report)
    decision_set_checks = failure_checks(decision_set_report)
    cases = [
        {
            "case_id": "invalid_packet_validation_rejected",
            "observed_return_code": invalid_packet_rc,
            "upstream_packet_valid_failure_present": "upstream_packet_valid" in invalid_checks,
            "passed": invalid_packet_rc == 1
            and invalid_packet_report.get("intake_valid") is False
            and "upstream_packet_valid" in invalid_checks,
        },
        {
            "case_id": "upstream_review_fields_nonempty_rejected",
            "observed_return_code": nonempty_review_rc,
            "upstream_review_fields_empty_failure_present": "upstream_review_fields_empty" in nonempty_checks,
            "passed": nonempty_review_rc == 1
            and nonempty_review_report.get("intake_valid") is False
            and "upstream_review_fields_empty" in nonempty_checks,
        },
        {
            "case_id": "allowed_decision_set_drift_rejected",
            "observed_return_code": decision_set_rc,
            "allowed_decisions_match_packet_failure_present": "allowed_decisions_match_packet" in decision_set_checks,
            "passed": decision_set_rc == 1
            and decision_set_report.get("intake_valid") is False
            and "allowed_decisions_match_packet" in decision_set_checks,
        },
    ]
    real_after = {str(path): sha256_file(path) for path in real_paths}
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_adjudication_upstream_packet_provenance_regression",
        "stage": 25,
        "success": all(case["passed"] for case in cases) and real_before == real_after,
        "case_rows": len(cases),
        "passed_rows": sum(case["passed"] for case in cases),
        "failed_rows": sum(not case["passed"] for case in cases),
        "invalid_packet_validation_rejected_rows": int(cases[0]["passed"]),
        "upstream_review_fields_nonempty_rejected_rows": int(cases[1]["passed"]),
        "allowed_decision_set_drift_rejected_rows": int(cases[2]["passed"]),
        "real_packet_mutated": real_before[str(REAL_PACKET)] != real_after[str(REAL_PACKET)],
        "real_packet_validation_mutated": real_before[str(REAL_PACKET_VALIDATION)] != real_after[str(REAL_PACKET_VALIDATION)],
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
        "policy": "Temporary isolated upstream packet-provenance regression only. No real packet, review, receipt, or decision input is modified and CM5 L262V is not adjudicated.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "success": report["success"], "case_rows": report["case_rows"], "passed_rows": report["passed_rows"]}, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
