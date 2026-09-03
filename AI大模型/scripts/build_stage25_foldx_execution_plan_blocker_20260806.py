#!/usr/bin/env python3
"""Build a Stage 25 receipt for the FoldX execution-plan blocker."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PLAN_REPORT = AI_ROOT / "reports" / "ddg_backend_execution_plan_foldx_stage25_20260806.json"
PLAN_JSONL = AI_ROOT / "datasets" / "curation" / "ddg_backend_execution_plan.foldx_stage25_20260806.jsonl"
READINESS = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"
TECHNICAL_SMOKE_VALIDATION = AI_ROOT / "reports" / "stage25_foldx_technical_smoke_validation_20260806.json"
OUTPUT = AI_ROOT / "reports" / "stage25_foldx_execution_plan_blocker_20260806.json"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise SystemExit(f"{path} contains a non-object row")
        rows.append(row)
    return rows


def main() -> int:
    plan = load_json(PLAN_REPORT)
    readiness = load_json(READINESS)
    technical_smoke = load_json(TECHNICAL_SMOKE_VALIDATION)
    plan_rows = load_jsonl(PLAN_JSONL)
    foldx_backend = next(
        (row for row in readiness.get("backends") or [] if isinstance(row, dict) and row.get("backend") == "foldx"),
        {},
    )
    blocker_counts = Counter()
    for row in plan_rows:
        for blocker in row.get("blockers") or []:
            blocker_counts[str(blocker)] += 1

    safe_flags = {
        "formal_runtime_receipt_written": False,
        "approved_for_physical_ddg_runtime": False,
        "foldx_buildmodel_physical_smoke_executed": False,
        "foldx_buildmodel_technical_smoke_executed": technical_smoke.get("success") is True and technical_smoke.get("technical_smoke_passed") is True,
        "foldx_technical_smoke_only": technical_smoke.get("technical_smoke_only") is True,
        "foldx_technical_smoke_artifact_count": technical_smoke.get("artifact_count"),
        "foldx_technical_smoke_satisfies_formal_provision": False,
        "bridge_intake_rows_written": 0,
        "external_sqlite_mutated": False,
        "apply_executed": False,
        "export_safe_released": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    receipt = {
        "schema_version": 1,
        "created_at": "2026-08-06",
        "mode": "stage25_foldx_execution_plan_blocker",
        "stage": 25,
        "selected_backend": plan.get("selected_backend"),
        "requested_backend": plan.get("requested_backend"),
        "backend_selection_mode": plan.get("backend_selection_mode"),
        "plan_report": str(PLAN_REPORT),
        "plan_jsonl": str(PLAN_JSONL),
        "readiness_report": str(READINESS),
        "plan_rows": plan.get("plan_rows"),
        "jsonl_rows": len(plan_rows),
        "ready_rows": plan.get("ready_rows"),
        "blocked_rows": plan.get("blocked_rows"),
        "one_ddg_backend_ready": plan.get("one_ddg_backend_ready"),
        "executable_ddg_backend_ready": plan.get("executable_ddg_backend_ready"),
        "foldx_technical_probe_ready": foldx_backend.get("technical_probe_ready"),
        "foldx_runtime_receipt_ready": foldx_backend.get("runtime_receipt_ready"),
        "foldx_bootstrap_smoke_artifact_ready": foldx_backend.get("bootstrap_smoke_artifact_ready"),
        "foldx_production_data_ready": foldx_backend.get("production_data_ready"),
        "foldx_current_execution_ready": foldx_backend.get("current_execution_ready"),
        "foldx_ready_for_execution": foldx_backend.get("ready_for_execution"),
        "foldx_install_ready": foldx_backend.get("install_ready"),
        "foldx_license_ready": foldx_backend.get("license_ready"),
        "foldx_runtime_ready": foldx_backend.get("runtime_ready"),
        "foldx_data_ready": foldx_backend.get("data_ready"),
        "foldx_backend_blockers": foldx_backend.get("blockers") or [],
        "plan_blocker_counts": dict(sorted(blocker_counts.items())),
        "receipt_decision": "blocked_execution_plan_no_ready_rows",
        "completion_condition": "A formal FoldX runtime receipt, approved formal physical-smoke artifacts, reviewed structure/mutation rows for FoldX, and nonzero ready execution-plan rows must validate before physical-ddG or model-claim use.",
        "policy": "Receipt only. An isolated BuildModel technical smoke exists, but it cannot satisfy formal provision or physical-ddG approval. This builder does not execute FoldX, write SQLite, create a formal runtime receipt, bridge benchmark intake, or open release/model claims.",
        **safe_flags,
    }
    OUTPUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "receipt_decision": receipt["receipt_decision"],
        "plan_rows": receipt["plan_rows"],
        "ready_rows": receipt["ready_rows"],
        "blocked_rows": receipt["blocked_rows"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
