#!/usr/bin/env python3
"""Validate deterministic structure mapping candidates without promoting them."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INDEX = AI_ROOT / "datasets" / "features" / "verified_mutation_structure_mapping_candidates.jsonl"
REPORT = AI_ROOT / "reports" / "verified_mutation_structure_mapping_candidate_validation_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = row.get("mapping_status")
    if not row.get("source_structure_id"):
        errors.append("source_structure_id_missing")
    if not row.get("executed_structure_id"):
        errors.append("executed_structure_id_missing")
    if not isinstance(row.get("source_executed_structure_match"), bool):
        errors.append("source_executed_structure_match_missing")
    if row.get("structure_context_scope") not in {"near_full_length_context", "partial_domain_context", "unknown"}:
        errors.append("structure_context_scope_invalid")
    if not isinstance(row.get("hetero_residue_names_observed"), list):
        errors.append("hetero_residue_names_missing")
    if not isinstance(row.get("ligand_or_nonprotein_context_present"), bool):
        errors.append("ligand_context_flag_missing")
    if row.get("ligand_handling_policy") != "ignore_unrecognized_res_true":
        errors.append("ligand_handling_policy_invalid")
    if row.get("ligand_modeling_complete") is not False:
        errors.append("ligand_modeling_complete_must_be_false")
    if status == "deterministic_input_candidate":
        if not row.get("selected_chain_id"):
            errors.append("selected_chain_missing")
        if row.get("residue_present") is not True:
            errors.append("residue_present_not_true")
        if row.get("wt_residue_match") is not True:
            errors.append("wt_match_not_true")
        if row.get("pdb_observed_residue_one_letter") != row.get("wild_type"):
            errors.append("observed_wt_mismatch")
        if int(row.get("pose_position") or 0) <= 0:
            errors.append("pose_position_missing")
        if float(row.get("alignment_identity") or 0) < 0.9:
            errors.append("alignment_identity_below_0_9")
        if row.get("usable_as_physics_input_feature") is not True:
            errors.append("physics_input_flag_missing")
        if row.get("structure_context_scope") == "unknown":
            errors.append("structure_context_scope_missing")
    if row.get("training_label") is not False:
        errors.append("training_label_must_be_false")
    if row.get("safe_for_model_claim") is not False:
        errors.append("safe_for_model_claim_must_be_false")
    if row.get("release_ready") is not False:
        errors.append("release_ready_must_be_false")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate verified mutation structure mapping candidates")
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.index)
    records = []
    counts: Counter[str] = Counter()
    for row in rows:
        errors = validate(row)
        counts.update(errors)
        records.append(
            {
                "candidate_id": row.get("candidate_id"),
                "mapping_status": row.get("mapping_status"),
                "valid": not errors,
                "errors": errors,
            }
        )
    valid_rows = sum(1 for record in records if record["valid"])
    report = {
        "input_rows": len(rows),
        "valid_rows": valid_rows,
        "invalid_rows": len(rows) - valid_rows,
        "error_counts": dict(counts),
        "deterministic_candidate_rows": sum(
            1 for row in rows if row.get("mapping_status") == "deterministic_input_candidate"
        ),
        "safe_for_model_claim": False,
        "training_import_eligible_rows": 0,
        "policy": "Validation proves only candidate-record integrity; it does not approve human review or model use.",
        "records": records,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "input_rows": report["input_rows"],
            "valid_rows": report["valid_rows"],
            "invalid_rows": report["invalid_rows"],
            "deterministic_candidate_rows": report["deterministic_candidate_rows"],
            "output": str(args.report),
        },
        ensure_ascii=False,
    ))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
