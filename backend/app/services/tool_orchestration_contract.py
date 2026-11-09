"""Machine-readable preflight for scientific tool plans.

This contract is intentionally side-effect free.  It validates a proposed plan
against input and evidence gates before the executor dispatches any tool.
"""

from __future__ import annotations

from typing import Any

from app.services.scheduler import ASYNC_TOOLS, get_task_profile
from app.tools.registry import ToolRegistry
from app.services.task_evidence import result_status, parse_tool_payload
from app.services.evidence_scope import evidence_scope, record_scope, scopes_match


SEQUENCE_REQUIRED = frozenset({
    "enzyme_sequence_identity",
    "thermostability_candidate_workflow", "ddgun_predict", "colabfold_predict", "evcouplings_analyze",
    "alphafold_folding", "alphafold2_folding", "esmfold_folding",
    "predict_properties", "mutation_scan", "mutation_priority_score",
    "protein_benchmark", "enzyme_identity_profile", "enzyme_function",
    "kcat_predict", "protssn_score", "blast_search",
    "enzyme_objective_module_plan", "rosetta_ddg",
})
PDB_REQUIRED = frozenset({
    "proteinmpnn_design", "esm_if1_design", "gromacs_md",
    "build_site_structure_function_features", "pocket_residue_lookup",
})
CANDIDATE_TOOLS = frozenset({
    "mutation_scan", "mutation_priority_score", "protssn_score",
})

TOOL_REQUIRES: dict[str, frozenset[str]] = {
    "thermostability_candidate_workflow": frozenset({"identity_profile", "objective_module"}),
    "enzyme_function": frozenset({"identity_profile"}),
    "enzyme_objective_module_plan": frozenset({"identity_profile"}),
    "residue_mapping_sifts": frozenset({"structure"}),
    "residue_numbering_gate": frozenset({"residue_mapping"}),
    "site_structure_function_features": frozenset({"structure", "numbering"}),
    "build_site_structure_function_features": frozenset({"structure", "numbering"}),
    "pocket_residue_lookup": frozenset({"structure"}),
    "mutation_priority_score": frozenset({"identity_profile", "objective_module", "numbering"}),
    "mutation_scan": frozenset({"identity_profile", "objective_module", "numbering"}),
    "protssn_score": frozenset({"identity_profile", "objective_module"}),
    "mutation_epistasis_check": frozenset({"candidate_set"}),
    "ligand_preprocess": frozenset({"ligand_3d_or_sdf"}),
    "diffdock_docking": frozenset({"structure", "ligand_3d"}),
    "gromacs_md": frozenset({"structure", "topology"}),
}

TOOL_PROVIDES: dict[str, frozenset[str]] = {
    "thermostability_candidate_workflow": frozenset({"candidate_set", "single_mutant_assay_plan"}),
    "ddgun_predict": frozenset({"predicted_unfolding_ddg"}),
    "colabfold_predict": frozenset({"structure"}),
    "evcouplings_analyze": frozenset({"coupling_pairs"}),
    "enzyme_identity_profile": frozenset({"identity_profile"}),
    "enzyme_objective_module_plan": frozenset({"objective_module"}),
    "structure_search_foldseek": frozenset({"structure"}),
    "residue_mapping_sifts": frozenset({"residue_mapping"}),
    "residue_numbering_gate": frozenset({"numbering"}),
    "mutation_priority_score": frozenset({"candidate_set"}),
    "mutation_scan": frozenset({"candidate_set"}),
    "proteinmpnn_design": frozenset({"designed_sequence"}),
    "ligand_preprocess": frozenset({"ligand_3d", "topology"}),
    "diffdock_docking": frozenset({"docking_pose"}),
    "gromacs_md": frozenset({"md_artifacts"}),
}

