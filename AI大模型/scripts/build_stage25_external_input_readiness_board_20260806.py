#!/usr/bin/env python3
"""Build a unified Stage 25 external-input readiness board."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_VALIDATION = AI_ROOT / "reports" / "stage25_source_drop_manifest_validation_20260806.json"
FOLDX_CANDIDATES = AI_ROOT / "datasets" / "governance" / "stage25_foldx_provision_manifest_candidate_20260806.jsonl"
STRICT_DRAFTS = AI_ROOT / "datasets" / "curation" / "kwb_venus15b_strict_holdout_review_decisions.stage25_draft_20260806.jsonl"
SUBSTRATE_DRAFTS = AI_ROOT / "datasets" / "curation" / "substrate_identity_review_decisions.stage25_draft_20260806.jsonl"
WORKSTREAM_VALIDATION = AI_ROOT / "reports" / "workstream_acceptance_decision_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "stage25_external_input_readiness_board_20260806.json"


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


def main() -> int:
    source_validation = load_json(SOURCE_VALIDATION)
    foldx_rows = load_jsonl(FOLDX_CANDIDATES)
    strict_rows = load_jsonl(STRICT_DRAFTS)
    substrate_rows = load_jsonl(SUBSTRATE_DRAFTS)
    workstream_validation = load_json(WORKSTREAM_VALIDATION)

    rows: list[dict[str, Any]] = []
    for source in source_validation.get("source_status") or []:
        rows.append({
            "input_id": source.get("source_id"),
            "category": "new_paper_source_drop",
            "blocker_id": "stage25_new_paper_fulltext_source_table",
            "proposal_id": source.get("intake_prefix"),
            "doi": source.get("doi"),
            "pmid": source.get("pmid"),
            "expected_local_path": source.get("expected_local_path"),
            "status": "present" if source.get("exists") else "missing",
            "completion_ready": source.get("ready_for_extraction") is True,
            "next_action": "place legally obtained source file at expected_local_path and rerun source-drop validators",
        })

    for foldx in foldx_rows:
        rows.append({
            "input_id": foldx.get("provision_id"),
            "category": "foldx_runtime_provision",
            "blocker_id": "stage25_foldx_runtime_receipt",
            "expected_local_path": foldx.get("expected_local_path"),
            "status": foldx.get("status"),
            "completion_ready": foldx.get("ready_for_runtime_receipt") is True,
            "next_action": "provide licensed executable or hashed FoldX smoke artifact and rerun FoldX provision validators",
        })

    for strict in strict_rows:
        rows.append({
            "input_id": strict.get("review_key"),
            "category": "strict_holdout_formal_decision",
            "blocker_id": "stage25_formal_decisions",
            "formal_decision_file": strict.get("formal_decision_file"),
            "status": strict.get("decision"),
            "completion_ready": (
                strict.get("decision") == "approved"
                and strict.get("source_evidence_confirmed") is True
                and strict.get("numbering_confirmed") is True
                and strict.get("wetlab_result_confirmed") is True
                and strict.get("leakage_check_passed") is True
                and bool(strict.get("acceptance_receipt"))
            ),
            "next_action": "human reviewer must fill formal strict-holdout decision with basis, reviewer, timestamp and acceptance receipt",
        })

    for substrate in substrate_rows:
        rows.append({
            "input_id": substrate.get("review_key"),
            "category": "substrate_identity_formal_decision",
            "blocker_id": "stage25_formal_decisions",
            "formal_decision_file": substrate.get("formal_decision_file"),
            "status": substrate.get("decision"),
            "completion_ready": (
                substrate.get("decision") == "approved"
                and substrate.get("identity_confirmed") is True
                and substrate.get("scope_confirmed") is True
                and substrate.get("condition_confirmed") is True
                and substrate.get("protocol_version_confirmed") is True
                and bool(substrate.get("acceptance_receipt"))
            ),
            "next_action": "human reviewer must fill formal substrate identity decision; do not infer substrate identity or SMILES",
        })

    records_by_stream = {
        str(record.get("stream")): record
        for record in workstream_validation.get("records") or []
        if isinstance(record, dict)
    }
    for stream in workstream_validation.get("expected_streams") or []:
        record = records_by_stream.get(str(stream), {})
        rows.append({
            "input_id": str(stream),
            "category": "workstream_acceptance_decision",
            "blocker_id": "stage25_model_release_claim",
            "status": record.get("acceptance_decision") or "missing",
            "completion_ready": record.get("accepted") is True,
            "next_action": "human owner must provide explicit accepted workstream decision before model/release/customer claims",
        })

    category_counts = {
        category: sum(1 for row in rows if row["category"] == category)
        for category in sorted({row["category"] for row in rows})
    }
    blocker_counts = {
        blocker: sum(1 for row in rows if row["blocker_id"] == blocker)
        for blocker in sorted({row["blocker_id"] for row in rows})
    }
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_external_input_readiness_board",
        "stage": 25,
        "board_valid": True,
        "input_rows": len(rows),
        "category_counts": category_counts,
        "blocker_counts": blocker_counts,
        "completion_ready_rows": sum(1 for row in rows if row.get("completion_ready") is True),
        "missing_or_needs_more_info_rows": sum(1 for row in rows if row.get("completion_ready") is not True),
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
        "input_rows": report["input_rows"],
        "completion_ready_rows": report["completion_ready_rows"],
        "missing_or_needs_more_info_rows": report["missing_or_needs_more_info_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
