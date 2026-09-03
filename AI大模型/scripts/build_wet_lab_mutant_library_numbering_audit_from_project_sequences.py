#!/usr/bin/env python3
"""Build numbering-audit rows from approved wet-lab project parent sequences."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
SEQUENCE_INPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_project_sequences.local.jsonl"
SEQUENCE_REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_project_sequence_intake_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_numbering_audit_from_project_sequences.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_numbering_audit_from_project_sequences_report.json"

MUTATION_RE = re.compile(r"^([A-Z])([0-9]+)([A-Z])$")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def clean_sequence(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value.upper() if ch.isalpha())


def approved_sequences(rows: list[dict[str, Any]], validation_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    approved_projects = set(validation_report.get("approved_projects") or [])
    result = {}
    for row in rows:
        project = str(row.get("project_id") or "")
        if project in approved_projects and row.get("approved_for_numbering_audit") is True:
            result[project] = row
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab numbering audit from approved project sequences")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--sequence-input", type=Path, default=SEQUENCE_INPUT)
    parser.add_argument("--sequence-report", type=Path, default=SEQUENCE_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    sequence_rows = load_jsonl(args.sequence_input)
    validation_report = load_json(args.sequence_report)
    sequences = approved_sequences(sequence_rows, validation_report)

    audit_rows: list[dict[str, Any]] = []
    counts = Counter()
    for candidate in candidates:
        project = str(candidate.get("source_project") or "")
        sequence_row = sequences.get(project)
        if not sequence_row:
            continue
        sequence = clean_sequence(sequence_row.get("sequence"))
        mutations = candidate.get("mutation_set") or []
        if not mutations:
            continue
        checks = []
        for mutation in mutations:
            match = MUTATION_RE.match(str(mutation))
            if not match:
                checks.append({
                    "mutation": mutation,
                    "valid_mutation_syntax": False,
                    "wild_type_matches": False,
                })
                continue
            wt, pos_text, mutant = match.groups()
            pos = int(pos_text)
            observed = sequence[pos - 1] if 1 <= pos <= len(sequence) else None
            checks.append({
                "mutation": mutation,
                "valid_mutation_syntax": True,
                "reported_wild_type": wt,
                "position": pos,
                "reported_mutant": mutant,
                "observed_residue": observed,
                "in_range": observed is not None,
                "wild_type_matches": observed == wt,
            })
        numbering_verified = bool(checks) and all(check.get("wild_type_matches") for check in checks)
        blockers = [] if numbering_verified else [
            "mutation_wild_type_mismatch_or_out_of_range",
            "manual_review_required_before_candidate_flag_update",
        ]
        audit_rows.append({
            "numbering_audit_id": f"wetlab-numbering-audit-{candidate.get('feedback_candidate_id')}",
            "feedback_candidate_id": candidate.get("feedback_candidate_id"),
            "source_project": project,
            "variant": candidate.get("variant"),
            "mutation_set": mutations,
            "sequence_intake_id": sequence_row.get("sequence_intake_id"),
            "sequence_id": sequence_row.get("sequence_id"),
            "sequence_version": sequence_row.get("sequence_version"),
            "sequence_length": len(sequence),
            "numbering_verified_candidate": numbering_verified,
            "mutation_checks": checks,
            "blockers": blockers,
            "ready_to_update_candidate_numbering_flag": False,
            "policy": "Audit row only; does not modify wet-lab feedback candidates or training labels.",
        })
        counts["audit_rows"] += 1
        counts[f"project_{project}_audit_rows"] += 1
        if numbering_verified:
            counts["numbering_verified_candidate_rows"] += 1
            counts[f"project_{project}_numbering_verified_candidate_rows"] += 1

    write_jsonl(args.output, audit_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidates": str(args.candidates),
        "sequence_input": str(args.sequence_input),
        "sequence_report": str(args.sequence_report),
        "output": str(args.output),
        "approved_projects": sorted(sequences),
        "candidate_rows": len(candidates),
        "audit_rows": len(audit_rows),
        "numbering_verified_candidate_rows": counts.get("numbering_verified_candidate_rows", 0),
        "ready_to_update_candidate_numbering_flags": False,
        "ready_for_feedback_intake_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "counts": dict(counts),
        "policy": "Approved parent sequences can produce numbering audit rows, but a separate reviewed apply gate is required before candidate flags change.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "approved_projects": report["approved_projects"],
        "audit_rows": report["audit_rows"],
        "numbering_verified_candidate_rows": report["numbering_verified_candidate_rows"],
        "ready_to_update_candidate_numbering_flags": report["ready_to_update_candidate_numbering_flags"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
