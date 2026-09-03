#!/usr/bin/env python3
"""Build a source-bound audit of P28 experiment-feedback source-review gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET_REPORT = AI_ROOT / "reports" / "experiment_feedback_source_review_packet_report.json"
VALIDATION_REPORT = AI_ROOT / "reports" / "experiment_feedback_source_review_decision_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "feedback" / "p28_feedback_source_review_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p28_feedback_source_review_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def base(audit_id: str, gap_type: str, blocker: str, source_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Feedback source-review audit only; candidate packets and drafts are not source approval, feedback intake, training data, or delivery authorization.",
    }


def main() -> int:
    packet_report = load_json(PACKET_REPORT)
    validation = load_json(VALIDATION_REPORT)
    packets = packet_report.get("packet_reports") or []
    candidate_rows = int(validation.get("candidate_rows") or packet_report.get("input_rows") or 0)
    decision_rows = int(validation.get("decision_rows") or 0)
    valid_rows = int(validation.get("valid_rows") or 0)
    rows: list[dict[str, Any]] = []
    for packet in packets:
        packet_id = packet.get("packet_id")
        rows.append(base(
            f"p28-feedback-source-packet::{packet_id}",
            "feedback_source_review_packet",
            "source packet remains open and requires explicit human source-review decision",
            {
                "packet_id": packet_id,
                "packet_rows": packet.get("rows"),
                "candidate_rows": candidate_rows,
                "decision_rows": decision_rows,
                "valid_rows": valid_rows,
                "ready_for_feedback_extraction": False,
                "ready_for_feedback_intake": False,
            },
        ) | {"packet_id": packet_id, "packet_rows": packet.get("rows"), "completion_ready": False})
    rows.append(base(
        "p28-feedback-source-summary",
        "feedback_source_review_summary",
        "all source-review decisions remain incomplete; no source extraction or intake is authorized",
        {
            "candidate_rows": candidate_rows,
            "decision_rows": decision_rows,
            "valid_rows": valid_rows,
            "missing_source_review_rows": validation.get("missing_source_review_rows"),
            "approved_for_feedback_extraction_rows": validation.get("approved_for_feedback_extraction_rows"),
            "approved_for_feedback_intake_rows": validation.get("approved_for_feedback_intake_rows"),
            "ready_for_feedback_extraction": validation.get("ready_for_feedback_extraction"),
            "ready_for_feedback_intake": validation.get("ready_for_feedback_intake"),
        },
    ) | {"completion_ready": False})
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "packet_audit_rows": len(packets),
        "packet_count": packet_report.get("packets"),
        "packet_rows": packet_report.get("packet_rows"),
        "candidate_rows": candidate_rows,
        "decision_rows": decision_rows,
        "valid_rows": valid_rows,
        "missing_source_review_rows": validation.get("missing_source_review_rows"),
        "approved_for_feedback_extraction_rows": validation.get("approved_for_feedback_extraction_rows"),
        "approved_for_feedback_intake_rows": validation.get("approved_for_feedback_intake_rows"),
        "ready_for_feedback_extraction": False,
        "ready_for_feedback_intake": False,
        "completion_ready": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/feedback/p28_feedback_source_review_gap_audit.jsonl",
        "policy": "This audit does not approve sources or create experiment feedback rows.",
    }
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": len(rows),
        "packet_audit_rows": len(packets),
        "candidate_rows": candidate_rows,
        "decision_rows": decision_rows,
        "ready_for_feedback_intake": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
