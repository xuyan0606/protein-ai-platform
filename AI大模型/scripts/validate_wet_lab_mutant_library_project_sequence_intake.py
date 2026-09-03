#!/usr/bin/env python3
"""Validate reviewed parent-sequence intake for wet-lab mutant-library projects."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
INPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_project_sequences.local.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_project_sequences.template.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_project_sequence_intake_validation_report.json"

AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")
MUTATION_RE = re.compile(r"^([A-Z])([0-9]+)([A-Z])$")
VALID_PROJECTS = {"15B", "16B", "4G"}


TEMPLATE_ROWS = [
    {
        "sequence_intake_id": "wetlab-sequence-16b-001",
        "project_id": "16B",
        "sequence_id": "",
        "sequence_version": "",
        "sequence": "",
        "sequence_source": "",
        "source_file": "",
        "reviewer": "",
        "reviewed_at": "",
        "review_basis": "",
        "approved_for_numbering_audit": False,
        "conditions": [],
        "residual_risks": ["template_not_reviewed"],
        "policy": "Template only; not reviewed sequence intake.",
    },
    {
        "sequence_intake_id": "wetlab-sequence-4g-001",
        "project_id": "4G",
        "sequence_id": "",
        "sequence_version": "",
        "sequence": "",
        "sequence_source": "",
        "source_file": "",
        "reviewer": "",
        "reviewed_at": "",
        "review_basis": "",
        "approved_for_numbering_audit": False,
        "conditions": [],
        "residual_risks": ["template_not_reviewed"],
        "policy": "Template only; not reviewed sequence intake.",
    },
]


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


def collect_project_mutations(candidates: list[dict[str, Any]]) -> dict[str, list[str]]:
    project_mutations: dict[str, set[str]] = defaultdict(set)
    for row in candidates:
        project = str(row.get("source_project") or "")
        for mutation in row.get("mutation_set") or []:
            if MUTATION_RE.match(str(mutation)):
                project_mutations[project].add(str(mutation))
    return {project: sorted(mutations, key=lambda m: (int(MUTATION_RE.match(m).group(2)), m)) for project, mutations in project_mutations.items()}


def mutation_checks(sequence: str, mutations: list[str]) -> list[dict[str, Any]]:
    checks = []
    for mutation in mutations:
        match = MUTATION_RE.match(mutation)
        if not match:
            continue
        wt, pos_text, mutant = match.groups()
        pos = int(pos_text)
        observed = sequence[pos - 1] if 1 <= pos <= len(sequence) else None
        checks.append({
            "mutation": mutation,
            "reported_wild_type": wt,
            "position": pos,
            "reported_mutant": mutant,
            "observed_residue": observed,
            "in_range": observed is not None,
            "wild_type_matches": observed == wt,
        })
    return checks


def missing(value: Any) -> bool:
    return value in (None, "", [])


def validate(row: dict[str, Any], project_mutations: dict[str, list[str]]) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    required = [
        "sequence_intake_id",
        "project_id",
        "sequence_id",
        "sequence_version",
        "sequence",
        "sequence_source",
        "reviewer",
        "reviewed_at",
        "review_basis",
        "approved_for_numbering_audit",
        "conditions",
        "residual_risks",
    ]
    for field in required:
        if field not in row:
            errors.append(f"missing_{field}")

    project = str(row.get("project_id") or "")
    if project not in VALID_PROJECTS:
        errors.append("invalid_project_id")

    sequence = clean_sequence(row.get("sequence"))
    if len(sequence) < 50:
        errors.append("sequence_too_short")
    invalid_chars = sorted(set(sequence) - AA_ALPHABET)
    if invalid_chars:
        errors.append("sequence_has_non_canonical_amino_acids")

    checks = mutation_checks(sequence, project_mutations.get(project, []))
    if not checks:
        errors.append("no_project_mutations_to_validate")
    if any(not check["in_range"] for check in checks):
        errors.append("mutation_position_out_of_range")
    if any(not check["wild_type_matches"] for check in checks):
        errors.append("mutation_wild_type_mismatch")

    if row.get("approved_for_numbering_audit") is not False and row.get("approved_for_numbering_audit") is not True:
        errors.append("invalid_approved_for_numbering_audit")
    if row.get("conditions") is not None and not isinstance(row.get("conditions"), list):
        errors.append("invalid_conditions")
    if row.get("residual_risks") is not None and not isinstance(row.get("residual_risks"), list):
        errors.append("invalid_residual_risks")

    if row.get("approved_for_numbering_audit") is True:
        for field in ["sequence_id", "sequence_version", "sequence_source", "reviewer", "reviewed_at", "review_basis"]:
            if missing(row.get(field)):
                errors.append(f"approval_missing_{field}")
        if row.get("residual_risks"):
            errors.append("approval_with_residual_risks")

    return errors, checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wet-lab mutant-library project sequence intake")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    project_mutations = collect_project_mutations(candidates)
    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, TEMPLATE_ROWS)

    rows = load_jsonl(args.input)
    records = []
    errors = Counter()
    seen = set()
    duplicate_ids = set()
    for row in rows:
        intake_id = str(row.get("sequence_intake_id"))
        if intake_id in seen:
            duplicate_ids.add(intake_id)
        seen.add(intake_id)
        row_errors, checks = validate(row, project_mutations)
        errors.update(row_errors)
        approved = row.get("approved_for_numbering_audit") is True and not row_errors
        records.append({
            "sequence_intake_id": row.get("sequence_intake_id"),
            "project_id": row.get("project_id"),
            "sequence_length": len(clean_sequence(row.get("sequence"))),
            "valid": not row_errors,
            "approved_for_numbering_audit": approved,
            "mutation_checks": len(checks),
            "wild_type_match_count": sum(1 for check in checks if check["wild_type_matches"]),
            "failed_mutation_checks": [check for check in checks if not check["wild_type_matches"]][:20],
            "errors": row_errors,
        })

    if duplicate_ids:
        errors.update({"duplicate_sequence_intake_id": len(duplicate_ids)})
        for record in records:
            if str(record["sequence_intake_id"]) in duplicate_ids:
                record["valid"] = False
                record["approved_for_numbering_audit"] = False
                record["errors"].append("duplicate_sequence_intake_id")

    approved_projects = sorted({record["project_id"] for record in records if record["approved_for_numbering_audit"]})
    valid_rows = sum(1 for record in records if record["valid"])
    approved_rows = sum(1 for record in records if record["approved_for_numbering_audit"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "input": str(args.input),
        "template": str(args.template),
        "project_mutation_counts": {project: len(mutations) for project, mutations in sorted(project_mutations.items())},
        "sequence_intake_rows": len(rows),
        "valid_sequence_intake_rows": valid_rows,
        "invalid_sequence_intake_rows": len(records) - valid_rows,
        "approved_sequence_rows": approved_rows,
        "approved_projects": approved_projects,
        "project_16B_ready_for_numbering_audit": "16B" in approved_projects,
        "project_4G_ready_for_numbering_audit": "4G" in approved_projects,
        "ready_to_apply_numbering_flags": False,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "error_counts": dict(errors),
        "records": records[:200],
        "policy": "Validated sequence intake only permits a later numbering audit; it does not update candidate numbering flags or training labels.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "sequence_intake_rows": report["sequence_intake_rows"],
        "approved_sequence_rows": report["approved_sequence_rows"],
        "approved_projects": report["approved_projects"],
        "ready_to_apply_numbering_flags": report["ready_to_apply_numbering_flags"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
