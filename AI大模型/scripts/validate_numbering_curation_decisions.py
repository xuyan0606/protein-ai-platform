#!/usr/bin/env python3
"""Validate numbering curation decisions before applying them."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
QUEUE = AI_ROOT / "datasets" / "curation" / "numbering_curation_queue.jsonl"
DEEP_AUDIT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_all_stability_records.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_curation_validation_report.json"

VALID_DECISIONS = {"map_to_canonical", "keep_unresolved_weak", "reject_label"}
VALID_BASIS = {
    "uniprot_version_alignment",
    "isoform_alignment",
    "literature_sequence_alignment",
    "author_numbering_mapping",
    "manual_expert_review",
    "unresolved",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_sequences(db_path: Path) -> dict[str, str]:
    with connect_ro(db_path) as conn:
        rows = conn.execute("SELECT uniprot_id, sequence FROM enzyme_records").fetchall()
    return {row["uniprot_id"]: row["sequence"] for row in rows}


def independent_real_source_reviewed(row: dict[str, Any]) -> bool:
    refs = row.get("source_refs")
    if not isinstance(refs, list):
        return False
    return any(str(ref).startswith("ReviewedSourceReceipt:") for ref in refs)


def validate_row(
    row: dict[str, Any],
    queue_ids: set[str],
    sequences: dict[str, str],
    deep_audit_by_record: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    record_id = row.get("record_id")
    if not record_id:
        errors.append("missing_record_id")
    elif record_id not in queue_ids:
        errors.append("record_id_not_in_curation_queue")
    decision = row.get("decision")
    if decision not in VALID_DECISIONS:
        errors.append("invalid_decision")
    basis = row.get("mapping_basis")
    if basis not in VALID_BASIS:
        errors.append("invalid_mapping_basis")
    confidence = row.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        errors.append("invalid_confidence")

    if decision == "map_to_canonical":
        audit = deep_audit_by_record.get(str(record_id))
        if (
            audit
            and audit.get("audit_recommended_decision") == "reject_label"
            and not independent_real_source_reviewed(row)
        ):
            errors.append("deep_audit_reject_rows_cannot_map_without_reviewed_source_receipt")
        uniprot_id = row.get("canonical_uniprot_id")
        pos = row.get("canonical_position")
        wt = str(row.get("canonical_wild_type") or "").upper()
        mutant = str(row.get("canonical_mutant") or "").upper()
        if not uniprot_id or not pos or not wt or not mutant:
            errors.append("missing_canonical_fields")
        else:
            sequence = sequences.get(str(uniprot_id))
            if not sequence:
                errors.append("missing_canonical_sequence")
            elif not isinstance(pos, int) or pos < 1 or pos > len(sequence):
                errors.append("canonical_position_out_of_range")
            elif sequence[pos - 1].upper() != wt:
                errors.append("canonical_wild_type_mismatch")
        if isinstance(confidence, (int, float)) and float(confidence) < 0.5:
            errors.append("low_confidence_for_supervised_promotion")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate numbering curation decisions")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--deep-audit", type=Path, default=DEEP_AUDIT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    decisions = load_jsonl(args.decisions)
    queue_rows = load_jsonl(args.queue)
    deep_audit_rows = load_jsonl(args.deep_audit)
    queue_ids = {row["record_id"] for row in queue_rows if row.get("record_id")}
    deep_audit_by_record = {str(row.get("record_id")): row for row in deep_audit_rows if row.get("record_id")}
    sequences = load_sequences(args.db)
    records = []
    error_counts = Counter()
    inactive_decisions = [
        row for row in decisions
        if str(row.get("record_id") or "") not in queue_ids
    ]
    active_decisions = [
        row for row in decisions
        if str(row.get("record_id") or "") in queue_ids
    ]
    for row in active_decisions:
        errors = validate_row(row, queue_ids, sequences, deep_audit_by_record)
        error_counts.update(errors)
        records.append({
            "record_id": row.get("record_id"),
            "decision": row.get("decision"),
            "valid": not errors,
            "errors": errors,
        })
    blocked_deep_audit_map_rows = sum(
        1
        for record in records
        if "deep_audit_reject_rows_cannot_map_without_reviewed_source_receipt" in record["errors"]
    )
    report = {
        "decision_rows": len(decisions),
        "active_decision_rows": len(active_decisions),
        "inactive_decision_rows": len(inactive_decisions),
        "active_queue_rows": len(queue_ids),
        "valid_rows": sum(1 for row in records if row["valid"]),
        "invalid_rows": sum(1 for row in records if not row["valid"]),
        "deep_audit_rows": len(deep_audit_rows),
        "blocked_deep_audit_map_rows": blocked_deep_audit_map_rows,
        "error_counts": dict(error_counts),
        "records": records[:200],
        "inactive_records_sample": [
            {
                "record_id": row.get("record_id"),
                "decision": row.get("decision"),
                "skip_reason": "record_id_not_in_current_numbering_queue",
            }
            for row in inactive_decisions[:50]
        ],
        "policy": (
            "Only decisions whose record_id is in the current numbering queue are active. "
            "Inactive historical decisions are reported but do not fail current validation. "
            "map_to_canonical requires canonical WT to match the current canonical sequence. "
            "Rows recommended as reject_label by deep audit cannot be mapped unless a ReviewedSourceReceipt is cited."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": report["decision_rows"],
        "active_decision_rows": report["active_decision_rows"],
        "valid_rows": report["valid_rows"],
        "invalid_rows": report["invalid_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
