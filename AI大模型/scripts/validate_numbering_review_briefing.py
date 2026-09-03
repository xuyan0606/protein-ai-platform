#!/usr/bin/env python3
"""Validate the compact numbering review briefing.

The briefing is operator navigation only. This validator fails if it looks like
reviewed decisions, training labels, or model claims are being produced.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BRIEFING_JSON = AI_ROOT / "reports" / "numbering_review_briefing.json"
BRIEFING_MD = AI_ROOT / "reports" / "numbering_review_briefing.md"
PACKET_REPORT = AI_ROOT / "reports" / "numbering_review_packet_report.json"
REPORT_OUT = AI_ROOT / "reports" / "numbering_review_briefing_validation_report.json"

VALID_ACTION = "confirm_source_or_keep_unresolved_weak"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def validate_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_fields = [
        "packet_id",
        "review_rank",
        "record_id",
        "bucket",
        "uniprot_id",
        "mutation",
        "current_residue",
        "pmid",
        "title_flag",
        "review_action",
    ]
    for field in required_fields:
        if row.get(field) in (None, ""):
            errors.append(f"missing_{field}")
    if row.get("review_action") != VALID_ACTION:
        errors.append("unexpected_review_action")
    if str(row.get("title_flag") or "") not in {"title_mismatch_risk", "title_has_broad_protein_signal", "title_mentions_mutation"}:
        errors.append("unexpected_title_flag")
    forbidden_fields = {
        "decision",
        "canonical_position",
        "canonical_wild_type",
        "confidence",
        "usable_as_supervised_label",
        "safe_for_model_claim",
    }
    for field in forbidden_fields:
        if field in row:
            errors.append(f"forbidden_field_{field}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate numbering review briefing")
    parser.add_argument("--briefing-json", type=Path, default=BRIEFING_JSON)
    parser.add_argument("--briefing-md", type=Path, default=BRIEFING_MD)
    parser.add_argument("--packet-report", type=Path, default=PACKET_REPORT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    briefing = load_json(args.briefing_json)
    packet_report = load_json(args.packet_report)
    rows = briefing.get("briefing_rows") or []
    errors: list[str] = []
    expected_packet_ids = [
        packet.get("packet_id")
        for packet in packet_report.get("packet_reports") or []
        if packet.get("rows")
    ][:2]
    expected_packet_rows = {
        packet.get("packet_id"): packet.get("rows")
        for packet in packet_report.get("packet_reports") or []
        if packet.get("packet_id") in set(expected_packet_ids)
    }
    expected_rows = sum(int(value or 0) for value in expected_packet_rows.values())

    if not briefing.get("local_only"):
        errors.append("briefing_not_local_only")
    if briefing.get("briefing_packet_ids") != expected_packet_ids:
        errors.append("packet_id_order_mismatch")
    if len(rows) != expected_rows:
        errors.append("briefing_row_count_mismatch")

    packet_counts = Counter(str(row.get("packet_id") or "") for row in rows)
    if dict(packet_counts) != expected_packet_rows:
        errors.append("packet_row_counts_mismatch")

    packet_order = {packet_id: index for index, packet_id in enumerate(expected_packet_ids)}
    sort_key = [(packet_order.get(str(row.get("packet_id")), 99), int(row.get("review_rank") or 0)) for row in rows]
    if sort_key != sorted(sort_key):
        errors.append("briefing_rows_not_in_review_order")

    row_errors: list[dict[str, Any]] = []
    for row in rows:
        current = validate_row(row)
        if current:
            row_errors.append({
                "record_id": row.get("record_id"),
                "packet_id": row.get("packet_id"),
                "errors": current,
            })
            errors.extend(current)

    md_text = args.briefing_md.read_text(encoding="utf-8") if args.briefing_md.exists() else ""
    for token in [
        "not a curation decision",
        "not a supervised label source",
        "Only reviewed rows should be copied",
    ]:
        if token not in md_text:
            errors.append(f"markdown_missing_{token.replace(' ', '_')}")

    report = {
        "local_only": True,
        "briefing_json": str(args.briefing_json),
        "briefing_md": str(args.briefing_md),
        "packet_report": str(args.packet_report),
        "briefing_rows": len(rows),
        "expected_rows": expected_rows,
        "expected_packet_ids": expected_packet_ids,
        "packet_counts": dict(packet_counts),
        "valid_rows": len(rows) - len(row_errors),
        "invalid_rows": len(row_errors),
        "error_counts": dict(Counter(errors)),
        "all_rows_valid": not errors,
        "completion_ready_rows": 0,
        "ready_for_decision_write_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "row_errors": row_errors,
        "policy": "Briefing validation only; it never writes reviewed numbering decisions or supervised labels.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "briefing_rows": report["briefing_rows"],
        "valid_rows": report["valid_rows"],
        "invalid_rows": report["invalid_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if report["all_rows_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
