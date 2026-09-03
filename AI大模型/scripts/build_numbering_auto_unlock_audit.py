#!/usr/bin/env python3
"""Audit whether numbering candidates can be safely auto-promoted."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ISOFORM = AI_ROOT / "datasets" / "curation" / "numbering_isoform_review_candidates.jsonl"
PUBMED = AI_ROOT / "datasets" / "curation" / "numbering_pubmed_abstract_evidence.jsonl"
FIREPROT = AI_ROOT / "datasets" / "curation" / "numbering_fireprotdb_evidence.jsonl"
OUT = AI_ROOT / "reports" / "numbering_auto_unlock_audit_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("record_id")): row for row in rows if row.get("record_id")}


def audit_row(candidate: dict[str, Any], pubmed: dict[str, Any], fireprot: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if not candidate.get("candidate_decision") == "map_to_canonical":
        blockers.append("no_candidate_map_to_canonical")
    if candidate.get("review_required"):
        blockers.append("isoform_candidate_still_requires_manual_review")
    if not pubmed.get("reported_mutation_mentioned_in_title_or_abstract"):
        blockers.append("reported_mutation_not_mentioned_in_pubmed_title_or_abstract")
    if pubmed.get("review_risk") == "high":
        blockers.append("pubmed_review_risk_high")
    if not fireprot.get("exact_uniprot_mutation_match"):
        blockers.append("no_exact_fireprotdb_uniprot_mutation_match")
    if fireprot.get("curl_returncode") not in {0, None}:
        blockers.append("fireprotdb_query_failed_or_timed_out")
    ready = not blockers
    return {
        "record_id": candidate.get("record_id"),
        "uniprot_id": candidate.get("uniprot_id"),
        "reported_mutation": candidate.get("reported_mutation"),
        "candidate_isoforms": candidate.get("candidate_isoforms"),
        "candidate_canonical_position": candidate.get("candidate_canonical_position"),
        "pubmed_review_risk": pubmed.get("review_risk"),
        "pubmed_mutation_mentioned": bool(pubmed.get("reported_mutation_mentioned_in_title_or_abstract")),
        "fireprotdb_exact_match": bool(fireprot.get("exact_uniprot_mutation_match")),
        "ready_for_decision_draft": ready,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build numbering auto-unlock audit")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    candidates = load_jsonl(ISOFORM)
    pubmed_by_id = by_id(load_jsonl(PUBMED))
    fireprot_by_id = by_id(load_jsonl(FIREPROT))
    rows = [
        audit_row(candidate, pubmed_by_id.get(str(candidate.get("record_id")), {}), fireprot_by_id.get(str(candidate.get("record_id")), {}))
        for candidate in candidates
    ]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidate_rows": len(candidates),
        "ready_for_decision_draft_rows": sum(1 for row in rows if row["ready_for_decision_draft"]),
        "blocked_rows": sum(1 for row in rows if not row["ready_for_decision_draft"]),
        "safe_to_auto_promote": False,
        "rows": rows,
        "policy": "Auto-promotion requires isoform/canonical mapping plus direct source support; unresolved candidates stay weak.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": report["candidate_rows"],
        "ready_for_decision_draft_rows": report["ready_for_decision_draft_rows"],
        "blocked_rows": report["blocked_rows"],
        "safe_to_auto_promote": report["safe_to_auto_promote"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
