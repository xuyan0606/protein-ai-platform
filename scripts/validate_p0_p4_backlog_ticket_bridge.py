#!/usr/bin/env python3
"""Validate the P0-P4 to remaining backlog ticket bridge without executing gates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_p0_p4_backlog_ticket_bridge import (
    DEFAULT_EXECUTION_TICKETS,
    DEFAULT_GO_NO_GO,
    DEFAULT_OUTPUT_JSON as DEFAULT_BRIDGE,
    DEFAULT_STATUS_EXPORT,
    build_bridge,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-backlog-ticket-bridge-validation-report.json"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def validate_bridge(
    bridge: dict[str, Any],
    status_export: dict[str, Any],
    tickets: dict[str, Any],
    go_no_go: dict[str, Any],
    status_path: Path,
    tickets_path: Path,
    go_no_go_path: Path,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []

    def expect(name: str, condition: bool, observed: Any, expected: Any) -> None:
        if not condition:
            failures.append({"name": name, "observed": observed, "expected": expected})

    expected = build_bridge(status_export, tickets, go_no_go, status_path, tickets_path, go_no_go_path)
    comparable = dict(bridge)
    comparable.pop("created_at", None)
    expected_cmp = dict(expected)
    expected_cmp.pop("created_at", None)
    expect("source_bound_current", comparable == expected_cmp, "differs", "matches rebuilt bridge")
    expect("mode", bridge.get("mode") == "read_only_p0_p4_backlog_ticket_bridge", bridge.get("mode"), "read_only_p0_p4_backlog_ticket_bridge")
    expect("network_io", bridge.get("network_io") == "not_executed", bridge.get("network_io"), "not_executed")
    expect("destructive_actions", bridge.get("destructive_actions") == "not_executed", bridge.get("destructive_actions"), "not_executed")
    expect("secrets_printed", bridge.get("secrets_printed") is False, bridge.get("secrets_printed"), False)
    expect("live_gate_execution_allowed", bridge.get("live_gate_execution_allowed") is False, bridge.get("live_gate_execution_allowed"), False)
    contracts = bridge.get("contracts") if isinstance(bridge.get("contracts"), list) else []
    ticket_rows = bridge.get("tickets") if isinstance(bridge.get("tickets"), list) else []
    source_contracts = status_export.get("contract_status_items") if isinstance(status_export.get("contract_status_items"), list) else []
    source_tickets = tickets.get("tickets") if isinstance(tickets.get("tickets"), list) else []
    expect("contract_count", len(contracts) == len(source_contracts), len(contracts), len(source_contracts))
    expect("ticket_count", len(ticket_rows) == len(source_tickets), len(ticket_rows), len(source_tickets))
    expect("go_no_go_decision", bridge.get("go_no_go_decision") == go_no_go.get("decision"), bridge.get("go_no_go_decision"), go_no_go.get("decision"))
    expect("ready_for_live_gate_execution", bridge.get("ready_for_live_gate_execution") is (go_no_go.get("ready_for_live_gate_execution") is True), bridge.get("ready_for_live_gate_execution"), go_no_go.get("ready_for_live_gate_execution"))
    contract_names = [row.get("contract_name") for row in contracts if isinstance(row, dict)]
    expect("unique_contract_names", len(contract_names) == len(set(contract_names)), contract_names, "unique")
    ticket_ids = [row.get("ticket_id") for row in ticket_rows if isinstance(row, dict)]
    expect("unique_ticket_ids", len(ticket_ids) == len(set(ticket_ids)), ticket_ids, "unique")
    for row in contracts:
        if not isinstance(row, dict):
            continue
        expect(
            f"{row.get('contract_name')}.blockers_preserved",
            set(row.get("uncovered_blockers") or []).issubset(set(row.get("external_blockers") or [])),
            row.get("uncovered_blockers"),
            "subset of external_blockers",
        )
        expect(
            f"{row.get('contract_name')}.status_valid",
            row.get("ticket_link_status") in {"linked", "partially_linked", "contract_followup_only"},
            row.get("ticket_link_status"),
            "valid bridge status",
        )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_p0_p4_backlog_ticket_bridge_validation",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "contract_count": len(contracts),
        "ticket_count": len(ticket_rows),
        "source_bound_current": not any(item["name"] == "source_bound_current" for item in failures),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge", default=str(DEFAULT_BRIDGE))
    parser.add_argument("--status-export", default=str(DEFAULT_STATUS_EXPORT))
    parser.add_argument("--execution-tickets", default=str(DEFAULT_EXECUTION_TICKETS))
    parser.add_argument("--go-no-go", default=str(DEFAULT_GO_NO_GO))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-success", action="store_true")
    args = parser.parse_args()

    bridge_path = Path(args.bridge).expanduser().resolve()
    status_path = Path(args.status_export).expanduser().resolve()
    tickets_path = Path(args.execution_tickets).expanduser().resolve()
    go_no_go_path = Path(args.go_no_go).expanduser().resolve()
    report = validate_bridge(
        _load(bridge_path),
        _load(status_path),
        _load(tickets_path),
        _load(go_no_go_path),
        status_path,
        tickets_path,
        go_no_go_path,
    )
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("success", "failure_count", "contract_count", "ticket_count", "source_bound_current")}, ensure_ascii=False, sort_keys=True))
    return 1 if args.require_success and not report["success"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
