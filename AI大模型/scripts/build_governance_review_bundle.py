#!/usr/bin/env python3
"""Build one fail-closed human review bundle for governance decisions."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "datasets" / "governance" / "governance_review_bundle.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "governance_review_bundle_report.json"
MD_OUT = AI_ROOT / "reports" / "governance_review_bundle.md"

LICENSE_PACKETS = AI_ROOT / "datasets" / "governance" / "external_license_review_packets.jsonl"
LICENSE_VALIDATION = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"
BIOSECURITY_DRAFTS = AI_ROOT / "datasets" / "governance" / "biosecurity_screening_drafts.jsonl"
BIOSECURITY_VALIDATION = AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json"
SEQUENCE_PACKET_DIR = AI_ROOT / "datasets" / "curation" / "sequence_ip_review_packets"
SEQUENCE_VALIDATION = AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json"
OPERATOR_QUEUE = AI_ROOT / "datasets" / "governance" / "operator_review_action_queue.jsonl"
OPERATOR_VALIDATION = AI_ROOT / "reports" / "operator_review_action_decision_validation_report.json"
WORKSTREAM_GATES = AI_ROOT / "reports" / "workstream_acceptance_gates.json"
WORKSTREAM_VALIDATION = AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json"


WORKSTREAM_META = {
    "external_license_review": {
        "priority": "P0",
        "decision_input": "datasets/governance/external_license_review_decisions.jsonl",
        "template": "datasets/governance/external_license_review_decisions.template.jsonl",
        "validator_command": "python3 scripts/validate_external_license_review_decisions.py",
        "validator_report": "reports/external_license_review_decision_validation_report.json",
        "reviewer_role": "human legal/license reviewer",
        "required_human_decision": "license/use clearance for training, local evaluation, and customer delivery scopes",
        "blocking_claims": ["external_tool_production_use", "customer_sequence_package", "model_training_with_external_data"],
    },
    "biosecurity_screening": {
        "priority": "P0",
        "decision_input": "datasets/governance/biosecurity_screening_decisions.jsonl",
        "template": "datasets/governance/biosecurity_screening_decisions.template.jsonl",
        "validator_command": "python3 scripts/validate_biosecurity_screening_decisions.py",
        "validator_report": "reports/biosecurity_screening_decision_validation_report.json",
        "reviewer_role": "human biosecurity/order reviewer",
        "required_human_decision": "screening provider/reference, intended-use approval, and ordering permission",
        "blocking_claims": ["approved_for_ordering", "customer_sequence_package", "experiment_submission"],
    },
    "sequence_ip_fto": {
        "priority": "P0",
        "decision_input": "datasets/governance/sequence_ip_fto_decisions.jsonl",
        "template": "datasets/governance/sequence_ip_fto_decisions.template.jsonl",
        "validator_command": "python3 scripts/validate_sequence_ip_fto_decisions.py",
        "validator_report": "reports/sequence_ip_fto_decision_validation_report.json",
        "reviewer_role": "human IP/FTO reviewer",
        "required_human_decision": "prior-art evidence, jurisdictions, FTO decision, and delivery approval boundary",
        "blocking_claims": ["ip_fto_cleared", "customer_sequence_package"],
    },
    "operator_review_actions": {
        "priority": "P1",
        "decision_input": "datasets/governance/operator_review_action_decisions.jsonl",
        "template": "datasets/governance/operator_review_action_decisions.template.jsonl",
        "validator_command": "python3 scripts/validate_operator_review_action_decisions.py",
        "validator_report": "reports/operator_review_action_decision_validation_report.json",
        "reviewer_role": "human operator",
        "required_human_decision": "operator completion decision backed by existing evidence and validation artifacts",
        "blocking_claims": ["local_release_review_package", "operator_handoff_complete"],
    },
    "workstream_acceptance": {
        "priority": "P1",
        "decision_input": "datasets/governance/workstream_acceptance_decisions.jsonl",
        "template": "datasets/governance/workstream_acceptance_decisions.template.jsonl",
        "validator_command": "python3 scripts/validate_workstream_acceptance_decisions.py",
        "validator_report": "reports/workstream_acceptance_decision_validation_report.json",
        "reviewer_role": "human workstream owner",
        "required_human_decision": "accept, reject, block, or request more information for each workstream",
        "blocking_claims": ["model_claim", "customer_delivery", "experiment_submission"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def validation_records(path: Path, key_field: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key_field)): row for row in load_json(path).get("records", []) if row.get(key_field)}


def sequence_validation_records() -> dict[str, dict[str, Any]]:
    records = {}
    for row in load_json(SEQUENCE_VALIDATION).get("records", []):
        key = f"{row.get('review_packet_id')}:{row.get('candidate_id')}"
        records[key] = row
    return records


def row_status(record: dict[str, Any] | None, completion_key: str) -> str:
    if not record:
        return "open_blocked_waiting_for_human_decision"
    if not record.get("valid"):
        return "blocked_invalid_human_decision"
    if record.get(completion_key):
        return "reviewed_completion_ready"
    return "reviewed_valid_but_not_approved"


def make_bundle_row(
    *,
    workstream: str,
    source_artifact: str,
    source_row_id: str,
    source_row_summary: dict[str, Any],
    status: str,
    validation_record: dict[str, Any] | None,
    required_fields: list[str],
    review_order: int,
) -> dict[str, Any]:
    meta = WORKSTREAM_META[workstream]
    return {
        "bundle_id": f"governance_review:{workstream}:{slug(source_row_id)}",
        "workstream": workstream,
        "priority": meta["priority"],
        "review_order": review_order,
        "source_artifact": source_artifact,
        "source_row_id": source_row_id,
        "source_row_summary": source_row_summary,
        "decision_input": meta["decision_input"],
        "template": meta["template"],
        "validator_command": meta["validator_command"],
        "validator_report": meta["validator_report"],
        "reviewer_role": meta["reviewer_role"],
        "required_human_decision": meta["required_human_decision"],
        "required_fields": required_fields,
        "current_status": status,
        "human_review_required": True,
        "no_auto_approval": True,
        "completion_ready": status == "reviewed_completion_ready",
        "blocking_claims": meta["blocking_claims"],
        "validation_record": validation_record or {},
        "operator_next_step": "Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.",
        "policy": "Governance bundle rows are review work items only; they do not grant legal, biosecurity, FTO, operator, workstream, model, release, customer, or ordering approval.",
    }


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    order = 1

    license_records = validation_records(LICENSE_VALIDATION, "review_item_id")
    for packet in load_jsonl(LICENSE_PACKETS):
        source_id = str(packet.get("review_item_id"))
        record = license_records.get(source_id)
        rows.append(make_bundle_row(
            workstream="external_license_review",
            source_artifact=rel(LICENSE_PACKETS),
            source_row_id=source_id,
            source_row_summary={
                "item_type": packet.get("item_type"),
                "name": packet.get("name"),
                "declared_license": packet.get("declared_license"),
                "commercial_status": packet.get("commercial_status"),
                "redistribution_status": packet.get("redistribution_status"),
            },
            status=row_status(record, "approved_for_customer_delivery"),
            validation_record=record,
            required_fields=list(packet.get("required_review_fields") or []),
            review_order=order,
        ))
        order += 1

    biosecurity_records = validation_records(BIOSECURITY_VALIDATION, "screening_request_id")
    for draft in load_jsonl(BIOSECURITY_DRAFTS):
        source_id = str(draft.get("screening_request_id"))
        record = biosecurity_records.get(source_id)
        rows.append(make_bundle_row(
            workstream="biosecurity_screening",
            source_artifact=rel(BIOSECURITY_DRAFTS),
            source_row_id=source_id,
            source_row_summary={
                "candidate_id": draft.get("candidate_id"),
                "mutation_set": draft.get("mutation_set") or [],
                "screening_state": draft.get("screening_state"),
                "synthesis_permission": draft.get("synthesis_permission"),
                "blocked_reason": draft.get("blocked_reason"),
            },
            status=row_status(record, "approved_for_ordering"),
            validation_record=record,
            required_fields=[
                "screening_provider",
                "screening_reference",
                "customer_or_project_approval",
                "intended_use_statement",
                "human_reviewer_decision",
                "approved_for_ordering",
            ],
            review_order=order,
        ))
        order += 1

    sequence_records = sequence_validation_records()
    for path in sorted(SEQUENCE_PACKET_DIR.glob("*.jsonl")):
        for packet in load_jsonl(path):
            source_id = f"{packet.get('review_packet_id')}:{packet.get('candidate_id')}"
            record = sequence_records.get(source_id)
            rows.append(make_bundle_row(
                workstream="sequence_ip_fto",
                source_artifact=rel(path),
                source_row_id=source_id,
                source_row_summary={
                    "candidate_id": packet.get("candidate_id"),
                    "mutation_set": packet.get("mutation_set") or [],
                    "prior_art_source": packet.get("prior_art_source"),
                    "jurisdiction": packet.get("jurisdiction"),
                    "legal_status": packet.get("legal_status"),
                    "source_record": packet.get("source_record") or {},
                },
                status=row_status(record, "approved_for_customer_delivery"),
                validation_record=record,
                required_fields=[
                    "review_basis",
                    "prior_art_evidence",
                    "jurisdictions",
                    "fto_decision",
                    "approved_for_internal_use",
                    "approved_for_customer_delivery",
                ],
                review_order=order,
            ))
            order += 1

    operator_records = validation_records(OPERATOR_VALIDATION, "action_id")
    for action in load_jsonl(OPERATOR_QUEUE):
        source_id = str(action.get("action_id"))
        record = operator_records.get(source_id)
        rows.append(make_bundle_row(
            workstream="operator_review_actions",
            source_artifact=rel(OPERATOR_QUEUE),
            source_row_id=source_id,
            source_row_summary={
                "stream": action.get("stream"),
                "priority": action.get("priority"),
                "status": action.get("status"),
                "suggested_next_artifacts": action.get("suggested_next_artifacts"),
                "done_definition": action.get("done_definition"),
            },
            status=row_status(record, "completed"),
            validation_record=record,
            required_fields=[
                "evidence_artifacts",
                "validation_reports",
                "completion_note",
                "residual_risks",
                "next_action",
            ],
            review_order=order,
        ))
        order += 1

    workstream_records = validation_records(WORKSTREAM_VALIDATION, "stream")
    gates = load_json(WORKSTREAM_GATES).get("gates", [])
    for gate in gates:
        source_id = str(gate.get("stream"))
        record = workstream_records.get(source_id)
        rows.append(make_bundle_row(
            workstream="workstream_acceptance",
            source_artifact=rel(WORKSTREAM_GATES),
            source_row_id=source_id,
            source_row_summary={
                "technical_ready": bool(gate.get("technical_ready")),
                "human_accepted": bool(gate.get("human_accepted")),
                "accepted": bool(gate.get("accepted")),
                "acceptance_requires": gate.get("acceptance_requires") or [],
            },
            status=row_status(record, "accepted"),
            validation_record=record,
            required_fields=[
                "evidence_artifacts",
                "validation_reports",
                "acceptance_scope",
                "acceptance_decision",
                "acceptance_note",
                "residual_risks",
            ],
            review_order=order,
        ))
        order += 1

    return rows


def write_markdown(path: Path, report: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Governance Review Bundle",
        "",
        "This bundle coordinates human governance review only. It does not create approvals.",
        "",
        f"- Total rows: {report['bundle_rows']}",
        f"- Open rows: {report['open_rows']}",
        f"- Completion-ready rows: {report['completion_ready_rows']}",
        f"- Release ready: {str(report['release_ready']).lower()}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "| Workstream | Rows | Open | Completion Ready | Decision Input | Validator |",
        "|---|---:|---:|---:|---|---|",
    ]
    for item in report["workstreams"]:
        meta = WORKSTREAM_META[item["workstream"]]
        lines.append(
            "| {workstream} | {rows} | {open_rows} | {completion_ready_rows} | `{decision}` | `{validator}` |".format(
                workstream=item["workstream"],
                rows=item["rows"],
                open_rows=item["open_rows"],
                completion_ready_rows=item["completion_ready_rows"],
                decision=meta["decision_input"],
                validator=meta["validator_command"],
            )
        )
    lines.extend([
        "",
        "## First Open Items",
        "",
    ])
    for row in rows[:20]:
        lines.append(
            f"- `{row['bundle_id']}`: {row['current_status']} -> {row['operator_next_step']}"
        )
    lines.extend([
        "",
        "## Policy",
        "",
        report["policy"],
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build governance review bundle")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    args = parser.parse_args()

    rows = build_rows()
    write_jsonl(args.output, rows)

    by_workstream = Counter(row["workstream"] for row in rows)
    open_by_workstream = Counter(row["workstream"] for row in rows if not row["completion_ready"])
    ready_by_workstream = Counter(row["workstream"] for row in rows if row["completion_ready"])
    completion_ready_rows = sum(1 for row in rows if row["completion_ready"])
    open_rows = len(rows) - completion_ready_rows
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "online_deployment": False,
        "jsonl": rel(args.output),
        "markdown": rel(args.markdown),
        "bundle_rows": len(rows),
        "open_rows": open_rows,
        "completion_ready_rows": completion_ready_rows,
        "human_review_required_rows": sum(1 for row in rows if row["human_review_required"]),
        "no_auto_approval_rows": sum(1 for row in rows if row["no_auto_approval"]),
        "ready": open_rows == 0 and bool(rows),
        "safe_for_model_claim": False,
        "release_ready": False,
        "workstreams": [
            {
                "workstream": workstream,
                "priority": WORKSTREAM_META[workstream]["priority"],
                "rows": by_workstream.get(workstream, 0),
                "open_rows": open_by_workstream.get(workstream, 0),
                "completion_ready_rows": ready_by_workstream.get(workstream, 0),
                "decision_input": WORKSTREAM_META[workstream]["decision_input"],
                "validator_report": WORKSTREAM_META[workstream]["validator_report"],
                "validator_command": WORKSTREAM_META[workstream]["validator_command"],
            }
            for workstream in WORKSTREAM_META
        ],
        "top_blockers": [
            {
                "bundle_id": row["bundle_id"],
                "workstream": row["workstream"],
                "source_row_id": row["source_row_id"],
                "current_status": row["current_status"],
                "decision_input": row["decision_input"],
                "validator_command": row["validator_command"],
            }
            for row in rows
            if not row["completion_ready"]
        ][:25],
        "policy": "This governance bundle is a shared human-review work queue. It preserves fail-closed gates: no row grants license, FTO, biosecurity, operator, workstream, model, release, ordering, customer, or deployment approval until the separate human decision file and validator explicitly say so.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.markdown, report, rows)
    print(json.dumps({
        "bundle_rows": report["bundle_rows"],
        "open_rows": report["open_rows"],
        "completion_ready_rows": report["completion_ready_rows"],
        "ready": report["ready"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
