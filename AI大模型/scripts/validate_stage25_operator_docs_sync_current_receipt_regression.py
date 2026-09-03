#!/usr/bin/env python3
"""Prove current operator-doc sync receipt validation fails closed in isolation."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType


AI_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = AI_ROOT.parent
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")
CONTRACT_MODULE = AI_ROOT / "scripts" / "stage25_operator_docs_sync_contract.py"
POLICY_VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_operator_docs_sync_contract_policy.py"
CURRENT_VALIDATOR = AI_ROOT / "scripts" / "validate_stage25_operator_docs_sync_current_receipt.py"
CANONICAL_RECEIPT = AI_ROOT / "reports" / "stage25_operator_docs_dynamic_status_sync_report.json"
OUTPUT = AI_ROOT / "reports" / "stage25_operator_docs_sync_current_receipt_regression_report.json"


def load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("stage25_operator_docs_sync_regression_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load contract module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_validator(
    receipt: Path,
    contract_module: Path,
    policy_report: Path,
    ai_root: Path,
    platform_root: Path,
    enzyme_db_root: Path,
    output: Path,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    process = subprocess.run(
        [
            sys.executable,
            str(CURRENT_VALIDATOR),
            "--receipt", str(receipt),
            "--contract-module", str(contract_module),
            "--policy-report", str(policy_report),
            "--ai-root", str(ai_root),
            "--platform-root", str(platform_root),
            "--enzyme-db-root", str(enzyme_db_root),
            "--output", str(output),
        ],
        cwd=AI_ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    report = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return process, report


def main() -> int:
    canonical_module = load_module(CONTRACT_MODULE)
    canonical_receipt = json.loads(CANONICAL_RECEIPT.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="stage25-doc-sync-current-") as temp_dir:
        temp_root = Path(temp_dir)
        fixture_ai = temp_root / "AI大模型"
        fixture_platform = temp_root / "酶蛋白AI平台"
        fixture_enzyme = temp_root / "酶数据库"
        fixture_ai.mkdir(parents=True)
        fixture_platform.mkdir(parents=True)
        fixture_enzyme.mkdir(parents=True)
        fixture_contract = canonical_module.resolve_path(
            "ai:scripts/stage25_operator_docs_sync_contract.py",
            ai_root=fixture_ai,
            platform_root=fixture_platform,
            enzyme_db_root=fixture_enzyme,
        )
        for _role, path_id, _kind in canonical_module.UPSTREAM_INPUT_SPECS:
            source = canonical_module.resolve_path(path_id)
            target = canonical_module.resolve_path(
                path_id,
                ai_root=fixture_ai,
                platform_root=fixture_platform,
                enzyme_db_root=fixture_enzyme,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for _namespace, path_id in canonical_module.TARGET_SPECS:
            source = canonical_module.resolve_path(path_id)
            target = canonical_module.resolve_path(
                path_id,
                ai_root=fixture_ai,
                platform_root=fixture_platform,
                enzyme_db_root=fixture_enzyme,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        fixture_module = load_module(fixture_contract)
        fixture_receipt_path = fixture_module.resolve_path(
            fixture_module.OUTPUT_PATH_ID,
            ai_root=fixture_ai,
            platform_root=fixture_platform,
            enzyme_db_root=fixture_enzyme,
        )
        fixture_lock_path = fixture_module.resolve_path(
            fixture_module.LOCK_PATH_ID,
            ai_root=fixture_ai,
            platform_root=fixture_platform,
            enzyme_db_root=fixture_enzyme,
        )
        fixture_targets = [
            {
                "namespace": namespace,
                "path_id": path_id,
                "path": str(fixture_module.resolve_path(path_id, ai_root=fixture_ai, platform_root=fixture_platform, enzyme_db_root=fixture_enzyme)),
            }
            for namespace, path_id in fixture_module.TARGET_SPECS
        ]
        fixture_provenance, provenance_failures = fixture_module.build_provenance(
            ai_root=fixture_ai,
            platform_root=fixture_platform,
            enzyme_db_root=fixture_enzyme,
        )
        if provenance_failures:
            raise RuntimeError(f"fixture provenance failed: {provenance_failures}")
        fixture_receipt = copy.deepcopy(canonical_receipt)
        fixture_receipt["canonical_output_path"] = str(fixture_receipt_path)
        fixture_receipt["observed_output_path"] = str(fixture_receipt_path)
        fixture_receipt["canonical_lock_path"] = str(fixture_lock_path)
        fixture_receipt["lock_path"] = str(fixture_lock_path)
        fixture_receipt["canonical_targets"] = fixture_targets
        fixture_receipt["observed_targets"] = [
            {"namespace": row["namespace"], "path": row["path"]}
            for row in fixture_targets
        ]
        path_map = {
            str(canonical_module.resolve_path(path_id)): row["path"]
            for row, (_namespace, path_id) in zip(fixture_targets, fixture_module.TARGET_SPECS)
        }
        for row in fixture_receipt.get("results") or []:
            row["path"] = path_map[str(row["path"])]
        for row in fixture_receipt.get("document_hashes") or []:
            row["path"] = path_map[str(row["path"])]
        fixture_receipt["provenance_rows"] = fixture_provenance
        fixture_receipt["provenance_row_count"] = len(fixture_provenance)
        fixture_receipt["provenance_sha256"] = fixture_module.provenance_sha256(fixture_provenance)
        fixture_receipt["observed_provenance_sha256"] = fixture_module.observed_provenance_sha256(fixture_provenance)
        fixture_receipt_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_receipt_path.write_text(json.dumps(fixture_receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        fixture_policy = temp_root / "fixture-policy.json"
        policy_process = subprocess.run(
            [sys.executable, str(POLICY_VALIDATOR), "--contract-module", str(fixture_contract), "--output", str(fixture_policy)],
            cwd=AI_ROOT,
            text=True,
            capture_output=True,
            timeout=300,
        )
        control_output = temp_root / "control-validation.json"
        control_process, control_report = run_validator(
            fixture_receipt_path,
            fixture_contract,
            fixture_policy,
            fixture_ai,
            fixture_platform,
            fixture_enzyme,
            control_output,
        )
        control_valid = policy_process.returncode == 0 and control_process.returncode == 0 and control_report.get("success") is True

        raw_only_source = fixture_module.resolve_path(
            "ai:reports/data_lake_manifest.json",
            ai_root=fixture_ai,
            platform_root=fixture_platform,
            enzyme_db_root=fixture_enzyme,
        )
        raw_only_payload = json.loads(raw_only_source.read_text(encoding="utf-8"))
        raw_only_payload["_non_consumed_regression_field"] = "raw-sha-drift-only"
        raw_only_source.write_text(json.dumps(raw_only_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raw_only_output = temp_root / "raw-only-validation.json"
        raw_only_process, raw_only_report = run_validator(
            fixture_receipt_path,
            fixture_contract,
            fixture_policy,
            fixture_ai,
            fixture_platform,
            fixture_enzyme,
            raw_only_output,
        )
        raw_only_change_valid = raw_only_process.returncode == 0 and raw_only_report.get("success") is True

        source_drift_specs = (
            ("local_release_consumed_field_drift", "ai:reports/local_release_manifest.json", "artifact_count"),
            ("data_lake_consumed_field_drift", "ai:reports/data_lake_manifest.json", "artifact_rows"),
            ("live_integrity_consumed_field_drift", "ai:reports/data_lake_live_content_integrity_validation_report.json", "success"),
            ("post_source_receipt_consumed_field_drift", "ai:reports/stage25_post_source_drop_rerun_receipt_20260806.json", "command_rows"),
            ("post_source_validation_consumed_field_drift", "ai:reports/stage25_post_source_drop_rerun_receipt_validation_20260806.json", "receipt_valid"),
            ("post_source_dry_run_consumed_field_drift", "ai:reports/stage25_post_source_drop_rerun_dry_run_audit_validation_20260806.json", "audit_valid"),
        )
        for index, (case_id, path_id, field) in enumerate(source_drift_specs, start=1):
            source_path = fixture_module.resolve_path(
                path_id,
                ai_root=fixture_ai,
                platform_root=fixture_platform,
                enzyme_db_root=fixture_enzyme,
            )
            original_source = source_path.read_text(encoding="utf-8")
            source_payload = json.loads(original_source)
            value = source_payload[field]
            source_payload[field] = (not value) if isinstance(value, bool) else int(value) + 1
            source_path.write_text(json.dumps(source_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output_path = temp_root / f"source-drift-{index}-validation.json"
            process, validation = run_validator(
                fixture_receipt_path,
                fixture_contract,
                fixture_policy,
                fixture_ai,
                fixture_platform,
                fixture_enzyme,
                output_path,
            )
            source_path.write_text(original_source, encoding="utf-8")
            checks = [str(row.get("check") or "") for row in validation.get("failures") or []]
            results.append({
                "case_id": case_id,
                "tamper_rejected": process.returncode != 0 and "provenance_projection_current" in checks,
                "expected_check": "provenance_projection_current",
                "expected_check_observed": "provenance_projection_current" in checks,
                "failure_count": int(validation.get("failure_count") or 0),
            })

        cases = [
            ("stale_sync_script_sha", lambda data: data["provenance_rows"][0].update({"sha256": "0" * 64}), "provenance_file_sha_current"),
            ("file_bound_source_report_sha_drift", lambda data: next(row for row in data["provenance_rows"] if row["role"] == "approved_apply").update({"sha256": "1" * 64}), "provenance_file_sha_current"),
            ("semantic_source_projection_drift", lambda data: next(row for row in data["provenance_rows"] if row["role"] == "data_lake")["projection"].update({"artifact_rows": -1}), "provenance_projection_current"),
            ("semantic_projection_mode_drift", lambda data: next(row for row in data["provenance_rows"] if row["role"] == "local_release").update({"freshness_mode": "file_sha256"}), "provenance_projection_contract_exact"),
            ("semantic_projection_fields_drift", lambda data: next(row for row in data["provenance_rows"] if row["role"] == "live_integrity")["projection_fields"].pop(), "provenance_projection_contract_exact"),
            ("semantic_projection_digest_drift", lambda data: next(row for row in data["provenance_rows"] if row["role"] == "data_lake").update({"projection_sha256": "4" * 64}), "provenance_projection_sha_current"),
            ("target_path_drift", lambda data: data["observed_targets"][0].update({"path": str(temp_root / "forged.md")}), "observed_targets_exact"),
            ("marker_set_drift", lambda data: data["marker_specs"].pop(), "marker_specs_exact"),
            ("lock_path_drift", lambda data: data.update({"lock_path": str(temp_root / "forged.lock")}), "lock_path_exact"),
            ("output_path_drift", lambda data: data.update({"observed_output_path": str(temp_root / "forged.json")}), "observed_output_path_exact"),
            ("document_after_sha_drift", lambda data: data["document_hashes"][0].update({"after_sha256": "2" * 64}), "document_after_sha_current"),
            ("provenance_digest_drift", lambda data: data.update({"provenance_sha256": "3" * 64}), "provenance_digest_exact"),
        ]
        for index, (case_id, mutate, expected_check) in enumerate(cases, start=1):
            tampered = copy.deepcopy(fixture_receipt)
            mutate(tampered)
            receipt_path = temp_root / f"case-{index}-receipt.json"
            output_path = temp_root / f"case-{index}-validation.json"
            receipt_path.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            process, validation = run_validator(
                receipt_path,
                fixture_contract,
                fixture_policy,
                fixture_ai,
                fixture_platform,
                fixture_enzyme,
                output_path,
            )
            checks = [str(row.get("check") or "") for row in validation.get("failures") or []]
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
        "success": control_valid and raw_only_change_valid and passed == len(results),
        "isolated_fixture": True,
        "control_valid": control_valid,
        "raw_only_change_valid": raw_only_change_valid,
        "case_rows": len(results),
        "passed_rows": passed,
        "failed_rows": len(results) - passed,
        "real_inputs_mutated": False,
        "results": results,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "The regression copies all contract inputs into temporary roots and never edits canonical documents, reports, or scripts.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report["success"],
        "control_valid": report["control_valid"],
        "raw_only_change_valid": report["raw_only_change_valid"],
        "case_rows": report["case_rows"],
        "passed_rows": report["passed_rows"],
        "failed_rows": report["failed_rows"],
        "real_inputs_mutated": report["real_inputs_mutated"],
        "output": str(OUTPUT),
    }, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
