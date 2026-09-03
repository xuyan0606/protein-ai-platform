#!/usr/bin/env python3
"""Validate remaining backlog execution tickets without running them."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from build_remaining_backlog_execution_tickets import (  # noqa: E402
    DEFAULT_DISPATCH,
    DEFAULT_GO_NO_GO,
    DEFAULT_OUTPUT_JSON as DEFAULT_TICKETS,
    build_tickets,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-execution-tickets-validation-report.json"
EXPECTED_MODE = "read_only_remaining_backlog_execution_tickets"
FORBIDDEN_SUBSTRINGS = ("op://", "password=", "PASSWORD=", "secret=", "SECRET=", "access_key=", "ACCESS_KEY=")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _failure(name: str, observed: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "observed": observed, "expected": expected}


def _comparable(payload: dict[str, Any]) -> dict[str, Any]:
    comparable = dict(payload)
    comparable.pop("created_at", None)
    return comparable


def validate_tickets(tickets: dict[str, Any], dispatch: dict[str, Any], go_no_go: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []

    def expect(name: str, condition: bool, observed: Any, expected: Any) -> None:
        if not condition:
            failures.append(_failure(name, observed, expected))

    rows = tickets.get("tickets") if isinstance(tickets.get("tickets"), list) else []
    dispatch_rows = dispatch.get("items") if isinstance(dispatch.get("items"), list) else []
    go_no_go_decision = go_no_go.get("decision")
    ready_for_live_gate = go_no_go.get("ready_for_live_gate_execution") is True

    expect("mode", tickets.get("mode") == EXPECTED_MODE, tickets.get("mode"), EXPECTED_MODE)
    expect("network_io", tickets.get("network_io") == "not_executed", tickets.get("network_io"), "not_executed")
    expect("destructive_actions", tickets.get("destructive_actions") == "not_executed", tickets.get("destructive_actions"), "not_executed")
    expect("secrets_printed", tickets.get("secrets_printed") is False, tickets.get("secrets_printed"), False)
    expect("live_gate_execution_allowed", tickets.get("live_gate_execution_allowed") is False, tickets.get("live_gate_execution_allowed"), False)
    expect("command_execution_allowed", tickets.get("command_execution_allowed") is False, tickets.get("command_execution_allowed"), False)
    expect("ticket_count", tickets.get("ticket_count") == len(rows), tickets.get("ticket_count"), len(rows))

    blocked_ticket_count = sum(1 for row in rows if isinstance(row, dict) and "blocked" in str(row.get("ticket_status")))
    armed_ticket_count = sum(
        1
        for row in rows
        if isinstance(row, dict) and "pending_explicit_operator_live_gate_review" in str(row.get("ticket_status"))
    )
    expect("blocked_ticket_count", tickets.get("blocked_ticket_count") == blocked_ticket_count, tickets.get("blocked_ticket_count"), blocked_ticket_count)
    expect("armed_ticket_count", tickets.get("armed_ticket_count") == armed_ticket_count, tickets.get("armed_ticket_count"), armed_ticket_count)

    priority_summary = tickets.get("priority_summary") if isinstance(tickets.get("priority_summary"), dict) else {}
    expected_priorities = sorted({str(row.get("priority") or "unassigned") for row in rows if isinstance(row, dict)})
    expect("priority_summary_keys", sorted(priority_summary) == expected_priorities, sorted(priority_summary), expected_priorities)
    for priority in expected_priorities:
        priority_rows = [row for row in rows if isinstance(row, dict) and str(row.get("priority") or "unassigned") == priority]
        summary_row = priority_summary.get(priority) if isinstance(priority_summary.get(priority), dict) else {}
        expect(f"priority_summary.{priority}.ticket_count", summary_row.get("ticket_count") == len(priority_rows), summary_row.get("ticket_count"), len(priority_rows))
        expect(
            f"priority_summary.{priority}.blocked_ticket_count",
            summary_row.get("blocked_ticket_count") == sum(1 for row in priority_rows if "blocked" in str(row.get("ticket_status"))),
            summary_row.get("blocked_ticket_count"),
            sum(1 for row in priority_rows if "blocked" in str(row.get("ticket_status"))),
        )
        expect(
            f"priority_summary.{priority}.armed_ticket_count",
            summary_row.get("armed_ticket_count")
            == sum(1 for row in priority_rows if "pending_explicit_operator_live_gate_review" in str(row.get("ticket_status"))),
            summary_row.get("armed_ticket_count"),
            sum(1 for row in priority_rows if "pending_explicit_operator_live_gate_review" in str(row.get("ticket_status"))),
        )

    ticket_names = sorted(str(row.get("name")) for row in rows if isinstance(row, dict))
    dispatch_names = sorted(str(row.get("name")) for row in dispatch_rows if isinstance(row, dict))
    expect("ticket_names_match_dispatch", ticket_names == dispatch_names, ticket_names, dispatch_names)
    expect("go_no_go_decision", tickets.get("go_no_go_decision") == go_no_go_decision, tickets.get("go_no_go_decision"), go_no_go_decision)
    expect(
        "ready_for_live_gate_execution",
        tickets.get("ready_for_live_gate_execution") is ready_for_live_gate,
        tickets.get("ready_for_live_gate_execution"),
        ready_for_live_gate,
    )

    for row in rows:
        if not isinstance(row, dict):
            failures.append(_failure("ticket_shape", type(row).__name__, "object"))
            continue
        name = row.get("name")
        expect(f"{name}.command_execution_allowed", row.get("command_execution_allowed") is False, row.get("command_execution_allowed"), False)
        expect(f"{name}.live_command_plan_included", row.get("live_command_plan_included") is False, row.get("live_command_plan_included"), False)
        expect(f"{name}.network_io", row.get("network_io") == "not_executed", row.get("network_io"), "not_executed")
        expect(f"{name}.destructive_actions", row.get("destructive_actions") == "not_executed", row.get("destructive_actions"), "not_executed")
        expect(f"{name}.secrets_printed", row.get("secrets_printed") is False, row.get("secrets_printed"), False)
        expect(f"{name}.ticket_id", str(row.get("ticket_id") or "").startswith("RB-"), row.get("ticket_id"), "RB-*")
        expect(f"{name}.operator_action_required", bool(row.get("operator_action_required")), row.get("operator_action_required"), "non-empty")

    rendered = json.dumps(tickets, ensure_ascii=False, sort_keys=True)
    forbidden_hits = [token for token in FORBIDDEN_SUBSTRINGS if token in rendered]
    expect("forbidden_secret_material_absent", not forbidden_hits, forbidden_hits, [])

    expected = build_tickets(dispatch, go_no_go)
    expect("source_bound_current", _comparable(tickets) == _comparable(expected), "differs", "matches rebuilt tickets")

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_remaining_backlog_execution_tickets_validation",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "ticket_count": len(rows),
        "blocked_ticket_count": blocked_ticket_count,
        "armed_ticket_count": armed_ticket_count,
        "source_bound_current": not any(failure["name"] == "source_bound_current" for failure in failures),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickets", default=str(DEFAULT_TICKETS))
    parser.add_argument("--dispatch", default=str(DEFAULT_DISPATCH))
    parser.add_argument("--go-no-go", default=str(DEFAULT_GO_NO_GO))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-success", action="store_true", help="Exit non-zero if validation fails")
    args = parser.parse_args()

    report = validate_tickets(
        _load_json(Path(args.tickets).expanduser().resolve()),
        _load_json(Path(args.dispatch).expanduser().resolve()),
        _load_json(Path(args.go_no_go).expanduser().resolve()),
    )
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "success": report["success"],
                "failure_count": report["failure_count"],
                "ticket_count": report["ticket_count"],
                "blocked_ticket_count": report["blocked_ticket_count"],
                "armed_ticket_count": report["armed_ticket_count"],
                "source_bound_current": report["source_bound_current"],
                "output": str(output),
                "network_io": report["network_io"],
                "destructive_actions": report["destructive_actions"],
                "secrets_printed": report["secrets_printed"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 1 if args.require_success and not report["success"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
