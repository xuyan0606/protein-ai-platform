#!/usr/bin/env python3
"""Build a fail-closed checklist for missing external license decisions."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKETS = AI_ROOT / "datasets" / "governance" / "external_license_review_packets.jsonl"
DECISIONS = AI_ROOT / "datasets" / "governance" / "external_license_review_decisions.jsonl"
OUT = AI_ROOT / "datasets" / "governance" / "external_license_review_missing_checklist.jsonl"
REPORT = AI_ROOT / "reports" / "external_license_review_missing_checklist_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build external license missing checklist")
    parser.add_argument("--packets", type=Path, default=PACKETS)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    packets = load_jsonl(args.packets)
    decisions = load_jsonl(args.decisions)
    decision_by_id = {str(row.get("review_item_id")): row for row in decisions if row.get("review_item_id")}
    rows: list[dict[str, Any]] = []
    for index, packet in enumerate(packets, start=1):
        review_item_id = str(packet.get("review_item_id") or "")
        decision = decision_by_id.get(review_item_id)
        authorization_status = decision.get("authorization_status") if decision else None
        verified = authorization_status == "verified"
        customer_ready = bool(decision and decision.get("approved_for_customer_delivery") and verified)
        rows.append({
            "checklist_id": f"external-license-check-{index:03d}",
            "review_item_id": review_item_id,
            "item_type": packet.get("item_type"),
            "name": packet.get("name"),
            "packet_declared_license": packet.get("declared_license"),
            "packet_commercial_status": packet.get("commercial_status"),
            "decision_present": bool(decision),
            "authorization_status": authorization_status or "missing_decision",
            "verification_required": True,
            "verified_authorization": verified,
            "approved_for_customer_delivery": customer_ready,
            "required_review_fields": packet.get("required_review_fields") or [],
            "next_human_action": "verify_existing_decision" if decision else "write_formal_license_decision",
            "formal_decision_target": "datasets/governance/external_license_review_decisions.jsonl",
            "policy": "checklist only; does not grant license clearance, customer delivery, model claim, or release readiness",
        })

    counts = Counter(row["authorization_status"] for row in rows)
    missing_rows = sum(1 for row in rows if not row["decision_present"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet_rows": len(packets),
        "decision_rows": len(decisions),
        "checklist_rows": len(rows),
        "missing_decision_rows": missing_rows,
        "self_attested_rows": counts.get("self_attested", 0),
        "verified_rows": counts.get("verified", 0),
        "approved_for_customer_delivery_rows": sum(1 for row in rows if row["approved_for_customer_delivery"]),
        "output": str(args.output),
        "ready": False,
        "policy": "Fail-closed license checklist for human/legal review only.",
    }
    write_jsonl(args.output, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "checklist_rows": report["checklist_rows"],
        "missing_decision_rows": report["missing_decision_rows"],
        "verified_rows": report["verified_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
