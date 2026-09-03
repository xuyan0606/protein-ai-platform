#!/usr/bin/env python3
"""Validate CM5 external message drafts and their live SHA-256 parity."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DRAFTS = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_request_message_drafts_20260807.jsonl"
MARKDOWN = AI_ROOT / "reports/stage25_cm5_l262v_external_request_message_drafts_20260807.md"
REQUEST_PACKET = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl"
REQUEST_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_request_packet_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_request_message_drafts_validation_20260807.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    for label, path in (("drafts", DRAFTS), ("markdown", MARKDOWN), ("request_packet", REQUEST_PACKET), ("request_validation", REQUEST_VALIDATION)):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")
    rows = load_jsonl(DRAFTS) if DRAFTS.is_file() else []
    requests = load_jsonl(REQUEST_PACKET) if REQUEST_PACKET.is_file() else []
    request_validation = load_json(REQUEST_VALIDATION) if REQUEST_VALIDATION.is_file() else {}
    fail_if(request_validation.get("packet_valid") is not True, failures, "upstream_request_packet_valid", request_validation.get("packet_valid"), True)
    fail_if(request_validation.get("request_rows") != 4, failures, "upstream_request_rows", request_validation.get("request_rows"), 4)
    fail_if(len(rows) != 4, failures, "draft_rows", len(rows), 4)
    expected_ids = [str(row.get("request_id")) for row in requests]
    observed_ids = [str(row.get("request_id")) for row in rows]
    fail_if(observed_ids != expected_ids, failures, "request_ids_exact_order", observed_ids, expected_ids)
    seen_hashes: set[str] = set()
    for index, row in enumerate(rows, 1):
        prefix = f"drafts[{index}]"
        request = requests[index - 1] if index <= len(requests) else {}
        for field in ("request_id", "slot_id", "requested_artifact", "minimum_content"):
            fail_if(row.get(field) != request.get(field), failures, f"{prefix}.{field}_matches_request", row.get(field), request.get(field))
        subject = str(row.get("subject") or "")
        body = str(row.get("body") or "")
        message_text = str(row.get("message_text") or "")
        message_sha = str(row.get("message_sha256") or "")
        fail_if(not subject or not body, failures, f"{prefix}.message_content_present", {"subject": subject, "body": bool(body)}, "non-empty")
        fail_if(message_text != f"Subject: {subject}\n\n{body}", failures, f"{prefix}.message_text_canonical", message_text, "Subject + body")
        fail_if(not SHA256_RE.match(message_sha), failures, f"{prefix}.message_sha256_format", message_sha, "64 lowercase hex")
        fail_if(message_sha != sha256_text(message_text), failures, f"{prefix}.message_sha256_live_parity", message_sha, sha256_text(message_text))
        fail_if(message_sha in seen_hashes, failures, f"{prefix}.message_sha256_unique", message_sha, "unique")
        seen_hashes.add(message_sha)
        for term in (str(row.get("requested_artifact") or ""), str(row.get("minimum_content") or ""), "lawful", "not sent"):
            fail_if(term.lower() not in message_text.lower(), failures, f"{prefix}.message_contains:{term}", message_text, f"contains {term}")
        for field, expected in (("draft_status", "draft_unapproved"), ("recipient_contact", ""), ("approved_channels", []), ("message_approved", False), ("request_sent", False), ("external_message_sent", False), ("evidence_received", False), ("discrepancy_resolved", False), ("external_sqlite_mutated", False), ("apply_executed", False), ("release_ready", False)):
            fail_if(row.get(field) != expected, failures, f"{prefix}.{field}", row.get(field), expected)
        fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written_zero", row.get("formal_decision_rows_written"), 0)
    markdown = MARKDOWN.read_text(encoding="utf-8") if MARKDOWN.is_file() else ""
    for row in rows:
        for term in (row.get("request_id"), row.get("message_sha256"), row.get("draft_status")):
            fail_if(str(term) not in markdown, failures, f"markdown_contains:{term}", markdown, f"contains {term}")
    for term in ("Draft rows: `4`", "Message-approved rows: `0`", "Request-sent rows: `0`", "External-message-sent rows: `0`", "message_approved=false", "send_executor_present=false"):
        fail_if(term not in markdown, failures, f"markdown_contains:{term}", markdown, f"contains {term}")
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_external_request_message_drafts_validation",
        "stage": 25,
        "drafts_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "draft_rows": len(rows),
        "unique_message_sha256_rows": len(seen_hashes),
        "message_approved_rows": 0,
        "request_sent_rows": 0,
        "external_message_sent_rows": 0,
        "evidence_received_rows": 0,
        "discrepancy_resolved": False,
        "send_executor_present": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Hash-bound message drafts only. They are not approved outbound messages, sent communications, source evidence, decisions, SQLite payloads, model claims, or release artifacts.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "drafts_valid": report["drafts_valid"], "failure_count": report["failure_count"], "draft_rows": report["draft_rows"], "message_approved_rows": report["message_approved_rows"]}, sort_keys=True))
    return 0 if report["drafts_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
