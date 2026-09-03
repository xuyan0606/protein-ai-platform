#!/usr/bin/env python3
"""Build the next human decision closeout package for shortest blockers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "reports" / "human_decision_release_blocker_matrix_20260806.json"
DEFAULT_OUTPUT = ROOT / "reports" / "human_decision_next_closeout_package_20260806.json"
TARGET_BLOCKERS = {"partial_valid_rows_manual_rows_missing", "formal_acceptance_or_action_missing"}
VALIDATE_COMMANDS = {
    "numbering_curation": "python3 AI大模型/scripts/validate_numbering_curation_decisions.py",
    "structure_chain_mapping": "python3 AI大模型/scripts/validate_structure_chain_mapping_decisions.py",
    "external_license_review": "python3 AI大模型/scripts/validate_external_license_review_decisions.py",
    "workstream_acceptance": "python3 AI大模型/scripts/validate_workstream_acceptance_decisions.py",
    "operator_review_actions": "python3 AI大模型/scripts/validate_operator_review_action_decisions.py",
}
MIN_FIELDS = {
    "numbering_curation": ["packet_id", "decision", "canonical_or_isoform_mapping", "evidence_refs", "reviewer"],
    "structure_chain_mapping": ["packet_id", "biological_chain", "numbering_basis", "uniprot_match", "confidence", "reviewer"],
    "external_license_review": ["source_id", "license_evidence", "allowed_use", "decision", "reviewer"],
    "workstream_acceptance": ["workstream", "accept_or_reject", "evidence_artifacts", "reviewer", "decision_timestamp"],
    "operator_review_actions": ["action_id", "action_decision", "evidence_artifacts", "reviewer", "decision_timestamp"],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    rows = []
    for row in matrix.get("rows", []):
        if row.get("blocker_type") not in TARGET_BLOCKERS:
            continue
        workstream = row.get("workstream")
        rows.append({
            "workstream": workstream,
            "blocker_type": row.get("blocker_type"),
            "priority": row.get("priority"),
            "missing_rows": row.get("missing_rows"),
            "valid_rows": row.get("valid_rows"),
            "decision_input": row.get("decision_input"),
            "validator_report": row.get("validator_report"),
            "minimum_required_fields": MIN_FIELDS.get(workstream, ["decision", "reviewer", "evidence_refs"]),
            "validate_command": VALIDATE_COMMANDS.get(workstream),
            "review_status": "pending_human_input",
            "formal_decision_rows_written": 0,
            "release_ready": False,
        })
    output = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "human_decision_next_closeout_package",
        "write_policy": "closeout_package_only; no_formal_decision_rows_written",
        "summary": {
            "target_blockers": len(rows),
            "total_missing_rows_in_scope": sum(int(row.get("missing_rows") or 0) for row in rows),
            "formal_decision_rows_written": 0,
            "release_ready": False,
            "safe_for_model_claim": False,
        },
        "items": rows,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
