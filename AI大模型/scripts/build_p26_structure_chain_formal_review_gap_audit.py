#!/usr/bin/env python3
"""Build a source-bound audit of P26 structure-chain formal-review gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PACKET_REPORT = AI_ROOT / "reports" / "structure_chain_review_packet_report.json"
VALIDATION_REPORT = AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json"
BACKLOG_REPORT = AI_ROOT / "reports" / "structure_chain_mapping_backlog_readiness_report.json"
AUTOREVIEW_REPORT = AI_ROOT / "reports" / "structure_chain_autoreview_candidate_report.json"
AUTOREVIEW_DRAFT_REPORT = AI_ROOT / "reports" / "structure_chain_autoreview_decision_draft_report.json"
HUMAN_BACKLOG = AI_ROOT / "reports" / "human_decision_backlog_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "curation" / "p26_structure_chain_formal_review_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p26_structure_chain_formal_review_gap_audit_report.json"


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
        "policy": "Structure-chain packet/backlog audit only; no new reviewed decision, coordinate claim, training label, release, or production approval is created.",
    }


def main() -> int:
    packet_report = load_json(PACKET_REPORT)
    validation = load_json(VALIDATION_REPORT)
    backlog = load_json(BACKLOG_REPORT)
    autoreview = load_json(AUTOREVIEW_REPORT)
    autoreview_draft = load_json(AUTOREVIEW_DRAFT_REPORT)
    human_backlog = load_json(HUMAN_BACKLOG)
    worklist_rows = int(validation.get("worklist_rows") or packet_report.get("input_rows") or 0)
    reviewed_rows = int(validation.get("reviewed_chain_mapping_rows") or validation.get("valid_rows") or 0)
    remaining_rows = max(worklist_rows - reviewed_rows, 0)
    packet_rows = int(packet_report.get("packets") or 0)
    rows: list[dict[str, Any]] = []

    for packet in packet_report.get("packet_reports") or []:
        packet_id = packet.get("packet_id")
        rows.append(base(
            f"p26-structure-chain-packet::{packet_id}",
            "structure_chain_review_packet",
            "packet remains open and requires formal human chain/numbering review",
            {
                "packet_id": packet_id,
                "packet_rows": packet.get("rows"),
                "packet_report_rows": packet_report.get("packet_rows"),
                "decision_rows_existing": reviewed_rows,
                "remaining_unreviewed_rows": remaining_rows,
                "completion_ready": False,
                "autoreview_accepted_rows": autoreview_draft.get("accepted_rows", 0),
            },
        ) | {
            "packet_id": packet_id,
            "packet_rows": packet.get("rows"),
            "completion_ready": False,
        })

    summary_state = {
        "worklist_rows": worklist_rows,
        "reviewed_chain_mapping_rows": reviewed_rows,
        "remaining_unreviewed_rows": remaining_rows,
        "strict_evidence_remaining_rows": backlog.get("strict_evidence_remaining_rows"),
        "packet_count": packet_rows,
        "packet_rows": packet_report.get("packet_rows"),
        "autoreview_candidate_rows": autoreview.get("candidate_rows"),
        "autoreview_draft_rows": autoreview_draft.get("draft_rows"),
        "autoreview_accepted_rows": autoreview_draft.get("accepted_rows"),
        "autoreview_ready_for_apply": autoreview_draft.get("ready_for_apply"),
        "human_backlog_structure_chain_missing_rows": next(
            (item.get("missing_rows") for item in human_backlog.get("items", [])
             if item.get("workstream") == "structure_chain_mapping"),
            None,
        ),
        "completion_ready": False,
    }
    rows.append(base(
        "p26-structure-chain-summary",
        "structure_chain_formal_review_summary",
        "structure-chain review is partially complete but remaining rows and unaccepted auto-review drafts block completion",
        summary_state,
    ) | {
        "completion_ready": False,
        "formal_reviewed_rows": reviewed_rows,
        "remaining_unreviewed_rows": remaining_rows,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "packet_audit_rows": len(packet_report.get("packet_reports") or []),
        "packet_count": packet_rows,
        "packet_rows": packet_report.get("packet_rows"),
        "worklist_rows": worklist_rows,
        "formal_reviewed_rows": reviewed_rows,
        "remaining_unreviewed_rows": remaining_rows,
        "strict_evidence_remaining_rows": backlog.get("strict_evidence_remaining_rows"),
        "autoreview_candidate_rows": autoreview.get("candidate_rows"),
        "autoreview_draft_rows": autoreview_draft.get("draft_rows"),
        "autoreview_accepted_rows": autoreview_draft.get("accepted_rows"),
        "autoreview_ready_for_apply": autoreview_draft.get("ready_for_apply"),
        "completion_ready": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/curation/p26_structure_chain_formal_review_gap_audit.jsonl",
        "policy": "This audit records partial reviewed progress and remaining human review gaps. It does not create or apply structure-chain decisions.",
    }
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": len(rows),
        "packet_audit_rows": report["packet_audit_rows"],
        "formal_reviewed_rows": reviewed_rows,
        "remaining_unreviewed_rows": remaining_rows,
        "autoreview_accepted_rows": report["autoreview_accepted_rows"],
        "completion_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
