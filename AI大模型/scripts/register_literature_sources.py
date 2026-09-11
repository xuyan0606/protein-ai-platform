#!/usr/bin/env python3
"""Validate literature discovery records without inventing source evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


PRIMARY_TYPES = {"primary_data_file", "paper_fulltext", "supplementary_table", "author_repository"}
ALLOWED_STATUSES = {"needs_review", "research_candidate", "research_only", "blocked_license"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("line %d is not a JSON object" % line_number)
        rows.append(value)
    return rows


def validate_source_manifest(path: Path) -> Dict[str, Any]:
    rows = _load(path)
    errors: List[str] = []
    valid_rows = 0
    row_results: List[Dict[str, Any]] = []
    for row in rows:
        row_errors: List[str] = []
        if not row.get("source_id"):
            row_errors.append("missing_source_id")
        if not row.get("discovery_engine") or not row.get("query") or not row.get("result_url"):
            row_errors.append("missing_discovery_fields")
        evidence_type = str(row.get("evidence_type") or "")
        source_file = Path(str(row.get("source_file") or ""))
        if evidence_type == "search_result":
            row_errors.append("search_result_not_primary_evidence")
        if evidence_type not in PRIMARY_TYPES:
            row_errors.append("missing_primary_evidence_type")
        if not row.get("primary_evidence_url"):
            row_errors.append("missing_primary_evidence_url")
        if not source_file.is_file():
            row_errors.append("source_file_missing")
        else:
            expected = str(row.get("source_file_sha256") or "")
            actual = _sha256(source_file)
            if expected != actual:
                row_errors.append("source_hash_mismatch")
        if not row.get("license"):
            row_errors.append("missing_license")
        if str(row.get("training_import_status") or "") not in ALLOWED_STATUSES:
            row_errors.append("invalid_training_import_status")
        if row_errors:
            errors.extend(row_errors)
        else:
            valid_rows += 1
        row_results.append({"source_id": row.get("source_id"), "errors": sorted(set(row_errors)), "training_import_allowed": not row_errors})
    unique_errors = sorted(set(errors))
    return {
        "source_rows": len(rows),
        "valid_rows": valid_rows,
        "errors": unique_errors,
        "rows": row_results,
        "training_import_allowed": bool(rows) and not unique_errors,
        "formal_intake_authorized": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Search results are discovery evidence only; primary files, hashes, licenses, and provenance are required.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    result = validate_source_manifest(args.manifest)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["training_import_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
