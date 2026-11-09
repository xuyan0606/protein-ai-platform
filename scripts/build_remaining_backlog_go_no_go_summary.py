#!/usr/bin/env python3
"""Build a read-only go/no-go summary for the remaining backlog handoff."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_VALIDATION = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-external-input-validation-report.json"
DEFAULT_EXECUTION_PLAN = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-gate-execution-plan.json"
DEFAULT_DISPATCH_CHECKLIST = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-operator-dispatch-checklist.json"
DEFAULT_DISPATCH_VALIDATION = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-operator-dispatch-checklist-validation-report.json"
DEFAULT_OPERATOR_MANIFEST = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-operator-packet-manifest.json"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-go-no-go-summary.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-go-no-go-summary.md"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_exists": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_exists": True, "_invalid_json": str(exc)}
    if not isinstance(payload, dict):
        return {"_exists": True, "_invalid_shape": "expected object"}
    payload["_exists"] = True
    return payload


def _source(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        source_path = str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        source_path = str(path)
    return {
        "path": source_path,
        "exists": bool(payload.get("_exists")),
        "invalid_json": payload.get("_invalid_json"),
        "invalid_shape": payload.get("_invalid_shape"),
    }


def _manifest_freshness_check(manifest_path: Path) -> dict[str, Any]:
    script = PROJECT_ROOT / "scripts" / "build_remaining_backlog_operator_packet_manifest.py"
    if not script.exists():
        return {
            "status": "stale-or-missing",
            "reason": "manifest_check_script_missing",
            "current": False,
            "returncode": None,
        }
    proc = subprocess.run(
        [sys.executable, str(script), "--output", str(manifest_path), "--check", "--json"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {
        "status": str(payload.get("status") or "stale-or-missing"),
        "reason": payload.get("reason"),
        "current": proc.returncode == 0 and payload.get("status") == "current",
        "returncode": proc.returncode,
        "stale_sections": payload.get("stale_sections") or [],
    }


def _check(
    name: str,
    status: str,
    ready: bool,
    blocking_detail: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "ready": ready,
        "blocking_detail": blocking_detail,
    }


def _priority_summary(dispatch_checklist: dict[str, Any]) -> dict[str, Any]:
    items = dispatch_checklist.get("items") if isinstance(dispatch_checklist.get("items"), list) else []
    summary: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        priority = str(item.get("priority") or "unassigned")
        row = summary.setdefault(
            priority,
            {
                "item_count": 0,
                "missing_input_rows": 0,
                "ready_to_run_rows": 0,
                "armed_rows": 0,
                "blocked_rows": 0,
                "items": [],
            },
        )
        row["item_count"] += 1
        row["items"].append(str(item.get("name") or "unnamed"))
        if item.get("missing_fields"):
            row["missing_input_rows"] += 1
            row["blocked_rows"] += 1
        if item.get("ready_to_run_after_inputs") is True:
            row["ready_to_run_rows"] += 1
        if item.get("armed_in_execution_plan") is True:
            row["armed_rows"] += 1
    return {priority: summary[priority] for priority in sorted(summary)}


def build_summary(
    input_validation_path: Path,
    execution_plan_path: Path,
    dispatch_checklist_path: Path,
    dispatch_validation_path: Path,
    operator_manifest_path: Path,
) -> dict[str, Any]:
    input_validation = _load_json(input_validation_path)
    execution_plan = _load_json(execution_plan_path)
    dispatch_checklist = _load_json(dispatch_checklist_path)
    dispatch_validation = _load_json(dispatch_validation_path)
    operator_manifest = _load_json(operator_manifest_path)
    manifest_summary = operator_manifest.get("summary") if isinstance(operator_manifest.get("summary"), dict) else {}
    manifest_status = str(manifest_summary.get("status") or "missing")
    manifest_freshness = _manifest_freshness_check(operator_manifest_path)

    item_count = int(input_validation.get("item_count") or execution_plan.get("item_count") or 0)
    missing_input_rows = int(input_validation.get("missing_input_rows") or 0)
    ready_to_run_rows = int(input_validation.get("ready_to_run_rows") or 0)
    armed_rows = int(execution_plan.get("armed_rows") or dispatch_validation.get("armed_rows") or 0)
    blocked_rows = int(execution_plan.get("blocked_rows") or dispatch_validation.get("blocked_rows") or 0)

    inputs_ready = (
        input_validation.get("_exists") is True
        and not input_validation.get("_invalid_json")
        and input_validation.get("all_inputs_present") is True
        and missing_input_rows == 0
        and ready_to_run_rows == item_count
        and item_count > 0
    )
    execution_plan_ready = (
        execution_plan.get("_exists") is True
        and not execution_plan.get("_invalid_json")
        and execution_plan.get("all_inputs_present") is True
        and blocked_rows == 0
        and armed_rows == item_count
        and item_count > 0
    )
    dispatch_ready = (
        dispatch_validation.get("_exists") is True
        and not dispatch_validation.get("_invalid_json")
        and dispatch_validation.get("success") is True
        and dispatch_validation.get("source_bound_current") is True
    )
    manifest_ready = manifest_status == "ready-for-operator-review" and manifest_freshness["current"] is True
    ready_for_live_gate_execution = inputs_ready and execution_plan_ready and dispatch_ready and manifest_ready

    checks = [
        _check(
            "external_input_validation",
            "complete" if inputs_ready else "waiting_for_external_inputs",
            inputs_ready,
            {"missing_input_rows": missing_input_rows, "ready_to_run_rows": ready_to_run_rows},
        ),
        _check(
            "gate_execution_plan",
            "armed" if execution_plan_ready else "not_armed",
            execution_plan_ready,
            {"blocked_rows": blocked_rows, "armed_rows": armed_rows},
        ),
        _check(
            "operator_dispatch_validation",
            "valid" if dispatch_ready else "invalid_or_stale",
            dispatch_ready,
            {
                "success": dispatch_validation.get("success"),
                "source_bound_current": dispatch_validation.get("source_bound_current"),
                "failure_count": dispatch_validation.get("failure_count"),
            },
        ),
        _check(
            "operator_packet_manifest",
            manifest_status if manifest_ready else f"{manifest_status}/not-current",
            manifest_ready,
            {
                "manifest_status": manifest_status,
                "freshness": manifest_freshness,
                "missing_files": manifest_summary.get("missing_files") or [],
            },
        ),
    ]
    blocking_items = [check["name"] for check in checks if not check["ready"]]
    decision = (
        "ready_for_explicit_operator_live_gate_review"
        if ready_for_live_gate_execution
        else "defer_waiting_for_external_inputs"
    )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_remaining_backlog_go_no_go_summary",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "live_gate_execution_allowed": False,
        "decision": decision,
        "ready_for_live_gate_execution": ready_for_live_gate_execution,
        "blocking_items": blocking_items,
        "item_count": item_count,
        "ready_to_run_rows": ready_to_run_rows,
        "missing_input_rows": missing_input_rows,
        "armed_rows": armed_rows,
        "blocked_rows": blocked_rows,
        "priority_summary": _priority_summary(dispatch_checklist),
        "checks": checks,
        "operator_packet_manifest": {
            "status": manifest_status,
            "current": manifest_freshness["current"],
            "freshness_status": manifest_freshness["status"],
        },
        "sources": {
            "external_input_validation": _source(input_validation_path, input_validation),
            "gate_execution_plan": _source(execution_plan_path, execution_plan),
            "operator_dispatch_checklist": _source(dispatch_checklist_path, dispatch_checklist),
            "operator_dispatch_validation": _source(dispatch_validation_path, dispatch_validation),
            "operator_packet_manifest": _source(operator_manifest_path, operator_manifest),
        },
        "next_action": (
            "collect and validate external inputs by operator lane; rerun the summary; do not execute live gates"
            if not ready_for_live_gate_execution
            else "operator review may explicitly choose which armed live gates to execute; this summary still does not execute them"
        ),
    }


def write_markdown(summary: dict[str, Any], output: Path) -> None:
    rows = [
        "| Check | Status | Ready | Blocking detail |",
        "|---|---|---|---|",
    ]
    for check in summary["checks"]:
        detail = json.dumps(check.get("blocking_detail") or {}, ensure_ascii=False, sort_keys=True)
        rows.append(f"| `{check['name']}` | `{check['status']}` | `{check['ready']}` | `{detail}` |")

    priority_rows = [
        "| Priority | Items | Missing Inputs | Ready To Run | Armed | Blocked |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for priority, row in summary.get("priority_summary", {}).items():
        priority_rows.append(
            f"| `{priority}` | `{', '.join(row['items'])}` | `{row['missing_input_rows']}` | "
            f"`{row['ready_to_run_rows']}` | `{row['armed_rows']}` | `{row['blocked_rows']}` |"
        )

    text = "\n".join([
        "# Remaining Backlog Go/No-Go Summary",
        "",
        f"- decision: `{summary['decision']}`",
        f"- ready_for_live_gate_execution: `{summary['ready_for_live_gate_execution']}`",
        f"- live_gate_execution_allowed: `{summary['live_gate_execution_allowed']}`",
        f"- item_count: `{summary['item_count']}`",
        f"- missing_input_rows: `{summary['missing_input_rows']}`",
        f"- ready_to_run_rows: `{summary['ready_to_run_rows']}`",
        f"- armed_rows: `{summary['armed_rows']}`",
        f"- blocked_rows: `{summary['blocked_rows']}`",
        f"- blocking_items: `{', '.join(summary['blocking_items']) if summary['blocking_items'] else 'none'}`",
        "",
        "## Priority Summary",
        "",
        *priority_rows,
        "",
        "## Gate Checks",
        "",
        *rows,
        "",
        f"Next action: {summary['next_action']}",
        "",
    ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-validation", default=str(DEFAULT_INPUT_VALIDATION))
    parser.add_argument("--execution-plan", default=str(DEFAULT_EXECUTION_PLAN))
    parser.add_argument("--dispatch-checklist", default=str(DEFAULT_DISPATCH_CHECKLIST))
    parser.add_argument("--dispatch-validation", default=str(DEFAULT_DISPATCH_VALIDATION))
    parser.add_argument("--operator-manifest", default=str(DEFAULT_OPERATOR_MANIFEST))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--require-live-ready", action="store_true", help="Exit non-zero unless all live gates are ready for explicit operator review")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    summary = build_summary(
        Path(args.input_validation).expanduser().resolve(),
        Path(args.execution_plan).expanduser().resolve(),
        Path(args.dispatch_checklist).expanduser().resolve(),
        Path(args.dispatch_validation).expanduser().resolve(),
        Path(args.operator_manifest).expanduser().resolve(),
    )
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(summary, output_md)

    response = {
        "decision": summary["decision"],
        "ready_for_live_gate_execution": summary["ready_for_live_gate_execution"],
        "blocking_items": summary["blocking_items"],
        "item_count": summary["item_count"],
        "missing_input_rows": summary["missing_input_rows"],
        "ready_to_run_rows": summary["ready_to_run_rows"],
        "armed_rows": summary["armed_rows"],
        "blocked_rows": summary["blocked_rows"],
        "priority_summary": summary["priority_summary"],
        "operator_packet_manifest": summary["operator_packet_manifest"],
        "output_json": str(output_json),
        "output_md": str(output_md),
        "network_io": summary["network_io"],
        "destructive_actions": summary["destructive_actions"],
        "secrets_printed": summary["secrets_printed"],
    }
    if args.json:
        print(json.dumps(response, ensure_ascii=False, sort_keys=True))
    else:
        print(f"summary\t{response['decision']}\tblocking={len(response['blocking_items'])}")
        print(f"output_json\t{response['output_json']}")
        print(f"output_md\t{response['output_md']}")
    if args.require_live_ready and not summary["ready_for_live_gate_execution"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
