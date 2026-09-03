#!/usr/bin/env python3
"""Build a freshness and source-binding audit for the P678 P0 status board."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STATUS = AI_ROOT / "datasets" / "governance" / "p678_p0_real_input_live_status_board.jsonl"
STATUS_REPORT = AI_ROOT / "reports" / "p678_p0_real_input_live_status_board_report.json"
STATUS_VALIDATION = AI_ROOT / "reports" / "p678_p0_real_input_live_status_board_validation_report.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p679_p0_real_input_status_freshness_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p679_p0_real_input_status_freshness_audit_report.json"
OUT_MD = AI_ROOT / "reports" / "p679_p0_real_input_status_freshness_audit.md"

FALSE_FLAGS = {
    "real_input_received": False,
    "formal_validator_passed": False,
    "completion_ready": False,
    "p0_unblocked": False,
    "training_import_allowed": False,
    "safe_for_training_import": False,
    "safe_for_model_claim": False,
    "customer_delivery_ready": False,
    "release_ready": False,
    "production_execution_allowed": False,
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def split_paths(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def source_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    target_paths = split_paths(str(row.get("formal_target_file") or ""))
    validator_paths = split_paths(str(row.get("validator_report") or ""))
    target_lines: dict[str, int] = {}
    target_missing: list[str] = []
    target_mtime_ns: dict[str, int] = {}
    for relative in target_paths:
        path = AI_ROOT / relative
        if not path.is_file():
            target_missing.append(relative)
            continue
        target_lines[relative] = sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
        target_mtime_ns[relative] = path.stat().st_mtime_ns

    validator_missing: list[str] = []
    validator_mtime_ns: dict[str, int] = {}
    for relative in validator_paths:
        path = AI_ROOT / relative
        if not path.is_file():
            validator_missing.append(relative)
            continue
        validator_mtime_ns[relative] = path.stat().st_mtime_ns

    observed_status = str(row.get("live_status") or "")
    stale = (
        bool(target_missing)
        or bool(validator_missing)
        or target_lines != {
            relative: count
            for relative, count in zip(target_lines, [row.get("target_nonempty_lines")])
        }
    ) if len(target_paths) == 1 else bool(target_missing or validator_missing)
    if len(target_paths) == 1 and target_paths[0] in target_lines:
        stale = stale or target_lines[target_paths[0]] != row.get("target_nonempty_lines")
    return {
        "target_paths": target_paths,
        "target_lines": target_lines,
        "target_missing": target_missing,
        "target_mtime_ns": target_mtime_ns,
        "validator_paths": validator_paths,
        "validator_missing": validator_missing,
        "validator_mtime_ns": validator_mtime_ns,
        "board_target_nonempty_lines": row.get("target_nonempty_lines"),
        "live_status": observed_status,
        "freshness_status": "stale_or_missing_source" if stale else "current_source_bound",
    }


def main() -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    rows = load_jsonl(STATUS)
    status_report = load_json(STATUS_REPORT)
    status_validation = load_json(STATUS_VALIDATION)
    audits: list[dict[str, Any]] = []
    stale_rows = 0
    source_missing_rows = 0
    for row in rows:
        snapshot = source_snapshot(row)
        stale = snapshot["freshness_status"] != "current_source_bound"
        stale_rows += int(stale)
        source_missing_rows += int(bool(snapshot["target_missing"] or snapshot["validator_missing"]))
        audits.append({
            "audit_id": f"p679::{row.get('lane')}",
            "created_at": created_at,
            "lane": row.get("lane"),
            "priority": row.get("priority"),
            "source_status_id": row.get("status_id"),
            "source_status_report": "reports/p678_p0_real_input_live_status_board_report.json",
            "source_status_validation": "reports/p678_p0_real_input_live_status_board_validation_report.json",
            "formal_target_file": row.get("formal_target_file"),
            "validator_report": row.get("validator_report"),
            "source_snapshot": snapshot,
            "freshness_audit_status": snapshot["freshness_status"],
            "stale_or_missing_source": stale,
            "completion_ready": False,
            "next_required_action": row.get("next_required_action"),
            "blocker": "P678 source-bound status remains blocked; freshness audit does not supply missing real input or decisions",
            "policy": "Freshness audit only. It cannot write formal inputs, reviewed decisions, training labels, model claims, release approval, or production authorization.",
            **FALSE_FLAGS,
        })

    audits.sort(key=lambda item: int(item.get("priority") or 0))
    summary = {
        "audit_id": "p679::summary",
        "created_at": created_at,
        "lane": "summary",
        "source_status_report": "reports/p678_p0_real_input_live_status_board_report.json",
        "source_status_validation": "reports/p678_p0_real_input_live_status_board_validation_report.json",
        "source_status_rows": len(rows),
        "source_status_validation_success": status_validation.get("success"),
        "source_status_report_rows": status_report.get("status_rows"),
        "freshness_audit_rows": len(audits),
        "stale_rows": stale_rows,
        "source_missing_rows": source_missing_rows,
        "current_source_bound_rows": len(audits) - stale_rows,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "freshness_audit_status": "blocked_source_bound_audit" if stale_rows == 0 else "blocked_stale_or_missing_source",
        "blocker": "P679 verifies source freshness only; real P0 input and formal decisions remain absent",
        "policy": "P679 is a fail-closed freshness audit and cannot promote downstream state.",
        **FALSE_FLAGS,
    }
    audits.append(summary)
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in audits), encoding="utf-8")

    report = {
        "created_at": created_at,
        "local_only": True,
        "source_status_rows": len(rows),
        "audit_rows": len(audits),
        "lane_audit_rows": len(rows),
        "freshness_audit_rows": len(rows),
        "stale_rows": stale_rows,
        "source_missing_rows": source_missing_rows,
        "current_source_bound_rows": len(rows) - stale_rows,
        "real_input_received": False,
        "formal_validator_passed": False,
        "completion_ready_rows": 0,
        "p0_unblocked_rows": 0,
        "source_status_validation_success": status_validation.get("success"),
        "freshness_audit_status": "blocked_source_bound_audit" if stale_rows == 0 else "blocked_stale_or_missing_source",
        "audit_jsonl": str(OUT_JSONL.relative_to(AI_ROOT)),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "p0_unblocked": False,
        "completion_ready": False,
        "policy": "P679 verifies that P678 remains current and source-bound; it does not create real input or approval.",
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# P679 P0 real-input status freshness audit",
        "",
        f"- audit_rows: `{len(audits)}`",
        f"- freshness_audit_rows: `{len(rows)}`",
        f"- current_source_bound_rows: `{len(rows) - stale_rows}`",
        f"- stale_rows: `{stale_rows}`",
        f"- source_missing_rows: `{source_missing_rows}`",
        "- completion_ready_rows: `0`",
        "- release_ready: `false`",
        "",
        "| Priority | Lane | Freshness status |",
        "|---:|---|---|",
    ]
    for item in audits[:-1]:
        lines.append(f"| {item['priority']} | {item['lane']} | `{item['freshness_audit_status']}` |")
    lines.extend([
        "",
        "This audit checks source freshness and binding only. It does not write formal inputs, decisions, labels, claims, release approval, or production authorization.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": len(audits),
        "freshness_audit_rows": len(rows),
        "current_source_bound_rows": len(rows) - stale_rows,
        "stale_rows": stale_rows,
        "completion_ready_rows": 0,
        "release_ready": False,
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
