#!/usr/bin/env python3
"""Fetch UniProt isoform FASTA evidence for numbering curation.

This script emits evidence and suggestions only. It never creates reviewed
curation decisions and never promotes weak labels.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "numbering_uniprot_evidence.jsonl"
CACHE_DIR = AI_ROOT / "datasets" / "curation" / "numbering_public_evidence" / "isoform_fastas"
OUT = AI_ROOT / "datasets" / "curation" / "numbering_isoform_evidence.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_isoform_evidence_report.json"
UNIPROT_FASTA_URL = "https://rest.uniprot.org/uniprotkb/{isoform}.fasta"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def parse_fasta(text: str) -> tuple[str, str]:
    header = ""
    chunks: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            header = line[1:].strip()
        elif line.strip():
            chunks.append(line.strip())
    return header, "".join(chunks)


def fetch_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "KWB-EnzymeDesigner-local-curation/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def cache_path(cache_dir: Path, isoform: str) -> Path:
    return cache_dir / f"{isoform.upper()}.fasta"


def load_or_fetch(isoform: str, cache_dir: Path, timeout: int, refresh: bool) -> tuple[str | None, str | None, str]:
    path = cache_path(cache_dir, isoform)
    if path.exists() and not refresh:
        header, sequence = parse_fasta(path.read_text(encoding="utf-8"))
        return header, sequence, "cached"
    try:
        text = fetch_text(UNIPROT_FASTA_URL.format(isoform=isoform), timeout)
    except urllib.error.HTTPError as exc:
        return None, None, f"failed:HTTP {exc.code}"
    except Exception as exc:
        return None, None, f"failed:{exc}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    header, sequence = parse_fasta(text)
    return header, sequence, "fetched"


def nearest_positions(sequence: str, residue: str, position: int, radius: int = 25) -> list[int]:
    if not sequence or not residue:
        return []
    residue = residue.upper()
    start = max(1, position - radius)
    end = min(len(sequence), position + radius)
    return [idx for idx in range(start, end + 1) if sequence[idx - 1].upper() == residue and idx != position]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch UniProt isoform evidence")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--limit-isoforms", type=int, default=0)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    input_rows = load_jsonl(args.input)
    isoforms = sorted({isoform for row in input_rows for isoform in (row.get("isoforms") or [])})
    if args.limit_isoforms:
        isoforms = isoforms[: args.limit_isoforms]
    isoform_set = set(isoforms)
    sequence_by_isoform: dict[str, str] = {}
    header_by_isoform: dict[str, str] = {}
    fetch_states: dict[str, str] = {}
    errors: dict[str, str] = {}

    for isoform in isoforms:
        header, sequence, state = load_or_fetch(isoform, args.cache_dir, args.timeout, args.refresh)
        fetch_states[isoform] = state
        if sequence:
            sequence_by_isoform[isoform] = sequence
            header_by_isoform[isoform] = header or ""
        elif state.startswith("failed:"):
            errors[isoform] = state.removeprefix("failed:")
        if args.sleep:
            time.sleep(args.sleep)

    output_rows = []
    for row in input_rows:
        row_isoforms = [isoform for isoform in (row.get("isoforms") or []) if isoform in isoform_set]
        if not row_isoforms:
            continue
        reported_position = int(row.get("reported_position") or 0)
        reported_wt = str(row.get("reported_wild_type") or "").upper()
        candidates = []
        for isoform in row_isoforms:
            sequence = sequence_by_isoform.get(isoform, "")
            residue = None
            if sequence and 1 <= reported_position <= len(sequence):
                residue = sequence[reported_position - 1].upper()
            candidates.append({
                "isoform": isoform,
                "sequence_length": len(sequence) if sequence else None,
                "fetch_state": fetch_states.get(isoform),
                "residue_at_reported_position": residue,
                "reported_wt_matches_isoform": residue == reported_wt,
                "nearest_same_wt_positions_pm25": nearest_positions(sequence, reported_wt, reported_position),
                "fasta_header": header_by_isoform.get(isoform),
            })
        exact = [item["isoform"] for item in candidates if item.get("reported_wt_matches_isoform")]
        output_rows.append({
            "record_id": row.get("record_id"),
            "packet_id": row.get("packet_id"),
            "priority": row.get("priority"),
            "uniprot_id": row.get("uniprot_id"),
            "reported_mutation": row.get("reported_mutation"),
            "reported_position": reported_position,
            "reported_wild_type": reported_wt,
            "reported_mutant": row.get("reported_mutant"),
            "literature_ref": row.get("literature_ref"),
            "isoform_candidates": candidates,
            "exact_isoform_position_matches": exact,
            "has_exact_isoform_position_match": bool(exact),
            "policy": "isoform evidence only; requires reviewed curation decision before label promotion",
        })

    write_jsonl(args.output, output_rows)
    exact_rows = sum(1 for row in output_rows if row.get("has_exact_isoform_position_match"))
    report = {
        "input_rows": len(input_rows),
        "rows_with_isoforms_in_scope": len(output_rows),
        "unique_isoforms_requested": len(isoforms),
        "unique_isoforms_fetched_or_cached": len(sequence_by_isoform),
        "fetch_state_counts": dict(Counter(fetch_states.values())),
        "errors": errors,
        "rows_with_exact_isoform_position_match": exact_rows,
        "rows_without_exact_isoform_position_match": len(output_rows) - exact_rows,
        "priority_exact_match_counts": dict(Counter(row.get("priority") for row in output_rows if row.get("has_exact_isoform_position_match"))),
        "output": str(args.output),
        "cache_dir": str(args.cache_dir),
        "policy": "evidence only; not reviewed decisions",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows_with_isoforms_in_scope": report["rows_with_isoforms_in_scope"],
        "unique_isoforms_fetched_or_cached": report["unique_isoforms_fetched_or_cached"],
        "rows_with_exact_isoform_position_match": exact_rows,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