EVIDENCE_ALIASES = {
    "has_pdb": "structure", "has_structure": "structure",
    "identity_ready": "identity_profile", "objective_ready": "objective_module",
    "numbering_ready": "numbering", "has_numbering": "numbering",
    "has_residue_mapping": "residue_mapping", "has_topology": "topology",
    "has_ligand_3d": "ligand_3d", "has_candidate_set": "candidate_set",
}


def evidence_from_completed_tasks(tasks: list[dict[str, Any]] | None, *, scope: dict | None = None) -> dict[str, bool]:
    """Derive only conservative gate state from persisted terminal task audits."""
    evidence: dict[str, bool] = {}
    providers = {
        "enzyme_identity_profile": "identity_ready",
        "enzyme_objective_module_plan": "objective_ready",
        "structure_search_foldseek": "has_structure",
        "residue_mapping_sifts": "has_residue_mapping",
        "residue_numbering_gate": "has_numbering",
        "mutation_priority_score": "has_candidate_set",
        "mutation_scan": "has_candidate_set",
        "ligand_preprocess": "has_ligand_3d",
    }
    for task in tasks or []:
        if not isinstance(task, dict) or str(task.get("status") or "").lower() != "completed":
            continue
        payload = parse_tool_payload(task.get('result') or task.get('result_summary'))
        if result_status('completed', payload)['result_status'] != 'usable':
            continue
        if scope and not scopes_match(evidence_scope(scope), record_scope(task)):
            continue
        tool = str(task.get('tool_name') or task.get('tool') or '')
        if tool == 'enzyme_identity_profile' and (payload.get('identity_status') != 'identified' or payload.get('guardrail', {}).get('status') != 'ready'):
            continue
        if tool == 'enzyme_objective_module_plan' and payload.get('candidate_output_allowed') is not True:
            continue
        if tool == 'residue_mapping_sifts' and not payload.get('found'):
            continue
        key = providers.get(str(task.get("tool_name") or task.get("tool") or ""))
        if key:
            evidence[key] = True
    return evidence


def is_terminal_tool_evidence(tool_name: str, result: Any) -> bool:
    """Only completed, non-queued payloads may satisfy scientific gates."""
    if not isinstance(result, dict):
        return False
    status = str(result.get("status") or "").strip().lower()
    if result_status('completed', result)['result_status'] not in {'usable', 'empty'}:
        return False
    if status == "completed":
        return True
    # Async payloads without an explicit terminal status are ambiguous.
    if tool_name in ASYNC_TOOLS:
        return False
    return bool(result)


