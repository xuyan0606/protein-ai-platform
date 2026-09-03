#!/usr/bin/env python3
"""Build a prioritized numbering review worklist from public evidence.

The worklist is an operator queue only. It must not be consumed as reviewed
numbering decisions or supervised labels.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "curation" / "numbering_curation_queue.jsonl"
UNIPROT = AI_ROOT / "datasets" / "curation" / "numbering_uniprot_evidence.jsonl"
ISOFORMS = AI_ROOT / "datasets" / "curation" / "numbering_isoform_review_candidates.jsonl"
ABSTRACTS = AI_ROOT / "datasets" / "curation" / "numbering_pubmed_abstract_evidence.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "numbering_review_worklist.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_review_worklist_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def by_record(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("record_id")): row for row in rows if row.get("record_id")}


def priority_base(priority: str | None) -> int:
    return {"P0": 300, "P1": 200, "P2": 100}.get(priority or "", 0)


def review_bucket(row: dict[str, Any]) -> str:
    if row["has_isoform_exact_candidate"] and row["has_abstract_signal"]:
        return "isoform_exact_plus_abstract_signal"
    if row["has_isoform_exact_candidate"]:
        return "isoform_exact_candidate"
    if row["reported_mutation_mentioned_in_title_or_abstract"]:
        return "direct_mutation_mention"
    if row["has_abstract_signal"]:
        return "abstract_signal"
    if row["literature_ref_in_uniprot_references"]:
        return "uniprot_reference_link"
    if not row["pubmed_found"]:
        return "pubmed_missing_or_invalid"
    return "low_signal_high_risk"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build numbering review worklist")
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--uniprot", type=Path, default=UNIPROT)
    parser.add_argument("--isoforms", type=Path, default=ISOFORMS)
    parser.add_argument("--abstracts", type=Path, default=ABSTRACTS)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    queue_rows = load_jsonl(args.queue)
    uniprot_by_id = by_record(load_jsonl(args.uniprot))
    isoform_by_id = by_record(load_jsonl(args.isoforms))
    abstract_by_id = by_record(load_jsonl(args.abstracts))

    worklist = []
    for queue_row in queue_rows:
        record_id = str(queue_row.get("record_id") or "")
        uniprot = uniprot_by_id.get(record_id, {})
        isoform = isoform_by_id.get(record_id, {})
        abstract = abstract_by_id.get(record_id, {})
        has_isoform = bool(isoform)
        has_abstract_signal = bool(abstract.get("abstract_has_protein_or_mutation_signal"))
        mutation_mention = bool(abstract.get("reported_mutation_mentioned_in_title_or_abstract"))
        literature_ref_linked = bool(uniprot.get("literature_ref_in_uniprot_references"))

        score = priority_base(queue_row.get("priority"))
        score += 120 if has_isoform else 0
        score += 80 if mutation_mention else 0
        score += 40 if has_abstract_signal else 0
        score += 30 if literature_ref_linked else 0
        score += 10 if queue_row.get("measurement_strength") == "strong" else 0
        score -= 40 if abstract and not abstract.get("pubmed_found") else 0

        row = {
            "record_id": record_id,
            "priority": queue_row.get("priority"),
            "review_score": score,
            "review_bucket": "",
            "uniprot_id": queue_row.get("uniprot_id"),
            "reported_mutation": queue_row.get("mutation") or uniprot.get("reported_mutation"),
            "reported_position": queue_row.get("reported_position"),
            "reported_wild_type": queue_row.get("reported_wild_type"),
            "reported_mutant": uniprot.get("reported_mutant"),
            "current_sequence_residue": queue_row.get("current_sequence_residue"),
            "nearest_matches_within_window": queue_row.get("nearest_matches_within_window"),
            "source_db": queue_row.get("source_db"),
            "method": queue_row.get("method"),
            "measurement_strength": queue_row.get("measurement_strength"),
            "label_decision": queue_row.get("label_decision"),
            "literature_ref": queue_row.get("literature_ref"),
            "pubmed_found": bool(abstract.get("pubmed_found")),
            "pubmed_title": abstract.get("title"),
            "has_abstract": bool(abstract.get("has_abstract")),
            "abstract_keyword_hits": abstract.get("abstract_keyword_hits") or [],
            "has_abstract_signal": has_abstract_signal,
            "reported_mutation_mentioned_in_title_or_abstract": mutation_mention,
            "literature_ref_in_uniprot_references": literature_ref_linked,
            "reported_wt_matches_current_uniprot": bool(uniprot.get("reported_wt_matches_current_uniprot")),
            "canonical_residue_at_reported_position": uniprot.get("residue_at_reported_position"),
            "canonical_nearest_same_wt_positions_pm25": uniprot.get("nearest_same_wt_positions_pm25") or [],
            "has_isoform_exact_candidate": has_isoform,
            "candidate_isoforms": isoform.get("candidate_isoforms") or [],
            "candidate_mapping_basis": isoform.get("candidate_mapping_basis"),
            "required_review_checks": [
                "confirm original source really reports this protein and mutation",
                "confirm numbering system and isoform/canonical sequence version",
                "confirm wild-type residue and mutant residue against source evidence",
                "only then write a reviewed row to numbering_curation_decisions.jsonl",
            ],
            "policy": "operator worklist only; not_a_curation_decision; not_a_supervised_label",
        }
        row["review_bucket"] = review_bucket(row)
        worklist.append(row)

    worklist.sort(key=lambda row: (-int(row["review_score"]), row.get("priority") or "P9", row.get("record_id") or ""))
    for index, row in enumerate(worklist, start=1):
        row["review_rank"] = index

    write_jsonl(args.output, worklist)
    bucket_counts = Counter(row["review_bucket"] for row in worklist)
    priority_counts = Counter(row.get("priority") for row in worklist)
    report = {
        "input_queue_rows": len(queue_rows),
        "worklist_rows": len(worklist),
        "priority_counts": dict(priority_counts),
        "bucket_counts": dict(bucket_counts),
        "top_review_bucket": worklist[0]["review_bucket"] if worklist else None,
        "top_review_score": worklist[0]["review_score"] if worklist else None,
        "isoform_exact_candidate_rows": sum(1 for row in worklist if row["has_isoform_exact_candidate"]),
        "abstract_signal_rows": sum(1 for row in worklist if row["has_abstract_signal"]),
        "direct_mutation_mention_rows": sum(1 for row in worklist if row["reported_mutation_mentioned_in_title_or_abstract"]),
        "pubmed_missing_or_invalid_rows": sum(1 for row in worklist if not row["pubmed_found"]),
        "output": str(args.output),
        "policy": "worklist is not applied automatically and must not promote labels",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "worklist_rows": report["worklist_rows"],
        "bucket_counts": report["bucket_counts"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
