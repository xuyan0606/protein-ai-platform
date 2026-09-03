#!/usr/bin/env python3
"""Build coverage audit for latest Stage 25 blocker handoff surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = AI_ROOT.parent
MATRIX = AI_ROOT / "reports" / "stage25_remaining_blocker_closure_matrix_20260806.json"
OVERALL = AI_ROOT / "reports" / "stage25_overall_fail_closed_index_20260806.json"
RUNNER = AI_ROOT / "reports" / "stage25_fail_closed_validation_run_report_20260806.json"
HANDOFF = AI_ROOT / "reports" / "stage25_handoff_bundle_manifest_20260806.json"
NEXT_OPERATOR = AI_ROOT / "reports" / "next_operator_packet_20260806.md"
DAILY = PLATFORM_ROOT / "docs" / "manuals" / "2026-08-06-daily-report.md"
REVIEWER_PACKET = AI_ROOT / "reports" / "stage25_execute_closeout_reviewer_packet_20260806.md"
OUTPUT = AI_ROOT / "reports" / "stage25_latest_blocker_coverage_audit_20260806.json"


BLOCKER_COVERAGE = {
    "stage25_new_paper_fulltext_source_table": {
        "overall_terms": ["source_drop_manifest_valid", "source_acquisition_shortlist_valid", "literature_web_search_receipt_valid", "source_drop_extraction_readiness_candidates_valid"],
        "runner_terms": ["validate_stage25_source_drop_manifest", "validate_stage25_source_acquisition_shortlist", "validate_stage25_literature_web_search_receipt", "validate_stage25_source_drop_extraction_readiness_candidates"],
        "doc_terms": ["fulltext/source-table", "source-drop", "Source acquisition shortlist", "Literature search"],
    },
    "stage25_sqlite_apply": {
        "overall_terms": ["family_apply_transaction_plans_valid", "family_apply_transaction_ready_to_apply_rows"],
        "runner_terms": ["validate_stage25_family_apply_transaction_plans", "validate_stage25_approved_apply_report", "validate_new_paper_proposal_set_consistency"],
        "doc_terms": ["SQLite", "apply", "proposal set consistency"],
    },
    "stage25_formal_decisions": {
        "overall_terms": ["hard_gate_formal_decision_draft_package_valid", "workstream_acceptance_decision_rows"],
        "runner_terms": ["validate_stage25_hard_gate_formal_decision_draft_package", "validate_workstream_acceptance_decisions"],
        "doc_terms": ["formal decision", "needs_more_info"],
    },
    "stage25_foldx_runtime_receipt": {
        "overall_terms": ["foldx_provision_manifest_candidate_valid", "foldx_runtime_receipt_candidate_drafts_valid"],
        "runner_terms": ["validate_stage25_foldx_provision_manifest_candidate", "validate_stage25_foldx_runtime_receipt_candidate_drafts"],
        "doc_terms": ["FoldX", "runtime receipt"],
    },
    "stage25_model_release_claim": {
        "overall_terms": ["claim_release_consistency_valid", "local_release_consistency_success"],
        "runner_terms": ["validate_stage25_claim_release_consistency", "validate_local_release_manifest_fail_closed_consistency"],
        "doc_terms": ["model", "release"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> int:
    matrix = load_json(MATRIX)
    overall = load_json(OVERALL)
    runner = load_json(RUNNER)
    handoff = load_json(HANDOFF)
    next_operator_text = file_text(NEXT_OPERATOR)
    daily_text = file_text(DAILY)
    reviewer_text = file_text(REVIEWER_PACKET)
    docs_text = "\n".join([next_operator_text, daily_text, reviewer_text])
    handoff_paths = {str(row.get("path")) for row in handoff.get("files") or [] if isinstance(row, dict)}
    runner_text = json.dumps(runner, ensure_ascii=False)

    rows = []
    for blocker in matrix.get("blockers") or []:
        blocker_id = str(blocker.get("blocker_id"))
        coverage = BLOCKER_COVERAGE.get(blocker_id, {})
        current_receipt = str(blocker.get("current_receipt") or "")
        overall_terms = coverage.get("overall_terms", [])
        runner_terms = coverage.get("runner_terms", [])
        doc_terms = coverage.get("doc_terms", [])
        matched_overall_terms = [term for term in overall_terms if term in overall]
        matched_runner_terms = [term for term in runner_terms if term in runner_text]
        matched_doc_terms = [term for term in doc_terms if term in docs_text]
        covered_by_current_receipt = Path(current_receipt).exists()
        covered_by_overall_index = matched_overall_terms == overall_terms
        covered_by_handoff_manifest = current_receipt in handoff_paths
        covered_by_operator_docs = blocker_id in docs_text or matched_doc_terms == doc_terms
        covered_by_runner_or_rerun = matched_runner_terms == runner_terms
        rows.append({
            "blocker_id": blocker_id,
            "status": blocker.get("status"),
            "current_receipt": current_receipt,
            "closure_condition": blocker.get("closure_condition"),
            "expected_overall_terms": overall_terms,
            "matched_overall_terms": matched_overall_terms,
            "missing_overall_terms": [term for term in overall_terms if term not in matched_overall_terms],
            "expected_runner_terms": runner_terms,
            "matched_runner_terms": matched_runner_terms,
            "missing_runner_terms": [term for term in runner_terms if term not in matched_runner_terms],
            "expected_doc_terms": doc_terms,
            "matched_doc_terms": matched_doc_terms,
            "missing_doc_terms": [term for term in doc_terms if term not in matched_doc_terms],
            "covered_by_current_receipt": covered_by_current_receipt,
            "covered_by_overall_index": covered_by_overall_index,
            "covered_by_handoff_manifest": covered_by_handoff_manifest,
            "covered_by_operator_docs": covered_by_operator_docs,
            "covered_by_runner_or_rerun": covered_by_runner_or_rerun,
            "coverage_complete": all([
                covered_by_current_receipt,
                covered_by_overall_index,
                covered_by_handoff_manifest,
                covered_by_operator_docs,
                covered_by_runner_or_rerun,
            ]),
        })

    uncovered = [row["blocker_id"] for row in rows if row.get("coverage_complete") is not True]
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_latest_blocker_coverage_audit",
        "stage": 25,
        "audit_valid": not uncovered,
        "blocker_rows": len(rows),
        "covered_by_current_receipt_rows": sum(1 for row in rows if row.get("covered_by_current_receipt") is True),
        "covered_by_overall_index_rows": sum(1 for row in rows if row.get("covered_by_overall_index") is True),
        "covered_by_handoff_manifest_rows": sum(1 for row in rows if row.get("covered_by_handoff_manifest") is True),
        "covered_by_operator_docs_rows": sum(1 for row in rows if row.get("covered_by_operator_docs") is True),
        "covered_by_runner_or_rerun_rows": sum(1 for row in rows if row.get("covered_by_runner_or_rerun") is True),
        "uncovered_blockers": uncovered,
        "rows": rows,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "audit_valid": report["audit_valid"],
        "blocker_rows": report["blocker_rows"],
        "uncovered_blockers": len(uncovered),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
