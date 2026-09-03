#!/usr/bin/env python3
"""Prove local release only accepts canonical live-integrity evidence."""

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
    from data_lake_release_input_contract import (
        CONTRACT_VERSION,
        RELEASE_INPUT_EXCLUDED_PATHS,
        build_release_input_contract,
    )
except ModuleNotFoundError:
    from scripts.data_lake_release_input_contract import (
        CONTRACT_VERSION,
        RELEASE_INPUT_EXCLUDED_PATHS,
        build_release_input_contract,
    )


AI_ROOT = Path(__file__).resolve().parents[1]
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
LIVE_INTEGRITY = AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json"
VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_manifest_fail_closed_consistency.py"
OUTPUT = AI_ROOT / "reports" / "local_release_live_integrity_binding_regression_report.json"
VOLATILE_PATHS = {
    "reports/safe_training_pipeline_run.json",
    "reports/data_lake_live_content_integrity_validation_report.json",
}
def prepare_control_fixture(
    release: dict[str, Any],
    data_lake: dict[str, Any],
    live: dict[str, Any],
    data_lake_path: Path,
) -> None:
    artifact_rows = len(data_lake.get("artifacts") or [])
    manifest_sha256 = hashlib.sha256(data_lake_path.read_bytes()).hexdigest()
    contract = build_release_input_contract(data_lake)
    live.update({
        "success": True,
        "failure_count": 0,
        "failures": [],
        "validated_root": str(AI_ROOT),
        "validated_manifest_path": str(DATA_LAKE.resolve()),
        "validated_manifest_sha256": manifest_sha256,
        "release_input_contract_version": contract["version"],
        "release_input_contract_sha256": contract["sha256"],
        "release_input_artifact_rows": contract["artifact_rows"],
        "release_input_excluded_paths": contract["excluded_paths"],
        "artifact_rows": artifact_rows,
        "strict_verified_rows": artifact_rows - len(VOLATILE_PATHS),
        "volatile_existence_only_rows": len(VOLATILE_PATHS),
        "missing_rows": 0,
        "unsafe_path_rows": 0,
        "size_mismatch_rows": 0,
        "sha256_mismatch_rows": 0,
        "row_mismatch_rows": 0,
        "configured_volatile_existence_only_paths": sorted(VOLATILE_PATHS),
        "volatile_existence_only_paths": sorted(VOLATILE_PATHS),
    })
    summary = release.setdefault("readiness_summary", {})
    summary.update({
        "data_lake_live_content_integrity_success": True,
        "data_lake_live_content_integrity_failure_count": 0,
        "data_lake_live_content_integrity_validated_root": live["validated_root"],
        "data_lake_live_content_integrity_validated_manifest_path": live["validated_manifest_path"],
        "data_lake_live_content_integrity_release_input_contract_version": contract["version"],
        "data_lake_live_content_integrity_release_input_contract_sha256": contract["sha256"],
        "data_lake_live_content_integrity_release_input_artifact_rows": contract["artifact_rows"],
        "data_lake_live_content_integrity_release_input_excluded_paths": contract["excluded_paths"],
        "data_lake_live_content_integrity_artifact_rows": artifact_rows,
        "data_lake_live_content_integrity_strict_verified_rows": live["strict_verified_rows"],
        "data_lake_live_content_integrity_volatile_rows": len(VOLATILE_PATHS),
        "local_release_live_integrity_binding_regression_success": True,
        "local_release_live_integrity_binding_regression_failed_rows": 0,
    })


