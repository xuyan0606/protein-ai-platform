#!/usr/bin/env python3
"""Validate that the operator-doc sync receipt matches current canonical inputs."""

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
PLATFORM_ROOT = AI_ROOT.parent
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")
RECEIPT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_report.json"
CONTRACT_MODULE = AI_ROOT / "scripts" / "stage25_operator_docs_sync_contract.py"
POLICY_REPORT = AI_ROOT / "reports" / "stage25_operator_docs_sync_contract_policy_validation_report.json"
OUTPUT = AI_ROOT / "reports" / "stage25_operator_docs_sync_current_receipt_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("stage25_operator_docs_sync_current_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load contract module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_check(
    failures: list[dict[str, Any]],
    check: str,
    observed: Any,
    expected: Any,
) -> None:
    if observed != expected:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate current Stage 25 operator-doc sync receipt")
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--contract-module", type=Path, default=CONTRACT_MODULE)
    parser.add_argument("--policy-report", type=Path, default=POLICY_REPORT)
    parser.add_argument("--ai-root", type=Path, default=AI_ROOT)
    parser.add_argument("--platform-root", type=Path, default=PLATFORM_ROOT)
    parser.add_argument("--enzyme-db-root", type=Path, default=ENZYME_DB_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    receipt = load_json(args.receipt)
    policy = load_json(args.policy_report)
    module: ModuleType | None = None
    if not args.receipt.is_file():
        failures.append({"check": "receipt_exists", "observed": str(args.receipt), "expected": "file"})
    if not args.contract_module.is_file():
        failures.append({"check": "contract_module_exists", "observed": str(args.contract_module), "expected": "file"})
    else:
        try:
            module = load_contract_module(args.contract_module)
        except Exception as exc:
            failures.append({"check": "contract_module_loads", "observed": f"{type(exc).__name__}:{exc}", "expected": "loadable"})
    if not args.policy_report.is_file():
        failures.append({"check": "policy_report_exists", "observed": str(args.policy_report), "expected": "file"})

    contract = module.policy_contract() if module else {}
    resolve = module.resolve_path if module else None
    expected_output = resolve(module.OUTPUT_PATH_ID, ai_root=args.ai_root, platform_root=args.platform_root, enzyme_db_root=args.enzyme_db_root) if module else None
    expected_lock = resolve(module.LOCK_PATH_ID, ai_root=args.ai_root, platform_root=args.platform_root, enzyme_db_root=args.enzyme_db_root) if module else None
    expected_targets = [
        {
            "namespace": namespace,
            "path_id": path_id,
            "path": str(resolve(path_id, ai_root=args.ai_root, platform_root=args.platform_root, enzyme_db_root=args.enzyme_db_root)),
        }
        for namespace, path_id in getattr(module, "TARGET_SPECS", ())
    ] if module else []
    expected_observed_targets = [
        {"namespace": row["namespace"], "path": row["path"]}
        for row in expected_targets
    ]
    expected_markers = module.marker_specs() if module else []

    add_check(failures, "receipt_success", receipt.get("success"), True)
    add_check(failures, "receipt_failure_count_zero", receipt.get("failure_count"), 0)
    add_check(failures, "receipt_failures_empty", receipt.get("failures") or [], [])
    add_check(failures, "receipt_atomic_commit_true", receipt.get("receipt_atomic_commit"), True)
    add_check(failures, "receipt_lock_acquired", receipt.get("lock_acquired"), True)
    add_check(failures, "contract_version_exact", receipt.get("contract_version"), contract.get("version"))
    add_check(failures, "contract_sha256_exact", receipt.get("contract_sha256"), contract.get("sha256"))
    add_check(failures, "canonical_output_path_exact", receipt.get("canonical_output_path"), str(expected_output) if expected_output else None)
    add_check(failures, "observed_output_path_exact", receipt.get("observed_output_path"), str(expected_output) if expected_output else None)
    add_check(failures, "canonical_lock_path_exact", receipt.get("canonical_lock_path"), str(expected_lock) if expected_lock else None)
    add_check(failures, "lock_path_exact", receipt.get("lock_path"), str(expected_lock) if expected_lock else None)
    add_check(failures, "canonical_targets_exact", receipt.get("canonical_targets"), expected_targets)
    add_check(failures, "observed_targets_exact", receipt.get("observed_targets"), expected_observed_targets)
    add_check(failures, "slots_exact", receipt.get("slots"), list(getattr(module, "SLOTS", ())))
    add_check(failures, "marker_specs_exact", receipt.get("marker_specs"), expected_markers)
    add_check(failures, "target_rows_exact", receipt.get("target_rows"), len(expected_markers))
    add_check(failures, "stale_rows_zero", receipt.get("stale_rows"), 0)
    add_check(failures, "safe_for_model_claim_false", receipt.get("safe_for_model_claim"), False)
    add_check(failures, "release_ready_false", receipt.get("release_ready"), False)

    expected_result_keys = sorted(
        (row["path"], marker["slot"])
        for row in expected_targets
        for marker in expected_markers
        if marker["namespace"] == row["namespace"]
    )
    observed_results = receipt.get("results") or []
    observed_result_keys = sorted((str(row.get("path")), str(row.get("slot"))) for row in observed_results)
    add_check(failures, "result_target_slot_set_exact", observed_result_keys, expected_result_keys)
    add_check(failures, "result_rows_not_stale", [bool(row.get("stale")) for row in observed_results], [False] * len(expected_result_keys))

    document_hash_rows = receipt.get("document_hashes") or []
    document_hash_by_path = {str(row.get("path")): row for row in document_hash_rows}
    add_check(failures, "document_hash_path_set_exact", sorted(document_hash_by_path), sorted(row["path"] for row in expected_targets))
    for target in expected_targets:
        path = Path(target["path"])
        row = document_hash_by_path.get(str(path)) or {}
        if not path.is_file():
            failures.append({"check": "target_document_exists", "path": str(path), "expected": "file"})
            continue
        current_sha = sha256(path)
        add_check(failures, "document_after_sha_current", row.get("after_sha256"), current_sha)
        add_check(failures, "document_proposed_sha_current", row.get("proposed_sha256"), current_sha)

    expected_provenance_rows, provenance_failures = module.build_provenance(
        ai_root=args.ai_root,
        platform_root=args.platform_root,
        enzyme_db_root=args.enzyme_db_root,
    ) if module else ([], [])
    failures.extend(provenance_failures)
    observed_provenance_rows = receipt.get("provenance_rows") or []
    expected_by_role = {str(row.get("role")): row for row in expected_provenance_rows}
    observed_by_role = {str(row.get("role")): row for row in observed_provenance_rows}
    add_check(failures, "provenance_role_set_exact", sorted(observed_by_role), sorted(expected_by_role))
    for role, expected_row in expected_by_role.items():
        observed_row = observed_by_role.get(role) or {}
        add_check(failures, "provenance_row_keys_exact", sorted(observed_row), sorted(expected_row))
        if expected_row.get("freshness_mode") == "semantic_projection":
            for field in ("role", "kind", "path_id", "path", "freshness_mode", "projection_version", "projection_fields"):
                add_check(failures, "provenance_projection_contract_exact", observed_row.get(field), expected_row.get(field))
            add_check(failures, "provenance_projection_current", observed_row.get("projection"), expected_row.get("projection"))
            add_check(failures, "provenance_projection_sha_current", observed_row.get("projection_sha256"), expected_row.get("projection_sha256"))
            observed_size = observed_row.get("size_bytes")
            observed_sha = observed_row.get("sha256")
            if not isinstance(observed_size, int) or observed_size < 0:
                failures.append({"check": "provenance_observed_size_valid", "role": role, "observed": observed_size, "expected": "non-negative integer"})
            if not isinstance(observed_sha, str) or len(observed_sha) != 64 or any(char not in "0123456789abcdef" for char in observed_sha):
                failures.append({"check": "provenance_observed_sha_valid", "role": role, "observed": observed_sha, "expected": "lowercase SHA-256"})
        else:
            add_check(failures, "provenance_file_sha_current", observed_row, expected_row)
    add_check(failures, "provenance_row_count_exact", receipt.get("provenance_row_count"), len(expected_provenance_rows))
    add_check(failures, "provenance_digest_exact", receipt.get("provenance_sha256"), module.provenance_sha256(expected_provenance_rows) if module else None)
    add_check(failures, "observed_provenance_digest_self_consistent", receipt.get("observed_provenance_sha256"), module.observed_provenance_sha256(observed_provenance_rows) if module else None)

    add_check(failures, "policy_success", policy.get("success"), True)
    add_check(failures, "policy_failure_count_zero", policy.get("failure_count"), 0)
    add_check(failures, "policy_contract_version_exact", policy.get("expected_contract_version"), contract.get("version"))
    add_check(failures, "policy_contract_sha256_exact", policy.get("expected_contract_sha256"), contract.get("sha256"))
    add_check(failures, "policy_semantic_projection_version_exact", policy.get("expected_semantic_projection_version"), getattr(module, "SEMANTIC_PROJECTION_VERSION", None) if module else None)
    add_check(failures, "policy_semantic_projection_test_vector_exact", policy.get("expected_semantic_projection_test_vector_sha256"), contract.get("semantic_projection_test_vector_sha256"))
    add_check(failures, "policy_module_path_exact", policy.get("contract_module_path"), str(args.contract_module.resolve()))
    add_check(failures, "policy_module_sha_current", policy.get("contract_module_sha256"), sha256(args.contract_module) if args.contract_module.is_file() else None)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "receipt_path": str(args.receipt.resolve()),
        "receipt_sha256": sha256(args.receipt) if args.receipt.is_file() else None,
        "contract_module_path": str(args.contract_module.resolve()),
        "contract_module_sha256": sha256(args.contract_module) if args.contract_module.is_file() else None,
        "policy_report_path": str(args.policy_report.resolve()),
        "policy_report_sha256": sha256(args.policy_report) if args.policy_report.is_file() else None,
        "contract_version": contract.get("version"),
        "contract_sha256": contract.get("sha256"),
        "semantic_projection_version": contract.get("semantic_projection_version"),
        "semantic_projection_test_vector_sha256": contract.get("semantic_projection_test_vector_sha256"),
        "target_rows": len(expected_markers),
        "stale_rows": int(receipt.get("stale_rows") or 0),
        "provenance_rows": len(expected_provenance_rows),
        "semantic_provenance_rows": sum(row.get("freshness_mode") == "semantic_projection" for row in expected_provenance_rows),
        "failure_count": len(failures),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "This validator is read-only and requires the receipt to match current contract, policy, provenance, and document bytes.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "target_rows": report["target_rows"],
        "stale_rows": report["stale_rows"],
        "provenance_rows": report["provenance_rows"],
        "failure_count": report["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
