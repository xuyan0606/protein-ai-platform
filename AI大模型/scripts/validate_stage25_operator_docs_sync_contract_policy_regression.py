#!/usr/bin/env python3
"""Prove the independent operator-doc sync policy rejects contract drift."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


AI_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE = AI_ROOT / "scripts" / "stage25_operator_docs_sync_contract.py"
VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_operator_docs_sync_contract_policy.py"
OUTPUT = AI_ROOT / "reports" / "stage25_operator_docs_sync_contract_policy_regression_report.json"


def replace_exact(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"expected one replacement target: {old!r}")
    return source.replace(old, new, 1)


def main() -> int:
    source = CONTRACT_MODULE.read_text(encoding="utf-8")
    cases: list[tuple[str, Callable[[str], str], str]] = [
        (
            "contract_version_drift",
            lambda text: replace_exact(text, 'CONTRACT_VERSION = "stage25-operator-docs-sync-v4"', 'CONTRACT_VERSION = "stage25-operator-docs-sync-v5"'),
            "contract_version_exact",
        ),
        (
            "output_path_drift",
            lambda text: replace_exact(text, 'OUTPUT_PATH_ID = "ai:reports/stage25_operator_docs_dynamic_status_sync_report.json"', 'OUTPUT_PATH_ID = "ai:reports/forged_sync_report.json"'),
            "output_path_exact",
        ),
        (
            "lock_path_drift",
            lambda text: replace_exact(text, 'LOCK_PATH_ID = "ai:reports/.stage25_operator_docs_sync.lock"', 'LOCK_PATH_ID = "ai:reports/.forged_sync.lock"'),
            "lock_path_exact",
        ),
        (
            "target_path_drift",
            lambda text: replace_exact(text, '("next", "ai:reports/next_operator_packet_20260806.md"),', '("next", "ai:reports/forged_operator_packet.md"),'),
            "target_specs_exact",
        ),
        (
            "marker_set_drift",
            lambda text: replace_exact(text, 'SLOTS = ("latest-release", "core-counts", "data-lake", "human-backlog", "post-source")', 'SLOTS = ("latest-release", "core-counts", "data-lake", "human-backlog", "release")'),
            "slot_specs_exact",
        ),
        (
            "semantic_projection_version_drift",
            lambda text: replace_exact(text, 'SEMANTIC_PROJECTION_VERSION = "stage25-operator-docs-semantic-projection-v3"', 'SEMANTIC_PROJECTION_VERSION = "stage25-operator-docs-semantic-projection-v4"'),
            "semantic_projection_version_exact",
        ),
        (
            "semantic_projection_fields_drift",
            lambda text: replace_exact(text, '("local_release", ("artifact_count", "release_ready")),', '("local_release", ("artifact_count", "release_ready", "created_at")),'),
            "semantic_projection_specs_exact",
        ),
        (
            "canonicalization_drift",
            lambda text: replace_exact(text, 'separators=(",", ":")', 'separators=(", ", ": ")'),
            "test_vector_contract_sha256_exact",
        ),
    ]
    results: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="stage25-doc-sync-policy-") as temp_dir:
        temp_root = Path(temp_dir)
        control_report = temp_root / "control.json"
        control = subprocess.run(
            [sys.executable, str(VALIDATOR), "--contract-module", str(CONTRACT_MODULE), "--output", str(control_report)],
            cwd=AI_ROOT,
            text=True,
            capture_output=True,
            timeout=300,
        )
        control_validation = json.loads(control_report.read_text(encoding="utf-8")) if control_report.exists() else {}
        control_valid = control.returncode == 0 and control_validation.get("success") is True

        for index, (case_id, mutate, expected_check) in enumerate(cases, start=1):
            module_path = temp_root / f"case-{index}-contract.py"
            report_path = temp_root / f"case-{index}-validation.json"
            module_path.write_text(mutate(source), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(VALIDATOR), "--contract-module", str(module_path), "--output", str(report_path)],
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

    passed = sum(bool(row["tamper_rejected"]) for row in results)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": control_valid and passed == len(results),
        "isolated_fixture": True,
        "control_valid": control_valid,
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "real_inputs_mutated": False,
        "results": results,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Only temporary contract-module copies are mutated; canonical sync inputs remain unchanged.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "control_valid": report["control_valid"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(OUTPUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
