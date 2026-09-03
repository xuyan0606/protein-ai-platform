#!/usr/bin/env python3
"""Validate the human target / antibody contract gap report."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "human_target_contract_gap_validation_report.json"
REPORT = AI_ROOT / "reports" / "human_target_contract_gap_report.json"
BUILDER = AI_ROOT / "scripts" / "build_human_target_contract_gap_report.py"
BACKEND_CONTRACTS = AI_ROOT.parent / "backend" / "app" / "tools" / "human_target_antibody_contracts.py"
EXPECTED_SECTIONS = {"human_target_intelligence", "antibody_humanization"}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        try:
            return str(Path("..") / path.relative_to(AI_ROOT.parent))
        except ValueError:
            return str(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("build_human_target_contract_gap_report", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load builder: {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate human target / antibody contract gap report")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    builder = load_builder()
    expected_report = builder.build_report(created_at=report.get("created_at"))
    expected_contracts = {
        name
        for names in builder.EXPECTED_CONTRACTS.values()
        for name in names
    }
    expected_backend_contracts = set(builder.IMPLEMENTED_SCHEMA_ONLY)
    product_lines = report.get("product_lines") if isinstance(report.get("product_lines"), dict) else {}
    backend_schema_contracts = (
        report.get("backend_schema_contracts")
        if isinstance(report.get("backend_schema_contracts"), dict)
        else {}
    )
    expected_product_lines = expected_report.get("product_lines") or {}
    failures: list[dict[str, Any]] = []

    fail_if(not report, failures, "gap_report_present", rel(args.report), "existing JSON report")
    fail_if(not BACKEND_CONTRACTS.exists(), failures, "backend_contract_source_present", rel(BACKEND_CONTRACTS), "existing backend contract module")
    fail_if(report != expected_report, failures, "report_matches_current_builder_projection", report, expected_report)
    fail_if(set(product_lines) != EXPECTED_SECTIONS, failures, "product_line_sections_match_contract", sorted(product_lines), sorted(EXPECTED_SECTIONS))
    fail_if(
        set(backend_schema_contracts) != expected_backend_contracts,
        failures,
        "backend_schema_contract_set_matches_builder_contract",
        sorted(backend_schema_contracts),
        sorted(expected_backend_contracts),
    )
    for section in ("human_target_intelligence", "antibody_humanization"):
        block = product_lines.get(section, {}) if isinstance(product_lines.get(section), dict) else {}
        expected_block = expected_product_lines.get(section, {}) if isinstance(expected_product_lines.get(section), dict) else {}
        if not str(block.get("status") or "").startswith("schema_only_contracts"):
            failures.append({"check": "schema_only_status", "section": section, "observed": block.get("status")})
        if not block.get("missing_runtime_or_source_contracts"):
            failures.append({"check": "runtime_or_source_gaps_present", "section": section})
        if block != expected_block:
            failures.append({
                "check": "section_matches_current_builder_projection",
                "section": section,
                "observed": block,
                "expected": expected_block,
            })
        present = set(block.get("schema_only_contracts_present") or [])
        missing = set(block.get("missing_schema_contracts") or [])
        expected_names = set(builder.EXPECTED_CONTRACTS[section])
        fail_if(
            present | missing != expected_names,
            failures,
            f"{section}_schema_contract_partition_complete",
            sorted(present | missing),
            sorted(expected_names),
        )
        fail_if(
            bool(present & missing),
            failures,
            f"{section}_schema_contract_partition_disjoint",
            sorted(present & missing),
            [],
        )
        if section == "antibody_humanization" and len(block.get("schema_only_contracts_present") or []) < 4:
            failures.append({
                "check": "antibody_schema_contracts_present",
                "observed": block.get("schema_only_contracts_present"),
                "expected": ">=4 schema-only contracts",
            })

    expected_gate_snapshot = expected_report.get("gate_snapshot") or {}
    fail_if(
        report.get("gate_snapshot") != expected_gate_snapshot,
        failures,
        "gate_snapshot_matches_current_source_reports",
        report.get("gate_snapshot"),
        expected_gate_snapshot,
    )
    fail_if(report.get("local_only") is not True, failures, "local_only_true", report.get("local_only"), True)
    fail_if(
        "does not imply real source retrieval" not in str(report.get("policy") or ""),
        failures,
        "policy_preserves_gap_only_boundary",
        report.get("policy"),
        "contains gap-only / no real source retrieval boundary",
    )
    fail_if(
        any(name not in backend_schema_contracts for name in expected_contracts),
        failures,
        "all_product_contracts_have_backend_schema_entry",
        sorted(expected_contracts - set(backend_schema_contracts)),
        [],
    )

    validation = {
        "local_only": True,
        "success": not failures,
        "checked_report": rel(args.report),
        "builder_contract": rel(BUILDER),
        "backend_contract_source": rel(BACKEND_CONTRACTS),
        "report_matches_current_builder_projection": report == expected_report,
        "expected_product_line_sections": sorted(EXPECTED_SECTIONS),
        "observed_product_line_sections": sorted(product_lines),
        "expected_backend_schema_contracts": sorted(expected_backend_contracts),
        "observed_backend_schema_contracts": sorted(backend_schema_contracts),
        "source_gate_snapshot": expected_gate_snapshot,
        "failures": failures,
        "failure_count": len(failures),
        "human_target_gap_sections": len(product_lines),
        "schema_only_contract_count": sum(1 for ready in (report.get("backend_schema_contracts") or {}).values() if ready),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation proves the file is a gap report only. It does not create real target or antibody capability.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
