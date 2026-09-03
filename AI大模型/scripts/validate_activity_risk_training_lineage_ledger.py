#!/usr/bin/env python3
"""Validate the activity_risk training lineage ledger."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LEDGER = AI_ROOT / "datasets" / "governance" / "activity_risk_training_lineage_ledger.jsonl"
REPORT = AI_ROOT / "reports" / "activity_risk_training_lineage_ledger_report.json"
FORMAL_REPORT = AI_ROOT / "reports" / "activity_risk_formal_label_decision_report.json"
TRAINING_CONTRACT = AI_ROOT / "reports" / "training_label_import_contract_report.json"
THRESHOLD_REPORT = AI_ROOT / "reports" / "five_head_training_threshold_report.json"
OUT = AI_ROOT / "reports" / "activity_risk_training_lineage_ledger_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: row must be a JSON object")
        rows.append(value)
    return rows


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate activity_risk lineage ledger")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    rows = load_jsonl(LEDGER)
    report = load_json(REPORT)
    formal = load_json(FORMAL_REPORT)
    training = load_json(TRAINING_CONTRACT)
    threshold = load_json(THRESHOLD_REPORT)
    activity_threshold = ((threshold.get("heads") or {}).get("activity_risk") or {})
    contract_totals = training.get("contract_totals") if isinstance(training.get("contract_totals"), dict) else {}
    failures: list[dict[str, Any]] = []

    expected_rows = as_int(formal.get("formal_decision_rows"))
    fail_if(len(rows) != expected_rows, failures, "ledger_rows_match_formal_decisions", len(rows), expected_rows)
    fail_if(report.get("ledger_rows") != len(rows), failures, "report_ledger_rows_match", report.get("ledger_rows"), len(rows))
    fail_if(report.get("formal_label_rows") != len(rows), failures, "report_formal_label_rows_match", report.get("formal_label_rows"), len(rows))
    fail_if(as_int(report.get("source_training_import_eligible_rows")) != as_int(formal.get("ready_for_training_import_rows")), failures, "source_training_import_eligible_matches_formal_report", report.get("source_training_import_eligible_rows"), formal.get("ready_for_training_import_rows"))
    fail_if(as_int(contract_totals.get("training_import_eligible_rows")) < len(rows), failures, "contract_training_import_eligible_covers_ledger", contract_totals.get("training_import_eligible_rows"), f">={len(rows)}")
    fail_if(as_int(activity_threshold.get("label_rows")) != len(rows), failures, "threshold_label_rows_match_ledger", activity_threshold.get("label_rows"), len(rows))
    fail_if(activity_threshold.get("thresholds_met") is not False, failures, "activity_thresholds_not_met", activity_threshold.get("thresholds_met"), False)
    fail_if(as_int(((activity_threshold.get("label_metrics") or {}).get("replicate_count"))) != 0, failures, "activity_replicate_count_zero", ((activity_threshold.get("label_metrics") or {}).get("replicate_count")), 0)

    seen_ids = set()
    for idx, row in enumerate(rows, start=1):
        decision_id = row.get("formal_decision_id")
        fail_if(not decision_id, failures, "row_decision_id_present", {"row": idx, "value": decision_id}, "non-empty")
        fail_if(decision_id in seen_ids, failures, "row_decision_id_unique", {"row": idx, "value": decision_id}, "unique")
        seen_ids.add(decision_id)
        for field in ("feedback_present", "authorization_present", "formal_label_present", "source_training_import_eligible", "source_trace_reviewed", "numbering_reviewed", "unit_condition_reviewed", "batch_control_reviewed", "replicate_policy_reviewed"):
            fail_if(row.get(field) is not True, failures, f"row_{field}_true", {"row": idx, "value": row.get(field)}, True)
        fail_if(row.get("activity_risk_label") not in {"low_activity_risk", "watch_activity_risk", "high_activity_risk"}, failures, "row_activity_risk_label_allowed", {"row": idx, "value": row.get("activity_risk_label")}, "allowed label")
        fail_if(row.get("replicate_decision") != "single_measurement_not_replicate", failures, "row_replicate_decision_single_measurement", {"row": idx, "value": row.get("replicate_decision")}, "single_measurement_not_replicate")
        fail_if(as_int(row.get("replicate_count_counted_for_training")) != 0, failures, "row_replicate_count_zero", {"row": idx, "value": row.get("replicate_count_counted_for_training")}, 0)
        for field in ("training_execution_allowed", "safe_for_model_claim", "release_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"row": idx, "value": row.get(field)}, False)

    for field in ("training_execution_allowed", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "ledger_rows": len(rows),
        "expected_formal_decision_rows": expected_rows,
        "training_import_eligible_rows_from_contract": contract_totals.get("training_import_eligible_rows"),
        "activity_threshold_label_rows": activity_threshold.get("label_rows"),
        "activity_threshold_group_count": ((activity_threshold.get("label_metrics") or {}).get("group_count")),
        "activity_threshold_replicate_count": ((activity_threshold.get("label_metrics") or {}).get("replicate_count")),
        "success": not failures,
        "failures": failures,
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Lineage validator only. It proves traceability and remaining threshold blockers, not model quality or release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "ledger_rows": validation["ledger_rows"],
        "activity_threshold_label_rows": validation["activity_threshold_label_rows"],
        "activity_threshold_replicate_count": validation["activity_threshold_replicate_count"],
        "failures": len(failures),
        "safe_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
