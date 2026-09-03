#!/usr/bin/env python3
"""Fetch PubMed metadata evidence for numbering curation.

This script stores bibliographic metadata and lightweight relevance flags only.
It does not store full article text and does not create reviewed curation
decisions.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "numbering_uniprot_evidence.jsonl"
CACHE_DIR = AI_ROOT / "datasets" / "curation" / "numbering_public_evidence" / "pubmed_esummary"
OUT = AI_ROOT / "datasets" / "curation" / "numbering_pubmed_evidence.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_pubmed_evidence_report.json"
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

PROTEIN_KEYWORDS = {
    "protein", "enzyme", "mutation", "mutant", "variant", "amino", "residue",
    "isoform", "stability", "thermostability", "catalytic", "activity",
    "expression", "folding", "kinase", "receptor", "dehydrogenase", "hydrolase",
    "transferase", "oxidase", "reductase", "protease", "lipase", "amylase",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def pmid_from_ref(ref: str | None) -> str | None:
    if not ref:
        return None
    text = str(ref).strip()
    if text.upper().startswith("PMID:"):
        text = text.split(":", 1)[1]
    return text if text.isdigit() else None


def batch_key(pmids: list[str]) -> str:
    return f"{pmids[0]}-{pmids[-1]}-{len(pmids)}.json"


def fetch_esummary(pmids: list[str], timeout: int) -> dict[str, Any]:
    query = urllib.parse.urlencode({
        "db": "pubmed",
        "retmode": "json",
        "id": ",".join(pmids),
    })
    request = urllib.request.Request(f"{EUTILS_BASE}?{query}", headers={"User-Agent": "KWB-EnzymeDesigner-local-curation/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("PubMed esummary response was not a JSON object")
    return payload


def load_or_fetch_batch(pmids: list[str], cache_dir: Path, timeout: int, refresh: bool) -> tuple[dict[str, Any], str]:
    path = cache_dir / batch_key(pmids)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8")), "cached"
    payload = fetch_esummary(pmids, timeout)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload, "fetched"


def article_ids(summary: dict[str, Any]) -> dict[str, str]:
    ids = {}
    for item in summary.get("articleids") or []:
        kind = str(item.get("idtype") or "").lower()
        value = item.get("value")
        if kind and value:
            ids[kind] = str(value)
    return ids


def keyword_hits(title: str) -> list[str]:
    lower = title.lower()
    return sorted({keyword for keyword in PROTEIN_KEYWORDS if keyword in lower})


def mutation_title_mentions(title: str, mutation: str | None) -> bool:
    if not mutation:
        return False
    lower = title.lower().replace(" ", "")
    compact = str(mutation).lower().replace(" ", "")
    return compact in lower


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return " ".join(text.split())


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch PubMed metadata evidence for numbering curation")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--sleep", type=float, default=0.34)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    input_rows = load_jsonl(args.input)
    pmids = sorted({pmid for row in input_rows if (pmid := pmid_from_ref(row.get("literature_ref")))})
    summaries: dict[str, dict[str, Any]] = {}
    fetch_states = Counter()
    errors: dict[str, str] = {}

    for start in range(0, len(pmids), args.batch_size):
        batch = pmids[start:start + args.batch_size]
        try:
            payload, state = load_or_fetch_batch(batch, args.cache_dir, args.timeout, args.refresh)
            fetch_states[state] += 1
            result = payload.get("result") or {}
            for pmid in batch:
                item = result.get(pmid)
                if isinstance(item, dict) and item.get("uid"):
                    summaries[pmid] = item
        except Exception as exc:
            fetch_states["failed"] += 1
            for pmid in batch:
                errors[pmid] = str(exc)
        if args.sleep:
            time.sleep(args.sleep)

    evidence_rows = []
    for row in input_rows:
        pmid = pmid_from_ref(row.get("literature_ref"))
        summary = summaries.get(pmid or "")
        title = clean_text((summary or {}).get("title")) or ""
        hits = keyword_hits(title)
        ids = article_ids(summary or {})
        evidence_rows.append({
            "record_id": row.get("record_id"),
            "packet_id": row.get("packet_id"),
            "priority": row.get("priority"),
            "uniprot_id": row.get("uniprot_id"),
            "reported_mutation": row.get("reported_mutation"),
            "literature_ref": row.get("literature_ref"),
            "pmid": pmid,
            "pubmed_found": bool(summary),
            "title": title,
            "journal": clean_text((summary or {}).get("fulljournalname") or (summary or {}).get("source")),
            "pubdate": clean_text((summary or {}).get("pubdate")),
            "doi": clean_text(ids.get("doi")),
            "pubtypes": (summary or {}).get("pubtype") or [],
            "title_protein_keyword_hits": hits,
            "title_has_protein_keyword": bool(hits),
            "reported_mutation_mentioned_in_title": mutation_title_mentions(title, row.get("reported_mutation")),
            "review_risk": "high" if summary and not hits else ("missing_pubmed" if not summary else "needs_review"),
            "policy": "PubMed metadata evidence only; not a curation decision",
        })

    write_jsonl(args.output, evidence_rows)
    found = sum(1 for row in evidence_rows if row["pubmed_found"])
    title_keyword = sum(1 for row in evidence_rows if row["title_has_protein_keyword"])
    title_mutation = sum(1 for row in evidence_rows if row["reported_mutation_mentioned_in_title"])
    report = {
        "input_rows": len(input_rows),
        "unique_pmids_requested": len(pmids),
        "unique_pmids_found": len(summaries),
        "rows_with_pubmed_found": found,
        "rows_with_title_protein_keyword": title_keyword,
        "rows_with_title_mutation_mention": title_mutation,
        "rows_high_review_risk": sum(1 for row in evidence_rows if row["review_risk"] == "high"),
        "fetch_state_counts": dict(fetch_states),
        "errors": errors,
        "output": str(args.output),
        "cache_dir": str(args.cache_dir),
        "policy": "metadata only; high review risk rows must not be promoted without source review",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "unique_pmids_found": report["unique_pmids_found"],
        "rows_with_title_protein_keyword": title_keyword,
        "rows_high_review_risk": report["rows_high_review_risk"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
