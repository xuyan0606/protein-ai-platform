#!/usr/bin/env python3
"""Compute auditable PyRosetta ddG features for deterministic mapping candidates.

All outputs are computational input features in REU. They are not wet-lab
labels, and this script never changes training or release eligibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_python_module_discovery import add_local_module_paths


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "features" / "verified_mutation_structure_mapping_candidates.jsonl"
OUT_DIR = AI_ROOT / "cache" / "advanced_features" / "physical_ddg" / "pyrosetta" / "verified_mutations_v1"
OUT = AI_ROOT / "datasets" / "features" / "pyrosetta_verified_mutation_ddg_features.jsonl"
REPORT = AI_ROOT / "reports" / "pyrosetta_verified_mutation_ddg_feature_report.json"
REQUIRED_ARTIFACTS = ("parameters.json", "input_mapping.sha256", "ddg_features.jsonl", "runtime.log")
DDG_ABS_SANITY_LIMIT_REU = 20.0
TOTAL_SCORE_SANITY_LIMIT_REU = 5000.0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build PyRosetta ddG input features")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--random-seed", type=int, default=20260803)
    args = parser.parse_args()

    input_path = args.input if args.input.is_absolute() else AI_ROOT / args.input
    output_path = args.output if args.output.is_absolute() else AI_ROOT / args.output
    output_dir = args.output_dir if args.output_dir.is_absolute() else AI_ROOT / args.output_dir
    report_path = args.report if args.report.is_absolute() else AI_ROOT / args.report
    candidates: list[dict[str, Any]] = []
    for row in load_jsonl(input_path):
        if row.get("mapping_status") == "deterministic_input_candidate" and row.get("usable_as_physics_input_feature") is True:
            candidates.append({**row, "chain_execution_mode": "deterministic_single_chain"})
        elif row.get("mapping_status") == "blocked_ambiguous_multiple_chains":
            for chain in row.get("chain_mapping_candidates") or []:
                if chain.get("wt_match") is True and int(chain.get("pose_position") or 0) > 0:
                    candidates.append(
                        {
                            **row,
                            "selected_chain_id": chain.get("chain_id"),
                            "pdb_author_residue_number": chain.get("author_residue_number"),
                            "pdb_insertion_code": chain.get("insertion_code"),
                            "pdb_observed_residue_one_letter": chain.get("observed_residue_one_letter"),
                            "alignment_identity": chain.get("alignment_identity"),
                            "alignment_observed_coverage": chain.get("observed_coverage"),
                            "pose_position": chain.get("pose_position"),
                            "chain_execution_mode": "multi_chain_context",
                        }
                    )

    output_dir.mkdir(parents=True, exist_ok=True)
    parameters = {
        "backend": "pyrosetta",
        "protocol": "fa_scorefxn_single_mutation_feature",
        "input": rel(input_path),
        "input_sha256": sha256(input_path) if input_path.exists() else None,
        "random_seed": args.random_seed,
        "constant_seed": True,
        "pyrosetta_init_options": "-mute all -ignore_unrecognized_res true -constant_seed",
        "ddg_units": "REU",
        "negative_ddg_is_stabilizing": True,
        "quality_gate": {
            "ddg_abs_sanity_limit_reu": DDG_ABS_SANITY_LIMIT_REU,
            "total_score_sanity_limit_reu": TOTAL_SCORE_SANITY_LIMIT_REU,
            "policy": (
                "Heuristic runtime sanity checks only; thresholds do not establish "
                "scientific validity or convert REU into a wet-lab label."
            ),
        },
        "output_scope": "computational_input_feature_only",
        "training_label": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    (output_dir / "parameters.json").write_text(
        json.dumps(parameters, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "input_mapping.sha256").write_text(
        (parameters["input_sha256"] or "") + "\n", encoding="utf-8"
    )

    runtime_log: dict[str, Any] = {
        "python_executable": sys.executable,
        "candidate_rows": len(candidates),
        "errors": [],
    }
    results: list[dict[str, Any]] = []
    try:
        add_local_module_paths()
        import pyrosetta  # type: ignore
        from pyrosetta.toolbox.mutants import mutate_residue  # type: ignore

        pyrosetta.init(f"-mute all -ignore_unrecognized_res true -constant_seed -jran {args.random_seed}")
        scorefxn = pyrosetta.get_fa_scorefxn()
        runtime_log.update(
            {
                "pyrosetta_init_executed": True,
                "pyrosetta_file": getattr(pyrosetta, "__file__", None),
                "pyrosetta_version": getattr(pyrosetta, "__version__", None),
            }
        )
        pose_cache: dict[str, Any] = {}
        pose_errors: dict[str, str] = {}
        for candidate in candidates:
            structure_path = AI_ROOT / str(candidate["actual_cache_path"])
            try:
                pose = pose_cache.get(str(structure_path))
                if pose is None and str(structure_path) not in pose_errors:
                    try:
                        pose = pyrosetta.pose_from_pdb(str(structure_path))
                        pose_cache[str(structure_path)] = pose
                    except Exception as exc:
                        pose_errors[str(structure_path)] = f"{type(exc).__name__}: {exc}"
                if pose is None:
                    raise RuntimeError(pose_errors.get(str(structure_path), "pose_load_failed"))
                pose_position = int(candidate["pose_position"])
                observed_wt = pose.residue(pose_position).name1()
                expected_wt = str(candidate["wild_type"])
                if observed_wt != expected_wt:
                    raise RuntimeError(f"pose WT mismatch: {observed_wt} != {expected_wt}")
                wild_score = float(scorefxn(pose))
                mutant_pose = pose.clone()
                mutate_residue(mutant_pose, pose_position, str(candidate["mutant"]))
                mutant_score = float(scorefxn(mutant_pose))
                ddg_reu = mutant_score - wild_score
                quality_reasons: list[str] = []
                if not all(math.isfinite(value) for value in (wild_score, mutant_score, ddg_reu)):
                    quality_reasons.append("nonfinite_score")
                if math.isfinite(ddg_reu) and abs(ddg_reu) > DDG_ABS_SANITY_LIMIT_REU:
                    quality_reasons.append("ddg_abs_gt_20_reu")
                if math.isfinite(wild_score) and abs(wild_score) > TOTAL_SCORE_SANITY_LIMIT_REU:
                    quality_reasons.append("wild_total_score_sanity_warning")
                if math.isfinite(mutant_score) and abs(mutant_score) > TOTAL_SCORE_SANITY_LIMIT_REU:
                    quality_reasons.append("mutant_total_score_sanity_warning")
                quality_gate_passed = not any(
                    reason in {"nonfinite_score", "ddg_abs_gt_20_reu"}
                    for reason in quality_reasons
                )
                results.append(
                    {
                        "feature_id": (
                            f"pyrosetta::{candidate['candidate_id']}::"
                            f"{candidate.get('executed_structure_id') or candidate['structure_id']}::"
                            f"{candidate['selected_chain_id']}"
                        ),
                        "candidate_id": candidate["candidate_id"],
                        "source_candidate_id": candidate["candidate_id"],
                        "ambiguity_group_id": (
                            candidate["candidate_id"]
                            if candidate["chain_execution_mode"] == "multi_chain_context"
                            else None
                        ),
                        "record_id": candidate["record_id"],
                        "uniprot_id": candidate["uniprot_id"],
                        "structure_id": candidate["structure_id"],
                        "source_structure_id": candidate.get("source_structure_id"),
                        "executed_structure_id": candidate.get("executed_structure_id"),
                        "source_executed_structure_match": candidate.get("source_executed_structure_match"),
                        "structure_sha256": candidate.get("structure_sha256_observed"),
                        "chain_id": candidate["selected_chain_id"],
                        "mutation": candidate["mutation"],
                        "pdb_author_residue_number": candidate["pdb_author_residue_number"],
                        "pdb_insertion_code": candidate["pdb_insertion_code"],
                        "pose_position": pose_position,
                        "chain_execution_mode": candidate["chain_execution_mode"],
                        "mapping_status": candidate.get("mapping_status"),
                        "structure_context_scope": candidate.get("structure_context_scope"),
                        "alignment_observed_coverage": candidate.get("alignment_observed_coverage"),
                        "hetero_residue_names_observed": candidate.get("hetero_residue_names_observed") or [],
                        "ligand_or_nonprotein_context_present": bool(
                            candidate.get("ligand_or_nonprotein_context_present")
                        ),
                        "ligand_handling_policy": candidate.get("ligand_handling_policy"),
                        "ligand_modeling_complete": False,
                        "wild_type": observed_wt,
                        "mutant": candidate["mutant"],
                        "wild_score_reu": wild_score,
                        "mutant_score_reu": mutant_score,
                        "ddg_reu": ddg_reu,
                        "ddg_abs_reu": abs(ddg_reu) if math.isfinite(ddg_reu) else None,
                        "ddg_units": "REU",
                        "negative_ddg_is_stabilizing": True,
                        "runtime_status": "computed",
                        "pose_total_residue": int(pose.total_residue()),
                        "score_quality_status": "quality_passed" if quality_gate_passed else "quality_blocked",
                        "score_quality_reasons": quality_reasons,
                        "quality_gate_passed": quality_gate_passed,
                        "quality_gate_policy": {
                            "ddg_abs_sanity_limit_reu": DDG_ABS_SANITY_LIMIT_REU,
                            "total_score_sanity_limit_reu": TOTAL_SCORE_SANITY_LIMIT_REU,
                            "scientific_validity_claim": False,
                        },
                        "manual_review_required": True,
                        "feature_scope": (
                            "computational_physics_input_candidate_multi_chain_context"
                            if candidate["chain_execution_mode"] == "multi_chain_context"
                            else "computational_physics_input_only"
                        ),
                        "training_label": False,
                        "safe_for_training_import": False,
                        "safe_for_model_claim": False,
                        "release_ready": False,
                        "limitations": [
                            "single-structure, single-score-function computational feature",
                            "REU is not a wet-lab kcal/mol label",
                            "requires downstream scientific review before experimental prioritization",
                        ],
                    }
                )
            except Exception as exc:
                runtime_log["errors"].append(
                    {"candidate_id": candidate.get("candidate_id"), "error": f"{type(exc).__name__}: {exc}"}
                )
    except Exception:
        runtime_log["fatal_error"] = traceback.format_exc()
        runtime_log["pyrosetta_init_executed"] = False

    write_jsonl(output_path, results)
    (output_dir / "ddg_features.jsonl").write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")
    runtime_log["ddg_protocol_executed"] = bool(results)
    runtime_log["computed_rows"] = len(results)
    (output_dir / "runtime.log").write_text(
        json.dumps(runtime_log, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifact_sha256 = {rel(output_dir / name): sha256(output_dir / name) for name in REQUIRED_ARTIFACTS}
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": "pyrosetta",
        "candidate_input_rows": len(candidates),
        "computed_feature_rows": len(results),
        "failed_candidate_rows": len(runtime_log["errors"]),
        "multi_chain_context_rows": sum(
            1 for row in results if row.get("chain_execution_mode") == "multi_chain_context"
        ),
        "pyrosetta_init_executed": runtime_log.get("pyrosetta_init_executed") is True,
        "ddg_protocol_executed": bool(results),
        "random_seed": args.random_seed,
        "constant_seed": True,
        "ddg_units": "REU",
        "negative_ddg_is_stabilizing": True,
        "quality_gate": {
            "ddg_abs_sanity_limit_reu": DDG_ABS_SANITY_LIMIT_REU,
            "total_score_sanity_limit_reu": TOTAL_SCORE_SANITY_LIMIT_REU,
            "quality_passed_rows": sum(1 for row in results if row.get("quality_gate_passed") is True),
            "quality_blocked_rows": sum(1 for row in results if row.get("quality_gate_passed") is False),
            "policy": (
                "Quality status is a fail-closed computational sanity classification. "
                "It is not a scientific validity claim, wet-lab label, or model-quality gate."
            ),
        },
        "artifact_paths": sorted(artifact_sha256),
        "artifact_sha256": artifact_sha256,
        "errors": runtime_log["errors"],
        "output": rel(output_path),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Computed PyRosetta ddG features only; no training-label, model-claim, or release promotion.",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "candidate_input_rows": report["candidate_input_rows"],
            "computed_feature_rows": report["computed_feature_rows"],
            "failed_candidate_rows": report["failed_candidate_rows"],
            "output": str(report_path),
        },
        ensure_ascii=False,
    ))
    return 0 if report["pyrosetta_init_executed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
