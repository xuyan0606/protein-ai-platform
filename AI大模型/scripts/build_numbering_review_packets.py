#!/usr/bin/env python3
"""Build human review packets from the numbering review worklist.

Packets are review aids only. Decision drafts default to unresolved weak and
are written outside the applied decision file.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "numbering_review_worklist.jsonl"
OUT_DIR = AI_ROOT / "datasets" / "curation" / "numbering_review_packets"
DRAFT_DIR = AI_ROOT / "datasets" / "curation" / "numbering_review_decision_drafts"
REPORT_OUT = AI_ROOT / "reports" / "numbering_review_packet_report.json"


PACKET_GROUPS = [
    {
        "prefix": "numbering_review_enzyme_fireprot_manual",
        "bucket_filter": {"enzyme_ec_confirmed_fireprot_manual_review"},
        "goal": "Review EC-confirmed FireProt enzyme rows that still require manual attention.",
    },
    {
        "prefix": "numbering_review_enzyme_fireprot",
        "bucket_filter": {"enzyme_ec_confirmed_fireprot"},
        "goal": "Review EC-confirmed FireProt enzyme rows before KWB import approval.",
    },
    {
        "prefix": "numbering_review_isoform_exact",
        "bucket_filter": {"isoform_exact_plus_abstract_signal", "isoform_exact_candidate"},
        "goal": "Review all isoform exact candidates before any label promotion.",
    },
    {
        "prefix": "numbering_review_abstract_signal",
        "bucket_filter": {"abstract_signal"},
        "goal": "Review abstract-signal rows after isoform candidates.",
    },
    {
        "prefix": "numbering_review_pubmed_missing",
        "bucket_filter": {"pubmed_missing_or_invalid"},
        "goal": "Review missing or invalid PubMed references before any label promotion.",
    },
    {
        "prefix": "numbering_review_low_signal_high_risk",
        "bucket_filter": {"low_signal_high_risk"},
        "goal": "Review low-signal high-risk rows only after higher-yield packets.",
    },
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def mutation_tail(mutation: str | None) -> str | None:
    if not mutation:
        return None
    return str(mutation)[-1:] or None


def draft_for(row: dict[str, Any], packet_id: str) -> dict[str, Any]:
    refs = [row["literature_ref"]] if row.get("literature_ref") else []
    refs.append(f"UniProt:{row.get('uniprot_id')}")
    for isoform in row.get("candidate_isoforms") or []:
        refs.append(f"UniProtIsoform:{isoform}")
    return {
        "record_id": row.get("record_id"),
        "decision": "keep_unresolved_weak",
        "canonical_uniprot_id": row.get("uniprot_id"),
        "canonical_position": None,
        "canonical_wild_type": None,
        "canonical_mutant": mutation_tail(row.get("reported_mutation")),
        "mapping_basis": "unresolved",
        "source_refs": refs,
        "confidence": 0.0,
        "notes": (
            f"Draft from {packet_id}. Keep unresolved until original source confirms "
            "protein, mutation, isoform/canonical numbering, and assay provenance."
        ),
        "curator": "local-curator",
        "curated_at": "2026-07-25T00:00:00+08:00",
        "draft_policy": "draft_only; copy reviewed rows manually into numbering_curation_decisions.jsonl only after source review",
    }


def title_flag(row: dict[str, Any]) -> str:
    title = (row.get("pubmed_title") or "").lower()
    mutation = (row.get("reported_mutation") or "").lower()
    protein_words = {"protein", "enzyme", "mutation", "mutant", "residue", "amino acid", "stability"}
    if mutation and mutation in title.replace(" ", ""):
        return "title_mentions_mutation"
    if any(word in title for word in protein_words):
        return "title_has_broad_protein_signal"
    if row.get("pubmed_found"):
        return "title_mismatch_risk"
    return "pubmed_missing_or_invalid"


def write_markdown(path: Path, packet_id: str, goal: str, rows: list[dict[str, Any]], draft_path: Path) -> None:
    lines = [
        f"# {packet_id}",
        "",
        goal,
        "",
        "Policy: this packet is not a curation decision and must not be used as a supervised label source.",
        "",
        f"Decision draft template: `{draft_path}`",
        "",
        "| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        isoforms = ", ".join(row.get("candidate_isoforms") or [])
        lines.append(
            "| {rank} | {record_id} | {bucket} | {uniprot} | {mutation} | {current} | {isoforms} | {pmid} / {flag} | {action} |".format(
                rank=row.get("review_rank"),
                record_id=row.get("record_id"),
                bucket=row.get("review_bucket"),
                uniprot=row.get("uniprot_id"),
                mutation=row.get("reported_mutation"),
                current=row.get("current_sequence_residue"),
                isoforms=isoforms or "",
                pmid=row.get("literature_ref") or "",
                flag=title_flag(row),
                action="confirm_source_or_keep_unresolved_weak",
            )
        )
    lines.extend([
        "",
        "Required checks:",
        "- Confirm the original source really reports this protein and mutation.",
        "- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.",
        "- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.",
        "- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def clear_generated_outputs(out_dir: Path, draft_dir: Path) -> None:
    for directory, patterns in (
        (out_dir, ("numbering_review_*.jsonl", "numbering_review_*.md")),
        (draft_dir, ("numbering_review_*.decisions.draft.jsonl",)),
    ):
        if not directory.exists():
            continue
        for pattern in patterns:
            for path in directory.glob(pattern):
                path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build numbering review packets")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--draft-dir", type=Path, default=DRAFT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    reports = []
    clear_generated_outputs(args.out_dir, args.draft_dir)
    for spec in PACKET_GROUPS:
        group_rows = [
            row for row in rows
            if row.get("review_bucket") in spec["bucket_filter"]
        ]
        for index, packet_rows in enumerate(chunks(group_rows, args.batch_size), start=1):
            packet_id = f"{spec['prefix']}_{index:03d}"
            packet_jsonl = args.out_dir / f"{packet_id}.jsonl"
            packet_md = args.out_dir / f"{packet_id}.md"
            draft_jsonl = args.draft_dir / f"{packet_id}.decisions.draft.jsonl"
            write_jsonl(packet_jsonl, packet_rows)
            write_jsonl(draft_jsonl, [draft_for(row, packet_id) for row in packet_rows])
            write_markdown(packet_md, packet_id, spec["goal"], packet_rows, draft_jsonl)
            reports.append({
                "packet_id": packet_id,
                "rows": len(packet_rows),
                "bucket_counts": dict(Counter(row.get("review_bucket") for row in packet_rows)),
                "jsonl": str(packet_jsonl),
                "markdown": str(packet_md),
                "decision_draft": str(draft_jsonl),
            })

    report = {
        "input_rows": len(rows),
        "packets": len(reports),
        "packet_rows": sum(item["rows"] for item in reports),
        "packet_reports": reports,
        "draft_rows": sum(item["rows"] for item in reports),
        "policy": "packets and drafts are not applied automatically; reviewed decisions remain 0 until manually curated",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "packets": report["packets"],
        "packet_rows": report["packet_rows"],
        "draft_rows": report["draft_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
