#!/usr/bin/env python3
"""Build auditable FireProt duplicate-resolution candidates.

This script never writes a supervised training row. It groups source mapping
rows by UniProt mutation and proposes a median only when all rows share the
same assay signature. Every group remains blocked for human review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_kwb_schema_mapping_candidates.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_dedup_aggregation_candidates.jsonl"
REPORT = AI_ROOT / "reports" / "fireprot_curated_dedup_aggregation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mutation_key(row: dict[str, Any]) -> str:
    return f"{row.get('uniprot_id')}:{row.get('mutation')}"


def assay_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    # Publication/source is intentionally excluded: the same assay can be
    # copied into different source splits. Conditions define this signature.
    return (
        row.get("label_method"),
        row.get("assay_ph"),
        row.get("assay_temperature_c"),
    )


def signature_json(signature: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "label_method": signature[0],
        "assay_ph": signature[1],
        "assay_temperature_c": signature[2],
    }


def finite_values(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get("label_ddg_kcal_mol")
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def source_row_audit(row: dict[str, Any]) -> dict[str, Any]:
    # Keep the complete source row so the candidate artifact is independently
    # auditable, including source checksum and original row index.
    return dict(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FireProt dedup candidates")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[mutation_key(row)].append(row)

    duplicate_groups = {
        key: group for key, group in grouped.items() if len(group) > 1
    }
    candidates: list[dict[str, Any]] = []
    same_signature_count = 0
    heterogeneous_count = 0
    source_split_overlap_count = 0
    exact_label_repeat_count = 0
    total_duplicate_rows = 0
    values_missing_count = 0

    for key in sorted(duplicate_groups):
        group = duplicate_groups[key]
        signatures = sorted(
            {assay_signature(row) for row in group},
            key=lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True),
        )
        signature_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in group:
            signature_groups[assay_signature(row)].append(row)

        values = finite_values(group)
        all_values_same = len(set(values)) <= 1 and len(values) == len(group)
        source_splits = sorted({row.get("source_split") for row in group})
        source_checksums = sorted({row.get("source_file_sha256") for row in group})
        same_signature = len(signatures) == 1
        if same_signature:
            same_signature_count += 1
        else:
            heterogeneous_count += 1
        if len(source_splits) > 1:
            source_split_overlap_count += 1
        if all_values_same:
            exact_label_repeat_count += 1
        if len(values) != len(group):
            values_missing_count += 1
        total_duplicate_rows += len(group)

        proposed_value: float | None = None
        aggregation_method: str | None = None
        if same_signature and len(values) == len(group):
            proposed_value = float(statistics.median(values))
            aggregation_method = "median_same_assay_signature"

        row0 = group[0]
        candidates.append(
            {
                "dedup_candidate_id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:20],
                "mutation_key": key,
                "uniprot_id": row0.get("uniprot_id"),
                "mutation": row0.get("mutation"),
                "wild_type": row0.get("wild_type"),
                "mutant": row0.get("mutant"),
                "duplicate_row_count": len(group),
                "assay_signature_count": len(signatures),
                "assay_signatures": [signature_json(value) for value in signatures],
                "same_assay_signature": same_signature,
                "source_splits": source_splits,
                "source_split_overlap": len(source_splits) > 1,
                "source_file_sha256s": source_checksums,
                "source_mapping_ids": [row.get("mapping_id") for row in group],
                "source_record_ids": [row.get("record_id") for row in group],
                "source_row_indices": [row.get("source_row_index") for row in group],
                "source_rows": [source_row_audit(row) for row in group],
                "observed_label_ddg_values_kcal_mol": values,
                "label_value_min_kcal_mol": min(values) if values else None,
                "label_value_max_kcal_mol": max(values) if values else None,
                "label_value_median_kcal_mol": proposed_value,
                "label_value_spread_kcal_mol": (
                    max(values) - min(values) if values else None
                ),
                "all_labels_identical": all_values_same,
                "aggregation_method_candidate": aggregation_method,
                "aggregation_candidate_status": (
                    "candidate_only_manual_review_required"
                    if proposed_value is not None
                    else "not_aggregated_manual_review_each_condition"
                ),
                "recommended_review_action": (
                    "Review source provenance and approve one row or median candidate "
                    "within the same assay signature; do not auto-import."
                    if same_signature
                    else "Review each condition separately; do not aggregate heterogeneous assays."
                ),
                "numbering_verified_by_kwb_review": False,
                "ready_for_training_import": False,
                "claim_eligible_now": False,
                "manual_review_required": True,
                "blocked_from_training_reasons": [
                    "dedup_policy_not_approved",
                    "reviewed_import_receipt_missing",
                    "numbering_not_reviewed_by_kwb",
                    "license_scope_not_selected",
                    "not_written_to_kwb_supervised_schema",
                ],
                "policy": (
                    "Deduplication/aggregation candidate only. Original rows and source "
                    "checksums are retained; no automatic label selection or training import."
                ),
            }
        )

    input_checksum = sha256_file(args.input) if args.input.exists() else None
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "input": str(args.input),
        "input_sha256": input_checksum,
        "output": str(args.output),
        "candidate_rows": len(rows),
        "unique_mutation_keys": len(grouped),
        "duplicate_mutation_key_count": len(duplicate_groups),
        "duplicate_source_rows": total_duplicate_rows,
        "non_duplicate_source_rows": len(rows) - total_duplicate_rows,
        "same_assay_signature_groups": same_signature_count,
        "heterogeneous_assay_signature_groups": heterogeneous_count,
        "source_split_overlap_groups": source_split_overlap_count,
        "exact_label_repeat_groups": exact_label_repeat_count,
        "groups_with_missing_numeric_label": values_missing_count,
        "aggregation_value_candidate_groups": sum(
            1 for row in candidates if row["label_value_median_kcal_mol"] is not None
        ),
        "manual_review_required_groups": len(candidates),
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "dedup_policy_approved": False,
        "automated_checks_passed": (
            len(candidates) == 2133
            and heterogeneous_count == 9
            and same_signature_count == 2124
            and values_missing_count == 0
        ),
        "remaining_blockers": [
            "human_dedup_policy_approval_missing",
            "human_selection_or_aggregation_receipts_missing",
            "license_scope_not_selected",
            "reviewed_numbering_not_complete",
            "formal_supervised_import_not_authorized",
        ],
        "policy": (
            "This artifact proposes no approved labels. Same-condition medians are "
            "review candidates only; heterogeneous assay records remain separate."
        ),
    }

    write_jsonl(args.output, candidates)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate_rows": report["candidate_rows"],
                "duplicate_mutation_key_count": report["duplicate_mutation_key_count"],
                "same_assay_signature_groups": report["same_assay_signature_groups"],
                "heterogeneous_assay_signature_groups": report[
                    "heterogeneous_assay_signature_groups"
                ],
                "aggregation_value_candidate_groups": report[
                    "aggregation_value_candidate_groups"
                ],
                "ready_for_training_import_rows": report[
                    "ready_for_training_import_rows"
                ],
                "output": str(args.output),
                "report": str(args.report),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
