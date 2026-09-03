#!/usr/bin/env python3
"""Check that supervised training reads only the strict repaired table."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT_TABLE = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
REPAIRED_REPORT = AI_ROOT / "reports" / "repaired_supervised_table_report.json"
READINESS = AI_ROOT / "reports" / "training_readiness_report.json"
PROVENANCE = AI_ROOT / "reports" / "label_provenance_audit_report.json"
OUT = AI_ROOT / "reports" / "safe_training_entrypoint_check.json"


def is_truthy_marker(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return False


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check strict supervised training entrypoint")
    parser.add_argument("--strict-table", type=Path, default=STRICT_TABLE)
    parser.add_argument("--repaired-report", type=Path, default=REPAIRED_REPORT)
    parser.add_argument("--readiness", type=Path, default=READINESS)
    parser.add_argument("--provenance", type=Path, default=PROVENANCE)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--min-rows-for-claim", type=int, default=100)
    args = parser.parse_args()

    rows = load_jsonl(args.strict_table) if args.strict_table.exists() else []
    repaired_report = load_json(args.repaired_report)
    readiness = load_json(args.readiness)
    provenance = load_json(args.provenance)
    failures: list[str] = []
    warnings: list[str] = []

    for index, row in enumerate(rows, start=1):
        if row.get("usable_as_supervised_label") is not True:
            failures.append(f"row_{index}_not_usable_as_supervised_label")
        if row.get("numbering_verified_by_sequence") is not True:
            failures.append(f"row_{index}_numbering_not_verified")
        if is_truthy_marker(row.get("usable_as_weak_evidence")):
            failures.append(f"row_{index}_weak_evidence_leak")
        if row.get("integrity_flags"):
            failures.append(f"row_{index}_integrity_flags_present")
        if row.get("label_decision") not in {"go", "watch", "no_go"}:
            failures.append(f"row_{index}_invalid_label_decision")

    if repaired_report.get("supervised_rows") != len(rows):
        failures.append("repaired_report_row_count_mismatch")
    readiness_rows = readiness.get("rows", {}).get("enzyme_mutation_supervised_repaired_verified")
    if readiness_rows != len(rows):
        failures.append("readiness_row_count_mismatch")
    strict_rows = readiness.get("label_integrity", {}).get("strict_supervised_rows")
    if strict_rows != len(rows):
        failures.append("readiness_strict_supervised_rows_mismatch")
    if len(rows) < args.min_rows_for_claim:
        warnings.append("below_model_claim_row_threshold")
    if not rows:
        warnings.append("strict_table_empty_training_pipeline_blocked")
    claim_eligible_rows = provenance.get("claim_eligible_rows", 0)
    if claim_eligible_rows < args.min_rows_for_claim:
        warnings.append("below_claim_eligible_real_label_threshold")
    if provenance.get("synthetic_or_unreceipted_rows", 0):
        warnings.append("synthetic_or_unreceipted_labels_present")

    report = {
        "strict_table": str(args.strict_table),
        "rows": len(rows),
        "claim_eligible_rows": claim_eligible_rows,
        "synthetic_or_unreceipted_rows": provenance.get("synthetic_or_unreceipted_rows", 0),
        "groups": len({row.get("group_key") for row in rows}),
        "label_distribution": dict(Counter(row.get("label_decision") for row in rows)),
        "status_counts": dict(Counter(row.get("curation_status") for row in rows)),
        "failures": failures,
        "warnings": warnings,
        "no_leakage_guard_passed": not failures,
        "training_pipeline_unlocked": not failures and len(rows) >= args.min_rows_for_claim,
        "safe_for_training_pipeline": not failures and len(rows) >= args.min_rows_for_claim,
        "safe_for_model_claim": not failures and claim_eligible_rows >= args.min_rows_for_claim,
        "policy": "strict table must contain only verified supervised labels; training/model claims require enough rows and non-synthetic claim-eligible label provenance. Empty strict tables are leakage-safe but training-blocked.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows": report["rows"],
        "failures": len(failures),
        "warnings": warnings,
        "no_leakage_guard_passed": report["no_leakage_guard_passed"],
        "training_pipeline_unlocked": report["training_pipeline_unlocked"],
        "safe_for_training_pipeline": report["safe_for_training_pipeline"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
