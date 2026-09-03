#!/usr/bin/env python3
"""Validate the P26 structure-chain formal-review gap audit."""

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
AUDIT = AI_ROOT / "datasets" / "curation" / "p26_structure_chain_formal_review_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p26_structure_chain_formal_review_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p26_structure_chain_formal_review_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    packet_report = load_json(PACKET_REPORT)
    validation = load_json(VALIDATION_REPORT)
    backlog = load_json(BACKLOG_REPORT)
    autoreview = load_json(AUTOREVIEW_REPORT)
    autoreview_draft = load_json(AUTOREVIEW_DRAFT_REPORT)
    human_backlog = load_json(HUMAN_BACKLOG)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    worklist_rows = int(validation.get("worklist_rows") or packet_report.get("input_rows") or 0)
    reviewed_rows = int(validation.get("reviewed_chain_mapping_rows") or validation.get("valid_rows") or 0)
    remaining_rows = max(worklist_rows - reviewed_rows, 0)
    packets = packet_report.get("packet_reports") or []
    expected_rows = len(packets) + 1
    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_exact", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_exact", report.get("audit_rows"), expected_rows)
    fail_if(report.get("packet_audit_rows") != len(packets), failures, "packet_audit_rows_exact", report.get("packet_audit_rows"), len(packets))
    fail_if(report.get("worklist_rows") != worklist_rows, failures, "worklist_rows_bound", report.get("worklist_rows"), worklist_rows)
    fail_if(report.get("formal_reviewed_rows") != reviewed_rows, failures, "formal_reviewed_rows_bound", report.get("formal_reviewed_rows"), reviewed_rows)
    fail_if(report.get("remaining_unreviewed_rows") != remaining_rows, failures, "remaining_rows_bound", report.get("remaining_unreviewed_rows"), remaining_rows)
    fail_if(report.get("packet_rows") != packet_report.get("packet_rows"), failures, "packet_rows_bound", report.get("packet_rows"), packet_report.get("packet_rows"))
    fail_if(report.get("strict_evidence_remaining_rows") != backlog.get("strict_evidence_remaining_rows"), failures, "strict_evidence_remaining_bound", report.get("strict_evidence_remaining_rows"), backlog.get("strict_evidence_remaining_rows"))
    fail_if(report.get("autoreview_candidate_rows") != autoreview.get("candidate_rows"), failures, "autoreview_candidates_bound", report.get("autoreview_candidate_rows"), autoreview.get("candidate_rows"))
    fail_if(report.get("autoreview_draft_rows") != autoreview_draft.get("draft_rows"), failures, "autoreview_drafts_bound", report.get("autoreview_draft_rows"), autoreview_draft.get("draft_rows"))
    fail_if(report.get("autoreview_accepted_rows") != 0, failures, "autoreview_accepted_zero", report.get("autoreview_accepted_rows"), 0)
    fail_if(report.get("autoreview_ready_for_apply") is not False, failures, "autoreview_ready_for_apply_false", report.get("autoreview_ready_for_apply"), False)
    fail_if(report.get("completion_ready") is not False, failures, "completion_ready_false", report.get("completion_ready"), False)
    human_item = next((item for item in human_backlog.get("items", []) if item.get("workstream") == "structure_chain_mapping"), {})
    fail_if(human_item.get("missing_rows") != remaining_rows, failures, "human_backlog_remaining_bound", human_item.get("missing_rows"), remaining_rows)

    packet_audit = audit_rows[:-1] if audit_rows else []
    summary = audit_rows[-1] if audit_rows else {}
    fail_if(len(packet_audit) != len(packets), failures, "packet_audit_count", len(packet_audit), len(packets))
    fail_if(summary.get("gap_type") != "structure_chain_formal_review_summary", failures, "summary_gap_type", summary.get("gap_type"), "structure_chain_formal_review_summary")
    for idx, row in enumerate(audit_rows):
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(row.get(field) is not False, failures, f"{field}_false", {"index": idx, "observed": row.get(field)}, False)
        fail_if(row.get("completion_ready") is not False, failures, "completion_ready_row_false", {"index": idx, "observed": row.get("completion_ready")}, False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "packet_audit_rows": len(packet_audit),
        "formal_reviewed_rows": reviewed_rows,
        "remaining_unreviewed_rows": remaining_rows,
        "autoreview_accepted_rows": autoreview_draft.get("accepted_rows"),
        "completion_ready": False,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Existing reviewed rows do not imply full workstream acceptance or downstream authorization.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "formal_reviewed_rows": reviewed_rows,
        "remaining_unreviewed_rows": remaining_rows,
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
