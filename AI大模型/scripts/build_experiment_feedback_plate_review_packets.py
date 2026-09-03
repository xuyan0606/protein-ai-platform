#!/usr/bin/env python3
"""Build plate-level feedback review packets from candidate feedback sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPORT = AI_ROOT / "reports" / "experiment_feedback_source_review_packet_report.json"
OUT_DIR = AI_ROOT / "datasets" / "feedback" / "plate_review_packets"
DRAFT_DIR = AI_ROOT / "datasets" / "feedback" / "plate_review_drafts"
REPORT_OUT = AI_ROOT / "reports" / "experiment_feedback_plate_review_packet_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def draft_for(row: dict[str, Any], packet_id: str) -> dict[str, Any]:
    return {
        "packet_id": packet_id,
        "source_path": row.get("relative_path"),
        "plate_id": None,
        "well_id": None,
        "variant_id": None,
        "sample_batch": None,
        "assay_type": None,
        "substrate_smiles": None,
        "temperature_c": None,
        "ph": None,
        "replicate": None,
        "raw_signal": None,
        "normalized_activity": None,
        "qc_flag": "not_reviewed",
        "instrument": None,
        "protocol_version": None,
        "operator": None,
        "raw_data_uri": None,
        "review_status": "draft",
        "approved_for_plate_intake": False,
        "required_checks": [
            "confirm source is a genuine KWB wet-lab or historical experimental result",
            "extract one row per plate/well/replicate",
            "preserve failed and inconclusive outcomes when genuine",
            "verify mutation numbering before training eligibility",
        ],
        "policy": "draft only; not schema-valid feedback until reviewed and completed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build plate-level feedback review packets")
    parser.add_argument("--source-report", type=Path, default=SOURCE_REPORT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--draft-dir", type=Path, default=DRAFT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    source_report = load_json(args.source_report)
    priority_packets = [
        item for item in source_report.get("packet_reports", [])
        if item.get("bucket") in {"historical_feedback_candidate", "historical_session_candidate", "manual_feedback_triage"}
    ]
    packet_rows: list[dict[str, Any]] = []
    draft_rows: list[dict[str, Any]] = []
    for packet in priority_packets:
        packet_id = str(packet.get("packet_id"))
        rows = load_jsonl(Path(str(packet.get("jsonl"))))
        for row in rows:
            packet_rows.append({
                "packet_id": "plate_" + packet_id,
                "source_packet_id": packet_id,
                "source_path": row.get("relative_path"),
                "source_review_bucket": row.get("source_review_bucket"),
                "candidate_score": row.get("candidate_score"),
                "keyword_hits": row.get("keyword_hits"),
                "target_schema": "contracts/experiment_feedback_plate.schema.json",
                "plate_feedback_status": "needs_manual_extraction",
                "approved_for_plate_intake": False,
                "policy": "source-to-plate review only; not feedback data",
            })
            draft_rows.append(draft_for(row, "plate_" + packet_id))
    packet_path = args.out_dir / "feedback_plate_review_priority_001.jsonl"
    draft_path = args.draft_dir / "feedback_plate_review_priority_001.plate_feedback.draft.jsonl"
    write_jsonl(packet_path, packet_rows)
    write_jsonl(draft_path, draft_rows)
    report = {
        "source_packets_considered": len(priority_packets),
        "plate_review_packet_rows": len(packet_rows),
        "plate_feedback_draft_rows": len(draft_rows),
        "approved_for_plate_intake_rows": 0,
        "training_eligible_rows": 0,
        "packet_file": str(packet_path),
        "draft_file": str(draft_path),
        "ready_for_feedback_intake": False,
        "policy": "plate review packets start P28 work but cannot become training rows without manual source extraction and schema validation",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"plate_review_packet_rows": len(packet_rows), "ready_for_feedback_intake": False, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
