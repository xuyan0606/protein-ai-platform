#!/usr/bin/env python3
"""Build a concise Stage 25 source-acquisition shortlist."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "datasets" / "governance" / "stage25_source_drop_manifest_20260806.jsonl"
WEB_RECEIPT = AI_ROOT / "reports" / "stage25_literature_web_search_receipt_20260806.json"
INVENTORY = AI_ROOT / "reports" / "stage25_source_drop_inventory_20260806.json"
OUT_MD = AI_ROOT / "reports" / "stage25_source_acquisition_shortlist_20260806.md"
OUT_JSON = AI_ROOT / "reports" / "stage25_source_acquisition_shortlist_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise SystemExit(f"{path} contains a non-object row")
        rows.append(row)
    return rows


def main() -> int:
    manifest_rows = load_jsonl(MANIFEST)
    web = load_json(WEB_RECEIPT)
    inventory = load_json(INVENTORY)
    web_by_pmid = {str(row.get("pmid")): row for row in web.get("rows") or [] if isinstance(row, dict)}
    inventory_by_path = {
        str(row.get("expected_local_path")): row
        for row in inventory.get("expected_files") or []
        if isinstance(row, dict)
    }

    grouped: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        pmid = str(row.get("pmid"))
        entry = grouped.setdefault(pmid, {
            "pmid": pmid,
            "doi": row.get("doi"),
            "title": (web_by_pmid.get(pmid) or {}).get("title"),
            "primary_pages_found": (web_by_pmid.get(pmid) or {}).get("primary_pages_found") or [],
            "secondary_pages_found": (web_by_pmid.get(pmid) or {}).get("secondary_pages_found") or [],
            "evidence_level": (web_by_pmid.get(pmid) or {}).get("evidence_level"),
            "importer_decision": (web_by_pmid.get(pmid) or {}).get("importer_decision"),
            "required_files": [],
            "search_findings": (web_by_pmid.get(pmid) or {}).get("search_findings") or [],
        })
        expected_path = str(row.get("expected_local_path"))
        observed = inventory_by_path.get(expected_path) or {}
        entry["required_files"].append({
            "required_file_kind": row.get("required_file_kind"),
            "expected_local_path": expected_path,
            "exists": observed.get("exists") is True,
        })

    rows = [grouped[pmid] for pmid in sorted(grouped)]
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_source_acquisition_shortlist",
        "stage": 25,
        "paper_rows": len(rows),
        "required_file_rows": sum(len(row["required_files"]) for row in rows),
        "paper_ready_rows": 0,
        "ready_for_sqlite_apply_rows": 0,
        "rows": rows,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Operator shortlist only. Public links, directory targets, and file presence do not replace reviewed source locators, formal decisions, SQLite apply approval, benchmark intake, model claims, customer delivery, or release.",
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Stage 25 Source Acquisition Shortlist",
        "",
        "This shortlist is an operator aid. Public links, directory targets, and file presence do not replace reviewed source locators, formal decisions, SQLite apply approval, benchmark intake, model claims, customer delivery, or release.",
        "",
        f"- Paper rows: `{report['paper_rows']}`",
        f"- Required file rows: `{report['required_file_rows']}`",
        f"- Paper ready rows: `{report['paper_ready_rows']}`",
        f"- Ready for SQLite apply rows: `{report['ready_for_sqlite_apply_rows']}`",
        f"- Policy: {report['policy']}",
        "",
    ]
    for row in rows:
        lines.extend([
            f"## PMID {row['pmid']}",
            "",
            f"- DOI: `{row.get('doi')}`",
            f"- Title: {row.get('title')}",
            f"- Evidence level: `{row.get('evidence_level')}`",
            f"- Importer decision: `{row.get('importer_decision')}`",
            "- Primary pages:",
        ])
        for url in row.get("primary_pages_found") or []:
            lines.append(f"  - {url}")
        if row.get("secondary_pages_found"):
            lines.append("- Secondary leads:")
            for url in row.get("secondary_pages_found") or []:
                lines.append(f"  - {url}")
        lines.append("- Required local files:")
        for file_row in row["required_files"]:
            status = "present" if file_row["exists"] else "missing"
            lines.append(f"  - `{file_row['expected_local_path']}` ({file_row['required_file_kind']}; {status})")
        lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "output_json": str(OUT_JSON),
        "output_md": str(OUT_MD),
        "paper_rows": report["paper_rows"],
        "paper_ready_rows": report["paper_ready_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
