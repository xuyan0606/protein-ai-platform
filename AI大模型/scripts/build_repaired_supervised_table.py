#!/usr/bin/env python3
"""Build a strict supervised table from repaired curation output."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_repaired.jsonl"
DEEP_AUDIT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_all_stability_records.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "repaired_supervised_table_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def source_rejected_by_deep_audit(row: dict[str, Any], deep_audit_by_record: dict[str, dict[str, Any]]) -> bool:
    audit = deep_audit_by_record.get(str(row.get("record_id") or ""))
    if not audit:
        return False
    source_flags = set(audit.get("source_lineage_flags") or [])
    return (
        audit.get("audit_recommended_decision") == "reject_label"
        and bool(source_flags & {
            "synthetic_generator_fingerprint_prothermdb_pmid_310xxxxx",
            "sample_fixture_literal_pmid",
        })
    )


def is_strong_supervised(row: dict[str, Any]) -> bool:
    return (
        row.get("usable_as_supervised_label") is True
        and row.get("numbering_verified_by_sequence") is True
        and row.get("label_decision") in {"go", "watch", "no_go"}
        and not row.get("integrity_flags")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build strict repaired supervised table")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--deep-audit", type=Path, default=DEEP_AUDIT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    deep_audit_rows = load_jsonl(args.deep_audit)
    deep_audit_by_record = {str(row.get("record_id")): row for row in deep_audit_rows if row.get("record_id")}
    supervised = [
        row
        for row in rows
        if is_strong_supervised(row) and not source_rejected_by_deep_audit(row, deep_audit_by_record)
    ]
    excluded = [row for row in rows if row not in supervised]
    write_jsonl(args.output, supervised)

    excluded_reasons = Counter()
    for row in excluded:
        if not row.get("usable_as_supervised_label"):
            excluded_reasons["not_usable_as_supervised_label"] += 1
        elif not row.get("numbering_verified_by_sequence"):
            excluded_reasons["numbering_not_verified"] += 1
        elif row.get("label_decision") not in {"go", "watch", "no_go"}:
            excluded_reasons["invalid_label_decision"] += 1
        elif row.get("integrity_flags"):
            excluded_reasons["integrity_flags_present"] += 1
        elif source_rejected_by_deep_audit(row, deep_audit_by_record):
            excluded_reasons["source_rejected_by_deep_audit"] += 1
        else:
            excluded_reasons["other"] += 1

    report = {
        "input_rows": len(rows),
        "supervised_rows": len(supervised),
        "excluded_rows": len(excluded),
        "deep_audit_rows": len(deep_audit_rows),
        "source_rejected_by_deep_audit_rows": excluded_reasons.get("source_rejected_by_deep_audit", 0),
        "excluded_reasons": dict(excluded_reasons),
        "groups": len({row.get("group_key") for row in supervised}),
        "label_distribution": dict(Counter(row["label_decision"] for row in supervised)),
        "status_counts": dict(Counter(row.get("curation_status") for row in supervised)),
        "output": str(args.output),
        "policy": "training scripts should use this strict table, not the full repaired table",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "input_rows": len(rows),
        "supervised_rows": len(supervised),
        "excluded_rows": len(excluded),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
