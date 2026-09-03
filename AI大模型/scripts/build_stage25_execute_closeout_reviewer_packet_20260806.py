#!/usr/bin/env python3
"""Build human-readable reviewer packet for Stage 25 execute closeout items."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "reports" / "stage25_execute_closeout_checklist_20260806.json"
INTAKE = AI_ROOT / "datasets" / "governance" / "stage25_execute_closeout_reviewer_intake_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_execute_closeout_reviewer_packet_20260806.md"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise SystemExit(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def bullet_list(values: list[Any]) -> list[str]:
    return [f"- {value}" for value in values]


def main() -> int:
    checklist = load_json(CHECKLIST)
    intake_rows = load_jsonl(INTAKE)
    proposals = checklist.get("proposals") or []
    rows_by_proposal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in intake_rows:
        rows_by_proposal[str(row.get("proposal_id"))].append(row)

    lines = [
        "# Stage 25 Execute Closeout Reviewer Packet",
        "",
        "- Date: 2026-08-06",
        "- Mode: execute requested but blocked; reviewer closeout packet only",
        "- Scope: four new lipase/xylanase paper proposals with 24 open apply blockers",
        "- Governance: needs_more_info for every row; no SQLite write, no apply execution, no export-safe release, no model claim",
        "- allow_apply=false",
        "- external_sqlite_mutated=false",
        "- export_safe_released=false",
        "- release_ready=false",
        "- safe_for_model_claim=false",
        "- formal_decision_rows_written=0",
        "- Do not write SQLite",
        "- Required gate: fulltext/source-table evidence and reviewer approval must close before importer apply",
        "",
        "## Summary",
        "",
        f"- Proposal rows: {len(proposals)}",
        f"- Checklist rows: {len(intake_rows)}",
        f"- Closed rows: {sum(1 for row in intake_rows if row.get('closed') is True)}",
        f"- Approved rows: {sum(1 for row in intake_rows if row.get('review_decision') == 'approved')}",
        "",
    ]

    for proposal in proposals:
        proposal_id = str(proposal["proposal_id"])
        proposal_rows = sorted(rows_by_proposal.get(proposal_id, []), key=lambda row: str(row.get("check")))
        lines.extend([
            f"## {proposal_id}",
            "",
            f"- Family: {proposal.get('family')}",
            f"- DOI: {proposal.get('doi')}",
            f"- PMID: {proposal.get('pmid')}",
            f"- Stable proposal id: {proposal.get('stable_proposal_id')}",
            f"- Evidence level: {proposal.get('current_evidence_level')}",
            f"- Source gap: {proposal.get('source_access_gap')}",
            f"- Next action: {proposal.get('next_action')}",
            f"- Closeout ready: {str(proposal.get('closeout_ready')).lower()}",
            "",
            "Required before apply:",
            "",
            *bullet_list(list(proposal.get("required_before_apply") or [])),
            "",
            "Open checklist items:",
            "",
        ])
        for row in proposal_rows:
            lines.extend([
                f"- `{row.get('check')}`: {row.get('closeout_action')} "
                f"[decision={row.get('review_decision')}, closed={str(row.get('closed')).lower()}, "
                f"approved_for_family_importer={str(row.get('approved_for_family_importer')).lower()}, "
                f"export_safe={str(row.get('export_safe')).lower()}]",
            ])
        lines.append("")

    OUTPUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "proposal_rows": len(proposals),
        "checklist_rows": len(intake_rows),
        "closed_rows": sum(1 for row in intake_rows if row.get("closed") is True),
        "approved_rows": sum(1 for row in intake_rows if row.get("review_decision") == "approved"),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
