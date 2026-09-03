#!/usr/bin/env python3
"""Build the KWB fail-closed tool lifecycle registry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "kwb_tool_lifecycle_registry.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "kwb_tool_lifecycle_registry_report.json"


TOOLS: list[dict[str, Any]] = [
    {
        "tool_id": "rosetta_ddg",
        "display_name": "Rosetta ddG",
        "tool_family": "physics_ddg",
        "runtime_type": "local_executable_or_container",
        "borrowed_pattern": "ProteinMCP install/probe/register split",
        "current_runtime_evidence": [
            "reports/ddg_executable_probe_report.json",
            "reports/ddg_backend_readiness_report.json",
        ],
        "install_status": "not_installed",
        "license_status": "not_reviewed",
        "probe_status": "not_found",
        "smoke_status": "not_run",
        "register_status": "blocked_before_agent_exposure",
        "blockers": ["license_not_approved", "executable_not_found", "physics_ddg_smoke_missing"],
    },
    {
        "tool_id": "pyrosetta_ddg",
        "display_name": "PyRosetta ddG",
        "tool_family": "physics_ddg",
        "runtime_type": "python_module",
        "borrowed_pattern": "ProteinMCP install/probe/register split",
        "current_runtime_evidence": [
            "reports/ddg_executable_probe_report.json",
            "reports/ddg_backend_readiness_report.json",
        ],
        "install_status": "not_installed",
        "license_status": "not_reviewed",
        "probe_status": "module_unavailable",
        "smoke_status": "not_run",
        "register_status": "blocked_before_agent_exposure",
        "blockers": ["license_not_approved", "python_module_unavailable", "physics_ddg_smoke_missing"],
    },
    {
        "tool_id": "foldx_ddg",
        "display_name": "FoldX ddG",
        "tool_family": "physics_ddg",
        "runtime_type": "local_executable",
        "borrowed_pattern": "ProteinMCP install/probe/register split",
        "current_runtime_evidence": [
            "reports/ddg_executable_probe_report.json",
            "reports/ddg_backend_readiness_report.json",
        ],
        "install_status": "not_installed",
        "license_status": "not_reviewed",
        "probe_status": "not_found",
        "smoke_status": "not_run",
        "register_status": "blocked_before_agent_exposure",
        "blockers": ["license_not_approved", "executable_not_found", "physics_ddg_smoke_missing"],
    },
    {
        "tool_id": "thermompnn_proxy",
        "display_name": "ThermoMPNN proxy ddG",
        "tool_family": "computational_proxy_ddg",
        "runtime_type": "local_python_runtime",
        "borrowed_pattern": "ProteinMCP tool registry plus explicit limitation flags",
        "current_runtime_evidence": [
            "reports/thermompnn_local_source_report.json",
            "reports/thermompnn_venus15b_smoke_report.json",
            "reports/ddg_model_consumption_contract_report.json",
        ],
        "install_status": "local_source_cached",
        "license_status": "source_detected_not_production_approved",
        "probe_status": "proxy_smoke_artifact_present",
        "smoke_status": "proxy_smoke_completed",
        "register_status": "registered_for_manual_review_only",
        "blockers": ["not_physics_ddg", "manual_review_required", "not_training_label"],
    },
    {
        "tool_id": "mmseqs2_msa",
        "display_name": "MMseqs2 MSA",
        "tool_family": "msa",
        "runtime_type": "local_executable",
        "borrowed_pattern": "ProteinMCP runtime catalog with local probe receipts",
        "current_runtime_evidence": [
            "reports/mmseqs2_local_runtime_report.json",
            "reports/mmseqs_homolog_database_report.json",
            "reports/msa_conservation_cache_validation_report.json",
        ],
        "install_status": "local_runtime_cached",
        "license_status": "review_required_before_production",
        "probe_status": "cache_generated",
        "smoke_status": "msa_cache_validation_passed",
        "register_status": "registered_as_feature_input_only",
        "blockers": ["feature_only_not_training_label", "production_license_review_required"],
    },
    {
        "tool_id": "interpro_domain",
        "display_name": "InterPro/domain evidence",
        "tool_family": "domain_annotation",
        "runtime_type": "local_or_cached_evidence",
        "borrowed_pattern": "ProteinMCP catalog radar without uncontrolled installation",
        "current_runtime_evidence": [
            "reports/domain_interval_batch_status_report.json",
            "datasets/curation/domain_interval_decisions.jsonl",
        ],
        "install_status": "cached_evidence_available",
        "license_status": "review_required_before_production",
        "probe_status": "partial_evidence_1785_of_1942",
        "smoke_status": "decision_validation_passed",
        "register_status": "registered_as_position_feature_input_only",
        "blockers": ["157_domain_rows_undecided", "feature_only_not_training_label"],
    },
    {
        "tool_id": "esm_prottrans_plm_features",
        "display_name": "ESM/ProtTrans PLM features",
        "tool_family": "plm_feature",
        "runtime_type": "future_container_or_local_model",
        "borrowed_pattern": "ProteinMCP Docker/GPU registry as radar only",
        "current_runtime_evidence": ["reports/proteinmcp_deep_research_2026_07_31.json"],
        "install_status": "not_installed",
        "license_status": "not_reviewed",
        "probe_status": "not_run",
        "smoke_status": "not_run",
        "register_status": "staging_candidate_only",
        "blockers": ["model_weights_not_authorized", "runtime_not_locked", "feature_schema_missing"],
    },
    {
        "tool_id": "amber_gromacs_md",
        "display_name": "AMBER/GROMACS MD evidence",
        "tool_family": "molecular_dynamics",
        "runtime_type": "future_local_or_container_runtime",
        "borrowed_pattern": "ProteinMCP catalog radar as non-claim auxiliary evidence",
        "current_runtime_evidence": ["reports/proteinmcp_deep_research_2026_07_31.json"],
        "install_status": "not_installed",
        "license_status": "not_reviewed",
        "probe_status": "not_run",
        "smoke_status": "not_run",
        "register_status": "staging_candidate_only",
        "blockers": ["runtime_not_authorized", "protocol_not_reviewed", "not_model_claim_evidence"],
    },
]


def complete_row(row: dict[str, Any]) -> dict[str, Any]:
    blockers = row.get("blockers") or []
    return {
        **row,
        "lifecycle_state": row["register_status"],
        "status_cache_ttl_seconds": 300,
        "requires_file_lock_for_probe_cache": True,
        "install_probe_register_split": True,
        "requires_execution_receipt": True,
        "requires_license_review": row.get("license_status") != "reviewed_approved",
        "requires_schema_contract": True,
        "production_allowed": False,
        "agent_exposure_allowed": False,
        "training_label_source": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "human_or_external_blocked": bool(blockers),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KWB tool lifecycle registry")
    parser.add_argument("--jsonl-output", type=Path, default=JSONL_OUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = [complete_row(row) for row in TOOLS]
    args.jsonl_output.parent.mkdir(parents=True, exist_ok=True)
    args.jsonl_output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool_rows": len(rows),
        "production_allowed_rows": sum(1 for row in rows if row["production_allowed"]),
        "agent_exposure_allowed_rows": sum(1 for row in rows if row["agent_exposure_allowed"]),
        "training_label_source_rows": sum(1 for row in rows if row["training_label_source"]),
        "safe_for_model_claim": False,
        "release_ready": False,
        "borrowed_from_proteinmcp": [
            "lifecycle registry",
            "install/probe/register split",
            "status cache TTL",
            "tool catalog as radar",
        ],
        "jsonl_path": str(args.jsonl_output.relative_to(AI_ROOT)),
    }
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tool_rows": len(rows), "production_allowed_rows": 0, "safe_for_model_claim": False, "output": str(args.report_output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
