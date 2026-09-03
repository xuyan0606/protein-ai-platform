#!/usr/bin/env python3
"""Validate local structure cache manifests and acquisition rows.

This validator checks real local cache evidence only: file presence, sha256
consistency, manifest/acquisition row alignment, and fail-closed claim flags.
It does not download structures, infer chain mappings, or unlock labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
EXPECTED = AI_ROOT / "reports" / "structure_cache_expected_manifest.json"
ACQUISITION = AI_ROOT / "datasets" / "curation" / "structure_acquisition_manifest.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_cache_manifest_validation_report.json"

VALID_SOURCES = {"pdb", "alphafold", "esmfold", "uploaded"}
VALID_STATUSES = {"missing", "present", "invalid", "pending"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_paths(path_text: str) -> list[Path]:
    path = Path(path_text)
    if path.is_absolute():
        candidates = [path]
    else:
        candidates = [
            PROJECT_ROOT / path,
            PROJECT_ROOT / "backend" / path,
            PROJECT_ROOT / "deploy_data" / path,
            AI_ROOT / path,
            AI_ROOT / "cache" / "structures" / path,
        ]
    expanded: list[Path] = []
    for candidate in candidates:
        expanded.append(candidate)
        if candidate.suffix.lower() == ".pdb":
            expanded.append(candidate.with_suffix(".cif"))
        elif candidate.suffix.lower() == ".cif":
            expanded.append(candidate.with_suffix(".pdb"))
    seen: list[Path] = []
    for candidate in expanded:
        if candidate not in seen:
            seen.append(candidate)
    return seen


def first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("source") or ""), str(row.get("structure_id") or "").upper())


def truthy_claim_flags(row: dict[str, Any]) -> list[str]:
    return [
        field
        for field in ("safe_for_model_claim", "safe_for_training_import", "release_ready")
        if row.get(field) is True
    ]


def validate_expected(manifest: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    failures: list[str] = []
    row_failures: list[dict[str, Any]] = []
    entries = manifest.get("entries")
    if manifest.get("local_only") is not True:
        failures.append("expected_manifest_not_local_only")
    if not isinstance(manifest.get("cache_roots"), list) or not manifest.get("cache_roots"):
        failures.append("expected_manifest_missing_cache_roots")
    if not isinstance(entries, list):
        failures.append("expected_manifest_entries_not_list")
        return failures, row_failures
    summary = manifest.get("summary") or {}
    if summary.get("entries") is not None and int(summary.get("entries") or 0) != len(entries):
        failures.append("expected_summary_entry_count_mismatch")

    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(entries):
        errors: list[str] = []
        key = row_key(row)
        if key in seen:
            errors.append("duplicate_expected_structure_key")
        seen.add(key)
        if not key[1]:
            errors.append("missing_structure_id")
        if key[0] not in VALID_SOURCES:
            errors.append("invalid_source")
        expected_path = row.get("expected_path")
        if not isinstance(expected_path, str) or not expected_path:
            errors.append("missing_expected_path")
            actual_path = None
        else:
            actual_path = first_existing(candidate_paths(expected_path))
        status = row.get("status")
        if status not in VALID_STATUSES:
            errors.append("invalid_status")
        elif status == "present" and actual_path is None:
            errors.append("expected_status_present_but_file_missing")
        elif status == "missing" and actual_path is not None:
            errors.append("expected_status_missing_but_file_present")
        if truthy_claim_flags(row):
            errors.append("unexpected_positive_claim_flag")
        if errors:
            row_failures.append({"index": index, "structure_id": key[1], "source": key[0], "errors": errors})
    return failures, row_failures


def validate_acquisition(
    rows: list[dict[str, Any]],
    expected_entries: list[dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], dict[str, int]]:
    failures: list[str] = []
    row_failures: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    expected_keys = {row_key(row) for row in expected_entries}
    seen: set[tuple[str, str]] = set()
    if len(rows) != len(expected_entries):
        failures.append("acquisition_row_count_mismatch")
    for index, row in enumerate(rows):
        errors: list[str] = []
        key = row_key(row)
        if key in seen:
            errors.append("duplicate_acquisition_structure_key")
        seen.add(key)
        if key not in expected_keys:
            errors.append("acquisition_key_not_in_expected_manifest")
        status = row.get("status")
        if status not in VALID_STATUSES:
            errors.append("invalid_status")
        actual_path_text = row.get("actual_cache_path")
        actual_path = Path(actual_path_text) if actual_path_text else None
        actual_exists = bool(actual_path and actual_path.exists() and actual_path.stat().st_size > 0)
        if status == "present":
            counts["present_rows"] += 1
            if not actual_exists:
                errors.append("present_row_missing_actual_cache_path")
            else:
                expected_sha = row.get("sha256")
                actual_sha = sha256_file(actual_path)
                counts["sha256_checked_rows"] += 1
                if expected_sha != actual_sha:
                    errors.append("sha256_mismatch")
                    counts["sha256_mismatch_rows"] += 1
                local_validation = row.get("local_validation") or {}
                if int(local_validation.get("atom_lines") or 0) <= 0:
                    errors.append("present_row_missing_atom_lines")
        else:
            if actual_exists:
                errors.append("non_present_row_has_actual_cache_path")
            counts["non_present_rows"] += 1
        if row.get("policy") and "no source DB modification" not in str(row.get("policy")):
            errors.append("policy_missing_no_db_modification")
        if truthy_claim_flags(row):
            errors.append("unexpected_positive_claim_flag")
        if errors:
            row_failures.append({"index": index, "structure_id": key[1], "source": key[0], "errors": errors})
    missing_keys = sorted(expected_keys - seen)
    unexpected_keys = sorted(seen - expected_keys)
    if missing_keys:
        failures.append("missing_acquisition_rows")
    if unexpected_keys:
        failures.append("unexpected_acquisition_rows")
    counts["missing_key_rows"] = len(missing_keys)
    counts["unexpected_key_rows"] = len(unexpected_keys)
    return failures, row_failures, dict(counts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate structure cache manifest")
    parser.add_argument("--expected", type=Path, default=EXPECTED)
    parser.add_argument("--acquisition", type=Path, default=ACQUISITION)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    expected = load_json(args.expected)
    acquisition_rows = load_jsonl(args.acquisition)
    expected_entries = expected.get("entries") if isinstance(expected.get("entries"), list) else []

    expected_failures, expected_row_failures = validate_expected(expected)
    acquisition_failures, acquisition_row_failures, acquisition_counts = validate_acquisition(
        acquisition_rows,
        expected_entries,
    )
    error_counts = Counter(expected_failures + acquisition_failures)
    for row in expected_row_failures + acquisition_row_failures:
        error_counts.update(row.get("errors") or [])

    present_expected = sum(1 for row in expected_entries if row.get("status") == "present")
    report = {
        "local_only": True,
        "expected_manifest": str(args.expected),
        "acquisition_manifest": str(args.acquisition),
        "expected_entries": len(expected_entries),
        "expected_present_rows": present_expected,
        "acquisition_rows": len(acquisition_rows),
        "acquisition_present_rows": acquisition_counts.get("present_rows", 0),
        "sha256_checked_rows": acquisition_counts.get("sha256_checked_rows", 0),
        "sha256_mismatch_rows": acquisition_counts.get("sha256_mismatch_rows", 0),
        "coordinate_cache_real_data_ready": acquisition_counts.get("present_rows", 0) > 0,
        "chain_mapping_review_required": True,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "success": not expected_failures and not acquisition_failures and not expected_row_failures and not acquisition_row_failures,
        "failures": expected_failures + acquisition_failures,
        "expected_row_failures": expected_row_failures[:200],
        "acquisition_row_failures": acquisition_row_failures[:200],
        "error_counts": dict(error_counts),
        "policy": "Structure cache validation proves local coordinate files only; reviewed chain mapping and numbering remain separate gates.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "expected_entries": report["expected_entries"],
        "acquisition_rows": report["acquisition_rows"],
        "acquisition_present_rows": report["acquisition_present_rows"],
        "sha256_mismatch_rows": report["sha256_mismatch_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
