#!/usr/bin/env python3
"""Validate the CM5 external request send guard has no side effects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GUARD = AI_ROOT / "reports/stage25_cm5_l262v_external_request_send_guard_20260807.json"
AUTHORIZATION = AI_ROOT / "reports/stage25_cm5_l262v_external_request_authorization_validation_20260807.json"
REQUEST_PACKET = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_request_packet_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_request_send_guard_validation_20260807.json"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    for label, path in (("guard", GUARD), ("authorization", AUTHORIZATION), ("request_packet", REQUEST_PACKET)):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")
    guard = load_json(GUARD) if GUARD.is_file() else {}
    authorization = load_json(AUTHORIZATION) if AUTHORIZATION.is_file() else {}
    request_packet = load_json(REQUEST_PACKET) if REQUEST_PACKET.is_file() else {}
    fail_if(guard.get("mode") != "stage25_cm5_l262v_external_request_send_guard", failures, "mode", guard.get("mode"), "stage25_cm5_l262v_external_request_send_guard")
    fail_if(guard.get("authorization_validation_valid") is not True, failures, "authorization_validation_valid", guard.get("authorization_validation_valid"), True)
    fail_if(guard.get("request_packet_valid") is not True, failures, "request_packet_valid", guard.get("request_packet_valid"), True)
    fail_if(guard.get("request_rows") != 4, failures, "request_rows", guard.get("request_rows"), 4)
    fail_if(guard.get("authorization_rows") != authorization.get("authorization_rows"), failures, "authorization_rows_parity", guard.get("authorization_rows"), authorization.get("authorization_rows"))
    fail_if(guard.get("authorized_send_rows") != 0, failures, "authorized_send_rows_zero", guard.get("authorized_send_rows"), 0)
    fail_if(guard.get("execution_status") != "blocked_no_authorization_and_no_executor", failures, "execution_status", guard.get("execution_status"), "blocked_no_authorization_and_no_executor")
    for field in ("send_attempted", "external_message_sent", "send_executor_present", "external_sqlite_mutated", "formal_decision_rows_written", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        expected = 0 if field == "formal_decision_rows_written" else False
        fail_if(guard.get(field) is not expected, failures, f"{field}_safe", guard.get(field), expected)
    policy = str(guard.get("policy") or "")
    for term in ("never sends email", "HTTP requests", "external communications"):
        fail_if(term not in policy, failures, f"policy_contains:{term}", policy, f"contains {term}")
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_external_request_send_guard_validation",
        "stage": 25,
        "guard_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "request_rows": guard.get("request_rows"),
        "authorization_rows": guard.get("authorization_rows"),
        "authorized_send_rows": guard.get("authorized_send_rows"),
        "send_attempted": False,
        "external_message_sent": False,
        "send_executor_present": False,
        "execution_status": guard.get("execution_status"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "guard_valid": report["guard_valid"], "failure_count": report["failure_count"], "execution_status": report["execution_status"]}, sort_keys=True))
    return 0 if report["guard_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
