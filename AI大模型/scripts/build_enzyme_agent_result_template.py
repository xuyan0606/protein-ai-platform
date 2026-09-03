#!/usr/bin/env python3
"""Build a fail-closed structured result template for enzyme agent outputs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "enzyme_agent_result_template.json"

FORMAL_NUMBERING = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
FORMAL_STRUCTURE = AI_ROOT / "datasets" / "curation" / "structure_chain_mapping_decisions.jsonl"
FORMAL_WET_LAB_AUTH = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"

REQUIRED_FORBIDDEN_CLAIMS = [
    "model_quality_claim",
    "customer_delivery",
    "approved_for_ordering",
    "release_ready",
    "training_import",
    "safe_for_model_claim",
    "pyrosetta_physics_ddg_training_or_release_claim",
    "rosetta_or_foldx_physics_ddg_integrated",
    "reviewed_numbering_complete",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Build enzyme agent structured result template")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    resource_plan = load_json(AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_report.json")
    resource_validation = load_json(AI_ROOT / "reports" / "enzyme_resource_retrieval_plan_validation_report.json")
    label_provenance = load_json(AI_ROOT / "reports" / "label_provenance_audit_report.json")
    strict_msa = load_json(AI_ROOT / "reports" / "strict_msa_site_feature_report.json")
    claim_matrix = load_json(AI_ROOT / "reports" / "claim_readiness_matrix.json")
    local_release = load_json(AI_ROOT / "reports" / "local_release_manifest.json")
    ddg_backend = load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json")
    wet_lab_preflight = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_preflight_report.json")
    benchmark_cache = load_json(AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json")

    reviewed_numbering_rows = count_jsonl_rows(FORMAL_NUMBERING)
    reviewed_structure_chain_rows = count_jsonl_rows(FORMAL_STRUCTURE)
    wet_lab_authorization_rows = count_jsonl_rows(FORMAL_WET_LAB_AUTH)
    claim_eligible_rows = int(label_provenance.get("claim_eligible_rows") or 0)
    strict_msa_rows = int(strict_msa.get("feature_rows") or 0)

    blocked_reasons = []
    if claim_eligible_rows < 100:
        blocked_reasons.append("claim_eligible_training_rows_below_100")
    if reviewed_numbering_rows < 75:
        blocked_reasons.append("reviewed_numbering_rows_below_75")
    if wet_lab_authorization_rows == 0:
        blocked_reasons.append("wet_lab_feedback_authorization_rows_zero")
    if resource_validation.get("success") is not True:
        blocked_reasons.append("resource_plan_validation_not_success")
    if local_release.get("release_ready") is not False:
        blocked_reasons.append("local_release_ready_state_unexpected")

    result = {
        "result_id": "enzyme_agent_result_template_20260731_p168",
        "created_at": created_at,
        "local_only": True,
        "source_plan_id": resource_plan.get("plan_id") or "missing_resource_plan",
        "request_class": "enzyme_mutation_analysis_result_template_fail_closed",
        "selected_variants": [],
        "property_predictions": [
            {
                "head": "mutation_rank",
                "status": "blocked_no_claim_eligible_training_rows",
                "safe_to_rank_for_customer": False,
            },
            {
                "head": "stability",
                "status": "proxy_ddg_available_but_not_training_label",
                "safe_to_rank_for_customer": False,
            },
            {
                "head": "activity_risk",
                "status": "blocked_no_authorized_numeric_wet_lab_feedback",
                "safe_to_rank_for_customer": False,
            },
            {
                "head": "substrate_fit",
                "status": "blocked_pending_reviewed_structure_and_substrate_evidence",
                "safe_to_rank_for_customer": False,
            },
            {
                "head": "assay_success",
                "status": "blocked_no_training_eligible_plate_feedback",
                "safe_to_rank_for_customer": False,
            },
        ],
        "ddg_results": [
            {
                "backend_family": "ThermoMPNN_proxy",
                "ready": bool(ddg_backend.get("proxy_ddg_backend_ready") or ddg_backend.get("one_ddg_backend_ready")),
                "negative_ddg_is_stabilizing": True,
                "usable_for": "manual_review_support_only",
                "safe_for_model_claim": False,
            },
            {
                "backend_family": "Rosetta/PyRosetta/FoldX_physics",
                "ready": bool(ddg_backend.get("executable_ddg_backend_ready")),
                "negative_ddg_is_stabilizing": True,
                "usable_for": "local_noncommercial_runtime_feature_manual_review_only" if ddg_backend.get("executable_ddg_backend_ready") else "blocked_until_license_runtime_receipt",
                "safe_for_model_claim": False,
            },
        ],
        "evidence_summary": {
            "reviewed_numbering_rows": reviewed_numbering_rows,
            "reviewed_structure_chain_mapping_rows": reviewed_structure_chain_rows,
            "claim_eligible_training_rows": claim_eligible_rows,
            "strict_msa_site_feature_rows": strict_msa_rows,
            "wet_lab_authorization_rows": wet_lab_authorization_rows,
            "wet_lab_preflight_rows": int(wet_lab_preflight.get("preflight_rows") or 0),
            "benchmark_score_cache_ready": bool(benchmark_cache.get("ready_for_model_claim")),
            "claim_matrix_blocked_claims": claim_matrix.get("claims_blocked"),
            "resource_plan_validation_success": bool(resource_validation.get("success")),
            "resource_plan_blocked_actions": (resource_plan.get("summary") or {}).get("blocked_requires_human_decision_rows"),
            "resource_plan_forbidden_actions": (resource_plan.get("summary") or {}).get("forbidden_for_current_request_rows"),
            "local_release_ready": bool(local_release.get("release_ready")),
        },
        "manual_review_required": True,
        "experimental_plan": {
            "status": "blocked_pending_review",
            "allowed_next_step": "Use this template to display blocked evidence and prepare manual numbering, wet-lab authorization, benchmark, or ddG runtime review; do not execute training import.",
            "blocked_reason": ";".join(blocked_reasons) if blocked_reasons else "manual_review_required_before_any_go_recommendation",
        },
        "forbidden_claims": REQUIRED_FORBIDDEN_CLAIMS,
        "artifact_refs": [
            "schemas/enzyme_agent_result.schema.json",
            "reports/enzyme_resource_retrieval_plan_report.json",
            "reports/enzyme_resource_retrieval_plan_validation_report.json",
            "reports/label_provenance_audit_report.json",
            "reports/strict_msa_site_feature_report.json",
            "reports/claim_readiness_matrix.json",
            "reports/local_release_manifest.json",
            "reports/ddg_backend_readiness_report.json",
        ],
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed output contract for future enzyme agent recommendations. No selected variant may be treated as Go, training import, model-quality claim, customer delivery, ordering approval, or release approval from this template.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "result_id": result["result_id"],
        "selected_variants": len(result["selected_variants"]),
        "claim_eligible_training_rows": claim_eligible_rows,
        "manual_review_required": True,
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
