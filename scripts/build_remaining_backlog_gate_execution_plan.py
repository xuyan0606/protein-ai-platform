#!/usr/bin/env python3
"""Build a redacted execution plan for remaining backlog live gates.

This script consumes the external input packet and operator values file. It
does not run live gates, contact networks, read secret material, or mutate
deployment state. Items are armed only when all required inputs are present.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from validate_remaining_backlog_external_inputs import (  # noqa: E402
    DEFAULT_PACKET,
    DEFAULT_TEMPLATE,
    build_report,
    field_is_secret_reference,
    load_json,
    values_by_item,
)


DEFAULT_JSON = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-gate-execution-plan.json"
DEFAULT_MD = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-gate-execution-plan.md"

COMMAND_TEMPLATES = {
    "formal_domain_https": [
        "PUBLIC_BASE_URL={PUBLIC_BASE_URL} FRONTEND_URL={FRONTEND_URL} OIDC_ISSUER={OIDC_ISSUER} make production-config-gate",
        "FRONTEND_BASE_URL={PUBLIC_BASE_URL} make nightly-live-gates",
    ],
    "gpu_gromacs_md_live": [
        "GPU_NODE_OR_RUNNER={gpu_node_or_runner} GROMACS_RUNTIME_VERSION={gromacs_runtime_version} make backend-md-topology-live-gate",
        "Submit approved WT/mutant replicate batches using wt_pdb_input={wt_pdb_input} and mutant_pdb_input={mutant_pdb_input} during md_worker_capacity_window={md_worker_capacity_window}.",
    ],
    "md_blackbox_live_e2e": [
        "Resolve credential_secret_reference into the live runner environment without printing it.",
        "make backend-md-blackbox MD_BLACKBOX_ARGS='--task-id-or-submit {MD_BLACKBOX_TASK_ID_or_ALLOW_MD_BLACKBOX_SUBMIT} --email {MD_BLACKBOX_EMAIL_or_LIVE_AI_EMAIL}'",
    ],
    "ligand_runtime_live": [
        "Verify ligand runtime host/image {ligand_worker_image_or_host} has OpenBabel/RDKit={OpenBabel_or_RDKit_available}, Vina={AutoDock_Vina_available}, ACPYPE/AmberTools={ACPYPE_or_AmberTools_available}, GROMACS={GROMACS_available}.",
        "make backend-ligand-toolchain-live-gate",
    ],
    "oss_minio_live_e2e": [
        "Resolve access_key_secret_reference into OSS/MinIO environment variables without printing it.",
        "python3 scripts/smoke_oss_minio_contract.py --json --require-live",
    ],
    "admin_authenticated_screenshots": [
        "Resolve SCREENSHOT_EMAIL_secret_reference and SCREENSHOT_PASSWORD_secret_reference into environment variables without printing them.",
        "FRONTEND_BASE_URL={FRONTEND_BASE_URL} make manual-screenshots",
    ],
    "maintenance_window_drills": [
        "MAINTENANCE_WINDOW_ID={MAINTENANCE_WINDOW_ID} make rollback-plan-json",
        "Run approved production drills only after ALLOW_PRODUCTION_DRILL_approval={ALLOW_PRODUCTION_DRILL_approval}, remote target={REMOTE_BACKUP_TARGET_or_OFFSITE_BACKUP_TARGET}, restore target={EXTERNAL_STORAGE_RESTORE_TARGET}.",
    ],
    "remote_pytest_runner": [
        "Run ci_workflow_or_runner_image={ci_workflow_or_runner_image} with trigger_policy={trigger_policy}.",
        "Archive coverage_artifact_access={coverage_artifact_access} after backend pytest completes.",
    ],
}

SAFETY_NOTES = {
    "formal_domain_https": "Requires real DNS and TLS cutover evidence before production HTTPS status can be claimed.",
    "gpu_gromacs_md_live": "Requires a real GPU/GROMACS runner and real WT/mutant inputs; this plan does not start MD jobs.",
    "md_blackbox_live_e2e": "Requires live credentials and either an existing task id or explicit submission approval.",
    "ligand_runtime_live": "Requires the real ligand toolchain runtime; local missing tools remain blocked.",
    "oss_minio_live_e2e": "Requires write/read/delete permission in a controlled live bucket scope.",
    "admin_authenticated_screenshots": "Requires admin credentials through secret references only.",
    "maintenance_window_drills": "Requires an approved maintenance window before any production drill.",
    "remote_pytest_runner": "Non-production CI runner must be used; production runtime containers are not test runners.",
}


def _display_value(field: str, value: Any) -> str:
    if field_is_secret_reference(field):
        return "<secret-reference-provided>"
    return str(value).strip()


def _command_value(field: str, item_values: Dict[str, Any]) -> str:
    value = _display_value(field, item_values.get(field, f"<{field}>"))
    return shlex.quote(value)


def _render_command(template: str, item_values: Dict[str, Any]) -> str:
    rendered = template
    for field in item_values:
        rendered = rendered.replace("{" + field + "}", _command_value(field, item_values))
    return rendered


def _redacted_values(required: List[str], item_values: Dict[str, Any]) -> Dict[str, str]:
    values = {}
    for field in required:
        if field in item_values:
            values[field] = _display_value(field, item_values[field])
    return values


def build_plan(packet: Dict[str, Any], values_payload: Dict[str, Any]) -> Dict[str, Any]:
    validation = build_report(packet, values_payload)
    values = values_by_item(values_payload)
    rows = []

    for row in validation["items"]:
        name = row["name"]
        item_values = values.get(name) if isinstance(values.get(name), dict) else {}
        templates = COMMAND_TEMPLATES.get(name, row.get("validation_commands") or [])
        commands = [_render_command(template, item_values) for template in templates] if row["ready_to_run"] else []
        rows.append(
            {
                "name": name,
                "status": row["status"],
                "ready_to_run": row["ready_to_run"],
                "armed": row["ready_to_run"],
                "missing_fields": row["missing_fields"],
                "required_input_fields": row["required_input_fields"],
                "secret_reference_fields": row["secret_reference_fields"],
                "redacted_values": _redacted_values(row["required_input_fields"], item_values),
                "command_plan": commands,
                "safety_note": SAFETY_NOTES.get(name, "Run only after required operator inputs are present."),
            }
        )

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_remaining_backlog_gate_execution_plan",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "item_count": len(rows),
        "armed_rows": sum(1 for row in rows if row["armed"]),
        "blocked_rows": sum(1 for row in rows if not row["armed"]),
        "all_inputs_present": validation["all_inputs_present"],
        "items": rows,
    }


def markdown(plan: Dict[str, Any]) -> str:
    lines = [
        "# Remaining Backlog Gate Execution Plan",
        "",
        f"- Created at: `{plan['created_at']}`",
        f"- Mode: `{plan['mode']}`",
        f"- Network IO: `{plan['network_io']}`",
        f"- Destructive actions: `{plan['destructive_actions']}`",
        f"- Secrets printed: `{str(plan['secrets_printed']).lower()}`",
        f"- Armed rows: `{plan['armed_rows']}`",
        f"- Blocked rows: `{plan['blocked_rows']}`",
        "",
    ]
    for item in plan["items"]:
        lines.extend(
            [
                f"## {item['name']}",
                "",
                f"- Status: `{item['status']}`",
                f"- Armed: `{str(item['armed']).lower()}`",
                f"- Safety note: {item['safety_note']}",
            ]
        )
        if item["missing_fields"]:
            lines.append("- Missing fields:")
            for field in item["missing_fields"]:
                lines.append(f"  - `{field}`")
        if item["redacted_values"]:
            lines.append("- Redacted values:")
            for field, value in sorted(item["redacted_values"].items()):
                lines.append(f"  - `{field}` = `{value}`")
        if item["command_plan"]:
            lines.append("- Command plan:")
            for command in item["command_plan"]:
                lines.append(f"  - `{command}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--values", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_MD))
    parser.add_argument("--require-any-armed", action="store_true", help="Exit non-zero unless at least one item is armed")
    args = parser.parse_args()

    packet = load_json(Path(args.packet).expanduser().resolve())
    values = load_json(Path(args.values).expanduser().resolve())
    plan = build_plan(packet, values)

    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(markdown(plan), encoding="utf-8")

    success = not (args.require_any_armed and plan["armed_rows"] == 0)
    print(
        json.dumps(
            {
                "success": success,
                "item_count": plan["item_count"],
                "armed_rows": plan["armed_rows"],
                "blocked_rows": plan["blocked_rows"],
                "all_inputs_present": plan["all_inputs_present"],
                "output_json": str(output_json),
                "output_md": str(output_md),
                "network_io": plan["network_io"],
                "destructive_actions": plan["destructive_actions"],
                "secrets_printed": plan["secrets_printed"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
