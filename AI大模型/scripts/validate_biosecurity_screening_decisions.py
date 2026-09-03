#!/usr/bin/env python3
"""Validate human biosecurity screening decisions fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DRAFTS = AI_ROOT / "datasets" / "governance" / "biosecurity_screening_drafts.jsonl"
INPUT = AI_ROOT / "datasets" / "governance" / "biosecurity_screening_decisions.jsonl"
TEMPLATE = AI_ROOT / "datasets" / "governance" / "biosecurity_screening_decisions.template.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json"

VALID_STATES = {
    "screening_required",
    "screening_pending",
    "screening_denied",
    "screening_granted",
    "manual_exemption_required",
    "approved_for_ordering",
}
VALID_PERMISSIONS = {"pending", "denied", "granted", "not_applicable"}
VALID_PROJECT_APPROVALS = {"approved", "denied", "pending", "not_applicable"}
VALID_REVIEW = {"approved", "rejected", "needs_more_info"}

TEMPLATE_ROW = {
    "screening_request_id": "screening:stability:34",
    "candidate_id": "stability:34",
    "screening_state": "screening_pending",
    "synthesis_permission": "pending",
    "screening_provider": "screening-provider-or-internal-policy",
    "screening_reference": "screening-report-id-or-policy-reference",
    "customer_or_project_approval": "pending",
    "intended_use_statement": "internal enzyme design research",
    "human_reviewer_decision": "needs_more_info",
    "reviewer": "human-biosecurity-reviewer",
    "reviewed_at": "2026-07-27T00:00:00+08:00",
    "approved_for_ordering": False,
    "conditions": [],
    "order_ready_payload_uri": None,
    "notes": "template only; copy to the local decisions file after screening and human review",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def validate(row: dict[str, Any], draft_by_id: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for field in [
        "screening_request_id",
        "candidate_id",
        "screening_state",
        "synthesis_permission",
        "screening_provider",
        "screening_reference",
        "customer_or_project_approval",
        "intended_use_statement",
        "human_reviewer_decision",
        "reviewer",
        "reviewed_at",
        "approved_for_ordering",
    ]:
        if field not in row or row.get(field) in {None, ""}:
            errors.append(f"missing_{field}")
    request_id = str(row.get("screening_request_id"))
    draft = draft_by_id.get(request_id)
    if not draft:
        errors.append("unknown_screening_request_id")
    elif row.get("candidate_id") != draft.get("candidate_id"):
        errors.append("candidate_id_mismatch")
    if row.get("screening_state") not in VALID_STATES:
        errors.append("invalid_screening_state")
    if row.get("synthesis_permission") not in VALID_PERMISSIONS:
        errors.append("invalid_synthesis_permission")
    if row.get("customer_or_project_approval") not in VALID_PROJECT_APPROVALS:
        errors.append("invalid_customer_or_project_approval")
    if row.get("human_reviewer_decision") not in VALID_REVIEW:
        errors.append("invalid_human_reviewer_decision")
    if not isinstance(row.get("approved_for_ordering"), bool):
        errors.append("invalid_approved_for_ordering")
    if row.get("conditions") is not None and not isinstance(row.get("conditions"), list):
        errors.append("invalid_conditions")
    if row.get("order_ready_payload_uri") and not row.get("approved_for_ordering"):
        errors.append("order_ready_payload_without_ordering_approval")
    if row.get("approved_for_ordering"):
        if row.get("screening_state") != "approved_for_ordering":
            errors.append("approved_for_ordering_requires_final_state")
        if row.get("synthesis_permission") != "granted":
            errors.append("approved_for_ordering_requires_granted_permission")
        if row.get("customer_or_project_approval") != "approved":
            errors.append("approved_for_ordering_requires_project_approval")
        if row.get("human_reviewer_decision") != "approved":
            errors.append("approved_for_ordering_requires_human_approval")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate biosecurity screening decisions")
    parser.add_argument("--drafts", type=Path, default=DRAFTS)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    args.input.parent.mkdir(parents=True, exist_ok=True)
    if not args.input.exists():
        args.input.write_text("", encoding="utf-8")
    write_jsonl(args.template, [TEMPLATE_ROW])

    drafts = load_jsonl(args.drafts)
    decisions = load_jsonl(args.input)
    draft_by_id = {str(row.get("screening_request_id")): row for row in drafts}
    records = []
    errors = Counter()
    seen = set()
    duplicates = set()
    for row in decisions:
        request_id = str(row.get("screening_request_id"))
        if request_id in seen:
            duplicates.add(request_id)
        seen.add(request_id)
        row_errors = validate(row, draft_by_id)
        errors.update(row_errors)
        records.append({
            "screening_request_id": row.get("screening_request_id"),
            "candidate_id": row.get("candidate_id"),
            "screening_state": row.get("screening_state"),
            "valid": not row_errors,
            "approved_for_ordering": bool(row.get("approved_for_ordering")) and not row_errors,
            "errors": row_errors,
        })
    if duplicates:
        errors.update({"duplicate_screening_request_id": len(duplicates)})
        for record in records:
            if record["screening_request_id"] in duplicates:
                record["valid"] = False
                record["approved_for_ordering"] = False
                record["errors"].append("duplicate_screening_request_id")

    valid_rows = sum(1 for item in records if item["valid"])
    approved = sum(1 for item in records if item["approved_for_ordering"])
    decided_request_ids = {str(item["screening_request_id"]) for item in records if item["valid"]}
    missing_draft_decisions = sorted(set(draft_by_id) - decided_request_ids)
    report = {
        "local_only": True,
        "input": str(args.input),
        "template": str(args.template),
        "draft_rows": len(drafts),
        "decision_rows": len(decisions),
        "valid_rows": valid_rows,
        "invalid_rows": len(records) - valid_rows,
        "approved_for_ordering_rows": approved,
        "all_drafts_decided": len(missing_draft_decisions) == 0 and bool(drafts),
        "missing_draft_decisions": missing_draft_decisions[:100],
        "ready_for_ordering": approved == len(drafts) and bool(drafts) and not errors,
        "error_counts": dict(errors),
        "records": records[:200],
        "policy": "Biosecurity approval requires explicit screening result, project/use approval, and human reviewer decision; empty decisions stay blocked.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": len(decisions),
        "valid_rows": valid_rows,
        "approved_for_ordering_rows": approved,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
