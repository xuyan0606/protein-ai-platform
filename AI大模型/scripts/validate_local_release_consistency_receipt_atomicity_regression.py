#!/usr/bin/env python3
"""Exercise isolated local-release consistency receipt durability cases."""

from __future__ import annotations

import fcntl
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

try:
    import validate_local_release_manifest_fail_closed_consistency as target
except ModuleNotFoundError:
    from scripts import validate_local_release_manifest_fail_closed_consistency as target


AI_ROOT = Path(__file__).resolve().parents[1]
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
LIVE_INTEGRITY = AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json"
CONTRACT_POLICY = AI_ROOT / "reports" / "data_lake_release_input_contract_policy_validation_report.json"
SEMANTIC_POLICY = AI_ROOT / "reports" / "local_release_consistency_semantic_policy_validation_report.json"
CANONICAL_RECEIPT = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "local_release_consistency_receipt_atomicity_regression_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    protected = [Path(target.__file__).resolve(), RELEASE, DATA_LAKE, LIVE_INTEGRITY, CONTRACT_POLICY, SEMANTIC_POLICY, CANONICAL_RECEIPT]
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="local-release-consistency-atomicity-") as temp_name:
        temp_root = Path(temp_name)
        fixture_output = temp_root / "consistency.json"
        fixture_lock = temp_root / "consistency.lock"
        input_paths = {
            "release": RELEASE,
            "data_lake": DATA_LAKE,
            "live_integrity": LIVE_INTEGRITY,
            "contract_policy": CONTRACT_POLICY,
            "semantic_policy": SEMANTIC_POLICY,
        }
        snapshots = {name: target.load_json_snapshot(path) for name, path in input_paths.items()}
        snapshot_hashes_exact = all(
            digest == sha256(input_paths[name]) and isinstance(payload, dict)
            for name, (payload, digest) in snapshots.items()
        )
        results.append({
            "case": "input_snapshot_hashes_exact",
            "passed": snapshot_hashes_exact,
            "snapshot_rows": len(snapshots),
        })

        provenance = target.build_receipt_provenance(
            release_path=RELEASE,
            release_sha256=snapshots["release"][1],
            data_lake_path=DATA_LAKE,
            data_lake_sha256=snapshots["data_lake"][1],
            live_integrity_path=LIVE_INTEGRITY,
            live_integrity_sha256=snapshots["live_integrity"][1],
            contract_policy_path=CONTRACT_POLICY,
            contract_policy_sha256=snapshots["contract_policy"][1],
            semantic_policy_path=SEMANTIC_POLICY,
            semantic_policy_sha256=snapshots["semantic_policy"][1],
            output_path=fixture_output,
            lock_path=fixture_lock,
        )
        expected_provenance = {
            "validator_script_path": str(Path(target.__file__).resolve()),
            "validator_script_sha256": sha256(Path(target.__file__).resolve()),
            "release_path": str(RELEASE.resolve()),
            "release_sha256": sha256(RELEASE),
            "data_lake_path": str(DATA_LAKE.resolve()),
            "data_lake_sha256": sha256(DATA_LAKE),
            "live_integrity_path": str(LIVE_INTEGRITY.resolve()),
            "live_integrity_sha256": sha256(LIVE_INTEGRITY),
            "contract_policy_path": str(CONTRACT_POLICY.resolve()),
            "contract_policy_sha256": sha256(CONTRACT_POLICY),
            "semantic_policy_path": str(SEMANTIC_POLICY.resolve()),
            "semantic_policy_sha256": sha256(SEMANTIC_POLICY),
            "output_path": str(fixture_output.resolve()),
            "lock_path": str(fixture_lock.resolve()),
            "lock_acquired": True,
            "receipt_atomic_commit": True,
        }
        results.append({
            "case": "receipt_provenance_exact",
            "passed": provenance == expected_provenance,
            "observed": provenance,
            "expected": expected_provenance,
        })

        first_payload = {"generation": 1, "success": True}
        target.write_json_atomic(fixture_output, first_payload)
        first_bytes = fixture_output.read_bytes()
        results.append({
            "case": "atomic_commit_complete_json",
            "passed": json.loads(first_bytes.decode("utf-8")) == first_payload and first_bytes.endswith(b"\n"),
            "output_sha256": sha256(fixture_output),
        })

        interrupted = False
        try:
            target.write_json_atomic(fixture_output, {"generation": 2, "success": False}, fail_before_replace=True)
        except RuntimeError as exc:
            interrupted = str(exc) == "simulated_local_release_consistency_receipt_failure_before_replace"
        residual_temp_files = sorted(path.name for path in temp_root.glob(f".{fixture_output.name}.receipt-*"))
        results.append({
            "case": "interrupted_commit_preserves_prior_receipt",
            "passed": interrupted and fixture_output.read_bytes() == first_bytes and not residual_temp_files,
            "interrupted": interrupted,
            "prior_receipt_preserved": fixture_output.read_bytes() == first_bytes,
            "residual_temp_files": residual_temp_files,
        })

        first_lock = target.acquire_receipt_lock(fixture_lock, 0.2)
        second_lock = target.acquire_receipt_lock(fixture_lock, 0.0) if first_lock is not None else None
        if first_lock is not None:
            fcntl.flock(first_lock.fileno(), fcntl.LOCK_UN)
            first_lock.close()
        recovered_lock = target.acquire_receipt_lock(fixture_lock, 0.2)
        recovered = recovered_lock is not None
        if recovered_lock is not None:
            fcntl.flock(recovered_lock.fileno(), fcntl.LOCK_UN)
            recovered_lock.close()
        results.append({
            "case": "lock_contention_and_recovery",
            "passed": first_lock is not None and second_lock is None and recovered,
            "first_lock_acquired": first_lock is not None,
            "contender_blocked": second_lock is None,
            "recovered_after_release": recovered,
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
        "mode": "local_release_consistency_receipt_atomicity_regression",
        "success": not failures,
        "isolated_fixture": True,
        "regression_script_path": str(regression_script),
        "regression_script_sha256": sha256(regression_script),
        "validator_script_path": str(Path(target.__file__).resolve()),
        "validator_script_sha256": sha256(Path(target.__file__).resolve()),
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
