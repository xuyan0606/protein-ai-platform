#!/usr/bin/env python3
"""Validate the Stage 25 source-acquisition shortlist."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SHORTLIST = AI_ROOT / "reports" / "stage25_source_acquisition_shortlist_20260806.json"
SHORTLIST_MD = AI_ROOT / "reports" / "stage25_source_acquisition_shortlist_20260806.md"
MANIFEST = AI_ROOT / "datasets" / "governance" / "stage25_source_drop_manifest_20260806.jsonl"
INVENTORY = AI_ROOT / "reports" / "stage25_source_drop_inventory_20260806.json"
WEB_RECEIPT = AI_ROOT / "reports" / "stage25_literature_web_search_receipt_20260806.json"
OUT = AI_ROOT / "reports" / "stage25_source_acquisition_shortlist_validation_20260806.json"
EXPECTED_PMIDS = ["39743673", "42134585", "42235695", "42248057"]


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
            raise ValueError(f"{path} contains a non-object row")
        rows.append(row)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not SHORTLIST.exists(), failures, "shortlist_json_exists", "missing", str(SHORTLIST))
    fail_if(not SHORTLIST_MD.exists(), failures, "shortlist_md_exists", "missing", str(SHORTLIST_MD))
    data = load_json(SHORTLIST) if SHORTLIST.exists() else {}
    md_text = SHORTLIST_MD.read_text(encoding="utf-8") if SHORTLIST_MD.exists() else ""
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    manifest_rows = load_jsonl(MANIFEST)
    inventory = load_json(INVENTORY)
    web = load_json(WEB_RECEIPT)
    inventory_by_path = {
        str(row.get("expected_local_path")): row
        for row in inventory.get("expected_files") or []
        if isinstance(row, dict)
    }
    web_by_pmid = {
        str(row.get("pmid")): row
        for row in web.get("rows") or []
        if isinstance(row, dict)
    }
    expected_by_pmid: dict[str, list[dict[str, Any]]] = {}
    for row in manifest_rows:
        expected_by_pmid.setdefault(str(row.get("pmid")), []).append(row)
    observed_pmids = [str(row.get("pmid")) for row in rows if isinstance(row, dict)]
    flattened_files = [
        (str(row.get("pmid")), file_row)
        for row in rows if isinstance(row, dict)
        for file_row in row.get("required_files") or [] if isinstance(file_row, dict)
    ]
    observed_paths = [str(file_row.get("expected_local_path")) for _, file_row in flattened_files]
    expected_paths = [str(row.get("expected_local_path")) for row in manifest_rows]
    fail_if(data.get("mode") != "stage25_source_acquisition_shortlist", failures, "mode", data.get("mode"), "stage25_source_acquisition_shortlist")
    fail_if(data.get("paper_rows") != 4, failures, "paper_rows", data.get("paper_rows"), 4)
    fail_if(data.get("required_file_rows") != 8, failures, "required_file_rows", data.get("required_file_rows"), 8)
    fail_if(len(rows) != 4, failures, "rows_len", len(rows), 4)
    fail_if(data.get("paper_rows") != len(rows), failures, "paper_rows_matches_rows_len", data.get("paper_rows"), len(rows))
    fail_if(observed_pmids != EXPECTED_PMIDS, failures, "pmids_exact_order", observed_pmids, EXPECTED_PMIDS)
    fail_if(len(set(observed_pmids)) != 4, failures, "unique_pmid_rows", len(set(observed_pmids)), 4)
    fail_if(sorted(expected_by_pmid) != EXPECTED_PMIDS, failures, "manifest_pmids_exact", sorted(expected_by_pmid), EXPECTED_PMIDS)
    fail_if(len(flattened_files) != 8, failures, "flattened_required_file_rows", len(flattened_files), 8)
    fail_if(data.get("required_file_rows") != len(flattened_files), failures, "required_file_rows_matches_flattened", data.get("required_file_rows"), len(flattened_files))
    fail_if(sorted(observed_paths) != sorted(expected_paths), failures, "required_file_paths_exact", sorted(observed_paths), sorted(expected_paths))
    fail_if(len(set(observed_paths)) != 8, failures, "unique_required_file_path_rows", len(set(observed_paths)), 8)
    fail_if(data.get("paper_ready_rows") != 0, failures, "paper_ready_rows_zero", data.get("paper_ready_rows"), 0)
    fail_if(data.get("ready_for_sqlite_apply_rows") != 0, failures, "ready_for_sqlite_apply_rows_zero", data.get("ready_for_sqlite_apply_rows"), 0)
    policy = str(data.get("policy") or "")
    for term in ("Operator shortlist only", "file presence", "reviewed source locators", "SQLite apply approval"):
        fail_if(term not in policy, failures, f"policy_contains.{term}", policy, f"contains {term}")
        fail_if(term not in md_text, failures, f"markdown_policy_contains.{term}", md_text[:500], f"contains {term}")
    for term in ("Paper ready rows: `0`", "Ready for SQLite apply rows: `0`"):
        fail_if(term not in md_text, failures, f"markdown_contains.{term}", md_text[:500], f"contains {term}")
        fail_if(md_text.count(term) != 1, failures, f"markdown_once.{term}", md_text.count(term), 1)
    fail_if(md_text.count("## PMID ") != 4, failures, "markdown_pmid_heading_rows", md_text.count("## PMID "), 4)
    for row in rows:
        prefix = f"row[{row.get('pmid')}]"
        pmid = str(row.get("pmid"))
        expected_manifest_rows = expected_by_pmid.get(pmid) or []
        expected_web = web_by_pmid.get(pmid) or {}
        expected_dois = {str(item.get("doi")) for item in expected_manifest_rows}
        expected_file_specs = sorted(
            (str(item.get("required_file_kind")), str(item.get("expected_local_path")))
            for item in expected_manifest_rows
        )
        observed_file_specs = sorted(
            (str(item.get("required_file_kind")), str(item.get("expected_local_path")))
            for item in row.get("required_files") or [] if isinstance(item, dict)
        )
        fail_if(len(expected_dois) != 1 or str(row.get("doi")) not in expected_dois, failures, f"{prefix}.doi_matches_manifest", row.get("doi"), sorted(expected_dois))
        fail_if(row.get("title") != expected_web.get("title"), failures, f"{prefix}.title_matches_web_receipt", row.get("title"), expected_web.get("title"))
        fail_if(row.get("primary_pages_found") != expected_web.get("primary_pages_found"), failures, f"{prefix}.primary_pages_match_web_receipt", row.get("primary_pages_found"), expected_web.get("primary_pages_found"))
        expected_secondary_pages = expected_web.get("secondary_pages_found") or []
        fail_if(row.get("secondary_pages_found") != expected_secondary_pages, failures, f"{prefix}.secondary_pages_match_web_receipt", row.get("secondary_pages_found"), expected_secondary_pages)
        fail_if(row.get("evidence_level") != expected_web.get("evidence_level"), failures, f"{prefix}.evidence_level_matches_web_receipt", row.get("evidence_level"), expected_web.get("evidence_level"))
        fail_if(row.get("importer_decision") != expected_web.get("importer_decision"), failures, f"{prefix}.importer_decision_matches_web_receipt", row.get("importer_decision"), expected_web.get("importer_decision"))
        fail_if(not row.get("primary_pages_found"), failures, f"{prefix}.primary_pages_found", row.get("primary_pages_found"), "non-empty")
        fail_if(len(row.get("required_files") or []) < 1, failures, f"{prefix}.required_files", row.get("required_files"), "non-empty")
        fail_if(observed_file_specs != expected_file_specs, failures, f"{prefix}.required_files_match_manifest", observed_file_specs, expected_file_specs)
        fail_if(md_text.count(f"## PMID {pmid}") != 1, failures, f"{prefix}.markdown_heading_once", md_text.count(f"## PMID {pmid}"), 1)
        fail_if(md_text.count(f"- DOI: `{row.get('doi')}`") != 1, failures, f"{prefix}.markdown_doi_once", md_text.count(f"- DOI: `{row.get('doi')}`"), 1)
        for file_row in row.get("required_files") or []:
            if not isinstance(file_row, dict):
                continue
            path = str(file_row.get("expected_local_path"))
            expected_exists = (inventory_by_path.get(path) or {}).get("exists") is True
            fail_if(file_row.get("exists") is not expected_exists, failures, f"{prefix}.inventory_exists.{path}", file_row.get("exists"), expected_exists)
            fail_if(md_text.count(f"`{path}`") != 1, failures, f"{prefix}.markdown_path_once.{path}", md_text.count(f"`{path}`"), 1)
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(data.get(flag) is not False, failures, f"{flag}_false", data.get(flag), False)
    fail_if(data.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", data.get("formal_decision_rows_written"), 0)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_source_acquisition_shortlist_validation",
        "stage": 25,
        "shortlist_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "paper_rows": data.get("paper_rows"),
        "unique_pmid_rows": len(set(observed_pmids)),
        "required_file_rows": data.get("required_file_rows"),
        "unique_required_file_path_rows": len(set(observed_paths)),
        "markdown_pmid_heading_rows": md_text.count("## PMID "),
        "markdown_exact_coverage": not any(
            failure["check"].startswith("markdown_") or ".markdown_" in failure["check"]
            for failure in failures
        ),
        "paper_ready_rows": data.get("paper_ready_rows"),
        "ready_for_sqlite_apply_rows": 0,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "formal_decision_rows_written": 0,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUT.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "shortlist_valid": validation["shortlist_valid"],
        "failure_count": validation["failure_count"],
        "paper_ready_rows": validation["paper_ready_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if validation["shortlist_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
