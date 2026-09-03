#!/usr/bin/env python3
"""Validate domain interval curation decisions before applying them."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "curation" / "domain_interval_repair_queue.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "domain_interval_decisions.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "domain_interval_decision_validation_report.json"

VALID_DECISIONS = {"set_interval", "keep_unresolved", "reject_domain_hit"}
VALID_BASIS = {"hmmer_rerun", "pfam_annotation", "uniprot_feature", "manual_review", "unresolved"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(row: dict[str, Any], queue_by_id: dict[int, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    record_id = row.get("domain_record_id")
    queue_row = queue_by_id.get(record_id) if isinstance(record_id, int) else None
    if not queue_row:
        errors.append("domain_record_id_not_in_queue")
    if row.get("decision") not in VALID_DECISIONS:
        errors.append("invalid_decision")
    if row.get("basis") not in VALID_BASIS:
        errors.append("invalid_basis")
    confidence = row.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        errors.append("invalid_confidence")
    if row.get("decision") == "set_interval":
        start = row.get("start_pos")
        end = row.get("end_pos")
        seq_len = int(queue_row.get("sequence_length") or 0) if queue_row else 0
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append("missing_interval")
        elif start < 1 or end < start or (seq_len and end > seq_len):
            errors.append("invalid_interval_range")
        if isinstance(confidence, (int, float)) and float(confidence) < 0.5:
            errors.append("low_confidence_for_interval")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate domain interval curation decisions")
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    queue_rows = load_jsonl(args.queue)
    decisions = load_jsonl(args.decisions)
    queue_by_id = {row["domain_record_id"]: row for row in queue_rows if row.get("domain_record_id") is not None}
    records = []
    error_counts = Counter()
    for row in decisions:
        errors = validate(row, queue_by_id)
        error_counts.update(errors)
        records.append({"domain_record_id": row.get("domain_record_id"), "decision": row.get("decision"), "valid": not errors, "errors": errors})
    report = {
        "decision_rows": len(decisions),
        "valid_rows": sum(1 for row in records if row["valid"]),
        "invalid_rows": sum(1 for row in records if not row["valid"]),
        "error_counts": dict(error_counts),
        "records": records[:200],
        "policy": "set_interval requires valid start/end within sequence length and confidence >= 0.5",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision_rows": report["decision_rows"], "valid_rows": report["valid_rows"], "invalid_rows": report["invalid_rows"], "output": str(args.report)}, ensure_ascii=False))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
