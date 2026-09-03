#!/usr/bin/env python3
"""Validate the Stage 25 source-drop inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = AI_ROOT / "reports" / "stage25_source_drop_inventory_20260806.json"
MANIFEST = AI_ROOT / "datasets" / "governance" / "stage25_source_drop_manifest_20260806.jsonl"
ROOT = AI_ROOT / "datasets" / "source_drops" / "stage25"
OUT = AI_ROOT / "reports" / "stage25_source_drop_inventory_validation_20260806.json"
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not INVENTORY.exists(), failures, "inventory_exists", "missing", str(INVENTORY))
    inventory = load_json(INVENTORY) if INVENTORY.exists() else {}
    manifest_rows = load_jsonl(MANIFEST)
    expected_files = inventory.get("expected_files") if isinstance(inventory.get("expected_files"), list) else []
    directory_inventory = inventory.get("directory_inventory") if isinstance(inventory.get("directory_inventory"), list) else []
    expected_paths = [str(row.get("expected_local_path")) for row in manifest_rows]
    observed_paths = [str(row.get("expected_local_path")) for row in expected_files if isinstance(row, dict)]
    expected_source_ids = [str(row.get("source_id")) for row in manifest_rows]
    observed_source_ids = [str(row.get("source_id")) for row in expected_files if isinstance(row, dict)]
    expected_by_path = {str(row.get("expected_local_path")): row for row in manifest_rows}
    fail_if(inventory.get("mode") != "stage25_source_drop_inventory", failures, "mode", inventory.get("mode"), "stage25_source_drop_inventory")
    fail_if(inventory.get("source_drop_root") != "datasets/source_drops/stage25", failures, "source_drop_root", inventory.get("source_drop_root"), "datasets/source_drops/stage25")
    fail_if(inventory.get("manifest_source_rows") != 8, failures, "manifest_source_rows", inventory.get("manifest_source_rows"), 8)
    fail_if(inventory.get("inventory_generated_from_manifest") is not True, failures, "inventory_generated_from_manifest", inventory.get("inventory_generated_from_manifest"), True)
    fail_if(inventory.get("unique_expected_file_path_rows") != 8, failures, "unique_expected_file_path_rows", inventory.get("unique_expected_file_path_rows"), 8)
    fail_if(inventory.get("duplicate_expected_file_paths") != [], failures, "duplicate_expected_file_paths_empty", inventory.get("duplicate_expected_file_paths"), [])
    fail_if(inventory.get("directory_rows") != 4, failures, "directory_rows", inventory.get("directory_rows"), 4)
    fail_if(inventory.get("existing_directory_rows") != 4, failures, "existing_directory_rows", inventory.get("existing_directory_rows"), 4)
    fail_if(inventory.get("expected_file_rows") != 8, failures, "expected_file_rows", inventory.get("expected_file_rows"), 8)
    fail_if(len(expected_files) != 8, failures, "expected_files_len", len(expected_files), 8)
    fail_if(observed_paths != expected_paths, failures, "expected_file_paths_exact_order", observed_paths, expected_paths)
    fail_if(observed_source_ids != expected_source_ids, failures, "source_ids_exact_order", observed_source_ids, expected_source_ids)
    fail_if(len(set(observed_paths)) != 8, failures, "unique_observed_file_paths", len(set(observed_paths)), 8)
    fail_if(len(set(observed_source_ids)) != 8, failures, "unique_observed_source_ids", len(set(observed_source_ids)), 8)
    observed_present_rows = 0
    for index, row in enumerate(expected_files, start=1):
        if not isinstance(row, dict):
            fail_if(True, failures, f"expected_files[{index}].object", row, "object")
            continue
        path_key = str(row.get("expected_local_path"))
        manifest_row = expected_by_path.get(path_key) or {}
        path = AI_ROOT / path_key
        exists = path.exists() and path.is_file()
        size = path.stat().st_size if exists else None
        digest = sha256_file(path) if exists else None
        observed_present_rows += 1 if exists else 0
        for field in ("source_id", "pmid", "doi", "required_file_kind", "expected_local_path"):
            fail_if(row.get(field) != manifest_row.get(field), failures, f"expected_files[{index}].{field}_matches_manifest", row.get(field), manifest_row.get(field))
        fail_if(row.get("exists") is not exists, failures, f"expected_files[{index}].exists_matches_filesystem", row.get("exists"), exists)
        fail_if(row.get("size_bytes") != size, failures, f"expected_files[{index}].size_matches_filesystem", row.get("size_bytes"), size)
        fail_if(row.get("sha256") != digest, failures, f"expected_files[{index}].sha256_matches_filesystem", row.get("sha256"), digest)
    fail_if(inventory.get("present_expected_file_rows") != observed_present_rows, failures, "present_expected_file_rows_recomputed", inventory.get("present_expected_file_rows"), observed_present_rows)
    fail_if(inventory.get("missing_expected_file_rows") != 8 - observed_present_rows, failures, "missing_expected_file_rows_recomputed", inventory.get("missing_expected_file_rows"), 8 - observed_present_rows)
    observed_directory_pmids = [str(row.get("pmid")) for row in directory_inventory if isinstance(row, dict)]
    fail_if(len(directory_inventory) != 4, failures, "directory_inventory_len", len(directory_inventory), 4)
    fail_if(observed_directory_pmids != EXPECTED_PMIDS, failures, "directory_pmids_exact_order", observed_directory_pmids, EXPECTED_PMIDS)
    for index, row in enumerate(directory_inventory, start=1):
        if not isinstance(row, dict):
            fail_if(True, failures, f"directory_inventory[{index}].object", row, "object")
            continue
        pmid = EXPECTED_PMIDS[index - 1] if index <= len(EXPECTED_PMIDS) else ""
        path = ROOT / pmid
        exists = path.exists() and path.is_dir()
        file_count = sum(1 for child in path.iterdir() if child.is_file()) if exists else 0
        fail_if(row.get("path") != f"datasets/source_drops/stage25/{pmid}", failures, f"directory_inventory[{index}].path", row.get("path"), f"datasets/source_drops/stage25/{pmid}")
        fail_if(row.get("exists") is not exists, failures, f"directory_inventory[{index}].exists_matches_filesystem", row.get("exists"), exists)
        fail_if(row.get("file_count") != file_count, failures, f"directory_inventory[{index}].file_count_matches_filesystem", row.get("file_count"), file_count)
    fail_if(inventory.get("ready_for_extraction_rows") != 0, failures, "ready_for_extraction_rows_zero", inventory.get("ready_for_extraction_rows"), 0)
    fail_if(inventory.get("ready_for_sqlite_apply_rows") != 0, failures, "ready_for_sqlite_apply_rows_zero", inventory.get("ready_for_sqlite_apply_rows"), 0)
    policy = str(inventory.get("policy") or "")
    for term in ("Directory inventory only", "File presence and hashes", "source locators", "SQLite apply"):
        fail_if(term not in policy, failures, f"policy_contains.{term}", policy, f"contains {term}")
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(inventory.get(flag) is not False, failures, f"{flag}_false", inventory.get(flag), False)
    fail_if(inventory.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", inventory.get("formal_decision_rows_written"), 0)

    validation = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_source_drop_inventory_validation",
        "stage": 25,
        "inventory_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "directory_rows": inventory.get("directory_rows"),
        "directory_inventory_exact": not any(failure["check"].startswith("directory_") for failure in failures),
        "existing_directory_rows": inventory.get("existing_directory_rows"),
        "expected_file_rows": inventory.get("expected_file_rows"),
        "unique_expected_file_path_rows": len(set(observed_paths)),
        "unique_source_id_rows": len(set(observed_source_ids)),
        "inventory_matches_manifest": observed_paths == expected_paths and observed_source_ids == expected_source_ids,
        "filesystem_state_matches": not any("matches_filesystem" in failure["check"] for failure in failures),
        "present_expected_file_rows": inventory.get("present_expected_file_rows"),
        "missing_expected_file_rows": inventory.get("missing_expected_file_rows"),
        "ready_for_extraction_rows": 0,
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
        "inventory_valid": validation["inventory_valid"],
        "failure_count": validation["failure_count"],
        "present_expected_file_rows": validation["present_expected_file_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if validation["inventory_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
