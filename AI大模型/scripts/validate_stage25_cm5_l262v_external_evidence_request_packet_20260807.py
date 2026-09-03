#!/usr/bin/env python3
"""Validate the CM5 L262V external evidence request packet remains unsent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl"
MARKDOWN = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_request_packet_20260807.md"
INTAKE = AI_ROOT / "datasets/governance/stage25_cm5_l262v_adjudication_evidence_intake_20260807.jsonl"
INTAKE_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_evidence_intake_validation_20260807.json"
PUBLIC_PROBE = AI_ROOT / "reports/stage25_cm5_l262v_public_source_probe_receipt_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_request_packet_validation_20260807.json"
EXPECTED_SLOT_IDS = [
    "cm5_codon262_primary_raw_trace",
    "cm5_independent_resequencing",
    "cm5_complete_construct_record",
    "cm5_sequence_pdb_version_reconciliation",
]
NEGATIVE_FLAGS = (
    "request_sent",
    "outbound_authorization_present",
    "artifact_present",
    "evidence_received",
    "evidence_reviewed",
    "completion_ready",
    "discrepancy_resolved",
    "external_sqlite_mutated",
    "apply_executed",
    "export_safe_released",
    "safe_for_model_claim",
    "release_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    for label, path in (("packet", PACKET), ("markdown", MARKDOWN), ("intake", INTAKE), ("intake_validation", INTAKE_VALIDATION), ("public_probe", PUBLIC_PROBE)):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")

    rows = load_jsonl(PACKET) if PACKET.is_file() else []
    intake_rows = load_jsonl(INTAKE) if INTAKE.is_file() else []
    intake_validation = load_json(INTAKE_VALIDATION) if INTAKE_VALIDATION.is_file() else {}
    public_probe = load_json(PUBLIC_PROBE) if PUBLIC_PROBE.is_file() else {}
    intake_by_id = {str(row.get("slot_id")): row for row in intake_rows}

    fail_if(intake_validation.get("intake_valid") is not True, failures, "upstream_intake_valid", intake_validation.get("intake_valid"), True)
    fail_if(public_probe.get("receipt_valid") is not True, failures, "upstream_public_probe_valid", public_probe.get("receipt_valid"), True)
    fail_if(public_probe.get("slot_artifact_rows") != 0, failures, "upstream_slot_artifact_rows", public_probe.get("slot_artifact_rows"), 0)
    fail_if(len(rows) != 4, failures, "request_rows", len(rows), 4)
    slot_ids = [str(row.get("slot_id")) for row in rows]
    fail_if(slot_ids != EXPECTED_SLOT_IDS, failures, "slot_ids_exact", slot_ids, EXPECTED_SLOT_IDS)
    fail_if(len(set(str(row.get("request_id")) for row in rows)) != 4, failures, "unique_request_ids", len(set(str(row.get("request_id")) for row in rows)), 4)

    for index, row in enumerate(rows, 1):
        prefix = f"requests[{index}]"
        slot = intake_by_id.get(str(row.get("slot_id")), {})
        fail_if(row.get("canonical_delivery_path") != slot.get("canonical_path"), failures, f"{prefix}.canonical_delivery_path", row.get("canonical_delivery_path"), slot.get("canonical_path"))
        fail_if(row.get("evidence_class") != slot.get("evidence_class"), failures, f"{prefix}.evidence_class", row.get("evidence_class"), slot.get("evidence_class"))
        fail_if(row.get("accepted_extensions") != slot.get("allowed_extensions"), failures, f"{prefix}.accepted_extensions", row.get("accepted_extensions"), slot.get("allowed_extensions"))
        fail_if(row.get("recipient_role") != "corresponding_author_or_designated_data_custodian", failures, f"{prefix}.recipient_role", row.get("recipient_role"), "corresponding_author_or_designated_data_custodian")
        fail_if(row.get("request_status") != "not_sent", failures, f"{prefix}.request_status", row.get("request_status"), "not_sent")
        fail_if(row.get("outbound_authorization_required") is not True, failures, f"{prefix}.outbound_authorization_required", row.get("outbound_authorization_required"), True)
        for field in ("request_sent_at", "recipient_contact", "outbound_message_id", "reviewer", "reviewed_at", "review_notes"):
            fail_if(row.get(field) != "", failures, f"{prefix}.{field}_empty", row.get(field), "")
        for field in NEGATIVE_FLAGS:
            fail_if(row.get(field) is not False, failures, f"{prefix}.{field}_false", row.get(field), False)
        fail_if(row.get("formal_decision_rows_written") != 0, failures, f"{prefix}.formal_decision_rows_written_zero", row.get("formal_decision_rows_written"), 0)
        fail_if(not row.get("requested_artifact"), failures, f"{prefix}.requested_artifact", row.get("requested_artifact"), "non-empty")
        fail_if(not row.get("minimum_content"), failures, f"{prefix}.minimum_content", row.get("minimum_content"), "non-empty")
        policy = str(row.get("policy") or "")
        for term in ("Do not send", "explicit outbound authorization", "separate gates"):
            fail_if(term not in policy, failures, f"{prefix}.policy_contains:{term}", policy, f"contains {term}")

    markdown = MARKDOWN.read_text(encoding="utf-8") if MARKDOWN.is_file() else ""
    for row in rows:
        for value in (row.get("request_id"), row.get("canonical_delivery_path")):
            fail_if(str(value) not in markdown, failures, f"markdown_contains:{value}", markdown, f"contains {value}")
    for term in ("Status: `not_sent`", "no email, message, form submission", "Request sent rows: `0`", "Outbound authorization rows: `0`", "Evidence received rows: `0`", "Completion-ready rows: `0`", "request_sent=false", "discrepancy_resolved=false"):
        fail_if(term not in markdown, failures, f"markdown_contains:{term}", markdown, f"contains {term}")

    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_external_evidence_request_packet_validation",
        "stage": 25,
        "packet_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "request_rows": len(rows),
        "unique_request_rows": len(set(str(row.get("request_id")) for row in rows)),
        "request_sent_rows": sum(row.get("request_sent") is True for row in rows),
        "outbound_authorization_rows": sum(row.get("outbound_authorization_present") is True for row in rows),
        "evidence_received_rows": sum(row.get("evidence_received") is True for row in rows),
        "evidence_reviewed_rows": sum(row.get("evidence_reviewed") is True for row in rows),
        "completion_ready_rows": sum(row.get("completion_ready") is True for row in rows),
        "discrepancy_resolved": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "packet_valid": report["packet_valid"], "failure_count": report["failure_count"], "request_rows": report["request_rows"], "request_sent_rows": report["request_sent_rows"]}, sort_keys=True))
    return 0 if report["packet_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
