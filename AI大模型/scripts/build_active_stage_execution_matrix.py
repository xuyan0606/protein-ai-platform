#!/usr/bin/env python3
"""Build a fail-closed execution matrix for active P26-P31 workstreams."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "active_stage_execution_matrix_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "active_stage_execution_matrix.jsonl"


def load_json(rel: str) -> dict[str, Any]:
    path = AI_ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def row(
    stage_id: str,
    title: str,
    status: str,
    evidence: dict[str, Any],
    nonhuman_next: list[str],
    human_next: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "title": title,
        "status": status,
        "evidence": evidence,
        "nonhuman_next_actions": nonhuman_next,
        "human_or_external_next_actions": human_next,
        "blockers": blockers,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
    }


def main() -> int:
    structure_cache = load_json("reports/structure_cache_manifest_validation_report.json")
    domain_status = load_json("reports/domain_interval_batch_status_report.json")
    numbering_validation = load_json("reports/numbering_curation_validation_report.json")
    validated_features = load_json("reports/validated_feature_index_report.json")
    strict_msa = load_json("reports/strict_msa_site_feature_report.json")
    structure_contract = load_json("reports/structure_feature_model_contract_report.json")
    wetlab = load_json("reports/wet_lab_feedback_authorization_contract_report.json")
    feedback_semantic = load_json("reports/feedback_training_import_semantic_guard_report.json")
    training_import = load_json("reports/training_label_import_contract_report.json")
    five_head = load_json("reports/five_head_training_execution_contract_report.json")
    model_quality = load_json("reports/model_quality_hard_gate_contract_report.json")
    release = load_json("reports/local_release_manifest.json")
    customer = load_json("reports/customer_delivery_readiness_report.json")
    workstream = load_json("reports/workstream_acceptance_gates.json")

    rows = [
        row(
            "P26",
            "真实数据解阻第一波",
            "partially_unblocked_fail_closed",
            {
                "numbering_formal_decision_rows": numbering_validation.get("decision_rows"),
                "structure_cache_validation_success": structure_cache.get("success"),
                "structure_cache_present_rows": structure_cache.get("acquisition_present_rows"),
                "structure_cache_sha256_mismatch_rows": structure_cache.get("sha256_mismatch_rows"),
                "domain_decided_rows": domain_status.get("decided_rows"),
                "domain_undecided_rows": domain_status.get("undecided_rows"),
                "domain_coverage": domain_status.get("coverage"),
            },
            [
                "continue domain evidence retrieval for 157 undecided domain rows",
                "refresh structure cache validator after any cache file changes",
                "prepare numbering review evidence packets without writing formal decisions",
            ],
            [
                "review and approve/reject numbering decisions",
                "review remaining domain interval evidence where no exact InterPro decision exists",
            ],
            [
                "formal reviewed numbering decisions remain below claim threshold",
                "157 domain interval rows remain undecided",
                "unreviewed chain mappings cannot enter reviewed graph features",
            ],
        ),
        row(
            "P27",
            "序列/结构特征生产",
            "input_features_partially_ready_fail_closed",
            {
                "validated_feature_rows": validated_features.get("feature_rows"),
                "validated_feature_model_consumable_rows": validated_features.get("model_consumable_rows"),
                "validated_feature_training_label_source_rows": validated_features.get("training_label_source_rows"),
                "strict_msa_input_rows": strict_msa.get("input_rows"),
                "strict_msa_feature_rows": strict_msa.get("feature_rows"),
                "structure_feature_contract_status": structure_contract.get("status"),
                "domain_decided_rows": domain_status.get("decided_rows"),
                "domain_undecided_rows": domain_status.get("undecided_rows"),
            },
            [
                "rebuild validated feature index after P26 domain/structure updates",
                "generate feature-only coverage report by head and protein group",
                "keep MSA/structure/domain rows marked input-only",
            ],
            [
                "review chain mappings before adding more structure graph rows",
                "review numbering before joining features to training labels",
            ],
            [
                "strict MSA feature table has zero input rows because strict supervised rows remain closed",
                "features are not training labels",
                "475 unreviewed coordinate rows remain excluded from reviewed graph features",
            ],
        ),
        row(
            "P28",
            "实验反馈闭环",
            "candidate_evidence_ready_authorization_blocked",
            {
                "wet_lab_candidate_rows": wetlab.get("candidate_rows"),
                "numeric_training_candidate_rows": wetlab.get("numeric_training_candidate_rows"),
                "authorization_rows": wetlab.get("authorization_rows"),
                "authorized_rows": wetlab.get("authorized_rows"),
                "preflight_rows": wetlab.get("preflight_rows"),
                "ready_for_training_import_rows": wetlab.get("ready_for_training_import_rows"),
                "qualitative_feedback_eligible": feedback_semantic.get("qualitative_feedback_eligible"),
                "numeric_training_import_eligible": feedback_semantic.get("numeric_training_import_eligible"),
            },
            [
                "refresh wet-lab authorization worklists and closeout boards",
                "validate source/numbering/unit/batch/replicate fields remain explicit",
                "prepare training-import preflight only after authorization rows exist",
            ],
            [
                "human authorization for 12 numeric candidates",
                "QC decision and reviewer/date/basis for each approved metric",
                "explicit permission before appending approved rows to local feedback intake",
            ],
            [
                "0 authorized rows",
                "0 preflight rows",
                "qualitative feedback cannot be used as numeric supervised labels",
            ],
        ),
        row(
            "P29",
            "五头统一模型训练",
            "training_execution_blocked",
            {
                "ready_head_count": five_head.get("ready_head_count"),
                "total_head_training_rows": five_head.get("total_head_training_rows"),
                "training_execution_allowed": five_head.get("training_execution_allowed"),
                "training_import_eligible_rows": model_quality.get("training_import_eligible_rows"),
                "benchmark_ready_for_model_claim": model_quality.get("benchmark_ready_for_model_claim"),
                "feature_inputs_ready": model_quality.get("feature_inputs_ready"),
                "feature_inputs_input_only": model_quality.get("feature_inputs_input_only"),
            },
            [
                "keep five-head training contract refreshed",
                "run scaffold/interface regressions only",
                "quantify missing rows per head without training a claimable model",
            ],
            [
                "approve/import enough reviewed labels per head",
                "approve benchmark scorecards before model-quality claims",
            ],
            [
                "ready_head_count is 0",
                "training-import-eligible rows are 0",
                "benchmark ready_for_model_claim is false",
            ],
        ),
        row(
            "P30",
            "本地平台验收",
            "local_review_package_fail_closed",
            {
                "local_release_artifact_count": release.get("artifact_count"),
                "local_release_ready": release.get("release_ready"),
                "customer_delivery_ready": customer.get("ready"),
                "workstream_total_streams": workstream.get("total_streams"),
                "workstream_accepted_streams": workstream.get("accepted_streams"),
                "workstream_all_accepted": workstream.get("all_accepted"),
            },
            [
                "refresh local release manifest and safety guard links",
                "keep acceptance gates visible in the local review package",
                "run local-only smoke/validator evidence",
            ],
            [
                "human acceptance for workstream gates",
                "customer-delivery/IP/license/biosecurity approvals before any external claim",
            ],
            [
                "release_ready is false",
                "customer delivery ready is false",
                "0 workstreams human-accepted",
            ],
        ),
        row(
            "P31",
            "生产接入评审",
            "review_preparation_only",
            {
                "local_release_ready": release.get("release_ready"),
                "customer_delivery_ready": customer.get("ready"),
                "workstream_all_accepted": workstream.get("all_accepted"),
                "explicit_production_authorization_present": False,
            },
            [
                "prepare pre-sync requirement checklist",
                "prepare rollback and smoke-test review material",
                "validate production execution remains disabled",
            ],
            [
                "explicit user authorization for production sync/deploy/restart",
                "release/capability acceptance gates must be resolved first",
            ],
            [
                "no explicit production authorization",
                "release_ready is false",
                "production execution is forbidden in the current request",
            ],
        ),
    ]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "stage_count": len(rows),
        "rows": rows,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Execution matrix for active P26-P31 workstreams. It provides next actions and blockers only; it does not authorize training import, model claims, release, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    JSONL_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSONL_OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps({
        "stage_count": report["stage_count"],
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
