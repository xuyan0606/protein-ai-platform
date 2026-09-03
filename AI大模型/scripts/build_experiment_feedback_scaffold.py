#!/usr/bin/env python3
"""Build local experiment feedback templates and readiness report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_OUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.template.jsonl"
LOCAL_OUT = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "experiment_feedback_readiness_report.json"


TEMPLATE = {
    "feedback_id": "local-example-001",
    "enzyme_id": "example-enzyme",
    "uniprot_id": None,
    "project_id": "local-rd",
    "mutation": "A1V",
    "canonical_position": 1,
    "numbering_verified": False,
    "assay_type": "activity",
    "assay_condition": {
        "ph": 7.0,
        "temperature_c": 37.0,
        "buffer": None,
        "substrate": None,
        "expression_system": None
    },
    "outcome": "inconclusive",
    "activity_relative_to_wt": None,
    "stability_delta_tm_c": None,
    "expression_yield_relative": None,
    "notes": "Template only. Replace with reviewed KWB wet-lab record before training.",
    "source": "local_fixture",
    "recorded_at": "2026-07-24T00:00:00+08:00"
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build experiment feedback scaffold")
    parser.add_argument("--template-output", type=Path, default=TEMPLATE_OUT)
    parser.add_argument("--local-output", type=Path, default=LOCAL_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    args.template_output.parent.mkdir(parents=True, exist_ok=True)
    args.template_output.write_text(json.dumps(TEMPLATE, ensure_ascii=False) + "\n", encoding="utf-8")
    args.local_output.parent.mkdir(parents=True, exist_ok=True)
    if not args.local_output.exists():
        args.local_output.write_text("", encoding="utf-8")
    local_rows = load_jsonl(args.local_output)
    reviewed_rows = [
        row for row in local_rows
        if row.get("source") in {"kwb_wet_lab", "kwb_historical"} and row.get("numbering_verified")
    ]
    report = {
        "template": str(args.template_output),
        "local_feedback_file": str(args.local_output),
        "local_rows": len(local_rows),
        "reviewed_numbered_rows": len(reviewed_rows),
        "ready_for_training": len(reviewed_rows) >= 100,
        "policy": "template rows are not training data; only reviewed KWB feedback with verified numbering can become labels",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"local_rows": len(local_rows), "reviewed_numbered_rows": len(reviewed_rows), "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
