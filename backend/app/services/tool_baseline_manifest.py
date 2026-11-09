"""Deterministic comparison between intended and runtime tool registries."""

from __future__ import annotations

from typing import Any, Iterable
from pathlib import Path
import re


DEFAULT_FALLBACKS = {
    "catalytic_site_lookup": "enzyme_identity_profile",
    "external_research_evidence": "literature_live_search",
    "feedback_iteration_planner": "mutation_epistasis_check",
    "residue_numbering_gate": "residue_mapping_sifts",
}


def reconcile_tool_baseline(
    *,
    desired_tools: Iterable[str],
    runtime_tools: Iterable[str],
    fallback_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a read-only tool baseline ledger without masking runtime gaps."""
    desired = sorted({str(name) for name in desired_tools if str(name)})
    runtime = {str(name) for name in runtime_tools if str(name)}
    fallbacks = fallback_map or {}
    entries = []
    for tool_id in desired:
        configured_fallback_tool = fallbacks.get(tool_id)
        fallback_tool = None
        if tool_id in runtime:
            state = "available"
            level = "DIRECT"
        elif configured_fallback_tool and configured_fallback_tool in runtime:
            state = "degraded"
            fallback_tool = configured_fallback_tool
            level = "DEGRADED"
        else:
            state = "pending_reconnect"
            level = None
        entries.append({
            "tool_id": tool_id,
            "runtime_state": state,
            "fallback_tool": fallback_tool,
            "configured_fallback_tool": configured_fallback_tool,
            "fallback_level": level,
            "owner_action": "none" if state == "available" else "reconnect_or_confirm_fallback",
        })
    summary = {state: sum(row["runtime_state"] == state for row in entries) for state in (
        "available", "degraded", "pending_reconnect", "not_applicable"
    )}
    return {
        "schema_version": "tool-baseline-manifest-v1",
        "catalog_tool_count": len(desired),
        "runtime_tool_count": len(runtime),
        "entries": entries,
        "summary": summary,
    }


def load_catalog_tool_names(catalog_path: str | Path) -> list[str]:
    """Extract canonical tool identifiers from a delivery catalog Markdown."""
    path = Path(catalog_path)
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"\|\s*`([a-z][a-z0-9_]{2,})`\s*\|", text)))
