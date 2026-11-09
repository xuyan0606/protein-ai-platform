#!/usr/bin/env python3
"""Validate evidence recorded for the three release manual gates.

This validator is read-only with respect to external systems. It reads a
local JSON evidence record, writes a validation report, and never contacts
cloud storage, runs release acceptance, restores a database, or changes a
production path.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-evidence-inputs.template.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "manuals" / "release-manual-gate-evidence-validation-report.json"

GATE_FIELDS = {
    "production_rollback_drill_gate": [
        "maintenance_window_id",
        "authorization_evidence_path",
        "rollback_plan_path",
        "restore_drill_path",
        "backup_verify_path",
        "pg_restore_list_path",
    ],
    "offsite_backup_restore_drill_gate": [
        "backup_target",
        "restore_target",
        "copy_evidence_path",
        "checksum_evidence_path",
        "restore_evidence_path",
        "application_readonly_smoke_path",
    ],
    "external_storage_restore_validation_gate": [
        "backup_ref",
        "restore_target",
        "shadow_restore_evidence_path",
        "sample_object_read_evidence_path",
        "application_readonly_smoke_path",
    ],
}

PLACEHOLDER_PREFIXES = ("<",)
PLACEHOLDER_VALUES = {"", "tbd", "todo", "pending", "fill", "none", "null"}


def _template() -> dict[str, Any]:
    return {
        "mode": "release_manual_gate_evidence_template",
        "policy": (
            "Record references to evidence only. Do not paste cloud access keys, database passwords, "
            "OIDC secrets, or raw tokens into this file. The validator does not contact external systems."
        ),
        "release": {
            "release_date": "<YYYY-MM-DD>",
            "release_owner": "<name / team>",
            "reviewer": "<name / team>",
            "business_owner": "<name / team>",
            "maintenance_window_id": "<MAINTENANCE_WINDOW_ID>",
            "release_package": "<dist/packages/...tar.gz>",
            "release_package_sha256_evidence": "<path>",
            "database_backup": "<backups/protein_ai_...dump>",
            "database_backup_sha256_evidence": "<path>",
            "evidence_archive_dir": "<docs/manuals/drill-records/YYYY-MM-DD-.../>",
        },
        "release_acceptance": {
            "status": "<passed>",
            "failed": None,
            "blocked": None,
            "manual_required": None,
            "skipped": None,
            "json_output_path": "<path>",
        },
        "gates": {
            "production_rollback_drill_gate": {
                "status": "<passed>",
                "maintenance_window_id": "<fill>",
                "authorization_evidence_path": "<path>",
                "rollback_plan_path": "<path>",
                "restore_drill_path": "<path>",
                "backup_verify_path": "<path>",
                "pg_restore_list_path": "<path>",
                "conclusion": "<passed>",
            },
            "offsite_backup_restore_drill_gate": {
                "status": "<passed>",
                "backup_target": "<redacted target / object ref>",
                "restore_target": "<independent restore target>",
                "copy_evidence_path": "<path>",
                "checksum_evidence_path": "<path>",
                "restore_evidence_path": "<path>",
                "application_readonly_smoke_path": "<path>",
                "conclusion": "<passed>",
            },
            "external_storage_restore_validation_gate": {
                "status": "<passed>",
                "backup_ref": "<snapshot / backup ref>",
                "restore_target": "<shadow bucket / prefix>",
                "shadow_restore_evidence_path": "<path>",
                "sample_object_read_evidence_path": "<path>",
                "application_readonly_smoke_path": "<path>",
                "production_path_switched": None,
                "conclusion": "<passed>",
            },
        },
        "decision": {
            "automatic_failed_zero": None,
            "automatic_blocked_zero": None,
            "maintenance_evidence_complete": None,
            "offsite_restore_evidence_complete": None,
            "external_storage_evidence_complete": None,
            "rollback_path_ready": None,
            "approvals_complete": None,
            "final_decision": "<go/no-go/defer>",
            "release_owner_signature": "<name / timestamp>",
            "reviewer_signature": "<name / timestamp>",
            "business_owner_signature": "<name / timestamp>",
        },
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _is_filled(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        return bool(normalized) and normalized not in PLACEHOLDER_VALUES and not normalized.startswith(PLACEHOLDER_PREFIXES)
    return bool(value)


def _is_zero(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def _is_true(value: Any) -> bool:
    return value is True


def _group(payload: dict[str, Any], key: str) -> dict[str, Any]:
    groups = payload.get("gates")
    if not isinstance(groups, dict):
        return {}
    value = groups.get(key)
    return value if isinstance(value, dict) else {}


def _validate_gate(name: str, values: dict[str, Any]) -> dict[str, Any]:
    missing = []
    for field in GATE_FIELDS[name]:
        if not _is_filled(values.get(field)):
            missing.append(field)
    if values.get("status") != "passed":
        missing.append("status=passed")
    if values.get("conclusion") != "passed":
        missing.append("conclusion=passed")
    if name == "external_storage_restore_validation_gate" and values.get("production_path_switched") is not False:
        missing.append("production_path_switched=false")
    return {
        "name": name,
        "ready": not missing,
        "missing_fields": missing,
    }


def _build_report(payload: dict[str, Any]) -> dict[str, Any]:
    release = payload.get("release") if isinstance(payload.get("release"), dict) else {}
    acceptance = payload.get("release_acceptance")
    acceptance = acceptance if isinstance(acceptance, dict) else {}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}

    release_missing = [
        field
        for field in (
            "release_date",
            "release_owner",
            "reviewer",
            "business_owner",
            "release_package",
            "release_package_sha256_evidence",
            "database_backup",
            "database_backup_sha256_evidence",
            "evidence_archive_dir",
        )
        if not _is_filled(release.get(field))
    ]
    acceptance_missing = [
        field
        for field in ("status", "json_output_path")
        if not _is_filled(acceptance.get(field))
    ]
    for field in ("failed", "blocked", "manual_required", "skipped"):
        if not _is_zero(acceptance.get(field)):
            acceptance_missing.append(f"{field}=0")
    if acceptance.get("status") != "passed":
        acceptance_missing.append("status=passed")

    gates = [_validate_gate(name, _group(payload, name)) for name in GATE_FIELDS]
    missing_gates = [gate["name"] for gate in gates if not gate["ready"]]
    decision_missing = []
    for field in (
        "automatic_failed_zero",
        "automatic_blocked_zero",
        "maintenance_evidence_complete",
        "offsite_restore_evidence_complete",
        "external_storage_evidence_complete",
        "rollback_path_ready",
        "approvals_complete",
        "release_owner_signature",
        "reviewer_signature",
        "business_owner_signature",
    ):
        if field in {
            "automatic_failed_zero",
            "automatic_blocked_zero",
            "maintenance_evidence_complete",
            "offsite_restore_evidence_complete",
            "external_storage_evidence_complete",
            "rollback_path_ready",
            "approvals_complete",
        }:
            if not _is_true(decision.get(field)):
                decision_missing.append(f"{field}=true")
        elif not _is_filled(decision.get(field)):
            decision_missing.append(field)

    final_decision = decision.get("final_decision")
    if final_decision not in {"go", "no-go", "defer"}:
        decision_missing.append("final_decision=go|no-go|defer")

    missing_sections = []
    if release_missing:
        missing_sections.append("release")
    if acceptance_missing:
        missing_sections.append("release_acceptance")
    if missing_gates:
        missing_sections.extend(missing_gates)
    if decision_missing:
        missing_sections.append("decision")

    evidence_complete = not missing_sections
    ready_for_go = evidence_complete and final_decision == "go"
    if ready_for_go:
        status = "ready-for-go"
    elif final_decision == "no-go" and evidence_complete:
        status = "no-go"
    elif final_decision == "defer" and evidence_complete:
        status = "defer"
    else:
        status = "manual_required"

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_release_manual_gate_evidence_validation",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "evidence_complete": evidence_complete,
        "ready_for_go": ready_for_go,
        "status": status,
        "missing_sections": missing_sections,
        "release_missing_fields": release_missing,
        "release_acceptance_missing_fields": acceptance_missing,
        "gates": gates,
        "decision_missing_fields": decision_missing,
        "final_decision": final_decision if _is_filled(final_decision) else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--values", default=str(DEFAULT_TEMPLATE), help="Completed evidence JSON record")
    parser.add_argument("--write-template", action="store_true", help="Write/update the evidence input template")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Validation report path")
    parser.add_argument("--require-go", action="store_true", help="Exit non-zero unless evidence is complete and final decision is go")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    values_path = Path(args.values).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if args.write_template or not values_path.exists():
        values_path.parent.mkdir(parents=True, exist_ok=True)
        values_path.write_text(json.dumps(_template(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    try:
        payload = _load_json(values_path)
        report = _build_report(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        report = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "read_only_release_manual_gate_evidence_validation",
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
            "evidence_complete": False,
            "ready_for_go": False,
            "status": "manual_required",
            "missing_sections": ["evidence_file"],
            "error": str(exc),
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "status": report["status"],
        "evidence_complete": report["evidence_complete"],
        "ready_for_go": report["ready_for_go"],
        "missing_sections": report.get("missing_sections", []),
        "output": str(output_path),
        "evidence": str(values_path),
        "network_io": report["network_io"],
        "destructive_actions": report["destructive_actions"],
        "secrets_printed": report["secrets_printed"],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"summary\t{summary['status']}\tmissing_sections={len(summary['missing_sections'])}")
        print(f"output\t{summary['output']}")
        print(f"evidence\t{summary['evidence']}")
    if args.require_go:
        return 0 if report["ready_for_go"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
