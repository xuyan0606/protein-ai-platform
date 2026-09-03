#!/usr/bin/env python3
"""Validate operator inputs required to clear release manual gates.

This script is read-only. It validates values for the three release acceptance
manual gates and emits the exact non-destructive final acceptance command. It
does not contact external services, run rollback, restore databases, or switch
storage paths.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-inputs.template.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-input-validation-report.json"

REQUIRED_GROUPS = {
    "production_rollback_drill_gate": [
        "MAINTENANCE_WINDOW_ID",
        "ALLOW_PRODUCTION_DRILL",
    ],
    "offsite_backup_restore_drill_gate": [
        "OFFSITE_BACKUP_TARGET",
        "OFFSITE_RESTORE_TARGET",
    ],
    "external_storage_restore_validation_gate": [
        "EXTERNAL_STORAGE_BACKUP_REF",
        "EXTERNAL_STORAGE_RESTORE_TARGET",
    ],
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _template() -> dict[str, Any]:
    return {
        "mode": "release_manual_gate_inputs_template",
        "policy": (
            "Fill release approval identifiers, restore targets, and backup/storage references only. "
            "Do not paste cloud access keys, database passwords, or OIDC secrets into this file."
        ),
        "required_inputs": {
            "production_rollback_drill_gate": {
                "MAINTENANCE_WINDOW_ID": "<fill>",
                "ALLOW_PRODUCTION_DRILL": False,
            },
            "offsite_backup_restore_drill_gate": {
                "OFFSITE_BACKUP_TARGET": "<fill>",
                "OFFSITE_RESTORE_TARGET": "<fill-independent-restore-target>",
            },
            "external_storage_restore_validation_gate": {
                "EXTERNAL_STORAGE_BACKUP_REF": "<fill>",
                "EXTERNAL_STORAGE_RESTORE_TARGET": "<fill-shadow-bucket-or-prefix>",
            },
        },
        "options": {
            "BACKUP_FILE": "",
            "BACKUP_VERIFY_COMPOSE": True,
        },
    }


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        return bool(stripped) and not stripped.startswith("<")
    return bool(value)


def _values(payload: dict[str, Any]) -> dict[str, Any]:
    required = payload.get("required_inputs")
    return required if isinstance(required, dict) else {}


def _options(payload: dict[str, Any]) -> dict[str, Any]:
    options = payload.get("options")
    return options if isinstance(options, dict) else {}


def _validate_group(group: str, required_fields: list[str], values: dict[str, Any]) -> dict[str, Any]:
    group_values = values.get(group)
    group_values = group_values if isinstance(group_values, dict) else {}
    missing = []
    provided = []
    for field in required_fields:
        if _nonempty(group_values.get(field)):
            provided.append(field)
        else:
            missing.append(field)
    return {
        "name": group,
        "ready": not missing,
        "provided_fields": provided,
        "missing_fields": missing,
    }


def _build_command(payload: dict[str, Any], ready: bool) -> list[str]:
    if not ready:
        return []
    values = _values(payload)
    options = _options(payload)
    rollback = values["production_rollback_drill_gate"]
    offsite = values["offsite_backup_restore_drill_gate"]
    storage = values["external_storage_restore_validation_gate"]
    command = [
        "./backend/.venv/bin/python",
        "scripts/run_release_acceptance.py",
        "--include-backup-verify",
    ]
    if options.get("BACKUP_VERIFY_COMPOSE", True):
        command.append("--backup-verify-compose")
    backup_file = str(options.get("BACKUP_FILE") or "").strip()
    if backup_file and not backup_file.startswith("<"):
        command.extend(["--backup-file", backup_file])
    command.extend([
        "--maintenance-window-id",
        str(rollback["MAINTENANCE_WINDOW_ID"]).strip(),
        "--allow-production-drill",
        "--offsite-backup-target",
        str(offsite["OFFSITE_BACKUP_TARGET"]).strip(),
        "--offsite-restore-target",
        str(offsite["OFFSITE_RESTORE_TARGET"]).strip(),
        "--external-storage-backup-ref",
        str(storage["EXTERNAL_STORAGE_BACKUP_REF"]).strip(),
        "--external-storage-restore-target",
        str(storage["EXTERNAL_STORAGE_RESTORE_TARGET"]).strip(),
        "--json",
    ])
    return command


def _build_report(payload: dict[str, Any]) -> dict[str, Any]:
    values = _values(payload)
    groups = [_validate_group(group, fields, values) for group, fields in REQUIRED_GROUPS.items()]
    missing_groups = [group["name"] for group in groups if not group["ready"]]
    ready = not missing_groups
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_release_manual_gate_input_validation",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "all_inputs_present": ready,
        "ready_to_run_final_acceptance": ready,
        "missing_gate_count": len(missing_groups),
        "missing_gates": missing_groups,
        "groups": groups,
        "final_acceptance_command": _build_command(payload, ready),
        "status": "ready" if ready else "manual_required",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--values", default=str(DEFAULT_TEMPLATE), help="Operator-supplied JSON values")
    parser.add_argument("--write-template", action="store_true", help="Write/update the input template")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Validation report path")
    parser.add_argument("--require-complete", action="store_true", help="Exit non-zero unless all required inputs are present")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    values_path = Path(args.values).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if args.write_template or not values_path.exists():
        values_path.parent.mkdir(parents=True, exist_ok=True)
        values_path.write_text(json.dumps(_template(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload = _load_json(values_path)
    report = _build_report(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "success": not (args.require_complete and not report["all_inputs_present"]),
        "status": report["status"],
        "all_inputs_present": report["all_inputs_present"],
        "ready_to_run_final_acceptance": report["ready_to_run_final_acceptance"],
        "missing_gate_count": report["missing_gate_count"],
        "output": str(output_path),
        "template": str(values_path),
        "network_io": report["network_io"],
        "destructive_actions": report["destructive_actions"],
        "secrets_printed": report["secrets_printed"],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"summary\t{summary['status']}\tmissing_gate_count={summary['missing_gate_count']}")
        print(f"output\t{summary['output']}")
        print(f"template\t{summary['template']}")
    return 1 if args.require_complete and not report["all_inputs_present"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
