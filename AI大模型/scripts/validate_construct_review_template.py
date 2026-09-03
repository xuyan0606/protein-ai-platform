#!/usr/bin/env python3
"""Validate human construct/numbering review input without promoting labels."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

FIELDS = [
    "measurement_id", "construct_accession", "construct_fasta", "parent_accession",
    "parent_sequence", "mature_chain_start", "mature_chain_end", "signal_peptide_length",
    "mutation_notation", "numbering_scheme", "numbering_verified", "condition_comparable",
    "reviewer", "reviewed_at", "review_basis", "authorization_received",
    "authorization_receipt", "review_status",
]
REQUIRED = ("measurement_id", "mutation_notation", "numbering_scheme", "reviewer", "reviewed_at", "authorization_receipt")
BOOL_FIELDS = ("numbering_verified", "condition_comparable", "authorization_received")


def validate(path: Path) -> dict:
    failures = []
    allowed = 0
    rows = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            return {"success": False, "rows": 0, "training_import_allowed_rows": 0, "failure_count": 1,
                    "failures": [{"check": "field_contract"}]}
        seen = set()
        for line, row in enumerate(reader, 2):
            rows += 1
            mid = row.get("measurement_id", "").strip()
            if not mid or mid in seen:
                failures.append({"check": "measurement_id_unique", "line": line})
            seen.add(mid)
            for field in BOOL_FIELDS:
                if row.get(field, "") not in {"", "true", "false"}:
                    failures.append({"check": "boolean_contract", "field": field, "line": line})
            for field in REQUIRED:
                if not row.get(field, "").strip():
                    failures.append({"check": "required_field", "field": field, "line": line})
            if row.get("reviewed_at", "").strip():
                try:
                    datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
                except ValueError:
                    failures.append({"check": "reviewed_at_iso8601", "line": line})
            complete = all(row.get(f) == "true" for f in BOOL_FIELDS) and not failures
            if complete:
                allowed += 1
    return {"success": not failures, "rows": rows, "numbering_verified_rows": 0,
            "condition_comparable_rows": 0, "authorization_received_rows": 0,
            "training_import_allowed_rows": 0, "safe_for_model_claim": False,
            "failure_count": len(failures), "failures": failures,
            "policy": "Validation only; human review and authorization are never inferred or promoted."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.input)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["success"] else 1)
