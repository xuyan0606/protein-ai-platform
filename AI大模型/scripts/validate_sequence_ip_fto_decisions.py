#!/usr/bin/env python3
"""Validate human IP/FTO review decisions for sequence candidates fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET_DIR = AI_ROOT / "datasets" / "curation" / "sequence_ip_review_packets"
INPUT = AI_ROOT / "datasets" / "governance" / "sequence_ip_fto_decisions.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "governance" / "sequence_ip_fto_decisions.template.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json"

VALID_DECISIONS = {"cleared", "cleared_with_conditions", "blocked", "needs_more_info"}

TEMPLATE_ROW = {
    "review_packet_id": "sequence_ip_review_internal_labels_001",
    "candidate_id": "stability:34",
    "fto_decision": "needs_more_info",
    "reviewer": "human-ip-fto-reviewer",
    "reviewed_at": "2026-07-27T00:00:00+08:00",
    "review_basis": "template only; replace with reviewed prior-art/legal evidence",
    "prior_art_evidence": [],
    "jurisdictions": ["not_selected"],
    "approved_for_internal_use": False,
    "approved_for_customer_delivery": False,
    "conditions": [],
    "prohibited_uses": ["customer delivery until FTO review is complete"],
    "notes": "template only; this is not an FTO conclusion",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def missing(value: Any) -> bool:
    return value is None or value == ""


def packet_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("review_packet_id")), str(row.get("candidate_id")))


def validate(row: dict[str, Any], packet_keys: set[tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    for field in [
        "review_packet_id",
        "candidate_id",
        "fto_decision",
        "reviewer",
        "reviewed_at",
        "review_basis",
        "prior_art_evidence",
        "jurisdictions",
        "approved_for_internal_use",
        "approved_for_customer_delivery",
        "conditions",
        "prohibited_uses",
    ]:
        if field not in row or missing(row.get(field)):
            errors.append(f"missing_{field}")
    if packet_key(row) not in packet_keys:
        errors.append("unknown_packet_candidate")
    if row.get("fto_decision") not in VALID_DECISIONS:
        errors.append("invalid_fto_decision")
    for field in ["approved_for_internal_use", "approved_for_customer_delivery"]:
        if not isinstance(row.get(field), bool):
            errors.append(f"invalid_{field}")
    for field in ["prior_art_evidence", "jurisdictions", "conditions", "prohibited_uses"]:
        if not isinstance(row.get(field), list):
            errors.append(f"invalid_{field}")
    if row.get("fto_decision") == "cleared_with_conditions" and not row.get("conditions"):
        errors.append("cleared_with_conditions_missing_conditions")
    if row.get("approved_for_customer_delivery") and row.get("fto_decision") not in {"cleared", "cleared_with_conditions"}:
        errors.append("customer_delivery_without_cleared_decision")
    if row.get("approved_for_customer_delivery") and not row.get("prior_art_evidence"):
        errors.append("customer_delivery_without_prior_art_evidence")
    if row.get("approved_for_customer_delivery") and not row.get("jurisdictions"):
        errors.append("customer_delivery_without_jurisdictions")
    if row.get("fto_decision") == "blocked" and (row.get("approved_for_internal_use") or row.get("approved_for_customer_delivery")):
        errors.append("blocked_decision_with_approval")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate sequence IP/FTO review decisions")
    parser.add_argument("--packet-dir", type=Path, default=PACKET_DIR)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, [TEMPLATE_ROW])

    packet_rows: list[dict[str, Any]] = []
    if args.packet_dir.exists():
        for path in sorted(args.packet_dir.glob("*.jsonl")):
            packet_rows.extend(load_jsonl(path))
    decisions = load_jsonl(args.input)
    packet_keys = {packet_key(row) for row in packet_rows}
    records = []
    errors = Counter()
    seen = set()
    duplicates = set()
    for row in decisions:
        key = packet_key(row)
        if key in seen:
            duplicates.add(key)
        seen.add(key)
        row_errors = validate(row, packet_keys)
        errors.update(row_errors)
        records.append({
            "review_packet_id": row.get("review_packet_id"),
            "candidate_id": row.get("candidate_id"),
            "fto_decision": row.get("fto_decision"),
            "valid": not row_errors,
            "approved_for_internal_use": bool(row.get("approved_for_internal_use")) and not row_errors,
            "approved_for_customer_delivery": bool(row.get("approved_for_customer_delivery")) and not row_errors,
            "errors": row_errors,
        })
    if duplicates:
        errors.update({"duplicate_packet_candidate": len(duplicates)})
        for record in records:
            key = (str(record["review_packet_id"]), str(record["candidate_id"]))
            if key in duplicates:
                record["valid"] = False
                record["approved_for_internal_use"] = False
                record["approved_for_customer_delivery"] = False
                record["errors"].append("duplicate_packet_candidate")

    valid_rows = sum(1 for item in records if item["valid"])
    internal_approved = sum(1 for item in records if item["approved_for_internal_use"])
    delivery_approved = sum(1 for item in records if item["approved_for_customer_delivery"])
    approved_delivery_keys = {
        (str(item["review_packet_id"]), str(item["candidate_id"]))
        for item in records
        if item["approved_for_customer_delivery"]
    }
    missing_delivery_decisions = sorted(
        f"{packet_id}:{candidate_id}" for packet_id, candidate_id in packet_keys - approved_delivery_keys
    )
    report = {
        "local_only": True,
        "input": str(args.input),
        "template": str(args.template),
        "packet_rows": len(packet_rows),
        "decision_rows": len(decisions),
        "valid_rows": valid_rows,
        "invalid_rows": len(records) - valid_rows,
        "approved_for_internal_use_rows": internal_approved,
        "approved_for_customer_delivery_rows": delivery_approved,
        "all_packet_candidates_decided_for_delivery": delivery_approved == len(packet_rows) and bool(packet_rows) and not errors,
        "missing_delivery_decisions": missing_delivery_decisions[:100],
        "ready_for_customer_delivery": delivery_approved == len(packet_rows) and bool(packet_rows) and not errors,
        "error_counts": dict(errors),
        "records": records[:200],
        "policy": "IP/FTO readiness requires explicit human/legal decisions; review packets are not clearance.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": len(decisions),
        "valid_rows": valid_rows,
        "approved_for_customer_delivery_rows": delivery_approved,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
