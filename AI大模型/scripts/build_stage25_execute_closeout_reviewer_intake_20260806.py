#!/usr/bin/env python3
"""Build reviewer intake template for Stage 25 execute closeout items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "reports" / "stage25_execute_closeout_checklist_20260806.json"
OUTPUT = AI_ROOT / "datasets" / "governance" / "stage25_execute_closeout_reviewer_intake_20260806.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def main() -> int:
    checklist = load_json(CHECKLIST)
    proposals = {row["proposal_id"]: row for row in checklist.get("proposals", [])}
    rows = []
    for item in checklist.get("checklist_items", []):
        proposal = proposals[str(item["proposal_id"])]
        rows.append({
            "intake_id": f"{item['proposal_id']}::{item['check']}",
            "stage": 25,
            "proposal_id": item["proposal_id"],
            "family": proposal.get("family"),
            "doi": proposal.get("doi"),
            "pmid": proposal.get("pmid"),
            "check": item["check"],
            "required_before_apply": proposal.get("required_before_apply") or [],
            "closeout_action": item["closeout_action"],
            "review_decision": "needs_more_info",
            "reviewer": "",
            "reviewed_at": "",
            "evidence_artifacts": [],
            "source_locators": [],
            "payload_draft_refs": [],
            "approval_basis": "",
            "closed": False,
            "approved_for_family_importer": False,
            "export_safe": False,
            "notes": "",
        })
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "intake_rows": len(rows), "closed_rows": sum(1 for row in rows if row["closed"])}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
