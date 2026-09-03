#!/usr/bin/env python3
"""Validate human reviews of receipted CM5 evidence without adjudicating it."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_reviews.local.json"
RECEIPT_INPUT = AI_ROOT / "datasets/governance/stage25_cm5_l262v_external_evidence_receipts.local.json"
RECEIPT_VALIDATION = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_receipt_validation_20260807.json"
OUTPUT = AI_ROOT / "reports/stage25_cm5_l262v_external_evidence_review_validation_20260807.json"
ALLOWED_REVIEW_STATUSES = {"pass", "fail", "needs_more_info"}
ALLOWED_SUFFICIENCY = {"accepted_for_adjudication", "rejected", "needs_more_info"}
ALLOWED_OPTIONS = {
    "confirm_L262V_in_CM5_construct",
    "reject_L262V_as_sequence_artifact",
    "confirm_construct_or_model_version_mismatch",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


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
    for label, path in (("input", INPUT), ("receipt_input", RECEIPT_INPUT), ("receipt_validation", RECEIPT_VALIDATION)):
        fail_if(not path.is_file(), failures, f"{label}_exists", str(path), "present file")
    document = load_json(INPUT) if INPUT.is_file() else {}
    receipt_document = load_json(RECEIPT_INPUT) if RECEIPT_INPUT.is_file() else {}
    receipt_validation = load_json(RECEIPT_VALIDATION) if RECEIPT_VALIDATION.is_file() else {}
    reviews = document.get("reviews") if isinstance(document.get("reviews"), list) else []
    receipts = receipt_document.get("receipts") if isinstance(receipt_document.get("receipts"), list) else []
    valid_receipt_ids = {
        str(row.get("receipt_id"))
        for row in receipt_validation.get("records", [])
        if isinstance(row, dict) and row.get("valid") is True
    }
    receipt_by_id = {str(row.get("receipt_id")): row for row in receipts if isinstance(row, dict)}

    fail_if(document.get("schema_version") != 1, failures, "schema_version", document.get("schema_version"), 1)
    fail_if(document.get("mode") != "stage25_cm5_l262v_external_evidence_reviews", failures, "mode", document.get("mode"), "stage25_cm5_l262v_external_evidence_reviews")
    fail_if(document.get("stage") != 25, failures, "stage", document.get("stage"), 25)
    fail_if(document.get("receipt_intake") != "datasets/governance/stage25_cm5_l262v_external_evidence_receipts.local.json", failures, "receipt_intake", document.get("receipt_intake"), "canonical receipt intake")
    fail_if(receipt_validation.get("intake_valid") is not True, failures, "upstream_receipt_intake_valid", receipt_validation.get("intake_valid"), True)
    fail_if(len(reviews) > 4, failures, "review_rows_max", len(reviews), "<=4")

    records = []
    seen_review_ids: set[str] = set()
    seen_receipt_ids: set[str] = set()
    valid_reviewed_receipt_ids: set[str] = set()
    for index, row in enumerate(reviews, 1):
        prefix = f"reviews[{index}]"
        row_failures: list[str] = []
        if not isinstance(row, dict):
            failures.append({"check": f"{prefix}.object", "observed": row, "expected": "object"})
            continue
        review_id = str(row.get("review_id") or "")
        receipt_id = str(row.get("receipt_id") or "")
        receipt = receipt_by_id.get(receipt_id, {})
        if not review_id or review_id in seen_review_ids:
            row_failures.append("missing_or_duplicate_review_id")
        seen_review_ids.add(review_id)
        if receipt_id not in valid_receipt_ids or receipt_id in seen_receipt_ids:
            row_failures.append("missing_invalid_or_duplicate_receipt_id")
        seen_receipt_ids.add(receipt_id)
        for field in ("request_id", "slot_id"):
            if row.get(field) != receipt.get(field):
                row_failures.append(f"{field}_receipt_mismatch")
        artifact_sha = str(row.get("artifact_sha256") or "")
        if not SHA256_RE.match(artifact_sha):
            row_failures.append("invalid_artifact_sha256")
        elif artifact_sha != receipt.get("artifact_sha256"):
            row_failures.append("artifact_sha256_receipt_mismatch")
        canonical_path = str(receipt.get("canonical_path") or "")
        artifact_path = AI_ROOT / canonical_path
        if not artifact_path.is_file():
            row_failures.append("canonical_artifact_missing")
        elif artifact_sha != sha256_file(artifact_path):
            row_failures.append("artifact_sha256_live_mismatch")
        for field in ("reviewer", "reviewed_source_locator", "review_basis"):
            if not str(row.get(field) or "").strip():
                row_failures.append(f"missing_{field}")
        if not valid_utc_timestamp(row.get("reviewed_at")):
            row_failures.append("invalid_reviewed_at")
        format_status = row.get("format_review_status")
        integrity_status = row.get("integrity_review_status")
        sufficiency = row.get("scientific_sufficiency")
        if format_status not in ALLOWED_REVIEW_STATUSES:
            row_failures.append("invalid_format_review_status")
        if integrity_status not in ALLOWED_REVIEW_STATUSES:
            row_failures.append("invalid_integrity_review_status")
        if sufficiency not in ALLOWED_SUFFICIENCY:
            row_failures.append("invalid_scientific_sufficiency")
        options = row.get("supports_adjudication_options") if isinstance(row.get("supports_adjudication_options"), list) else []
        if len(options) != len(set(options)) or any(option not in ALLOWED_OPTIONS for option in options):
            row_failures.append("invalid_supports_adjudication_options")
        if sufficiency == "accepted_for_adjudication":
            if format_status != "pass" or integrity_status != "pass":
                row_failures.append("accepted_review_requires_format_and_integrity_pass")
            if not options:
                row_failures.append("accepted_review_requires_supported_option")
        elif options:
            row_failures.append("nonaccepted_review_must_not_support_options")
        for error in row_failures:
            failures.append({"check": f"{prefix}.{error}", "observed": row, "expected": "valid human review bound to valid receipt and live artifact"})
        valid = not row_failures
        if valid:
            valid_reviewed_receipt_ids.add(receipt_id)
        records.append({
            "review_id": review_id,
            "receipt_id": receipt_id,
            "request_id": row.get("request_id"),
            "slot_id": row.get("slot_id"),
            "reviewer": row.get("reviewer"),
            "reviewed_at": row.get("reviewed_at"),
            "reviewed_source_locator": row.get("reviewed_source_locator"),
            "canonical_path": canonical_path,
            "artifact_sha256": artifact_sha,
            "valid": valid,
            "scientific_sufficiency": sufficiency,
            "supports_adjudication_options": options,
            "errors": row_failures,
        })

    accepted_rows = sum(record["valid"] and record["scientific_sufficiency"] == "accepted_for_adjudication" for record in records)
    unreviewed_valid_receipts = sorted(valid_receipt_ids - valid_reviewed_receipt_ids)
    report = {
        "schema_version": 1,
        "mode": "stage25_cm5_l262v_external_evidence_review_validation",
        "stage": 25,
        "intake_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "review_input_sha256": sha256_file(INPUT) if INPUT.is_file() else None,
        "receipt_input_sha256": sha256_file(RECEIPT_INPUT) if RECEIPT_INPUT.is_file() else None,
        "valid_receipt_rows": len(valid_receipt_ids),
        "review_rows": len(reviews),
        "valid_review_rows": sum(record["valid"] for record in records),
        "accepted_for_adjudication_rows": accepted_rows,
        "unreviewed_valid_receipt_rows": len(unreviewed_valid_receipts),
        "ready_for_adjudication_rows": accepted_rows,
        "review_is_adjudication": False,
        "discrepancy_resolved": False,
        "formal_decision_rows_written": 0,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "records": records,
        "policy": "Evidence review validates format, integrity, and scientific sufficiency only. Accepted rows remain adjudication candidates and do not resolve the discrepancy or authorize downstream writes and claims.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "intake_valid": report["intake_valid"], "failure_count": report["failure_count"], "review_rows": report["review_rows"], "valid_review_rows": report["valid_review_rows"], "ready_for_adjudication_rows": report["ready_for_adjudication_rows"]}, sort_keys=True))
    return 0 if report["intake_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
