#!/usr/bin/env python3
"""Validate human target and antibody source/runtime manifest stays fail-closed."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "human_target_source_runtime_manifest.json"
RECEIPTS = AI_ROOT / "datasets" / "governance" / "human_target_source_runtime_receipts.jsonl"
OUT = AI_ROOT / "reports" / "human_target_source_runtime_manifest_validation_report.json"
BUILDER = AI_ROOT / "scripts" / "build_human_target_source_runtime_manifest.py"

EXPECTED = {
    "hpa_expression",
    "gtex_expression",
    "reactome_pathway",
    "ligand_receptor_graph",
    "anarci_imgt_runtime",
    "human_germline_db",
    "sabdab_oas_reference",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("build_human_target_source_runtime_manifest", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load builder: {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate human target source/runtime manifest")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    report = load_json(args.report)
    receipts = load_jsonl(args.receipts)
    builder = load_builder()
    sources = report.get("sources") or []
    by_id = {row.get("source_id"): row for row in sources if isinstance(row, dict)}
    source_created_at = {
        str(row.get("source_id")): str(row.get("created_at"))
        for row in sources
        if isinstance(row, dict) and row.get("source_id") and row.get("created_at")
    }
    expected_report, expected_receipts = builder.build(
        created_at=report.get("created_at"),
        source_created_at=source_created_at,
    )
    failures: list[dict[str, Any]] = []
    missing = sorted(EXPECTED - set(by_id))
    extra = sorted(set(by_id) - EXPECTED)

    fail_if(not report, failures, "manifest_report_present", rel(args.report), "existing JSON report")
    fail_if(report != expected_report, failures, "manifest_matches_current_builder_projection", report, expected_report)
    fail_if(receipts != expected_receipts, failures, "receipts_match_current_builder_projection", receipts, expected_receipts)
    fail_if(bool(missing), failures, "expected_sources_present", missing, [])
    fail_if(bool(extra), failures, "no_extra_sources", extra, [])
    fail_if(len(receipts) != len(sources), failures, "receipt_count_matches_sources", len(receipts), len(sources))
    fail_if(
        {str(row.get("source_id")) for row in receipts if isinstance(row, dict)}
        != {str(row.get("source_id")) for row in sources if isinstance(row, dict)},
        failures,
        "receipt_source_ids_match_sources",
        sorted({str(row.get("source_id")) for row in receipts if isinstance(row, dict)}),
        sorted({str(row.get("source_id")) for row in sources if isinstance(row, dict)}),
    )
    fail_if(
        report.get("summary") != expected_report.get("summary"),
        failures,
        "summary_matches_current_builder_projection",
        report.get("summary"),
        expected_report.get("summary"),
    )
    for source_id, row in sorted(by_id.items()):
        if row.get("status") != "blocked":
            failures.append({"check": "all_sources_blocked", "source_id": source_id, "observed": row.get("status")})
        for field in ("source_ready", "claim_eligible", "customer_ready", "release_ready"):
            if row.get(field) is not False:
                failures.append({"check": f"{field}_false", "source_id": source_id, "observed": row.get(field)})
        if not row.get("blocked_reason"):
            failures.append({"check": "blocked_reason_present", "source_id": source_id})
    validation = {
        "local_only": True,
        "success": not failures,
        "checked_report": rel(args.report),
        "checked_receipts": rel(args.receipts),
        "builder_contract": rel(BUILDER),
        "manifest_matches_current_builder_projection": report == expected_report,
        "receipts_match_current_builder_projection": receipts == expected_receipts,
        "expected_sources": len(expected_report.get("sources") or []),
        "expected_receipts": len(expected_receipts),
        "sources": len(sources),
        "receipts": len(receipts),
        "failures": failures,
        "failure_count": len(failures),
        "safe_for_model_claim": False,
        "customer_ready": False,
        "release_ready": False,
        "policy": "Validation only proves the blocked source/runtime manifest is internally consistent.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": validation["success"], "sources": validation["sources"], "failures": len(failures), "output": str(args.output)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
