#!/usr/bin/env python3
"""Build a validated feature index for model-consumable cached features."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT_JSONL = AI_ROOT / "datasets" / "features" / "validated_feature_index.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "validated_feature_index_report.json"
PYROSETTA_FEATURES = AI_ROOT / "datasets" / "features" / "pyrosetta_verified_mutation_ddg_features.jsonl"
PYROSETTA_VALIDATION = AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_feature_validation_report.json"
PYROSETTA_CONCORDANCE = AI_ROOT / "datasets" / "features" / "pyrosetta_verified_mutation_ddg_concordance.jsonl"
PYROSETTA_CONCORDANCE_VALIDATION = AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_concordance_validation_report.json"
SITE_FEATURES = AI_ROOT / "datasets" / "features" / "mutation_structure_site_features.jsonl"
SITE_CANDIDATES = AI_ROOT / "datasets" / "features" / "verified_mutation_structure_mapping_candidates.jsonl"
SITE_VALIDATION = AI_ROOT / "reports" / "mutation_structure_site_feature_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: str | Path) -> str:
    p = Path(path)
    return str(p.relative_to(AI_ROOT)) if p.is_absolute() else str(p)


def build_msa_rows(created_at: str) -> list[dict[str, Any]]:
    manifest = load_json(AI_ROOT / "reports" / "msa_conservation_manifest.json")
    validation = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
    if validation.get("ready") is not True:
        return []
    validation_records = {row.get("uniprot_id"): row for row in validation.get("records") or []}
    rows = []
    for target in manifest.get("targets") or []:
        uniprot_id = target.get("uniprot_id")
        record = validation_records.get(uniprot_id) or {}
        if record.get("valid") is not True:
            continue
        rows.append({
            "created_at": created_at,
            "local_only": True,
            "feature_index_id": f"msa_conservation:{uniprot_id}",
            "feature_family": "msa_conservation",
            "entity_type": "uniprot_sequence",
            "uniprot_id": uniprot_id,
            "structure_id": None,
            "chain_id": None,
            "sequence_length": target.get("sequence_length"),
            "feature_path": rel(target.get("conservation_feature_path")),
            "feature_sha256": target.get("conservation_sha256"),
            "secondary_artifact_path": rel(target.get("msa_path")),
            "secondary_artifact_sha256": target.get("msa_sha256"),
            "source_database": manifest.get("source_database"),
            "database_version": manifest.get("database_version"),
            "validator_report": "reports/msa_conservation_cache_validation_report.json",
            "validator_ready": True,
            "validator_errors": [],
            "model_consumable": True,
            "training_label_source": False,
            "requires_human_review_before_label_use": True,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "MSA conservation cache feature only; not a wet-lab label or model-quality claim.",
        })
    return rows


def build_structure_rows(created_at: str) -> list[dict[str, Any]]:
    index_rows = load_jsonl(AI_ROOT / "datasets" / "features" / "reviewed_structure_graph_features.jsonl")
    validation = load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json")
    if validation.get("ready_for_coordinate_feature_use") is not True:
        return []
    valid_by_structure = {
        row.get("structure_id"): row for row in validation.get("records") or [] if row.get("valid") is True
    }
    rows = []
    for graph in index_rows:
        graph_path = graph.get("graph_path")
        if graph.get("structure_id") not in valid_by_structure:
            continue
        rows.append({
            "created_at": created_at,
            "local_only": True,
            "feature_index_id": f"structure_graph:{graph.get('structure_id')}:{graph.get('selected_chain_id')}",
            "feature_family": "structure_graph",
            "entity_type": "reviewed_structure_chain",
            "uniprot_id": graph.get("uniprot_id"),
            "structure_id": graph.get("structure_id"),
            "chain_id": graph.get("selected_chain_id"),
            "sequence_length": graph.get("node_count"),
            "feature_path": graph_path,
            "feature_sha256": graph.get("graph_sha256"),
            "secondary_artifact_path": None,
            "secondary_artifact_sha256": graph.get("input_structure_sha256"),
            "source_database": "reviewed_local_structure_cache",
            "database_version": "local_reviewed_chain_mapping",
            "validator_report": "reports/reviewed_structure_graph_validation_report.json",
            "validator_ready": True,
            "validator_errors": [],
            "model_consumable": True,
            "training_label_source": False,
            "requires_human_review_before_label_use": bool(graph.get("requires_mutation_numbering_review", True)),
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Reviewed chain coordinate graph feature only; does not prove mutation numbering or wet-lab effect.",
        })
    return rows


def build_pyrosetta_ddg_rows(created_at: str) -> list[dict[str, Any]]:
    validation = load_json(PYROSETTA_VALIDATION)
    concordance_validation = load_json(PYROSETTA_CONCORDANCE_VALIDATION)
    if validation.get("invalid_rows") != 0 or concordance_validation.get("invalid_rows") != 0:
        return []
    feature_rows = load_jsonl(PYROSETTA_FEATURES)
    concordance_by_candidate = {
        row.get("candidate_id"): row for row in load_jsonl(PYROSETTA_CONCORDANCE)
    }
    if not PYROSETTA_FEATURES.exists():
        return []
    feature_sha256 = sha256(PYROSETTA_FEATURES)
    rows = []
    for feature in feature_rows:
        if feature.get("quality_gate_passed") is not True:
            continue
        if feature.get("runtime_status") != "computed":
            continue
        if feature.get("structure_context_scope") != "near_full_length_context":
            continue
        execution_mode = feature.get("chain_execution_mode")
        if execution_mode == "multi_chain_context":
            concordance = concordance_by_candidate.get(feature.get("candidate_id")) or {}
            if concordance.get("quality_gate_passed") is not True:
                continue
        elif execution_mode != "deterministic_single_chain":
            continue
        rows.append({
            "created_at": created_at,
            "local_only": True,
            "feature_index_id": f"pyrosetta_ddg_reu_input:{feature.get('feature_id')}",
            "feature_family": "pyrosetta_ddg_reu_input",
            "entity_type": "mutation_structure_chain",
            "uniprot_id": feature.get("uniprot_id"),
            "structure_id": feature.get("executed_structure_id"),
            "source_structure_id": feature.get("source_structure_id"),
            "chain_id": feature.get("chain_id"),
            "sequence_length": feature.get("pose_total_residue"),
            "feature_path": rel(PYROSETTA_FEATURES),
            "feature_sha256": feature_sha256,
            "feature_record_id": feature.get("feature_id"),
            "feature_group_id": feature.get("ambiguity_group_id") or feature.get("candidate_id"),
            "group_execution_policy": (
                "preserve_all_matching_chains"
                if execution_mode == "multi_chain_context"
                else "deterministic_single_chain"
            ),
            "independent_training_sample": False,
            "secondary_artifact_path": None,
            "secondary_artifact_sha256": feature.get("structure_sha256"),
            "source_database": "local_pdb_with_pyrosetta",
            "database_version": "verified_mutations_v1",
            "validator_report": "reports/pyrosetta_verified_mutation_ddg_feature_validation_report.json",
            "validator_ready": True,
            "validator_errors": [],
            "model_consumable": True,
            "training_label_source": False,
            "requires_human_review_before_label_use": True,
            "manual_review_required": True,
            "ddg_units": "REU",
            "ddg_reu": feature.get("ddg_reu"),
            "quality_gate_passed": True,
            "chain_execution_mode": execution_mode,
            "source_executed_structure_match": feature.get("source_executed_structure_match"),
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": (
                "Quality-gated PyRosetta REU input feature only; not a wet-lab label, "
                "not a reviewed mapping decision, and not a model-quality claim."
            ),
        })
    return rows


def build_structure_site_rows(created_at: str) -> list[dict[str, Any]]:
    validation = load_json(SITE_VALIDATION)
    if validation.get("invalid_rows") != 0 or not SITE_FEATURES.exists():
        return []
    candidates = {
        row.get("candidate_id"): row
        for row in load_jsonl(SITE_CANDIDATES)
        if row.get("mapping_status") == "deterministic_input_candidate"
    }
    feature_sha256 = sha256(SITE_FEATURES)
    rows = []
    for feature in load_jsonl(SITE_FEATURES):
        candidate = candidates.get(feature.get("candidate_id")) or {}
        if feature.get("mapping_status") != "deterministic_input_candidate":
            continue
        rows.append({
            "created_at": created_at,
            "local_only": True,
            "feature_index_id": f"structure_site:{feature.get('feature_id')}",
            "feature_family": "structure_site",
            "entity_type": "mutation_structure_site",
            "uniprot_id": candidate.get("uniprot_id"),
            "structure_id": feature.get("structure_id"),
            "chain_id": feature.get("selected_chain_id"),
            "sequence_length": candidate.get("canonical_sequence_length"),
            "feature_path": rel(SITE_FEATURES),
            "feature_sha256": feature_sha256,
            "feature_record_id": feature.get("feature_id"),
            "secondary_artifact_path": candidate.get("actual_cache_path"),
            "secondary_artifact_sha256": candidate.get("structure_sha256"),
            "source_database": "local_verified_mutation_structure_cache",
            "database_version": "verified_mutation_structure_site_v1",
            "validator_report": "reports/mutation_structure_site_feature_validation_report.json",
            "validator_ready": True,
            "validator_errors": [],
            "model_consumable": True,
            "training_label_source": False,
            "requires_human_review_before_label_use": True,
            "manual_review_required": True,
            "mapping_status": feature.get("mapping_status"),
            "structure_context_scope": feature.get("structure_context_scope"),
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Deterministic mutation-site coordinate feature only; not a reviewed label, physics result, or model-quality claim.",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build validated feature index")
    parser.add_argument("--output-jsonl", type=Path, default=OUT_JSONL)
    parser.add_argument("--output-report", type=Path, default=OUT_REPORT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    rows = (
        build_msa_rows(created_at)
        + build_structure_rows(created_at)
        + build_pyrosetta_ddg_rows(created_at)
        + build_structure_site_rows(created_at)
    )
    family_counts: dict[str, int] = {}
    for row in rows:
        family = row["feature_family"]
        family_counts[family] = family_counts.get(family, 0) + 1
    pyrosetta_rows = [row for row in rows if row.get("feature_family") == "pyrosetta_ddg_reu_input"]
    pyrosetta_group_ids = {
        row.get("feature_group_id") for row in pyrosetta_rows if row.get("feature_group_id")
    }
    report = {
        "created_at": created_at,
        "local_only": True,
        "feature_rows": len(rows),
        "model_consumable_rows": sum(1 for row in rows if row["model_consumable"]),
        "training_label_source_rows": sum(1 for row in rows if row["training_label_source"]),
        "family_counts": family_counts,
        "pyrosetta_ddg_input_feature_rows": len(pyrosetta_rows),
        "pyrosetta_ddg_unique_mutation_groups": len(pyrosetta_group_ids),
        "pyrosetta_ddg_independent_training_sample_rows": sum(
            1 for row in pyrosetta_rows if row.get("independent_training_sample") is True
        ),
        "msa_cache_validation_ready": bool(load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json").get("ready")),
        "structure_graph_validation_ready": bool(load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json").get("ready_for_coordinate_feature_use")),
        "pyrosetta_ddg_validation_ready": (
            load_json(PYROSETTA_VALIDATION).get("invalid_rows") == 0
            and load_json(PYROSETTA_CONCORDANCE_VALIDATION).get("invalid_rows") == 0
        ),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "index": str(args.output_jsonl.relative_to(AI_ROOT)),
        "policy": "Validated feature index exposes only validator-ready cached features for model input contracts. It does not import labels, train models, approve model claims, or release.",
    }
    write_jsonl(args.output_jsonl, rows)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "feature_rows": report["feature_rows"],
        "family_counts": report["family_counts"],
        "safe_for_model_claim": False,
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
