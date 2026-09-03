#!/usr/bin/env python3
"""Build per-proposal closeout checklist for Stage 25 execute blockers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = AI_ROOT.parents[1] / "酶数据库"
DETAIL = AI_ROOT / "reports" / "stage25_execute_blocker_detail_20260806.json"
REVIEWER_PACKAGE = ENZYME_DB_ROOT / "stage25_reviewer_package_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_execute_closeout_checklist_20260806.json"

CHECK_ACTIONS = {
    "human_review_status": "Set review_status to approved_for_family_importer only after source locators and payload drafts are reviewed.",
    "approved_for_family_importer": "Record explicit family-importer approval for this proposal.",
    "source_locators": "Provide source table/figure/supplement locators for every imported identity and measurement claim.",
    "payload_draft": "Fill reviewed variant and/or measurement payload drafts with values, units, conditions and evidence levels.",
    "paper_pdf": "Place legally obtained full text or supplementary files in the approved local intake path.",
    "intake_approval": "Mark intake approved only after file hash, source locator and reviewer package checks pass.",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def main() -> int:
    detail = load_json(DETAIL)
    package = load_json(REVIEWER_PACKAGE)
    package_items = {
        str(row.get("proposal_id")): row
        for row in package.get("items", [])
        if isinstance(row, dict)
    }
    rows = []
    checklist_items = []
    for blocker in detail.get("proposal_blocker_rows", []):
        proposal_id = str(blocker.get("proposal_id"))
        package_row = package_items.get(proposal_id, {})
        checks = sorted(str(check) for check in blocker.get("checks", []))
        rows.append({
            "proposal_id": proposal_id,
            "family": package_row.get("family"),
            "doi": package_row.get("doi"),
            "pmid": package_row.get("pmid"),
            "stable_proposal_id": package_row.get("stable_proposal_id"),
            "current_evidence_level": package_row.get("current_evidence_level"),
            "source_access_gap": package_row.get("source_access_gap"),
            "required_before_apply": package_row.get("required_before_apply") or [],
            "next_action": package_row.get("next_action"),
            "blocker_count": len(checks),
            "checks": checks,
            "closeout_ready": False,
        })
        for check in checks:
            checklist_items.append({
                "proposal_id": proposal_id,
                "check": check,
                "closeout_action": CHECK_ACTIONS.get(check, "Close this blocker with reviewed evidence."),
                "closed": False,
            })

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_execute_closeout_checklist",
        "stage": 25,
        "proposal_rows": len(rows),
        "checklist_item_rows": len(checklist_items),
        "closed_item_rows": sum(1 for row in checklist_items if row["closed"]),
        "closeout_ready_rows": sum(1 for row in rows if row["closeout_ready"]),
        "proposals": rows,
        "checklist_items": checklist_items,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "proposal_rows": report["proposal_rows"], "checklist_item_rows": report["checklist_item_rows"], "closeout_ready_rows": report["closeout_ready_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
