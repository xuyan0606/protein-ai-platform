#!/usr/bin/env python3
"""Run local adapter regression scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from platform_integration.kwb_tool_adapter_local import (  # noqa: E402
    WorkflowContext,
    run_local_adapter,
)


DEFAULT_OUT = AI_ROOT / "reports" / "local_tool_adapter_demo.json"
VALID_STAGES = {
    "input_parsing",
    "structure_gate",
    "residue_numbering",
    "evidence_retrieval",
    "feature_enrichment",
    "multi_head_scoring",
    "candidate_ranking",
    "experiment_planning",
}
VALID_STATUSES = {"planned", "running", "completed", "failed", "blocked", "cancelled"}


def base_case() -> dict:
    return {
        "case_id": "local-adapter-demo",
        "case_type": "multi_objective",
        "objective": {"primary_goal": "stability"},
        "enzyme": {
            "name": "demo-enzyme",
            "sequence": "M" * 120,
        },
        "structure": {
            "source_type": "none",
            "numbering_verified": None,
        },
        "mutations": [
            {
                "code": "A42P",
                "position": 42,
                "wild_type": "A",
                "mutant": "P",
                "status": "untested",
                "risk_flags": [],
            }
        ],
        "evidence": [],
        "tool_results": [],
        "assay_condition": {"ph": 7.0, "temperature_c": 30, "assay_method": "local-demo"},
    }


def assert_event_contract(result: dict) -> None:
    for event in result["events"]:
        assert event["event_id"]
        assert event["session_id"] == result["context"]["session_id"]
        assert event["tool_name"]
        assert event["stage"] in VALID_STAGES
        assert event["status"] in VALID_STATUSES
        assert 0 <= event["progress_percent"] <= 100
        assert event["tool_params"]["task_id"]
        assert event["created_at"].endswith("+08:00")


def run() -> dict:
    uploaded = base_case()
    uploaded["structure"] = {
        "source_type": "uploaded_pdb",
        "object_name": "uploads/demo.pdb",
        "chain_id": "A",
        "numbering_verified": True,
    }
    uploaded_result = run_local_adapter(
        uploaded,
        WorkflowContext("adapter-session", "adapter-conversation", "turn-uploaded"),
    )
    assert uploaded_result["status"] == "completed"
    assert_event_contract(uploaded_result)
    assert uploaded_result["result"]["model"]["name"] == "KWB-EnzymeDesigner"
    assert "esmfold_folding" not in [
        step["tool_name"] for step in uploaded_result["workflow"]["steps"]
    ]

    unverified = base_case()
    unverified["structure"] = {
        "source_type": "uploaded_pdb",
        "object_name": "uploads/demo.pdb",
        "numbering_verified": False,
    }
    unverified_result = run_local_adapter(
        unverified,
        WorkflowContext("adapter-session", "adapter-conversation", "turn-unverified"),
    )
    assert unverified_result["status"] == "blocked"
    assert_event_contract(unverified_result)
    assert unverified_result["result"] is None
    assert unverified_result["error_code"] == "numbering_not_verified"

    sequence_result = run_local_adapter(
        base_case(),
        WorkflowContext("adapter-session", "adapter-conversation", "turn-sequence"),
    )
    assert sequence_result["status"] == "pending_structure"
    assert_event_contract(sequence_result)
    assert sequence_result["result"] is None
    assert sequence_result["error_code"] == "pending_structure_prediction"

    predicted_case = base_case()
    predicted_case["structure"] = {
        "source_type": "esmfold",
        "object_name": "tasks/esmfold/current/model.cif",
        "chain_id": "A",
        "numbering_verified": True,
        "confidence": 82,
    }
    predicted_result = run_local_adapter(
        predicted_case,
        WorkflowContext("adapter-session", "adapter-conversation", "turn-predicted"),
        completed_tools=["esmfold_folding"],
    )
    assert predicted_result["status"] == "completed"
    assert_event_contract(predicted_result)
    assert predicted_result["result"]["evidence_summary"]["structure_evidence"] == "esmfold_structure"

    return {
        "uploaded_structure": uploaded_result,
        "uploaded_structure_unverified": unverified_result,
        "sequence_only_pending": sequence_result,
        "sequence_only_after_esmfold": predicted_result,
        "assertions": {
            "uploaded_structure_calls_kwb_without_esmfold": True,
            "unverified_numbering_blocks_kwb": True,
            "sequence_only_returns_pending_without_prediction": True,
            "sequence_only_can_call_kwb_after_prediction": True,
            "tool_events_match_contract_shape": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local KWB tool adapter demo")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "assertions": report["assertions"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
