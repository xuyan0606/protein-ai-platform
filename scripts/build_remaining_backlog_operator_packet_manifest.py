#!/usr/bin/env python3
"""Build a checksum manifest for the remaining backlog operator packet.

The manifest is read-only. It hashes the remaining-backlog scripts and handoff
artifacts, records the dispatch checklist validation boundary, and can check
whether an existing manifest is current. It does not run live gates, contact
networks, deploy code, or print secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-operator-packet-manifest.json"
DISPATCH_VALIDATION_REPORT = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-operator-dispatch-checklist-validation-report.json"

PACKET_FILES = [
    ("readiness_script", "scripts/check_remaining_backlog_readiness.py"),
    ("external_input_packet_builder", "scripts/build_remaining_backlog_external_input_packet.py"),
    ("external_input_validator", "scripts/validate_remaining_backlog_external_inputs.py"),
    ("gate_execution_plan_builder", "scripts/build_remaining_backlog_gate_execution_plan.py"),
    ("operator_dispatch_builder", "scripts/build_remaining_backlog_operator_dispatch_checklist.py"),
    ("operator_dispatch_validator", "scripts/validate_remaining_backlog_operator_dispatch_checklist.py"),
    ("operator_packet_manifest_builder", "scripts/build_remaining_backlog_operator_packet_manifest.py"),
    ("remaining_backlog_go_no_go_summary_builder", "scripts/build_remaining_backlog_go_no_go_summary.py"),
    ("remaining_backlog_execution_tickets_builder", "scripts/build_remaining_backlog_execution_tickets.py"),
    ("remaining_backlog_execution_tickets_validator", "scripts/validate_remaining_backlog_execution_tickets.py"),
    ("p0_p4_backlog_ticket_bridge_builder", "scripts/build_p0_p4_backlog_ticket_bridge.py"),
    ("p0_p4_backlog_ticket_bridge_validator", "scripts/validate_p0_p4_backlog_ticket_bridge.py"),
    ("p0_p4_status_export_builder", "scripts/build_p0_p4_status_export.py"),
    ("p0_p4_status_export_json", "docs/manuals/p0-p4-status-export.json"),
    ("p0_p4_status_export_md", "docs/manuals/p0-p4-status-export.md"),
    ("p0_p4_backlog_ticket_bridge_json", "docs/manuals/p0-p4-backlog-ticket-bridge.json"),
    ("p0_p4_backlog_ticket_bridge_md", "docs/manuals/p0-p4-backlog-ticket-bridge.md"),
    ("p0_p4_backlog_ticket_bridge_validation_report", "docs/manuals/p0-p4-backlog-ticket-bridge-validation-report.json"),
    ("remaining_backlog_go_no_go_summary_json", "docs/manuals/remaining-backlog-go-no-go-summary.json"),
    ("remaining_backlog_go_no_go_summary_md", "docs/manuals/remaining-backlog-go-no-go-summary.md"),
    ("external_input_packet_json", "docs/manuals/remaining-backlog-external-input-packet.json"),
    ("external_input_packet_md", "docs/manuals/remaining-backlog-external-input-packet.md"),
    ("external_input_values_template", "docs/manuals/remaining-backlog-external-input-values.template.json"),
    ("external_input_validation_report", "docs/manuals/remaining-backlog-external-input-validation-report.json"),
    ("gate_execution_plan_json", "docs/manuals/remaining-backlog-gate-execution-plan.json"),
    ("gate_execution_plan_md", "docs/manuals/remaining-backlog-gate-execution-plan.md"),
    ("operator_dispatch_checklist_json", "docs/manuals/remaining-backlog-operator-dispatch-checklist.json"),
    ("operator_dispatch_checklist_md", "docs/manuals/remaining-backlog-operator-dispatch-checklist.md"),
    ("operator_dispatch_validation_report", "docs/manuals/remaining-backlog-operator-dispatch-checklist-validation-report.json"),
    ("execution_tickets_json", "docs/manuals/remaining-backlog-execution-tickets.json"),
    ("execution_tickets_md", "docs/manuals/remaining-backlog-execution-tickets.md"),
    ("execution_tickets_validation_report", "docs/manuals/remaining-backlog-execution-tickets-validation-report.json"),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_row(label: str, relative_path: str) -> Dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    exists = path.exists()
    return {
        "label": label,
        "path": relative_path,
        "exists": exists,
        "sha256": _sha256(path) if exists and path.is_file() else None,
        "bytes": path.stat().st_size if exists and path.is_file() else None,
    }


def _load_dispatch_validation() -> Dict[str, Any]:
    if not DISPATCH_VALIDATION_REPORT.exists():
        return {"_exists": False}
    try:
        payload = json.loads(DISPATCH_VALIDATION_REPORT.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_exists": True, "_invalid_json": str(exc)}
    if not isinstance(payload, dict):
        return {"_exists": True, "_invalid_shape": "expected object"}
    payload["_exists"] = True
    return payload


def _dispatch_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "exists": bool(payload.get("_exists")),
        "invalid_json": payload.get("_invalid_json"),
        "invalid_shape": payload.get("_invalid_shape"),
        "success": payload.get("success") is True,
        "failure_count": int(payload.get("failure_count") or 0),
        "source_bound_current": payload.get("source_bound_current") is True,
        "item_count": payload.get("item_count"),
        "lane_count": payload.get("lane_count"),
        "blocked_rows": payload.get("blocked_rows"),
        "armed_rows": payload.get("armed_rows"),
    }


def build_manifest() -> Dict[str, Any]:
    files = [_file_row(label, rel) for label, rel in PACKET_FILES]
    missing = [row["path"] for row in files if not row["exists"]]
    validation = _dispatch_summary(_load_dispatch_validation())
    packet_ready = not missing and validation["success"] is True and validation["source_bound_current"] is True
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_remaining_backlog_operator_packet_manifest",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "live_gate_execution_allowed": False,
        "operator_packet_status": {
            "ready_for_operator_review": packet_ready,
            "remaining_backlog_status": "external_required",
            "live_gate_armed_rows": validation.get("armed_rows"),
            "blocked_input_rows": validation.get("blocked_rows"),
            "next_decision": "operator must collect external inputs by lane, rerun validation, then explicitly execute live gates only for armed rows",
        },
        "dispatch_validation": validation,
        "files": files,
        "summary": {
            "status": "ready-for-operator-review" if packet_ready else "incomplete",
            "file_count": len(files),
            "missing_files": missing,
        },
    }


def _comparable_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    comparable = dict(manifest)
    comparable.pop("created_at", None)
    return comparable


def check_manifest(output: Path) -> Tuple[bool, Dict[str, Any]]:
    if not output.exists():
        return False, {
            "status": "stale-or-missing",
            "reason": "manifest_missing",
            "output": str(output),
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
        }
    try:
        existing = json.loads(output.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, {
            "status": "stale-or-missing",
            "reason": "manifest_invalid_json",
            "error": str(exc),
            "output": str(output),
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
        }
    if not isinstance(existing, dict):
        return False, {
            "status": "stale-or-missing",
            "reason": "manifest_invalid_shape",
            "output": str(output),
            "network_io": "not_executed",
            "destructive_actions": "not_executed",
            "secrets_printed": False,
        }

    current = build_manifest()
    existing_cmp = _comparable_manifest(existing)
    current_cmp = _comparable_manifest(current)
    is_current = existing_cmp == current_cmp and current["summary"]["status"] == "ready-for-operator-review"
    stale_sections: List[str] = []
    for key in (
        "mode",
        "network_io",
        "destructive_actions",
        "secrets_printed",
        "live_gate_execution_allowed",
        "operator_packet_status",
        "dispatch_validation",
        "files",
        "summary",
    ):
        if existing_cmp.get(key) != current_cmp.get(key):
            stale_sections.append(key)
    if current["summary"]["status"] != "ready-for-operator-review" and "summary" not in stale_sections:
        stale_sections.append("summary")

    return is_current, {
        "status": "current" if is_current else "stale-or-missing",
        "reason": None if is_current else (
            "manifest_differs_from_current_packet"
            if existing_cmp != current_cmp
            else "current_packet_incomplete"
        ),
        "stale_sections": stale_sections,
        "file_count": current["summary"]["file_count"],
        "missing_files": current["summary"]["missing_files"],
        "dispatch_validation_success": current["dispatch_validation"]["success"],
        "source_bound_current": current["dispatch_validation"]["source_bound_current"],
        "output": str(output),
        "network_io": current["network_io"],
        "destructive_actions": current["destructive_actions"],
        "secrets_printed": current["secrets_printed"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Manifest output JSON path")
    parser.add_argument("--check", action="store_true", help="Verify that the existing manifest is current without writing")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    if args.check:
        ok, summary = check_manifest(output)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        else:
            print(f"summary\t{summary['status']}\toutput={summary['output']}")
            if summary.get("reason"):
                print(f"reason\t{summary['reason']}")
            if summary.get("stale_sections"):
                print(f"stale_sections\t{','.join(summary['stale_sections'])}")
        return 0 if ok else 1

    manifest = build_manifest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "status": manifest["summary"]["status"],
        "file_count": manifest["summary"]["file_count"],
        "missing_files": manifest["summary"]["missing_files"],
        "dispatch_validation_success": manifest["dispatch_validation"]["success"],
        "source_bound_current": manifest["dispatch_validation"]["source_bound_current"],
        "output": str(output),
        "network_io": manifest["network_io"],
        "destructive_actions": manifest["destructive_actions"],
        "secrets_printed": manifest["secrets_printed"],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "summary\t"
            f"{summary['status']}\t"
            f"files={summary['file_count']}\t"
            f"missing={len(summary['missing_files'])}"
        )
        print(f"output\t{summary['output']}")
    return 0 if manifest["summary"]["status"] == "ready-for-operator-review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
