#!/usr/bin/env python3
"""Build reviewed-import candidates from local ThermoMPNN FireProt CSVs.

This creates a candidate dataset and receipt only. It does not append rows to
KWB supervised training tables or mark rows claim-eligible.
"""

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
SOURCE_FILES = [
    AI_ROOT / "cache" / "external" / "ThermoMPNN" / "data_all" / "training" / "fireprot_train.csv",
    AI_ROOT / "cache" / "external" / "ThermoMPNN" / "data_all" / "training" / "fireprot_val.csv",
    AI_ROOT / "cache" / "external" / "ThermoMPNN" / "data_all" / "testing" / "fireprot_test.csv",
    AI_ROOT / "cache" / "external" / "ThermoMPNN" / "data_all" / "testing" / "fireprot_HF.csv",
]
OUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_stability_import_candidates.jsonl"
RECEIPT_OUT = AI_ROOT / "reports" / "fireprot_curated_stability_import_candidate_receipt.json"
LEAKAGE_OUT = AI_ROOT / "reports" / "fireprot_curated_stability_import_leakage_report.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any) -> float | None:
    try:
        if value in {None, "", "-"}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def make_candidate(source_file: Path, split_name: str, row_index: int, row: dict[str, str]) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    ddg = as_float(row.get("ddG"))
    position = int(float(row["position"])) if str(row.get("position") or "").replace(".", "", 1).isdigit() else None
    wild_type = row.get("wild_type")
    mutant = row.get("mutation")
    sequence = row.get("sequence") or ""
    uniprot_id = row.get("uniprot_id") or None
    if str(row.get("is_curated")).lower() != "true":
        blockers.append("not_fireprot_curated")
    if ddg is None:
        blockers.append("missing_ddg")
    if not uniprot_id:
        blockers.append("missing_uniprot_id")
    if position is None:
        blockers.append("missing_position")
    if not wild_type or not mutant:
        blockers.append("missing_mutation_residue")
    if not sequence:
        blockers.append("missing_sequence")
    if not row.get("publication_doi") and not row.get("publication_pubmed"):
        blockers.append("missing_publication_reference")
    if position and sequence and wild_type and (position < 1 or position > len(sequence) or sequence[position - 1] != wild_type):
        blockers.append("sequence_wt_mismatch")
    if blockers:
        return None, blockers

    mutation = f"{wild_type}{position}{mutant}"
    source_file_rel = str(source_file.relative_to(AI_ROOT))
    source_row_id = f"{source_file_rel}:{row_index}"
    candidate_id = "fireprot-curated-" + hashlib.sha256(source_row_id.encode("utf-8")).hexdigest()[:16]
    ddg_kcal_mol = float(ddg)
    return {
        "candidate_id": candidate_id,
        "source_family": "fireprot_curated_stability",
        "source_file": source_file_rel,
        "source_file_sha256": sha256(source_file),
        "source_row_index": row_index,
        "source_split": split_name,
        "experiment_id": row.get("experiment_id"),
        "protein_name": row.get("protein_name"),
        "uniprot_id": uniprot_id,
        "pdb_id": row.get("pdb_id_corrected") or row.get("pdb_id"),
        "chain": row.get("chain"),
        "mutation": mutation,
        "canonical_position": position,
        "wild_type": wild_type,
        "mutant": mutant,
        "numbering_verified_by_source_sequence": True,
        "ddg_source_value": ddg_kcal_mol,
        "ddg_source_convention": "FireProt/ThermoMPNN CSV ddG; direction kept as source value until KWB normalization review",
        "ddg_kcal_mol_source_direction": ddg_kcal_mol,
        "kwb_direction_normalized": False,
        "dTm_c": as_float(row.get("dTm")),
        "assay_condition": {
            "ph": as_float(row.get("pH")),
            "temperature_c": as_float(row.get("tm")),
            "method": row.get("method") or None,
            "technique": row.get("technique") or None,
            "notes": row.get("notes") or None,
        },
        "publication_doi": row.get("publication_doi") or None,
        "publication_pubmed": row.get("publication_pubmed") or None,
        "datasets": row.get("datasets") or None,
        "sequence_sha256": hashlib.sha256(sequence.encode("utf-8")).hexdigest(),
        "sequence_length": len(sequence),
        "reviewed_import_receipt": None,
        "ready_for_schema_mapping": True,
        "claim_eligible_now": False,
        "blocked_from_training_reasons": [
            "ddg_direction_not_kwb_normalized",
            "not_written_to_kwb_supervised_schema",
            "leakage_review_not_approved_for_training",
            "reviewed_import_receipt_missing",
        ],
        "policy": "Candidate only; do not train until direction normalization, leakage review and reviewed import receipt are complete.",
    }, []


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FireProt curated stability import candidates")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--receipt", type=Path, default=RECEIPT_OUT)
    parser.add_argument("--leakage-report", type=Path, default=LEAKAGE_OUT)
    args = parser.parse_args()

    candidates: list[dict[str, Any]] = []
    excluded_reasons: Counter[str] = Counter()
    source_summaries = []
    for source_file in SOURCE_FILES:
        rows = read_csv(source_file)
        split_name = source_file.stem.replace("fireprot_", "")
        before = len(candidates)
        for idx, row in enumerate(rows, start=2):
            candidate, blockers = make_candidate(source_file, split_name, idx, row)
            if candidate:
                candidates.append(candidate)
            else:
                excluded_reasons.update(blockers)
        source_summaries.append({
            "source_file": str(source_file.relative_to(AI_ROOT)),
            "sha256": sha256(source_file),
            "rows": len(rows),
            "accepted_candidates": len(candidates) - before,
        })

    strict_rows = load_jsonl(AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl")
    benchmark_rows = load_jsonl(AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_strict_mutation_holdout" / "dataset.jsonl")
    strict_keys = {f"{row.get('uniprot_id')}:{row.get('mutation')}" for row in strict_rows}
    candidate_keys = {f"{row.get('uniprot_id')}:{row.get('mutation')}" for row in candidates}
    benchmark_keys = {f"{row.get('uniprot_id')}:{row.get('mutation')}" for row in benchmark_rows}
    leakage = {
        "candidate_rows": len(candidates),
        "strict_supervised_overlap_rows": len(candidate_keys & strict_keys),
        "kwb_strict_holdout_overlap_rows": len(candidate_keys & benchmark_keys),
        "leakage_review_status": "candidate_review_only_not_approved_for_training",
        "policy": "Overlap check is preliminary. Training import remains blocked until split and benchmark leakage policy is approved.",
    }

    write_jsonl(args.output, candidates)
    receipt = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source": "ThermoMPNN bundled FireProt CSVs",
        "candidate_output": str(args.output),
        "source_files": source_summaries,
        "candidate_rows": len(candidates),
        "claim_eligible_rows_now": 0,
        "excluded_reason_counts": dict(excluded_reasons),
        "leakage_report": str(args.leakage_report),
        "ready_for_training_import": False,
        "next_steps": [
            "Review license scope for FireProt-derived labels.",
            "Normalize ddG direction to KWB label convention.",
            "Map to KWB supervised schema with source receipt.",
            "Approve leakage policy before training.",
        ],
        "policy": "Receipt documents candidate provenance only; it is not a reviewed import approval.",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.leakage_report.parent.mkdir(parents=True, exist_ok=True)
    args.leakage_report.write_text(json.dumps(leakage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": len(candidates),
        "claim_eligible_rows_now": 0,
        "strict_supervised_overlap_rows": leakage["strict_supervised_overlap_rows"],
        "kwb_strict_holdout_overlap_rows": leakage["kwb_strict_holdout_overlap_rows"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
