#!/usr/bin/env python3
"""Pin release-input contract policy independently from its shared implementation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE = AI_ROOT / "scripts" / "data_lake_release_input_contract.py"
OUTPUT = AI_ROOT / "reports" / "data_lake_release_input_contract_policy_validation_report.json"
EXPECTED_VERSION = "data-lake-release-input-v1"
EXPECTED_EXCLUDED_PATHS = {
    "reports/safe_training_pipeline_run.json",
    "reports/data_lake_live_content_integrity_validation_report.json",
    "reports/local_release_manifest.json",
    "reports/local_release_manifest_fail_closed_consistency_validation_report.json",
    "reports/local_release_safety_guard_link_validation_report.json",
}
EXPECTED_TEST_VECTOR_SHA256 = "73faca201747ecef0df5579526c987eee6e0b37203e800c5d7491457e7d38615"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_input_contract_policy_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load contract module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vector_manifest() -> dict[str, Any]:
    artifacts = [{
        "path": "datasets/contract_probe.jsonl",
        "exists": True,
        "size_bytes": 17,
        "rows": 1,
        "sha256": "a" * 64,
    }]
    for index, path in enumerate(sorted(EXPECTED_EXCLUDED_PATHS), start=1):
        artifacts.append({
            "path": path,
            "exists": True,
            "size_bytes": index,
            "rows": None,
            "sha256": str(index) * 64,
        })
    return {"root": "/contract-test-root", "artifacts": artifacts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate release-input contract policy anchor")
    parser.add_argument("--contract-module", type=Path, default=CONTRACT_MODULE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    module: ModuleType | None = None
    contract: dict[str, Any] = {}
    if not args.contract_module.is_file():
        failures.append({"check": "contract_module_exists", "observed": str(args.contract_module), "expected": "file"})
    else:
        try:
            module = load_contract_module(args.contract_module)
            contract = module.build_release_input_contract(test_vector_manifest())
        except Exception as exc:
            failures.append({"check": "contract_module_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})

    observed_version = getattr(module, "CONTRACT_VERSION", None) if module else None
    observed_excluded = set(getattr(module, "RELEASE_INPUT_EXCLUDED_PATHS", set()) or []) if module else set()
    checks = (
        ("contract_version_exact", observed_version, EXPECTED_VERSION),
        ("contract_exclusion_paths_exact", sorted(observed_excluded), sorted(EXPECTED_EXCLUDED_PATHS)),
        ("test_vector_contract_version_exact", contract.get("version"), EXPECTED_VERSION),
        ("test_vector_contract_sha256_exact", contract.get("sha256"), EXPECTED_TEST_VECTOR_SHA256),
        ("test_vector_artifact_rows_exact", contract.get("artifact_rows"), 1),
        ("test_vector_excluded_paths_exact", contract.get("excluded_paths"), sorted(EXPECTED_EXCLUDED_PATHS)),
    )
    for check, observed, expected in checks:
        if observed != expected:
            failures.append({"check": check, "observed": observed, "expected": expected})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "contract_module_path": str(args.contract_module.resolve()),
        "contract_module_sha256": sha256(args.contract_module) if args.contract_module.is_file() else None,
        "expected_contract_version": EXPECTED_VERSION,
        "expected_excluded_paths": sorted(EXPECTED_EXCLUDED_PATHS),
        "expected_test_vector_sha256": EXPECTED_TEST_VECTOR_SHA256,
        "observed_test_vector_contract": contract,
        "failure_count": len(failures),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "The independent anchor pins the shared contract policy but does not compute production release evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "failure_count": report["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
