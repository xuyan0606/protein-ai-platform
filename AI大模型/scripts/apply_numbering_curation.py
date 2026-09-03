#!/usr/bin/env python3
"""Apply reviewed numbering curation decisions to weak evidence labels."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
AUDITED_INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_audited.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
QUEUE = AI_ROOT / "datasets" / "curation" / "numbering_curation_queue.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_repaired.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_curation_apply_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_sequences(db_path: Path) -> dict[str, str]:
    with connect_ro(db_path) as conn:
        rows = conn.execute("SELECT uniprot_id, sequence FROM enzyme_records").fetchall()
    return {row["uniprot_id"]: row["sequence"] for row in rows}


def invalid_decision(row: dict[str, Any], decision: dict[str, Any], reason: str) -> dict[str, Any]:
    output = dict(row)
    output["curation_status"] = f"invalid_curation_decision_{reason}"
    output["usable_as_supervised_label"] = False
    output["usable_as_weak_evidence"] = True
    output["curation_decision"] = decision
    output.setdefault("integrity_flags", [])
    output["integrity_flags"] = sorted(set(output["integrity_flags"] + [f"curation_{reason}"]))
    return output


def apply_decision(row: dict[str, Any], decision: dict[str, Any], sequences: dict[str, str]) -> dict[str, Any] | None:
    mode = decision.get("decision")
    if mode == "reject_label":
        return None
    output = dict(row)
    if mode == "keep_unresolved_weak":
        output["curation_status"] = "weak_evidence_unresolved_after_review"
        output["usable_as_supervised_label"] = False
        output["usable_as_weak_evidence"] = True
        output["curation_decision"] = decision
        return output
    if mode == "map_to_canonical":
        canonical_position = decision.get("canonical_position")
        canonical_wt = str(decision.get("canonical_wild_type") or "").upper()
        canonical_mutant = str(decision.get("canonical_mutant") or row.get("mutant") or "").upper()
        if not canonical_position or not canonical_wt or not canonical_mutant:
            return invalid_decision(row, decision, "missing_canonical_fields")
        canonical_uniprot = decision.get("canonical_uniprot_id") or row.get("uniprot_id")
        sequence = sequences.get(str(canonical_uniprot))
        if not sequence:
            return invalid_decision(row, decision, "missing_canonical_sequence")
        if int(canonical_position) < 1 or int(canonical_position) > len(sequence):
            return invalid_decision(row, decision, "canonical_position_out_of_range")
        current_wt = sequence[int(canonical_position) - 1].upper()
        if current_wt != canonical_wt:
            output = invalid_decision(row, decision, "canonical_wild_type_mismatch")
            output["canonical_sequence_residue"] = current_wt
            return output
        if float(decision.get("confidence") or 0.0) < 0.5:
            return invalid_decision(row, decision, "low_confidence")
        output.update({
            "uniprot_id": canonical_uniprot,
            "group_key": f"uniprot:{canonical_uniprot}",
            "mutation_position": int(canonical_position),
            "wild_type": canonical_wt,
            "mutant": canonical_mutant,
            "mutation": f"{canonical_wt}{int(canonical_position)}{canonical_mutant}",
            "numbering_verified_by_sequence": True,
            "integrity_flags": [],
            "curation_status": "repaired_supervised_label",
            "usable_as_supervised_label": True,
            "usable_as_weak_evidence": False,
            "curation_decision": decision,
        })
        return output
    output["curation_status"] = "unknown_curation_decision"
    output["usable_as_supervised_label"] = False
    output["usable_as_weak_evidence"] = True
    output["curation_decision"] = decision
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply numbering curation decisions")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--input", type=Path, default=AUDITED_INPUT)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    decisions = load_jsonl(args.decisions)
    queue_ids = {
        str(row.get("record_id") or "")
        for row in load_jsonl(args.queue)
        if row.get("record_id")
    }
    active_decisions = [
        row for row in decisions
        if str(row.get("record_id") or "") in queue_ids
    ]
    inactive_decisions = [
        row for row in decisions
        if str(row.get("record_id") or "") not in queue_ids
    ]
    sequences = load_sequences(args.db)
    decision_by_record = {row["record_id"]: row for row in active_decisions if row.get("record_id")}
    repaired = []
    rejected = 0
    for row in rows:
        decision = decision_by_record.get(row.get("record_id"))
        if decision:
            applied = apply_decision(row, decision, sequences)
            if applied is None:
                rejected += 1
            else:
                repaired.append(applied)
        else:
            repaired.append(row)

    write_jsonl(args.output, repaired)
    status_counts = Counter(row.get("curation_status") for row in repaired)
    supervised_rows = sum(1 for row in repaired if row.get("usable_as_supervised_label"))
    report = {
        "input_rows": len(rows),
        "decision_rows": len(decisions),
        "active_decision_rows": len(active_decisions),
        "inactive_decision_rows": len(inactive_decisions),
        "active_queue_rows": len(queue_ids),
        "output_rows": len(repaired),
        "rejected_rows": rejected,
        "usable_as_supervised_label": supervised_rows,
        "status_counts": dict(status_counts),
        "output": str(args.output),
        "policy": (
            "Only current numbering queue decisions are applied. Inactive historical decisions are ignored. "
            "Only map_to_canonical decisions with canonical fields can promote weak evidence into supervised labels."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": len(decisions),
        "active_decision_rows": len(active_decisions),
        "usable_as_supervised_label": supervised_rows,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
