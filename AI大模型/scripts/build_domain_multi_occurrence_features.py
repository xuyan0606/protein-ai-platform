#!/usr/bin/env python3
"""Build safe sidecar features for repeated Pfam domain occurrences.

The existing domain interval decision schema intentionally stores one
start/end interval per domain_record_id. Repeated Pfam domains are therefore
represented here as a feature sidecar that preserves all occurrences without
pretending a single occurrence was selected.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = AI_ROOT / "datasets" / "curation" / "domain_interpro_evidence.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "domain_interval_decisions.jsonl"
OUTPUT = AI_ROOT / "datasets" / "curation" / "domain_multi_occurrence_features.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "domain_multi_occurrence_feature_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def validate_multi_occurrence(row: dict[str, Any], decided_ids: set[int]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    record_id = row.get("domain_record_id")
    if not isinstance(record_id, int):
        errors.append("invalid_domain_record_id")
    elif record_id in decided_ids:
        errors.append("already_has_single_interval_decision")

    intervals = row.get("matched_pfam_intervals") or []
    if len(intervals) <= 1:
        errors.append("not_multi_interval")

    pfam_id = row.get("pfam_id")
    seq_len = row.get("sequence_length")
    if not isinstance(seq_len, int) or seq_len <= 0:
        errors.append("invalid_sequence_length")

    normalized: list[tuple[int, int]] = []
    for interval in intervals:
        start = interval.get("start")
        end = interval.get("end")
        if interval.get("pfam_id") != pfam_id:
            errors.append("pfam_mismatch")
        if interval.get("source_database") not in {"reviewed", "unreviewed"}:
            errors.append("invalid_source_database")
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append("missing_interval_range")
            continue
        if start < 1 or end < start or (isinstance(seq_len, int) and end > seq_len):
            errors.append("invalid_interval_range")
            continue
        normalized.append((start, end))

    normalized.sort()
    for previous, current in zip(normalized, normalized[1:]):
        if current[0] <= previous[1]:
            errors.append("overlapping_intervals")
            break

    return not errors, sorted(set(errors))


def feature_for(row: dict[str, Any]) -> dict[str, Any]:
    intervals = sorted(row.get("matched_pfam_intervals") or [], key=lambda item: (item.get("start") or 0, item.get("end") or 0))
    spans = []
    covered_positions: set[int] = set()
    for index, interval in enumerate(intervals, start=1):
        start = int(interval["start"])
        end = int(interval["end"])
        covered_positions.update(range(start, end + 1))
        spans.append({
            "occurrence_index": index,
            "start_pos": start,
            "end_pos": end,
            "length": end - start + 1,
            "source_database": interval.get("source_database"),
            "dc_status": interval.get("dc_status"),
            "model": interval.get("model"),
            "score": interval.get("score"),
            "representative": bool(interval.get("representative")),
        })

    sequence_length = int(row["sequence_length"])
    return {
        "domain_record_id": int(row["domain_record_id"]),
        "uniprot_id": row.get("uniprot_id"),
        "pfam_id": row.get("pfam_id"),
        "sequence_length": sequence_length,
        "occurrence_count": len(spans),
        "total_covered_positions": len(covered_positions),
        "coverage_fraction": round(len(covered_positions) / sequence_length, 6) if sequence_length else 0,
        "occurrences": spans,
        "safe_for_position_features": True,
        "feature_policy": "multi_occurrence_sidecar; preserves all Pfam intervals; no single occurrence selection",
        "source": "InterPro/Pfam matched_pfam_intervals",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build repeated-domain occurrence sidecar features")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    evidence_rows = load_jsonl(args.evidence)
    decisions = load_jsonl(args.decisions)
    decided_ids = {int(row["domain_record_id"]) for row in decisions if row.get("domain_record_id") is not None}

    output_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    error_counts: Counter[str] = Counter()
    for row in evidence_rows:
        intervals = row.get("matched_pfam_intervals") or []
        if len(intervals) <= 1:
            continue
        valid, errors = validate_multi_occurrence(row, decided_ids)
        error_counts.update(errors)
        audit_rows.append({
            "domain_record_id": row.get("domain_record_id"),
            "uniprot_id": row.get("uniprot_id"),
            "pfam_id": row.get("pfam_id"),
            "occurrence_count": len(intervals),
            "valid": valid,
            "errors": errors,
        })
        if valid:
            output_rows.append(feature_for(row))

    output_rows.sort(key=lambda item: int(item.get("domain_record_id") or 0))
    write_jsonl(args.output, output_rows)

    occurrence_counts = Counter(row.get("occurrence_count") for row in output_rows)
    report = {
        "evidence_rows": len(evidence_rows),
        "decision_rows": len(decisions),
        "candidate_multi_occurrence_rows": len(audit_rows),
        "feature_rows": len(output_rows),
        "valid_rows": len(output_rows),
        "invalid_rows": len(audit_rows) - len(output_rows),
        "safe_for_position_features_rows": sum(1 for row in output_rows if row.get("safe_for_position_features")),
        "occurrence_count_distribution": dict(sorted(occurrence_counts.items())),
        "error_counts": dict(error_counts),
        "output": str(args.output),
        "ready_for_feature_use": bool(output_rows) and len(audit_rows) == len(output_rows),
        "safe_for_model_claim": False,
        "policy": (
            "Repeated Pfam occurrences are preserved as a sidecar feature. "
            "This does not create reviewed single-interval decisions, reviewed numbering, "
            "wet-lab feedback, ddG artifacts, or model-quality claims."
        ),
        "records": audit_rows[:200],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "feature_rows": report["feature_rows"],
        "invalid_rows": report["invalid_rows"],
        "ready_for_feature_use": report["ready_for_feature_use"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
