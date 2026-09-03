#!/usr/bin/env python3
"""Build an explicit queue for human/machine numbering decision conflicts.

This script is audit-only. It detects rows where the human notes say the label
should be rejected, but the machine-readable decision still keeps the row as
unresolved weak evidence. It does not modify the reviewed decision file.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
DEEP_AUDIT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_all_stability_records.jsonl"
WORKLIST = AI_ROOT / "datasets" / "curation" / "numbering_review_worklist.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "numbering_decision_semantic_conflict_queue.jsonl"
REPORT = AI_ROOT / "reports" / "numbering_decision_semantic_conflict_report.json"
MARKDOWN = AI_ROOT / "reports" / "numbering_decision_semantic_conflict_report.md"

REJECTION_NOTE_TOKENS = (
    "拒绝",
    "错误",
    "不能支持",
    "错配",
    "不匹配",
    "reject",
    "wrong",
    "cannot support",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def note_rejects_label(notes: str) -> bool:
    lowered = notes.lower()
    return any(token.lower() in lowered for token in REJECTION_NOTE_TOKENS)


def build_conflict_rows(
    decisions: list[dict[str, Any]],
    deep_audit: list[dict[str, Any]],
    active_record_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    audit_by_id = {str(row.get("record_id")): row for row in deep_audit if row.get("record_id")}
    rows: list[dict[str, Any]] = []
    for index, decision in enumerate(decisions, start=1):
        record_id = str(decision.get("record_id") or "")
        if active_record_ids is not None and record_id not in active_record_ids:
            continue
        notes = str(decision.get("notes") or "")
        machine_decision = decision.get("decision")
        conflict = machine_decision == "keep_unresolved_weak" and note_rejects_label(notes)
        if not conflict:
            continue
        audit = audit_by_id.get(record_id, {})
        rows.append({
            "conflict_id": f"numbering_semantic_conflict:{index:04d}",
            "record_id": record_id,
            "uniprot_id": decision.get("canonical_uniprot_id") or audit.get("uniprot_id"),
            "mutation": audit.get("mutation") or decision.get("canonical_mutant"),
            "current_decision": machine_decision,
            "human_note_interpretation": "reject_label",
            "conflict_type": "human_notes_reject_label_but_machine_decision_keeps_weak",
            "severity": "high",
            "notes": notes,
            "source_refs": decision.get("source_refs") or [],
            "curator": decision.get("curator"),
            "curated_at": decision.get("curated_at"),
            "deep_audit_recommended_decision": audit.get("audit_recommended_decision"),
            "deep_audit_flags": audit.get("audit_flags") or [],
            "allowed_resolution_actions": [
                "convert_to_reject_label_after_human_confirmation",
                "confirm_keep_unresolved_weak_with_clear_notes",
            ],
            "recommended_resolution": "convert_to_reject_label_after_human_confirmation",
            "safe_for_model_claim": False,
            "policy": "Do not auto-rewrite human decisions; resolve only by explicit reviewed decision update.",
            "existing_decision": decision,
        })
    return rows


def write_markdown(report: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# Numbering Decision Semantic Conflicts",
        "",
        "This queue lists reviewed rows whose notes and machine decision disagree.",
        "",
        "## Result",
        "",
        f"- Decision rows checked: {report['decision_rows_checked']}",
        f"- Conflict rows: {report['semantic_conflict_rows']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Required Human Resolution",
        "",
        "1. If the notes are correct, change the decision to `reject_label`.",
        "2. If the row should remain weak, rewrite the notes so they no longer say the label is rejected.",
        "3. Run numbering validation, apply numbering curation, then the safe training pipeline.",
        "",
        "## Rows",
        "",
    ]
    for row in rows:
        lines.append(
            f"- `{row['record_id']}`: current `{row['current_decision']}`, notes imply `{row['human_note_interpretation']}`"
        )
    if not rows:
        lines.append("- No semantic conflicts detected.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build numbering semantic conflict queue")
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--deep-audit", type=Path, default=DEEP_AUDIT)
    parser.add_argument("--worklist", type=Path, default=WORKLIST)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    args = parser.parse_args()

    decisions = load_jsonl(args.decisions)
    active_record_ids = {
        str(row.get("record_id") or "")
        for row in load_jsonl(args.worklist)
        if row.get("record_id")
    }
    rows = build_conflict_rows(decisions, load_jsonl(args.deep_audit), active_record_ids or None)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "decision_rows_checked": len(decisions),
        "active_worklist_rows": len(active_record_ids),
        "semantic_conflict_rows": len(rows),
        "open_conflict_rows": len(rows),
        "conflict_type_counts": {
            "human_notes_reject_label_but_machine_decision_keeps_weak": len(rows),
        } if rows else {},
        "conflict_queue_output": str(args.output),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Audit-only queue. Explicit human action is required before modifying numbering_curation_decisions.jsonl.",
    }
    write_jsonl(args.output, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, rows, args.markdown)
    print(json.dumps({
        "decision_rows_checked": report["decision_rows_checked"],
        "semantic_conflict_rows": report["semantic_conflict_rows"],
        "output": str(args.output),
        "report": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
