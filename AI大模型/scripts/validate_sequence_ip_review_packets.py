#!/usr/bin/env python3
"""Validate sequence IP/FTO review packets as fail-closed pre-decision inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET = AI_ROOT / "datasets" / "curation" / "sequence_ip_review_packets" / "sequence_ip_review_internal_labels_001.jsonl"
REPORT = AI_ROOT / "reports" / "sequence_ip_review_packet_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["review_packet_id", "candidate_id", "mutation_set", "review_decision", "allowed_use", "forbidden_use", "evidence_key"]:
        if row.get(field) is None or row.get(field) == "" or row.get(field) == []:
            errors.append(f"missing_{field}")
    if row.get("review_decision") != "manual_ip_review_required":
        errors.append("review_decision_not_manual_required")
    if row.get("ready_for_customer_delivery") is True or row.get("approved_for_customer_delivery") is True:
        errors.append("packet_contains_customer_delivery_approval")
    if not isinstance(row.get("mutation_set"), list):
        errors.append("invalid_mutation_set")
    parent_hash = row.get("parent_sequence_hash")
    parent_path = row.get("parent_sequence_path")
    hash_source = row.get("parent_sequence_hash_source")
    material_available = row.get("sequence_material_available")
    if parent_hash is None:
        if parent_path is not None or hash_source is not None or material_available is not False:
            errors.append("missing_parent_hash_has_provenance_claim")
    else:
        if not isinstance(parent_hash, str) or len(parent_hash) != 64 or any(char not in "0123456789abcdef" for char in parent_hash):
            errors.append("invalid_parent_sequence_hash")
        if hash_source != "source_receipts.parent_sequence.sha256":
            errors.append("invalid_parent_sequence_hash_source")
        if not isinstance(parent_path, str) or not parent_path or Path(parent_path).is_absolute() or ".." in Path(parent_path).parts:
            errors.append("invalid_parent_sequence_path")
        else:
            live_path = AI_ROOT / parent_path
            if not live_path.is_file():
                errors.append("parent_sequence_file_missing")
            elif isinstance(parent_hash, str) and sha256(live_path) != parent_hash:
                errors.append("parent_sequence_hash_live_mismatch")
        if material_available is not True:
            errors.append("parent_sequence_material_not_available")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate sequence IP review packets")
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.packet)
    records = []
    for row in rows:
        errors = validate(row)
        records.append({
            "candidate_id": row.get("candidate_id"),
            "review_packet_id": row.get("review_packet_id"),
            "valid": not errors,
            "errors": errors,
        })
    invalid_rows = sum(1 for row in records if not row["valid"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "packet": str(args.packet),
        "packet_rows": len(rows),
        "valid_rows": len(rows) - invalid_rows,
        "invalid_rows": invalid_rows,
        "ready_for_customer_delivery": False,
        "records": records[:200],
        "success": invalid_rows == 0 and len(rows) > 0,
        "policy": "Packet validation only. These rows are not IP/FTO decisions and do not grant customer delivery.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "packet_rows": len(rows), "invalid_rows": invalid_rows, "output": str(args.report)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
