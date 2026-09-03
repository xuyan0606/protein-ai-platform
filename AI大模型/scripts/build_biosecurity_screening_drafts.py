#!/usr/bin/env python3
"""Build fail-closed biosecurity screening request drafts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
IP_PACKET = AI_ROOT / "datasets" / "curation" / "sequence_ip_review_packets" / "sequence_ip_review_internal_labels_001.jsonl"
OUT = AI_ROOT / "datasets" / "governance" / "biosecurity_screening_drafts.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "biosecurity_screening_draft_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build biosecurity screening drafts")
    parser.add_argument("--ip-packet", type=Path, default=IP_PACKET)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    ip_rows = load_jsonl(args.ip_packet)
    drafts = []
    for row in ip_rows:
        drafts.append({
            "screening_request_id": f"screening:{row.get('candidate_id')}",
            "candidate_id": row.get("candidate_id"),
            "sequence_hash": row.get("sequence_hash"),
            "parent_sequence_hash": row.get("parent_sequence_hash"),
            "mutation_set": row.get("mutation_set"),
            "screening_state": "not_requested",
            "synthesis_permission": "not_requested",
            "screening_provider": None,
            "customer_or_project_approval": "not_requested",
            "intended_use_statement": None,
            "human_reviewer_decision": "not_reviewed",
            "approved_for_ordering": False,
            "blocked_reason": "screening and customer/use review have not been performed",
            "policy": "draft only; do not create order-ready DNA/RNA/construct/provider payloads",
        })
    write_jsonl(args.output, drafts)
    report = {
        "local_only": True,
        "draft_rows": len(drafts),
        "submitted_rows": 0,
        "approved_for_ordering_rows": 0,
        "screening_provider_configured": False,
        "packet_file": str(args.output),
        "ready_for_ordering": False,
        "policy": "Screening drafts start the review workflow but never grant synthesis permission.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"draft_rows": len(drafts), "approved_for_ordering_rows": 0, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
