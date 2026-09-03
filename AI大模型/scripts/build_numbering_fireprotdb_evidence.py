#!/usr/bin/env python3
"""Query FireProtDB API for numbering evidence candidates.

This script is conservative: it caches API responses and reports exact
UniProt+mutation matches only. It does not write reviewed decisions.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "curation" / "numbering_isoform_review_candidates.jsonl"
OUT_JSONL = AI_ROOT / "datasets" / "curation" / "numbering_fireprotdb_evidence.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "numbering_fireprotdb_evidence_report.json"
CACHE_DIR = AI_ROOT / "cache" / "external" / "FireProtDB" / "numbering_evidence"
API = "https://loschmidt.chemi.muni.cz/fireprotdb/api/search"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def run_curl(url: str, timeout: int) -> tuple[int, str, str]:
    process = subprocess.run(
        ["curl", "-L", "--max-time", str(timeout), url],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return process.returncode, process.stdout, process.stderr


def find_strings(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found.update(find_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.update(find_strings(item))
    elif value is not None:
        found.add(str(value))
    return found


def exact_match(payload: Any, uniprot_id: str, mutation: str) -> bool:
    strings = find_strings(payload)
    text = "\n".join(strings).upper()
    return uniprot_id.upper() in text and mutation.upper() in text


def query_url(uniprot_id: str, mutation: str, limit: int) -> str:
    query = json.dumps({"fulltext": f"{uniprot_id} {mutation}"}, separators=(",", ":"))
    return f"{API}?query={urllib.parse.quote(query)}&limit={limit}&format=json&inline=true"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FireProtDB numbering evidence")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--output-jsonl", type=Path, default=OUT_JSONL)
    parser.add_argument("--output-report", type=Path, default=OUT_REPORT)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--max-rows", type=int, default=8)
    args = parser.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    candidates = load_jsonl(args.candidates)[: args.max_rows]
    for candidate in candidates:
        record_id = str(candidate.get("record_id"))
        uniprot_id = str(candidate.get("uniprot_id"))
        mutation = str(candidate.get("reported_mutation"))
        url = query_url(uniprot_id, mutation, args.limit)
        code, stdout, stderr = run_curl(url, args.timeout)
        cache_path = args.cache_dir / f"{record_id.replace(':', '_')}.json"
        payload: Any = []
        parse_error = None
        if code == 0:
            try:
                payload = json.loads(stdout or "[]")
            except json.JSONDecodeError as exc:
                parse_error = str(exc)
                payload = {"raw": stdout}
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        row_count = len(payload) if isinstance(payload, list) else None
        rows.append({
            "record_id": record_id,
            "uniprot_id": uniprot_id,
            "reported_mutation": mutation,
            "source": "FireProtDB API",
            "api_url": url,
            "curl_returncode": code,
            "stderr_tail": stderr[-500:],
            "cache_path": str(cache_path.relative_to(AI_ROOT)),
            "response_rows": row_count,
            "exact_uniprot_mutation_match": bool(code == 0 and parse_error is None and exact_match(payload, uniprot_id, mutation)),
            "parse_error": parse_error,
            "policy": "evidence only; not a reviewed numbering decision",
        })
    write_jsonl(args.output_jsonl, rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source": "FireProtDB API",
        "candidate_rows": len(candidates),
        "evidence_rows": len(rows),
        "exact_match_rows": sum(1 for row in rows if row["exact_uniprot_mutation_match"]),
        "failed_query_rows": sum(1 for row in rows if row["curl_returncode"] != 0),
        "output_jsonl": str(args.output_jsonl),
        "cache_dir": str(args.cache_dir),
        "safe_to_auto_promote": False,
        "policy": "Only exact API evidence may become a decision draft after local canonical WT validation; this report does not promote labels.",
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": report["candidate_rows"],
        "exact_match_rows": report["exact_match_rows"],
        "failed_query_rows": report["failed_query_rows"],
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0 if report["failed_query_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
