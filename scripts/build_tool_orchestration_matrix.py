#!/usr/bin/env python3
"""Build a read-only coverage report for registered scientific tools."""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.scheduler import ASYNC_TOOLS, get_task_profile  # noqa: E402
from app.tools.registry import ToolRegistry  # noqa: E402
from app.tools.tool_capability_audit import _CAPABILITIES  # noqa: E402
from app.services.tool_orchestration_contract import TOOL_PROVIDES, TOOL_REQUIRES  # noqa: E402


def _evidence_level(capability: dict | None) -> str:
    status = str((capability or {}).get("capability_status") or "unknown").lower()
    if status in {"real", "live", "evidence_synthesis"}:
        return "runtime_or_source_evidence"
    if status in {"proxy", "proxy_or_external_lookup", "model", "heuristic"}:
        return "proxy_or_ranking_only"
    return "unverified"


def build_report() -> dict:
    ToolRegistry.discover()
    rows = []
    for name, tool in sorted(ToolRegistry._tools.items()):
        capability = _CAPABILITIES.get(name)
        profile = get_task_profile(name)
        rows.append({
            "tool": name,
            "category": tool.category,
            "registry_timeout_seconds": tool.timeout_seconds,
            "async": name in ASYNC_TOOLS,
            "queue": profile.queue,
            "task_time_limit_seconds": profile.time_limit,
            "capability_audited": capability is not None,
            "capability_status": capability.get("capability_status") if capability else "unknown",
            "license_class": capability.get("license_class") if capability else None,
            "commercial_use_status": capability.get("commercial_use_status") if capability else None,
            "minimum_artifacts": capability.get("minimum_artifacts", []) if capability else ["capability audit entry"],
            "requires": sorted(TOOL_REQUIRES.get(name, frozenset())),
            "provides": sorted(TOOL_PROVIDES.get(name, frozenset())),
            "evidence_level": _evidence_level(capability),
            "runtime_mode": "async_worker" if name in ASYNC_TOOLS else "inline_sync",
            "license_status": (
                "review_required"
                if not capability or not capability.get("license_class")
                else str(capability.get("commercial_use_status") or "review_required")
            ),
        })
    return {
        "mode": "tool_orchestration_coverage_report",
        "contract_version": "tool_orchestration_v1",
        "registered_tool_count": len(rows),
        "alias_count": len(ToolRegistry._aliases),
        "async_tool_count": sum(1 for row in rows if row["async"]),
        "capability_audited_count": sum(1 for row in rows if row["capability_audited"]),
        "unknown_capability_tools": [row["tool"] for row in rows if not row["capability_audited"]],
        "rows": rows,
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/designs/2026-08-25-tool-orchestration-coverage.json")
    args = parser.parse_args()
    payload = build_report()
    output = PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in payload if k != "rows"}, ensure_ascii=False, indent=2))
    print(f"output\t{output.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
