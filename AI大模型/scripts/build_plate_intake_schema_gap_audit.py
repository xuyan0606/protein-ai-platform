#!/usr/bin/env python3
"""Build a row-level audit of plate intake schema gaps without performing intake."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = AI_ROOT / "contracts" / "experiment_feedback_plate.schema.json"
BACKLOG = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_plate_intake_backlog.jsonl"
BACKLOG_REPORT = AI_ROOT / "reports" / "experiment_feedback_plate_intake_backlog_report.json"
BACKLOG_VALIDATION = AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "feedback" / "plate_intake_schema_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "plate_intake_schema_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    schema = load_json(SCHEMA)
    backlog_rows = load_jsonl(BACKLOG)
    backlog_report = load_json(BACKLOG_REPORT)
    validation = load_json(BACKLOG_VALIDATION)
    required_fields = list(schema.get("required") or [])
    usable_qc = {"pass", "warning", "fail"}

    audit_rows = []
    missing_counts: Counter[str] = Counter()
    invalid_value_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    for row in backlog_rows:
        missing_fields = [str(field) for field in row.get("missing_required_fields") or []]
        invalid_fields = []
        if row.get("qc_flag") not in usable_qc:
            invalid_fields.append("qc_flag")
        for field in missing_fields:
            missing_counts[field] += 1
        for field in invalid_fields:
            invalid_value_counts[field] += 1
        for blocker in row.get("blockers") or []:
            blocker_counts[str(blocker)] += 1
        audit_rows.append({
            "created_at": created_at,
            "local_only": True,
            "audit_id": f"plate-schema-gap::{row.get('backlog_id')}",
            "backlog_id": row.get("backlog_id"),
            "source": row.get("source"),
            "source_path": row.get("source_path"),
            "packet_id": row.get("packet_id"),
            "plate_id": row.get("plate_id"),
            "well_id": row.get("well_id"),
            "variant_id": row.get("variant_id"),
            "required_schema_fields": required_fields,
            "missing_required_fields": missing_fields,
            "invalid_field_values": invalid_fields,
            "missing_required_field_count": len(missing_fields),
            "invalid_field_value_count": len(invalid_fields),
            "blockers": row.get("blockers") or [],
            "review_status": row.get("review_status"),
            "approved_for_plate_intake": row.get("approved_for_plate_intake") is True,
            "qc_flag": row.get("qc_flag"),
            "training_eligible": False,
            "claim_eligible_now": False,
            "formal_intake_allowed": False,
            "required_human_actions": row.get("required_human_actions") or [],
            "source_backlog": "datasets/feedback/experiment_feedback_plate_intake_backlog.jsonl",
            "source_backlog_report": "reports/experiment_feedback_plate_intake_backlog_report.json",
            "source_validation_report": "reports/experiment_feedback_plate_intake_validation_report.json",
            "training_import_allowed": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "production_execution_allowed": False,
            "policy": "Draft/backlog schema gap audit only; not a training label and does not approve plate intake, training import, claims, release, or production.",
        })

    report = {
        "created_at": created_at,
        "local_only": True,
        "required_schema_fields": required_fields,
        "backlog_rows": len(backlog_rows),
        "audit_rows": len(audit_rows),
        "source_backlog_report_rows": backlog_report.get("backlog_rows"),
        "source_validation_success": validation.get("ready_for_training") is False and validation.get("invalid_rows", 0) >= 0,
        "missing_required_field_counts": dict(sorted(missing_counts.items())),
        "invalid_field_value_counts": dict(sorted(invalid_value_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "rows_with_missing_required_fields": sum(1 for row in audit_rows if row["missing_required_fields"]),
        "rows_with_invalid_field_values": sum(1 for row in audit_rows if row["invalid_field_values"]),
        "rows_approved_for_formal_intake": sum(1 for row in audit_rows if row["approved_for_plate_intake"]),
        "training_eligible_rows": 0,
        "formal_intake_allowed": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/feedback/plate_intake_schema_gap_audit.jsonl",
        "policy": "Row-level draft/backlog plate schema audit only. Missing or invalid fields remain human-review blockers and never become training labels automatically.",
    }
    write_jsonl(OUT_JSONL, audit_rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "rows_with_missing_required_fields": report["rows_with_missing_required_fields"],
        "rows_with_invalid_field_values": report["rows_with_invalid_field_values"],
        "rows_approved_for_formal_intake": report["rows_approved_for_formal_intake"],
        "formal_intake_allowed": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
