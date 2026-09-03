#!/usr/bin/env python3
"""Build a compact operator briefing for the highest-priority numbering review packets.

This report is navigation only. It does not write reviewed decisions and it does
not promote any weak evidence into a supervised label.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET_REPORT = AI_ROOT / "reports" / "numbering_review_packet_report.json"
OUT_JSON = AI_ROOT / "reports" / "numbering_review_briefing.json"
OUT_MD = AI_ROOT / "reports" / "numbering_review_briefing.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def bullet_list(values: list[str]) -> str:
    return ", ".join(values) if values else ""


def table_row(row: dict[str, Any], packet_id: str) -> dict[str, Any]:
    return {
        "packet_id": packet_id,
        "review_rank": row.get("review_rank"),
        "record_id": row.get("record_id"),
        "bucket": row.get("review_bucket"),
        "uniprot_id": row.get("uniprot_id"),
        "mutation": row.get("reported_mutation"),
        "current_residue": row.get("current_sequence_residue"),
        "candidate_isoforms": row.get("candidate_isoforms") or [],
        "pmid": row.get("literature_ref"),
        "title_flag": title_flag(row),
        "review_action": "confirm_source_or_keep_unresolved_weak",
        "notes": row.get("pubmed_title"),
    }


def load_packet_rows(packet_report: dict[str, Any], packet_id: str) -> list[dict[str, Any]]:
    for packet in packet_report.get("packet_reports") or []:
        if packet.get("packet_id") == packet_id:
            return load_jsonl(Path(packet["jsonl"]))
    return []


def packet_summary(packet_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "packet_id": packet_id,
        "rows": len(rows),
        "bucket_counts": dict(Counter(str(row.get("review_bucket") or "") for row in rows)),
        "title_flag_counts": dict(Counter(title_flag(row) for row in rows)),
        "review_rank_min": min((int(row.get("review_rank") or 0) for row in rows), default=None),
        "review_rank_max": max((int(row.get("review_rank") or 0) for row in rows), default=None),
    }


def markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {rank} | {record_id} | {bucket} | {uniprot_id} | {mutation} | {current_residue} | {candidate_isoforms} | {pmid} / {title_flag} | {review_action} |".format(
                rank=row.get("review_rank"),
                record_id=row.get("record_id"),
                bucket=row.get("bucket"),
                uniprot_id=row.get("uniprot_id"),
                mutation=row.get("mutation"),
                current_residue=row.get("current_residue"),
                candidate_isoforms=bullet_list(row.get("candidate_isoforms") or []),
                pmid=row.get("pmid") or "",
                title_flag=row.get("title_flag"),
                review_action=row.get("review_action"),
            )
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a compact numbering review briefing")
    parser.add_argument("--packet-report", type=Path, default=PACKET_REPORT)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=OUT_MD)
    args = parser.parse_args()

    packet_report = load_json(args.packet_report)
    packet_ids = [
        packet.get("packet_id")
        for packet in packet_report.get("packet_reports") or []
        if packet.get("rows")
    ][:2]
    packet_order = {packet_id: index for index, packet_id in enumerate(packet_ids)}
    packet_rows: dict[str, list[dict[str, Any]]] = {
        packet_id: load_packet_rows(packet_report, packet_id) for packet_id in packet_ids
    }
    packet_briefing_rows: dict[str, list[dict[str, Any]]] = {
        packet_id: [table_row(row, packet_id) for row in rows] for packet_id, rows in packet_rows.items()
    }
    summaries = [packet_summary(packet_id, rows) for packet_id, rows in packet_rows.items()]
    briefing_rows = [row for packet_id in packet_ids for row in packet_briefing_rows[packet_id]]
    briefing_rows.sort(key=lambda row: (packet_order.get(str(row["packet_id"]), 99), int(row.get("review_rank") or 0)))

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet_report": str(args.packet_report),
        "briefing_packet_ids": packet_ids,
        "packet_summaries": summaries,
        "briefing_rows": briefing_rows,
        "policy": "Navigation only; do not copy these rows into numbering_curation_decisions.jsonl without source review.",
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        "# Numbering Review Briefing",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This is a local operator briefing only. It is not a curation decision and not a supervised label source.",
        "",
        "Recommended order:",
    ]
    md_lines.extend(f"{index}. `{packet_id}`" for index, packet_id in enumerate(packet_ids, start=1))
    if not packet_ids:
        md_lines.append("No packets available.")
    md_lines.extend([
        "",
        "## Packet Summary",
        "| Packet | Rows | Rank range | Bucket counts | Title flag counts |",
        "|---|---:|---|---|---|",
    ])
    for summary in summaries:
        md_lines.append(
            "| {packet_id} | {rows} | {rank_min}..{rank_max} | {buckets} | {flags} |".format(
                packet_id=summary["packet_id"],
                rows=summary["rows"],
                rank_min=summary["review_rank_min"],
                rank_max=summary["review_rank_max"],
                buckets=json.dumps(summary["bucket_counts"], ensure_ascii=False),
                flags=json.dumps(summary["title_flag_counts"], ensure_ascii=False),
            )
        )

    md_lines.append("")
    for packet_id in packet_ids:
        md_lines.extend([
            f"## {packet_id}",
            "",
            markdown_table(packet_briefing_rows[packet_id]),
            "",
        ])

    md_lines.extend([
        "Required checks:",
        "- Confirm the original source really reports this protein and mutation.",
        "- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.",
        "- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.",
        "- Only reviewed rows should be copied into `datasets/curation/numbering_curation_decisions.jsonl`.",
    ])
    args.out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "packet_ids": packet_ids,
        "briefing_rows": len(briefing_rows),
        "output_json": str(args.out_json),
        "output_md": str(args.out_md),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
