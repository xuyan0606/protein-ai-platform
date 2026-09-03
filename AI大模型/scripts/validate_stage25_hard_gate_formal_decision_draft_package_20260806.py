#!/usr/bin/env python3
"""Validate Stage 25 hard-gate formal decision draft package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT_DRAFT = AI_ROOT / "datasets" / "curation" / "kwb_venus15b_strict_holdout_review_decisions.stage25_draft_20260806.jsonl"
SUBSTRATE_DRAFT = AI_ROOT / "datasets" / "curation" / "substrate_identity_review_decisions.stage25_draft_20260806.jsonl"
STRICT_FORMAL = AI_ROOT / "datasets" / "curation" / "kwb_venus15b_strict_holdout_review_decisions.jsonl"
SUBSTRATE_FORMAL = AI_ROOT / "datasets" / "curation" / "substrate_identity_review_decisions.jsonl"
BRIDGE_REPORT = AI_ROOT / "reports" / "hard_gate_decision_benchmark_bridge_report.json"
OUTPUT = AI_ROOT / "reports" / "stage25_hard_gate_formal_decision_draft_package_validation_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def validate_draft_rows(rows: list[dict[str, Any]], expected_rows: int, lane: str, failures: list[dict[str, Any]]) -> None:
    fail_if(len(rows) != expected_rows, failures, f"{lane}.row_count", len(rows), expected_rows)
    keys = [str(row.get("review_key") or "") for row in rows]
    fail_if(len(set(keys)) != len(keys), failures, f"{lane}.unique_review_keys", len(set(keys)), len(keys))
    for index, row in enumerate(rows, start=1):
        prefix = f"{lane}.rows[{index}]"
        fail_if(row.get("decision") != "needs_more_info", failures, f"{prefix}.decision", row.get("decision"), "needs_more_info")
        fail_if(row.get("review_draft") is not True, failures, f"{prefix}.review_draft_true", row.get("review_draft"), True)
        for field in ("reviewer", "reviewed_at", "review_basis"):
            fail_if(str(row.get(field) or "") != "", failures, f"{prefix}.{field}_empty", row.get(field), "")
        fail_if(row.get("acceptance_receipt") is not None, failures, f"{prefix}.acceptance_receipt_null", row.get("acceptance_receipt"), None)
        for flag in ("safe_for_model_claim", "release_ready"):
            fail_if(row.get(flag) is not False, failures, f"{prefix}.{flag}_false", row.get(flag), False)
        policy = str(row.get("draft_policy") or "")
        for term in ("draft only", "formal decision file", "human review"):
            fail_if(term not in policy, failures, f"{prefix}.policy_contains.{term}", policy, f"contains {term}")


def main() -> int:
    failures: list[dict[str, Any]] = []
    strict_draft = load_jsonl(STRICT_DRAFT)
    substrate_draft = load_jsonl(SUBSTRATE_DRAFT)
    strict_formal = load_jsonl(STRICT_FORMAL)
    substrate_formal = load_jsonl(SUBSTRATE_FORMAL)
    bridge = load_json(BRIDGE_REPORT) if BRIDGE_REPORT.exists() else {}

    validate_draft_rows(strict_draft, 3, "strict", failures)
    validate_draft_rows(substrate_draft, 9, "substrate", failures)
    fail_if(len(strict_formal) != 0, failures, "strict_formal_rows_zero", len(strict_formal), 0)
    fail_if(len(substrate_formal) != 0, failures, "substrate_formal_rows_zero", len(substrate_formal), 0)
    fail_if(bridge.get("intake_rows_written") != 0, failures, "bridge_intake_rows_written_zero", bridge.get("intake_rows_written"), 0)
    fail_if(bridge.get("training_import_written_rows") != 0, failures, "bridge_training_import_written_rows_zero", bridge.get("training_import_written_rows"), 0)
    for flag in ("safe_for_model_claim", "release_ready"):
        fail_if(bridge.get(flag) is not False, failures, f"bridge.{flag}_false", bridge.get(flag), False)

    report = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_hard_gate_formal_decision_draft_package_validation",
        "stage": 25,
        "draft_package_valid": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "strict_draft_rows": len(strict_draft),
        "substrate_draft_rows": len(substrate_draft),
        "formal_decision_rows_written": 0,
        "strict_formal_rows": len(strict_formal),
        "substrate_formal_rows": len(substrate_formal),
        "bridge_intake_rows_written": bridge.get("intake_rows_written"),
        "training_import_written_rows": bridge.get("training_import_written_rows"),
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "draft_package_valid": report["draft_package_valid"], "failure_count": report["failure_count"], "strict_draft_rows": report["strict_draft_rows"], "substrate_draft_rows": report["substrate_draft_rows"], "formal_decision_rows_written": report["formal_decision_rows_written"]}, ensure_ascii=False, sort_keys=True))
    return 0 if report["draft_package_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
