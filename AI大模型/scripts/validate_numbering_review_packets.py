#!/usr/bin/env python3
"""Validate numbering review packets and their draft decisions.

Packets and drafts are operator review aids only. This validator confirms the
packet slices still match the worklist and that draft rows remain unresolved
weak placeholders rather than reviewed curation decisions.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "curation" / "numbering_review_worklist.jsonl"
PACKET_DIR = AI_ROOT / "datasets" / "curation" / "numbering_review_packets"
DRAFT_DIR = AI_ROOT / "datasets" / "curation" / "numbering_review_decision_drafts"
STATUS_OUT = AI_ROOT / "datasets" / "curation" / "numbering_review_packets_status.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_review_packet_validation_report.json"

PACKET_GROUPS = [
    {
        "prefix": "numbering_review_enzyme_fireprot_manual",
        "bucket_filter": {"enzyme_ec_confirmed_fireprot_manual_review"},
    },
    {
        "prefix": "numbering_review_enzyme_fireprot",
        "bucket_filter": {"enzyme_ec_confirmed_fireprot"},
    },
    {
        "prefix": "numbering_review_isoform_exact",
        "bucket_filter": {"isoform_exact_plus_abstract_signal", "isoform_exact_candidate"},
    },
    {
        "prefix": "numbering_review_abstract_signal",
        "bucket_filter": {"abstract_signal"},
    },
    {
        "prefix": "numbering_review_pubmed_missing",
        "bucket_filter": {"pubmed_missing_or_invalid"},
    },
    {
        "prefix": "numbering_review_low_signal_high_risk",
        "bucket_filter": {"low_signal_high_risk"},
    },
]

VALID_DRAFT_DECISIONS = {"keep_unresolved_weak"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def validate_packet_rows(actual: list[dict[str, Any]], expected: list[dict[str, Any]], bucket_filter: set[str]) -> list[str]:
    errors: list[str] = []
    if actual != expected:
        errors.append("packet_rows_mismatch_worklist_slice")
    if not actual:
        errors.append("packet_empty")
        return errors
    if any(row.get("review_bucket") not in bucket_filter for row in actual):
        errors.append("packet_bucket_filter_mismatch")
    ranks = [int(row.get("review_rank") or 0) for row in actual]
    if ranks != sorted(ranks):
        errors.append("packet_review_rank_not_sorted")
    if any(not row.get("record_id") for row in actual):
        errors.append("packet_missing_record_id")
    return errors


def validate_draft_rows(
    actual: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
    packet_id: str,
) -> list[str]:
    errors: list[str] = []
    if len(actual) != len(packet_rows):
        errors.append("draft_row_count_mismatch")
    actual_ids = [str(row.get("record_id") or "") for row in actual]
    packet_ids = [str(row.get("record_id") or "") for row in packet_rows]
    if actual_ids != packet_ids:
        errors.append("draft_record_order_mismatch")
    for draft, packet_row in zip(actual, packet_rows):
        record_id = str(packet_row.get("record_id") or "")
        if draft.get("record_id") != record_id:
            errors.append("draft_record_id_mismatch")
            continue
        if draft.get("decision") not in VALID_DRAFT_DECISIONS:
            errors.append("draft_decision_not_unresolved_weak")
        if draft.get("mapping_basis") != "unresolved":
            errors.append("draft_mapping_basis_not_unresolved")
        if float(draft.get("confidence") or 0.0) != 0.0:
            errors.append("draft_confidence_not_zero")
        if draft.get("canonical_position") is not None:
            errors.append("draft_canonical_position_not_null")
        if draft.get("canonical_wild_type") is not None:
            errors.append("draft_canonical_wild_type_not_null")
        expected_mutant = str(packet_row.get("reported_mutation") or "")[-1:]
        if draft.get("canonical_mutant") != expected_mutant:
            errors.append("draft_canonical_mutant_mismatch")
        refs = draft.get("source_refs") or []
        if not isinstance(refs, list) or not refs:
            errors.append("draft_source_refs_missing")
        else:
            ref_text = " ".join(str(item) for item in refs)
            if packet_row.get("literature_ref") and str(packet_row.get("literature_ref")) not in ref_text:
                errors.append("draft_source_refs_missing_literature_ref")
            if f"UniProt:{packet_row.get('uniprot_id')}" not in ref_text:
                errors.append("draft_source_refs_missing_uniprot")
        notes = str(draft.get("notes") or "").lower()
        if "keep unresolved" not in notes:
            errors.append("draft_notes_missing_fail_closed_language")
        if "draft_only" not in str(draft.get("draft_policy") or "").lower():
            errors.append("draft_policy_missing_draft_only")
        if packet_id not in str(draft.get("notes") or ""):
            errors.append("draft_notes_missing_packet_id")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate numbering review packets")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--packet-dir", type=Path, default=PACKET_DIR)
    parser.add_argument("--draft-dir", type=Path, default=DRAFT_DIR)
    parser.add_argument("--status-out", type=Path, default=STATUS_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    worklist = load_jsonl(args.worklist)
    status_rows: list[dict[str, Any]] = []
    packet_reports: list[dict[str, Any]] = []
    error_counts = Counter()
    total_packet_rows = 0
    total_draft_rows = 0
    valid_packet_rows = 0
    valid_draft_rows = 0
    expected_packet_ids: list[str] = []
    packet_files = sorted(path for path in args.packet_dir.glob("*.jsonl") if not path.name.endswith(".status.jsonl"))

    filtered_by_prefix: dict[str, list[dict[str, Any]]] = {}
    for spec in PACKET_GROUPS:
        filtered_by_prefix[spec["prefix"]] = [
            row for row in worklist if str(row.get("review_bucket") or "") in spec["bucket_filter"]
        ]
        for index in range(0, len(filtered_by_prefix[spec["prefix"]]), 25):
            expected_packet_ids.append(f"{spec['prefix']}_{(index // 25) + 1:03d}")

    for packet_file in packet_files:
        packet_id = packet_file.stem
        spec = next((item for item in PACKET_GROUPS if packet_id.startswith(item["prefix"])), None)
        packet_rows = load_jsonl(packet_file)
        draft_file = args.draft_dir / f"{packet_id}.decisions.draft.jsonl"
        draft_rows = load_jsonl(draft_file)
        expected_packet_rows: list[dict[str, Any]] = []
        packet_errors = ["unknown_packet_prefix"] if spec is None else []

        if spec is not None:
            filtered = filtered_by_prefix[spec["prefix"]]
            packet_index = [path.stem for path in packet_files if path.stem.startswith(spec["prefix"])].index(packet_id)
            expected_packet_rows = chunks(filtered, 25)[packet_index]
            packet_errors.extend(validate_packet_rows(packet_rows, expected_packet_rows, spec["bucket_filter"]))
            draft_errors = validate_draft_rows(draft_rows, packet_rows, packet_id)
        else:
            draft_errors = ["unknown_packet_prefix"]

        total_packet_rows += len(packet_rows)
        total_draft_rows += len(draft_rows)
        valid_packet = not packet_errors
        valid_draft = not draft_errors
        valid_packet_rows += len(packet_rows) if valid_packet else 0
        valid_draft_rows += len(draft_rows) if valid_draft else 0
        error_counts.update(packet_errors)
        error_counts.update(draft_errors)

        status_rows.append({
            "packet_id": packet_id,
            "review_order": [row.get("record_id") for row in packet_rows[:3]],
            "packet_rows": len(packet_rows),
            "draft_rows": len(draft_rows),
            "valid_packet": valid_packet,
            "valid_draft": valid_draft,
            "completion_ready": False,
            "requires_human_input": True,
            "errors": packet_errors + draft_errors,
            "policy": "Packet and draft validation only; reviewed numbering decisions remain manual and outside this validator.",
        })
        packet_reports.append({
            "packet_id": packet_id,
            "rows": len(packet_rows),
            "valid_rows": len(packet_rows) if valid_packet else 0,
            "invalid_rows": 0 if valid_packet else len(packet_rows),
            "draft_rows": len(draft_rows),
            "draft_valid_rows": len(draft_rows) if valid_draft else 0,
            "draft_invalid_rows": 0 if valid_draft else len(draft_rows),
            "bucket_counts": dict(Counter(str(row.get("review_bucket") or "") for row in packet_rows)),
            "draft_decision_counts": dict(Counter(str(row.get("decision") or "") for row in draft_rows)),
            "expected_packet_rows": len(expected_packet_rows),
            "packet_file": str(packet_file),
            "draft_file": str(draft_file),
        })

    expected_packet_rows = len(worklist)
    packet_count = len(packet_files)
    draft_count = len([path for path in args.draft_dir.glob("*.jsonl") if path.name.endswith(".decisions.draft.jsonl")])
    all_valid = not error_counts and valid_packet_rows == total_packet_rows and valid_draft_rows == total_draft_rows
    expected_packet_count = len(expected_packet_ids)
    actual_packet_ids = [path.stem for path in packet_files]
    missing_packet_rows = len(sorted(set(expected_packet_ids) - set(actual_packet_ids)))
    unexpected_packet_rows = len(sorted(set(actual_packet_ids) - set(expected_packet_ids)))
    duplicate_packet_rows = len(actual_packet_ids) - len(set(actual_packet_ids))

    write_jsonl(args.status_out, status_rows)
    report = {
        "local_only": True,
        "worklist_rows": len(worklist),
        "packet_count": packet_count,
        "draft_count": draft_count,
        "packet_rows": total_packet_rows,
        "draft_rows": total_draft_rows,
        "valid_packet_rows": valid_packet_rows,
        "invalid_packet_rows": total_packet_rows - valid_packet_rows,
        "valid_draft_rows": valid_draft_rows,
        "invalid_draft_rows": total_draft_rows - valid_draft_rows,
        "expected_packet_rows": expected_packet_rows,
        "expected_packet_count": expected_packet_count,
        "missing_packet_rows": missing_packet_rows,
        "unexpected_packet_rows": unexpected_packet_rows,
        "duplicate_packet_rows": duplicate_packet_rows,
        "status_rows": len(status_rows),
        "completion_ready_rows": 0,
        "requires_human_input_rows": len(status_rows),
        "ready_for_decision_write_rows": 0,
        "ready_for_apply_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "all_numbering_review_packets_valid": all_valid,
        "packet_reports": packet_reports,
        "error_counts": dict(error_counts),
        "status_output": str(args.status_out),
        "packet_directory": str(args.packet_dir),
        "draft_directory": str(args.draft_dir),
        "policy": "Numbering review packets are review aids only; this validator never writes reviewed curation decisions or supervised labels.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "packet_count": packet_count,
        "valid_packet_rows": report["valid_packet_rows"],
        "valid_draft_rows": report["valid_draft_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
