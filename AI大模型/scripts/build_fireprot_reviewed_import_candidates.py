#!/usr/bin/env python3
"""Build reviewed FireProt import candidates from validated dedup decisions.

This remains one step before supervised training import. It creates auditable
candidate rows only for human-reviewed duplicate decisions that the validator
marks approved_for_import_candidate.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "curation" / "fireprot_curated_dedup_aggregation_candidates.jsonl"
DECISIONS = AI_ROOT / "datasets" / "curation" / "fireprot_dedup_review_decisions.jsonl"
VALIDATION = AI_ROOT / "reports" / "fireprot_dedup_review_decision_validation_report.json"
OUTPUT = AI_ROOT / "datasets" / "curation" / "fireprot_reviewed_import_candidates.jsonl"
REPORT = AI_ROOT / "reports" / "fireprot_reviewed_import_candidate_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def selected_source_rows(candidate: dict[str, Any], mapping_ids: list[str]) -> list[dict[str, Any]]:
    selected = set(mapping_ids)
    return [
        row
        for row in candidate.get("source_rows") or []
        if row.get("mapping_id") in selected
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FireProt reviewed import candidates")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--validation", type=Path, default=VALIDATION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    candidates = load_jsonl(args.candidates)
    decisions = load_jsonl(args.decisions)
    validation = load_json(args.validation)
    candidate_by_id = {str(row.get("dedup_candidate_id")): row for row in candidates}
    decision_by_id = {str(row.get("dedup_candidate_id")): row for row in decisions}
    approved_ids = [
        str(row.get("dedup_candidate_id"))
        for row in validation.get("records") or []
        if row.get("approved_for_import_candidate") is True
    ]

    import_candidates: list[dict[str, Any]] = []
    skipped_missing_decision = []
    skipped_missing_candidate = []
    for candidate_id in approved_ids:
        candidate = candidate_by_id.get(candidate_id)
        decision = decision_by_id.get(candidate_id)
        if not candidate:
            skipped_missing_candidate.append(candidate_id)
            continue
        if not decision:
            skipped_missing_decision.append(candidate_id)
            continue

        selected_mapping_ids = [str(value) for value in decision.get("selected_source_mapping_ids") or []]
        import_candidates.append({
            "reviewed_import_candidate_id": f"fireprot-reviewed-import-{candidate_id}",
            "dedup_candidate_id": candidate_id,
            "mutation_key": candidate.get("mutation_key"),
            "uniprot_id": candidate.get("uniprot_id"),
            "mutation": candidate.get("mutation"),
            "wild_type": candidate.get("wild_type"),
            "mutant": candidate.get("mutant"),
            "decision": decision.get("decision"),
            "approved_label_ddg_kcal_mol": decision.get("approved_label_ddg_kcal_mol"),
            "approved_assay_signature": decision.get("approved_assay_signature"),
            "selected_source_mapping_ids": selected_mapping_ids,
            "selected_source_rows": selected_source_rows(candidate, selected_mapping_ids),
            "source_file_sha256s": candidate.get("source_file_sha256s"),
            "review_basis": decision.get("review_basis"),
            "reviewer": decision.get("reviewer"),
            "reviewed_at": decision.get("reviewed_at"),
            "reviewed_import_receipt": decision.get("reviewed_import_receipt"),
            "license_scope": decision.get("license_scope"),
            "numbering_reviewed": decision.get("numbering_reviewed") is True,
            "source_provenance_checked": decision.get("source_provenance_checked") is True,
            "ready_for_supervised_import_candidate": True,
            "ready_for_training_import": False,
            "claim_eligible_now": False,
            "remaining_blockers": [
                "formal_supervised_import_not_authorized",
                "not_written_to_kwb_supervised_schema",
                "training_release_gate_not_approved",
            ],
            "policy": (
                "Reviewed import candidate only. This is not yet a KWB supervised "
                "training row and cannot support model-quality claims."
            ),
        })

    write_jsonl(args.output, import_candidates)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "candidates": str(args.candidates),
        "decisions": str(args.decisions),
        "validation": str(args.validation),
        "output": str(args.output),
        "dedup_candidate_rows": len(candidates),
        "decision_rows": len(decisions),
        "validation_approved_for_import_candidate_rows": len(approved_ids),
        "reviewed_import_candidate_rows": len(import_candidates),
        "skipped_missing_decision_ids": skipped_missing_decision[:50],
        "skipped_missing_candidate_ids": skipped_missing_candidate[:50],
        "ready_for_training_import_rows": 0,
        "claim_eligible_rows_now": 0,
        "safe_for_model_claim": False,
        "policy": (
            "Reviewed import candidates remain blocked from training until a "
            "separate formal supervised import is explicitly authorized."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision_rows": report["decision_rows"],
        "validation_approved_for_import_candidate_rows": report["validation_approved_for_import_candidate_rows"],
        "reviewed_import_candidate_rows": report["reviewed_import_candidate_rows"],
        "ready_for_training_import_rows": report["ready_for_training_import_rows"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
