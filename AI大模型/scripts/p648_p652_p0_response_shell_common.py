#!/usr/bin/env python3
"""Shared builders and validators for P648-P674 P0 response shell layers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]

FALSE_FIELDS = (
    "training_import_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "customer_delivery_ready",
    "release_ready",
    "production_execution_allowed",
    "completion_ready",
)

DOWNSTREAM_FALSE_FLAGS = (
    "queue_dequeued",
    "response_received",
    "response_validated",
    "real_input_received",
    "reviewed_decision_written",
    "formal_intake_written",
    "runtime_receipt_written",
    "training_label_written",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def layer_row(config: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    out = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        config["id_field"]: f"{config['id']}::{row.get('plan_item_id')}",
        config["source_id_field"]: row.get(config["source_id_field"]),
        "preflight_id": row.get("preflight_id"),
        "queue_item_id": row.get("queue_item_id"),
        "response_slot_id": row.get("response_slot_id"),
        "handoff_id": row.get("handoff_id"),
        "dispatch_id": row.get("dispatch_id"),
        "packet_id": row.get("packet_id"),
        "plan_item_id": row.get("plan_item_id"),
        "priority": row.get("priority"),
        "workstream": row.get("workstream"),
        "packet_category": row.get("packet_category"),
        "required_input_type": row.get("required_input_type"),
        "response_schema": row.get("response_schema"),
        "dispatch_wave": row.get("dispatch_wave"),
        "dispatch_wave_name": row.get("dispatch_wave_name"),
        "dispatch_order": row.get("dispatch_order"),
        config["order_field"]: row.get(config["source_order_field"]),
        "operator_next_action": row.get("operator_next_action"),
        "acceptance_condition": row.get("acceptance_condition"),
        "source_refs": row.get("source_refs") or [],
        "status": config["status"],
        config["open_flag"]: True,
        config["empty_flag"]: True,
        config["blocked_flag"]: True,
        "model_claim_allowed": False,
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "policy": config["row_policy"],
    }
    for flag in DOWNSTREAM_FALSE_FLAGS + tuple(config["extra_false_flags"]):
        out[flag] = False
    for field in FALSE_FIELDS:
        out[field] = False
    return out


def build_layer(config: dict[str, Any]) -> int:
    source_report = load_json(config["source_report"])
    source_validation = load_json(config["source_validation"])
    source_rows = load_jsonl(config["source_jsonl"])
    rows = [layer_row(config, row) for row in source_rows]
    rows.sort(key=lambda row: (row.get("dispatch_wave"), row.get(config["order_field"])))

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "manifest_id": config["manifest_id"],
        "source_jsonl": rel(config["source_jsonl"]),
        "source_report": rel(config["source_report"]),
        "source_validation_report": rel(config["source_validation"]),
        "source_rows": source_report.get(config["source_count_field"]),
        "source_validation_success": source_validation.get("success"),
        config["count_field"]: len(rows),
        config["open_count_field"]: sum(1 for row in rows if row[config["open_flag"]] is True),
        config["empty_count_field"]: sum(1 for row in rows if row[config["empty_flag"]] is True),
        config["blocked_count_field"]: sum(1 for row in rows if row[config["blocked_flag"]] is True),
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "artifact_jsonl": rel(config["out_jsonl"]),
        "artifact_md": rel(config["out_md"]),
        "policy": config["report_policy"],
    }
    for flag in DOWNSTREAM_FALSE_FLAGS + tuple(config["extra_false_flags"]):
        report[f"{flag}_rows"] = sum(1 for row in rows if row.get(flag) is True)
    for field in FALSE_FIELDS:
        report[field] = False

    write_jsonl(config["out_jsonl"], rows)
    write_json(config["out_report"], report)
    lines = [
        f"# {config['title']}",
        "",
        f"Status: {config['status']}.",
        "",
        f"| {config['title_id_label']} | Workstream | Schema | Status |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row[config['id_field']]} | {row.get('workstream')} | {row.get('response_schema')} | {row.get('status')} |")
    lines.extend(["", config["md_policy"]])
    config["out_md"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest_id": config["manifest_id"],
        config["count_field"]: report[config["count_field"]],
        config["open_count_field"]: report[config["open_count_field"]],
        config["empty_count_field"]: report[config["empty_count_field"]],
        "response_received_rows": report["response_received_rows"],
        "output": str(config["out_report"]),
    }, ensure_ascii=False))
    return 0


def add_failure(failures: list[dict[str, Any]], condition: bool, check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_layer(config: dict[str, Any]) -> int:
    source_validation = load_json(config["source_validation"])
    source_rows = load_jsonl(config["source_jsonl"])
    report = load_json(config["out_report"])
    rows = load_jsonl(config["out_jsonl"])
    failures: list[dict[str, Any]] = []

    add_failure(failures, source_validation.get("success") is not True, "source_validation_success", source_validation.get("success"), True)
    add_failure(failures, len(rows) != len(source_rows), "rows_match_source", len(rows), len(source_rows))
    add_failure(failures, report.get(config["count_field"]) != len(rows), "report_rows_bound", report.get(config["count_field"]), len(rows))
    add_failure(failures, report.get(config["open_count_field"]) != len(rows), "all_rows_open", report.get(config["open_count_field"]), len(rows))
    add_failure(failures, report.get(config["empty_count_field"]) != len(rows), "all_rows_empty", report.get(config["empty_count_field"]), len(rows))
    add_failure(failures, report.get(config["blocked_count_field"]) != len(rows), "all_rows_blocked", report.get(config["blocked_count_field"]), len(rows))
    add_failure(failures, report.get("p0_unblocked") is not False, "p0_unblocked_false", report.get("p0_unblocked"), False)
    add_failure(failures, report.get("p0_completion_ready") is not False, "p0_completion_ready_false", report.get("p0_completion_ready"), False)
    for flag in DOWNSTREAM_FALSE_FLAGS + tuple(config["extra_false_flags"]):
        add_failure(failures, report.get(f"{flag}_rows") != 0, f"{flag}_rows_zero", report.get(f"{flag}_rows"), 0)
    for field in FALSE_FIELDS:
        add_failure(failures, report.get(field) is not False, f"report_{field}_false", report.get(field), False)

    ids = [row.get(config["id_field"]) for row in rows]
    add_failure(failures, len(ids) != len(set(ids)), "row_ids_unique", ids, "unique")
    source_ids = {row.get(config["source_id_field"]) for row in source_rows}
    add_failure(
        failures,
        {row.get(config["source_id_field"]) for row in rows} != source_ids,
        "source_ids_exactly_covered",
        {row.get(config["source_id_field"]) for row in rows},
        source_ids,
    )
    orders = [row.get(config["order_field"]) for row in rows]
    add_failure(failures, orders != sorted(orders), "order_sorted", orders, "ascending")
    for idx, row in enumerate(rows):
        add_failure(failures, row.get("status") != config["status"], f"row_status_{idx}", row.get("status"), config["status"])
        add_failure(failures, row.get(config["open_flag"]) is not True, f"row_open_{idx}", row.get(config["open_flag"]), True)
        add_failure(failures, row.get(config["empty_flag"]) is not True, f"row_empty_{idx}", row.get(config["empty_flag"]), True)
        add_failure(failures, row.get(config["blocked_flag"]) is not True, f"row_blocked_{idx}", row.get(config["blocked_flag"]), True)
        add_failure(failures, row.get("p0_unblocked") is not False, f"row_p0_unblocked_{idx}", row.get("p0_unblocked"), False)
        add_failure(failures, row.get("p0_completion_ready") is not False, f"row_p0_completion_ready_{idx}", row.get("p0_completion_ready"), False)
        for flag in DOWNSTREAM_FALSE_FLAGS + tuple(config["extra_false_flags"]):
            add_failure(failures, row.get(flag) is not False, f"row_{flag}_{idx}", row.get(flag), False)
        for field in FALSE_FIELDS:
            add_failure(failures, row.get(field) is not False, f"row_{field}_{idx}", row.get(field), False)

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "manifest_id": config["manifest_id"],
        config["count_field"]: len(rows),
        config["open_count_field"]: sum(1 for row in rows if row.get(config["open_flag"]) is True),
        config["empty_count_field"]: sum(1 for row in rows if row.get(config["empty_flag"]) is True),
        config["blocked_count_field"]: sum(1 for row in rows if row.get(config["blocked_flag"]) is True),
        "p0_unblocked": False,
        "p0_completion_ready": False,
        "failures": failures,
        "policy": config["validation_policy"],
    }
    for flag in DOWNSTREAM_FALSE_FLAGS + tuple(config["extra_false_flags"]):
        result[f"{flag}_rows"] = sum(1 for row in rows if row.get(flag) is True)
    for field in FALSE_FIELDS:
        result[field] = False
    write_json(config["out_validation"], result)
    print(json.dumps({
        "success": result["success"],
        config["count_field"]: result[config["count_field"]],
        config["open_count_field"]: result[config["open_count_field"]],
        "response_received_rows": result["response_received_rows"],
        "failures": len(failures),
        "output": str(config["out_validation"]),
    }, ensure_ascii=False))
    return 0 if result["success"] else 1


def cfg(
    pid: str,
    slug: str,
    manifest_id: str,
    source_slug: str,
    source_id_field: str,
    source_order_field: str,
    id_field: str,
    order_field: str,
    status: str,
    count_field: str,
    open_count_field: str,
    empty_count_field: str,
    blocked_count_field: str,
    open_flag: str,
    empty_flag: str,
    blocked_flag: str,
    extra_false_flags: tuple[str, ...],
    title: str,
    title_id_label: str,
) -> dict[str, Any]:
    source_base = AI_ROOT / "datasets" / "governance" / f"{source_slug}.jsonl"
    return {
        "id": pid,
        "manifest_id": manifest_id,
        "slug": slug,
        "source_jsonl": source_base,
        "source_report": AI_ROOT / "reports" / f"{source_slug}_report.json",
        "source_validation": AI_ROOT / "reports" / f"{source_slug}_validation_report.json",
        "source_count_field": "preflight_rows" if pid == "p648" else CONFIGS_SOURCE_COUNTS[source_slug],
        "source_id_field": source_id_field,
        "source_order_field": source_order_field,
        "out_jsonl": AI_ROOT / "datasets" / "governance" / f"{slug}.jsonl",
        "out_report": AI_ROOT / "reports" / f"{slug}_report.json",
        "out_validation": AI_ROOT / "reports" / f"{slug}_validation_report.json",
        "out_md": AI_ROOT / "reports" / f"{slug.replace(f'{pid}_', '')}.md",
        "id_field": id_field,
        "order_field": order_field,
        "status": status,
        "count_field": count_field,
        "open_count_field": open_count_field,
        "empty_count_field": empty_count_field,
        "blocked_count_field": blocked_count_field,
        "open_flag": open_flag,
        "empty_flag": empty_flag,
        "blocked_flag": blocked_flag,
        "extra_false_flags": extra_false_flags,
        "title": title,
        "title_id_label": title_id_label,
        "row_policy": f"{manifest_id} records a local-only fail-closed shell. It does not receive input, validate response content, write decisions, perform formal intake, create runtime receipts or training labels, approve model claims, release, delivery, or production execution.",
        "report_policy": f"{manifest_id} is a local response-control shell only; all P0 gates remain fail-closed.",
        "validation_policy": f"{manifest_id} validates empty fail-closed response-control rows only.",
        "md_policy": "This artifact is not a response, approval, formal intake, runtime receipt, training label, model claim, release approval, or production authorization.",
    }


CONFIGS_SOURCE_COUNTS = {
    "p648_p0_external_input_response_schema_contract": "schema_contract_rows",
    "p649_p0_external_input_response_evidence_quarantine": "evidence_quarantine_rows",
    "p650_p0_external_input_response_decision_routing": "decision_routing_rows",
    "p651_p0_external_input_formal_intake_dry_run_guard": "formal_intake_dry_run_rows",
    "p652_p0_external_input_closeout_readiness_gate": "closeout_gate_rows",
    "p653_p0_external_input_closeout_blocker_ledger": "blocker_ledger_rows",
    "p654_p0_external_input_blocker_escalation_queue": "blocker_escalation_rows",
    "p655_p0_external_input_blocker_escalation_status_board": "blocker_status_rows",
    "p656_p0_external_input_blocker_escalation_watchlist": "blocker_watch_rows",
    "p657_p0_external_input_blocker_escalation_review_queue": "blocker_review_rows",
    "p658_p0_external_input_blocker_escalation_review_status_board": "blocker_review_status_rows",
    "p659_p0_external_input_blocker_escalation_review_watchlist": "blocker_review_watch_rows",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit": "blocker_review_aging_rows",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit": "blocker_review_owner_gap_rows",
    "p662_p0_external_input_evidence_missing_matrix": "evidence_missing_rows",
    "p663_p0_formal_decision_readiness_false_positive_guard": "formal_decision_false_positive_guard_rows",
    "p664_p0_closeout_non_approval_receipt_audit": "closeout_non_approval_receipt_rows",
    "p665_p0_closeout_non_approval_watchlist": "closeout_non_approval_watch_rows",
    "p666_p0_closeout_owner_review_queue": "closeout_owner_review_rows",
    "p667_p0_formal_intake_non_write_guard_audit": "formal_intake_non_write_guard_rows",
    "p668_p0_training_label_non_import_guard_audit": "training_label_non_import_guard_rows",
    "p669_p0_release_claim_non_promotion_guard_audit": "release_claim_non_promotion_guard_rows",
    "p670_p0_release_claim_non_promotion_status_board": "release_claim_non_promotion_status_rows",
    "p671_p0_model_claim_non_assertion_guard_audit": "model_claim_non_assertion_guard_rows",
    "p672_p0_customer_delivery_non_authorization_guard_audit": "customer_delivery_non_authorization_guard_rows",
    "p673_p0_production_execution_non_authorization_guard_audit": "production_execution_non_authorization_guard_rows",
    "p674_p0_terminal_blocked_state_rollup_audit": "terminal_blocked_state_rollup_rows",
}


CONFIGS: dict[str, dict[str, Any]] = {}
CONFIGS["p648"] = cfg(
    "p648",
    "p648_p0_external_input_response_schema_contract",
    "P648",
    "p647_p0_external_input_response_validation_preflight",
    "preflight_id",
    "preflight_order",
    "schema_contract_id",
    "schema_contract_order",
    "open_empty_schema_contract",
    "schema_contract_rows",
    "open_schema_contract_rows",
    "empty_schema_contract_rows",
    "blocked_schema_contract_rows",
    "schema_contract_open",
    "schema_contract_empty",
    "schema_contract_blocked",
    ("schema_contract_approved",),
    "P0 External Input Response Schema Contract",
    "Schema Contract",
)
CONFIGS["p649"] = cfg(
    "p649",
    "p649_p0_external_input_response_evidence_quarantine",
    "P649",
    "p648_p0_external_input_response_schema_contract",
    "schema_contract_id",
    "schema_contract_order",
    "evidence_quarantine_id",
    "evidence_quarantine_order",
    "open_empty_evidence_quarantine",
    "evidence_quarantine_rows",
    "open_evidence_quarantine_rows",
    "empty_evidence_quarantine_rows",
    "blocked_evidence_quarantine_rows",
    "evidence_quarantine_open",
    "evidence_quarantine_empty",
    "evidence_quarantine_blocked",
    ("evidence_quarantine_released", "evidence_promoted_to_decision"),
    "P0 External Input Response Evidence Quarantine",
    "Evidence Quarantine",
)
CONFIGS["p650"] = cfg(
    "p650",
    "p650_p0_external_input_response_decision_routing",
    "P650",
    "p649_p0_external_input_response_evidence_quarantine",
    "evidence_quarantine_id",
    "evidence_quarantine_order",
    "decision_routing_id",
    "decision_routing_order",
    "open_empty_decision_routing",
    "decision_routing_rows",
    "open_decision_routing_rows",
    "empty_decision_routing_rows",
    "blocked_decision_routing_rows",
    "decision_routing_open",
    "decision_routing_empty",
    "decision_routing_blocked",
    ("decision_route_executed", "routed_to_formal_review"),
    "P0 External Input Response Decision Routing",
    "Decision Routing",
)
CONFIGS["p651"] = cfg(
    "p651",
    "p651_p0_external_input_formal_intake_dry_run_guard",
    "P651",
    "p650_p0_external_input_response_decision_routing",
    "decision_routing_id",
    "decision_routing_order",
    "formal_intake_dry_run_id",
    "formal_intake_dry_run_order",
    "open_empty_formal_intake_dry_run_guard",
    "formal_intake_dry_run_rows",
    "open_formal_intake_dry_run_rows",
    "empty_formal_intake_dry_run_rows",
    "blocked_formal_intake_dry_run_rows",
    "formal_intake_dry_run_open",
    "formal_intake_dry_run_empty",
    "formal_intake_dry_run_blocked",
    ("formal_intake_dry_run_executed", "formal_intake_dry_run_passed"),
    "P0 External Input Formal Intake Dry-Run Guard",
    "Formal Intake Dry Run",
)
CONFIGS["p652"] = cfg(
    "p652",
    "p652_p0_external_input_closeout_readiness_gate",
    "P652",
    "p651_p0_external_input_formal_intake_dry_run_guard",
    "formal_intake_dry_run_id",
    "formal_intake_dry_run_order",
    "closeout_gate_id",
    "closeout_gate_order",
    "open_empty_closeout_readiness_gate",
    "closeout_gate_rows",
    "open_closeout_gate_rows",
    "empty_closeout_gate_rows",
    "blocked_closeout_gate_rows",
    "closeout_gate_open",
    "closeout_gate_empty",
    "closeout_gate_blocked",
    ("closeout_ready", "completion_ready_observed"),
    "P0 External Input Closeout Readiness Gate",
    "Closeout Gate",
)
CONFIGS["p653"] = cfg(
    "p653",
    "p653_p0_external_input_closeout_blocker_ledger",
    "P653",
    "p652_p0_external_input_closeout_readiness_gate",
    "closeout_gate_id",
    "closeout_gate_order",
    "blocker_ledger_id",
    "blocker_ledger_order",
    "open_unresolved_closeout_blocker",
    "blocker_ledger_rows",
    "open_blocker_ledger_rows",
    "empty_blocker_ledger_rows",
    "blocked_blocker_ledger_rows",
    "blocker_ledger_open",
    "blocker_ledger_empty",
    "blocker_ledger_blocked",
    ("blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Closeout Blocker Ledger",
    "Blocker Ledger",
)
CONFIGS["p654"] = cfg(
    "p654",
    "p654_p0_external_input_blocker_escalation_queue",
    "P654",
    "p653_p0_external_input_closeout_blocker_ledger",
    "blocker_ledger_id",
    "blocker_ledger_order",
    "blocker_escalation_id",
    "blocker_escalation_order",
    "open_empty_blocker_escalation_queue",
    "blocker_escalation_rows",
    "open_blocker_escalation_rows",
    "empty_blocker_escalation_rows",
    "blocked_blocker_escalation_rows",
    "blocker_escalation_open",
    "blocker_escalation_empty",
    "blocker_escalation_blocked",
    ("escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Blocker Escalation Queue",
    "Blocker Escalation",
)
CONFIGS["p655"] = cfg(
    "p655",
    "p655_p0_external_input_blocker_escalation_status_board",
    "P655",
    "p654_p0_external_input_blocker_escalation_queue",
    "blocker_escalation_id",
    "blocker_escalation_order",
    "blocker_status_id",
    "blocker_status_order",
    "open_empty_blocker_escalation_status_board",
    "blocker_status_rows",
    "open_blocker_status_rows",
    "empty_blocker_status_rows",
    "blocked_blocker_status_rows",
    "blocker_status_open",
    "blocker_status_empty",
    "blocker_status_blocked",
    ("escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Blocker Escalation Status Board",
    "Blocker Status Board",
)
CONFIGS["p656"] = cfg(
    "p656",
    "p656_p0_external_input_blocker_escalation_watchlist",
    "P656",
    "p655_p0_external_input_blocker_escalation_status_board",
    "blocker_status_id",
    "blocker_status_order",
    "blocker_watch_id",
    "blocker_watch_order",
    "open_empty_blocker_escalation_watchlist",
    "blocker_watch_rows",
    "open_blocker_watch_rows",
    "empty_blocker_watch_rows",
    "blocked_blocker_watch_rows",
    "blocker_watch_open",
    "blocker_watch_empty",
    "blocker_watch_blocked",
    ("escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Blocker Escalation Watchlist",
    "Blocker Watchlist",
)
CONFIGS["p657"] = cfg(
    "p657",
    "p657_p0_external_input_blocker_escalation_review_queue",
    "P657",
    "p656_p0_external_input_blocker_escalation_watchlist",
    "blocker_watch_id",
    "blocker_watch_order",
    "blocker_review_id",
    "blocker_review_order",
    "open_empty_blocker_escalation_review_queue",
    "blocker_review_rows",
    "open_blocker_review_rows",
    "empty_blocker_review_rows",
    "blocked_blocker_review_rows",
    "blocker_review_open",
    "blocker_review_empty",
    "blocker_review_blocked",
    ("escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Blocker Escalation Review Queue",
    "Blocker Review Queue",
)
CONFIGS["p658"] = cfg(
    "p658",
    "p658_p0_external_input_blocker_escalation_review_status_board",
    "P658",
    "p657_p0_external_input_blocker_escalation_review_queue",
    "blocker_review_id",
    "blocker_review_order",
    "blocker_review_status_id",
    "blocker_review_status_order",
    "open_empty_blocker_escalation_review_status_board",
    "blocker_review_status_rows",
    "open_blocker_review_status_rows",
    "empty_blocker_review_status_rows",
    "blocked_blocker_review_status_rows",
    "blocker_review_status_open",
    "blocker_review_status_empty",
    "blocker_review_status_blocked",
    ("escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Blocker Escalation Review Status Board",
    "Blocker Review Status",
)
CONFIGS["p659"] = cfg(
    "p659",
    "p659_p0_external_input_blocker_escalation_review_watchlist",
    "P659",
    "p658_p0_external_input_blocker_escalation_review_status_board",
    "blocker_review_status_id",
    "blocker_review_status_order",
    "blocker_review_watch_id",
    "blocker_review_watch_order",
    "open_empty_blocker_escalation_review_watchlist",
    "blocker_review_watch_rows",
    "open_blocker_review_watch_rows",
    "empty_blocker_review_watch_rows",
    "blocked_blocker_review_watch_rows",
    "blocker_review_watch_open",
    "blocker_review_watch_empty",
    "blocker_review_watch_blocked",
    ("escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Blocker Escalation Review Watchlist",
    "Blocker Review Watchlist",
)
CONFIGS["p660"] = cfg(
    "p660",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit",
    "P660",
    "p659_p0_external_input_blocker_escalation_review_watchlist",
    "blocker_review_watch_id",
    "blocker_review_watch_order",
    "blocker_review_aging_id",
    "blocker_review_aging_order",
    "open_empty_blocker_review_watchlist_aging_audit",
    "blocker_review_aging_rows",
    "open_blocker_review_aging_rows",
    "empty_blocker_review_aging_rows",
    "blocked_blocker_review_aging_rows",
    "blocker_review_aging_open",
    "blocker_review_aging_empty",
    "blocker_review_aging_blocked",
    ("aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Blocker Review Watchlist Aging Audit",
    "Blocker Review Aging",
)
CONFIGS["p661"] = cfg(
    "p661",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit",
    "P661",
    "p660_p0_external_input_blocker_review_watchlist_aging_audit",
    "blocker_review_aging_id",
    "blocker_review_aging_order",
    "blocker_review_owner_gap_id",
    "blocker_review_owner_gap_order",
    "open_empty_blocker_review_owner_assignment_gap",
    "blocker_review_owner_gap_rows",
    "open_blocker_review_owner_gap_rows",
    "empty_blocker_review_owner_gap_rows",
    "blocked_blocker_review_owner_gap_rows",
    "blocker_review_owner_gap_open",
    "blocker_review_owner_gap_empty",
    "blocker_review_owner_gap_blocked",
    ("owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Blocker Review Owner Assignment Gap Audit",
    "Blocker Review Owner Gap",
)
CONFIGS["p662"] = cfg(
    "p662",
    "p662_p0_external_input_evidence_missing_matrix",
    "P662",
    "p661_p0_external_input_blocker_review_owner_assignment_gap_audit",
    "blocker_review_owner_gap_id",
    "blocker_review_owner_gap_order",
    "evidence_missing_id",
    "evidence_missing_order",
    "open_empty_evidence_missing_matrix",
    "evidence_missing_rows",
    "open_evidence_missing_rows",
    "empty_evidence_missing_rows",
    "blocked_evidence_missing_rows",
    "evidence_missing_open",
    "evidence_missing_empty",
    "evidence_missing_blocked",
    ("evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 External Input Evidence Missing Matrix",
    "Evidence Missing",
)
CONFIGS["p663"] = cfg(
    "p663",
    "p663_p0_formal_decision_readiness_false_positive_guard",
    "P663",
    "p662_p0_external_input_evidence_missing_matrix",
    "evidence_missing_id",
    "evidence_missing_order",
    "formal_decision_false_positive_guard_id",
    "formal_decision_false_positive_guard_order",
    "open_empty_formal_decision_readiness_false_positive_guard",
    "formal_decision_false_positive_guard_rows",
    "open_formal_decision_false_positive_guard_rows",
    "empty_formal_decision_false_positive_guard_rows",
    "blocked_formal_decision_false_positive_guard_rows",
    "formal_decision_false_positive_guard_open",
    "formal_decision_false_positive_guard_empty",
    "formal_decision_false_positive_guard_blocked",
    ("formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Formal Decision Readiness False-Positive Guard",
    "Formal Decision Guard",
)
CONFIGS["p664"] = cfg(
    "p664",
    "p664_p0_closeout_non_approval_receipt_audit",
    "P664",
    "p663_p0_formal_decision_readiness_false_positive_guard",
    "formal_decision_false_positive_guard_id",
    "formal_decision_false_positive_guard_order",
    "closeout_non_approval_receipt_id",
    "closeout_non_approval_receipt_order",
    "open_empty_closeout_non_approval_receipt_audit",
    "closeout_non_approval_receipt_rows",
    "open_closeout_non_approval_receipt_rows",
    "empty_closeout_non_approval_receipt_rows",
    "blocked_closeout_non_approval_receipt_rows",
    "closeout_non_approval_receipt_open",
    "closeout_non_approval_receipt_empty",
    "closeout_non_approval_receipt_blocked",
    ("closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Closeout Non-Approval Receipt Audit",
    "Closeout Non-Approval Receipt",
)
CONFIGS["p665"] = cfg(
    "p665",
    "p665_p0_closeout_non_approval_watchlist",
    "P665",
    "p664_p0_closeout_non_approval_receipt_audit",
    "closeout_non_approval_receipt_id",
    "closeout_non_approval_receipt_order",
    "closeout_non_approval_watch_id",
    "closeout_non_approval_watch_order",
    "open_empty_closeout_non_approval_watchlist",
    "closeout_non_approval_watch_rows",
    "open_closeout_non_approval_watch_rows",
    "empty_closeout_non_approval_watch_rows",
    "blocked_closeout_non_approval_watch_rows",
    "closeout_non_approval_watch_open",
    "closeout_non_approval_watch_empty",
    "closeout_non_approval_watch_blocked",
    ("closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Closeout Non-Approval Watchlist",
    "Closeout Non-Approval Watch",
)
CONFIGS["p666"] = cfg(
    "p666",
    "p666_p0_closeout_owner_review_queue",
    "P666",
    "p665_p0_closeout_non_approval_watchlist",
    "closeout_non_approval_watch_id",
    "closeout_non_approval_watch_order",
    "closeout_owner_review_id",
    "closeout_owner_review_order",
    "open_empty_closeout_owner_review_queue",
    "closeout_owner_review_rows",
    "open_closeout_owner_review_rows",
    "empty_closeout_owner_review_rows",
    "blocked_closeout_owner_review_rows",
    "closeout_owner_review_open",
    "closeout_owner_review_empty",
    "closeout_owner_review_blocked",
    ("closeout_owner_assigned", "closeout_owner_reviewed", "closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Closeout Owner Review Queue",
    "Closeout Owner Review",
)
CONFIGS["p667"] = cfg(
    "p667",
    "p667_p0_formal_intake_non_write_guard_audit",
    "P667",
    "p666_p0_closeout_owner_review_queue",
    "closeout_owner_review_id",
    "closeout_owner_review_order",
    "formal_intake_non_write_guard_id",
    "formal_intake_non_write_guard_order",
    "open_empty_formal_intake_non_write_guard",
    "formal_intake_non_write_guard_rows",
    "open_formal_intake_non_write_guard_rows",
    "empty_formal_intake_non_write_guard_rows",
    "blocked_formal_intake_non_write_guard_rows",
    "formal_intake_non_write_guard_open",
    "formal_intake_non_write_guard_empty",
    "formal_intake_non_write_guard_blocked",
    ("formal_intake_guard_reviewed", "formal_intake_write_authorized", "closeout_owner_assigned", "closeout_owner_reviewed", "closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Formal Intake Non-Write Guard Audit",
    "Formal Intake Non-Write Guard",
)
CONFIGS["p668"] = cfg(
    "p668",
    "p668_p0_training_label_non_import_guard_audit",
    "P668",
    "p667_p0_formal_intake_non_write_guard_audit",
    "formal_intake_non_write_guard_id",
    "formal_intake_non_write_guard_order",
    "training_label_non_import_guard_id",
    "training_label_non_import_guard_order",
    "open_empty_training_label_non_import_guard",
    "training_label_non_import_guard_rows",
    "open_training_label_non_import_guard_rows",
    "empty_training_label_non_import_guard_rows",
    "blocked_training_label_non_import_guard_rows",
    "training_label_non_import_guard_open",
    "training_label_non_import_guard_empty",
    "training_label_non_import_guard_blocked",
    ("training_label_guard_reviewed", "training_label_import_authorized", "formal_intake_guard_reviewed", "formal_intake_write_authorized", "closeout_owner_assigned", "closeout_owner_reviewed", "closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Training Label Non-Import Guard Audit",
    "Training Label Non-Import Guard",
)
CONFIGS["p669"] = cfg(
    "p669",
    "p669_p0_release_claim_non_promotion_guard_audit",
    "P669",
    "p668_p0_training_label_non_import_guard_audit",
    "training_label_non_import_guard_id",
    "training_label_non_import_guard_order",
    "release_claim_non_promotion_guard_id",
    "release_claim_non_promotion_guard_order",
    "open_empty_release_claim_non_promotion_guard",
    "release_claim_non_promotion_guard_rows",
    "open_release_claim_non_promotion_guard_rows",
    "empty_release_claim_non_promotion_guard_rows",
    "blocked_release_claim_non_promotion_guard_rows",
    "release_claim_non_promotion_guard_open",
    "release_claim_non_promotion_guard_empty",
    "release_claim_non_promotion_guard_blocked",
    ("release_claim_guard_reviewed", "release_claim_promoted", "training_label_guard_reviewed", "training_label_import_authorized", "formal_intake_guard_reviewed", "formal_intake_write_authorized", "closeout_owner_assigned", "closeout_owner_reviewed", "closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Release Claim Non-Promotion Guard Audit",
    "Release Claim Non-Promotion Guard",
)
CONFIGS["p670"] = cfg(
    "p670",
    "p670_p0_release_claim_non_promotion_status_board",
    "P670",
    "p669_p0_release_claim_non_promotion_guard_audit",
    "release_claim_non_promotion_guard_id",
    "release_claim_non_promotion_guard_order",
    "release_claim_non_promotion_status_id",
    "release_claim_non_promotion_status_order",
    "open_empty_release_claim_non_promotion_status_board",
    "release_claim_non_promotion_status_rows",
    "open_release_claim_non_promotion_status_rows",
    "empty_release_claim_non_promotion_status_rows",
    "blocked_release_claim_non_promotion_status_rows",
    "release_claim_non_promotion_status_open",
    "release_claim_non_promotion_status_empty",
    "release_claim_non_promotion_status_blocked",
    ("release_claim_status_reviewed", "release_claim_guard_reviewed", "release_claim_promoted", "training_label_guard_reviewed", "training_label_import_authorized", "formal_intake_guard_reviewed", "formal_intake_write_authorized", "closeout_owner_assigned", "closeout_owner_reviewed", "closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Release Claim Non-Promotion Status Board",
    "Release Claim Non-Promotion Status",
)
CONFIGS["p671"] = cfg(
    "p671",
    "p671_p0_model_claim_non_assertion_guard_audit",
    "P671",
    "p670_p0_release_claim_non_promotion_status_board",
    "release_claim_non_promotion_status_id",
    "release_claim_non_promotion_status_order",
    "model_claim_non_assertion_guard_id",
    "model_claim_non_assertion_guard_order",
    "open_empty_model_claim_non_assertion_guard",
    "model_claim_non_assertion_guard_rows",
    "open_model_claim_non_assertion_guard_rows",
    "empty_model_claim_non_assertion_guard_rows",
    "blocked_model_claim_non_assertion_guard_rows",
    "model_claim_non_assertion_guard_open",
    "model_claim_non_assertion_guard_empty",
    "model_claim_non_assertion_guard_blocked",
    ("model_claim_guard_reviewed", "model_claim_asserted", "release_claim_status_reviewed", "release_claim_guard_reviewed", "release_claim_promoted", "training_label_guard_reviewed", "training_label_import_authorized", "formal_intake_guard_reviewed", "formal_intake_write_authorized", "closeout_owner_assigned", "closeout_owner_reviewed", "closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Model Claim Non-Assertion Guard Audit",
    "Model Claim Non-Assertion Guard",
)
CONFIGS["p672"] = cfg(
    "p672",
    "p672_p0_customer_delivery_non_authorization_guard_audit",
    "P672",
    "p671_p0_model_claim_non_assertion_guard_audit",
    "model_claim_non_assertion_guard_id",
    "model_claim_non_assertion_guard_order",
    "customer_delivery_non_authorization_guard_id",
    "customer_delivery_non_authorization_guard_order",
    "open_empty_customer_delivery_non_authorization_guard",
    "customer_delivery_non_authorization_guard_rows",
    "open_customer_delivery_non_authorization_guard_rows",
    "empty_customer_delivery_non_authorization_guard_rows",
    "blocked_customer_delivery_non_authorization_guard_rows",
    "customer_delivery_non_authorization_guard_open",
    "customer_delivery_non_authorization_guard_empty",
    "customer_delivery_non_authorization_guard_blocked",
    ("customer_delivery_guard_reviewed", "customer_delivery_authorized", "model_claim_guard_reviewed", "model_claim_asserted", "release_claim_status_reviewed", "release_claim_guard_reviewed", "release_claim_promoted", "training_label_guard_reviewed", "training_label_import_authorized", "formal_intake_guard_reviewed", "formal_intake_write_authorized", "closeout_owner_assigned", "closeout_owner_reviewed", "closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Customer Delivery Non-Authorization Guard Audit",
    "Customer Delivery Non-Authorization Guard",
)
CONFIGS["p673"] = cfg(
    "p673",
    "p673_p0_production_execution_non_authorization_guard_audit",
    "P673",
    "p672_p0_customer_delivery_non_authorization_guard_audit",
    "customer_delivery_non_authorization_guard_id",
    "customer_delivery_non_authorization_guard_order",
    "production_execution_non_authorization_guard_id",
    "production_execution_non_authorization_guard_order",
    "open_empty_production_execution_non_authorization_guard",
    "production_execution_non_authorization_guard_rows",
    "open_production_execution_non_authorization_guard_rows",
    "empty_production_execution_non_authorization_guard_rows",
    "blocked_production_execution_non_authorization_guard_rows",
    "production_execution_non_authorization_guard_open",
    "production_execution_non_authorization_guard_empty",
    "production_execution_non_authorization_guard_blocked",
    ("production_execution_guard_reviewed", "production_execution_authorized", "customer_delivery_guard_reviewed", "customer_delivery_authorized", "model_claim_guard_reviewed", "model_claim_asserted", "release_claim_status_reviewed", "release_claim_guard_reviewed", "release_claim_promoted", "training_label_guard_reviewed", "training_label_import_authorized", "formal_intake_guard_reviewed", "formal_intake_write_authorized", "closeout_owner_assigned", "closeout_owner_reviewed", "closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Production Execution Non-Authorization Guard Audit",
    "Production Execution Non-Authorization Guard",
)
CONFIGS["p674"] = cfg(
    "p674",
    "p674_p0_terminal_blocked_state_rollup_audit",
    "P674",
    "p673_p0_production_execution_non_authorization_guard_audit",
    "production_execution_non_authorization_guard_id",
    "production_execution_non_authorization_guard_order",
    "terminal_blocked_state_rollup_id",
    "terminal_blocked_state_rollup_order",
    "open_empty_terminal_blocked_state_rollup",
    "terminal_blocked_state_rollup_rows",
    "open_terminal_blocked_state_rollup_rows",
    "empty_terminal_blocked_state_rollup_rows",
    "blocked_terminal_blocked_state_rollup_rows",
    "terminal_blocked_state_rollup_open",
    "terminal_blocked_state_rollup_empty",
    "terminal_blocked_state_rollup_blocked",
    ("terminal_blocked_state_reviewed", "p0_terminal_unblocked", "production_execution_guard_reviewed", "production_execution_authorized", "customer_delivery_guard_reviewed", "customer_delivery_authorized", "model_claim_guard_reviewed", "model_claim_asserted", "release_claim_status_reviewed", "release_claim_guard_reviewed", "release_claim_promoted", "training_label_guard_reviewed", "training_label_import_authorized", "formal_intake_guard_reviewed", "formal_intake_write_authorized", "closeout_owner_assigned", "closeout_owner_reviewed", "closeout_watch_reviewed", "closeout_approved", "closeout_approval_written", "formal_decision_ready", "false_positive_cleared", "evidence_received", "evidence_validated", "owner_assigned", "owner_acknowledged", "aging_reviewed", "staleness_resolved", "escalation_reviewed", "escalation_sent", "escalation_acknowledged", "blocker_resolved", "closeout_ready", "completion_ready_observed"),
    "P0 Terminal Blocked-State Rollup Audit",
    "Terminal Blocked-State Rollup",
)