def validate_tool_plan(
    plan: list[dict[str, Any]] | None,
    *,
    evidence: dict[str, Any] | None = None,
    enforce_candidate_gates: bool = True,
    enforce_dependency_order: bool = False,
) -> dict[str, Any]:
    """Validate a proposed plan without dispatching tools.

    ``evidence`` accepts the normalized state used by the planner:
    ``has_sequence``, ``has_pdb``, ``identity_ready`` and ``objective_ready``.
    Unknown tools are reported, never silently allowed.
    """
    rows = plan if isinstance(plan, list) else []
    state = evidence if isinstance(evidence, dict) else {}
    if not ToolRegistry._tools or any(
        str(item.get("tool_name") or item.get("tool") or "").strip() not in ToolRegistry._tools
        for item in rows
        if isinstance(item, dict)
    ):
        ToolRegistry.discover()
    available = {alias for key, alias in EVIDENCE_ALIASES.items() if state.get(key) is True}
    if state.get("has_sequence") is True:
        available.add("sequence")
    planned_names = {
        str(item.get("tool_name") or item.get("tool") or "").strip()
        for item in rows
        if isinstance(item, dict)
    }
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    # Plan-wide input conflicts are not per-step gates: the sequence a step would
    # score was rejected at hydration, so no step in this plan can be trusted.
    # Without these rows the callers' conflict branches had no code to match on.
    if state.get("sequence_structure_conflict") is True:
        violations.append({"index": -1, "code": "sequence_structure_conflict"})
    if state.get("pdb_sequence_unavailable") is True:
        violations.append({"index": -1, "code": "pdb_sequence_unavailable"})
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        step = raw if isinstance(raw, dict) else {}
        name = str(step.get("tool_name") or step.get("tool") or "").strip()
        if not name:
            violations.append({"index": index, "code": "missing_tool_name"})
            continue
        tool = ToolRegistry.get_tool(name)
        requested_sync = bool(step.get("allow_interactive_sync_run")) or bool(
            isinstance(step.get("params"), dict) and step["params"].get("allow_interactive_sync_run")
        )
        if name in ASYNC_TOOLS and requested_sync:
            violations.append({"index": index, "tool": name, "code": "async_tool_sync_override"})
        if tool is None:
            violations.append({"index": index, "tool": name, "code": "unknown_tool"})
        else:
            if name in ASYNC_TOOLS:
                profile = get_task_profile(name)
                if profile.time_limit < int(tool.timeout_seconds or 0):
                    warnings.append({"index": index, "tool": name, "code": "task_limit_below_registry_timeout"})
        if name in seen:
            # Repeated tools are valid for explicit replicate/rerun plans.
            pass
        seen.add(name)
        if enforce_dependency_order:
            required = TOOL_REQUIRES.get(name, frozenset())
            if (name == "mutation_priority_score"
                    and (step.get("params") or {}).get("sequence_provenance") == "pdb_coordinate_derived"):
                # Input-sequence candidate codes need an exact chain mapping;
                # they do not project an external UniProt/literature number.
                # Execution separately verifies the mapping's terminal payload.
                required = (required - {"numbering"}) | {"residue_mapping"}
            if name == "mutation_scan":
                # Coordinate/aligned candidate codes need an input-to-author
                # mapping, not a user-facing numbering gate. Execution verifies
                # the mapping's terminal payload via _coordinate_mapping_gate_passed.
                params = step.get("params") or {}
                if (params.get("sequence_provenance") in {"pdb_coordinate_derived", "user_fasta_aligned"}
                        and "residue_numbering_gate" not in planned_names):
                    required = (required - {"numbering"}) | {"residue_mapping"}
            if name == "build_site_structure_function_features":
                params = step.get("params") or {}
                # Raw coordinate geometry has no external numbering projection.
                # Catalytic/protected/target position requests still require it.
                if not any(params.get(k) for k in ("catalytic_positions", "protected_positions", "target_positions")):
                    required = required - {"numbering"}
            for dependency in sorted(required - available):
                violations.append({"index": index, "tool": name, "code": "dependency_required", "dependency": dependency})
        available.update(TOOL_PROVIDES.get(name, frozenset()))
        if name in SEQUENCE_REQUIRED and state.get("has_sequence") is not True:
            violations.append({"index": index, "tool": name, "code": "sequence_required"})
        if name in PDB_REQUIRED and state.get("has_pdb") is not True:
            violations.append({"index": index, "tool": name, "code": "structure_required"})
        if enforce_candidate_gates and name in CANDIDATE_TOOLS:
            if state.get("identity_ready") is not True and "enzyme_identity_profile" not in planned_names:
                violations.append({"index": index, "tool": name, "code": "identity_gate_required"})
            if state.get("objective_ready") is not True and "enzyme_objective_module_plan" not in planned_names:
                violations.append({"index": index, "tool": name, "code": "objective_gate_required"})
    return {
        "contract_version": "tool_orchestration_v1",
        "allowed": not violations,
        "step_count": len(rows),
        "violations": violations,
        "warnings": warnings,
        "evidence": {
            "has_sequence": state.get("has_sequence") is True,
            "has_pdb": state.get("has_pdb") is True,
            "identity_ready": state.get("identity_ready") is True,
            "objective_ready": state.get("objective_ready") is True,
            "async_tools": sorted(ASYNC_TOOLS),
            "dependency_order_enforced": enforce_dependency_order,
        },
    }
