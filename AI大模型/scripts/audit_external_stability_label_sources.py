#!/usr/bin/env python3
"""Audit local external stability label files before any supervised import."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
THERMOMPNN_DATA = AI_ROOT / "cache" / "external" / "ThermoMPNN" / "data_all"
REPORT_OUT = AI_ROOT / "reports" / "external_stability_label_source_audit_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "curation" / "external_stability_label_source_candidates.jsonl"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def as_float(value: Any) -> float | None:
    try:
        if value in {None, "", "-"}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def source_family(path: Path) -> str:
    name = path.name.lower()
    if "fireprot" in name:
        return "fireprot_curated_stability"
    if "mega" in name:
        return "megascale_proteolysis_stability"
    if "s669" in name:
        return "s669_ddg_benchmark"
    if "ssym" in name:
        return "ssym_ddg_benchmark"
    if "myoglobin" in name:
        return "myoglobin_p53_ddg_benchmark"
    return "unknown"


def audit_file(path: Path) -> dict[str, Any]:
    fields, rows = csv_rows(path)
    family = source_family(path)
    numeric_ddg_fields = [field for field in ["ddG", "DDG", "ddG_ML"] if field in fields]
    sequence_fields = [field for field in ["sequence", "SEQ", "aa_seq", "wt_seq", "pdb_sequence"] if field in fields]
    mutation_fields = [field for field in ["mutation", "MUT", "mut_type"] if field in fields]
    wt_fields = [field for field in ["wild_type"] if field in fields]
    position_fields = [field for field in ["position", "pdb_position"] if field in fields]
    source_fields = [field for field in ["publication_doi", "publication_pubmed", "datasets", "experiment_id"] if field in fields]

    usable_numeric_rows = 0
    curated_rows = 0
    publication_rows = 0
    self_consistent_rows = 0
    mutation_style_counts: Counter[str] = Counter()
    dataset_counts: Counter[str] = Counter()
    for row in rows:
        ddg = next((as_float(row.get(field)) for field in numeric_ddg_fields if as_float(row.get(field)) is not None), None)
        if ddg is not None:
            usable_numeric_rows += 1
        if str(row.get("is_curated")).lower() == "true":
            curated_rows += 1
        if row.get("publication_doi") or row.get("publication_pubmed"):
            publication_rows += 1
        if row.get("datasets"):
            for item in str(row["datasets"]).split("|"):
                if item:
                    dataset_counts[item] += 1
        mutation_token = row.get("MUT") or row.get("mutation") or row.get("mut_type") or ""
        if mutation_token:
            if mutation_token == "wt":
                mutation_style_counts["wt"] += 1
            elif ":" in mutation_token:
                mutation_style_counts["multi_mutation"] += 1
            elif "ins" in mutation_token or "del" in mutation_token:
                mutation_style_counts["indel"] += 1
            else:
                mutation_style_counts["single_substitution_like"] += 1

        if row.get("wild_type") and row.get("position") and row.get("sequence"):
            pos = int(float(row["position"])) if str(row["position"]).replace(".", "", 1).isdigit() else None
            seq = row["sequence"]
            if pos and 1 <= pos <= len(seq) and seq[pos - 1] == row["wild_type"]:
                self_consistent_rows += 1
        elif row.get("MUT") and row.get("SEQ"):
            mut = row["MUT"]
            seq = row["SEQ"]
            if len(mut) >= 3 and mut[1:-1].isdigit():
                pos = int(mut[1:-1])
                if 1 <= pos <= len(seq) and seq[pos - 1] == mut[0]:
                    self_consistent_rows += 1

    blockers = []
    if not numeric_ddg_fields:
        blockers.append("no_numeric_ddg_field")
    if not mutation_fields:
        blockers.append("no_mutation_field")
    if not sequence_fields:
        blockers.append("no_sequence_field")
    if family == "unknown":
        blockers.append("unknown_source_family")
    if usable_numeric_rows == 0:
        blockers.append("no_usable_numeric_rows")
    blockers.extend([
        "not_mapped_into_kwb_training_schema",
        "not_reviewed_for_label_direction_against_kwb_policy",
        "not_checked_for_train_test_leakage_against_kwb_benchmarks",
        "not_claim_eligible_without_reviewed_import_receipt",
    ])
    ready_as_import_candidate = usable_numeric_rows > 0 and bool(mutation_fields) and bool(sequence_fields)
    return {
        "source_file": str(path.relative_to(AI_ROOT)),
        "source_family": family,
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
        "row_count": len(rows),
        "field_count": len(fields),
        "fields": fields,
        "numeric_ddg_fields": numeric_ddg_fields,
        "sequence_fields": sequence_fields,
        "mutation_fields": mutation_fields,
        "wild_type_fields": wt_fields,
        "position_fields": position_fields,
        "source_reference_fields": source_fields,
        "usable_numeric_rows": usable_numeric_rows,
        "curated_rows": curated_rows,
        "publication_reference_rows": publication_rows,
        "self_consistent_numbering_rows_sample_rule": self_consistent_rows,
        "mutation_style_counts": dict(mutation_style_counts),
        "dataset_counts_top10": dict(dataset_counts.most_common(10)),
        "ready_as_external_import_candidate": ready_as_import_candidate,
        "claim_eligible_now": False,
        "blockers": blockers,
        "policy": "Audit only. External rows require reviewed import, direction normalization, leakage review and schema mapping before training use.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit external stability label source files")
    parser.add_argument("--source-root", type=Path, default=THERMOMPNN_DATA)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    files = sorted(args.source_root.rglob("*.csv")) if args.source_root.exists() else []
    rows = [audit_file(path) for path in files]
    families = Counter(row["source_family"] for row in rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_root": str(args.source_root),
        "source_file_count": len(rows),
        "total_rows": sum(row["row_count"] for row in rows),
        "total_usable_numeric_rows": sum(row["usable_numeric_rows"] for row in rows),
        "ready_import_candidate_files": sum(1 for row in rows if row["ready_as_external_import_candidate"]),
        "claim_eligible_rows_now": 0,
        "source_family_counts": dict(families),
        "jsonl": str(args.jsonl),
        "rows": rows,
        "next_steps": [
            "Choose allowed source family and license scope.",
            "Normalize ddG direction and units per dataset family.",
            "Map rows into KWB schema with source_file_sha256 and reviewed import receipt.",
            "Run train/test leakage review before any supervised training use.",
            "Keep model-quality claim blocked until claim-eligible real supervised rows >=100.",
        ],
        "safe_for_model_claim": False,
        "policy": "This report creates candidate evidence only; it does not import labels into KWB supervised training.",
    }
    write_jsonl(args.jsonl, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_file_count": report["source_file_count"],
        "total_rows": report["total_rows"],
        "total_usable_numeric_rows": report["total_usable_numeric_rows"],
        "ready_import_candidate_files": report["ready_import_candidate_files"],
        "claim_eligible_rows_now": report["claim_eligible_rows_now"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
