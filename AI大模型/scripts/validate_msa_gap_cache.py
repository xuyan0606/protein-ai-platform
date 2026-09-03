#!/usr/bin/env python3
"""Validate isolated MSA/conservation artifacts before human intake review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

AI_ROOT = Path(__file__).resolve().parents[1]
INTAKE = AI_ROOT / "datasets/curation/msa_gap_trusted_cache_intake.local.jsonl"
REPORT = AI_ROOT / "reports/msa_gap_cache_validation_report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve(value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else AI_ROOT / path


def parse_fasta(path: Path) -> list[tuple[str, str]]:
    records = []
    header = None
    sequence: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(sequence)))
            header, sequence = line[1:].strip(), []
        elif header is not None:
            sequence.append(line.strip())
    if header is not None:
        records.append((header, "".join(sequence)))
    return records


def validate_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    msa = resolve(row.get("msa_path"))
    conservation = resolve(row.get("conservation_feature_path"))
    if not msa.exists():
        return ["msa_file_missing"]
    if not conservation.exists():
        return ["conservation_file_missing"]
    records = parse_fasta(msa)
    if not records or not records[0][0].startswith(f"{row.get('uniprot_id')}|query"):
        errors.append("msa_query_missing")
    query = records[0][1] if records else ""
    expected_length = int(row.get("sequence_length") or 0)
    if len(query) != expected_length:
        errors.append("msa_query_length_mismatch")
    try:
        payload = json.loads(conservation.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return errors + ["conservation_json_invalid"]
    if payload.get("uniprot_id") != row.get("uniprot_id"):
        errors.append("conservation_uniprot_mismatch")
    values = payload.get("position_conservation")
    if not isinstance(values, list) or len(values) != expected_length:
        errors.append("conservation_length_mismatch")
    elif any(not isinstance(value, (int, float)) or not 0 <= float(value) <= 1 for value in values):
        errors.append("conservation_value_invalid")
    if row.get("msa_sha256") and sha256(msa) != str(row["msa_sha256"]).lower():
        errors.append("msa_sha256_mismatch")
    if row.get("conservation_sha256") and sha256(conservation) != str(row["conservation_sha256"]).lower():
        errors.append("conservation_sha256_mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MSA gap cache")
    parser.add_argument("--intake", type=Path, default=INTAKE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.intake.read_text(encoding="utf-8").splitlines() if line.strip()] if args.intake.exists() else []
    records = [{"uniprot_id": row.get("uniprot_id"), "valid": not validate_row(row), "errors": validate_row(row)} for row in rows]
    report = {
        "local_only": True,
        "input_rows": len(rows),
        "valid_rows": sum(item["valid"] for item in records),
        "invalid_rows": sum(not item["valid"] for item in records),
        "records": records,
        "ready_for_manual_intake_review": bool(rows) and all(item["valid"] for item in records),
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Artifact validation only; formal manifest intake and human review remain required.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
