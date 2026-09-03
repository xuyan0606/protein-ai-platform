#!/usr/bin/env python3
"""Validate Stage 25 FoldX provision manifest without writing runtime receipts."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "datasets" / "governance" / "stage25_foldx_provision_manifest_20260806.jsonl"
OUTPUT = AI_ROOT / "reports" / "stage25_foldx_provision_manifest_validation_20260806.json"

EXPECTED_IDS = {
    "stage25_foldx_executable",
    "stage25_foldx_parameters",
    "stage25_foldx_input_structure_sha256",
    "stage25_foldx_mutation_list",
    "stage25_foldx_ddg_table",
    "stage25_foldx_runtime_log",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not MANIFEST.exists(), failures, "manifest_exists", "missing", str(MANIFEST))
    rows = load_jsonl(MANIFEST) if MANIFEST.exists() else []
    ids = {str(row.get("provision_id")) for row in rows}
    fail_if(ids != EXPECTED_IDS, failures, "provision_ids", sorted(ids), sorted(EXPECTED_IDS))

    status_rows = []
    ready_rows = 0
    for index, row in enumerate(rows, start=1):
        prefix = f"rows[{index}]"
        fail_if(row.get("stage") != 25, failures, f"{prefix}.stage", row.get("stage"), 25)
        fail_if(row.get("required") is not True, failures, f"{prefix}.required_true", row.get("required"), True)
        rel_path = str(row.get("expected_local_path") or "")
        fail_if(not (rel_path.startswith("cache/external/FoldX/") or rel_path.startswith("cache/advanced_features/ddg_physical_smoke/foldx/")), failures, f"{prefix}.path_scope", rel_path, "FoldX provision path")
        path = AI_ROOT / rel_path
        exists = path.exists()
        is_file = path.is_file()
        size = path.stat().st_size if exists and is_file else None
        digest = sha256_file(path) if exists and is_file else None
        executable_bit = bool(exists and is_file and path.stat().st_mode & 0o111)
        ready = bool(exists and is_file and size and size > 0)
        if row.get("artifact_kind") == "licensed_foldx_executable":
            ready = ready and executable_bit
        if row.get("expected_local_path", "").endswith("input_structure.sha256") and exists and is_file:
            content = path.read_text(encoding="utf-8", errors="ignore").strip().split()[0] if size else ""
            ready = ready and bool(SHA256_RE.match(content))
        ready_rows += 1 if ready else 0
        status_rows.append({
            "provision_id": row.get("provision_id"),
            "artifact_kind": row.get("artifact_kind"),
            "expected_local_path": rel_path,
            "exists": exists,
            "is_file": is_file,
            "size_bytes": size,
            "sha256": digest,
            "executable_bit": executable_bit,
            "ready_for_runtime_receipt": ready,
        })

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_foldx_provision_manifest_validation",
        "stage": 25,
        "manifest_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "provision_rows": len(rows),
        "ready_for_runtime_receipt_rows": ready_rows,
        "all_foldx_provision_ready": ready_rows == len(rows) and len(rows) > 0,
        "status_rows": status_rows,
        "formal_runtime_receipt_written": False,
        "approved_for_physical_ddg_runtime": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "manifest_valid": report["manifest_valid"], "failure_count": report["failure_count"], "provision_rows": report["provision_rows"], "ready_for_runtime_receipt_rows": report["ready_for_runtime_receipt_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["manifest_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
