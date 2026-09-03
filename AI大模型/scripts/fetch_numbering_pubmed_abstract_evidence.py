#!/usr/bin/env python3
"""Fetch PubMed abstract metadata for numbering curation risk review.

This script uses NCBI EFetch XML and stores metadata/abstract evidence only.
It does not fetch full articles and does not write reviewed curation decisions.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "numbering_pubmed_evidence.jsonl"
CACHE_DIR = AI_ROOT / "datasets" / "curation" / "numbering_public_evidence" / "pubmed_efetch"
OUT = AI_ROOT / "datasets" / "curation" / "numbering_pubmed_abstract_evidence.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_pubmed_abstract_evidence_report.json"
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

STRONG_KEYWORDS = {
    "protein", "enzyme", "mutation", "mutant", "amino acid", "residue",
    "isoform", "stability", "thermostability", "catalytic", "folding",
    "hydrolase", "transferase", "oxidase", "reductase", "protease",
    "lipase", "amylase", "dehydrogenase", "variant", "overexpression",
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def batch_key(pmids: list[str]) -> str:
    return f"{pmids[0]}-{pmids[-1]}-{len(pmids)}.xml"


def fetch_xml(pmids: list[str], timeout: int) -> str:
    query = urllib.parse.urlencode({
        "db": "pubmed",
        "retmode": "xml",
        "id": ",".join(pmids),
    })
    request = urllib.request.Request(f"{EUTILS_BASE}?{query}", headers={"User-Agent": "KWB-EnzymeDesigner-local-curation/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def load_or_fetch_batch(pmids: list[str], cache_dir: Path, timeout: int, refresh: bool) -> tuple[str, str]:
    path = cache_dir / batch_key(pmids)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8"), "cached"
    text = fetch_xml(pmids, timeout)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text, "fetched"


def parse_pubmed_xml(text: str) -> dict[str, dict[str, Any]]:
    root = ET.fromstring(text)
    parsed: dict[str, dict[str, Any]] = {}
    for article in root.findall(".//PubmedArticle"):
        pmid = clean_text(article.findtext(".//MedlineCitation/PMID"))
        if not pmid:
            continue
        title = clean_text(article.findtext(".//ArticleTitle"))
        abstract_parts = []
        for node in article.findall(".//Abstract/AbstractText"):
            label = clean_text(node.attrib.get("Label"))
            body = clean_text("".join(node.itertext()))
            if not body:
                continue
            abstract_parts.append(f"{label}: {body}" if label else body)
        keyword_list = [clean_text("".join(node.itertext())) for node in article.findall(".//KeywordList/Keyword")]
        parsed[pmid] = {
            "pmid": pmid,
            "title": title,
            "abstract": clean_text(" ".join(abstract_parts)),
            "keywords": [item for item in keyword_list if item],
        }
    return parsed


def keyword_hits(text: str) -> list[str]:
    lower = text.lower()
    return sorted({keyword for keyword in STRONG_KEYWORDS if keyword in lower})


def compact_mutation(mutation: str | None) -> str:
    return clean_text(mutation).lower().replace(" ", "")


def mentions_mutation(text: str, mutation: str | None) -> bool:
    compact = compact_mutation(mutation)
    if not compact:
        return False
    lower = clean_text(text).lower().replace(" ", "")
    return compact in lower


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch PubMed abstract evidence")
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
    pmids = sorted({str(row.get("pmid")) for row in input_rows if row.get("pmid")})
    parsed: dict[str, dict[str, Any]] = {}
    fetch_states = Counter()
    errors: dict[str, str] = {}
    for start in range(0, len(pmids), args.batch_size):
        batch = pmids[start:start + args.batch_size]
        try:
            text, state = load_or_fetch_batch(batch, args.cache_dir, args.timeout, args.refresh)
            fetch_states[state] += 1
            parsed.update(parse_pubmed_xml(text))
        except Exception as exc:
            fetch_states["failed"] += 1
            for pmid in batch:
                errors[pmid] = str(exc)
        if args.sleep:
            time.sleep(args.sleep)

    output_rows = []
    for row in input_rows:
        pmid = str(row.get("pmid") or "")
        item = parsed.get(pmid, {})
        title = item.get("title") or clean_text(row.get("title"))
        abstract = item.get("abstract") or ""
        combined = f"{title} {abstract} {' '.join(item.get('keywords') or [])}"
        hits = keyword_hits(combined)
        mutation_hit = mentions_mutation(combined, row.get("reported_mutation"))
        output_rows.append({
            "record_id": row.get("record_id"),
            "priority": row.get("priority"),
            "uniprot_id": row.get("uniprot_id"),
            "reported_mutation": row.get("reported_mutation"),
            "literature_ref": row.get("literature_ref"),
            "pmid": pmid,
            "pubmed_found": bool(item),
            "title": title,
            "has_abstract": bool(abstract),
            "abstract": abstract,
            "keywords": item.get("keywords") or [],
            "abstract_keyword_hits": hits,
            "abstract_has_protein_or_mutation_signal": bool(hits),
            "reported_mutation_mentioned_in_title_or_abstract": mutation_hit,
            "review_risk": "possible_relevance" if (mutation_hit or hits) else "high",
            "policy": "PubMed abstract metadata evidence only; not a curation decision",
        })

    write_jsonl(args.output, output_rows)
    report = {
        "input_rows": len(input_rows),
        "unique_pmids_requested": len(pmids),
        "unique_pmids_found": len(parsed),
        "rows_with_abstract": sum(1 for row in output_rows if row["has_abstract"]),
        "rows_with_abstract_signal": sum(1 for row in output_rows if row["abstract_has_protein_or_mutation_signal"]),
        "rows_with_reported_mutation_mention": sum(1 for row in output_rows if row["reported_mutation_mentioned_in_title_or_abstract"]),
        "rows_high_risk_after_abstract": sum(1 for row in output_rows if row["review_risk"] == "high"),
        "rows_possible_relevance_after_abstract": sum(1 for row in output_rows if row["review_risk"] == "possible_relevance"),
        "fetch_state_counts": dict(fetch_states),
        "errors": errors,
        "output": str(args.output),
        "cache_dir": str(args.cache_dir),
        "policy": "abstract metadata only; high-risk rows must remain weak without source review",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "unique_pmids_found": report["unique_pmids_found"],
        "rows_with_abstract_signal": report["rows_with_abstract_signal"],
        "rows_with_reported_mutation_mention": report["rows_with_reported_mutation_mention"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
