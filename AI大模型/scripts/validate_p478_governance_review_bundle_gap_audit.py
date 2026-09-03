#!/usr/bin/env python3
"""Validate the P478 governance review bundle gap audit."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = AI_ROOT / "datasets" / "governance" / "governance_review_bundle.jsonl"
BUNDLE_REPORT = AI_ROOT / "reports" / "governance_review_bundle_report.json"
BUNDLE_VALIDATION = AI_ROOT / "reports" / "governance_review_bundle_validation_report.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p478_governance_review_bundle_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p478_governance_review_bundle_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p478_governance_review_bundle_gap_audit_validation_report.json"


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
    bundle_rows = load_jsonl(BUNDLE)
    bundle_report = load_json(BUNDLE_REPORT)
    validation = load_json(BUNDLE_VALIDATION)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    failures: list[dict[str, Any]] = []
    expected_rows = len(bundle_rows) + 1
    workstream_counts = dict(sorted(Counter(str(row.get("workstream")) for row in bundle_rows).items()))
    status_counts = dict(sorted(Counter(str(row.get("current_status")) for row in bundle_rows).items()))

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("bundle_audit_rows") != len(bundle_rows), failures, "bundle_audit_rows_bound", report.get("bundle_audit_rows"), len(bundle_rows))
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    for field in ("bundle_rows", "open_rows", "completion_ready_rows", "human_review_required_rows", "no_auto_approval_rows"):
        fail_if(report.get(field) != bundle_report.get(field), failures, f"{field}_bound", report.get(field), bundle_report.get(field))
    fail_if(report.get("bundle_ready") is not False, failures, "bundle_ready_false", report.get("bundle_ready"), False)
    fail_if(report.get("bundle_safe_for_model_claim") is not False, failures, "bundle_safe_for_model_claim_false", report.get("bundle_safe_for_model_claim"), False)
    fail_if(report.get("bundle_release_ready") is not False, failures, "bundle_release_ready_false", report.get("bundle_release_ready"), False)
    for field, validation_field in (
        ("validation_valid_rows", "valid_rows"),
        ("validation_invalid_rows", "invalid_rows"),
        ("validation_open_rows", "open_rows"),
        ("validation_completion_ready_rows", "completion_ready_rows"),
        ("all_source_rows_covered", "all_source_rows_covered"),
        ("all_rows_valid", "all_rows_valid"),
        ("validation_ready", "ready"),
    ):
        fail_if(report.get(field) != validation.get(validation_field), failures, f"{field}_bound", report.get(field), validation.get(validation_field))
    fail_if(report.get("workstream_counts") != workstream_counts, failures, "workstream_counts_bound", report.get("workstream_counts"), workstream_counts)
    fail_if(report.get("status_counts") != status_counts, failures, "status_counts_bound", report.get("status_counts"), status_counts)
    fail_if(bundle_report.get("open_rows") != len(bundle_rows), failures, "all_bundle_rows_open", bundle_report.get("open_rows"), len(bundle_rows))
    fail_if(bundle_report.get("completion_ready_rows") != 0, failures, "completion_ready_rows_zero", bundle_report.get("completion_ready_rows"), 0)
    fail_if(validation.get("completion_ready_rows") != 0, failures, "validation_completion_ready_rows_zero", validation.get("completion_ready_rows"), 0)
    fail_if(validation.get("ready") is not False, failures, "validation_ready_false", validation.get("ready"), False)

    validation_by_id = {
        str(row.get("bundle_id")): row
        for row in validation.get("records", [])
        if row.get("bundle_id")
    }
    bundle_by_id = {row.get("bundle_id"): row for row in bundle_rows}
    seen_types: list[Any] = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"governance_review_bundle_item_gap", "governance_review_bundle_summary_gap"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P478 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "governance_review_bundle_item_gap":
            source = bundle_by_id.get(row.get("bundle_id"), {})
            source_validation = validation_by_id.get(str(row.get("bundle_id")), {})
            for field in ("workstream", "priority", "review_order", "current_status"):
                fail_if(row.get(field) != source.get(field), failures, f"item_{field}_bound", {"index": idx, "observed": row.get(field)}, source.get(field))
            fail_if(row.get("bundle_completion_ready") is not False, failures, "item_bundle_completion_ready_false", {"index": idx, "observed": row.get("bundle_completion_ready")}, False)
            fail_if(row.get("validation_valid") is not True, failures, "item_validation_valid_true", {"index": idx, "observed": row.get("validation_valid")}, True)
            fail_if(row.get("validation_completion_ready") is not False, failures, "item_validation_completion_ready_false", {"index": idx, "observed": row.get("validation_completion_ready")}, False)
            fail_if(source_validation.get("completion_ready") is not False, failures, "source_validation_completion_ready_false", {"index": idx, "observed": source_validation.get("completion_ready")}, False)
        if gap_type == "governance_review_bundle_summary_gap":
            fail_if(row.get("bundle_rows") != bundle_report.get("bundle_rows"), failures, "summary_bundle_rows_bound", row.get("bundle_rows"), bundle_report.get("bundle_rows"))
            fail_if(row.get("open_rows") != bundle_report.get("open_rows"), failures, "summary_open_rows_bound", row.get("open_rows"), bundle_report.get("open_rows"))
            fail_if(row.get("completion_ready_rows") != 0, failures, "summary_completion_ready_rows_zero", row.get("completion_ready_rows"), 0)
            fail_if(row.get("validation_valid_rows") != validation.get("valid_rows"), failures, "summary_validation_valid_rows_bound", row.get("validation_valid_rows"), validation.get("valid_rows"))
            fail_if(row.get("validation_open_rows") != validation.get("open_rows"), failures, "summary_validation_open_rows_bound", row.get("validation_open_rows"), validation.get("open_rows"))
            fail_if(row.get("workstream_counts") != workstream_counts, failures, "summary_workstream_counts_bound", row.get("workstream_counts"), workstream_counts)
            fail_if(row.get("status_counts") != status_counts, failures, "summary_status_counts_bound", row.get("status_counts"), status_counts)

    fail_if(seen_types.count("governance_review_bundle_item_gap") != len(bundle_rows), failures, "item_gap_type_count", seen_types.count("governance_review_bundle_item_gap"), len(bundle_rows))
    fail_if(seen_types.count("governance_review_bundle_summary_gap") != 1, failures, "summary_type_count", seen_types.count("governance_review_bundle_summary_gap"), 1)
    for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "bundle_audit_rows": len(bundle_rows),
        "bundle_rows": bundle_report.get("bundle_rows"),
        "open_rows": bundle_report.get("open_rows"),
        "completion_ready_rows": bundle_report.get("completion_ready_rows"),
        "validation_valid_rows": validation.get("valid_rows"),
        "validation_ready": validation.get("ready"),
        "workstream_counts": workstream_counts,
        "status_counts": status_counts,
        "failures": failures,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Governance review bundle gaps do not authorize training, claims, release, delivery, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "bundle_audit_rows": result["bundle_audit_rows"],
        "open_rows": result["open_rows"],
        "completion_ready_rows": result["completion_ready_rows"],
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
