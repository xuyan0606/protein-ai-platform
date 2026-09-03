#!/usr/bin/env python3
"""Validate MCP wrapper staging gate is fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "governance" / "mcp_wrapper_staging_queue.jsonl"
REPORT = AI_ROOT / "reports" / "mcp_wrapper_staging_gate_report.json"
SCHEMA = AI_ROOT / "contracts" / "mcp_wrapper_staging.schema.json"
OUT = AI_ROOT / "reports" / "mcp_wrapper_staging_gate_validation_report.json"

REQUIRED_FIELDS = (
    "wrapper_id",
    "source_project",
    "source_url",
    "source_checksum",
    "license_review_status",
    "runtime_lock_status",
    "output_schema_status",
    "forbidden_writes_declared",
    "smoke_status",
    "staging_status",
    "production_allowed",
    "agent_exposure_allowed",
    "training_write_allowed",
    "safe_for_model_claim",
    "release_ready",
    "blockers",
)
FORBIDDEN_TRUE_FIELDS = (
    "production_allowed",
    "agent_exposure_allowed",
    "training_write_allowed",
    "safe_for_model_claim",
    "release_ready",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MCP wrapper staging gate")
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--schema", type=Path, default=SCHEMA)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    rows = read_jsonl(args.queue)
    report = load_json(args.report)
    schema = load_json(args.schema)
    fail_if(not args.queue.exists(), failures, "queue_present", str(args.queue), "exists")
    fail_if(not args.report.exists(), failures, "report_present", str(args.report), "exists")
    fail_if(not args.schema.exists(), failures, "schema_present", str(args.schema), "exists")
    fail_if(not schema.get("required"), failures, "schema_has_required", schema.get("required"), "non-empty")
    fail_if(report.get("queue_rows") != len(rows), failures, "report_queue_rows_match", report.get("queue_rows"), len(rows))

    ids = [row.get("wrapper_id") for row in rows]
    fail_if(len(ids) != len(set(ids)), failures, "unique_wrapper_ids", ids, "unique")
    for index, row in enumerate(rows):
        missing = [field for field in REQUIRED_FIELDS if field not in row]
        fail_if(bool(missing), failures, "required_fields", {"row": index, "wrapper_id": row.get("wrapper_id"), "missing": missing}, [])
        for field in FORBIDDEN_TRUE_FIELDS:
            fail_if(row.get(field) is True, failures, "forbidden_true_field", {"wrapper_id": row.get("wrapper_id"), "field": field}, False)
        fail_if(row.get("forbidden_writes_declared") is not True, failures, "forbidden_writes_declared_true", row.get("wrapper_id"), True)
        fail_if(not isinstance(row.get("blockers"), list) or not row.get("blockers"), failures, "blockers_non_empty", row.get("wrapper_id"), "non-empty list")
        if row.get("staging_status") == "ready":
            ready_checks = {
                "source_checksum": bool(row.get("source_checksum")),
                "license_review_status": row.get("license_review_status") == "reviewed_approved",
                "runtime_lock_status": row.get("runtime_lock_status") == "locked",
                "output_schema_status": row.get("output_schema_status") == "declared",
                "smoke_status": row.get("smoke_status") == "passed",
            }
            fail_if(not all(ready_checks.values()), failures, "ready_requires_all_receipts", {"wrapper_id": row.get("wrapper_id"), **ready_checks}, "all true")

    fail_if(report.get("production_allowed_rows") != 0, failures, "report_production_allowed_zero", report.get("production_allowed_rows"), 0)
    fail_if(report.get("agent_exposure_allowed_rows") != 0, failures, "report_agent_exposure_zero", report.get("agent_exposure_allowed_rows"), 0)
    fail_if(report.get("training_write_allowed_rows") != 0, failures, "report_training_write_zero", report.get("training_write_allowed_rows"), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "report_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "report_release_ready_false", report.get("release_ready"), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "queue_rows": len(rows),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "queue_rows": len(rows), "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
