#!/usr/bin/env python3
"""Build a head-level model-card status draft from current readiness reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MULTITASK = AI_ROOT / "reports" / "multitask_training_readiness_report.json"
BENCHMARK = AI_ROOT / "reports" / "benchmark_matrix_report.json"
OUT = AI_ROOT / "model_cards" / "KWB-EnzymeDesigner-heads.status.md"
REPORT_OUT = AI_ROOT / "reports" / "head_model_card_status_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build head model-card status")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    multitask = load_json(MULTITASK)
    benchmark = load_json(BENCHMARK)
    benchmark_by_head = {row.get("head"): row for row in benchmark.get("heads", [])}
    lines = [
        "# KWB-EnzymeDesigner Head Status",
        "",
        "Local-only status draft. This is not a model-quality claim.",
        "",
    ]
    for head, info in (multitask.get("heads") or {}).items():
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    report = {
        "local_only": True,
        "heads": len(multitask.get("heads") or {}),
        "ready_heads": sum(1 for item in (multitask.get("heads") or {}).values() if item.get("ready")),
        "model_card_status": str(args.output),
        "ready_for_model_claim": False,
        "policy": "Status draft mirrors blocked readiness and must not be used as a release model card.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"heads": report["heads"], "ready_heads": report["ready_heads"], "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