def main() -> int:
    baseline_release = json.loads(RELEASE.read_text(encoding="utf-8"))
    baseline_data_lake = json.loads(DATA_LAKE.read_text(encoding="utf-8"))
    baseline_live = json.loads(LIVE_INTEGRITY.read_text(encoding="utf-8"))

    def temporary_root_report(release: dict[str, Any], live: dict[str, Any]) -> None:
        live["validated_root"] = "/tmp/isolated-live-integrity-root"

    def release_summary_root_drift(release: dict[str, Any], live: dict[str, Any]) -> None:
        release.setdefault("readiness_summary", {})["data_lake_live_content_integrity_validated_root"] = "/tmp/forged-summary-root"

    def artifact_count_drift(release: dict[str, Any], live: dict[str, Any]) -> None:
        live["artifact_rows"] = int(live["artifact_rows"]) + 1
        live["strict_verified_rows"] = int(live["strict_verified_rows"]) + 1

    def stale_manifest_sha(release: dict[str, Any], live: dict[str, Any]) -> None:
        live["validated_manifest_sha256"] = "0" * 64

    def stale_release_input_contract_sha(release: dict[str, Any], live: dict[str, Any]) -> None:
        live["release_input_contract_sha256"] = "0" * 64

    def release_input_contract_version_drift(release: dict[str, Any], live: dict[str, Any]) -> None:
        live["release_input_contract_version"] = f"{CONTRACT_VERSION}-drift"

    def release_summary_contract_sha_drift(release: dict[str, Any], live: dict[str, Any]) -> None:
        release.setdefault("readiness_summary", {})["data_lake_live_content_integrity_release_input_contract_sha256"] = "f" * 64

    def noncanonical_manifest_path(release: dict[str, Any], live: dict[str, Any]) -> None:
        live["validated_manifest_path"] = "/tmp/isolated-data-lake-manifest.json"

    cases: list[tuple[str, Callable[[dict[str, Any], dict[str, Any]], None], str]] = [
        ("temporary_root_success_report", temporary_root_report, "canonical_live_integrity_root"),
        ("release_summary_root_drift", release_summary_root_drift, "live_integrity_summary_matches_report"),
        ("live_artifact_count_drift", artifact_count_drift, "canonical_live_integrity_artifact_rows"),
        ("stale_live_manifest_sha", stale_manifest_sha, "canonical_live_integrity_manifest_sha256"),
        ("stale_release_input_contract_sha", stale_release_input_contract_sha, "canonical_live_integrity_release_input_contract_sha256"),
        ("release_input_contract_version_drift", release_input_contract_version_drift, "canonical_live_integrity_release_input_contract_version"),
        ("release_summary_contract_sha_drift", release_summary_contract_sha_drift, "live_integrity_summary_matches_report"),
        ("noncanonical_live_manifest_path", noncanonical_manifest_path, "canonical_live_integrity_manifest_path"),
    ]
    results: list[dict[str, Any]] = []
    control_valid = False

    with tempfile.TemporaryDirectory(prefix="release-live-integrity-binding-") as temp_dir:
        temp_root = Path(temp_dir)
        data_lake_path = temp_root / "data-lake.json"
        data_lake_path.write_text(json.dumps(baseline_data_lake, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        prepare_control_fixture(baseline_release, baseline_data_lake, baseline_live, data_lake_path)
        baseline_contract = build_release_input_contract(baseline_data_lake)
        included_drift = copy.deepcopy(baseline_data_lake)
        included_row = next(
            row for row in included_drift.get("artifacts") or []
            if row.get("path") not in RELEASE_INPUT_EXCLUDED_PATHS
        )
        included_row["sha256"] = "0" * 64 if included_row.get("sha256") != "0" * 64 else "1" * 64
        included_contract_changed = build_release_input_contract(included_drift)["sha256"] != baseline_contract["sha256"]
        results.append({
            "case_id": "included_metadata_changes_contract",
            "tamper_rejected": included_contract_changed,
            "expected_check": "included_metadata_changes_contract",
            "expected_check_observed": included_contract_changed,
            "failure_count": 0 if included_contract_changed else 1,
        })
        excluded_drift = copy.deepcopy(baseline_data_lake)
        for row in excluded_drift.get("artifacts") or []:
            if row.get("path") in RELEASE_INPUT_EXCLUDED_PATHS:
                row["sha256"] = "f" * 64
                row["size_bytes"] = int(row.get("size_bytes") or 0) + 1
        excluded_contract_stable = build_release_input_contract(excluded_drift)["sha256"] == baseline_contract["sha256"]
        results.append({
            "case_id": "excluded_metadata_keeps_contract_stable",
            "tamper_rejected": excluded_contract_stable,
            "expected_check": "excluded_metadata_keeps_contract_stable",
            "expected_check_observed": excluded_contract_stable,
            "failure_count": 0 if excluded_contract_stable else 1,
        })
        control_release_path = temp_root / "control-release.json"
        control_live_path = temp_root / "control-live.json"
        control_report_path = temp_root / "control-validation.json"
        control_release_path.write_text(json.dumps(baseline_release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        control_live_path.write_text(json.dumps(baseline_live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        control = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--release",
                str(control_release_path),
                "--data-lake",
                str(data_lake_path),
                "--live-integrity",
                str(control_live_path),
                "--output",
                str(control_report_path),
            ],
            cwd=AI_ROOT,
            text=True,
            capture_output=True,
            timeout=300,
        )
        control_validation = json.loads(control_report_path.read_text(encoding="utf-8")) if control_report_path.exists() else {}
        control_valid = control.returncode == 0 and control_validation.get("success") is True
        for index, (case_id, mutate, expected_check) in enumerate(cases, start=1):
            release = copy.deepcopy(baseline_release)
            live = copy.deepcopy(baseline_live)
            mutate(release, live)
            release_path = temp_root / f"case-{index}-release.json"
            live_path = temp_root / f"case-{index}-live.json"
            report_path = temp_root / f"case-{index}-validation.json"
            release_path.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            live_path.write_text(json.dumps(live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--release",
                    str(release_path),
                    "--data-lake",
                    str(data_lake_path),
                    "--live-integrity",
                    str(live_path),
                    "--output",
                    str(report_path),
                ],
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
                "failure_count": len(validation.get("failures") or []),
            })

    passed = sum(row["tamper_rejected"] for row in results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": control_valid and passed == len(results),
        "isolated_fixture": True,
        "control_valid": control_valid,
        "control_failures": control_validation.get("failures") or [],
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "real_inputs_mutated": False,
        "results": results,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Local release must bind canonical-root live integrity; isolated-root success is test evidence only.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "isolated_fixture": report["isolated_fixture"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "control_valid": report["control_valid"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(OUTPUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
