#!/usr/bin/env python3
"""Fetch public UniProt evidence for mutation-numbering curation.

This creates evidence records only. It never writes curation decisions and never
promotes weak labels into supervised training labels.
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
PACKET_DIR = AI_ROOT / "datasets" / "curation" / "numbering_retrieval_packets"
CACHE_DIR = AI_ROOT / "datasets" / "curation" / "numbering_public_evidence" / "uniprot_entries"
EVIDENCE_OUT = AI_ROOT / "datasets" / "curation" / "numbering_uniprot_evidence.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_uniprot_evidence_report.json"
UNIPROT_ENTRY_URL = "https://rest.uniprot.org/uniprotkb/{accession}.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def read_packets(packet_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(packet_dir.glob("*.jsonl")):
        rows.extend(load_jsonl(path))
    return rows


def fetch_json(url: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "KWB-EnzymeDesigner-local-curation/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("UniProt response was not a JSON object")
    return payload


def cache_path(cache_dir: Path, accession: str) -> Path:
    return cache_dir / f"{accession.upper()}.json"


def load_or_fetch(accession: str, cache_dir: Path, timeout: int, refresh: bool) -> tuple[dict[str, Any] | None, str]:
    path = cache_path(cache_dir, accession)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8")), "cached"
    try:
        payload = fetch_json(UNIPROT_ENTRY_URL.format(accession=accession), timeout)
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}", "accession": accession}, "failed"
    except Exception as exc:
        return {"error": str(exc), "accession": accession}, "failed"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload, "fetched"


def extract_isoforms(entry: dict[str, Any]) -> list[str]:
    isoforms: list[str] = []
    for comment in entry.get("comments") or []:
        if comment.get("commentType") != "ALTERNATIVE PRODUCTS":
            continue
        for isoform in comment.get("isoforms") or []:
            for iso_id in isoform.get("isoformIds") or []:
                isoforms.append(str(iso_id))
    return sorted(set(isoforms))


def extract_pubmed_ids(entry: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for ref in entry.get("references") or []:
        citation = ref.get("citation") or {}
        for citation_id in citation.get("citationCrossReferences") or []:
            if citation_id.get("database") == "PubMed" and citation_id.get("id"):
                ids.append(f"PMID:{citation_id.get('id')}")
    return sorted(set(ids))


def summarize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    sequence = (entry.get("sequence") or {}).get("value") or ""
    return {
        "primary_accession": entry.get("primaryAccession"),
        "uni_prot_kb_id": entry.get("uniProtkbId"),
        "entry_type": entry.get("entryType"),
        "entry_version": entry.get("entryAudit", {}).get("entryVersion"),
        "sequence_version": entry.get("entryAudit", {}).get("sequenceVersion"),
        "sequence_length": len(sequence),
        "sequence": sequence,
        "isoforms": extract_isoforms(entry),
        "reference_pubmed_ids": extract_pubmed_ids(entry),
    }


def nearest_positions(sequence: str, residue: str, position: int, radius: int = 25) -> list[int]:
    if not residue or not sequence:
        return []
    residue = residue.upper()
    start = max(1, position - radius)
    end = min(len(sequence), position + radius)
    return [idx for idx in range(start, end + 1) if sequence[idx - 1].upper() == residue and idx != position]


def build_evidence(row: dict[str, Any], summary: dict[str, Any] | None, fetch_state: str) -> dict[str, Any]:
    accession = str(row.get("uniprot_id") or "")
    reported_position = int(row.get("reported_position") or 0)
    reported_wt = str(row.get("reported_wild_type") or "").upper()
    sequence = (summary or {}).get("sequence") or ""
    residue_at_reported_position = None
    if sequence and 1 <= reported_position <= len(sequence):
        residue_at_reported_position = sequence[reported_position - 1].upper()
    literature_ref = row.get("literature_ref")
    reference_pubmed_ids = set((summary or {}).get("reference_pubmed_ids") or [])
    return {
        "record_id": row.get("record_id"),
        "packet_id": row.get("packet_id"),
        "priority": row.get("priority"),
        "uniprot_id": accession,
        "reported_mutation": row.get("reported_mutation"),
        "reported_position": reported_position,
        "reported_wild_type": reported_wt,
        "reported_mutant": str(row.get("reported_mutation") or "")[-1:].upper(),
        "literature_ref": literature_ref,
        "fetch_state": fetch_state,
        "primary_accession": (summary or {}).get("primary_accession"),
        "entry_version": (summary or {}).get("entry_version"),
        "sequence_version": (summary or {}).get("sequence_version"),
        "sequence_length": (summary or {}).get("sequence_length"),
        "isoform_count": len((summary or {}).get("isoforms") or []),
        "isoforms": (summary or {}).get("isoforms") or [],
        "residue_at_reported_position": residue_at_reported_position,
        "reported_wt_matches_current_uniprot": residue_at_reported_position == reported_wt,
        "nearest_same_wt_positions_pm25": nearest_positions(sequence, reported_wt, reported_position),
        "literature_ref_in_uniprot_references": literature_ref in reference_pubmed_ids if literature_ref else False,
        "source_refs": [
            f"UniProt:{accession}",
            str(literature_ref) if literature_ref else "",
        ],
        "policy": "evidence only; not a reviewed numbering curation decision",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch UniProt evidence for numbering curation")
    parser.add_argument("--packet-dir", type=Path, default=PACKET_DIR)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--evidence-output", type=Path, default=EVIDENCE_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--limit-accessions", type=int, default=0)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    packets = read_packets(args.packet_dir)
    accessions = sorted({str(row.get("uniprot_id")) for row in packets if row.get("uniprot_id")})
    if args.limit_accessions:
        accessions = accessions[: args.limit_accessions]
    summaries: dict[str, dict[str, Any]] = {}
    fetch_states: dict[str, str] = {}
    errors: dict[str, str] = {}
    for accession in accessions:
        payload, state = load_or_fetch(accession, args.cache_dir, args.timeout, args.refresh)
        fetch_states[accession] = state
        if payload and payload.get("error"):
            errors[accession] = str(payload.get("error"))
        elif payload:
            summaries[accession] = summarize_entry(payload)
        if args.sleep:
            time.sleep(args.sleep)

    evidence_rows = [
        build_evidence(row, summaries.get(str(row.get("uniprot_id"))), fetch_states.get(str(row.get("uniprot_id")), "not_requested"))
        for row in packets
        if str(row.get("uniprot_id")) in set(accessions)
    ]
    write_jsonl(args.evidence_output, evidence_rows)
    exact_matches = sum(1 for row in evidence_rows if row.get("reported_wt_matches_current_uniprot"))
    isoform_rows = sum(1 for row in evidence_rows if row.get("isoform_count", 0) > 0)
    report = {
        "packet_rows_total": len(packets),
        "evidence_rows": len(evidence_rows),
        "unique_accessions_requested": len(accessions),
        "unique_accessions_fetched_or_cached": len(summaries),
        "fetch_state_counts": dict(Counter(fetch_states.values())),
        "errors": errors,
        "reported_wt_matches_current_uniprot": exact_matches,
        "reported_wt_mismatch_current_uniprot": len(evidence_rows) - exact_matches,
        "rows_with_isoform_options": isoform_rows,
        "evidence_output": str(args.evidence_output),
        "cache_dir": str(args.cache_dir),
        "policy": "public UniProt evidence only; decisions still require reviewed curation",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "evidence_rows": report["evidence_rows"],
        "unique_accessions_fetched_or_cached": report["unique_accessions_fetched_or_cached"],
        "reported_wt_matches_current_uniprot": exact_matches,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
