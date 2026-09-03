#!/usr/bin/env python3
"""Build a fail-closed FoldX physical smoke bootstrap report.

This script records whether FoldX can be executed locally. It does not create
a runtime receipt, approve a license, import labels, or open model claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_backend_config import default_ddg_config_path


AI_ROOT = Path(__file__).resolve().parents[1]
CONFIG = default_ddg_config_path()
LICENSE_REPORT = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"
EXECUTABLE_PROBE = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
READINESS = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"
RUNTIME_RECEIPT_VALIDATION = AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json"
PREFLIGHT = AI_ROOT / "reports" / "ddg_physical_runtime_receipt_preflight_report.json"
PARSER_CONTRACT = AI_ROOT / "reports" / "foldx_buildmodel_parser_contract_report.json"
EXECUTION_PLAN = AI_ROOT / "datasets" / "curation" / "ddg_backend_execution_plan.jsonl"
REPORT = AI_ROOT / "reports" / "foldx_physical_smoke_bootstrap_report.json"
MARKDOWN = AI_ROOT / "reports" / "foldx_physical_smoke_bootstrap.md"
SMOKE_DIR = AI_ROOT / "cache" / "advanced_features" / "ddg_physical_smoke" / "foldx" / "bootstrap_probe"
REQUIRED_ARTIFACTS = [
    "parameters.json",
    "input_structure.sha256",
    "mutation_list.json",
    "ddg_table.json",
    "runtime.log",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def license_record(report: dict[str, Any]) -> dict[str, Any]:
    for row in report.get("records") or []:
        if isinstance(row, dict) and row.get("review_item_id") == "foreign_tool:foldx":
            return row
    return {}


def foldx_probe_row(report: dict[str, Any]) -> dict[str, Any]:
    for row in report.get("backend_rows") or []:
        if isinstance(row, dict) and row.get("backend") == "foldx":
            return row
    return {}


def backend_row(report: dict[str, Any], backend: str) -> dict[str, Any]:
    for row in report.get("backends") or []:
        if isinstance(row, dict) and row.get("backend") == backend:
            return row
    return {}


def ready_execution_plan_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("backend") == "foldx" and row.get("status") == "ready_to_execute"
    ]


def first_executable_from_probe(row: dict[str, Any]) -> str | None:
    for item in row.get("candidate_executables") or []:
        if item.get("found") and item.get("path"):
            return str(item["path"])
    found = shutil.which("foldx") or shutil.which("FoldX")
    return found


def artifact_map(path: Path) -> dict[str, str]:
    result = {}
    for name in REQUIRED_ARTIFACTS:
        artifact = path / name
        if artifact.exists() and artifact.is_file():
            result[rel(artifact)] = sha256(artifact)
    return result


def run_help_probe(executable: str, timeout: int) -> dict[str, Any]:
    try:
        process = subprocess.run(
            [executable, "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            cwd=str(Path(executable).parent),
        )
        return {
            "attempted": True,
            "command": [executable, "--help"],
            "returncode": process.returncode,
            "stdout_head": process.stdout[:2000],
            "stderr_head": process.stderr[:2000],
            "succeeded": process.returncode == 0,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"attempted": True, "command": [executable, "--help"], "error": str(exc), "succeeded": False}


def build_markdown(report: dict[str, Any]) -> str:
    blockers = report.get("blockers") or []
    return "\n".join(
        [
            "# FoldX Physical Smoke Bootstrap",
            "",
            f"Created: `{report['created_at']}`",
            "",
            f"- Config enabled: `{report['config_enabled']}`",
            f"- License local evaluation approved: `{report['license_local_evaluation_approved']}`",
            f"- Executable found: `{report['foldx_executable_found']}`",
            f"- Help probe succeeded: `{report['help_probe_succeeded']}`",
            f"- Runtime receipt ready: `{report['runtime_receipt_ready']}`",
            f"- Parser contract ready: `{report['parser_contract_ready']}`",
            f"- Ready execution plan rows: `{report['ready_execution_plan_rows']}`",
            f"- Physical smoke passed: `{report['physical_smoke_passed']}`",
            f"- Blockers: `{', '.join(blockers) or 'none'}`",
            "",
            "`safe_for_model_claim=false`; `release_ready=false`.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FoldX physical smoke bootstrap")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--license-report", type=Path, default=LICENSE_REPORT)
    parser.add_argument("--executable-probe", type=Path, default=EXECUTABLE_PROBE)
    parser.add_argument("--readiness", type=Path, default=READINESS)
    parser.add_argument("--runtime-receipt-validation", type=Path, default=RUNTIME_RECEIPT_VALIDATION)
    parser.add_argument("--preflight", type=Path, default=PREFLIGHT)
    parser.add_argument("--parser-contract", type=Path, default=PARSER_CONTRACT)
    parser.add_argument("--execution-plan", type=Path, default=EXECUTION_PLAN)
    parser.add_argument("--output", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--smoke-dir", type=Path, default=SMOKE_DIR)
    parser.add_argument("--output-dir", dest="smoke_dir", type=Path, default=SMOKE_DIR)
    parser.add_argument("--execute", action="store_true", help="Reserved for a fully gated future BuildModel smoke")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()

    config = load_json(args.config)
    backend_cfg = ((config.get("backends") or {}).get("foldx") or {})
    license_row = license_record(load_json(args.license_report))
    probe = foldx_probe_row(load_json(args.executable_probe))
    readiness_row = backend_row(load_json(args.readiness), "foldx")
    receipt_validation = load_json(args.runtime_receipt_validation)
    preflight_row = backend_row(load_json(args.preflight), "foldx")
    parser_contract = load_json(args.parser_contract)
    execution_rows = load_jsonl(args.execution_plan)
    ready_plans = ready_execution_plan_rows(execution_rows)
    executable = first_executable_from_probe(probe)
    config_enabled = bool(backend_cfg.get("enabled"))
    license_ok = bool(license_row.get("approved_for_local_evaluation"))
    runtime_receipt_ready = "foldx" in set(receipt_validation.get("backends_with_approved_runtime") or [])
    parser_contract_ready = bool(parser_contract.get("parser_contract_ready"))
    preflight_ready_for_smoke = bool(preflight_row.get("ready_to_run_physical_ddg_smoke"))
    executable_found = bool(executable and Path(executable).exists())
    executable_bit = bool(executable and os.access(executable, os.X_OK))

    help_probe = {"attempted": False, "succeeded": False}
    if executable and executable_bit:
        help_probe = run_help_probe(executable, args.timeout_seconds)

    blockers = [
        reason
        for reason, blocked in [
            ("foldx_backend_disabled_in_config", not config_enabled),
            ("foldx_license_not_approved_for_local_evaluation", not license_ok),
            ("foldx_executable_not_found", not executable_found),
            ("foldx_executable_not_runnable", executable_found and not executable_bit),
            ("foldx_help_probe_not_successful", executable_found and not help_probe.get("succeeded")),
            ("foldx_runtime_receipt_not_approved", not runtime_receipt_ready),
            ("foldx_runtime_preflight_not_ready_for_smoke", not preflight_ready_for_smoke),
            ("foldx_parser_contract_not_ready", not parser_contract_ready),
            ("foldx_execution_plan_has_no_ready_rows", not ready_plans),
            ("foldx_buildmodel_physical_smoke_not_executed", True),
        ]
        if blocked
    ]
    ready_to_execute_buildmodel = (
        config_enabled
        and license_ok
        and executable_found
        and executable_bit
        and bool(help_probe.get("succeeded"))
        and runtime_receipt_ready
        and preflight_ready_for_smoke
        and parser_contract_ready
        and bool(ready_plans)
    )
    status = "ready_to_execute_after_explicit_execute" if ready_to_execute_buildmodel else "blocked_missing_runtime_evidence"

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "backend": "foldx",
        "config": str(args.config),
        "status": status,
        "config_enabled": config_enabled,
        "license_review_item_id": "foreign_tool:foldx",
        "license_decision_status": license_row.get("decision_status"),
        "authorization_status": license_row.get("authorization_status"),
        "license_local_evaluation_approved": license_ok,
        "foldx_executable_found": executable_found,
        "foldx_executable_path": executable,
        "foldx_executable_bit": executable_bit,
        "technical_probe_ready": bool(probe.get("ready_for_ddg_execution") or help_probe.get("succeeded")),
        "readiness_ready_for_execution": bool(readiness_row.get("ready_for_execution")),
        "runtime_receipt_ready": runtime_receipt_ready,
        "preflight_ready_for_smoke": preflight_ready_for_smoke,
        "parser_contract_ready": parser_contract_ready,
        "parser_contract_report": str(args.parser_contract),
        "execution_plan_rows": sum(1 for row in execution_rows if row.get("backend") == "foldx"),
        "ready_execution_plan_rows": len(ready_plans),
        "help_probe_attempted": bool(help_probe.get("attempted")),
        "help_probe_succeeded": bool(help_probe.get("succeeded")),
        "help_probe": help_probe,
        "execute_requested": bool(args.execute),
        "execute_attempted": False,
        "buildmodel_executed": False,
        "ddg_protocol_executed": False,
        "ddg_table_rows": 0,
        "physical_smoke_passed": False,
        "smoke_dir": rel(args.smoke_dir),
        "required_artifacts": REQUIRED_ARTIFACTS,
        "artifact_sha256": artifact_map(args.smoke_dir),
        "blockers": blockers,
        "ready_to_write_runtime_receipt": False,
        "ready_for_ddg_smoke": ready_to_execute_buildmodel,
        "training_import_written_rows": 0,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "FoldX bootstrap is a fail-closed technical probe. A true runtime breakthrough still requires license/config/probe review, BuildModel smoke artifacts with checksums, and a formal runtime receipt.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(build_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "foldx_executable_found": report["foldx_executable_found"],
                "help_probe_succeeded": report["help_probe_succeeded"],
                "physical_smoke_passed": report["physical_smoke_passed"],
                "blockers": len(blockers),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
