#!/usr/bin/env python3
"""Build a real-input handoff package for the remaining P0 blockers."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = AI_ROOT / "酶改造突变体库-湿实验数据" / "4G_database-提高比活力"
RAW_MEASUREMENTS = SOURCE_DIR / "04_原始测量事实表.csv"
STRICT_HOLDOUT_DATASET = AI_ROOT / "cache" / "advanced_features" / "benchmarks" / "kwb_strict_mutation_holdout" / "dataset.jsonl"
PLATE_INTAKE = AI_ROOT / "datasets" / "feedback" / "experiment_feedback_plate.local.jsonl"
NUMBERING_DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
SUBSTRATE_DECISIONS = AI_ROOT / "datasets" / "curation" / "substrate_identity_review_decisions.jsonl"

WORK_PACKAGE = AI_ROOT / "datasets" / "governance" / "p676_p0_real_input_handoff_work_package.jsonl"
WORKSHEET_JSONL = AI_ROOT / "datasets" / "feedback" / "p676_4g_plate_feedback_human_review_worksheet.jsonl"
WORKSHEET_CSV = AI_ROOT / "datasets" / "feedback" / "p676_4g_plate_feedback_human_review_worksheet.csv"
REPORT = AI_ROOT / "reports" / "p676_p0_real_input_handoff_work_package_report.json"
MARKDOWN = AI_ROOT / "reports" / "p676_p0_real_input_handoff_work_package.md"

LOCATION_RE = re.compile(r"Row(?P<row>\d+)\s*,\s*Col(?P<col>\d+)", re.IGNORECASE)
MISSING_PLATE_FIELDS = [
    "formal_plate_id",
    "instrument_id",
    "protocol_version",
    "recorded_at",
    "human_qc_decision",
    "human_review_status",
]
FALSE_FLAGS = {
    "training_import_allowed": False,
    "safe_for_training_import": False,
    "safe_for_model_claim": False,
    "customer_delivery_ready": False,
    "release_ready": False,
    "production_execution_allowed": False,
    "completion_ready": False,
    "p0_unblocked": False,
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


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


def base_row(handoff_id: str, blocker: str, source_state: dict[str, Any], required_inputs: list[str]) -> dict[str, Any]:
    return {
        "handoff_id": handoff_id,
        "status": "open_blocked_waiting_for_real_input",
        "blocker": blocker,
        "source_state": source_state,
        "required_real_inputs": required_inputs,
        "required_human_or_external_input": True,
        "formal_write_allowed_now": False,
        "policy": "Real-input handoff only. This package is not a reviewed decision, formal intake, training label, model claim, release approval, or production authorization.",
        **FALSE_FLAGS,
    }


def build_worksheet(raw_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_hash = sha256(RAW_MEASUREMENTS)
    for source_row_index, row in enumerate(raw_rows, start=1):
        if row.get("metric_code") != "xylanase_activity":
            continue
        value = numeric(row.get("raw_value_numeric"))
        plate_row, plate_col = parse_location(row.get("source_location") or "")
        if value is None or plate_row is None or plate_col is None:
            continue
        rows.append({
            "worksheet_id": f"p676-4g-plate-feedback::{len(rows) + 1:04d}",
            "source_row_index": source_row_index,
            "measurement_id": row.get("measurement_id"),
            "sample_id": row.get("sample_id"),
            "batch_id": row.get("batch_id"),
            "variant_name": row.get("variant_name"),
            "source_file": row.get("source_file"),
            "source_location": row.get("source_location"),
            "plate_row_observed": plate_row,
            "plate_col_observed": plate_col,
            "assay_person_observed": row.get("assay_person"),
            "experiment_round_observed": row.get("experiment_round"),
            "replicate_status": row.get("replicate_status"),
            "confidence_tier_observed": row.get("confidence_tier"),
            "metric_name": row.get("metric_name"),
            "metric_code": row.get("metric_code"),
            "condition_name": row.get("condition_name"),
            "raw_value_numeric": value,
            "unit_standardized": row.get("unit_standardized"),
            "control_compare_scope": row.get("control_compare_scope"),
            "source_raw_measurement_file": rel(RAW_MEASUREMENTS),
            "source_raw_measurement_sha256": source_hash,
            "missing_formal_fields": MISSING_PLATE_FIELDS,
            "formal_plate_id": "",
            "instrument_id": "",
            "protocol_version": "",
            "recorded_at": "",
            "human_qc_decision": "",
            "human_review_status": "",
            "reviewer": "",
            "reviewed_at": "",
            "review_notes": "",
            "worksheet_only": True,
            "ready_for_formal_plate_intake": False,
            "formal_intake_written": False,
            **FALSE_FLAGS,
        })
    return rows


def write_worksheet_csv(rows: list[dict[str, Any]]) -> None:
    WORKSHEET_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        WORKSHEET_CSV.write_text("", encoding="utf-8")
        return
    fieldnames = [key for key in rows[0].keys() if key != "missing_formal_fields"]
    fieldnames.append("missing_formal_fields")
    with WORKSHEET_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["missing_formal_fields"] = ";".join(row["missing_formal_fields"])
            writer.writerow(out)


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    raw_rows = read_csv(RAW_MEASUREMENTS)
    worksheet_rows = build_worksheet(raw_rows)
    write_jsonl(WORKSHEET_JSONL, worksheet_rows)
    write_worksheet_csv(worksheet_rows)

    plate_validation = load_json(AI_ROOT / "reports" / "experiment_feedback_plate_intake_validation_report.json")
    plate_benchmark_validation = load_json(AI_ROOT / "reports" / "kwb_plate_level_feedback_benchmark_validation_report.json")
    activity_benchmark_validation = load_json(AI_ROOT / "reports" / "kwb_activity_risk_plate_feedback_benchmark_validation_report.json")
    benchmark_validation = load_json(AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json")
    substrate_validation = load_json(AI_ROOT / "reports" / "substrate_identity_evidence_candidate_validation_report.json")
    license_validation = load_json(AI_ROOT / "reports" / "external_license_review_decision_validation_report.json")
    biosecurity_validation = load_json(AI_ROOT / "reports" / "biosecurity_screening_decision_validation_report.json")
    ip_validation = load_json(AI_ROOT / "reports" / "sequence_ip_fto_decision_validation_report.json")
    numbering_validation = load_json(AI_ROOT / "reports" / "numbering_curation_validation_report.json")

    strict_holdout_rows = len(load_jsonl(STRICT_HOLDOUT_DATASET))
    numbering_decision_rows = len(load_jsonl(NUMBERING_DECISIONS))
    substrate_decision_rows = len(load_jsonl(SUBSTRATE_DECISIONS))
    work_rows = [
        base_row(
            "p676::plate_feedback_4g_human_qc_review",
            "4G plate feedback has benchmark rows but lacks formal plate intake metadata and human QC/review decisions",
            {
                "raw_measurement_rows": len(raw_rows),
                "worksheet_rows": len(worksheet_rows),
                "plate_benchmark_rows": plate_benchmark_validation.get("dataset_rows"),
                "activity_risk_benchmark_rows": activity_benchmark_validation.get("dataset_rows"),
                "formal_plate_intake_rows": plate_validation.get("input_rows"),
                "training_eligible_plate_rows": plate_validation.get("training_eligible_rows"),
                "worksheet_jsonl": rel(WORKSHEET_JSONL),
                "worksheet_csv": rel(WORKSHEET_CSV),
            },
            MISSING_PLATE_FIELDS + ["reviewer", "reviewed_at", "review_notes"],
        ),
        base_row(
            "p676::strict_mutation_holdout_benchmark",
            "KWB strict mutation holdout remains absent from formal benchmark score cache",
            {
                "strict_holdout_dataset_rows": strict_holdout_rows,
                "benchmark_valid_rows": benchmark_validation.get("valid_rows"),
                "benchmark_invalid_rows": benchmark_validation.get("invalid_rows"),
                "benchmark_error_counts": benchmark_validation.get("error_counts"),
            },
            ["real strict holdout records", "dataset checksum", "split definition", "leakage review", "human benchmark acceptance receipt"],
        ),
        base_row(
            "p676::substrate_identity_review",
            "reviewed substrate identity set lacks formal reviewed decisions",
            {
                "candidate_rows": substrate_validation.get("candidate_rows"),
                "valid_rows": substrate_validation.get("valid_rows"),
                "review_decision_rows": substrate_decision_rows,
                "ready_for_training_import": substrate_validation.get("ready_for_training_import"),
            },
            ["substrate identity reviewed decision rows", "source evidence locator", "reviewer", "reviewed_at", "decision rationale"],
        ),
        base_row(
            "p676::numbering_curation_review",
            "formal numbering decisions do not contain accepted canonical mappings for the remaining P0 labels",
            {
                "numbering_decision_rows": numbering_decision_rows,
                "numbering_validation_valid_rows": numbering_validation.get("valid_rows"),
                "numbering_apply_strict_rows": load_json(AI_ROOT / "reports" / "numbering_curation_apply_report.json").get("strict_rows"),
            },
            ["accepted canonical mapping decision", "source sequence/version", "WT match evidence", "reviewer", "reviewed_at"],
        ),
        base_row(
            "p676::license_ip_biosecurity_governance",
            "external license/IP/FTO/biosecurity decisions are still insufficient for delivery or production authorization",
            {
                "license_decision_rows": license_validation.get("decision_rows"),
                "verified_customer_delivery_rows": license_validation.get("verified_customer_delivery_rows"),
                "biosecurity_decision_rows": biosecurity_validation.get("decision_rows"),
                "biosecurity_ready_for_ordering": biosecurity_validation.get("ready_for_ordering"),
                "ip_fto_decision_rows": ip_validation.get("decision_rows"),
                "ip_fto_ready_for_customer_delivery": ip_validation.get("ready_for_customer_delivery"),
            },
            ["verified license scope", "IP/FTO decision", "biosecurity screening decision", "delivery authorization", "production authorization"],
        ),
    ]
    write_jsonl(WORK_PACKAGE, work_rows)

    report = {
        "created_at": created_at,
        "local_only": True,
        "work_package_rows": len(work_rows),
        "worksheet_rows": len(worksheet_rows),
        "raw_measurement_rows": len(raw_rows),
        "formal_plate_intake_rows": plate_validation.get("input_rows"),
        "training_eligible_plate_rows": plate_validation.get("training_eligible_rows"),
        "strict_holdout_dataset_rows": strict_holdout_rows,
        "substrate_review_decision_rows": substrate_decision_rows,
        "numbering_decision_rows": numbering_decision_rows,
        "required_real_input_rows": len(work_rows),
        "work_package_jsonl": rel(WORK_PACKAGE),
        "worksheet_jsonl": rel(WORKSHEET_JSONL),
        "worksheet_csv": rel(WORKSHEET_CSV),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "p0_unblocked": False,
        "policy": "P676 is a handoff package for real human/external inputs. It does not populate formal intake or decision files.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MARKDOWN.write_text(
        "\n".join([
            "# P676 P0 real-input handoff work package",
            "",
            f"- work_package_rows: `{len(work_rows)}`",
            f"- 4G worksheet_rows: `{len(worksheet_rows)}`",
            f"- formal_plate_intake_rows: `{plate_validation.get('input_rows')}`",
            f"- strict_holdout_dataset_rows: `{strict_holdout_rows}`",
            f"- substrate_review_decision_rows: `{substrate_decision_rows}`",
            f"- numbering_decision_rows: `{numbering_decision_rows}`",
            "- release_ready: `false`",
            "- safe_for_model_claim: `false`",
            "",
            "This package is only an operator handoff. It preserves missing fields and does not write formal reviewed decisions, plate intake, training labels, model claims, release approval, or production authorization.",
            "",
            f"4G worksheet JSONL: `{rel(WORKSHEET_JSONL)}`",
            f"4G worksheet CSV: `{rel(WORKSHEET_CSV)}`",
        ])
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "work_package_rows": len(work_rows),
        "worksheet_rows": len(worksheet_rows),
        "formal_plate_intake_rows": report["formal_plate_intake_rows"],
        "p0_unblocked": False,
        "output": str(REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
