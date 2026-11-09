#!/usr/bin/env python3
"""Build an operator input packet for the remaining external backlog gates.

The packet is read-only. It does not contact networks, run live gates, mutate
deployment state, or print secrets. It converts the current readiness report
into concrete input fields and validation commands for the currently blocked
items.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from check_remaining_backlog_readiness import (  # noqa: E402
    DEFAULT_DEPLOY_ROOT,
    _load_values,
    _summary,
    collect,
)


DEFAULT_JSON = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-external-input-packet.json"
DEFAULT_MD = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-external-input-packet.md"

ITEM_ORDER = [
    "formal_domain_https",
    "gpu_gromacs_md_live",
    "md_blackbox_live_e2e",
    "ligand_runtime_live",
    "oss_minio_live_e2e",
    "admin_authenticated_screenshots",
    "maintenance_window_drills",
    "remote_pytest_runner",
]

INPUT_FIELDS = {
    "formal_domain_https": [
        "formal_domain",
        "dns_record_owner",
        "tls_certificate_source",
        "PUBLIC_BASE_URL",
        "FRONTEND_URL",
        "OIDC_ISSUER",
    ],
    "gpu_gromacs_md_live": [
        "gpu_node_or_runner",
        "gromacs_runtime_version",
        "wt_pdb_input",
        "mutant_pdb_input",
        "md_worker_capacity_window",
    ],
    "md_blackbox_live_e2e": [
        "MD_BLACKBOX_TASK_ID_or_ALLOW_MD_BLACKBOX_SUBMIT",
        "MD_BLACKBOX_EMAIL_or_LIVE_AI_EMAIL",
        "credential_secret_reference",
        "validation_window",
    ],
    "ligand_runtime_live": [
        "ligand_worker_image_or_host",
        "OpenBabel_or_RDKit_available",
        "AutoDock_Vina_available",
        "ACPYPE_or_AmberTools_available",
        "GROMACS_available",
    ],
    "oss_minio_live_e2e": [
        "storage_endpoint",
        "bucket_name",
        "access_key_secret_reference",
        "write_read_delete_permission_scope",
    ],
    "admin_authenticated_screenshots": [
        "SCREENSHOT_EMAIL_secret_reference",
        "SCREENSHOT_PASSWORD_secret_reference",
        "FRONTEND_BASE_URL",
    ],
    "maintenance_window_drills": [
        "MAINTENANCE_WINDOW_ID",
        "ALLOW_PRODUCTION_DRILL_approval",
        "REMOTE_BACKUP_TARGET_or_OFFSITE_BACKUP_TARGET",
        "EXTERNAL_STORAGE_RESTORE_TARGET",
    ],
    "remote_pytest_runner": [
        "ci_workflow_or_runner_image",
        "trigger_policy",
        "coverage_artifact_access",
        "local_backfill_runner_path",
    ],
}

VALIDATION_COMMANDS = {
    "formal_domain_https": [
        "make production-config-gate",
        "make nightly-live-gates FRONTEND_BASE_URL=https://<domain>",
    ],
    "gpu_gromacs_md_live": [
        "make backend-md-topology-live-gate",
    ],
    "md_blackbox_live_e2e": [
        "make backend-md-blackbox MD_BLACKBOX_ARGS='--task-id <id> --email <email>'",
    ],
    "ligand_runtime_live": [
        "make backend-ligand-toolchain-live-gate",
    ],
    "oss_minio_live_e2e": [
        "python3 scripts/smoke_oss_minio_contract.py --json --require-live",
    ],
    "admin_authenticated_screenshots": [
        "make manual-screenshots FRONTEND_BASE_URL=<url>",
    ],
    "maintenance_window_drills": [
        "make rollback-plan-json",
        "make restore-drill BACKUP_FILE=<backup>",
    ],
    "remote_pytest_runner": [
        "make pytest-runner-plan",
        "make pytest-runner",
    ],
}

PRIORITIES = {
    "formal_domain_https": "P0",
    "gpu_gromacs_md_live": "P0",
    "md_blackbox_live_e2e": "P0",
    "ligand_runtime_live": "P1",
    "oss_minio_live_e2e": "P0",
    "admin_authenticated_screenshots": "P1",
    "maintenance_window_drills": "P1",
    "remote_pytest_runner": "P1",
}


def item_payload(index: int, item: Any) -> Dict[str, Any]:
    name = item.name
    return {
        "id": index,
        "name": name,
        "priority": PRIORITIES.get(name, "P2"),
        "status": item.status,
        "bucket": item.bucket,
        "detail": item.detail,
        "missing_requirements": list(item.missing_requirements),
        "required_input_fields": INPUT_FIELDS.get(name, list(item.missing_requirements)),
        "validation_commands": VALIDATION_COMMANDS.get(name, list(item.next_actions)),
        "next_actions": list(item.next_actions),
        "source": item.source,
    }


def priority_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for item in items:
        priority = str(item.get("priority") or "P2")
        row = summary.setdefault(
            priority,
            {
                "item_count": 0,
                "items": [],
                "required_input_field_count": 0,
            },
        )
        row["item_count"] += 1
        row["items"].append(str(item.get("name") or "unnamed"))
        row["required_input_field_count"] += len(item.get("required_input_fields") or [])
    return {priority: summary[priority] for priority in sorted(summary)}


def build_packet(deploy_root: Path, env_file: Path | None) -> Dict[str, Any]:
    values = _load_values(env_file)
    runtime_env = {
        key: value
        for key, value in values.items()
        if key.startswith("MINIO_") or key.startswith("ALIYUN_OSS_")
    }
    items = collect(deploy_root, values, runtime_env=runtime_env)
    by_name = {item.name: item for item in items}
    ordered = [
        item_payload(index, by_name[name])
        for index, name in enumerate(ITEM_ORDER, start=1)
        if name in by_name
        and by_name[name].bucket != "local_capable"
        and by_name[name].status != "ready"
    ]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_external_input_packet",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "summary": _summary(items),
        "item_count": len(ordered),
        "priority_summary": priority_summary(ordered),
        "items": ordered,
    }


def markdown(packet: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# Remaining Backlog External Input Packet",
        "",
        f"- Created at: `{packet['created_at']}`",
        f"- Mode: `{packet['mode']}`",
        f"- Network IO: `{packet['network_io']}`",
        f"- Destructive actions: `{packet['destructive_actions']}`",
        f"- Summary: `{json.dumps(packet['summary'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Priority Summary",
        "",
        "| Priority | Items | Required Input Fields |",
        "|---|---:|---:|",
    ]
    for priority, row in packet.get("priority_summary", {}).items():
        lines.append(
            f"| `{priority}` | `{', '.join(row['items'])}` | `{row['required_input_field_count']}` |"
        )
    lines.append("")
    for item in packet["items"]:
        lines.extend(
            [
                f"## {item['id']}. {item['name']}",
                "",
                f"- Priority: `{item['priority']}`",
                f"- Status: `{item['status']}`",
                f"- Bucket: `{item['bucket']}`",
                f"- Detail: {item['detail']}",
                "- Required input fields:",
            ]
        )
        for field in item["required_input_fields"]:
            lines.append(f"  - `{field}`")
        if item["missing_requirements"]:
            lines.append("- Current missing requirements:")
            for missing in item["missing_requirements"]:
                lines.append(f"  - `{missing}`")
        lines.append("- Validation commands:")
        for command in item["validation_commands"]:
            lines.append(f"  - `{command}`")
        if item["next_actions"]:
            lines.append("- Next actions:")
            for action in item["next_actions"]:
                lines.append(f"  - {action}")
        if item["source"]:
            lines.append(f"- Source: `{item['source']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deploy-root", default=str(DEFAULT_DEPLOY_ROOT))
    parser.add_argument("--env-file", default=str(PROJECT_ROOT / "docker" / ".env.aliyun.app.example"))
    parser.add_argument("--output-json", default=str(DEFAULT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_MD))
    args = parser.parse_args()

    deploy_root = Path(args.deploy_root).expanduser().resolve()
    env_file = Path(args.env_file).expanduser().resolve() if args.env_file else None
    packet = build_packet(deploy_root, env_file)

    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.write_text(markdown(packet), encoding="utf-8")

    print(json.dumps({
        "success": True,
        "item_count": packet["item_count"],
        "summary": packet["summary"],
        "priority_summary": packet["priority_summary"],
        "output_json": str(output_json),
        "output_md": str(output_md),
        "network_io": packet["network_io"],
        "destructive_actions": packet["destructive_actions"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
