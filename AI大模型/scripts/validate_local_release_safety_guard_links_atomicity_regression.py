#!/usr/bin/env python3
"""Isolated durability regression for the local-release safety receipt."""

from __future__ import annotations

import fcntl
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import validate_local_release_safety_guard_links as target

AI_ROOT = Path(__file__).resolve().parents[1]
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
CONSISTENCY = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
SAFETY_RECEIPT = AI_ROOT / "reports" / "local_release_safety_guard_link_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "local_release_safety_guard_links_atomicity_regression_report.json"
LOCK = AI_ROOT / "reports" / ".local_release_safety_guard_links.lock"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    protected = [Path(target.__file__).resolve(), RELEASE, DATA_LAKE, CONSISTENCY, SAFETY_RECEIPT]
    before = {str(path): sha256(path) for path in protected if path.is_file()}
    results: list[dict[str, Any]] = []
    snapshots = {name: target.load_json_snapshot(path) for name, path in {"release": RELEASE, "data_lake": DATA_LAKE, "consistency": CONSISTENCY}.items()}
    results.append({"case": "input_snapshot_hashes_exact", "passed": all(isinstance(payload, dict) and digest == sha256({"release": RELEASE, "data_lake": DATA_LAKE, "consistency": CONSISTENCY}[name]) for name, (payload, digest) in snapshots.items())})

    provenance = target.build_receipt_provenance(release_path=RELEASE, release_sha256=sha256(RELEASE), data_lake_path=DATA_LAKE, data_lake_sha256=sha256(DATA_LAKE), consistency_path=CONSISTENCY, consistency_sha256=sha256(CONSISTENCY), output_path=SAFETY_RECEIPT, lock_path=LOCK)
    provenance_ok = provenance == {"validator_script_path": str(Path(target.__file__).resolve()), "validator_script_sha256": sha256(Path(target.__file__).resolve()), "release_path": str(RELEASE.resolve()), "release_sha256": sha256(RELEASE), "data_lake_path": str(DATA_LAKE.resolve()), "data_lake_sha256": sha256(DATA_LAKE), "consistency_receipt_path": str(CONSISTENCY.resolve()), "consistency_receipt_sha256": sha256(CONSISTENCY), "output_path": str(SAFETY_RECEIPT.resolve()), "lock_path": str(LOCK.resolve()), "lock_acquired": True, "atomic_commit": True}
    results.append({"case": "receipt_provenance_exact", "passed": provenance_ok})

    with tempfile.TemporaryDirectory(prefix="safety-guard-atomicity-") as name:
        root = Path(name)
        output = root / "safety.json"
        lock = root / "safety.lock"
        first = {"generation": 1, "success": True}
        target.write_json_atomic(output, first)
        prior = output.read_bytes()
        results.append({"case": "atomic_commit_complete_json", "passed": json.loads(prior.decode("utf-8")) == first and prior.endswith(b"\n")})
        interrupted = False
        try:
            target.write_json_atomic(output, {"generation": 2}, fail_before_replace=True)
        except RuntimeError as exc:
            interrupted = str(exc) == "simulated_safety_guard_receipt_failure_before_replace"
        residue = list(root.glob(f".{output.name}.safety-*"))
        results.append({"case": "interrupted_replace_preserves_prior", "passed": interrupted and output.read_bytes() == prior and not residue})
        first_lock = target.acquire_lock(lock, 0.2)
        second_lock = target.acquire_lock(lock, 0.0) if first_lock is not None else None
        if first_lock is not None:
            fcntl.flock(first_lock.fileno(), fcntl.LOCK_UN); first_lock.close()
        recovered = target.acquire_lock(lock, 0.2)
        recovered_ok = recovered is not None
        if recovered is not None:
            fcntl.flock(recovered.fileno(), fcntl.LOCK_UN); recovered.close()
        results.append({"case": "lock_timeout_and_recovery", "passed": first_lock is not None and second_lock is None and recovered_ok})

    after = {str(path): sha256(path) for path in protected if path.is_file()}
    failed = sum(1 for row in results if not row.get("passed"))
    failures = []
    if failed:
        failures.append({"check": "all_cases_pass", "observed": failed, "expected": 0})
    if before != after:
        failures.append({"check": "real_inputs_unchanged", "observed": {"before": before, "after": after}, "expected": True})
    script = Path(__file__).resolve()
    report = {"schema_version": 1, "mode": "local-release-safety-guard-links-atomicity-regression-v1", "created_at": datetime.now(timezone.utc).isoformat(), "success": not failures, "isolated_fixture": True, "regression_script_path": str(script), "regression_script_sha256": sha256(script), "validator_script_path": str(Path(target.__file__).resolve()), "validator_script_sha256": sha256(Path(target.__file__).resolve()), "output_path": str(OUTPUT.resolve()), "lock_path": str(LOCK.resolve()), "lock_acquired": True, "atomic_commit": True, "case_count": len(results), "passed_case_count": len(results) - failed, "failed_case_count": failed, "real_inputs_mutated": before != after, "failure_count": len(failures), "failures": failures, "cases": results, "safe_for_model_claim": False, "release_ready": False}
    handle = target.acquire_lock(LOCK, 30.0)
    if handle is None:
        return 1
    try:
        target.write_json_atomic(OUTPUT, report)
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN); handle.close()
    print(json.dumps({"success": report["success"], "case_count": report["case_count"], "passed_case_count": report["passed_case_count"], "failure_count": report["failure_count"], "real_inputs_mutated": report["real_inputs_mutated"], "output": str(OUTPUT)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
