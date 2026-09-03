#!/usr/bin/env python3
"""Exercise isolated local-release consistency semantic-current drift cases."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

try:
    import validate_local_release_manifest_fail_closed_consistency as target
    from local_release_consistency_receipt_contract import build_semantic_inputs
except ModuleNotFoundError:
    from scripts import validate_local_release_manifest_fail_closed_consistency as target
    from scripts.local_release_consistency_receipt_contract import build_semantic_inputs


AI_ROOT = Path(__file__).resolve().parents[1]
CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_consistency_receipt_current.py"
CONSISTENCY_VALIDATOR = AI_ROOT / "scripts" / "validate_local_release_manifest_fail_closed_consistency.py"
SEMANTIC_CONTRACT = AI_ROOT / "scripts" / "local_release_consistency_receipt_contract.py"
CANONICAL_RECEIPT = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
CANONICAL_CURRENT = AI_ROOT / "reports" / "local_release_consistency_receipt_current_validation_report.json"
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
LIVE_INTEGRITY = AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json"
CONTRACT_POLICY = AI_ROOT / "reports" / "data_lake_release_input_contract_policy_validation_report.json"
SEMANTIC_POLICY = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json"
LOCK_PATH = AI_ROOT / "reports" / ".local_release_manifest_fail_closed_consistency.lock"
OUTPUT = AI_ROOT / "reports" / "local_release_consistency_receipt_current_regression_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_current(paths: dict[str, Path], output: Path) -> tuple[int, dict[str, Any]]:
    process = subprocess.run(
        [
            sys.executable,
            str(CURRENT_VALIDATOR),
            "--receipt", str(paths["receipt"]),
            "--validator", str(CONSISTENCY_VALIDATOR),
            "--semantic-contract", str(SEMANTIC_CONTRACT),
            "--release", str(paths["release"]),
            "--data-lake", str(paths["data_lake"]),
            "--live-integrity", str(paths["live_integrity"]),
            "--contract-policy", str(paths["contract_policy"]),
            "--semantic-policy", str(paths["semantic_policy"]),
            "--expected-lock-path", str(LOCK_PATH),
            "--output", str(output),
        ],
        cwd=AI_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return process.returncode, load_json(output)


def main() -> int:
    protected = [
        CURRENT_VALIDATOR,
        CONSISTENCY_VALIDATOR,
        SEMANTIC_CONTRACT,
        CANONICAL_RECEIPT,
        RELEASE,
        DATA_LAKE,
        LIVE_INTEGRITY,
        CONTRACT_POLICY,
        SEMANTIC_POLICY,
    ]
    if CANONICAL_CURRENT.is_file():
        protected.append(CANONICAL_CURRENT)
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="local-release-consistency-current-") as temp_name:
        temp_root = Path(temp_name)
        paths = {
            "receipt": temp_root / "receipt.json",
            "release": temp_root / "release.json",
            "data_lake": temp_root / "data-lake.json",
            "live_integrity": temp_root / "live.json",
            "contract_policy": temp_root / "policy.json",
            "semantic_policy": temp_root / "semantic-policy.json",
        }
        canonical_inputs = {
            "release": RELEASE,
            "data_lake": DATA_LAKE,
            "live_integrity": LIVE_INTEGRITY,
            "contract_policy": CONTRACT_POLICY,
            "semantic_policy": SEMANTIC_POLICY,
        }
        for role, source in canonical_inputs.items():
            shutil.copy2(source, paths[role])

        fixture_policy = load_json(paths["semantic_policy"])
        fixture_policy["policy_output_path"] = str(paths["semantic_policy"].resolve())
        write_json(paths["semantic_policy"], fixture_policy)

        receipt = load_json(CANONICAL_RECEIPT)
        payloads = {role: load_json(paths[role]) for role in canonical_inputs}
        semantic = build_semantic_inputs(payloads)
        receipt.update({
            "validator_script_path": str(CONSISTENCY_VALIDATOR.resolve()),
            "validator_script_sha256": sha256(CONSISTENCY_VALIDATOR),
            "semantic_contract_module_path": str(SEMANTIC_CONTRACT.resolve()),
            "semantic_contract_module_sha256": sha256(SEMANTIC_CONTRACT),
            "release_path": str(paths["release"].resolve()),
            "release_sha256": sha256(paths["release"]),
            "data_lake_path": str(paths["data_lake"].resolve()),
            "data_lake_sha256": sha256(paths["data_lake"]),
            "live_integrity_path": str(paths["live_integrity"].resolve()),
            "live_integrity_sha256": sha256(paths["live_integrity"]),
            "contract_policy_path": str(paths["contract_policy"].resolve()),
            "contract_policy_sha256": sha256(paths["contract_policy"]),
            "semantic_policy_path": str(paths["semantic_policy"].resolve()),
            "semantic_policy_sha256": sha256(paths["semantic_policy"]),
            "output_path": str(paths["receipt"].resolve()),
            "semantic_input_rows": semantic["input_rows"],
            "semantic_inputs": semantic["rows"],
            "semantic_inputs_sha256": semantic["sha256"],
            "safe_pipeline_terminal_deferred": os.environ.get("KWB_DEFER_SAFE_PIPELINE_TERMINAL") == "1",
        })
        write_json(paths["receipt"], receipt)
        baseline_bytes = {name: path.read_bytes() for name, path in paths.items()}

        control_output = temp_root / "control-current.json"
        control_rc, control = run_current(paths, control_output)
        results.append({
            "case": "fixture_control",
            "passed": control_rc == 0 and control.get("success") is True and control.get("failure_count") == 0,
            "returncode": control_rc,
            "failure_count": control.get("failure_count"),
            "observed_checks": [row.get("check") for row in control.get("failures") or [] if isinstance(row, dict)],
        })

        excluded_release = load_json(paths["release"])
        excluded_release["readiness_summary"]["local_release_fail_closed_consistency_success"] = "post-consistency-drift"
        write_json(paths["release"], excluded_release)
        excluded_output = temp_root / "excluded-release-current.json"
        excluded_rc, excluded_report = run_current(paths, excluded_output)
        results.append({
            "case": "post_consistency_release_summary_drift_allowed",
            "passed": excluded_rc == 0 and excluded_report.get("success") is True,
            "returncode": excluded_rc,
            "failure_count": excluded_report.get("failure_count"),
            "observed_checks": [row.get("check") for row in excluded_report.get("failures") or [] if isinstance(row, dict)],
        })

        def restore() -> None:
            for name, content in baseline_bytes.items():
                paths[name].write_bytes(content)

        def mutate_json(path: Path, mutator: Callable[[dict[str, Any]], None]) -> None:
            payload = load_json(path)
            mutator(payload)
            write_json(path, payload)

        cases: list[tuple[str, Callable[[], None], str]] = [
            (
                "release_consumed_field_drift",
                lambda: mutate_json(paths["release"], lambda payload: payload.__setitem__("release_ready", True)),
                "semantic_inputs_exact_current",
            ),
            (
                "data_lake_included_artifact_drift",
                lambda: mutate_json(paths["data_lake"], lambda payload: payload["artifacts"][0].__setitem__("sha256", "0" * 64)),
                "semantic_inputs_exact_current",
            ),
            (
                "live_consumed_field_drift",
                lambda: mutate_json(paths["live_integrity"], lambda payload: payload.__setitem__("strict_verified_rows", int(payload["strict_verified_rows"]) + 1)),
                "semantic_inputs_exact_current",
            ),
            (
                "policy_consumed_field_drift",
                lambda: mutate_json(paths["contract_policy"], lambda payload: payload.__setitem__("expected_contract_version", "drifted-version")),
                "semantic_inputs_exact_current",
            ),
            (
                "semantic_policy_consumed_field_drift",
                lambda: mutate_json(paths["semantic_policy"], lambda payload: payload.__setitem__("expected_contract_version", "drifted-version")),
                "semantic_inputs_exact_current",
            ),
            (
                "recorded_semantic_rows_drift",
                lambda: mutate_json(paths["receipt"], lambda payload: payload["semantic_inputs"][0].__setitem__("projection_sha256", "1" * 64)),
                "semantic_inputs_exact_current",
            ),
            (
                "recorded_semantic_digest_drift",
                lambda: mutate_json(paths["receipt"], lambda payload: payload.__setitem__("semantic_inputs_sha256", "2" * 64)),
                "semantic_inputs_sha256_current",
            ),
            (
                "validator_sha_drift",
                lambda: mutate_json(paths["receipt"], lambda payload: payload.__setitem__("validator_script_sha256", "3" * 64)),
                "receipt_validator_sha256_current",
            ),
            (
                "contract_module_sha_drift",
                lambda: mutate_json(paths["receipt"], lambda payload: payload.__setitem__("semantic_contract_module_sha256", "4" * 64)),
                "receipt_semantic_contract_sha256_current",
            ),
            (
                "receipt_output_path_drift",
                lambda: mutate_json(paths["receipt"], lambda payload: payload.__setitem__("output_path", "/tmp/non-canonical-consistency.json")),
                "receipt_output_path",
            ),
            (
                "receipt_lock_path_drift",
                lambda: mutate_json(paths["receipt"], lambda payload: payload.__setitem__("lock_path", "/tmp/non-canonical-consistency.lock")),
                "receipt_lock_path",
            ),
            (
                "receipt_atomic_flag_drift",
                lambda: mutate_json(paths["receipt"], lambda payload: payload.__setitem__("receipt_atomic_commit", False)),
                "receipt_atomic_commit",
            ),
            (
                "receipt_success_flag_drift",
                lambda: mutate_json(paths["receipt"], lambda payload: payload.__setitem__("success", False)),
                "receipt_success",
            ),
            (
                "release_receipt_proof_current_sha_drift",
                lambda: mutate_json(paths["release"], lambda payload: payload["readiness_summary"].__setitem__("enzyme_agent_execution_receipt_proof_current_sha256", "f" * 64)),
                "semantic_inputs_exact_current",
            ),
        ]

        for name, mutation, expected_check in cases:
            restore()
            mutation()
            case_output = temp_root / f"{name}-current.json"
            returncode, report = run_current(paths, case_output)
            observed_checks = [row.get("check") for row in report.get("failures", []) if isinstance(row, dict)]
            results.append({
                "case": name,
                "passed": returncode != 0 and report.get("success") is False and expected_check in observed_checks,
                "returncode": returncode,
                "expected_check": expected_check,
                "observed_checks": observed_checks,
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
        "mode": "local_release_consistency_receipt_current_regression",
        "success": not failures,
        "isolated_fixture": True,
        "post_consistency_drift_allowed": bool(results[1].get("passed")) if len(results) > 1 else False,
        "regression_script_path": str(regression_script),
        "regression_script_sha256": sha256(regression_script),
        "current_validator_script_path": str(CURRENT_VALIDATOR.resolve()),
        "current_validator_script_sha256": sha256(CURRENT_VALIDATOR),
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
    target.write_json_atomic(OUTPUT, report)
    print(json.dumps({
        "success": report["success"],
        "case_count": report["case_count"],
        "passed_case_count": report["passed_case_count"],
        "failure_count": report["failure_count"],
        "real_inputs_mutated": real_inputs_mutated,
        "output": str(OUTPUT),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
