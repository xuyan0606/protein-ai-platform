#!/usr/bin/env python3
"""Validate operator-provided input values for remaining backlog gates.

This is a read-only readiness preflight. It validates that required values or
secret references have been provided for each backlog item, but it does not run
live gates, contact networks, print secrets, or mutate deployment state.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACKET = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-external-input-packet.json"
DEFAULT_TEMPLATE = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-external-input-values.template.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-external-input-validation-report.json"

SECRET_FIELD_TOKENS = ("PASSWORD", "SECRET", "ACCESS_KEY", "credential", "secret_reference")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and not value.strip().startswith("<")
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return True


def field_is_secret_reference(field: str) -> bool:
    normalized = field.lower()
    return any(token.lower() in normalized for token in SECRET_FIELD_TOKENS)


def validate_item(packet_item: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
    name = str(packet_item["name"])
    item_values = values.get(name) if isinstance(values.get(name), dict) else {}
    required = list(packet_item.get("required_input_fields") or [])
    missing = []
    provided = []
    secret_reference_fields = [field for field in required if field_is_secret_reference(field)]

    for field in required:
        value = item_values.get(field)
        if nonempty(value):
            provided.append(field)
        else:
            missing.append(field)

    ready_to_run = not missing and packet_item.get("status") in {"external_required", "planned"}
    return {
        "name": name,
        "priority": packet_item.get("priority"),
        "status": packet_item.get("status"),
        "ready_to_run": ready_to_run,
        "required_input_fields": required,
        "provided_fields": provided,
        "missing_fields": missing,
        "secret_reference_fields": secret_reference_fields,
        "validation_commands": packet_item.get("validation_commands") or [],
    }


def priority_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for row in rows:
        priority = str(row.get("priority") or "P2")
        summary_row = summary.setdefault(
            priority,
            {
                "item_count": 0,
                "ready_to_run_rows": 0,
                "missing_input_rows": 0,
                "missing_field_count": 0,
                "items": [],
            },
        )
        summary_row["item_count"] += 1
        summary_row["items"].append(str(row.get("name") or "unnamed"))
        if row.get("ready_to_run"):
            summary_row["ready_to_run_rows"] += 1
        if row.get("missing_fields"):
            summary_row["missing_input_rows"] += 1
            summary_row["missing_field_count"] += len(row.get("missing_fields") or [])
    return {priority: summary[priority] for priority in sorted(summary)}


def template_from_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mode": "operator_supplied_values_template",
        "policy": "Fill values or secret references only. Do not paste raw passwords or cloud secrets into this file.",
        "priority_summary": packet.get("priority_summary") or {},
        "items": {
            item["name"]: {
                field: "<fill>" if not field_is_secret_reference(field) else "<secret-reference-only>"
                for field in item.get("required_input_fields") or []
            }
            for item in packet.get("items") or []
        },
    }


def values_by_item(values_payload: Dict[str, Any]) -> Dict[str, Any]:
    items = values_payload.get("items")
    return items if isinstance(items, dict) else {}


def build_report(packet: Dict[str, Any], values_payload: Dict[str, Any]) -> Dict[str, Any]:
    values = values_by_item(values_payload)
    rows = [validate_item(item, values) for item in packet.get("items") or []]
    ready_rows = sum(1 for row in rows if row["ready_to_run"])
    missing_rows = sum(1 for row in rows if row["missing_fields"])
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_external_input_validation",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "item_count": len(rows),
        "ready_to_run_rows": ready_rows,
        "missing_input_rows": missing_rows,
        "priority_summary": priority_summary(rows),
        "all_inputs_present": missing_rows == 0,
        "items": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", default=str(DEFAULT_PACKET), help="Input packet JSON from build_remaining_backlog_external_input_packet.py")
    parser.add_argument("--values", default=str(DEFAULT_TEMPLATE), help="Operator-supplied values JSON")
    parser.add_argument("--write-template", action="store_true", help="Write/update the values template from the current packet")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Validation report path")
    parser.add_argument("--require-complete", action="store_true", help="Exit non-zero unless all required fields are present")
    args = parser.parse_args()

    packet_path = Path(args.packet).expanduser().resolve()
    values_path = Path(args.values).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    packet = load_json(packet_path)
    if args.write_template or not values_path.exists():
        values_path.parent.mkdir(parents=True, exist_ok=True)
        values_path.write_text(json.dumps(template_from_packet(packet), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    values_payload = load_json(values_path)
    report = build_report(packet, values_payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "success": not (args.require_complete and not report["all_inputs_present"]),
        "all_inputs_present": report["all_inputs_present"],
        "item_count": report["item_count"],
        "ready_to_run_rows": report["ready_to_run_rows"],
        "missing_input_rows": report["missing_input_rows"],
        "priority_summary": report["priority_summary"],
        "output": str(output_path),
        "template": str(values_path),
        "network_io": report["network_io"],
        "destructive_actions": report["destructive_actions"],
        "secrets_printed": report["secrets_printed"],
    }, ensure_ascii=False, sort_keys=True))
    return 1 if args.require_complete and not report["all_inputs_present"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
