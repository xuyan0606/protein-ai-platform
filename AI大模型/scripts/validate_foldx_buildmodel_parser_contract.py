#!/usr/bin/env python3
"""Validate the FoldX BuildModel parser contract remains parser-only."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "foldx_buildmodel_parser_contract_report.json"
OUT = AI_ROOT / "reports" / "foldx_buildmodel_parser_contract_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FoldX parser contract")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    failures: list[dict[str, Any]] = []
    fail_if(not report, failures, "report_present", str(args.report), "existing report")
    fail_if(report.get("parser_contract_ready") is not True, failures, "parser_contract_ready", report.get("parser_contract_ready"), True)
    fail_if(report.get("parse_status") != "parsed", failures, "parse_status", report.get("parse_status"), "parsed")
    fail_if(int(report.get("parsed_rows") or 0) != 1, failures, "parsed_rows", report.get("parsed_rows"), 1)
    fail_if(report.get("first_ddg_kcal_mol") != -1.234, failures, "first_ddg_kcal_mol", report.get("first_ddg_kcal_mol"), -1.234)
    fail_if(report.get("negative_ddg_is_stabilizing") is not True, failures, "negative_ddg_is_stabilizing", report.get("negative_ddg_is_stabilizing"), True)
    for field in (
        "foldx_runtime_ready",
        "foldx_executable_found",
        "safe_for_training_import",
        "safe_for_model_claim",
        "release_ready",
    ):
        fail_if(report.get(field) is not False, failures, f"{field}_false", report.get(field), False)
    fail_if(int(report.get("training_import_written_rows") or 0) != 0, failures, "training_import_written_rows_zero", report.get("training_import_written_rows"), 0)
    files = report.get("fixture_files") if isinstance(report.get("fixture_files"), list) else []
    fail_if(len(files) != 3, failures, "fixture_file_count", len(files), 3)
    for item in files:
        path = AI_ROOT / str(item.get("path") or "")
        fail_if(not path.exists(), failures, "fixture_file_exists", str(path), "exists")
        fail_if(not item.get("sha256"), failures, "fixture_sha256_present", item, "sha256")

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "parser_contract_ready": report.get("parser_contract_ready") is True,
        "parsed_rows": int(report.get("parsed_rows") or 0),
        "foldx_runtime_ready": False,
        "failures": failures,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "FoldX parser validation is an ingestion-contract check only. Runtime remains blocked until a licensed binary, config, probe, smoke artifacts, and runtime receipt exist.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "parsed_rows": validation["parsed_rows"],
        "foldx_runtime_ready": validation["foldx_runtime_ready"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
