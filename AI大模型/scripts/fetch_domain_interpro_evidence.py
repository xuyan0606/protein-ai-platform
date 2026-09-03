#!/usr/bin/env python3
"""Fetch InterPro/Pfam domain interval evidence for invalid local domain rows.

This script stores public InterPro evidence only. It does not write reviewed
domain interval decisions and does not modify the source database.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "domain_interval_repair_queue.jsonl"
CACHE_DIR = AI_ROOT / "datasets" / "curation" / "domain_public_evidence" / "interpro_pfam"
OUT = AI_ROOT / "datasets" / "curation" / "domain_interpro_evidence.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "domain_interpro_evidence_report.json"
INTERPRO_BASE = "https://www.ebi.ac.uk/interpro/api/entry/pfam/protein/UniProt"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def cache_path(cache_dir: Path, accession: str) -> Path:
    return cache_dir / f"{accession.upper()}.json"


def fetch_json(url: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "KWB-EnzymeDesigner-local-curation/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_interpro(accession: str, timeout: int, page_size: int) -> dict[str, Any]:
    encoded = urllib.parse.quote(accession.upper())
    url = f"{INTERPRO_BASE}/{encoded}?page_size={page_size}"
    results: list[dict[str, Any]] = []
    while url:
        data = fetch_json(url, timeout)
        results.extend(data.get("results") or [])
        url = data.get("next")
    return {"accession": accession.upper(), "results": results}


def load_or_fetch(accession: str, cache_dir: Path, timeout: int, page_size: int, refresh: bool) -> tuple[dict[str, Any], str]:
    path = cache_path(cache_dir, accession)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8")), "cached"
    data = fetch_interpro(accession, timeout, page_size)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data, "fetched"


def intervals_for_entry(entry: dict[str, Any], accession: str) -> list[dict[str, Any]]:
    intervals = []
    metadata = entry.get("metadata") or {}
    pfam_id = metadata.get("accession")
    for protein in entry.get("proteins") or []:
        if str(protein.get("accession") or "").upper() != accession.upper():
            continue
        for location in protein.get("entry_protein_locations") or []:
            score = location.get("score")
            model = location.get("model")
            representative = bool(location.get("representative"))
            for fragment in location.get("fragments") or []:
                start = fragment.get("start")
                end = fragment.get("end")
                if isinstance(start, int) and isinstance(end, int) and start > 0 and end >= start:
                    intervals.append({
                        "pfam_id": pfam_id,
                        "start": start,
                        "end": end,
                        "dc_status": fragment.get("dc-status"),
                        "model": model,
                        "score": score,
                        "representative": representative,
                        "source_database": protein.get("source_database"),
                        "protein_length": protein.get("protein_length"),
                    })
    return intervals


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch InterPro/Pfam domain interval evidence")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--limit-accessions", type=int, default=0, help="0 means all accessions in input")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--sleep", type=float, default=0.12)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    queue_rows = load_jsonl(args.input)
    accessions = sorted({str(row.get("uniprot_id")).upper() for row in queue_rows if row.get("uniprot_id")})
    if args.limit_accessions and args.limit_accessions > 0:
        accessions = accessions[: args.limit_accessions]

    evidence_by_accession: dict[str, dict[str, Any]] = {}
    fetch_states = Counter()
    errors: dict[str, str] = {}

    def fetch_one(accession: str) -> tuple[str, dict[str, Any] | None, str, str | None]:
        try:
            data, state = load_or_fetch(accession, args.cache_dir, args.timeout, args.page_size, args.refresh)
            return accession, data, state, None
        except Exception as exc:
            return accession, None, "failed", str(exc)

    if args.workers <= 1:
        iterator = (fetch_one(accession) for accession in accessions)
        for accession, data, state, error in iterator:
            fetch_states[state] += 1
            if data is not None:
                evidence_by_accession[accession] = data
            if error:
                errors[accession] = error
            if args.sleep:
                time.sleep(args.sleep)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(fetch_one, accession): accession for accession in accessions}
            for future in as_completed(futures):
                accession, data, state, error = future.result()
                fetch_states[state] += 1
                if data is not None:
                    evidence_by_accession[accession] = data
                if error:
                    errors[accession] = error

    output_rows = []
    for row in queue_rows:
        accession = str(row.get("uniprot_id") or "").upper()
        requested_pfam = row.get("pfam_id")
        data = evidence_by_accession.get(accession)
        if not data:
            output_rows.append({
                **row,
                "interpro_fetch_state": "not_requested" if accession not in accessions else "failed",
                "interpro_entries_found": 0,
                "matched_pfam_intervals": [],
                "other_pfam_ids": [],
                "has_exact_pfam_interval": False,
                "policy": "InterPro evidence only; not a reviewed domain interval decision",
            })
            continue
        entries = data.get("results") or []
        all_intervals = []
        other_pfam_ids = []
        for entry in entries:
            pfam_id = (entry.get("metadata") or {}).get("accession")
            intervals = intervals_for_entry(entry, accession)
            if pfam_id == requested_pfam:
                all_intervals.extend(intervals)
            elif pfam_id:
                other_pfam_ids.append(pfam_id)
        output_rows.append({
            **row,
            "interpro_fetch_state": "ok",
            "interpro_entries_found": len(entries),
            "matched_pfam_intervals": all_intervals,
            "other_pfam_ids": sorted(set(other_pfam_ids)),
            "has_exact_pfam_interval": bool(all_intervals),
            "policy": "InterPro evidence only; not a reviewed domain interval decision",
        })

    write_jsonl(args.output, output_rows)
    report = {
        "input_rows": len(queue_rows),
        "unique_accessions_in_input": len({str(row.get("uniprot_id")).upper() for row in queue_rows if row.get("uniprot_id")}),
        "unique_accessions_requested": len(accessions),
        "output_rows": len(output_rows),
        "rows_with_exact_pfam_interval": sum(1 for row in output_rows if row["has_exact_pfam_interval"]),
        "rows_without_exact_pfam_interval": sum(1 for row in output_rows if not row["has_exact_pfam_interval"]),
        "rows_not_requested": sum(1 for row in output_rows if row["interpro_fetch_state"] == "not_requested"),
        "fetch_state_counts": dict(fetch_states),
        "errors": errors,
        "output": str(args.output),
        "cache_dir": str(args.cache_dir),
        "source": INTERPRO_BASE,
        "policy": "public evidence only; reviewed domain decisions must be written separately",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "unique_accessions_requested": report["unique_accessions_requested"],
        "rows_with_exact_pfam_interval": report["rows_with_exact_pfam_interval"],
        "errors": len(errors),
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
