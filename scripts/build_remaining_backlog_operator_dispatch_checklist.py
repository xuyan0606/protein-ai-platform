#!/usr/bin/env python3
"""Build a role-oriented dispatch checklist for remaining backlog inputs.

This is a read-only handoff artifact. It consumes the existing external input
packet, validation report, and execution plan, then groups missing inputs by
operator lane. It does not run live gates, contact networks, read secret
material, or produce executable command plans.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACKET = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-external-input-packet.json"
DEFAULT_VALIDATION = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-external-input-validation-report.json"
DEFAULT_EXECUTION_PLAN = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-gate-execution-plan.json"
DEFAULT_JSON = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-operator-dispatch-checklist.json"
DEFAULT_MD = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-operator-dispatch-checklist.md"

LANES = {
    "formal_domain_https": ("infra_dns_tls", "P0"),
    "gpu_gromacs_md_live": ("md_runtime", "P0"),
    "md_blackbox_live_e2e": ("md_runtime", "P0"),
    "ligand_runtime_live": ("ligand_runtime", "P1"),
    "oss_minio_live_e2e": ("storage", "P0"),
    "admin_authenticated_screenshots": ("qa_admin", "P1"),
    "maintenance_window_drills": ("release_ops", "P1"),
    "remote_pytest_runner": ("ci_runner", "P1"),
}

LANE_LABELS = {
    "infra_dns_tls": "Formal domain, TLS, and identity config",
    "md_runtime": "GPU/GROMACS and MD live validation",
    "ligand_runtime": "Ligand preprocessing, docking, topology runtime",
    "storage": "OSS/MinIO live storage scope",
    "qa_admin": "Authenticated admin screenshot evidence",
    "release_ops": "Maintenance window and drill evidence",
    "ci_runner": "Non-production backend pytest runner",
}


def load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _by_name(rows: List[Any]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("name"):
            result[str(row["name"])] = row
    return result


def _dispatch_status(validation_row: Dict[str, Any], execution_row: Dict[str, Any]) -> str:
    if execution_row.get("armed") is True:
        return "inputs_present_pending_operator_live_gate"
    if validation_row.get("missing_fields"):
        return "waiting_for_operator_input"
    if validation_row.get("ready_to_run") is True:
        return "inputs_present_pending_execution_plan_refresh"
    return "blocked_by_validation"


def build_checklist(packet: Dict[str, Any], validation: Dict[str, Any], execution_plan: Dict[str, Any]) -> Dict[str, Any]:
    packet_rows = _by_name(list(packet.get("items") or []))
    validation_rows = _by_name(list(validation.get("items") or []))
    execution_rows = _by_name(list(execution_plan.get("items") or []))

    items: List[Dict[str, Any]] = []
    for name, packet_row in packet_rows.items():
        validation_row = validation_rows.get(name, {})
        execution_row = execution_rows.get(name, {})
        lane, priority = LANES.get(name, ("unassigned", "P2"))
        missing_fields = list(validation_row.get("missing_fields") or packet_row.get("required_input_fields") or [])
        required_fields = list(packet_row.get("required_input_fields") or validation_row.get("required_input_fields") or [])
        secret_fields = list(validation_row.get("secret_reference_fields") or [])
        items.append(
            {
                "name": name,
                "lane": lane,
                "lane_label": LANE_LABELS.get(lane, lane),
                "priority": priority,
                "source_status": packet_row.get("status"),
                "dispatch_status": _dispatch_status(validation_row, execution_row),
                "ready_to_run_after_inputs": bool(validation_row.get("ready_to_run")),
                "armed_in_execution_plan": bool(execution_row.get("armed")),
                "required_input_fields": required_fields,
                "missing_fields": missing_fields,
                "secret_reference_fields": secret_fields,
                "missing_requirements": list(packet_row.get("missing_requirements") or []),
                "evidence_to_collect": list(packet_row.get("next_actions") or []),
                "validation_after_collection": list(packet_row.get("validation_commands") or []),
                "safety_note": execution_row.get("safety_note") or "Run live gates only after required operator inputs are present.",
                "live_command_plan_included": False,
            }
        )

    lane_rows: List[Dict[str, Any]] = []
    for lane in sorted({item["lane"] for item in items}):
        lane_items = [item for item in items if item["lane"] == lane]
        lane_rows.append(
            {
                "lane": lane,
                "lane_label": LANE_LABELS.get(lane, lane),
                "item_count": len(lane_items),
                "waiting_for_input_count": sum(1 for item in lane_items if item["missing_fields"]),
                "armed_count": sum(1 for item in lane_items if item["armed_in_execution_plan"]),
                "items": [item["name"] for item in lane_items],
            }
        )

    blocked_rows = sum(1 for item in items if item["missing_fields"])
    armed_rows = sum(1 for item in items if item["armed_in_execution_plan"])
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_remaining_backlog_operator_dispatch_checklist",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "live_commands_included": False,
        "item_count": len(items),
        "lane_count": len(lane_rows),
        "blocked_rows": blocked_rows,
        "armed_rows": armed_rows,
        "all_inputs_present": bool(validation.get("all_inputs_present")),
        "lanes": lane_rows,
        "items": items,
    }


def markdown(checklist: Dict[str, Any]) -> str:
    lines = [
        "# Remaining Backlog Operator Dispatch Checklist",
        "",
        f"- Created at: `{checklist['created_at']}`",
        f"- Mode: `{checklist['mode']}`",
        f"- Network IO: `{checklist['network_io']}`",
        f"- Destructive actions: `{checklist['destructive_actions']}`",
        f"- Secrets printed: `{str(checklist['secrets_printed']).lower()}`",
        f"- Live commands included: `{str(checklist['live_commands_included']).lower()}`",
        f"- Blocked rows: `{checklist['blocked_rows']}`",
        f"- Armed rows: `{checklist['armed_rows']}`",
        "",
    ]
    for lane in checklist["lanes"]:
        lines.extend(
            [
                f"## {lane['lane']}",
                "",
                f"- Scope: {lane['lane_label']}",
                f"- Items: `{', '.join(lane['items'])}`",
                f"- Waiting for input: `{lane['waiting_for_input_count']}`",
                f"- Armed: `{lane['armed_count']}`",
                "",
            ]
        )
        for item in [row for row in checklist["items"] if row["lane"] == lane["lane"]]:
            lines.extend(
                [
                    f"### {item['name']}",
                    "",
                    f"- Priority: `{item['priority']}`",
                    f"- Source status: `{item['source_status']}`",
                    f"- Dispatch status: `{item['dispatch_status']}`",
                    f"- Safety note: {item['safety_note']}",
                ]
            )
            if item["missing_fields"]:
                lines.append("- Fields to collect:")
                for field in item["missing_fields"]:
                    suffix = " (secret reference only)" if field in item["secret_reference_fields"] else ""
                    lines.append(f"  - `{field}`{suffix}")
            if item["missing_requirements"]:
                lines.append("- Missing requirements:")
                for requirement in item["missing_requirements"]:
                    lines.append(f"  - {requirement}")
            if item["validation_after_collection"]:
                lines.append("- Validate after collection:")
                for command in item["validation_after_collection"]:
                    lines.append(f"  - `{command}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--validation", default=str(DEFAULT_VALIDATION))
    parser.add_argument("--execution-plan", default=str(DEFAULT_EXECUTION_PLAN))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_MD))
    args = parser.parse_args()

    checklist = build_checklist(
        load_json(Path(args.packet).expanduser().resolve()),
        load_json(Path(args.validation).expanduser().resolve()),
        load_json(Path(args.execution_plan).expanduser().resolve()),
    )

    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(checklist, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(markdown(checklist), encoding="utf-8")

    print(
        json.dumps(
            {
                "success": True,
                "item_count": checklist["item_count"],
                "lane_count": checklist["lane_count"],
                "blocked_rows": checklist["blocked_rows"],
                "armed_rows": checklist["armed_rows"],
                "all_inputs_present": checklist["all_inputs_present"],
                "output_json": str(output_json),
                "output_md": str(output_md),
                "network_io": checklist["network_io"],
                "destructive_actions": checklist["destructive_actions"],
                "secrets_printed": checklist["secrets_printed"],
                "live_commands_included": checklist["live_commands_included"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
