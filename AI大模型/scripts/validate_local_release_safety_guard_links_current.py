#!/usr/bin/env python3
"""Validate the canonical safety receipt against a live recomputation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import validate_local_release_safety_guard_links as target

AI_ROOT = Path(__file__).resolve().parents[1]
SAFETY = AI_ROOT / "reports" / "local_release_safety_guard_link_validation_report.json"
RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
DATA_LAKE = AI_ROOT / "reports" / "data_lake_manifest.json"
CONSISTENCY = AI_ROOT / "reports" / "local_release_manifest_fail_closed_consistency_validation_report.json"
OUT = AI_ROOT / "reports" / "local_release_safety_guard_links_current_validation_report.json"
LOCK = AI_ROOT / "reports" / ".local_release_safety_guard_links.lock"


def sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def add(failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current safety guard receipt")
    parser.add_argument("--safety-receipt", type=Path, default=SAFETY)
    parser.add_argument("--release", type=Path, default=RELEASE)
    parser.add_argument("--data-lake", type=Path, default=DATA_LAKE)
    parser.add_argument("--consistency-receipt", type=Path, default=CONSISTENCY)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-before-replace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    handle = target.acquire_lock(args.lock_path, args.lock_timeout_seconds)
    if handle is None:
        print(json.dumps({"success": False, "error": "safety_current_lock_timeout", "output_preserved": args.output.exists()}, ensure_ascii=False))
        return 1
    try:
        receipt = load(args.safety_receipt)
        failures: list[dict[str, Any]] = []
        add(failures, "receipt_schema", receipt.get("schema_version"), 2)
        add(failures, "receipt_mode", receipt.get("mode"), "local-release-safety-guard-links-v2")
        add(failures, "receipt_success", receipt.get("success"), True)
        add(failures, "receipt_validator_path", receipt.get("validator_script_path"), str(Path(target.__file__).resolve()))
        add(failures, "receipt_validator_sha", receipt.get("validator_script_sha256"), sha256(Path(target.__file__).resolve()))
        add(failures, "receipt_release_path", receipt.get("release_path"), str(args.release.resolve()))
        add(failures, "receipt_release_sha", receipt.get("release_sha256"), sha256(args.release))
        add(failures, "receipt_data_lake_path", receipt.get("data_lake_path"), str(args.data_lake.resolve()))
        recorded_data_lake_sha = receipt.get("data_lake_sha256")
        if not isinstance(recorded_data_lake_sha, str) or len(recorded_data_lake_sha) != 64 or any(char not in "0123456789abcdef" for char in recorded_data_lake_sha):
            failures.append({"check": "receipt_data_lake_snapshot_sha_valid", "observed": recorded_data_lake_sha, "expected": "64 lowercase hex chars"})
        add(failures, "receipt_consistency_path", receipt.get("consistency_receipt_path"), str(args.consistency_receipt.resolve()))
        add(failures, "receipt_consistency_sha", receipt.get("consistency_receipt_sha256"), sha256(args.consistency_receipt))
        add(failures, "receipt_output_path", receipt.get("output_path"), str(args.safety_receipt.resolve()))
        add(failures, "receipt_lock_path", receipt.get("lock_path"), str(args.lock_path.resolve()))
        add(failures, "receipt_lock_acquired", receipt.get("lock_acquired"), True)
        add(failures, "receipt_atomic_commit", receipt.get("atomic_commit"), True)
        with tempfile.TemporaryDirectory(prefix="safety-current-recompute-") as name:
            root = Path(name)
            recomputed_path = root / "safety.json"
            process = subprocess.run([sys.executable, str(Path(target.__file__).resolve()), "--release", str(args.release), "--data-lake", str(args.data_lake), "--consistency-receipt", str(args.consistency_receipt), "--output", str(recomputed_path), "--lock-path", str(root / "safety.lock")], cwd=AI_ROOT, text=True, capture_output=True, check=False)
            recomputed = load(recomputed_path)
        add(failures, "live_recompute_returncode", process.returncode, 0)
        add(failures, "live_recompute_success", recomputed.get("success"), True)
        add(failures, "live_recompute_failure_rows", len(recomputed.get("failures") or []), 0)
        add(failures, "guard_link_count_current", receipt.get("guard_link_count"), recomputed.get("guard_link_count"))
        add(failures, "checked_guard_links_current", receipt.get("checked_guard_links"), recomputed.get("checked_guard_links"))
        add(failures, "checked_summary_fields_current", receipt.get("checked_summary_success_fields"), recomputed.get("checked_summary_success_fields"))
        script = Path(__file__).resolve()
        result = {"schema_version": 1, "mode": "local-release-safety-guard-links-current-v1", "created_at": datetime.now(timezone.utc).isoformat(), "success": not failures, "safety_receipt_path": str(args.safety_receipt.resolve()), "safety_receipt_sha256": sha256(args.safety_receipt), "validator_script_path": str(Path(target.__file__).resolve()), "validator_script_sha256": sha256(Path(target.__file__).resolve()), "current_validator_script_path": str(script), "current_validator_script_sha256": sha256(script), "release_path": str(args.release.resolve()), "release_sha256": sha256(args.release), "data_lake_path": str(args.data_lake.resolve()), "data_lake_live_sha256": sha256(args.data_lake), "data_lake_signed_snapshot_sha256": recorded_data_lake_sha, "consistency_receipt_path": str(args.consistency_receipt.resolve()), "consistency_receipt_sha256": sha256(args.consistency_receipt), "output_path": str(args.output.resolve()), "lock_path": str(args.lock_path.resolve()), "lock_acquired": True, "atomic_commit": True, "guard_link_count": recomputed.get("guard_link_count"), "failure_count": len(failures), "failures": failures, "safe_for_model_claim": False, "release_ready": False}
        target.write_json_atomic(args.output, result, fail_before_replace=args.fail_before_replace)
    finally:
        handle.close()
    print(json.dumps({"success": result["success"], "guard_link_count": result["guard_link_count"], "failure_count": result["failure_count"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
