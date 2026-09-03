#!/usr/bin/env python3
"""Validate external CM5 evidence receipts against live source-drop files."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_receipts.local.json"
REQUEST_PACKET = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl"
EVIDENCE_INTAKE = AI_ROOT / "datasets/governance/stage25_cm5_l262v_adjudication_evidence_intake_20260807.jsonl"
EVIDENCE_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_adjudication_evidence_intake_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_receipt_validation_20260807.json"
ALLOWED_TRANSFER_METHODS = {"email_attachment", "secure_file_transfer", "repository_deposit", "manual_local_copy"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    for label, path in (("input", INPUT), ("request_packet", REQUEST_PACKET), ("evidence_intake", EVIDENCE_INTAKE), ("evidence_validation", EVIDENCE_VALIDATION)):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")
    document = load_json(INPUT) if INPUT.is_file() else {}
    requests = load_jsonl(REQUEST_PACKET) if REQUEST_PACKET.is_file() else []
    intake_rows = load_jsonl(EVIDENCE_INTAKE) if EVIDENCE_INTAKE.is_file() else []
    intake_validation = load_json(EVIDENCE_VALIDATION) if EVIDENCE_VALIDATION.is_file() else {}
    receipts = document.get("receipts") if isinstance(document.get("receipts"), list) else []
    request_by_id = {str(row.get("request_id")): row for row in requests}
    intake_by_slot = {str(row.get("slot_id")): row for row in intake_rows}

    fail_if(document.get("schema_version") != 1, failures, "schema_version", document.get("schema_version"), 1)
    fail_if(document.get("mode") != "stage25_cm5_l262v_external_evidence_receipts", failures, "mode", document.get("mode"), "stage25_cm5_l262v_external_evidence_receipts")
    fail_if(document.get("stage") != 25, failures, "stage", document.get("stage"), 25)
    fail_if(document.get("request_packet") != "datasets/governance/stage25_cm5_l262v_external_evidence_request_packet_20260807.jsonl", failures, "request_packet", document.get("request_packet"), "canonical request packet")
    fail_if(document.get("evidence_intake") != "datasets/governance/stage25_cm5_l262v_adjudication_evidence_intake_20260807.jsonl", failures, "evidence_intake", document.get("evidence_intake"), "canonical evidence intake")
    fail_if(intake_validation.get("intake_valid") is not True, failures, "upstream_evidence_intake_valid", intake_validation.get("intake_valid"), True)
    fail_if(len(requests) != 4, failures, "request_rows", len(requests), 4)
    fail_if(len(intake_rows) != 4, failures, "evidence_slot_rows", len(intake_rows), 4)
    fail_if(len(receipts) > 4, failures, "receipt_rows_max", len(receipts), "<=4")

    records = []
    seen_receipt_ids: set[str] = set()
    seen_request_ids: set[str] = set()
    valid_receipt_requests: set[str] = set()
    receipt_without_artifact_rows = 0
    for index, row in enumerate(receipts, 1):
        prefix = f"receipts[{index}]"
        row_failures: list[str] = []
        if not isinstance(row, dict):
            failures.append({"check": f"{prefix}.object", "observed": row, "expected": "object"})
            continue
        receipt_id = str(row.get("receipt_id") or "")
        request_id = str(row.get("request_id") or "")
        request = request_by_id.get(request_id, {})
        slot_id = str(row.get("slot_id") or "")
        intake = intake_by_slot.get(slot_id, {})
        canonical_path = str(row.get("canonical_path") or "")
        artifact_path = AI_ROOT / canonical_path
        artifact_exists = artifact_path.is_file()
        live_sha = sha256_file(artifact_path) if artifact_exists else None
        if not receipt_id or receipt_id in seen_receipt_ids:
            row_failures.append("missing_or_duplicate_receipt_id")
        seen_receipt_ids.add(receipt_id)
        if request_id not in request_by_id or request_id in seen_request_ids:
            row_failures.append("unknown_or_duplicate_request_id")
        seen_request_ids.add(request_id)
        if slot_id != request.get("slot_id") or slot_id not in intake_by_slot:
            row_failures.append("slot_id_mismatch")
        expected_path = request.get("canonical_delivery_path")
        if canonical_path != expected_path or canonical_path != intake.get("canonical_path"):
            row_failures.append("canonical_path_mismatch")
        if not valid_utc_timestamp(row.get("received_at")):
            row_failures.append("invalid_received_at")
        for field in ("received_from", "source_locator", "rights_basis"):
            if not str(row.get(field) or "").strip():
                row_failures.append(f"missing_{field}")
        if row.get("transfer_method") not in ALLOWED_TRANSFER_METHODS:
            row_failures.append("invalid_transfer_method")
        declared_sha = str(row.get("artifact_sha256") or "")
        if not SHA256_RE.match(declared_sha):
            row_failures.append("invalid_artifact_sha256")
        if not artifact_exists:
            receipt_without_artifact_rows += 1
            row_failures.append("canonical_artifact_missing")
        elif declared_sha != live_sha:
            row_failures.append("artifact_sha256_mismatch")
        if intake.get("exists") is not artifact_exists or intake.get("sha256") != live_sha:
            row_failures.append("evidence_intake_filesystem_parity_mismatch")
        for error in row_failures:
            failures.append({"check": f"{prefix}.{error}", "observed": row, "expected": "valid receipt bound to live canonical artifact"})
        valid = not row_failures
        if valid:
            valid_receipt_requests.add(request_id)
        records.append({"receipt_id": receipt_id, "request_id": request_id, "slot_id": slot_id, "valid": valid, "artifact_exists": artifact_exists, "errors": row_failures})

    present_request_ids = {
        str(request.get("request_id"))
        for request in requests
        if intake_by_slot.get(str(request.get("slot_id")), {}).get("exists") is True
    }
    unreceipted_present = sorted(present_request_ids - valid_receipt_requests)
    for request_id in unreceipted_present:
        failures.append({"check": "present_artifact_requires_valid_receipt", "observed": request_id, "expected": "matching valid receipt"})

    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_external_evidence_receipt_validation",
        "stage": 25,
        "intake_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "request_rows": len(requests),
        "evidence_slot_rows": len(intake_rows),
        "receipt_rows": len(receipts),
        "valid_receipt_rows": sum(record["valid"] for record in records),
        "present_artifact_rows": len(present_request_ids),
        "unreceipted_present_artifact_rows": len(unreceipted_present),
        "receipt_without_artifact_rows": receipt_without_artifact_rows,
        "evidence_reviewed_rows": 0,
        "ready_for_adjudication_rows": 0,
        "discrepancy_resolved": False,
        "receipt_is_reviewed_evidence": False,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "records": records,
        "policy": "Receipt intake proves transfer provenance and live file identity only. It is not scientific review, adjudication, SQLite approval, model evidence, or release authorization.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "intake_valid": report["intake_valid"], "failure_count": report["failure_count"], "receipt_rows": report["receipt_rows"], "present_artifact_rows": report["present_artifact_rows"], "unreceipted_present_artifact_rows": report["unreceipted_present_artifact_rows"]}, sort_keys=True))
    return 0 if report["intake_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
