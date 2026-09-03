#!/usr/bin/env python3
"""Audit local sequence evidence for wet-lab mutant-library numbering gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = AI_ROOT.parent
CANDIDATES = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_candidates.jsonl"
OUTPUT = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_sequence_evidence_audit.jsonl"
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_sequence_evidence_audit_report.json"

AA_RE = re.compile(r"[ACDEFGHIKLMNPQRSTVWY]{20,}")
MUTATION_RE = re.compile(r"^([A-Z])([0-9]+)([A-Z])$")


SEQUENCE_SOURCE_CANDIDATES = [
    {
        "source_id": "venus15b_user_confirmed_sequence",
        "project_hint": "15B",
        "path": AI_ROOT / "Venus-15B淀粉酶项目" / "淀粉酶15B序列.txt",
        "source_type": "user_confirmed_project_sequence",
    },
    {
        "source_id": "backend_upload_55c614a471014f4da1372b081a0b6b77",
        "project_hint": None,
        "path": PLATFORM_ROOT / "backend" / "storage" / "uploads" / "55c614a471014f4da1372b081a0b6b77.fasta",
        "source_type": "unreviewed_upload_fasta",
    },
    {
        "source_id": "backend_upload_c6b7fa18cdc143688a5bfe95c91ef9f2",
        "project_hint": None,
        "path": PLATFORM_ROOT / "backend" / "storage" / "uploads" / "c6b7fa18cdc143688a5bfe95c91ef9f2.fasta",
        "source_type": "unreviewed_upload_fasta",
    },
    {
        "source_id": "matvenus_session_12_review_sequence",
        "project_hint": None,
        "path": PLATFORM_ROOT / "matvenus-research" / "reviews" / "12-咨询给定序列酶的改造以提升比活力的方案-065e88f7.review.md",
        "source_type": "historical_session_sequence_candidate",
    },
    {
        "source_id": "matvenus_session_12_raw_sequence",
        "project_hint": None,
        "path": PLATFORM_ROOT / "matvenus-research" / "raw" / "12-咨询给定序列酶的改造以提升比活力的方案-065e88f7.stream-events.json",
        "source_type": "historical_session_sequence_candidate",
    },
]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def extract_sequences(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".fa", ".faa", ".fasta"}:
        body = "\n".join(line.strip() for line in text.splitlines() if line.strip() and not line.startswith(">"))
        seq = "".join(re.findall(r"[ACDEFGHIKLMNPQRSTVWY]+", body.upper()))
        return [seq] if seq else []
    return sorted(set(match.group(0) for match in AA_RE.finditer(text.upper())), key=lambda seq: (-len(seq), seq))


def collect_project_mutations(candidates: list[dict[str, Any]]) -> dict[str, list[str]]:
    project_mutations: dict[str, set[str]] = defaultdict(set)
    for row in candidates:
        project = str(row.get("source_project") or "")
        for mutation in row.get("mutation_set") or []:
            if MUTATION_RE.match(str(mutation)):
                project_mutations[project].add(str(mutation))
    return {project: sorted(mutations, key=lambda m: (int(MUTATION_RE.match(m).group(2)), m)) for project, mutations in project_mutations.items()}


def evaluate_sequence(seq: str, mutations: list[str]) -> dict[str, Any]:
    checks = []
    for mutation in mutations:
        match = MUTATION_RE.match(mutation)
        if not match:
            continue
        wt, pos_text, mutant = match.groups()
        pos = int(pos_text)
        observed = seq[pos - 1] if 1 <= pos <= len(seq) else None
        checks.append({
            "mutation": mutation,
            "reported_wild_type": wt,
            "position": pos,
            "reported_mutant": mutant,
            "observed_residue": observed,
            "in_range": observed is not None,
            "wild_type_matches": observed == wt,
        })
    total = len(checks)
    in_range = sum(1 for check in checks if check["in_range"])
    matches = sum(1 for check in checks if check["wild_type_matches"])
    return {
        "mutation_count": total,
        "in_range_mutation_count": in_range,
        "wild_type_match_count": matches,
        "wild_type_mismatch_count": total - matches,
        "wild_type_match_fraction": (matches / total) if total else 0.0,
        "checks": checks,
    }


def decision_for(source: dict[str, Any], project: str, seq: str, evaluation: dict[str, Any]) -> tuple[str, list[str]]:
    reasons = []
    source_type = source["source_type"]
    source_hint = source.get("project_hint")
    match_count = evaluation["wild_type_match_count"]
    mutation_count = evaluation["mutation_count"]
    if len(seq) < 50:
        return "rejected", ["sequence_too_short_for_parent_numbering"]
    if mutation_count == 0:
        return "rejected", ["no_project_mutations_to_test"]
    if match_count != mutation_count:
        reasons.append("not_all_project_mutation_wild_types_match")
    if source_hint and source_hint != project:
        reasons.append("source_project_hint_does_not_match_project")
    if source_type != "user_confirmed_project_sequence":
        reasons.append("source_not_user_confirmed_project_sequence")
    if not reasons:
        return "accepted_for_numbering_evidence", []
    return "manual_review_or_rejected", reasons


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local sequence evidence for wet-lab mutant library")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    project_mutations = collect_project_mutations(candidates)
    rows: list[dict[str, Any]] = []
    counts = Counter()
    for source in SEQUENCE_SOURCE_CANDIDATES:
        path = source["path"]
        sequences = extract_sequences(path)
        counts["source_rows"] += 1
        if not sequences:
            rows.append({
                "sequence_evidence_id": f"{source['source_id']}:missing_or_no_sequence",
                "source_id": source["source_id"],
                "source_type": source["source_type"],
                "source_project_hint": source.get("project_hint"),
                "source_path": str(path.relative_to(AI_ROOT)) if path.is_relative_to(AI_ROOT) else str(path),
                "source_exists": path.exists(),
                "sequence_index": None,
                "sequence_length": 0,
                "sequence_sha256": None,
                "project_id": None,
                "decision": "rejected",
                "blockers": ["missing_or_no_extractable_sequence"],
                "policy": "Sequence evidence audit only; does not update numbering_verified flags.",
            })
            counts["rejected_rows"] += 1
            continue
        for seq_index, seq in enumerate(sequences[:5], start=1):
            for project, mutations in sorted(project_mutations.items()):
                evaluation = evaluate_sequence(seq, mutations)
                decision, blockers = decision_for(source, project, seq, evaluation)
                rows.append({
                    "sequence_evidence_id": f"{source['source_id']}:{seq_index}:{project}",
                    "source_id": source["source_id"],
                    "source_type": source["source_type"],
                    "source_project_hint": source.get("project_hint"),
                    "source_path": str(path.relative_to(AI_ROOT)) if path.is_relative_to(AI_ROOT) else str(path),
                    "source_exists": path.exists(),
                    "sequence_index": seq_index,
                    "sequence_length": len(seq),
                    "sequence_sha256": sha256_text(seq),
                    "project_id": project,
                    "mutation_count": evaluation["mutation_count"],
                    "in_range_mutation_count": evaluation["in_range_mutation_count"],
                    "wild_type_match_count": evaluation["wild_type_match_count"],
                    "wild_type_mismatch_count": evaluation["wild_type_mismatch_count"],
                    "wild_type_match_fraction": evaluation["wild_type_match_fraction"],
                    "failed_mutation_checks": [
                        check for check in evaluation["checks"] if not check["wild_type_matches"]
                    ][:20],
                    "decision": decision,
                    "blockers": blockers,
                    "policy": "Sequence evidence audit only; does not update numbering_verified flags.",
                })
                counts[f"decision_{decision}_rows"] += 1
                if decision == "accepted_for_numbering_evidence":
                    counts[f"project_{project}_accepted_sequence_evidence_rows"] += 1
                else:
                    counts["non_accepted_rows"] += 1

    write_jsonl(args.output, rows)
    accepted_projects = sorted({
        row["project_id"]
        for row in rows
        if row.get("decision") == "accepted_for_numbering_evidence"
    })
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidates": str(args.candidates),
        "output": str(args.output),
        "source_candidate_rows": len(SEQUENCE_SOURCE_CANDIDATES),
        "sequence_evidence_rows": len(rows),
        "project_mutation_counts": {project: len(mutations) for project, mutations in sorted(project_mutations.items())},
        "accepted_projects": accepted_projects,
        "accepted_sequence_evidence_rows": counts.get("decision_accepted_for_numbering_evidence_rows", 0),
        "project_15B_accepted_sequence_evidence_rows": counts.get("project_15B_accepted_sequence_evidence_rows", 0),
        "project_16B_accepted_sequence_evidence_rows": counts.get("project_16B_accepted_sequence_evidence_rows", 0),
        "project_4G_accepted_sequence_evidence_rows": counts.get("project_4G_accepted_sequence_evidence_rows", 0),
        "ready_to_update_numbering_flags": False,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "counts": dict(counts),
        "policy": "Only user-confirmed project sequence with all project mutation wild-type residues matching can be accepted as numbering evidence; applying numbering flags requires a separate reviewed apply gate.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "sequence_evidence_rows": report["sequence_evidence_rows"],
        "accepted_projects": report["accepted_projects"],
        "accepted_sequence_evidence_rows": report["accepted_sequence_evidence_rows"],
        "ready_to_update_numbering_flags": report["ready_to_update_numbering_flags"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
