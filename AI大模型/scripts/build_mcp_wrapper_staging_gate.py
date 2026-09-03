#!/usr/bin/env python3
"""Build a fail-closed staging gate for future MCP/tool wrappers."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
QUEUE = AI_ROOT / "datasets" / "governance" / "mcp_wrapper_staging_queue.jsonl"
REPORT = AI_ROOT / "reports" / "mcp_wrapper_staging_gate_report.json"
SCHEMA = AI_ROOT / "contracts" / "mcp_wrapper_staging.schema.json"


SEED_ROWS: list[dict[str, Any]] = [
    {
        "wrapper_id": "staging_rosetta_mcp_template",
        "source_project": "Rosetta MCP template candidate",
        "source_url": "https://github.com/Biomolecular-Design-Nexus/rosetta_mcp",
        "source_checksum": "",
        "license_review_status": "not_reviewed",
        "runtime_lock_status": "missing",
        "output_schema_status": "missing",
        "forbidden_writes_declared": True,
        "smoke_status": "not_run",
        "staging_status": "blocked_template_only",
        "production_allowed": False,
        "agent_exposure_allowed": False,
        "training_write_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "blockers": ["source_not_downloaded", "license_not_approved", "runtime_not_locked", "smoke_missing"],
    },
    {
        "wrapper_id": "staging_foldx_ddg_template",
        "source_project": "FoldX ddG wrapper candidate",
        "source_url": "manual_vendor_or_local_install_required",
        "source_checksum": "",
        "license_review_status": "not_reviewed",
        "runtime_lock_status": "missing",
        "output_schema_status": "missing",
        "forbidden_writes_declared": True,
        "smoke_status": "not_run",
        "staging_status": "blocked_template_only",
        "production_allowed": False,
        "agent_exposure_allowed": False,
        "training_write_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "blockers": ["vendor_runtime_not_present", "license_not_approved", "runtime_not_locked", "smoke_missing"],
    },
    {
        "wrapper_id": "staging_esm_prottrans_features_template",
        "source_project": "ESM/ProtTrans feature wrapper candidate",
        "source_url": "future_model_weight_source_requires_authorization",
        "source_checksum": "",
        "license_review_status": "not_reviewed",
        "runtime_lock_status": "missing",
        "output_schema_status": "missing",
        "forbidden_writes_declared": True,
        "smoke_status": "not_run",
        "staging_status": "blocked_template_only",
        "production_allowed": False,
        "agent_exposure_allowed": False,
        "training_write_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "blockers": ["weights_not_authorized", "license_not_approved", "runtime_not_locked", "schema_missing"],
    },
]


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MCP wrapper staging gate")
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--schema", type=Path, default=SCHEMA)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    args.queue.parent.mkdir(parents=True, exist_ok=True)
    if not args.queue.exists() or not args.queue.read_text(encoding="utf-8").strip():
        rows = SEED_ROWS
        args.queue.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    else:
        rows = read_rows(args.queue)

    production_allowed_rows = [row for row in rows if row.get("production_allowed") is True]
    agent_exposure_rows = [row for row in rows if row.get("agent_exposure_allowed") is True]
    training_write_rows = [row for row in rows if row.get("training_write_allowed") is True]
    schema_ready_rows = [
        row for row in rows
        if row.get("source_checksum")
        and row.get("license_review_status") == "reviewed_approved"
        and row.get("runtime_lock_status") == "locked"
        and row.get("output_schema_status") == "declared"
        and row.get("smoke_status") == "passed"
    ]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "queue_rows": len(rows),
        "schema_path": str(args.schema.relative_to(AI_ROOT)),
        "schema_present": args.schema.exists(),
        "staging_ready_rows": len(schema_ready_rows),
        "production_allowed_rows": len(production_allowed_rows),
        "agent_exposure_allowed_rows": len(agent_exposure_rows),
        "training_write_allowed_rows": len(training_write_rows),
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Wrappers may be described in staging only. No wrapper is exposed to agents, production, training import, model claim, or release without explicit checksum/license/runtime/schema/smoke receipts.",
        "queue_path": str(args.queue.relative_to(AI_ROOT)),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"queue_rows": len(rows), "staging_ready_rows": report["staging_ready_rows"], "production_allowed_rows": 0, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
