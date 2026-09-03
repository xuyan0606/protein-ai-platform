#!/usr/bin/env python3
"""Build review packets for InterPro domain rows not auto-converted."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = AI_ROOT / "datasets" / "curation" / "domain_interpro_evidence.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "domain_interval_decisions.jsonl"
MULTI_OCCURRENCE = AI_ROOT / "datasets" / "curation" / "domain_multi_occurrence_features.jsonl"
OUT_DIR = AI_ROOT / "datasets" / "curation" / "domain_interpro_review_packets"
DRAFT_DIR = AI_ROOT / "datasets" / "curation" / "domain_interpro_decision_drafts"
REPORT_OUT = AI_ROOT / "reports" / "domain_interpro_review_packet_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def clean_generated_files(out_dir: Path, draft_dir: Path) -> None:
    for directory, patterns in (
        (out_dir, ("domain_interpro_unresolved_*.jsonl", "domain_interpro_unresolved_*.md")),
        (draft_dir, ("domain_interpro_unresolved_*.decisions.draft.jsonl",)),
    ):
        if not directory.exists():
            continue
        for pattern in patterns:
            for path in directory.glob(pattern):
                path.unlink()


def bucket(row: dict[str, Any], decided_ids: set[int], multi_occurrence_ids: set[int]) -> str:
    record_id = row.get("domain_record_id")
    if record_id in decided_ids:
        return "already_program_reviewed"
    if record_id in multi_occurrence_ids:
        return "multi_interval_sidecar_resolved_for_feature_use"
    intervals = row.get("matched_pfam_intervals") or []
    if len(intervals) > 1:
        return "multi_interval_needs_occurrence_selection"
    if not intervals:
        return "no_exact_pfam_interval"
    return "other_unresolved"


def interval_summary(row: dict[str, Any]) -> str:
    parts = []
    for interval in row.get("matched_pfam_intervals") or []:
        parts.append(
            "{start}-{end} score={score} status={status}".format(
                start=interval.get("start"),
                end=interval.get("end"),
                score=interval.get("score"),
                status=interval.get("dc_status"),
            )
        )
    return "; ".join(parts[:8])


def draft_for(row: dict[str, Any], packet_id: str) -> dict[str, Any]:
    return {
        "domain_record_id": row.get("domain_record_id"),
        "decision": "keep_unresolved",
        "start_pos": None,
        "end_pos": None,
        "basis": "unresolved",
        "confidence": 0.0,
        "notes": (
            f"Draft from {packet_id}. Multiple or missing InterPro intervals require "
            "manual selection/rejection before set_interval."
        ),
        "curator": "local-curator",
        "curated_at": "2026-07-25T00:00:00+08:00",
        "draft_policy": "draft_only; not applied automatically",
    }


def write_markdown(path: Path, packet_id: str, rows: list[dict[str, Any]], draft_path: Path) -> None:
    lines = [
        f"# {packet_id}",
        "",
        "Review domain rows that could not be safely converted from InterPro/Pfam evidence.",
        "",
        "Policy: this packet is not applied automatically. Multi-interval rows require occurrence selection.",
        "",
        f"Decision draft template: `{draft_path}`",
        "",
        "| domain_record_id | bucket | UniProt | Pfam | seq len | intervals | action |",
        "|---:|---|---|---|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {id} | {bucket} | {uniprot} | {pfam} | {seq_len} | {intervals} | {action} |".format(
                id=row.get("domain_record_id"),
                bucket=row.get("review_bucket"),
                uniprot=row.get("uniprot_id"),
                pfam=row.get("pfam_id"),
                seq_len=row.get("sequence_length"),
                intervals=interval_summary(row).replace("|", "/"),
                action="select_one_interval_or_keep_unresolved",
            )
        )
    lines.extend([
        "",
        "Required checks:",
        "- For repeated domains, confirm which occurrence belongs to the intended local domain record.",
        "- If no exact Pfam interval exists in InterPro, keep unresolved or reject the hit.",
        "- Write reviewed rows to `domain_interval_decisions.jsonl` only after occurrence selection.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build InterPro domain review packets")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--multi-occurrence", type=Path, default=MULTI_OCCURRENCE)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--draft-dir", type=Path, default=DRAFT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--batch-size", type=int, default=75)
    args = parser.parse_args()

    evidence = load_jsonl(args.evidence)
    decisions = load_jsonl(args.decisions)
    multi_occurrence = load_jsonl(args.multi_occurrence)
    decided_ids = {int(row["domain_record_id"]) for row in decisions if row.get("domain_record_id") is not None}
    multi_occurrence_ids = {
        int(row["domain_record_id"])
        for row in multi_occurrence
        if row.get("domain_record_id") is not None and row.get("safe_for_position_features") is True
    }

    raw_unresolved = []
    feature_use_unresolved = []
    sidecar_resolved = []
    for row in evidence:
        review_bucket = bucket(row, decided_ids, multi_occurrence_ids)
        if review_bucket == "already_program_reviewed":
            continue
        enriched = {**row, "review_bucket": review_bucket}
        raw_unresolved.append(enriched)
        if review_bucket == "multi_interval_sidecar_resolved_for_feature_use":
            sidecar_resolved.append(enriched)
        else:
            feature_use_unresolved.append(enriched)
    feature_use_unresolved.sort(key=lambda row: (row.get("review_bucket") or "", row.get("uniprot_id") or "", row.get("domain_record_id") or 0))
    raw_unresolved.sort(key=lambda row: (row.get("review_bucket") or "", row.get("uniprot_id") or "", row.get("domain_record_id") or 0))

    clean_generated_files(args.out_dir, args.draft_dir)

    packet_reports = []
    for index, packet_rows in enumerate(chunks(feature_use_unresolved, args.batch_size), start=1):
        packet_id = f"domain_interpro_unresolved_{index:03d}"
        packet_jsonl = args.out_dir / f"{packet_id}.jsonl"
        packet_md = args.out_dir / f"{packet_id}.md"
        draft_jsonl = args.draft_dir / f"{packet_id}.decisions.draft.jsonl"
        write_jsonl(packet_jsonl, packet_rows)
        write_jsonl(draft_jsonl, [draft_for(row, packet_id) for row in packet_rows])
        write_markdown(packet_md, packet_id, packet_rows, draft_jsonl)
        packet_reports.append({
            "packet_id": packet_id,
            "rows": len(packet_rows),
            "bucket_counts": dict(Counter(row["review_bucket"] for row in packet_rows)),
            "jsonl": str(packet_jsonl),
            "markdown": str(packet_md),
            "decision_draft": str(draft_jsonl),
        })

    report = {
        "evidence_rows": len(evidence),
        "decided_rows": len(decided_ids),
        "raw_unresolved_rows": len(raw_unresolved),
        "raw_unresolved_bucket_counts": dict(Counter(row["review_bucket"] for row in raw_unresolved)),
        "multi_occurrence_sidecar_rows": len(multi_occurrence_ids),
        "multi_occurrence_sidecar_resolved_rows": len(sidecar_resolved),
        "unresolved_rows": len(feature_use_unresolved),
        "unresolved_bucket_counts": dict(Counter(row["review_bucket"] for row in feature_use_unresolved)),
        "packets": len(packet_reports),
        "packet_rows": sum(row["rows"] for row in packet_reports),
        "packet_reports": packet_reports,
        "policy": (
            "Review packets are generated only for rows still unresolved for position feature use. "
            "Valid repeated Pfam rows may be resolved by domain_multi_occurrence_features sidecar, "
            "which preserves all occurrences without creating single-interval decisions."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "unresolved_rows": report["unresolved_rows"],
        "packets": report["packets"],
        "packet_rows": report["packet_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
