#!/usr/bin/env python3
"""Build the model-quality hard-gate total contract report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "model_quality_hard_gate_contract_report.json"
MINIMUM_BASE_FEATURE_INPUTS = 183

SOURCE_REPORTS = {
    "p183_training_label_import_contract": "reports/training_label_import_contract_report.json",
    "p184_wet_lab_feedback_authorization_contract": "reports/wet_lab_feedback_authorization_contract_report.json",
    "p185_ddg_model_consumption_contract": "reports/ddg_model_consumption_contract_report.json",
    "benchmark_coverage_dashboard_validation": "reports/benchmark_coverage_dashboard_validation_report.json",
    "advanced_model_feature_contract_validation": "reports/advanced_model_feature_contract_validation_report.json",
    "local_release_manifest": "reports/local_release_manifest.json",
    "claim_readiness_matrix": "reports/claim_readiness_matrix.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def claim_by_id(report: dict[str, Any], claim_id: str) -> dict[str, Any]:
    claims = report.get("claims")
    if not isinstance(claims, list):
        return {}
    for item in claims:
        if isinstance(item, dict) and item.get("claim_id") == claim_id:
            return item
    return {}


def build_gate(
    gate_id: str,
    observed: Any,
    expected: Any,
    unlocked: bool,
    source_supported: bool,
    source_ref: str,
    notes: str | None = None,
) -> dict[str, Any]:
    gate = {
        "gate_id": gate_id,
        "observed": observed,
        "expected": expected,
        "unlocked": unlocked,
        "source_supported": source_supported,
        "source_ref": source_ref,
    }
    if notes:
        gate["notes"] = notes
    return gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Build model-quality hard-gate contract report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    paths = {name: AI_ROOT / rel_path for name, rel_path in SOURCE_REPORTS.items()}
    reports = {name: load_json(path) for name, path in paths.items()}
    p183 = reports["p183_training_label_import_contract"]
    p184 = reports["p184_wet_lab_feedback_authorization_contract"]
    p185 = reports["p185_ddg_model_consumption_contract"]
    benchmark = reports["benchmark_coverage_dashboard_validation"]
    advanced = reports["advanced_model_feature_contract_validation"]
    release = reports["local_release_manifest"]
    claim_matrix = reports["claim_readiness_matrix"]

    p183_totals = p183.get("contract_totals") if isinstance(p183.get("contract_totals"), dict) else {}
    p184_values = p184.get("source_values") if isinstance(p184.get("source_values"), dict) else {}
    p185_physics = p185.get("physics_ddg_state") if isinstance(p185.get("physics_ddg_state"), dict) else {}
    benchmark_observed = benchmark.get("observed") if isinstance(benchmark.get("observed"), dict) else {}
    feature_contract = advanced.get("feature_contract") if isinstance(advanced.get("feature_contract"), dict) else {}
    release_summary = release.get("readiness_summary") if isinstance(release.get("readiness_summary"), dict) else {}
    model_quality_claim = claim_by_id(claim_matrix, "model_quality_claim")

    training_import_eligible_rows = as_int(p183_totals.get("training_import_eligible_rows"))
    training_import_written_rows = as_int(p183.get("training_import_written_rows"))
    wetlab_authorized_rows = as_int(p184_values.get("authorized_rows"))
    wetlab_preflight_rows = as_int(p184_values.get("preflight_rows"))
    wetlab_import_rows = as_int(p184_values.get("ready_for_training_import_rows"))
    physics_ddg_ready = p185_physics.get("physics_ddg_ready") is True
    benchmark_ready_for_model_claim = benchmark_observed.get("ready_for_model_claim") is True
    feature_inputs_ready = as_int(feature_contract.get("ready_feature_refs"))
    feature_inputs_input_only = (
        as_int(feature_contract.get("model_input_only_feature_refs")) == feature_inputs_ready
        and as_int(feature_contract.get("training_label_source_feature_refs")) == 0
    )
    feature_inputs_source_supported = (
        advanced.get("success") is True
        and feature_inputs_ready >= MINIMUM_BASE_FEATURE_INPUTS
        and feature_inputs_input_only
    )
    model_quality_ready = False
    safe_for_model_claim = (
        model_quality_claim.get("ready") is True
        and model_quality_claim.get("allowed") is True
        and release_summary.get("master_overall_status") == "ready_for_model_claim"
    )
    release_ready = release.get("release_ready") is True

    hard_gates = [
        build_gate(
            "training_import_eligible_rows",
            training_import_eligible_rows,
            ">0",
            training_import_eligible_rows > 0,
            p183.get("success") is True
            and training_import_eligible_rows > 0
            and as_int(p183_totals.get("training_import_eligible_label_sources")) > 0,
            "reports/training_label_import_contract_report.json",
        ),
        build_gate(
            "wetlab_authorized_rows",
            wetlab_authorized_rows,
            ">0",
            wetlab_authorized_rows > 0,
            p184.get("success") is True and wetlab_authorized_rows > 0,
            "reports/wet_lab_feedback_authorization_contract_report.json",
        ),
        build_gate(
            "wetlab_preflight_rows",
            wetlab_preflight_rows,
            ">0",
            wetlab_preflight_rows > 0,
            p184.get("success") is True and wetlab_preflight_rows > 0,
            "reports/wet_lab_feedback_authorization_contract_report.json",
        ),
        build_gate(
            "wetlab_import_rows",
            wetlab_import_rows,
            0,
            False,
            wetlab_import_rows == 0,
            "reports/wet_lab_feedback_authorization_contract_report.json",
        ),
        build_gate(
            "physics_ddg_ready",
            physics_ddg_ready,
            False,
            False,
            physics_ddg_ready is False and p185_physics.get("executable_ddg_backend_ready") is False,
            "reports/ddg_model_consumption_contract_report.json",
            "The full Rosetta/PyRosetta/FoldX physical ddG lane remains blocked; PyRosetta smoke is computational feature evidence only.",
        ),
        build_gate(
            "benchmark_ready_for_model_claim",
            benchmark_ready_for_model_claim,
            False,
            False,
            benchmark_ready_for_model_claim is False
            and benchmark.get("safe_for_model_claim") is False
            and benchmark.get("release_ready") is False,
            "reports/benchmark_coverage_dashboard_validation_report.json",
        ),
        build_gate(
            "feature_inputs_ready",
            feature_inputs_ready,
            f">={MINIMUM_BASE_FEATURE_INPUTS}",
            False,
            feature_inputs_source_supported,
            "reports/advanced_model_feature_contract_validation_report.json",
            "input-only model features do not authorize model claims.",
        ),
        build_gate(
            "model_quality_ready",
            model_quality_ready,
            False,
            False,
            model_quality_ready is False,
            "reports/claim_readiness_matrix.json",
        ),
        build_gate(
            "safe_for_model_claim",
            safe_for_model_claim,
            False,
            False,
            safe_for_model_claim is False,
            "reports/claim_readiness_matrix.json",
        ),
        build_gate(
            "release_ready",
            release_ready,
            False,
            False,
            release_ready is False,
            "reports/local_release_manifest.json",
        ),
    ]

    source_state = {
        "training_import_eligible_rows": training_import_eligible_rows,
        "training_import_eligible_label_sources": as_int(p183_totals.get("training_import_eligible_label_sources")),
        "training_import_written_rows": training_import_written_rows,
        "wetlab_authorized_rows": wetlab_authorized_rows,
        "wetlab_preflight_rows": wetlab_preflight_rows,
        "wetlab_import_rows": wetlab_import_rows,
        "wetlab_candidate_rows": as_int(p184_values.get("wet_lab_candidate_rows")),
        "wetlab_numeric_training_candidate_rows": as_int(p184_values.get("numeric_training_candidate_rows")),
        "wetlab_claim_eligible_rows_now": as_int(p184_values.get("claim_eligible_rows_now")),
        "physics_ddg_ready": physics_ddg_ready,
        "executable_ddg_backend_ready": p185_physics.get("executable_ddg_backend_ready") is True,
        "benchmark_ready_for_model_claim": benchmark_ready_for_model_claim,
        "benchmark_rows": as_int(benchmark_observed.get("benchmark_rows")),
        "feature_inputs_ready": feature_inputs_ready,
        "feature_inputs_minimum_required": MINIMUM_BASE_FEATURE_INPUTS,
        "feature_inputs_input_only": feature_inputs_input_only,
        "feature_inputs_source_supported": feature_inputs_source_supported,
        "feature_inputs_model_input_only_feature_refs": as_int(feature_contract.get("model_input_only_feature_refs")),
        "feature_inputs_training_label_source_feature_refs": as_int(feature_contract.get("training_label_source_feature_refs")),
        "model_quality_ready": model_quality_ready,
        "safe_for_model_claim": safe_for_model_claim,
        "release_ready": release_ready,
        "local_release_master_status": release_summary.get("master_overall_status"),
        "claim_matrix_model_quality_claim_ready": model_quality_claim.get("ready") is True,
        "claim_matrix_model_quality_claim_allowed": model_quality_claim.get("allowed") is True,
    }

    current_state = {
        "training_import_eligible_rows": training_import_eligible_rows,
        "training_import_written_rows": training_import_written_rows,
        "wetlab_authorized_rows": wetlab_authorized_rows,
        "wetlab_preflight_rows": wetlab_preflight_rows,
        "wetlab_import_rows": wetlab_import_rows,
        "physics_ddg_ready": physics_ddg_ready,
        "benchmark_ready_for_model_claim": benchmark_ready_for_model_claim,
        "feature_inputs_ready": feature_inputs_ready,
        "feature_inputs_minimum_required": MINIMUM_BASE_FEATURE_INPUTS,
        "feature_inputs_input_only": feature_inputs_input_only,
        "model_quality_ready": model_quality_ready,
        "safe_for_model_claim": safe_for_model_claim,
        "release_ready": release_ready,
    }

    success = (
        training_import_eligible_rows > 0
        and wetlab_authorized_rows > 0
        and wetlab_preflight_rows > 0
        and wetlab_import_rows == 0
        and physics_ddg_ready is False
        and benchmark_ready_for_model_claim is False
        and feature_inputs_source_supported
        and model_quality_ready is False
        and safe_for_model_claim is False
        and release_ready is False
        and all(gate["source_supported"] is True for gate in hard_gates)
    )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": success,
        "checked_reports": {name: rel(path) for name, path in paths.items()},
        "current_state": current_state,
        "source_state": source_state,
        "hard_gates": hard_gates,
        "negative_protection_checks": {
            "training_import_eligible_rows_source_supported": training_import_eligible_rows > 0,
            "wetlab_authorized_preflight_source_supported": (
                wetlab_authorized_rows > 0 and wetlab_preflight_rows > 0 and wetlab_import_rows == 0
            ),
            "physics_ddg_ready_fail_closed": physics_ddg_ready is False,
            "benchmark_ready_for_model_claim_false": benchmark_ready_for_model_claim is False,
            "feature_inputs_model_input_only": feature_inputs_input_only,
            "feature_inputs_source_supported": feature_inputs_source_supported,
            "model_quality_ready_false": model_quality_ready is False,
            "safe_for_model_claim_false": safe_for_model_claim is False,
            "release_ready_false": release_ready is False,
        },
        "training_import_eligible_rows": training_import_eligible_rows,
        "training_import_written_rows": training_import_written_rows,
        "wetlab_authorized_rows": wetlab_authorized_rows,
        "wetlab_preflight_rows": wetlab_preflight_rows,
        "wetlab_import_rows": wetlab_import_rows,
        "physics_ddg_ready": physics_ddg_ready,
        "benchmark_ready_for_model_claim": benchmark_ready_for_model_claim,
        "feature_inputs_ready": feature_inputs_ready,
        "feature_inputs_minimum_required": MINIMUM_BASE_FEATURE_INPUTS,
        "feature_inputs_input_only": feature_inputs_input_only,
        "model_quality_ready": model_quality_ready,
        "safe_for_model_claim": safe_for_model_claim,
        "release_ready": release_ready,
        "policy": (
            "Fail-closed aggregate for the model-quality hard gate. "
            "Training import, wet-lab authorization, physics ddG runtime, benchmark claim readiness, "
            "feature-input consumption, model-quality readiness, model claim safety, and release "
            "readiness remain closed unless the source reports explicitly support an unlock."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "training_import_eligible_rows": training_import_eligible_rows,
        "wetlab_authorized_rows": wetlab_authorized_rows,
        "wetlab_preflight_rows": wetlab_preflight_rows,
        "wetlab_import_rows": wetlab_import_rows,
        "physics_ddg_ready": physics_ddg_ready,
        "benchmark_ready_for_model_claim": benchmark_ready_for_model_claim,
        "feature_inputs_ready": feature_inputs_ready,
        "feature_inputs_input_only": feature_inputs_input_only,
        "model_quality_ready": model_quality_ready,
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
