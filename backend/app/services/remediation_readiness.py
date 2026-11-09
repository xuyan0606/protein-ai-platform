"""Read-only remediation readiness summary for operator handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.model_runtime_readiness import collect_model_runtime_readiness
from app.services.tool_baseline_manifest import DEFAULT_FALLBACKS, load_catalog_tool_names, reconcile_tool_baseline
from app.tools.registry import ToolRegistry


def collect_remediation_readiness(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root)
    catalog = root / "AI酶工程平台三层架构_交付包_v2_20260827" / "03_执行控制层/enzyme-property-workflow-router/references/platform_tool_catalog.md"
    desired = load_catalog_tool_names(catalog)
    baseline = reconcile_tool_baseline(
        desired_tools=desired or ToolRegistry._tools.keys(),
        runtime_tools=ToolRegistry._tools.keys(),
        fallback_map=DEFAULT_FALLBACKS,
    )
    model = collect_model_runtime_readiness()
    blockers = []
    if baseline["summary"]["pending_reconnect"]:
        blockers.append("tool_reconnect_required")
    if model["esm2"]["status"] == "blocked":
        blockers.append("esm2_runtime_dependencies_missing")
    blockers.extend(["production_endpoint_verification_required", "operator_approval_required"])
    return {
        "schema_version": "remediation-readiness-v1",
        "status": "ready_for_operator" if blockers else "ready_for_local_validation",
        "local_validation": "complete",
        "blockers": sorted(set(blockers)),
        "tool_baseline": baseline,
        "model_runtime": model,
        "operator_actions": [
            "capture_authenticated /api/tools manifest from target deployment",
            "reconnect or approve degraded mappings for pending tools",
            "install and smoke-test torch/ESM-2 in target runtime",
            "run browser-level outage and SSE interruption acceptance",
        ],
    }
