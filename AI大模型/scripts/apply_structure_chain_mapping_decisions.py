#!/usr/bin/env python3
"""Apply reviewed structure chain mapping decisions to local JSONL output."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
WORKLIST = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_worklist.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_decisions.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curation" / "structure_chain_mappings_curated.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_chain_mapping_apply_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def normalize_structure_id(value: Any) -> str:
    return str(value or "").strip().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply structure chain mapping decisions")
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    worklist_rows = load_jsonl(args.worklist)
    decisions = load_jsonl(args.decisions)
    worklist_by_id = {normalize_structure_id(row.get("structure_id")): row for row in worklist_rows}
    decision_by_id = {
        normalize_structure_id(row.get("structure_id")): row
        for row in decisions
        if row.get("structure_id") is not None
    }

    output_rows = []
    rejected = 0
    for structure_id, decision in sorted(decision_by_id.items()):
        worklist_row = worklist_by_id.get(structure_id)
        if not worklist_row:
            continue
        mode = decision.get("decision")
        if mode == "reject_structure":
            rejected += 1
            continue
        if mode == "keep_unreviewed":
            output_rows.append({
                **worklist_row,
                "curation_status": "structure_chain_unreviewed",
                "usable_for_coordinate_features": False,
                "chain_mapping_decision": decision,
            })
        elif mode == "set_chain_mapping":
            output_rows.append({
                **worklist_row,
                "curation_status": "structure_chain_mapping_curated",
                "selected_chain_id": decision.get("selected_chain_id"),
                "canonical_uniprot_id": decision.get("canonical_uniprot_id"),
                "sequence_to_structure_mapping_status": decision.get("sequence_to_structure_mapping_status"),
                "residue_numbering_basis": decision.get("residue_numbering_basis"),
                "missing_residue_ranges": decision.get("missing_residue_ranges") or [],
                "usable_for_coordinate_features": True,
                "chain_mapping_decision": decision,
            })

    write_jsonl(args.output, output_rows)
    report = {
        "worklist_rows": len(worklist_rows),
        "decision_rows": len(decisions),
        "output_rows": len(output_rows),
        "rejected_rows": rejected,
        "reviewed_chain_mapping_rows": sum(1 for row in output_rows if row.get("curation_status") == "structure_chain_mapping_curated"),
        "usable_for_coordinate_features": sum(1 for row in output_rows if row.get("usable_for_coordinate_features")),
        "status_counts": dict(Counter(row.get("curation_status") for row in output_rows)),
        "output": str(args.output),
        "policy": "curated chain mappings are local JSONL only; source SQLite DB and structure cache are not modified",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": report["decision_rows"],
        "reviewed_chain_mapping_rows": report["reviewed_chain_mapping_rows"],
        "usable_for_coordinate_features": report["usable_for_coordinate_features"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
