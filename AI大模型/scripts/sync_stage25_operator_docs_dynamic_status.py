#!/usr/bin/env python3
"""Synchronize marked Stage 25 current-state documentation rows."""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import importlib.util
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

try:
    from stage25_operator_docs_sync_contract import (
        CONTRACT_VERSION,
        LOCK_PATH_ID,
        OUTPUT_PATH_ID,
        SLOTS,
        TARGET_SPECS,
        UPSTREAM_INPUT_SPECS,
        build_provenance,
        marker_for,
        marker_specs,
        observed_provenance_sha256,
        policy_contract,
        provenance_sha256,
        resolve_path,
    )
except ImportError:
    from scripts.stage25_operator_docs_sync_contract import (
        CONTRACT_VERSION,
        LOCK_PATH_ID,
        OUTPUT_PATH_ID,
        SLOTS,
        TARGET_SPECS,
        UPSTREAM_INPUT_SPECS,
        build_provenance,
        marker_for,
        marker_specs,
        observed_provenance_sha256,
        policy_contract,
        provenance_sha256,
        resolve_path,
    )


AI_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = AI_ROOT.parent
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")
TARGET_PATHS = {
    namespace: resolve_path(path_id)
    for namespace, path_id in TARGET_SPECS
}
INPUT_PATHS = {
    role: resolve_path(path_id)
    for role, path_id, _kind in UPSTREAM_INPUT_SPECS
}
NEXT_OPERATOR = TARGET_PATHS["next"]
DAILY_REPORT = TARGET_PATHS["daily"]
OUTPUT = resolve_path(OUTPUT_PATH_ID)
LOCK_PATH = resolve_path(LOCK_PATH_ID)
RUNNER_SCRIPT = INPUT_PATHS["runner_contract"]
OVERALL_SCRIPT = INPUT_PATHS["overall_contract"]
HANDOFF_SCRIPT = INPUT_PATHS["handoff_contract"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_lines() -> tuple[dict[str, str], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    runner = load_module(RUNNER_SCRIPT, "stage25_sync_runner_contract")
    overall = load_module(OVERALL_SCRIPT, "stage25_sync_overall_contract")
    handoff = load_module(HANDOFF_SCRIPT, "stage25_sync_handoff_contract")
    safety_guard = load_module(INPUT_PATHS["safety_guard_contract"], "stage25_sync_safety_guard_contract")
    command_count = len(getattr(runner, "COMMANDS", []))
    summary_count = len(getattr(overall, "INPUTS", {}))
    handoff_rows = handoff.collect_rows()
    bundle_rows = len(handoff_rows)
    freshness_verified_rows = sum(row.get("freshness_check_mode") == "current_filesystem" for row in handoff_rows)
    freshness_exempt_rows = bundle_rows - freshness_verified_rows

    release = load_json(AI_ROOT / "reports" / "local_release_manifest.json")
    data_lake = load_json(AI_ROOT / "reports" / "data_lake_manifest.json")
    live = load_json(AI_ROOT / "reports" / "data_lake_live_content_integrity_validation_report.json")
    human_backlog = load_json(INPUT_PATHS["human_backlog"])
    approved = load_json(ENZYME_DB_ROOT / "stage25_approved_apply_report_20260806.json")
    approved_validation = load_json(ENZYME_DB_ROOT / "stage25_approved_apply_report_validation_20260806.json")
    post_source_receipt = load_json(INPUT_PATHS["post_source_receipt"])
    post_source_validation = load_json(INPUT_PATHS["post_source_validation"])
    post_source_dry_run = load_json(INPUT_PATHS["post_source_dry_run"])

    required = [
        ("command_count_positive", command_count > 0, command_count),
        ("summary_count_positive", summary_count > 0, summary_count),
        ("handoff_rows_present", bundle_rows > 0, bundle_rows),
        ("handoff_single_exemption", freshness_exempt_rows == 1, freshness_exempt_rows),
        ("release_ready_false", release.get("release_ready") is False, release.get("release_ready")),
        ("release_artifact_parity", release.get("artifact_count") == data_lake.get("artifact_rows"), {"release": release.get("artifact_count"), "data_lake": data_lake.get("artifact_rows")}),
        ("live_success", live.get("success") is True and live.get("failure_count") == 0, {"success": live.get("success"), "failure_count": live.get("failure_count")}),
        ("live_artifact_parity", live.get("artifact_rows") == data_lake.get("artifact_rows"), {"live": live.get("artifact_rows"), "data_lake": data_lake.get("artifact_rows")}),
        ("human_backlog_success", human_backlog.get("success") is True and not (human_backlog.get("failures") or []), {"success": human_backlog.get("success"), "failures": human_backlog.get("failures")}),
        ("human_backlog_rows_valid", all(isinstance(human_backlog.get(field), int) and not isinstance(human_backlog.get(field), bool) and human_backlog.get(field) >= 0 for field in ("open_items", "total_required_rows", "total_completed_rows", "total_missing_rows")), {"open_items": human_backlog.get("open_items"), "required": human_backlog.get("total_required_rows"), "completed": human_backlog.get("total_completed_rows"), "missing": human_backlog.get("total_missing_rows")}),
        ("human_backlog_gates_closed", human_backlog.get("safe_for_model_claim") is False and human_backlog.get("release_ready") is False, {"safe_for_model_claim": human_backlog.get("safe_for_model_claim"), "release_ready": human_backlog.get("release_ready")}),
        ("approved_apply_blocked", approved.get("status") == "blocked" and approved_validation.get("apply_executed") is False and approved_validation.get("external_sqlite_mutated") is False, {"status": approved.get("status"), "apply_executed": approved_validation.get("apply_executed"), "external_sqlite_mutated": approved_validation.get("external_sqlite_mutated")}),
        ("post_source_receipt_valid", post_source_receipt.get("command_rows") == 62 and isinstance(post_source_receipt.get("command_contract_sha256"), str) and len(post_source_receipt.get("command_contract_sha256")) == 64 and post_source_receipt.get("sqlite_write_command_rows") == 0 and post_source_receipt.get("rerun_ready") is True and post_source_receipt.get("safe_for_model_claim") is False and post_source_receipt.get("release_ready") is False, {"command_rows": post_source_receipt.get("command_rows"), "command_contract_sha256": post_source_receipt.get("command_contract_sha256"), "sqlite_write_command_rows": post_source_receipt.get("sqlite_write_command_rows"), "rerun_ready": post_source_receipt.get("rerun_ready")}),
        ("post_source_validation_valid", post_source_validation.get("command_rows") == 62 and post_source_validation.get("command_contract_valid") is True and post_source_validation.get("receipt_valid") is True and post_source_validation.get("failure_count") == 0 and post_source_validation.get("sqlite_write_command_rows") == 0 and post_source_validation.get("safe_for_model_claim") is False and post_source_validation.get("release_ready") is False, {"command_rows": post_source_validation.get("command_rows"), "command_contract_valid": post_source_validation.get("command_contract_valid"), "receipt_valid": post_source_validation.get("receipt_valid"), "failure_count": post_source_validation.get("failure_count")}),
        ("post_source_dry_run_valid", post_source_dry_run.get("audit_valid") is True and post_source_dry_run.get("command_rows") == 62 and post_source_dry_run.get("command_contract_sha256") == post_source_receipt.get("command_contract_sha256") and post_source_dry_run.get("sqlite_write_command_rows") == 0 and post_source_dry_run.get("commands_executed") is False and post_source_dry_run.get("outputs_freshness_verified") is False and post_source_dry_run.get("rerun_completion_receipted") is False and post_source_dry_run.get("ready_for_source_drop_rerun") is False and post_source_dry_run.get("safe_for_model_claim") is False and post_source_dry_run.get("release_ready") is False, {"audit_valid": post_source_dry_run.get("audit_valid"), "command_rows": post_source_dry_run.get("command_rows"), "command_contract_sha256": post_source_dry_run.get("command_contract_sha256"), "commands_executed": post_source_dry_run.get("commands_executed"), "ready_for_source_drop_rerun": post_source_dry_run.get("ready_for_source_drop_rerun")}),
    ]
    for check, valid, observed in required:
        if not valid:
            failures.append({"check": check, "observed": observed, "expected": True})

    failure_count = int(approved.get("failure_count") or 0)
    artifact_count = release.get("artifact_count")
    source_rows = data_lake.get("source_artifact_rows")
    unique_rows = data_lake.get("artifact_rows")
    deduplicated_rows = data_lake.get("deduplicated_input_rows")
    strict_rows = live.get("strict_verified_rows")
    volatile_rows = live.get("volatile_existence_only_rows")
    mismatch_rows = sum(int(live.get(field) or 0) for field in ("missing_rows", "unsafe_path_rows", "size_mismatch_rows", "sha256_mismatch_rows", "row_mismatch_rows"))
    guard_links = len(getattr(safety_guard, "REQUIRED_GUARD_LINKS", {}))
    backlog_open_items = human_backlog.get("open_items")
    backlog_missing_rows = human_backlog.get("total_missing_rows")
    post_source_command_sha = post_source_receipt.get("command_contract_sha256")

    lines = {
        "next:latest-release": f"- Latest apply/release attempt: Stage 25 approved apply executor ran with `--execute` requested and remained blocked (`failure_count={failure_count}`, `apply_executed=false`, `external_sqlite_mutated=false`); current local release manifest has `artifact_count={artifact_count}`, `release_ready=false`.",
        "next:core-counts": f"- Current fields remain `command_count={command_count}`, `summary_count={summary_count}`, `bundle_rows={bundle_rows}`, `freshness_verified_rows={freshness_verified_rows}`, `freshness_exempt_rows={freshness_exempt_rows}`, and `artifact_count={artifact_count}`.",
        "next:data-lake": f"- Current data lake is `{source_rows}` source rows, `{unique_rows}` unique artifacts, and `{deduplicated_rows}` deduplicated rows; live=`{strict_rows} strict + {volatile_rows} volatile / {mismatch_rows} mismatch`; safety links=`{guard_links}/0`; `release_ready=false`.",
        "next:human-backlog": f"- `human_backlog_open_items={backlog_open_items}`; `human_backlog_missing_rows={backlog_missing_rows}`.",
        "next:post-source": f"- Post-source receipt=`post_source_command_rows={post_source_receipt.get('command_rows')}`/`post_source_command_contract_sha256={post_source_command_sha}`/`post_source_sqlite_write_command_rows=0`; validation=`receipt_valid=true`/`command_contract_valid=true`/`failure_count=0`; dry-run=`post_source_commands_executed=false`/`outputs_freshness_verified=false`/`rerun_completion_receipted=false`/`ready_for_source_drop_rerun=false`; `release_ready=false`.",
        "daily:latest-release": f"- Latest apply/release attempt: approved apply executor ran with `--execute` requested and remains `status=blocked` with `failure_count={failure_count}`; `apply_executed=false`, `external_sqlite_mutated=false`. Current local release manifest has `artifact_count={artifact_count}`, `release_ready=false`.",
        "daily:core-counts": f"- 当前标准字段为 `command_count={command_count}`、`summary_count={summary_count}`、`bundle_rows={bundle_rows}`、`freshness_verified_rows={freshness_verified_rows}`、`freshness_exempt_rows={freshness_exempt_rows}`、`artifact_count={artifact_count}`。",
        "daily:data-lake": f"- 当前 data lake=`{source_rows} source/{unique_rows} unique/{deduplicated_rows} deduplicated`、live=`{strict_rows} strict+{volatile_rows} volatile/{mismatch_rows} mismatch`、safety links=`{guard_links}/0`、`release_ready=false`。",
        "daily:human-backlog": f"- `human_backlog_open_items={backlog_open_items}`；`human_backlog_missing_rows={backlog_missing_rows}`。",
        "daily:post-source": f"- Post-source receipt=`post_source_command_rows={post_source_receipt.get('command_rows')}`/`post_source_command_contract_sha256={post_source_command_sha}`/`post_source_sqlite_write_command_rows=0`；validation=`receipt_valid=true`/`command_contract_valid=true`/`failure_count=0`；dry-run=`post_source_commands_executed=false`/`outputs_freshness_verified=false`/`rerun_completion_receipted=false`/`ready_for_source_drop_rerun=false`；`release_ready=false`。",
    }
    return lines, failures


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_bytes_atomic(path: Path, payload: bytes, prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=prefix, dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_json_atomic(path: Path, payload: dict[str, Any], *, apply_receipt_test_hooks: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.receipt-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        delay_seconds = float(os.environ.get("STAGE25_DOC_SYNC_TEST_RECEIPT_DELAY_SECONDS", "0") or 0) if apply_receipt_test_hooks else 0.0
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        if apply_receipt_test_hooks and os.environ.get("STAGE25_DOC_SYNC_TEST_RECEIPT_FAIL_STAGE") == "before_replace":
            raise RuntimeError("simulated_receipt_failure_before_replace")
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def plan_document(path: Path, namespace: str, expected: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bytes, bytes]:
    original = path.read_bytes()
    lines = original.decode("utf-8").splitlines()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for slot in SLOTS:
        marker = marker_for(slot)
        indexes = [index for index, line in enumerate(lines) if line == marker]
        if len(indexes) != 1:
            failures.append({"check": "marker_exactly_once", "path": str(path), "marker": marker, "observed": len(indexes), "expected": 1})
            continue
        target_index = indexes[0] + 1
        if target_index >= len(lines):
            failures.append({"check": "marker_has_target_line", "path": str(path), "marker": marker})
            continue
        expected_line = expected[f"{namespace}:{slot}"]
        stale = lines[target_index] != expected_line
        results.append({"path": str(path.resolve()), "slot": slot, "stale": stale})
        if stale:
            lines[target_index] = expected_line
    proposed = ("\n".join(lines) + "\n").encode("utf-8")
    return results, failures, original, proposed


def commit_documents(plans: list[dict[str, Any]]) -> tuple[bool, bool, list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    temp_paths: dict[Path, Path] = {}
    replaced: list[Path] = []
    rollback_performed = False
    fail_after = int(os.environ.get("STAGE25_DOC_SYNC_TEST_FAIL_AFTER", "0") or 0)
    try:
        for plan in plans:
            current = plan["path"].read_bytes()
            if current != plan["original"]:
                failures.append({
                    "check": "document_changed_after_plan",
                    "path": str(plan["path"]),
                    "observed_sha256": sha256_bytes(current),
                    "expected_sha256": sha256_bytes(plan["original"]),
                })
        if failures:
            return False, False, failures
        for plan in plans:
            path = plan["path"]
            if plan["original"] == plan["proposed"]:
                continue
            descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.sync-", dir=path.parent)
            temp_path = Path(temp_name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(plan["proposed"])
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, path.stat().st_mode)
            temp_paths[path] = temp_path
        for path, temp_path in temp_paths.items():
            os.replace(temp_path, path)
            replaced.append(path)
            if fail_after and len(replaced) >= fail_after:
                raise RuntimeError(f"simulated_commit_failure_after_{fail_after}")
        for parent in {path.parent for path in replaced}:
            fsync_directory(parent)
        return True, False, failures
    except Exception as exc:
        failures.append({"check": "document_transaction_commit", "observed": f"{type(exc).__name__}:{exc}", "expected": "all replacements succeed"})
        if replaced:
            rollback_performed = True
        for plan in plans:
            if plan["path"] in replaced:
                write_bytes_atomic(plan["path"], plan["original"], f".{plan['path'].name}.rollback-")
        return False, rollback_performed, failures
    finally:
        for temp_path in temp_paths.values():
            if temp_path.exists():
                temp_path.unlink()


def restore_documents(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for plan in plans:
        path = plan["path"]
        try:
            if path.read_bytes() != plan["original"]:
                write_bytes_atomic(path, plan["original"], f".{path.name}.rollback-")
        except Exception as exc:
            failures.append({
                "check": "receipt_failure_document_rollback",
                "path": str(path),
                "observed": f"{type(exc).__name__}:{exc}",
                "expected": "original bytes restored",
            })
    return failures


def transaction_journal_path(output: Path) -> Path:
    return output.with_name(f".{output.name}.transaction.json")


def write_transaction_journal(path: Path, output: Path, plans: list[dict[str, Any]]) -> None:
    payload = {
        "schema_version": 1,
        "output_path": str(output.resolve()),
        "documents": [
            {
                "path": str(plan["path"].resolve()),
                "original_sha256": sha256_bytes(plan["original"]),
                "proposed_sha256": sha256_bytes(plan["proposed"]),
                "original_base64": base64.b64encode(plan["original"]).decode("ascii"),
                "proposed_base64": base64.b64encode(plan["proposed"]).decode("ascii"),
            }
            for plan in plans
            if plan["original"] != plan["proposed"]
        ],
    }
    write_json_atomic(path, payload, apply_receipt_test_hooks=False)


def remove_transaction_journal(path: Path) -> None:
    if path.exists():
        path.unlink()
        fsync_directory(path.parent)


def recover_transaction_journal(
    journal_path: Path,
    output: Path,
    target_paths: list[Path],
) -> tuple[bool, str, list[dict[str, Any]]]:
    if not journal_path.exists():
        return False, "none", []
    failures: list[dict[str, Any]] = []
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, "invalid", [{
            "check": "transaction_journal_loads",
            "path": str(journal_path),
            "observed": f"{type(exc).__name__}:{exc}",
            "expected": "valid JSON transaction journal",
        }]
    if journal.get("output_path") != str(output.resolve()):
        failures.append({"check": "transaction_journal_output_path", "observed": journal.get("output_path"), "expected": str(output.resolve())})
    rows = journal.get("documents") if isinstance(journal.get("documents"), list) else []
    row_by_path = {str(row.get("path")): row for row in rows if isinstance(row, dict)}
    expected_changed_paths = {str(path.resolve()) for path in target_paths if str(path.resolve()) in row_by_path}
    if set(row_by_path) != expected_changed_paths:
        failures.append({"check": "transaction_journal_target_paths", "observed": sorted(row_by_path), "expected": sorted(expected_changed_paths)})
    decoded_rows: list[tuple[Path, bytes, bytes]] = []
    for path_text, row in row_by_path.items():
        path = Path(path_text)
        try:
            original = base64.b64decode(str(row.get("original_base64") or ""), validate=True)
            proposed = base64.b64decode(str(row.get("proposed_base64") or ""), validate=True)
        except Exception as exc:
            failures.append({"check": "transaction_journal_document_decodes", "path": path_text, "observed": f"{type(exc).__name__}:{exc}", "expected": "valid base64"})
            continue
        if row.get("original_sha256") != sha256_bytes(original) or row.get("proposed_sha256") != sha256_bytes(proposed):
            failures.append({"check": "transaction_journal_document_sha", "path": path_text, "expected": "encoded bytes match journal SHA"})
            continue
        current = path.read_bytes() if path.is_file() else b""
        if current not in (original, proposed):
            failures.append({"check": "transaction_recovery_document_conflict", "path": path_text, "observed_sha256": sha256_bytes(current), "expected": [sha256_bytes(original), sha256_bytes(proposed)]})
        decoded_rows.append((path, original, proposed))
    if failures:
        return False, "conflict", failures

    receipt = load_json(output)
    receipt_hashes = {
        str(Path(str(row.get("path"))).resolve()): row.get("after_sha256")
        for row in receipt.get("document_hashes") or []
        if row.get("path")
    }
    receipt_committed = bool(decoded_rows) and all(
        path.read_bytes() == proposed and receipt_hashes.get(str(path.resolve())) == sha256_bytes(proposed)
        for path, _original, proposed in decoded_rows
    )
    mode = "finalized_committed_receipt" if receipt_committed else "rolled_back_uncommitted_documents"
    if not receipt_committed:
        for path, original, _proposed in decoded_rows:
            if path.read_bytes() != original:
                write_bytes_atomic(path, original, f".{path.name}.recovery-")
    remove_transaction_journal(journal_path)
    return True, mode, []


def acquire_sync_lock(path: Path, timeout_seconds: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(0.05)


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize Stage 25 operator-doc current-state rows")
    parser.add_argument("--next-operator", type=Path, default=NEXT_OPERATOR)
    parser.add_argument("--daily-report", type=Path, default=DAILY_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lock-path", type=Path, default=LOCK_PATH)
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    lock_handle = acquire_sync_lock(args.lock_path, args.lock_timeout_seconds)
    lock_acquired = lock_handle is not None
    failures: list[dict[str, Any]] = []
    expected: dict[str, str] = {}
    provenance_rows: list[dict[str, Any]] = []
    journal_path = transaction_journal_path(args.output)
    recovery_performed = False
    recovery_mode = "none"
    if not lock_acquired:
        failures.append({"check": "sync_lock_acquired", "path": str(args.lock_path), "expected": True})
    else:
        recovery_performed, recovery_mode, recovery_failures = recover_transaction_journal(
            journal_path,
            args.output,
            [args.next_operator, args.daily_report],
        )
        failures.extend(recovery_failures)
        if not recovery_failures:
            provenance_rows, provenance_failures = build_provenance()
            failures.extend(provenance_failures)
            expected, upstream_failures = expected_lines()
            failures.extend(upstream_failures)
    results: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    for path, namespace in ((args.next_operator, "next"), (args.daily_report, "daily")) if lock_acquired else ():
        if not path.is_file():
            failures.append({"check": "document_exists", "path": str(path), "expected": True})
            continue
        doc_results, doc_failures, original, proposed = plan_document(path, namespace, expected)
        results.extend(doc_results)
        failures.extend(doc_failures)
        plans.append({"path": path, "original": original, "proposed": proposed})
    test_mutation = os.environ.get("STAGE25_DOC_SYNC_TEST_MUTATE_AFTER_PLAN")
    if test_mutation and plans:
        target = next((plan for plan in plans if plan["path"].name.startswith(test_mutation)), plans[0])
        with target["path"].open("ab") as handle:
            handle.write(b"external-concurrent-edit\n")
    detected_stale_rows = sum(row["stale"] for row in results)
    if args.check and detected_stale_rows:
        failures.append({"check": "documents_current", "observed": detected_stale_rows, "expected": 0})
    transaction_applied = False
    rollback_performed = False
    if not args.check and not failures:
        changed_plans = [plan for plan in plans if plan["original"] != plan["proposed"]]
        if changed_plans:
            try:
                write_transaction_journal(journal_path, args.output, plans)
            except Exception as exc:
                failures.append({"check": "transaction_journal_commit", "path": str(journal_path), "observed": f"{type(exc).__name__}:{exc}", "expected": "durable journal before document replace"})
        if not failures:
            transaction_applied, rollback_performed, commit_failures = commit_documents(plans)
            failures.extend(commit_failures)
            if transaction_applied and os.environ.get("STAGE25_DOC_SYNC_TEST_CRASH_AFTER_DOCUMENT_COMMIT") == "1":
                os._exit(91)
    for row in results:
        row["detected_stale"] = bool(row["stale"])
        if transaction_applied:
            row["stale"] = False
    document_hashes = []
    for plan in plans:
        final = plan["path"].read_bytes()
        document_hashes.append({
            "path": str(plan["path"].resolve()),
            "before_sha256": sha256_bytes(plan["original"]),
            "proposed_sha256": sha256_bytes(plan["proposed"]),
            "after_sha256": sha256_bytes(final),
        })
    contract = policy_contract()
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "contract_version": CONTRACT_VERSION,
        "contract_sha256": contract["sha256"],
        "canonical_output_path": str(OUTPUT),
        "observed_output_path": str(args.output.resolve()),
        "canonical_lock_path": str(LOCK_PATH),
        "check_only": args.check,
        "lock_path": str(args.lock_path.resolve()),
        "lock_acquired": lock_acquired,
        "canonical_targets": [
            {"namespace": namespace, "path_id": path_id, "path": str(resolve_path(path_id))}
            for namespace, path_id in TARGET_SPECS
        ],
        "observed_targets": [
            {"namespace": "next", "path": str(args.next_operator.resolve())},
            {"namespace": "daily", "path": str(args.daily_report.resolve())},
        ],
        "slots": list(SLOTS),
        "marker_specs": marker_specs(),
        "provenance_rows": provenance_rows,
        "provenance_row_count": len(provenance_rows),
        "provenance_sha256": provenance_sha256(provenance_rows),
        "observed_provenance_sha256": observed_provenance_sha256(provenance_rows),
        "target_rows": len(results),
        "detected_stale_rows": detected_stale_rows,
        "stale_rows": 0 if transaction_applied else detected_stale_rows,
        "changed_rows": detected_stale_rows if transaction_applied else 0,
        "transaction_applied": transaction_applied,
        "rollback_performed": rollback_performed,
        "transaction_journal_path": str(journal_path.resolve()),
        "recovery_performed": recovery_performed,
        "recovery_mode": recovery_mode,
        "document_hashes": document_hashes,
        "results": results,
        "failure_count": len(failures),
        "failures": failures,
        "receipt_atomic_commit": True,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Only six marker-bound current-state lines may be synchronized from local validated reports.",
    }
    receipt_committed = False
    receipt_error = ""
    try:
        if lock_acquired or args.output.resolve() != OUTPUT.resolve():
            write_json_atomic(args.output, report)
            receipt_committed = True
            remove_transaction_journal(journal_path)
    except Exception as exc:
        receipt_error = f"{type(exc).__name__}:{exc}"
        if transaction_applied and any(plan["original"] != plan["proposed"] for plan in plans):
            rollback_performed = True
            restore_failures = restore_documents(plans)
            failures.extend(restore_failures)
            if not restore_failures:
                remove_transaction_journal(journal_path)
        report["success"] = False
        report["rollback_performed"] = rollback_performed
        report["failure_count"] = len(failures) + 1
        report["failures"] = failures + [{
            "check": "receipt_atomic_commit",
            "path": str(args.output),
            "observed": receipt_error,
            "expected": "atomic receipt committed while sync lock is held",
        }]
    finally:
        if lock_handle is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()
    print(json.dumps({
        "success": report["success"] and receipt_committed,
        "check_only": report["check_only"],
        "target_rows": report["target_rows"],
        "stale_rows": report["stale_rows"],
        "changed_rows": report["changed_rows"],
        "transaction_applied": report["transaction_applied"],
        "rollback_performed": report["rollback_performed"],
        "failure_count": report["failure_count"],
        "receipt_committed": receipt_committed,
        "receipt_error": receipt_error,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if report["success"] and receipt_committed else 1


if __name__ == "__main__":
    raise SystemExit(main())
