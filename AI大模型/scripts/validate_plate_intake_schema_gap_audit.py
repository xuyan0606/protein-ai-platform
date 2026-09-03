#!/usr/bin/env python3
"""Validate the plate intake schema gap audit remains source-bound and fail-closed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = AI_ROOT / "contracts" / "experiment_feedback_plate.schema.json"
BACKLOG = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_plate_intake_backlog.jsonl"
BACKLOG_REPORT = AI_ROOT / "reports" / "experiment_feedback_plate_intake_backlog_report.json"
AUDIT_JSONL = AI_ROOT / "datasets" / "feedback" / "plate_intake_schema_gap_audit.jsonl"
AUDIT_REPORT = AI_ROOT / "reports" / "plate_intake_schema_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "plate_intake_schema_gap_audit_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    schema = load_json(SCHEMA)
    backlog_rows = load_jsonl(BACKLOG)
    audit_rows = load_jsonl(AUDIT_JSONL)
    backlog_report = load_json(BACKLOG_REPORT)
    audit_report = load_json(AUDIT_REPORT)
    required_fields = list(schema.get("required") or [])
    usable_qc = {"pass", "warning", "fail"}
    failures: list[dict[str, Any]] = []

    fail_if(audit_report.get("backlog_rows") != len(backlog_rows), failures, "backlog_rows_match", audit_report.get("backlog_rows"), len(backlog_rows))
    fail_if(audit_report.get("audit_rows") != len(audit_rows), failures, "audit_rows_match", audit_report.get("audit_rows"), len(audit_rows))
    fail_if(audit_report.get("source_backlog_report_rows") != backlog_report.get("backlog_rows"), failures, "source_backlog_report_rows_bound", audit_report.get("source_backlog_report_rows"), backlog_report.get("backlog_rows"))
    fail_if(audit_report.get("required_schema_fields") != required_fields, failures, "required_schema_fields_exact", audit_report.get("required_schema_fields"), required_fields)
    fail_if(audit_report.get("rows_approved_for_formal_intake") != 0, failures, "rows_approved_for_formal_intake_zero", audit_report.get("rows_approved_for_formal_intake"), 0)
    fail_if(audit_report.get("training_eligible_rows") != 0, failures, "training_eligible_rows_zero", audit_report.get("training_eligible_rows"), 0)

    for idx, (source, audit) in enumerate(zip(backlog_rows, audit_rows)):
        missing = [str(field) for field in source.get("missing_required_fields") or []]
        invalid = ["qc_flag"] if source.get("qc_flag") not in usable_qc else []
        fail_if(audit.get("backlog_id") != source.get("backlog_id"), failures, "audit_backlog_id_source_bound", {"index": idx, "observed": audit.get("backlog_id")}, source.get("backlog_id"))
        fail_if(audit.get("missing_required_fields") != missing, failures, "audit_missing_fields_source_bound", {"index": idx, "observed": audit.get("missing_required_fields")}, missing)
        fail_if(audit.get("invalid_field_values") != invalid, failures, "audit_invalid_values_source_bound", {"index": idx, "observed": audit.get("invalid_field_values")}, invalid)
        fail_if(audit.get("required_schema_fields") != required_fields, failures, "audit_required_fields_exact", {"index": idx, "observed": audit.get("required_schema_fields")}, required_fields)
        fail_if(audit.get("approved_for_plate_intake") is not False, failures, "audit_approved_for_plate_intake_false", {"index": idx, "observed": audit.get("approved_for_plate_intake")}, False)
        fail_if(audit.get("training_eligible") is not False, failures, "audit_training_eligible_false", {"index": idx, "observed": audit.get("training_eligible")}, False)
        fail_if(audit.get("formal_intake_allowed") is not False, failures, "audit_formal_intake_allowed_false", {"index": idx, "observed": audit.get("formal_intake_allowed")}, False)
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
            fail_if(audit.get(field) is not False, failures, f"audit_{field}_false", {"index": idx, "observed": audit.get(field)}, False)

    for field in ("formal_intake_allowed", "training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        fail_if(audit_report.get(field) is not False, failures, f"report_{field}_false", audit_report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "backlog_rows": len(backlog_rows),
        "audit_rows": len(audit_rows),
        "rows_with_missing_required_fields": sum(1 for row in audit_rows if row.get("missing_required_fields")),
        "rows_with_invalid_field_values": sum(1 for row in audit_rows if row.get("invalid_field_values")),
        "failures": failures,
        "formal_intake_allowed": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. Plate schema gaps remain human-review blockers and cannot become training labels automatically.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "backlog_rows": validation["backlog_rows"],
        "audit_rows": validation["audit_rows"],
        "rows_with_missing_required_fields": validation["rows_with_missing_required_fields"],
        "rows_with_invalid_field_values": validation["rows_with_invalid_field_values"],
        "failures": len(failures),
        "formal_intake_allowed": False,
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
