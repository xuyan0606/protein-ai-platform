#!/usr/bin/env python3
"""Validate the remaining backlog operator dispatch checklist.

The validator is read-only. It checks that the dispatch checklist is shaped
correctly, stays source-bound to the packet/validation/execution-plan inputs,
does not expose secret references, and does not include executable live command
plans.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from build_remaining_backlog_operator_dispatch_checklist import (  # noqa: E402
    DEFAULT_EXECUTION_PLAN,
    DEFAULT_JSON as DEFAULT_CHECKLIST,
    DEFAULT_PACKET,
    DEFAULT_VALIDATION,
    build_checklist,
    load_json,
)


DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-operator-dispatch-checklist-validation-report.json"
FORBIDDEN_SUBSTRINGS = ("op://", "password=", "PASSWORD=", "secret=", "SECRET=", "access_key=", "ACCESS_KEY=")
EXPECTED_MODE = "read_only_remaining_backlog_operator_dispatch_checklist"


def _failure(name: str, detail: str, observed: Any = None, expected: Any = None) -> Dict[str, Any]:
    return {
        "name": name,
        "detail": detail,
        "observed": observed,
        "expected": expected,
    }


def _comparable(payload: Dict[str, Any]) -> Dict[str, Any]:
    comparable = dict(payload)
    comparable.pop("created_at", None)
    return comparable


def validate_checklist(
    checklist: Dict[str, Any],
    packet: Dict[str, Any],
    validation: Dict[str, Any],
    execution_plan: Dict[str, Any],
) -> Dict[str, Any]:
    failures: List[Dict[str, Any]] = []

    def expect(name: str, condition: bool, observed: Any = None, expected: Any = None) -> None:
        if not condition:
            failures.append(_failure(name, f"{name} failed", observed, expected))

    expect("mode", checklist.get("mode") == EXPECTED_MODE, checklist.get("mode"), EXPECTED_MODE)
    expect("network_io", checklist.get("network_io") == "not_executed", checklist.get("network_io"), "not_executed")
    expect("destructive_actions", checklist.get("destructive_actions") == "not_executed", checklist.get("destructive_actions"), "not_executed")
    expect("secrets_printed", checklist.get("secrets_printed") is False, checklist.get("secrets_printed"), False)
    expect("live_commands_included", checklist.get("live_commands_included") is False, checklist.get("live_commands_included"), False)

    items = checklist.get("items") if isinstance(checklist.get("items"), list) else []
    lanes = checklist.get("lanes") if isinstance(checklist.get("lanes"), list) else []
    packet_items = packet.get("items") if isinstance(packet.get("items"), list) else []
    validation_items = validation.get("items") if isinstance(validation.get("items"), list) else []
    execution_items = execution_plan.get("items") if isinstance(execution_plan.get("items"), list) else []

    item_names = [row.get("name") for row in items if isinstance(row, dict)]
    packet_names = [row.get("name") for row in packet_items if isinstance(row, dict)]
    validation_names = [row.get("name") for row in validation_items if isinstance(row, dict)]
    execution_names = [row.get("name") for row in execution_items if isinstance(row, dict)]
    expect("item_names_match_packet", sorted(item_names) == sorted(packet_names), sorted(item_names), sorted(packet_names))
    expect("item_names_match_validation", sorted(item_names) == sorted(validation_names), sorted(item_names), sorted(validation_names))
    expect("item_names_match_execution_plan", sorted(item_names) == sorted(execution_names), sorted(item_names), sorted(execution_names))

    blocked_rows = sum(1 for row in items if isinstance(row, dict) and row.get("missing_fields"))
    armed_rows = sum(1 for row in items if isinstance(row, dict) and row.get("armed_in_execution_plan") is True)
    lane_names = [row.get("lane") for row in lanes if isinstance(row, dict)]
    item_lane_names = sorted({row.get("lane") for row in items if isinstance(row, dict)})
    expect("item_count", checklist.get("item_count") == len(items), checklist.get("item_count"), len(items))
    expect("lane_count", checklist.get("lane_count") == len(lanes), checklist.get("lane_count"), len(lanes))
    expect("blocked_rows", checklist.get("blocked_rows") == blocked_rows, checklist.get("blocked_rows"), blocked_rows)
    expect("armed_rows", checklist.get("armed_rows") == armed_rows, checklist.get("armed_rows"), armed_rows)
    expect("lane_coverage", sorted(lane_names) == item_lane_names, sorted(lane_names), item_lane_names)

    for row in items:
        if not isinstance(row, dict):
            failures.append(_failure("item_shape", "dispatch item must be an object", row, "object"))
            continue
        name = row.get("name")
        expect(f"{name}.live_command_plan_included", row.get("live_command_plan_included") is False, row.get("live_command_plan_included"), False)
        expect(f"{name}.no_command_plan", "command_plan" not in row, row.get("command_plan"), "absent")
        expect(f"{name}.missing_fields_shape", isinstance(row.get("missing_fields"), list), type(row.get("missing_fields")).__name__, "list")
        expect(f"{name}.required_input_fields_shape", isinstance(row.get("required_input_fields"), list), type(row.get("required_input_fields")).__name__, "list")
        expect(f"{name}.lane_present", bool(row.get("lane")), row.get("lane"), "non-empty lane")

    rendered = json.dumps(checklist, ensure_ascii=False, sort_keys=True)
    forbidden_hits = [token for token in FORBIDDEN_SUBSTRINGS if token in rendered]
    expect("forbidden_secret_material_absent", not forbidden_hits, forbidden_hits, [])

    expected = build_checklist(packet, validation, execution_plan)
    expect("source_bound_current", _comparable(checklist) == _comparable(expected), "differs", "matches rebuilt checklist")

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_remaining_backlog_operator_dispatch_checklist_validation",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "success": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "item_count": len(items),
        "lane_count": len(lanes),
        "blocked_rows": blocked_rows,
        "armed_rows": armed_rows,
        "source_bound_current": not any(failure["name"] == "source_bound_current" for failure in failures),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--validation", default=str(DEFAULT_VALIDATION))
    parser.add_argument("--execution-plan", default=str(DEFAULT_EXECUTION_PLAN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-success", action="store_true", help="Exit non-zero if validation fails")
    args = parser.parse_args()

    report = validate_checklist(
        load_json(Path(args.checklist).expanduser().resolve()),
        load_json(Path(args.packet).expanduser().resolve()),
        load_json(Path(args.validation).expanduser().resolve()),
        load_json(Path(args.execution_plan).expanduser().resolve()),
    )
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "success": report["success"],
                "failure_count": report["failure_count"],
                "item_count": report["item_count"],
                "lane_count": report["lane_count"],
                "blocked_rows": report["blocked_rows"],
                "armed_rows": report["armed_rows"],
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
