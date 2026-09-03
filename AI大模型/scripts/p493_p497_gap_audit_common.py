#!/usr/bin/env python3
"""Shared builders/validators for P493-P497 fail-closed gap audits."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_optional_json(path: Path | None) -> dict[str, Any]:
    return load_json(path) if path else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def base(config: dict[str, Any], audit_id: str, gap_type: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": config["source_report_rel"],
        "source_jsonl": config.get("source_jsonl_rel"),
        "source_validation_report": config.get("source_validation_rel"),
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "completion_ready": False,
        "policy": config["row_policy"],
    }


def item_value(item: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    for key in keys:
        if key in item:
            return item.get(key)
    return default


def configured_rows(config: dict[str, Any], source_report: dict[str, Any]) -> list[dict[str, Any]]:
    source_jsonl = config.get("source_jsonl")
    if source_jsonl:
        return [row for row in load_jsonl(source_jsonl) if isinstance(row, dict)]
    if config["id"] == "p501":
        return [row for row in source_report.get("rows") or [] if isinstance(row, dict)]
    if config["id"] == "p497":
        return []
    return []


def build_audit(config: dict[str, Any]) -> int:
    source_report = load_json(config["source_report"])
    source_validation = load_optional_json(config.get("source_validation"))
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    source_rows = configured_rows(config, source_report)
    rows: list[dict[str, Any]] = []

    for item in source_rows:
        item_id = item_value(item, config["item_id_keys"], "unknown")
        rows.append(base(
            config,
            f"{config['id']}-{config['slug']}::{item_id}",
            config["item_gap_type"],
            {key: item.get(key) for key in config["item_state_keys"]},
            config["item_blocker"],
        ) | {
            config["item_id_name"]: item_id,
            "source_status": item_value(item, config.get("status_keys", [])),
            "source_completion_ready": item.get("completion_ready"),
            "source_release_ready": item.get("release_ready"),
            "requires_human_input": item.get("requires_human_input"),
        })

    metrics = config["metric_fn"](source_report, source_validation, source_rows)
    rows.append(base(
        config,
        f"{config['id']}-{config['slug']}-summary",
        config["summary_gap_type"],
        {
            "source_report_metrics": {key: source_report.get(key) for key in config["report_metric_keys"]},
            "source_validation_metrics": {key: source_validation.get(key) for key in config["validation_metric_keys"]},
            "local_release_ready": local_release.get("release_ready"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        config["summary_blocker"],
    ) | metrics | {"summary_row": True})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "summary_audit_rows": 1,
        "source_report": config["source_report_rel"],
        "source_jsonl": config.get("source_jsonl_rel"),
        "source_validation_report": config.get("source_validation_rel"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "audit_jsonl": rel(config["out_jsonl"]),
        "policy": config["report_policy"],
    } | metrics | {field: False for field in FALSE_FIELDS if field != "completion_ready"}
    report["completion_ready"] = False
    write_jsonl(config["out_jsonl"], rows)
    write_json(config["out_report"], report)
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "summary_audit_rows": report["summary_audit_rows"],
        "primary_rows": metrics.get(config["primary_count_key"]),
        "blocked_or_open_rows": metrics.get(config["blocked_count_key"]),
        "output": str(config["out_report"]),
    }, ensure_ascii=False))
    return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_audit(config: dict[str, Any]) -> int:
    source_report = load_json(config["source_report"])
    source_validation = load_optional_json(config.get("source_validation"))
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    source_rows = configured_rows(config, source_report)
    audit_rows = load_jsonl(config["out_jsonl"])
    report = load_json(config["out_report"])
    metrics = config["metric_fn"](source_report, source_validation, source_rows)
    expected_rows = len(source_rows) + 1
    if config.get("summary_only"):
        expected_rows = 1
    failures: list[dict[str, Any]] = []

    fail_if(len(audit_rows) != expected_rows, failures, "audit_rows_expected", len(audit_rows), expected_rows)
    fail_if(report.get("audit_rows") != expected_rows, failures, "report_audit_rows_expected", report.get("audit_rows"), expected_rows)
    fail_if(report.get("summary_audit_rows") != 1, failures, "summary_audit_rows_one", report.get("summary_audit_rows"), 1)
    fail_if(local_release.get("release_ready") is not False, failures, "source_local_release_ready_false", local_release.get("release_ready"), False)
    fail_if(report.get("local_release_ready") is not False, failures, "report_local_release_ready_false", report.get("local_release_ready"), False)
    fail_if(report.get("claims_blocked") != claim_matrix.get("claims_blocked"), failures, "claims_blocked_bound", report.get("claims_blocked"), claim_matrix.get("claims_blocked"))
    for key, expected in metrics.items():
        fail_if(report.get(key) != expected, failures, f"report_{key}_bound", report.get(key), expected)

    config["source_check_fn"](source_report, source_validation, source_rows, failures)
    for idx, row in enumerate(audit_rows):
        fail_if(row.get("gap_type") not in {config["item_gap_type"], config["summary_gap_type"]}, failures, "gap_type_allowed", {"index": idx, "observed": row.get("gap_type")}, "configured gap type")
        for field in FALSE_FIELDS:
            fail_if(row.get(field) is not False, failures, f"row_{field}_false", {"index": idx, "observed": row.get(field)}, False)
    for field in FALSE_FIELDS:
        fail_if(report.get(field) is not False, failures, f"report_{field}_false", report.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "audit_rows": len(audit_rows),
        "summary_audit_rows": 1,
        "failures": failures,
        "policy": config["validation_policy"],
    } | metrics | {field: False for field in FALSE_FIELDS if field != "completion_ready"}
    result["completion_ready"] = False
    write_json(config["out_validation"], result)
    print(json.dumps({
        "success": result["success"],
        "audit_rows": result["audit_rows"],
        "primary_rows": metrics.get(config["primary_count_key"]),
        "blocked_or_open_rows": metrics.get(config["blocked_count_key"]),
        "failures": len(failures),
        "output": str(config["out_validation"]),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


def closeout_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "closeout_audit_rows": len(rows),
        "closeout_rows": report.get("closeout_rows"),
        "awaiting_human_decision_rows": sum(1 for row in rows if row.get("status") == "awaiting_human_decision"),
        "requires_human_input_rows": sum(1 for row in rows if row.get("requires_human_input") is True),
        "source_completion_ready_rows": sum(1 for row in rows if row.get("completion_ready") is True),
        "closeout_ready_rows": report.get("closeout_ready_rows"),
        "total_prepared_packet_rows": report.get("total_prepared_packet_rows"),
        "total_formal_decision_rows": report.get("total_formal_decision_rows"),
        "source_validation_success": validation.get("success"),
    }


def closeout_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("closeout_rows") != len(rows), failures, "source_closeout_rows_bound", report.get("closeout_rows"), len(rows))
    fail_if(report.get("awaiting_human_decision_rows") != len(rows), failures, "source_awaiting_all_rows", report.get("awaiting_human_decision_rows"), len(rows))
    fail_if(report.get("completion_ready_rows") != 0, failures, "source_completion_ready_zero", report.get("completion_ready_rows"), 0)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("completion_ready_rows") != 0, failures, "source_validation_completion_ready_zero", validation.get("completion_ready_rows"), 0)


def closeout_current_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "closeout_current_boundary_audit_rows": 1,
        "closeout_current_rows": report.get("closeout_rows"),
        "closeout_current_awaiting_human_decision_rows": report.get("awaiting_human_decision_rows"),
        "closeout_current_completion_ready_rows": report.get("completion_ready_rows"),
        "closeout_current_validation_success": report.get("success"),
        "closeout_current_failure_count": len(report.get("failures") or []),
    }


def closeout_current_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("closeout_rows") != report.get("awaiting_human_decision_rows"), failures, "source_all_closeouts_await_human_decision", {"closeout_rows": report.get("closeout_rows"), "awaiting": report.get("awaiting_human_decision_rows")}, "equal")
    fail_if(report.get("completion_ready_rows") != 0, failures, "source_completion_ready_zero", report.get("completion_ready_rows"), 0)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)


def receipt_manifest_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "receipt_rows": report.get("receipt_rows"),
        "open_blocked_receipt_rows": report.get("open_blocked_receipt_rows"),
        "validated_receipt_rows": report.get("validated_receipt_rows"),
        "invalid_receipt_rows": report.get("invalid_receipt_rows"),
        "source_completion_ready_items": report.get("completion_ready_items"),
        "source_target_rows_met_items": report.get("target_rows_met_items"),
        "observed_decision_input_rows": report.get("observed_decision_input_rows"),
        "source_validation_success": report.get("success"),
    }


def receipt_manifest_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(report.get("open_blocked_receipt_rows") != report.get("receipt_rows"), failures, "source_all_receipts_open_blocked", report.get("open_blocked_receipt_rows"), report.get("receipt_rows"))
    fail_if(report.get("completion_ready_items") != 0, failures, "source_completion_ready_zero", report.get("completion_ready_items"), 0)
    fail_if(report.get("target_rows_met_items") != 0, failures, "source_target_rows_met_zero", report.get("target_rows_met_items"), 0)


def receipt_manifest_current_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "receipt_manifest_current_boundary_audit_rows": 1,
        "receipt_manifest_current_receipt_rows": report.get("receipt_rows"),
        "receipt_manifest_current_open_blocked_receipt_rows": report.get("open_blocked_receipt_rows"),
        "receipt_manifest_current_validated_receipt_rows": report.get("validated_receipt_rows"),
        "receipt_manifest_current_invalid_receipt_rows": report.get("invalid_receipt_rows"),
        "receipt_manifest_current_completion_ready_items": report.get("completion_ready_items"),
        "receipt_manifest_current_target_rows_met_items": report.get("target_rows_met_items"),
        "receipt_manifest_current_observed_decision_input_rows": report.get("observed_decision_input_rows"),
        "receipt_manifest_current_success": report.get("success"),
        "receipt_manifest_current_release_ready": report.get("release_ready"),
    }


def receipt_manifest_current_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    receipt_manifest_checks(report, validation, rows, failures)
    fail_if(report.get("validated_receipt_rows") != report.get("receipt_rows"), failures, "source_validated_receipts_bound", report.get("validated_receipt_rows"), report.get("receipt_rows"))
    fail_if(report.get("invalid_receipt_rows") != 0, failures, "source_invalid_receipts_zero", report.get("invalid_receipt_rows"), 0)
    fail_if(report.get("observed_decision_input_rows") != report.get("receipt_rows"), failures, "source_decision_inputs_observed_only", report.get("observed_decision_input_rows"), report.get("receipt_rows"))


def ready_receipt_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "receipt_audit_rows": len(rows),
        "receipt_rows": report.get("receipt_rows"),
        "valid_receipt_rows": validation.get("valid_receipt_rows"),
        "invalid_receipt_rows": validation.get("invalid_receipt_rows"),
        "source_completion_ready_rows": sum(1 for row in rows if row.get("completion_ready") is True),
        "verification_passed_workstreams": report.get("verification_passed_workstreams"),
        "blocked_workstreams_not_executed": report.get("blocked_workstreams_not_executed"),
        "source_success": report.get("success"),
        "source_validation_success": validation.get("success"),
    }


def ready_receipt_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("receipt_rows") != len(rows), failures, "source_receipt_rows_bound", report.get("receipt_rows"), len(rows))
    fail_if(validation.get("valid_receipt_rows") != len(rows), failures, "source_valid_receipt_rows_bound", validation.get("valid_receipt_rows"), len(rows))
    fail_if(validation.get("invalid_receipt_rows") != 0, failures, "source_invalid_receipt_rows_zero", validation.get("invalid_receipt_rows"), 0)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)
    fail_if(any(row.get("completion_ready") is True for row in rows), failures, "source_completion_ready_rows_zero", "nonzero", 0)


def ready_receipt_current_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = {
        "ready_receipt_current_boundary_audit_rows": 1,
        "ready_receipt_current_receipt_rows": report.get("receipt_rows"),
        "ready_receipt_current_valid_receipt_rows": validation.get("valid_receipt_rows"),
        "ready_receipt_current_invalid_receipt_rows": validation.get("invalid_receipt_rows"),
        "ready_receipt_current_board_blocked_workstreams": report.get("board_blocked_workstreams"),
        "ready_receipt_current_blocked_workstreams_not_executed": report.get("blocked_workstreams_not_executed"),
        "ready_receipt_current_validation_success": validation.get("success"),
        "ready_receipt_current_release_ready": validation.get("release_ready"),
        "ready_receipt_current_safe_for_model_claim": validation.get("safe_for_model_claim"),
    }
    if report.get("safe_for_training_import") is not None:
        metrics["ready_receipt_current_safe_for_training_import"] = report.get("safe_for_training_import")
    return metrics


def ready_receipt_current_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("receipt_rows") != validation.get("expected_receipt_rows"), failures, "source_receipt_rows_bound", report.get("receipt_rows"), validation.get("expected_receipt_rows"))
    fail_if(validation.get("valid_receipt_rows") != report.get("receipt_rows"), failures, "source_valid_receipt_rows_bound", validation.get("valid_receipt_rows"), report.get("receipt_rows"))
    fail_if(validation.get("invalid_receipt_rows") != 0, failures, "source_invalid_receipt_rows_zero", validation.get("invalid_receipt_rows"), 0)
    fail_if(report.get("blocked_workstreams_not_executed") is not True, failures, "source_blocked_workstreams_not_executed_true", report.get("blocked_workstreams_not_executed"), True)
    fail_if(validation.get("blocked_workstreams_not_executed") is not True, failures, "source_validation_blocked_workstreams_not_executed_true", validation.get("blocked_workstreams_not_executed"), True)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)
    if report.get("safe_for_training_import") is not None:
        fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
        fail_if(validation.get("safe_for_training_import") is not False, failures, "source_validation_safe_for_training_import_false", validation.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)


def docs_sync_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "target_rows": report.get("target_rows"),
        "stale_rows": report.get("stale_rows"),
        "changed_rows": report.get("changed_rows"),
        "provenance_rows": validation.get("provenance_rows"),
        "semantic_provenance_rows": validation.get("semantic_provenance_rows"),
        "source_success": report.get("success"),
        "source_validation_success": validation.get("success"),
        "receipt_atomic_commit": report.get("receipt_atomic_commit"),
    }


def docs_sync_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(validation.get("failure_count") != 0, failures, "source_validation_failure_count_zero", validation.get("failure_count"), 0)


def pipeline_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "safe_pipeline_terminal_deferred": os.environ.get("KWB_DEFER_SAFE_PIPELINE_TERMINAL") == "1",
        "pipeline_source_success": report.get("success"),
        "pipeline_steps_run": report.get("steps_run"),
        "pipeline_failed_steps": report.get("failed_steps"),
        "pipeline_failure_count": report.get("failure_count"),
        "pipeline_receipt_atomic_commit": report.get("receipt_atomic_commit"),
        "current_receipt_command_rows": validation.get("command_rows"),
        "current_receipt_step_rows": validation.get("step_rows"),
        "current_receipt_failure_count": validation.get("failure_count"),
        "current_receipt_success": validation.get("success"),
        "current_receipt_release_ready": validation.get("release_ready"),
        "pipeline_safe_for_model_claim": report.get("safe_for_model_claim"),
        "pipeline_release_ready": report.get("release_ready"),
    }


def pipeline_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    terminal_deferred = os.environ.get("KWB_DEFER_SAFE_PIPELINE_TERMINAL") == "1"
    if not terminal_deferred:
        fail_if(report.get("success") is not True, failures, "source_pipeline_success_true", report.get("success"), True)
        fail_if(report.get("failed_steps") != 0, failures, "source_pipeline_failed_steps_zero", report.get("failed_steps"), 0)
        fail_if(report.get("failure_count") != 0, failures, "source_pipeline_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("receipt_atomic_commit") is not True, failures, "source_pipeline_receipt_atomic_commit_true", report.get("receipt_atomic_commit"), True)
    if not terminal_deferred:
        fail_if(validation.get("success") is not True, failures, "source_current_receipt_success_true", validation.get("success"), True)
        fail_if(validation.get("failure_count") != 0, failures, "source_current_receipt_failure_count_zero", validation.get("failure_count"), 0)
    fail_if(report.get("release_ready") is not False, failures, "source_pipeline_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_current_receipt_release_ready_false", validation.get("release_ready"), False)


def release_consistency_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "semantic_input_rows": report.get("semantic_input_rows"),
        "source_failure_count": report.get("failure_count"),
        "source_success": report.get("success"),
        "current_atomic_commit": report.get("current_atomic_commit"),
        "safe_pipeline_terminal_deferred": report.get("safe_pipeline_terminal_deferred"),
        "source_release_ready": report.get("release_ready"),
    }


def release_consistency_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(report.get("current_atomic_commit") is not True, failures, "source_current_atomic_commit_true", report.get("current_atomic_commit"), True)


def stage25_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "command_rows": report.get("command_rows"),
        "source_failure_count": report.get("failure_count"),
        "source_success": report.get("success"),
        "source_release_ready": report.get("release_ready"),
        "receipt_safe_for_model_claim": report.get("safe_for_model_claim"),
    }


def stage25_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)


def promotion_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "promotion_audit_rows": len(rows),
        "source_audit_rows": report.get("audit_rows"),
        "receipt_valid_rows": report.get("receipt_valid_rows"),
        "local_artifact_completion_rows": report.get("local_artifact_completion_rows"),
        "verified_blocked_rows": report.get("verified_blocked_rows"),
        "automatic_promotion_rows": report.get("automatic_promotion_rows"),
        "workstream_completion_ready_rows": report.get("workstream_completion_ready_rows"),
        "execution_ready_rows": report.get("execution_ready_rows"),
        "safe_for_training_import_rows": report.get("safe_for_training_import_rows"),
        "safe_for_model_claim_rows": report.get("safe_for_model_claim_rows"),
        "customer_delivery_ready_rows": report.get("customer_delivery_ready_rows"),
        "release_ready_rows": report.get("release_ready_rows"),
        "selected_variant_rows": report.get("selected_variant_rows"),
        "source_validation_success": validation.get("success"),
    }


def promotion_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not None and validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("audit_rows") != validation.get("audit_rows"), failures, "source_audit_rows_bound", report.get("audit_rows"), validation.get("audit_rows"))
    fail_if(report.get("automatic_promotion_rows") != 0, failures, "source_automatic_promotion_zero", report.get("automatic_promotion_rows"), 0)
    for field in ("workstream_completion_ready_rows", "execution_ready_rows", "safe_for_training_import_rows", "safe_for_model_claim_rows", "customer_delivery_ready_rows", "release_ready_rows", "selected_variant_rows"):
        fail_if(report.get(field) != 0, failures, f"source_{field}_zero", report.get(field), 0)


def failure_count(report: dict[str, Any]) -> int | None:
    explicit = report.get("failure_count")
    if explicit is not None:
        return int(explicit)
    failures = report.get("failures")
    if isinstance(failures, list):
        return len(failures)
    return None


def guard_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "guard_link_audit_rows": 1,
        "guard_link_count": report.get("guard_link_count"),
        "current_guard_link_count": validation.get("guard_link_count"),
        "source_failure_count": failure_count(report),
        "current_failure_count": failure_count(validation),
        "source_success": report.get("success"),
        "current_success": validation.get("success"),
        "source_release_ready": report.get("release_ready"),
        "current_release_ready": validation.get("release_ready"),
    }


def guard_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(validation.get("success") is not True, failures, "current_success_true", validation.get("success"), True)
    fail_if(failure_count(report) != 0, failures, "source_failure_count_zero", failure_count(report), 0)
    fail_if(failure_count(validation) != 0, failures, "current_failure_count_zero", failure_count(validation), 0)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("release_ready") is not False, failures, "current_release_ready_false", validation.get("release_ready"), False)
    fail_if(report.get("guard_link_count") != validation.get("guard_link_count"), failures, "guard_link_count_bound", report.get("guard_link_count"), validation.get("guard_link_count"))


def regression_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "regression_audit_rows": 1,
        "source_case_rows": report.get("case_rows", report.get("case_count")),
        "source_passed_rows": report.get("passed_rows", report.get("passed_case_count")),
        "source_failed_rows": report.get("failed_rows", report.get("failed_case_count")),
        "source_failure_count": failure_count(report),
        "source_real_inputs_mutated": report.get("real_inputs_mutated"),
        "source_isolated_fixture": report.get("isolated_fixture"),
        "source_success": report.get("success"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def regression_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    case_rows = report.get("case_rows", report.get("case_count"))
    passed_rows = report.get("passed_rows", report.get("passed_case_count"))
    failed_rows = report.get("failed_rows", report.get("failed_case_count"))
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    if case_rows is not None and passed_rows is not None and failed_rows is not None:
        fail_if(passed_rows + failed_rows != case_rows, failures, "source_case_partition_exact", {"case_rows": case_rows, "passed_rows": passed_rows, "failed_rows": failed_rows}, "passed + failed = case rows")
        fail_if(failed_rows != 0, failures, "source_failed_rows_zero", failed_rows, 0)
    fail_if(failure_count(report) not in (None, 0), failures, "source_failure_count_zero", failure_count(report), 0)
    fail_if(report.get("real_inputs_mutated") is not False, failures, "source_real_inputs_unchanged", report.get("real_inputs_mutated"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    if report.get("isolated_fixture") is not None:
        fail_if(report.get("isolated_fixture") is not True, failures, "source_isolated_fixture_true", report.get("isolated_fixture"), True)


def policy_receipt_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "policy_receipt_audit_rows": 1,
        "source_failure_count": failure_count(report),
        "source_success": report.get("success"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def policy_receipt_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(failure_count(report) != 0, failures, "source_failure_count_zero", failure_count(report), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def stage25_contract_policy_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "policy_audit_rows": 1,
        "source_contract_module_path": report.get("contract_module_path"),
        "source_contract_module_sha256": report.get("contract_module_sha256"),
        "source_expected_contract_version": report.get("expected_contract_version"),
        "source_expected_contract_sha256": report.get("expected_contract_sha256"),
        "source_failure_count": report.get("failure_count"),
        "source_success": report.get("success"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
        "source_regression_case_rows": validation.get("case_rows"),
        "source_regression_passed_rows": validation.get("passed_rows"),
        "source_regression_failed_rows": validation.get("failed_rows"),
        "source_regression_success": validation.get("success"),
    }


def stage25_contract_policy_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("success") is not True, failures, "source_regression_success_true", validation.get("success"), True)
    fail_if(validation.get("failed_rows") != 0, failures, "source_regression_failed_rows_zero", validation.get("failed_rows"), 0)
    fail_if(validation.get("passed_rows") != validation.get("case_rows"), failures, "source_regression_case_partition_exact", {"passed_rows": validation.get("passed_rows"), "case_rows": validation.get("case_rows")}, "passed = case rows")
    fail_if(report.get("contract_module_path") != str((AI_ROOT / "scripts" / "stage25_operator_docs_sync_contract.py").resolve()), failures, "source_contract_module_path_exact", report.get("contract_module_path"), str((AI_ROOT / "scripts" / "stage25_operator_docs_sync_contract.py").resolve()))
    fail_if(report.get("contract_module_sha256") != "2f754c5865ddcbfa824f4f1e8d61f919f6f08bda998f15e68c0cd8d8c3bcc6fe", failures, "source_contract_module_sha256_exact", report.get("contract_module_sha256"), "2f754c5865ddcbfa824f4f1e8d61f919f6f08bda998f15e68c0cd8d8c3bcc6fe")
    fail_if(report.get("expected_contract_version") != "stage25-operator-docs-sync-v4", failures, "source_expected_contract_version_exact", report.get("expected_contract_version"), "stage25-operator-docs-sync-v4")
    fail_if(report.get("expected_contract_sha256") != "5bd2721fd12b10d35394d789a8eebea6debb5bc46d9a5a02e18e6dca19bd2cc2", failures, "source_expected_contract_sha256_exact", report.get("expected_contract_sha256"), "5bd2721fd12b10d35394d789a8eebea6debb5bc46d9a5a02e18e6dca19bd2cc2")


def stage25_dynamic_current_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "current_validation_audit_rows": 1,
        "source_case_count": report.get("case_count"),
        "source_passed_case_count": report.get("passed_case_count"),
        "source_failed_case_count": report.get("failed_case_count"),
        "source_failure_count": report.get("failure_count"),
        "source_success": report.get("success"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
        "source_atomic_commit": report.get("atomic_commit"),
        "source_lock_acquired": report.get("lock_acquired"),
    }


def stage25_dynamic_current_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("case_count") != report.get("passed_case_count"), failures, "source_case_partition_exact", {"case_count": report.get("case_count"), "passed_case_count": report.get("passed_case_count")}, "passed = case count")
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(report.get("atomic_commit") is not True, failures, "source_atomic_commit_true", report.get("atomic_commit"), True)
    fail_if(report.get("lock_acquired") is not True, failures, "source_lock_acquired_true", report.get("lock_acquired"), True)


def stage25_blocker_cross_binding_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "blocker_cross_binding_audit_rows": 1,
        "source_success": report.get("success"),
        "source_failure_count": failure_count(report),
        "source_expected_blocker_rows": report.get("expected_blocker_rows"),
        "source_shared_blocker_rows": report.get("shared_blocker_rows"),
        "source_closure_blocker_rows": report.get("closure_blocker_rows"),
        "source_activation_blocker_rows": report.get("activation_blocker_rows"),
        "source_coverage_blocker_rows": report.get("coverage_blocker_rows"),
        "source_blocked_status_rows": report.get("blocked_status_rows"),
        "source_coverage_complete_rows": report.get("coverage_complete_rows"),
        "source_closure_completion_ready_rows": report.get("closure_completion_ready_rows"),
        "source_activation_completion_ready_rows": report.get("activation_completion_ready_rows"),
        "source_external_sqlite_mutated": report.get("external_sqlite_mutated"),
        "source_formal_decision_rows_written": report.get("formal_decision_rows_written"),
        "source_apply_executed": report.get("apply_executed"),
        "source_export_safe_released": report.get("export_safe_released"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def stage25_blocker_cross_binding_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    expected = report.get("expected_blocker_rows")
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("cross_binding_valid") is not True, failures, "source_cross_binding_valid_true", report.get("cross_binding_valid"), True)
    fail_if(failure_count(report) != 0, failures, "source_failure_count_zero", failure_count(report), 0)
    for key in ("shared_blocker_rows", "closure_blocker_rows", "activation_blocker_rows", "coverage_blocker_rows", "blocked_status_rows", "exact_current_receipt_rows", "exact_closure_condition_rows"):
        fail_if(report.get(key) != expected, failures, f"source_{key}_bound", report.get(key), expected)
    fail_if(report.get("coverage_complete_rows") != expected, failures, "source_coverage_complete_rows_bound", report.get("coverage_complete_rows"), expected)
    fail_if(report.get("closure_completion_ready_rows") != 0, failures, "source_closure_completion_ready_rows_zero", report.get("closure_completion_ready_rows"), 0)
    fail_if(report.get("activation_completion_ready_rows") != 0, failures, "source_activation_completion_ready_rows_zero", report.get("activation_completion_ready_rows"), 0)
    fail_if(len(report.get("uncovered_blockers") or []) != 0, failures, "source_uncovered_blockers_zero", len(report.get("uncovered_blockers") or []), 0)
    fail_if(report.get("external_sqlite_mutated") is not False, failures, "source_external_sqlite_mutated_false", report.get("external_sqlite_mutated"), False)
    fail_if(report.get("formal_decision_rows_written") != 0, failures, "source_formal_decision_rows_written_zero", report.get("formal_decision_rows_written"), 0)
    fail_if(report.get("apply_executed") is not False, failures, "source_apply_executed_false", report.get("apply_executed"), False)
    fail_if(report.get("export_safe_released") is not False, failures, "source_export_safe_released_false", report.get("export_safe_released"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def execution_receipt_gate_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "execution_receipt_gate_audit_rows": 1,
        "receipt_rows": report.get("receipt_rows"),
        "executed_action_count": report.get("executed_action_count"),
        "executed_passed_receipt_rows": report.get("executed_passed_receipt_rows"),
        "executed_failed_receipt_rows": report.get("executed_failed_receipt_rows"),
        "source_missing_receipt_action_count": len(report.get("missing_receipt_action_ids") or []),
        "source_unexpected_receipt_action_count": len(report.get("unexpected_receipt_action_ids") or []),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": failure_count(validation),
        "source_validation_missing_receipt_action_count": validation.get("missing_receipt_action_count"),
        "source_validation_unexpected_receipt_action_count": validation.get("unexpected_receipt_action_count"),
        "source_execution_wave_atomic_pair_valid": report.get("execution_wave_atomic_pair_valid"),
        "source_safe_for_execution_claim": report.get("safe_for_execution_claim"),
        "source_safe_for_training_import": report.get("safe_for_training_import"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def execution_receipt_gate_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("lock_acquired") is not True, failures, "source_lock_acquired_true", report.get("lock_acquired"), True)
    fail_if(report.get("atomic_commit") is not True, failures, "source_atomic_commit_true", report.get("atomic_commit"), True)
    fail_if(report.get("execution_wave_atomic_pair_valid") is not True, failures, "source_execution_wave_atomic_pair_valid_true", report.get("execution_wave_atomic_pair_valid"), True)
    fail_if(report.get("receipt_rows") != report.get("executed_action_count"), failures, "source_receipt_rows_match_executed_actions", {"receipt_rows": report.get("receipt_rows"), "executed_action_count": report.get("executed_action_count")}, "receipt rows = executed actions")
    fail_if(report.get("executed_failed_receipt_rows") != 0, failures, "source_executed_failed_receipt_rows_zero", report.get("executed_failed_receipt_rows"), 0)
    fail_if(len(report.get("missing_receipt_action_ids") or []) != 0, failures, "source_missing_receipt_actions_zero", len(report.get("missing_receipt_action_ids") or []), 0)
    fail_if(len(report.get("unexpected_receipt_action_ids") or []) != 0, failures, "source_unexpected_receipt_actions_zero", len(report.get("unexpected_receipt_action_ids") or []), 0)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(failure_count(validation) != 0, failures, "source_validation_failure_count_zero", failure_count(validation), 0)
    fail_if(validation.get("lock_acquired") is not True, failures, "source_validation_lock_acquired_true", validation.get("lock_acquired"), True)
    fail_if(validation.get("atomic_commit") is not True, failures, "source_validation_atomic_commit_true", validation.get("atomic_commit"), True)
    fail_if(validation.get("receipt_rows") != report.get("receipt_rows"), failures, "source_validation_receipt_rows_bound", validation.get("receipt_rows"), report.get("receipt_rows"))
    fail_if(validation.get("executed_failed_receipt_rows") != 0, failures, "source_validation_executed_failed_receipt_rows_zero", validation.get("executed_failed_receipt_rows"), 0)
    fail_if(validation.get("missing_receipt_action_count") != 0, failures, "source_validation_missing_receipt_action_count_zero", validation.get("missing_receipt_action_count"), 0)
    fail_if(validation.get("unexpected_receipt_action_count") != 0, failures, "source_validation_unexpected_receipt_action_count_zero", validation.get("unexpected_receipt_action_count"), 0)
    for field in ("safe_for_execution_claim", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def execution_receipt_lineage_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "execution_receipt_lineage_audit_rows": 1,
        "source_success": report.get("success"),
        "source_failure_count": failure_count(report),
        "receipt_rows": report.get("receipt_rows"),
        "wave_action_rows": report.get("wave_action_rows"),
        "receipt_action_rows": report.get("receipt_action_rows"),
        "unique_receipt_ids": report.get("unique_receipt_ids"),
        "executed_passed_rows": report.get("executed_passed_rows"),
        "executed_failed_rows": report.get("executed_failed_rows"),
        "source_safe_for_training_import": report.get("safe_for_training_import"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def execution_receipt_lineage_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(failure_count(report) != 0, failures, "source_failure_count_zero", failure_count(report), 0)
    fail_if(report.get("lock_acquired") is not True, failures, "source_lock_acquired_true", report.get("lock_acquired"), True)
    fail_if(report.get("atomic_commit") is not True, failures, "source_atomic_commit_true", report.get("atomic_commit"), True)
    for key in ("wave_action_rows", "receipt_action_rows", "unique_receipt_ids"):
        fail_if(report.get(key) != report.get("receipt_rows"), failures, f"source_{key}_matches_receipt_rows", report.get(key), report.get("receipt_rows"))
    fail_if(report.get("executed_failed_rows") != 0, failures, "source_executed_failed_rows_zero", report.get("executed_failed_rows"), 0)
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def atomic_policy_receipt_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "atomic_policy_receipt_audit_rows": 1,
        "source_success": report.get("success"),
        "source_failure_count": failure_count(report),
        "source_lock_acquired": report.get("lock_acquired"),
        "source_atomic_commit": report.get("atomic_commit"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def atomic_policy_receipt_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(failure_count(report) != 0, failures, "source_failure_count_zero", failure_count(report), 0)
    fail_if(report.get("lock_acquired") is not True, failures, "source_lock_acquired_true", report.get("lock_acquired"), True)
    fail_if(report.get("atomic_commit") is not True, failures, "source_atomic_commit_true", report.get("atomic_commit"), True)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def safety_regression_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "safety_regression_audit_rows": 1,
        "source_case_rows": report.get("case_rows"),
        "source_positive_cases": report.get("positive_cases"),
        "source_negative_cases": report.get("negative_cases"),
        "source_expected_rejected_negative_cases": report.get("expected_rejected_negative_cases"),
        "source_actual_rejected_negative_cases": report.get("actual_rejected_negative_cases"),
        "source_failed_regression_cases": report.get("failed_regression_cases"),
        "source_success": report.get("success"),
        "source_safe_for_execution_claim": report.get("safe_for_execution_claim"),
        "source_safe_for_training_import": report.get("safe_for_training_import"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def safety_regression_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("positive_cases", 0) + report.get("negative_cases", 0) != report.get("case_rows"), failures, "source_case_partition_exact", {"case_rows": report.get("case_rows"), "positive_cases": report.get("positive_cases"), "negative_cases": report.get("negative_cases")}, "positive + negative = case rows")
    fail_if(report.get("actual_rejected_negative_cases") != report.get("expected_rejected_negative_cases"), failures, "source_rejected_negative_cases_exact", report.get("actual_rejected_negative_cases"), report.get("expected_rejected_negative_cases"))
    fail_if(report.get("failed_regression_cases") != 0, failures, "source_failed_regression_cases_zero", report.get("failed_regression_cases"), 0)
    for field in ("safe_for_execution_claim", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def execution_eligibility_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "execution_eligibility_audit_rows": 1,
        "action_rows": report.get("action_rows"),
        "current_execution_allowed_rows": report.get("current_execution_allowed_rows"),
        "requires_user_confirmation_rows": report.get("requires_user_confirmation_rows"),
        "formal_decision_required_rows": report.get("formal_decision_required_rows"),
        "receipt_required_rows": report.get("receipt_required_rows"),
        "executed_in_current_trace_rows": report.get("executed_in_current_trace_rows"),
        "receipt_present_rows": report.get("receipt_present_rows"),
        "executed_with_receipt_rows": report.get("executed_with_receipt_rows"),
        "executed_passed_rows": report.get("executed_passed_rows"),
        "executed_failed_rows": report.get("executed_failed_rows"),
        "skipped_rows": report.get("skipped_rows"),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": failure_count(validation),
        "source_safe_for_execution_claim": report.get("safe_for_execution_claim"),
        "source_safe_for_training_import": report.get("safe_for_training_import"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def execution_eligibility_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(failure_count(validation) != 0, failures, "source_validation_failure_count_zero", failure_count(validation), 0)
    fail_if(report.get("action_rows") != validation.get("action_rows"), failures, "source_action_rows_bound", report.get("action_rows"), validation.get("action_rows"))
    fail_if(report.get("current_execution_allowed_rows") != validation.get("current_execution_allowed_rows"), failures, "source_current_execution_allowed_rows_bound", report.get("current_execution_allowed_rows"), validation.get("current_execution_allowed_rows"))
    fail_if(report.get("executed_in_current_trace_rows") != validation.get("executed_in_current_trace_rows"), failures, "source_executed_in_current_trace_rows_bound", report.get("executed_in_current_trace_rows"), validation.get("executed_in_current_trace_rows"))
    fail_if(report.get("receipt_present_rows") != validation.get("receipt_present_rows"), failures, "source_receipt_present_rows_bound", report.get("receipt_present_rows"), validation.get("receipt_present_rows"))
    fail_if(report.get("executed_failed_rows") != 0, failures, "source_executed_failed_rows_zero", report.get("executed_failed_rows"), 0)
    fail_if(report.get("receipt_gate_validation_success") is not True, failures, "source_receipt_gate_validation_success_true", report.get("receipt_gate_validation_success"), True)
    fail_if(report.get("receipt_safety_regression_success") is not True, failures, "source_receipt_safety_regression_success_true", report.get("receipt_safety_regression_success"), True)
    fail_if(report.get("receipt_safety_regression_failed_cases") != 0, failures, "source_receipt_safety_regression_failed_cases_zero", report.get("receipt_safety_regression_failed_cases"), 0)
    for field in ("safe_for_execution_claim", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def outcome_dashboard_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "outcome_dashboard_audit_rows": 1,
        "action_rows": report.get("action_rows"),
        "receipt_present_rows": report.get("receipt_present_rows"),
        "executed_passed_rows": report.get("executed_passed_rows"),
        "executed_failed_rows": report.get("executed_failed_rows"),
        "engineering_ready_rows": report.get("engineering_ready_rows"),
        "hard_gate_unlocked_rows": report.get("hard_gate_unlocked_rows"),
        "physics_ddg_ready": report.get("rosetta_pyrosetta_foldx_physics_ddg_ready"),
        "thermompnn_proxy_ready": report.get("thermompnn_proxy_ready"),
        "benchmark_ready_for_model_claim": report.get("benchmark_ready_for_model_claim"),
        "source_validation_success": validation.get("success"),
        "source_validation_action_rows": validation.get("action_rows"),
        "source_safe_for_training_import": report.get("safe_for_training_import"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def outcome_dashboard_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("action_rows") != validation.get("action_rows"), failures, "source_action_rows_bound", report.get("action_rows"), validation.get("action_rows"))
    fail_if(report.get("executed_failed_rows") != 0, failures, "source_executed_failed_rows_zero", report.get("executed_failed_rows"), 0)
    fail_if(report.get("executed_passed_rows") != report.get("receipt_present_rows"), failures, "source_executed_passed_receipts_bound", {"executed_passed_rows": report.get("executed_passed_rows"), "receipt_present_rows": report.get("receipt_present_rows")}, "executed passed rows = receipt rows")
    fail_if(report.get("hard_gate_unlocked_rows", 0) < 0, failures, "source_hard_gate_unlocked_nonnegative", report.get("hard_gate_unlocked_rows"), ">= 0")
    fail_if(report.get("benchmark_ready_for_model_claim") is not False, failures, "source_benchmark_ready_for_model_claim_false", report.get("benchmark_ready_for_model_claim"), False)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def construction_board_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "construction_board_audit_rows": 1,
        "total_workstreams": report.get("total_workstreams"),
        "started_workstreams": report.get("started_workstreams"),
        "blocked_workstreams": report.get("blocked_workstreams", report.get("started_blocked_workstreams")),
        "ready_to_verify_workstreams": report.get("ready_to_verify_workstreams", report.get("started_ready_to_verify_workstreams")),
        "completion_ready_workstreams": report.get("completion_ready_workstreams"),
        "source_validation_success": validation.get("success"),
        "source_validated_workstreams": validation.get("validated_workstreams"),
        "source_validated_packets": validation.get("validated_packets"),
        "source_failed_checks": validation.get("failed_checks"),
    }


def construction_board_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    total = report.get("total_workstreams")
    blocked = report.get("blocked_workstreams", report.get("started_blocked_workstreams"))
    ready = report.get("ready_to_verify_workstreams", report.get("started_ready_to_verify_workstreams"))
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("started_workstreams") != total, failures, "source_started_workstreams_equal_total", report.get("started_workstreams"), total)
    fail_if(validation.get("validated_workstreams") != total, failures, "source_validated_workstreams_equal_total", validation.get("validated_workstreams"), total)
    fail_if(validation.get("validated_packets") != total, failures, "source_validated_packets_equal_total", validation.get("validated_packets"), total)
    fail_if(report.get("completion_ready_workstreams") != 0, failures, "source_completion_ready_workstreams_zero", report.get("completion_ready_workstreams"), 0)
    fail_if(blocked + ready + report.get("completion_ready_workstreams", 0) != total, failures, "source_workstream_partition_exact", {"total": total, "blocked": blocked, "ready": ready, "completion": report.get("completion_ready_workstreams")}, "blocked + ready + completion = total")
    fail_if(validation.get("failed_checks") != 0, failures, "source_failed_checks_zero", validation.get("failed_checks"), 0)


def parallel_receipt_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "parallel_receipt_audit_rows": 1,
        "receipt_rows": report.get("receipt_rows"),
        "validation_passed_rows": report.get("validation_passed_rows"),
        "executed_rows": report.get("executed_rows"),
        "eligibility_changed_rows": report.get("eligibility_changed_rows"),
        "formal_decision_written_rows": report.get("formal_decision_written_rows"),
        "runtime_receipt_written_rows": report.get("runtime_receipt_written_rows"),
        "training_import_written_rows": report.get("training_import_written_rows"),
        "model_or_release_flags_changed_rows": report.get("model_or_release_flags_changed_rows"),
        "source_validation_success": validation.get("success"),
        "source_expected_lane_count": validation.get("expected_lane_count"),
        "source_validation_passed_rows": validation.get("validation_passed_rows"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def parallel_receipt_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("receipt_rows") != validation.get("receipt_rows"), failures, "source_receipt_rows_bound", report.get("receipt_rows"), validation.get("receipt_rows"))
    fail_if(report.get("receipt_rows") != validation.get("expected_lane_count"), failures, "source_receipt_rows_expected_lane_count", report.get("receipt_rows"), validation.get("expected_lane_count"))
    fail_if(report.get("validation_passed_rows") != report.get("receipt_rows"), failures, "source_validation_passed_rows_exact", report.get("validation_passed_rows"), report.get("receipt_rows"))
    fail_if(report.get("executed_rows") != report.get("receipt_rows"), failures, "source_executed_rows_exact", report.get("executed_rows"), report.get("receipt_rows"))
    fail_if(report.get("eligibility_changed_rows") != 0, failures, "source_eligibility_changed_rows_zero", report.get("eligibility_changed_rows"), 0)
    fail_if(report.get("training_import_written_rows") != 0, failures, "source_training_import_written_rows_zero", report.get("training_import_written_rows"), 0)
    fail_if(report.get("model_or_release_flags_changed_rows") != 0, failures, "source_model_or_release_flags_changed_rows_zero", report.get("model_or_release_flags_changed_rows"), 0)
    fail_if(validation.get("eligibility_changed_rows") != 0, failures, "source_validation_eligibility_changed_rows_zero", validation.get("eligibility_changed_rows"), 0)
    fail_if(validation.get("training_import_written_rows") != 0, failures, "source_validation_training_import_written_rows_zero", validation.get("training_import_written_rows"), 0)
    for field in ("safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def freshness_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "freshness_audit_rows": 1,
        "total_receipts": report.get("total_receipts"),
        "fresh_receipts": report.get("fresh_receipts"),
        "stale_receipts": report.get("stale_receipts"),
        "missing_artifacts": report.get("missing_artifacts"),
        "sha256_mismatches": report.get("sha256_mismatches"),
        "sha256_unreadable_artifacts": report.get("sha256_unreadable_artifacts"),
        "artifact_reference_checks": report.get("artifact_reference_checks"),
        "receipts_without_artifact_hash_fields": report.get("receipts_without_artifact_hash_fields"),
        "receipts_with_only_exists_mtime_freshness": len(report.get("receipts_with_only_exists_mtime_freshness") or []),
        "source_success": report.get("success"),
        "source_safe_for_training_import": report.get("safe_for_training_import"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def freshness_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("fresh_receipts") + report.get("stale_receipts") != report.get("total_receipts"), failures, "source_receipt_freshness_partition_exact", {"total": report.get("total_receipts"), "fresh": report.get("fresh_receipts"), "stale": report.get("stale_receipts")}, "fresh + stale = total")
    for key in ("stale_receipts", "missing_artifacts", "sha256_mismatches", "sha256_unreadable_artifacts"):
        fail_if(report.get(key) != 0, failures, f"source_{key}_zero", report.get(key), 0)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def freshness_hash_coverage_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "freshness_hash_coverage_audit_rows": 1,
        "total_receipts": report.get("total_receipts"),
        "receipts_without_artifact_hash_fields": report.get("receipts_without_artifact_hash_fields"),
        "exists_mtime_only_receipts": len(report.get("receipts_with_only_exists_mtime_freshness") or []),
        "artifact_reference_checks": report.get("artifact_reference_checks"),
        "sha256_mismatches": report.get("sha256_mismatches"),
        "sha256_unreadable_artifacts": report.get("sha256_unreadable_artifacts"),
        "missing_artifacts": report.get("missing_artifacts"),
        "source_success": report.get("success"),
        "source_hash_freshness_note": report.get("hash_freshness_note"),
        "source_safe_for_training_import": report.get("safe_for_training_import"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def freshness_hash_coverage_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    total = report.get("total_receipts")
    no_hash = report.get("receipts_without_artifact_hash_fields")
    exists_mtime_only = len(report.get("receipts_with_only_exists_mtime_freshness") or [])
    fail_if(not isinstance(total, int) or total < 0, failures, "source_total_receipts_nonnegative", total, "nonnegative integer")
    fail_if(not isinstance(no_hash, int) or no_hash < 0 or no_hash > total, failures, "source_hash_gap_bounded", no_hash, f"0 <= no_hash <= {total}")
    fail_if(no_hash != exists_mtime_only, failures, "source_hash_gap_matches_exists_mtime_only", no_hash, exists_mtime_only)
    for key in ("missing_artifacts", "sha256_mismatches", "sha256_unreadable_artifacts"):
        fail_if(report.get(key) != 0, failures, f"source_{key}_zero", report.get(key), 0)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def board_claim_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    readiness = report.get("current_readiness") or {}
    return {
        "board_claim_boundary_audit_rows": 1,
        "total_workstreams": report.get("total_workstreams"),
        "started_workstreams": report.get("started_workstreams"),
        "blocked_workstreams": report.get("blocked_workstreams", report.get("started_blocked_workstreams")),
        "ready_to_verify_workstreams": report.get("ready_to_verify_workstreams", report.get("started_ready_to_verify_workstreams")),
        "completion_ready_workstreams": report.get("completion_ready_workstreams"),
        "current_state_is_top_tier": readiness.get("current_state_is_top_tier"),
        "claims_allowed": readiness.get("claims_allowed"),
        "blocked_capabilities_count": len(report.get("blocked_capabilities") or []),
        "source_safe_for_model_claim": readiness.get("safe_for_model_claim"),
        "source_release_ready": readiness.get("release_ready"),
        "source_validation_success": validation.get("success"),
        "source_validation_failed_checks": validation.get("failed_checks"),
    }


def board_claim_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    readiness = report.get("current_readiness") or {}
    total = report.get("total_workstreams")
    blocked = report.get("blocked_workstreams", report.get("started_blocked_workstreams"))
    ready = report.get("ready_to_verify_workstreams", report.get("started_ready_to_verify_workstreams"))
    completion = report.get("completion_ready_workstreams")
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("started_workstreams") != total, failures, "source_started_workstreams_equal_total", report.get("started_workstreams"), total)
    fail_if(completion != 0, failures, "source_completion_ready_workstreams_zero", completion, 0)
    fail_if(blocked + ready + completion != total, failures, "source_workstream_partition_exact", {"total": total, "blocked": blocked, "ready": ready, "completion": completion}, "blocked + ready + completion = total")
    fail_if(readiness.get("safe_for_model_claim") is not False, failures, "source_current_readiness_model_claim_false", readiness.get("safe_for_model_claim"), False)
    fail_if(readiness.get("release_ready") is not False, failures, "source_current_readiness_release_false", readiness.get("release_ready"), False)
    fail_if(validation.get("failed_checks") != 0, failures, "source_failed_checks_zero", validation.get("failed_checks"), 0)


def outcome_formal_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    formal = report.get("formal_counts") or {}
    return {
        "outcome_formal_boundary_audit_rows": 1,
        "action_rows": report.get("action_rows"),
        "hard_gate_unlocked_rows": report.get("hard_gate_unlocked_rows"),
        "numbering_decision_rows": formal.get("numbering_curation_decisions"),
        "structure_decision_rows": formal.get("structure_chain_mapping_decisions"),
        "wet_lab_authorization_rows": formal.get("wet_lab_feedback_authorizations"),
        "strict_repaired_supervised_rows": formal.get("strict_repaired_supervised_rows"),
        "claim_eligible_rows": formal.get("claim_eligible_rows"),
        "benchmark_ready_for_model_claim": report.get("benchmark_ready_for_model_claim"),
        "source_validation_success": validation.get("success"),
        "source_safe_for_training_import": report.get("safe_for_training_import"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def outcome_formal_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    formal = report.get("formal_counts") or {}
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("action_rows") != validation.get("action_rows"), failures, "source_action_rows_bound", report.get("action_rows"), validation.get("action_rows"))
    fail_if(formal.get("strict_repaired_supervised_rows") != 0, failures, "source_strict_repaired_supervised_rows_zero", formal.get("strict_repaired_supervised_rows"), 0)
    fail_if(formal.get("claim_eligible_rows") != 0, failures, "source_claim_eligible_rows_zero", formal.get("claim_eligible_rows"), 0)
    fail_if(report.get("benchmark_ready_for_model_claim") is not False, failures, "source_benchmark_ready_for_model_claim_false", report.get("benchmark_ready_for_model_claim"), False)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def parallel_decision_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "parallel_decision_boundary_audit_rows": 1,
        "receipt_rows": report.get("receipt_rows"),
        "formal_decision_written_rows": report.get("formal_decision_written_rows"),
        "runtime_receipt_written_rows": report.get("runtime_receipt_written_rows"),
        "training_import_written_rows": report.get("training_import_written_rows"),
        "model_or_release_flags_changed_rows": report.get("model_or_release_flags_changed_rows"),
        "eligibility_changed_rows": report.get("eligibility_changed_rows"),
        "source_validation_success": validation.get("success"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def parallel_decision_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("receipt_rows") != validation.get("receipt_rows"), failures, "source_receipt_rows_bound", report.get("receipt_rows"), validation.get("receipt_rows"))
    fail_if(report.get("eligibility_changed_rows") != 0, failures, "source_eligibility_changed_rows_zero", report.get("eligibility_changed_rows"), 0)
    fail_if(report.get("training_import_written_rows") != 0, failures, "source_training_import_written_rows_zero", report.get("training_import_written_rows"), 0)
    fail_if(report.get("model_or_release_flags_changed_rows") != 0, failures, "source_model_or_release_flags_changed_rows_zero", report.get("model_or_release_flags_changed_rows"), 0)
    for field in ("safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def ready_receipt_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ready_receipt_boundary_audit_rows": 1,
        "receipt_rows": report.get("receipt_rows"),
        "valid_receipt_rows": validation.get("valid_receipt_rows"),
        "invalid_receipt_rows": validation.get("invalid_receipt_rows"),
        "board_ready_to_verify_workstreams": report.get("board_ready_to_verify_workstreams"),
        "verification_passed_workstreams": report.get("verification_passed_workstreams"),
        "blocked_workstreams_not_executed": report.get("blocked_workstreams_not_executed"),
        "source_success": report.get("success"),
        "source_validation_success": validation.get("success"),
        "source_safe_for_training_import": report.get("safe_for_training_import", False),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def ready_receipt_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("receipt_rows") != validation.get("expected_receipt_rows"), failures, "source_receipt_rows_expected_bound", report.get("receipt_rows"), validation.get("expected_receipt_rows"))
    fail_if(validation.get("valid_receipt_rows") != report.get("receipt_rows"), failures, "source_valid_receipt_rows_exact", validation.get("valid_receipt_rows"), report.get("receipt_rows"))
    fail_if(validation.get("invalid_receipt_rows") != 0, failures, "source_invalid_receipt_rows_zero", validation.get("invalid_receipt_rows"), 0)
    ready_workstreams = report.get("board_ready_to_verify_workstreams") or []
    fail_if(report.get("verification_passed_workstreams") != len(ready_workstreams), failures, "source_verification_rows_bound", {"verification_passed_workstreams": report.get("verification_passed_workstreams"), "board_ready_to_verify_workstreams": ready_workstreams}, "verification passed = count of board ready-to-verify workstreams")
    fail_if(report.get("blocked_workstreams_not_executed") is not True, failures, "source_blocked_workstreams_not_executed_true", report.get("blocked_workstreams_not_executed"), True)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        report_value = report.get(field, False)
        validation_value = validation.get(field, False)
        fail_if(report_value is not False, failures, f"source_{field}_false", report_value, False)
        fail_if(validation_value is not False, failures, f"source_validation_{field}_false", validation_value, False)


def live_integrity_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "live_integrity_boundary_audit_rows": 1,
        "artifact_rows": report.get("artifact_rows"),
        "strict_verified_rows": report.get("strict_verified_rows"),
        "volatile_existence_only_rows": report.get("volatile_existence_only_rows"),
        "missing_rows": report.get("missing_rows"),
        "unsafe_path_rows": report.get("unsafe_path_rows"),
        "size_mismatch_rows": report.get("size_mismatch_rows"),
        "sha256_mismatch_rows": report.get("sha256_mismatch_rows"),
        "row_mismatch_rows": report.get("row_mismatch_rows"),
        "source_success": report.get("success"),
        "source_failure_count": report.get("failure_count"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
    }


def live_integrity_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("strict_verified_rows") + report.get("volatile_existence_only_rows") != report.get("artifact_rows"), failures, "source_integrity_partition_exact", {"artifact_rows": report.get("artifact_rows"), "strict_verified_rows": report.get("strict_verified_rows"), "volatile_existence_only_rows": report.get("volatile_existence_only_rows")}, "strict + volatile = artifacts")
    for key in ("missing_rows", "unsafe_path_rows", "size_mismatch_rows", "sha256_mismatch_rows", "row_mismatch_rows"):
        fail_if(report.get(key) != 0, failures, f"source_{key}_zero", report.get(key), 0)
    for field in ("safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def release_consistency_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "release_consistency_boundary_audit_rows": 1,
        "artifact_count": report.get("artifact_count"),
        "data_lake_artifact_count": report.get("data_lake_artifact_count"),
        "data_lake_unique_path_rows": report.get("data_lake_unique_path_rows"),
        "missing_artifacts": len(report.get("missing_artifacts") or []),
        "data_lake_duplicate_final_paths": len(report.get("data_lake_duplicate_final_paths") or []),
        "data_lake_unsafe_artifact_paths": len(report.get("data_lake_unsafe_artifact_paths") or []),
        "min_expected_artifact_count": report.get("min_expected_artifact_count"),
        "source_success": report.get("success"),
        "source_failure_count": report.get("failure_count"),
        "source_release_ready": report.get("release_ready"),
        "receipt_atomic_commit": report.get("receipt_atomic_commit"),
        "lock_acquired": report.get("lock_acquired"),
    }


def release_consistency_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("artifact_count") != report.get("data_lake_artifact_count"), failures, "source_artifact_count_bound", report.get("artifact_count"), report.get("data_lake_artifact_count"))
    fail_if(report.get("artifact_count") != report.get("data_lake_unique_path_rows"), failures, "source_unique_path_count_bound", report.get("artifact_count"), report.get("data_lake_unique_path_rows"))
    for key in ("missing_artifacts", "data_lake_duplicate_final_paths", "data_lake_unsafe_artifact_paths"):
        fail_if(len(report.get(key) or []) != 0, failures, f"source_{key}_empty", len(report.get(key) or []), 0)
    fail_if(report.get("receipt_atomic_commit") is not True, failures, "source_receipt_atomic_commit_true", report.get("receipt_atomic_commit"), True)
    fail_if(report.get("lock_acquired") is not True, failures, "source_lock_acquired_true", report.get("lock_acquired"), True)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def numbering_queue_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "numbering_boundary_audit_rows": 1,
        "queue_rows": report.get("queue_rows"),
        "decision_rows": report.get("decision_rows"),
        "open_numbering_rows": report.get("open_numbering_rows"),
        "reviewed_no_conflict_rows": report.get("reviewed_no_conflict_rows"),
        "semantic_conflict_rows": report.get("semantic_conflict_rows"),
        "deep_audit_reject_recommendation_rows": report.get("deep_audit_reject_recommendation_rows"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
    }


def numbering_queue_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("queue_rows") != report.get("open_numbering_rows", 0) + report.get("decision_rows", 0), failures, "source_queue_partition_exact", {"queue_rows": report.get("queue_rows"), "open_numbering_rows": report.get("open_numbering_rows"), "decision_rows": report.get("decision_rows")}, "open + decision = queue")
    fail_if(report.get("deep_audit_reject_recommendation_rows") != report.get("queue_rows"), failures, "source_deep_audit_rows_bound", report.get("deep_audit_reject_recommendation_rows"), report.get("queue_rows"))
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)


def feedback_numeric_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "feedback_boundary_audit_rows": 1,
        "input_rows": report.get("input_rows"),
        "valid_rows": report.get("valid_rows"),
        "invalid_rows": report.get("invalid_rows"),
        "intake_training_eligible_rows": report.get("training_eligible_rows"),
        "qualitative_training_eligible_rows": report.get("qualitative_training_eligible_rows"),
        "numeric_training_eligible_rows": report.get("numeric_training_eligible_rows"),
        "trainability_source_rows": validation.get("source_rows"),
        "trainability_audited_rows": validation.get("audited_rows"),
        "trainability_training_eligible_rows": validation.get("training_eligible_rows"),
        "trainability_manual_review_required_rows": validation.get("manual_review_required_rows"),
        "ready_for_feedback_intake": validation.get("ready_for_feedback_intake"),
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def feedback_numeric_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("valid_rows", 0) + report.get("invalid_rows", 0) != report.get("input_rows"), failures, "source_feedback_input_partition_exact", {"input_rows": report.get("input_rows"), "valid_rows": report.get("valid_rows"), "invalid_rows": report.get("invalid_rows")}, "valid + invalid = input")
    fail_if(report.get("qualitative_training_eligible_rows", 0) + report.get("numeric_training_eligible_rows", 0) != report.get("training_eligible_rows"), failures, "source_feedback_type_partition_exact", {"training_eligible_rows": report.get("training_eligible_rows"), "qualitative_training_eligible_rows": report.get("qualitative_training_eligible_rows"), "numeric_training_eligible_rows": report.get("numeric_training_eligible_rows")}, "qualitative + numeric = eligible")
    fail_if(validation.get("ready_for_feedback_intake") is not False, failures, "source_ready_for_feedback_intake_false", validation.get("ready_for_feedback_intake"), False)
    fail_if(validation.get("training_eligible_rows") != 0, failures, "source_trainability_training_eligible_zero", validation.get("training_eligible_rows"), 0)
    fail_if(validation.get("manual_review_required_rows") != validation.get("audited_rows"), failures, "source_manual_review_all_audited", validation.get("manual_review_required_rows"), validation.get("audited_rows"))


def ddg_readiness_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    backends = report.get("backends") or []
    physics_names = {"rosetta", "pyrosetta", "foldx"}
    return {
        "ddg_boundary_audit_rows": 1,
        "ready_backend_count": report.get("ready_backend_count"),
        "executable_ddg_backend_ready": report.get("executable_ddg_backend_ready"),
        "proxy_ddg_backend_ready": report.get("proxy_ddg_backend_ready"),
        "current_execution_ready_count": report.get("current_execution_ready_count"),
        "physics_backend_current_execution_rows": sum(1 for item in backends if item.get("backend") in physics_names and item.get("current_execution_ready") is True),
        "license_review_blocked_backend_rows": sum(1 for item in backends if item.get("commercial_status") == "license_review_required"),
        "source_ready_for_model_claim": report.get("ready_for_model_claim", False),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
    }


def ddg_readiness_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("ready_backend_count") != report.get("current_execution_ready_count"), failures, "source_ready_backend_count_bound", report.get("ready_backend_count"), report.get("current_execution_ready_count"))
    fail_if(report.get("executable_ddg_backend_ready") is not True, failures, "source_executable_ddg_backend_ready_true", report.get("executable_ddg_backend_ready"), True)
    fail_if(report.get("proxy_ddg_backend_ready") is not True, failures, "source_proxy_ddg_backend_ready_true", report.get("proxy_ddg_backend_ready"), True)
    fail_if(report.get("ready_for_model_claim", False) is not False, failures, "source_ready_for_model_claim_false", report.get("ready_for_model_claim", False), False)
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)


def claim_matrix_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "claim_boundary_audit_rows": 1,
        "claim_rows": len(report.get("claims") or []),
        "claims_allowed": report.get("claims_allowed"),
        "claims_blocked": report.get("claims_blocked"),
        "current_policy_success": validation.get("success"),
        "current_failure_count": validation.get("failure_count"),
        "current_all_claims_ready": validation.get("all_claims_ready"),
        "current_promotion_policy_allows_all_claims": validation.get("promotion_policy_allows_all_claims"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
    }


def claim_matrix_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("claims_allowed", 0) + report.get("claims_blocked", 0) != len(report.get("claims") or []), failures, "source_claim_partition_exact", {"claim_rows": len(report.get("claims") or []), "claims_allowed": report.get("claims_allowed"), "claims_blocked": report.get("claims_blocked")}, "allowed + blocked = claims")
    fail_if(validation.get("success") is not True, failures, "source_current_policy_success_true", validation.get("success"), True)
    fail_if(validation.get("failure_count") != 0, failures, "source_current_policy_failure_count_zero", validation.get("failure_count"), 0)
    fail_if(validation.get("all_claims_ready") is not False, failures, "source_all_claims_ready_false", validation.get("all_claims_ready"), False)
    fail_if(validation.get("promotion_policy_allows_all_claims") is not False, failures, "source_promotion_policy_allows_all_claims_false", validation.get("promotion_policy_allows_all_claims"), False)
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)


def production_release_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "production_release_boundary_audit_rows": 1,
        "artifact_count": report.get("artifact_count"),
        "source_release_ready": report.get("release_ready"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": validation.get("failure_count"),
        "source_validation_release_ready": validation.get("release_ready"),
        "source_validation_artifact_count": validation.get("artifact_count"),
        "source_validation_safe_for_training_pipeline": validation.get("safe_for_training_pipeline"),
        "source_validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
    }


def production_release_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("artifact_count") != validation.get("artifact_count"), failures, "source_artifact_count_bound", report.get("artifact_count"), validation.get("artifact_count"))
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("failure_count") != 0, failures, "source_validation_failure_count_zero", validation.get("failure_count"), 0)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)


def five_head_training_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    heads = report.get("heads") or {}
    return {
        "five_head_training_boundary_audit_rows": 1,
        "audited_rows": report.get("audited_rows"),
        "strict_rows": report.get("strict_rows"),
        "ready_head_count": report.get("ready_head_count"),
        "missing_head_label_count": len(report.get("missing_head_labels") or []),
        "training_execution_allowed": report.get("training_execution_allowed"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
        "head_count": len(heads),
        "head_ready_rows": sum(1 for item in heads.values() if item.get("ready") is True),
        "head_training_execution_allowed_rows": sum(1 for item in heads.values() if item.get("training_execution_allowed") is True),
        "source_validation_success": validation.get("success"),
        "source_validation_ready_head_count": validation.get("ready_head_count"),
        "source_validation_training_execution_allowed": validation.get("training_execution_allowed"),
        "source_validation_safe_for_training_import": validation.get("safe_for_training_import"),
        "source_validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
        "source_validation_release_ready": validation.get("release_ready"),
    }


def five_head_training_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not None and report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("ready_head_count") != 0, failures, "source_ready_head_count_zero", report.get("ready_head_count"), 0)
    fail_if(report.get("training_execution_allowed") is not False, failures, "source_training_execution_allowed_false", report.get("training_execution_allowed"), False)
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("ready_head_count") != 0, failures, "source_validation_ready_head_count_zero", validation.get("ready_head_count"), 0)
    fail_if(validation.get("training_execution_allowed") is not False, failures, "source_validation_training_execution_allowed_false", validation.get("training_execution_allowed"), False)
    fail_if(validation.get("safe_for_training_import") is not False, failures, "source_validation_safe_for_training_import_false", validation.get("safe_for_training_import"), False)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)
    fail_if(any(item.get("ready") is True for item in (report.get("heads") or {}).values()), failures, "source_head_ready_rows_zero", "nonzero", 0)
    fail_if(any(item.get("training_execution_allowed") is True for item in (report.get("heads") or {}).values()), failures, "source_head_training_execution_rows_zero", "nonzero", 0)


def validated_feature_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "validated_feature_boundary_audit_rows": 1,
        "feature_rows": report.get("feature_rows"),
        "model_consumable_rows": report.get("model_consumable_rows"),
        "training_label_source_rows": report.get("training_label_source_rows"),
        "pyrosetta_ddg_input_feature_rows": report.get("pyrosetta_ddg_input_feature_rows"),
        "pyrosetta_ddg_independent_training_sample_rows": report.get("pyrosetta_ddg_independent_training_sample_rows"),
        "pyrosetta_ddg_unique_mutation_groups": report.get("pyrosetta_ddg_unique_mutation_groups"),
        "source_safe_for_training_import": report.get("safe_for_training_import", False),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
        "source_validation_success": validation.get("success"),
        "source_validation_feature_rows": validation.get("feature_rows"),
        "source_validation_model_consumable_rows": validation.get("model_consumable_rows"),
        "source_validation_training_label_source_rows": validation.get("training_label_source_rows"),
        "source_validation_safe_for_training_import": validation.get("safe_for_training_import"),
        "source_validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
        "source_validation_release_ready": validation.get("release_ready"),
    }


def validated_feature_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("feature_rows") != report.get("model_consumable_rows"), failures, "source_feature_rows_model_consumable_bound", {"feature_rows": report.get("feature_rows"), "model_consumable_rows": report.get("model_consumable_rows")}, "feature rows = model consumable rows")
    fail_if(report.get("training_label_source_rows") != 0, failures, "source_training_label_source_rows_zero", report.get("training_label_source_rows"), 0)
    fail_if(report.get("pyrosetta_ddg_independent_training_sample_rows") != 0, failures, "source_independent_training_sample_rows_zero", report.get("pyrosetta_ddg_independent_training_sample_rows"), 0)
    fail_if(report.get("safe_for_training_import", False) is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import", False), False)
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("feature_rows") != report.get("feature_rows"), failures, "source_validation_feature_rows_bound", validation.get("feature_rows"), report.get("feature_rows"))
    fail_if(validation.get("model_consumable_rows") != report.get("model_consumable_rows"), failures, "source_validation_model_consumable_rows_bound", validation.get("model_consumable_rows"), report.get("model_consumable_rows"))
    fail_if(validation.get("training_label_source_rows") != 0, failures, "source_validation_training_label_source_rows_zero", validation.get("training_label_source_rows"), 0)
    fail_if(validation.get("safe_for_training_import") is not False, failures, "source_validation_safe_for_training_import_false", validation.get("safe_for_training_import"), False)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)


def model_artifact_claim_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model_artifact_boundary_audit_rows": 1,
        "artifact_count": report.get("artifact_count"),
        "claimable_model_artifact_count": report.get("claimable_model_artifact_count"),
        "trained_neural_weight_artifact_count": report.get("trained_neural_weight_artifact_count"),
        "production_model_artifact_count": report.get("production_model_artifact_count"),
        "missing_artifact_count": len(report.get("missing_artifacts") or []),
        "source_success": report.get("success"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
        "source_validation_success": validation.get("success"),
        "source_validation_expected_artifact_count": validation.get("expected_artifact_count"),
        "source_validation_report_matches_current_artifact_sources": validation.get("report_matches_current_artifact_sources"),
        "source_validation_claimable_model_artifact_count": validation.get("claimable_model_artifact_count"),
        "source_validation_trained_neural_weight_artifact_count": validation.get("trained_neural_weight_artifact_count"),
        "source_validation_production_model_artifact_count": validation.get("production_model_artifact_count"),
        "source_validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
        "source_validation_release_ready": validation.get("release_ready"),
    }


def model_artifact_claim_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("artifact_count") != validation.get("expected_artifact_count"), failures, "source_artifact_count_expected_bound", report.get("artifact_count"), validation.get("expected_artifact_count"))
    fail_if(validation.get("artifact_count") != report.get("artifact_count"), failures, "source_validation_artifact_count_bound", validation.get("artifact_count"), report.get("artifact_count"))
    fail_if(validation.get("report_matches_current_artifact_sources") is not True, failures, "source_validation_artifact_sources_match_true", validation.get("report_matches_current_artifact_sources"), True)
    for key in ("claimable_model_artifact_count", "trained_neural_weight_artifact_count", "production_model_artifact_count"):
        fail_if(report.get(key) != 0, failures, f"source_{key}_zero", report.get(key), 0)
        fail_if(validation.get(key) != 0, failures, f"source_validation_{key}_zero", validation.get(key), 0)
    fail_if(len(report.get("missing_artifacts") or []) != 0, failures, "source_missing_artifacts_zero", len(report.get("missing_artifacts") or []), 0)
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)


def local_release_guard_coverage_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    guards = report.get("checked_guards") or []
    projection_checks = report.get("human_target_projection_checks") or {}
    return {
        "local_release_guard_boundary_audit_rows": 1,
        "guard_coverage_count": report.get("guard_coverage_count"),
        "checked_guard_rows": len(guards),
        "guard_failure_count": len(report.get("failures") or []),
        "projection_check_count": len(projection_checks),
        "projection_checks_failed_count": sum(1 for value in projection_checks.values() if value is not True),
        "source_success": report.get("success"),
        "source_safe_for_training_pipeline": report.get("safe_for_training_pipeline"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
    }


def local_release_guard_coverage_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    guards = report.get("checked_guards") or []
    projection_checks = report.get("human_target_projection_checks") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("guard_coverage_count") != len(guards), failures, "source_guard_coverage_count_bound", report.get("guard_coverage_count"), len(guards))
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failure_rows_zero", len(report.get("failures") or []), 0)
    fail_if(any(item.get("data_lake_artifact_exists") is not True or item.get("data_lake_artifact_present") is not True or item.get("report_present") is not True or item.get("release_link_present") is not True for item in guards), failures, "source_guard_rows_complete", "incomplete guard row", "all guard rows complete")
    fail_if(any(value is not True for value in projection_checks.values()), failures, "source_projection_checks_true", projection_checks, "all true")
    fail_if(report.get("safe_for_training_pipeline") is not True, failures, "source_safe_for_training_pipeline_true", report.get("safe_for_training_pipeline"), True)
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)


def training_readiness_quality_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    label_integrity = report.get("label_integrity") or {}
    multitask = report.get("multitask_training") or {}
    return {
        "training_readiness_boundary_audit_rows": 1,
        "quality_score": report.get("quality_score"),
        "ready_for_baseline_training": report.get("ready_for_baseline_training"),
        "ready_for_supervised_training_pipeline": report.get("ready_for_supervised_training_pipeline"),
        "ready_for_supervised_small_model_claim": report.get("ready_for_supervised_small_model_claim"),
        "strict_supervised_rows": label_integrity.get("strict_supervised_rows"),
        "claim_eligible_supervised_rows": label_integrity.get("claim_eligible_supervised_rows"),
        "verified_rows": label_integrity.get("verified_rows"),
        "multitask_audited_rows": multitask.get("audited_rows"),
        "multitask_ready_head_count": multitask.get("ready_head_count"),
        "multitask_training_execution_allowed": multitask.get("training_execution_allowed"),
        "multitask_safe_for_model_claim": multitask.get("safe_for_model_claim"),
        "source_blocker_count": len(report.get("blockers") or []),
        "source_release_ready": False,
        "source_safe_for_model_claim": report.get("ready_for_supervised_small_model_claim", False),
    }


def training_readiness_quality_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    label_integrity = report.get("label_integrity") or {}
    multitask = report.get("multitask_training") or {}
    fail_if(report.get("quality_score") is None, failures, "source_quality_score_present", report.get("quality_score"), "numeric quality score")
    fail_if(report.get("ready_for_baseline_training") is not True, failures, "source_ready_for_baseline_training_true", report.get("ready_for_baseline_training"), True)
    fail_if(report.get("ready_for_supervised_training_pipeline") is not True, failures, "source_ready_for_supervised_training_pipeline_true", report.get("ready_for_supervised_training_pipeline"), True)
    fail_if(report.get("ready_for_supervised_small_model_claim") is not False, failures, "source_ready_for_supervised_small_model_claim_false", report.get("ready_for_supervised_small_model_claim"), False)
    fail_if(label_integrity.get("strict_supervised_rows") != 0, failures, "source_strict_supervised_rows_zero", label_integrity.get("strict_supervised_rows"), 0)
    fail_if(label_integrity.get("claim_eligible_supervised_rows") != 0, failures, "source_claim_eligible_supervised_rows_zero", label_integrity.get("claim_eligible_supervised_rows"), 0)
    fail_if(multitask.get("ready_head_count") != 0, failures, "source_multitask_ready_head_count_zero", multitask.get("ready_head_count"), 0)
    fail_if(multitask.get("training_execution_allowed") is not False, failures, "source_multitask_training_execution_allowed_false", multitask.get("training_execution_allowed"), False)
    fail_if(multitask.get("safe_for_model_claim") is not False, failures, "source_multitask_safe_for_model_claim_false", multitask.get("safe_for_model_claim"), False)
    fail_if(len(report.get("blockers") or []) == 0, failures, "source_blockers_present", len(report.get("blockers") or []), "nonzero")


def five_head_execution_contract_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    head_rows = report.get("head_rows") or {}
    training_label_import = report.get("training_label_import") or {}
    feature_input_gate = report.get("feature_input_gate") or {}
    benchmark_gate = report.get("benchmark_gate") or {}
    return {
        "five_head_contract_boundary_audit_rows": 1,
        "expected_head_count": len(report.get("expected_heads") or []),
        "head_rows_count": len(head_rows),
        "ready_head_count": report.get("ready_head_count"),
        "ready_heads_count": len(report.get("ready_heads") or []),
        "total_head_training_rows": report.get("total_head_training_rows"),
        "training_import_eligible_rows": training_label_import.get("training_import_eligible_rows"),
        "feature_ready_refs": feature_input_gate.get("ready_feature_refs"),
        "feature_inputs_are_labels": feature_input_gate.get("feature_inputs_are_labels"),
        "benchmark_ready_for_model_claim": benchmark_gate.get("ready_for_model_claim"),
        "blocked_reason_count": len(report.get("blocked_reasons") or []),
        "source_success": report.get("success"),
        "source_training_execution_allowed": report.get("training_execution_allowed"),
        "source_safe_for_training_import": report.get("safe_for_training_import", False),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": len(validation.get("failures") or []),
        "source_validation_ready_head_count": validation.get("ready_head_count"),
        "source_validation_training_import_eligible_rows": validation.get("training_import_eligible_rows"),
        "source_validation_training_execution_allowed": validation.get("training_execution_allowed"),
        "source_validation_safe_for_training_import": validation.get("safe_for_training_import"),
        "source_validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
        "source_validation_release_ready": validation.get("release_ready"),
    }


def five_head_execution_contract_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    head_rows = report.get("head_rows") or {}
    training_label_import = report.get("training_label_import") or {}
    feature_input_gate = report.get("feature_input_gate") or {}
    benchmark_gate = report.get("benchmark_gate") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(report.get("expected_heads") or []) != len(head_rows), failures, "source_head_rows_cover_expected_heads", len(head_rows), len(report.get("expected_heads") or []))
    fail_if(report.get("ready_head_count") != 0, failures, "source_ready_head_count_zero", report.get("ready_head_count"), 0)
    fail_if(len(report.get("ready_heads") or []) != 0, failures, "source_ready_heads_empty", len(report.get("ready_heads") or []), 0)
    fail_if(any(item.get("ready") is True or item.get("thresholds_met") is True for item in head_rows.values()), failures, "source_no_ready_or_threshold_met_heads", "nonzero", 0)
    fail_if(report.get("training_execution_allowed") is not False, failures, "source_training_execution_allowed_false", report.get("training_execution_allowed"), False)
    fail_if(report.get("model_quality_claim_allowed") is not False, failures, "source_model_quality_claim_allowed_false", report.get("model_quality_claim_allowed"), False)
    fail_if(report.get("safe_for_training_import", False) is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import", False), False)
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)
    fail_if(training_label_import.get("training_import_eligible_rows") != validation.get("training_import_eligible_rows"), failures, "source_training_import_rows_bound", training_label_import.get("training_import_eligible_rows"), validation.get("training_import_eligible_rows"))
    fail_if(feature_input_gate.get("feature_inputs_are_labels") is not False, failures, "source_feature_inputs_not_labels", feature_input_gate.get("feature_inputs_are_labels"), False)
    fail_if(benchmark_gate.get("ready_for_model_claim") is not False, failures, "source_benchmark_ready_for_model_claim_false", benchmark_gate.get("ready_for_model_claim"), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    fail_if(validation.get("ready_head_count") != 0, failures, "source_validation_ready_head_count_zero", validation.get("ready_head_count"), 0)
    fail_if(validation.get("training_execution_allowed") is not False, failures, "source_validation_training_execution_allowed_false", validation.get("training_execution_allowed"), False)
    fail_if(validation.get("safe_for_training_import") is not False, failures, "source_validation_safe_for_training_import_false", validation.get("safe_for_training_import"), False)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)


def model_quality_hard_gate_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    hard_gates = report.get("hard_gates") or []
    return {
        "model_quality_contract_boundary_audit_rows": 1,
        "hard_gate_count": len(hard_gates),
        "unlocked_gate_count": sum(1 for item in hard_gates if item.get("unlocked") is True),
        "training_import_eligible_rows": report.get("training_import_eligible_rows"),
        "training_import_written_rows": report.get("training_import_written_rows"),
        "wetlab_authorized_rows": report.get("wetlab_authorized_rows"),
        "wetlab_preflight_rows": report.get("wetlab_preflight_rows"),
        "wetlab_import_rows": report.get("wetlab_import_rows"),
        "feature_inputs_ready": report.get("feature_inputs_ready"),
        "feature_inputs_input_only": report.get("feature_inputs_input_only"),
        "physics_ddg_ready": report.get("physics_ddg_ready"),
        "benchmark_ready_for_model_claim": report.get("benchmark_ready_for_model_claim"),
        "model_quality_ready": report.get("model_quality_ready"),
        "source_success": report.get("success"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": len(validation.get("failures") or []),
        "source_validation_report_matches_current_sources": validation.get("report_matches_current_sources"),
        "source_validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
        "source_validation_release_ready": validation.get("release_ready"),
    }


def model_quality_hard_gate_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    hard_gates = report.get("hard_gates") or []
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(hard_gates) == 0, failures, "source_hard_gates_present", len(hard_gates), "nonzero")
    fail_if(report.get("wetlab_import_rows") != 0, failures, "source_wetlab_import_rows_zero", report.get("wetlab_import_rows"), 0)
    fail_if(report.get("feature_inputs_input_only") is not True, failures, "source_feature_inputs_input_only_true", report.get("feature_inputs_input_only"), True)
    for key in ("physics_ddg_ready", "benchmark_ready_for_model_claim", "model_quality_ready", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(key, False) is not False, failures, f"source_{key}_false", report.get(key, False), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    fail_if(validation.get("report_matches_current_sources") is not True, failures, "source_validation_report_matches_current_sources_true", validation.get("report_matches_current_sources"), True)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)
    negative_checks = validation.get("negative_protection_checks") or {}
    fail_if(any(value is not True for value in negative_checks.values()), failures, "source_negative_protection_checks_true", negative_checks, "all true")


def tool_lane_evidence_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    lanes = report.get("lanes") or []
    summary = report.get("summary") or {}
    return {
        "tool_lane_boundary_audit_rows": 1,
        "total_lanes": summary.get("total_lanes"),
        "blocked_lanes": summary.get("blocked_lanes"),
        "ready_lanes": summary.get("ready_lanes"),
        "proxy_lanes": summary.get("proxy_lanes"),
        "real_runtime_gated_lanes": summary.get("real_runtime_gated_lanes"),
        "lane_rows": len(lanes),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": len(validation.get("failures") or []),
        "source_validation_ready_lanes": validation.get("ready_lanes"),
        "source_validation_proxy_lanes_blocked": validation.get("proxy_lanes_blocked"),
        "source_validation_receipts": validation.get("receipts"),
        "source_validation_expected_receipts": validation.get("expected_receipts"),
        "source_validation_report_matches_current_builder_projection": validation.get("report_matches_current_builder_projection"),
        "source_validation_receipts_match_current_builder_projection": validation.get("receipts_match_current_builder_projection"),
    }


def tool_lane_evidence_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    lanes = report.get("lanes") or []
    summary = report.get("summary") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(summary.get("total_lanes") != len(lanes), failures, "source_total_lanes_bound", summary.get("total_lanes"), len(lanes))
    fail_if(summary.get("ready_lanes") != 0, failures, "source_ready_lanes_zero", summary.get("ready_lanes"), 0)
    fail_if(summary.get("blocked_lanes") != summary.get("total_lanes"), failures, "source_all_lanes_blocked", summary.get("blocked_lanes"), summary.get("total_lanes"))
    fail_if(any(item.get("status") != "blocked" for item in lanes), failures, "source_all_lane_status_blocked", "nonblocked lane", "all blocked")
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    fail_if(validation.get("lanes") != summary.get("total_lanes"), failures, "source_validation_lanes_bound", validation.get("lanes"), summary.get("total_lanes"))
    fail_if(validation.get("ready_lanes") != 0, failures, "source_validation_ready_lanes_zero", validation.get("ready_lanes"), 0)
    fail_if(validation.get("proxy_lanes_blocked") != summary.get("proxy_lanes"), failures, "source_proxy_lanes_blocked_bound", validation.get("proxy_lanes_blocked"), summary.get("proxy_lanes"))
    fail_if(validation.get("receipts") != validation.get("expected_receipts"), failures, "source_validation_receipts_expected", validation.get("receipts"), validation.get("expected_receipts"))
    fail_if(validation.get("report_matches_current_builder_projection") is not True, failures, "source_report_projection_true", validation.get("report_matches_current_builder_projection"), True)
    fail_if(validation.get("receipts_match_current_builder_projection") is not True, failures, "source_receipts_projection_true", validation.get("receipts_match_current_builder_projection"), True)


def human_target_runtime_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    sources = report.get("sources") or []
    summary = report.get("summary") or {}
    return {
        "human_target_runtime_boundary_audit_rows": 1,
        "total_sources": summary.get("total_sources"),
        "blocked_sources": summary.get("blocked_sources"),
        "ready_sources": summary.get("ready_sources"),
        "human_target_blocked_sources": summary.get("human_target_blocked_sources"),
        "antibody_blocked_sources": summary.get("antibody_blocked_sources"),
        "source_rows": len(sources),
        "customer_ready": report.get("customer_ready"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": validation.get("failure_count"),
        "source_validation_sources": validation.get("sources"),
        "source_validation_receipts": validation.get("receipts"),
        "source_validation_expected_sources": validation.get("expected_sources"),
        "source_validation_expected_receipts": validation.get("expected_receipts"),
        "source_validation_manifest_matches_current_builder_projection": validation.get("manifest_matches_current_builder_projection"),
        "source_validation_receipts_match_current_builder_projection": validation.get("receipts_match_current_builder_projection"),
    }


def human_target_runtime_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    sources = report.get("sources") or []
    summary = report.get("summary") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(summary.get("total_sources") != len(sources), failures, "source_total_sources_bound", summary.get("total_sources"), len(sources))
    fail_if(summary.get("ready_sources") != 0, failures, "source_ready_sources_zero", summary.get("ready_sources"), 0)
    fail_if(summary.get("blocked_sources") != summary.get("total_sources"), failures, "source_all_sources_blocked", summary.get("blocked_sources"), summary.get("total_sources"))
    fail_if(any(item.get("source_ready") is True or item.get("claim_eligible") is True or item.get("customer_ready") is True or item.get("release_ready") is True for item in sources), failures, "source_no_ready_claim_customer_release_sources", "nonzero", 0)
    fail_if(report.get("customer_ready") is not False, failures, "source_customer_ready_false", report.get("customer_ready"), False)
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("failure_count") != 0, failures, "source_validation_failure_count_zero", validation.get("failure_count"), 0)
    fail_if(validation.get("sources") != validation.get("expected_sources"), failures, "source_validation_sources_expected", validation.get("sources"), validation.get("expected_sources"))
    fail_if(validation.get("receipts") != validation.get("expected_receipts"), failures, "source_validation_receipts_expected", validation.get("receipts"), validation.get("expected_receipts"))
    fail_if(validation.get("manifest_matches_current_builder_projection") is not True, failures, "source_manifest_projection_true", validation.get("manifest_matches_current_builder_projection"), True)
    fail_if(validation.get("receipts_match_current_builder_projection") is not True, failures, "source_receipts_projection_true", validation.get("receipts_match_current_builder_projection"), True)
    fail_if(validation.get("customer_ready") is not False, failures, "source_validation_customer_ready_false", validation.get("customer_ready"), False)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)


def human_target_unlock_checklist_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "human_target_unlock_boundary_audit_rows": 1,
        "checklist_rows": report.get("checklist_rows"),
        "blocked_rows": report.get("blocked_rows"),
        "ready_to_unlock_rows": report.get("ready_to_unlock_rows"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": validation.get("failure_count"),
        "source_validation_checklist_rows": validation.get("checklist_rows"),
        "source_validation_expected_checklist_rows": validation.get("expected_checklist_rows"),
        "source_validation_ready_to_unlock_rows": validation.get("ready_to_unlock_rows"),
        "source_validation_checklist_matches_current_builder_projection": validation.get("checklist_matches_current_builder_projection"),
        "source_validation_report_matches_current_builder_projection": validation.get("report_matches_current_builder_projection"),
        "source_validation_blocked_index_projection_valid": validation.get("blocked_source_manifest_index_projection_valid"),
        "source_validation_blocked_split_manifests_projection_valid": validation.get("blocked_split_manifests_projection_valid"),
    }


def human_target_unlock_checklist_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("checklist_rows") != report.get("blocked_rows"), failures, "source_checklist_rows_blocked", report.get("checklist_rows"), report.get("blocked_rows"))
    fail_if(report.get("ready_to_unlock_rows") != 0, failures, "source_ready_to_unlock_rows_zero", report.get("ready_to_unlock_rows"), 0)
    fail_if(report.get("safe_for_model_claim", False) is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim", False), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("failure_count") != 0, failures, "source_validation_failure_count_zero", validation.get("failure_count"), 0)
    fail_if(validation.get("checklist_rows") != validation.get("expected_checklist_rows"), failures, "source_validation_checklist_rows_expected", validation.get("checklist_rows"), validation.get("expected_checklist_rows"))
    fail_if(validation.get("checklist_rows") != report.get("checklist_rows"), failures, "source_validation_checklist_rows_bound", validation.get("checklist_rows"), report.get("checklist_rows"))
    fail_if(validation.get("ready_to_unlock_rows") != 0, failures, "source_validation_ready_to_unlock_rows_zero", validation.get("ready_to_unlock_rows"), 0)
    for key in ("checklist_matches_current_builder_projection", "report_matches_current_builder_projection", "blocked_source_manifest_index_projection_valid", "blocked_split_manifests_projection_valid", "blocked_source_manifest_index_validation_success"):
        fail_if(validation.get(key) is not True, failures, f"source_validation_{key}_true", validation.get(key), True)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)


def training_label_import_contract_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = report.get("contract_totals") or {}
    state = report.get("observed_current_state") or {}
    return {
        "training_label_contract_boundary_audit_rows": 1,
        "training_import_eligible_label_sources": totals.get("training_import_eligible_label_sources"),
        "training_import_eligible_rows": totals.get("training_import_eligible_rows"),
        "counted_as_trainable_rows": totals.get("counted_as_trainable_rows"),
        "training_import_written_rows": report.get("training_import_written_rows"),
        "training_import_validated_written_rows": report.get("training_import_validated_written_rows"),
        "strict_supervised_rows": state.get("strict_supervised_jsonl_rows"),
        "claim_eligible_rows": state.get("claim_eligible_jsonl_rows"),
        "wet_lab_ready_for_training_import_rows": state.get("wet_lab_ready_for_training_import_rows"),
        "numeric_feedback_training_import_eligible_rows": state.get("numeric_feedback_training_import_eligible_rows"),
        "source_success": report.get("success"),
        "source_safe_for_training_import": report.get("safe_for_training_import"),
        "source_safe_for_model_claim": report.get("safe_for_model_claim"),
        "source_release_ready": report.get("release_ready"),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": len(validation.get("failures") or []),
        "source_validation_safe_for_training_import": validation.get("safe_for_training_import"),
        "source_validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
        "source_validation_release_ready": validation.get("release_ready"),
    }


def training_label_import_contract_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    totals = report.get("contract_totals") or {}
    state = report.get("observed_current_state") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(totals.get("training_import_eligible_rows") != validation.get("contract_totals", {}).get("training_import_eligible_rows"), failures, "source_training_import_rows_bound", totals.get("training_import_eligible_rows"), validation.get("contract_totals", {}).get("training_import_eligible_rows"))
    fail_if(report.get("training_import_written_rows") != validation.get("training_import_written_rows"), failures, "source_training_import_written_rows_bound", report.get("training_import_written_rows"), validation.get("training_import_written_rows"))
    fail_if(state.get("strict_supervised_jsonl_rows") != 0, failures, "source_strict_supervised_rows_zero", state.get("strict_supervised_jsonl_rows"), 0)
    fail_if(state.get("claim_eligible_jsonl_rows") != 0, failures, "source_claim_eligible_rows_zero", state.get("claim_eligible_jsonl_rows"), 0)
    fail_if(state.get("wet_lab_ready_for_training_import_rows") != 0, failures, "source_wet_lab_ready_for_training_import_zero", state.get("wet_lab_ready_for_training_import_rows"), 0)
    fail_if(report.get("safe_for_training_import") is not True, failures, "source_safe_for_training_import_true_observational", report.get("safe_for_training_import"), True)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    fail_if(validation.get("safe_for_training_import") is not True, failures, "source_validation_safe_for_training_import_true_observational", validation.get("safe_for_training_import"), True)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)


def wet_lab_authorization_contract_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    safety = report.get("safety_flags") or {}
    return {
        "wet_lab_authorization_boundary_audit_rows": 1,
        "candidate_rows": report.get("candidate_rows"),
        "numeric_training_candidate_rows": report.get("numeric_training_candidate_rows"),
        "authorization_rows": report.get("authorization_rows"),
        "authorized_rows": report.get("authorized_rows"),
        "preflight_rows": report.get("preflight_rows"),
        "apply_plan_rows": report.get("apply_plan_rows"),
        "ready_for_training_import_rows": report.get("ready_for_training_import_rows"),
        "claim_eligible_rows_now": report.get("claim_eligible_rows_now"),
        "duplicate_audit_safe_to_append_rows": (report.get("source_values") or {}).get("apply_duplicate_safe_to_append_rows"),
        "source_success": report.get("success"),
        "source_safe_for_training_import": safety.get("safe_for_training_import"),
        "source_safe_for_model_claim": safety.get("safe_for_model_claim"),
        "source_release_ready": safety.get("release_ready"),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": len(validation.get("failures") or []),
    }


def wet_lab_authorization_contract_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    safety = report.get("safety_flags") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("source_state_matches_expected") is not True, failures, "source_state_matches_expected_true", report.get("source_state_matches_expected"), True)
    fail_if(report.get("authorization_rows") != validation.get("authorization_rows"), failures, "source_authorization_rows_bound", report.get("authorization_rows"), validation.get("authorization_rows"))
    fail_if(report.get("preflight_rows") != validation.get("preflight_rows"), failures, "source_preflight_rows_bound", report.get("preflight_rows"), validation.get("preflight_rows"))
    fail_if(report.get("ready_for_training_import_rows") != 0, failures, "source_ready_for_training_import_zero", report.get("ready_for_training_import_rows"), 0)
    fail_if(report.get("claim_eligible_rows_now") != 0, failures, "source_claim_eligible_rows_zero", report.get("claim_eligible_rows_now"), 0)
    fail_if((report.get("source_values") or {}).get("apply_duplicate_safe_to_append_rows") != 0, failures, "source_duplicate_safe_to_append_zero", (report.get("source_values") or {}).get("apply_duplicate_safe_to_append_rows"), 0)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(safety.get(field) is not False, failures, f"source_{field}_false", safety.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    negative_checks = validation.get("negative_protection_checks") or {}
    fail_if(any(value is not True for value in negative_checks.values()), failures, "source_negative_protection_checks_true", negative_checks, "all true")


def ddg_consumption_contract_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    state = report.get("physics_ddg_state") or {}
    physics = report.get("physics_ddg_consumption") or {}
    proxy = report.get("proxy_ddg_consumption") or {}
    validation_state = validation.get("state_summary") or {}
    return {
        "ddg_consumption_boundary_audit_rows": 1,
        "physics_ddg_ready": state.get("physics_ddg_ready"),
        "executable_ddg_backend_ready": state.get("executable_ddg_backend_ready"),
        "proxy_is_physics": state.get("proxy_is_physics"),
        "pyrosetta_physics_rows": physics.get("mutation_row_count"),
        "thermompnn_proxy_rows": proxy.get("mutation_row_count"),
        "physics_training_label": physics.get("training_label"),
        "proxy_training_label": proxy.get("training_label"),
        "source_success": report.get("success"),
        "source_safe_for_training_import": physics.get("safe_for_training_import") or proxy.get("safe_for_training_import"),
        "source_safe_for_model_claim": physics.get("safe_for_model_claim") or proxy.get("safe_for_model_claim"),
        "source_release_ready": physics.get("release_ready") or proxy.get("release_ready"),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": len(validation.get("failures") or []),
        "source_validation_pyrosetta_physics_rows": validation_state.get("pyrosetta_physics_rows"),
        "source_validation_thermompnn_proxy_rows": validation_state.get("thermompnn_proxy_rows"),
    }


def ddg_consumption_contract_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    state = report.get("physics_ddg_state") or {}
    physics = report.get("physics_ddg_consumption") or {}
    proxy = report.get("proxy_ddg_consumption") or {}
    validation_state = validation.get("state_summary") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(state.get("physics_ddg_ready") is not False, failures, "source_physics_ddg_ready_false", state.get("physics_ddg_ready"), False)
    fail_if(state.get("proxy_is_physics") is not False, failures, "source_proxy_is_physics_false", state.get("proxy_is_physics"), False)
    fail_if(physics.get("training_label") is not False, failures, "source_physics_training_label_false", physics.get("training_label"), False)
    fail_if(proxy.get("training_label") is not False, failures, "source_proxy_training_label_false", proxy.get("training_label"), False)
    for source_name, source in (("physics", physics), ("proxy", proxy)):
        for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
            fail_if(source.get(field) is not False, failures, f"source_{source_name}_{field}_false", source.get(field), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    fail_if(validation_state.get("pyrosetta_physics_rows") != physics.get("mutation_row_count"), failures, "source_validation_pyrosetta_rows_bound", validation_state.get("pyrosetta_physics_rows"), physics.get("mutation_row_count"))
    fail_if(validation_state.get("thermompnn_proxy_rows") != proxy.get("mutation_row_count"), failures, "source_validation_proxy_rows_bound", validation_state.get("thermompnn_proxy_rows"), proxy.get("mutation_row_count"))
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def structure_feature_contract_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    parse = report.get("coordinate_file_parse_evidence") or {}
    reviewed = report.get("reviewed_chain_graph_boundary") or {}
    contract = report.get("model_consumption_contract") or {}
    return {
        "structure_feature_contract_boundary_audit_rows": 1,
        "coordinate_manifest_rows": parse.get("manifest_rows"),
        "parsed_coordinate_feature_rows": parse.get("parsed_coordinate_feature_rows"),
        "parse_failures": parse.get("parse_failures"),
        "reviewed_graph_rows": reviewed.get("reviewed_graph_index_rows"),
        "formal_chain_mapping_decision_rows": reviewed.get("formal_chain_mapping_decision_rows"),
        "model_consumable_reviewed_graph_rows": contract.get("model_consumable_reviewed_graph_rows"),
        "unreviewed_coordinate_rows_excluded": contract.get("unreviewed_coordinate_rows_excluded_from_reviewed_graph"),
        "training_label_source_rows": contract.get("training_label_source_rows"),
        "source_safe_for_model_claim": contract.get("safe_for_model_claim"),
        "source_release_ready": contract.get("release_ready"),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": len(validation.get("failures") or []),
    }


def structure_feature_contract_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    parse = report.get("coordinate_file_parse_evidence") or {}
    reviewed = report.get("reviewed_chain_graph_boundary") or {}
    contract = report.get("model_consumption_contract") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("status") != "input_feature_boundary_only", failures, "source_status_input_feature_boundary_only", report.get("status"), "input_feature_boundary_only")
    fail_if(parse.get("coordinate_parse_complete") is not True, failures, "source_coordinate_parse_complete_true", parse.get("coordinate_parse_complete"), True)
    fail_if(parse.get("parse_failures") != 0, failures, "source_parse_failures_zero", parse.get("parse_failures"), 0)
    fail_if(reviewed.get("reviewed_graph_index_rows") != reviewed.get("formal_chain_mapping_decision_rows"), failures, "source_reviewed_graph_formal_decisions_bound", reviewed.get("reviewed_graph_index_rows"), reviewed.get("formal_chain_mapping_decision_rows"))
    fail_if(contract.get("unreviewed_coordinate_rows_counted_as_model_consumable_reviewed_graph") != 0, failures, "source_unreviewed_counted_zero", contract.get("unreviewed_coordinate_rows_counted_as_model_consumable_reviewed_graph"), 0)
    fail_if(contract.get("training_label_source") is not False, failures, "source_training_label_source_false", contract.get("training_label_source"), False)
    fail_if(contract.get("training_label_source_rows") != 0, failures, "source_training_label_source_rows_zero", contract.get("training_label_source_rows"), 0)
    for field in ("safe_for_model_claim", "release_ready"):
        fail_if(contract.get(field) is not False, failures, f"source_{field}_false", contract.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)


def advanced_feature_contract_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    contract = report.get("feature_index_contract") or {}
    scaffold = report.get("advanced_model_contract") or {}
    validation_contract = validation.get("feature_contract") or {}
    validation_scaffold = validation.get("advanced_model_scaffold") or {}
    return {
        "advanced_feature_contract_boundary_audit_rows": 1,
        "feature_ref_count": contract.get("feature_ref_count"),
        "ready_feature_ref_count": contract.get("advanced_model_ready_feature_ref_count"),
        "model_input_only_feature_ref_count": contract.get("model_input_only_feature_ref_count"),
        "training_label_source_feature_ref_count": contract.get("training_label_source_feature_ref_count"),
        "optional_physical_ddg_feature_ref_count": contract.get("optional_physical_ddg_feature_ref_count"),
        "independent_training_sample_rows": (contract.get("optional_physical_ddg_group_summary") or {}).get("independent_training_sample_rows"),
        "scaffold_status": scaffold.get("status"),
        "validation_scaffold_status": validation_scaffold.get("status"),
        "source_success": report.get("success"),
        "source_safe_for_training_import": report.get("safe_for_training_import", False),
        "source_safe_for_model_claim": report.get("safe_for_model_claim", False),
        "source_release_ready": report.get("release_ready", False),
        "source_validation_success": validation.get("success"),
        "source_validation_feature_refs": validation_contract.get("feature_refs"),
        "source_validation_training_label_source_feature_refs": validation_contract.get("training_label_source_feature_refs"),
    }


def advanced_feature_contract_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    contract = report.get("feature_index_contract") or {}
    scaffold = report.get("advanced_model_contract") or {}
    validation_contract = validation.get("feature_contract") or {}
    validation_scaffold = validation.get("advanced_model_scaffold") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(contract.get("feature_ref_count") != validation_contract.get("feature_refs"), failures, "source_feature_refs_bound", contract.get("feature_ref_count"), validation_contract.get("feature_refs"))
    fail_if(contract.get("advanced_model_ready_feature_ref_count") != validation_contract.get("ready_feature_refs"), failures, "source_ready_feature_refs_bound", contract.get("advanced_model_ready_feature_ref_count"), validation_contract.get("ready_feature_refs"))
    fail_if(contract.get("model_input_only_feature_ref_count") != contract.get("feature_ref_count"), failures, "source_all_features_input_only", contract.get("model_input_only_feature_ref_count"), contract.get("feature_ref_count"))
    fail_if(contract.get("training_label_source_feature_ref_count") != 0, failures, "source_training_label_source_refs_zero", contract.get("training_label_source_feature_ref_count"), 0)
    fail_if((contract.get("optional_physical_ddg_group_summary") or {}).get("independent_training_sample_rows") != 0, failures, "source_independent_training_sample_rows_zero", (contract.get("optional_physical_ddg_group_summary") or {}).get("independent_training_sample_rows"), 0)
    fail_if(scaffold.get("status") != "scaffold_only_fail_closed", failures, "source_scaffold_status_fail_closed", scaffold.get("status"), "scaffold_only_fail_closed")
    fail_if(validation_scaffold.get("status") != "scaffold_only_fail_closed", failures, "source_validation_scaffold_status_fail_closed", validation_scaffold.get("status"), "scaffold_only_fail_closed")
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    negative_checks = validation.get("negative_protection_checks") or {}
    fail_if(any(value is not True for value in negative_checks.values()), failures, "source_negative_protection_checks_true", negative_checks, "all true")
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field, False) is not False, failures, f"source_{field}_false", report.get(field, False), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def active_learning_readiness_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = report.get("blockers") or []
    return {
        "active_learning_boundary_audit_rows": 1,
        "draft_rows": report.get("draft_rows"),
        "candidate_generation_allowed": report.get("candidate_generation_allowed"),
        "experiment_submission_allowed": report.get("experiment_submission_allowed"),
        "human_approval_required": report.get("human_approval_required"),
        "model_status": report.get("model_status"),
        "benchmark_ready_for_model_claim": report.get("benchmark_ready_for_model_claim"),
        "blocker_count": len(blockers),
        "source_ready": report.get("ready"),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": len(validation.get("failures") or []),
        "source_validation_customer_delivery_ready": validation.get("customer_delivery_ready"),
        "source_validation_biosecurity_ready_for_ordering": validation.get("biosecurity_ready_for_ordering"),
    }


def active_learning_readiness_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("ready") is not False, failures, "source_ready_false", report.get("ready"), False)
    fail_if(report.get("candidate_generation_allowed") is not False, failures, "source_candidate_generation_allowed_false", report.get("candidate_generation_allowed"), False)
    fail_if(report.get("experiment_submission_allowed") is not False, failures, "source_experiment_submission_allowed_false", report.get("experiment_submission_allowed"), False)
    fail_if(report.get("human_approval_required") is not True, failures, "source_human_approval_required_true", report.get("human_approval_required"), True)
    fail_if(report.get("model_status") != "blocked", failures, "source_model_status_blocked", report.get("model_status"), "blocked")
    fail_if(len(report.get("blockers") or []) == 0, failures, "source_blockers_present", len(report.get("blockers") or []), ">0")
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    for field in ("candidate_generation_allowed", "experiment_submission_allowed", "safe_for_model_claim", "release_ready", "customer_delivery_ready", "biosecurity_ready_for_ordering"):
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def benchmark_packet_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    return {
        "benchmark_packet_boundary_audit_rows": 1,
        "packet_rows": summary.get("packet_rows"),
        "invalid_gap_rows": summary.get("invalid_gap_rows"),
        "local_contract_only_rows": summary.get("local_contract_only_rows"),
        "completion_ready_rows": summary.get("completion_ready_rows"),
        "score_values_recorded": summary.get("score_values_recorded"),
        "source_status": report.get("status"),
        "source_ready_for_model_claim": report.get("ready_for_model_claim"),
        "source_validation_contract_valid": validation.get("contract_valid"),
        "source_validation_failure_count": validation.get("failure_count"),
        "source_validation_blocked_rows": validation.get("blocked_rows"),
    }


def benchmark_packet_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    summary = report.get("summary") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("status") != "blocked", failures, "source_status_blocked", report.get("status"), "blocked")
    fail_if(summary.get("completion_ready_rows") != 0, failures, "source_completion_ready_rows_zero", summary.get("completion_ready_rows"), 0)
    fail_if(summary.get("score_values_recorded") != 0, failures, "source_score_values_recorded_zero", summary.get("score_values_recorded"), 0)
    fail_if(report.get("training_labels_modified") is not False, failures, "source_training_labels_modified_false", report.get("training_labels_modified"), False)
    fail_if(report.get("write_benchmark_score_cache_intake_allowed") is not False, failures, "source_write_score_cache_false", report.get("write_benchmark_score_cache_intake_allowed"), False)
    fail_if(report.get("manifest_update_allowed") is not False, failures, "source_manifest_update_allowed_false", report.get("manifest_update_allowed"), False)
    fail_if(report.get("release_flags_modified") is not False, failures, "source_release_flags_modified_false", report.get("release_flags_modified"), False)
    fail_if(validation.get("contract_valid") is not True, failures, "source_validation_contract_valid_true", validation.get("contract_valid"), True)
    fail_if(validation.get("failure_count") != 0, failures, "source_validation_failure_count_zero", validation.get("failure_count"), 0)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    fail_if(validation.get("packet_report_summary_matches_current_packets") is not True, failures, "source_validation_summary_current_true", validation.get("packet_report_summary_matches_current_packets"), True)
    fail_if(validation.get("markdown_matches_current_packets") is not True, failures, "source_validation_markdown_current_true", validation.get("markdown_matches_current_packets"), True)
    for field in ("ready_for_model_claim", "safe_for_model_claim", "release_ready", "training_labels_modified", "release_flags_modified"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def enzyme_tool_contract_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "enzyme_tool_contract_boundary_audit_rows": 1,
        "action_rows": report.get("action_rows"),
        "contract_rows": report.get("contract_rows"),
        "required_action_rows": report.get("required_action_rows"),
        "required_contract_rows": report.get("required_contract_rows"),
        "human_confirmation_required_actions": report.get("human_confirmation_required_actions"),
        "formal_decision_actions": report.get("formal_decision_actions"),
        "training_write_actions": report.get("training_write_actions"),
        "safe_for_model_claim_actions": report.get("safe_for_model_claim_actions"),
        "contract_training_write_tools": report.get("contract_training_write_tools"),
        "contract_formal_write_tools": report.get("contract_formal_write_tools"),
        "safe_for_controlled_agent_planning": report.get("safe_for_controlled_agent_planning"),
        "source_success": report.get("success"),
        "source_failure_count": len(report.get("failures") or []),
    }


def enzyme_tool_contract_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("action_rows") != report.get("required_action_rows"), failures, "source_action_rows_required", report.get("action_rows"), report.get("required_action_rows"))
    fail_if(report.get("contract_rows") != report.get("required_contract_rows"), failures, "source_contract_rows_required", report.get("contract_rows"), report.get("required_contract_rows"))
    fail_if(report.get("training_write_actions") != 0, failures, "source_training_write_actions_zero", report.get("training_write_actions"), 0)
    fail_if(report.get("safe_for_model_claim_actions") != 0, failures, "source_model_claim_actions_zero", report.get("safe_for_model_claim_actions"), 0)
    fail_if(report.get("contract_training_write_tools") != 0, failures, "source_contract_training_write_tools_zero", report.get("contract_training_write_tools"), 0)
    fail_if(report.get("contract_formal_write_tools") != 0, failures, "source_contract_formal_write_tools_zero", report.get("contract_formal_write_tools"), 0)
    fail_if(report.get("safe_for_controlled_agent_planning") is not True, failures, "source_safe_for_controlled_planning_true", report.get("safe_for_controlled_agent_planning"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def foreign_tool_readiness_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    tool_rows = int(report.get("tool_rows") or 0)
    ready_rows = int(report.get("ready_for_local_evaluation") or 0)
    status_counts = report.get("status_counts") or {}
    panel_status_counts = report.get("panel_status_counts") or {}
    license_review_required = report.get("license_review_required_tools") or []
    restricted = report.get("restricted_tools") or []
    commercial_allowed = report.get("commercial_evaluation_allowed_tools") or []
    verified_license = report.get("verified_license_clearance_tools") or []
    return {
        "foreign_tool_boundary_audit_rows": 1,
        "tool_rows": tool_rows,
        "ready_for_local_evaluation_rows": ready_rows,
        "non_ready_tool_rows": tool_rows - ready_rows,
        "ready_panel_rows": panel_status_counts.get("ready"),
        "not_installed_rows": status_counts.get("not_installed"),
        "runtime_or_data_blocked_rows": status_counts.get("blocked_by_runtime_or_data"),
        "license_review_required_rows": len(license_review_required),
        "restricted_tool_rows": len(restricted),
        "commercial_evaluation_allowed_rows": len(commercial_allowed),
        "verified_license_clearance_rows": len(verified_license),
    }


def foreign_tool_readiness_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    tools = report.get("tools") or []
    status_counts = report.get("status_counts") or {}
    panel_status_counts = report.get("panel_status_counts") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("tool_rows") != len(tools), failures, "source_tool_rows_bound", report.get("tool_rows"), len(tools))
    fail_if(report.get("ready_for_local_evaluation") != status_counts.get("ready_for_local_evaluation"), failures, "source_ready_count_bound", report.get("ready_for_local_evaluation"), status_counts.get("ready_for_local_evaluation"))
    fail_if(report.get("ready_for_local_evaluation") != panel_status_counts.get("ready"), failures, "source_panel_ready_count_bound", report.get("ready_for_local_evaluation"), panel_status_counts.get("ready"))
    fail_if(len(report.get("verified_license_clearance_tools") or []) != 0, failures, "source_verified_license_clearance_empty", len(report.get("verified_license_clearance_tools") or []), 0)
    fail_if(len(report.get("license_review_required_tools") or []) == 0, failures, "source_license_review_required_present", len(report.get("license_review_required_tools") or []), ">0")
    fail_if(len(report.get("restricted_tools") or []) == 0, failures, "source_restricted_tools_present", len(report.get("restricted_tools") or []), ">0")
    fail_if(any(not tool.get("forbidden_use") for tool in tools), failures, "source_all_tools_have_forbidden_use", "missing", "present")


def msa_runtime_readiness_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    homolog_database = report.get("homolog_database") or {}
    local_binary = report.get("local_binary") or {}
    docker_image = report.get("docker_image") or {}
    trusted_cache = report.get("trusted_cache") or {}
    blockers = report.get("blockers") or []
    return {
        "msa_runtime_boundary_audit_rows": 1,
        "target_rows": report.get("target_rows"),
        "runtime_ready": report.get("runtime_ready"),
        "selected_runtime": report.get("selected_runtime"),
        "homolog_database_ready": homolog_database.get("ready"),
        "local_binary_ready": local_binary.get("ready"),
        "trusted_cache_ready": trusted_cache.get("ready"),
        "present_msa": trusted_cache.get("present_msa"),
        "present_conservation": trusted_cache.get("present_conservation"),
        "docker_daemon_ready": docker_image.get("docker_daemon_ready"),
        "docker_pull_allowed": docker_image.get("pull_allowed"),
        "blocker_count": len(blockers),
    }


def msa_runtime_readiness_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    homolog_database = report.get("homolog_database") or {}
    local_binary = report.get("local_binary") or {}
    docker_image = report.get("docker_image") or {}
    trusted_cache = report.get("trusted_cache") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("runtime_ready") is not True, failures, "source_runtime_ready_true", report.get("runtime_ready"), True)
    fail_if(report.get("selected_runtime") != "local_binary", failures, "source_selected_runtime_local_binary", report.get("selected_runtime"), "local_binary")
    fail_if(homolog_database.get("ready") is not True, failures, "source_homolog_database_ready_true", homolog_database.get("ready"), True)
    fail_if(local_binary.get("ready") is not True, failures, "source_local_binary_ready_true", local_binary.get("ready"), True)
    fail_if(trusted_cache.get("ready") is not True, failures, "source_trusted_cache_ready_true", trusted_cache.get("ready"), True)
    fail_if(trusted_cache.get("present_msa") != report.get("target_rows"), failures, "source_present_msa_target_rows", trusted_cache.get("present_msa"), report.get("target_rows"))
    fail_if(trusted_cache.get("present_conservation") != report.get("target_rows"), failures, "source_present_conservation_target_rows", trusted_cache.get("present_conservation"), report.get("target_rows"))
    fail_if(docker_image.get("docker_daemon_ready") is not False, failures, "source_docker_daemon_ready_false", docker_image.get("docker_daemon_ready"), False)
    fail_if(docker_image.get("pull_allowed") is not False, failures, "source_docker_pull_allowed_false", docker_image.get("pull_allowed"), False)


def resource_retrieval_plan_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    return {
        "resource_retrieval_boundary_audit_rows": 1,
        "action_rows": summary.get("action_rows"),
        "recommended_read_only_rows": summary.get("recommended_read_only_rows"),
        "executable_after_user_confirmation_rows": summary.get("executable_after_user_confirmation_rows"),
        "blocked_requires_human_decision_rows": summary.get("blocked_requires_human_decision_rows"),
        "forbidden_for_current_request_rows": summary.get("forbidden_for_current_request_rows"),
        "writes_training_rows": summary.get("writes_training_rows"),
        "writes_formal_decision_rows": summary.get("writes_formal_decision_rows"),
        "safe_for_model_claim_rows": summary.get("safe_for_model_claim_rows"),
        "source_safe_for_execution": report.get("safe_for_execution"),
        "source_validation_success": validation.get("success"),
        "source_validation_safe_for_controlled_agent_planning": validation.get("safe_for_controlled_agent_planning"),
        "source_validation_safe_for_execution": validation.get("safe_for_execution"),
        "source_validation_failure_count": len(validation.get("failures") or []),
    }


def resource_retrieval_plan_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    summary = report.get("summary") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("request_class") != "controlled_resource_retrieval_only", failures, "source_request_class_retrieval_only", report.get("request_class"), "controlled_resource_retrieval_only")
    fail_if(summary.get("action_rows") != validation.get("action_rows"), failures, "source_action_rows_bound", summary.get("action_rows"), validation.get("action_rows"))
    fail_if(summary.get("writes_training_rows") != 0, failures, "source_writes_training_rows_zero", summary.get("writes_training_rows"), 0)
    fail_if(summary.get("safe_for_model_claim_rows") != 0, failures, "source_claim_rows_zero", summary.get("safe_for_model_claim_rows"), 0)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("safe_for_controlled_agent_planning") is not True, failures, "source_controlled_planning_true", validation.get("safe_for_controlled_agent_planning"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    for field in ("safe_for_execution", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def agent_result_validation_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "agent_result_validation_boundary_audit_rows": 1,
        "selected_variant_rows": report.get("selected_variant_rows"),
        "property_prediction_rows": report.get("property_prediction_rows"),
        "ddg_result_rows": report.get("ddg_result_rows"),
        "artifact_ref_count": report.get("artifact_ref_count"),
        "reviewed_numbering_rows": report.get("reviewed_numbering_rows"),
        "claim_eligible_training_rows": report.get("claim_eligible_training_rows"),
        "strict_msa_site_feature_rows": report.get("strict_msa_site_feature_rows"),
        "wet_lab_authorization_rows": report.get("wet_lab_authorization_rows"),
        "warning_count": len(report.get("warnings") or []),
        "source_success": report.get("success"),
        "source_failure_count": len(report.get("failures") or []),
    }


def agent_result_validation_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("selected_variant_rows") != 0, failures, "source_selected_variant_rows_zero", report.get("selected_variant_rows"), 0)
    fail_if(report.get("claim_eligible_training_rows") != 0, failures, "source_claim_eligible_training_rows_zero", report.get("claim_eligible_training_rows"), 0)
    fail_if(report.get("strict_msa_site_feature_rows") != 0, failures, "source_strict_msa_site_feature_rows_zero", report.get("strict_msa_site_feature_rows"), 0)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(len(report.get("warnings") or []) == 0, failures, "source_warnings_present", len(report.get("warnings") or []), ">0")
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def agent_result_safety_regression_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "agent_result_regression_boundary_audit_rows": 1,
        "case_rows": report.get("case_rows"),
        "positive_cases": report.get("positive_cases"),
        "negative_cases": report.get("negative_cases"),
        "expected_rejected_negative_cases": report.get("expected_rejected_negative_cases"),
        "actual_rejected_negative_cases": report.get("actual_rejected_negative_cases"),
        "failed_regression_cases": report.get("failed_regression_cases"),
        "source_success": report.get("success"),
    }


def agent_result_safety_regression_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("actual_rejected_negative_cases") != report.get("expected_rejected_negative_cases"), failures, "source_rejected_negative_cases_bound", report.get("actual_rejected_negative_cases"), report.get("expected_rejected_negative_cases"))
    fail_if(report.get("failed_regression_cases") != 0, failures, "source_failed_regression_cases_zero", report.get("failed_regression_cases"), 0)
    fail_if(report.get("case_rows") != (report.get("positive_cases") or 0) + (report.get("negative_cases") or 0), failures, "source_case_rows_sum", report.get("case_rows"), (report.get("positive_cases") or 0) + (report.get("negative_cases") or 0))
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def agent_trace_audit_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "agent_trace_boundary_audit_rows": 1,
        "trace_rows": report.get("trace_rows"),
        "event_type_count": len(report.get("event_types") or []),
        "executed_action_count": report.get("executed_action_count"),
        "blocked_action_count": report.get("blocked_action_count"),
        "forbidden_action_count": report.get("forbidden_action_count"),
        "selected_variant_rows": report.get("selected_variant_rows"),
        "resource_plan_validation_success": report.get("resource_plan_validation_success"),
        "result_validation_success": report.get("result_validation_success"),
        "result_safety_regression_success": report.get("result_safety_regression_success"),
        "result_safety_regression_failed_cases": report.get("result_safety_regression_failed_cases"),
        "source_validation_success": validation.get("success"),
        "source_validation_failure_count": len(validation.get("failures") or []),
    }


def agent_trace_audit_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("executed_action_count") != 0, failures, "source_executed_action_count_zero", report.get("executed_action_count"), 0)
    fail_if(report.get("selected_variant_rows") != 0, failures, "source_selected_variant_rows_zero", report.get("selected_variant_rows"), 0)
    fail_if(report.get("result_safety_regression_failed_cases") != 0, failures, "source_regression_failed_cases_zero", report.get("result_safety_regression_failed_cases"), 0)
    for field in ("resource_plan_validation_success", "result_validation_success", "result_safety_regression_success"):
        fail_if(report.get(field) is not True, failures, f"source_{field}_true", report.get(field), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("trace_rows") != report.get("trace_rows"), failures, "source_validation_trace_rows_bound", validation.get("trace_rows"), report.get("trace_rows"))
    fail_if(validation.get("executed_action_count") != 0, failures, "source_validation_executed_action_count_zero", validation.get("executed_action_count"), 0)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def controlled_release_order_current_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "controlled_release_current_boundary_audit_rows": 1,
        "schema_version": report.get("schema_version"),
        "mode": report.get("mode"),
        "failure_count": report.get("failure_count"),
        "current_lock_acquired": report.get("current_lock_acquired"),
        "current_atomic_commit": report.get("current_atomic_commit"),
        "action_contract_hash_matches": report.get("expected_action_contract_sha256") == report.get("observed_action_contract_sha256"),
        "source_success": report.get("success"),
    }


def controlled_release_order_current_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("mode") != "enzyme-agent-controlled-release-guard-order-current-v1", failures, "source_mode_current", report.get("mode"), "enzyme-agent-controlled-release-guard-order-current-v1")
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(report.get("current_lock_acquired") is not True, failures, "source_current_lock_acquired_true", report.get("current_lock_acquired"), True)
    fail_if(report.get("current_atomic_commit") is not True, failures, "source_current_atomic_commit_true", report.get("current_atomic_commit"), True)
    fail_if(report.get("expected_action_contract_sha256") != report.get("observed_action_contract_sha256"), failures, "source_action_contract_hash_match", report.get("observed_action_contract_sha256"), report.get("expected_action_contract_sha256"))
    for field in ("safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def governance_readiness_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    components = report.get("components") or {}
    return {
        "governance_boundary_audit_rows": 1,
        "governance_ready": report.get("ready"),
        "external_source_rows": components.get("external_data_source_rows"),
        "external_source_ready_rows": components.get("external_data_source_registry_ready_sources"),
        "license_review_decision_rows": components.get("license_review_decision_rows"),
        "verified_delivery_scope_rows": components.get("license_review_verified_customer_delivery_rows"),
        "sequence_ip_fto_decision_rows": components.get("sequence_ip_fto_decision_rows"),
        "sequence_ip_fto_delivery_rows": components.get("sequence_ip_fto_approved_for_delivery"),
        "governance_blocker_count": len(report.get("blockers") or []),
    }


def governance_readiness_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    components = report.get("components") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("ready") is not False, failures, "source_governance_ready_false", report.get("ready"), False)
    fail_if(components.get("external_data_source_registry_ready") is not False, failures, "source_external_registry_ready_false", components.get("external_data_source_registry_ready"), False)
    fail_if(components.get("external_data_source_registry_ready_sources") != 0, failures, "source_external_ready_sources_zero", components.get("external_data_source_registry_ready_sources"), 0)
    fail_if(components.get("license_review_verified_customer_delivery_rows") != 0, failures, "source_verified_delivery_scope_rows_zero", components.get("license_review_verified_customer_delivery_rows"), 0)
    fail_if(components.get("license_review_ready_for_delivery") is not False, failures, "source_license_delivery_ready_false", components.get("license_review_ready_for_delivery"), False)
    fail_if(components.get("benchmark_ready_for_model_claim") is not False, failures, "source_benchmark_model_claim_ready_false", components.get("benchmark_ready_for_model_claim"), False)
    fail_if(components.get("biosecurity_ready_for_ordering") is not False, failures, "source_biosecurity_order_ready_false", components.get("biosecurity_ready_for_ordering"), False)
    fail_if(components.get("sequence_ip_fto_decision_rows") != 0, failures, "source_sequence_ip_decision_rows_zero", components.get("sequence_ip_fto_decision_rows"), 0)
    fail_if(components.get("sequence_ip_fto_approved_for_delivery") != 0, failures, "source_sequence_ip_delivery_rows_zero", components.get("sequence_ip_fto_approved_for_delivery"), 0)
    fail_if(components.get("sequence_ip_fto_ready_for_delivery") is not False, failures, "source_sequence_ip_delivery_ready_false", components.get("sequence_ip_fto_ready_for_delivery"), False)
    fail_if(len(report.get("blockers") or []) == 0, failures, "source_blockers_present", len(report.get("blockers") or []), ">0")


def biosecurity_readiness_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "biosecurity_boundary_audit_rows": 1,
        "state_machine_ready": report.get("state_machine_ready"),
        "decision_validation_ready": report.get("decision_validation_ready"),
        "decision_rows": report.get("decision_rows"),
        "valid_decision_rows": report.get("valid_decision_rows"),
        "invalid_decision_rows": report.get("invalid_decision_rows"),
        "approved_for_ordering_rows": report.get("approved_for_ordering_rows"),
        "order_ready_outputs_detected": report.get("order_ready_outputs_detected"),
        "biosecurity_blocker_count": len(report.get("blockers") or []),
    }


def biosecurity_readiness_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("state_machine_ready") is not True, failures, "source_state_machine_ready_true", report.get("state_machine_ready"), True)
    fail_if(report.get("decision_validation_ready") is not False, failures, "source_decision_validation_ready_false", report.get("decision_validation_ready"), False)
    for key in ("decision_rows", "valid_decision_rows", "invalid_decision_rows", "approved_for_ordering_rows", "order_ready_outputs_detected"):
        fail_if(report.get(key) != 0, failures, f"source_{key}_zero", report.get(key), 0)
    fail_if(report.get("ready_for_ordering") is not False, failures, "source_ready_for_ordering_false", report.get("ready_for_ordering"), False)
    fail_if(len(report.get("order_ready_output_files") or []) != 0, failures, "source_order_ready_output_files_zero", len(report.get("order_ready_output_files") or []), 0)
    fail_if(len(report.get("order_ready_output_artifacts") or []) != 0, failures, "source_order_ready_output_artifacts_zero", len(report.get("order_ready_output_artifacts") or []), 0)
    fail_if(len(report.get("blockers") or []) == 0, failures, "source_blockers_present", len(report.get("blockers") or []), ">0")


def workstream_acceptance_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "workstream_acceptance_boundary_audit_rows": 1,
        "total_streams": report.get("total_streams"),
        "acceptance_decision_rows": report.get("acceptance_decision_rows"),
        "human_accepted_streams": report.get("human_accepted_streams"),
        "accepted_streams": report.get("accepted_streams"),
        "technical_ready_streams": sum(1 for gate in report.get("gates") or [] if gate.get("technical_ready") is True),
        "validator_decision_rows": validation.get("decision_rows"),
        "validator_valid_rows": validation.get("valid_rows"),
        "missing_stream_decision_rows": len(validation.get("missing_stream_decisions") or []),
        "unaccepted_stream_rows": len(validation.get("unaccepted_streams") or []),
    }


def workstream_acceptance_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    gates = report.get("gates") or []
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("total_streams") != len(gates), failures, "source_total_streams_bound", report.get("total_streams"), len(gates))
    fail_if(report.get("acceptance_decision_rows") != validation.get("decision_rows"), failures, "source_decision_rows_bound", report.get("acceptance_decision_rows"), validation.get("decision_rows"))
    fail_if(report.get("human_accepted_streams") != 0, failures, "source_human_accepted_streams_zero", report.get("human_accepted_streams"), 0)
    fail_if(report.get("accepted_streams") != 0, failures, "source_accepted_streams_zero", report.get("accepted_streams"), 0)
    fail_if(report.get("all_accepted") is not False, failures, "source_all_accepted_false", report.get("all_accepted"), False)
    fail_if(any(gate.get("accepted") is True or gate.get("human_accepted") is True for gate in gates), failures, "source_gate_acceptance_rows_zero", "nonzero", 0)
    fail_if(validation.get("local_only") is not True, failures, "source_validation_local_only_true", validation.get("local_only"), True)
    fail_if(validation.get("valid_rows", 0) + validation.get("invalid_rows", 0) != validation.get("decision_rows"), failures, "source_validation_decision_partition_exact", {"decision_rows": validation.get("decision_rows"), "valid_rows": validation.get("valid_rows"), "invalid_rows": validation.get("invalid_rows")}, "valid + invalid = decision rows")
    fail_if(validation.get("all_streams_decided") is not False, failures, "source_validation_all_streams_decided_false", validation.get("all_streams_decided"), False)
    fail_if(validation.get("all_streams_accepted") is not False, failures, "source_validation_all_streams_accepted_false", validation.get("all_streams_accepted"), False)
    for key in ("accepted_streams", "accepted_for_model_claim_streams", "accepted_for_customer_delivery_streams", "accepted_for_experiment_submission_streams"):
        fail_if(len(validation.get(key) or []) != 0, failures, f"source_validation_{key}_zero", len(validation.get(key) or []), 0)
    fail_if(len(validation.get("missing_stream_decisions") or []) == 0, failures, "source_validation_missing_decisions_present", len(validation.get("missing_stream_decisions") or []), ">0")


def sequence_ip_fto_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sequence_ip_fto_boundary_audit_rows": 1,
        "packet_rows": report.get("packet_rows"),
        "decision_rows": report.get("decision_rows"),
        "valid_rows": report.get("valid_rows"),
        "invalid_rows": report.get("invalid_rows"),
        "approved_for_internal_use_rows": report.get("approved_for_internal_use_rows"),
        "approved_for_customer_delivery_rows": report.get("approved_for_customer_delivery_rows"),
        "missing_delivery_decision_rows": len(report.get("missing_delivery_decisions") or []),
    }


def sequence_ip_fto_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    for key in ("decision_rows", "valid_rows", "invalid_rows", "approved_for_internal_use_rows", "approved_for_customer_delivery_rows"):
        fail_if(report.get(key) != 0, failures, f"source_{key}_zero", report.get(key), 0)
    fail_if(report.get("all_packet_candidates_decided_for_delivery") is not False, failures, "source_all_packet_candidates_decided_false", report.get("all_packet_candidates_decided_for_delivery"), False)
    fail_if(report.get("ready_for_customer_delivery") is not False, failures, "source_ready_for_customer_delivery_false", report.get("ready_for_customer_delivery"), False)
    fail_if(report.get("packet_rows") != len(report.get("missing_delivery_decisions") or []), failures, "source_missing_delivery_rows_bound", report.get("packet_rows"), len(report.get("missing_delivery_decisions") or []))


def model_claim_consistency_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model_claim_consistency_boundary_audit_rows": 1,
        "strict_rows": report.get("strict_rows"),
        "claim_eligible_rows": report.get("claim_eligible_rows"),
        "strict_msa_site_feature_rows": report.get("strict_msa_site_feature_rows"),
        "promotion_audit_rows": report.get("promotion_audit_rows"),
        "promotion_automatic_rows": report.get("promotion_automatic_rows"),
        "blocked_claim_count": report.get("claim_matrix_blocked_claims"),
        "consistency_failure_count": len(report.get("failures") or []),
        "consistency_warning_count": len(report.get("warnings") or []),
        "consistency_success": report.get("success"),
    }


def model_claim_consistency_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    for key in ("strict_rows", "claim_eligible_rows", "strict_msa_site_feature_rows", "promotion_automatic_rows"):
        fail_if(report.get(key) != 0, failures, f"source_{key}_zero", report.get(key), 0)
    fail_if(report.get("promotion_validation_success") is not True, failures, "source_promotion_validation_success_true", report.get("promotion_validation_success"), True)
    fail_if(report.get("claim_matrix_blocked_claims", 0) <= 0, failures, "source_blocked_claims_present", report.get("claim_matrix_blocked_claims"), ">0")
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def external_registry_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    records = report.get("records") or []
    return {
        "external_registry_boundary_audit_rows": 1,
        "registry_source_rows": report.get("source_rows"),
        "registry_valid_rows": report.get("valid_rows"),
        "registry_invalid_rows": report.get("invalid_rows"),
        "registry_ready_source_count": report.get("ready_sources"),
        "registry_not_ready_source_count": sum(1 for record in records if record.get("ready_for_training_or_delivery") is not True),
        "registry_blocker_category_count": len(report.get("blocker_counts") or {}),
        "registry_blocker_observation_count": sum(int(value) for value in (report.get("blocker_counts") or {}).values()),
    }


def external_registry_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    records = report.get("records") or []
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("source_rows") != len(records), failures, "source_rows_bound", report.get("source_rows"), len(records))
    fail_if(report.get("valid_rows") != len(records), failures, "source_valid_rows_bound", report.get("valid_rows"), len(records))
    fail_if(report.get("invalid_rows") != 0, failures, "source_invalid_rows_zero", report.get("invalid_rows"), 0)
    fail_if(report.get("ready_sources") != 0, failures, "source_ready_sources_zero", report.get("ready_sources"), 0)
    fail_if(report.get("ready") is not False, failures, "source_ready_false", report.get("ready"), False)
    fail_if(any(record.get("valid") is not True for record in records), failures, "source_records_valid_true", records, "all true")
    fail_if(any(record.get("ready_for_training_or_delivery") is not False for record in records), failures, "source_records_not_ready", records, "all false")
    fail_if(any(not record.get("blockers") for record in records), failures, "source_record_blockers_present", records, "all nonempty")
    fail_if(len(report.get("blocker_counts") or {}) == 0, failures, "source_blocker_categories_present", report.get("blocker_counts"), "nonempty")


def operator_status_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    status = report.get("status") or {}
    return {
        "operator_status_boundary_audit_rows": 1,
        "operator_action_rows": report.get("action_rows"),
        "operator_completed_action_rows": report.get("completed_action_rows"),
        "operator_open_action_rows": int(report.get("action_rows") or 0) - int(report.get("completed_action_rows") or 0),
        "operator_blocker_count": len(report.get("blockers") or []),
        "operator_external_license_valid_rows": (status.get("external_license_review") or {}).get("valid_rows"),
        "operator_external_license_customer_delivery_rows": (status.get("external_license_review") or {}).get("approved_for_customer_delivery_rows"),
        "operator_biosecurity_decision_rows": (status.get("biosecurity_screening") or {}).get("decision_rows"),
        "operator_workstream_accepted_rows": (status.get("workstream_acceptance") or {}).get("accepted_streams"),
        "operator_completion_decision_rows": (status.get("operator_action_completion") or {}).get("decision_rows"),
    }


def operator_status_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    status = report.get("status") or {}
    external = status.get("external_license_review") or {}
    biosecurity = status.get("biosecurity_screening") or {}
    acceptance = status.get("workstream_acceptance") or {}
    completion = status.get("operator_action_completion") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("ready") is not False, failures, "source_ready_false", report.get("ready"), False)
    fail_if(report.get("completed_action_rows") != 0, failures, "source_completed_actions_zero", report.get("completed_action_rows"), 0)
    fail_if(len(report.get("blockers") or []) == 0, failures, "source_blockers_present", report.get("blockers"), "nonempty")
    fail_if(external.get("approved_for_training_rows") != 0, failures, "source_external_training_rows_zero", external.get("approved_for_training_rows"), 0)
    fail_if(external.get("approved_for_customer_delivery_rows") != 0, failures, "source_external_delivery_rows_zero", external.get("approved_for_customer_delivery_rows"), 0)
    fail_if(external.get("ready_for_customer_delivery") is not False, failures, "source_external_delivery_false", external.get("ready_for_customer_delivery"), False)
    fail_if(biosecurity.get("ready_for_ordering") is not False, failures, "source_biosecurity_ordering_false", biosecurity.get("ready_for_ordering"), False)
    fail_if(acceptance.get("accepted_streams") != 0, failures, "source_accepted_streams_zero", acceptance.get("accepted_streams"), 0)
    fail_if(acceptance.get("all_accepted") is not False, failures, "source_all_accepted_false", acceptance.get("all_accepted"), False)
    fail_if(completion.get("completed_rows") != 0, failures, "source_completion_rows_zero", completion.get("completed_rows"), 0)
    fail_if(completion.get("all_actions_completed") is not False, failures, "source_all_actions_completed_false", completion.get("all_actions_completed"), False)


def human_review_consistency_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "human_review_consistency_boundary_audit_rows": 1,
        "human_review_consistency_closeout_rows": report.get("closeout_rows"),
        "human_review_consistency_launch_rows": report.get("launch_rows"),
        "human_review_consistency_open_closeout_rows": int(report.get("closeout_rows") or 0) - int(report.get("completion_ready_rows") or 0),
        "human_review_consistency_completion_count": report.get("completion_ready_rows"),
        "human_review_consistency_prepared_packet_rows": report.get("total_prepared_packet_rows"),
        "human_review_consistency_formal_row_count": report.get("total_formal_decision_rows"),
        "human_review_consistency_failure_count": len(report.get("failures") or []),
        "human_review_consistency_source_success": report.get("success"),
    }


def human_review_consistency_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(report.get("closeout_rows") != report.get("launch_rows"), failures, "source_closeout_launch_rows_match", report.get("closeout_rows"), report.get("launch_rows"))
    fail_if(report.get("completion_ready_rows") != 0, failures, "source_completion_ready_zero", report.get("completion_ready_rows"), 0)
    fail_if(report.get("customer_ready") is not False, failures, "source_customer_ready_false", report.get("customer_ready"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def claim_promotion_decision_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "claim_promotion_boundary_audit_rows": 1,
        "claim_promotion_target_count": report.get("target_claim_rows"),
        "claim_promotion_template_count": report.get("template_rows"),
        "claim_promotion_decision_count": report.get("decision_rows"),
        "claim_promotion_valid_count": report.get("valid_rows"),
        "claim_promotion_approved_count": report.get("approved_rows"),
        "claim_promotion_missing_decision_count": len(report.get("missing_promotion_decisions") or []),
        "claim_promotion_required_evidence_count": report.get("required_evidence_artifact_count"),
        "claim_promotion_required_validation_count": report.get("required_validation_report_count"),
        "claim_promotion_failure_count": report.get("failure_count"),
    }


def claim_promotion_decision_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    target_claim_ids = report.get("target_claim_ids") or []
    missing = report.get("missing_promotion_decisions") or []
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("template_rows") != len(target_claim_ids), failures, "source_template_target_count_match", report.get("template_rows"), len(target_claim_ids))
    fail_if(report.get("decision_rows") != 0, failures, "source_decision_rows_zero", report.get("decision_rows"), 0)
    fail_if(report.get("valid_rows") != 0, failures, "source_valid_rows_zero", report.get("valid_rows"), 0)
    fail_if(report.get("approved_rows") != 0, failures, "source_approved_rows_zero", report.get("approved_rows"), 0)
    fail_if(sorted(missing) != sorted(target_claim_ids), failures, "source_all_target_decisions_missing", sorted(missing), sorted(target_claim_ids))
    fail_if(report.get("all_high_risk_decisions_present") is not False, failures, "source_high_risk_decisions_false", report.get("all_high_risk_decisions_present"), False)
    fail_if(report.get("all_high_risk_claims_promoted") is not False, failures, "source_high_risk_promotions_false", report.get("all_high_risk_claims_promoted"), False)
    fail_if(report.get("ready_for_claim_promotion") is not False, failures, "source_promotion_ready_false", report.get("ready_for_claim_promotion"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def claim_policy_current_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "claim_policy_current_boundary_audit_rows": 1,
        "claim_policy_current_failure_count": report.get("failure_count"),
        "claim_policy_current_source_parity_success": report.get("source_parity_success"),
        "claim_policy_current_lock_acquired": report.get("current_lock_acquired"),
        "claim_policy_current_atomic_commit": report.get("current_atomic_commit"),
        "claim_policy_current_policy_anchor_present": bool(report.get("policy_anchor_report_sha256")),
        "claim_policy_current_receipt_present": bool(report.get("receipt_sha256")),
        "claim_policy_current_source_success": report.get("success"),
    }


def claim_policy_current_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(report.get("source_parity_success") is not True, failures, "source_parity_success_true", report.get("source_parity_success"), True)
    fail_if(report.get("current_lock_acquired") is not True, failures, "source_lock_acquired_true", report.get("current_lock_acquired"), True)
    fail_if(report.get("current_atomic_commit") is not True, failures, "source_atomic_commit_true", report.get("current_atomic_commit"), True)
    fail_if(not report.get("policy_anchor_report_sha256"), failures, "source_policy_anchor_present", report.get("policy_anchor_report_sha256"), "nonempty")
    fail_if(not report.get("receipt_sha256"), failures, "source_receipt_present", report.get("receipt_sha256"), "nonempty")
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def structure_feature_operator_packet_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "structure_feature_operator_packet_boundary_audit_rows": 1,
        "structure_feature_packet_rows": report.get("packet_rows"),
        "structure_feature_valid_rows": report.get("valid_rows"),
        "structure_feature_invalid_rows": report.get("invalid_rows"),
        "structure_feature_completion_ready_rows": report.get("completion_ready_rows"),
        "structure_feature_requires_human_input_rows": report.get("requires_human_input_rows"),
        "structure_feature_all_packets_valid": report.get("all_operator_packets_valid"),
        "structure_feature_graph_fallback_used": report.get("graph_validation_report_compatibility_fallback_used"),
    }


def structure_feature_operator_packet_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("all_operator_packets_valid") is not True, failures, "source_all_packets_valid_true", report.get("all_operator_packets_valid"), True)
    fail_if(report.get("valid_rows") != report.get("packet_rows"), failures, "source_valid_packet_rows_match", report.get("valid_rows"), report.get("packet_rows"))
    fail_if(report.get("invalid_rows") != 0, failures, "source_invalid_rows_zero", report.get("invalid_rows"), 0)
    fail_if(report.get("completion_ready_rows") != 0, failures, "source_completion_ready_zero", report.get("completion_ready_rows"), 0)
    fail_if(report.get("requires_human_input_rows") != report.get("packet_rows"), failures, "source_requires_human_input_all_rows", report.get("requires_human_input_rows"), report.get("packet_rows"))
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def wet_lab_hard_gate_operator_packet_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "wet_lab_hard_gate_operator_packet_boundary_audit_rows": 1,
        "wet_lab_hard_gate_packet_rows": report.get("packet_rows"),
        "wet_lab_hard_gate_expected_packet_rows": report.get("expected_packet_rows"),
        "wet_lab_hard_gate_completion_ready_rows": report.get("completion_ready_rows"),
        "wet_lab_hard_gate_failure_count": report.get("failure_count"),
        "wet_lab_hard_gate_contract_valid": report.get("contract_valid"),
        "wet_lab_hard_gate_markdown_matches_current_packets": report.get("markdown_matches_current_packets"),
        "wet_lab_hard_gate_report_matches_current_packets": report.get("report_matches_current_packets"),
        "wet_lab_hard_gate_status": report.get("status"),
    }


def wet_lab_hard_gate_operator_packet_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("contract_valid") is not True, failures, "source_contract_valid_true", report.get("contract_valid"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("packet_rows") != report.get("expected_packet_rows"), failures, "source_expected_packet_rows_match", report.get("packet_rows"), report.get("expected_packet_rows"))
    fail_if(report.get("completion_ready_rows") != 0, failures, "source_completion_ready_zero", report.get("completion_ready_rows"), 0)
    fail_if(report.get("status") != "blocked", failures, "source_status_blocked", report.get("status"), "blocked")
    fail_if(report.get("markdown_matches_current_packets") is not True, failures, "source_markdown_current_true", report.get("markdown_matches_current_packets"), True)
    fail_if(report.get("report_matches_current_packets") is not True, failures, "source_report_current_true", report.get("report_matches_current_packets"), True)
    fail_if(report.get("safe_for_feedback_intake") is not False, failures, "source_safe_for_feedback_intake_false", report.get("safe_for_feedback_intake"), False)
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def benchmark_hard_gate_operator_packet_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "benchmark_hard_gate_operator_packet_boundary_audit_rows": 1,
        "benchmark_hard_gate_packet_rows": report.get("packet_rows"),
        "benchmark_hard_gate_expected_packet_rows": report.get("expected_packet_rows"),
        "benchmark_hard_gate_completion_ready_rows": report.get("completion_ready_rows"),
        "benchmark_hard_gate_failure_count": report.get("failure_count"),
        "benchmark_hard_gate_contract_valid": report.get("contract_valid"),
        "benchmark_hard_gate_markdown_matches_current_packets": report.get("markdown_matches_current_packets"),
        "benchmark_hard_gate_report_summary_matches_packets": report.get("report_summary_matches_packets"),
        "benchmark_hard_gate_status": report.get("status"),
    }


def benchmark_hard_gate_operator_packet_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("contract_valid") is not True, failures, "source_contract_valid_true", report.get("contract_valid"), True)
    fail_if(report.get("failure_count") != 0, failures, "source_failure_count_zero", report.get("failure_count"), 0)
    fail_if(report.get("packet_rows") != report.get("expected_packet_rows"), failures, "source_expected_packet_rows_match", report.get("packet_rows"), report.get("expected_packet_rows"))
    fail_if(report.get("completion_ready_rows") != 0, failures, "source_completion_ready_zero", report.get("completion_ready_rows"), 0)
    fail_if(report.get("status") != "blocked", failures, "source_status_blocked", report.get("status"), "blocked")
    fail_if(report.get("markdown_matches_current_packets") is not True, failures, "source_markdown_current_true", report.get("markdown_matches_current_packets"), True)
    fail_if(report.get("report_summary_matches_packets") is not True, failures, "source_report_summary_match_true", report.get("report_summary_matches_packets"), True)
    fail_if(report.get("manifest_update_allowed") is not False, failures, "source_manifest_update_allowed_false", report.get("manifest_update_allowed"), False)
    fail_if(report.get("safe_pipeline_integration_allowed") is not False, failures, "source_pipeline_integration_false", report.get("safe_pipeline_integration_allowed"), False)
    fail_if(report.get("write_benchmark_score_cache_intake_allowed") is not False, failures, "source_score_cache_write_false", report.get("write_benchmark_score_cache_intake_allowed"), False)
    fail_if(report.get("ready_for_model_claim") is not False, failures, "source_ready_for_model_claim_false", report.get("ready_for_model_claim"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def substrate_fit_hard_gate_operator_packet_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "substrate_fit_hard_gate_operator_packet_boundary_audit_rows": 1,
        "substrate_fit_hard_gate_packet_rows": report.get("packet_rows"),
        "substrate_fit_hard_gate_valid_rows": report.get("valid_rows"),
        "substrate_fit_hard_gate_invalid_rows": report.get("invalid_rows"),
        "substrate_fit_hard_gate_completion_ready_rows": report.get("completion_ready_rows"),
        "substrate_fit_hard_gate_all_packets_valid": report.get("all_operator_packets_valid"),
        "substrate_fit_hard_gate_report_error_count": len(report.get("report_errors") or []),
    }


def substrate_fit_hard_gate_operator_packet_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("all_operator_packets_valid") is not True, failures, "source_all_packets_valid_true", report.get("all_operator_packets_valid"), True)
    fail_if(report.get("valid_rows") != report.get("packet_rows"), failures, "source_valid_packet_rows_match", report.get("valid_rows"), report.get("packet_rows"))
    fail_if(report.get("invalid_rows") != 0, failures, "source_invalid_rows_zero", report.get("invalid_rows"), 0)
    fail_if(report.get("completion_ready_rows") != 0, failures, "source_completion_ready_zero", report.get("completion_ready_rows"), 0)
    fail_if(len(report.get("report_errors") or []) != 0, failures, "source_report_errors_empty", len(report.get("report_errors") or []), 0)
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def review_draft_formal_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "review_draft_formal_boundary_audit_rows": 1,
        "review_draft_total_rows": report.get("total_review_draft_rows"),
        "review_draft_total_formal_decision_rows": report.get("total_formal_decision_rows"),
        "review_draft_rows_counted_as_formal_decisions": report.get("draft_rows_counted_as_formal_decisions"),
        "review_draft_failure_count": len(report.get("failures") or []),
        "review_draft_source_success": report.get("success"),
        "review_draft_file_group_count": len(report.get("draft_files") or {}),
        "formal_decision_file_group_count": len(report.get("formal_files") or {}),
    }


def review_draft_formal_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(int(report.get("total_review_draft_rows") or 0) <= 0, failures, "source_review_drafts_present", report.get("total_review_draft_rows"), ">0")
    fail_if(int(report.get("total_formal_decision_rows") or 0) <= 0, failures, "source_formal_decisions_observed", report.get("total_formal_decision_rows"), ">0")
    fail_if(report.get("draft_rows_counted_as_formal_decisions") != 0, failures, "source_drafts_not_formal", report.get("draft_rows_counted_as_formal_decisions"), 0)
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def activity_risk_formal_label_decision_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "activity_risk_formal_label_boundary_audit_rows": 1,
        "activity_risk_formal_decision_rows": report.get("formal_decision_rows"),
        "activity_risk_label_rows_created": report.get("activity_risk_label_rows_created"),
        "activity_risk_source_numeric_rows": report.get("source_numeric_activity_rows"),
        "activity_risk_authorized_numeric_rows": report.get("authorized_numeric_activity_source_rows"),
        "activity_risk_unauthorized_numeric_rows": report.get("unauthorized_numeric_activity_source_rows"),
        "activity_risk_ready_for_training_import_rows": report.get("ready_for_training_import_rows"),
        "activity_risk_replicate_rows_counted_for_training": report.get("replicate_rows_counted_for_training"),
        "activity_risk_source_safe_for_training_import": report.get("safe_for_training_import"),
        "activity_risk_source_success": report.get("success"),
    }


def activity_risk_formal_label_decision_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(report.get("formal_decision_rows") != report.get("activity_risk_label_rows_created"), failures, "source_formal_label_rows_match", report.get("formal_decision_rows"), report.get("activity_risk_label_rows_created"))
    fail_if(report.get("formal_decision_rows") != report.get("ready_for_training_import_rows"), failures, "source_ready_rows_match_formal_rows", report.get("ready_for_training_import_rows"), report.get("formal_decision_rows"))
    fail_if(report.get("authorized_numeric_activity_source_rows") != report.get("source_numeric_activity_rows"), failures, "source_numeric_rows_authorized", report.get("authorized_numeric_activity_source_rows"), report.get("source_numeric_activity_rows"))
    fail_if(report.get("unauthorized_numeric_activity_source_rows") != 0, failures, "source_unauthorized_numeric_zero", report.get("unauthorized_numeric_activity_source_rows"), 0)
    fail_if(report.get("replicate_rows_counted_for_training") != 0, failures, "source_replicate_rows_zero", report.get("replicate_rows_counted_for_training"), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def activity_risk_lineage_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "activity_risk_lineage_boundary_audit_rows": 1,
        "activity_risk_lineage_ledger_rows": report.get("ledger_rows"),
        "activity_risk_lineage_expected_formal_decision_rows": report.get("expected_formal_decision_rows"),
        "activity_risk_lineage_threshold_label_rows": report.get("activity_threshold_label_rows"),
        "activity_risk_lineage_threshold_group_count": report.get("activity_threshold_group_count"),
        "activity_risk_lineage_replicate_count": report.get("activity_threshold_replicate_count"),
        "activity_risk_lineage_training_import_eligible_rows_from_contract": report.get("training_import_eligible_rows_from_contract"),
        "activity_risk_lineage_training_execution_allowed": report.get("training_execution_allowed"),
        "activity_risk_lineage_source_success": report.get("success"),
    }


def activity_risk_lineage_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(report.get("ledger_rows") != report.get("expected_formal_decision_rows"), failures, "source_ledger_rows_match_expected_decisions", report.get("ledger_rows"), report.get("expected_formal_decision_rows"))
    fail_if(report.get("activity_threshold_label_rows") != report.get("ledger_rows"), failures, "source_threshold_rows_match_ledger", report.get("activity_threshold_label_rows"), report.get("ledger_rows"))
    fail_if(report.get("activity_threshold_replicate_count") != 0, failures, "source_replicate_count_zero", report.get("activity_threshold_replicate_count"), 0)
    fail_if(report.get("training_import_eligible_rows_from_contract") != report.get("ledger_rows"), failures, "source_import_eligible_rows_match_ledger", report.get("training_import_eligible_rows_from_contract"), report.get("ledger_rows"))
    fail_if(report.get("training_execution_allowed") is not False, failures, "source_training_execution_false", report.get("training_execution_allowed"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def feedback_training_import_semantic_guard_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_supported = report.get("source_supported_counts") or {}
    observed = report.get("observed_guard_counts") or {}
    return {
        "feedback_training_guard_boundary_audit_rows": 1,
        "feedback_training_guard_qualitative_feedback_eligible": report.get("qualitative_feedback_eligible"),
        "feedback_training_guard_numeric_training_import_eligible": report.get("numeric_training_import_eligible"),
        "feedback_training_guard_strict_supervised_rows": report.get("strict_supervised_rows"),
        "feedback_training_guard_claim_eligible_rows": report.get("claim_eligible_rows"),
        "feedback_training_guard_source_supported_numeric_rows": source_supported.get("numeric_training_import_eligible"),
        "feedback_training_guard_observed_numeric_rows": observed.get("numeric_training_import_eligible"),
        "feedback_training_guard_source_safe_for_training_import": report.get("safe_for_training_import"),
        "feedback_training_guard_source_success": report.get("success"),
    }


def feedback_training_import_semantic_guard_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    source_supported = report.get("source_supported_counts") or {}
    observed = report.get("observed_guard_counts") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(report.get("numeric_training_import_eligible") != source_supported.get("numeric_training_import_eligible"), failures, "source_numeric_supported_bound", report.get("numeric_training_import_eligible"), source_supported.get("numeric_training_import_eligible"))
    fail_if(report.get("numeric_training_import_eligible") != observed.get("numeric_training_import_eligible"), failures, "source_numeric_observed_bound", report.get("numeric_training_import_eligible"), observed.get("numeric_training_import_eligible"))
    fail_if(report.get("strict_supervised_rows") != 0, failures, "source_strict_supervised_zero", report.get("strict_supervised_rows"), 0)
    fail_if(report.get("claim_eligible_rows") != 0, failures, "source_claim_eligible_zero", report.get("claim_eligible_rows"), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def wet_lab_feedback_import_reconciliation_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = report.get("counts") or {}
    return {
        "wet_lab_import_reconciliation_boundary_audit_rows": 1,
        "wet_lab_import_reconciliation_contract_training_import_eligible_rows": counts.get("contract_training_import_eligible_rows"),
        "wet_lab_import_reconciliation_local_feedback_numeric_training_eligible_rows": counts.get("local_feedback_numeric_training_eligible_rows"),
        "wet_lab_import_reconciliation_duplicate_safe_to_append_rows": counts.get("duplicate_safe_to_append_rows"),
        "wet_lab_import_reconciliation_duplicate_training_import_from_apply_plan_rows": counts.get("duplicate_training_import_from_apply_plan_rows"),
        "wet_lab_import_reconciliation_model_quality_training_import_eligible_rows": counts.get("model_quality_training_import_eligible_rows"),
        "wet_lab_import_reconciliation_claim_eligible_rows": counts.get("claim_eligible_rows"),
        "wet_lab_import_reconciliation_source_success": report.get("success"),
    }


def wet_lab_feedback_import_reconciliation_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    counts = report.get("counts") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(counts.get("contract_training_import_eligible_rows") != counts.get("local_feedback_numeric_training_eligible_rows"), failures, "source_contract_local_numeric_match", counts.get("contract_training_import_eligible_rows"), counts.get("local_feedback_numeric_training_eligible_rows"))
    fail_if(counts.get("duplicate_safe_to_append_rows") != 0, failures, "source_duplicate_append_zero", counts.get("duplicate_safe_to_append_rows"), 0)
    fail_if(counts.get("duplicate_training_import_from_apply_plan_rows") != 0, failures, "source_duplicate_apply_import_zero", counts.get("duplicate_training_import_from_apply_plan_rows"), 0)
    fail_if(counts.get("model_quality_training_import_eligible_rows") != counts.get("contract_training_import_eligible_rows"), failures, "source_model_quality_import_bound_to_contract", counts.get("model_quality_training_import_eligible_rows"), counts.get("contract_training_import_eligible_rows"))
    fail_if(counts.get("claim_eligible_rows") != 0, failures, "source_claim_eligible_zero", counts.get("claim_eligible_rows"), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def positive_claim_gate_quarantine_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "positive_claim_gate_quarantine_boundary_audit_rows": 1,
        "positive_claim_gate_scanned_report_count": report.get("scanned_report_count"),
        "positive_claim_gate_risky_true_hit_count": report.get("risky_true_hit_count"),
        "positive_claim_gate_allowlisted_true_hit_count": report.get("allowlisted_true_hit_count"),
        "positive_claim_gate_disallowed_true_hit_count": report.get("disallowed_true_hit_count"),
        "positive_claim_gate_safe_for_training_pipeline": report.get("safe_for_training_pipeline"),
        "positive_claim_gate_source_success": report.get("success"),
        "positive_claim_gate_failure_count": len(report.get("failures") or []),
    }


def positive_claim_gate_quarantine_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    fail_if(report.get("risky_true_hit_count") != report.get("allowlisted_true_hit_count"), failures, "source_risky_hits_allowlisted", report.get("risky_true_hit_count"), report.get("allowlisted_true_hit_count"))
    fail_if(report.get("disallowed_true_hit_count") != 0, failures, "source_disallowed_true_zero", report.get("disallowed_true_hit_count"), 0)
    fail_if(report.get("safe_for_training_pipeline") is not True, failures, "source_safe_for_training_pipeline_true", report.get("safe_for_training_pipeline"), True)
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def activity_risk_training_import_label_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "activity_risk_import_label_boundary_audit_rows": 1,
        "activity_risk_import_label_rows": report.get("training_import_label_rows"),
        "activity_risk_import_written_rows": report.get("training_import_written_rows"),
        "activity_risk_import_source_decision_rows": report.get("source_decision_rows"),
        "activity_risk_import_source_numeric_feedback_rows": report.get("source_numeric_feedback_rows"),
        "activity_risk_import_source_authorization_rows": report.get("source_authorization_rows"),
        "activity_risk_import_independent_group_count": report.get("independent_group_count"),
        "activity_risk_import_explicit_replicate_count": report.get("explicit_replicate_count"),
        "activity_risk_import_replicate_rows_counted": report.get("replicate_rows_counted_for_training"),
        "activity_risk_import_source_safe_for_training_import": report.get("safe_for_training_import"),
        "activity_risk_import_training_execution_allowed": report.get("training_execution_allowed"),
        "activity_risk_import_validation_success": validation.get("success"),
    }


def activity_risk_training_import_label_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("training_import_label_rows") != validation.get("training_import_label_rows"), failures, "source_validation_label_rows_bound", report.get("training_import_label_rows"), validation.get("training_import_label_rows"))
    fail_if(report.get("training_import_written_rows") != validation.get("training_import_written_rows"), failures, "source_validation_written_rows_bound", report.get("training_import_written_rows"), validation.get("training_import_written_rows"))
    fail_if(report.get("training_import_label_rows") != report.get("source_decision_rows"), failures, "source_label_rows_bound_to_decisions", report.get("training_import_label_rows"), report.get("source_decision_rows"))
    fail_if(report.get("training_import_written_rows") != report.get("training_import_label_rows"), failures, "source_written_rows_match_labels", report.get("training_import_written_rows"), report.get("training_import_label_rows"))
    fail_if(report.get("replicate_rows_counted_for_training") != 0, failures, "source_replicate_rows_zero", report.get("replicate_rows_counted_for_training"), 0)
    fail_if(report.get("training_execution_allowed") is not False, failures, "source_training_execution_false", report.get("training_execution_allowed"), False)
    fail_if(validation.get("training_execution_allowed") is not False, failures, "source_validation_training_execution_false", validation.get("training_execution_allowed"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def activity_risk_label_replicate_preflight_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "activity_risk_replicate_preflight_boundary_audit_rows": 1,
        "activity_risk_replicate_preflight_rows": report.get("preflight_rows"),
        "activity_risk_replicate_decision_template_rows": report.get("decision_template_rows"),
        "activity_risk_replicate_formal_decision_rows": report.get("formal_decision_rows"),
        "activity_risk_replicate_label_rows_created": report.get("activity_risk_label_rows_created"),
        "activity_risk_replicate_ready_for_training_import_rows": report.get("ready_for_training_import_rows"),
        "activity_risk_replicate_training_import_written_rows": report.get("training_import_written_rows"),
        "activity_risk_replicate_rows_counted_for_training": report.get("replicate_rows_counted_for_training"),
        "activity_risk_replicate_source_numeric_activity_rows": report.get("source_numeric_activity_rows"),
        "activity_risk_replicate_validation_success": validation.get("success"),
    }


def activity_risk_label_replicate_preflight_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("preflight_rows") != validation.get("preflight_rows"), failures, "source_validation_preflight_rows_bound", report.get("preflight_rows"), validation.get("preflight_rows"))
    fail_if(report.get("decision_template_rows") != validation.get("decision_template_rows"), failures, "source_validation_template_rows_bound", report.get("decision_template_rows"), validation.get("decision_template_rows"))
    fail_if(report.get("preflight_rows") != report.get("decision_template_rows"), failures, "source_preflight_template_rows_match", report.get("preflight_rows"), report.get("decision_template_rows"))
    fail_if(report.get("formal_decision_rows") != 0, failures, "source_formal_decision_rows_zero", report.get("formal_decision_rows"), 0)
    fail_if(report.get("activity_risk_label_rows_created") != 0, failures, "source_label_rows_created_zero", report.get("activity_risk_label_rows_created"), 0)
    fail_if(report.get("ready_for_training_import_rows") != 0, failures, "source_ready_rows_zero", report.get("ready_for_training_import_rows"), 0)
    fail_if(report.get("training_import_written_rows") != 0, failures, "source_training_import_written_zero", report.get("training_import_written_rows"), 0)
    fail_if(report.get("replicate_rows_counted_for_training") != 0, failures, "source_replicate_rows_zero", report.get("replicate_rows_counted_for_training"), 0)
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def feature_coverage_by_head_group_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "feature_coverage_by_head_group_boundary_audit_rows": 1,
        "feature_coverage_by_head_group_coverage_rows": report.get("coverage_row_count"),
        "feature_coverage_by_head_group_feature_rows": report.get("source_feature_rows"),
        "feature_coverage_by_head_group_protein_group_count": report.get("protein_group_count"),
        "feature_coverage_by_head_group_training_label_source_rows": report.get("source_training_label_source_rows"),
        "feature_coverage_by_head_group_feature_rows_counted_as_labels": report.get("source_feature_rows_counted_as_labels"),
        "feature_coverage_by_head_group_five_head_ready_head_count": report.get("five_head_ready_head_count"),
        "feature_coverage_by_head_group_training_execution_allowed": report.get("five_head_training_execution_allowed"),
        "feature_coverage_by_head_group_validation_success": validation.get("success"),
    }


def feature_coverage_by_head_group_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("coverage_row_count") != validation.get("coverage_rows"), failures, "source_validation_coverage_rows_bound", report.get("coverage_row_count"), validation.get("coverage_rows"))
    fail_if(report.get("source_feature_rows") != validation.get("feature_rows"), failures, "source_validation_feature_rows_bound", report.get("source_feature_rows"), validation.get("feature_rows"))
    fail_if(report.get("source_training_label_source_rows") != 0, failures, "source_training_label_source_rows_zero", report.get("source_training_label_source_rows"), 0)
    fail_if(report.get("source_feature_rows_counted_as_labels") != 0, failures, "source_features_counted_as_labels_zero", report.get("source_feature_rows_counted_as_labels"), 0)
    fail_if(report.get("five_head_ready_head_count") != 0, failures, "source_ready_head_count_zero", report.get("five_head_ready_head_count"), 0)
    fail_if(report.get("five_head_training_execution_allowed") is not False, failures, "source_training_execution_false", report.get("five_head_training_execution_allowed"), False)
    fail_if(report.get("training_import_allowed") is not False, failures, "source_training_import_allowed_false", report.get("training_import_allowed"), False)
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(report.get("production_execution_allowed") is not False, failures, "source_production_execution_false", report.get("production_execution_allowed"), False)


def feature_coverage_gap_queue_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "feature_coverage_gap_queue_boundary_audit_rows": 1,
        "feature_coverage_gap_queue_gap_count": report.get("gap_count"),
        "feature_coverage_gap_queue_source_coverage_rows": report.get("source_coverage_rows"),
        "feature_coverage_gap_queue_training_label_source_rows": report.get("training_label_source_rows"),
        "feature_coverage_gap_queue_feature_rows_counted_as_labels": report.get("feature_rows_counted_as_labels"),
        "feature_coverage_gap_queue_validation_success": validation.get("success"),
    }


def feature_coverage_gap_queue_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("gap_count") != validation.get("gap_count"), failures, "source_validation_gap_count_bound", report.get("gap_count"), validation.get("gap_count"))
    fail_if(report.get("gap_count") != validation.get("expected_gap_count"), failures, "source_expected_gap_count_bound", report.get("gap_count"), validation.get("expected_gap_count"))
    fail_if(report.get("training_label_source_rows") != 0, failures, "source_training_label_source_rows_zero", report.get("training_label_source_rows"), 0)
    fail_if(report.get("feature_rows_counted_as_labels") != 0, failures, "source_features_counted_as_labels_zero", report.get("feature_rows_counted_as_labels"), 0)
    fail_if(report.get("training_import_allowed") is not False, failures, "source_training_import_allowed_false", report.get("training_import_allowed"), False)
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(report.get("production_execution_allowed") is not False, failures, "source_production_execution_false", report.get("production_execution_allowed"), False)


def feature_label_boundary_quarantine_audit_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "feature_label_boundary_quarantine_audit_boundary_audit_rows": 1,
        "feature_label_boundary_quarantine_validated_feature_index_rows": report.get("validated_feature_index_rows"),
        "feature_label_boundary_quarantine_label_contaminated_artifact_count": report.get("label_contaminated_artifact_count"),
        "feature_label_boundary_quarantine_label_contaminated_record_count": report.get("label_contaminated_record_count"),
        "feature_label_boundary_quarantine_excluded_from_index_artifact_count": report.get("excluded_from_index_artifact_count"),
        "feature_label_boundary_quarantine_input_only_boundary": report.get("input_only_boundary"),
        "feature_label_boundary_quarantine_source_success": report.get("success"),
    }


def feature_label_boundary_quarantine_audit_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("input_only_boundary") is not True, failures, "source_input_only_boundary_true", report.get("input_only_boundary"), True)
    fail_if(int(report.get("validated_feature_index_rows") or 0) <= 0, failures, "source_validated_feature_index_rows_present", report.get("validated_feature_index_rows"), ">0")
    fail_if(int(report.get("label_contaminated_artifact_count") or 0) < 0, failures, "source_label_contaminated_artifact_count_nonnegative", report.get("label_contaminated_artifact_count"), ">=0")
    fail_if(int(report.get("excluded_from_index_artifact_count") or 0) < int(report.get("label_contaminated_artifact_count") or 0), failures, "source_contaminated_artifacts_excluded", report.get("excluded_from_index_artifact_count"), f">={report.get('label_contaminated_artifact_count')}")
    fail_if(report.get("safe_for_training_import") is not False, failures, "source_safe_for_training_import_false", report.get("safe_for_training_import"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def benchmark_score_cache_validation_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    head_scorecards = report.get("head_scorecards") or {}
    records = report.get("records") or []
    return {
        "benchmark_score_cache_validation_boundary_audit_rows": 1,
        "benchmark_score_cache_validation_benchmark_rows": report.get("benchmark_rows"),
        "benchmark_score_cache_validation_valid_rows": report.get("valid_rows"),
        "benchmark_score_cache_validation_invalid_rows": report.get("invalid_rows"),
        "benchmark_score_cache_validation_heads_ready": report.get("heads_ready"),
        "benchmark_score_cache_validation_head_count": len(head_scorecards),
        "benchmark_score_cache_validation_ready_head_rows": sum(1 for item in head_scorecards.values() if item.get("ready") is True),
        "benchmark_score_cache_validation_invalid_record_rows": sum(1 for item in records if item.get("valid") is not True),
        "benchmark_score_cache_validation_ready_for_model_claim": report.get("ready_for_model_claim"),
        "benchmark_score_cache_validation_safe_for_model_claim": report.get("safe_for_model_claim"),
        "benchmark_score_cache_validation_release_ready": report.get("release_ready", False),
    }


def benchmark_score_cache_validation_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    head_scorecards = report.get("head_scorecards") or {}
    records = report.get("records") or []
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("valid_rows", 0) + report.get("invalid_rows", 0) != report.get("benchmark_rows"), failures, "source_benchmark_rows_partition_exact", {"benchmark_rows": report.get("benchmark_rows"), "valid_rows": report.get("valid_rows"), "invalid_rows": report.get("invalid_rows")}, "valid + invalid = benchmark rows")
    fail_if(report.get("heads_ready") != sum(1 for item in head_scorecards.values() if item.get("ready") is True), failures, "source_heads_ready_bound", report.get("heads_ready"), "count of ready head scorecards")
    fail_if(report.get("invalid_rows") != sum(1 for item in records if item.get("valid") is not True), failures, "source_invalid_rows_bound", report.get("invalid_rows"), "count of invalid records")
    fail_if(report.get("ready_for_model_claim") is not False, failures, "source_ready_for_model_claim_false", report.get("ready_for_model_claim"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready", False) is not False, failures, "source_release_ready_false", report.get("release_ready", False), False)


def benchmark_coverage_dashboard_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    observed = validation.get("observed") or {}
    return {
        "benchmark_coverage_dashboard_boundary_audit_rows": 1,
        "benchmark_coverage_dashboard_benchmark_rows": report.get("benchmark_rows"),
        "benchmark_coverage_dashboard_valid_rows": report.get("valid_rows"),
        "benchmark_coverage_dashboard_invalid_rows": report.get("invalid_rows"),
        "benchmark_coverage_dashboard_heads_ready": report.get("heads_ready"),
        "benchmark_coverage_dashboard_head_count": len(report.get("heads") or []),
        "benchmark_coverage_dashboard_gap_queue_rows": summary.get("gap_queue_rows"),
        "benchmark_coverage_dashboard_validation_gap_queue_rows": observed.get("gap_queue_rows"),
        "benchmark_coverage_dashboard_status": report.get("status"),
        "benchmark_coverage_dashboard_ready_for_model_claim": report.get("ready_for_model_claim"),
        "benchmark_coverage_dashboard_safe_for_model_claim": report.get("safe_for_model_claim"),
        "benchmark_coverage_dashboard_release_ready": report.get("release_ready"),
        "benchmark_coverage_dashboard_validation_success": validation.get("success"),
        "benchmark_coverage_dashboard_validation_safe_for_training_pipeline": validation.get("safe_for_training_pipeline"),
        "benchmark_coverage_dashboard_validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
        "benchmark_coverage_dashboard_validation_release_ready": validation.get("release_ready"),
    }


def benchmark_coverage_dashboard_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    observed = validation.get("observed") or {}
    policy_checks = report.get("policy_checks") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(report.get("status") != "blocked", failures, "source_status_blocked", report.get("status"), "blocked")
    for key in ("benchmark_rows", "valid_rows", "invalid_rows", "heads_ready"):
        fail_if(report.get(key) != observed.get(key), failures, f"source_validation_{key}_bound", report.get(key), observed.get(key))
    for key in ("benchmark_intake_modified", "benchmark_is_training_label_source", "model_claim_gate_opened", "release_gate_opened"):
        fail_if(policy_checks.get(key) is not False, failures, f"source_policy_{key}_false", policy_checks.get(key), False)
    fail_if(report.get("ready_for_model_claim") is not False, failures, "source_ready_for_model_claim_false", report.get("ready_for_model_claim"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)


def five_head_benchmark_gap_plan_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    actions = report.get("actions") or []
    return {
        "five_head_benchmark_gap_plan_boundary_audit_rows": 1,
        "five_head_benchmark_gap_plan_action_rows": validation.get("action_rows"),
        "five_head_benchmark_gap_plan_required_benchmarks": validation.get("required_benchmarks"),
        "five_head_benchmark_gap_plan_planned_benchmarks": summary.get("planned_benchmarks"),
        "five_head_benchmark_gap_plan_cache_validated_benchmarks": validation.get("cache_validated_benchmarks"),
        "five_head_benchmark_gap_plan_heads_with_complete_scorecards": validation.get("heads_with_complete_scorecards"),
        "five_head_benchmark_gap_plan_open_blocked_action_rows": sum(1 for item in actions if item.get("status") == "open_blocked"),
        "five_head_benchmark_gap_plan_metric_claim_allowed_rows": sum(1 for item in actions if item.get("metric_claim_allowed") is True),
        "five_head_benchmark_gap_plan_status": report.get("status"),
        "five_head_benchmark_gap_plan_source_report_consistent": validation.get("source_report_consistent"),
        "five_head_benchmark_gap_plan_ready_for_model_claim": report.get("ready_for_model_claim"),
        "five_head_benchmark_gap_plan_safe_for_model_claim": report.get("safe_for_model_claim"),
        "five_head_benchmark_gap_plan_release_ready": report.get("release_ready"),
        "five_head_benchmark_gap_plan_validation_success": validation.get("success"),
        "five_head_benchmark_gap_plan_validation_failure_count": validation.get("failure_count"),
    }


def five_head_benchmark_gap_plan_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    summary = report.get("summary") or {}
    actions = report.get("actions") or []
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("failure_count") != 0, failures, "source_validation_failure_count_zero", validation.get("failure_count"), 0)
    fail_if(validation.get("source_report_consistent") is not True, failures, "source_report_consistent_true", validation.get("source_report_consistent"), True)
    fail_if(report.get("status") != "blocked", failures, "source_status_blocked", report.get("status"), "blocked")
    fail_if(validation.get("action_rows") != len(actions), failures, "source_action_rows_bound", validation.get("action_rows"), len(actions))
    fail_if(validation.get("required_benchmarks") != summary.get("required_benchmarks"), failures, "source_required_benchmarks_bound", validation.get("required_benchmarks"), summary.get("required_benchmarks"))
    fail_if(validation.get("cache_validated_benchmarks") != summary.get("cache_validated_benchmarks"), failures, "source_cache_validated_benchmarks_bound", validation.get("cache_validated_benchmarks"), summary.get("cache_validated_benchmarks"))
    fail_if(any(item.get("metric_claim_allowed") is True for item in actions), failures, "source_metric_claim_allowed_rows_zero", "nonzero", 0)
    fail_if(any(item.get("safe_for_model_claim") is not False or item.get("release_ready") is not False for item in actions), failures, "source_action_claim_release_false", "nonfalse row", "all false")
    fail_if(report.get("ready_for_model_claim") is not False, failures, "source_ready_for_model_claim_false", report.get("ready_for_model_claim"), False)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)
    fail_if(validation.get("safe_for_model_claim") is not False, failures, "source_validation_safe_for_model_claim_false", validation.get("safe_for_model_claim"), False)
    fail_if(validation.get("release_ready") is not False, failures, "source_validation_release_ready_false", validation.get("release_ready"), False)


def benchmark_lane_machine_prereview_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    lanes = report.get("lanes") or {}
    return {
        "benchmark_lane_machine_prereview_boundary_audit_rows": 1,
        "benchmark_lane_machine_prereview_lane_count": len(lanes),
        "benchmark_lane_machine_prereview_status": report.get("status"),
        "benchmark_lane_machine_prereview_formal_decision_rows_observed": report.get("formal_decision_rows_observed"),
        "benchmark_lane_machine_prereview_training_import_written_rows": report.get("training_import_written_rows"),
        "benchmark_lane_machine_prereview_formal_approved_rows_observed": sum(int(item.get("formal_approved_rows_observed") or 0) for item in lanes.values()),
        "benchmark_lane_machine_prereview_formal_decision_written_lane_rows": sum(1 for item in lanes.values() if item.get("formal_decision_written_by_this_script") is True),
        "benchmark_lane_machine_prereview_training_import_written_lane_rows": sum(1 for item in lanes.values() if item.get("training_import_written_by_this_script") is True),
        "benchmark_lane_machine_prereview_safe_for_model_claim": report.get("safe_for_model_claim"),
        "benchmark_lane_machine_prereview_release_ready": report.get("release_ready"),
    }


def benchmark_lane_machine_prereview_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    lanes = report.get("lanes") or {}
    fail_if(report.get("status") != "ready_for_human_review", failures, "source_status_ready_for_human_review", report.get("status"), "ready_for_human_review")
    fail_if(report.get("formal_decision_rows_observed") != 0, failures, "source_formal_decision_rows_zero", report.get("formal_decision_rows_observed"), 0)
    fail_if(report.get("training_import_written_rows") != 0, failures, "source_training_import_written_rows_zero", report.get("training_import_written_rows"), 0)
    fail_if(any(item.get("formal_decision_written_by_this_script") is True for item in lanes.values()), failures, "source_formal_decision_written_lane_rows_zero", "nonzero", 0)
    fail_if(any(item.get("training_import_written_by_this_script") is True for item in lanes.values()), failures, "source_training_import_written_lane_rows_zero", "nonzero", 0)
    fail_if(any(int(item.get("formal_approved_rows_observed") or 0) != 0 for item in lanes.values()), failures, "source_formal_approved_rows_zero", "nonzero", 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def benchmark_lane_status_aggregate_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    lanes = report.get("lanes") or {}
    return {
        "benchmark_lane_status_aggregate_boundary_audit_rows": 1,
        "benchmark_lane_status_aggregate_lane_count": len(lanes),
        "benchmark_lane_status_aggregate_status": report.get("status"),
        "benchmark_lane_status_aggregate_bridge_validation_success": report.get("bridge_validation_success"),
        "benchmark_lane_status_aggregate_claim_release_gate": report.get("claim_release_gate"),
        "benchmark_lane_status_aggregate_training_import_written_rows": report.get("training_import_written_rows"),
        "benchmark_lane_status_aggregate_formal_approved_rows": sum(int(item.get("formal_approved_rows") or 0) for item in lanes.values()),
        "benchmark_lane_status_aggregate_blocked_bridge_rows": sum(1 for item in lanes.values() if item.get("bridge_status") == "blocked_no_approved_decisions"),
        "benchmark_lane_status_aggregate_blocked_cache_rows": sum(1 for item in lanes.values() if item.get("cache_status") == "blocked"),
        "benchmark_lane_status_aggregate_safe_for_model_claim": report.get("safe_for_model_claim"),
        "benchmark_lane_status_aggregate_release_ready": report.get("release_ready"),
    }


def benchmark_lane_status_aggregate_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    lanes = report.get("lanes") or {}
    fail_if(report.get("status") != "blocked", failures, "source_status_blocked", report.get("status"), "blocked")
    fail_if(report.get("bridge_validation_success") is not True, failures, "source_bridge_validation_success_true", report.get("bridge_validation_success"), True)
    fail_if(report.get("claim_release_gate") != "closed", failures, "source_claim_release_gate_closed", report.get("claim_release_gate"), "closed")
    fail_if(report.get("training_import_written_rows") != 0, failures, "source_training_import_written_rows_zero", report.get("training_import_written_rows"), 0)
    fail_if(any(int(item.get("formal_approved_rows") or 0) != 0 for item in lanes.values()), failures, "source_formal_approved_rows_zero", "nonzero", 0)
    fail_if(any(item.get("bridge_status") != "blocked_no_approved_decisions" for item in lanes.values()), failures, "source_bridge_status_blocked", "nonblocked lane", "blocked_no_approved_decisions")
    fail_if(any(item.get("cache_status") != "blocked" for item in lanes.values()), failures, "source_cache_status_blocked", "nonblocked lane", "blocked")
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "source_release_ready_false", report.get("release_ready"), False)


def ddg_executable_probe_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    backend_rows = report.get("backend_rows") or []
    version_probe_rows = sum(
        1
        for backend in backend_rows
        for item in backend.get("candidate_executables", [])
        if item.get("version_probe_succeeded") is True
    )
    return {
        "ddg_executable_probe_boundary_audit_rows": 1,
        "ddg_executable_probe_backend_rows": len(backend_rows),
        "ddg_executable_probe_ready_for_ddg_execution_rows": report.get("ready_for_ddg_execution_rows"),
        "ddg_executable_probe_version_probe_succeeded_rows": report.get("version_probe_succeeded_rows"),
        "ddg_executable_probe_version_probe_rows_counted": version_probe_rows,
        "ddg_executable_probe_rosetta_executable_found": report.get("rosetta_executable_found"),
        "ddg_executable_probe_foldx_executable_found": report.get("foldx_executable_found"),
        "ddg_executable_probe_pyrosetta_module_available": report.get("pyrosetta_module_available"),
        "ddg_executable_probe_executable_ddg_backend_ready": report.get("executable_ddg_backend_ready"),
        "ddg_executable_probe_physics_ddg_ready": report.get("physics_ddg_ready"),
        "ddg_executable_probe_ddg_smoke_job_executed": report.get("ddg_smoke_job_executed"),
        "ddg_executable_probe_claim_eligible_rows_now": report.get("claim_eligible_rows_now"),
        "ddg_executable_probe_safe_for_model_claim": report.get("safe_for_model_claim"),
        "ddg_executable_probe_release_ready": report.get("release_ready"),
    }


def ddg_executable_probe_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    backend_rows = report.get("backend_rows") or []
    ready_rows = sum(1 for item in backend_rows if item.get("ready_for_ddg_execution") is True)
    version_probe_rows = sum(
        1
        for backend in backend_rows
        for item in backend.get("candidate_executables", [])
        if item.get("version_probe_succeeded") is True
    )
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(len(backend_rows) != int(report.get("ready_for_ddg_execution_rows") or 0), failures, "source_backend_rows_all_ready", len(backend_rows), report.get("ready_for_ddg_execution_rows"))
    fail_if(report.get("ready_for_ddg_execution_rows") != ready_rows, failures, "source_ready_for_ddg_execution_rows_bound", report.get("ready_for_ddg_execution_rows"), ready_rows)
    fail_if(report.get("version_probe_succeeded_rows") != version_probe_rows, failures, "source_version_probe_succeeded_rows_bound", report.get("version_probe_succeeded_rows"), version_probe_rows)
    fail_if(report.get("executable_ddg_backend_ready") is not True, failures, "source_executable_ddg_backend_ready_true", report.get("executable_ddg_backend_ready"), True)
    fail_if(report.get("physics_ddg_ready") is not False, failures, "source_physics_ddg_ready_false", report.get("physics_ddg_ready"), False)
    fail_if(report.get("ddg_smoke_job_executed") is not False, failures, "source_ddg_smoke_job_executed_false", report.get("ddg_smoke_job_executed"), False)
    fail_if(report.get("claim_eligible_rows_now") != 0, failures, "source_claim_eligible_rows_zero", report.get("claim_eligible_rows_now"), 0)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def pyrosetta_physical_smoke_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    ddg_rows = (report.get("ddg_table") or {}).get("rows") or []
    return {
        "pyrosetta_physical_smoke_boundary_audit_rows": 1,
        "pyrosetta_physical_smoke_physical_smoke_passed": report.get("physical_smoke_passed"),
        "pyrosetta_physical_smoke_ddg_protocol_executed": report.get("ddg_protocol_executed"),
        "pyrosetta_physical_smoke_pyrosetta_init_executed": report.get("pyrosetta_init_executed"),
        "pyrosetta_physical_smoke_smoke_artifact_count": len(report.get("smoke_artifact_paths") or []),
        "pyrosetta_physical_smoke_required_artifact_count": len(report.get("required_artifacts") or []),
        "pyrosetta_physical_smoke_ddg_table_rows": len(ddg_rows),
        "pyrosetta_physical_smoke_training_label_rows": sum(1 for item in ddg_rows if item.get("training_label") is True),
        "pyrosetta_physical_smoke_manual_review_required_rows": sum(1 for item in ddg_rows if item.get("manual_review_required") is True),
        "pyrosetta_physical_smoke_runtime_smoke_only_not_training_label": (report.get("ddg_table") or {}).get("runtime_smoke_only_not_training_label"),
        "pyrosetta_physical_smoke_safe_for_model_claim": report.get("safe_for_model_claim"),
        "pyrosetta_physical_smoke_release_ready": report.get("release_ready"),
    }


def pyrosetta_physical_smoke_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    ddg_table = report.get("ddg_table") or {}
    ddg_rows = ddg_table.get("rows") or []
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("physical_smoke_passed") is not True, failures, "source_physical_smoke_passed_true", report.get("physical_smoke_passed"), True)
    fail_if(report.get("ddg_protocol_executed") is not True, failures, "source_ddg_protocol_executed_true", report.get("ddg_protocol_executed"), True)
    fail_if(report.get("pyrosetta_init_executed") is not True, failures, "source_pyrosetta_init_executed_true", report.get("pyrosetta_init_executed"), True)
    fail_if(len(report.get("smoke_artifact_paths") or []) != len(report.get("required_artifacts") or []), failures, "source_smoke_artifacts_required_exact", len(report.get("smoke_artifact_paths") or []), len(report.get("required_artifacts") or []))
    fail_if(len(ddg_rows) <= 0, failures, "source_ddg_table_rows_present", len(ddg_rows), ">0")
    fail_if(any(item.get("training_label") is True for item in ddg_rows), failures, "source_training_label_rows_zero", "nonzero", 0)
    fail_if(any(item.get("manual_review_required") is not True for item in ddg_rows), failures, "source_manual_review_required_all_rows", "non-manual row", "all true")
    fail_if(ddg_table.get("runtime_smoke_only_not_training_label") is not True, failures, "source_runtime_smoke_only_true", ddg_table.get("runtime_smoke_only_not_training_label"), True)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def pyrosetta_verified_ddg_feature_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    quality = report.get("quality_gate") or {}
    quality_policy = validation.get("quality_gate_policy") or {}
    return {
        "pyrosetta_verified_ddg_feature_boundary_audit_rows": 1,
        "pyrosetta_verified_ddg_feature_candidate_input_rows": report.get("candidate_input_rows"),
        "pyrosetta_verified_ddg_feature_computed_feature_rows": report.get("computed_feature_rows"),
        "pyrosetta_verified_ddg_feature_failed_candidate_rows": report.get("failed_candidate_rows"),
        "pyrosetta_verified_ddg_feature_multi_chain_context_rows": report.get("multi_chain_context_rows"),
        "pyrosetta_verified_ddg_feature_quality_passed_rows": quality.get("quality_passed_rows"),
        "pyrosetta_verified_ddg_feature_quality_blocked_rows": quality.get("quality_blocked_rows"),
        "pyrosetta_verified_ddg_feature_validation_feature_rows": validation.get("feature_rows"),
        "pyrosetta_verified_ddg_feature_validation_valid_rows": validation.get("valid_rows"),
        "pyrosetta_verified_ddg_feature_validation_invalid_rows": validation.get("invalid_rows"),
        "pyrosetta_verified_ddg_feature_validation_quality_gate_status": validation.get("quality_gate_status"),
        "pyrosetta_verified_ddg_feature_scientific_validity_claim": quality_policy.get("scientific_validity_claim"),
        "pyrosetta_verified_ddg_feature_safe_for_model_claim": report.get("safe_for_model_claim"),
        "pyrosetta_verified_ddg_feature_release_ready": report.get("release_ready"),
    }


def pyrosetta_verified_ddg_feature_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    quality = report.get("quality_gate") or {}
    quality_policy = validation.get("quality_gate_policy") or {}
    fail_if(report.get("computed_feature_rows") != report.get("candidate_input_rows"), failures, "source_computed_candidate_rows_exact", report.get("computed_feature_rows"), report.get("candidate_input_rows"))
    fail_if(report.get("failed_candidate_rows") != 0, failures, "source_failed_candidate_rows_zero", report.get("failed_candidate_rows"), 0)
    fail_if(len(report.get("errors") or []) != 0, failures, "source_errors_empty", len(report.get("errors") or []), 0)
    fail_if(report.get("ddg_protocol_executed") is not True, failures, "source_ddg_protocol_executed_true", report.get("ddg_protocol_executed"), True)
    fail_if(report.get("pyrosetta_init_executed") is not True, failures, "source_pyrosetta_init_executed_true", report.get("pyrosetta_init_executed"), True)
    fail_if(validation.get("feature_rows") != report.get("computed_feature_rows"), failures, "source_validation_feature_rows_bound", validation.get("feature_rows"), report.get("computed_feature_rows"))
    fail_if(validation.get("valid_rows") != report.get("computed_feature_rows"), failures, "source_validation_valid_rows_bound", validation.get("valid_rows"), report.get("computed_feature_rows"))
    fail_if(validation.get("invalid_rows") != 0, failures, "source_validation_invalid_rows_zero", validation.get("invalid_rows"), 0)
    fail_if((quality.get("quality_passed_rows") or 0) + (quality.get("quality_blocked_rows") or 0) != report.get("computed_feature_rows"), failures, "source_quality_rows_partition_exact", {"passed": quality.get("quality_passed_rows"), "blocked": quality.get("quality_blocked_rows")}, report.get("computed_feature_rows"))
    fail_if(validation.get("quality_gate_status") != "blocked", failures, "source_validation_quality_gate_blocked", validation.get("quality_gate_status"), "blocked")
    fail_if(quality_policy.get("scientific_validity_claim") is not False, failures, "source_scientific_validity_claim_false", quality_policy.get("scientific_validity_claim"), False)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def foldx_physical_smoke_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "foldx_physical_smoke_boundary_audit_rows": 1,
        "foldx_physical_smoke_foldx_executable_found": report.get("foldx_executable_found"),
        "foldx_physical_smoke_help_probe_succeeded": report.get("help_probe_succeeded"),
        "foldx_physical_smoke_parser_contract_ready": report.get("parser_contract_ready"),
        "foldx_physical_smoke_physical_smoke_passed": report.get("physical_smoke_passed"),
        "foldx_physical_smoke_status": report.get("status"),
        "foldx_physical_smoke_ready_execution_plan_rows": report.get("ready_execution_plan_rows"),
        "foldx_physical_smoke_runtime_receipt_ready": report.get("runtime_receipt_ready"),
        "foldx_physical_smoke_blocker_count": report.get("blocker_count"),
        "foldx_physical_smoke_validation_success": report.get("success"),
        "foldx_physical_smoke_validation_failure_count": len(report.get("failures") or []),
        "foldx_physical_smoke_safe_for_model_claim": report.get("safe_for_model_claim"),
        "foldx_physical_smoke_release_ready": report.get("release_ready"),
    }


def foldx_physical_smoke_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_validation_success_true", report.get("success"), True)
    fail_if(len(report.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(report.get("failures") or []), 0)
    fail_if(report.get("foldx_executable_found") is not True, failures, "source_foldx_executable_found_true", report.get("foldx_executable_found"), True)
    fail_if(report.get("help_probe_succeeded") is not True, failures, "source_help_probe_succeeded_true", report.get("help_probe_succeeded"), True)
    fail_if(report.get("parser_contract_ready") is not True, failures, "source_parser_contract_ready_true", report.get("parser_contract_ready"), True)
    fail_if(report.get("physical_smoke_passed") is not False, failures, "source_physical_smoke_passed_false", report.get("physical_smoke_passed"), False)
    fail_if(report.get("status") != "blocked_missing_runtime_evidence", failures, "source_status_blocked_runtime_evidence", report.get("status"), "blocked_missing_runtime_evidence")
    fail_if(report.get("ready_execution_plan_rows") != 0, failures, "source_ready_execution_plan_rows_zero", report.get("ready_execution_plan_rows"), 0)
    fail_if(report.get("runtime_receipt_ready") is not False, failures, "source_runtime_receipt_ready_false", report.get("runtime_receipt_ready"), False)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def ddg_backend_operator_packet_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ddg_backend_operator_packet_boundary_audit_rows": 1,
        "ddg_backend_operator_packet_packet_rows": report.get("packet_rows"),
        "ddg_backend_operator_packet_physical_backend_rows": report.get("physical_backend_rows"),
        "ddg_backend_operator_packet_ready_for_execution_now_rows": report.get("ready_for_execution_now_rows"),
        "ddg_backend_operator_packet_requires_human_input_rows": report.get("requires_human_input_rows"),
        "ddg_backend_operator_packet_completion_ready_rows": report.get("completion_ready_rows"),
        "ddg_backend_operator_packet_foldx_packet_ready": report.get("foldx_packet_ready"),
        "ddg_backend_operator_packet_pyrosetta_packet_ready": report.get("pyrosetta_packet_ready"),
        "ddg_backend_operator_packet_rosetta_packet_ready": report.get("rosetta_packet_ready"),
        "ddg_backend_operator_packet_validation_all_packets_valid": validation.get("all_operator_packets_valid"),
        "ddg_backend_operator_packet_validation_valid_status_rows": validation.get("valid_status_rows"),
        "ddg_backend_operator_packet_safe_for_model_claim": report.get("safe_for_model_claim"),
        "ddg_backend_operator_packet_release_ready": report.get("release_ready"),
    }


def ddg_backend_operator_packet_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(validation.get("all_operator_packets_valid") is not True, failures, "source_all_operator_packets_valid_true", validation.get("all_operator_packets_valid"), True)
    fail_if(report.get("packet_rows") != validation.get("packet_rows"), failures, "source_packet_rows_bound", report.get("packet_rows"), validation.get("packet_rows"))
    fail_if(report.get("packet_rows") != report.get("physical_backend_rows"), failures, "source_packet_rows_physical_backend_rows", report.get("packet_rows"), report.get("physical_backend_rows"))
    fail_if(report.get("ready_for_execution_now_rows") != validation.get("ready_for_execution_now_rows"), failures, "source_ready_execution_rows_bound", report.get("ready_for_execution_now_rows"), validation.get("ready_for_execution_now_rows"))
    fail_if(report.get("requires_human_input_rows") != report.get("packet_rows"), failures, "source_requires_human_input_all_packets", report.get("requires_human_input_rows"), report.get("packet_rows"))
    fail_if(report.get("completion_ready_rows") != 0, failures, "source_completion_ready_rows_zero", report.get("completion_ready_rows"), 0)
    fail_if(report.get("foldx_packet_ready") is not False, failures, "source_foldx_packet_ready_false", report.get("foldx_packet_ready"), False)
    fail_if(report.get("pyrosetta_packet_ready") is not True, failures, "source_pyrosetta_packet_ready_true", report.get("pyrosetta_packet_ready"), True)
    fail_if(report.get("rosetta_packet_ready") is not False, failures, "source_rosetta_packet_ready_false", report.get("rosetta_packet_ready"), False)
    fail_if(validation.get("valid_status_rows") != validation.get("status_rows"), failures, "source_valid_status_rows_all", validation.get("valid_status_rows"), validation.get("status_rows"))
    for field in ("safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def rosetta_physical_smoke_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rosetta_physical_smoke_boundary_audit_rows": 1,
        "rosetta_physical_smoke_artifact_count": report.get("artifact_count"),
        "rosetta_physical_smoke_artifact_sha256_count": len(report.get("artifact_sha256") or {}),
        "rosetta_physical_smoke_physical_smoke_passed": report.get("physical_smoke_passed"),
        "rosetta_physical_smoke_ddg_protocol_executed": report.get("ddg_protocol_executed"),
        "rosetta_physical_smoke_status": report.get("status"),
        "rosetta_physical_smoke_returncode": report.get("returncode"),
        "rosetta_physical_smoke_safe_for_model_claim": report.get("safe_for_model_claim"),
        "rosetta_physical_smoke_release_ready": report.get("release_ready"),
    }


def rosetta_physical_smoke_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    artifact_count = report.get("artifact_count")
    fail_if(report.get("backend") != "rosetta", failures, "source_backend_rosetta", report.get("backend"), "rosetta")
    fail_if(artifact_count != len(report.get("artifact_paths") or []), failures, "source_artifact_paths_count_bound", len(report.get("artifact_paths") or []), artifact_count)
    fail_if(artifact_count != len(report.get("artifact_sha256") or {}), failures, "source_artifact_sha256_count_bound", len(report.get("artifact_sha256") or {}), artifact_count)
    fail_if(report.get("physical_smoke_passed") is not True, failures, "source_physical_smoke_passed_true", report.get("physical_smoke_passed"), True)
    fail_if(report.get("ddg_protocol_executed") is not True, failures, "source_ddg_protocol_executed_true", report.get("ddg_protocol_executed"), True)
    fail_if(report.get("status") != "completed", failures, "source_status_completed", report.get("status"), "completed")
    fail_if(report.get("returncode") != 0, failures, "source_returncode_zero", report.get("returncode"), 0)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def pyrosetta_concordance_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pyrosetta_concordance_boundary_audit_rows": 1,
        "pyrosetta_concordance_input_feature_rows": report.get("input_feature_rows"),
        "pyrosetta_concordance_multi_chain_candidate_rows": report.get("multi_chain_candidate_rows"),
        "pyrosetta_concordance_multi_chain_feature_rows": report.get("multi_chain_feature_rows"),
        "pyrosetta_concordance_quality_passed_rows": report.get("quality_passed_rows"),
        "pyrosetta_concordance_quality_blocked_rows": report.get("quality_blocked_rows"),
        "pyrosetta_concordance_validation_concordance_rows": validation.get("concordance_rows"),
        "pyrosetta_concordance_validation_valid_rows": validation.get("valid_rows"),
        "pyrosetta_concordance_validation_invalid_rows": validation.get("invalid_rows"),
        "pyrosetta_concordance_quality_gate_status": validation.get("quality_gate_status"),
        "pyrosetta_concordance_safe_for_model_claim": report.get("safe_for_model_claim"),
        "pyrosetta_concordance_release_ready": validation.get("release_ready"),
    }


def pyrosetta_concordance_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    candidate_rows = report.get("multi_chain_candidate_rows")
    fail_if(report.get("input_feature_rows", 0) < int(candidate_rows or 0), failures, "source_input_covers_multi_chain_candidates", report.get("input_feature_rows"), f">={candidate_rows}")
    fail_if(report.get("multi_chain_feature_rows") != int(candidate_rows or 0) * 2, failures, "source_multi_chain_feature_rows_double_candidates", report.get("multi_chain_feature_rows"), f"{candidate_rows} * 2")
    fail_if((report.get("quality_passed_rows") or 0) + (report.get("quality_blocked_rows") or 0) != candidate_rows, failures, "source_quality_rows_partition_exact", {"passed": report.get("quality_passed_rows"), "blocked": report.get("quality_blocked_rows")}, candidate_rows)
    fail_if(validation.get("concordance_rows") != candidate_rows, failures, "source_validation_concordance_rows_bound", validation.get("concordance_rows"), candidate_rows)
    fail_if(validation.get("source_multi_chain_candidate_rows") != candidate_rows, failures, "source_validation_candidate_rows_bound", validation.get("source_multi_chain_candidate_rows"), candidate_rows)
    fail_if(validation.get("valid_rows") != candidate_rows, failures, "source_validation_valid_rows_bound", validation.get("valid_rows"), candidate_rows)
    fail_if(validation.get("invalid_rows") != 0, failures, "source_validation_invalid_rows_zero", validation.get("invalid_rows"), 0)
    fail_if(validation.get("quality_gate_status") != "blocked", failures, "source_quality_gate_blocked", validation.get("quality_gate_status"), "blocked")
    fail_if(report.get("safe_for_model_claim") is not False, failures, "source_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    for field in ("safe_for_model_claim", "release_ready"):
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def pyrosetta_local_install_probe_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    install = report.get("install") or {}
    module_spec = report.get("module_spec") or {}
    import_probe = report.get("import_probe") or {}
    wheel = report.get("wheel") or {}
    return {
        "pyrosetta_install_probe_boundary_audit_rows": 1,
        "pyrosetta_install_probe_wheel_present": wheel.get("present"),
        "pyrosetta_install_probe_install_path_exists": install.get("path_exists"),
        "pyrosetta_install_probe_module_spec_available": module_spec.get("available"),
        "pyrosetta_install_probe_import_succeeded": import_probe.get("succeeded"),
        "pyrosetta_install_probe_formal_license_decision_written": report.get("formal_license_decision_written"),
        "pyrosetta_install_probe_formal_runtime_receipt_written": report.get("formal_runtime_receipt_written"),
        "pyrosetta_install_probe_approved_for_physical_ddg_runtime": report.get("approved_for_physical_ddg_runtime"),
        "pyrosetta_install_probe_physics_ddg_ready": report.get("physics_ddg_ready"),
        "pyrosetta_install_probe_ready_for_ddg_smoke": report.get("ready_for_ddg_smoke"),
        "pyrosetta_install_probe_validation_success": validation.get("success"),
        "pyrosetta_install_probe_safe_for_model_claim": report.get("safe_for_model_claim"),
        "pyrosetta_install_probe_release_ready": report.get("release_ready"),
    }


def pyrosetta_local_install_probe_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    install = report.get("install") or {}
    module_spec = report.get("module_spec") or {}
    import_probe = report.get("import_probe") or {}
    wheel = report.get("wheel") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(wheel.get("present") is not True, failures, "source_wheel_present_true", wheel.get("present"), True)
    fail_if(install.get("path_exists") is not True, failures, "source_install_path_exists_true", install.get("path_exists"), True)
    fail_if(module_spec.get("available") is not True, failures, "source_module_spec_available_true", module_spec.get("available"), True)
    fail_if(import_probe.get("succeeded") is not True, failures, "source_import_succeeded_true", import_probe.get("succeeded"), True)
    for field in ("formal_license_decision_written", "formal_runtime_receipt_written", "approved_for_physical_ddg_runtime", "physics_ddg_ready", "ready_for_ddg_smoke", "ddg_protocol_executed", "backend_config_enabled", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    for field in ("wheel_present", "install_path_exists", "module_spec_available", "import_succeeded"):
        fail_if(validation.get(field) is not True, failures, f"source_validation_{field}_true", validation.get(field), True)
    for field in ("physics_ddg_ready", "safe_for_model_claim", "release_ready"):
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def ddg_runtime_preflight_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ddg_runtime_preflight_boundary_audit_rows": 1,
        "ddg_runtime_preflight_physical_backend_rows": report.get("physical_backend_rows"),
        "ddg_runtime_preflight_ready_physical_backend_rows": len(report.get("ready_physical_backends") or []),
        "ddg_runtime_preflight_blocked_physical_backend_rows": len(report.get("blocked_physical_backends") or []),
        "ddg_runtime_preflight_approved_runtime_receipt_rows": report.get("approved_runtime_receipt_rows"),
        "ddg_runtime_preflight_per_backend_physics_ready_rows": report.get("per_backend_physics_ready_rows"),
        "ddg_runtime_preflight_capability_status": report.get("physical_ddg_lane_capability_status"),
        "ddg_runtime_preflight_safe_pipeline_manifest_connected": report.get("safe_pipeline_manifest_connected"),
        "ddg_runtime_preflight_validation_success": validation.get("success"),
        "ddg_runtime_preflight_safe_for_model_claim": report.get("safe_for_model_claim"),
        "ddg_runtime_preflight_release_ready": report.get("release_ready"),
    }


def ddg_runtime_preflight_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    physical_rows = report.get("physical_backend_rows")
    ready_rows = len(report.get("ready_physical_backends") or [])
    blocked_rows = len(report.get("blocked_physical_backends") or [])
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(len(report.get("backends") or []) != physical_rows, failures, "source_backend_rows_bound", len(report.get("backends") or []), physical_rows)
    fail_if(ready_rows != report.get("per_backend_physics_ready_rows"), failures, "source_ready_backend_rows_bound", ready_rows, report.get("per_backend_physics_ready_rows"))
    fail_if(ready_rows + blocked_rows != physical_rows, failures, "source_ready_blocked_partition_exact", {"ready": ready_rows, "blocked": blocked_rows}, physical_rows)
    fail_if(report.get("approved_runtime_receipt_rows") != report.get("runtime_receipt_rows"), failures, "source_runtime_receipt_rows_bound", report.get("approved_runtime_receipt_rows"), report.get("runtime_receipt_rows"))
    fail_if(report.get("physical_ddg_lane_capability_status") != "blocked", failures, "source_capability_status_blocked", report.get("physical_ddg_lane_capability_status"), "blocked")
    for field in ("all_physical_backends_ready", "physics_ddg_ready", "safe_pipeline_manifest_connected", "safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    fail_if(validation.get("approved_runtime_receipt_rows") != report.get("approved_runtime_receipt_rows"), failures, "source_validation_approved_rows_bound", validation.get("approved_runtime_receipt_rows"), report.get("approved_runtime_receipt_rows"))
    for field in ("physical_ddg_lane_capability_status",):
        fail_if(validation.get(field) != "blocked", failures, f"source_validation_{field}_blocked", validation.get(field), "blocked")
    for field in ("physics_ddg_ready", "safe_for_model_claim", "release_ready"):
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def ddg_runtime_receipt_validation_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ddg_runtime_receipt_boundary_audit_rows": 1,
        "ddg_runtime_receipt_receipt_rows": report.get("receipt_rows"),
        "ddg_runtime_receipt_valid_receipt_rows": report.get("valid_receipt_rows"),
        "ddg_runtime_receipt_invalid_receipt_rows": report.get("invalid_receipt_rows"),
        "ddg_runtime_receipt_approved_runtime_rows": report.get("approved_runtime_rows"),
        "ddg_runtime_receipt_missing_backend_rows": len(report.get("missing_backend_runtime_receipts") or []),
        "ddg_runtime_receipt_any_backend_runtime_ready": report.get("any_backend_runtime_ready"),
        "ddg_runtime_receipt_all_physical_backends_ready": report.get("all_physical_backends_ready"),
        "ddg_runtime_receipt_capability_status": report.get("physical_ddg_lane_capability_status"),
        "ddg_runtime_receipt_safe_for_model_claim": report.get("safe_for_model_claim"),
        "ddg_runtime_receipt_release_ready": report.get("release_ready"),
    }


def ddg_runtime_receipt_validation_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("invalid_receipt_rows") != 0, failures, "source_invalid_receipt_rows_zero", report.get("invalid_receipt_rows"), 0)
    fail_if(len(report.get("error_counts") or {}) != 0, failures, "source_error_counts_empty", len(report.get("error_counts") or {}), 0)
    for field in ("valid_receipt_rows", "approved_runtime_rows", "per_backend_runtime_ready_rows", "ready_for_ddg_smoke_rows", "ready_to_enable_backend_rows"):
        fail_if(report.get(field) != report.get("receipt_rows"), failures, f"source_{field}_bound", report.get(field), report.get("receipt_rows"))
    fail_if(report.get("missing_backend_runtime_receipts") != ["foldx"], failures, "source_missing_foldx_receipt", report.get("missing_backend_runtime_receipts"), ["foldx"])
    fail_if(report.get("any_backend_runtime_ready") is not True, failures, "source_any_backend_runtime_ready_true", report.get("any_backend_runtime_ready"), True)
    fail_if(report.get("physical_ddg_lane_capability_status") != "blocked", failures, "source_capability_status_blocked", report.get("physical_ddg_lane_capability_status"), "blocked")
    for field in ("all_physical_backends_ready", "executable_ddg_backend_ready", "physics_ddg_ready", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def ddg_physical_smoke_harness_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ddg_physical_smoke_harness_boundary_audit_rows": 1,
        "ddg_physical_smoke_harness_contract_rows": report.get("harness_contract_rows"),
        "ddg_physical_smoke_harness_executor_contract_implemented_rows": report.get("executor_contract_implemented_rows"),
        "ddg_physical_smoke_harness_approved_runtime_receipt_rows": report.get("approved_runtime_receipt_rows"),
        "ddg_physical_smoke_harness_passed_rows": report.get("physical_smoke_passed_rows"),
        "ddg_physical_smoke_harness_can_execute_now_rows": report.get("can_execute_physical_smoke_now_rows"),
        "ddg_physical_smoke_harness_ready_execution_plan_rows": report.get("ready_execution_plan_rows"),
        "ddg_physical_smoke_harness_physics_ddg_ready_observed": report.get("physics_ddg_ready"),
        "ddg_physical_smoke_harness_validation_success": validation.get("success"),
        "ddg_physical_smoke_harness_audit_safe_for_model_claim": report.get("safe_for_model_claim"),
        "ddg_physical_smoke_harness_audit_release_ready": report.get("release_ready"),
    }


def ddg_physical_smoke_harness_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    contract_rows = report.get("harness_contract_rows")
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("executor_contract_implemented_rows") != contract_rows, failures, "source_executor_contract_rows_bound", report.get("executor_contract_implemented_rows"), contract_rows)
    fail_if(report.get("approved_runtime_receipt_rows") != report.get("runtime_receipt_status_rows"), failures, "source_approved_receipt_rows_bound", report.get("approved_runtime_receipt_rows"), report.get("runtime_receipt_status_rows"))
    fail_if(report.get("physical_smoke_passed_rows") > report.get("approved_runtime_receipt_rows"), failures, "source_smoke_passed_receipts_bounded", report.get("physical_smoke_passed_rows"), "<= approved receipts")
    fail_if(report.get("can_execute_physical_smoke_now_rows") != 0, failures, "source_can_execute_now_zero", report.get("can_execute_physical_smoke_now_rows"), 0)
    fail_if(report.get("ready_execution_plan_rows") != 0, failures, "source_ready_execution_plan_zero", report.get("ready_execution_plan_rows"), 0)
    fail_if(report.get("execute_attempted_rows") != 0, failures, "source_execute_attempted_zero", report.get("execute_attempted_rows"), 0)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    fail_if(validation.get("harness_contract_rows") != contract_rows, failures, "source_validation_contract_rows_bound", validation.get("harness_contract_rows"), contract_rows)
    fail_if(validation.get("physical_smoke_passed_rows") != report.get("physical_smoke_passed_rows"), failures, "source_validation_smoke_rows_bound", validation.get("physical_smoke_passed_rows"), report.get("physical_smoke_passed_rows"))
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def ddg_proxy_physics_claim_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ddg_proxy_physics_claim_boundary_audit_rows": 1,
        "ddg_proxy_physics_proxy_backend_ready": report.get("proxy_ddg_backend_ready"),
        "ddg_proxy_physics_thermompnn_proxy_ready": report.get("thermompnn_proxy_ready"),
        "ddg_proxy_physics_proxy_is_physics": report.get("proxy_is_physics"),
        "ddg_proxy_physics_physics_ddg_ready": report.get("physics_ddg_ready"),
        "ddg_proxy_physics_executable_backend_ready": report.get("executable_ddg_backend_ready"),
        "ddg_proxy_physics_checked_physical_backend_rows": len(report.get("physical_backends_checked") or []),
        "ddg_proxy_physics_contradictory_state_rows": len(report.get("contradictory_executable_physics_states") or []),
        "ddg_proxy_physics_validation_success": report.get("success"),
        "ddg_proxy_physics_audit_safe_for_model_claim": report.get("safe_for_model_claim"),
        "ddg_proxy_physics_audit_release_ready": report.get("release_ready"),
    }


def ddg_proxy_physics_claim_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("proxy_ddg_backend_ready") is not True, failures, "source_proxy_backend_ready_true", report.get("proxy_ddg_backend_ready"), True)
    fail_if(report.get("thermompnn_proxy_ready") is not True, failures, "source_thermompnn_proxy_ready_true", report.get("thermompnn_proxy_ready"), True)
    fail_if(report.get("proxy_is_physics") is not False, failures, "source_proxy_is_physics_false", report.get("proxy_is_physics"), False)
    fail_if(report.get("physics_ddg_ready") is not False, failures, "source_physics_ddg_ready_false", report.get("physics_ddg_ready"), False)
    fail_if(report.get("executable_ddg_backend_ready") is not False, failures, "source_executable_backend_ready_false", report.get("executable_ddg_backend_ready"), False)
    fail_if(len(report.get("contradictory_executable_physics_states") or []) != 0, failures, "source_contradictory_states_empty", len(report.get("contradictory_executable_physics_states") or []), 0)
    for field in ("safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def execution_receipt_freshness_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "execution_receipt_freshness_boundary_audit_rows": 1,
        "execution_receipt_freshness_total_receipts": report.get("total_receipts"),
        "execution_receipt_freshness_fresh_receipts": report.get("fresh_receipts"),
        "execution_receipt_freshness_stale_receipts": report.get("stale_receipts"),
        "execution_receipt_freshness_missing_artifacts": report.get("missing_artifacts"),
        "execution_receipt_freshness_sha256_mismatches": report.get("sha256_mismatches"),
        "execution_receipt_freshness_artifact_reference_checks": report.get("artifact_reference_checks"),
        "execution_receipt_freshness_receipts_without_hash_fields": report.get("receipts_without_artifact_hash_fields"),
        "execution_receipt_freshness_exists_mtime_only_receipts": len(report.get("receipts_with_only_exists_mtime_freshness") or []),
        "execution_receipt_freshness_validation_success": report.get("success"),
        "execution_receipt_freshness_audit_safe_for_model_claim": report.get("safe_for_model_claim"),
        "execution_receipt_freshness_audit_release_ready": report.get("release_ready"),
    }


def execution_receipt_freshness_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    total = report.get("total_receipts")
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("success") is not True, failures, "source_success_true", report.get("success"), True)
    fail_if(report.get("fresh_receipts", 0) + report.get("stale_receipts", 0) != total, failures, "source_freshness_partition_exact", {"fresh": report.get("fresh_receipts"), "stale": report.get("stale_receipts"), "total": total}, "fresh + stale = total")
    for key in ("stale_receipts", "missing_artifacts", "sha256_mismatches", "sha256_unreadable_artifacts"):
        fail_if(report.get(key) != 0, failures, f"source_{key}_zero", report.get(key), 0)
    fail_if(report.get("receipts_without_artifact_hash_fields") != len(report.get("receipts_with_only_exists_mtime_freshness") or []), failures, "source_hash_gap_matches_mtime_only", report.get("receipts_without_artifact_hash_fields"), len(report.get("receipts_with_only_exists_mtime_freshness") or []))
    fail_if(len(report.get("failures") or []) != 0, failures, "source_failures_empty", len(report.get("failures") or []), 0)
    for field in ("safe_for_training_import", "safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)


def parallel_hard_gate_execution_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "parallel_hard_gate_execution_boundary_audit_rows": 1,
        "parallel_hard_gate_execution_receipt_rows": report.get("receipt_rows"),
        "parallel_hard_gate_execution_validation_passed_rows": report.get("validation_passed_rows"),
        "parallel_hard_gate_execution_executed_rows": report.get("executed_rows"),
        "parallel_hard_gate_execution_eligibility_changed_rows": report.get("eligibility_changed_rows"),
        "parallel_hard_gate_execution_formal_decision_written_rows": report.get("formal_decision_written_rows"),
        "parallel_hard_gate_execution_runtime_receipt_written_rows": report.get("runtime_receipt_written_rows"),
        "parallel_hard_gate_execution_training_import_written_rows": report.get("training_import_written_rows"),
        "parallel_hard_gate_execution_model_or_release_flags_changed_rows": report.get("model_or_release_flags_changed_rows"),
        "parallel_hard_gate_execution_validation_success": validation.get("success"),
        "parallel_hard_gate_execution_audit_safe_for_model_claim": report.get("safe_for_model_claim"),
        "parallel_hard_gate_execution_audit_release_ready": report.get("release_ready"),
    }


def parallel_hard_gate_execution_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    receipt_rows = report.get("receipt_rows")
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(validation.get("success") is not True, failures, "source_validation_success_true", validation.get("success"), True)
    for key in ("validation_passed_rows", "executed_rows"):
        fail_if(report.get(key) != receipt_rows, failures, f"source_{key}_bound", report.get(key), receipt_rows)
    for key in ("eligibility_changed_rows", "training_import_written_rows", "model_or_release_flags_changed_rows"):
        fail_if(report.get(key) != 0, failures, f"source_{key}_zero", report.get(key), 0)
    fail_if(validation.get("receipt_rows") != receipt_rows, failures, "source_validation_receipt_rows_bound", validation.get("receipt_rows"), receipt_rows)
    fail_if(validation.get("expected_lane_count") != receipt_rows, failures, "source_validation_lane_count_bound", validation.get("expected_lane_count"), receipt_rows)
    fail_if(validation.get("validation_passed_rows") != receipt_rows, failures, "source_validation_passed_rows_bound", validation.get("validation_passed_rows"), receipt_rows)
    fail_if(validation.get("eligibility_changed_rows") != 0, failures, "source_validation_eligibility_zero", validation.get("eligibility_changed_rows"), 0)
    fail_if(validation.get("training_import_written_rows") != 0, failures, "source_validation_training_zero", validation.get("training_import_written_rows"), 0)
    fail_if(len(validation.get("failures") or []) != 0, failures, "source_validation_failures_empty", len(validation.get("failures") or []), 0)
    for field in ("safe_for_model_claim", "release_ready"):
        fail_if(report.get(field) is not False, failures, f"source_{field}_false", report.get(field), False)
        fail_if(validation.get(field) is not False, failures, f"source_validation_{field}_false", validation.get(field), False)


def ddg_backend_failure_boundary_metrics(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ddg_backend_failure_boundary_audit_rows": 1,
        "ddg_backend_failure_capability_status": report.get("physical_ddg_lane_capability_status"),
        "ddg_backend_failure_physics_ddg_ready": report.get("physics_ddg_ready"),
        "ddg_backend_failure_one_backend_ready": report.get("one_ddg_backend_ready"),
        "ddg_backend_failure_ready_backend_count": report.get("ready_backend_count"),
        "ddg_backend_failure_physics_backend_ready_count": report.get("physics_backend_ready_count"),
        "ddg_backend_failure_proxy_backend_ready": report.get("proxy_ddg_backend_ready"),
        "ddg_backend_failure_proxy_is_physics": report.get("proxy_is_physics"),
        "ddg_backend_failure_formal_runtime_receipt_written": (report.get("guardrails") or {}).get("formal_runtime_receipt_written"),
        "ddg_backend_failure_training_labels_written": (report.get("guardrails") or {}).get("training_labels_written"),
        "ddg_backend_failure_unreviewed_formal_decision_written": (report.get("guardrails") or {}).get("unreviewed_formal_decision_written"),
        "ddg_backend_failure_audit_release_ready": (report.get("guardrails") or {}).get("release_ready"),
    }


def ddg_backend_failure_boundary_checks(report: dict[str, Any], validation: dict[str, Any], rows: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    guardrails = report.get("guardrails") or {}
    fail_if(report.get("local_only") is not True, failures, "source_local_only_true", report.get("local_only"), True)
    fail_if(report.get("physical_ddg_lane_capability_status") != "blocked", failures, "source_capability_blocked", report.get("physical_ddg_lane_capability_status"), "blocked")
    fail_if(report.get("physics_ddg_ready") is not False, failures, "source_physics_ddg_ready_false", report.get("physics_ddg_ready"), False)
    fail_if(report.get("one_ddg_backend_ready") is not True, failures, "source_one_backend_ready_true", report.get("one_ddg_backend_ready"), True)
    fail_if(report.get("physics_backend_ready_count") != 1, failures, "source_physics_backend_ready_count_one", report.get("physics_backend_ready_count"), 1)
    fail_if(report.get("proxy_ddg_backend_ready") is not True, failures, "source_proxy_backend_ready_true", report.get("proxy_ddg_backend_ready"), True)
    fail_if(report.get("proxy_is_physics") is not False, failures, "source_proxy_is_physics_false", report.get("proxy_is_physics"), False)
    fail_if(guardrails.get("formal_runtime_receipt_written") is not True, failures, "source_formal_runtime_receipt_written_true", guardrails.get("formal_runtime_receipt_written"), True)
    fail_if(guardrails.get("training_labels_written") is not False, failures, "source_training_labels_written_false", guardrails.get("training_labels_written"), False)
    fail_if(guardrails.get("unreviewed_formal_decision_written") is not False, failures, "source_unreviewed_decision_false", guardrails.get("unreviewed_formal_decision_written"), False)
    fail_if(guardrails.get("release_ready") is not False, failures, "source_release_ready_false", guardrails.get("release_ready"), False)
def cfg(
    pid: str,
    slug: str,
    source_report: str,
    source_validation: str | None,
    source_jsonl: str | None,
    out_jsonl: str,
    metric_fn: Any,
    source_check_fn: Any,
    primary_count_key: str,
    blocked_count_key: str,
    item_id_name: str = "source_item_id",
    item_id_keys: list[str] | None = None,
    item_state_keys: list[str] | None = None,
    status_keys: list[str] | None = None,
    summary_only: bool = False,
) -> dict[str, Any]:
    report_path = AI_ROOT / source_report
    validation_path = AI_ROOT / source_validation if source_validation else None
    jsonl_path = AI_ROOT / source_jsonl if source_jsonl else None
    out = AI_ROOT / out_jsonl
    out_report = AI_ROOT / "reports" / f"{out.stem}_report.json"
    out_validation = AI_ROOT / "reports" / f"{out.stem}_validation_report.json"
    return {
        "id": pid,
        "slug": slug,
        "source_report": report_path,
        "source_report_rel": source_report,
        "source_validation": validation_path,
        "source_validation_rel": source_validation,
        "source_jsonl": jsonl_path,
        "source_jsonl_rel": source_jsonl,
        "out_jsonl": out,
        "out_report": out_report,
        "out_validation": out_validation,
        "metric_fn": metric_fn,
        "source_check_fn": source_check_fn,
        "primary_count_key": primary_count_key,
        "blocked_count_key": blocked_count_key,
        "item_id_name": item_id_name,
        "item_id_keys": item_id_keys or [item_id_name],
        "item_state_keys": item_state_keys or [],
        "status_keys": status_keys or ["status", "verification_status"],
        "summary_only": summary_only,
        "item_gap_type": f"{slug}_gap",
        "summary_gap_type": f"{slug}_summary_gap",
        "item_blocker": "source row remains observational and does not authorize completion or release",
        "summary_blocker": "source report remains observational and does not authorize completion, training, claims, delivery, release, deployment, sync, restart, or production execution",
        "row_policy": f"{pid.upper()} gap audit only; source rows are not approvals, training imports, model claims, customer delivery authorization, release approval, deployment, sync, restart, or production execution.",
        "report_policy": f"{pid.upper()} audit only. Source observations remain fail-closed and cannot authorize training, claims, delivery, release, deployment, sync, restart, or production execution.",
        "validation_policy": f"Validation only. {pid.upper()} gap audit does not authorize training, claims, delivery, release, deployment, sync, restart, or production execution.",
        "report_metric_keys": [],
        "validation_metric_keys": [],
    }


CONFIGS: dict[str, dict[str, Any]] = {
    "p493": cfg(
        "p493",
        "human_review_closeout",
        "reports/human_review_closeout_board_report.json",
        "reports/human_review_closeout_board_validation_report.json",
        "datasets/governance/human_review_closeout_board.jsonl",
        "datasets/governance/p493_human_review_closeout_gap_audit.jsonl",
        closeout_metrics,
        closeout_checks,
        "closeout_rows",
        "awaiting_human_decision_rows",
        "closeout_id",
        ["closeout_id"],
        ["closeout_id", "lane_id", "status", "closeout_ready", "completion_ready", "requires_human_input", "packet_rows", "formal_decision_rows", "formal_decision_target", "formal_validator_report", "operator_open_first"],
        ["status"],
    ),
    "p494": cfg(
        "p494",
        "operator_work_receipt_manifest_consistency",
        "reports/operator_work_receipt_manifest_consistency_validation_report.json",
        None,
        None,
        "datasets/governance/p494_operator_work_receipt_manifest_consistency_gap_audit.jsonl",
        receipt_manifest_metrics,
        receipt_manifest_checks,
        "receipt_rows",
        "open_blocked_receipt_rows",
        summary_only=True,
    ),
    "p495": cfg(
        "p495",
        "top_tier_ready_to_verify_receipt",
        "reports/top_tier_model_ready_to_verify_receipt_report.json",
        "reports/top_tier_model_ready_to_verify_receipt_validation_report.json",
        "datasets/governance/top_tier_model_ready_to_verify_receipts.jsonl",
        "datasets/governance/p495_top_tier_ready_to_verify_receipt_gap_audit.jsonl",
        ready_receipt_metrics,
        ready_receipt_checks,
        "receipt_rows",
        "receipt_audit_rows",
        "workstream_id",
        ["workstream_id"],
        ["workstream_id", "title", "source_status", "verification_status", "commands_ok", "evidence_ok", "completion_ready", "safe_for_training_import", "safe_for_model_claim", "release_ready", "blocked_lanes_executed", "policy"],
        ["verification_status"],
    ),
    "p496": cfg(
        "p496",
        "non_human_ready_to_verify_receipt",
        "reports/non_human_ready_to_verify_receipt_report.json",
        "reports/non_human_ready_to_verify_receipt_validation_report.json",
        "datasets/governance/non_human_ready_to_verify_receipts.jsonl",
        "datasets/governance/p496_non_human_ready_to_verify_receipt_gap_audit.jsonl",
        ready_receipt_metrics,
        ready_receipt_checks,
        "receipt_rows",
        "receipt_audit_rows",
        "workstream_id",
        ["workstream_id"],
        ["workstream_id", "title", "source_status", "verification_status", "commands_ok", "evidence_ok", "completion_ready", "safe_for_model_claim", "release_ready", "blocked_lanes_executed", "policy"],
        ["verification_status"],
    ),
    "p497": cfg(
        "p497",
        "stage25_operator_docs_sync_receipt",
        "reports/stage25_operator_docs_dynamic_status_sync_report.json",
        "reports/stage25_operator_docs_sync_current_receipt_validation_report.json",
        None,
        "datasets/governance/p497_stage25_operator_docs_sync_receipt_gap_audit.jsonl",
        docs_sync_metrics,
        docs_sync_checks,
        "target_rows",
        "stale_rows",
        summary_only=True,
    ),
    "p498": cfg(
        "p498",
        "safe_training_pipeline_current_receipt",
        "reports/safe_training_pipeline_run.json",
        "reports/safe_training_pipeline_current_receipt_validation_report.json",
        None,
        "datasets/governance/p498_safe_training_pipeline_current_receipt_gap_audit.jsonl",
        pipeline_metrics,
        pipeline_checks,
        "pipeline_steps_run",
        "pipeline_failed_steps",
        summary_only=True,
    ),
    "p499": cfg(
        "p499",
        "local_release_consistency_receipt",
        "reports/local_release_consistency_receipt_current_validation_report.json",
        None,
        None,
        "datasets/governance/p499_local_release_consistency_receipt_gap_audit.jsonl",
        release_consistency_metrics,
        release_consistency_checks,
        "semantic_input_rows",
        "source_failure_count",
        summary_only=True,
    ),
    "p500": cfg(
        "p500",
        "stage25_fail_closed_validation_current_receipt",
        "reports/stage25_fail_closed_validation_current_receipt_validation_report.json",
        None,
        None,
        "datasets/governance/p500_stage25_fail_closed_validation_current_receipt_gap_audit.jsonl",
        stage25_metrics,
        stage25_checks,
        "command_rows",
        "source_failure_count",
        summary_only=True,
    ),
    "p501": cfg(
        "p501",
        "ready_to_verify_promotion",
        "reports/ready_to_verify_promotion_board.json",
        "reports/ready_to_verify_promotion_validation_report.json",
        None,
        "datasets/governance/p501_ready_to_verify_promotion_gap_audit.jsonl",
        promotion_metrics,
        promotion_checks,
        "source_audit_rows",
        "verified_blocked_rows",
        "audit_id",
        ["audit_id"],
        ["audit_id", "scope", "workstream_id", "title", "receipt_valid", "promotion_status", "automatic_promotion_allowed", "workstream_completion_ready", "execution_ready", "safe_for_training_import", "safe_for_model_claim", "customer_delivery_ready", "release_ready", "selected_variant_rows", "remaining_blockers", "policy"],
        [],
    ),
    "p502": cfg(
        "p502",
        "local_release_safety_guard_link",
        "reports/local_release_safety_guard_link_validation_report.json",
        "reports/local_release_safety_guard_links_current_validation_report.json",
        None,
        "datasets/governance/p502_local_release_safety_guard_link_gap_audit.jsonl",
        guard_metrics,
        guard_checks,
        "guard_link_audit_rows",
        "source_failure_count",
        summary_only=True,
    ),
    "p503": cfg(
        "p503",
        "safe_training_pipeline_receipt_atomicity",
        "reports/safe_training_pipeline_receipt_atomicity_regression_report.json",
        None,
        None,
        "datasets/governance/p503_safe_training_pipeline_receipt_atomicity_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p504": cfg(
        "p504",
        "local_release_consistency_receipt_atomicity",
        "reports/local_release_consistency_receipt_atomicity_regression_report.json",
        None,
        None,
        "datasets/governance/p504_local_release_consistency_receipt_atomicity_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p505": cfg(
        "p505",
        "local_release_terminal_defer_mode",
        "reports/local_release_terminal_defer_mode_regression_report.json",
        None,
        None,
        "datasets/governance/p505_local_release_terminal_defer_mode_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p506": cfg(
        "p506",
        "local_release_consistency_semantic_policy_current",
        "reports/local_release_consistency_semantic_policy_current_regression_report.json",
        None,
        None,
        "datasets/governance/p506_local_release_consistency_semantic_policy_current_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p507": cfg(
        "p507",
        "data_lake_artifact_integrity",
        "reports/data_lake_artifact_integrity_regression_report.json",
        None,
        None,
        "datasets/governance/p507_data_lake_artifact_integrity_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p508": cfg(
        "p508",
        "local_release_safety_guard_link_atomicity",
        "reports/local_release_safety_guard_links_atomicity_regression_report.json",
        None,
        None,
        "datasets/governance/p508_local_release_safety_guard_link_atomicity_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p509": cfg(
        "p509",
        "local_release_safety_guard_link_current_atomicity",
        "reports/local_release_safety_guard_links_current_regression_atomicity_regression_report.json",
        None,
        None,
        "datasets/governance/p509_local_release_safety_guard_link_current_atomicity_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p510": cfg(
        "p510",
        "data_lake_volatile_exemption",
        "reports/data_lake_volatile_exemption_safety_regression_report.json",
        None,
        None,
        "datasets/governance/p510_data_lake_volatile_exemption_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p511": cfg(
        "p511",
        "data_lake_live_content_integrity",
        "reports/data_lake_live_content_integrity_regression_report.json",
        None,
        None,
        "datasets/governance/p511_data_lake_live_content_integrity_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p512": cfg(
        "p512",
        "local_release_live_integrity_binding",
        "reports/local_release_live_integrity_binding_regression_report.json",
        None,
        None,
        "datasets/governance/p512_local_release_live_integrity_binding_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p513": cfg(
        "p513",
        "data_lake_release_input_contract_policy",
        "reports/data_lake_release_input_contract_policy_validation_report.json",
        None,
        None,
        "datasets/governance/p513_data_lake_release_input_contract_policy_gap_audit.jsonl",
        policy_receipt_metrics,
        policy_receipt_checks,
        "policy_receipt_audit_rows",
        "source_failure_count",
        summary_only=True,
    ),
    "p514": cfg(
        "p514",
        "data_lake_release_input_contract_policy_regression",
        "reports/data_lake_release_input_contract_policy_regression_report.json",
        None,
        None,
        "datasets/governance/p514_data_lake_release_input_contract_policy_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p515": cfg(
        "p515",
        "local_release_contract_policy_binding",
        "reports/local_release_contract_policy_binding_regression_report.json",
        None,
        None,
        "datasets/governance/p515_local_release_contract_policy_binding_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p516": cfg(
        "p516",
        "safe_training_pipeline_bootstrap_release_consistency",
        "reports/safe_training_pipeline_bootstrap_release_consistency_regression_report.json",
        None,
        None,
        "datasets/governance/p516_safe_training_pipeline_bootstrap_release_consistency_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p517": cfg(
        "p517",
        "local_release_high_risk_summary_safety",
        "reports/local_release_high_risk_summary_safety_regression_report.json",
        None,
        None,
        "datasets/governance/p517_local_release_high_risk_summary_safety_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p518": cfg(
        "p518",
        "local_release_high_risk_coverage_safety",
        "reports/local_release_high_risk_coverage_safety_regression_report.json",
        None,
        None,
        "datasets/governance/p518_local_release_high_risk_coverage_safety_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p519": cfg(
        "p519",
        "safe_training_pipeline_current_receipt_regression",
        "reports/safe_training_pipeline_current_receipt_regression_report.json",
        None,
        None,
        "datasets/governance/p519_safe_training_pipeline_current_receipt_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p520": cfg(
        "p520",
        "local_release_consistency_receipt_current_regression",
        "reports/local_release_consistency_receipt_current_regression_report.json",
        None,
        None,
        "datasets/governance/p520_local_release_consistency_receipt_current_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p521": cfg(
        "p521",
        "local_release_consistency_semantic_policy_regression",
        "reports/local_release_consistency_semantic_policy_regression_report.json",
        None,
        None,
        "datasets/governance/p521_local_release_consistency_semantic_policy_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p522": cfg(
        "p522",
        "local_release_consistency_semantic_policy_atomicity_regression",
        "reports/local_release_consistency_semantic_policy_atomicity_regression_report.json",
        None,
        None,
        "datasets/governance/p522_local_release_consistency_semantic_policy_atomicity_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p523": cfg(
        "p523",
        "stage25_operator_docs_sync_contract_policy",
        "reports/stage25_operator_docs_sync_contract_policy_validation_report.json",
        "reports/stage25_operator_docs_sync_contract_policy_regression_report.json",
        None,
        "datasets/governance/p523_stage25_operator_docs_sync_contract_policy_gap_audit.jsonl",
        stage25_contract_policy_metrics,
        stage25_contract_policy_checks,
        "policy_audit_rows",
        "source_failure_count",
        summary_only=True,
    ),
    "p524": cfg(
        "p524",
        "stage25_operator_docs_dynamic_status_sync",
        "reports/stage25_operator_docs_dynamic_status_sync_regression_report.json",
        None,
        None,
        "datasets/governance/p524_stage25_operator_docs_dynamic_status_sync_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p525": cfg(
        "p525",
        "stage25_operator_docs_dynamic_status_sync_current",
        "reports/stage25_operator_docs_dynamic_status_sync_regression_current_validation_report.json",
        None,
        None,
        "datasets/governance/p525_stage25_operator_docs_dynamic_status_sync_current_gap_audit.jsonl",
        stage25_dynamic_current_metrics,
        stage25_dynamic_current_checks,
        "current_validation_audit_rows",
        "source_failure_count",
        summary_only=True,
    ),
    "p526": cfg(
        "p526",
        "stage25_operator_docs_dynamic_status_sync_current_regression",
        "reports/stage25_operator_docs_dynamic_status_sync_regression_current_regression_report.json",
        None,
        None,
        "datasets/governance/p526_stage25_operator_docs_dynamic_status_sync_current_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p527": cfg(
        "p527",
        "stage25_operator_docs_dynamic_status_sync_atomicity",
        "reports/stage25_operator_docs_dynamic_status_sync_regression_atomicity_regression_report.json",
        None,
        None,
        "datasets/governance/p527_stage25_operator_docs_dynamic_status_sync_atomicity_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p528": cfg(
        "p528",
        "stage25_operator_docs_sync_contract_policy_regression",
        "reports/stage25_operator_docs_sync_contract_policy_regression_report.json",
        None,
        None,
        "datasets/governance/p528_stage25_operator_docs_sync_contract_policy_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p529": cfg(
        "p529",
        "stage25_operator_docs_sync_current_receipt_regression",
        "reports/stage25_operator_docs_sync_current_receipt_regression_report.json",
        None,
        None,
        "datasets/governance/p529_stage25_operator_docs_sync_current_receipt_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p530": cfg(
        "p530",
        "stage25_operator_docs_sync_terminal_recovery_regression",
        "reports/stage25_operator_docs_sync_terminal_recovery_regression_report.json",
        None,
        None,
        "datasets/governance/p530_stage25_operator_docs_sync_terminal_recovery_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p531": cfg(
        "p531",
        "controlled_release_guard_order_validation_receipt",
        "reports/enzyme_agent_controlled_release_guard_order_validation_report.json",
        None,
        None,
        "datasets/governance/p531_controlled_release_guard_order_validation_receipt_gap_audit.jsonl",
        policy_receipt_metrics,
        policy_receipt_checks,
        "policy_receipt_audit_rows",
        "source_failure_count",
        summary_only=True,
    ),
    "p532": cfg(
        "p532",
        "controlled_release_guard_order_regression",
        "reports/enzyme_agent_controlled_release_guard_order_regression_report.json",
        None,
        None,
        "datasets/governance/p532_controlled_release_guard_order_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p533": cfg(
        "p533",
        "controlled_release_guard_order_current_validation_receipt",
        "reports/enzyme_agent_controlled_release_guard_order_current_validation_report.json",
        None,
        None,
        "datasets/governance/p533_controlled_release_guard_order_current_validation_receipt_gap_audit.jsonl",
        policy_receipt_metrics,
        policy_receipt_checks,
        "policy_receipt_audit_rows",
        "source_failure_count",
        summary_only=True,
    ),
    "p534": cfg(
        "p534",
        "controlled_release_guard_order_current_regression",
        "reports/enzyme_agent_controlled_release_guard_order_current_regression_report.json",
        None,
        None,
        "datasets/governance/p534_controlled_release_guard_order_current_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p535": cfg(
        "p535",
        "controlled_release_guard_order_atomicity_regression",
        "reports/enzyme_agent_controlled_release_guard_order_atomicity_regression_report.json",
        None,
        None,
        "datasets/governance/p535_controlled_release_guard_order_atomicity_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p536": cfg(
        "p536",
        "stage25_remaining_blocker_cross_binding",
        "reports/stage25_remaining_blocker_cross_binding_validation_report.json",
        None,
        None,
        "datasets/governance/p536_stage25_remaining_blocker_cross_binding_gap_audit.jsonl",
        stage25_blocker_cross_binding_metrics,
        stage25_blocker_cross_binding_checks,
        "source_expected_blocker_rows",
        "source_blocked_status_rows",
        summary_only=True,
    ),
    "p537": cfg(
        "p537",
        "stage25_remaining_blocker_cross_binding_regression",
        "reports/stage25_remaining_blocker_cross_binding_regression_report.json",
        None,
        None,
        "datasets/governance/p537_stage25_remaining_blocker_cross_binding_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p538": cfg(
        "p538",
        "controlled_execution_wave_pair_atomicity_regression",
        "reports/enzyme_agent_controlled_execution_wave_pair_atomicity_regression_report.json",
        None,
        None,
        "datasets/governance/p538_controlled_execution_wave_pair_atomicity_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p539": cfg(
        "p539",
        "enzyme_agent_execution_receipt_gate",
        "reports/enzyme_agent_execution_receipt_gate_report.json",
        "reports/enzyme_agent_execution_receipt_gate_validation_report.json",
        None,
        "datasets/governance/p539_enzyme_agent_execution_receipt_gate_gap_audit.jsonl",
        execution_receipt_gate_metrics,
        execution_receipt_gate_checks,
        "receipt_rows",
        "executed_failed_receipt_rows",
        summary_only=True,
    ),
    "p540": cfg(
        "p540",
        "enzyme_agent_execution_receipt_lineage",
        "reports/enzyme_agent_execution_receipt_lineage_validation_report.json",
        None,
        None,
        "datasets/governance/p540_enzyme_agent_execution_receipt_lineage_gap_audit.jsonl",
        execution_receipt_lineage_metrics,
        execution_receipt_lineage_checks,
        "receipt_rows",
        "executed_failed_rows",
        summary_only=True,
    ),
    "p541": cfg(
        "p541",
        "enzyme_agent_execution_receipt_proof_current",
        "reports/enzyme_agent_execution_receipt_proof_current_validation_report.json",
        None,
        None,
        "datasets/governance/p541_enzyme_agent_execution_receipt_proof_current_gap_audit.jsonl",
        atomic_policy_receipt_metrics,
        atomic_policy_receipt_checks,
        "atomic_policy_receipt_audit_rows",
        "source_failure_count",
        summary_only=True,
    ),
    "p542": cfg(
        "p542",
        "enzyme_agent_execution_receipt_proof_current_regression",
        "reports/enzyme_agent_execution_receipt_proof_current_regression_report.json",
        None,
        None,
        "datasets/governance/p542_enzyme_agent_execution_receipt_proof_current_regression_gap_audit.jsonl",
        regression_metrics,
        regression_checks,
        "regression_audit_rows",
        "source_failed_rows",
        summary_only=True,
    ),
    "p543": cfg(
        "p543",
        "enzyme_agent_execution_receipt_safety_regression",
        "reports/enzyme_agent_execution_receipt_safety_regression_report.json",
        None,
        None,
        "datasets/governance/p543_enzyme_agent_execution_receipt_safety_regression_gap_audit.jsonl",
        safety_regression_metrics,
        safety_regression_checks,
        "safety_regression_audit_rows",
        "source_failed_regression_cases",
        summary_only=True,
    ),
    "p544": cfg(
        "p544",
        "enzyme_agent_execution_eligibility_matrix",
        "reports/enzyme_agent_execution_eligibility_matrix_report.json",
        "reports/enzyme_agent_execution_eligibility_matrix_validation_report.json",
        None,
        "datasets/governance/p544_enzyme_agent_execution_eligibility_matrix_gap_audit.jsonl",
        execution_eligibility_metrics,
        execution_eligibility_checks,
        "action_rows",
        "executed_failed_rows",
        summary_only=True,
    ),
    "p545": cfg(
        "p545",
        "enzyme_agent_execution_eligibility_safety_regression",
        "reports/enzyme_agent_execution_eligibility_safety_regression_report.json",
        None,
        None,
        "datasets/governance/p545_enzyme_agent_execution_eligibility_safety_regression_gap_audit.jsonl",
        safety_regression_metrics,
        safety_regression_checks,
        "safety_regression_audit_rows",
        "source_failed_regression_cases",
        summary_only=True,
    ),
    "p546": cfg(
        "p546",
        "enzyme_agent_execution_outcome_dashboard",
        "reports/enzyme_agent_execution_outcome_dashboard_report.json",
        "reports/enzyme_agent_execution_outcome_dashboard_validation_report.json",
        None,
        "datasets/governance/p546_enzyme_agent_execution_outcome_dashboard_gap_audit.jsonl",
        outcome_dashboard_metrics,
        outcome_dashboard_checks,
        "action_rows",
        "executed_failed_rows",
        summary_only=True,
    ),
    "p547": cfg(
        "p547",
        "top_tier_model_execution_board",
        "reports/top_tier_model_execution_board.json",
        "reports/top_tier_model_execution_validation_report.json",
        None,
        "datasets/governance/p547_top_tier_model_execution_board_gap_audit.jsonl",
        construction_board_metrics,
        construction_board_checks,
        "total_workstreams",
        "blocked_workstreams",
        summary_only=True,
    ),
    "p548": cfg(
        "p548",
        "non_human_construction_board",
        "reports/non_human_construction_board.json",
        "reports/non_human_construction_validation_report.json",
        None,
        "datasets/governance/p548_non_human_construction_board_gap_audit.jsonl",
        construction_board_metrics,
        construction_board_checks,
        "total_workstreams",
        "blocked_workstreams",
        summary_only=True,
    ),
    "p549": cfg(
        "p549",
        "parallel_hard_gate_execution_receipts",
        "reports/parallel_hard_gate_execution_receipts_report.json",
        "reports/parallel_hard_gate_execution_receipts_validation_report.json",
        None,
        "datasets/governance/p549_parallel_hard_gate_execution_receipts_gap_audit.jsonl",
        parallel_receipt_metrics,
        parallel_receipt_checks,
        "receipt_rows",
        "eligibility_changed_rows",
        summary_only=True,
    ),
    "p550": cfg(
        "p550",
        "execution_receipt_artifact_freshness",
        "reports/execution_receipt_artifact_freshness_validation_report.json",
        None,
        None,
        "datasets/governance/p550_execution_receipt_artifact_freshness_gap_audit.jsonl",
        freshness_metrics,
        freshness_checks,
        "total_receipts",
        "stale_receipts",
        summary_only=True,
    ),
    "p551": cfg(
        "p551",
        "execution_receipt_artifact_hash_coverage",
        "reports/execution_receipt_artifact_freshness_validation_report.json",
        None,
        None,
        "datasets/governance/p551_execution_receipt_artifact_hash_coverage_gap_audit.jsonl",
        freshness_hash_coverage_metrics,
        freshness_hash_coverage_checks,
        "total_receipts",
        "receipts_without_artifact_hash_fields",
        summary_only=True,
    ),
    "p552": cfg(
        "p552",
        "top_tier_model_execution_board_claim_boundary",
        "reports/top_tier_model_execution_board.json",
        "reports/top_tier_model_execution_validation_report.json",
        None,
        "datasets/governance/p552_top_tier_model_execution_board_claim_boundary_gap_audit.jsonl",
        board_claim_boundary_metrics,
        board_claim_boundary_checks,
        "total_workstreams",
        "blocked_workstreams",
        summary_only=True,
    ),
    "p553": cfg(
        "p553",
        "non_human_construction_board_claim_boundary",
        "reports/non_human_construction_board.json",
        "reports/non_human_construction_validation_report.json",
        None,
        "datasets/governance/p553_non_human_construction_board_claim_boundary_gap_audit.jsonl",
        board_claim_boundary_metrics,
        board_claim_boundary_checks,
        "total_workstreams",
        "blocked_workstreams",
        summary_only=True,
    ),
    "p554": cfg(
        "p554",
        "enzyme_agent_execution_outcome_formal_boundary",
        "reports/enzyme_agent_execution_outcome_dashboard_report.json",
        "reports/enzyme_agent_execution_outcome_dashboard_validation_report.json",
        None,
        "datasets/governance/p554_enzyme_agent_execution_outcome_formal_boundary_gap_audit.jsonl",
        outcome_formal_boundary_metrics,
        outcome_formal_boundary_checks,
        "action_rows",
        "claim_eligible_rows",
        summary_only=True,
    ),
    "p555": cfg(
        "p555",
        "parallel_hard_gate_execution_decision_boundary",
        "reports/parallel_hard_gate_execution_receipts_report.json",
        "reports/parallel_hard_gate_execution_receipts_validation_report.json",
        None,
        "datasets/governance/p555_parallel_hard_gate_execution_decision_boundary_gap_audit.jsonl",
        parallel_decision_boundary_metrics,
        parallel_decision_boundary_checks,
        "receipt_rows",
        "eligibility_changed_rows",
        summary_only=True,
    ),
    "p556": cfg(
        "p556",
        "top_tier_ready_receipt_completion_boundary",
        "reports/top_tier_model_ready_to_verify_receipt_report.json",
        "reports/top_tier_model_ready_to_verify_receipt_validation_report.json",
        None,
        "datasets/governance/p556_top_tier_ready_receipt_completion_boundary_gap_audit.jsonl",
        ready_receipt_boundary_metrics,
        ready_receipt_boundary_checks,
        "receipt_rows",
        "invalid_receipt_rows",
        summary_only=True,
    ),
    "p557": cfg(
        "p557",
        "non_human_ready_receipt_completion_boundary",
        "reports/non_human_ready_to_verify_receipt_report.json",
        "reports/non_human_ready_to_verify_receipt_validation_report.json",
        None,
        "datasets/governance/p557_non_human_ready_receipt_completion_boundary_gap_audit.jsonl",
        ready_receipt_boundary_metrics,
        ready_receipt_boundary_checks,
        "receipt_rows",
        "invalid_receipt_rows",
        summary_only=True,
    ),
    "p558": cfg(
        "p558",
        "ready_to_verify_promotion_boundary",
        "reports/ready_to_verify_promotion_board.json",
        "reports/ready_to_verify_promotion_validation_report.json",
        None,
        "datasets/governance/p558_ready_to_verify_promotion_boundary_gap_audit.jsonl",
        promotion_metrics,
        promotion_checks,
        "source_audit_rows",
        "verified_blocked_rows",
        summary_only=True,
    ),
    "p559": cfg(
        "p559",
        "data_lake_live_integrity_boundary",
        "reports/data_lake_live_content_integrity_validation_report.json",
        None,
        None,
        "datasets/governance/p559_data_lake_live_integrity_boundary_gap_audit.jsonl",
        live_integrity_boundary_metrics,
        live_integrity_boundary_checks,
        "artifact_rows",
        "failure_count",
        summary_only=True,
    ),
    "p560": cfg(
        "p560",
        "local_release_consistency_boundary",
        "reports/local_release_manifest_fail_closed_consistency_validation_report.json",
        None,
        None,
        "datasets/governance/p560_local_release_consistency_boundary_gap_audit.jsonl",
        release_consistency_boundary_metrics,
        release_consistency_boundary_checks,
        "artifact_count",
        "failure_count",
        summary_only=True,
    ),
    "p561": cfg(
        "p561",
        "reviewed_numbering_hard_boundary",
        "reports/numbering_review_operator_queue.json",
        None,
        None,
        "datasets/governance/p561_reviewed_numbering_hard_boundary_gap_audit.jsonl",
        numbering_queue_boundary_metrics,
        numbering_queue_boundary_checks,
        "queue_rows",
        "open_numbering_rows",
        summary_only=True,
    ),
    "p562": cfg(
        "p562",
        "wet_lab_feedback_numeric_eligibility_boundary",
        "reports/experiment_feedback_intake_validation_report.json",
        "reports/experiment_feedback_trainability_audit_report.json",
        None,
        "datasets/governance/p562_wet_lab_feedback_numeric_eligibility_boundary_gap_audit.jsonl",
        feedback_numeric_boundary_metrics,
        feedback_numeric_boundary_checks,
        "numeric_training_eligible_rows",
        "trainability_training_eligible_rows",
        summary_only=True,
    ),
    "p563": cfg(
        "p563",
        "physics_ddg_backend_readiness_boundary",
        "reports/ddg_backend_readiness_report.json",
        None,
        None,
        "datasets/governance/p563_physics_ddg_backend_readiness_boundary_gap_audit.jsonl",
        ddg_readiness_boundary_metrics,
        ddg_readiness_boundary_checks,
        "ready_backend_count",
        "physics_backend_current_execution_rows",
        summary_only=True,
    ),
    "p564": cfg(
        "p564",
        "claim_readiness_matrix_hard_boundary",
        "reports/claim_readiness_matrix.json",
        "reports/claim_readiness_matrix_fail_closed_policy_validation_report.json",
        None,
        "datasets/governance/p564_claim_readiness_matrix_hard_boundary_gap_audit.jsonl",
        claim_matrix_boundary_metrics,
        claim_matrix_boundary_checks,
        "claim_rows",
        "claims_blocked",
        summary_only=True,
    ),
    "p565": cfg(
        "p565",
        "production_release_authorization_boundary",
        "reports/local_release_manifest.json",
        "reports/local_release_manifest_fail_closed_consistency_validation_report.json",
        None,
        "datasets/governance/p565_production_release_authorization_boundary_gap_audit.jsonl",
        production_release_boundary_metrics,
        production_release_boundary_checks,
        "artifact_count",
        "source_validation_failure_count",
        summary_only=True,
    ),
    "p566": cfg(
        "p566",
        "five_head_training_execution_boundary",
        "reports/multitask_training_readiness_report.json",
        "reports/multitask_training_readiness_validation_report.json",
        None,
        "datasets/governance/p566_five_head_training_execution_boundary_gap_audit.jsonl",
        five_head_training_boundary_metrics,
        five_head_training_boundary_checks,
        "ready_head_count",
        "strict_rows",
        summary_only=True,
    ),
    "p567": cfg(
        "p567",
        "validated_feature_index_training_label_boundary",
        "reports/validated_feature_index_report.json",
        "reports/validated_feature_index_validation_report.json",
        None,
        "datasets/governance/p567_validated_feature_index_training_label_boundary_gap_audit.jsonl",
        validated_feature_boundary_metrics,
        validated_feature_boundary_checks,
        "model_consumable_rows",
        "training_label_source_rows",
        summary_only=True,
    ),
    "p568": cfg(
        "p568",
        "model_artifact_claim_boundary",
        "reports/model_artifact_claim_guard_report.json",
        "reports/model_artifact_claim_guard_validation_report.json",
        None,
        "datasets/governance/p568_model_artifact_claim_boundary_gap_audit.jsonl",
        model_artifact_claim_boundary_metrics,
        model_artifact_claim_boundary_checks,
        "artifact_count",
        "claimable_model_artifact_count",
        summary_only=True,
    ),
    "p569": cfg(
        "p569",
        "local_release_guard_coverage_boundary",
        "reports/local_release_guard_coverage_validation_report.json",
        None,
        None,
        "datasets/governance/p569_local_release_guard_coverage_boundary_gap_audit.jsonl",
        local_release_guard_coverage_boundary_metrics,
        local_release_guard_coverage_boundary_checks,
        "guard_coverage_count",
        "guard_failure_count",
        summary_only=True,
    ),
    "p570": cfg(
        "p570",
        "training_readiness_quality_boundary",
        "reports/training_readiness_report.json",
        None,
        None,
        "datasets/governance/p570_training_readiness_quality_boundary_gap_audit.jsonl",
        training_readiness_quality_boundary_metrics,
        training_readiness_quality_boundary_checks,
        "quality_score",
        "source_blocker_count",
        summary_only=True,
    ),
    "p571": cfg(
        "p571",
        "five_head_training_execution_contract_boundary",
        "reports/five_head_training_execution_contract_report.json",
        "reports/five_head_training_execution_contract_validation_report.json",
        None,
        "datasets/governance/p571_five_head_training_execution_contract_boundary_gap_audit.jsonl",
        five_head_execution_contract_boundary_metrics,
        five_head_execution_contract_boundary_checks,
        "ready_head_count",
        "blocked_reason_count",
        summary_only=True,
    ),
    "p572": cfg(
        "p572",
        "model_quality_hard_gate_contract_boundary",
        "reports/model_quality_hard_gate_contract_report.json",
        "reports/model_quality_hard_gate_contract_validation_report.json",
        None,
        "datasets/governance/p572_model_quality_hard_gate_contract_boundary_gap_audit.jsonl",
        model_quality_hard_gate_boundary_metrics,
        model_quality_hard_gate_boundary_checks,
        "hard_gate_count",
        "unlocked_gate_count",
        summary_only=True,
    ),
    "p573": cfg(
        "p573",
        "tool_lane_evidence_boundary",
        "reports/tool_lane_evidence_pack.json",
        "reports/tool_lane_evidence_pack_validation_report.json",
        None,
        "datasets/governance/p573_tool_lane_evidence_boundary_gap_audit.jsonl",
        tool_lane_evidence_boundary_metrics,
        tool_lane_evidence_boundary_checks,
        "total_lanes",
        "blocked_lanes",
        summary_only=True,
    ),
    "p574": cfg(
        "p574",
        "human_target_source_runtime_boundary",
        "reports/human_target_source_runtime_manifest.json",
        "reports/human_target_source_runtime_manifest_validation_report.json",
        None,
        "datasets/governance/p574_human_target_source_runtime_boundary_gap_audit.jsonl",
        human_target_runtime_boundary_metrics,
        human_target_runtime_boundary_checks,
        "total_sources",
        "blocked_sources",
        summary_only=True,
    ),
    "p575": cfg(
        "p575",
        "human_target_source_unlock_checklist_boundary",
        "reports/human_target_source_unlock_checklist_report.json",
        "reports/human_target_source_unlock_checklist_validation_report.json",
        None,
        "datasets/governance/p575_human_target_source_unlock_checklist_boundary_gap_audit.jsonl",
        human_target_unlock_checklist_boundary_metrics,
        human_target_unlock_checklist_boundary_checks,
        "checklist_rows",
        "ready_to_unlock_rows",
        summary_only=True,
    ),
    "p576": cfg(
        "p576",
        "training_label_import_contract_boundary",
        "reports/training_label_import_contract_report.json",
        "reports/training_label_import_contract_validation_report.json",
        None,
        "datasets/governance/p576_training_label_import_contract_boundary_gap_audit.jsonl",
        training_label_import_contract_boundary_metrics,
        training_label_import_contract_boundary_checks,
        "training_import_eligible_rows",
        "claim_eligible_rows",
        summary_only=True,
    ),
    "p577": cfg(
        "p577",
        "wet_lab_feedback_authorization_contract_boundary",
        "reports/wet_lab_feedback_authorization_contract_report.json",
        "reports/wet_lab_feedback_authorization_contract_validation_report.json",
        None,
        "datasets/governance/p577_wet_lab_feedback_authorization_contract_boundary_gap_audit.jsonl",
        wet_lab_authorization_contract_boundary_metrics,
        wet_lab_authorization_contract_boundary_checks,
        "candidate_rows",
        "ready_for_training_import_rows",
        summary_only=True,
    ),
    "p578": cfg(
        "p578",
        "ddg_model_consumption_contract_boundary",
        "reports/ddg_model_consumption_contract_report.json",
        "reports/ddg_model_consumption_contract_validation_report.json",
        None,
        "datasets/governance/p578_ddg_model_consumption_contract_boundary_gap_audit.jsonl",
        ddg_consumption_contract_boundary_metrics,
        ddg_consumption_contract_boundary_checks,
        "thermompnn_proxy_rows",
        "pyrosetta_physics_rows",
        summary_only=True,
    ),
    "p579": cfg(
        "p579",
        "structure_feature_model_contract_boundary",
        "reports/structure_feature_model_contract_report.json",
        "reports/structure_feature_model_contract_validation_report.json",
        None,
        "datasets/governance/p579_structure_feature_model_contract_boundary_gap_audit.jsonl",
        structure_feature_contract_boundary_metrics,
        structure_feature_contract_boundary_checks,
        "model_consumable_reviewed_graph_rows",
        "unreviewed_coordinate_rows_excluded",
        summary_only=True,
    ),
    "p580": cfg(
        "p580",
        "advanced_model_feature_contract_boundary",
        "reports/advanced_model_feature_contract_report.json",
        "reports/advanced_model_feature_contract_validation_report.json",
        None,
        "datasets/governance/p580_advanced_model_feature_contract_boundary_gap_audit.jsonl",
        advanced_feature_contract_boundary_metrics,
        advanced_feature_contract_boundary_checks,
        "ready_feature_ref_count",
        "training_label_source_feature_ref_count",
        summary_only=True,
    ),
    "p581": cfg(
        "p581",
        "active_learning_trial_readiness_boundary",
        "reports/active_learning_trial_readiness_report.json",
        "reports/active_learning_trial_readiness_validation_report.json",
        None,
        "datasets/governance/p581_active_learning_trial_readiness_boundary_gap_audit.jsonl",
        active_learning_readiness_boundary_metrics,
        active_learning_readiness_boundary_checks,
        "draft_rows",
        "blocker_count",
        summary_only=True,
    ),
    "p582": cfg(
        "p582",
        "benchmark_readiness_packet_boundary",
        "reports/benchmark_readiness_packet_report.json",
        "reports/benchmark_readiness_packet_validation_report.json",
        None,
        "datasets/governance/p582_benchmark_readiness_packet_boundary_gap_audit.jsonl",
        benchmark_packet_boundary_metrics,
        benchmark_packet_boundary_checks,
        "packet_rows",
        "invalid_gap_rows",
        summary_only=True,
    ),
    "p583": cfg(
        "p583",
        "enzyme_tool_contract_boundary",
        "reports/enzyme_tool_contract_validation_report.json",
        None,
        None,
        "datasets/governance/p583_enzyme_tool_contract_boundary_gap_audit.jsonl",
        enzyme_tool_contract_boundary_metrics,
        enzyme_tool_contract_boundary_checks,
        "contract_rows",
        "training_write_actions",
        summary_only=True,
    ),
    "p584": cfg(
        "p584",
        "foreign_tool_readiness_boundary",
        "reports/foreign_tool_readiness_report.json",
        None,
        None,
        "datasets/governance/p584_foreign_tool_readiness_boundary_gap_audit.jsonl",
        foreign_tool_readiness_boundary_metrics,
        foreign_tool_readiness_boundary_checks,
        "tool_rows",
        "non_ready_tool_rows",
        summary_only=True,
    ),
    "p585": cfg(
        "p585",
        "msa_runtime_readiness_boundary",
        "reports/msa_runtime_readiness_report.json",
        None,
        None,
        "datasets/governance/p585_msa_runtime_readiness_boundary_gap_audit.jsonl",
        msa_runtime_readiness_boundary_metrics,
        msa_runtime_readiness_boundary_checks,
        "target_rows",
        "blocker_count",
        summary_only=True,
    ),
    "p586": cfg(
        "p586",
        "enzyme_resource_retrieval_plan_boundary",
        "reports/enzyme_resource_retrieval_plan_report.json",
        "reports/enzyme_resource_retrieval_plan_validation_report.json",
        None,
        "datasets/governance/p586_enzyme_resource_retrieval_plan_boundary_gap_audit.jsonl",
        resource_retrieval_plan_boundary_metrics,
        resource_retrieval_plan_boundary_checks,
        "action_rows",
        "blocked_requires_human_decision_rows",
        summary_only=True,
    ),
    "p587": cfg(
        "p587",
        "enzyme_agent_result_validation_boundary",
        "reports/enzyme_agent_result_validation_report.json",
        None,
        None,
        "datasets/governance/p587_enzyme_agent_result_validation_boundary_gap_audit.jsonl",
        agent_result_validation_boundary_metrics,
        agent_result_validation_boundary_checks,
        "artifact_ref_count",
        "selected_variant_rows",
        summary_only=True,
    ),
    "p588": cfg(
        "p588",
        "enzyme_agent_result_safety_regression_boundary",
        "reports/enzyme_agent_result_safety_regression_report.json",
        None,
        None,
        "datasets/governance/p588_enzyme_agent_result_safety_regression_boundary_gap_audit.jsonl",
        agent_result_safety_regression_boundary_metrics,
        agent_result_safety_regression_boundary_checks,
        "case_rows",
        "failed_regression_cases",
        summary_only=True,
    ),
    "p589": cfg(
        "p589",
        "enzyme_agent_trace_audit_boundary",
        "reports/enzyme_agent_trace_audit_report.json",
        "reports/enzyme_agent_trace_audit_validation_report.json",
        None,
        "datasets/governance/p589_enzyme_agent_trace_audit_boundary_gap_audit.jsonl",
        agent_trace_audit_boundary_metrics,
        agent_trace_audit_boundary_checks,
        "trace_rows",
        "executed_action_count",
        summary_only=True,
    ),
    "p590": cfg(
        "p590",
        "enzyme_agent_controlled_release_order_current_boundary",
        "reports/enzyme_agent_controlled_release_guard_order_current_validation_report.json",
        None,
        None,
        "datasets/governance/p590_enzyme_agent_controlled_release_order_current_boundary_gap_audit.jsonl",
        controlled_release_order_current_boundary_metrics,
        controlled_release_order_current_boundary_checks,
        "failure_count",
        "failure_count",
        summary_only=True,
    ),
    "p591": cfg(
        "p591",
        "governance_readiness_boundary",
        "reports/governance_readiness_report.json",
        None,
        None,
        "datasets/governance/p591_governance_readiness_boundary_gap_audit.jsonl",
        governance_readiness_boundary_metrics,
        governance_readiness_boundary_checks,
        "external_source_rows",
        "governance_blocker_count",
        summary_only=True,
    ),
    "p592": cfg(
        "p592",
        "biosecurity_readiness_boundary",
        "reports/biosecurity_readiness_report.json",
        None,
        None,
        "datasets/governance/p592_biosecurity_readiness_boundary_gap_audit.jsonl",
        biosecurity_readiness_boundary_metrics,
        biosecurity_readiness_boundary_checks,
        "decision_rows",
        "approved_for_ordering_rows",
        summary_only=True,
    ),
    "p593": cfg(
        "p593",
        "workstream_acceptance_boundary",
        "reports/workstream_acceptance_gates.json",
        "reports/workstream_acceptance_decision_validation_report.json",
        None,
        "datasets/governance/p593_workstream_acceptance_boundary_gap_audit.jsonl",
        workstream_acceptance_boundary_metrics,
        workstream_acceptance_boundary_checks,
        "total_streams",
        "missing_stream_decision_rows",
        summary_only=True,
    ),
    "p594": cfg(
        "p594",
        "sequence_ip_fto_decision_boundary",
        "reports/sequence_ip_fto_decision_validation_report.json",
        None,
        None,
        "datasets/governance/p594_sequence_ip_fto_decision_boundary_gap_audit.jsonl",
        sequence_ip_fto_boundary_metrics,
        sequence_ip_fto_boundary_checks,
        "packet_rows",
        "missing_delivery_decision_rows",
        summary_only=True,
    ),
    "p595": cfg(
        "p595",
        "model_claim_fail_closed_consistency_boundary",
        "reports/model_claim_fail_closed_consistency_report.json",
        None,
        None,
        "datasets/governance/p595_model_claim_fail_closed_consistency_boundary_gap_audit.jsonl",
        model_claim_consistency_boundary_metrics,
        model_claim_consistency_boundary_checks,
        "strict_rows",
        "blocked_claim_count",
        summary_only=True,
    ),
    "p596": cfg(
        "p596",
        "external_data_source_registry_boundary",
        "reports/external_data_source_registry_validation_report.json",
        None,
        None,
        "datasets/governance/p596_external_data_source_registry_boundary_gap_audit.jsonl",
        external_registry_boundary_metrics,
        external_registry_boundary_checks,
        "registry_source_rows",
        "registry_not_ready_source_count",
        summary_only=True,
    ),
    "p597": cfg(
        "p597",
        "operator_review_status_boundary",
        "reports/operator_review_status_report.json",
        None,
        None,
        "datasets/governance/p597_operator_review_status_boundary_gap_audit.jsonl",
        operator_status_boundary_metrics,
        operator_status_boundary_checks,
        "operator_action_rows",
        "operator_open_action_rows",
        summary_only=True,
    ),
    "p598": cfg(
        "p598",
        "human_review_release_consistency_boundary",
        "reports/human_review_release_consistency_validation_report.json",
        None,
        None,
        "datasets/governance/p598_human_review_release_consistency_boundary_gap_audit.jsonl",
        human_review_consistency_boundary_metrics,
        human_review_consistency_boundary_checks,
        "human_review_consistency_closeout_rows",
        "human_review_consistency_open_closeout_rows",
        summary_only=True,
    ),
    "p599": cfg(
        "p599",
        "claim_promotion_decision_boundary",
        "reports/claim_promotion_decision_validation_report.json",
        None,
        None,
        "datasets/governance/p599_claim_promotion_decision_boundary_gap_audit.jsonl",
        claim_promotion_decision_boundary_metrics,
        claim_promotion_decision_boundary_checks,
        "claim_promotion_target_count",
        "claim_promotion_missing_decision_count",
        summary_only=True,
    ),
    "p600": cfg(
        "p600",
        "claim_readiness_policy_current_boundary",
        "reports/claim_readiness_matrix_fail_closed_policy_current_validation_report.json",
        None,
        None,
        "datasets/governance/p600_claim_readiness_policy_current_boundary_gap_audit.jsonl",
        claim_policy_current_boundary_metrics,
        claim_policy_current_boundary_checks,
        "claim_policy_current_failure_count",
        "claim_policy_current_failure_count",
        summary_only=True,
    ),
    "p601": cfg(
        "p601",
        "structure_feature_hard_gate_operator_packet_boundary",
        "reports/structure_feature_hard_gate_operator_packet_validation_report.json",
        None,
        None,
        "datasets/governance/p601_structure_feature_hard_gate_operator_packet_boundary_gap_audit.jsonl",
        structure_feature_operator_packet_boundary_metrics,
        structure_feature_operator_packet_boundary_checks,
        "structure_feature_packet_rows",
        "structure_feature_completion_ready_rows",
        summary_only=True,
    ),
    "p602": cfg(
        "p602",
        "wet_lab_hard_gate_operator_packet_boundary",
        "reports/wet_lab_hard_gate_operator_packet_validation_report.json",
        None,
        None,
        "datasets/governance/p602_wet_lab_hard_gate_operator_packet_boundary_gap_audit.jsonl",
        wet_lab_hard_gate_operator_packet_boundary_metrics,
        wet_lab_hard_gate_operator_packet_boundary_checks,
        "wet_lab_hard_gate_packet_rows",
        "wet_lab_hard_gate_completion_ready_rows",
        summary_only=True,
    ),
    "p603": cfg(
        "p603",
        "benchmark_hard_gate_operator_packet_boundary",
        "reports/benchmark_hard_gate_operator_packet_validation_report.json",
        None,
        None,
        "datasets/governance/p603_benchmark_hard_gate_operator_packet_boundary_gap_audit.jsonl",
        benchmark_hard_gate_operator_packet_boundary_metrics,
        benchmark_hard_gate_operator_packet_boundary_checks,
        "benchmark_hard_gate_packet_rows",
        "benchmark_hard_gate_completion_ready_rows",
        summary_only=True,
    ),
    "p604": cfg(
        "p604",
        "substrate_fit_hard_gate_operator_packet_boundary",
        "reports/substrate_fit_hard_gate_operator_packet_validation_report.json",
        None,
        None,
        "datasets/governance/p604_substrate_fit_hard_gate_operator_packet_boundary_gap_audit.jsonl",
        substrate_fit_hard_gate_operator_packet_boundary_metrics,
        substrate_fit_hard_gate_operator_packet_boundary_checks,
        "substrate_fit_hard_gate_packet_rows",
        "substrate_fit_hard_gate_completion_ready_rows",
        summary_only=True,
    ),
    "p605": cfg(
        "p605",
        "review_draft_formal_boundary",
        "reports/review_draft_formal_boundary_validation_report.json",
        None,
        None,
        "datasets/governance/p605_review_draft_formal_boundary_gap_audit.jsonl",
        review_draft_formal_boundary_metrics,
        review_draft_formal_boundary_checks,
        "review_draft_total_rows",
        "review_draft_rows_counted_as_formal_decisions",
        summary_only=True,
    ),
    "p606": cfg(
        "p606",
        "activity_risk_formal_label_decision_boundary",
        "reports/activity_risk_formal_label_decision_validation_report.json",
        None,
        None,
        "datasets/governance/p606_activity_risk_formal_label_decision_boundary_gap_audit.jsonl",
        activity_risk_formal_label_decision_boundary_metrics,
        activity_risk_formal_label_decision_boundary_checks,
        "activity_risk_formal_decision_rows",
        "activity_risk_replicate_rows_counted_for_training",
        summary_only=True,
    ),
    "p607": cfg(
        "p607",
        "activity_risk_training_lineage_boundary",
        "reports/activity_risk_training_lineage_ledger_validation_report.json",
        None,
        None,
        "datasets/governance/p607_activity_risk_training_lineage_boundary_gap_audit.jsonl",
        activity_risk_lineage_boundary_metrics,
        activity_risk_lineage_boundary_checks,
        "activity_risk_lineage_ledger_rows",
        "activity_risk_lineage_replicate_count",
        summary_only=True,
    ),
    "p608": cfg(
        "p608",
        "feedback_training_import_semantic_guard_boundary",
        "reports/feedback_training_import_semantic_guard_validation_report.json",
        None,
        None,
        "datasets/governance/p608_feedback_training_import_semantic_guard_boundary_gap_audit.jsonl",
        feedback_training_import_semantic_guard_boundary_metrics,
        feedback_training_import_semantic_guard_boundary_checks,
        "feedback_training_guard_numeric_training_import_eligible",
        "feedback_training_guard_claim_eligible_rows",
        summary_only=True,
    ),
    "p609": cfg(
        "p609",
        "wet_lab_feedback_import_reconciliation_boundary",
        "reports/wet_lab_feedback_import_reconciliation_validation_report.json",
        None,
        None,
        "datasets/governance/p609_wet_lab_feedback_import_reconciliation_boundary_gap_audit.jsonl",
        wet_lab_feedback_import_reconciliation_boundary_metrics,
        wet_lab_feedback_import_reconciliation_boundary_checks,
        "wet_lab_import_reconciliation_contract_training_import_eligible_rows",
        "wet_lab_import_reconciliation_claim_eligible_rows",
        summary_only=True,
    ),
    "p610": cfg(
        "p610",
        "positive_claim_gate_quarantine_boundary",
        "reports/report_positive_claim_gate_quarantine_validation_report.json",
        None,
        None,
        "datasets/governance/p610_positive_claim_gate_quarantine_boundary_gap_audit.jsonl",
        positive_claim_gate_quarantine_boundary_metrics,
        positive_claim_gate_quarantine_boundary_checks,
        "positive_claim_gate_scanned_report_count",
        "positive_claim_gate_disallowed_true_hit_count",
        summary_only=True,
    ),
    "p611": cfg(
        "p611",
        "activity_risk_training_import_label_boundary",
        "reports/activity_risk_training_import_label_report.json",
        "reports/activity_risk_training_import_label_validation_report.json",
        None,
        "datasets/governance/p611_activity_risk_training_import_label_boundary_gap_audit.jsonl",
        activity_risk_training_import_label_boundary_metrics,
        activity_risk_training_import_label_boundary_checks,
        "activity_risk_import_label_rows",
        "activity_risk_import_training_execution_allowed",
        summary_only=True,
    ),
    "p612": cfg(
        "p612",
        "activity_risk_label_replicate_preflight_boundary",
        "reports/activity_risk_label_replicate_preflight_report.json",
        "reports/activity_risk_label_replicate_preflight_validation_report.json",
        None,
        "datasets/governance/p612_activity_risk_label_replicate_preflight_boundary_gap_audit.jsonl",
        activity_risk_label_replicate_preflight_boundary_metrics,
        activity_risk_label_replicate_preflight_boundary_checks,
        "activity_risk_replicate_preflight_rows",
        "activity_risk_replicate_ready_for_training_import_rows",
        summary_only=True,
    ),
    "p613": cfg(
        "p613",
        "feature_coverage_by_head_group_boundary",
        "reports/feature_coverage_by_head_group_report.json",
        "reports/feature_coverage_by_head_group_validation_report.json",
        None,
        "datasets/governance/p613_feature_coverage_by_head_group_boundary_gap_audit.jsonl",
        feature_coverage_by_head_group_boundary_metrics,
        feature_coverage_by_head_group_boundary_checks,
        "feature_coverage_by_head_group_coverage_rows",
        "feature_coverage_by_head_group_feature_rows_counted_as_labels",
        summary_only=True,
    ),
    "p614": cfg(
        "p614",
        "feature_coverage_gap_queue_boundary",
        "reports/feature_coverage_gap_queue_report.json",
        "reports/feature_coverage_gap_queue_validation_report.json",
        None,
        "datasets/governance/p614_feature_coverage_gap_queue_boundary_gap_audit.jsonl",
        feature_coverage_gap_queue_boundary_metrics,
        feature_coverage_gap_queue_boundary_checks,
        "feature_coverage_gap_queue_gap_count",
        "feature_coverage_gap_queue_training_label_source_rows",
        summary_only=True,
    ),
    "p615": cfg(
        "p615",
        "feature_label_boundary_quarantine_audit",
        "reports/feature_label_boundary_quarantine_report.json",
        None,
        None,
        "datasets/governance/p615_feature_label_boundary_quarantine_gap_audit.jsonl",
        feature_label_boundary_quarantine_audit_metrics,
        feature_label_boundary_quarantine_audit_checks,
        "feature_label_boundary_quarantine_label_contaminated_artifact_count",
        "feature_label_boundary_quarantine_excluded_from_index_artifact_count",
        summary_only=True,
    ),
    "p616": cfg(
        "p616",
        "benchmark_score_cache_validation_boundary",
        "reports/benchmark_score_cache_validation_report.json",
        None,
        None,
        "datasets/governance/p616_benchmark_score_cache_validation_boundary_gap_audit.jsonl",
        benchmark_score_cache_validation_boundary_metrics,
        benchmark_score_cache_validation_boundary_checks,
        "benchmark_score_cache_validation_benchmark_rows",
        "benchmark_score_cache_validation_invalid_rows",
        summary_only=True,
    ),
    "p617": cfg(
        "p617",
        "benchmark_coverage_dashboard_boundary",
        "reports/benchmark_coverage_dashboard.json",
        "reports/benchmark_coverage_dashboard_validation_report.json",
        None,
        "datasets/governance/p617_benchmark_coverage_dashboard_boundary_gap_audit.jsonl",
        benchmark_coverage_dashboard_boundary_metrics,
        benchmark_coverage_dashboard_boundary_checks,
        "benchmark_coverage_dashboard_benchmark_rows",
        "benchmark_coverage_dashboard_invalid_rows",
        summary_only=True,
    ),
    "p618": cfg(
        "p618",
        "five_head_benchmark_gap_plan_boundary",
        "reports/five_head_benchmark_gap_plan_report.json",
        "reports/five_head_benchmark_gap_plan_validation_report.json",
        None,
        "datasets/governance/p618_five_head_benchmark_gap_plan_boundary_gap_audit.jsonl",
        five_head_benchmark_gap_plan_boundary_metrics,
        five_head_benchmark_gap_plan_boundary_checks,
        "five_head_benchmark_gap_plan_action_rows",
        "five_head_benchmark_gap_plan_metric_claim_allowed_rows",
        summary_only=True,
    ),
    "p619": cfg(
        "p619",
        "benchmark_lane_machine_prereview_boundary",
        "reports/benchmark_lane_machine_prereview_report.json",
        None,
        None,
        "datasets/governance/p619_benchmark_lane_machine_prereview_boundary_gap_audit.jsonl",
        benchmark_lane_machine_prereview_boundary_metrics,
        benchmark_lane_machine_prereview_boundary_checks,
        "benchmark_lane_machine_prereview_lane_count",
        "benchmark_lane_machine_prereview_formal_decision_rows_observed",
        summary_only=True,
    ),
    "p620": cfg(
        "p620",
        "benchmark_lane_status_aggregate_boundary",
        "reports/benchmark_lane_status_aggregate_report.json",
        None,
        None,
        "datasets/governance/p620_benchmark_lane_status_aggregate_boundary_gap_audit.jsonl",
        benchmark_lane_status_aggregate_boundary_metrics,
        benchmark_lane_status_aggregate_boundary_checks,
        "benchmark_lane_status_aggregate_lane_count",
        "benchmark_lane_status_aggregate_training_import_written_rows",
        summary_only=True,
    ),
    "p621": cfg(
        "p621",
        "ddg_executable_probe_boundary",
        "reports/ddg_executable_probe_report.json",
        None,
        None,
        "datasets/governance/p621_ddg_executable_probe_boundary_gap_audit.jsonl",
        ddg_executable_probe_boundary_metrics,
        ddg_executable_probe_boundary_checks,
        "ddg_executable_probe_backend_rows",
        "ddg_executable_probe_claim_eligible_rows_now",
        summary_only=True,
    ),
    "p622": cfg(
        "p622",
        "pyrosetta_physical_smoke_boundary",
        "reports/pyrosetta_physical_smoke_bootstrap_report.json",
        None,
        None,
        "datasets/governance/p622_pyrosetta_physical_smoke_boundary_gap_audit.jsonl",
        pyrosetta_physical_smoke_boundary_metrics,
        pyrosetta_physical_smoke_boundary_checks,
        "pyrosetta_physical_smoke_ddg_table_rows",
        "pyrosetta_physical_smoke_training_label_rows",
        summary_only=True,
    ),
    "p623": cfg(
        "p623",
        "pyrosetta_verified_ddg_feature_boundary",
        "reports/pyrosetta_verified_mutation_ddg_feature_report.json",
        "reports/pyrosetta_verified_mutation_ddg_feature_validation_report.json",
        None,
        "datasets/governance/p623_pyrosetta_verified_ddg_feature_boundary_gap_audit.jsonl",
        pyrosetta_verified_ddg_feature_boundary_metrics,
        pyrosetta_verified_ddg_feature_boundary_checks,
        "pyrosetta_verified_ddg_feature_computed_feature_rows",
        "pyrosetta_verified_ddg_feature_quality_blocked_rows",
        summary_only=True,
    ),
    "p624": cfg(
        "p624",
        "foldx_physical_smoke_boundary",
        "reports/foldx_physical_smoke_bootstrap_validation_report.json",
        None,
        None,
        "datasets/governance/p624_foldx_physical_smoke_boundary_gap_audit.jsonl",
        foldx_physical_smoke_boundary_metrics,
        foldx_physical_smoke_boundary_checks,
        "foldx_physical_smoke_blocker_count",
        "foldx_physical_smoke_ready_execution_plan_rows",
        summary_only=True,
    ),
    "p625": cfg(
        "p625",
        "ddg_backend_operator_packet_boundary",
        "reports/ddg_backend_operator_packet_report.json",
        "reports/ddg_backend_operator_packet_validation_report.json",
        None,
        "datasets/governance/p625_ddg_backend_operator_packet_boundary_gap_audit.jsonl",
        ddg_backend_operator_packet_boundary_metrics,
        ddg_backend_operator_packet_boundary_checks,
        "ddg_backend_operator_packet_packet_rows",
        "ddg_backend_operator_packet_completion_ready_rows",
        summary_only=True,
    ),
    "p626": cfg(
        "p626",
        "rosetta_physical_smoke_boundary",
        "reports/rosetta_physical_smoke_bootstrap_report.json",
        None,
        None,
        "datasets/governance/p626_rosetta_physical_smoke_boundary_gap_audit.jsonl",
        rosetta_physical_smoke_boundary_metrics,
        rosetta_physical_smoke_boundary_checks,
        "rosetta_physical_smoke_artifact_count",
        "rosetta_physical_smoke_artifact_count",
        summary_only=True,
    ),
    "p627": cfg(
        "p627",
        "pyrosetta_verified_mutation_ddg_concordance_boundary",
        "reports/pyrosetta_verified_mutation_ddg_concordance_report.json",
        "reports/pyrosetta_verified_mutation_ddg_concordance_validation_report.json",
        None,
        "datasets/governance/p627_pyrosetta_verified_mutation_ddg_concordance_boundary_gap_audit.jsonl",
        pyrosetta_concordance_boundary_metrics,
        pyrosetta_concordance_boundary_checks,
        "pyrosetta_concordance_input_feature_rows",
        "pyrosetta_concordance_quality_blocked_rows",
        summary_only=True,
    ),
    "p628": cfg(
        "p628",
        "pyrosetta_local_install_probe_boundary",
        "reports/pyrosetta_local_install_probe_report.json",
        "reports/pyrosetta_local_install_probe_validation_report.json",
        None,
        "datasets/governance/p628_pyrosetta_local_install_probe_boundary_gap_audit.jsonl",
        pyrosetta_local_install_probe_boundary_metrics,
        pyrosetta_local_install_probe_boundary_checks,
        "pyrosetta_install_probe_wheel_present",
        "pyrosetta_install_probe_ready_for_ddg_smoke",
        summary_only=True,
    ),
    "p629": cfg(
        "p629",
        "ddg_physical_runtime_receipt_preflight_boundary",
        "reports/ddg_physical_runtime_receipt_preflight_report.json",
        "reports/ddg_physical_runtime_receipt_preflight_validation_report.json",
        None,
        "datasets/governance/p629_ddg_physical_runtime_receipt_preflight_boundary_gap_audit.jsonl",
        ddg_runtime_preflight_boundary_metrics,
        ddg_runtime_preflight_boundary_checks,
        "ddg_runtime_preflight_physical_backend_rows",
        "ddg_runtime_preflight_blocked_physical_backend_rows",
        summary_only=True,
    ),
    "p630": cfg(
        "p630",
        "ddg_backend_runtime_receipt_validation_boundary",
        "reports/ddg_backend_runtime_receipt_validation_report.json",
        None,
        None,
        "datasets/governance/p630_ddg_backend_runtime_receipt_validation_boundary_gap_audit.jsonl",
        ddg_runtime_receipt_validation_boundary_metrics,
        ddg_runtime_receipt_validation_boundary_checks,
        "ddg_runtime_receipt_receipt_rows",
        "ddg_runtime_receipt_missing_backend_rows",
        summary_only=True,
    ),
    "p631": cfg(
        "p631",
        "ddg_physical_smoke_harness_boundary",
        "reports/ddg_physical_smoke_harness_report.json",
        "reports/ddg_physical_smoke_harness_validation_report.json",
        None,
        "datasets/governance/p631_ddg_physical_smoke_harness_boundary_gap_audit.jsonl",
        ddg_physical_smoke_harness_boundary_metrics,
        ddg_physical_smoke_harness_boundary_checks,
        "ddg_physical_smoke_harness_contract_rows",
        "ddg_physical_smoke_harness_can_execute_now_rows",
        summary_only=True,
    ),
    "p632": cfg(
        "p632",
        "ddg_proxy_physics_claim_boundary",
        "reports/ddg_proxy_not_physics_claim_validation_report.json",
        None,
        None,
        "datasets/governance/p632_ddg_proxy_physics_claim_boundary_gap_audit.jsonl",
        ddg_proxy_physics_claim_boundary_metrics,
        ddg_proxy_physics_claim_boundary_checks,
        "ddg_proxy_physics_proxy_backend_ready",
        "ddg_proxy_physics_physics_ddg_ready",
        summary_only=True,
    ),
    "p633": cfg(
        "p633",
        "execution_receipt_freshness_boundary",
        "reports/execution_receipt_artifact_freshness_validation_report.json",
        None,
        None,
        "datasets/governance/p633_execution_receipt_freshness_boundary_gap_audit.jsonl",
        execution_receipt_freshness_boundary_metrics,
        execution_receipt_freshness_boundary_checks,
        "execution_receipt_freshness_total_receipts",
        "execution_receipt_freshness_receipts_without_hash_fields",
        summary_only=True,
    ),
    "p634": cfg(
        "p634",
        "parallel_hard_gate_execution_boundary",
        "reports/parallel_hard_gate_execution_receipts_report.json",
        "reports/parallel_hard_gate_execution_receipts_validation_report.json",
        None,
        "datasets/governance/p634_parallel_hard_gate_execution_boundary_gap_audit.jsonl",
        parallel_hard_gate_execution_boundary_metrics,
        parallel_hard_gate_execution_boundary_checks,
        "parallel_hard_gate_execution_receipt_rows",
        "parallel_hard_gate_execution_eligibility_changed_rows",
        summary_only=True,
    ),
    "p635": cfg(
        "p635",
        "ddg_backend_failure_boundary",
        "reports/ddg_backend_failure_diagnostic_report.json",
        None,
        None,
        "datasets/governance/p635_ddg_backend_failure_boundary_gap_audit.jsonl",
        ddg_backend_failure_boundary_metrics,
        ddg_backend_failure_boundary_checks,
        "ddg_backend_failure_ready_backend_count",
        "ddg_backend_failure_physics_backend_ready_count",
        summary_only=True,
    ),
    "p636": cfg(
        "p636",
        "human_review_closeout_current_boundary",
        "reports/human_review_closeout_board_validation_report.json",
        None,
        None,
        "datasets/governance/p636_human_review_closeout_current_boundary_gap_audit.jsonl",
        closeout_current_boundary_metrics,
        closeout_current_boundary_checks,
        "closeout_current_rows",
        "closeout_current_awaiting_human_decision_rows",
        summary_only=True,
    ),
    "p637": cfg(
        "p637",
        "operator_work_receipt_manifest_current_boundary",
        "reports/operator_work_receipt_manifest_consistency_validation_report.json",
        None,
        None,
        "datasets/governance/p637_operator_work_receipt_manifest_current_boundary_gap_audit.jsonl",
        receipt_manifest_current_boundary_metrics,
        receipt_manifest_current_boundary_checks,
        "receipt_manifest_current_receipt_rows",
        "receipt_manifest_current_open_blocked_receipt_rows",
        summary_only=True,
    ),
    "p638": cfg(
        "p638",
        "top_tier_ready_to_verify_current_boundary",
        "reports/top_tier_model_ready_to_verify_receipt_report.json",
        "reports/top_tier_model_ready_to_verify_receipt_validation_report.json",
        None,
        "datasets/governance/p638_top_tier_ready_to_verify_current_boundary_gap_audit.jsonl",
        ready_receipt_current_boundary_metrics,
        ready_receipt_current_boundary_checks,
        "ready_receipt_current_receipt_rows",
        "ready_receipt_current_valid_receipt_rows",
        summary_only=True,
    ),
    "p639": cfg(
        "p639",
        "non_human_ready_to_verify_current_boundary",
        "reports/non_human_ready_to_verify_receipt_report.json",
        "reports/non_human_ready_to_verify_receipt_validation_report.json",
        None,
        "datasets/governance/p639_non_human_ready_to_verify_current_boundary_gap_audit.jsonl",
        ready_receipt_current_boundary_metrics,
        ready_receipt_current_boundary_checks,
        "ready_receipt_current_receipt_rows",
        "ready_receipt_current_valid_receipt_rows",
        summary_only=True,
    ),
    "p640": cfg(
        "p640",
        "ready_to_verify_promotion_current_boundary",
        "reports/ready_to_verify_promotion_board.json",
        "reports/ready_to_verify_promotion_validation_report.json",
        None,
        "datasets/governance/p640_ready_to_verify_promotion_current_boundary_gap_audit.jsonl",
        promotion_metrics,
        promotion_checks,
        "source_audit_rows",
        "verified_blocked_rows",
        summary_only=True,
    ),
}

CONFIGS["p605"]["row_policy"] = (
    "P605 review-draft boundary audit only; draft markers remain audit observations "
    "and are not approvals, formal decisions, training imports, model claims, customer delivery authorization, "
    "release approval, deployment, sync, restart, or production execution."
)
