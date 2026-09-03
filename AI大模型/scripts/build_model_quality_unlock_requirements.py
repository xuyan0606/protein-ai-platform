#!/usr/bin/env python3
"""Build model-quality unlock requirements from local readiness reports.

This is a local-only planning artifact. It does not install tools, call external
services, create reviewed decisions, generate MSA values, or sync production.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT_OUT = AI_ROOT / "reports" / "model_quality_unlock_requirements_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "model_quality_unlock_requirements.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def requirement(
    requirement_id: str,
    workstream: str,
    current_state: dict[str, Any],
    target_state: dict[str, Any],
    required_artifacts: list[str],
    validator_reports: list[str],
    *,
    authorization_required: bool,
    forbidden_shortcuts: list[str],
    status: str = "blocked",
    unlocks: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "workstream": workstream,
        "status": status,
        "current_state": current_state,
        "target_state": target_state,
        "required_artifacts": required_artifacts,
        "validator_reports": validator_reports,
        "human_or_external_authorization_required": authorization_required,
        "forbidden_shortcuts": forbidden_shortcuts,
        "unlocks_when_complete": unlocks or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build model quality unlock requirements")
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    safe_entry = load_json(AI_ROOT / "reports" / "safe_training_entrypoint_check.json")
    numbering = load_json(AI_ROOT / "reports" / "numbering_curation_validation_report.json")
    repaired = load_json(AI_ROOT / "reports" / "repaired_supervised_table_report.json")
    msa_runtime = load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json")
    msa_cache = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
    feedback = load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json")
    plate_feedback = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
    foreign_tools = load_json(AI_ROOT / "reports" / "foreign_tool_readiness_report.json")
    ddg_backend = load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json")
    strict_msa_features = load_json(AI_ROOT / "reports" / "strict_msa_site_feature_report.json")
    label_provenance = load_json(AI_ROOT / "reports" / "label_provenance_audit_report.json")
    claim_matrix = load_json(AI_ROOT / "reports" / "claim_readiness_matrix.json")
    release = load_json(AI_ROOT / "reports" / "local_release_manifest.json")
    policy = load_json(AI_ROOT / "reports" / "enzyme_analysis_constraint_policy_report.json")
    blocker_matrix = load_json(AI_ROOT / "reports" / "next_unlock_blocker_matrix.json")

    strict_rows = repaired.get("supervised_rows") or safe_entry.get("rows") or 0
    claim_eligible_rows = label_provenance.get("claim_eligible_rows", 0)
    strict_rows_int = int(strict_rows or 0)
    strict_msa_feature_rows = int(strict_msa_features.get("feature_rows") or 0)
    msa_requirement_ready = (
        bool(msa_runtime.get("runtime_ready"))
        and bool(msa_cache.get("ready"))
        and int(msa_cache.get("valid_rows") or 0) >= 158
        and strict_rows_int > 0
        and strict_msa_feature_rows > 0
        and strict_msa_feature_rows == strict_rows_int
        and int(strict_msa_features.get("missing_rows") or 0) == 0
    )
    model_claim = next(
        (row for row in claim_matrix.get("claims", []) if row.get("claim_id") == "model_quality_claim"),
        {},
    )

    requirements = [
        requirement(
            "MQ-U001",
            "reviewed_numbering",
            {
                "valid_reviewed_numbering_rows": numbering.get("valid_rows", 0),
                "strict_supervised_rows": strict_rows,
                "claim_eligible_real_supervised_rows": claim_eligible_rows,
                "synthetic_or_unreceipted_rows": label_provenance.get("synthetic_or_unreceipted_rows"),
                "label_provenance_hard_gate_status": label_provenance.get("hard_gate_status"),
                "safe_for_model_claim": safe_entry.get("safe_for_model_claim"),
            },
            {
                "minimum_new_valid_reviewed_numbering_rows": max(75 - int(numbering.get("valid_rows") or 0), 0),
                "strict_supervised_rows": ">=100",
                "claim_eligible_real_supervised_rows": ">=100",
                "synthetic_or_unreceipted_rows": 0,
                "safe_for_model_claim": True,
            },
            [
                "datasets/curation/numbering_curation_decisions.jsonl",
                "datasets/curation/numbering_review_packets/",
                "datasets/curation/numbering_review_decision_drafts/",
                "datasets/curated/enzyme_mutation_supervised_claim_eligible.jsonl",
                "reports/label_provenance_audit_report.json",
            ],
            [
                "reports/numbering_curation_validation_report.json",
                "reports/numbering_curation_apply_report.json",
                "reports/safe_training_entrypoint_check.json",
                "reports/label_provenance_audit_report.json",
            ],
            authorization_required=True,
            forbidden_shortcuts=[
                "Do not promote weak evidence without canonical/isoform/literature numbering review.",
                "Do not use template rows as reviewed decisions.",
                "Do not use generate_sample_data synthetic ProThermDB rows for model-quality claims.",
            ],
            unlocks=["strict row-count and real-label provenance gate for supervised training"],
        ),
        requirement(
            "MQ-U002",
            "msa_conservation",
            {
                "runtime_ready": msa_runtime.get("runtime_ready"),
                "selected_runtime": msa_runtime.get("selected_runtime"),
                "cache_ready": msa_cache.get("ready"),
                "valid_cache_rows": msa_cache.get("valid_rows"),
                "invalid_cache_rows": msa_cache.get("invalid_rows"),
                "strict_msa_site_feature_rows": strict_msa_features.get("feature_rows"),
                "strict_msa_site_feature_missing_rows": strict_msa_features.get("missing_rows"),
                "runtime_blockers": msa_runtime.get("blockers", []),
            },
            {
                "runtime_ready_or_cache_ready": True,
                "target_rows": 158,
                "valid_cache_rows": 158,
                "manifest_errors": [],
            },
            [
                "config/msa_runtime.local.example.json",
                "reports/msa_conservation_manifest.json",
                "cache/msa/",
                "datasets/curation/msa_conservation/",
                "datasets/curation/msa_inputs/msa_targets.fasta",
                "datasets/curated/enzyme_mutation_strict_msa_site_features.jsonl",
            ],
            [
                "reports/msa_runtime_readiness_report.json",
                "reports/msa_conservation_cache_validation_report.json",
                "reports/msa_execution_plan_report.json",
                "reports/strict_msa_site_feature_report.json",
            ],
            authorization_required=True,
            forbidden_shortcuts=[
                "Do not synthesize conservation from a single sequence.",
                "Do not mark MSA ready without homolog database version and file checksums.",
                "Do not mark MSA site features ready when strict real-source supervised rows are zero.",
                "Do not run Docker pulls or downloads without explicit approval.",
            ],
            status="ready_to_verify" if msa_requirement_ready else "blocked",
            unlocks=["MSA/conservation feature production"],
        ),
        requirement(
            "MQ-U003",
            "rosetta_pyrosetta_foldx_ddg",
            {
                "rosetta_policy_status": (policy.get("rosetta_integration_status") or {}).get("status"),
                "ddg_adapter_integrated": bool(ddg_backend.get("adapter_integrated")),
                "executable_ddg_backend_ready": bool(ddg_backend.get("executable_ddg_backend_ready")),
                "proxy_ddg_backend_ready": bool(ddg_backend.get("proxy_ddg_backend_ready")),
                "one_ddg_backend_ready": bool(ddg_backend.get("one_ddg_backend_ready")),
                "thermompnn_ready": any(
                    tool.get("tool_id") == "thermompnn" and tool.get("ready_for_local_evaluation")
                    for tool in foreign_tools.get("tools", [])
                ),
                "ready_external_tools": foreign_tools.get("ready_for_local_evaluation", 0),
            },
            {
                "one_ddg_backend_ready": True,
                "allowed_backends": ["Rosetta", "PyRosetta", "FoldX", "ThermoMPNN baseline"],
                "artifact_requirements": ["parameters", "input_structure_checksum", "mutation_list", "ddg_table", "runtime_log"],
            },
            [
                "config/foreign_tool_registry.local.example.json",
                "config/ddg_backend.local.example.json",
                "contracts/external_tool_adapter.schema.json",
                "contracts/ddg_backend_result.schema.json",
                "reports/foreign_tool_readiness_report.json",
                "reports/ddg_backend_readiness_report.json",
                "reports/ddg_backend_execution_plan_report.json",
                "reports/enzyme_analysis_constraint_policy_report.json",
            ],
            [
                "reports/foreign_tool_readiness_report.json",
                "reports/ddg_backend_readiness_report.json",
                "reports/ddg_backend_execution_plan_report.json",
                "reports/external_license_review_decision_validation_report.json",
                "reports/enzyme_analysis_constraint_policy_report.json",
            ],
            authorization_required=True,
            forbidden_shortcuts=[
                "Do not claim Rosetta/PyRosetta/FoldX ddG execution without licensed runtime evidence.",
                "Do not treat ddG predictions as wet-lab stability labels.",
                "Do not use restricted or unreviewed external tools for production claims.",
            ],
            status="ready_to_verify" if bool(ddg_backend.get("executable_ddg_backend_ready")) else "blocked",
            unlocks=["external ddG evidence tier", "stability-head external baseline comparison"],
        ),
        requirement(
            "MQ-U004",
            "real_experiment_feedback",
            {
                "feedback_training_eligible_rows": feedback.get("training_eligible_rows", 0),
                "feedback_qualitative_training_eligible_rows": feedback.get("qualitative_training_eligible_rows", 0),
                "feedback_numeric_training_eligible_rows": feedback.get("numeric_training_eligible_rows", 0),
                "plate_training_eligible_rows": plate_feedback.get("training_eligible_rows", 0),
            },
            {
                "feedback_training_eligible_rows": ">0",
                "numeric_feedback_training_eligible_rows": ">0 for numeric activity/stability calibration",
                "plate_training_eligible_rows": ">0 for assay_success_head",
                "required_fields": ["variant_id", "mutation", "assay_condition", "replicate", "normalized_activity", "QC_flag"],
            },
            [
                "datasets/feedback/experiment_feedback.local.jsonl",
                "datasets/feedback/experiment_feedback_plate.local.jsonl",
                "contracts/experiment_feedback.schema.json",
                "contracts/experiment_feedback_plate.schema.json",
            ],
            [
                "reports/experiment_feedback_intake_validation_report.json",
                "reports/experiment_feedback_plate_intake_validation_report.json",
                "reports/multitask_training_readiness_report.json",
            ],
            authorization_required=True,
            forbidden_shortcuts=[
                "Do not convert Matvenus summaries or model reports directly into wet-lab feedback.",
                "Do not accept rows without units, conditions, replicate/QC and numbering verification.",
            ],
            unlocks=["activity_risk_head labels", "assay_success_head labels", "closed-loop model updates"],
        ),
        requirement(
            "MQ-U005",
            "production_sync_authorization",
            {
                "local_release_ready": release.get("release_ready"),
                "artifact_count": release.get("artifact_count"),
                "model_quality_claim_ready": model_claim.get("ready"),
            },
            {
                "explicit_user_authorization": True,
                "pre_sync_requirements": [
                    "release_ready true",
                    "backup plan",
                    "minimal file set",
                    "rollback plan",
                    "smoke test plan",
                ],
            },
            [
                "reports/local_release_manifest.json",
                "reports/claim_readiness_matrix.json",
                "reports/customer_delivery_readiness_report.json",
            ],
            [
                "reports/local_release_manifest.json",
                "reports/claim_readiness_matrix.json",
            ],
            authorization_required=True,
            forbidden_shortcuts=[
                "Do not sync, deploy, restart, or modify production without explicit user instruction.",
                "Do not treat local-only reports as customer delivery approval.",
            ],
            unlocks=["P31 production integration review only after explicit authorization"],
        ),
    ]

    blocked = [row for row in requirements if row["status"] == "blocked"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "jsonl": str(args.jsonl.relative_to(AI_ROOT) if args.jsonl.is_absolute() else args.jsonl),
        "requirement_rows": len(requirements),
        "blocked_requirements": len(blocked),
        "ready_to_verify_requirements": sum(1 for row in requirements if row["status"] == "ready_to_verify"),
        "complete_requirements": sum(1 for row in requirements if row["status"] == "complete"),
        "model_quality_ready": False,
        "model_quality_claim_missing_requirements": model_claim.get("missing_requirements", []),
        "top_blockers": blocker_matrix.get("top_blockers", [])[:8],
        "minimum_unlock_sequence": [
            "MQ-U001 reviewed numbering: get strict supervised rows to >=100",
            "MQ-U001 label provenance: replace synthetic/unreceipted stability rows with real source receipts",
            "MQ-U002 MSA conservation: only ready after strict real-source rows join to MSA site features (>0 rows)",
            "MQ-U004 real experiment feedback: add schema-valid numbered feedback rows",
            "MQ-U003 physical ddG backend: approve/license/install Rosetta/PyRosetta/FoldX and produce runtime receipts; ThermoMPNN remains proxy evidence only",
            "Rerun safe pipeline, benchmark matrix and claim readiness",
            "MQ-U005 production sync: only after explicit user authorization and release_ready=true",
        ],
        "requirements": requirements,
        "policy": (
            "This report defines what is required to unlock model-quality work. "
            "It does not execute external tools, create labels, approve production, "
            "or change release_ready/model-quality status."
        ),
    }

    write_jsonl(args.jsonl, requirements)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "requirement_rows": report["requirement_rows"],
        "blocked_requirements": report["blocked_requirements"],
        "model_quality_ready": report["model_quality_ready"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
