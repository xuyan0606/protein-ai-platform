#!/usr/bin/env python3
"""Validate data-lake artifact metadata against the live filesystem."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from data_lake_release_input_contract import (
        RELEASE_INPUT_EXCLUDED_PATHS,
        build_release_input_contract,
    )
except ModuleNotFoundError:
    from scripts.data_lake_release_input_contract import (
        RELEASE_INPUT_EXCLUDED_PATHS,
        build_release_input_contract,
    )


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "reports" / "data_lake_manifest.json"
OUTPUT = AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json"
VOLATILE_EXISTENCE_ONLY_PATHS = {
    "reports/safe_training_pipeline_run.json",
    "reports/data_lake_live_content_integrity_validation_report.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_nonempty_lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and "\\" not in value and str(path) == value


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate live data-lake artifact content integrity")
    parser.add_argument("--root", type=Path, default=AI_ROOT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest.exists() else {}
    artifacts = [row for row in manifest.get("artifacts") or [] if isinstance(row, dict)]
    failures: list[dict[str, Any]] = []
    missing_paths: list[str] = []
    unsafe_paths: list[str] = []
    size_mismatch_paths: list[str] = []
    sha_mismatch_paths: list[str] = []
    row_mismatch_paths: list[str] = []
    strict_verified_rows = 0
    exempt_verified_rows = 0
    exempt_verified_paths: list[str] = []

    root = args.root.resolve()
    if manifest.get("root") != str(root):
        failures.append({"check": "manifest_root_exact", "observed": manifest.get("root"), "expected": str(root)})
    if manifest.get("artifact_rows") != len(artifacts) or manifest.get("unique_path_rows") != len(artifacts):
        failures.append({"check": "manifest_artifact_count_parity", "observed": {"artifact_rows": manifest.get("artifact_rows"), "unique_path_rows": manifest.get("unique_path_rows"), "actual": len(artifacts)}, "expected": "all equal"})

    seen: set[str] = set()
    for row in artifacts:
        rel = str(row.get("path") or "")
        if rel in seen:
            failures.append({"check": "artifact_path_unique", "path": rel})
            continue
        seen.add(rel)
        if not safe_relative_path(rel):
            unsafe_paths.append(rel)
            continue
        path = root / rel
        if not path.is_file():
            missing_paths.append(rel)
            continue
        if rel in VOLATILE_EXISTENCE_ONLY_PATHS:
            exempt_verified_rows += 1
            exempt_verified_paths.append(rel)
            continue
        mismatch = False
        if row.get("exists") is not True:
            failures.append({"check": "artifact_manifest_exists_true", "path": rel, "observed": row.get("exists"), "expected": True})
            mismatch = True
        if row.get("size_bytes") != path.stat().st_size:
            size_mismatch_paths.append(rel)
            mismatch = True
        if row.get("sha256") != sha256(path):
            sha_mismatch_paths.append(rel)
            mismatch = True
        if row.get("rows") is not None and row.get("rows") != count_nonempty_lines(path):
            row_mismatch_paths.append(rel)
            mismatch = True
        if not mismatch:
            strict_verified_rows += 1

    for check, paths in (
        ("artifact_path_safe_relative", unsafe_paths),
        ("artifact_live_file_exists", missing_paths),
        ("artifact_size_live_parity", size_mismatch_paths),
        ("artifact_sha256_live_parity", sha_mismatch_paths),
        ("artifact_rows_live_parity", row_mismatch_paths),
    ):
        if paths:
            failures.append({"check": check, "count": len(paths), "paths": sorted(paths)})

    observed_exempt_paths = set(exempt_verified_paths)
    if observed_exempt_paths != VOLATILE_EXISTENCE_ONLY_PATHS:
        failures.append({
            "check": "volatile_exemption_paths_exact",
            "observed": sorted(observed_exempt_paths),
            "expected": sorted(VOLATILE_EXISTENCE_ONLY_PATHS),
        })
    if strict_verified_rows + exempt_verified_rows != len(artifacts):
        failures.append({"check": "artifact_verification_decomposition", "observed": {"strict": strict_verified_rows, "exempt": exempt_verified_rows}, "expected": len(artifacts)})
    release_contract = build_release_input_contract(manifest)
    release_excluded_paths = release_contract["excluded_paths"]
    if set(release_excluded_paths) != RELEASE_INPUT_EXCLUDED_PATHS:
        failures.append({
            "check": "release_input_exclusion_paths_exact",
            "observed": release_excluded_paths,
            "expected": sorted(RELEASE_INPUT_EXCLUDED_PATHS),
        })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "validated_root": str(root),
        "validated_manifest_path": str(args.manifest.resolve()),
        "validated_manifest_sha256": sha256(args.manifest) if args.manifest.is_file() else None,
        "release_input_contract_version": release_contract["version"],
        "release_input_contract_sha256": release_contract["sha256"],
        "release_input_artifact_rows": release_contract["artifact_rows"],
        "release_input_excluded_paths": release_excluded_paths,
        "success": not failures,
        "artifact_rows": len(artifacts),
        "strict_verified_rows": strict_verified_rows,
        "volatile_existence_only_rows": exempt_verified_rows,
        "missing_rows": len(missing_paths),
        "unsafe_path_rows": len(unsafe_paths),
        "size_mismatch_rows": len(size_mismatch_paths),
        "sha256_mismatch_rows": len(sha_mismatch_paths),
        "row_mismatch_rows": len(row_mismatch_paths),
        "failure_count": len(failures),
        "failures": failures,
        "configured_volatile_existence_only_paths": sorted(VOLATILE_EXISTENCE_ONLY_PATHS),
        "volatile_existence_only_paths": sorted(observed_exempt_paths),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "All non-volatile data-lake artifacts require live size, SHA-256, and applicable row-count parity. Explicit post-run outputs are existence-only and do not grant release readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "artifact_rows": report["artifact_rows"],
        "strict_verified_rows": report["strict_verified_rows"],
        "volatile_existence_only_rows": report["volatile_existence_only_rows"],
        "failure_count": report["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
