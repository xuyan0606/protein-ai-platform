#!/usr/bin/env python3
"""Validate trusted MSA/conservation cache before feature use."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "reports" / "msa_conservation_manifest.json"
TARGETS = AI_ROOT / "datasets" / "curation" / "msa_conservation_targets.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json"
HEX_DIGITS = set("0123456789abcdefABCDEF")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_sha256_hex(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in HEX_DIGITS for char in text)


def resolve_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else AI_ROOT / path


def validate_conservation_json(path: Path, expected_length: int) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ["conservation_json_not_parseable"]
    if not isinstance(payload, dict):
        return ["conservation_json_not_object"]
    values = payload.get("position_conservation")
    if values is not None:
        if not isinstance(values, list):
            errors.append("position_conservation_not_list")
        elif expected_length and len(values) != expected_length:
            errors.append("position_conservation_length_mismatch")
        else:
            for item in values:
                if not isinstance(item, (int, float)) or not 0 <= float(item) <= 1:
                    errors.append("position_conservation_invalid_value")
                    break
    elif not any(key in payload for key in ("site_scores", "conservation_scores", "summary")):
        errors.append("conservation_json_missing_scores")
    return errors


def validate_row(row: dict[str, Any], expected_targets: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    uniprot_id = row.get("uniprot_id")
    target = expected_targets.get(str(uniprot_id))
    if not target:
        errors.append("uniprot_id_not_in_targets")
    expected_length = int((target or {}).get("sequence_length") or row.get("sequence_length") or 0)
    if row.get("sequence_length") != expected_length:
        errors.append("sequence_length_mismatch")
    if row.get("status") != "present":
        errors.append("target_status_not_present")

    msa_path = resolve_path(row.get("msa_path"))
    conservation_path = resolve_path(row.get("conservation_feature_path"))
    msa_checksum = row.get("msa_sha256")
    conservation_checksum = row.get("conservation_sha256")
    if not msa_checksum:
        errors.append("msa_sha256_missing")
    elif not is_sha256_hex(msa_checksum):
        errors.append("msa_sha256_invalid")
    if not conservation_checksum:
        errors.append("conservation_sha256_missing")
    elif not is_sha256_hex(conservation_checksum):
        errors.append("conservation_sha256_invalid")
    if not msa_path or not msa_path.exists():
        errors.append("msa_file_missing")
    elif is_sha256_hex(msa_checksum) and sha256(msa_path) != str(msa_checksum).lower():
        errors.append("msa_sha256_mismatch")
    if not conservation_path or not conservation_path.exists():
        errors.append("conservation_file_missing")
    else:
        if is_sha256_hex(conservation_checksum) and sha256(conservation_path) != str(conservation_checksum).lower():
            errors.append("conservation_sha256_mismatch")
        errors.extend(validate_conservation_json(conservation_path, expected_length))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MSA/conservation cache manifest")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--targets", type=Path, default=TARGETS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    target_rows = load_jsonl(args.targets)
    expected_targets = {str(row.get("uniprot_id")): row for row in target_rows if row.get("uniprot_id")}
    records = []
    error_counts = Counter()
    manifest_errors = []
    if manifest.get("local_only") is not True:
        manifest_errors.append("manifest_not_local_only")
    if manifest.get("status") != "ready":
        manifest_errors.append("manifest_status_not_ready")
    if not manifest.get("source") or manifest.get("source") == "not_configured":
        manifest_errors.append("missing_source")
    if not manifest.get("source_database"):
        manifest_errors.append("missing_source_database")
    if not manifest.get("database_version"):
        manifest_errors.append("missing_database_version")
    targets = manifest.get("targets")
    if not isinstance(targets, list):
        manifest_errors.append("targets_not_list")
        targets = []

    seen = set()
    for row in targets:
        if not isinstance(row, dict):
            error_counts["target_not_object"] += 1
            continue
        uniprot_id = str(row.get("uniprot_id") or "")
        errors = []
        if uniprot_id in seen:
            errors.append("duplicate_uniprot_id")
        seen.add(uniprot_id)
        errors.extend(validate_row(row, expected_targets))
        error_counts.update(errors)
        records.append({
            "uniprot_id": uniprot_id,
            "valid": not errors,
            "errors": errors,
        })
    missing_targets = sorted(set(expected_targets) - seen)
    error_counts["missing_target_rows"] += len(missing_targets)
    error_counts.update(manifest_errors)

    valid_rows = sum(1 for row in records if row["valid"])
    invalid_rows = sum(1 for row in records if not row["valid"]) + len(missing_targets)
    ready = not manifest_errors and not invalid_rows and valid_rows == len(expected_targets) and bool(expected_targets)
    report = {
        "manifest": str(args.manifest),
        "target_rows_expected": len(expected_targets),
        "target_rows_in_manifest": len(records),
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "missing_targets": missing_targets[:200],
        "manifest_errors": manifest_errors,
        "error_counts": dict(error_counts),
        "ready": ready,
        "records": records[:200],
        "policy": "MSA/conservation cache is usable only when every target has present files, source database metadata, and required sha256 checksums that match local files",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ready": report["ready"],
        "valid_rows": report["valid_rows"],
        "invalid_rows": report["invalid_rows"],
        "manifest_errors": report["manifest_errors"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
