#!/usr/bin/env python3
"""Build a fail-closed board for parallel R&D agent lanes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "multi_agent_rnd_acceleration_board.json"
MD_OUT = AI_ROOT / "reports" / "multi_agent_rnd_acceleration_board.md"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "multi_agent_rnd_acceleration_lanes.jsonl"

LANES = [
    {
        "lane_id": "rnd_lane_five_head_training_gap",
        "owner": "main",
        "report": "reports/five_head_training_gap_plan_report.json",
        "expected_script": "scripts/build_five_head_training_gap_plan.py",
        "purpose": "Quantify five-head label gaps and next data gates.",
    },
    {
        "lane_id": "rnd_lane_substrate_fit_gap",
        "owner": "subagent_substrate_fit",
        "report": "reports/substrate_fit_label_gap_plan_report.json",
        "expected_script": "scripts/build_substrate_fit_label_gap_plan.py",
        "purpose": "Define substrate-fit label gap and forbidden shortcuts.",
    },
    {
        "lane_id": "rnd_lane_benchmark_gap",
        "owner": "subagent_benchmark",
        "report": "reports/five_head_benchmark_gap_plan_report.json",
        "expected_script": "scripts/build_five_head_benchmark_gap_plan.py",
        "purpose": "Quantify benchmark coverage gaps per model head.",
    },
    {
        "lane_id": "rnd_lane_wet_lab_head_authorization",
        "owner": "subagent_wet_lab",
        "report": "reports/wet_lab_head_authorization_gap_plan_report.json",
        "expected_script": "scripts/build_wet_lab_head_authorization_gap_plan.py",
        "purpose": "Turn wet-lab metric candidates into an authorization work plan.",
    },
    {
        "lane_id": "rnd_lane_structure_feature_gap",
        "owner": "subagent_structure",
        "report": "reports/structure_feature_head_gap_plan_report.json",
        "expected_script": "scripts/build_structure_feature_head_gap_plan.py",
        "purpose": "Quantify reviewed structure graph feature coverage for model heads.",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def lane_status(lane: dict[str, str]) -> dict[str, Any]:
    report_path = AI_ROOT / lane["report"]
    script_path = AI_ROOT / lane["expected_script"]
    report = load_json(report_path)
    exists = report_path.exists()
    return {
        **lane,
        "script_exists": script_path.exists(),
        "report_exists": exists,
        "status": "ready_to_integrate" if exists and script_path.exists() else "waiting_for_agent_output",
        "report_status": report.get("status"),
        "safe_for_model_claim": bool(report.get("safe_for_model_claim")) if exists else False,
        "release_ready": bool(report.get("release_ready")) if exists else False,
        "summary": {
            key: report.get(key)
            for key in [
                "ready_heads",
                "total_heads",
                "candidate_rows",
                "gap_rows",
                "actions",
                "safe_for_training_import",
            ]
            if key in report
        },
        "policy": "Parallel R&D coordination only; not a data approval, training run, release, or model-quality claim.",
    }


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Multi-Agent R&D Acceleration Board",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This board coordinates parallel fail-closed R&D lanes.",
        "",
        "## Summary",
        "",
        f"- Lanes: {report['lane_count']}",
        f"- Ready to integrate: {report['ready_to_integrate_lanes']}",
        f"- Waiting: {report['waiting_lanes']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Lanes",
        "",
        "| lane | owner | status | report | purpose |",
        "|---|---|---|---|---|",
    ]
    for lane in report["lanes"]:
        lines.append(
            f"| {lane['lane_id']} | {lane['owner']} | {lane['status']} | {lane['report']} | {lane['purpose']} |"
        )
    MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build multi-agent R&D acceleration board")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    lanes = [lane_status(lane) for lane in LANES]
    ready = sum(1 for lane in lanes if lane["status"] == "ready_to_integrate")
    waiting = len(lanes) - ready
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "in_progress" if waiting else "ready_to_review",
        "lane_count": len(lanes),
        "ready_to_integrate_lanes": ready,
        "waiting_lanes": waiting,
        "lanes": lanes,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "This board coordinates subagent outputs only. It never imports labels, trains models, or opens release gates.",
    }
    write_jsonl(args.jsonl, lanes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report)
    print(json.dumps({
        "status": report["status"],
        "lane_count": report["lane_count"],
        "ready_to_integrate_lanes": report["ready_to_integrate_lanes"],
        "waiting_lanes": report["waiting_lanes"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
