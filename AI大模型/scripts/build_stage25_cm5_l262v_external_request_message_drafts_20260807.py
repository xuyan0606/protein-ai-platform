#!/usr/bin/env python3
"""Build unsent, hash-bound message drafts for CM5 evidence requests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REQUEST_PACKET = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl"
REQUEST_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_request_packet_validation_20260807.json"
OUTPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_request_message_drafts_20260807.jsonl"
MARKDOWN_OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_request_message_drafts_20260807.md"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def message_for(row: dict[str, Any]) -> tuple[str, str]:
    request_id = str(row["request_id"])
    subject = f"CM5 source evidence request for PMID 42235695: {request_id}"
    body = f"""Dear corresponding author or designated data custodian,

We are reviewing the source evidence associated with PMID 42235695 (DOI 10.1016/j.biortech.2026.135069). The available CM5 plain-text read calls GTG/Val at codon 262, while the CM5 structure records Leu at residue 262 and the declared substitution list does not include L262V. This is an unresolved evidence discrepancy, not a scientific adjudication.

For request {request_id}, could you please provide: {row['requested_artifact']}.

Minimum useful content: {row['minimum_content']}.

Please use a lawful, mutually agreed transfer route and preserve sample, construct, acquisition, and version provenance where applicable. We will place any received artifact into the designated local source-drop slot only after an independent receipt and review process. File presence alone will not be treated as reviewed evidence.

This draft does not request restricted publisher content and does not ask the recipient to approve a database write or a scientific conclusion. The request remains subject to local operator authorization and is not sent by this system."""
    return subject, body


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_rows() -> list[dict[str, Any]]:
    validation = load_json(REQUEST_VALIDATION)
    if validation.get("packet_valid") is not True or validation.get("request_rows") != 4:
        raise ValueError("P287 request packet must be valid with four rows")
    rows = []
    for row in load_jsonl(REQUEST_PACKET):
        subject, body = message_for(row)
        message_text = f"Subject: {subject}\n\n{body}"
        rows.append({
            "request_id": row["request_id"],
            "slot_id": row["slot_id"],
            "requested_artifact": row["requested_artifact"],
            "minimum_content": row["minimum_content"],
            "subject": subject,
            "body": body,
            "message_text": message_text,
            "message_sha256": sha256_text(message_text),
            "draft_status": "draft_unapproved",
            "recipient_role": row["recipient_role"],
            "recipient_contact": "",
            "approved_channels": [],
            "message_approved": False,
            "request_sent": False,
            "external_message_sent": False,
            "evidence_received": False,
            "discrepancy_resolved": False,
            "external_sqlite_mutated": False,
            "formal_decision_rows_written": 0,
            "apply_executed": False,
            "export_safe_released": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Message draft only. Do not send without separate local authorization and an external execution control; this artifact is not evidence or approval.",
        })
    return rows


def build_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# CM5 L262V External Request Message Drafts",
        "",
        "These are hash-bound message drafts only. No recipient, channel, approval, email, message, form submission, or external execution is present.",
        "",
        "| Request | Subject | Draft status | SHA-256 |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| `{row['request_id']}` | {row['subject']} | `{row['draft_status']}` | `{row['message_sha256']}` |")
    lines.extend(["", f"Draft rows: `{len(rows)}`", "Message-approved rows: `0`", "Request-sent rows: `0`", "External-message-sent rows: `0`", "Evidence-received rows: `0`", "", "`message_approved=false`; `request_sent=false`; `external_message_sent=false`; `send_executor_present=false`; `discrepancy_resolved=false`; `release_ready=false`.", ""])
    return "\n".join(lines)


def main() -> int:
    rows = build_rows()
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(build_markdown(rows), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "markdown_output": str(MARKDOWN_OUTPUT), "draft_rows": len(rows), "message_approved_rows": 0, "request_sent_rows": 0, "external_message_sent_rows": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
