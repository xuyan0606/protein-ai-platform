#!/usr/bin/env python3
"""Build operator review packets for FireProt duplicate candidates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_dedup_aggregation_candidates.jsonl"
OUT_DIR = AI_ROOT / "datasets" / "curation" / "fireprot_dedup_review_packets"
TEMPLATE = AI_ROOT / "datasets" / "curation" / "fireprot_dedup_review_decisions.template.jsonl"
REPORT = AI_ROOT / "reports" / "fireprot_dedup_review_packet_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def priority(row: dict[str, Any]) -> tuple[int, int, str]:
    if not row.get("same_assay_signature"):
        bucket = 0
    elif not row.get("all_labels_identical"):
        bucket = 1
    else:
        bucket = 2
    return (bucket, -int(row.get("duplicate_row_count") or 0), str(row.get("mutation_key") or ""))


def review_row(row: dict[str, Any], packet_id: str, ordinal: int) -> dict[str, Any]:
    if not row.get("same_assay_signature"):
        review_class = "heterogeneous_assay_manual"
        action = "keep_conditions_separate_or_exclude_after_review"
    elif not row.get("all_labels_identical"):
        review_class = "same_assay_value_conflict"
        action = "select_source_row_or_approve_median_after_provenance_review"
    else:
        review_class = "same_assay_exact_repeat"
        action = "confirm_duplicate_provenance_then_select_one_or_approve_median"
    return {
        "packet_id": packet_id,
        "packet_ordinal": ordinal,
        "dedup_candidate_id": row.get("dedup_candidate_id"),
        "mutation_key": row.get("mutation_key"),
        "uniprot_id": row.get("uniprot_id"),
        "mutation": row.get("mutation"),
        "review_class": review_class,
        "review_priority_action": action,
        "duplicate_row_count": row.get("duplicate_row_count"),
        "assay_signature_count": row.get("assay_signature_count"),
        "assay_signatures": row.get("assay_signatures"),
        "source_splits": row.get("source_splits"),
        "source_split_overlap": row.get("source_split_overlap"),
        "source_mapping_ids": row.get("source_mapping_ids"),
        "source_record_ids": row.get("source_record_ids"),
        "source_row_indices": row.get("source_row_indices"),
        "source_file_sha256s": row.get("source_file_sha256s"),
        "observed_label_ddg_values_kcal_mol": row.get("observed_label_ddg_values_kcal_mol"),
        "candidate_median_ddg_kcal_mol": row.get("label_value_median_kcal_mol"),
        "label_value_spread_kcal_mol": row.get("label_value_spread_kcal_mol"),
        "all_labels_identical": row.get("all_labels_identical"),
        "required_human_checks": [
            "confirm source rows refer to the same protein sequence and mutation numbering",
            "confirm source checksum, publication, assay method, pH, and temperature",
            "confirm train/HF/test copies are not independent experiments",
            "for heterogeneous assays, keep conditions separate and never use a pooled median",
            "record reviewer, review date, basis, and receipt before any import consideration",
        ],
        "decision_status": "pending",
        "decision_input_path": "datasets/curation/fireprot_dedup_review_decisions.jsonl",
        "ready_for_training_import": False,
        "claim_eligible_now": False,
        "policy": "Review packet only; no decision, approval, label selection, or training import.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FireProt dedup review packets")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    candidates = sorted(load_jsonl(args.input), key=priority)
    packet_reports: list[dict[str, Any]] = []
    packet_rows = 0
    class_counts: Counter[str] = Counter()
    for start in range(0, len(candidates), args.batch_size):
        packet_number = start // args.batch_size + 1
        packet_id = f"fireprot_dedup_review_{packet_number:03d}"
        batch = candidates[start : start + args.batch_size]
        rows = [review_row(row, packet_id, start + index + 1) for index, row in enumerate(batch)]
        packet_path = args.out_dir / f"{packet_id}.jsonl"
        write_jsonl(packet_path, rows)
        packet_reports.append({
            "packet_id": packet_id,
            "rows": len(rows),
            "path": str(packet_path),
            "decision_input": "datasets/curation/fireprot_dedup_review_decisions.jsonl",
        })
        packet_rows += len(rows)
        class_counts.update(row["review_class"] for row in rows)

    template_row = {
        "dedup_candidate_id": "<required: candidate id from review packet>",
        "decision": "pending",
        "selected_source_mapping_ids": [],
        "approved_label_ddg_kcal_mol": None,
        "approved_assay_signature": None,
        "review_basis": "",
        "source_provenance_checked": False,
        "numbering_reviewed": False,
        "license_scope": None,
        "reviewer": "",
        "reviewed_at": "",
        "reviewed_import_receipt": None,
        "notes": "",
        "policy": (
            "Human decision template only. Allowed decisions are pending, "
            "select_source_row, approve_median, keep_separate, or exclude. "
            "A template row is not a decision and cannot enter training."
        ),
    }
    write_jsonl(args.template, [template_row])
    report = {
        "local_only": True,
        "input": str(args.input),
        "out_dir": str(args.out_dir),
        "template": str(args.template),
        "packet_count": len(packet_reports),
        "packet_rows": packet_rows,
        "review_class_counts": dict(class_counts),
        "decision_rows_present": 0,
        "approved_rows": 0,
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "requires_human_input": True,
        "policy": (
            "Packets and the decision template are operator aids only. No candidate "
            "is approved, selected, numbered, licensed, or imported automatically."
        ),
        "packets": packet_reports,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "packet_count": report["packet_count"],
        "packet_rows": report["packet_rows"],
        "review_class_counts": report["review_class_counts"],
        "decision_rows_present": report["decision_rows_present"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
