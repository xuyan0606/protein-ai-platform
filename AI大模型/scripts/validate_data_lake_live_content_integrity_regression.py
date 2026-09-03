#!/usr/bin/env python3
"""Prove stale data-lake size, SHA, and row metadata fail closed."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from data_lake_release_input_contract import RELEASE_INPUT_EXCLUDED_PATHS
except ModuleNotFoundError:
    from scripts.data_lake_release_input_contract import RELEASE_INPUT_EXCLUDED_PATHS


AI_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = AI_ROOT / "scripts" / "validate_data_lake_live_content_integrity.py"
OUTPUT = AI_ROOT / "reports" / "data_lake_live_content_integrity_regression_report.json"
STRICT_PATH = "datasets/fixture_rows.jsonl"
VOLATILE_PATHS = (
    "reports/safe_training_pipeline_run.json",
    "reports/data_lake_live_content_integrity_validation_report.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_row(root: Path, rel: str, rows: int | None = None) -> dict[str, Any]:
    path = root / rel
    return {
        "path": rel,
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "rows": rows,
    }


def build_fixture(root: Path) -> dict[str, Any]:
    strict = root / STRICT_PATH
    strict.parent.mkdir(parents=True, exist_ok=True)
    strict.write_text('{"id": 1}\n{"id": 2}\n', encoding="utf-8")
    for rel in sorted(RELEASE_INPUT_EXCLUDED_PATHS):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    artifacts = [artifact_row(root, STRICT_PATH, rows=2)] + [
        artifact_row(root, rel) for rel in sorted(RELEASE_INPUT_EXCLUDED_PATHS)
    ]
    return {
        "root": str(root.resolve()),
        "local_only": True,
        "source_artifact_rows": len(artifacts),
        "artifact_rows": len(artifacts),
        "unique_path_rows": len(artifacts),
        "deduplicated_input_rows": 0,
        "duplicate_input_path_rows": 0,
        "duplicate_input_paths": [],
        "artifacts": artifacts,
    }


def strict_row(manifest: dict[str, Any]) -> dict[str, Any]:
    return next(row for row in manifest["artifacts"] if row["path"] == STRICT_PATH)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="data-lake-live-integrity-") as temp_dir:
        temp_root = Path(temp_dir)
        baseline = build_fixture(temp_root)

        def stale_sha(manifest: dict[str, Any]) -> None:
            strict_row(manifest)["sha256"] = "0" * 64

        def stale_size(manifest: dict[str, Any]) -> None:
            row = strict_row(manifest)
            row["size_bytes"] = int(row["size_bytes"]) + 1

        def row_drift(manifest: dict[str, Any]) -> None:
            row = strict_row(manifest)
            row["rows"] = int(row["rows"]) + 1

        cases: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
            ("stale_sha256", stale_sha, "artifact_sha256_live_parity"),
            ("stale_size", stale_size, "artifact_size_live_parity"),
            ("row_count_drift", row_drift, "artifact_rows_live_parity"),
        ]
        results: list[dict[str, Any]] = []
        for index, (case_id, mutate, expected_check) in enumerate(cases, start=1):
            tampered = copy.deepcopy(baseline)
            mutate(tampered)
            manifest_path = temp_root / f"case-{index}.json"
            report_path = temp_root / f"case-{index}-validation.json"
            manifest_path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(VALIDATOR), "--root", str(temp_root), "--manifest", str(manifest_path), "--output", str(report_path)],
                cwd=AI_ROOT,
                text=True,
                capture_output=True,
                timeout=300,
            )
            validation = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
            checks = [str(item.get("check") or "") for item in validation.get("failures") or []]
            results.append({
                "case_id": case_id,
                "tamper_rejected": process.returncode != 0 and expected_check in checks,
                "expected_check": expected_check,
                "expected_check_observed": expected_check in checks,
                "failure_count": int(validation.get("failure_count") or 0),
            })

    passed = sum(row["tamper_rejected"] for row in results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": passed == len(results),
        "isolated_fixture": True,
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "real_inputs_mutated": False,
        "results": results,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Regression uses a temporary root and never reads or writes canonical data-lake artifacts.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "isolated_fixture": report["isolated_fixture"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(OUTPUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
