#!/usr/bin/env python3
"""Summarize local training readiness across data sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "reports" / "data_lake_manifest.json"
QUALITY = AI_ROOT / "reports" / "data_quality_report.json"
OUT = AI_ROOT / "reports" / "training_readiness_report.json"
DOMAIN_STATE = AI_ROOT / "reports" / "domain_state_consistency_20260829.json"


def domain_architecture_state(path: Path = DOMAIN_STATE) -> dict:
    if not path.exists():
        return {"rows": None, "invalid_interval_rows": None, "usable_for_position_features": False}
    state = json.loads(path.read_text(encoding="utf-8"))
    totals = state.get("totals", {})
    return {
        "rows": totals.get("evidence"),
        "invalid_interval_rows": totals.get("unresolved"),
        "usable_for_position_features": state.get("consistency", {}).get("ok") is True
        and (totals.get("single_interval_usable", 0) + totals.get("multi_occurrence_usable", 0)) > 0,
    }


def msa_conservation_state(scaffold: dict, cache_validation: dict, runtime: dict) -> dict:
    """Resolve MSA feature readiness from the hash-validating cache report.

    The scaffold is an historical planning artifact and is not authoritative
    once a trusted cache has been validated against every target.
    """
    targets = cache_validation.get("target_rows_expected", scaffold.get("targets", 0))
    valid_rows = cache_validation.get("valid_rows", 0)
    invalid_rows = cache_validation.get("invalid_rows", 0)
    trusted = runtime.get("trusted_cache") if isinstance(runtime.get("trusted_cache"), dict) else {}
    ready = bool(
        cache_validation.get("ready") is True
        and isinstance(targets, int)
        and targets > 0
        and valid_rows == targets
        and invalid_rows == 0
        and not cache_validation.get("missing_targets")
        and trusted.get("ready") is True
        and trusted.get("present_conservation") == targets
    )
    return {
        "targets": targets,
        "present": valid_rows if ready else 0,
        "missing": 0 if ready else max(int(targets or 0) - int(valid_rows or 0), 0),
        "ready": ready,
        "source": "trusted_cache_validated" if ready else "scaffold_or_unvalidated_cache",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local training readiness report")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--quality", type=Path, default=QUALITY)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    quality = json.loads(args.quality.read_text(encoding="utf-8"))
    by_path = {item["path"]: item for item in manifest.get("artifacts", [])}
    label_rows = by_path.get("datasets/features/enzyme_mutation_labels.jsonl", {}).get("rows", 0)
    supervised_rows = by_path.get("datasets/curated/enzyme_mutation_training_table.jsonl", {}).get("rows", 0)
    enriched_supervised_rows = by_path.get("datasets/curated/enzyme_mutation_training_table_enriched.jsonl", {}).get("rows", 0)
    verified_supervised_rows = by_path.get("datasets/curated/enzyme_mutation_training_table_verified.jsonl", {}).get("rows", 0)
    repaired_strict_rows = by_path.get("datasets/curated/enzyme_mutation_supervised_repaired_verified.jsonl", {}).get("rows", 0)
    lipase_rows = by_path.get("datasets/features/lipase_features.jsonl", {}).get("rows", 0)
    training_rows = by_path.get("datasets/curated/training_table.jsonl", {}).get("rows", 0)
    feedback_rows = by_path.get("datasets/feedback/experiment_feedback_features.jsonl", {}).get("rows", 0)
    audit_rows = by_path.get("datasets/features/tool_audit_features.jsonl", {}).get("rows", 0)
    baseline_eval_path = AI_ROOT / "reports" / "supervised_mutation_baseline_eval.json"
    enriched_eval_path = AI_ROOT / "reports" / "supervised_mutation_enriched_baseline_eval.json"
    integrity_path = AI_ROOT / "reports" / "mutation_label_integrity_report.json"
    structure_cache_path = AI_ROOT / "reports" / "structure_cache_audit_report.json"
    multitask_path = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
    msa_path = AI_ROOT / "reports" / "msa_conservation_readiness_report.json"
    msa_cache_path = AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json"
    msa_runtime_path = AI_ROOT / "reports" / "msa_runtime_readiness_report.json"
    chain_path = AI_ROOT / "reports" / "structure_chain_mapping_backlog_readiness_report.json"
    feedback_path = AI_ROOT / "reports" / "experiment_feedback_readiness_report.json"
    provenance_path = AI_ROOT / "reports" / "label_provenance_audit_report.json"
    baseline_eval = json.loads(baseline_eval_path.read_text(encoding="utf-8")) if baseline_eval_path.exists() else {}
    enriched_eval = json.loads(enriched_eval_path.read_text(encoding="utf-8")) if enriched_eval_path.exists() else {}
    integrity = json.loads(integrity_path.read_text(encoding="utf-8")) if integrity_path.exists() else {}
    structure_cache = json.loads(structure_cache_path.read_text(encoding="utf-8")) if structure_cache_path.exists() else {}
    multitask = json.loads(multitask_path.read_text(encoding="utf-8")) if multitask_path.exists() else {}
    msa = json.loads(msa_path.read_text(encoding="utf-8")) if msa_path.exists() else {}
    msa_cache = json.loads(msa_cache_path.read_text(encoding="utf-8")) if msa_cache_path.exists() else {}
    msa_runtime = json.loads(msa_runtime_path.read_text(encoding="utf-8")) if msa_runtime_path.exists() else {}
    chain = json.loads(chain_path.read_text(encoding="utf-8")) if chain_path.exists() else {}
    feedback = json.loads(feedback_path.read_text(encoding="utf-8")) if feedback_path.exists() else {}
    provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.exists() else {}
    domain_state = domain_architecture_state()
    msa_state = msa_conservation_state(msa, msa_cache, msa_runtime)
    pdb_total = (structure_cache.get("totals") or {}).get("pdb_structures", 0)
    pdb_existing = structure_cache.get("pdb_sample_existing", 0)
    structure_scope = "sample_only" if pdb_total and pdb_existing < pdb_total else "full_cache"
    validation_accuracy = baseline_eval.get("splits", {}).get("validation", {}).get("accuracy")
    test_accuracy = baseline_eval.get("splits", {}).get("test", {}).get("accuracy")
    enriched_validation_accuracy = enriched_eval.get("splits", {}).get("validation", {}).get("accuracy")
    enriched_test_accuracy = enriched_eval.get("splits", {}).get("test", {}).get("accuracy")
    pipeline_ready = bool(quality.get("ready_for_training")) and label_rows >= 50 and supervised_rows >= 50
    strong_supervised_rows = repaired_strict_rows
    claim_eligible_rows = provenance.get("claim_eligible_rows", strong_supervised_rows)
    integrity_ready = claim_eligible_rows >= 100 and integrity.get("verified_ratio", 0) >= 0.5
    model_claim_ready = (
        pipeline_ready
        and integrity_ready
        and isinstance(validation_accuracy, (int, float))
        and isinstance(test_accuracy, (int, float))
        and validation_accuracy >= 0.55
        and test_accuracy >= 0.55
    )
    blockers: list[str] = []
    if not integrity_ready:
        blockers.append("mutation label numbering/provenance integrity is below supervised claim threshold")
    if provenance.get("synthetic_or_unreceipted_rows", 0):
        blockers.append("strict labels include synthetic or unreceipted stability rows; replace with real source receipts")
    if not structure_cache.get("coordinate_features_ready"):
        blockers.append("local structure cache is not ready for coordinate-level features")
    if not (
        isinstance(validation_accuracy, (int, float))
        and isinstance(test_accuracy, (int, float))
        and validation_accuracy >= 0.55
        and test_accuracy >= 0.55
    ):
        blockers.append("supervised pipeline is ready, but current non-leaky baseline is below model-quality threshold")
    if multitask.get("status") != "ready":
        blockers.append("multi-task head labels are incomplete for the five-head model")
    if not msa_state["ready"]:
        blockers.append(f"MSA conservation cache missing or unvalidated for {msa_state['missing']} of {msa_state['targets']} targets")
    if chain.get("remaining_unreviewed_rows", 0):
        blockers.append(f"structure chain mapping still needs {chain.get('remaining_unreviewed_rows')} human-reviewed rows")
    if not feedback.get("ready_for_training", False):
        blockers.append(f"experiment feedback has {feedback.get('reviewed_numbered_rows', 0)} reviewed rows but is not training-authorized")
    blockers.append("need structure/pocket/conservation/family features and real KWB wet-lab feedback before claiming predictive quality")
    report = {
        "ready_for_baseline_training": training_rows >= 10,
        "ready_for_supervised_training_pipeline": pipeline_ready,
        "ready_for_supervised_small_model_claim": model_claim_ready,
        "quality_score": quality.get("overall_score"),
        "rows": {
            "training_table": training_rows,
            "enzyme_mutation_labels": label_rows,
            "enzyme_mutation_training_table": supervised_rows,
            "enzyme_mutation_training_table_enriched": enriched_supervised_rows,
            "enzyme_mutation_training_table_verified": verified_supervised_rows,
            "enzyme_mutation_supervised_repaired_verified": repaired_strict_rows,
            "lipase_features": lipase_rows,
            "feedback_features": feedback_rows,
            "tool_audit_features": audit_rows,
        },
        "supervised_baseline": {
            "selected_strategy": baseline_eval.get("selected_strategy"),
            "validation_accuracy": validation_accuracy,
            "test_accuracy": test_accuracy,
            "candidate_validation_accuracy": baseline_eval.get("candidate_validation_accuracy"),
        },
        "enriched_supervised_baseline": {
            "selected_strategy": enriched_eval.get("selected_strategy"),
            "validation_accuracy": enriched_validation_accuracy,
            "test_accuracy": enriched_test_accuracy,
            "candidate_validation_accuracy": enriched_eval.get("candidate_validation_accuracy"),
        },
        "label_integrity": {
            "verified_rows": integrity.get("verified_rows"),
            "strict_supervised_rows": strong_supervised_rows,
            "claim_eligible_supervised_rows": claim_eligible_rows,
            "synthetic_or_unreceipted_rows": provenance.get("synthetic_or_unreceipted_rows"),
            "label_provenance_hard_gate_status": provenance.get("hard_gate_status"),
            "verified_ratio": integrity.get("verified_ratio"),
            "decision": integrity.get("decision"),
            "integrity_flag_counts": integrity.get("integrity_flag_counts"),
            "domain_architecture": domain_state,
            "pdb_paths": integrity.get("pdb_paths"),
        },
        "structure_cache": {
            "coordinate_features_ready": structure_cache.get("coordinate_features_ready"),
            "coordinate_features_scope": structure_scope,
            "full_cache_ready": structure_scope == "full_cache",
            "pdb_sample_existing": structure_cache.get("pdb_sample_existing"),
            "alphafold_sample_existing": structure_cache.get("alphafold_sample_existing"),
            "totals": structure_cache.get("totals"),
        },
        "multitask_training": multitask,
        "feature_streams": {
            "msa_conservation": msa_state,
            "structure_chain_mapping": {"worklist_rows": chain.get("worklist_rows"), "reviewed_rows": chain.get("reviewed_chain_mapping_rows"), "remaining_unreviewed_rows": chain.get("remaining_unreviewed_rows")},
            "experiment_feedback": {"local_rows": feedback.get("local_rows"), "reviewed_numbered_rows": feedback.get("reviewed_numbered_rows"), "ready_for_training": feedback.get("ready_for_training", False)},
        },
        "blockers": [] if model_claim_ready else blockers,
        "next_steps": [
            "repair mutation label numbering via UniProt version/isoform/literature mapping",
            "review 2 unresolved domain intervals via domain_unresolved_review_packet_20260829.json",
            "materialize full local PDB/mmCIF cache; current coordinate evidence is sample-only",
            "add structure-aware mutation features from uploaded/AlphaFold/ESMFold structures",
            "add sequence conservation and enzyme-family embeddings",
            "train GBDT or neural multi-task heads after feature enrichment",
            "connect real experiment feedback and tool audit tables when available",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "ready_for_supervised_training_pipeline": pipeline_ready,
        "ready_for_supervised_small_model_claim": model_claim_ready,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
