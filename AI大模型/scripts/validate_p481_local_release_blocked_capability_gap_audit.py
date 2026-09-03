#!/usr/bin/env python3
"""Validate the P481 local release blocked capability gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
LOCAL_RELEASE_CONSISTENCY = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
SAFETY_GUARD = AI_ROOT / "reports" / "local_release_safety_guard_link_validation_report.json"
GUARD_COVERAGE = AI_ROOT / "reports" / "local_release_guard_coverage_validation_report.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p481_local_release_blocked_capability_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p481_local_release_blocked_capability_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p481_local_release_blocked_capability_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    release = load_json(LOCAL_RELEASE)
    consistency = load_json(LOCAL_RELEASE_CONSISTENCY)
    safety_guard = load_json(SAFETY_GUARD)
    guard_coverage = load_json(GUARD_COVERAGE)
    claim_matrix = load_json(CLAIM_MATRIX)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    blocked_capabilities = list(release.get("blocked_capabilities") or [])
    failures: list[dict[str, Any]] = []
    expected_rows = len(blocked_capabilities) + 1

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("blocked_capability_rows") != len(blocked_capabilities), failures, "blocked_capability_rows_bound", report.get("blocked_capability_rows"), len(blocked_capabilities))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(report.get("blocked_capabilities") != blocked_capabilities, failures, "blocked_capabilities_bound", report.get("blocked_capabilities"), blocked_capabilities)
    fail_if(report.get("release_ready_source") is not False, failures, "release_ready_source_false", report.get("release_ready_source"), False)
    fail_if(report.get("artifact_count") != release.get("artifact_count"), failures, "artifact_count_bound", report.get("artifact_count"), release.get("artifact_count"))
    fail_if(report.get("missing_artifacts") != (release.get("missing_artifacts") or []), failures, "missing_artifacts_bound", report.get("missing_artifacts"), release.get("missing_artifacts") or [])
    fail_if(report.get("consistency_success") is not True, failures, "consistency_success_true", report.get("consistency_success"), True)
    fail_if(report.get("consistency_failure_count") != consistency.get("failure_count"), failures, "consistency_failure_count_bound", report.get("consistency_failure_count"), consistency.get("failure_count"))
    fail_if(report.get("safety_guard_success") is not True, failures, "safety_guard_success_true", report.get("safety_guard_success"), True)
    fail_if(report.get("safety_guard_failure_count") != safety_guard.get("failure_count"), failures, "safety_guard_failure_count_bound", report.get("safety_guard_failure_count"), safety_guard.get("failure_count"))
    fail_if(report.get("guard_coverage_success") is not True, failures, "guard_coverage_success_true", report.get("guard_coverage_success"), True)
    fail_if(report.get("guard_coverage_failure_count") != guard_coverage.get("failure_count"), failures, "guard_coverage_failure_count_bound", report.get("guard_coverage_failure_count"), guard_coverage.get("failure_count"))
    fail_if(report.get("claims_allowed") != claim_matrix.get("claims_allowed"), failures, "claims_allowed_bound", report.get("claims_allowed"), claim_matrix.get("claims_allowed"))
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))

    seen_capabilities: list[Any] = []
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"local_release_blocked_capability_gap", "local_release_blocked_capability_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P481 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "local_release_blocked_capability_gap":
            capability = row.get("capability")
            seen_capabilities.append(capability)
            fail_if(capability not in blocked_capabilities, failures, "capability_known", {"index": idx, "observed": capability}, blocked_capabilities)
            fail_if(row.get("blocked") is not True, failures, "capability_blocked_true", {"index": idx, "observed": row.get("blocked")}, True)
            source_state = row.get("source_state") or {}
            fail_if(source_state.get("release_ready") is not False, failures, "source_release_ready_false", {"index": idx, "observed": source_state.get("release_ready")}, False)
        if gap_type == "local_release_blocked_capability_summary_gap":
            fail_if(row.get("blocked_capability_count") != len(blocked_capabilities), failures, "summary_blocked_capability_count_bound", row.get("blocked_capability_count"), len(blocked_capabilities))

    fail_if(sorted(seen_capabilities) != sorted(blocked_capabilities), failures, "blocked_capabilities_exactly_covered", sorted(seen_capabilities), sorted(blocked_capabilities))
    fail_if(seen_types.count("local_release_blocked_capability_gap") != len(blocked_capabilities), failures, "capability_gap_type_count", seen_types.count("local_release_blocked_capability_gap"), len(blocked_capabilities))
    fail_if(seen_types.count("local_release_blocked_capability_summary_gap") != 1, failures, "summary_type_count", seen_types.count("local_release_blocked_capability_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "blocked_capability_rows": len(blocked_capabilities),
        "blocked_capabilities": blocked_capabilities,
        "release_ready": False,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Local release blocked capabilities do not authorize downstream gates.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "blocked_capability_rows": result["blocked_capability_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
