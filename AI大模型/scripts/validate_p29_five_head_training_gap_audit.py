#!/usr/bin/env python3
"""Validate the P29 five-head training execution gap audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
GAP_ACTIONS = AI_ROOT / "datasets" / "governance" / "five_head_training_gap_actions.jsonl"
SAMPLE_QUEUE = AI_ROOT / "datasets" / "governance" / "five_head_training_sample_gap_queue.jsonl"
GAP_REPORT = AI_ROOT / "reports" / "five_head_training_gap_plan_report.json"
THRESHOLD_REPORT = AI_ROOT / "reports" / "five_head_training_threshold_report.json"
SAMPLE_REPORT = AI_ROOT / "reports" / "five_head_training_sample_gap_queue_report.json"
EXECUTION_REPORT = AI_ROOT / "reports" / "five_head_training_execution_contract_report.json"
EXECUTION_VALIDATION = AI_ROOT / "reports" / "five_head_training_execution_contract_validation_report.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
MODEL_QUALITY = AI_ROOT / "reports" / "model_quality_hard_gate_contract_report.json"
AUDIT = AI_ROOT / "datasets" / "governance" / "p29_five_head_training_gap_audit.jsonl"
REPORT = AI_ROOT / "reports" / "p29_five_head_training_gap_audit_report.json"
OUT = AI_ROOT / "reports" / "p29_five_head_training_gap_audit_validation_report.json"


EXPECTED_HEADS = ("mutation_rank", "stability", "activity_risk", "substrate_fit", "assay_success")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def claim_row(matrix: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for row in matrix.get("claims") or []:
        if isinstance(row, dict) and row.get("claim_id") == claim_id:
            return row
    return {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    gap_actions = load_jsonl(GAP_ACTIONS)
    sample_rows = load_jsonl(SAMPLE_QUEUE)
    gap_report = load_json(GAP_REPORT)
    threshold = load_json(THRESHOLD_REPORT)
    sample_report = load_json(SAMPLE_REPORT)
    execution = load_json(EXECUTION_REPORT)
    execution_validation = load_json(EXECUTION_VALIDATION)
    claim_matrix = load_json(CLAIM_MATRIX)
    model_quality = load_json(MODEL_QUALITY)
    audit_rows = load_jsonl(AUDIT)
    report = load_json(REPORT)
    five_head_claim = claim_row(claim_matrix, "five_head_training_run")
    training_label = execution.get("training_label_import") if isinstance(execution.get("training_label_import"), dict) else {}
    failures: list[dict[str, Any]] = []

    expected_rows = len(gap_actions) + len(sample_rows) + 1
    gap_heads = [row.get("head") for row in gap_actions]
    sample_heads = [row.get("head") for row in sample_rows]
    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("gap_action_rows") != len(gap_actions), failures, "gap_action_rows_bound", report.get("gap_action_rows"), len(gap_actions))
    fail_if(report.get("sample_gap_rows") != len(sample_rows), failures, "sample_gap_rows_bound", report.get("sample_gap_rows"), len(sample_rows))
    fail_if(report.get("expected_heads") != list(EXPECTED_HEADS), failures, "expected_heads_match", report.get("expected_heads"), list(EXPECTED_HEADS))
    fail_if(gap_heads != list(EXPECTED_HEADS), failures, "gap_action_heads_match", gap_heads, list(EXPECTED_HEADS))
    fail_if(sample_heads != list(EXPECTED_HEADS), failures, "sample_gap_heads_match", sample_heads, list(EXPECTED_HEADS))
    fail_if(report.get("gap_action_heads") != gap_heads, failures, "report_gap_action_heads_bound", report.get("gap_action_heads"), gap_heads)
    fail_if(report.get("sample_gap_heads") != sample_heads, failures, "report_sample_gap_heads_bound", report.get("sample_gap_heads"), sample_heads)

    fail_if(report.get("gap_plan_ready_heads") != gap_report.get("ready_heads"), failures, "gap_plan_ready_heads_bound", report.get("gap_plan_ready_heads"), gap_report.get("ready_heads"))
    fail_if(report.get("gap_plan_blocked_heads") != gap_report.get("blocked_heads"), failures, "gap_plan_blocked_heads_bound", report.get("gap_plan_blocked_heads"), gap_report.get("blocked_heads"))
    fail_if(report.get("threshold_ready_heads") != threshold.get("threshold_ready_heads"), failures, "threshold_ready_heads_bound", report.get("threshold_ready_heads"), threshold.get("threshold_ready_heads"))
    fail_if(report.get("threshold_blocked_heads") != threshold.get("blocked_heads"), failures, "threshold_blocked_heads_bound", report.get("threshold_blocked_heads"), threshold.get("blocked_heads"))
    fail_if(as_int(report.get("ready_head_count")) != as_int(execution.get("ready_head_count")), failures, "ready_head_count_bound", report.get("ready_head_count"), execution.get("ready_head_count"))
    fail_if(as_int(report.get("total_head_training_rows")) != as_int(execution.get("total_head_training_rows")), failures, "total_head_training_rows_bound", report.get("total_head_training_rows"), execution.get("total_head_training_rows"))
    fail_if(as_int(report.get("training_import_eligible_rows")) != as_int(training_label.get("training_import_eligible_rows")), failures, "training_import_eligible_rows_bound", report.get("training_import_eligible_rows"), training_label.get("training_import_eligible_rows"))
    fail_if(report.get("sample_gap_queue_rows") != sample_report.get("queue_rows"), failures, "sample_gap_queue_rows_bound", report.get("sample_gap_queue_rows"), sample_report.get("queue_rows"))
    fail_if(report.get("missing_label_rows_total") != sample_report.get("missing_label_rows_total"), failures, "missing_label_rows_total_bound", report.get("missing_label_rows_total"), sample_report.get("missing_label_rows_total"))
    fail_if(report.get("missing_replicates_total") != sample_report.get("missing_replicates_total"), failures, "missing_replicates_total_bound", report.get("missing_replicates_total"), sample_report.get("missing_replicates_total"))
    fail_if(report.get("missing_groups_total") != sample_report.get("missing_groups_total"), failures, "missing_groups_total_bound", report.get("missing_groups_total"), sample_report.get("missing_groups_total"))
    fail_if(report.get("blocked_reasons") != execution.get("blocked_reasons"), failures, "blocked_reasons_bound", report.get("blocked_reasons"), execution.get("blocked_reasons"))
    fail_if(report.get("five_head_claim_ready") is not False, failures, "five_head_claim_ready_false", report.get("five_head_claim_ready"), False)
    fail_if(report.get("five_head_claim_allowed") is not False, failures, "five_head_claim_allowed_false", report.get("five_head_claim_allowed"), False)
    fail_if(five_head_claim.get("ready") is not False or five_head_claim.get("allowed") is not False, failures, "claim_matrix_five_head_blocked", {"ready": five_head_claim.get("ready"), "allowed": five_head_claim.get("allowed")}, {"ready": False, "allowed": False})
    fail_if((model_quality.get("current_state") or {}).get("model_quality_ready") is not False, failures, "model_quality_ready_false", (model_quality.get("current_state") or {}).get("model_quality_ready"), False)
    fail_if(execution_validation.get("success") is not True, failures, "execution_validation_success_true", execution_validation.get("success"), True)

    gap_by_head = {row.get("head"): row for row in gap_actions}
    sample_by_head = {row.get("head"): row for row in sample_rows}
    seen_types = []
    for idx, row in enumerate(audit_rows):
        gap_type = row.get("gap_type")
        seen_types.append(gap_type)
        fail_if(gap_type not in {"five_head_training_gap_action", "five_head_sample_threshold_gap", "five_head_training_execution_summary"}, failures, "gap_type_allowed", {"index": idx, "observed": gap_type}, "allowed P29 gap type")
        for field in ("training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed", "completion_ready"):
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
        if gap_type == "five_head_training_gap_action":
            source = gap_by_head.get(row.get("head"), {})
            fail_if(row.get("thresholds_met") is not False, failures, "gap_action_thresholds_met_false", {"index": idx, "observed": row.get("thresholds_met")}, False)
            fail_if(row.get("training_unlocked") is not False, failures, "gap_action_training_unlocked_false", {"index": idx, "observed": row.get("training_unlocked")}, False)
            fail_if(as_int(row.get("current_training_rows")) != as_int(source.get("current_training_rows")), failures, "gap_action_current_training_rows_bound", {"index": idx, "observed": row.get("current_training_rows")}, source.get("current_training_rows"))
            fail_if(as_int(row.get("missing_to_minimum")) != as_int(source.get("missing_to_minimum")), failures, "gap_action_missing_to_minimum_bound", {"index": idx, "observed": row.get("missing_to_minimum")}, source.get("missing_to_minimum"))
        if gap_type == "five_head_sample_threshold_gap":
            source = sample_by_head.get(row.get("head"), {})
            fail_if(as_int(row.get("current_label_rows")) != as_int(source.get("current_label_rows")), failures, "sample_gap_current_label_rows_bound", {"index": idx, "observed": row.get("current_label_rows")}, source.get("current_label_rows"))
            fail_if(as_int(row.get("missing_label_rows_to_minimum")) != as_int(source.get("missing_label_rows_to_minimum")), failures, "sample_gap_missing_labels_bound", {"index": idx, "observed": row.get("missing_label_rows_to_minimum")}, source.get("missing_label_rows_to_minimum"))
            fail_if(as_int(row.get("missing_replicates_to_minimum")) != as_int(source.get("missing_replicates_to_minimum")), failures, "sample_gap_missing_replicates_bound", {"index": idx, "observed": row.get("missing_replicates_to_minimum")}, source.get("missing_replicates_to_minimum"))
            fail_if(as_int(row.get("missing_groups_to_minimum")) != as_int(source.get("missing_groups_to_minimum")), failures, "sample_gap_missing_groups_bound", {"index": idx, "observed": row.get("missing_groups_to_minimum")}, source.get("missing_groups_to_minimum"))
        if gap_type == "five_head_training_execution_summary":
            fail_if(row.get("training_execution_allowed") is not False, failures, "summary_training_execution_allowed_false", row.get("training_execution_allowed"), False)
            fail_if(as_int(row.get("ready_head_count")) != as_int(execution.get("ready_head_count")), failures, "summary_ready_head_count_bound", row.get("ready_head_count"), execution.get("ready_head_count"))
            fail_if(as_int(row.get("training_import_eligible_rows")) != as_int(training_label.get("training_import_eligible_rows")), failures, "summary_training_import_eligible_rows_bound", row.get("training_import_eligible_rows"), training_label.get("training_import_eligible_rows"))

    fail_if(seen_types.count("five_head_training_gap_action") != len(gap_actions), failures, "gap_action_audit_type_count", seen_types.count("five_head_training_gap_action"), len(gap_actions))
    fail_if(seen_types.count("five_head_sample_threshold_gap") != len(sample_rows), failures, "sample_gap_audit_type_count", seen_types.count("five_head_sample_threshold_gap"), len(sample_rows))
    fail_if(seen_types.count("five_head_training_execution_summary") != 1, failures, "summary_audit_type_count", seen_types.count("five_head_training_execution_summary"), 1)

    for field in ("training_execution_allowed", "training_import_allowed", "safe_for_training_import", "safe_for_model_claim", "release_ready", "production_execution_allowed"):
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "gap_action_rows": len(gap_actions),
        "sample_gap_rows": len(sample_rows),
        "ready_head_count": execution.get("ready_head_count"),
        "total_head_training_rows": execution.get("total_head_training_rows"),
        "training_import_eligible_rows": training_label.get("training_import_eligible_rows"),
        "missing_label_rows_total": sample_report.get("missing_label_rows_total"),
        "missing_replicates_total": sample_report.get("missing_replicates_total"),
        "missing_groups_total": sample_report.get("missing_groups_total"),
        "failures": failures,
        "training_execution_allowed": False,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Validation only. P29 five-head training gaps remain blocking and do not authorize training, model claims, release, or production execution.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "audit_rows": validation["audit_rows"],
        "ready_head_count": validation["ready_head_count"],
        "training_execution_allowed": False,
        "failures": len(failures),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
