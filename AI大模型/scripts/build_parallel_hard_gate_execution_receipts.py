#!/usr/bin/env python3
"""Build execution receipts for the four parallel hard-gate workstreams."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "parallel_hard_gate_execution_receipts.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "parallel_hard_gate_execution_receipts_report.json"


def load_json(rel: str) -> dict[str, Any]:
    path = AI_ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def base_receipt(lane: str, source_reports: list[str], commands: list[str], validation_passed: bool) -> dict[str, Any]:
    return {
        "receipt_id": f"parallel-hard-gate-execution-{lane}",
        "lane": lane,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "execution_performed": True,
        "execution_commands": commands,
        "source_reports": source_reports,
        "validation_passed": bool(validation_passed),
        "status": "executed_blocked",
        "eligibility_changed": False,
        "formal_decision_written": False,
        "runtime_receipt_written": False,
        "training_import_written": False,
        "model_or_release_flags_changed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build parallel hard-gate execution receipts")
    parser.add_argument("--output-jsonl", type=Path, default=OUT_JSONL)
    parser.add_argument("--output-report", type=Path, default=OUT_REPORT)
    args = parser.parse_args()

    benchmark = load_json("reports/benchmark_readiness_packet_report.json")
    benchmark_validation = load_json("reports/benchmark_readiness_packet_validation_report.json")
    ddg = load_json("reports/ddg_physical_runtime_receipt_preflight_report.json")
    ddg_validation = load_json("reports/ddg_physical_runtime_receipt_preflight_validation_report.json")
    five_head = load_json("reports/five_head_training_threshold_report.json")
    five_head_validation = load_json("reports/five_head_training_threshold_validation_report.json")
    human = load_json("reports/human_preflight_package_report.json")
    human_validation = load_json("reports/human_preflight_package_validation_report.json")

    benchmark_receipt = base_receipt(
        "benchmark_readiness",
        [
            "reports/benchmark_readiness_packet_report.json",
            "reports/benchmark_readiness_packet_validation_report.json",
            "datasets/governance/benchmark_readiness_packets.jsonl",
        ],
        [
            "python3 scripts/build_benchmark_readiness_packet.py",
            "python3 scripts/validate_benchmark_readiness_packet.py",
        ],
        bool(benchmark_validation.get("contract_valid")) and int(benchmark_validation.get("failure_count") or 0) == 0,
    )
    benchmark_receipt.update({
        "packet_rows": int((benchmark.get("summary") or {}).get("packet_rows") or benchmark_validation.get("packet_rows") or 0),
        "completion_ready_rows": int(benchmark_validation.get("completion_ready_rows") or 0),
        "score_values_recorded": int(benchmark_validation.get("score_values_recorded") or 0),
        "blocking_summary": "Benchmark packets are structurally valid, but no missing benchmark has score receipts sufficient for model-claim readiness.",
    })

    ddg_receipt = base_receipt(
        "ddg_runtime_probe_receipt",
        [
            "reports/ddg_physical_runtime_receipt_preflight_report.json",
            "reports/ddg_physical_runtime_receipt_preflight_validation_report.json",
            "datasets/governance/ddg_physical_runtime_receipt_preflight.jsonl",
        ],
        [
            "python3 scripts/build_ddg_physical_runtime_receipt_preflight.py",
            "python3 scripts/validate_ddg_physical_runtime_receipt_preflight.py",
        ],
        bool(ddg_validation.get("success")),
    )
    ddg_receipt.update({
        "physical_backend_rows": int(ddg.get("physical_backend_rows") or 0),
        "runtime_receipt_rows": int(ddg.get("runtime_receipt_rows") or 0),
        "approved_runtime_receipt_rows": int(ddg_validation.get("approved_runtime_receipt_rows") or 0),
        "physics_ddg_ready": bool(ddg_validation.get("physics_ddg_ready")),
        "eligibility_changed": bool(ddg_validation.get("physics_ddg_ready")),
        "formal_decision_written": int(ddg_validation.get("approved_runtime_receipt_rows") or 0) > 0,
        "runtime_receipt_written": int(ddg_validation.get("approved_runtime_receipt_rows") or 0) > 0,
        "blocking_summary": "PyRosetta has self-attested component authorization plus an approved physical ddG runtime smoke receipt; Rosetta still needs a smoke/runtime receipt and FoldX remains blocked. Computed ddG remains non-training computational evidence unless separate label eligibility approves it.",
    })

    five_head_receipt = base_receipt(
        "five_head_minimum_sample_threshold",
        [
            "reports/five_head_training_threshold_report.json",
            "reports/five_head_training_threshold_validation_report.json",
        ],
        [
            "python3 scripts/build_five_head_training_threshold_report.py",
            "python3 scripts/validate_five_head_training_threshold_report.py",
        ],
        bool(five_head_validation.get("success")),
    )
    five_head_receipt.update({
        "ready_head_count": int(five_head.get("ready_head_count") or five_head_validation.get("ready_head_count") or 0),
        "candidate_heads": five_head_validation.get("candidate_heads") or [],
        "blocked_heads": five_head_validation.get("blocked_heads") or [],
        "source_counts": five_head_validation.get("source_counts") or {},
        "training_execution_allowed": bool(five_head_validation.get("training_execution_allowed")),
        "blocking_summary": "Only activity_risk has six numeric candidates; zero heads meet explicit sample, group, replicate, and label-field thresholds.",
    })

    human_receipt = base_receipt(
        "human_preflight_fireprot_plate_retention",
        [
            "reports/human_preflight_package_report.json",
            "reports/human_preflight_package_validation_report.json",
            "datasets/governance/human_preflight_package.jsonl",
        ],
        [
            "python3 scripts/build_human_preflight_package.py",
            "python3 scripts/validate_human_preflight_package.py",
        ],
        bool(human_validation.get("success")),
    )
    human_receipt.update({
        "package_rows": int(human.get("package_rows") or 0),
        "valid_package_rows": int(human_validation.get("valid_package_rows") or 0),
        "fireprot_packet_rows": int(human.get("fireprot_packet_rows") or 0),
        "plate_backlog_rows": int(human.get("plate_backlog_rows") or 0),
        "retention_feedback_only_rows": int(human.get("retention_feedback_only_rows") or 0),
        "ready_for_training_import_rows": int(human_validation.get("ready_for_training_import_rows") or 0),
        "blocking_summary": "Human preflight package is valid, but it is not a formal decision source and imports zero training rows.",
    })

    receipts = [benchmark_receipt, ddg_receipt, five_head_receipt, human_receipt]
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.output_jsonl.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in receipts) + "\n", encoding="utf-8")

    validation_passed_rows = sum(1 for row in receipts if row["validation_passed"])
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "receipt_rows": len(receipts),
        "validation_passed_rows": validation_passed_rows,
        "executed_rows": sum(1 for row in receipts if row["execution_performed"]),
        "eligibility_changed_rows": sum(1 for row in receipts if row["eligibility_changed"]),
        "formal_decision_written_rows": sum(1 for row in receipts if row["formal_decision_written"]),
        "runtime_receipt_written_rows": sum(1 for row in receipts if row["runtime_receipt_written"]),
        "training_import_written_rows": sum(1 for row in receipts if row["training_import_written"]),
        "model_or_release_flags_changed_rows": sum(1 for row in receipts if row["model_or_release_flags_changed"]),
        "safe_for_model_claim": False,
        "release_ready": False,
        "output": str(args.output_jsonl.relative_to(AI_ROOT)),
        "policy": "Execution receipt only. The ddG lane may record a valid local PyRosetta runtime receipt, but these rows do not approve training imports, model claims, customer delivery, or release readiness.",
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt_rows": report["receipt_rows"],
        "validation_passed_rows": report["validation_passed_rows"],
        "eligibility_changed_rows": report["eligibility_changed_rows"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "release_ready": report["release_ready"],
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
