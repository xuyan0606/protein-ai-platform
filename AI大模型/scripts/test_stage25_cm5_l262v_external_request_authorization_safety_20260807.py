#!/usr/bin/env python3
"""Run isolated positive/negative regressions for outbound authorization safety."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = AI_ROOT / "scripts/validate_stage25_cm5_l262v_external_request_authorizations_20260807.py"
DRAFTS = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_request_message_drafts_20260807.jsonl"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_request_authorization_safety_regression_20260807.json"


def load_validator():
    spec = importlib.util.spec_from_file_location("cm5_authorization_validator_regression", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authorization_document(request_id: str, sha256: str) -> dict:
    return {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_external_request_authorizations",
        "stage": 25,
        "request_packet": "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl",
        "authorizations": [{
            "request_id": request_id,
            "decision": "authorize_send",
            "approved_channels": ["email"],
            "recipient_contact": "regression-only@example.invalid",
            "reviewer": "regression_fixture",
            "reviewed_at": "2026-08-07T00:00:00Z",
            "authorization_basis": "isolated contract regression only; not a real authorization",
            "approved_message_sha256": sha256,
        }],
    }


def run_case(module, temp_root: Path, case_id: str, document: dict) -> tuple[int, dict]:
    input_path = temp_root / f"{case_id}.json"
    output_path = temp_root / f"{case_id}.report.json"
    input_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    module.INPUT = input_path
    module.OUTPUT = output_path
    with contextlib.redirect_stdout(io.StringIO()):
        return_code = module.main()
    return return_code, json.loads(output_path.read_text(encoding="utf-8"))


def main() -> int:
    drafts = [json.loads(line) for line in DRAFTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    first = drafts[0]
    request_id = str(first["request_id"])
    current_sha = str(first["message_sha256"])
    forged_sha = "0" * 64 if current_sha != "0" * 64 else "1" * 64
    module = load_validator()
    with tempfile.TemporaryDirectory(prefix="cm5_authorization_regression_") as temp_dir:
        temp_root = Path(temp_dir)
        valid_rc, valid_report = run_case(module, temp_root, "matching_sha", authorization_document(request_id, current_sha))
        forged_rc, forged_report = run_case(module, temp_root, "forged_sha", authorization_document(request_id, forged_sha))

    forged_checks = [str(item.get("check")) for item in forged_report.get("failures", [])]
    cases = [
        {
            "case_id": "matching_current_draft_sha",
            "expected_return_code": 0,
            "observed_return_code": valid_rc,
            "intake_valid": valid_report.get("intake_valid"),
            "authorized_send_rows": valid_report.get("authorized_send_rows"),
            "message_sha_bound_authorization_rows": valid_report.get("message_sha_bound_authorization_rows"),
            "request_sent_rows": valid_report.get("request_sent_rows"),
            "external_message_sent": valid_report.get("external_message_sent"),
            "passed": valid_rc == 0 and valid_report.get("intake_valid") is True and valid_report.get("authorized_send_rows") == 1 and valid_report.get("message_sha_bound_authorization_rows") == 1 and valid_report.get("request_sent_rows") == 0 and valid_report.get("external_message_sent") is False,
        },
        {
            "case_id": "forged_well_formed_sha",
            "expected_return_code": 1,
            "observed_return_code": forged_rc,
            "intake_valid": forged_report.get("intake_valid"),
            "failure_check_present": any(check.endswith("approved_message_sha256_not_current_request_draft") for check in forged_checks),
            "request_sent_rows": forged_report.get("request_sent_rows"),
            "external_message_sent": forged_report.get("external_message_sent"),
            "passed": forged_rc == 1 and forged_report.get("intake_valid") is False and any(check.endswith("approved_message_sha256_not_current_request_draft") for check in forged_checks) and forged_report.get("request_sent_rows") == 0 and forged_report.get("external_message_sent") is False,
        },
    ]
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_external_request_authorization_safety_regression",
        "stage": 25,
        "success": all(case["passed"] for case in cases),
        "case_rows": len(cases),
        "passed_rows": sum(case["passed"] for case in cases),
        "failed_rows": sum(not case["passed"] for case in cases),
        "real_authorization_input_mutated": False,
        "request_sent_rows": 0,
        "external_message_sent": False,
        "send_executor_present": False,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "cases": cases,
        "policy": "Temporary isolated contract regression only. The real authorization input is not modified and no external communication is attempted.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "success": report["success"], "case_rows": report["case_rows"], "passed_rows": report["passed_rows"], "request_sent_rows": 0}, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
