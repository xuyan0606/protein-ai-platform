#!/usr/bin/env python3
"""Build a fail-closed board for the four parallel hard-gate workstreams."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "parallel_hard_gate_workstreams_board_report.json"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "parallel_hard_gate_workstreams_board.jsonl"


def load_json(rel: str) -> dict[str, Any]:
    path = AI_ROOT / rel
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def row(
    lane_id: str,
    title: str,
    status: str,
    source_reports: list[str],
    evidence: dict[str, Any],
    nonhuman_actions: list[str],
    human_or_external_blockers: list[str],
    acceptance_artifacts: list[str],
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "title": title,
        "status": status,
        "source_reports": source_reports,
        "evidence": evidence,
        "nonhuman_actions": nonhuman_actions,
        "human_or_external_blockers": human_or_external_blockers,
        "acceptance_artifacts": acceptance_artifacts,
        "started": True,
        "training_import_allowed": False,
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
    }


def main() -> int:
    benchmark = load_json("reports/benchmark_coverage_dashboard.json")
    benchmark_validation = load_json("reports/benchmark_coverage_dashboard_validation_report.json")
    ddg_probe = load_json("reports/ddg_executable_probe_report.json")
    ddg_readiness = load_json("reports/ddg_backend_readiness_report.json")
    ddg_receipts = load_json("reports/ddg_backend_runtime_receipt_validation_report.json")
    five_head = load_json("reports/five_head_training_execution_contract_report.json")
    training_contract = load_json("reports/training_label_import_contract_report.json")
    fireprot = load_json("reports/fireprot_reviewed_import_candidate_report.json")
    fireprot_validation = load_json("reports/fireprot_dedup_review_decision_validation_report.json")
    plate = load_json("reports/experiment_feedback_plate_intake_backlog_report.json")
    retention = load_json("reports/wet_lab_feedback_apply_duplicate_audit_report.json")

    rows = [
        row(
            "benchmark_readiness",
            "Benchmark readiness and score receipts",
            "started_blocked",
            [
                "reports/benchmark_coverage_dashboard.json",
                "reports/benchmark_coverage_dashboard_validation_report.json",
                "reports/benchmark_score_cache_validation_report.json",
            ],
            {
                "benchmark_rows": benchmark.get("benchmark_rows"),
                "valid_rows": benchmark.get("valid_rows"),
                "invalid_rows": benchmark.get("invalid_rows"),
                "ready_for_model_claim": benchmark.get("ready_for_model_claim"),
                "coverage_validation_success": benchmark_validation.get("success"),
            },
            [
                "reconcile benchmark case IDs with score-cache rows",
                "validate every score receipt source/version/checksum/metric direction",
                "rebuild five-head benchmark gap report without importing scores as labels",
            ],
            [
                "missing valid scorecards for current benchmark cases",
                "head-level score receipt and acceptance review remains open",
                "benchmark readiness cannot be inferred from acquisition plans",
            ],
            [
                "reports/benchmark_readiness_packet_report.json",
                "reports/benchmark_readiness_packet_validation_report.json",
                "datasets/governance/benchmark_readiness_packet.jsonl",
            ],
        ),
        row(
            "ddg_runtime_probe_receipt",
            "Rosetta/PyRosetta/FoldX runtime probe and receipt",
            "started_blocked",
            [
                "reports/ddg_executable_probe_report.json",
                "reports/ddg_backend_readiness_report.json",
                "reports/ddg_backend_runtime_receipt_validation_report.json",
            ],
            {
                "rosetta_executable_found": ddg_probe.get("rosetta_executable_found"),
                "foldx_executable_found": ddg_probe.get("foldx_executable_found"),
                "pyrosetta_module_available": ddg_probe.get("pyrosetta_module_available"),
                "executable_ddg_backend_ready": ddg_probe.get("executable_ddg_backend_ready"),
                "backend_readiness": ddg_readiness.get("executable_ddg_backend_ready"),
                "approved_runtime_rows": ddg_receipts.get("approved_runtime_rows"),
            },
            [
                "rerun local executable/module discovery",
                "validate runtime receipt schema, input hash, output artifact and smoke result",
                "keep ThermoMPNN proxy explicitly separate from physics ddG",
            ],
            [
                "Rosetta/FoldX installation and licensing or approved runtime path",
                "PyRosetta package/runtime availability",
                "runtime smoke receipt and manual acceptance are required before physics ddG",
            ],
            [
                "reports/ddg_physical_runtime_receipt_preflight_report.json",
                "reports/ddg_physical_runtime_receipt_preflight_validation_report.json",
                "datasets/governance/ddg_physical_runtime_receipt_preflight.jsonl",
            ],
        ),
        row(
            "five_head_minimum_samples",
            "Five-head minimum sample and replicate threshold",
            "started_blocked",
            [
                "reports/five_head_training_execution_contract_report.json",
                "reports/five_head_training_gap_plan_report.json",
                "reports/training_label_import_contract_report.json",
            ],
            {
                "ready_head_count": five_head.get("ready_head_count"),
                "total_head_training_rows": five_head.get("total_head_training_rows"),
                "training_import_eligible_rows": five_head.get("training_import_eligible_rows"),
                "training_execution_allowed": five_head.get("training_execution_allowed"),
                "contract_training_import_rows": (training_contract.get("contract_totals") or {}).get("training_import_eligible_rows"),
            },
            [
                "calculate per-head minimum rows, replicate, group and holdout requirements",
                "validate threshold report against current real label sources",
                "keep scaffold/interface regression available without starting training",
            ],
            [
                "reviewed labels and independent holdout data per head",
                "replicate/batch metadata for activity and stability",
                "benchmark acceptance before any model-quality claim",
            ],
            [
                "reports/five_head_training_threshold_report.json",
                "reports/five_head_training_threshold_validation_report.json",
            ],
        ),
        row(
            "human_preflight_packages",
            "FireProt, plate and retention human preflight packages",
            "started_blocked",
            [
                "reports/fireprot_reviewed_import_candidate_report.json",
                "reports/fireprot_dedup_review_decision_validation_report.json",
                "reports/experiment_feedback_plate_intake_backlog_report.json",
                "reports/wet_lab_feedback_apply_duplicate_audit_report.json",
            ],
            {
                "fireprot_decision_rows": fireprot.get("decision_rows"),
                "fireprot_approved_for_import_candidate_rows": fireprot.get("approved_for_import_candidate_rows"),
                "fireprot_decision_validation_success": fireprot_validation.get("success"),
                "plate_backlog_rows": plate.get("backlog_rows"),
                "retention_new_feedback_only_rows": retention.get("new_feedback_only_rows"),
                "retention_safe_to_append_rows": retention.get("safe_to_append_rows"),
            },
            [
                "refresh required-field and evidence completeness checks for all three packages",
                "keep decisions empty until human reviewer writes formal decision rows",
                "verify retention remains feedback-only and is not converted to dTm/ddG",
            ],
            [
                "FireProt dedup/license/numbering import decisions",
                "plate/well/raw signal/QC/operator review and authorization",
                "retention target semantics and explicit feedback append decision",
            ],
            [
                "reports/human_preflight_package_report.json",
                "reports/human_preflight_package_validation_report.json",
                "datasets/governance/human_preflight_package.jsonl",
            ],
        ),
    ]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "lane_count": len(rows),
        "started_lane_count": sum(1 for item in rows if item["started"]),
        "rows": rows,
        "training_import_allowed": False,
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Parallel hard-gate board only. It records real evidence and next actions; it never authorizes training import, model claims, release, production execution, or automatic human decisions.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    JSONL_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSONL_OUT.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in rows), encoding="utf-8")
    print(json.dumps({"lane_count": report["lane_count"], "started_lane_count": report["started_lane_count"], "release_ready": False, "output": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
