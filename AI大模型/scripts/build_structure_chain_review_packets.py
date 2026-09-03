#!/usr/bin/env python3
"""Build human review packets for structure chain mapping candidates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_worklist.jsonl"
OUT_DIR = AI_ROOT / "datasets" / "curation" / "structure_chain_review_packets"
DRAFT_DIR = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_decision_drafts"
REPORT_OUT = AI_ROOT / "reports" / "structure_chain_review_packet_report.json"


PACKET_GROUPS = [
    {
        "prefix": "structure_chain_single_close",
        "bucket_filter": {"single_chain_ca_length_close"},
        "goal": "Review the easiest single-chain candidates first.",
    },
    {
        "prefix": "structure_chain_multi_select",
        "bucket_filter": {"multi_chain_needs_selection"},
        "goal": "Review multi-chain structures requiring biological chain selection.",
    },
    {
        "prefix": "structure_chain_single_mismatch",
        "bucket_filter": {"single_chain_ca_length_mismatch"},
        "goal": "Review single-chain structures with sequence-length mismatch.",
    },
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def draft_for(row: dict[str, Any], packet_id: str) -> dict[str, Any]:
    return {
        "structure_id": row.get("structure_id"),
        "decision": "keep_unreviewed",
        "canonical_uniprot_id": row.get("uniprot_id"),
        "selected_chain_id": None,
        "sequence_to_structure_mapping_status": "unreviewed",
        "residue_numbering_basis": "unreviewed",
        "missing_residue_ranges": [],
        "insertion_code_policy": "unreviewed",
        "source_refs": [
            f"PDB:{row.get('structure_id')}",
            f"UniProt:{row.get('uniprot_id')}",
        ],
        "confidence": 0.0,
        "notes": (
            f"Draft from {packet_id}. Keep unreviewed until biological chain, "
            "residue numbering, construct tags, and missing residues are confirmed."
        ),
        "curator": "local-curator",
        "curated_at": "2026-07-25T00:00:00+08:00",
        "draft_policy": "draft_only; not_a_reviewed_chain_mapping; cannot_unlock_structure_conclusions",
    }


def chain_summary(row: dict[str, Any]) -> str:
    counts = row.get("residue_count_by_chain") or {}
    if not counts:
        return ""
    return ", ".join(f"{chain}:{count}" for chain, count in sorted(counts.items())[:8])


def write_markdown(path: Path, packet_id: str, goal: str, rows: list[dict[str, Any]], draft_path: Path) -> None:
    lines = [
        f"# {packet_id}",
        "",
        goal,
        "",
        "Policy: this packet is not a reviewed chain mapping and cannot unlock structure-dependent conclusions.",
        "",
        f"Decision draft template: `{draft_path}`",
        "",
        "| rank | PDB | bucket | UniProt | protein | method/resolution | chains | seq len | CA atoms | delta | action |",
        "|---:|---|---|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        method = row.get("method") or ""
        resolution = row.get("resolution")
        method_resolution = f"{method} / {resolution}" if resolution is not None else method
        lines.append(
            "| {rank} | {pdb} | {bucket} | {uniprot} | {protein} | {method_resolution} | {chains} | {seq_len} | {ca} | {delta} | {action} |".format(
                rank=row.get("review_rank"),
                pdb=row.get("structure_id"),
                bucket=row.get("review_bucket"),
                uniprot=row.get("uniprot_id"),
                protein=(row.get("protein_name") or "").replace("|", "/"),
                method_resolution=method_resolution.replace("|", "/"),
                chains=chain_summary(row),
                seq_len=row.get("seq_length"),
                ca=row.get("ca_atoms"),
                delta=row.get("length_delta_ca_minus_sequence"),
                action="confirm_chain_and_numbering_or_keep_unreviewed",
            )
        )
    lines.extend([
        "",
        "Required checks:",
        "- Confirm the biological chain for the UniProt accession.",
        "- Confirm residue numbering, insertion codes, missing residues, engineered tags, and construct truncations.",
        "- Confirm ligands/cofactors only after chain mapping is reviewed.",
        "- Structure distance, pocket, exposure, and catalytic-network features stay blocked until reviewed mapping exists.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure chain review packets")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--draft-dir", type=Path, default=DRAFT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    reports = []
    for spec in PACKET_GROUPS:
        group_rows = [
            row for row in rows
            if row.get("review_bucket") in spec["bucket_filter"]
        ]
        for index, packet_rows in enumerate(chunks(group_rows, args.batch_size), start=1):
            packet_id = f"{spec['prefix']}_{index:03d}"
            packet_jsonl = args.out_dir / f"{packet_id}.jsonl"
            packet_md = args.out_dir / f"{packet_id}.md"
            draft_jsonl = args.draft_dir / f"{packet_id}.chain_mapping.draft.jsonl"
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
        "policy": "packets and drafts are not applied automatically; reviewed chain mapping remains unavailable",
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
