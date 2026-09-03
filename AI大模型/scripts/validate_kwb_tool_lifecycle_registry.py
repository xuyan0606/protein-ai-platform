#!/usr/bin/env python3
"""Validate the KWB tool lifecycle registry remains fail-closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
JSONL = AI_ROOT / "datasets" / "governance" / "kwb_tool_lifecycle_registry.jsonl"
REPORT = AI_ROOT / "reports" / "kwb_tool_lifecycle_registry_report.json"
OUT = AI_ROOT / "reports" / "kwb_tool_lifecycle_registry_validation_report.json"

REQUIRED_FIELDS = (
    "tool_id",
    "tool_family",
    "runtime_type",
    "install_status",
    "license_status",
    "probe_status",
    "smoke_status",
    "register_status",
    "blockers",
    "install_probe_register_split",
    "requires_execution_receipt",
    "requires_schema_contract",
    "production_allowed",
    "agent_exposure_allowed",
    "training_label_source",
    "safe_for_training_import",
    "safe_for_model_claim",
    "release_ready",
)
FORBIDDEN_TRUE_FIELDS = (
    "production_allowed",
    "agent_exposure_allowed",
    "training_label_source",
    "safe_for_training_import",
    "safe_for_model_claim",
    "release_ready",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate KWB tool lifecycle registry")
    parser.add_argument("--jsonl", type=Path, default=JSONL)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    rows = read_jsonl(args.jsonl)
    report = load_json(args.report)
    fail_if(not args.jsonl.exists(), failures, "registry_jsonl_present", str(args.jsonl), "exists")
    fail_if(not args.report.exists(), failures, "registry_report_present", str(args.report), "exists")
    fail_if(len(rows) < 8, failures, "minimum_tool_rows", len(rows), ">= 8")
    fail_if(report.get("tool_rows") != len(rows), failures, "report_row_count_matches_jsonl", report.get("tool_rows"), len(rows))

    ids = [row.get("tool_id") for row in rows]
    fail_if(len(ids) != len(set(ids)), failures, "unique_tool_ids", ids, "unique")

    for index, row in enumerate(rows):
        missing = [field for field in REQUIRED_FIELDS if field not in row]
        fail_if(bool(missing), failures, "required_fields", {"row": index, "tool_id": row.get("tool_id"), "missing": missing}, [])
        for field in FORBIDDEN_TRUE_FIELDS:
            fail_if(row.get(field) is True, failures, "forbidden_true_field", {"row": index, "tool_id": row.get("tool_id"), "field": field}, False)
        fail_if(row.get("install_probe_register_split") is not True, failures, "install_probe_register_split_true", row.get("tool_id"), True)
        fail_if(row.get("requires_execution_receipt") is not True, failures, "requires_execution_receipt_true", row.get("tool_id"), True)
        fail_if(row.get("requires_schema_contract") is not True, failures, "requires_schema_contract_true", row.get("tool_id"), True)
        fail_if(not isinstance(row.get("blockers"), list) or not row.get("blockers"), failures, "blockers_non_empty", row.get("tool_id"), "non-empty list")

    fail_if(report.get("production_allowed_rows") != 0, failures, "report_production_allowed_zero", report.get("production_allowed_rows"), 0)
    fail_if(report.get("agent_exposure_allowed_rows") != 0, failures, "report_agent_exposure_zero", report.get("agent_exposure_allowed_rows"), 0)
    fail_if(report.get("training_label_source_rows") != 0, failures, "report_training_label_source_zero", report.get("training_label_source_rows"), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "report_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "report_release_ready_false", report.get("release_ready"), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "tool_rows": len(rows),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "tool_rows": len(rows), "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
