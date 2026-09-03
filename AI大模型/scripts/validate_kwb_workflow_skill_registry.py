#!/usr/bin/env python3
"""Validate KWB workflow skills are documentation/receipt workflows only."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
JSONL = AI_ROOT / "datasets" / "governance" / "kwb_workflow_skill_registry.jsonl"
REPORT = AI_ROOT / "reports" / "kwb_workflow_skill_registry_report.json"
OUT = AI_ROOT / "reports" / "kwb_workflow_skill_registry_validation_report.json"


REQUIRED_SKILLS = {
    "enzyme_mutation_prioritization",
    "ddg_backend_runtime_probe",
    "wet_lab_feedback_intake_review",
    "numbering_review_formalization",
    "five_head_model_gate_review",
}
FORBIDDEN_TRUE_FIELDS = (
    "writes_training_labels",
    "writes_formal_decisions_without_human",
    "production_execution_allowed",
    "safe_for_training_import",
    "safe_for_model_claim",
    "release_ready",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate KWB workflow skill registry")
    parser.add_argument("--jsonl", type=Path, default=JSONL)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    failures: list[dict[str, Any]] = []
    rows = read_jsonl(args.jsonl)
    report = load_json(args.report)
    skill_ids = {row.get("skill_id") for row in rows}
    fail_if(not args.jsonl.exists(), failures, "skill_registry_jsonl_present", str(args.jsonl), "exists")
    fail_if(not args.report.exists(), failures, "skill_registry_report_present", str(args.report), "exists")
    fail_if(skill_ids != REQUIRED_SKILLS, failures, "required_skill_ids", sorted(skill_ids), sorted(REQUIRED_SKILLS))
    fail_if(report.get("skill_rows") != len(rows), failures, "report_skill_rows_match", report.get("skill_rows"), len(rows))

    for row in rows:
        path = AI_ROOT / str(row.get("path", ""))
        fail_if(not path.exists(), failures, "skill_file_exists", row.get("path"), "exists")
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        fail_if("## 禁止动作" not in text, failures, "skill_forbidden_actions_section", row.get("skill_id"), "present")
        fail_if("safe_for_model_claim=false" not in text, failures, "skill_fail_closed_text", row.get("skill_id"), "safe_for_model_claim=false")
        fail_if(row.get("requires_receipt") is not True, failures, "requires_receipt_true", row.get("skill_id"), True)
        fail_if(row.get("requires_validator") is not True, failures, "requires_validator_true", row.get("skill_id"), True)
        fail_if(not row.get("validators"), failures, "validators_non_empty", row.get("skill_id"), "non-empty")
        for field in FORBIDDEN_TRUE_FIELDS:
            fail_if(row.get(field) is True, failures, "forbidden_true_field", {"skill_id": row.get("skill_id"), "field": field}, False)

    fail_if(report.get("production_execution_allowed_rows") != 0, failures, "report_production_execution_zero", report.get("production_execution_allowed_rows"), 0)
    fail_if(report.get("training_write_allowed_rows") != 0, failures, "report_training_write_zero", report.get("training_write_allowed_rows"), 0)
    fail_if(report.get("safe_for_model_claim") is not False, failures, "report_safe_for_model_claim_false", report.get("safe_for_model_claim"), False)
    fail_if(report.get("release_ready") is not False, failures, "report_release_ready_false", report.get("release_ready"), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "success": not failures,
        "skill_rows": len(rows),
        "skill_files_present": sum(1 for row in rows if (AI_ROOT / str(row.get("path", ""))).exists()),
        "failures": failures,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "skill_rows": len(rows), "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if validation["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
