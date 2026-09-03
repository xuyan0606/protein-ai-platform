#!/usr/bin/env python3
"""Validate execution receipt artifact freshness without granting release claims."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
AI_ROOT_RESOLVED = AI_ROOT.resolve()
RECEIPTS = AI_ROOT / "datasets" / "governance" / "enzyme_agent_execution_receipts.local.jsonl"
OUT = AI_ROOT / "reports" / "execution_receipt_artifact_freshness_validation_report.json"

ARTIFACT_FIELDS = ("output_artifacts", "validator_artifacts")
HASH_MAP_FIELDS = (
    "artifact_hashes",
    "artifact_sha256",
    "artifact_sha256s",
    "artifact_sha256_by_path",
    "artifact_hashes_sha256",
    "sha256",
    "sha256s",
)
KIND_HASH_FIELDS = {
    "output_artifacts": (
        "output_artifact_hashes",
        "output_artifact_sha256",
        "output_artifact_sha256s",
        "output_artifacts_sha256",
    ),
    "validator_artifacts": (
        "validator_artifact_hashes",
        "validator_artifact_sha256",
        "validator_artifact_sha256s",
        "validator_artifacts_sha256",
    ),
}


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if not path.exists():
        return rows, [{"check": "receipts_file_exists", "observed": str(path), "expected": "existing JSONL file"}]

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append({"check": "receipt_json_parseable", "line": line_no, "error": str(exc)})
            continue
        if not isinstance(row, dict):
            errors.append({"check": "receipt_row_is_object", "line": line_no, "observed": type(row).__name__, "expected": "object"})
            continue
        rows.append(row)
    return rows, errors


def parse_created_at(value: Any, idx: int, action_id: Any, failures: list[dict[str, Any]]) -> datetime | None:
    if not isinstance(value, str) or not value:
        failures.append({
            "check": "receipt_created_at_parseable",
            "index": idx,
            "action_id": action_id,
            "observed": value,
            "expected": "ISO-8601 datetime string",
        })
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        failures.append({
            "check": "receipt_created_at_parseable",
            "index": idx,
            "action_id": action_id,
            "observed": value,
            "expected": "ISO-8601 datetime string",
            "error": str(exc),
        })
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_artifact_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve(strict=False)
    return (AI_ROOT / path).resolve(strict=False)


def is_within_ai_root(path: Path) -> bool:
    try:
        path.relative_to(AI_ROOT_RESOLVED)
    except ValueError:
        return False
    return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_hash_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("sha256", "hash", "digest"):
            nested = value.get(key)
            if isinstance(nested, str):
                return nested
    return None


def expected_hash_from_mapping(mapping: Any, artifact_ref: str) -> str | None:
    if not isinstance(mapping, dict):
        return None
    candidates = (
        artifact_ref,
        str(Path(artifact_ref)),
        str(resolve_artifact_path(artifact_ref)),
        Path(artifact_ref).name,
    )
    for key in candidates:
        if key in mapping:
            return normalize_hash_value(mapping[key])
    return None


def expected_hash_for_artifact(row: dict[str, Any], artifact_field: str, artifact_ref: str) -> str | None:
    for field in HASH_MAP_FIELDS + KIND_HASH_FIELDS[artifact_field]:
        expected = expected_hash_from_mapping(row.get(field), artifact_ref)
        if expected:
            return expected.lower()
    return None


def row_has_hash_expectations(row: dict[str, Any]) -> bool:
    for field in HASH_MAP_FIELDS:
        if field in row and row.get(field):
            return True
    for fields in KIND_HASH_FIELDS.values():
        for field in fields:
            if field in row and row.get(field):
                return True
    return False


def relative_display(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT_RESOLVED))
    except ValueError:
        return str(path)


def validate_freshness(receipts: list[dict[str, Any]], load_errors: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = list(load_errors)
    stale_details: list[dict[str, Any]] = []
    missing_details: list[dict[str, Any]] = []
    sha256_mismatch_details: list[dict[str, Any]] = []
    sha256_unreadable_details: list[dict[str, Any]] = []
    artifact_checks: list[dict[str, Any]] = []
    only_exists_mtime_receipts: list[dict[str, Any]] = []
    fresh_receipts = 0
    stale_receipts = 0

    for idx, row in enumerate(receipts):
        action_id = row.get("action_id")
        receipt_id = row.get("receipt_id")
        created_at = parse_created_at(row.get("created_at"), idx, action_id, failures)
        receipt_failures_before = len(failures)
        receipt_stale = False
        receipt_missing = False
        receipt_hash_unreadable = False
        receipt_hash_mismatch = False
        has_hash_expectations = row_has_hash_expectations(row)
        artifact_refs_seen = 0

        for artifact_field in ARTIFACT_FIELDS:
            artifact_refs = row.get(artifact_field)
            if not isinstance(artifact_refs, list):
                failures.append({
                    "check": "receipt_artifact_list_present",
                    "index": idx,
                    "receipt_id": receipt_id,
                    "action_id": action_id,
                    "field": artifact_field,
                    "observed": artifact_refs,
                    "expected": "list of artifact paths",
                })
                continue

            for artifact_ref in artifact_refs:
                artifact_refs_seen += 1
                if not isinstance(artifact_ref, str) or not artifact_ref:
                    failures.append({
                        "check": "receipt_artifact_ref_is_path_string",
                        "index": idx,
                        "receipt_id": receipt_id,
                        "action_id": action_id,
                        "field": artifact_field,
                        "observed": artifact_ref,
                        "expected": "nonempty path string",
                    })
                    receipt_missing = True
                    continue

                artifact_path = resolve_artifact_path(artifact_ref)
                artifact_record: dict[str, Any] = {
                    "index": idx,
                    "receipt_id": receipt_id,
                    "action_id": action_id,
                    "field": artifact_field,
                    "artifact": artifact_ref,
                    "resolved_artifact": relative_display(artifact_path),
                }

                if not is_within_ai_root(artifact_path):
                    detail = {**artifact_record, "check": "artifact_path_within_ai_root", "expected": str(AI_ROOT_RESOLVED)}
                    missing_details.append(detail)
                    failures.append(detail)
                    receipt_missing = True
                    continue
                if not artifact_path.exists():
                    detail = {**artifact_record, "check": "artifact_exists", "expected": "existing local artifact"}
                    missing_details.append(detail)
                    failures.append(detail)
                    receipt_missing = True
                    continue
                if not artifact_path.is_file():
                    detail = {**artifact_record, "check": "artifact_is_file", "expected": "regular file"}
                    missing_details.append(detail)
                    failures.append(detail)
                    receipt_missing = True
                    continue

                mtime = datetime.fromtimestamp(artifact_path.stat().st_mtime, tz=timezone.utc)
                artifact_record["artifact_mtime"] = mtime.isoformat()
                artifact_record["receipt_created_at"] = created_at.isoformat() if created_at else row.get("created_at")
                if created_at is None or mtime <= created_at:
                    detail = {
                        **artifact_record,
                        "check": "artifact_mtime_after_receipt_created_at",
                        "observed": mtime.isoformat(),
                        "expected": f"mtime later than {artifact_record['receipt_created_at']}",
                    }
                    stale_details.append(detail)
                    failures.append(detail)
                    receipt_stale = True

                try:
                    actual_sha256 = sha256_file(artifact_path)
                except OSError as exc:
                    detail = {
                        **artifact_record,
                        "check": "artifact_sha256_readable",
                        "expected": "readable artifact content",
                        "error": str(exc),
                    }
                    sha256_unreadable_details.append(detail)
                    failures.append(detail)
                    receipt_hash_unreadable = True
                    continue

                artifact_record["sha256"] = actual_sha256
                expected_sha256 = expected_hash_for_artifact(row, artifact_field, artifact_ref)
                if expected_sha256:
                    artifact_record["expected_sha256"] = expected_sha256
                    if actual_sha256.lower() != expected_sha256:
                        detail = {
                            **artifact_record,
                            "check": "artifact_sha256_matches_receipt",
                            "observed": actual_sha256,
                            "expected": expected_sha256,
                        }
                        sha256_mismatch_details.append(detail)
                        failures.append(detail)
                        receipt_hash_mismatch = True
                else:
                    artifact_record["hash_freshness_level"] = "computed_sha256_without_receipt_expected_hash"
                artifact_checks.append(artifact_record)

        if not has_hash_expectations:
            only_exists_mtime_receipts.append({
                "index": idx,
                "receipt_id": receipt_id,
                "action_id": action_id,
                "note": "receipt has no artifact hash field; this validator can only prove exists/mtime-level freshness plus sha256 readability",
            })

        receipt_has_failure = (
            receipt_missing
            or receipt_stale
            or receipt_hash_unreadable
            or receipt_hash_mismatch
            or len(failures) > receipt_failures_before
            or created_at is None
            or artifact_refs_seen == 0
        )
        if artifact_refs_seen == 0:
            failures.append({
                "check": "receipt_has_artifact_refs",
                "index": idx,
                "receipt_id": receipt_id,
                "action_id": action_id,
                "expected": "at least one output_artifacts or validator_artifacts entry",
            })
            receipt_has_failure = True
        if receipt_has_failure:
            stale_receipts += 1
        else:
            fresh_receipts += 1

    missing_artifacts = len(missing_details)
    sha256_mismatches = len(sha256_mismatch_details)
    success = not failures
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": success,
        "total_receipts": len(receipts),
        "fresh_receipts": fresh_receipts,
        "stale_receipts": stale_receipts,
        "missing_artifacts": missing_artifacts,
        "sha256_mismatches": sha256_mismatches,
        "sha256_unreadable_artifacts": len(sha256_unreadable_details),
        "artifact_reference_checks": len(artifact_checks) + missing_artifacts,
        "receipts_without_artifact_hash_fields": len(only_exists_mtime_receipts),
        "hash_freshness_note": "Receipts without artifact hash fields can only be validated at exists/mtime-level freshness plus sha256 readability; no receipt-level hash match can be proven for those rows.",
        "stale_artifact_details": stale_details,
        "missing_artifact_details": missing_details,
        "sha256_mismatch_details": sha256_mismatch_details,
        "sha256_unreadable_details": sha256_unreadable_details,
        "receipts_with_only_exists_mtime_freshness": only_exists_mtime_receipts,
        "artifact_checks": artifact_checks,
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Read-only receipt artifact freshness validation. This report does not write training rows, formal decisions, model claims, customer delivery approvals, or release readiness.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate execution receipt artifact freshness")
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    receipts, load_errors = load_jsonl(args.receipts)
    validation = validate_freshness(receipts, load_errors)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "total_receipts": validation["total_receipts"],
        "fresh_receipts": validation["fresh_receipts"],
        "stale_receipts": validation["stale_receipts"],
        "missing_artifacts": validation["missing_artifacts"],
        "sha256_mismatches": validation["sha256_mismatches"],
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
