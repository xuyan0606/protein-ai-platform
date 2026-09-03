#!/usr/bin/env python3
"""Build leakage review and split proposal for FireProt import candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_kwb_schema_mapping_candidates.jsonl"
SPLIT_OUT = AI_ROOT / "datasets" / "curation" / "fireprot_curated_import_split_proposal.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "fireprot_curated_import_leakage_review_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def split_for_group(group_key: str) -> str:
    digest = hashlib.sha256(group_key.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "validation"
    return "test"


def mutation_key(row: dict[str, Any]) -> str:
    return f"{row.get('uniprot_id')}:{row.get('mutation')}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FireProt leakage review")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--split-output", type=Path, default=SPLIT_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    strict_rows = load_jsonl(AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl")
    holdout_rows = load_jsonl(AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_strict_mutation_holdout" / "dataset.jsonl")

    strict_keys = {mutation_key(row) for row in strict_rows}
    holdout_keys = {mutation_key(row) for row in holdout_rows}
    candidate_keys = [mutation_key(row) for row in rows]
    key_counts = Counter(candidate_keys)
    duplicate_keys = {key: count for key, count in key_counts.items() if count > 1}
    group_to_split = {row.get("group_key"): split_for_group(str(row.get("group_key"))) for row in rows}
    split_rows = []
    for row in rows:
        split = group_to_split[row.get("group_key")]
        split_rows.append({
            "mapping_id": row.get("mapping_id"),
            "record_id": row.get("record_id"),
            "group_key": row.get("group_key"),
            "uniprot_id": row.get("uniprot_id"),
            "mutation": row.get("mutation"),
            "proposed_split": split,
            "split_rule": "sha256(group_key) modulo 10: 0-7 train, 8 validation, 9 test",
            "ready_for_training_import": False,
            "policy": "Split proposal only; not approved for training.",
        })

    groups_by_split: dict[str, set[str]] = defaultdict(set)
    rows_by_split: Counter[str] = Counter()
    for row in split_rows:
        groups_by_split[row["proposed_split"]].add(row["group_key"])
        rows_by_split[row["proposed_split"]] += 1
    all_group_assignments = defaultdict(set)
    for row in split_rows:
        all_group_assignments[row["group_key"]].add(row["proposed_split"])
    leaking_groups = {group: sorted(splits) for group, splits in all_group_assignments.items() if len(splits) > 1}

    strict_overlap = sorted(set(candidate_keys) & strict_keys)
    holdout_overlap = sorted(set(candidate_keys) & holdout_keys)
    passed_automated_checks = not leaking_groups and not strict_overlap and not holdout_overlap
    remaining_blockers = [
        "leakage_policy_human_approval_missing",
        "license_scope_not_selected",
        "reviewed_import_receipt_missing",
        "numbering_not_reviewed_by_kwb",
    ]
    if duplicate_keys:
        remaining_blockers.append("duplicate_mutation_keys_require_dedup_policy")

    write_jsonl(args.split_output, split_rows)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "input": str(args.input),
        "split_output": str(args.split_output),
        "candidate_rows": len(rows),
        "candidate_unique_mutation_keys": len(set(candidate_keys)),
        "duplicate_mutation_key_count": len(duplicate_keys),
        "duplicate_mutation_key_examples": dict(list(duplicate_keys.items())[:20]),
        "group_count": len(group_to_split),
        "rows_by_split": dict(rows_by_split),
        "groups_by_split": {split: len(groups) for split, groups in groups_by_split.items()},
        "group_split_leakage_count": len(leaking_groups),
        "group_split_leakage_examples": dict(list(leaking_groups.items())[:20]),
        "strict_supervised_overlap_rows": len(strict_overlap),
        "strict_supervised_overlap_examples": strict_overlap[:20],
        "kwb_strict_holdout_overlap_rows": len(holdout_overlap),
        "kwb_strict_holdout_overlap_examples": holdout_overlap[:20],
        "automated_leakage_checks_passed": passed_automated_checks,
        "leakage_policy_approved": False,
        "ready_for_training_import": False,
        "claim_eligible_rows_now": 0,
        "remaining_blockers": remaining_blockers,
        "safe_for_model_claim": False,
        "policy": "Automated leakage checks do not equal human approval. Rows remain blocked from training.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_rows": report["candidate_rows"],
        "group_count": report["group_count"],
        "automated_leakage_checks_passed": report["automated_leakage_checks_passed"],
        "duplicate_mutation_key_count": report["duplicate_mutation_key_count"],
        "ready_for_training_import": report["ready_for_training_import"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
