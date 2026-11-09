"""Runtime workflow adapter for the delivery package's C6 definitions."""

from __future__ import annotations

import re
import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.tools.esmfold_folding import _MAX_SEQUENCE_LENGTH as ESMFOLD_MAX_SEQUENCE_LENGTH


WORKFLOW_FILE = Path(__file__).resolve().parents[1] / "workflows" / "enzyme_skill_workflows.yaml"


@dataclass(frozen=True)
class WorkflowStage:
    id: int
    name: str
    tools: tuple[str, ...] = ()
    gates: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class WorkflowDefinition:
    skill_id: str
    objective: str
    triggers: tuple[str, ...]
    stages: tuple[WorkflowStage, ...]
    missing_capabilities: tuple[str, ...] = ()


@dataclass
class WorkflowPlan:
    workflow: WorkflowDefinition
    steps: list[dict[str, Any]] = field(default_factory=list)
    unavailable_tools: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    missing_capabilities: list[str] = field(default_factory=list)


class WorkflowRegistry:
    """Loads and validates runtime-adapted objective workflows."""

    _workflows: dict[str, WorkflowDefinition] = {}
    _loaded_from: Path | None = None

    @classmethod
    def load(cls, path: Path = WORKFLOW_FILE) -> dict[str, WorkflowDefinition]:
        if cls._loaded_from == path and cls._workflows:
            return cls._workflows
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        definitions: dict[str, WorkflowDefinition] = {}
        for item in raw.get("workflows", []):
            stages = tuple(
                WorkflowStage(
                    id=int(stage["id"]),
                    name=str(stage["name"]),
                    tools=tuple(stage.get("tools", [])),
                    gates=tuple(stage.get("gates", [])),
                )
                for stage in item.get("stages", [])
            )
            definition = WorkflowDefinition(
                skill_id=str(item["skill_id"]),
                objective=str(item["objective"]),
                triggers=tuple(item.get("triggers", [])),
                stages=stages,
                missing_capabilities=tuple(item.get("missing_capabilities", [])),
            )
            definitions[definition.objective] = definition
        cls._workflows = definitions
        cls._loaded_from = path
        return definitions

    @classmethod
    def get(cls, objective: str) -> WorkflowDefinition | None:
        return cls.load().get(objective)

    @classmethod
    def infer_objective(cls, message: str) -> str | None:
        lower = message.lower()
        # Prefer the most specific trigger when definitions overlap.
        candidates = [
            (len(trigger), objective, workflow)
            for objective, workflow in cls.load().items()
            for trigger in workflow.triggers
            if trigger and trigger.lower() in lower
        ]
        for _, objective, workflow in sorted(candidates, reverse=True):
            if objective:
                return objective
        return None

    @classmethod
    def match_objectives(cls, message: str) -> tuple[str, ...]:
        """Return every governed objective matched by a configured trigger."""
        lower = message.lower()
        thermal_explicit = any(
            token in lower
            for token in (
                "热稳定", "耐热", "thermostability", "thermal stability",
                "heat stability", "melting temperature", "temperature stability",
            )
        )
        matches: list[str] = []
        for objective, workflow in cls.load().items():
            if objective == "stability" and thermal_explicit:
                # Generic stability is a distinct objective.  A thermal phrase
                # must not be double-counted as both generic and thermal.
                continue
            if any(trigger and trigger.lower() in lower for trigger in workflow.triggers):
                matches.append(objective)
        return tuple(matches)

    @classmethod
    def build_plan(cls, objective: str, sequence: str | None, task: str, available_tools: set[str]) -> WorkflowPlan | None:
        workflow = cls.get(objective)
        if workflow is None:
            return None
        plan = WorkflowPlan(workflow=workflow)
        plan.missing_capabilities = list(workflow.missing_capabilities)
        if not sequence or not sequence.strip():
            plan.blocked_reason = "工作流输入门控未通过：未检测到有效氨基酸序列"
            return plan

        sequence = sequence.strip()
        host = _extract_host(task)

        completed_stage_ids: set[int] = set()
        for stage in workflow.stages:
            for gate in stage.gates:
                if gate.get("type") == "requires_sequence" and not sequence:
                    plan.blocked_reason = str(gate.get("message", "序列输入门控未通过"))
                    return plan
                if gate.get("type") == "requires_host" and host is None:
                    plan.blocked_reason = str(gate.get("message", "宿主输入门控未通过"))
                    return plan
                if gate.get("type") == "requires_completed_stage":
                    required = int(gate["stage_id"])
                    if required not in completed_stage_ids:
                        plan.blocked_reason = str(gate.get("message", "前置阶段未完成"))
                        return plan

            stage_added = False
            missing_stage_tools: list[str] = []
            stage_tools = list(stage.tools)
            if "interproscan_sequence_submit" in stage_tools and "annotation_bundle" in stage_tools:
                stage_tools.remove("interproscan_sequence_submit")
                stage_tools.insert(stage_tools.index("annotation_bundle"), "interproscan_sequence_submit")
            for tool_name in stage_tools:
                # A canonical UniProt accession uses the cheaper live lookup;
                # InterProScan is only required for accession-less sequences.
                if tool_name == "interproscan_sequence_submit" and _extract_uniprot_id(task):
                    continue
                if tool_name == "residue_numbering_gate" and _extract_pdb_id(task) is None:
                    continue
                if tool_name == "esmfold_folding" and len(sequence) > ESMFOLD_MAX_SEQUENCE_LENGTH:
                    continue
                if tool_name not in available_tools:
                    # Objective gating is a capability enhancement.  Older
                    # deployments may not register it yet; leave the step out
                    # and let candidate execution fail closed at runtime.
                    if tool_name == "enzyme_objective_module_plan":
                        if tool_name not in plan.unavailable_tools:
                            plan.unavailable_tools.append(tool_name)
                        continue
                    if tool_name not in plan.unavailable_tools:
                        plan.unavailable_tools.append(tool_name)
                    missing_stage_tools.append(tool_name)
                    continue
                stage_added = True
                params = _params_for_tool(tool_name, sequence, task, objective, host)
                plan.steps.append({
                    "tool_name": tool_name,
                    "description": f"[{stage.name}] execute {tool_name}",
                    "params": params,
                    "stage_id": stage.id,
                    "stage_name": stage.name,
                })
            # A stage with missing required tools must fail closed. Partial
            # execution can otherwise be mistaken for a complete workflow.
            if missing_stage_tools:
                plan.blocked_reason = (
                    f"阶段 {stage.name} 缺少必需工具；"
                    f"缺失: {', '.join(missing_stage_tools)}"
                )
                return plan
            # An empty stage is valid for input gates, but a non-input stage
            # with no executable tool must block instead of silently advancing.
            if stage.id > 0 and stage.tools and not stage_added:
                plan.blocked_reason = (
                    f"阶段 {stage.name} 没有当前版本可执行的工具；"
                    f"缺失: {', '.join(stage.tools) or '未定义'}"
                )
                return plan
            completed_stage_ids.add(stage.id)
        return plan

    @classmethod
    def validate_tools(cls, available_tools: set[str]) -> dict[str, dict[str, list[str]]]:
        """Return startup diagnostics without hiding unavailable capabilities."""
        diagnostics: dict[str, dict[str, list[str]]] = {}
        for objective, workflow in cls.load().items():
            stage_tools = {tool for stage in workflow.stages for tool in stage.tools}
            diagnostics[objective] = {
                "registered_but_missing_from_workflow": sorted(available_tools - stage_tools),
                "workflow_tools_not_registered": sorted(stage_tools - available_tools),
                "declared_missing_capabilities": sorted(workflow.missing_capabilities),
            }
        return diagnostics


