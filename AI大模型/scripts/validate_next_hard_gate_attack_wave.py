#!/usr/bin/env python3
"""Validate the next hard-gate attack wave remains source-bound and fail-closed."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "governance" / "next_hard_gate_attack_wave.jsonl"
REPORT = AI_ROOT / "reports" / "next_hard_gate_attack_wave_report.json"
OUT = AI_ROOT / "reports" / "next_hard_gate_attack_wave_validation_report.json"
POLICY = (
    "Next hard-gate attack wave records real local probes and reviewed receipts only. "
    "PyRosetta runtime can be marked as a local computational ddG breakthrough, but "
    "benchmark scores, head labels, training imports, model claims, and release readiness "
    "remain separately gated."
)

EXPECTED_LANES = {
    "benchmark_real_score_cache",
    "physical_ddg_runtime_probe",
    "five_head_label_threshold",
    "human_formal_decision_preflight",
}
EXPECTED_BENCHMARK_HEAD_COUNT = 5
FORBIDDEN_TRUE_FIELDS = {
    "claimed_breakthrough",
    "eligibility_changed",
    "formal_decision_written",
    "formal_decisions_written",
    "runtime_receipt_written",
    "training_import_written",
    "model_or_release_flags_changed",
    "safe_for_model_claim",
    "release_ready",
    "physics_ddg_ready",
    "training_execution_allowed",
}
PHYSICAL_DDG_ALLOWED_TRUE_FIELDS = {
    "claimed_breakthrough",
    "eligibility_changed",
    "formal_decision_written",
    "runtime_receipt_written",
}


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path, failures: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append({"check": f"{label}_valid_json", "observed": str(exc), "expected": "JSON object"})
        return {}
    if not isinstance(value, dict):
        failures.append({"check": f"{label}_json_object", "observed": type(value).__name__, "expected": "object"})
        return {}
    return value


def load_source_json(rel: str, failures: list[dict[str, Any]]) -> dict[str, Any]:
    return load_json(AI_ROOT / rel, failures, rel.replace("/", "_").replace(".", "_"))


def load_jsonl(path: Path, failures: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append({"check": f"{label}_valid_jsonl", "line": line_number, "observed": str(exc), "expected": "JSON object"})
            continue
        if not isinstance(value, dict):
            failures.append({"check": f"{label}_jsonl_object", "line": line_number, "observed": type(value).__name__, "expected": "object"})
            continue
        rows.append(value)
    return rows


def base_row(lane_id: str, title: str, created_at: str, executed_commands: list[str], source_reports: list[str]) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "title": title,
        "created_at": created_at,
        "local_only": True,
        "status": "executed_blocked",
        "executed_commands": executed_commands,
        "source_reports": source_reports,
        "claimed_breakthrough": False,
        "eligibility_changed": False,
        "formal_decision_written": False,
        "runtime_receipt_written": False,
        "training_import_written": False,
        "model_or_release_flags_changed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def created_at_by_lane(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(row.get("lane_id")): str(row.get("created_at") or "")
        for row in rows
        if isinstance(row.get("lane_id"), str)
    }


def expected_rows(rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    created = created_at_by_lane(rows)
    benchmark_intake = load_source_json("reports/benchmark_score_cache_intake_report.json", failures)
    benchmark_validation = load_source_json("reports/benchmark_score_cache_validation_report.json", failures)
    benchmark_coverage = load_source_json("reports/benchmark_coverage_dashboard.json", failures)
    smoke_benchmark = load_source_json("reports/kwb_activity_risk_smoke_benchmark_report.json", failures)
    smoke_benchmark_validation = load_source_json("reports/kwb_activity_risk_smoke_benchmark_validation_report.json", failures)
    strict_benchmark = load_source_json("reports/kwb_strict_mutation_holdout_benchmark_report.json", failures)
    metric_report = load_source_json("cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/metric_report.json", failures)
    ddg_probe = load_source_json("reports/ddg_executable_probe_report.json", failures)
    pyrosetta_install = load_source_json("reports/pyrosetta_local_install_probe_report.json", failures)
    ddg_discovery = load_source_json("reports/ddg_local_runtime_discovery_report.json", failures)
    ddg_runtime = load_source_json("reports/ddg_backend_runtime_receipt_validation_report.json", failures)
    ddg_preflight = load_source_json("reports/ddg_physical_runtime_receipt_preflight_validation_report.json", failures)
    pyrosetta_smoke = load_source_json("reports/pyrosetta_physical_smoke_bootstrap_report.json", failures)
    five_head = load_source_json("reports/five_head_training_threshold_report.json", failures)
    five_head_validation = load_source_json("reports/five_head_training_threshold_validation_report.json", failures)
    human = load_source_json("reports/human_preflight_package_report.json", failures)
    human_validation = load_source_json("reports/human_preflight_package_validation_report.json", failures)

    primary_metrics = metric_report.get("primary_metrics") if isinstance(metric_report.get("primary_metrics"), dict) else {}
    usable_score_values = 0
    if primary_metrics.get("rows") and primary_metrics.get("accuracy") is not None:
        usable_score_values += 1
    if primary_metrics.get("rows") and primary_metrics.get("macro_f1") is not None:
        usable_score_values += 1

    coverage_heads = benchmark_coverage.get("heads") if isinstance(benchmark_coverage.get("heads"), list) else []
    ready_heads = [
        str(row.get("head"))
        for row in coverage_heads
        if isinstance(row, dict) and row.get("ready") is True and isinstance(row.get("head"), str)
    ]
    missing_heads = [
        str(row.get("head"))
        for row in coverage_heads
        if isinstance(row, dict) and int(row.get("missing") or 0) > 0 and isinstance(row.get("head"), str)
    ]
    valid_benchmark_rows = int(benchmark_validation.get("valid_rows") or 0)
    invalid_benchmark_rows = int(benchmark_validation.get("invalid_rows") or 0)

    benchmark_row = base_row(
        "benchmark_real_score_cache",
        "Benchmark real score cache probe",
        created.get("benchmark_real_score_cache", ""),
        [
            "python3 scripts/build_kwb_strict_mutation_holdout_benchmark.py",
            "python3 scripts/apply_benchmark_score_cache_intake.py",
            "python3 scripts/validate_benchmark_score_cache.py",
            "python3 scripts/build_benchmark_coverage_dashboard.py",
            "python3 scripts/build_kwb_activity_risk_smoke_benchmark.py",
            "python3 scripts/validate_kwb_activity_risk_smoke_benchmark.py",
        ],
        [
            "reports/kwb_strict_mutation_holdout_benchmark_report.json",
            "reports/kwb_activity_risk_smoke_benchmark_report.json",
            "reports/kwb_activity_risk_smoke_benchmark_validation_report.json",
            "reports/benchmark_score_cache_intake_report.json",
            "reports/benchmark_score_cache_validation_report.json",
            "reports/benchmark_coverage_dashboard.json",
        ],
    )
    benchmark_row.update({
        "candidate_scorecard_rows": 1 if strict_benchmark else 0,
        "candidate_dataset_rows": int(strict_benchmark.get("dataset_rows") or 0),
        "candidate_primary_holdout_rows": int(strict_benchmark.get("primary_holdout_rows") or 0),
        "candidate_leakage_check_status": strict_benchmark.get("leakage_check_status"),
        "intake_rows": int(benchmark_intake.get("intake_rows") or 0),
        "accepted_score_cache_rows": int(benchmark_intake.get("accepted_rows") or 0),
        "rejected_score_cache_rows": int(benchmark_intake.get("rejected_rows") or 0),
        "valid_benchmark_rows": valid_benchmark_rows,
        "invalid_benchmark_rows": invalid_benchmark_rows,
        "heads_ready": int(benchmark_validation.get("heads_ready") or 0),
        "ready_benchmark_heads": ready_heads,
        "missing_benchmark_heads": missing_heads,
        "benchmark_ready_for_model_claim": bool(benchmark_validation.get("ready_for_model_claim")),
        "sample_limited_smoke_benchmark_rows": int(smoke_benchmark.get("dataset_rows") or 0),
        "sample_limited_smoke_benchmark_valid": bool(smoke_benchmark_validation.get("success")),
        "sample_limited_smoke_quality_status": smoke_benchmark.get("quality_status"),
        "usable_score_values": usable_score_values,
        "blockers": [
            "strict supervised source currently yields zero benchmark rows after provenance gates",
            "local KWB strict holdout intake is rejected because leakage_check_status is not passed",
            f"benchmark cache is {valid_benchmark_rows}/15 valid with {invalid_benchmark_rows} invalid or missing rows",
            f"missing benchmark heads: {', '.join(missing_heads) if missing_heads else 'none'}",
        ],
        "next_required_artifacts": [
            "non-empty benchmark dataset artifact",
            "passed leakage check",
            "scorecard and metric report with non-null primary metrics",
            "approved benchmark score cache intake row",
        ],
    })

    ddg_row = base_row(
        "physical_ddg_runtime_probe",
        "Rosetta/PyRosetta/FoldX physical ddG runtime probe",
        created.get("physical_ddg_runtime_probe", ""),
        [
            "python3 scripts/build_ddg_executable_probe.py",
            "python3 scripts/build_pyrosetta_local_install_probe.py",
            "python3 scripts/build_ddg_local_runtime_discovery.py",
            "python3 scripts/build_pyrosetta_physical_smoke_bootstrap.py",
            "python3 scripts/validate_ddg_backend_runtime_receipts.py",
            "python3 scripts/build_ddg_physical_runtime_receipt_preflight.py",
            "python3 scripts/validate_ddg_physical_runtime_receipt_preflight.py",
        ],
        [
            "reports/ddg_executable_probe_report.json",
            "reports/pyrosetta_local_install_probe_report.json",
            "reports/pyrosetta_physical_smoke_bootstrap_report.json",
            "reports/ddg_local_runtime_discovery_report.json",
            "reports/ddg_backend_runtime_receipt_validation_report.json",
            "reports/ddg_physical_runtime_receipt_preflight_report.json",
            "reports/ddg_physical_runtime_receipt_preflight_validation_report.json",
        ],
    )
    ddg_row.update({
        "rosetta_executable_found": bool(ddg_probe.get("rosetta_executable_found")),
        "foldx_executable_found": bool(ddg_probe.get("foldx_executable_found")),
        "pyrosetta_module_available": bool(ddg_probe.get("pyrosetta_module_available")),
        "pyrosetta_install_import_succeeded": bool((pyrosetta_install.get("import_probe") or {}).get("succeeded")),
        "pyrosetta_install_approved_for_physical_ddg_runtime": bool(ddg_runtime.get("physics_ddg_ready")),
        "pyrosetta_physical_smoke_passed": bool(pyrosetta_smoke.get("physical_smoke_passed")),
        "pyrosetta_physical_smoke_artifact_count": len(pyrosetta_smoke.get("smoke_artifact_sha256") or {}),
        "version_probe_succeeded_rows": int(ddg_probe.get("version_probe_succeeded_rows") or 0),
        "runtime_discovery_candidate_rows": int(ddg_discovery.get("candidate_rows") or 0),
        "ready_for_ddg_execution_rows": int(ddg_discovery.get("ready_for_ddg_execution_rows") or 0),
        "runtime_receipt_rows": int(ddg_runtime.get("receipt_rows") or 0),
        "approved_runtime_rows": int(ddg_runtime.get("approved_runtime_rows") or 0),
        "physics_ddg_ready": bool(ddg_preflight.get("physics_ddg_ready")),
        "claimed_breakthrough": bool(ddg_preflight.get("physics_ddg_ready")),
        "eligibility_changed": bool(ddg_preflight.get("physics_ddg_ready")),
        "formal_decision_written": bool(ddg_runtime.get("approved_runtime_rows")),
        "runtime_receipt_written": bool(ddg_runtime.get("approved_runtime_rows")),
        "blockers": [
            *([] if bool(ddg_probe.get("rosetta_executable_found")) else ["Rosetta executable not found"]),
            *([] if bool(ddg_probe.get("foldx_executable_found")) else ["FoldX executable not found"]),
            *([] if bool(ddg_probe.get("pyrosetta_module_available")) else ["PyRosetta module not available"]),
            *([] if int(ddg_runtime.get("approved_runtime_rows") or 0) else ["no approved runtime receipt"]),
            *([] if bool(pyrosetta_smoke.get("physical_smoke_passed")) else ["no physical ddG smoke artifact"]),
            *([] if bool(ddg_preflight.get("physics_ddg_ready")) else ["physics ddG preflight not ready"]),
        ],
        "next_required_artifacts": [
            "Rosetta executable and receipt if Rosetta is required",
            "FoldX executable and receipt if FoldX is required",
            "production/customer legal review before any delivery use",
        ],
    })

    five_row = base_row(
        "five_head_label_threshold",
        "Five-head minimum label threshold probe",
        created.get("five_head_label_threshold", ""),
        [
            "python3 scripts/build_five_head_training_threshold_report.py",
            "python3 scripts/validate_five_head_training_threshold_report.py",
        ],
        [
            "reports/five_head_training_threshold_report.json",
            "reports/five_head_training_threshold_validation_report.json",
        ],
    )
    five_row.update({
        "ready_head_count": int(five_head.get("ready_head_count") or five_head_validation.get("ready_head_count") or 0),
        "candidate_heads": five_head_validation.get("candidate_heads") or [],
        "blocked_heads": five_head_validation.get("blocked_heads") or [],
        "source_counts": five_head_validation.get("source_counts") or {},
        "training_execution_allowed": bool(five_head_validation.get("training_execution_allowed")),
        "blockers": [
            "activity_risk has six formal labels but remains below the 100-sample, 10-group, 3-explicit-replicate thresholds",
            "mutation_rank, stability, substrate_fit, and assay_success have zero eligible label rows",
        ],
        "next_required_artifacts": [
            "additional authorized activity_risk formal labels with explicit replicate decisions",
            "replicate metadata or explicit no-replicate rejection",
            "additional reviewed label rows per head",
            "head-specific validator receipts before training",
        ],
    })

    human_row = base_row(
        "human_formal_decision_preflight",
        "Human formal decision preflight",
        created.get("human_formal_decision_preflight", ""),
        [
            "python3 scripts/build_human_preflight_package.py",
            "python3 scripts/validate_human_preflight_package.py",
        ],
        [
            "reports/human_preflight_package_report.json",
            "reports/human_preflight_package_validation_report.json",
            "datasets/governance/human_preflight_package.jsonl",
        ],
    )
    human_row.update({
        "package_rows": int(human.get("package_rows") or 0),
        "valid_package_rows": int(human_validation.get("valid_package_rows") or 0),
        "fireprot_packet_rows": int(human.get("fireprot_packet_rows") or 0),
        "plate_backlog_rows": int(human.get("plate_backlog_rows") or 0),
        "retention_feedback_only_rows": int(human.get("retention_feedback_only_rows") or 0),
        "ready_for_training_import_rows": int(human_validation.get("ready_for_training_import_rows") or 0),
        "formal_decisions_written": bool(human_validation.get("formal_decisions_written")),
        "blockers": [
            "FireProt dedup decisions still require human review",
            "plate backlog rows still lack required schema fields and approval",
            "85C/3min retention rows remain feedback-only and not stability labels",
        ],
        "next_required_artifacts": [
            "reviewed FireProt dedup decision rows",
            "schema-complete plate/well rows with QC and approval",
            "retention feedback-only acknowledgement or exclusion decision",
            "validator receipts before any formal application",
        ],
    })
    return [benchmark_row, ddg_row, five_row, human_row]


def expected_report(created_at: str, rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    return {
        "created_at": created_at,
        "local_only": True,
        "lane_rows": len(rows),
        "executed_blocked_rows": sum(1 for row in rows if row.get("status") == "executed_blocked"),
        "claimed_breakthrough_rows": sum(1 for row in rows if row.get("claimed_breakthrough") is True),
        "eligibility_changed_rows": sum(1 for row in rows if row.get("eligibility_changed") is True),
        "formal_decision_written_rows": sum(1 for row in rows if row.get("formal_decision_written") is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row.get("runtime_receipt_written") is True),
        "training_import_written_rows": sum(1 for row in rows if row.get("training_import_written") is True),
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": relative(output),
        "policy": POLICY,
    }


def add_mismatch(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate next hard-gate attack wave")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    rows = load_jsonl(args.input, failures, "attack_wave_jsonl")
    report_input = load_json(args.report, failures, "attack_wave_report")
    source_failures: list[dict[str, Any]] = []
    source_expected_rows = expected_rows(rows, source_failures)
    failures.extend(source_failures)

    if rows != source_expected_rows:
        add_mismatch(failures, "attack_wave_jsonl_matches_current_sources", rows, source_expected_rows)
    report_created_at = str(report_input.get("created_at") or "")
    source_expected_report = expected_report(report_created_at, source_expected_rows, args.input)
    if report_input != source_expected_report:
        add_mismatch(failures, "attack_wave_report_matches_current_rows", report_input, source_expected_report)

    lanes = [str(row.get("lane_id") or "") for row in rows]
    counts = Counter(lanes)

    if set(lanes) != EXPECTED_LANES:
        failures.append({"check": "expected_lanes", "observed": sorted(set(lanes)), "expected": sorted(EXPECTED_LANES)})
    for lane, count in counts.items():
        if count != 1:
            failures.append({"check": "duplicate_lane", "lane": lane, "count": count})

    for idx, row in enumerate(rows, start=1):
        lane = str(row.get("lane_id") or "")
        row_failures: list[str] = []
        if row.get("status") != "executed_blocked":
            row_failures.append("status_not_executed_blocked")
        if not row.get("executed_commands"):
            row_failures.append("missing_executed_commands")
        if not row.get("source_reports"):
            row_failures.append("missing_source_reports")
        if not row.get("blockers"):
            row_failures.append("missing_blockers")
        if not row.get("next_required_artifacts"):
            row_failures.append("missing_next_required_artifacts")
        allowed_true_fields = PHYSICAL_DDG_ALLOWED_TRUE_FIELDS if lane == "physical_ddg_runtime_probe" else set()
        for field in FORBIDDEN_TRUE_FIELDS:
            if field in allowed_true_fields:
                continue
            if row.get(field) is True:
                row_failures.append(f"forbidden_true_{field}")

        if lane == "benchmark_real_score_cache":
            if int(row.get("accepted_score_cache_rows") or 0) < 0:
                row_failures.append("benchmark_accepted_rows_negative")
            if int(row.get("valid_benchmark_rows") or 0) < 0:
                row_failures.append("benchmark_valid_rows_negative")
            heads_ready = int(row.get("heads_ready") or 0)
            invalid_benchmark_rows = int(row.get("invalid_benchmark_rows") or 0)
            if heads_ready < 0 or heads_ready > EXPECTED_BENCHMARK_HEAD_COUNT:
                row_failures.append("benchmark_heads_ready_out_of_range")
            if invalid_benchmark_rows > 0 and heads_ready == EXPECTED_BENCHMARK_HEAD_COUNT:
                row_failures.append("benchmark_heads_ready_inconsistent_with_invalid_rows")
            if row.get("benchmark_ready_for_model_claim") is True:
                row_failures.append("benchmark_ready_for_model_claim_unexpected")
            if int(row.get("valid_benchmark_rows") or 0) > 0:
                if int(row.get("sample_limited_smoke_benchmark_rows") or 0) <= 0:
                    row_failures.append("benchmark_valid_rows_without_sample_limited_smoke_context")
                if row.get("sample_limited_smoke_quality_status") != "sample_limited_internal_smoke_only":
                    row_failures.append("benchmark_smoke_quality_status_unexpected")
            if int(row.get("usable_score_values") or 0) != 0:
                row_failures.append("benchmark_usable_score_values_unexpected")
            if row.get("candidate_leakage_check_status") == "passed":
                row_failures.append("benchmark_candidate_leakage_unexpectedly_passed")
        if lane == "physical_ddg_runtime_probe":
            if int(row.get("ready_for_ddg_execution_rows") or 0) < 1:
                row_failures.append("ddg_ready_execution_missing_after_pyrosetta_import")
            if int(row.get("approved_runtime_rows") or 0) < 1:
                row_failures.append("ddg_approved_runtime_missing_after_formal_receipt")
            if row.get("rosetta_executable_found") is not True:
                row_failures.append("rosetta_executable_missing_after_conda_install")
            if row.get("foldx_executable_found") is not True:
                row_failures.append("foldx_executable_missing_after_local_probe")
            if row.get("pyrosetta_module_available") is not True:
                row_failures.append("pyrosetta_module_missing")
            if row.get("pyrosetta_install_import_succeeded") is not True:
                row_failures.append("pyrosetta_module_available_without_import_probe")
            if int(row.get("approved_runtime_rows") or 0) < 1:
                row_failures.append("ddg_runtime_receipt_not_approved")
            if row.get("pyrosetta_physical_smoke_passed") is not True:
                row_failures.append("pyrosetta_physical_smoke_not_passed")
            if int(row.get("pyrosetta_physical_smoke_artifact_count") or 0) < 5:
                row_failures.append("pyrosetta_physical_smoke_artifacts_incomplete")
            if row.get("physics_ddg_ready") is not False:
                row_failures.append("physics_ddg_ready_not_fail_closed_for_full_lane")
            if row.get("safe_for_model_claim") is not False or row.get("release_ready") is not False:
                row_failures.append("ddg_breakthrough_changed_model_or_release_flags")
        if lane == "five_head_label_threshold":
            if int(row.get("ready_head_count") or 0) != 0:
                row_failures.append("five_head_ready_count_unexpected")
            if set(row.get("candidate_heads") or []) != set():
                row_failures.append("five_head_candidate_heads_unexpected")
        if lane == "human_formal_decision_preflight":
            if int(row.get("package_rows") or 0) != 3:
                row_failures.append("human_package_rows_not_3")
            if int(row.get("ready_for_training_import_rows") or 0) != 0:
                row_failures.append("human_ready_training_rows_unexpected")
        if row_failures:
            failures.append({"check": "row_policy", "row": idx, "lane": lane, "failures": row_failures})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "source_bound": not source_failures and rows == source_expected_rows and report_input == source_expected_report,
        "lane_rows": len(rows),
        "expected_lane_count": len(EXPECTED_LANES),
        "executed_blocked_rows": sum(1 for row in rows if row.get("status") == "executed_blocked"),
        "claimed_breakthrough_rows": sum(1 for row in rows if row.get("claimed_breakthrough") is True),
        "eligibility_changed_rows": sum(1 for row in rows if row.get("eligibility_changed") is True),
        "formal_decision_written_rows": sum(1 for row in rows if row.get("formal_decision_written") is True or row.get("formal_decisions_written") is True),
        "runtime_receipt_written_rows": sum(1 for row in rows if row.get("runtime_receipt_written") is True),
        "training_import_written_rows": sum(1 for row in rows if row.get("training_import_written") is True),
        "report_lane_rows": report_input.get("lane_rows"),
        "report_matches_current_sources": report_input == source_expected_report,
        "jsonl_matches_current_sources": rows == source_expected_rows,
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "The attack wave is a verified execution-and-blocker snapshot only. It cannot unlock claims unless upstream formal artifacts are valid.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "lane_rows": report["lane_rows"],
        "executed_blocked_rows": report["executed_blocked_rows"],
        "failures": len(failures),
        "safe_for_model_claim": report["safe_for_model_claim"],
        "release_ready": report["release_ready"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
