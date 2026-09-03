#!/usr/bin/env python3
"""Build a source-bound audit of master readiness stream gaps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
BOARD = AI_ROOT / "reports" / "master_readiness_board.json"
BOARD_VALIDATION = AI_ROOT / "reports" / "master_readiness_board_validation_report.json"
LOCAL_RELEASE = AI_ROOT / "reports" / "local_release_manifest.json"
CLAIM_MATRIX = AI_ROOT / "reports" / "claim_readiness_matrix.json"
OUT_JSONL = AI_ROOT / "datasets" / "governance" / "p482_master_readiness_stream_gap_audit.jsonl"
OUT_REPORT = AI_ROOT / "reports" / "p482_master_readiness_stream_gap_audit_report.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def base(audit_id: str, gap_type: str, source_state: dict[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_id": audit_id,
        "gap_type": gap_type,
        "source_report": "reports/master_readiness_board.json",
        "source_validation_report": "reports/master_readiness_board_validation_report.json",
        "source_state": source_state,
        "blocker": blocker,
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "policy": "Master readiness stream audit only; stream readiness rows do not authorize training, model claims, customer delivery, release, ordering, legal clearance, or production execution.",
    }


def main() -> int:
    board = load_json(BOARD)
    validation = load_json(BOARD_VALIDATION)
    local_release = load_json(LOCAL_RELEASE)
    claim_matrix = load_json(CLAIM_MATRIX)
    streams = [row for row in board.get("streams") or [] if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []

    for stream in streams:
        stream_id = stream.get("stream")
        blockers = list(stream.get("blockers") or [])
        stream_ready = stream.get("ready") is True
        rows.append(base(
            f"p482-master-readiness-stream::{stream_id}",
            "master_readiness_stream_gap",
            {
                "stream": stream_id,
                "status": stream.get("status"),
                "stream_ready_source": stream.get("ready"),
                "blockers": blockers,
                "blocker_count": len(blockers),
                "current_key_count": len(stream.get("current") or {}),
                "overall_status": board.get("overall_status"),
                "board_ready_streams": board.get("ready_streams"),
                "board_total_streams": board.get("total_streams"),
                "validation_success": validation.get("success"),
                "validation_ready_streams": validation.get("ready_streams"),
                "validation_total_streams": validation.get("total_streams"),
            },
            "master readiness stream is not globally claim/release authorizing",
        ) | {
            "stream": stream_id,
            "stream_status": stream.get("status"),
            "stream_ready_source": stream_ready,
            "stream_blocker_count": len(blockers),
            "completion_ready": False,
        })

    blocked_stream_rows = sum(1 for row in streams if row.get("ready") is not True)
    rows.append(base(
        "p482-master-readiness-summary",
        "master_readiness_stream_summary_gap",
        {
            "overall_status": board.get("overall_status"),
            "ready_streams": board.get("ready_streams"),
            "total_streams": board.get("total_streams"),
            "blocked_stream_rows": blocked_stream_rows,
            "validation_success": validation.get("success"),
            "validation_failures": validation.get("failures") or [],
            "validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
            "validation_release_ready": validation.get("release_ready"),
            "local_release_ready": local_release.get("release_ready"),
            "claims_allowed": claim_matrix.get("claims_allowed"),
            "claims_blocked": claim_matrix.get("claims_blocked"),
        },
        "master readiness board remains blocked and cannot authorize model claims or release",
    ) | {
        "overall_status": board.get("overall_status"),
        "ready_streams": board.get("ready_streams"),
        "total_streams": board.get("total_streams"),
        "blocked_stream_rows": blocked_stream_rows,
        "completion_ready": False,
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "audit_rows": len(rows),
        "stream_audit_rows": len(streams),
        "blocked_stream_rows": blocked_stream_rows,
        "summary_audit_rows": 1,
        "overall_status": board.get("overall_status"),
        "ready_streams": board.get("ready_streams"),
        "total_streams": board.get("total_streams"),
        "data_quality_score": board.get("data_quality_score"),
        "validation_success": validation.get("success"),
        "validation_failures": validation.get("failures") or [],
        "validation_safe_for_model_claim": validation.get("safe_for_model_claim"),
        "validation_release_ready": validation.get("release_ready"),
        "local_release_ready": local_release.get("release_ready"),
        "claims_allowed": claim_matrix.get("claims_allowed"),
        "claims_blocked": claim_matrix.get("claims_blocked"),
        "training_import_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "customer_delivery_ready": False,
        "release_ready": False,
        "production_execution_allowed": False,
        "audit_jsonl": "datasets/governance/p482_master_readiness_stream_gap_audit.jsonl",
        "policy": "P482 audit only. Master readiness remains blocked until all source streams and formal gates pass.",
    }
    write_jsonl(OUT_JSONL, rows)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "audit_rows": report["audit_rows"],
        "stream_audit_rows": report["stream_audit_rows"],
        "blocked_stream_rows": report["blocked_stream_rows"],
        "overall_status": report["overall_status"],
        "output": str(OUT_REPORT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
