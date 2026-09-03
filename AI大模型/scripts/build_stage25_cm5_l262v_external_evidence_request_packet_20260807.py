#!/usr/bin/env python3
"""Build an unsent operator request packet for missing CM5 L262V evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INTAKE = AI_ROOT / "datasets/governance/stage25_cm5_l262v_adjudication_evidence_intake_20260807.jsonl"
INTAKE_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_evidence_intake_validation_20260807.json"
PUBLIC_PROBE = AI_ROOT / "reports/stage25_cm5_l262v_public_source_probe_receipt_validation_20260807.json"
OUTPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl"
MARKDOWN_OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_request_packet_20260807.md"

REQUEST_DETAILS = {
    "cm5_codon262_primary_raw_trace": {
        "request_id": "request_cm5_codon262_primary_raw_trace",
        "requested_artifact": "Original CM5 codon-262 sequencing chromatogram with trace and base-quality data",
        "minimum_content": "Original instrument output identifying the CM5 sample and showing the codon-262 peak calls and quality values",
    },
    "cm5_independent_resequencing": {
        "request_id": "request_cm5_independent_resequencing",
        "requested_artifact": "Independent CM5 clone resequencing with per-base quality",
        "minimum_content": "Independent clone identity, sequence covering codon 262, per-base quality, and acquisition metadata",
    },
    "cm5_complete_construct_record": {
        "request_id": "request_cm5_complete_construct_record",
        "requested_artifact": "Complete CM5 construct record",
        "minimum_content": "Full construct composition, plasmid or clone identifier, build history, and version/provenance record",
    },
    "cm5_sequence_pdb_version_reconciliation": {
        "request_id": "request_cm5_sequence_pdb_version_reconciliation",
        "requested_artifact": "Sequence, physical construct, and PDB version reconciliation",
        "minimum_content": "Reviewed linkage and version identifiers for the CM5 sequence read, physical construct, and deposited PDB model",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_rows() -> list[dict[str, Any]]:
    intake_validation = load_json(INTAKE_VALIDATION)
    public_probe = load_json(PUBLIC_PROBE)
    if intake_validation.get("intake_valid") is not True or intake_validation.get("slot_rows") != 4:
        raise ValueError("P283 evidence intake must be valid with four slots")
    if public_probe.get("receipt_valid") is not True or public_probe.get("slot_artifact_rows") != 0:
        raise ValueError("P286 public probe must be valid and evidence-neutral")

    rows = []
    for slot in load_jsonl(INTAKE):
        slot_id = str(slot.get("slot_id") or "")
        details = REQUEST_DETAILS.get(slot_id)
        if details is None:
            raise ValueError(f"unexpected evidence slot: {slot_id}")
        rows.append({
            **details,
            "slot_id": slot_id,
            "evidence_class": slot.get("evidence_class"),
            "canonical_delivery_path": slot.get("canonical_path"),
            "accepted_extensions": slot.get("allowed_extensions"),
            "recipient_role": "corresponding_author_or_designated_data_custodian",
            "request_status": "not_sent",
            "request_sent": False,
            "request_sent_at": "",
            "recipient_contact": "",
            "outbound_message_id": "",
            "outbound_authorization_required": True,
            "outbound_authorization_present": False,
            "artifact_present": bool(slot.get("exists")),
            "evidence_received": False,
            "evidence_reviewed": False,
            "reviewer": "",
            "reviewed_at": "",
            "review_notes": "",
            "completion_ready": False,
            "discrepancy_resolved": False,
            "external_sqlite_mutated": False,
            "formal_decision_rows_written": 0,
            "apply_executed": False,
            "export_safe_released": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Operator request draft only. Do not send without explicit outbound authorization. Receipt, review, adjudication, and downstream apply remain separate gates.",
        })
    return rows


def build_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# CM5 L262V External Evidence Request Packet",
        "",
        "Status: `not_sent`. This is an operator request draft only; no email, message, form submission, or other external contact has been made.",
        "",
        "| Request | Missing evidence | Minimum content | Delivery path | Status |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['request_id']}` | {row['requested_artifact']} | {row['minimum_content']} | `{row['canonical_delivery_path']}` | `{row['request_status']}` |"
        )
    lines.extend([
        "",
        "Recipient role: `corresponding_author_or_designated_data_custodian` (contact details intentionally blank).",
        "",
        "Request sent rows: `0`",
        "Outbound authorization rows: `0`",
        "Evidence received rows: `0`",
        "Evidence reviewed rows: `0`",
        "Completion-ready rows: `0`",
        "",
        "`request_sent=false`; `outbound_authorization_present=false`; `discrepancy_resolved=false`; `apply_executed=false`; `safe_for_model_claim=false`; `release_ready=false`.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    rows = build_rows()
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(build_markdown(rows), encoding="utf-8")
    result = {
        "request_rows": len(rows),
        "request_sent_rows": sum(row["request_sent"] for row in rows),
        "outbound_authorization_rows": sum(row["outbound_authorization_present"] for row in rows),
        "evidence_received_rows": sum(row["evidence_received"] for row in rows),
        "completion_ready_rows": sum(row["completion_ready"] for row in rows),
        "output": str(OUTPUT),
        "markdown_output": str(MARKDOWN_OUTPUT),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
