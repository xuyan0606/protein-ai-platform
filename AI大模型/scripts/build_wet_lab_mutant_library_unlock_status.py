#!/usr/bin/env python3
"""Build a fail-closed unlock status board for wet-lab mutant-library data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "wet_lab_mutant_library_unlock_status_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def gate(gate_id: str, name: str, status: str, observed: Any, expected: Any, evidence: str, blocker: str | None) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "name": name,
        "status": status,
        "observed": observed,
        "expected": expected,
        "evidence": evidence,
        "blocker": blocker,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wet-lab mutant-library unlock status")
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()

    assets = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_asset_audit_report.json")
    candidates = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_candidate_report.json")
    operator_packets = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_operator_packet_report.json")
    sequence_evidence = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_sequence_evidence_audit_report.json")
    sequence_intake = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_project_sequence_intake_validation_report.json")
    numbering_audit = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_numbering_audit_from_project_sequences_report.json")
    authorization = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_authorization_validation_report.json")
    preflight = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_preflight_report.json")
    apply_plan = load_json(AI_ROOT / "reports" / "wet_lab_mutant_library_feedback_intake_apply_plan_report.json")
    feedback_intake = load_json(AI_ROOT / "reports" / "experiment_feedback_intake_validation_report.json")
    ddg_backend = load_json(AI_ROOT / "reports" / "ddg_backend_readiness_report.json")
    ddg_probe = load_json(AI_ROOT / "reports" / "ddg_executable_probe_report.json")
    msa_runtime = load_json(AI_ROOT / "reports" / "msa_runtime_readiness_report.json")
    msa_cache = load_json(AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json")
    strict_msa_features = load_json(AI_ROOT / "reports" / "strict_msa_site_feature_report.json")
    label_provenance = load_json(AI_ROOT / "reports" / "label_provenance_audit_report.json")
    model_quality = load_json(AI_ROOT / "reports" / "model_quality_unlock_requirements_report.json")
    release = load_json(AI_ROOT / "reports" / "local_release_manifest.json")

    candidate_rows = candidates.get("candidate_rows", 0)
    numeric_training_candidate_rows = candidates.get("numeric_training_candidate_rows", 0)
    parseable_mutation_rows = candidates.get("parseable_mutation_rows", 0)
    authorized_rows = authorization.get("authorized_candidate_rows", 0)
    sequence_approved_projects = set(sequence_intake.get("approved_projects") or [])
    executable_ddg_ready = bool(ddg_backend.get("executable_ddg_backend_ready")) or bool(ddg_probe.get("executable_ddg_backend_ready"))
    strict_msa_feature_rows = int(strict_msa_features.get("feature_rows") or 0)
    msa_ready_for_wet_lab_feature_use = (
        bool(msa_runtime.get("runtime_ready"))
        and bool(msa_cache.get("ready"))
        and strict_msa_feature_rows > 0
    )

    gates = [
        gate(
            "WLM-G001",
            "wet_lab_source_assets_present",
            "ready_to_verify" if assets.get("csv_file_count", 0) > 0 else "blocked",
            assets.get("csv_file_count", 0),
            ">0 real wet-lab CSV files",
            "reports/wet_lab_mutant_library_asset_audit_report.json",
            None if assets.get("csv_file_count", 0) > 0 else "no_wet_lab_csv_assets",
        ),
        gate(
            "WLM-G002",
            "mutation_parsing",
            "ready_to_verify" if parseable_mutation_rows > 0 else "blocked",
            parseable_mutation_rows,
            ">0 parseable mutation rows",
            "reports/wet_lab_mutant_library_feedback_candidate_report.json",
            None if parseable_mutation_rows > 0 else "no_parseable_mutations",
        ),
        gate(
            "WLM-G003",
            "strict_numeric_feedback_candidates",
            "ready_to_verify" if numeric_training_candidate_rows > 0 else "blocked",
            numeric_training_candidate_rows,
            ">0 numeric candidates before authorization",
            "datasets/feedback/wet_lab_mutant_library_feedback_candidates.jsonl",
            None if numeric_training_candidate_rows > 0 else "no_numeric_training_candidates",
        ),
        gate(
            "WLM-G004",
            "human_feedback_authorization",
            "ready_to_verify" if authorized_rows > 0 else "blocked",
            authorized_rows,
            f"{numeric_training_candidate_rows} authorized candidate rows",
            "reports/wet_lab_mutant_library_feedback_authorization_validation_report.json",
            None if authorized_rows > 0 else "authorization_rows_missing_or_not_approved",
        ),
        gate(
            "WLM-G005",
            "16b_parent_sequence_numbering",
            "ready_to_verify" if "16B" in sequence_approved_projects else "blocked",
            "16B" in sequence_approved_projects,
            True,
            "reports/wet_lab_mutant_library_project_sequence_intake_validation_report.json",
            None if "16B" in sequence_approved_projects else "reviewed_16b_parent_sequence_missing",
        ),
        gate(
            "WLM-G006",
            "4g_parent_sequence_numbering",
            "ready_to_verify" if "4G" in sequence_approved_projects else "blocked",
            "4G" in sequence_approved_projects,
            True,
            "reports/wet_lab_mutant_library_project_sequence_intake_validation_report.json",
            None if "4G" in sequence_approved_projects else "reviewed_4g_parent_sequence_missing",
        ),
        gate(
            "WLM-G007",
            "numbering_audit_rows",
            "ready_to_verify" if numbering_audit.get("numbering_verified_candidate_rows", 0) > 0 else "blocked",
            numbering_audit.get("numbering_verified_candidate_rows", 0),
            ">0 verified candidate rows from approved project sequences",
            "reports/wet_lab_mutant_library_numbering_audit_from_project_sequences_report.json",
            None if numbering_audit.get("numbering_verified_candidate_rows", 0) > 0 else "numbering_audit_has_no_verified_rows",
        ),
        gate(
            "WLM-G008",
            "feedback_preflight_rows",
            "ready_to_verify" if preflight.get("preflight_rows", 0) > 0 else "blocked",
            preflight.get("preflight_rows", 0),
            ">0 preflight rows",
            "reports/wet_lab_mutant_library_feedback_preflight_report.json",
            None if preflight.get("preflight_rows", 0) > 0 else "no_authorized_preflight_rows",
        ),
        gate(
            "WLM-G009",
            "feedback_apply_plan_rows",
            "ready_to_verify" if apply_plan.get("apply_plan_rows", 0) > 0 else "blocked",
            apply_plan.get("apply_plan_rows", 0),
            ">0 apply-plan rows after explicit authorization",
            "reports/wet_lab_mutant_library_feedback_intake_apply_plan_report.json",
            None if apply_plan.get("apply_plan_rows", 0) > 0 else "apply_plan_empty",
        ),
        gate(
            "WLM-G010",
            "physics_ddg_backend",
            "ready_to_verify" if executable_ddg_ready else "blocked",
            executable_ddg_ready,
            True,
            "reports/ddg_executable_probe_report.json",
            None if executable_ddg_ready else "rosetta_pyrosetta_foldx_executable_backend_not_ready",
        ),
        gate(
            "WLM-G011",
            "msa_runtime_and_cache",
            "ready_to_verify" if msa_ready_for_wet_lab_feature_use else "blocked",
            {
                "runtime_ready": bool(msa_runtime.get("runtime_ready")),
                "cache_ready": bool(msa_cache.get("ready")),
                "valid_cache_rows": msa_cache.get("valid_rows"),
                "strict_msa_site_feature_rows": strict_msa_feature_rows,
            },
            {"runtime_ready": True, "cache_ready": True, "strict_msa_site_feature_rows": ">0"},
            "reports/strict_msa_site_feature_report.json",
            None if msa_ready_for_wet_lab_feature_use else "msa_runtime_cache_or_strict_site_features_not_ready",
        ),
        gate(
            "WLM-G012",
            "claim_eligible_real_supervised_rows",
            "ready_to_verify" if label_provenance.get("claim_eligible_rows", 0) >= 100 else "blocked",
            label_provenance.get("claim_eligible_rows", 0),
            ">=100 claim-eligible real supervised rows",
            "reports/label_provenance_audit_report.json",
            None if label_provenance.get("claim_eligible_rows", 0) >= 100 else "strict_claim_eligible_rows_below_threshold",
        ),
    ]

    blocked_gates = [row for row in gates if row["status"] == "blocked"]
    ready_to_verify_gates = [row for row in gates if row["status"] == "ready_to_verify"]
    hard_blockers = [row["blocker"] for row in blocked_gates if row.get("blocker")]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "wet_lab_summary": {
            "candidate_rows": candidate_rows,
            "parseable_mutation_rows": parseable_mutation_rows,
            "numeric_training_candidate_rows": numeric_training_candidate_rows,
            "operator_sequence_request_packets": operator_packets.get("sequence_request_packet_rows", 0),
            "operator_feedback_review_packets": operator_packets.get("feedback_review_packet_rows", 0),
            "authorization_rows": authorization.get("authorization_rows", 0),
            "authorized_candidate_rows": authorized_rows,
            "preflight_rows": preflight.get("preflight_rows", 0),
            "apply_plan_rows": apply_plan.get("apply_plan_rows", 0),
            "formal_experiment_feedback_training_eligible_rows": feedback_intake.get("training_eligible_rows"),
            "accepted_sequence_evidence_rows": sequence_evidence.get("accepted_sequence_evidence_rows", 0),
            "approved_sequence_projects": sorted(sequence_approved_projects),
            "numbering_audit_rows": numbering_audit.get("audit_rows", 0),
            "numbering_verified_candidate_rows": numbering_audit.get("numbering_verified_candidate_rows", 0),
        },
        "runtime_summary": {
            "msa_runtime_ready": bool(msa_runtime.get("runtime_ready")),
            "msa_cache_ready": bool(msa_cache.get("ready")),
            "strict_msa_site_feature_rows": strict_msa_feature_rows,
            "ddg_proxy_backend_ready": bool(ddg_backend.get("proxy_ddg_backend_ready")),
            "ddg_executable_backend_ready": executable_ddg_ready,
            "rosetta_executable_found": bool(ddg_probe.get("rosetta_executable_found")),
            "foldx_executable_found": bool(ddg_probe.get("foldx_executable_found")),
            "pyrosetta_module_available": bool(ddg_probe.get("pyrosetta_module_available")),
        },
        "quality_summary": {
            "model_quality_ready": bool(model_quality.get("model_quality_ready")),
            "release_ready": bool(release.get("release_ready")),
            "safe_for_model_claim": False,
            "claim_eligible_rows": label_provenance.get("claim_eligible_rows"),
            "synthetic_or_unreceipted_rows": label_provenance.get("synthetic_or_unreceipted_rows"),
        },
        "gate_rows": len(gates),
        "ready_to_verify_gates": len(ready_to_verify_gates),
        "blocked_gates": len(blocked_gates),
        "hard_blockers": hard_blockers,
        "gates": gates,
        "next_operator_files": [
            "datasets/feedback/wet_lab_mutant_library_feedback_review_packets.jsonl",
            "datasets/feedback/wet_lab_mutant_library_sequence_request_packets.jsonl",
            "datasets/governance/wet_lab_mutant_library_unlock_actions.jsonl",
        ],
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Status board is fail-closed; ready_to_verify means evidence exists for review, not approval or model-quality claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "gate_rows": report["gate_rows"],
        "ready_to_verify_gates": report["ready_to_verify_gates"],
        "blocked_gates": report["blocked_gates"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "release_ready": report["release_ready"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