def _extract_host(task: str) -> str | None:
    lower = task.lower()
    if any(token in lower for token in ("gs115", "pichia", "毕赤酵母")):
        return "pichia_gs115"
    if any(token in lower for token in ("bacillus licheniformis", "地衣芽孢杆菌")):
        return "bacillus_licheniformis"
    return None


def _params_for_tool(
    tool_name: str,
    sequence: str,
    task: str,
    objective: str,
    host: str | None = None,
) -> dict[str, Any]:
    """Map common repository tool schemas to workflow inputs."""
    uniprot_id = _extract_uniprot_id(task)
    pdb_id = _extract_pdb_id(task)
    residue_numbers = _extract_residue_numbers(task)
    if tool_name == "interproscan_sequence_submit":
        params = {"sequence": sequence, "max_wait_seconds": 300}
        # Missing contact information is an optional evidence gap.  The tool
        # keeps its strict default behavior for direct callers, while governed
        # workflows continue through BLAST/annotation/identity evidence.
        if not os.getenv("INTERPROSCAN_EMAIL", "").strip():
            params["optional"] = True
    elif tool_name in {"annotation_bundle", "catalytic_site_lookup", "enzyme_identity_profile"}:
        params = {"sequence": sequence}
        if uniprot_id:
            params["uniprot_id"] = uniprot_id
        if residue_numbers:
            params["catalytic_residues"] = residue_numbers
        if pdb_id and tool_name != "catalytic_site_lookup":
            params["pdb_id"] = pdb_id
    elif tool_name == "enzyme_objective_module_plan":
        params = {
            "sequence": sequence,
            "objective": {
                "specific_activity": "specific_activity",
                "thermostability": "thermostability",
                "stability": "stability",
                "substrate_specificity": "substrate_specificity",
                "expression_secretion": "soluble_expression",
            }.get(objective, objective),
            "objective_signals": [objective],
        }
    elif tool_name == "thermostability_candidate_workflow":
        # The workflow never invents assay conditions or random substitutions.
        # Explicit data can be supplied through the registered tool/API; chat
        # receives needs_input until a complete objective is available.
        params = {"sequence": sequence}
        assay_marker = re.search(r"thermal_assay\s*[:：]\s*", task, re.IGNORECASE)
        if assay_marker:
            try:
                assay, _ = json.JSONDecoder().raw_decode(task[assay_marker.end():])
                if isinstance(assay, dict):
                    params["objective"] = assay
            except ValueError:
                pass
        mutations = re.findall(r"\b[ACDEFGHIKLMNPQRSTVWY][1-9][0-9]*[ACDEFGHIKLMNPQRSTVWY]\b", task.upper())
        if mutations:
            params["mutations"] = sorted(set(mutations))
    elif tool_name in {
        "blast_search", "predict_properties", "mutation_scan", "mutation_priority_score",
        "esmfold_folding", "enzyme_assistant_recommend", "enzyme_assistant_build",
    }:
        params: dict[str, Any] = {"sequence": sequence}
    elif tool_name == "sequence_search":
        params = {"query": sequence, "database": "uniprot", "max_results": 10}
    elif tool_name == "substrate_search":
        params = {"query": task, "namespace": "name", "limit": 10}
    elif tool_name == "protein_benchmark":
        params = {"query_sequence": sequence}
    elif tool_name == "residue_numbering_gate":
        params = {
            "pdb_id": pdb_id,
            "chain_id": _extract_chain_id(task) or "A",
            "residues": residue_numbers,
        }
    elif tool_name == "soluble_mpnn_design":
        params = {"sequence": sequence}
    elif tool_name == "diffdock_docking":
        # The current tool requires ligand/structure context not available in
        # every chat. Keep the workflow explicit and let the tool fail closed.
        params = {"sequence": sequence, "task": task}
    elif tool_name == "gromacs_md":
        params = {"sequence": sequence, "simulation_time_ns": 10.0}
    elif tool_name in {"disulfide_saltbridge_scan", "substrate_tunnel_analysis", "pocket_residue_lookup", "thermompnn_predict"}:
        # The executor maps a verified pdb_content artifact from a completed
        # upstream folding step. It never substitutes sequence text as PDB.
        params = {}
    else:
        params = {"sequence": sequence}
    if tool_name in {
        "codon_optimize",
        "secretion_efficiency_predict",
        "host_expression_yield_predict",
    } and host is not None:
        params["host"] = host
    if tool_name == "mutation_priority_score":
        params["engineering_goal"] = {
            "specific_activity": "activity",
            "thermostability": "thermostability",
            "stability": "stability",
            "substrate_specificity": "specificity",
            "expression_secretion": "general",
        }.get(objective, "general")
    if tool_name == "thermompnn_predict":
        params["mutations"] = []
    if tool_name == "enzyme_assistant_build":
        # Mutations are supplied by the caller; an empty plan fails closed in
        # the adapter instead of inventing candidates.
        params["mutations"] = []
    if tool_name == "enzyme_assistant_recommend":
        params["goal"] = "thermo" if objective == "thermostability" else "both"
    return params


def _extract_uniprot_id(task: str) -> str | None:
    """Extract an explicitly supplied canonical UniProt accession from task text."""
    for candidate in re.findall(r"\b[A-Z0-9]{6,10}\b", task.upper()):
        if re.fullmatch(r"[A-Z][0-9][A-Z0-9]{4,8}", candidate):
            return candidate
    return None


def _extract_pdb_id(task: str) -> str | None:
    match = re.search(r"\b[0-9][A-Z0-9]{3}\b", task.upper())
    return match.group(0) if match else None


def _extract_chain_id(task: str) -> str | None:
    match = re.search(r"(?:chain|链)\s*[:：]?\s*([A-Z0-9])", task.upper())
    return match.group(1) if match else None


def _extract_residue_numbers(task: str) -> list[int]:
    match = re.search(
        r"(?:residues?|残基(?:编号)?)\s*[:：]?\s*([0-9][0-9,，、\s]*)",
        task,
        re.IGNORECASE,
    )
    if not match:
        return []
    return sorted(set(int(value) for value in re.findall(r"\d+", match.group(1))))
