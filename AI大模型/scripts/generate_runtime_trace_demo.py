#!/usr/bin/env python3
"""Generate a local runtime trace demo for the advanced model panel."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = AI_ROOT / "reports" / "runtime_trace_demo.jsonl"
FOREIGN_TOOL_REPORT = AI_ROOT / "reports" / "foreign_tool_readiness_report.json"


STAGES = [
    ("input_parsing", "Input parsing", 8, {"candidate_count": 0}),
    ("structure_gate", "Structure gate", 20, {"structure_gate_passed": True}),
    ("residue_numbering", "Residue numbering", 34, {"numbering_verified": True}),
    ("evidence_retrieval", "Evidence retrieval", 52, {"candidate_count": 12}),
    ("feature_enrichment", "Feature enrichment", 68, {"candidate_count": 12}),
    ("multi_head_scoring", "Multi-head scoring", 82, {"candidate_count": 12}),
    ("candidate_ranking", "Candidate ranking", 94, {"go_count": 3, "watch_count": 7, "no_go_count": 2}),
    ("experiment_planning", "Experiment planning", 100, {"go_count": 3, "watch_count": 7, "no_go_count": 2}),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate runtime trace demo JSONL")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--session-id", default="local-demo")
    args = parser.parse_args()

    base = datetime(2026, 7, 24, 10, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    foreign_tool_readiness = {}
    if FOREIGN_TOOL_REPORT.exists():
        foreign_tool_readiness = json.loads(FOREIGN_TOOL_REPORT.read_text(encoding="utf-8"))
    events = []
    for index, (stage, title, progress, metrics) in enumerate(STAGES, start=1):
        now = base + timedelta(seconds=index * 3)
        display_metrics = dict(metrics)
        if stage in {"evidence_retrieval", "feature_enrichment"}:
            display_metrics["external_tool_status_counts"] = foreign_tool_readiness.get("status_counts", {})
            display_metrics["external_tools_ready_for_local_evaluation"] = foreign_tool_readiness.get("ready_for_local_evaluation", 0)
            display_metrics["external_tool_policy"] = "fail_closed_license_and_install_gate"
        events.append({
            "event_id": f"kwb-demo-{index:03d}",
            "session_id": args.session_id,
            "conversation_id": None,
            "project_id": "local-rd",
            "user_id": "local",
            "model_name": "KWB-EnzymeDesigner",
            "model_version": "0.4.0-supervised-pipeline",
            "tool_name": "kwb_enzyme_designer",
            "tool_params": {
                "objective": "multi-objective enzyme optimization",
                "local_only": True,
                "external_tool_registry": "config/foreign_tool_registry.local.example.json",
            },
            "stage": stage,
            "stage_title": title,
            "progress_percent": progress,
            "status": "completed" if progress == 100 else "running",
            "evidence_counts": {
                "kwb_private_records": 24,
                "public_database_records": 500,
                "structure_records": 500,
                "tool_results": 6,
            },
            "display_metrics": display_metrics,
            "result_ref": "reports/sample_case_result.json" if progress == 100 else None,
            "error_code": None,
            "quality_flags": [
                "local_only",
                "non_leaky_features",
                "wet_lab_validation_required",
            ],
            "created_at": now.isoformat(),
            "completed_at": now.isoformat() if progress == 100 else None,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events), encoding="utf-8")
    print(json.dumps({"events": len(events), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
