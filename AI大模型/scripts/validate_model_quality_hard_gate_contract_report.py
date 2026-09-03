#!/usr/bin/env python3
"""Validate the model-quality hard-gate total contract fail closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "model_quality_hard_gate_contract_report.json"
OUT = AI_ROOT / "reports" / "model_quality_hard_gate_contract_validation_report.json"
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
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


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
    parser = argparse.ArgumentParser(description="Validate model-quality hard-gate contract report")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    contract = load_json(args.report)
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

    failures: list[dict[str, Any]] = []

    fail_if(not contract, failures, "contract_report_present", str(args.report), "existing JSON report")
    fail_if(
        bool([name for name, path in paths.items() if not path.exists()]),
        failures,
        "required_source_reports_present",
        [rel(path) for path in paths.values() if not path.exists()],
        [],
    )
    fail_if(
        bool([name for name, report in reports.items() if not report]),
        failures,
        "required_source_reports_non_empty",
        [name for name, report in reports.items() if not report],
        [],
    )

    expected = {
        "training_import_eligible_rows": as_int(p183_totals.get("training_import_eligible_rows")),
        "training_import_written_rows": as_int(p183.get("training_import_written_rows")),
        "wetlab_authorized_rows": as_int(p184_values.get("authorized_rows")),
        "wetlab_preflight_rows": as_int(p184_values.get("preflight_rows")),
        "wetlab_import_rows": as_int(p184_values.get("ready_for_training_import_rows")),
        "physics_ddg_ready": False,
        "benchmark_ready_for_model_claim": False,
        "feature_inputs_ready": as_int(feature_contract.get("ready_feature_refs")),
        "feature_inputs_minimum_required": MINIMUM_BASE_FEATURE_INPUTS,
        "feature_inputs_input_only": True,
        "model_quality_ready": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    observed = {
        "training_import_eligible_rows": as_int(p183_totals.get("training_import_eligible_rows")),
        "training_import_written_rows": as_int(p183.get("training_import_written_rows")),
        "wetlab_authorized_rows": as_int(p184_values.get("authorized_rows")),
        "wetlab_preflight_rows": as_int(p184_values.get("preflight_rows")),
        "wetlab_import_rows": as_int(p184_values.get("ready_for_training_import_rows")),
        "physics_ddg_ready": p185_physics.get("physics_ddg_ready") is True,
        "benchmark_ready_for_model_claim": benchmark_observed.get("ready_for_model_claim") is True,
        "feature_inputs_ready": as_int(feature_contract.get("ready_feature_refs")),
        "feature_inputs_minimum_required": MINIMUM_BASE_FEATURE_INPUTS,
        "feature_inputs_input_only": (
            as_int(feature_contract.get("model_input_only_feature_refs")) == as_int(feature_contract.get("ready_feature_refs"))
            and as_int(feature_contract.get("training_label_source_feature_refs")) == 0
        ),
        "feature_inputs_source_supported": (
            advanced.get("success") is True
            and as_int(feature_contract.get("ready_feature_refs")) >= MINIMUM_BASE_FEATURE_INPUTS
            and (
                as_int(feature_contract.get("model_input_only_feature_refs"))
                == as_int(feature_contract.get("ready_feature_refs"))
            )
            and as_int(feature_contract.get("training_label_source_feature_refs")) == 0
        ),
        "model_quality_ready": False,
        "safe_for_model_claim": (
            model_quality_claim.get("ready") is True
            and model_quality_claim.get("allowed") is True
            and release_summary.get("master_overall_status") == "ready_for_model_claim"
        ),
        "release_ready": release.get("release_ready") is True,
    }
    expected_hard_gates = [
        build_gate(
            "training_import_eligible_rows",
            observed["training_import_eligible_rows"],
            ">0",
            observed["training_import_eligible_rows"] > 0,
            p183.get("success") is True
            and observed["training_import_eligible_rows"] > 0
            and as_int(p183_totals.get("training_import_eligible_label_sources")) > 0,
            "reports/training_label_import_contract_report.json",
        ),
        build_gate(
            "wetlab_authorized_rows",
            observed["wetlab_authorized_rows"],
            ">0",
            observed["wetlab_authorized_rows"] > 0,
            p184.get("success") is True and observed["wetlab_authorized_rows"] > 0,
            "reports/wet_lab_feedback_authorization_contract_report.json",
        ),
        build_gate(
            "wetlab_preflight_rows",
            observed["wetlab_preflight_rows"],
            ">0",
            observed["wetlab_preflight_rows"] > 0,
            p184.get("success") is True and observed["wetlab_preflight_rows"] > 0,
            "reports/wet_lab_feedback_authorization_contract_report.json",
        ),
        build_gate(
            "wetlab_import_rows",
            observed["wetlab_import_rows"],
            0,
            False,
            observed["wetlab_import_rows"] == 0,
            "reports/wet_lab_feedback_authorization_contract_report.json",
        ),
        build_gate(
            "physics_ddg_ready",
            observed["physics_ddg_ready"],
            False,
            False,
            observed["physics_ddg_ready"] is False and p185_physics.get("executable_ddg_backend_ready") is False,
            "reports/ddg_model_consumption_contract_report.json",
            "The full Rosetta/PyRosetta/FoldX physical ddG lane remains blocked; PyRosetta smoke is computational feature evidence only.",
        ),
        build_gate(
            "benchmark_ready_for_model_claim",
            observed["benchmark_ready_for_model_claim"],
            False,
            False,
            observed["benchmark_ready_for_model_claim"] is False
            and benchmark.get("safe_for_model_claim") is False
            and benchmark.get("release_ready") is False,
            "reports/benchmark_coverage_dashboard_validation_report.json",
        ),
        build_gate(
            "feature_inputs_ready",
            observed["feature_inputs_ready"],
            f">={MINIMUM_BASE_FEATURE_INPUTS}",
            False,
            observed["feature_inputs_source_supported"],
            "reports/advanced_model_feature_contract_validation_report.json",
            "input-only model features do not authorize model claims.",
        ),
        build_gate("model_quality_ready", False, False, False, True, "reports/claim_readiness_matrix.json"),
        build_gate("safe_for_model_claim", observed["safe_for_model_claim"], False, False, observed["safe_for_model_claim"] is False, "reports/claim_readiness_matrix.json"),
        build_gate("release_ready", observed["release_ready"], False, False, observed["release_ready"] is False, "reports/local_release_manifest.json"),
    ]
    expected_source_state = {
        "training_import_eligible_rows": observed["training_import_eligible_rows"],
        "training_import_eligible_label_sources": as_int(p183_totals.get("training_import_eligible_label_sources")),
        "training_import_written_rows": observed["training_import_written_rows"],
        "wetlab_authorized_rows": observed["wetlab_authorized_rows"],
        "wetlab_preflight_rows": observed["wetlab_preflight_rows"],
        "wetlab_import_rows": observed["wetlab_import_rows"],
        "wetlab_candidate_rows": as_int(p184_values.get("wet_lab_candidate_rows")),
        "wetlab_numeric_training_candidate_rows": as_int(p184_values.get("numeric_training_candidate_rows")),
        "wetlab_claim_eligible_rows_now": as_int(p184_values.get("claim_eligible_rows_now")),
        "physics_ddg_ready": observed["physics_ddg_ready"],
        "executable_ddg_backend_ready": p185_physics.get("executable_ddg_backend_ready") is True,
        "benchmark_ready_for_model_claim": observed["benchmark_ready_for_model_claim"],
        "benchmark_rows": as_int(benchmark_observed.get("benchmark_rows")),
        "feature_inputs_ready": observed["feature_inputs_ready"],
        "feature_inputs_minimum_required": MINIMUM_BASE_FEATURE_INPUTS,
        "feature_inputs_input_only": observed["feature_inputs_input_only"],
        "feature_inputs_source_supported": observed["feature_inputs_source_supported"],
        "feature_inputs_model_input_only_feature_refs": as_int(feature_contract.get("model_input_only_feature_refs")),
        "feature_inputs_training_label_source_feature_refs": as_int(feature_contract.get("training_label_source_feature_refs")),
        "model_quality_ready": False,
        "safe_for_model_claim": observed["safe_for_model_claim"],
        "release_ready": observed["release_ready"],
        "local_release_master_status": release_summary.get("master_overall_status"),
        "claim_matrix_model_quality_claim_ready": model_quality_claim.get("ready") is True,
        "claim_matrix_model_quality_claim_allowed": model_quality_claim.get("allowed") is True,
    }
    expected_negative_checks = {
        "training_import_eligible_rows_source_supported": observed["training_import_eligible_rows"] > 0,
        "wetlab_authorized_preflight_source_supported": (
            observed["wetlab_authorized_rows"] > 0
            and observed["wetlab_preflight_rows"] > 0
            and observed["wetlab_import_rows"] == 0
        ),
        "physics_ddg_ready_fail_closed": observed["physics_ddg_ready"] is False,
        "benchmark_ready_for_model_claim_false": observed["benchmark_ready_for_model_claim"] is False,
        "feature_inputs_model_input_only": observed["feature_inputs_input_only"],
        "feature_inputs_source_supported": observed["feature_inputs_source_supported"],
        "model_quality_ready_false": True,
        "safe_for_model_claim_false": observed["safe_for_model_claim"] is False,
        "release_ready_false": observed["release_ready"] is False,
    }
    expected_full_report = {
        "created_at": contract.get("created_at"),
        "local_only": True,
        "success": (
            observed["training_import_eligible_rows"] > 0
            and observed["wetlab_authorized_rows"] > 0
            and observed["wetlab_preflight_rows"] > 0
            and observed["wetlab_import_rows"] == 0
            and observed["physics_ddg_ready"] is False
            and observed["benchmark_ready_for_model_claim"] is False
            and observed["feature_inputs_source_supported"]
            and observed["model_quality_ready"] is False
            and observed["safe_for_model_claim"] is False
            and observed["release_ready"] is False
            and all(gate["source_supported"] is True for gate in expected_hard_gates)
        ),
        "checked_reports": {name: rel(path) for name, path in paths.items()},
        "current_state": expected,
        "source_state": expected_source_state,
        "hard_gates": expected_hard_gates,
        "negative_protection_checks": expected_negative_checks,
        "training_import_eligible_rows": observed["training_import_eligible_rows"],
        "training_import_written_rows": observed["training_import_written_rows"],
        "wetlab_authorized_rows": observed["wetlab_authorized_rows"],
        "wetlab_preflight_rows": observed["wetlab_preflight_rows"],
        "wetlab_import_rows": observed["wetlab_import_rows"],
        "physics_ddg_ready": observed["physics_ddg_ready"],
        "benchmark_ready_for_model_claim": observed["benchmark_ready_for_model_claim"],
        "feature_inputs_ready": observed["feature_inputs_ready"],
        "feature_inputs_minimum_required": MINIMUM_BASE_FEATURE_INPUTS,
        "feature_inputs_input_only": observed["feature_inputs_input_only"],
        "model_quality_ready": False,
        "safe_for_model_claim": observed["safe_for_model_claim"],
        "release_ready": observed["release_ready"],
        "policy": (
            "Fail-closed aggregate for the model-quality hard gate. "
            "Training import, wet-lab authorization, physics ddG runtime, benchmark claim readiness, "
            "feature-input consumption, model-quality readiness, model claim safety, and release "
            "readiness remain closed unless the source reports explicitly support an unlock."
        ),
    }

    report_current = contract.get("current_state") if isinstance(contract.get("current_state"), dict) else {}
    fail_if(contract != expected_full_report, failures, "contract_report_matches_current_sources", contract, expected_full_report)
    for key, value in expected.items():
        fail_if(observed[key] != value, failures, f"source_{key}_expected", observed[key], value)
        fail_if(report_current.get(key) != value, failures, f"contract_{key}_matches_expected", report_current.get(key), value)
        fail_if(contract.get(key) != value, failures, f"top_level_{key}_matches_expected", contract.get(key), value)

    report_hard_gates = contract.get("hard_gates") if isinstance(contract.get("hard_gates"), list) else []
    fail_if(len(report_hard_gates) != 10, failures, "hard_gate_count_ten", len(report_hard_gates), 10)
    hard_gate_by_id: dict[str, dict[str, Any]] = {}
    for item in report_hard_gates:
        if isinstance(item, dict) and isinstance(item.get("gate_id"), str):
            hard_gate_by_id[item["gate_id"]] = item

    expected_hard_gate_ids = {
        "training_import_eligible_rows",
        "wetlab_authorized_rows",
        "wetlab_preflight_rows",
        "wetlab_import_rows",
        "physics_ddg_ready",
        "benchmark_ready_for_model_claim",
        "feature_inputs_ready",
        "model_quality_ready",
        "safe_for_model_claim",
        "release_ready",
    }
    fail_if(set(hard_gate_by_id) != expected_hard_gate_ids, failures, "hard_gate_ids_match", sorted(hard_gate_by_id), sorted(expected_hard_gate_ids))
    fail_if(report_hard_gates != expected_hard_gates, failures, "hard_gates_match_current_sources", report_hard_gates, expected_hard_gates)
    fail_if(contract.get("source_state") != expected_source_state, failures, "source_state_matches_current_sources", contract.get("source_state"), expected_source_state)
    fail_if(
        contract.get("negative_protection_checks") != expected_negative_checks,
        failures,
        "negative_protection_checks_match_current_sources",
        contract.get("negative_protection_checks"),
        expected_negative_checks,
    )

    allowed_unlocked_gates = {
        "training_import_eligible_rows": observed["training_import_eligible_rows"] > 0,
        "wetlab_authorized_rows": observed["wetlab_authorized_rows"] > 0,
        "wetlab_preflight_rows": observed["wetlab_preflight_rows"] > 0,
        "physics_ddg_ready": observed["physics_ddg_ready"] is True,
    }
    for gate_id, gate in hard_gate_by_id.items():
        expected_unlocked = allowed_unlocked_gates.get(gate_id, False)
        fail_if(gate.get("unlocked") is not expected_unlocked, failures, f"{gate_id}_unlock_state_matches_sources", gate.get("unlocked"), expected_unlocked)
        fail_if(gate.get("source_supported") is not True, failures, f"{gate_id}_source_supported", gate.get("source_supported"), True)

    fail_if(contract.get("success") is not True, failures, "contract_success_true", contract.get("success"), True)
    fail_if(contract.get("physics_ddg_ready") is not False, failures, "contract_physics_ddg_ready_false", contract.get("physics_ddg_ready"), False)
    fail_if(contract.get("benchmark_ready_for_model_claim") is not False, failures, "contract_benchmark_ready_for_model_claim_false", contract.get("benchmark_ready_for_model_claim"), False)
    fail_if(
        contract.get("feature_inputs_ready") < MINIMUM_BASE_FEATURE_INPUTS,
        failures,
        "contract_feature_inputs_ready_minimum",
        contract.get("feature_inputs_ready"),
        f">={MINIMUM_BASE_FEATURE_INPUTS}",
    )
    fail_if(
        contract.get("feature_inputs_minimum_required") != MINIMUM_BASE_FEATURE_INPUTS,
        failures,
        "contract_feature_inputs_minimum_required",
        contract.get("feature_inputs_minimum_required"),
        MINIMUM_BASE_FEATURE_INPUTS,
    )
    fail_if(contract.get("feature_inputs_input_only") is not True, failures, "contract_feature_inputs_input_only_true", contract.get("feature_inputs_input_only"), True)
    fail_if(contract.get("model_quality_ready") is not False, failures, "contract_model_quality_ready_false", contract.get("model_quality_ready"), False)
    fail_if(contract.get("safe_for_model_claim") is not False, failures, "contract_safe_for_model_claim_false", contract.get("safe_for_model_claim"), False)
    fail_if(contract.get("release_ready") is not False, failures, "contract_release_ready_false", contract.get("release_ready"), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "checked_report": rel(args.report),
        "checked_reports": {name: rel(path) for name, path in paths.items()},
        "report_matches_current_sources": contract == expected_full_report,
        "expected_current_state": expected,
        "observed_current_state": observed,
        "expected_source_state": expected_source_state,
        "checked_hard_gates": {
            gate_id: {
                "unlocked": gate.get("unlocked"),
                "source_supported": gate.get("source_supported"),
                "observed": gate.get("observed"),
                "expected": gate.get("expected"),
            }
            for gate_id, gate in sorted(hard_gate_by_id.items())
        },
        "negative_protection_checks": {
            "no_true_model_quality_or_release_flags": (
                contract.get("model_quality_ready") is False
                and contract.get("safe_for_model_claim") is False
                and contract.get("release_ready") is False
            ),
            "feature_inputs_are_model_input_only": contract.get("feature_inputs_input_only") is True,
            "wetlab_authorization_source_supported_but_import_stays_closed": (
                contract.get("wetlab_authorized_rows") == observed["wetlab_authorized_rows"]
                and contract.get("wetlab_preflight_rows") == observed["wetlab_preflight_rows"]
                and contract.get("wetlab_import_rows") == 0
            ),
            "physics_ddg_source_supported": contract.get("physics_ddg_ready") is False,
            "benchmark_claim_remains_false": contract.get("benchmark_ready_for_model_claim") is False,
        },
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": (
            "Fail-closed validation for the model-quality hard gate. "
            "Any true model_quality_ready, safe_for_model_claim, or release_ready flag fails validation; "
            "any hard gate marked unlocked without source support also fails validation."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "training_import_eligible_rows": observed["training_import_eligible_rows"],
        "wetlab_authorized_rows": observed["wetlab_authorized_rows"],
        "wetlab_preflight_rows": observed["wetlab_preflight_rows"],
        "wetlab_import_rows": observed["wetlab_import_rows"],
        "physics_ddg_ready": observed["physics_ddg_ready"],
        "benchmark_ready_for_model_claim": observed["benchmark_ready_for_model_claim"],
        "feature_inputs_ready": observed["feature_inputs_ready"],
        "feature_inputs_input_only": observed["feature_inputs_input_only"],
        "model_quality_ready": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
