#!/usr/bin/env python3
"""Build literature review risk queues from PubMed metadata evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "numbering_pubmed_evidence.jsonl"
HIGH_RISK_OUT = AI_ROOT / "datasets" / "curation" / "numbering_literature_high_risk_queue.jsonl"
POSSIBLE_OUT = AI_ROOT / "datasets" / "curation" / "numbering_literature_possible_relevance_queue.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_literature_review_risk_report.json"

STRONG_PROTEIN_KEYWORDS = {
    "protein", "enzyme", "mutation", "mutant", "amino", "residue", "isoform",
    "stability", "thermostability", "catalytic", "folding", "hydrolase",
    "transferase", "oxidase", "reductase", "protease", "lipase", "amylase",
    "dehydrogenase",
}
WEAK_AMBIGUOUS_KEYWORDS = {"activity", "expression", "variant", "receptor", "kinase"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def classify(row: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    hits = set(row.get("title_protein_keyword_hits") or [])
    if not row.get("pubmed_found"):
        return "missing_pubmed", ["pmid_not_found"]
    if row.get("reported_mutation_mentioned_in_title"):
        return "possible_relevance", ["reported_mutation_in_title"]
    strong_hits = sorted(hits & STRONG_PROTEIN_KEYWORDS)
    weak_hits = sorted(hits & WEAK_AMBIGUOUS_KEYWORDS)
    if strong_hits:
        reasons.append(f"strong_title_keywords:{','.join(strong_hits)}")
        if weak_hits:
            reasons.append(f"also_ambiguous_keywords:{','.join(weak_hits)}")
        return "possible_relevance", reasons
    if weak_hits:
        return "high_risk", [f"only_ambiguous_title_keywords:{','.join(weak_hits)}"]
    return "high_risk", ["no_protein_or_mutation_title_signal"]


def compact_row(row: dict[str, Any], risk_class: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "record_id": row.get("record_id"),
        "priority": row.get("priority"),
        "uniprot_id": row.get("uniprot_id"),
        "reported_mutation": row.get("reported_mutation"),
        "literature_ref": row.get("literature_ref"),
        "pmid": row.get("pmid"),
        "title": row.get("title"),
        "journal": row.get("journal"),
        "pubdate": row.get("pubdate"),
        "doi": row.get("doi"),
        "title_protein_keyword_hits": row.get("title_protein_keyword_hits"),
        "reported_mutation_mentioned_in_title": row.get("reported_mutation_mentioned_in_title"),
        "risk_class": risk_class,
        "risk_reasons": reasons,
        "review_required": True,
        "policy": "literature risk queue only; not a curation decision",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build literature review risk queues")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--high-risk-output", type=Path, default=HIGH_RISK_OUT)
    parser.add_argument("--possible-output", type=Path, default=POSSIBLE_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    high_risk = []
    possible = []
    class_counts = Counter()
    reason_counts = Counter()
    for row in rows:
        risk_class, reasons = classify(row)
        class_counts[risk_class] += 1
        reason_counts.update(reasons)
        compact = compact_row(row, risk_class, reasons)
        if risk_class == "possible_relevance":
            possible.append(compact)
        else:
            high_risk.append(compact)
    high_risk.sort(key=lambda row: (row.get("priority") or "P9", row.get("uniprot_id") or "", row.get("record_id") or ""))
    possible.sort(key=lambda row: (row.get("priority") or "P9", row.get("uniprot_id") or "", row.get("record_id") or ""))
    write_jsonl(args.high_risk_output, high_risk)
    write_jsonl(args.possible_output, possible)
    report = {
        "input_rows": len(rows),
        "risk_class_counts": dict(class_counts),
        "high_risk_rows": len(high_risk),
        "possible_relevance_rows": len(possible),
        "reported_mutation_title_mentions": sum(1 for row in rows if row.get("reported_mutation_mentioned_in_title")),
        "priority_high_risk_counts": dict(Counter(row.get("priority") for row in high_risk)),
        "priority_possible_counts": dict(Counter(row.get("priority") for row in possible)),
        "risk_reason_counts": dict(reason_counts),
        "high_risk_output": str(args.high_risk_output),
        "possible_output": str(args.possible_output),
        "policy": "high-risk literature rows must remain weak unless source review resolves the mismatch",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "high_risk_rows": len(high_risk),
        "possible_relevance_rows": len(possible),
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
