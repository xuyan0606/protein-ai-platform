#!/usr/bin/env python3
"""Validate the head model-card status draft mirrors current blocked readiness."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "head_model_card_status_report.json"
STATUS_MD = AI_ROOT / "model_cards" / "KWB-EnzymeDesigner-heads.status.md"
OUT = AI_ROOT / "reports" / "head_model_card_status_validation_report.json"
MULTITASK = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
BENCHMARK = AI_ROOT / "reports" / "benchmark_matrix_report.json"
EXPECTED_HEADS = ("mutation_rank", "stability", "activity_risk", "substrate_fit", "assay_success")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def fail_if(condition: bool, failures: list[dict[str, Any]], check: str, observed: Any, expected: Any) -> None:
    if condition:
        failures.append({"check": check, "observed": observed, "expected": expected})


def expected_markdown(multitask: dict[str, Any], benchmark: dict[str, Any]) -> str:
    benchmark_by_head = {
        row.get("head"): row
        for row in (benchmark.get("heads") or [])
        if isinstance(row, dict)
    }
    lines = [
        "# KWB-EnzymeDesigner Head Status",
        "",
        "Local-only status draft. This is not a model-quality claim.",
        "",
    ]
    heads = multitask.get("heads") if isinstance(multitask.get("heads"), dict) else {}
    for head, info in heads.items():
        bench = benchmark_by_head.get(head, {})
        lines.extend([
            f"## {head}",
            "",
            f"- Label rows: {info.get('rows')} / {info.get('minimum_rows')}",
            f"- Training ready: {str(info.get('ready')).lower()}",
            f"- Benchmark scorecard ready: {str(bench.get('scorecard_ready')).lower()}",
            f"- Status: {bench.get('status', 'blocked')}",
            "- Prohibited uses: customer delivery, ordering approval, wet-lab performance guarantee.",
            "",
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate head model-card status draft")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--status-md", type=Path, default=STATUS_MD)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = load_json(args.report)
    multitask = load_json(MULTITASK)
    benchmark = load_json(BENCHMARK)
    status_text = args.status_md.read_text(encoding="utf-8") if args.status_md.exists() else ""
    heads = multitask.get("heads") if isinstance(multitask.get("heads"), dict) else {}
    benchmark_heads = {
        row.get("head"): row
        for row in (benchmark.get("heads") or [])
        if isinstance(row, dict)
    }
    expected_ready_heads = sum(1 for item in heads.values() if isinstance(item, dict) and item.get("ready") is True)
    expected_text = expected_markdown(multitask, benchmark)
    failures: list[dict[str, Any]] = []

    fail_if(not report, failures, "report_present", str(args.report), "existing JSON report")
    fail_if(report.get("local_only") is not True, failures, "report_local_only_true", report.get("local_only"), True)
    fail_if(as_int(report.get("heads")) != len(EXPECTED_HEADS), failures, "report_head_count_expected", report.get("heads"), len(EXPECTED_HEADS))
    fail_if(as_int(report.get("heads")) != len(heads), failures, "report_head_count_matches_multitask", report.get("heads"), len(heads))
    fail_if(as_int(report.get("ready_heads")) != expected_ready_heads, failures, "report_ready_heads_matches_multitask", report.get("ready_heads"), expected_ready_heads)
    fail_if(report.get("ready_for_model_claim") is not False, failures, "report_ready_for_model_claim_false", report.get("ready_for_model_claim"), False)
    fail_if(Path(str(report.get("model_card_status", ""))).resolve() != args.status_md.resolve(), failures, "report_model_card_status_path_matches", report.get("model_card_status"), str(args.status_md))
    fail_if(set(heads) != set(EXPECTED_HEADS), failures, "multitask_heads_expected", sorted(heads), sorted(EXPECTED_HEADS))
    fail_if(set(benchmark_heads) != set(EXPECTED_HEADS), failures, "benchmark_heads_expected", sorted(benchmark_heads), sorted(EXPECTED_HEADS))
    fail_if(status_text != expected_text, failures, "status_markdown_matches_current_sources", "sha_or_text_drift", "exact builder projection")

    for head in EXPECTED_HEADS:
        info = heads.get(head) if isinstance(heads.get(head), dict) else {}
        bench = benchmark_heads.get(head) if isinstance(benchmark_heads.get(head), dict) else {}
        expected_lines = [
            f"## {head}",
            f"- Label rows: {info.get('rows')} / {info.get('minimum_rows')}",
            f"- Training ready: {str(info.get('ready')).lower()}",
            f"- Benchmark scorecard ready: {str(bench.get('scorecard_ready')).lower()}",
            f"- Status: {bench.get('status', 'blocked')}",
            "- Prohibited uses: customer delivery, ordering approval, wet-lab performance guarantee.",
        ]
        for line in expected_lines:
            fail_if(line not in status_text, failures, f"{head}_status_markdown_line_present", line if line in status_text else None, line)
        fail_if(info.get("ready") is not False, failures, f"{head}_multitask_ready_false", info.get("ready"), False)
        fail_if(bench.get("scorecard_ready") is not False, failures, f"{head}_benchmark_scorecard_ready_false", bench.get("scorecard_ready"), False)

    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "checked_report": str(args.report),
        "checked_status_md": str(args.status_md),
        "expected_heads": list(EXPECTED_HEADS),
        "heads": len(heads),
        "ready_heads": expected_ready_heads,
        "failures": failures,
        "success": not failures,
        "ready_for_model_claim": False,
        "release_ready": False,
        "policy": "Fail-closed validator for the local-only head status draft; it never promotes a draft into a release model card.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "heads": validation["heads"],
        "ready_heads": validation["ready_heads"],
        "failures": len(failures),
        "ready_for_model_claim": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
