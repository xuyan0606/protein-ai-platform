#!/usr/bin/env python3
"""Start all top-tier model workstreams as local fail-closed packets."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT_OUT = AI_ROOT / "reports" / "top_tier_model_execution_board.json"
WORKSTREAMS_OUT = AI_ROOT / "datasets" / "governance" / "top_tier_model_workstreams.jsonl"
PACKETS_OUT = AI_ROOT / "datasets" / "governance" / "top_tier_model_start_packets.jsonl"


WORKSTREAMS = [
    {
        "workstream_id": "p0_msa_cache_validator",
        "priority": "P0",
        "title": "MMseqs2 or trusted MSA/cache validator",
        "capability": "msa_conservation",
        "owner_role": "msa_runtime_operator",
        "source_artifacts": [
            "datasets/curation/msa_inputs/msa_targets.fasta",
            "reports/msa_runtime_readiness_report.json",
            "reports/msa_conservation_cache_validation_report.json",
        ],
        "target_artifacts": [
            "reports/msa_conservation_cache_validation_report.json",
            "cache/advanced_features/msa_conservation",
        ],
        "completion_checks": [
            "runtime_ready or trusted cache ready",
            "homolog database/cache manifest has version and checksum",
            "target coverage > 0",
        ],
    },
    {
        "workstream_id": "p0_reviewed_structure_graph",
        "priority": "P0",
        "title": "Reviewed structure graph feature builder",
        "capability": "structure_graph",
        "owner_role": "structure_feature_engineer",
        "source_artifacts": [
            "datasets/curation/structure_chain_mapping_decisions.jsonl",
            "reports/structure_chain_mapping_decision_validation_report.json",
            "reports/structure_coordinate_feature_report.json",
        ],
        "target_artifacts": [
            "cache/advanced_features/structure_graph",
            "datasets/curation/structure_chain_mappings_curated.jsonl",
        ],
        "completion_checks": [
            "reviewed chain mapping rows > 0",
            "residue graph checksum exists",
            "numbering_verified is true for exported rows",
        ],
    },
    {
        "workstream_id": "p0_proteingym_benchmark_cache",
        "priority": "P0",
        "title": "ProteinGym-style benchmark cache and no-leak scorecard",
        "capability": "benchmark_score_cache",
        "owner_role": "benchmark_engineer",
        "source_artifacts": [
            "reports/benchmark_matrix_report.json",
            "datasets/benchmark/benchmark_acquisition_plan.jsonl",
        ],
        "target_artifacts": [
            "cache/advanced_features/benchmarks",
            "reports/benchmark_matrix_report.json",
        ],
        "completion_checks": [
            "dataset license/version recorded",
            "protein/family/time split has no leakage",
            "scorecard exists for mutation_rank_head",
        ],
    },
    {
        "workstream_id": "p0_kwb_wet_lab_feedback",
        "priority": "P0",
        "title": "KWB plate/well wet-lab feedback calibration",
        "capability": "wet_lab_feedback_calibration",
        "owner_role": "assay_feedback_curator",
        "source_artifacts": [
            "datasets/feedback/experiment_feedback_plate.local.jsonl",
            "reports/experiment_feedback_plate_intake_validation_report.json",
            "reports/experiment_feedback_intake_validation_report.json",
        ],
        "target_artifacts": [
            "cache/advanced_features/wet_lab_feedback",
            "datasets/feedback/experiment_feedback_features.jsonl",
        ],
        "completion_checks": [
            "training eligible feedback rows > 0",
            "units, conditions, replicates and QC are validated",
            "numbering verified for feedback-linked variants",
        ],
    },
    {
        "workstream_id": "p1_boltz2_structure_affinity",
        "priority": "P1",
        "title": "Boltz-2 structure/affinity adapter",
        "capability": "structure_affinity_complex",
        "owner_role": "structure_affinity_engineer",
        "source_artifacts": [
            "reports/foreign_tool_readiness_report.json",
            "reports/google_github_advanced_model_research_2026_07_28.json",
        ],
        "target_artifacts": [
            "cache/advanced_features/structure_affinity",
        ],
        "completion_checks": [
            "license/runtime/model-weight gates pass",
            "input ligand identity is verified",
            "runtime log and checksum exist",
        ],
    },
    {
        "workstream_id": "p1_thermompnn_stability",
        "priority": "P1",
        "title": "ThermoMPNN and ThermoMPNN-D stability adapters",
        "capability": "ddg_stability",
        "owner_role": "stability_adapter_engineer",
        "source_artifacts": [
            "reports/foreign_tool_readiness_report.json",
            "datasets/curation/structure_chain_mappings_curated.jsonl",
        ],
        "target_artifacts": [
            "cache/advanced_features/ddg_stability",
        ],
        "completion_checks": [
            "reviewed structure rows exist",
            "runtime/model-weight gates pass",
            "ddG/proxy-ddG table has parameters and checksum",
        ],
    },
    {
        "workstream_id": "p1_plm_structure_representation",
        "priority": "P1",
        "title": "ESMC/SaProt/ProSST representation adapters",
        "capability": "sequence_plm_embeddings",
        "owner_role": "representation_model_engineer",
        "source_artifacts": [
            "reports/advanced_feature_cache_plan_report.json",
            "reports/google_github_advanced_model_research_2026_07_28.json",
        ],
        "target_artifacts": [
            "cache/advanced_features/sequence_plm",
            "cache/advanced_features/structure_graph",
        ],
        "completion_checks": [
            "per-model license and weight gates pass",
            "embedding/token metadata has model version",
            "input sequence or structure checksum exists",
        ],
    },
    {
        "workstream_id": "p1_catpred_kinetics",
        "priority": "P1",
        "title": "CatPred kinetics/function adapter",
        "capability": "kinetics_function",
        "owner_role": "enzyme_kinetics_engineer",
        "source_artifacts": [
            "reports/foreign_tool_readiness_report.json",
            "reports/google_github_advanced_model_research_2026_07_28.json",
        ],
        "target_artifacts": [
            "cache/advanced_features/kinetics_function",
        ],
        "completion_checks": [
            "substrate SMILES/InChI mapping is verified",
            "assay condition metadata exists",
            "calibration report exists before claim use",
        ],
    },
    {
        "workstream_id": "p2_ligandmpnn_generation_gate",
        "priority": "P2",
        "title": "LigandMPNN/ProteinMPNN candidate generation gate",
        "capability": "candidate_generation",
        "owner_role": "candidate_generation_engineer",
        "source_artifacts": [
            "reports/biosecurity_readiness_report.json",
            "reports/operator_review_status_report.json",
            "reports/google_github_advanced_model_research_2026_07_28.json",
        ],
        "target_artifacts": [
            "cache/advanced_features/candidate_generation",
        ],
        "completion_checks": [
            "protected sites are fixed or manually approved",
            "biosecurity and human approval gates pass",
            "candidate output remains design_candidate only",
        ],
    },
    {
        "workstream_id": "p2_rfdiffusion2_generation_gate",
        "priority": "P2",
        "title": "RFdiffusion2 enzyme active-site scaffold generation gate",
        "capability": "candidate_generation",
        "owner_role": "generative_design_reviewer",
        "source_artifacts": [
            "reports/biosecurity_readiness_report.json",
            "reports/operator_review_status_report.json",
            "reports/google_github_advanced_model_research_2026_07_28.json",
        ],
        "target_artifacts": [
            "cache/advanced_features/candidate_generation",
        ],
        "completion_checks": [
            "license/runtime gates pass",
            "motif/protected-site constraints are reviewed",
            "no order-ready sequence export is enabled",
        ],
    },
    {
        "workstream_id": "cross_rosetta_foldx_ddg_backend",
        "priority": "P0",
        "title": "Rosetta/PyRosetta/FoldX ddG backend gate",
        "capability": "ddg_stability",
        "owner_role": "ddg_backend_operator",
        "source_artifacts": [
            "reports/enzyme_analysis_constraint_policy_report.json",
            "reports/foreign_tool_readiness_report.json",
        ],
        "target_artifacts": [
            "cache/advanced_features/ddg_stability",
        ],
        "completion_checks": [
            "commercial license/legal review is recorded",
            "runtime command and parameters are versioned",
            "negative ddG stabilization convention is preserved",
        ],
    },
    {
        "workstream_id": "cross_license_runtime_weight_gate",
        "priority": "P0",
        "title": "Global license/runtime/model-weight gate",
        "capability": "governance",
        "owner_role": "release_governance_reviewer",
        "source_artifacts": [
            "reports/foreign_tool_readiness_report.json",
            "reports/external_license_review_decision_validation_report.json",
            "reports/local_release_manifest.json",
        ],
        "target_artifacts": [
            "reports/local_release_manifest.json",
        ],
        "completion_checks": [
            "license decisions are approved",
            "runtime/model-weight/data readiness is true",
            "release_ready remains false until all claim gates pass",
        ],
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def artifact_exists(rel_path: str) -> bool:
    return (AI_ROOT / rel_path).exists()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def infer_blockers(workstream: dict[str, Any], reports: dict[str, dict[str, Any]]) -> list[str]:
    capability = workstream["capability"]
    blockers: list[str] = []
    missing_sources = [path for path in workstream["source_artifacts"] if not artifact_exists(path)]
    if missing_sources:
        blockers.append("source artifacts missing: " + ", ".join(missing_sources))

    numbering = reports["numbering"].get("valid_rows", 0)
    structure_rows = reports["structure_mapping"].get("valid_rows") or reports["structure_mapping"].get("reviewed_rows") or 0
    msa_ready = bool(reports["msa_runtime"].get("runtime_ready")) or bool((reports["msa_runtime"].get("trusted_cache") or {}).get("ready"))
    feedback_rows = reports["feedback"].get("training_eligible_rows", 0)
    feedback_numeric_rows = reports["feedback"].get("numeric_training_eligible_rows", 0)
    plate_feedback_rows = reports["plate_feedback"].get("training_eligible_rows", 0)
    benchmark_ready = bool(reports["benchmark"].get("ready_for_model_claim"))
    benchmark_cache_ready = bool(reports.get("benchmark_score_cache_validation", {}).get("ready_for_model_claim"))
    ddg_adapter_integrated = bool(reports.get("ddg_backend", {}).get("adapter_integrated"))
    ddg_backend_ready = bool(reports.get("ddg_backend", {}).get("executable_ddg_backend_ready"))
    foreign_ready_tools = {
        tool.get("tool_id")
        for tool in reports["foreign_tools"].get("tools", [])
        if isinstance(tool, dict) and tool.get("ready_for_local_evaluation")
    }
    release_ready = bool(reports["release"].get("release_ready"))
    biosecurity_ready = bool(reports["biosecurity"].get("ready_for_ordering"))
    operator_ready = bool(reports["operator"].get("ready"))
    structure_graph_ready = bool(reports.get("structure_graph_validation", {}).get("ready_for_coordinate_feature_use"))
    strict_msa_feature_rows = reports["strict_msa_features"].get("feature_rows", 0)

    if capability in {"msa_conservation"} and not msa_ready:
        blockers.append("MSA runtime or trusted cache is not ready")
    if capability in {"msa_conservation"} and int(strict_msa_feature_rows or 0) <= 0:
        blockers.append("strict MSA site feature rows are zero after real-source label filtering")
    if capability in {"structure_graph", "ddg_stability"} and not structure_rows:
        blockers.append("reviewed structure chain mapping rows are missing")
    if capability == "structure_graph" and not structure_graph_ready:
        blockers.append("reviewed structure graph cache validation is not ready")
    if capability == "wet_lab_feedback_calibration" and not numbering:
        blockers.append("reviewed numbering rows are missing")
    if capability == "wet_lab_feedback_calibration" and not feedback_rows:
        blockers.append("training-eligible KWB feedback rows are missing")
    if capability == "wet_lab_feedback_calibration" and not (feedback_numeric_rows or plate_feedback_rows):
        blockers.append("numeric or plate-level training-eligible KWB feedback rows are missing")
    if capability == "benchmark_score_cache" and not (benchmark_ready and benchmark_cache_ready):
        blockers.append("external benchmark scorecard is not ready for model claim")
    if capability == "structure_affinity_complex" and "boltz2" not in foreign_ready_tools:
        blockers.append("Boltz-2 license/runtime/data/model-weight readiness is not complete")
    if capability == "kinetics_function" and "catpred" not in foreign_ready_tools:
        blockers.append("CatPred runtime/data/calibration readiness is not complete")
    if capability == "sequence_plm_embeddings":
        blockers.append("PLM license/runtime/model-weight readiness must be reviewed per model")
    if workstream["workstream_id"] == "p1_thermompnn_stability" and "thermompnn" not in foreign_ready_tools:
        blockers.append("ThermoMPNN runtime/model-weight readiness is not complete")
    if workstream["workstream_id"] == "cross_rosetta_foldx_ddg_backend":
        if not ddg_adapter_integrated:
            blockers.append("Rosetta/PyRosetta/FoldX ddG adapter contract is not integrated")
        if not ddg_backend_ready:
            blockers.append("Rosetta/PyRosetta/FoldX executable ddG backend is not license/runtime/data ready")
    if capability == "candidate_generation":
        if not biosecurity_ready:
            blockers.append("biosecurity ordering gate is not ready")
        if not operator_ready:
            blockers.append("human/operator approval gate is not ready")
    if capability == "governance" and not release_ready:
        blockers.append("release remains fail-closed")
    return blockers


def main() -> int:
    parser = argparse.ArgumentParser(description="Build top-tier model execution board")
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--workstreams", type=Path, default=WORKSTREAMS_OUT)
    parser.add_argument("--packets", type=Path, default=PACKETS_OUT)
    args = parser.parse_args()

    reports = {
        "numbering": load_json(AI_ROOT / "reports" / "numbering_curation_validation_report.json"),
        "structure_mapping": load_json(AI_ROOT / "reports" / "structure_chain_mapping_decision_validation_report.json"),
        "msa_runtime": load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json"),
        "feedback": load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json"),
        "plate_feedback": load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json"),
        "benchmark": load_json(AI_ROOT / "reports" / "benchmark_matrix_report.json"),
        "foreign_tools": load_json(AI_ROOT / "reports" / "foreign_tool_readiness_report.json"),
        "biosecurity": load_json(AI_ROOT / "reports" / "biosecurity_readiness_report.json"),
        "operator": load_json(AI_ROOT / "reports" / "operator_review_status_report.json"),
        "release": load_json(AI_ROOT / "reports" / "local_release_manifest.json"),
        "research": load_json(AI_ROOT / "reports" / "google_github_advanced_model_research_2026_07_28.json"),
        "structure_graph_validation": load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json"),
        "benchmark_score_cache_validation": load_json(AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json"),
        "ddg_backend": load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json"),
        "strict_msa_features": load_json(AI_ROOT / "reports" / "strict_msa_site_feature_report.json"),
    }

    created_at = datetime.now(timezone.utc).isoformat()
    workstream_rows = []
    packet_rows = []
    for workstream in WORKSTREAMS:
        blockers = infer_blockers(workstream, reports)
        row = {
            **workstream,
            "created_at": created_at,
            "local_only": True,
            "started": True,
            "completion_ready": False,
            "status": "started_blocked" if blockers else "started_ready_to_verify",
            "blockers": blockers,
            "policy": "Local execution workstream only; no external model execution, production sync, customer delivery, or model-quality claim.",
        }
        workstream_rows.append(row)
        packet_rows.append({
            "packet_id": f"{workstream['workstream_id']}-START",
            "workstream_id": workstream["workstream_id"],
            "priority": workstream["priority"],
            "owner_role": workstream["owner_role"],
            "started": True,
            "completion_ready": False,
            "status": row["status"],
            "next_local_steps": workstream["completion_checks"],
            "source_artifacts": workstream["source_artifacts"],
            "target_artifacts": workstream["target_artifacts"],
            "blockers": blockers,
            "manual_review_required": True,
            "policy": "This packet starts local work only and cannot be used as approval evidence.",
        })

    write_jsonl(args.workstreams, workstream_rows)
    write_jsonl(args.packets, packet_rows)

    blocked = [row for row in workstream_rows if row["status"] == "started_blocked"]
    report = {
        "created_at": created_at,
        "local_only": True,
        "research_report": "reports/google_github_advanced_model_research_2026_07_28.json",
        "workstreams": str(args.workstreams.relative_to(AI_ROOT) if args.workstreams.is_absolute() else args.workstreams),
        "start_packets": str(args.packets.relative_to(AI_ROOT) if args.packets.is_absolute() else args.packets),
        "total_workstreams": len(workstream_rows),
        "started_workstreams": len(workstream_rows),
        "blocked_workstreams": len(blocked),
        "ready_to_verify_workstreams": len(workstream_rows) - len(blocked),
        "completion_ready_workstreams": 0,
        "priority_counts": {
            priority: sum(1 for row in workstream_rows if row["priority"] == priority)
            for priority in ["P0", "P1", "P2"]
        },
        "current_readiness": {
            "current_state_is_top_tier": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "numbering_valid_rows": reports["numbering"].get("valid_rows", 0),
            "msa_runtime_ready": reports["msa_runtime"].get("runtime_ready"),
            "feedback_training_eligible_rows": reports["feedback"].get("training_eligible_rows", 0),
            "feedback_numeric_training_eligible_rows": reports["feedback"].get("numeric_training_eligible_rows", 0),
            "plate_feedback_training_eligible_rows": reports["plate_feedback"].get("training_eligible_rows", 0),
            "strict_msa_site_feature_rows": reports["strict_msa_features"].get("feature_rows", 0),
            "external_benchmark_ready_for_model_claim": reports["benchmark"].get("ready_for_model_claim"),
            "benchmark_score_cache_ready_for_model_claim": reports["benchmark_score_cache_validation"].get("ready_for_model_claim"),
            "benchmark_score_cache_valid_rows": reports["benchmark_score_cache_validation"].get("valid_rows"),
            "reviewed_structure_graph_ready_for_coordinate_feature_use": reports["structure_graph_validation"].get("ready_for_coordinate_feature_use"),
            "reviewed_structure_graph_valid_rows": reports["structure_graph_validation"].get("valid_rows"),
            "ddg_backend_adapter_integrated": reports["ddg_backend"].get("adapter_integrated"),
            "executable_ddg_backend_ready": reports["ddg_backend"].get("executable_ddg_backend_ready"),
            "proxy_ddg_backend_ready": reports["ddg_backend"].get("proxy_ddg_backend_ready"),
        },
        "blocked_capabilities": sorted({row["capability"] for row in blocked}),
        "rows": workstream_rows,
        "policy": "All top-tier model workstreams are started locally and fail closed. This board does not install tools, run external models, generate synthetic features, approve ordering, or unlock model-quality claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "started_workstreams": report["started_workstreams"],
        "blocked_workstreams": report["blocked_workstreams"],
        "ready_to_verify_workstreams": report["ready_to_verify_workstreams"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
