#!/usr/bin/env python3
"""Validate the P676 real-input handoff package remains fail-closed."""

from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
RAW_MEASUREMENTS = AI_ROOT / "酶改造突变体库-湿实验数据" / "4G_database-提高比活力" / "04_原始测量事实表.csv"
WORK_PACKAGE = AI_ROOT / "datasets" / "governance" / "p676_p0_real_input_handoff_work_package.jsonl"
WORKSHEET_JSONL = AI_ROOT / "datasets" / "feedback" / "p676_4g_plate_feedback_human_review_worksheet.jsonl"
WORKSHEET_CSV = AI_ROOT / "datasets" / "feedback" / "p676_4g_plate_feedback_human_review_worksheet.csv"
REPORT = AI_ROOT / "reports" / "p676_p0_real_input_handoff_work_package_report.json"
OUT = AI_ROOT / "reports" / "p676_p0_real_input_handoff_work_package_validation_report.json"

LOCATION_RE = re.compile(r"Row(?P<row>\d+)\s*,\s*Col(?P<col>\d+)", re.IGNORECASE)
EXPECTED_HANDOFF_IDS = {
    "p676::plate_feedback_4g_human_qc_review",
    "p676::strict_mutation_holdout_benchmark",
    "p676::substrate_identity_review",
    "p676::numbering_curation_review",
    "p676::license_ip_biosecurity_governance",
}
FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
    "p0_unblocked",
)
EMPTY_REVIEW_FIELDS = (
    "formal_plate_id",
    "instrument_id",
    "protocol_version",
    "recorded_at",
    "human_qc_decision",
    "human_review_status",
    "reviewer",
    "reviewed_at",
    "review_notes",
)
MISSING_PLATE_FIELDS = {
    "formal_plate_id",
    "instrument_id",
    "protocol_version",
    "recorded_at",
    "human_qc_decision",
    "human_review_status",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def numeric(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_location(value: str) -> tuple[int | None, int | None]:
    match = LOCATION_RE.search(value or "")
    if not match:
        return None, None
    return int(match.group("row")), int(match.group("col"))


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def expected_worksheet_rows(raw_rows: list[dict[str, str]]) -> int:
    count = 0
    for row in raw_rows:
        plate_row, plate_col = parse_location(row.get("source_location") or "")
        if row.get("metric_code") == "xylanase_activity" and numeric(row.get("raw_value_numeric")) is not None and plate_row is not None and plate_col is not None:
            count += 1
    return count


def main() -> int:
    raw_rows = read_csv(RAW_MEASUREMENTS)
    package_rows = load_jsonl(WORK_PACKAGE)
    worksheet_rows = load_jsonl(WORKSHEET_JSONL)
    report = load_json(REPORT)
    plate_validation = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
    failures: list[dict[str, Any]] = []

    fail_if(len(package_rows) != len(EXPECTED_HANDOFF_IDS), failures, "work_package_rows_exact", len(package_rows), len(EXPECTED_HANDOFF_IDS))
    fail_if({row.get("handoff_id") for row in package_rows} != EXPECTED_HANDOFF_IDS, failures, "handoff_ids_exact", sorted(row.get("handoff_id") for row in package_rows), sorted(EXPECTED_HANDOFF_IDS))
    for idx, row in enumerate(package_rows, start=1):
        fail_if(row.get("status") != "open_blocked_waiting_for_real_input", failures, "row_status_open_blocked", {"row": idx, "value": row.get("status")}, "open_blocked_waiting_for_real_input")
        fail_if(row.get("required_human_or_external_input") is not True, failures, "row_requires_input_true", {"row": idx, "value": row.get("required_human_or_external_input")}, True)
        fail_if(row.get("formal_write_allowed_now") is not False, failures, "row_formal_write_allowed_false", {"row": idx, "value": row.get("formal_write_allowed_now")}, False)
        fail_if(not row.get("required_real_inputs"), failures, "row_required_inputs_present", {"row": idx, "value": row.get("required_real_inputs")}, "non-empty")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": idx, "value": row.get(field)}, False)

    expected_rows = expected_worksheet_rows(raw_rows)
    fail_if(len(worksheet_rows) != expected_rows, failures, "worksheet_rows_bind_raw_csv", len(worksheet_rows), expected_rows)
    fail_if(report.get("worksheet_rows") != expected_rows, failures, "report_worksheet_rows_bind_raw_csv", report.get("worksheet_rows"), expected_rows)
    fail_if(report.get("work_package_rows") != len(EXPECTED_HANDOFF_IDS), failures, "report_work_package_rows", report.get("work_package_rows"), len(EXPECTED_HANDOFF_IDS))
    fail_if(report.get("formal_plate_intake_rows") != plate_validation.get("input_rows"), failures, "report_plate_intake_bound", report.get("formal_plate_intake_rows"), plate_validation.get("input_rows"))
    fail_if(report.get("training_eligible_plate_rows") != plate_validation.get("training_eligible_rows"), failures, "report_plate_training_bound", report.get("training_eligible_plate_rows"), plate_validation.get("training_eligible_rows"))
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    worksheet_ids = set()
    for idx, row in enumerate(worksheet_rows, start=1):
        worksheet_ids.add(row.get("worksheet_id"))
        fail_if(row.get("worksheet_only") is not True, failures, "worksheet_only_true", {"row": idx, "value": row.get("worksheet_only")}, True)
        fail_if(row.get("ready_for_formal_plate_intake") is not False, failures, "worksheet_ready_for_formal_intake_false", {"row": idx, "value": row.get("ready_for_formal_plate_intake")}, False)
        fail_if(row.get("formal_intake_written") is not False, failures, "worksheet_formal_intake_written_false", {"row": idx, "value": row.get("formal_intake_written")}, False)
        fail_if(set(row.get("missing_formal_fields") or []) != MISSING_PLATE_FIELDS, failures, "worksheet_missing_formal_fields", {"row": idx, "value": row.get("missing_formal_fields")}, sorted(MISSING_PLATE_FIELDS))
        for field in EMPTY_REVIEW_FIELDS:
            fail_if(row.get(field) not in ("", None), failures, f"worksheet_{field}_empty", {"row": idx, "value": row.get(field)}, "")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"worksheet_{field}_false", {"row": idx, "value": row.get(field)}, False)
    fail_if(len(worksheet_ids) != len(worksheet_rows), failures, "worksheet_ids_unique", len(worksheet_ids), len(worksheet_rows))
    fail_if(not WORKSHEET_CSV.exists(), failures, "worksheet_csv_exists", WORKSHEET_CSV.exists(), True)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "work_package_rows": len(package_rows),
        "worksheet_rows": len(worksheet_rows),
        "raw_measurement_rows": len(raw_rows),
        "formal_plate_intake_rows": plate_validation.get("input_rows"),
        "training_eligible_plate_rows": plate_validation.get("training_eligible_rows"),
        "required_real_input_rows": len(EXPECTED_HANDOFF_IDS),
        "worksheet_csv_exists": WORKSHEET_CSV.exists(),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "p0_unblocked": False,
        "policy": "Validation only. P676 handoff rows and worksheet rows remain non-promotional until real reviewed inputs are written to their separate formal files.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "work_package_rows": result["work_package_rows"],
        "worksheet_rows": result["worksheet_rows"],
        "formal_plate_intake_rows": result["formal_plate_intake_rows"],
        "failures": result["failure_count"],
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
