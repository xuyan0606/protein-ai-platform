#!/usr/bin/env python3
"""Build a compact P0-P4 status export from the read-only gap audit.

This script is a presentation/export layer only. It does not run live gates,
download data, train models, mutate databases, or print secrets.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_p0_p4_gap_audit import build_gap_audit


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_JSON = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-gap-audit.json"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-status-export.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-status-export.md"


PHASE_LABELS = {
    "P0": "Venus-level review experience",
    "P1": "enzyme-specific evidence layer",
    "P2": "structure-function scoring system",
    "P3": "DBTL project memory",
    "P4": "production closed-loop readiness",
}

APPROVAL_REQUIRED_TERMS = (
    "approval",
    "operator",
    "maintenance window",
    "product decision",
    "formal dbtl",
    "live gate",
    "wet-lab",
    "manufacturing",
    "training",
    "feedback",
    "baseline",
    "assay",
    "curated",
    "validated",
)


def _load_audit(input_json: Path) -> dict[str, Any]:
    if input_json.exists():
        return json.loads(input_json.read_text(encoding="utf-8"))
    return build_gap_audit()


def _item_names(items: list[dict[str, Any]], phase: str) -> list[str]:
    return [str(item.get("name")) for item in items if item.get("phase") == phase]


def _collect_by_phase(items: list[dict[str, Any]], phase: str, key: str) -> list[str]:
    values: list[str] = []
    for item in items:
        if item.get("phase") != phase:
            continue
        for value in item.get(key) or []:
            text = str(value)
            if text not in values:
                values.append(text)
    return values


def _open_local_gaps_by_phase(items: list[dict[str, Any]], phase: str) -> list[str]:
    values: list[str] = []
    for item in items:
        if item.get("phase") != phase:
            continue
        gap_status = item.get("local_gap_status")
        if isinstance(gap_status, dict) and isinstance(gap_status.get("open"), list):
            source = gap_status["open"]
        else:
            source = item.get("local_gaps") or []
        for value in source:
            text = str(value)
            if text not in values:
                values.append(text)
    return values


def _covered_local_gap_count(items: list[dict[str, Any]], phase: str) -> int:
    total = 0
    for item in items:
        if item.get("phase") != phase:
            continue
        gap_status = item.get("local_gap_status")
        if isinstance(gap_status, dict):
            total += int(gap_status.get("covered_count") or 0)
    return total


def _covered_local_followups(item: dict[str, Any]) -> list[dict[str, str]]:
    gap_status = item.get("local_gap_status")
    if not isinstance(gap_status, dict):
        return []
    covered = gap_status.get("covered")
    if not isinstance(covered, list):
        return []
    rows: list[dict[str, str]] = []
    for value in covered:
        if not isinstance(value, dict):
            continue
        rows.append(
            {
                "gap": str(value.get("gap") or ""),
                "status": str(value.get("status") or "covered_by_contract_status_export"),
                "evidence": str(value.get("evidence") or "p0_p4_contract_status_export_v1"),
            }
        )
    return rows


def _open_local_followups(item: dict[str, Any]) -> list[str]:
    gap_status = item.get("local_gap_status")
    if isinstance(gap_status, dict) and isinstance(gap_status.get("open"), list):
        return [str(value) for value in gap_status["open"]]
    return [str(value) for value in item.get("local_gaps") or []]


def _approval_required(item: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            str(item.get("phase") or ""),
            str(item.get("name") or ""),
            " ".join(str(value) for value in item.get("external_blockers") or []),
            " ".join(str(value) for value in item.get("must_not_claim") or []),
        ]
    ).lower()
    return bool(item.get("external_blockers")) or any(term in haystack for term in APPROVAL_REQUIRED_TERMS)


def _contract_status_item(item: dict[str, Any]) -> dict[str, Any]:
    external_blockers = [str(value) for value in item.get("external_blockers") or []]
    must_not_claim = [str(value) for value in item.get("must_not_claim") or []]
    return {
        "schema_version": "p0_p4_contract_status_export_v1",
        "phase": str(item.get("phase") or ""),
        "contract_name": str(item.get("name") or ""),
        "status": str(item.get("status") or "unknown"),
        "summary": str(item.get("summary") or ""),
        "evidence_tokens": [str(value) for value in item.get("evidence_tokens") or []],
        "local_followups": _open_local_followups(item),
        "covered_local_followups": _covered_local_followups(item),
        "external_blockers": external_blockers,
        "must_not_claim": must_not_claim,
        "read_only": True,
        "approval_required": _approval_required(item),
        "approval_state": "blocked_until_explicit_review" if _approval_required(item) else "not_required_for_local_contract_export",
        "capability_boundary": {
            "ready_local_contract_is_not_live_complete": True,
            "external_blockers_remain_blocking": bool(external_blockers),
            "covered_followups_are_visibility_only": True,
            "may_train_model": False,
            "may_claim_wet_lab_validation": False,
            "may_run_live_gate": False,
        },
    }


def _contract_status_items(audit: dict[str, Any]) -> list[dict[str, Any]]:
    items = audit.get("items") if isinstance(audit.get("items"), list) else []
    return [_contract_status_item(item) for item in items if isinstance(item, dict)]


def _phase_status_row(phase: str, audit: dict[str, Any]) -> dict[str, Any]:
    phase_summary = audit.get("phase_summary") or {}
    row = phase_summary.get(phase) or {}
    items = audit.get("items") if isinstance(audit.get("items"), list) else []
    item_count = int(row.get("item_count") or 0)
    ready_count = int(row.get("ready_local_contract") or 0)
    partial_count = int(row.get("partial") or 0)
    blocked_count = int(row.get("blocked") or 0)
    local_gaps = _open_local_gaps_by_phase(items, phase)
    external_blockers = _collect_by_phase(items, phase, "external_blockers")
    status = (
        "ready_local_contract"
        if item_count and ready_count == item_count and partial_count == 0 and blocked_count == 0
        else "partial"
    )
    return {
        "phase": phase,
        "label": PHASE_LABELS.get(phase, phase),
        "status": status,
        "item_count": item_count,
        "ready_local_contract": ready_count,
        "partial": partial_count,
        "blocked": blocked_count,
        "items": _item_names(items, phase),
        "top_local_gaps": local_gaps[:6],
        "covered_local_gap_count": _covered_local_gap_count(items, phase),
        "top_external_blockers": external_blockers[:6],
        "must_not_claim": _collect_by_phase(items, phase, "must_not_claim")[:8],
    }


def build_status_export(audit: dict[str, Any]) -> dict[str, Any]:
    phases = ["P0", "P1", "P2", "P3", "P4"]
    phase_rows = [_phase_status_row(phase, audit) for phase in phases]
    contract_status_items = _contract_status_items(audit)
    remaining = audit.get("remaining_backlog_summary") or {}
    local_followups = [
        gap
        for row in phase_rows
        for gap in row["top_local_gaps"]
    ]
    external_followups = [
        item.get("name")
        for item in audit.get("remaining_external_backlog", [])
        if isinstance(item, dict)
    ]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "p0_p4_status_export_v1",
        "mode": "read_only_p0_p4_status_export",
        "source_audit_mode": audit.get("mode") or "read_only_p0_p4_gap_audit",
        "decision": audit.get("decision") or "continue_local_gap_closure_fail_closed_for_external_dependencies",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "live_gate_execution_allowed": False,
        "phase_status": phase_rows,
        "contract_status_items": contract_status_items,
        "remaining_backlog_summary": remaining,
        "local_followups": local_followups[:12],
        "external_followups": external_followups,
        "status_export_contract": {
            "schema_version": "p0_p4_status_export_contract_v1",
            "source": "docs/manuals/p0-p4-gap-audit.json",
            "read_only": True,
            "consumer_scope": ["daily_report", "project_review", "SOP_status_page"],
            "must_label_ready_local_contract_as_not_live_complete": True,
            "must_keep_external_required_blocked": True,
            "open_local_gaps_are_read_from_gap_audit": True,
            "contract_status_items_are_source_bound": True,
            "covered_followups_do_not_clear_external_blockers": True,
            "local_followups_are_not_capability_completion": True,
        },
        "must_not_claim": [
            "ready local contract means production complete",
            "live gates have run",
            "model has been trained or retrained",
            "wet-lab validation is proven by status export",
            "manufacturing constraints are validated",
        ],
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# P0-P4 Status Export",
        "",
        f"- schema_version: `{payload['schema_version']}`",
        f"- decision: `{payload['decision']}`",
        f"- network_io: `{payload['network_io']}`",
        f"- live_gate_execution_allowed: `{payload['live_gate_execution_allowed']}`",
        "",
        "## Phase Status",
        "",
        "| Phase | Label | Status | Ready / Items | Open Local Followups | Covered Local Followups | External Blockers |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["phase_status"]:
        lines.append(
            f"| `{row['phase']}` | {row['label']} | `{row['status']}` | "
            f"`{row['ready_local_contract']} / {row['item_count']}` | "
            f"`{len(row['top_local_gaps'])}` | `{row['covered_local_gap_count']}` | "
            f"`{len(row['top_external_blockers'])}` |"
        )
    lines.extend(["", "## Phase Details", ""])
    for row in payload["phase_status"]:
        lines.extend(
            [
                f"### {row['phase']} / {row['label']}",
                f"- Status: `{row['status']}`",
                f"- Items: `{', '.join(row['items'])}`",
                f"- Covered local followups: `{row['covered_local_gap_count']}`",
            ]
        )
        if row["top_local_gaps"]:
            lines.append("- Local followups:")
            lines.extend([f"  - {value}" for value in row["top_local_gaps"]])
        if row["top_external_blockers"]:
            lines.append("- External blockers:")
            lines.extend([f"  - {value}" for value in row["top_external_blockers"]])
        if row["must_not_claim"]:
            lines.append("- Must not claim:")
            lines.extend([f"  - {value}" for value in row["must_not_claim"]])
        lines.append("")
    lines.extend(["## Contract Status Items", ""])
    for item in payload["contract_status_items"]:
        lines.extend(
            [
                f"### {item['phase']} / {item['contract_name']}",
                f"- Status: `{item['status']}`",
                f"- Read only: `{str(item['read_only']).lower()}`",
                f"- Approval required: `{str(item['approval_required']).lower()}`",
                f"- Approval state: `{item['approval_state']}`",
                f"- Evidence tokens: `{', '.join(item['evidence_tokens'])}`",
            ]
        )
        if item["local_followups"]:
            lines.append("- Open local followups:")
            lines.extend([f"  - {value}" for value in item["local_followups"]])
        if item["covered_local_followups"]:
            lines.append("- Covered local followups:")
            for covered in item["covered_local_followups"]:
                lines.append(f"  - {covered['gap']} -> `{covered['status']}` via `{covered['evidence']}`")
        if item["external_blockers"]:
            lines.append("- External blockers:")
            lines.extend([f"  - {value}" for value in item["external_blockers"]])
        if item["must_not_claim"]:
            lines.append("- Must not claim:")
            lines.extend([f"  - {value}" for value in item["must_not_claim"]])
        lines.append("")
    remaining_counts = (payload.get("remaining_backlog_summary") or {}).get("counts") or {}
    lines.extend(
        [
            "## Remaining Backlog",
            "",
            f"- counts: `{json.dumps(remaining_counts, sort_keys=True)}`",
            f"- external followups: `{', '.join(payload['external_followups'])}`",
            "",
            "## Contract",
            "",
            f"- schema_version: `{payload['status_export_contract']['schema_version']}`",
            "- read_only: `true`",
            "- ready local contract must not be described as live complete.",
            "",
            "## Must Not Claim",
        ]
    )
    lines.extend([f"- {value}" for value in payload["must_not_claim"]])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", default=str(DEFAULT_INPUT_JSON))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    audit = _load_audit(Path(args.input_json).expanduser().resolve())
    payload = build_status_export(audit)
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload, output_md)

    response = {
        "decision": payload["decision"],
        "schema_version": payload["schema_version"],
        "phase_count": len(payload["phase_status"]),
        "output_json": str(output_json),
        "output_md": str(output_md),
        "network_io": payload["network_io"],
        "destructive_actions": payload["destructive_actions"],
        "secrets_printed": payload["secrets_printed"],
        "live_gate_execution_allowed": payload["live_gate_execution_allowed"],
    }
    print(json.dumps(response, ensure_ascii=False, sort_keys=True) if args.json else f"status-export\t{response['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
