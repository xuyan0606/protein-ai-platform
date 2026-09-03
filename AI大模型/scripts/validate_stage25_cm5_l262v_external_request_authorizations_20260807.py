#!/usr/bin/env python3
"""Validate human outbound authorizations without sending any request."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_request_authorizations.local.json"
REQUEST_PACKET = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl"
REQUEST_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_request_packet_validation_20260807.json"
MESSAGE_DRAFTS = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_request_message_drafts_20260807.jsonl"
MESSAGE_DRAFT_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_external_request_message_drafts_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_request_authorization_validation_20260807.json"
ALLOWED_DECISIONS = {"authorize_send", "do_not_send", "needs_more_info"}
ALLOWED_CHANNELS = {"email", "publisher_contact_form", "repository_message"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    for label, path in (("input", INPUT), ("request_packet", REQUEST_PACKET), ("request_validation", REQUEST_VALIDATION), ("message_drafts", MESSAGE_DRAFTS), ("message_draft_validation", MESSAGE_DRAFT_VALIDATION)):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")

    document = load_json(INPUT) if INPUT.is_file() else {}
    request_rows = load_jsonl(REQUEST_PACKET) if REQUEST_PACKET.is_file() else []
    request_validation = load_json(REQUEST_VALIDATION) if REQUEST_VALIDATION.is_file() else {}
    message_drafts = load_jsonl(MESSAGE_DRAFTS) if MESSAGE_DRAFTS.is_file() else []
    message_draft_validation = load_json(MESSAGE_DRAFT_VALIDATION) if MESSAGE_DRAFT_VALIDATION.is_file() else {}
    authorizations = document.get("authorizations") if isinstance(document.get("authorizations"), list) else []
    request_ids = {str(row.get("request_id")) for row in request_rows}
    draft_sha_by_request = {str(row.get("request_id")): str(row.get("message_sha256") or "") for row in message_drafts}

    fail_if(document.get("schema_version") != 1, failures, "schema_version", document.get("schema_version"), 1)
    fail_if(document.get("mode") != "stage25_cm5_l262v_external_request_authorizations", failures, "mode", document.get("mode"), "stage25_cm5_l262v_external_request_authorizations")
    fail_if(document.get("stage") != 25, failures, "stage", document.get("stage"), 25)
    fail_if(document.get("request_packet") != "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl", failures, "request_packet", document.get("request_packet"), "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl")
    fail_if(request_validation.get("packet_valid") is not True, failures, "upstream_packet_valid", request_validation.get("packet_valid"), True)
    fail_if(request_validation.get("request_rows") != 4, failures, "upstream_request_rows", request_validation.get("request_rows"), 4)
    fail_if(message_draft_validation.get("drafts_valid") is not True, failures, "upstream_message_drafts_valid", message_draft_validation.get("drafts_valid"), True)
    fail_if(message_draft_validation.get("draft_rows") != 4, failures, "upstream_message_draft_rows", message_draft_validation.get("draft_rows"), 4)
    fail_if(set(draft_sha_by_request) != request_ids, failures, "message_draft_request_ids_exact", sorted(draft_sha_by_request), sorted(request_ids))
    fail_if(len(authorizations) > 4, failures, "authorization_rows_max", len(authorizations), "<=4")

    records = []
    seen_ids: set[str] = set()
    for index, row in enumerate(authorizations, 1):
        prefix = f"authorizations[{index}]"
        row_failures: list[str] = []
        if not isinstance(row, dict):
            failures.append({"check": f"{prefix}.object", "observed": row, "expected": "object"})
            continue
        request_id = str(row.get("request_id") or "")
        decision = str(row.get("decision") or "")
        channels = row.get("approved_channels") if isinstance(row.get("approved_channels"), list) else []
        if request_id not in request_ids:
            row_failures.append("unknown_request_id")
        if request_id in seen_ids:
            row_failures.append("duplicate_request_id")
        seen_ids.add(request_id)
        if decision not in ALLOWED_DECISIONS:
            row_failures.append("invalid_decision")
        if not isinstance(channels, list) or len(channels) != len(set(channels)) or any(channel not in ALLOWED_CHANNELS for channel in channels):
            row_failures.append("invalid_approved_channels")
        for field in ("reviewer", "reviewed_at", "authorization_basis"):
            if not str(row.get(field) or "").strip():
                row_failures.append(f"missing_{field}")
        if row.get("reviewed_at") and not valid_utc_timestamp(row.get("reviewed_at")):
            row_failures.append("invalid_reviewed_at")
        if decision == "authorize_send":
            if not channels:
                row_failures.append("missing_approved_channel")
            if not str(row.get("recipient_contact") or "").strip():
                row_failures.append("missing_recipient_contact")
            if not SHA256_RE.match(str(row.get("approved_message_sha256") or "")):
                row_failures.append("invalid_approved_message_sha256")
            elif str(row.get("approved_message_sha256")) != draft_sha_by_request.get(request_id):
                row_failures.append("approved_message_sha256_not_current_request_draft")
        else:
            if channels:
                row_failures.append("channels_for_non_authorize_decision")
            if str(row.get("approved_message_sha256") or ""):
                row_failures.append("message_sha_for_non_authorize_decision")
        for error in row_failures:
            failures.append({"check": f"{prefix}.{error}", "observed": row, "expected": "valid authorization contract"})
        records.append({"request_id": request_id, "decision": decision, "valid": not row_failures, "errors": row_failures})

    valid_authorization_rows = sum(record["valid"] for record in records)
    authorized_send_rows = sum(record["valid"] and record["decision"] == "authorize_send" for record in records)
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_external_request_authorization_validation",
        "stage": 25,
        "intake_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "request_rows": len(request_rows),
        "message_draft_validation_valid": message_draft_validation.get("drafts_valid") is True,
        "message_draft_rows": len(message_drafts),
        "message_draft_request_rows": len(draft_sha_by_request),
        "authorization_rows": len(authorizations),
        "valid_authorization_rows": valid_authorization_rows,
        "authorized_send_rows": authorized_send_rows,
        "message_sha_bound_authorization_rows": authorized_send_rows,
        "do_not_send_rows": sum(record["valid"] and record["decision"] == "do_not_send" for record in records),
        "needs_more_info_rows": sum(record["valid"] and record["decision"] == "needs_more_info" for record in records),
        "send_ready_candidate_rows": authorized_send_rows,
        "request_sent_rows": 0,
        "external_message_sent": False,
        "send_executor_present": False,
        "evidence_received_rows": 0,
        "discrepancy_resolved": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "records": records,
        "policy": "Authorization intake only. A valid authorize_send row does not send a request; outbound execution remains absent and separately controlled.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "intake_valid": report["intake_valid"], "failure_count": report["failure_count"], "authorization_rows": report["authorization_rows"], "authorized_send_rows": report["authorized_send_rows"], "request_sent_rows": report["request_sent_rows"]}, sort_keys=True))
    return 0 if report["intake_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
