#!/usr/bin/env python3
"""Validate Stage 25 claim/release consistency after local scaffolding advances."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OVERALL = AI_ROOT / "reports" / "stage25_overall_fail_closed_index_20260806.json"
RELEASE_SUMMARY = AI_ROOT / "reports" / "release_benchmark_stage25_fail_closed_summary_20260806.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
OUTPUT = AI_ROOT / "reports" / "stage25_claim_release_consistency_validation_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    for path, name in ((OVERALL, "overall"), (RELEASE_SUMMARY, "release_summary"), (LOCAL_RELEASE, "local_release")):
        fail_if(not path.exists(), failures, f"{name}_exists", "missing", str(path))

    overall = load_json(OVERALL) if OVERALL.exists() else {}
    release_summary = load_json(RELEASE_SUMMARY) if RELEASE_SUMMARY.exists() else {}
    local_release = load_json(LOCAL_RELEASE) if LOCAL_RELEASE.exists() else {}
    readiness = local_release.get("readiness_summary") or {}

    for flag in (
        "external_sqlite_mutated",
        "allow_apply",
        "export_safe_released",
        "release_ready",
        "safe_for_model_claim",
        "benchmark_ready_for_model_claim",
    ):
        fail_if(overall.get(flag) is not False, failures, f"overall.{flag}_false", overall.get(flag), False)
    fail_if(overall.get("formal_decision_rows_written") != 0, failures, "overall.formal_decision_rows_written_zero", overall.get("formal_decision_rows_written"), 0)
    fail_if(overall.get("release_status") != "not_released", failures, "overall.release_status", overall.get("release_status"), "not_released")

    fail_if(release_summary.get("summary_valid") is not True, failures, "release_summary_valid", release_summary.get("summary_valid"), True)
    for flag in ("release_ready", "safe_for_model_claim", "benchmark_ready_for_model_claim"):
        fail_if(release_summary.get(flag) is not False, failures, f"release_summary.{flag}_false", release_summary.get(flag), False)
    fail_if(release_summary.get("benchmark_completion_ready_rows") != 0, failures, "release_summary.benchmark_completion_ready_rows_zero", release_summary.get("benchmark_completion_ready_rows"), 0)
    fail_if(release_summary.get("formal_decision_rows_written") != 0, failures, "release_summary.formal_decision_rows_written_zero", release_summary.get("formal_decision_rows_written"), 0)

    fail_if(readiness.get("master_overall_status") != "blocked_for_model_claim", failures, "local_release.master_overall_status", readiness.get("master_overall_status"), "blocked_for_model_claim")
    for flag in (
        "governance_ready",
        "biosecurity_ready_for_ordering",
        "customer_delivery_ready",
        "benchmark_ready_for_model_claim",
        "operator_review_status_ready",
        "workstream_all_human_accepted",
        "license_ready_for_customer_delivery",
        "biosecurity_decision_ready_for_ordering",
        "sequence_ip_fto_ready_for_delivery",
    ):
        fail_if(readiness.get(flag) is not False, failures, f"local_release.{flag}_false", readiness.get(flag), False)
    fail_if(readiness.get("human_decision_backlog_missing_rows", 0) <= 0, failures, "local_release.human_decision_backlog_missing_rows_positive", readiness.get("human_decision_backlog_missing_rows"), ">0")
    allowed_claims = readiness.get("claim_matrix_fail_closed_policy_allowed_claim_ids")
    fail_if(allowed_claims != ["internal_design_review_artifacts"], failures, "local_release.only_internal_design_review_claim_allowed", allowed_claims, ["internal_design_review_artifacts"])
    blocked_claims = set(readiness.get("claim_matrix_fail_closed_policy_blocked_claim_ids") or [])
    for claim in ("model_quality_claim", "customer_sequence_package", "approved_for_ordering", "local_safe_training_pipeline"):
        fail_if(claim not in blocked_claims, failures, f"local_release.blocked_claim_contains.{claim}", sorted(blocked_claims), f"contains {claim}")

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_claim_release_consistency_validation",
        "stage": 25,
        "claim_release_consistent": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "overall_summary_count": len(overall.get("summaries") or []),
        "overall_command_status": "not_released",
        "external_sqlite_mutated": False,
        "allow_apply": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "benchmark_completion_ready_rows": release_summary.get("benchmark_completion_ready_rows"),
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "approved_for_ordering": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "claim_release_consistent": report["claim_release_consistent"], "failure_count": report["failure_count"], "safe_for_model_claim": report["safe_for_model_claim"], "release_ready": report["release_ready"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["claim_release_consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
