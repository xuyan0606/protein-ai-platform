#!/usr/bin/env python3
"""Start non-human construction workstreams as fail-closed build lanes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT_OUT = AI_ROOT / "reports" / "non_human_construction_board.json"
WORKSTREAMS_OUT = AI_ROOT / "datasets" / "governance" / "non_human_construction_workstreams.jsonl"
PACKETS_OUT = AI_ROOT / "datasets" / "governance" / "non_human_construction_start_packets.jsonl"
RUNBOOK_OUT = AI_ROOT / "platform_integration" / "non_human_construction_board.md"


WORKSTREAMS = [
    {
        "workstream_id": "nhc_ddg_physics_backend",
        "priority": "P0",
        "title": "Rosetta/PyRosetta/FoldX physics ddG backend",
        "capability": "ddg_physics",
        "safe_local_commands": [
            "python3 scripts/build_ddg_backend_readiness.py",
            "python3 scripts/build_ddg_backend_execution_plan.py",
            "python3 scripts/validate_ddg_backend_operator_packets.py",
        ],
        "completion_checks": [
            "executable_ddg_backend_ready true",
            "license/runtime/data gates approved",
            "negative ddG stabilization convention preserved",
        ],
    },
    {
        "workstream_id": "nhc_benchmark_scorecards",
        "priority": "P0",
        "title": "Benchmark score cache and head scorecards",
        "capability": "benchmarking",
        "safe_local_commands": [
            "python3 scripts/apply_benchmark_score_cache_intake.py",
            "python3 scripts/validate_benchmark_score_cache.py",
            "python3 scripts/build_benchmark_matrix_report.py",
        ],
        "completion_checks": [
            "benchmark_score_cache ready_for_model_claim true",
            "all five heads have scorecards",
            "split/leakage reports present",
        ],
    },
    {
        "workstream_id": "nhc_five_head_training",
        "priority": "P0",
        "title": "Five-head supervised training pipeline",
        "capability": "training",
        "safe_local_commands": [
            "python3 scripts/build_multitask_training_readiness.py",
            "python3 scripts/check_safe_training_entrypoint.py",
        ],
        "completion_checks": [
            "strict supervised rows >= 100",
            "claim-eligible real supervised rows >= 100",
            "all five heads have eligible labels",
        ],
    },
    {
        "workstream_id": "nhc_msa_conservation_production",
        "priority": "P0",
        "title": "MSA/conservation feature production",
        "capability": "msa_conservation",
        "safe_local_commands": [
            "python3 scripts/build_msa_runtime_readiness.py",
            "python3 scripts/validate_msa_conservation_cache.py",
            "python3 scripts/build_strict_msa_site_features.py",
        ],
        "completion_checks": [
            "msa_runtime_ready true",
            "cache validation valid_rows > 0",
            "strict MSA site feature table built",
        ],
    },
    {
        "workstream_id": "nhc_structure_gnn_features",
        "priority": "P0",
        "title": "Structure graph and GNN feature production",
        "capability": "structure_graph",
        "safe_local_commands": [
            "python3 scripts/build_reviewed_structure_graph_features.py",
            "python3 scripts/validate_reviewed_structure_graph_features.py",
        ],
        "completion_checks": [
            "reviewed structure graph validation ready",
            "valid graph rows > 0",
            "coordinate feature rows remain checksum-traceable",
        ],
    },
    {
        "workstream_id": "nhc_wet_lab_feedback_loop",
        "priority": "P0",
        "title": "Wet-lab feedback loop and calibration features",
        "capability": "feedback_loop",
        "safe_local_commands": [
            "python3 scripts/validate_experiment_feedback_intake.py",
            "python3 scripts/validate_experiment_feedback_plate_intake.py",
            "python3 scripts/build_experiment_feedback_trainability_audit.py",
        ],
        "completion_checks": [
            "training eligible feedback rows > 0",
            "plate/well QC rows valid",
            "feedback lineage and checksum receipts present",
        ],
    },
    {
        "workstream_id": "nhc_data_lake_cache_governance",
        "priority": "P0",
        "title": "Data lake, cache manifest and provenance governance",
        "capability": "data_governance",
        "safe_local_commands": [
            "python3 scripts/build_data_lake_manifest.py",
            "python3 scripts/build_provenance_graph_report.py",
            "python3 scripts/build_governance_readiness.py",
        ],
        "completion_checks": [
            "data lake manifest has no missing artifacts",
            "provenance graph ready",
            "governance readiness report exists",
        ],
    },
    {
        "workstream_id": "nhc_production_platform_services",
        "priority": "P1",
        "title": "Production platform services, jobs, audit logs and permissions",
        "capability": "production_service",
        "safe_local_commands": [
            "python3 scripts/build_customer_delivery_readiness.py",
            "python3 scripts/build_operator_review_status_report.py",
            "python3 scripts/build_local_release_manifest.py",
        ],
        "completion_checks": [
            "authn/authz and audit log design implemented",
            "job queue and rollback policy implemented",
            "release remains gated until all claims pass",
        ],
    },
    {
        "workstream_id": "nhc_safety_compliance_gates",
        "priority": "P0",
        "title": "Biosecurity, IP/FTO, license and delivery gates",
        "capability": "safety_compliance",
        "safe_local_commands": [
            "python3 scripts/validate_biosecurity_screening_decisions.py",
            "python3 scripts/validate_sequence_ip_fto_decisions.py",
            "python3 scripts/validate_external_license_review_decisions.py",
        ],
        "completion_checks": [
            "biosecurity screened",
            "IP/FTO cleared",
            "external license decisions approved",
        ],
    },
    {
        "workstream_id": "nhc_advanced_model_adapters",
        "priority": "P1",
        "title": "Advanced model adapters and top-tier architecture implementation",
        "capability": "advanced_model",
        "safe_local_commands": [
            "python3 scripts/build_advanced_model_architecture.py",
            "python3 scripts/build_advanced_feature_cache_plan.py",
            "python3 scripts/build_top_tier_model_execution_board.py",
        ],
        "completion_checks": [
            "PLM/MSA/structure/ddG/feedback adapters emit real cached features",
            "uncertainty and Pareto ranking use real modality evidence",
            "advanced model status is not scaffold_only",
        ],
    },
    {
        "workstream_id": "nhc_active_learning_loop",
        "priority": "P1",
        "title": "Active-learning experiment recommendation loop",
        "capability": "active_learning",
        "safe_local_commands": [
            "python3 scripts/build_active_learning_trial_readiness.py",
            "python3 scripts/build_biosecurity_readiness.py",
            "python3 scripts/build_customer_delivery_readiness.py",
        ],
        "completion_checks": [
            "five-head model and benchmark are ready",
            "budget/capacity and human approval are recorded",
            "biosecurity/order gate is approved",
        ],
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def truthy(report: dict[str, Any], *keys: str) -> bool:
    value: Any = report
    for key in keys:
        if not isinstance(value, dict):
            return False
        value = value.get(key)
    return bool(value)


def blockers_for(workstream: dict[str, Any], reports: dict[str, dict[str, Any]]) -> list[str]:
    capability = workstream["capability"]
    blockers: list[str] = []
    claim = reports["claim"]
    release = reports["release"]
    ddg = reports["ddg"]
    benchmark_cache = reports["benchmark_cache"]
    msa_runtime = reports["msa_runtime"]
    msa_cache = reports["msa_cache"]
    strict_msa_features = reports["strict_msa_features"]
    structure_graph = reports["structure_graph"]
    feedback = reports["feedback"]
    plate_feedback = reports["plate_feedback"]
    active_learning = reports["active_learning"]
    advanced = reports["advanced_model"]

    claims = {row.get("claim_id"): row for row in claim.get("claims", []) if isinstance(row, dict)}
    model_claim = claims.get("model_quality_claim", {})
    five_head_claim = claims.get("five_head_training_run", {})

    if capability == "ddg_physics":
        if not truthy(ddg, "executable_ddg_backend_ready"):
            blockers.append("Rosetta/PyRosetta/FoldX executable ddG backend is not ready")
        if not truthy(ddg, "negative_ddg_is_stabilizing"):
            blockers.append("negative ddG stabilization convention missing")
    elif capability == "benchmarking":
        if not truthy(benchmark_cache, "ready_for_model_claim"):
            blockers.append("benchmark score cache is not ready for model claim")
        if int(benchmark_cache.get("heads_ready") or 0) < 5:
            blockers.append("not all five head scorecards are ready")
    elif capability == "training":
        if not five_head_claim.get("ready"):
            blockers.extend(five_head_claim.get("missing_requirements") or ["five-head training claim is blocked"])
    elif capability == "msa_conservation":
        if not truthy(msa_runtime, "runtime_ready"):
            blockers.append("MSA runtime is not ready")
        if not truthy(msa_cache, "ready"):
            blockers.append("MSA conservation cache validation is not ready")
        if int(strict_msa_features.get("feature_rows") or 0) <= 0:
            blockers.append("strict MSA site feature rows are zero after real-source label filtering")
    elif capability == "structure_graph":
        if not truthy(structure_graph, "ready_for_coordinate_feature_use"):
            blockers.append("reviewed structure graph is not ready for coordinate feature use")
    elif capability == "feedback_loop":
        if int(feedback.get("training_eligible_rows") or 0) <= 0:
            blockers.append("experiment feedback has no training-eligible rows")
        if int(plate_feedback.get("training_eligible_rows") or 0) <= 0:
            blockers.append("plate/well feedback has no training-eligible rows")
    elif capability == "data_governance":
        if release.get("missing_artifacts"):
            blockers.append("data lake/local release manifest has missing artifacts")
        if not truthy(release, "readiness_summary", "provenance_ready"):
            blockers.append("provenance readiness is not true")
    elif capability == "production_service":
        if not truthy(release, "release_ready"):
            blockers.append("local release remains blocked")
        if not truthy(release, "readiness_summary", "operator_review_status_ready"):
            blockers.append("operator review status is not ready")
    elif capability == "safety_compliance":
        for claim_id in ["biosecurity_screened", "ip_fto_cleared", "external_tool_production_use", "customer_sequence_package"]:
            if not claims.get(claim_id, {}).get("ready"):
                blockers.append(f"{claim_id} is blocked")
    elif capability == "advanced_model":
        if advanced.get("status") == "scaffold_only_fail_closed":
            blockers.append("advanced model is scaffold only")
        if model_claim.get("ready") is not True:
            blockers.append("model quality claim is blocked")
    elif capability == "active_learning":
        if not active_learning.get("ready"):
            blockers.extend(active_learning.get("blockers") or ["active learning readiness is blocked"])
    return sorted(set(str(item) for item in blockers))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build non-human construction board")
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--workstreams", type=Path, default=WORKSTREAMS_OUT)
    parser.add_argument("--packets", type=Path, default=PACKETS_OUT)
    parser.add_argument("--runbook", type=Path, default=RUNBOOK_OUT)
    args = parser.parse_args()

    reports = {
        "claim": load_json(AI_ROOT / "reports" / "claim_readiness_matrix.json"),
        "release": load_json(AI_ROOT / "reports" / "local_release_manifest.json"),
        "ddg": load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json"),
        "benchmark_cache": load_json(AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json"),
        "msa_runtime": load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json"),
        "msa_cache": load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json"),
        "strict_msa_features": load_json(AI_ROOT / "reports" / "strict_msa_site_feature_report.json"),
        "structure_graph": load_json(AI_ROOT / "reports" / "reviewed_structure_graph_validation_report.json"),
        "feedback": load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json"),
        "plate_feedback": load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json"),
        "active_learning": load_json(AI_ROOT / "reports" / "active_learning_trial_readiness_report.json"),
        "advanced_model": load_json(AI_ROOT / "reports" / "advanced_model_architecture_report.json"),
    }

    created_at = datetime.now(timezone.utc).isoformat()
    workstream_rows = []
    packet_rows = []
    for index, workstream in enumerate(WORKSTREAMS, start=1):
        blockers = blockers_for(workstream, reports)
        status = "started_ready_to_verify" if not blockers else "started_blocked"
        row = {
            **workstream,
            "execution_order": index,
            "created_at": created_at,
            "local_only": True,
            "started": True,
            "status": status,
            "completion_ready": False,
            "automatic_external_execution_allowed": False,
            "blockers": blockers,
            "policy": "Started as local fail-closed construction lane; this row is not a model-quality, release, ordering, license, or production approval.",
        }
        workstream_rows.append(row)
        packet_rows.append({
            "packet_id": f"{workstream['workstream_id']}-START",
            "workstream_id": workstream["workstream_id"],
            "execution_order": index,
            "priority": workstream["priority"],
            "title": workstream["title"],
            "status": status,
            "safe_local_commands": workstream["safe_local_commands"],
            "completion_checks": workstream["completion_checks"],
            "blockers": blockers,
            "manual_approval_required_for_external_install_or_production": True,
        })

    write_jsonl(args.workstreams, workstream_rows)
    write_jsonl(args.packets, packet_rows)

    status_counts = {
        status: sum(1 for row in workstream_rows if row["status"] == status)
        for status in sorted({row["status"] for row in workstream_rows})
    }
    report = {
        "created_at": created_at,
        "local_only": True,
        "workstreams": str(args.workstreams.relative_to(AI_ROOT)),
        "start_packets": str(args.packets.relative_to(AI_ROOT)),
        "total_workstreams": len(workstream_rows),
        "started_workstreams": len(workstream_rows),
        "started_ready_to_verify_workstreams": status_counts.get("started_ready_to_verify", 0),
        "started_blocked_workstreams": status_counts.get("started_blocked", 0),
        "completion_ready_workstreams": 0,
        "status_counts": status_counts,
        "priority_counts": {
            priority: sum(1 for row in workstream_rows if row["priority"] == priority)
            for priority in ["P0", "P1", "P2"]
        },
        "current_readiness": {
            "safe_for_model_claim": False,
            "release_ready": bool(reports["release"].get("release_ready")),
            "claims_allowed": reports["claim"].get("claims_allowed"),
            "claims_blocked": reports["claim"].get("claims_blocked"),
            "executable_ddg_backend_ready": reports["ddg"].get("executable_ddg_backend_ready"),
            "proxy_ddg_backend_ready": reports["ddg"].get("proxy_ddg_backend_ready"),
            "benchmark_score_cache_ready_for_model_claim": reports["benchmark_cache"].get("ready_for_model_claim"),
            "msa_runtime_ready": reports["msa_runtime"].get("runtime_ready"),
            "msa_cache_valid_rows": reports["msa_cache"].get("valid_rows"),
            "strict_msa_site_feature_rows": reports["strict_msa_features"].get("feature_rows"),
            "reviewed_structure_graph_valid_rows": reports["structure_graph"].get("valid_rows"),
            "feedback_training_eligible_rows": reports["feedback"].get("training_eligible_rows"),
            "plate_feedback_training_eligible_rows": reports["plate_feedback"].get("training_eligible_rows"),
            "active_learning_ready": reports["active_learning"].get("ready"),
            "advanced_model_status": reports["advanced_model"].get("status"),
        },
        "rows": workstream_rows,
        "policy": "This board starts every non-human construction lane. It does not download tools, run unapproved external models, fabricate labels/features, approve production sync, or unlock model-quality claims.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    args.runbook.parent.mkdir(parents=True, exist_ok=True)
    args.runbook.write_text(
        "# Non-Human Construction Board\n\n"
        "This board starts all non-human build lanes in fail-closed mode.\n\n"
        f"- Workstreams: `{report['workstreams']}`\n"
        f"- Start packets: `{report['start_packets']}`\n"
        f"- Started: {report['started_workstreams']}\n"
        f"- Ready to verify: {report['started_ready_to_verify_workstreams']}\n"
        f"- Blocked: {report['started_blocked_workstreams']}\n\n"
        "Policy: no external install, production sync, customer delivery, model-quality claim, or ordering approval is granted by this board.\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "started_workstreams": report["started_workstreams"],
        "ready_to_verify": report["started_ready_to_verify_workstreams"],
        "blocked": report["started_blocked_workstreams"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
