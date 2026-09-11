#!/usr/bin/env python3
"""Fail-closed audit for general enzyme experimental records."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


SEQUENCE_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$")
ALLOWED_METRICS = {"km", "kcat", "kcat/km", "tm", "ph", "activity", "stability", "mutation_effect"}
ALLOWED_LICENSES = {"approved", "research_only", "cc-by-4.0", "cc-by-nc-nd-4.0", "mit"}


def audit_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(rows)
    errors: List[str] = []
    seen = set()
    sequence_splits: Dict[str, set] = {}
    source_splits: Dict[str, set] = {}
    head_counts: Counter = Counter()
    groups = set()
    replicates = set()
    for row in rows:
        metric = str(row.get("metric") or "").lower()
        sequence_hash = str(row.get("sequence_hash") or "")
        split = str(row.get("split") or "")
        key = (sequence_hash, row.get("mutation"), metric, row.get("value_si"), row.get("source_id"))
        if key in seen:
            errors.append("duplicate_record")
        seen.add(key)
        if not sequence_hash or (row.get("protein_sequence") and not SEQUENCE_RE.fullmatch(str(row["protein_sequence"]))):
            errors.append("invalid_sequence")
        if metric not in ALLOWED_METRICS:
            errors.append("unsupported_metric")
        if row.get("quality_flags"):
            errors.append("row_quality_flags")
        license_status = str(row.get("license_status") or row.get("license") or "")
        if license_status not in ALLOWED_LICENSES:
            errors.append("license_blocked")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("source_file_sha256") or "")):
            errors.append("missing_source_hash")
        if sequence_hash and split:
            sequence_splits.setdefault(sequence_hash, set()).add(split)
        source_id = str(row.get("source_id") or "")
        if source_id and split:
            source_splits.setdefault(source_id, set()).add(split)
        groups.add(str(row.get("enzyme_family") or sequence_hash))
        if row.get("replicate_id"):
            replicates.add(str(row["replicate_id"]))
        head_counts[metric] += 1
    if any(len(splits) > 1 for splits in sequence_splits.values()):
        errors.append("sequence_group_cross_split")
    if any(len(splits) > 1 for splits in source_splits.values()):
        errors.append("source_group_cross_split")
    unique_errors = sorted(set(errors))
    status = "passed" if rows and not unique_errors else ("blocked_no_records" if not rows else "blocked_quality_check")
    return {
        "status": status,
        "row_count": len(rows),
        "group_count": len(groups),
        "replicate_count": len(replicates),
        "metric_counts": dict(head_counts),
        "errors": unique_errors,
        "training_import_allowed": bool(rows) and not unique_errors,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Any unresolved quality, license, provenance, or split error blocks training import.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = audit_rows(rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["training_import_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
