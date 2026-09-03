#!/usr/bin/env python3
"""Build Stage 25 family-specific apply transaction plans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ENZYME_DB_ROOT = Path("/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库")
DESIGN = AI_ROOT / "datasets" / "governance" / "stage25_family_apply_importer_design_20260806.jsonl"
PAPER_PLAN = ENZYME_DB_ROOT / "stage25_paper_only_apply_plan_20260806.json"
SOURCE_READINESS = AI_ROOT / "reports" / "stage25_source_drop_extraction_readiness_candidate_validation_20260806.json"
OUTPUT = AI_ROOT / "datasets" / "governance" / "stage25_family_apply_transaction_plans_20260806.jsonl"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise SystemExit(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def main() -> int:
    designs = load_jsonl(DESIGN)
    paper_plan = load_json(PAPER_PLAN)
    source_readiness = load_json(SOURCE_READINESS)
    source_ready = int(source_readiness.get("ready_for_sqlite_apply_rows") or 0)
    paper_insert_count = int(paper_plan.get("paper_insert_count") or 0)

    rows = []
    for design in designs:
        family = design.get("family")
        blockers = []
        if source_ready == 0:
            blockers.append("source_drop_extraction_not_ready")
        if paper_plan.get("status") != "ready_for_human_review":
            blockers.append("paper_only_apply_plan_not_ready")
        if paper_insert_count == 0:
            blockers.append("paper_insert_plan_empty")
        if design.get("ready_to_apply_now") is not True:
            blockers.append("family_design_not_ready_to_apply_now")
        rows.append({
            "transaction_plan_id": f"stage25_family_apply_transaction_plan_{family}_20260806",
            "stage": 25,
            "family": family,
            "target_db": design.get("target_db"),
            "write_tables": design.get("write_tables") or [],
            "required_preflight": design.get("required_preflight") or [],
            "transaction_steps": design.get("transaction_steps") or [],
            "status": "blocked",
            "blockers": blockers,
            "source_ready_for_sqlite_apply_rows": source_ready,
            "paper_insert_count": paper_insert_count,
            "write_operation_count": 0,
            "sqlite_write_sql": [],
            "backup_required_before_apply": True,
            "begin_immediate_required": True,
            "rollback_required_on_any_failure": True,
            "apply_executed": False,
            "external_sqlite_mutated": False,
            "formal_decision_rows_written": 0,
            "export_safe_released": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Family transaction plan scaffold only; no SQLite writes or SQL statements are emitted until source, allowlist, backup, duplicate and integrity gates close.",
        })

    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "plan_rows": len(rows), "ready_to_apply_rows": 0, "write_operation_count": 0}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
