#!/usr/bin/env python3
"""Build a no-side-effect guard receipt for the CM5 evidence request packet."""

from __future__ import annotations

import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = AI_ROOT / "reports/stage25_cm5_l262v_external_request_authorization_validation_20260807.json"
REQUEST_PACKET = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_request_packet_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_request_send_guard_20260807.json"


def main() -> int:
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    request_packet = json.loads(REQUEST_PACKET.read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_external_request_send_guard",
        "stage": 25,
        "authorization_validation_valid": authorization.get("intake_valid") is True,
        "request_packet_valid": request_packet.get("packet_valid") is True,
        "request_rows": request_packet.get("request_rows", 0),
        "authorization_rows": authorization.get("authorization_rows", 0),
        "authorized_send_rows": authorization.get("authorized_send_rows", 0),
        "send_attempted": False,
        "external_message_sent": False,
        "send_executor_present": False,
        "execution_status": "blocked_no_authorization_and_no_executor",
        "blocked_reason": "No outbound executor is implemented; authorization intake is empty and external contact is outside this validation run.",
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Guard receipt only. It never sends email, HTTP requests, forms, repository messages, or other external communications.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "execution_status": report["execution_status"], "send_attempted": False, "external_message_sent": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
