#!/usr/bin/env python3
"""Validate FoldX physical smoke bootstrap remains fail-closed unless real evidence exists."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "foldx_physical_smoke_bootstrap_report.json"
OUT = AI_ROOT / "reports" / "foldx_physical_smoke_bootstrap_validation_report.json"
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


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FoldX physical smoke bootstrap")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    failures: list[dict[str, Any]] = []
    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(report.get("backend") != "foldx", failures, "backend", report.get("backend"), "foldx")
    fail_if(report.get("status") not in {"blocked_missing_runtime_evidence", "ready_to_execute_after_explicit_execute"}, failures, "status", report.get("status"), "known status")
    fail_if(report.get("required_artifacts") != REQUIRED_ARTIFACTS, failures, "required_artifacts", report.get("required_artifacts"), REQUIRED_ARTIFACTS)
    for field in (
        "execute_attempted",
        "buildmodel_executed",
        "ddg_protocol_executed",
        "physical_smoke_passed",
        "ready_to_write_runtime_receipt",
        "safe_for_training_import",
        "safe_for_model_claim",
        "release_ready",
    ):
        fail_if(report.get(field) is not False, failures, f"{field}_false", report.get(field), False)
    fail_if(int(report.get("training_import_written_rows") or 0) != 0, failures, "training_import_written_rows_zero", report.get("training_import_written_rows"), 0)
    fail_if(int(report.get("ddg_table_rows") or 0) != 0, failures, "ddg_table_rows_zero", report.get("ddg_table_rows"), 0)
    if report.get("physical_smoke_passed") is False:
        blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
        fail_if(not blockers, failures, "blocked_smoke_has_blockers", blockers, "non-empty blockers")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "foldx_executable_found": bool(report.get("foldx_executable_found")),
        "help_probe_succeeded": bool(report.get("help_probe_succeeded")),
        "physical_smoke_passed": False,
        "status": report.get("status"),
        "runtime_receipt_ready": bool(report.get("runtime_receipt_ready")),
        "parser_contract_ready": bool(report.get("parser_contract_ready")),
        "ready_execution_plan_rows": int(report.get("ready_execution_plan_rows") or 0),
        "blocker_count": len(report.get("blockers") or []),
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "FoldX bootstrap validation confirms probe evidence without allowing parser-only or missing-binary evidence to become runtime readiness.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": validation["success"],
                "foldx_executable_found": validation["foldx_executable_found"],
                "physical_smoke_passed": validation["physical_smoke_passed"],
                "failures": len(failures),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
