#!/usr/bin/env python3
"""Build read-only execution tickets for every remaining backlog item."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DISPATCH = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-operator-dispatch-checklist.json"
DEFAULT_GO_NO_GO = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-go-no-go-summary.json"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-execution-tickets.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-execution-tickets.md"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _ticket_status(item: dict[str, Any]) -> str:
    if item.get("armed_in_execution_plan") is True:
        return "started_pending_explicit_operator_live_gate_review"
    if item.get("missing_fields"):
        return "started_blocked_waiting_for_operator_input"
    return "started_blocked_waiting_for_plan_refresh"


def _priority_summary(tickets: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for ticket in tickets:
        priority = str(ticket.get("priority") or "unassigned")
        row = summary.setdefault(
            priority,
            {
                "ticket_count": 0,
                "blocked_ticket_count": 0,
                "armed_ticket_count": 0,
                "tickets": [],
                "items": [],
            },
        )
        row["ticket_count"] += 1
        row["tickets"].append(str(ticket.get("ticket_id") or "unnamed"))
        row["items"].append(str(ticket.get("name") or "unnamed"))
        if "blocked" in str(ticket.get("ticket_status")):
            row["blocked_ticket_count"] += 1
        if "pending_explicit_operator_live_gate_review" in str(ticket.get("ticket_status")):
            row["armed_ticket_count"] += 1
    return {priority: summary[priority] for priority in sorted(summary)}


def build_tickets(dispatch: dict[str, Any], go_no_go: dict[str, Any]) -> dict[str, Any]:
    decision = str(go_no_go.get("decision") or "unknown")
    ready_for_live_gate_execution = go_no_go.get("ready_for_live_gate_execution") is True
    tickets = []
    for index, item in enumerate(dispatch.get("items") or [], start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"item_{index}")
        missing_fields = list(item.get("missing_fields") or [])
        validation_after_collection = list(item.get("validation_after_collection") or [])
        tickets.append(
            {
                "ticket_id": f"RB-{index:03d}-{name}",
                "name": name,
                "lane": item.get("lane"),
                "lane_label": item.get("lane_label"),
                "priority": item.get("priority"),
                "ticket_status": _ticket_status(item),
                "source_status": item.get("source_status"),
                "dispatch_status": item.get("dispatch_status"),
                "go_no_go_decision": decision,
                "ready_for_live_gate_execution": ready_for_live_gate_execution,
                "command_execution_allowed": False,
                "live_command_plan_included": False,
                "network_io": "not_executed",
                "destructive_actions": "not_executed",
                "secrets_printed": False,
                "required_input_fields": list(item.get("required_input_fields") or []),
                "missing_fields": missing_fields,
                "secret_reference_fields": list(item.get("secret_reference_fields") or []),
                "operator_action_required": (
                    "collect_missing_inputs_and_rerun_validation"
                    if missing_fields
                    else "rerun_execution_plan_and_go_no_go_summary"
                ),
                "evidence_to_collect": list(item.get("evidence_to_collect") or []),
                "validation_after_collection": validation_after_collection,
                "safety_note": item.get("safety_note") or "Do not execute live gates until this ticket is armed by validation.",
            }
        )

    lane_summary = []
    for lane in dispatch.get("lanes") or []:
        if not isinstance(lane, dict):
            continue
        lane_name = lane.get("lane")
        lane_tickets = [ticket for ticket in tickets if ticket["lane"] == lane_name]
        lane_summary.append(
            {
                "lane": lane_name,
                "lane_label": lane.get("lane_label"),
                "ticket_count": len(lane_tickets),
                "blocked_ticket_count": sum(1 for ticket in lane_tickets if "blocked" in ticket["ticket_status"]),
                "armed_ticket_count": sum(1 for ticket in lane_tickets if "pending_explicit_operator_live_gate_review" in ticket["ticket_status"]),
                "tickets": [ticket["ticket_id"] for ticket in lane_tickets],
            }
        )

    blocked_ticket_count = sum(1 for ticket in tickets if "blocked" in ticket["ticket_status"])
    armed_ticket_count = sum(1 for ticket in tickets if "pending_explicit_operator_live_gate_review" in ticket["ticket_status"])
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_remaining_backlog_execution_tickets",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "live_gate_execution_allowed": False,
        "command_execution_allowed": False,
        "ticket_count": len(tickets),
        "blocked_ticket_count": blocked_ticket_count,
        "armed_ticket_count": armed_ticket_count,
        "go_no_go_decision": decision,
        "ready_for_live_gate_execution": ready_for_live_gate_execution,
        "lanes": lane_summary,
        "priority_summary": _priority_summary(tickets),
        "tickets": tickets,
        "next_action": (
            "collect missing operator inputs for every blocked ticket, rerun validation, then rerun go/no-go"
            if blocked_ticket_count
            else "rerun go/no-go and request explicit operator approval before any live gate"
        ),
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# Remaining Backlog Execution Tickets",
        "",
        f"- go_no_go_decision: `{payload['go_no_go_decision']}`",
        f"- ready_for_live_gate_execution: `{payload['ready_for_live_gate_execution']}`",
        f"- live_gate_execution_allowed: `{payload['live_gate_execution_allowed']}`",
        f"- command_execution_allowed: `{payload['command_execution_allowed']}`",
        f"- ticket_count: `{payload['ticket_count']}`",
        f"- blocked_ticket_count: `{payload['blocked_ticket_count']}`",
        f"- armed_ticket_count: `{payload['armed_ticket_count']}`",
        "",
        "## Priority Summary",
        "",
        "| Priority | Tickets | Blocked | Armed | Items |",
        "|---|---:|---:|---:|---|",
    ]
    for priority, row in payload.get("priority_summary", {}).items():
        lines.append(
            f"| `{priority}` | `{row['ticket_count']}` | `{row['blocked_ticket_count']}` | "
            f"`{row['armed_ticket_count']}` | `{', '.join(row['items'])}` |"
        )
    lines.append("")
    for ticket in payload["tickets"]:
        lines.extend(
            [
                f"## {ticket['ticket_id']}",
                "",
                f"- Item: `{ticket['name']}`",
                f"- Lane: `{ticket['lane']}`",
                f"- Priority: `{ticket['priority']}`",
                f"- Status: `{ticket['ticket_status']}`",
                f"- Operator action: `{ticket['operator_action_required']}`",
                f"- Safety: {ticket['safety_note']}",
            ]
        )
        if ticket["missing_fields"]:
            lines.append("- Missing inputs:")
            for field in ticket["missing_fields"]:
                suffix = " (secret reference only)" if field in ticket["secret_reference_fields"] else ""
                lines.append(f"  - `{field}`{suffix}")
        if ticket["evidence_to_collect"]:
            lines.append("- Evidence to collect:")
            for evidence in ticket["evidence_to_collect"]:
                lines.append(f"  - {evidence}")
        if ticket["validation_after_collection"]:
            lines.append("- Validate after collection:")
            for command in ticket["validation_after_collection"]:
                lines.append(f"  - `{command}`")
        lines.append("")
    lines.append(f"Next action: {payload['next_action']}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch", default=str(DEFAULT_DISPATCH))
    parser.add_argument("--go-no-go", default=str(DEFAULT_GO_NO_GO))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    payload = build_tickets(
        _load_json(Path(args.dispatch).expanduser().resolve()),
        _load_json(Path(args.go_no_go).expanduser().resolve()),
    )
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload, output_md)

    response = {
        "ticket_count": payload["ticket_count"],
        "blocked_ticket_count": payload["blocked_ticket_count"],
        "armed_ticket_count": payload["armed_ticket_count"],
        "go_no_go_decision": payload["go_no_go_decision"],
        "ready_for_live_gate_execution": payload["ready_for_live_gate_execution"],
        "priority_summary": payload["priority_summary"],
        "output_json": str(output_json),
        "output_md": str(output_md),
        "network_io": payload["network_io"],
        "destructive_actions": payload["destructive_actions"],
        "secrets_printed": payload["secrets_printed"],
        "live_gate_execution_allowed": payload["live_gate_execution_allowed"],
    }
    if args.json:
        print(json.dumps(response, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "summary\t"
            f"tickets={response['ticket_count']}\t"
            f"blocked={response['blocked_ticket_count']}\t"
            f"armed={response['armed_ticket_count']}"
        )
        print(f"output_json\t{response['output_json']}")
        print(f"output_md\t{response['output_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
