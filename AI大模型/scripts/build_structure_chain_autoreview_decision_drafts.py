#!/usr/bin/env python3
"""Build human-acceptance drafts from structure chain auto-review candidates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "curation" / "structure_chain_autoreview_candidates.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "structure_chain_autoreview_decision_drafts" / "structure_chain_autoreview_acceptance_001.decision_acceptance.draft.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_chain_autoreview_decision_draft_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def draft_for(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "structure_id": row.get("structure_id"),
        "candidate_bucket": row.get("candidate_bucket"),
        "human_acceptance_status": "not_reviewed",
        "review_draft": True,
        "draft_policy": "draft only; not a reviewed chain mapping decision",
        "curator": "",
        "curated_at": "",
        "source_refs": row.get("source_refs") or [],
        "suggested_decision_row": {
            "structure_id": row.get("structure_id"),
            "decision": row.get("suggested_decision"),
            "canonical_uniprot_id": row.get("canonical_uniprot_id"),
            "selected_chain_id": row.get("selected_chain_id"),
            "sequence_to_structure_mapping_status": row.get("suggested_sequence_to_structure_mapping_status"),
            "residue_numbering_basis": row.get("suggested_residue_numbering_basis"),
            "missing_residue_ranges": [],
            "source_refs": row.get("source_refs") or [],
            "confidence": row.get("confidence"),
            "notes": f"Auto-review candidate only. Human reviewer must verify title/header/sequence evidence before copying to structure_chain_mapping_decisions.jsonl. Title: {row.get('title')}",
            "curator": "human-required",
            "curated_at": None,
        },
        "acceptance_required_checks": [
            "confirm this structure maps to the stated UniProt accession and biological chain",
            "confirm construct/mutant differences and missing residues are acceptable for downstream feature scope",
            "fill curator and curated_at before copying any decision row",
            "do not copy manual_alignment candidates without explicit alignment evidence",
        ],
        "policy": "draft only; not consumed by apply_structure_chain_mapping_decisions.py",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure chain auto-review decision drafts")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    priority = [
        row for row in candidates
        if row.get("candidate_bucket") in {"exact_sequence_match_candidate", "construct_or_mutant_candidate"}
    ][: args.limit]
    drafts = [draft_for(row) for row in priority]
    write_jsonl(args.output, drafts)
    counts = Counter(row.get("candidate_bucket") for row in priority)
    report = {
        "candidate_rows": len(candidates),
        "draft_rows": len(drafts),
        "accepted_rows": 0,
        "bucket_counts": dict(counts),
        "draft_file": str(args.output),
        "ready_for_apply": False,
        "policy": "These drafts require human acceptance and are not valid reviewed decisions until copied with curator and curated_at.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"draft_rows": len(drafts), "accepted_rows": 0, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
