#!/usr/bin/env python3
"""Validate the model-consumable feature index."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INDEX = AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl"
REPORT = AI_ROOT / "reports" / "validated_feature_index_report.json"
OUT = AI_ROOT / "reports" / "validated_feature_index_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else AI_ROOT / path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_feature_file(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    feature_path = resolve(row.get("feature_path"))
    if not feature_path or not feature_path.exists():
        return ["feature_file_missing"]
    expected_sha = str(row.get("feature_sha256") or "")
    if expected_sha and sha256(feature_path) != expected_sha.lower():
        errors.append("feature_sha256_mismatch")
    if row.get("feature_family") == "structure_site":
        try:
            feature_rows = load_jsonl(feature_path)
        except Exception:
            return errors + ["structure_site_feature_jsonl_not_parseable"]
        matched = [item for item in feature_rows if item.get("feature_id") == row.get("feature_record_id")]
        if len(matched) != 1:
            errors.append("structure_site_feature_record_not_unique")
        elif matched[0].get("safe_for_model_claim") is not False or matched[0].get("training_label") is not False:
            errors.append("structure_site_safety_flags_invalid")
        return errors
    if row.get("feature_family") == "pyrosetta_ddg_reu_input":
        try:
            feature_rows = load_jsonl(feature_path)
        except Exception:
            return errors + ["pyrosetta_feature_jsonl_not_parseable"]
        matched = [
            item for item in feature_rows
            if item.get("feature_id") == row.get("feature_record_id")
        ]
        if len(matched) != 1:
            return errors + ["pyrosetta_feature_record_not_unique"]
        feature = matched[0]
        if feature.get("quality_gate_passed") is not True:
            errors.append("pyrosetta_quality_gate_not_passed")
        if feature.get("runtime_status") != "computed":
            errors.append("pyrosetta_runtime_not_computed")
        if feature.get("ddg_units") != "REU":
            errors.append("pyrosetta_ddg_units_not_reu")
        if feature.get("safe_for_training_import") is not False:
            errors.append("pyrosetta_training_import_not_false")
        if feature.get("safe_for_model_claim") is not False:
            errors.append("pyrosetta_model_claim_not_false")
        if feature.get("release_ready") is not False:
            errors.append("pyrosetta_release_not_false")
        if feature.get("structure_context_scope") != "near_full_length_context":
            errors.append("pyrosetta_structure_context_not_near_full_length")
        if row.get("feature_group_id") != (feature.get("ambiguity_group_id") or feature.get("candidate_id")):
            errors.append("pyrosetta_feature_group_mismatch")
        expected_policy = (
            "preserve_all_matching_chains"
            if feature.get("chain_execution_mode") == "multi_chain_context"
            else "deterministic_single_chain"
        )
        if row.get("group_execution_policy") != expected_policy:
            errors.append("pyrosetta_group_execution_policy_mismatch")
        if row.get("independent_training_sample") is not False:
            errors.append("pyrosetta_independent_training_sample_must_be_false")
        return errors
    try:
        payload = json.loads(feature_path.read_text(encoding="utf-8"))
    except Exception:
        return errors + ["feature_json_not_parseable"]
    if row.get("feature_family") == "msa_conservation":
        scores = payload.get("position_conservation")
        if not isinstance(scores, list):
            errors.append("msa_position_conservation_missing")
        elif row.get("sequence_length") and len(scores) != int(row["sequence_length"]):
            errors.append("msa_position_conservation_length_mismatch")
        elif any(not isinstance(value, (int, float)) or not 0 <= float(value) <= 1 for value in scores):
            errors.append("msa_position_conservation_value_invalid")
    if row.get("feature_family") == "structure_graph":
        nodes = payload.get("nodes")
        edges = payload.get("edges")
        if not isinstance(nodes, list) or not nodes:
            errors.append("structure_graph_nodes_missing")
        if not isinstance(edges, list):
            errors.append("structure_graph_edges_missing")
        if payload.get("safe_for_model_claim") is not False:
            errors.append("structure_graph_model_claim_not_false")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate validated feature index")
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.index)
    report = load_json(args.report)
    msa_validation = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
    graph_validation = load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json")
    pyrosetta_validation = load_json(AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_feature_validation_report.json")
    pyrosetta_concordance_validation = load_json(AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_concordance_validation_report.json")
    failures: list[dict[str, Any]] = []
    feature_ids = [row.get("feature_index_id") for row in rows]
    fail_if(report.get("feature_rows") != len(rows), failures, "feature_rows_match_index", report.get("feature_rows"), len(rows))
    fail_if(len(feature_ids) != len(set(feature_ids)), failures, "feature_index_ids_unique", feature_ids, "unique")
    fail_if(report.get("training_label_source_rows") != 0, failures, "training_label_source_rows_zero", report.get("training_label_source_rows"), 0)
    fail_if(report.get("safe_for_training_import") is not False, failures, "report_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "report_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "report_release_ready_false", report.get("release_ready"), False)

    for idx, row in enumerate(rows):
        family = row.get("feature_family")
        if family == "msa_conservation":
            fail_if(msa_validation.get("ready") is not True, failures, "msa_validation_ready", {"index": idx, "observed": msa_validation.get("ready")}, True)
        elif family == "structure_graph":
            fail_if(graph_validation.get("ready_for_coordinate_feature_use") is not True, failures, "structure_graph_validation_ready", {"index": idx, "observed": graph_validation.get("ready_for_coordinate_feature_use")}, True)
        elif family == "pyrosetta_ddg_reu_input":
            fail_if(pyrosetta_validation.get("invalid_rows") != 0, failures, "pyrosetta_feature_validation_clean", {"index": idx, "observed": pyrosetta_validation.get("invalid_rows")}, 0)
            fail_if(pyrosetta_concordance_validation.get("invalid_rows") != 0, failures, "pyrosetta_concordance_validation_clean", {"index": idx, "observed": pyrosetta_concordance_validation.get("invalid_rows")}, 0)
            fail_if(row.get("quality_gate_passed") is not True, failures, "pyrosetta_index_quality_gate_true", {"index": idx, "observed": row.get("quality_gate_passed")}, True)
            fail_if(not row.get("feature_group_id"), failures, "pyrosetta_feature_group_present", {"index": idx, "observed": row.get("feature_group_id")}, "non-empty group id")
            fail_if(row.get("independent_training_sample") is not False, failures, "pyrosetta_not_independent_training_sample", {"index": idx, "observed": row.get("independent_training_sample")}, False)
        elif family == "structure_site":
            fail_if(row.get("manual_review_required") is not True, failures, "structure_site_manual_review_required", {"index": idx, "observed": row.get("manual_review_required")}, True)
        else:
            failures.append({"check": "feature_family_allowed", "index": idx, "observed": family, "expected": ["msa_conservation", "structure_graph", "pyrosetta_ddg_reu_input", "structure_site"]})
        fail_if(row.get("model_consumable") is not True, failures, "row_model_consumable_true", {"index": idx, "observed": row.get("model_consumable")}, True)
        fail_if(row.get("training_label_source") is not False, failures, "row_training_label_source_false", {"index": idx, "observed": row.get("training_label_source")}, False)
        fail_if(row.get("safe_for_training_import") is not False, failures, "row_training_import_false", {"index": idx, "observed": row.get("safe_for_training_import")}, False)
        fail_if(row.get("safe_for_model_claim") is not False, failures, "row_model_claim_false", {"index": idx, "observed": row.get("safe_for_model_claim")}, False)
        fail_if(row.get("release_ready") is not False, failures, "row_release_ready_false", {"index": idx, "observed": row.get("release_ready")}, False)
        for error in validate_feature_file(row):
            failures.append({"check": "feature_file_valid", "index": idx, "feature_index_id": row.get("feature_index_id"), "observed": error, "expected": "valid feature artifact"})
        secondary_path = resolve(row.get("secondary_artifact_path"))
        if secondary_path:
            fail_if(not secondary_path.exists(), failures, "secondary_artifact_exists", {"index": idx, "observed": row.get("secondary_artifact_path")}, "existing file")
            expected_secondary_sha = str(row.get("secondary_artifact_sha256") or "")
            if secondary_path.exists() and expected_secondary_sha and sha256(secondary_path) != expected_secondary_sha.lower():
                failures.append({"check": "secondary_artifact_sha256_match", "index": idx, "observed": row.get("secondary_artifact_path"), "expected": expected_secondary_sha})

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "feature_rows": len(rows),
        "model_consumable_rows": sum(1 for row in rows if row.get("model_consumable") is True),
        "training_label_source_rows": sum(1 for row in rows if row.get("training_label_source") is True),
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Feature index validation only approves cached features for model input contracts. It does not authorize training import, model claims, or release.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "feature_rows": validation["feature_rows"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
