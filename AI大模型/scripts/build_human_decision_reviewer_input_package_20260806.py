#!/usr/bin/env python3
"""Build human decision reviewer input packets without writing formal decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports" / "human_decision_backlog_report.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_reviewer_input_package_20260806.json"


FIELDS_BY_WORKSTREAM = {
    "structure_chain_mapping": ["biological_chain", "numbering_basis", "uniprot_match", "confidence", "evidence_refs"],
    "numbering_curation": ["canonical_or_isoform_mapping", "literature_mapping", "decision", "evidence_refs"],
    "experiment_feedback_source_review": ["source_provenance", "eligibility", "reviewer", "decision", "evidence_refs"],
    "plate_feedback_intake": ["qc_status", "numbering_status", "training_eligibility", "reviewer", "evidence_refs"],
    "external_license_review": ["license_evidence", "allowed_use", "decision", "reviewer", "evidence_refs"],
    "biosecurity_screening": ["screening_provider", "screening_reference", "intended_use", "ordering_decision", "reviewer"],
    "sequence_ip_fto": ["prior_art_refs", "jurisdictions", "fto_decision", "delivery_permission", "reviewer"],
    "workstream_acceptance": ["evidence_artifacts", "accept_or_reject", "reviewer", "decision_timestamp"],
    "operator_review_actions": ["evidence_artifacts", "action_decision", "reviewer", "decision_timestamp"],
    "numbering_semantic_conflict_resolution": ["conflict_resolution", "reject_label_or_rewrite", "reviewer", "evidence_refs"],
    "domain_interval_occurrence_selection": ["selected_occurrence", "unresolved_reason", "reviewer", "evidence_refs"],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = []
    for item in source.get("items", []):
        workstream = item.get("workstream")
        items.append({
            "backlog_id": item.get("backlog_id"),
            "workstream": workstream,
            "priority": item.get("priority"),
            "required_rows": item.get("required_rows", 0),
            "completed_rows": item.get("completed_rows", 0),
            "missing_rows": item.get("missing_rows", 0),
            "review_source": item.get("review_source"),
            "decision_input": item.get("decision_input"),
            "validator_report": item.get("validator_report"),
            "next_action": item.get("next_action"),
            "review_fields": FIELDS_BY_WORKSTREAM.get(workstream, ["decision", "reviewer", "evidence_refs"]),
            "formal_decision_rows_written": 0,
            "review_status": "pending_human_input",
            "release_ready": False,
            "safe_for_model_claim": False,
        })
    package = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "human_decision_reviewer_input_package",
        "write_policy": "input_package_only; no_formal_decision_rows_written",
        "source_report": str(args.input),
        "backlog_summary": {
            "backlog_items": source.get("backlog_items"),
            "open_items": source.get("open_items"),
            "ready_items": source.get("ready_items"),
            "required_rows": source.get("total_required_rows"),
            "completed_rows": source.get("total_completed_rows"),
            "missing_rows": source.get("total_missing_rows"),
        },
        "items": items,
        "formal_decision_rows_written": 0,
        "release_flags": {
            "release_ready": False,
            "customer_delivery_ready": False,
            "safe_for_model_claim": False,
        },
    }
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "backlog_items": len(items),
        "missing_rows": package["backlog_summary"]["missing_rows"],
        "formal_decision_rows_written": 0,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
