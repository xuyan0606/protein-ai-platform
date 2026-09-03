#!/usr/bin/env python3
"""Validate PyRosetta verified-mutation ddG input features remain fail-closed."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
FEATURES = AI_ROOT / "datasets" / "features" / "pyrosetta_verified_mutation_ddg_features.jsonl"
REPORT = AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_feature_validation_report.json"
DDG_ABS_SANITY_LIMIT_REU = 20.0
TOTAL_SCORE_SANITY_LIMIT_REU = 5000.0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("candidate_id", "record_id", "structure_id", "chain_id", "mutation"):
        if not row.get(field):
            errors.append(f"{field}_missing")
    for field in ("source_structure_id", "executed_structure_id"):
        if not row.get(field):
            errors.append(f"{field}_missing")
    if not isinstance(row.get("source_executed_structure_match"), bool):
        errors.append("source_executed_structure_match_missing")
    if row.get("structure_context_scope") not in {"near_full_length_context", "partial_domain_context"}:
        errors.append("structure_context_scope_invalid")
    if not isinstance(row.get("hetero_residue_names_observed"), list):
        errors.append("hetero_residue_names_missing")
    if not isinstance(row.get("ligand_or_nonprotein_context_present"), bool):
        errors.append("ligand_context_flag_missing")
    if row.get("ligand_handling_policy") != "ignore_unrecognized_res_true":
        errors.append("ligand_handling_policy_invalid")
    if row.get("ligand_modeling_complete") is not False:
        errors.append("ligand_modeling_complete_must_be_false")
    if int(row.get("pose_position") or 0) <= 0:
        errors.append("pose_position_missing")
    if row.get("ddg_units") != "REU":
        errors.append("ddg_units_not_reu")
    if row.get("negative_ddg_is_stabilizing") is not True:
        errors.append("negative_direction_missing")
    numeric_values = ("wild_score_reu", "mutant_score_reu", "ddg_reu", "ddg_abs_reu")
    for field in numeric_values:
        value = row.get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            errors.append(f"{field}_nonfinite")
    if isinstance(row.get("ddg_reu"), (int, float)) and isinstance(row.get("ddg_abs_reu"), (int, float)):
        if abs(abs(float(row["ddg_reu"])) - float(row["ddg_abs_reu"])) > 1e-9:
            errors.append("ddg_abs_mismatch")
    if row.get("runtime_status") != "computed":
        errors.append("runtime_status_not_computed")
    if row.get("score_quality_status") not in {"quality_passed", "quality_blocked"}:
        errors.append("score_quality_status_invalid")
    if not isinstance(row.get("score_quality_reasons"), list):
        errors.append("score_quality_reasons_missing")
    if not isinstance(row.get("quality_gate_passed"), bool):
        errors.append("quality_gate_passed_missing")
    if row.get("quality_gate_passed") is True and abs(float(row.get("ddg_reu") or 0)) > DDG_ABS_SANITY_LIMIT_REU:
        errors.append("quality_gate_passed_with_ddg_outlier")
    if abs(float(row.get("ddg_reu") or 0)) > DDG_ABS_SANITY_LIMIT_REU and row.get("quality_gate_passed") is not False:
        errors.append("ddg_outlier_not_blocked")
    for field in ("wild_score_reu", "mutant_score_reu"):
        if abs(float(row.get(field) or 0)) > TOTAL_SCORE_SANITY_LIMIT_REU:
            expected_reason = f"{field.split('_')[0]}_total_score_sanity_warning"
            if expected_reason not in row.get("score_quality_reasons", []):
                errors.append(f"{field}_warning_missing")
    if row.get("manual_review_required") is not True:
        errors.append("manual_review_missing")
    if row.get("feature_scope") not in {
        "computational_physics_input_only",
        "computational_physics_input_candidate_multi_chain_context",
    }:
        errors.append("feature_scope_invalid")
    if row.get("chain_execution_mode") not in {"deterministic_single_chain", "multi_chain_context"}:
        errors.append("chain_execution_mode_invalid")
    for field in ("training_label", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
        if row.get(field) is not False:
            errors.append(f"{field}_must_be_false")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PyRosetta ddG input features")
    parser.add_argument("--features", type=Path, default=FEATURES)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.features)
    records = []
    counts: Counter[str] = Counter()
    for row in rows:
        errors = validate(row)
        counts.update(errors)
        records.append({"feature_id": row.get("feature_id"), "valid": not errors, "errors": errors})
    valid_rows = sum(1 for row in records if row["valid"])
    quality_passed_rows = sum(1 for row in rows if row.get("quality_gate_passed") is True)
    quality_blocked_rows = sum(1 for row in rows if row.get("quality_gate_passed") is False)
    quality_reason_counts: Counter[str] = Counter()
    quality_blocked_records = []
    for row in rows:
        reasons = row.get("score_quality_reasons") if isinstance(row.get("score_quality_reasons"), list) else []
        quality_reason_counts.update(str(reason) for reason in reasons)
        if row.get("quality_gate_passed") is False:
            quality_blocked_records.append(
                {
                    "feature_id": row.get("feature_id"),
                    "candidate_id": row.get("candidate_id"),
                    "mutation": row.get("mutation"),
                    "chain_id": row.get("chain_id"),
                    "ddg_reu": row.get("ddg_reu"),
                    "ddg_abs_reu": row.get("ddg_abs_reu"),
                    "score_quality_status": row.get("score_quality_status"),
                    "score_quality_reasons": reasons,
                }
            )
    report = {
        "feature_rows": len(rows),
        "valid_rows": valid_rows,
        "invalid_rows": len(rows) - valid_rows,
        "quality_passed_rows": quality_passed_rows,
        "quality_blocked_rows": quality_blocked_rows,
        "quality_blocked_reason_counts": dict(quality_reason_counts),
        "quality_blocked_records": quality_blocked_records,
        "error_counts": dict(counts),
        "quality_gate_status": "blocked" if quality_blocked_rows else "passed",
        "quality_gate_policy": {
            "ddg_abs_sanity_limit_reu": DDG_ABS_SANITY_LIMIT_REU,
            "total_score_sanity_limit_reu": TOTAL_SCORE_SANITY_LIMIT_REU,
            "scientific_validity_claim": False,
        },
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Features remain manual-review computational inputs, not training labels or claims.",
        "records": records,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "feature_rows": report["feature_rows"],
            "valid_rows": report["valid_rows"],
            "invalid_rows": report["invalid_rows"],
            "quality_passed_rows": report["quality_passed_rows"],
            "quality_blocked_rows": report["quality_blocked_rows"],
            "quality_gate_status": report["quality_gate_status"],
            "output": str(args.report),
        },
        ensure_ascii=False,
    ))
    return 0 if report["invalid_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
