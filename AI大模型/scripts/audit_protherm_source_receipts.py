#!/usr/bin/env python3
"""Audit ProTherm-like mutation rows against PubMed source receipts.

This is an evidence audit only. It never changes curation decisions, strict
tables, training imports, benchmark intake, or release flags. A PMID that is
found is still only a source candidate until the paper-level mutation,
protein, assay, and direction are independently reviewed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_verified.jsonl"
DEEP_AUDIT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_all_stability_records.jsonl"
REPORT = AI_ROOT / "reports" / "protherm_source_receipt_audit_report.json"
OUTPUT = AI_ROOT / "datasets" / "curation" / "protherm_source_receipt_audit.jsonl"

PMID_RE = re.compile(r"(?:PMID[: ]*)?(\d{6,9})", re.IGNORECASE)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def fetch_pubmed(pmids: list[str], timeout: float) -> tuple[bytes, int, str | None]:
    query = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"})
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "KWB-source-receipt-audit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return body, int(response.status), url
    except Exception as exc:  # network errors are recorded, not hidden
        return b"", 0, f"{url}#error={type(exc).__name__}:{exc}"


def parse_summary(body: bytes) -> dict[str, dict[str, Any]]:
    if not body:
        return {}
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for doc in root.findall(".//DocSum"):
        pmid = (doc.findtext("Id") or "").strip()
        if not pmid:
            continue
        values: dict[str, Any] = {"pmid": pmid}
        for item in doc.findall("Item"):
            name = item.attrib.get("Name")
            if name:
                values[name] = normalized_text(item.text or "")
        result[pmid] = values
    return result


def mutation_tokens(row: dict[str, Any]) -> list[str]:
    mutation = str(row.get("mutation") or "").upper()
    tokens = [mutation]
    match = re.match(r"^([A-Z])(\d+)([A-Z])$", mutation)
    if match:
        wt, pos, mut = match.groups()
        tokens.extend([f"{wt}{pos}{mut}", f"{wt}{pos} {mut}", f"{wt}{pos}->{mut}"])
    return tokens


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ProTherm-like rows against PubMed source receipts")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--deep-audit", type=Path, default=DEEP_AUDIT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--network", action="store_true", help="fetch PubMed summaries")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.35)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    deep = {str(row.get("record_id")): row for row in load_jsonl(args.deep_audit) if row.get("record_id")}
    pmid_by_record: dict[str, str] = {}
    for row in rows:
        match = PMID_RE.search(str(row.get("literature_ref") or ""))
        if match:
            pmid_by_record[str(row.get("record_id"))] = match.group(1)

    unique_pmids = sorted(set(pmid_by_record.values()))
    body = b""
    status = 0
    url: str | None = None
    if args.network and unique_pmids:
        body, status, url = fetch_pubmed(unique_pmids, args.timeout)
    summaries = parse_summary(body)

    audited: list[dict[str, Any]] = []
    for row in rows:
        record_id = str(row.get("record_id"))
        pmid = pmid_by_record.get(record_id)
        source = summaries.get(pmid or "")
        title = normalized_text(str(source.get("Title") or "")) if source else None
        abstract = normalized_text(str(source.get("AbstractText") or "")) if source else None
        haystack = f"{title or ''} {abstract or ''}".upper()
        tokens = mutation_tokens(row)
        mutation_match = any(token.upper() in haystack for token in tokens)
        deep_row = deep.get(record_id, {})
        if not args.network:
            receipt_status = "not_run_network_disabled"
        elif status != 200:
            receipt_status = "blocked_pubmed_request_failed"
        elif not source:
            receipt_status = "pubmed_id_not_returned"
        elif mutation_match:
            receipt_status = "pubmed_summary_contains_mutation_token"
        else:
            receipt_status = "pubmed_found_mutation_not_in_summary"
        audited.append({
            "record_id": record_id,
            "uniprot_id": row.get("uniprot_id"),
            "mutation": row.get("mutation"),
            "literature_ref": row.get("literature_ref"),
            "pmid": pmid,
            "pubmed_receipt_status": receipt_status,
            "pubmed_http_status": status or None,
            "pubmed_title": title,
            "pubmed_mutation_token_match_in_summary": mutation_match if source else None,
            "source_lineage_flags_before_review": deep_row.get("source_lineage_flags") or [],
            "deep_audit_recommended_decision": deep_row.get("audit_recommended_decision"),
            "candidate_only": True,
            "formal_review_required": True,
            "training_import_allowed_by_this_audit": False,
            "strict_benchmark_allowed_by_this_audit": False,
        })

    receipt = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": url,
        "network_requested": bool(args.network),
        "http_status": status or None,
        "response_sha256": sha256_bytes(body) if body else None,
        "response_bytes": len(body),
        "requested_pmids": unique_pmids,
        "returned_pmids": sorted(summaries),
        "row_count": len(audited),
    }
    counts: dict[str, int] = {}
    for row in audited:
        key = str(row["pubmed_receipt_status"])
        counts[key] = counts.get(key, 0) + 1
    report = {
        "receipt": receipt,
        "row_status_counts": counts,
        "source_verified_candidate_rows": sum(1 for row in audited if row["pubmed_receipt_status"] == "pubmed_summary_contains_mutation_token"),
        "formal_review_required_rows": len(audited),
        "training_import_written_rows": 0,
        "strict_holdout_rows_written": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "PubMed receipt evidence is candidate-only. It cannot override synthetic lineage flags, mutation/assay direction conflicts, numbering review, or formal source acceptance.",
        "output": str(args.output),
    }
    write_jsonl(args.output, audited)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(audited), "status_counts": counts, "source_verified_candidate_rows": report["source_verified_candidate_rows"], "training_import_written_rows": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
