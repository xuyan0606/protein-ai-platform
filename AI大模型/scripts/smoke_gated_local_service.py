#!/usr/bin/env python3
"""Smoke test the running gated local KWB service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib import request


AI_ROOT = Path(__file__).resolve().parents[1]


def post(endpoint: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{endpoint.rstrip('/')}/v1/enzyme-design",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def get_health(endpoint: str) -> dict:
    with request.urlopen(f"{endpoint.rstrip('/')}/health", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def get_status(endpoint: str) -> dict:
    with request.urlopen(f"{endpoint.rstrip('/')}/v1/status", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test gated local KWB service")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8766")
    args = parser.parse_args()

    health = get_health(args.endpoint)
    assert health["status"] == "ok"
    assert health["production_integration"] is False
    status = get_status(args.endpoint)
    assert status["service"]["production_integration"] is False
    assert status["summary"]["total_streams"] == 7

    uploaded_case = {
        "case_id": "gated-smoke-uploaded",
        "objective": {"primary_goal": "stability"},
        "enzyme": {"name": "smoke-enzyme", "sequence": "M" * 120},
        "structure": {
            "source_type": "uploaded_pdb",
            "object_name": "uploads/smoke.pdb",
            "chain_id": "A",
            "numbering_verified": True,
        },
        "mutations": [{
            "code": "A42P",
            "position": 42,
            "wild_type": "A",
            "mutant": "P",
            "status": "untested",
            "risk_flags": [],
        }],
        "evidence": [],
        "tool_results": [],
    }
    uploaded = post(args.endpoint, {
        **uploaded_case,
        "_kwb_context": {
            "session_id": "smoke-session",
            "conversation_id": "smoke-conversation",
            "request_turn_id": "smoke-uploaded",
        },
    })
    assert uploaded["status"] == "completed"
    assert uploaded["result"]["model"]["name"] == "KWB-EnzymeDesigner"
    assert "esmfold_folding" not in [
        step["tool_name"] for step in uploaded["workflow"]["steps"]
    ]

    sequence_case = dict(uploaded_case)
    sequence_case["case_id"] = "gated-smoke-sequence"
    sequence_case["structure"] = {"source_type": "none", "numbering_verified": None}
    sequence = post(args.endpoint, {
        **sequence_case,
        "_kwb_context": {
            "session_id": "smoke-session",
            "conversation_id": "smoke-conversation",
            "request_turn_id": "smoke-sequence",
        },
    })
    assert sequence["status"] == "pending_structure"
    assert sequence["result"] is None
    assert sequence["error_code"] == "pending_structure_prediction"
    print(json.dumps({
        "health": health,
        "ready_streams": f"{status['summary']['ready_streams']}/{status['summary']['total_streams']}",
        "uploaded_status": uploaded["status"],
        "sequence_status": sequence["status"],
        "smoke": "ok",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
