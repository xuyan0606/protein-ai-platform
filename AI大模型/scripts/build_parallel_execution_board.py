#!/usr/bin/env python3
"""Build a local board showing all started workstreams and fail-closed blockers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "parallel_execution_board.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build parallel execution board")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    board = {
        "local_only": True,
        "status": "all_local_workstreams_started",
        "acceptance_gates": "reports/workstream_acceptance_gates.json",
        "accepted_streams": load_json(AI_ROOT / "reports" / "workstream_acceptance_gates.json").get("accepted_streams"),
        "total_acceptance_gates": load_json(AI_ROOT / "reports" / "workstream_acceptance_gates.json").get("total_streams"),
        "workstreams": [
            {
                "stream": "numbering_curation",
                "started": True,
                "artifact": "datasets/curation/numbering_review_worklist.jsonl",
                "current_rows": load_json(AI_ROOT / "reports" / "numbering_review_worklist_report.json").get("worklist_rows"),
                "blocked_by": "requires reviewed numbering decisions",
            },
            {
                "stream": "structure_chain_mapping",
                "started": True,
                "artifact": "datasets/curation/structure_chain_autoreview_candidates.jsonl",
                "current_rows": load_json(AI_ROOT / "reports" / "structure_chain_autoreview_candidate_report.json").get("candidate_rows"),
                "blocked_by": "auto-review candidates require human acceptance before apply",
            },
            {
                "stream": "msa_conservation",
                "started": True,
                "artifact": "datasets/curation/msa_runtime_commands.jsonl",
                "current_rows": load_json(AI_ROOT / "reports" / "msa_runtime_command_report.json").get("command_rows"),
                "blocked_by": "mmseqs/docker/trusted cache not ready",
            },
            {
                "stream": "experiment_feedback_plate",
                "started": True,
                "artifact": "datasets/feedback/plate_review_packets/feedback_plate_review_priority_001.jsonl",
                "current_rows": load_json(AI_ROOT / "reports" / "experiment_feedback_plate_review_packet_report.json").get("plate_review_packet_rows"),
                "blocked_by": "requires manual extraction of genuine wet-lab plate/well records",
            },
            {
                "stream": "governance_release",
                "started": True,
                "artifact": "reports/local_release_manifest.json",
                "current_rows": load_json(AI_ROOT / "reports" / "data_lake_manifest.json").get("artifacts") and len(load_json(AI_ROOT / "reports" / "data_lake_manifest.json").get("artifacts", [])),
                "blocked_by": "license, IP/FTO, biosecurity, benchmark, and human approval gates",
            },
            {
                "stream": "active_learning",
                "started": True,
                "artifact": "reports/active_learning_trial_readiness_report.json",
                "current_rows": load_json(AI_ROOT / "reports" / "active_learning_trial_readiness_report.json").get("draft_rows"),
                "blocked_by": "no approved model, benchmark, plate feedback, budget, or human approval",
            },
        ],
        "policy": "All streams are started as local artifacts; blocked states are expected and must not be bypassed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": board["status"], "workstreams": len(board["workstreams"]), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
