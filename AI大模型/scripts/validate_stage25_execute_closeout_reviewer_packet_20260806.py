#!/usr/bin/env python3
"""Validate human-readable reviewer packet for Stage 25 execute closeout items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "reports" / "stage25_execute_closeout_checklist_20260806.json"
INTAKE = AI_ROOT / "datasets" / "governance" / "stage25_execute_closeout_reviewer_intake_20260806.jsonl"
PACKET = AI_ROOT / "reports" / "stage25_execute_closeout_reviewer_packet_20260806.md"
OUTPUT = AI_ROOT / "reports" / "stage25_execute_closeout_reviewer_packet_validation_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise SystemExit(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    checklist = load_json(CHECKLIST) if CHECKLIST.exists() else {}
    intake_rows = load_jsonl(INTAKE) if INTAKE.exists() else []
    text = PACKET.read_text(encoding="utf-8") if PACKET.exists() else ""
    proposals = checklist.get("proposals") or []
    checks = sorted({str(row.get("check")) for row in intake_rows})

    fail_if(not PACKET.exists(), failures, "packet_exists", "missing", str(PACKET))
    fail_if(len(proposals) != 4, failures, "proposal_rows", len(proposals), 4)
    fail_if(len(intake_rows) != 24, failures, "checklist_rows", len(intake_rows), 24)
    fail_if(sum(1 for row in intake_rows if row.get("closed") is True) != 0, failures, "closed_rows_zero", sum(1 for row in intake_rows if row.get("closed") is True), 0)
    fail_if(sum(1 for row in intake_rows if row.get("review_decision") == "approved") != 0, failures, "approved_rows_zero", sum(1 for row in intake_rows if row.get("review_decision") == "approved"), 0)

    for proposal in proposals:
        proposal_id = str(proposal.get("proposal_id"))
        fail_if(proposal_id not in text, failures, f"{proposal_id}_present", "missing", "present")
        fail_if(str(proposal.get("doi")) not in text, failures, f"{proposal_id}_doi_present", "missing", proposal.get("doi"))
        fail_if(str(proposal.get("pmid")) not in text, failures, f"{proposal_id}_pmid_present", "missing", proposal.get("pmid"))
        fail_if(str(proposal.get("current_evidence_level")) not in text, failures, f"{proposal_id}_evidence_level_present", "missing", proposal.get("current_evidence_level"))
    for check in checks:
        fail_if(f"`{check}`" not in text, failures, f"{check}_present", "missing", "present")
    for term in (
        "needs_more_info",
        "no SQLite write",
        "no apply execution",
        "no export-safe release",
        "no model claim",
        "fulltext/source-table evidence",
        "approved_for_family_importer=false",
        "export_safe=false",
    ):
        fail_if(term not in text, failures, f"term_{term}", "missing", "present")

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_execute_closeout_reviewer_packet_validation",
        "stage": 25,
        "packet_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "proposal_rows": len(proposals),
        "checklist_rows": len(intake_rows),
        "closed_rows": sum(1 for row in intake_rows if row.get("closed") is True),
        "approved_rows": sum(1 for row in intake_rows if row.get("review_decision") == "approved"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "packet_valid": validation["packet_valid"], "failure_count": validation["failure_count"], "proposal_rows": validation["proposal_rows"], "checklist_rows": validation["checklist_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if validation["packet_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
