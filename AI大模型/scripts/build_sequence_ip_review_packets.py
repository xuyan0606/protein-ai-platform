#!/usr/bin/env python3
"""Build fail-closed sequence IP/FTO review packets for candidate-facing rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
FALLBACK_INPUT = AI_ROOT / "datasets" / "curation" / "kwb_venus15b_strict_holdout_review_packets.jsonl"
PACKET_DIR = AI_ROOT / "datasets" / "curation" / "sequence_ip_review_packets"
REPORT_OUT = AI_ROOT / "reports" / "sequence_ip_review_packet_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def candidate_key(row: dict[str, Any]) -> str:
    return "|".join(str(row.get(key) or "") for key in ("uniprot_id", "mutation", "variant", "record_id", "packet_id", "literature_ref"))


def packet_row(row: dict[str, Any]) -> dict[str, Any]:
    key = candidate_key(row)
    mutation = row.get("mutation") or row.get("variant")
    source_receipts = row.get("source_receipts") if isinstance(row.get("source_receipts"), dict) else {}
    parent_sequence = source_receipts.get("parent_sequence") if isinstance(source_receipts.get("parent_sequence"), dict) else {}
    parent_sequence_hash = parent_sequence.get("sha256")
    parent_sequence_path = parent_sequence.get("path")
    return {
        "review_packet_id": "sequence_ip_review_internal_labels_001",
        "candidate_id": row.get("record_id") or row.get("packet_id") or row.get("review_key"),
        "sequence_hash": None,
        "parent_sequence_hash": parent_sequence_hash,
        "parent_sequence_path": parent_sequence_path,
        "parent_sequence_hash_source": "source_receipts.parent_sequence.sha256" if parent_sequence_hash else None,
        "sequence_material_available": bool(parent_sequence_hash and parent_sequence_path),
        "mutation_set": [mutation] if mutation else [],
        "source_model": "KWB-EnzymeDesigner",
        "source_tool": "strict_repaired_supervised_table",
        "prior_art_source": "not_searched",
        "hit_id": None,
        "identity": None,
        "coverage": None,
        "jurisdiction": "not_selected",
        "legal_status": "not_reviewed",
        "claim_relevance": "not_reviewed",
        "review_decision": "manual_ip_review_required",
        "allowed_use": "internal IP/FTO triage packet only",
        "forbidden_use": "no freedom-to-operate conclusion and no customer delivery approval",
        "evidence_key": hashlib.sha256(key.encode("utf-8")).hexdigest(),
        "source_record": {
            "uniprot_id": row.get("uniprot_id"),
            "mutation": mutation,
            "label_source_db": row.get("label_source_db"),
            "literature_ref": row.get("literature_ref"),
            "source_packet_id": row.get("packet_id"),
            "review_key": row.get("review_key"),
            "project_id": row.get("project_id"),
            "source_receipts": source_receipts,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build sequence IP review packets")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--packet-dir", type=Path, default=PACKET_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    input_path = args.input
    rows = load_jsonl(input_path)
    fallback_used = False
    if input_path == INPUT and not rows:
        input_path = FALLBACK_INPUT
        rows = load_jsonl(input_path)
        fallback_used = bool(rows)
    review_rows = [packet_row(row) for row in rows]
    packet_path = args.packet_dir / "sequence_ip_review_internal_labels_001.jsonl"
    write_jsonl(packet_path, review_rows)
    report = {
        "local_only": True,
        "input": str(input_path),
        "default_input": str(args.input),
        "fallback_input": str(FALLBACK_INPUT),
        "fallback_used": fallback_used,
        "packets": 1,
        "packet_rows": len(review_rows),
        "packet_files": [str(packet_path)],
        "reviewed_fto_rows": 0,
        "ready_for_customer_delivery": False,
        "blockers": [
            "sequence-level prior-art search is not performed locally",
            "no human IP/FTO decision is present",
            "candidate sequence hashes are not customer-delivery artifacts",
        ],
        "policy": "Packets support legal review; they do not provide FTO conclusions.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"packet_rows": len(review_rows), "reviewed_fto_rows": 0, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
