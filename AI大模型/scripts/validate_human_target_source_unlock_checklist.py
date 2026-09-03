#!/usr/bin/env python3
"""Validate human target source unlock checklist remains fail-closed."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = AI_ROOT / "datasets" / "governance" / "human_target_source_unlock_checklist.jsonl"
REPORT = AI_ROOT / "reports" / "human_target_source_unlock_checklist_report.json"
INDEX = AI_ROOT / "reports" / "human_target_blocked_source_manifest_index.json"
BLOCKED_INDEX_VALIDATION = AI_ROOT / "reports" / "human_target_blocked_source_manifest_index_validation_report.json"
OUT = AI_ROOT / "reports" / "human_target_source_unlock_checklist_validation_report.json"
BUILDER = AI_ROOT / "scripts" / "build_human_target_source_unlock_checklist.py"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("build_human_target_source_unlock_checklist", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load builder: {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate human target source unlock checklist")
    parser.add_argument("--checklist", type=Path, default=CHECKLIST)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--blocked-index-validation", type=Path, default=BLOCKED_INDEX_VALIDATION)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.checklist)
    report_payload = load_json(args.report)
    blocked_index_validation = load_json(args.blocked_index_validation)
    builder = load_builder()
    row_created_at = {
        str(row.get("source_id")): str(row.get("created_at"))
        for row in rows
        if isinstance(row, dict) and row.get("source_id") and row.get("created_at")
    }
    expected_rows, expected_report = builder.build_checklist(
        index_path=args.index,
        output_path=args.checklist,
        report_created_at=report_payload.get("created_at"),
        row_created_at=row_created_at,
    )
    failures: list[dict[str, Any]] = []

    fail_if(rows != expected_rows, failures, "checklist_matches_current_builder_projection", rows, expected_rows)
    fail_if(report_payload != expected_report, failures, "report_matches_current_builder_projection", report_payload, expected_report)
    fail_if(len(rows) != 7, failures, "checklist_row_count", len(rows), 7)
    fail_if(
        blocked_index_validation.get("success") is not True,
        failures,
        "blocked_source_manifest_index_validation_success",
        blocked_index_validation.get("success"),
        True,
    )
    fail_if(
        blocked_index_validation.get("index_matches_current_builder_projection") is not True,
        failures,
        "blocked_source_manifest_index_projection_valid",
        blocked_index_validation.get("index_matches_current_builder_projection"),
        True,
    )
    fail_if(
        blocked_index_validation.get("split_manifests_match_current_builder_projection") is not True,
        failures,
        "blocked_split_manifests_projection_valid",
        blocked_index_validation.get("split_manifests_match_current_builder_projection"),
        True,
    )
    expected_by_source = {
        str(row.get("source_id")): row
        for row in expected_rows
        if isinstance(row, dict)
    }
    seen: set[str] = set()
    for row in rows:
        source_id = row.get("source_id")
        if source_id in seen:
            failures.append({"check": "duplicate_source_id", "source_id": source_id})
        seen.add(str(source_id))
        if row.get("ready_to_unlock") is not False:
            failures.append({"check": "ready_to_unlock_false", "source_id": source_id})
        for field in ("claim_eligible", "customer_ready", "release_ready"):
            if row.get(field) is not False:
                failures.append({"check": f"{field}_false", "source_id": source_id})
        if not row.get("missing_steps"):
            failures.append({"check": "missing_steps_present", "source_id": source_id})
        expected_row = expected_by_source.get(str(source_id))
        if expected_row:
            fail_if(
                row.get("required_steps") != expected_row.get("required_steps"),
                failures,
                f"{source_id}_required_steps_match_builder",
                row.get("required_steps"),
                expected_row.get("required_steps"),
            )
            fail_if(
                row.get("missing_steps") != expected_row.get("missing_steps"),
                failures,
                f"{source_id}_missing_steps_match_required",
                row.get("missing_steps"),
                expected_row.get("missing_steps"),
            )
            fail_if(
                row.get("source_manifest_path") != expected_row.get("source_manifest_path"),
                failures,
                f"{source_id}_source_manifest_path_matches_index",
                row.get("source_manifest_path"),
                expected_row.get("source_manifest_path"),
            )
    report = {
        "local_only": True,
        "success": not failures,
        "checked_checklist": rel(args.checklist),
        "checked_report": rel(args.report),
        "checked_index": rel(args.index),
        "checked_blocked_index_validation": rel(args.blocked_index_validation),
        "builder_contract": rel(BUILDER),
        "checklist_matches_current_builder_projection": rows == expected_rows,
        "report_matches_current_builder_projection": report_payload == expected_report,
        "blocked_source_manifest_index_validation_success": blocked_index_validation.get("success") is True,
        "blocked_source_manifest_index_projection_valid": blocked_index_validation.get("index_matches_current_builder_projection") is True,
        "blocked_split_manifests_projection_valid": blocked_index_validation.get("split_manifests_match_current_builder_projection") is True,
        "expected_checklist_rows": len(expected_rows),
        "checklist_rows": len(rows),
        "ready_to_unlock_rows": sum(1 for row in rows if row.get("ready_to_unlock") is True),
        "failures": failures,
        "failure_count": len(failures),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation only proves generated checklist rows remain blocked.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "checklist_rows": report["checklist_rows"], "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
