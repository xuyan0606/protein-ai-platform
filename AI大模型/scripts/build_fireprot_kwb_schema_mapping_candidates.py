#!/usr/bin/env python3
"""Map FireProt direction-normalized candidates to a KWB supervised schema draft.

The output is a candidate mapping only. It is intentionally not consumed by
training scripts until license, leakage and reviewed import approvals exist.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_stability_direction_normalized_candidates.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_kwb_schema_mapping_candidates.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "fireprot_curated_kwb_schema_mapping_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def label_from_ddg(ddg: float) -> str:
    if ddg < -1.0:
        return "go"
    if ddg > 2.0:
        return "no_go"
    return "watch"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KWB schema mapping candidates for FireProt rows")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    mapped: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    for row in rows:
        ddg = row.get("kwb_ddg_kcal_mol")
        required = {
            "candidate_id": row.get("candidate_id"),
            "uniprot_id": row.get("uniprot_id"),
            "mutation": row.get("mutation"),
            "canonical_position": row.get("canonical_position"),
            "wild_type": row.get("wild_type"),
            "mutant": row.get("mutant"),
            "kwb_ddg_kcal_mol": ddg,
            "source_file_sha256": row.get("source_file_sha256"),
            "publication_reference": row.get("publication_doi") or row.get("publication_pubmed"),
        }
        missing = [key for key, value in required.items() if value in {None, ""}]
        if missing:
            excluded.update(f"missing_{key}" for key in missing)
            continue
        label_decision = label_from_ddg(float(ddg))
        manual_review = bool(row.get("manual_review_required")) or row.get("kwb_threshold_class") == "near_neutral_manual_review"
        mapped.append({
            "mapping_id": f"kwb-fireprot-map-{row['candidate_id'].replace('fireprot-curated-', '')}",
            "source_candidate_id": row["candidate_id"],
            "record_id": f"external_fireprot:{row['candidate_id']}",
            "source": "external_fireprot_curated_candidate",
            "record_type": "stability_label_candidate",
            "uniprot_id": row["uniprot_id"],
            "group_key": f"uniprot:{row['uniprot_id']}",
            "protein_name": row.get("protein_name"),
            "pdb_id": row.get("pdb_id"),
            "chain": row.get("chain"),
            "seq_length": row.get("sequence_length"),
            "mutation": row["mutation"],
            "mutation_position": row["canonical_position"],
            "wild_type": row["wild_type"],
            "mutant": row["mutant"],
            "numbering_verified_by_source_sequence": row.get("numbering_verified_by_source_sequence") is True,
            "numbering_verified_by_kwb_review": False,
            "label_decision_candidate": label_decision,
            "label_ddg_kcal_mol": float(ddg),
            "negative_ddg_is_stabilizing": True,
            "kwb_threshold_class": row.get("kwb_threshold_class"),
            "label_source_db": "FireProt_curated_via_ThermoMPNN_bundle",
            "label_method": (row.get("assay_condition") or {}).get("method"),
            "assay_ph": (row.get("assay_condition") or {}).get("ph"),
            "assay_temperature_c": (row.get("assay_condition") or {}).get("temperature_c"),
            "publication_doi": row.get("publication_doi"),
            "publication_pubmed": row.get("publication_pubmed"),
            "source_file": row.get("source_file"),
            "source_file_sha256": row.get("source_file_sha256"),
            "source_row_index": row.get("source_row_index"),
            "source_split": row.get("source_split"),
            "reviewed_import_receipt": None,
            "manual_review_required": manual_review,
            "ready_for_training_import": False,
            "claim_eligible_now": False,
            "blocked_from_training_reasons": sorted(set(row.get("blocked_from_training_reasons", []) + [
                "license_scope_not_selected",
                "reviewed_import_receipt_missing",
                "leakage_review_not_approved_for_training",
                "numbering_not_reviewed_by_kwb",
            ])),
            "policy": "KWB schema mapping candidate only; not a supervised training row.",
        })

    write_jsonl(args.output, mapped)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "input": str(args.input),
        "output": str(args.output),
        "input_rows": len(rows),
        "mapped_candidate_rows": len(mapped),
        "excluded_rows": len(rows) - len(mapped),
        "excluded_reason_counts": dict(excluded),
        "label_decision_candidate_counts": dict(Counter(row["label_decision_candidate"] for row in mapped)),
        "manual_review_required_rows": sum(1 for row in mapped if row["manual_review_required"]),
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "remaining_blockers": [
            "license_scope_not_selected",
            "reviewed_import_receipt_missing",
            "leakage_review_not_approved_for_training",
            "numbering_not_reviewed_by_kwb",
        ],
        "safe_for_model_claim": False,
        "policy": "Schema mapping is a candidate artifact only and must not be consumed by training.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "input_rows": report["input_rows"],
        "mapped_candidate_rows": report["mapped_candidate_rows"],
        "claim_eligible_rows_now": report["claim_eligible_rows_now"],
        "manual_review_required_rows": report["manual_review_required_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
