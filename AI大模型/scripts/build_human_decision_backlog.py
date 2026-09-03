#!/usr/bin/env python3
"""Build a unified backlog of human-reviewed decisions still required."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT_OUT = AI_ROOT / "reports" / "human_decision_backlog_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "human_decision_backlog.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def rel(path: str | None) -> str | None:
    if not path:
        return None
    value = Path(path)
    try:
        return str(value.relative_to(AI_ROOT)) if value.is_absolute() else str(value)
    except ValueError:
        return str(value)


def item(
    backlog_id: str,
    workstream: str,
    priority: str,
    decision_scope: str,
    review_source: str | None,
    decision_input: str | None,
    template: str | None,
    validator_report: str | None,
    required_rows: int,
    current_decision_rows: int,
    current_valid_rows: int,
    completed_rows: int,
    next_action: str,
    policy: str,
    milestone_required_rows: int | None = None,
) -> dict[str, Any]:
    missing_rows = max(required_rows - completed_rows, 0)
    row = {
        "backlog_id": backlog_id,
        "workstream": workstream,
        "priority": priority,
        "decision_scope": decision_scope,
        "review_source": review_source,
        "decision_input": decision_input,
        "template": template,
        "validator_report": validator_report,
        "required_rows": required_rows,
        "current_decision_rows": current_decision_rows,
        "current_valid_rows": current_valid_rows,
        "completed_rows": completed_rows,
        "missing_rows": missing_rows,
        "ready": missing_rows == 0 and required_rows > 0,
        "next_action": next_action,
        "policy": policy,
    }
    if milestone_required_rows is not None:
        row["milestone_required_rows"] = milestone_required_rows
        row["milestone_missing_rows"] = max(milestone_required_rows - completed_rows, 0)
    return row


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build human decision backlog")
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    numbering_queue = load_json(AI_ROOT / "reports" / "numbering_curation_queue_report.json")
    numbering_packets = load_json(AI_ROOT / "reports" / "numbering_review_packet_report.json")
    numbering_validation = load_json(AI_ROOT / "reports" / "numbering_curation_validation_report.json")
    numbering_semantic_conflict = load_json(AI_ROOT / "reports" / "numbering_decision_semantic_conflict_report.json")
    repaired = load_json(AI_ROOT / "reports" / "repaired_supervised_table_report.json")
    structure_packets = load_json(AI_ROOT / "reports" / "structure_chain_review_packet_report.json")
    structure_validation = load_json(AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json")
    domain_packets = load_json(AI_ROOT / "reports" / "domain_interpro_review_packet_report.json")
    domain_interpro = load_json(AI_ROOT / "reports" / "domain_interval_interpro_decision_report.json")
    domain_validation = load_json(AI_ROOT / "reports" / "domain_interval_decision_validation_report.json")
    feedback_sources = load_json(AI_ROOT / "reports" / "experiment_feedback_source_review_packet_report.json")
    feedback_source_decisions = load_json(AI_ROOT / "reports" / "experiment_feedback_source_review_decision_validation_report.json")
    feedback_plate_packets = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_review_packet_report.json")
    feedback_plate_validation = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
    feedback_validation = load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json")
    license_validation = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    biosecurity_validation = load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json")
    operator_validation = load_json(AI_ROOT / "reports" / "operator_review_action_decision_validation_report.json")
    workstream_validation = load_json(AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json")
    ip_validation = load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json")

    strict_rows = repaired.get("supervised_rows") or 0
    domain_manual_completed = max(
        (domain_validation.get("valid_rows") or 0) - (domain_interpro.get("interpro_program_reviewed_decisions") or 0),
        0,
    )
    rows = [
        item(
            "human_decision_numbering_semantic_conflict_001",
            "numbering_semantic_conflict_resolution",
            "P0",
            "notes/decision mismatch resolution for reviewed numbering rows",
            "datasets/curation/numbering_decision_semantic_conflict_queue.jsonl",
            "datasets/curation/numbering_curation_decisions.jsonl",
            "datasets/curation/numbering_curation_decisions.template.jsonl",
            "reports/numbering_decision_semantic_conflict_report.json",
            numbering_semantic_conflict.get("semantic_conflict_rows") or 0,
            numbering_semantic_conflict.get("semantic_conflict_rows") or 0,
            0,
            0,
            "Resolve each conflict by either converting the row to reject_label or rewriting notes so they no longer reject the label.",
            "A reviewed decision with contradictory notes must be made explicit before any downstream claim.",
        ),
        item(
            "human_decision_numbering_001",
            "numbering_curation",
            "P0",
            "mutation label numbering/canonical mapping",
            "datasets/curation/numbering_review_packets/",
            "datasets/curation/numbering_curation_decisions.jsonl",
            "datasets/curation/numbering_curation_decisions.template.jsonl",
            "reports/numbering_curation_validation_report.json",
            numbering_queue.get("queue_rows") or numbering_packets.get("packet_rows") or 0,
            numbering_validation.get("decision_rows") or 0,
            numbering_validation.get("valid_rows") or 0,
            numbering_validation.get("valid_rows") or 0,
            "Review numbering packets and append only verified canonical/isoform/literature mapping decisions.",
            "Weak evidence cannot become supervised labels without reviewed numbering decisions.",
            milestone_required_rows=max(100 - strict_rows, 0),
        ),
        item(
            "human_decision_structure_chain_001",
            "structure_chain_mapping",
            "P0",
            "biological chain and sequence-to-structure numbering",
            "datasets/curation/structure_chain_review_packets/",
            "datasets/curation/structure_chain_mapping_decisions.jsonl",
            "datasets/curation/structure_chain_mapping_decisions.template.jsonl",
            "reports/structure_chain_mapping_decision_validation_report.json",
            structure_packets.get("packet_rows") or structure_validation.get("worklist_rows") or 0,
            structure_validation.get("decision_rows") or 0,
            structure_validation.get("valid_rows") or 0,
            structure_validation.get("reviewed_chain_mapping_rows") or 0,
            "Review chain packets and append decisions with biological chain, numbering basis, UniProt match, and confidence.",
            "Parsed structure files do not permit coordinate-level claims until chain mappings are reviewed.",
        ),
        item(
            "human_decision_domain_occurrence_001",
            "domain_interval_occurrence_selection",
            "P1",
            "multi-interval Pfam/domain occurrence selection",
            "datasets/curation/domain_interpro_review_packets/",
            "datasets/curation/domain_interval_decisions.jsonl",
            "datasets/curation/domain_interval_decisions.template.jsonl",
            "reports/domain_interval_decision_validation_report.json",
            domain_packets.get("unresolved_rows") or domain_packets.get("packet_rows") or 0,
            domain_manual_completed,
            domain_manual_completed,
            domain_manual_completed,
            "Resolve multi-interval/no-exact Pfam rows by choosing the reviewed occurrence or keeping unresolved.",
            "Program-reviewed single-interval rows are usable; unresolved occurrence selection still needs human review.",
        ),
        item(
            "human_decision_feedback_source_001",
            "experiment_feedback_source_review",
            "P0",
            "source triage for genuine KWB wet-lab feedback",
            "datasets/feedback/source_review_packets/",
            rel((feedback_source_decisions.get("outputs") or {}).get("input")),
            rel((feedback_source_decisions.get("outputs") or {}).get("template")),
            "reports/experiment_feedback_source_review_decision_validation_report.json",
            feedback_sources.get("packet_rows") or 0,
            feedback_source_decisions.get("decision_rows") or 0,
            feedback_source_decisions.get("valid_rows") or 0,
            feedback_source_decisions.get("approved_for_feedback_extraction_rows") or 0,
            "Review source packets and approve only genuine wet-lab/historical sources for extraction before any schema transcription.",
            "Source packets and drafts are not feedback labels; approved source review only creates extraction candidates, not training rows.",
        ),
        item(
            "human_decision_plate_feedback_001",
            "plate_feedback_intake",
            "P0",
            "plate/well-level assay feedback intake",
            rel(feedback_plate_packets.get("packet_file")),
            rel(feedback_plate_validation.get("input")),
            rel(feedback_plate_validation.get("template")),
            "reports/experiment_feedback_plate_intake_validation_report.json",
            feedback_plate_packets.get("plate_review_packet_rows") or 0,
            feedback_plate_validation.get("input_rows") or 0,
            feedback_plate_validation.get("valid_rows") or 0,
            feedback_plate_validation.get("training_eligible_rows") or 0,
            "Move reviewed, QC-classified plate/well rows into the local plate feedback intake file.",
            "Plate drafts cannot become training rows without manual extraction and QC classification.",
        ),
        item(
            "human_decision_license_001",
            "external_license_review",
            "P0",
            "external data/tool license and allowed use",
            "datasets/governance/external_license_review_packets.jsonl",
            rel(license_validation.get("input")),
            rel(license_validation.get("template")),
            "reports/external_license_review_decision_validation_report.json",
            license_validation.get("packet_rows") or 0,
            license_validation.get("decision_rows") or 0,
            license_validation.get("valid_rows") or 0,
            license_validation.get("approved_for_customer_delivery_rows") or 0,
            "Record explicit legal/license decisions for each external data source and foreign tool.",
            "Packets organize review work; only reviewed license decisions can grant training, evaluation, or delivery use.",
        ),
        item(
            "human_decision_biosecurity_001",
            "biosecurity_screening",
            "P0",
            "sequence/order biosecurity screening and human approval",
            "datasets/governance/biosecurity_screening_drafts.jsonl",
            rel(biosecurity_validation.get("input")),
            rel(biosecurity_validation.get("template")),
            "reports/biosecurity_screening_decision_validation_report.json",
            biosecurity_validation.get("draft_rows") or 0,
            biosecurity_validation.get("decision_rows") or 0,
            biosecurity_validation.get("valid_rows") or 0,
            biosecurity_validation.get("approved_for_ordering_rows") or 0,
            "Record screening provider/reference, customer/use approval, and human reviewer decision.",
            "No order-ready sequence or construct output is permitted without explicit biosecurity approval.",
        ),
        item(
            "human_decision_sequence_ip_fto_001",
            "sequence_ip_fto",
            "P0",
            "sequence IP/FTO legal review",
            "datasets/curation/sequence_ip_review_packets/",
            rel(ip_validation.get("input")),
            rel(ip_validation.get("template")),
            "reports/sequence_ip_fto_decision_validation_report.json",
            ip_validation.get("packet_rows") or 0,
            ip_validation.get("decision_rows") or 0,
            ip_validation.get("valid_rows") or 0,
            ip_validation.get("approved_for_customer_delivery_rows") or 0,
            "Record prior-art evidence, jurisdictions, FTO decision, and delivery approval per sequence candidate.",
            "Review packets are not FTO clearance; legal/human decisions remain required.",
        ),
        item(
            "human_decision_workstream_acceptance_001",
            "workstream_acceptance",
            "P1",
            "human acceptance of technical workstreams",
            "reports/workstream_acceptance_gates.json",
            rel(workstream_validation.get("input")),
            rel(workstream_validation.get("template")),
            "reports/workstream_acceptance_decision_validation_report.json",
            len(workstream_validation.get("expected_streams") or []),
            workstream_validation.get("decision_rows") or 0,
            workstream_validation.get("valid_rows") or 0,
            workstream_validation.get("accepted_streams") or 0,
            "Accept or reject each workstream with evidence artifacts and validation reports.",
            "Technical readiness alone does not count as human acceptance.",
        ),
        item(
            "human_decision_operator_actions_001",
            "operator_review_actions",
            "P1",
            "operator action completion decisions",
            "datasets/governance/operator_review_action_queue.jsonl",
            rel(operator_validation.get("input")),
            rel(operator_validation.get("template")),
            "reports/operator_review_action_decision_validation_report.json",
            operator_validation.get("queue_rows") or 0,
            operator_validation.get("decision_rows") or 0,
            operator_validation.get("valid_rows") or 0,
            operator_validation.get("completed_rows") or 0,
            "Mark operator actions complete only with referenced evidence artifacts and validation reports.",
            "The action queue is not completion evidence; separate reviewed completion decisions are required.",
        ),
    ]
    write_jsonl(args.jsonl, rows)

    open_items = [row for row in rows if not row["ready"]]
    report = {
        "local_only": True,
        "jsonl": str(args.jsonl),
        "backlog_items": len(rows),
        "ready_items": len(rows) - len(open_items),
        "open_items": len(open_items),
        "total_required_rows": sum(row["required_rows"] for row in rows),
        "total_completed_rows": sum(row["completed_rows"] for row in rows),
        "total_missing_rows": sum(row["missing_rows"] for row in rows),
        "priority_counts": {
            priority: sum(1 for row in rows if row["priority"] == priority)
            for priority in sorted({row["priority"] for row in rows})
        },
        "top_open_items": sorted(
            (
                {
                    "backlog_id": row["backlog_id"],
                    "workstream": row["workstream"],
                    "priority": row["priority"],
                    "missing_rows": row["missing_rows"],
                    "decision_input": row["decision_input"],
                    "next_action": row["next_action"],
                }
                for row in open_items
            ),
            key=lambda row: (row["priority"], -row["missing_rows"], row["workstream"]),
        )[:10],
        "items": rows,
        "policy": "This backlog summarizes required human-reviewed inputs only; it does not create approvals or promote draft/template rows.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "backlog_items": report["backlog_items"],
        "open_items": report["open_items"],
        "total_missing_rows": report["total_missing_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
