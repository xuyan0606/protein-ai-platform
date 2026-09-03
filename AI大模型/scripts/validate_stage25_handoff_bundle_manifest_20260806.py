#!/usr/bin/env python3
"""Validate Stage 25 handoff bundle manifest."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "reports" / "stage25_handoff_bundle_manifest_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_handoff_bundle_manifest_validation_20260806.json"
OVERALL_REPORT = AI_ROOT / "reports" / "stage25_overall_fail_closed_index_20260806.json"
RUNNER_SCRIPT = AI_ROOT / "scripts" / "run_stage25_fail_closed_validation_20260806.py"
BUILDER_SCRIPT = AI_ROOT / "scripts" / "build_stage25_handoff_bundle_manifest_20260806.py"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_EXCLUDED_SELF_PATHS = [
    "reports/stage25_handoff_bundle_manifest_20260806.json",
    "reports/stage25_handoff_bundle_manifest_validation_20260806.json",
]
VOLATILE_RUN_REPORT = str((AI_ROOT / "reports" / "stage25_fail_closed_validation_run_report_20260806.json").resolve())
EXPECTED_ROW_KEYS = {"role", "root", "relative_path", "path", "exists", "size_bytes", "sha256", "freshness_check_mode"}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    failures: list[dict[str, Any]] = []
    fail_if(not MANIFEST.exists(), failures, "manifest_exists", "missing", str(MANIFEST))
    manifest = load_json(MANIFEST) if MANIFEST.exists() else {}
    rows = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    overall = load_json(OVERALL_REPORT) if OVERALL_REPORT.exists() else {}
    runner_module = load_module(RUNNER_SCRIPT, "stage25_runner_for_handoff_validation")
    builder_module = load_module(BUILDER_SCRIPT, "stage25_handoff_builder_for_validation")
    expected_overall_summary_count = len(overall.get("summaries") or {})
    expected_runner_command_count = len(runner_module.COMMANDS)
    expected_ai_required_rows = len(builder_module.AI_REQUIRED)
    expected_enzyme_required_rows = len(builder_module.ENZYME_REQUIRED)
    fail_if(manifest.get("mode") != "stage25_handoff_bundle_manifest", failures, "mode", manifest.get("mode"), "stage25_handoff_bundle_manifest")
    fail_if(manifest.get("missing_rows") != 0, failures, "missing_rows_zero", manifest.get("missing_rows"), 0)
    fail_if(manifest.get("overall_summary_count") != expected_overall_summary_count, failures, "overall_summary_count", manifest.get("overall_summary_count"), expected_overall_summary_count)
    fail_if(manifest.get("runner_command_count") != expected_runner_command_count, failures, "runner_command_count", manifest.get("runner_command_count"), expected_runner_command_count)
    fail_if(len(rows) <= 0, failures, "bundle_rows_positive", len(rows), ">0")
    fail_if(manifest.get("bundle_rows") != len(rows), failures, "bundle_rows_matches_files_len", manifest.get("bundle_rows"), len(rows))
    paths = [str(row.get("path")) for row in rows if isinstance(row, dict)]
    duplicate_paths = sorted({path for path in paths if paths.count(path) > 1})
    fail_if(manifest.get("unique_path_rows") != len(rows), failures, "unique_path_rows", manifest.get("unique_path_rows"), len(rows))
    fail_if(len(set(paths)) != len(rows), failures, "observed_unique_path_rows", len(set(paths)), len(rows))
    fail_if(manifest.get("duplicate_paths") != [], failures, "manifest_duplicate_paths_empty", manifest.get("duplicate_paths"), [])
    fail_if(duplicate_paths != [], failures, "observed_duplicate_paths_empty", duplicate_paths, [])
    expected_freshness_check_rows = sum(1 for row in rows if isinstance(row, dict) and row.get("freshness_check_mode") == "current_filesystem")
    expected_freshness_exempt_rows = sum(1 for row in rows if isinstance(row, dict) and row.get("freshness_check_mode") != "current_filesystem")
    fail_if(manifest.get("freshness_check_rows") != expected_freshness_check_rows, failures, "freshness_check_rows", manifest.get("freshness_check_rows"), expected_freshness_check_rows)
    fail_if(manifest.get("freshness_exempt_rows") != expected_freshness_exempt_rows, failures, "freshness_exempt_rows", manifest.get("freshness_exempt_rows"), expected_freshness_exempt_rows)
    fail_if(expected_freshness_exempt_rows != 1, failures, "single_freshness_exempt_row", expected_freshness_exempt_rows, 1)
    fail_if(manifest.get("self_referential_rows") != 0, failures, "self_referential_rows_zero", manifest.get("self_referential_rows"), 0)
    fail_if(manifest.get("excluded_self_referential_paths") != EXPECTED_EXCLUDED_SELF_PATHS, failures, "excluded_self_referential_paths", manifest.get("excluded_self_referential_paths"), EXPECTED_EXCLUDED_SELF_PATHS)
    roles = {str(row.get("role")) for row in rows if isinstance(row, dict)}
    role_counts = Counter(str(row.get("role")) for row in rows if isinstance(row, dict))
    expected_governance_rows = len(rows) - expected_ai_required_rows - expected_enzyme_required_rows
    expected_role_counts = Counter({"stage25_governance_artifact": expected_governance_rows, "ai_required": expected_ai_required_rows, "enzyme_required": expected_enzyme_required_rows})
    fail_if(expected_governance_rows <= 0, failures, "governance_rows_positive", expected_governance_rows, ">0")
    fail_if(role_counts != expected_role_counts, failures, "role_counts_exact", dict(role_counts), dict(expected_role_counts))
    for role in ("ai_required", "stage25_governance_artifact", "enzyme_required"):
        fail_if(role not in roles, failures, f"role_present.{role}", sorted(roles), f"contains {role}")
    freshness_verified_rows = 0
    freshness_exempt_rows = 0
    freshness_mismatch_rows = 0
    root_path_mismatch_rows = 0
    self_referential_rows = 0
    volatile_paths: list[str] = []
    for index, row in enumerate(rows, start=1):
        prefix = f"files[{index}]"
        if not isinstance(row, dict):
            fail_if(True, failures, f"{prefix}.object", row, "object")
            continue
        fail_if(set(row) != EXPECTED_ROW_KEYS, failures, f"{prefix}.keys_exact", sorted(row), sorted(EXPECTED_ROW_KEYS))
        root = Path(str(row.get("root") or ""))
        relative_path = str(row.get("relative_path") or "")
        expected_path = str((root / relative_path).resolve())
        observed_path = str(row.get("path") or "")
        if observed_path != expected_path:
            root_path_mismatch_rows += 1
        fail_if(observed_path != expected_path, failures, f"{prefix}.root_relative_path_resolves", observed_path, expected_path)
        if relative_path in EXPECTED_EXCLUDED_SELF_PATHS:
            self_referential_rows += 1
        fail_if(relative_path in EXPECTED_EXCLUDED_SELF_PATHS, failures, f"{prefix}.not_self_referential", relative_path, "not an excluded self-referential path")
        fail_if(row.get("exists") is not True, failures, f"{prefix}.exists_true", row.get("exists"), True)
        fail_if(not isinstance(row.get("size_bytes"), int) or row.get("size_bytes") <= 0, failures, f"{prefix}.size_positive", row.get("size_bytes"), ">0")
        fail_if(not SHA256_RE.match(str(row.get("sha256") or "")), failures, f"{prefix}.sha256", row.get("sha256"), "64 lowercase hex")
        path = Path(observed_path)
        mode = row.get("freshness_check_mode")
        if mode == "current_filesystem":
            exists = path.exists() and path.is_file()
            current_size = path.stat().st_size if exists else None
            current_sha256 = sha256_file(path) if exists else None
            row_matches = exists and row.get("size_bytes") == current_size and row.get("sha256") == current_sha256
            freshness_verified_rows += 1 if row_matches else 0
            freshness_mismatch_rows += 0 if row_matches else 1
            fail_if(not row_matches, failures, f"{prefix}.current_filesystem_parity", {"exists": exists, "size_bytes": current_size, "sha256": current_sha256}, {"exists": True, "size_bytes": row.get("size_bytes"), "sha256": row.get("sha256")})
        elif mode == "post_run_volatile_existence_only":
            freshness_exempt_rows += 1
            volatile_paths.append(observed_path)
            fail_if(observed_path != VOLATILE_RUN_REPORT, failures, f"{prefix}.volatile_path", observed_path, VOLATILE_RUN_REPORT)
            fail_if(not path.exists() or not path.is_file(), failures, f"{prefix}.volatile_exists", path.exists(), True)
        else:
            fail_if(True, failures, f"{prefix}.freshness_check_mode", mode, "current_filesystem or post_run_volatile_existence_only")
    fail_if(freshness_verified_rows != expected_freshness_check_rows, failures, "freshness_verified_rows", freshness_verified_rows, expected_freshness_check_rows)
    fail_if(freshness_exempt_rows != expected_freshness_exempt_rows, failures, "observed_freshness_exempt_rows", freshness_exempt_rows, expected_freshness_exempt_rows)
    fail_if(volatile_paths != [VOLATILE_RUN_REPORT], failures, "volatile_paths_exact", volatile_paths, [VOLATILE_RUN_REPORT])
    fail_if(self_referential_rows != 0, failures, "observed_self_referential_rows_zero", self_referential_rows, 0)
    policy = str(manifest.get("policy") or "")
    for term in ("Self-referential", "live size/SHA parity", "post-run volatile", "existence-only"):
        fail_if(term not in policy, failures, f"policy_contains.{term}", policy, f"contains {term}")
    for flag in ("external_sqlite_mutated", "apply_executed", "export_safe_released", "safe_for_model_claim", "release_ready"):
        fail_if(manifest.get(flag) is not False, failures, f"{flag}_false", manifest.get(flag), False)
    fail_if(manifest.get("formal_decision_rows_written") != 0, failures, "formal_decision_rows_written_zero", manifest.get("formal_decision_rows_written"), 0)
    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_handoff_bundle_manifest_validation",
        "stage": 25,
        "bundle_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "bundle_rows": len(rows),
        "unique_path_rows": len(set(paths)),
        "duplicate_paths": duplicate_paths,
        "freshness_verified_rows": freshness_verified_rows,
        "freshness_exempt_rows": freshness_exempt_rows,
        "freshness_mismatch_rows": freshness_mismatch_rows,
        "root_path_mismatch_rows": root_path_mismatch_rows,
        "self_referential_rows": self_referential_rows,
        "filesystem_integrity_valid": freshness_mismatch_rows == 0 and root_path_mismatch_rows == 0 and self_referential_rows == 0 and not duplicate_paths,
        "missing_rows": manifest.get("missing_rows"),
        "overall_summary_count": manifest.get("overall_summary_count"),
        "runner_command_count": manifest.get("runner_command_count"),
        "external_sqlite_mutated": False,
        "formal_decision_rows_written": 0,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "bundle_valid": report["bundle_valid"], "failure_count": report["failure_count"], "bundle_rows": report["bundle_rows"], "missing_rows": report["missing_rows"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["bundle_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
