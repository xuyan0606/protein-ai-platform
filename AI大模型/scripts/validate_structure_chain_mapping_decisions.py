#!/usr/bin/env python3
"""Validate reviewed structure chain mapping decisions before applying them."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_worklist.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_decisions.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json"

VALID_DECISIONS = {"set_chain_mapping", "keep_unreviewed", "reject_structure"}
REVIEWED_MAPPING_STATUSES = {
    "exact_sequence_match",
    "reviewed_with_missing_residues",
    "reviewed_with_construct_or_tags",
    "manual_alignment_reviewed",
}
VALID_MAPPING_STATUSES = REVIEWED_MAPPING_STATUSES | {"unreviewed", "rejected"}
REVIEWED_NUMBERING_BASES = {
    "sifts_uniprot_mapping",
    "pdb_label_seq_id",
    "pdb_author_numbering",
    "manual_alignment",
}
VALID_NUMBERING_BASES = REVIEWED_NUMBERING_BASES | {"unreviewed", "rejected"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize_structure_id(value: Any) -> str:
    return str(value or "").strip().upper()


def validate_missing_ranges(value: Any, seq_len: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return ["missing_residue_ranges_not_list"]
    for item in value:
        if not isinstance(item, dict):
            errors.append("missing_residue_range_not_object")
            continue
        start = item.get("start_pos")
        end = item.get("end_pos")
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append("missing_residue_range_missing_integer_bounds")
        elif start < 1 or end < start or (seq_len and end > seq_len):
            errors.append("missing_residue_range_invalid_bounds")
        if not item.get("basis"):
            errors.append("missing_residue_range_missing_basis")
    return errors


def validate(
    row: dict[str, Any],
    worklist_by_id: dict[str, dict[str, Any]],
    seen: set[str],
) -> list[str]:
    errors: list[str] = []
    structure_id = normalize_structure_id(row.get("structure_id"))
    worklist_row = worklist_by_id.get(structure_id)
    if not structure_id:
        errors.append("missing_structure_id")
    elif structure_id in seen:
        errors.append("duplicate_structure_id")
    elif not worklist_row:
        errors.append("structure_id_not_in_worklist")
    seen.add(structure_id)

    decision = row.get("decision")
    if decision not in VALID_DECISIONS:
        errors.append("invalid_decision")
    confidence = row.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        errors.append("invalid_confidence")
    source_refs = row.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs or not all(isinstance(item, str) and item for item in source_refs):
        errors.append("invalid_source_refs")
    if not row.get("curator"):
        errors.append("missing_curator")
    if not row.get("curated_at"):
        errors.append("missing_curated_at")

    mapping_status = row.get("sequence_to_structure_mapping_status")
    if mapping_status not in VALID_MAPPING_STATUSES:
        errors.append("invalid_sequence_to_structure_mapping_status")
    numbering_basis = row.get("residue_numbering_basis")
    if numbering_basis not in VALID_NUMBERING_BASES:
        errors.append("invalid_residue_numbering_basis")

    seq_len = int(worklist_row.get("seq_length") or 0) if worklist_row else 0
    errors.extend(validate_missing_ranges(row.get("missing_residue_ranges"), seq_len))

    if decision == "set_chain_mapping":
        selected_chain = row.get("selected_chain_id")
        parsed_chain_ids = set(worklist_row.get("parsed_chain_ids") or []) if worklist_row else set()
        expected_uniprot = worklist_row.get("uniprot_id") if worklist_row else None
        if not isinstance(selected_chain, str) or not selected_chain:
            errors.append("missing_selected_chain_id")
        elif parsed_chain_ids and selected_chain not in parsed_chain_ids:
            errors.append("selected_chain_not_in_parsed_structure")
        if row.get("canonical_uniprot_id") != expected_uniprot:
            errors.append("canonical_uniprot_mismatch")
        if mapping_status not in REVIEWED_MAPPING_STATUSES:
            errors.append("set_mapping_requires_reviewed_mapping_status")
        if numbering_basis not in REVIEWED_NUMBERING_BASES:
            errors.append("set_mapping_requires_reviewed_numbering_basis")
        if isinstance(confidence, (int, float)) and float(confidence) < 0.7:
            errors.append("low_confidence_for_chain_mapping")
    elif decision == "keep_unreviewed":
        if row.get("selected_chain_id") is not None:
            errors.append("keep_unreviewed_must_not_select_chain")
        if mapping_status != "unreviewed":
            errors.append("keep_unreviewed_requires_unreviewed_mapping_status")
        if numbering_basis != "unreviewed":
            errors.append("keep_unreviewed_requires_unreviewed_numbering_basis")
    elif decision == "reject_structure":
        if mapping_status != "rejected":
            errors.append("reject_structure_requires_rejected_mapping_status")
        if numbering_basis != "rejected":
            errors.append("reject_structure_requires_rejected_numbering_basis")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate structure chain mapping decisions")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    worklist_rows = load_jsonl(args.worklist)
    decisions = load_jsonl(args.decisions)
    worklist_by_id = {normalize_structure_id(row.get("structure_id")): row for row in worklist_rows}
    seen: set[str] = set()
    records = []
    error_counts = Counter()
    for row in decisions:
        errors = validate(row, worklist_by_id, seen)
        error_counts.update(errors)
        records.append({
            "structure_id": normalize_structure_id(row.get("structure_id")),
            "decision": row.get("decision"),
            "valid": not errors,
            "errors": errors,
        })

    report = {
        "worklist_rows": len(worklist_rows),
        "decision_rows": len(decisions),
        "valid_rows": sum(1 for row in records if row["valid"]),
        "invalid_rows": sum(1 for row in records if not row["valid"]),
        "reviewed_chain_mapping_rows": sum(
            1
            for row, record in zip(decisions, records)
            if record["valid"] and row.get("decision") == "set_chain_mapping"
        ),
        "error_counts": dict(error_counts),
        "records": records[:200],
        "policy": "set_chain_mapping requires reviewed biological chain, reviewed numbering basis, matching UniProt, parsed chain membership, and confidence >= 0.7",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": report["decision_rows"],
        "valid_rows": report["valid_rows"],
        "invalid_rows": report["invalid_rows"],
        "reviewed_chain_mapping_rows": report["reviewed_chain_mapping_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
