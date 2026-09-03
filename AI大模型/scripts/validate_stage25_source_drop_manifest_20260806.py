#!/usr/bin/env python3
"""Validate Stage 25 local source drop manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = AI_ROOT.parents[1] / "酶数据库"
FULLTEXT_INTAKE = ENZYME_DB_ROOT / "incoming" / "fulltext"
MANIFEST = AI_ROOT / "datasets" / "governance" / "stage25_source_drop_manifest_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_source_drop_manifest_validation_20260806.json"


EXPECTED_SOURCES = [
    ("stage25_source_39743673_si", "stage25_unblock_source_39743673_20260806", "xylanase", "39743673", "10.1021/acs.jafc.4c10256", "acs_supporting_information", "datasets/source_drops/stage25/39743673/jf4c10256_si_001.doc"),
    ("stage25_source_39743673_fulltext", "stage25_unblock_source_39743673_20260806", "xylanase", "39743673", "10.1021/acs.jafc.4c10256", "article_fulltext_or_vor_pdf", "datasets/source_drops/stage25/39743673/10.1021_acs.jafc.4c10256_fulltext.pdf"),
    ("stage25_source_42134585_fulltext", "stage25_unblock_source_42134585_20260806", "xylanase", "42134585", "10.1016/j.biortech.2026.134883", "article_fulltext_or_vor_pdf", "datasets/source_drops/stage25/42134585/10.1016_j.biortech.2026.134883_fulltext.pdf"),
    ("stage25_source_42134585_source_table", "stage25_unblock_source_42134585_20260806", "xylanase", "42134585", "10.1016/j.biortech.2026.134883", "source_table_or_supplement", "datasets/source_drops/stage25/42134585/source_table_or_supplement_for_9K-XynB2"),
    ("stage25_source_42235695_fulltext", "stage25_unblock_source_42235695_20260806", "lipase", "42235695", "10.1016/j.biortech.2026.135069", "article_fulltext_or_vor_pdf", "datasets/source_drops/stage25/42235695/10.1016_j.biortech.2026.135069_fulltext.pdf"),
    ("stage25_source_42235695_source_table", "stage25_unblock_source_42235695_20260806", "lipase", "42235695", "10.1016/j.biortech.2026.135069", "source_table_or_supplement", "datasets/source_drops/stage25/42235695/CM5_variant_and_process_source_locator"),
    ("stage25_source_42248057_fulltext", "stage25_unblock_source_42248057_20260806", "lipase", "42248057", "10.1016/j.enzmictec.2026.110921", "article_fulltext_or_vor_pdf", "datasets/source_drops/stage25/42248057/10.1016_j.enzmictec.2026.110921_fulltext.pdf"),
    ("stage25_source_42248057_source_table", "stage25_unblock_source_42248057_20260806", "lipase", "42248057", "10.1016/j.enzmictec.2026.110921", "source_table_or_supplement", "datasets/source_drops/stage25/42248057/XyEst_rXyEst_benchmark_source_locator"),
]
EXPECTED_SOURCE_IDS = [row[0] for row in EXPECTED_SOURCES]
EXPECTED_ROW_KEYS = {"source_id", "packet_id", "stage", "family", "pmid", "doi", "required_file_kind", "expected_local_path", "required", "status", "ready_for_extraction"}

INTAKE_PREFIX_BY_PMID = {
    "39743673": "XYN_CAND_20260805_001",
    "42134585": "XYN_CAND_20260805_002",
    "42235695": "LIP_CAND_20260805_003",
    "42248057": "LIP_CAND_20260805_004",
}

FULLTEXT_SUFFIXES = {".pdf"}
SOURCE_TABLE_SUFFIXES = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".tsv", ".txt"}
SOURCE_TABLE_TOKENS = ("supplement", "supplementary", "supporting", "_si", "-si", "source", "table", "figure")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_kind_matches(path: Path, required_file_kind: str) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if required_file_kind == "article_fulltext_or_vor_pdf":
        return suffix in FULLTEXT_SUFFIXES
    if required_file_kind in {"acs_supporting_information", "source_table_or_supplement"}:
        return suffix in SOURCE_TABLE_SUFFIXES and any(token in name for token in SOURCE_TABLE_TOKENS)
    return suffix in SOURCE_TABLE_SUFFIXES


def resolve_source_path(row: dict[str, Any]) -> tuple[Path, str]:
    rel_path = str(row.get("expected_local_path") or "")
    canonical = AI_ROOT / rel_path
    if canonical.exists():
        return canonical, rel_path

    prefix = INTAKE_PREFIX_BY_PMID.get(str(row.get("pmid") or ""))
    required_kind = str(row.get("required_file_kind") or "")
    if prefix and FULLTEXT_INTAKE.exists():
        matches = sorted(
            path for path in FULLTEXT_INTAKE.iterdir()
            if path.is_file() and path.name.startswith(prefix) and source_kind_matches(path, required_kind)
        )
        if matches:
            return matches[0], str(matches[0])
    return canonical, rel_path


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not MANIFEST.exists(), failures, "manifest_exists", "missing", str(MANIFEST))
    rows = load_jsonl(MANIFEST) if MANIFEST.exists() else []
    source_ids = [str(row.get("source_id")) for row in rows]
    expected_paths = [row[6] for row in EXPECTED_SOURCES]
    observed_paths = [str(row.get("expected_local_path")) for row in rows]
    expected_rows = [
        {
            "source_id": source_id,
            "packet_id": packet_id,
            "stage": 25,
            "family": family,
            "pmid": pmid,
            "doi": doi,
            "required_file_kind": required_kind,
            "expected_local_path": expected_path,
            "required": True,
            "status": "missing",
            "ready_for_extraction": False,
        }
        for source_id, packet_id, family, pmid, doi, required_kind, expected_path in EXPECTED_SOURCES
    ]
    fail_if(len(rows) != 8, failures, "source_rows", len(rows), 8)
    fail_if(source_ids != EXPECTED_SOURCE_IDS, failures, "source_ids_exact_order", source_ids, EXPECTED_SOURCE_IDS)
    fail_if(len(set(source_ids)) != 8, failures, "unique_source_id_rows", len(set(source_ids)), 8)
    fail_if(observed_paths != expected_paths, failures, "expected_paths_exact_order", observed_paths, expected_paths)
    fail_if(len(set(observed_paths)) != 8, failures, "unique_expected_path_rows", len(set(observed_paths)), 8)
    fail_if(rows != expected_rows, failures, "rows_exact_contract", rows, expected_rows)

    status_rows = []
    ready_rows = 0
    present_rows = 0
    missing_rows = 0
    resolved_existing_paths: list[str] = []
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(set(row) != EXPECTED_ROW_KEYS, failures, f"{prefix}.keys_exact", sorted(row), sorted(EXPECTED_ROW_KEYS))
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(row.get("required") is not True, failures, f"{prefix}.required_true", row.get("required"), True)
        rel_path = str(row.get("expected_local_path") or "")
        fail_if(not rel_path.startswith("datasets/source_drops/stage25/"), failures, f"{prefix}.expected_path_scope", rel_path, "datasets/source_drops/stage25/*")
        path, resolved_path = resolve_source_path(row)
        exists = path.exists()
        if exists and path.is_file():
            resolved_existing_paths.append(str(path.resolve()))
        size = path.stat().st_size if exists and path.is_file() else None
        digest = sha256_file(path) if exists and path.is_file() else None
        ready = False
        present_rows += 1 if exists else 0
        missing_rows += 0 if exists else 1
        ready_rows += 1 if ready else 0
        status_rows.append({
            "source_id": row.get("source_id"),
            "packet_id": row.get("packet_id"),
            "pmid": row.get("pmid"),
            "doi": row.get("doi"),
            "required_file_kind": row.get("required_file_kind"),
            "expected_local_path": rel_path,
            "resolved_local_path": resolved_path,
            "resolved_path_identity": str(path.resolve()) if exists else None,
            "intake_prefix": INTAKE_PREFIX_BY_PMID.get(str(row.get("pmid") or "")),
            "exists": exists,
            "size_bytes": size,
            "sha256": digest,
            "ready_for_extraction": ready,
        })

    duplicate_resolved_paths = sorted({path for path in resolved_existing_paths if resolved_existing_paths.count(path) > 1})
    fail_if(duplicate_resolved_paths != [], failures, "duplicate_resolved_source_paths_empty", duplicate_resolved_paths, [])
    fail_if(present_rows + missing_rows != len(rows), failures, "presence_count_matches_source_rows", present_rows + missing_rows, len(rows))

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_source_drop_manifest_validation",
        "stage": 25,
        "manifest_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "source_rows": len(rows),
        "unique_source_id_rows": len(set(source_ids)),
        "unique_expected_path_rows": len(set(observed_paths)),
        "exact_source_contract": rows == expected_rows,
        "duplicate_resolved_source_paths": duplicate_resolved_paths,
        "present_source_files": present_rows,
        "missing_source_files": missing_rows,
        "ready_for_extraction_rows": 0,
        "all_sources_ready_for_extraction": False,
        "source_status": status_rows,
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "ready_for_family_importer": False,
        "export_safe_released": False,
        "release_ready": False,
        "safe_for_model_claim": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "manifest_valid": report["manifest_valid"], "failure_count": report["failure_count"], "source_rows": report["source_rows"], "ready_for_extraction_rows": report["ready_for_extraction_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["manifest_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
