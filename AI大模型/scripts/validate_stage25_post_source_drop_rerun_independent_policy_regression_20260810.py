#!/usr/bin/env python3
"""Prove the independent post-source policy rejects coordinated drift."""

from __future__ import annotations

import hashlib
import json
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


AI_ROOT = Path(__file__).resolve().parents[1]
BUILDER = AI_ROOT / "scripts" / "build_stage25_post_source_drop_rerun_receipt_20260806.py"
VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_receipt_20260806.py"
POLICY = AI_ROOT / "scripts" / "validate_stage25_post_source_drop_rerun_independent_policy_20260810.py"
CANONICAL_RECEIPT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"
CANONICAL_VALIDATION = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_validation_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_independent_policy_regression_20260810.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source: str, old: str, new: str) -> str:
    if old not in source:
        raise RuntimeError(f"replacement target missing: {old!r}")
    return source.replace(old, new, 1)


def run_fixture(root: Path, builder_source: str) -> tuple[int, int, int, dict[str, object]]:
    scripts = root / "scripts"
    reports = root / "reports"
    scripts.mkdir(parents=True)
    reports.mkdir(parents=True)
    builder = scripts / BUILDER.name
    validator = scripts / VALIDATOR.name
    builder.write_text(builder_source, encoding="utf-8")
    shutil.copy2(VALIDATOR, validator)

    build = subprocess.run([sys.executable, str(builder)], cwd=root, capture_output=True, text=True, check=False)
    namespace = runpy.run_path(str(builder))
    receipt = Path(namespace["OUTPUT"]).resolve()
    lock_path = Path(namespace["LOCK_PATH"]).resolve()
    validation = reports / CANONICAL_VALIDATION.name
    validate = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--receipt",
            str(receipt),
            "--builder",
            str(builder),
            "--expected-output",
            str(receipt),
            "--expected-lock-path",
            str(lock_path),
            "--output",
            str(validation),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    policy_report = reports / "independent_policy.json"
    policy = subprocess.run(
        [
            sys.executable,
            str(POLICY),
            "--builder",
            str(builder),
            "--validator",
            str(validator),
            "--receipt",
            str(receipt),
            "--validation",
            str(validation),
            "--output",
            str(policy_report),
        ],
        cwd=AI_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(policy_report.read_text(encoding="utf-8")) if policy_report.is_file() else {"policy_stderr": policy.stderr[-1000:]}
    return build.returncode, validate.returncode, policy.returncode, report


def main() -> int:
    source = BUILDER.read_text(encoding="utf-8")
    protected = [BUILDER, VALIDATOR, POLICY, CANONICAL_RECEIPT, CANONICAL_VALIDATION]
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    cases: list[tuple[str, Callable[[str], str], str]] = [
        (
            "builder_contract_version_drift",
            lambda text: replace_once(text, 'BUILDER_CONTRACT_VERSION = "stage25-post-source-drop-rerun-receipt-v2"', 'BUILDER_CONTRACT_VERSION = "stage25-post-source-drop-rerun-receipt-v3"'),
            "builder_contract_version_exact",
        ),
        (
            "builder_output_path_drift",
            lambda text: replace_once(text, 'OUTPUT = AI_ROOT / "reports" / "stage25_post_source_drop_rerun_receipt_20260806.json"', 'OUTPUT = AI_ROOT / "reports" / "forged_post_source_receipt.json"'),
            "builder_output_path_exact",
        ),
        (
            "builder_lock_path_drift",
            lambda text: replace_once(text, 'LOCK_PATH = AI_ROOT / "reports" / ".stage25_post_source_drop_rerun_receipt.lock"', 'LOCK_PATH = AI_ROOT / "reports" / ".forged_post_source_receipt.lock"'),
            "builder_lock_path_exact",
        ),
        (
            "command_name_drift",
            lambda text: replace_once(text, '"name": "validate_legal_fulltext_intake",', '"name": "forged_fulltext_intake",'),
            "command_test_vector_sha256_exact",
        ),
        (
            "command_expected_output_drift",
            lambda text: replace_once(text, '"fulltext_intake_validation_report_20260806.json"', '"forged_fulltext_intake_report.json"'),
            "command_test_vector_sha256_exact",
        ),
        (
            "sqlite_write_flag_drift",
            lambda text: replace_once(text, '"writes_sqlite": False,', '"writes_sqlite": True,'),
            "all_commands_non_sqlite",
        ),
        (
            "apply_block_flag_drift",
            lambda text: replace_once(text, '"blocks_apply_until_passed": True,', '"blocks_apply_until_passed": False,'),
            "all_commands_block_apply",
        ),
        (
            "receipt_schema_drift",
            lambda text: replace_once(text, '"schema_version": 2,', '"schema_version": 99,'),
            "receipt_schema_version_exact",
        ),
        (
            "command_contract_schema_drift",
            lambda text: replace_once(text, '"command_contract_schema_version": 1,', '"command_contract_schema_version": 99,'),
            "receipt_command_contract_schema_version_exact",
        ),
    ]
    results: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="stage25-post-source-independent-policy-") as temp_name:
        temp_root = Path(temp_name)
        control_root = temp_root / "control" / "AI大模型"
        build_rc, validation_rc, policy_rc, control = run_fixture(control_root, source)
        control_valid = build_rc == 0 and validation_rc == 0 and policy_rc == 0 and control.get("success") is True
        results.append({
            "case": "fixture_control",
            "passed": control_valid,
            "builder_returncode": build_rc,
            "validator_returncode": validation_rc,
            "policy_returncode": policy_rc,
            "failure_count": control.get("failure_count"),
        })

        for index, (name, mutation, expected_check) in enumerate(cases, start=1):
            case_root = temp_root / f"case-{index}" / "AI大模型"
            build_rc, validation_rc, policy_rc, report = run_fixture(case_root, mutation(source))
            checks = [row.get("check") for row in report.get("failures", []) if isinstance(row, dict)]
            results.append({
                "case": name,
                "passed": policy_rc != 0 and report.get("success") is False and expected_check in checks,
                "builder_returncode": build_rc,
                "coordinated_validator_returncode": validation_rc,
                "coordinated_validator_accepted": validation_rc == 0,
                "policy_returncode": policy_rc,
                "policy_stderr": report.get("policy_stderr"),
                "expected_check": expected_check,
                "observed_checks": checks,
            })

    after = {str(path): sha256(path) for path in protected if path.is_file()}
    real_inputs_mutated = before != after
    failed_rows = sum(1 for row in results if not row.get("passed"))
    failures = []
    if failed_rows:
        failures.append({"check": "all_cases_pass", "observed": failed_rows, "expected": 0})
    if real_inputs_mutated:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})

    regression_script = Path(__file__).resolve()
    report = {
        "schema_version": 1,
        "mode": "stage25_post_source_drop_rerun_independent_policy_regression",
        "success": not failures,
        "isolated_fixture": True,
        "regression_script_path": str(regression_script),
        "regression_script_sha256": sha256(regression_script),
        "case_count": len(results),
        "passed_case_count": sum(1 for row in results if row.get("passed")),
        "failed_case_count": failed_rows,
        "real_inputs_mutated": real_inputs_mutated,
        "failure_count": len(failures),
        "failures": failures,
        "cases": results,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failure_count"], "real_inputs_mutated": real_inputs_mutated, "output": str(OUTPUT)}, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
