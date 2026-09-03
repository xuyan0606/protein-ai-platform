#!/usr/bin/env python3
"""Build the next hard-gate attack wave from real local probe results."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "next_hard_gate_attack_wave.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "next_hard_gate_attack_wave_report.json"


def load_json(rel: str) -> dict[str, Any]:
    path = AI_ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def base_row(lane_id: str, title: str, executed_commands: list[str], source_reports: list[str]) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build next hard-gate attack wave")
    parser.add_argument("--output-jsonl", type=Path, default=OUT_JSONL)
    parser.add_argument("--output-report", type=Path, default=OUT_REPORT)
    args = parser.parse_args()

    benchmark_intake = load_json("reports/benchmark_score_cache_intake_report.json")
    benchmark_validation = load_json("reports/benchmark_score_cache_validation_report.json")
    benchmark_coverage = load_json("reports/benchmark_coverage_dashboard.json")
    smoke_benchmark = load_json("reports/kwb_activity_risk_smoke_benchmark_report.json")
    smoke_benchmark_validation = load_json("reports/kwb_activity_risk_smoke_benchmark_validation_report.json")
    strict_benchmark = load_json("reports/kwb_strict_mutation_holdout_benchmark_report.json")
    metric_report = load_json("cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/metric_report.json")
    ddg_probe = load_json("reports/ddg_executable_probe_report.json")
    pyrosetta_install = load_json("reports/pyrosetta_local_install_probe_report.json")
    ddg_discovery = load_json("reports/ddg_local_runtime_discovery_report.json")
    ddg_runtime = load_json("reports/ddg_backend_runtime_receipt_validation_report.json")
    ddg_preflight = load_json("reports/ddg_physical_runtime_receipt_preflight_validation_report.json")
    pyrosetta_smoke = load_json("reports/pyrosetta_physical_smoke_bootstrap_report.json")
    five_head = load_json("reports/five_head_training_threshold_report.json")
    five_head_validation = load_json("reports/five_head_training_threshold_validation_report.json")
    human = load_json("reports/human_preflight_package_report.json")
    human_validation = load_json("reports/human_preflight_package_validation_report.json")

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

    rows = [benchmark_row, ddg_row, five_row, human_row]
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.output_jsonl.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
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
        "output": str(args.output_jsonl.relative_to(AI_ROOT)),
        "policy": "Next hard-gate attack wave records real local probes and reviewed receipts only. PyRosetta runtime can be marked as a local computational ddG breakthrough, but benchmark scores, head labels, training imports, model claims, and release readiness remain separately gated.",
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "lane_rows": report["lane_rows"],
        "executed_blocked_rows": report["executed_blocked_rows"],
        "claimed_breakthrough_rows": report["claimed_breakthrough_rows"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "release_ready": report["release_ready"],
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
