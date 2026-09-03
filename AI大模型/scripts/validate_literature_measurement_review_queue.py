#!/usr/bin/env python3
"""Validate literature measurement review tasks without promoting evidence."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports/literature_measurement_review_queue.json"
DEFAULT_OUTPUT = ROOT / "reports/literature_measurement_review_queue_validation_report.json"

def load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("rows", []) if isinstance(data, dict) else data

def validate_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not row.get("review_task_id"):
        errors.append("review_task_id_missing")
    ids = [x for x in str(row.get("measurement_ids", "")).split("|") if x]
    if not ids:
        errors.append("measurement_ids_missing")
    if len(ids) != len(set(ids)):
        errors.append("duplicate_measurement_id")
    status = str(row.get("human_review_status", ""))
    if not (status.startswith("pending_") or status.startswith("blocked_")):
        errors.append("review_status_not_pending")
    def enabled(value: Any) -> bool:
        return value is True or (isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"})
    if any(enabled(row.get(key)) for key in ("training_eligible", "formal_decision_written", "safe_for_model_claim")):
        errors.append("training_or_claim_flag_open")
    return errors

def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set(); global_errors: list[str] = []; records = []
    for row in rows:
        task_id = str(row.get("review_task_id", ""))
        errors = validate_row(row)
        if task_id in seen:
            errors.append("duplicate_review_task_id")
            if "duplicate_review_task_id" not in global_errors: global_errors.append("duplicate_review_task_id")
        seen.add(task_id)
        records.append({"review_task_id": row.get("review_task_id"), "measurement_count": len([x for x in str(row.get("measurement_ids", "")).split("|") if x]), "valid": not errors, "errors": errors})
    return {"queue_rows": len(rows), "valid_rows": sum(r["valid"] for r in records), "invalid_rows": sum(not r["valid"] for r in records), "global_errors": global_errors, "records": records, "training_import_allowed": False, "safe_for_model_claim": False, "release_ready": False, "policy": "Evidence-only review queue; human review and independent authorization remain required."}

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--input", type=Path, default=DEFAULT_INPUT); p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT); a = p.parse_args()
    report = build_report(load_rows(a.input)); a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(json.dumps(report, ensure_ascii=False)); return 0 if not report["global_errors"] and report["invalid_rows"] == 0 else 1
if __name__ == "__main__": raise SystemExit(main())
