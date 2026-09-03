"""Plan-Execute-Synthesize Agent Graph with checkpoint-based pause/resume.

Inspired by VenusFactory2's multi-role agent pattern:
  PI (Principal Investigator) → CB (Computational Biologist)
  → MLS (Machine Learning Specialist) → SC (Scientific Critic)
"""

from dataclasses import dataclass, field
from typing import TypedDict, Annotated, Any, AsyncGenerator
import asyncio
from contextlib import suppress
import functools
import hashlib
import json
import logging
import re
import time

logger = logging.getLogger(__name__)

from app.core.llm_gateway import llm_gateway
from app.core.config import settings
from app.services.agent_policy import get_agent_strategy_policy, policy_tokens
from app.services.strategy_checkpoint import list_recent_strategy_memory
from app.services.task_evidence import classify_task_evidence
from app.services.tool_orchestration_contract import validate_tool_plan
from app.services.report_quality_contract import assess_enzyme_report_completion
from app.services.identity_consistency import check_identity_consistency, sequence_hash
from app.tools.registry import ToolRegistry
from app.tools.scientific_claim_gate import scientific_claim_gate
from app.services.property_workflow_governance import PropertyWorkflowRouter, WorkflowPolicyValidator, compare_legacy_plan
from app.services.property_workflow_audit import persist_shadow_audit
from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime
from app.core.skills import get_skills_metadata, read_skill
from app.core.agent_roles import (
    PI_SYSTEM_PROMPT, CB_SYSTEM_PROMPT,
    MLS_SYSTEM_PROMPT, SC_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    ENZYME_ENGINEERING_REPORT_PROTOCOL,
)
from app.core.coordinator_agent import CoordinatorAgent

# Lazy import for experience store (avoids circular import at module load)
def _get_experience_store():
    from app.memory.experience_store import get_experience_store, ExperienceRecord
    return get_experience_store(), ExperienceRecord

# Tools that require a protein sequence — skip if no sequence available
_SEQUENCE_REQUIRED_TOOLS = frozenset({
    "alphafold_folding", "esmfold_folding", "predict_properties",
    "mutation_scan", "mutation_priority_score", "protein_benchmark",
    "enzyme_identity_profile", "enzyme_function", "kcat_predict", "protssn_score", "blast_search",
    "enzyme_objective_module_plan",
    "rosetta_ddg",
})

# Tools that require a PDB structure — skip if no PDB available
_PDB_REQUIRED_TOOLS = frozenset({
    "proteinmpnn_design",
    "esm_if1_design",
    "gromacs_md",
    "build_site_structure_function_features",
    "pocket_residue_lookup",
})

_STRUCTURE_GATE_TOOLS = frozenset({
    "structure_search_foldseek",
    "residue_mapping_sifts",
    "residue_numbering_gate",
    "build_site_structure_function_features",
    "pocket_residue_lookup",
})

_STRUCTURE_DEPENDENT_TOOLS = frozenset({
    "gromacs_md",
    "proteinmpnn_design",
    "esm_if1_design",
})

_ENZYME_FOUNDATION_TOOLS = frozenset({
    "annotation_bundle",
    "enzyme_identity_profile",
    "enzyme_objective_module_plan",
    "protein_benchmark",
    "enzyme_function",
    "mutation_priority_score",
})

_IDENTITY_GATED_CANDIDATE_TOOLS = frozenset({
    "mutation_scan",
    "protssn_score",
})

_OBJECTIVE_GATED_CANDIDATE_TOOLS = frozenset({
    "mutation_scan",
    "protssn_score",
})

@dataclass
class PlanStep:
    id: int
    tool_name: str
    description: str
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending | running | submitted | completed | failed
    result: Any = None
    error: str | None = None
    duration: float = 0.0


@dataclass
class ChatSnapshot:
    """Full state snapshot for SSE streaming (inspired by VenusFactory2)."""
    stage: str  # router | research | plan | execute | synthesize | done
    plan: list[dict] = field(default_factory=list)
    raw_plan_payload: list[dict] = field(default_factory=list, repr=False)
    current_step: int = 0
    step_results: list[dict] = field(default_factory=list)
    research_notes: str = ""
    final_report: str = ""
    waiting_for: str | None = None  # plan_confirmation | step_review | clarification
    strategy_signature: str | None = None
    task_fingerprint: str | None = None
    next_action: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    tokens: str = ""
    error: str | None = None
    workflow_shadow: dict[str, Any] = field(default_factory=dict)
    task_contract: dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    """Multi-role agent orchestrator with Plan-Execute-Synthesize pattern."""

    # Tool result cache: (tool_name, params_hash) → result  (max 256 entries)
    _tool_cache: dict[str, Any] = {}
    _TOOL_CACHE_MAX = 256

    @classmethod
    def _cache_key(cls, tool_name: str, params: dict) -> str:
        raw = json.dumps(params, sort_keys=True, default=str)
        h = hashlib.md5(raw.encode()).hexdigest()[:12]
        return f"{tool_name}:{h}"

    @classmethod
    def _cache_get(cls, key: str) -> Any | None:
        return cls._tool_cache.get(key)

    @classmethod
    def _cache_put(cls, key: str, result: Any) -> None:
        if len(cls._tool_cache) >= cls._TOOL_CACHE_MAX:
            # Evict oldest entry
            oldest = next(iter(cls._tool_cache))
            del cls._tool_cache[oldest]
        cls._tool_cache[key] = result

    def __init__(self):
        self._snapshot: ChatSnapshot | None = None
        self._coordinator = CoordinatorAgent()

    @staticmethod
    def _is_governance_evidence_request(message: str) -> bool:
        """Detect platform-state questions that require audited local evidence."""
        lower = str(message or "").lower()
        return any(token in lower for token in (
            "model claim", "model quality", "training eligible", "training status",
            "release ready", "release status", "customer delivery", "customer-ready",
            "模型声明", "模型质量", "训练资格", "训练状态", "发布状态", "客户交付",
            "客户可交付", "能不能交付",
        ))

    @staticmethod
    def _is_connectivity_status_request(message: str) -> bool:
        """Detect a question about current outbound connectivity, not a search query."""
        lower = str(message or "").strip().lower()
        if not lower:
            return False
        connectivity_terms = (
            "联网", "连网", "网络通", "外网", "网络连接",
            "internet connection", "connected to the internet", "internet connected", "online",
        )
        question_terms = (
            "吗", "么", "没有", "是否", "能不能", "可以", "状态", "通不通", "现在", "当前",
            "are you", "can you", "status", "connected", "online",
        )
        search_terms = (
            "搜索", "检索", "查文献", "查论文", "pubmed", "crossref", "doi", "pmid",
            "search", "literature", "paper", "publication",
        )
        return (
            any(term in lower for term in connectivity_terms)
            and any(term in lower for term in question_terms)
            and not any(term in lower for term in search_terms)
        )

    @classmethod
    def _wants_live_literature_search(cls, message: str) -> bool:
        """Detect requests that should use the live PubMed/Crossref search tool."""
        lower = str(message or "").lower()
        if cls._is_connectivity_status_request(message):
            return False
        return any(token in lower for token in (
            "网络搜索", "在线搜索", "实时搜索", "联网搜索", "最新", "最近", "文献",
            "论文", "pubmed", "crossref", "doi", "pmid", "literature",
            "paper", "papers", "publication", "publications",
        ))

    @staticmethod
    def _iter_text_stream_chunks(text: str, chunk_size: int = 96):
        """Yield text chunks without normalizing whitespace or Markdown layout."""
        if not text:
            return
        for start in range(0, len(text), chunk_size):
            yield text[start:start + chunk_size]

    @staticmethod
    def _is_document_reply_request(message: str) -> bool:
        lower = message.lower()
        return any(kw in lower for kw in [
            "checklist", "sop", "protocol", "schedule", "template", "table",
            "清单", "执行清单", "实验执行", "排期", "模板", "表格", "登记表",
            "整理成", "直接执行", "给学生", "给同事",
        ])

    @staticmethod
    def _is_design_pipeline_step(tool_name: str) -> bool:
        return tool_name in {
            "sequence_search",
            "rfdiffusion_design",
            "chroma_design",
            "proteinmpnn_design",
            "esmfold_folding",
            "soluble_mpnn_design",
            "predict_properties",
        }

    @staticmethod
    def _is_structure_gate_step(tool_name: str) -> bool:
        return tool_name in _STRUCTURE_GATE_TOOLS

    @staticmethod
    def _is_structure_dependent_step(tool_name: str) -> bool:
        return tool_name in _STRUCTURE_DEPENDENT_TOOLS

    @classmethod
    def _requires_ordered_execution(cls, plan: list[PlanStep]) -> bool:
        return (
            any(cls._is_structure_gate_step(step.tool_name) for step in plan)
            or any(cls._is_design_pipeline_step(step.tool_name) for step in plan)
            or any(step.tool_name in _ENZYME_FOUNDATION_TOOLS for step in plan)
        )

    @classmethod
    def _identity_gate_passed(cls, completed_steps: list[PlanStep]) -> bool:
        """Require a confirmed, coordinate-ready profile before candidate generation."""
        latest_identity = next(
            (
                step.result for step in reversed(completed_steps)
                if step.tool_name == "enzyme_identity_profile" and step.status == "completed"
            ),
            None,
        )
        profile = latest_identity if isinstance(latest_identity, dict) else cls._safe_parse_json(str(latest_identity or ""))
        guardrail = profile.get("guardrail") if isinstance(profile, dict) else {}
        return (
            isinstance(profile, dict)
            and profile.get("identity_status") == "identified"
            and isinstance(guardrail, dict)
            and guardrail.get("status") == "ready"
        )

    @classmethod
    def _objective_gate_passed(cls, completed_steps: list[PlanStep]) -> bool:
        """Require objective-specific evidence before mutation candidate generation."""
        latest_objective = next(
            (
                step.result for step in reversed(completed_steps)
                if step.tool_name == "enzyme_objective_module_plan" and step.status == "completed"
            ),
            None,
        )
        if latest_objective is None:
            return True
        payload = latest_objective if isinstance(latest_objective, dict) else cls._safe_parse_json(str(latest_objective or ""))
        return (
            isinstance(payload, dict)
            and payload.get("status") == "ready"
            and payload.get("candidate_output_allowed") is True
        )

    @classmethod
    def _structure_gate_passed(cls, step: PlanStep) -> bool:
        if step.status not in {"completed", "submitted"}:
            return False
        payload = step.result if isinstance(step.result, dict) else cls._safe_parse_json(str(step.result or ""))
        if step.tool_name == "structure_search_foldseek":
            query_structure = payload.get("query_structure") if isinstance(payload, dict) else None
            return bool(query_structure) or payload.get("found") is True
        if step.tool_name == "residue_mapping_sifts":
            return bool(payload.get("found")) and str(payload.get("status") or "").lower() == "completed"
        if step.tool_name == "residue_numbering_gate":
            return str(payload.get("status") or "").lower() in {"allowed", "warning"}
        return True

    @staticmethod
    def _should_submit_interactive_async_step(step: PlanStep) -> bool:
        """Return true when chat should enqueue a tool instead of running it inline."""
        try:
            from app.services.scheduler import ASYNC_TOOLS
        except Exception:
            logger.exception("Unable to load async tool registry")
            return False
        return step.tool_name in ASYNC_TOOLS and not step.params.get("allow_interactive_sync_run")

    @staticmethod
    def _normalize_interactive_async_params(step: PlanStep) -> PlanStep:
        """Prepare async tool params for real background execution."""
        if step.tool_name != "gromacs_md":
            return step

        step.params = {
            **step.params,
            "replicate_plan_only": False,
            "upload_artifacts": step.params.get("upload_artifacts", True),
        }
        step.description = (
            "Submit a real molecular dynamics job to the background task runner; "
            "poll the returned task status for progress, cancellation, and artifacts."
        )
        return step

    @staticmethod
    async def _submit_interactive_async_step(
        step: PlanStep,
        *,
        current_user: dict | None = None,
        audit_session: Any | None = None,
    ) -> dict:
        """Submit a long-running tool from chat without blocking the SSE stream."""
        if not current_user or current_user.get("id") is None:
            raise RuntimeError(f"Cannot submit async tool {step.tool_name}: missing current user")

        from app.services.scheduler import dispatch_tool, get_task_profile
        from app.services.tool_task_audit import record_task_submitted
        from app.services.tool_task_store import (
            record_tool_task_owner,
            record_tool_task_runtime_policy,
        )

        task_id = dispatch_tool(step.tool_name, step.params)
        profile = get_task_profile(step.tool_name)
        await record_tool_task_owner(task_id, current_user["id"], step.tool_name)
        await record_tool_task_runtime_policy(
            task_id,
            queue=profile.queue,
            soft_time_limit=profile.soft_time_limit,
            time_limit=profile.time_limit,
        )
        audit_recorded = False
        audit_error = None
        if audit_session is not None:
            try:
                await record_task_submitted(
                    audit_session,
                    task_id=task_id,
                    user_id=current_user["id"],
                    tool_name=step.tool_name,
                    params=step.params,
                    queue=profile.queue,
                    soft_time_limit=profile.soft_time_limit,
                    time_limit=profile.time_limit,
                )
                await audit_session.commit()
                audit_recorded = True
            except Exception as exc:
                logger.exception("Failed to record interactive async task audit for %s", task_id)
                audit_error = str(exc)
                with suppress(Exception):
                    await audit_session.rollback()

        return {
            "status": "submitted",
            "tool": step.tool_name,
            "task_id": task_id,
            "queue": profile.queue,
            "soft_time_limit": profile.soft_time_limit,
            "time_limit": profile.time_limit,
            "status_url": f"/api/tools/tasks/{task_id}",
            "cancel_url": f"/api/tools/tasks/{task_id}/cancel",
            "artifacts_url": f"/api/tools/tasks/{task_id}/artifacts",
            "audit_recorded": audit_recorded,
            "audit_error": audit_error,
            "note": (
                "Long-running tool submitted to the background worker. "
                "This is not a fixed report or plan-only shortcut; poll status_url for real execution progress."
            ),
        }

    @staticmethod
    def _extract_pdb_from_design_result(result: Any) -> str | None:
        if not isinstance(result, dict):
            return None

        def _format_chain(chain_id: str, coords: list[tuple[float, float, float]]) -> list[str]:
            lines: list[str] = []
            for idx, (x, y, z) in enumerate(coords, start=1):
                lines.append(
                    f"ATOM  {idx:5d}  CA  ALA {chain_id:>2}{idx:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 80.00           C"
                )
            return lines

        if "designs" not in result or not result["designs"]:
            return None

        design0 = result["designs"][0]
        sym = design0.get("symmetry_result", {})
        chains = sym.get("chains", [])
        if not chains:
            return None

        pdb_lines: list[str] = []
        atom_serial = 1
        for chain in chains:
            chain_id = str(chain.get("chain_id", "A"))[:2].strip() or "A"
            coords = chain.get("coordinates") or []
            for residue_index, coord in enumerate(coords, start=1):
                if not isinstance(coord, (list, tuple)) or len(coord) != 3:
                    continue
                x, y, z = coord
                pdb_lines.append(
                    f"ATOM  {atom_serial:5d}  CA  ALA {chain_id:>2}{residue_index:4d}    "
                    f"{float(x):8.3f}{float(y):8.3f}{float(z):8.3f}  1.00 80.00           C"
                )
                atom_serial += 1
            pdb_lines.append("TER")

        if not pdb_lines:
            return None
        pdb_lines.append("END")
        return "\n".join(pdb_lines)

    @staticmethod
    def _extract_sequence_from_result(result: Any) -> str | None:
        if not isinstance(result, dict):
            return None

        if isinstance(result.get("best_sequence"), str) and result["best_sequence"].strip():
            return result["best_sequence"].strip()

        designs = result.get("designs")
        if isinstance(designs, list) and designs:
            first = designs[0]
            if isinstance(first, dict) and isinstance(first.get("sequence"), str) and first["sequence"].strip():
                return first["sequence"].strip()

        seq = result.get("sequence")
        if isinstance(seq, str) and seq.strip():
            return seq.strip()

        return None

    @staticmethod
    def _sequence_from_residue_mapping(result: Any) -> str | None:
        if not isinstance(result, dict):
            return None
        mappings = result.get("mappings")
        if not isinstance(mappings, list):
            return None
        by_chain: dict[str, list[tuple[int, str]]] = {}
        for row in mappings:
            if not isinstance(row, dict):
                continue
            aa = str(row.get("residue_aa") or row.get("residue") or "").strip().upper()[:1]
            if not aa or aa == "X":
                continue
            try:
                pos = int(row.get("pdb_residue_no"))
            except (TypeError, ValueError):
                continue
            chain = str(row.get("chain_id") or "A")
            by_chain.setdefault(chain, []).append((pos, aa))
        if not by_chain:
            return None
        residues = max(by_chain.values(), key=len)
        residues.sort(key=lambda item: item[0])
        seq = "".join(aa for _pos, aa in residues)
        return seq if len(seq) >= 20 else None

    def _bridge_step_params(self, step: PlanStep, completed_steps: list[PlanStep]) -> PlanStep:
        """Inject missing dependent parameters from earlier completed design steps."""
        if not completed_steps:
            return step

        latest_pdb_result = next(
            (s.result for s in reversed(completed_steps) if s.tool_name == "rfdiffusion_design" and s.status == "completed"),
            None,
        )
        latest_sequence_result = next(
            (
                s.result for s in reversed(completed_steps)
                if s.tool_name in {"proteinmpnn_design", "chroma_design", "soluble_mpnn_design", "sequence_search"}
                and s.status == "completed"
            ),
            None,
        )
        latest_identity_result = next(
            (
                s.result for s in reversed(completed_steps)
                if s.tool_name == "enzyme_identity_profile" and s.status == "completed"
            ),
            None,
        )
        latest_annotation_result = next(
            (
                s.result for s in reversed(completed_steps)
                if s.tool_name == "annotation_bundle" and s.status == "completed"
            ),
            None,
        )
        latest_structure_search_result = next(
            (
                s.result for s in reversed(completed_steps)
                if s.tool_name == "structure_search_foldseek" and s.status == "completed"
            ),
            None,
        )
        latest_mapping_result = next(
            (
                s.result for s in reversed(completed_steps)
                if s.tool_name == "residue_mapping_sifts" and s.status == "completed"
            ),
            None,
        )
        latest_site_feature_result = next(
            (
                s.result for s in reversed(completed_steps)
                if s.tool_name == "build_site_structure_function_features" and s.status == "completed"
            ),
            None,
        )
        latest_pocket_result = next(
            (
                s.result for s in reversed(completed_steps)
                if s.tool_name == "pocket_residue_lookup" and s.status == "completed"
            ),
            None,
        )
        latest_objective_result = next(
            (
                s.result for s in reversed(completed_steps)
                if s.tool_name == "enzyme_objective_module_plan" and s.status == "completed"
            ),
            None,
        )
        latest_priority_result = next(
            (
                s.result for s in reversed(completed_steps)
                if s.tool_name == "mutation_priority_score" and s.status == "completed"
            ),
            None,
        )
        if step.tool_name == "proteinmpnn_design" and not step.params.get("pdb_structure"):
            pdb_text = self._extract_pdb_from_design_result(latest_pdb_result)
            if pdb_text:
                step.params = {**step.params, "pdb_structure": pdb_text}

        if step.tool_name == "esmfold_folding" and not step.params.get("sequence"):
            sequence = self._extract_sequence_from_result(latest_sequence_result)
            if sequence:
                step.params = {**step.params, "sequence": sequence}

        if step.tool_name == "chroma_design" and not step.params.get("length"):
            rf_params = latest_pdb_result.get("parameters", {}) if isinstance(latest_pdb_result, dict) else {}
            length = rf_params.get("length")
            if isinstance(length, int) and length > 0:
                step.params = {**step.params, "length": length}

        if step.tool_name in {"protein_benchmark", "enzyme_function", "mutation_priority_score"} and not step.params.get("identity_profile"):
            identity_profile = self._safe_parse_json(str(latest_identity_result)) if latest_identity_result is not None else {}
            if identity_profile:
                step.params = {**step.params, "identity_profile": identity_profile}

        if step.tool_name == "enzyme_objective_module_plan" and not step.params.get("identity_profile"):
            identity_profile = self._safe_parse_json(str(latest_identity_result)) if latest_identity_result is not None else {}
            if identity_profile:
                step.params = {**step.params, "identity_profile": identity_profile}

        if step.tool_name == "mutation_priority_score" and not step.params.get("objective_module_plan"):
            objective_plan = self._safe_parse_json(str(latest_objective_result)) if latest_objective_result is not None else {}
            if objective_plan:
                step.params = {**step.params, "objective_module_plan": objective_plan}

        if step.tool_name == "mutation_priority_score" and not step.params.get("pdb_coordinate_mapping"):
            mappings = (
                latest_mapping_result.get("numbering_registry_rows")
                or latest_mapping_result.get("mappings", [])
                if isinstance(latest_mapping_result, dict)
                else []
            )
            if isinstance(mappings, list) and mappings:
                step.params = {**step.params, "pdb_coordinate_mapping": mappings}

        if step.tool_name == "mutation_priority_score" and not step.params.get("site_structure_features"):
            features = latest_site_feature_result.get("features", []) if isinstance(latest_site_feature_result, dict) else []
            if isinstance(features, list) and features:
                step.params = {**step.params, "site_structure_features": features}

        if step.tool_name == "mutation_priority_score" and not step.params.get("pocket_residue_positions"):
            pocket_rows = latest_pocket_result.get("residue_positions", []) if isinstance(latest_pocket_result, dict) else []
            if isinstance(pocket_rows, list) and pocket_rows:
                mapping_rows = (
                    latest_mapping_result.get("numbering_registry_rows")
                    or latest_mapping_result.get("mappings", [])
                    if isinstance(latest_mapping_result, dict)
                    else []
                )
                by_author: dict[tuple[str, int, str], int] = {}
                for mapping in mapping_rows if isinstance(mapping_rows, list) else []:
                    if not isinstance(mapping, dict):
                        continue
                    try:
                        author_position = int(mapping.get("target_position") or mapping.get("pdb_residue_no"))
                        source_position = int(mapping.get("source_position") or mapping.get("user_sequence_position") or mapping.get("uniprot_position"))
                    except (TypeError, ValueError):
                        continue
                    chain = str(mapping.get("target_chain_id") or mapping.get("chain_id") or "A")
                    insertion = str(mapping.get("target_insertion_code") or mapping.get("insertion_code") or "")
                    by_author[(chain, author_position, insertion)] = source_position
                normalized_pocket_rows: list[dict] = []
                for pocket in pocket_rows:
                    if not isinstance(pocket, dict):
                        continue
                    row = dict(pocket)
                    try:
                        author_position = int(row.get("pdb_residue_no"))
                    except (TypeError, ValueError):
                        normalized_pocket_rows.append(row)
                        continue
                    chain = str(row.get("chain_id") or "A")
                    insertion = str(row.get("insertion_code") or "")
                    source_position = by_author.get((chain, author_position, insertion))
                    if source_position is None:
                        source_position = by_author.get((chain, author_position, ""))
                    if source_position is not None:
                        row["user_sequence_position"] = source_position
                        row["mapping_source"] = "residue_mapping_sifts"
                    normalized_pocket_rows.append(row)
                pocket_rows = normalized_pocket_rows
                step.params = {**step.params, "pocket_residue_positions": pocket_rows}

        if step.tool_name == "build_site_structure_function_features":
            bridged_params = dict(step.params)
            mappings = (
                latest_mapping_result.get("numbering_registry_rows")
                or latest_mapping_result.get("mappings", [])
                if isinstance(latest_mapping_result, dict)
                else []
            )
            if not bridged_params.get("residue_mappings") and isinstance(mappings, list) and mappings:
                bridged_params["residue_mappings"] = mappings
            identity_profile = self._safe_parse_json(str(latest_identity_result)) if latest_identity_result is not None else {}
            protected_positions = identity_profile.get("protected_positions") if isinstance(identity_profile, dict) else None
            if not bridged_params.get("protected_positions") and isinstance(protected_positions, list) and protected_positions:
                bridged_params["protected_positions"] = protected_positions
            key_residues = identity_profile.get("key_residues") if isinstance(identity_profile, dict) else None
            catalytic_positions: list[int] = []
            if isinstance(key_residues, list):
                for item in key_residues:
                    if not isinstance(item, dict):
                        continue
                    role = str(item.get("role") or "").lower()
                    if "catalytic" not in role and "催化" not in role:
                        continue
                    try:
                        position = int(item.get("position"))
                    except (TypeError, ValueError):
                        continue
                    if position not in catalytic_positions:
                        catalytic_positions.append(position)
            if not bridged_params.get("catalytic_positions") and catalytic_positions:
                bridged_params["catalytic_positions"] = catalytic_positions
            if bridged_params != step.params:
                step.params = bridged_params

        priority_payload = self._safe_parse_json(str(latest_priority_result)) if latest_priority_result is not None else {}
        if priority_payload:
            candidate_rows = priority_payload.get("experiment_design_table")
            if not isinstance(candidate_rows, list) or not candidate_rows:
                candidate_rows = []
                for key in ("tier_1_candidates", "tier_2_candidates"):
                    rows = priority_payload.get(key)
                    if isinstance(rows, list):
                        candidate_rows.extend(rows)
            candidate_positions: list[int] = []
            candidate_mutations: list[str] = []
            for row in candidate_rows:
                if not isinstance(row, dict):
                    continue
                try:
                    pos = int(row.get("position") or row.get("user_position") or 0)
                except (TypeError, ValueError):
                    pos = 0
                if pos > 0 and pos not in candidate_positions:
                    candidate_positions.append(pos)
                raw_mutations = row.get("recommended_mutations")
                if isinstance(raw_mutations, list):
                    for mutation in raw_mutations:
                        code = mutation.get("mutation") if isinstance(mutation, dict) else mutation
                        if isinstance(code, str) and code and code not in candidate_mutations:
                            candidate_mutations.append(code)
            if step.tool_name == "mutation_scan" and not step.params.get("positions") and candidate_positions:
                step.params = {**step.params, "positions": candidate_positions[:12]}
            if step.tool_name == "protssn_score" and not step.params.get("mutations") and candidate_mutations:
                step.params = {**step.params, "mutations": candidate_mutations[:50]}

        if step.tool_name == "enzyme_identity_profile" and not step.params.get("evidence_bundle"):
            annotation_bundle = self._safe_parse_json(str(latest_annotation_result)) if latest_annotation_result is not None else {}
            if annotation_bundle:
                step.params = {**step.params, "evidence_bundle": annotation_bundle}
        if step.tool_name == "enzyme_identity_profile":
            structure_evidence = (
                self._safe_parse_json(str(latest_structure_search_result))
                if latest_structure_search_result is not None else {}
            )
            residue_mapping = (
                self._safe_parse_json(str(latest_mapping_result))
                if latest_mapping_result is not None else {}
            )
            if structure_evidence and not step.params.get("structure_evidence"):
                step.params = {**step.params, "structure_evidence": structure_evidence}
            if residue_mapping and not step.params.get("residue_mapping"):
                step.params = {**step.params, "residue_mapping": residue_mapping}

        if step.tool_name == "residue_numbering_gate" and not step.params.get("mapping_rows"):
            registry_rows = latest_mapping_result.get("numbering_registry_rows", []) if isinstance(latest_mapping_result, dict) else []
            if isinstance(registry_rows, list) and registry_rows:
                step.params = {**step.params, "mapping_rows": registry_rows}
                return step
            mappings = latest_mapping_result.get("mappings", []) if isinstance(latest_mapping_result, dict) else []
            mapping_rows = []
            for row in mappings:
                if not isinstance(row, dict):
                    continue
                source_position = row.get("uniprot_position")
                target_position = row.get("pdb_residue_no")
                try:
                    source_position = int(source_position)
                    target_position = int(target_position)
                except (TypeError, ValueError):
                    continue
                confidence = str(row.get("mapping_confidence") or row.get("confidence") or "unknown")
                mapping_rows.append({
                    "source_scheme": "user_sequence",
                    "source_position": source_position,
                    "target_scheme": "pdb_author",
                    "target_position": target_position,
                    "chain_id": row.get("chain_id"),
                    "confidence": confidence,
                    "method": str(row.get("source") or "residue_mapping_sifts"),
                    "missing_in_structure": False,
                })
            if mapping_rows:
                step.params = {**step.params, "mapping_rows": mapping_rows}

        return step

    async def _attach_wet_lab_calibration_context(
        self,
        step: PlanStep,
        *,
        current_user: dict | None = None,
        audit_session: Any | None = None,
        project_id: str | None = None,
    ) -> PlanStep:
        """Attach latest same-project wet-lab calibration summary as ranking context."""
        if step.tool_name != "mutation_priority_score":
            return step
        if step.params.get("wet_lab_calibration_summary"):
            return step
        if not current_user or current_user.get("id") is None or audit_session is None or not project_id:
            return step

        objective = str(step.params.get("engineering_goal") or "multi_objective")
        try:
            from app.services.wet_lab_calibration import list_wet_lab_calibration_runs

            runs = await list_wet_lab_calibration_runs(
                audit_session,
                user_id=int(current_user["id"]),
                project_id=project_id,
                objective=objective,
                limit=1,
            )
            if not runs and objective != "multi_objective":
                runs = await list_wet_lab_calibration_runs(
                    audit_session,
                    user_id=int(current_user["id"]),
                    project_id=project_id,
                    objective="multi_objective",
                    limit=1,
                )
            if not runs:
                return step
            latest = runs[0]
            raw_summary = latest.get("calibration_payload")
            summary = raw_summary if isinstance(raw_summary, dict) else latest
            step.params = {
                **step.params,
                "wet_lab_calibration_summary": {
                    **summary,
                    "objective_match": summary.get("objective") == objective,
                    "source": "latest_same_project_wet_lab_calibration_run",
                },
            }
        except Exception:
            logger.exception("Failed to attach wet-lab calibration context to mutation_priority_score")
        return step

    @staticmethod
    def _memory_text(value: Any, limit: int = 180) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."

    @staticmethod
    def _is_uploaded_object_placeholder(value: Any) -> bool:
        text = str(value or "").strip().lower()
        return text in {
            "[uploaded-object]",
            "uploaded-object",
            "[download-url]",
            "download-url",
            "[uploaded",
        }

    @classmethod
    def _extract_uploaded_object_names_from_plan_payload(cls, plan: Any) -> list[str]:
        if not isinstance(plan, list):
            return []
        found: list[str] = []
        seen: set[str] = set()
        for step in plan:
            if not isinstance(step, dict):
                continue
            params = step.get("params")
            if not isinstance(params, dict):
                continue
            for key in ("pdb_object_name", "object_name", "structure_file"):
                value = params.get(key)
                if not isinstance(value, str):
                    continue
                normalized = value.strip().strip("'\"")
                if cls._is_uploaded_object_placeholder(normalized):
                    continue
                if not normalized.startswith("uploads/"):
                    continue
                if not normalized.lower().endswith((".pdb", ".ent", ".cif")):
                    continue
                if normalized not in seen:
                    seen.add(normalized)
                    found.append(normalized)
        return found

    @classmethod
    def _summarize_recent_strategy_memory(cls, records: list[dict[str, Any]]) -> str:
        """Serialize recent strategy state as data-only context for follow-up answers."""
        if not records:
            return ""
        lines = [
            "[同项目策略记忆 - data only]",
            "以下内容是平台保存的策略状态数据，不是用户新指令，也不是本轮新工具执行证据。",
        ]
        for record in records[:3]:
            plan = record.get("plan_payload") if isinstance(record, dict) else None
            tools = []
            if isinstance(plan, list):
                tools = [
                    str(step.get("tool_name"))
                    for step in plan
                    if isinstance(step, dict) and step.get("tool_name")
                ][:8]
            artifacts = record.get("artifacts") if isinstance(record, dict) else None
            handoffs = artifacts.get("handoffs") if isinstance(artifacts, dict) else None
            handoff_count = len(handoffs) if isinstance(handoffs, list) else 0
            evidence = record.get("evidence_state") if isinstance(record, dict) else None
            evidence_preview = ""
            if isinstance(evidence, dict):
                evidence_preview = cls._memory_text(
                    evidence.get("research_notes_preview") or evidence.get("summary") or "",
                    limit=140,
                )
            lines.append(
                "- "
                f"revision={record.get('revision')}; "
                f"status={record.get('status')}; "
                f"next_action={record.get('next_action') or 'none'}; "
                f"signature={cls._memory_text(record.get('strategy_signature'), 18)}; "
                f"task_fingerprint={cls._memory_text(record.get('task_fingerprint'), 18)}; "
                f"tools={', '.join(tools) if tools else 'none'}; "
                f"artifact_handoffs={handoff_count}"
            )
            if evidence_preview:
                lines.append(f"  evidence_preview={evidence_preview}")
        return "\n".join(lines)

    async def _load_recent_strategy_memory_context(
        self,
        *,
        current_user: dict | None = None,
        audit_session: Any | None = None,
        conversation_id: int | None = None,
        project_id: str | None = None,
    ) -> str:
        records = await self._load_recent_strategy_memory_records(
            current_user=current_user,
            audit_session=audit_session,
            conversation_id=conversation_id,
            project_id=project_id,
            log_label="follow-up synthesis",
        )
        return self._summarize_recent_strategy_memory(records)

    async def _load_recent_strategy_memory_records(
        self,
        *,
        current_user: dict | None = None,
        audit_session: Any | None = None,
        conversation_id: int | None = None,
        project_id: str | None = None,
        log_label: str = "strategy memory",
    ) -> list[dict[str, Any]]:
        """Load recent strategy checkpoints as structured data."""
        if not current_user or current_user.get("id") is None or audit_session is None:
            return []
        if not project_id and conversation_id is None:
            return []
        try:
            return await list_recent_strategy_memory(
                audit_session,
                user_id=int(current_user["id"]),
                conversation_id=conversation_id,
                project_id=project_id,
                limit=3,
            )
        except Exception:
            logger.exception("Failed to load recent strategy memory for %s", log_label)
            return []

    @classmethod
    def _summarize_recent_strategy_planning_context(cls, records: list[dict[str, Any]]) -> str:
        """Internal, raw-object continuation context for planning follow-up turns."""
        if not records:
            return ""
        lines: list[str] = []
        seen_objects: set[str] = set()
        for record in records[:3]:
            if not isinstance(record, dict):
                continue
            task_text = str(record.get("task_text") or "").strip()
            summary = cls._display_task_summary(task_text) if task_text else ""
            if summary and summary not in {"[空任务]", "[只包含上传附件元数据]"}:
                lines.append(f"[Prior user request summary: {summary[:240]}]")

            object_names = cls._extract_uploaded_object_names_from_plan_payload(record.get("plan_payload"))
            object_from_task = cls._extract_attached_object_name(task_text)
            if object_from_task:
                object_names.insert(0, object_from_task)
            for object_name in object_names:
                if object_name in seen_objects:
                    continue
                seen_objects.add(object_name)
                lines.append(f"[Uploaded structure object_name: {object_name}]")

            if lines:
                break
        return "\n".join(lines)

    async def _load_recent_strategy_planning_context(
        self,
        *,
        current_user: dict | None = None,
        audit_session: Any | None = None,
        conversation_id: int | None = None,
        project_id: str | None = None,
        message: str = "",
    ) -> str:
        """Recover raw task anchors for continuation planning from server checkpoints."""
        if self._message_starts_new_task(message) and not self._message_requests_continuation(message):
            return ""
        if not self._message_requests_continuation(message):
            return ""
        records = await self._load_recent_strategy_memory_records(
            current_user=current_user,
            audit_session=audit_session,
            conversation_id=conversation_id,
            project_id=project_id,
            log_label="continuation planning",
        )
        return self._summarize_recent_strategy_planning_context(records)

    @staticmethod
    def _artifact_item_from_mapping(raw: dict[str, Any], *, fallback_kind: str = "file") -> dict[str, Any] | None:
        name = raw.get("name") or raw.get("filename") or raw.get("file_name") or raw.get("object_name") or raw.get("path")
        object_name = raw.get("object_name") or raw.get("objectName")
        download_url = raw.get("download_url") or raw.get("downloadUrl") or raw.get("url")
        if not any([name, object_name, download_url, raw.get("task_id"), raw.get("status_url")]):
            return None
        return {
            "kind": raw.get("kind") or fallback_kind,
            "name": str(name or object_name or raw.get("task_id") or "artifact"),
            "category": raw.get("category") or raw.get("group") or raw.get("type"),
            "object_name": object_name,
            "download_url": download_url,
            "size": raw.get("size") or raw.get("size_bytes"),
            "task_id": raw.get("task_id"),
            "status_url": raw.get("status_url"),
            "artifacts_url": raw.get("artifacts_url"),
        }

    @classmethod
    def _extract_artifact_handoff_items(cls, tool_name: str, result: Any) -> list[dict[str, Any]]:
        """Extract generic artifacts without coupling the UI to specific tools."""
        if not isinstance(result, dict):
            return []

        items: list[dict[str, Any]] = []

        if result.get("task_id") or result.get("status_url"):
            task_item = cls._artifact_item_from_mapping(
                {
                    "kind": "async_task",
                    "name": result.get("task_id") or f"{tool_name} task",
                    "task_id": result.get("task_id"),
                    "status_url": result.get("status_url"),
                    "artifacts_url": result.get("artifacts_url"),
                    "category": result.get("queue") or "task",
                },
                fallback_kind="async_task",
            )
            if task_item:
                items.append(task_item)

        raw_artifacts = result.get("artifacts")
        if isinstance(raw_artifacts, list):
            for raw in raw_artifacts:
                if isinstance(raw, dict):
                    item = cls._artifact_item_from_mapping(raw)
                    if item:
                        items.append(item)

        manifest = result.get("artifact_manifest")
        groups = manifest.get("groups") if isinstance(manifest, dict) else None
        if isinstance(groups, dict) and not raw_artifacts:
            for group, group_items in groups.items():
                if not isinstance(group_items, list):
                    continue
                for raw in group_items:
                    if isinstance(raw, dict):
                        item = cls._artifact_item_from_mapping({**raw, "group": group})
                        if item:
                            items.append(item)

        for key in ("object_name", "download_url", "structure_file", "pdb_object_name"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                item = cls._artifact_item_from_mapping(
                    {
                        "kind": "structure" if "pdb" in key or "structure" in key else "file",
                        "name": value,
                        "object_name": value if "object_name" in key or key == "structure_file" else None,
                        "download_url": value if key == "download_url" else None,
                        "category": "structure" if "pdb" in key or "structure" in key else "file",
                    }
                )
                if item:
                    items.append(item)

        for key in ("best_sequence", "sequence"):
            value = result.get(key)
            if isinstance(value, str) and 5 <= len(value.strip()) <= 10000:
                items.append({
                    "kind": "sequence",
                    "name": key,
                    "category": "sequence",
                    "preview": value.strip()[:120],
                })
                break

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            key = "|".join(str(item.get(part) or "") for part in ("kind", "name", "object_name", "download_url", "task_id"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append({k: v for k, v in item.items() if v not in (None, "", [])})
            if len(deduped) >= 12:
                break
        return deduped

    def _append_artifact_handoff(self, *, step_index: int, step: PlanStep) -> None:
        if self._snapshot is None:
            return
        items = self._extract_artifact_handoff_items(step.tool_name, step.result)
        if not items and step.status not in {"submitted", "completed"}:
            return
        current = self._snapshot.artifacts if isinstance(self._snapshot.artifacts, dict) else {}
        handoffs = list(current.get("handoffs") or [])
        handoffs = [h for h in handoffs if h.get("step") != step_index + 1]
        handoffs.append({
            "step": step_index + 1,
            "tool": step.tool_name,
            "status": step.status,
            "handoff_status": "ready" if items else "none",
            "items": items,
        })
        handoffs.sort(key=lambda h: int(h.get("step") or 0))
        self._snapshot.artifacts = {
            **current,
            "handoffs": handoffs,
            "total_count": sum(len(h.get("items") or []) for h in handoffs),
        }

    @property
    def tools_schema(self) -> list[dict]:
        """Lazy-load tools schema — ToolRegistry is populated after import."""
        return ToolRegistry.get_tools_schema()

    @property
    def skills_metadata(self) -> list[dict]:
        """Lazy-load skills — SkillRegistry is populated after import."""
        return get_skills_metadata()

    def get_snapshot_data(self) -> dict | None:
        """Return current snapshot data for report generation (used by auto-publish)."""
        if self._snapshot is None:
            return None
        s = self._snapshot
        return {
            "stage": s.stage,
            "research_notes": s.research_notes,
            "plan": s.plan,
            "step_results": s.step_results,
            "final_report": s.final_report,
        }

    def get_checkpoint_execution_summary(self) -> dict[str, Any]:
        """Return compact execution evidence suitable for strategy memory."""
        if self._snapshot is None:
            return {}
        final_report = str(self._snapshot.final_report or "")
        step_results: list[dict[str, Any]] = []
        for item in self._snapshot.step_results[:20]:
            if not isinstance(item, dict):
                continue
            step_results.append({
                "step": item.get("step"),
                "tool": item.get("tool"),
                "status": item.get("status"),
                "duration": item.get("duration"),
                "result_preview": self._sanitize_uploaded_metadata_text(
                    item.get("result_preview") or item.get("error") or "",
                    limit=500,
                ),
                "raw_result": self._sanitize_uploaded_metadata_text(
                    item.get("raw_result") or "",
                    limit=2000,
                ),
                "evidence_source": item.get("evidence_source"),
            })
        claim_tool_results = [
            {
                "tool_name": item.get("tool"),
                "status": item.get("status"),
                "result": item.get("result_preview") or "",
            }
            for item in step_results
            if item.get("tool") and item.get("result_preview")
        ]
        claim_audit_summary = {}
        if claim_tool_results:
            claim_audit = self._build_claim_audit(claim_tool_results)
            claim_audit_summary = self._compact_claim_audit_summary(claim_audit)
        return {
            "research_notes_preview": self._sanitize_uploaded_metadata_text(
                self._snapshot.research_notes,
                limit=500,
            ),
            "step_results": step_results,
            "final_report_preview": self._sanitize_uploaded_metadata_text(
                final_report,
                limit=1000,
            ),
            "report_headings": [
                line.strip()
                for line in final_report.splitlines()
                if line.startswith("## ")
            ][:16],
            "claim_audit": claim_audit_summary,
        }

    def _build_context(self, history: list[dict]) -> str:
        """Build protein context from conversation history."""
        context_parts = []
        for msg in history:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            object_name = self._extract_attached_object_name(content)
            if object_name:
                context_parts.append(f"[Uploaded structure object_name: {object_name}]")
            if ">" in content:
                # Extract potential FASTA sequences
                if content.count(">") >= 1:
                    context_parts.append("[Protein sequence detected in conversation]")
            if any(kw in content.lower() for kw in ["pd-l1", "egfr", "her2", "kras", "p53"]):
                context_parts.append("[Known protein target discussed]")
        return "\n".join(context_parts) if context_parts else ""

    @classmethod
    def _message_starts_new_task(cls, message: str) -> bool:
        """Return true when the current user message should not inherit old protein context."""
        if not isinstance(message, str) or not message.strip():
            return False
        lower = message.lower()
        explicit_new = any(token in lower for token in policy_tokens("new_task_tokens"))
        concrete_current_input = bool(
            cls._extract_sequence(message)
            or cls._extract_attached_object_name(message)
            or cls._extract_uniprot_reference(message)
            or cls._extract_pdb_id_reference(message)
        )
        return explicit_new or concrete_current_input

    @staticmethod
    def _message_requests_continuation(message: str) -> bool:
        if not isinstance(message, str):
            return False
        lower = message.lower()
        return any(token in lower for token in policy_tokens("continuation_tokens"))

    @classmethod
    def _is_same_problem_synthesis_followup(cls, message: str, context: str) -> bool:
        """Detect explanation/formatting follow-ups that should not restart tools."""
        if not context or not cls._message_requests_continuation(message):
            return False
        if cls._message_starts_new_task(message):
            return False
        lower = message.lower()
        if any(term in lower for term in policy_tokens("execution_tokens")):
            return False
        return any(term in lower for term in policy_tokens("followup_synthesis_tokens"))

    @classmethod
    def _is_report_quality_review_followup(cls, message: str, context: str, history: list[dict] | None = None) -> bool:
        """Detect user feedback that asks to audit the previous report, not run tools."""
        if not cls._message_contains_report_quality_feedback(message):
            return False
        has_previous_report = bool(context)
        for item in history or []:
            content = item.get("content", "")
            if not isinstance(content, str):
                continue
            content_lower = content.lower()
            if any(token in content_lower for token in (
                "酶蛋白工程分析报告",
                "分析策略确认",
                "工具来源说明",
                "mutation_priority_score",
                "structure_search_foldseek",
            )):
                has_previous_report = True
                break
        return has_previous_report

    @classmethod
    def _message_contains_report_quality_feedback(cls, message: str) -> bool:
        """Return true for report-quality complaints or audit follow-up requests."""
        if not isinstance(message, str) or not message.strip():
            return False
        if cls._message_starts_new_task(message):
            return False
        lower = message.lower()
        if any(term in lower for term in policy_tokens("execution_tokens")):
            return False
        complaint_tokens = (
            "不准", "不准确", "错误", "错了", "乱了", "格式乱", "表格乱",
            "质量差", "越改越差", "很差", "差的要死", "让人生气", "生气",
            "不知道你在分析什么", "盲目", "别盲目", "上下文能力", "报告质量",
            "策略一般", "重新规划", "继续深度检查", "深度检查", "你看看你分析",
            "看看你分析", "review the report", "report quality", "wrong analysis",
        )
        return any(token in lower for token in complaint_tokens)

    @classmethod
    def _message_starts_new_protein_object_for_followup(cls, message: str) -> bool:
        """Return true when a P0 follow-up actually introduces a different protein object."""
        if not isinstance(message, str) or not message.strip():
            return False
        lower = message.lower()
        concrete_current_input = bool(
            cls._extract_sequence(message)
            or cls._extract_attached_object_name(message)
            or cls._extract_uniprot_reference(message)
            or cls._extract_pdb_id_reference(message)
        )
        if concrete_current_input:
            return True
        new_tokens = [
            token for token in policy_tokens("new_task_tokens")
            if token not in {"重新分析", "重新规划"}
        ]
        return any(token in lower for token in new_tokens)

    @classmethod
    def _message_requests_venus_gap_followup(cls, message: str) -> bool:
        """Detect Venus/MatVenus comparison follow-ups that should audit the prior result."""
        if not isinstance(message, str) or not message.strip():
            return False
        if cls._message_starts_new_protein_object_for_followup(message):
            return False
        lower = message.lower()
        if any(term in lower for term in policy_tokens("execution_tokens")):
            return False
        venus_tokens = ("venus", "matvenus", "mat venus")
        gap_tokens = (
            "差距", "哪里差", "差在哪", "对比", "对标", "比", "反超",
            "compare", "comparison", "gap", "benchmark",
        )
        return any(token in lower for token in venus_tokens) and any(token in lower for token in gap_tokens)

    @classmethod
    def _message_requests_candidate_site_explanation_followup(cls, message: str) -> bool:
        """Detect candidate/site explanation follow-ups that should reuse prior results."""
        if not isinstance(message, str) or not message.strip():
            return False
        if cls._message_starts_new_protein_object_for_followup(message):
            return False
        lower = message.lower()
        if any(term in lower for term in policy_tokens("execution_tokens")):
            return False
        site_tokens = (
            "这个位点", "该位点", "这个残基", "该残基", "候选位点", "推荐位点",
            "候选", "推荐", "position", "site", "residue", "candidate",
        )
        explain_tokens = (
            "为什么", "原因", "依据", "逻辑", "解释", "怎么看", "怎么样",
            "why", "explain", "rationale",
        )
        return any(token in lower for token in site_tokens) and any(token in lower for token in explain_tokens)

    @classmethod
    def _message_requests_prediction_experiment_mismatch_followup(cls, message: str) -> bool:
        """Detect prediction-vs-experiment discrepancy follow-ups."""
        if not isinstance(message, str) or not message.strip():
            return False
        if cls._message_starts_new_protein_object_for_followup(message):
            return False
        lower = message.lower()
        if any(term in lower for term in policy_tokens("execution_tokens")):
            return False
        prediction_tokens = ("预测", "计算", "模型", "prediction", "predicted", "model")
        experiment_tokens = ("实验", "实测", "反馈", "wet-lab", "wetlab", "assay", "experiment")
        mismatch_tokens = (
            "不一致", "不符", "冲突", "相反", "偏差", "差异", "没对上", "对不上",
            "mismatch", "conflict", "discrepancy", "inconsistent",
        )
        return (
            any(token in lower for token in prediction_tokens)
            and any(token in lower for token in experiment_tokens)
            and any(token in lower for token in mismatch_tokens)
        ) or ("实验结果不一致" in lower)

    @classmethod
    def _has_prior_engineering_result_context(cls, context: str, history: list[dict] | None = None) -> bool:
        if context:
            return True
        for item in history or []:
            content = item.get("content", "")
            if not isinstance(content, str):
                continue
            lower = content.lower()
            if any(token in lower for token in (
                "酶蛋白工程分析报告",
                "突变位点",
                "候选表",
                "mutation_priority_score",
                "specified_mutation_reviews",
                "objective module gate",
                "site_structure_function_features",
            )):
                return True
        return False

    @classmethod
    def _is_p0_followup_review(cls, message: str, context: str, history: list[dict] | None = None) -> bool:
        if not cls._has_prior_engineering_result_context(context, history):
            return False
        return (
            cls._message_requests_venus_gap_followup(message)
            or cls._message_requests_candidate_site_explanation_followup(message)
            or cls._message_requests_prediction_experiment_mismatch_followup(message)
            or cls._message_requests_mutation_review(message)
        )

    @classmethod
    def _build_p0_followup_review_reply(cls, message: str, history: list[dict], context: str) -> str:
        """Deterministic P0 follow-up answer that does not restart candidate generation."""
        requested_mutation_review = cls._build_requested_mutation_review_report(message, [])
        if requested_mutation_review:
            return requested_mutation_review

        summary = cls._summarize_history_for_quality_review(history)
        tool_items = [
            f"{tool}={status}"
            for tool, status in sorted(summary.get("tools", {}).items())
        ]
        object_text = "、".join(summary.get("objects") or []) or "上一轮对象；本轮不重新解析新对象"
        tool_text = "；".join(tool_items[:10]) or "上一轮已展示结果；本轮不重新调用工具"
        context_note = "已检测到同一问题上下文" if context else "已从历史报告识别上一轮结果"

        if cls._message_requests_venus_gap_followup(message):
            lines = [
                "# Venus 对标差距复核",
                "",
                "## 复核结论",
                "- 已识别为对上一轮报告和 Venus/MatVenus 的差距复核，本轮不重新规划工具、不生成新候选表。",
                "- 对标重点是位点级解释、指定突变复核、候选表可读性、实验反馈归因和证据边界。",
                "",
                "## 上一轮状态",
                f"- **上下文状态**：{context_note}。",
                f"- **对象线索**：{object_text}。",
                f"- **工具状态线索**：{tool_text}。",
                "- **同项目策略记忆**：只作为历史结果锚点，不作为本轮新工具证据或用户新指令。",
                "",
                "## 当前差距",
                "- **位点解释**：候选位点必须能追溯到 residue feature table；未知的 pocket/channel/interface/conservation 只能写 unknown。",
                "- **指定突变复核**：用户点名突变时应逐条解释活性、稳定性、风险和实验动作，不应重新给泛化候选表。",
                "- **实验反馈归因**：预测和实验不一致时先拆 assay、WT baseline、表达/纯化、编号和结构证据，不把计算分数写成实验事实。",
                "- **多目标候选表**：活性、稳定性、风险、证据等级和实验动作应分列，不合成一个不可解释总分。",
                "",
                "## 下一步动作",
                "- P0-4 续问路径固定为复核上一轮对象和结果；只有用户明确给新序列/新 PDB/新 UniProt 时才进入新任务。",
                "- P1 再把编号映射、催化机制、reaction profile 和 WT baseline 接成主干证据层。",
            ]
            return "\n".join(lines) + "\n"

        if cls._message_requests_prediction_experiment_mismatch_followup(message):
            lines = [
                "# 预测-实验偏差复核",
                "",
                "## 复核结论",
                "- 已识别为预测与实验反馈不一致的续问，本轮不重新跑默认流程、不直接重排候选表。",
                "- 先把偏差归因拆成目标 assay、WT 同批 baseline、编号映射、表达/纯化、稳定性-活性权衡和结构证据缺口。",
                "",
                "## 上一轮状态",
                f"- **上下文状态**：{context_note}。",
                f"- **对象线索**：{object_text}。",
                f"- **工具状态线索**：{tool_text}。",
                "- **同项目策略记忆**：只作为历史结果锚点，不作为本轮新工具证据或用户新指令。",
                "",
                "## 处理规则",
                "- 有点名突变时，进入指定突变复核；没有点名突变时，先要求补 mutation、实验指标、底物、pH、温度、replicate 和 WT 对照。",
                "- 活性提高但稳定性下降按 activity-stability trade-off 处理，先保留活性收益假设，再找补偿位点。",
                "- 只有同批 WT baseline、编号和 assay 条件闭合后，才能把偏差归因升级为候选设计约束。",
            ]
            return "\n".join(lines) + "\n"

        lines = [
            "# 候选位点解释复核",
            "",
            "## 复核结论",
            "- 已识别为对上一轮候选位点推荐理由的续问，本轮不重新执行工具、不生成新的候选表。",
            "- 回答只能复用上一轮候选表、位点结构-功能特征和证据门控；未知字段保持 unknown。",
            "",
            "## 上一轮状态",
            f"- **上下文状态**：{context_note}。",
            f"- **对象线索**：{object_text}。",
            f"- **工具状态线索**：{tool_text}。",
            "- **同项目策略记忆**：只作为历史结果锚点，不作为本轮新工具证据或用户新指令。",
            "",
            "## 解释口径",
            "- **活性**：说明是否来自催化簇距离、口袋/通道人工复核线索或目标模块假设；没有反应/底物证据时不声明比活提升。",
            "- **稳定性**：说明是否来自 CA B-factor、接触数、relSASA、ΔΔG 或保护位点风险；没有真实结果时只写复核需求。",
            "- **风险**：保护位点、催化位点、编号不明、mapping inferred、pocket/channel unknown 都必须写成风险或降级原因。",
            "- **实验动作**：只给单点验证、WT 同批 baseline、表达/纯化 QC 和后续补证据路线，不直接承诺组合突变。",
        ]
        return "\n".join(lines) + "\n"

    @classmethod
    def _summarize_history_for_quality_review(cls, history: list[dict]) -> dict[str, Any]:
        """Extract lightweight, user-visible state from recent conversation history."""
        recent_text = "\n".join(
            str(item.get("content") or "")
            for item in history[-8:]
            if isinstance(item.get("content"), str)
        )
        tools: dict[str, str] = {}
        for tool, status in re.findall(
            r"\b([a-z][a-z0-9_]{2,})\s*(?:\(|[:：])\s*(completed|complete|submitted|failed|blocked|running)\b",
            recent_text,
            flags=re.IGNORECASE,
        ):
            tools[tool] = status.lower()
        for tool in re.findall(
            r"\b(structure_search_foldseek|residue_mapping_sifts|predict_properties|annotation_bundle|"
            r"enzyme_identity_profile|enzyme_objective_module_plan|protein_benchmark|enzyme_function|"
            r"mutation_priority_score|kcat_predict|mutation_scan|protssn_score|blast_search)\b",
            recent_text,
        ):
            tools.setdefault(tool, "mentioned")

        object_names = []
        for match in re.finditer(r"\b([A-Za-z0-9_.-]+\.pdb)\b", recent_text, flags=re.IGNORECASE):
            name = match.group(1)
            if name not in object_names:
                object_names.append(name)

        blockers = []
        blocker_patterns = (
            "identity_status must be identified",
            "guardrail.status must be ready",
            "protected catalytic/key positions are not available",
            "Provide baseline Tm",
            "WT specific activity baseline",
            "identity_status",
            "编号",
            "SIFTS",
            "kcat",
            "submitted",
        )
        for pattern in blocker_patterns:
            if pattern.lower() in recent_text.lower() and pattern not in blockers:
                blockers.append(pattern)

        return {
            "objects": object_names[:4],
            "tools": tools,
            "blockers": blockers[:8],
            "has_report": "酶蛋白工程分析报告" in recent_text,
            "has_strategy": "分析策略确认" in recent_text,
        }

    @classmethod
    def _summarize_strategy_memory_for_quality_review(cls, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract structured quality-review state from saved strategy checkpoints."""
        if not records:
            return {}
        record = next((item for item in records if isinstance(item, dict)), {})
        if not record:
            return {}
        plan = record.get("plan_payload") if isinstance(record.get("plan_payload"), list) else []
        tools: dict[str, str] = {}
        for step in plan:
            if not isinstance(step, dict) or not step.get("tool_name"):
                continue
            status = str(step.get("status") or record.get("status") or "planned")
            tools[str(step["tool_name"])] = status
        objects = cls._extract_uploaded_object_names_from_plan_payload(plan)
        task_text = str(record.get("task_text") or "")
        task_object = cls._extract_attached_object_name(task_text)
        if task_object and task_object not in objects:
            objects.insert(0, task_object)

        evidence = record.get("evidence_state") if isinstance(record.get("evidence_state"), dict) else {}
        blockers: list[str] = []
        step_previews: list[str] = []
        evidence_steps = evidence.get("step_results")
        if isinstance(evidence_steps, list):
            for item in evidence_steps[:8]:
                if not isinstance(item, dict):
                    continue
                tool = str(item.get("tool") or "").strip()
                status = str(item.get("status") or "").strip()
                if tool:
                    tools[tool] = status or tools.get(tool, "completed")
                    preview = cls._memory_text(item.get("result_preview") or "", limit=120)
                    if preview:
                        step_previews.append(f"{tool}({status or 'unknown'}): {preview}")
        for key in ("blocked_reason", "gate_reason", "missing_evidence", "research_notes_preview", "summary"):
            value = evidence.get(key)
            if isinstance(value, list):
                blockers.extend(str(item) for item in value[:4])
            elif value:
                blockers.append(cls._memory_text(value, limit=180))
        final_preview = cls._memory_text(evidence.get("final_report_preview") or "", limit=220)
        if final_preview:
            blockers.append(f"final_report_preview: {final_preview}")
        claim_audit = (
            evidence.get("claim_audit")
            if isinstance(evidence.get("claim_audit"), dict)
            else evidence.get("claim_audit_summary")
            if isinstance(evidence.get("claim_audit_summary"), dict)
            else {}
        )
        artifacts = record.get("artifacts") if isinstance(record.get("artifacts"), dict) else {}
        handoffs = artifacts.get("handoffs") if isinstance(artifacts.get("handoffs"), list) else []
        return {
            "revision": record.get("revision"),
            "status": record.get("status"),
            "next_action": record.get("next_action") or "none",
            "strategy_signature": record.get("strategy_signature"),
            "task_fingerprint": record.get("task_fingerprint"),
            "objects": objects[:4],
            "tools": tools,
            "blockers": blockers[:8],
            "step_previews": step_previews[:8],
            "report_headings": evidence.get("report_headings") if isinstance(evidence.get("report_headings"), list) else [],
            "claim_audit": claim_audit,
            "artifact_handoff_count": len(handoffs),
        }

    @classmethod
    def _build_report_quality_review_reply(
        cls,
        message: str,
        history: list[dict],
        context: str,
        strategy_records: list[dict[str, Any]] | None = None,
    ) -> str:
        """Deterministic quality-audit response for report complaint follow-ups."""
        summary = cls._summarize_history_for_quality_review(history)
        memory_summary = cls._summarize_strategy_memory_for_quality_review(strategy_records or [])
        if memory_summary:
            if memory_summary.get("objects"):
                summary["objects"] = memory_summary["objects"]
            if memory_summary.get("tools"):
                summary["tools"] = memory_summary["tools"]
            if memory_summary.get("blockers"):
                summary["blockers"] = memory_summary["blockers"]
        tool_items = [
            f"{tool}={status}"
            for tool, status in sorted(summary.get("tools", {}).items())
        ]
        object_text = "、".join(summary.get("objects") or []) or "未能从历史稳定恢复对象名"
        tool_text = "；".join(tool_items[:12]) or "未能从历史稳定恢复工具状态"
        blocker_text = "；".join(summary.get("blockers") or []) or "历史中未提取到结构化阻断项"
        step_preview_text = "；".join(memory_summary.get("step_previews") or []) if memory_summary else ""
        headings_text = " → ".join(map(str, memory_summary.get("report_headings") or [])) if memory_summary else ""
        claim_audit = memory_summary.get("claim_audit") if memory_summary and isinstance(memory_summary.get("claim_audit"), dict) else {}
        claim_audit_lines: list[str] = []
        if claim_audit:
            summary_gate = claim_audit.get("summary_gate") if isinstance(claim_audit.get("summary_gate"), dict) else {}
            counts = summary_gate.get("counts") if isinstance(summary_gate.get("counts"), dict) else {}
            if summary_gate:
                claim_audit_lines.append(
                    "- **摘要/结论门控**："
                    f"{summary_gate.get('status', 'N/A')}；"
                    f"allowed={counts.get('allowed', 0)}；"
                    f"downgraded={counts.get('downgraded', 0)}；"
                    f"blocked={counts.get('blocked', 0)}。"
                )
            for label, key in (
                ("允许进入摘要", "allowed"),
                ("降级为正文假设", "downgraded"),
                ("禁止写成事实", "blocked"),
            ):
                items = claim_audit.get(key)
                if isinstance(items, list) and items:
                    claim_audit_lines.append(f"- **{label}**：{'; '.join(map(str, items[:8]))}。")
        context_note = "已检测到同一问题上下文" if context else "未检测到可用上下文"
        memory_line = ""
        if memory_summary:
            memory_line = (
                f"- **策略记忆**：revision={memory_summary.get('revision', 'N/A')}；"
                f"status={memory_summary.get('status', 'N/A')}；"
                f"next_action={memory_summary.get('next_action', 'none')}；"
                f"artifact_handoffs={memory_summary.get('artifact_handoff_count', 0)}。"
            )

        lines = [
            "# 报告质量复核",
            "",
            "## 复核结论",
            "- 已识别为对上一轮分析质量的复核请求，本轮不重新执行工具、不重新生成候选突变表。",
            "- 处理重点是定位证据链、上下文继承、报告顺序和语言格式问题；只有复核完成后才应重新跑策略或候选工具。",
            "",
            "## 上一轮状态摘要",
            f"- **上下文状态**：{context_note}。",
            f"- **对象线索**：{object_text}。",
            f"- **工具状态线索**：{tool_text}。",
            f"- **阻断/风险线索**：{blocker_text}。",
        ]
        if memory_line:
            lines.append(memory_line)
        if step_preview_text:
            lines.append(f"- **工具结果摘要**：{step_preview_text}。")
        if headings_text:
            lines.append(f"- **报告章节线索**：{headings_text}。")
        if claim_audit_lines:
            lines.extend([
                "",
                "## 科学声明审计",
                *claim_audit_lines,
                "- **使用规则**：只有 SUPPORTED 声明可进入摘要/结论；DESIGN_HYPOTHESIS、MISSING 或 RUNTIME_UNVERIFIED 只能写成边界、缺口或验证需求。",
            ])
        lines.extend([
            "",
            "## 主要问题归因",
            "- **证据升级过度**：弱 Foldseek 命中、inferred 编号或 submitted 后台任务不能写成酶身份、UniProt 映射或完成结果。",
            "- **目标拆解不足**：比活力和热稳定性必须并列门控，不能只按一个主目标生成通用位点表。",
            "- **报告结构失控**：突变清单和位点逻辑应放在 Objective Module Gate 之后；附录、审计和工具原始输出不能挤到核心结论区。",
            "- **续问模式错误**：用户指出不准或格式乱时，应进入质量复核，而不是继续套默认分析流程。",
            "",
            "## 后续修正动作",
            "- 固定输出“对象是谁、证据来自哪里、能否给突变、为什么、下一步做什么”。",
            "- 身份/编号/催化保护位点未通过时，只输出未放行原因和补证据路线，不输出 K288E/E275Q 这类通用突变建议。",
            "- kcat、EC 预测、BLAST submitted 等结果只放入边界或附录，不作为比活力提升结论。",
            "- 将本类续问加入回归测试，确保“不准/格式乱/继续深度检查”不会再触发新一轮工具规划。",
        ])
        return "\n".join(lines) + "\n"

    @classmethod
    def _build_context_for_message(cls, message: str, history: list[dict]) -> str:
        """Use prior context only for explicit follow-up turns or missing current input."""
        context_parts = []
        prior_user_summaries: list[str] = []
        wants_continuation = cls._message_requests_continuation(message)
        policy = get_agent_strategy_policy()["policy"]
        raw_requires_continuation = bool(policy.get("raw_sequence_history_requires_continuation", True))

        def _is_context_noise(content: str) -> bool:
            lower = content.lower()
            noisy_tokens = [
                "确认执行上述分析策略",
                "[用户确认]",
                "策略检查点校验失败",
                "confirmed_plan must be a list",
                "strategy_signature does not match confirmed_plan",
                "task_fingerprint does not match current task context",
                "发布到wiki",
                "report generated by protein ai platform",
                "protein engineering analysis report",
                "酶蛋白工程分析报告",
                "执行结果与科学审查报告",
            ]
            return any(token.lower() in lower for token in noisy_tokens)

        for msg in history:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            object_name = cls._extract_attached_object_name(content)
            if object_name:
                context_parts.append(f"[Uploaded structure object_name: {object_name}]")
            if wants_continuation and msg.get("role") == "user" and not _is_context_noise(content):
                summary = cls._display_task_summary(content)
                if summary and summary not in {"[空任务]", "[只包含上传附件元数据]"}:
                    prior_user_summaries.append(summary[:240])
            can_use_raw_sequence = (not raw_requires_continuation) or wants_continuation
            if msg.get("role") == "user" and cls._extract_sequence(content) and (">" in content or can_use_raw_sequence):
                context_parts.append("[Prior FASTA input present]")
            if any(kw in content.lower() for kw in ["pd-l1", "egfr", "her2", "kras", "p53"]):
                context_parts.append("[Known protein target discussed]")
        if prior_user_summaries:
            context_parts.append(f"[Prior user request summary: {prior_user_summaries[-1]}]")
        base_context = "\n".join(context_parts)
        if not base_context:
            return ""
        if cls._message_starts_new_task(message) and not cls._message_requests_continuation(message):
            return "[Context boundary: current message starts a new protein task; prior protein context ignored]"
        if wants_continuation:
            return base_context
        if cls._extract_sequence(message) or cls._extract_attached_object_name(message):
            return ""
        return base_context

    @staticmethod
    def _normalize_confirmed_task(message: str, control: str) -> str:
        """Keep confirmation metadata from changing the deterministic execution plan."""
        if control != "execute_confirmed" or not isinstance(message, str):
            return message
        return re.split(r"\n\s*\[用户确认\]", message, maxsplit=1)[0].strip() or message

    @staticmethod
    def _extract_sequence(text: str) -> str | None:
        """Extract a valid amino-acid sequence from FASTA, labelled, or raw sequence text.

        The raw fallback is intentionally case-sensitive. Otherwise ordinary words such
        as "specificity" are valid one-letter amino-acid strings and get misread as
        short protein fragments in mixed Chinese/English prompts.
        """
        if not isinstance(text, str) or not text.strip():
            return None

        def _clean(candidate: str) -> str:
            return re.sub(r"[^ACDEFGHIKLMNPQRSTVWY]", "", candidate.upper())

        fasta_blocks = re.findall(r">[^\n\r]*(?:\r?\n)([A-Za-z\s\r\n-]{10,})", text)
        fasta_matches = [_clean(block) for block in fasta_blocks]
        fasta_matches = [seq for seq in fasta_matches if len(seq) >= 10]
        if fasta_matches:
            return max(fasta_matches, key=len)

        labelled_matches = re.findall(
            r"(?:序列|氨基酸序列|protein sequence|sequence)\s*(?:为|是|=|[:：])\s*([A-Za-z\s\r\n-]{10,})",
            text,
            re.IGNORECASE,
        )
        labelled = [_clean(match) for match in labelled_matches]
        labelled = [seq for seq in labelled if len(seq) >= 10]
        if labelled:
            return max(labelled, key=len)

        sanitized = re.sub(r"序列前缀\s*[`=:：-]*\s*[ACDEFGHIKLMNPQRSTVWY]{10,}\s*`?", " ", text)
        sanitized = re.sub(r"sequence preview\s*[`=:：-]*\s*[ACDEFGHIKLMNPQRSTVWY]{10,}\s*`?", " ", sanitized, flags=re.IGNORECASE)
        matches = re.findall(r'(?<![A-Za-z])[ACDEFGHIKLMNPQRSTVWY]{10,}(?![A-Za-z])', sanitized)
        if matches:
            return max(matches, key=len).upper()
        return None

    @staticmethod
    def _clean_literature_query(text: str) -> str:
        """Keep live literature queries focused on the user's natural-language ask."""
        if not isinstance(text, str):
            return ""
        cleaned = re.split(r"\n\s*\[Attached files:", text, maxsplit=1)[0]
        cleaned = re.sub(r"\[[^\]]+\]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        for marker in ("请联网", "联网搜索", "网络搜索", "在线搜索", "实时搜索", "查一下", "检索一下"):
            cleaned = cleaned.replace(marker, " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ：:，,。")
        return cleaned[:240] or text.strip()[:240]

    @staticmethod
    def _display_task_summary(text: str, limit: int = 500) -> str:
        """Build a user-facing task summary without leaking object paths or hash-like IDs."""
        if not isinstance(text, str):
            return ""
        current_text = re.split(r"\n\s*\[", text, maxsplit=1)[0].strip()
        prior_matches = re.findall(r"\[Prior user request summary:\s*([^\]]+)\]", text)
        current_has_bound_input = bool(
            re.search(r"(?:\bPDB\b|\bFASTA\b|UniProt|上传|附件|结构文件|序列)", current_text, re.IGNORECASE)
        )
        if (
            prior_matches
            and current_text
            and AgentOrchestrator._message_requests_continuation(current_text)
            and not current_has_bound_input
        ):
            prior = AgentOrchestrator._sanitize_uploaded_metadata_text(prior_matches[-1]).strip()
            current = AgentOrchestrator._sanitize_uploaded_metadata_text(current_text).strip()
            if prior:
                summary = f"{prior}（续问：{current}）" if current else prior
                return re.sub(r"\s+", " ", summary).strip()[:limit]
        cleaned = re.split(r"\n\s*\[Attached files:", text, maxsplit=1)[0].strip()
        if not cleaned:
            cleaned = AgentOrchestrator._strip_attachment_metadata(text).strip()
        cleaned = AgentOrchestrator._sanitize_uploaded_metadata_text(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:limit] or "已上传结构文件，目标见本轮消息。"

    @staticmethod
    def _sanitize_uploaded_metadata_text(text: Any, limit: int | None = None) -> str:
        """Mask object-store paths and file download URLs in user-visible text."""
        if text is None:
            return ""
        cleaned = str(text)
        cleaned = re.sub(
            r"object_name\s*[:=]\s*[^,\s\]\}]+",
            "object_name: [uploaded-object]",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"pdb_object_name\s*[:=]\s*[^,\s\]\}]+",
            "pdb_object_name: [uploaded-object]",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"download_url\s*[:=]\s*[^,\s\]\}]+",
            "download: [download-url]",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"uploads/[^\s,\"'\]\}]+", "[uploaded-object]", cleaned)
        cleaned = re.sub(r"/api/files/[^\s,\"'\]\}]+", "[download-url]", cleaned)
        if limit is not None:
            return cleaned[:limit]
        return cleaned

    @staticmethod
    def _extract_attached_file_name(text: str) -> str | None:
        """Extract display-safe attached file name from the chat attachment block."""
        if not isinstance(text, str) or "name" not in text:
            return None
        candidates = re.findall(r"['\"]?name['\"]?\s*[:=]\s*['\"]?([^'\"\s,\]\}]+)", text)
        for candidate in candidates:
            candidate = candidate.strip()
            if candidate and not any(token in candidate.lower() for token in ("object_name", "download_url", "uploads/")):
                return candidate[:120]
        return None

    @staticmethod
    def _task_requests_no_tools(text: str) -> bool:
        if not isinstance(text, str):
            return False
        lower = text.lower()
        return any(pattern in lower for pattern in [
            "不要调用工具",
            "不调用工具",
            "禁止调用工具",
            "不要跑工具",
            "不要使用工具",
            "不使用工具",
            "只抽取",
            "只提取",
            "只解析",
            "只要抽取",
            "只做抽取",
            "不分析",
            "不要分析",
            "do not call tools",
            "don't call tools",
            "without tools",
            "no tools",
            "only extract",
            "extract only",
            "do not analyze",
            "don't analyze",
        ])

    @classmethod
    def _build_extraction_only_reply(cls, message: str) -> str:
        sequence = cls._extract_sequence(message)
        pdb_object_name = cls._extract_attached_object_name(message)
        protein_name = cls._extract_named_protein_reference(message)
        uniprot_id = cls._extract_uniprot_reference(message)
        pdb_id = cls._extract_pdb_id_reference(message)

        lines = ["## 抽取结果\n"]
        if sequence:
            lines.append(f"- 氨基酸序列：`{sequence}`")
            lines.append(f"- 序列长度：{len(sequence)} aa")
        if pdb_object_name:
            lines.append(f"- 已上传结构对象：`{pdb_object_name}`")
        if protein_name:
            lines.append(f"- 蛋白/酶名称：{protein_name}")
        if uniprot_id:
            lines.append(f"- UniProt：`{uniprot_id}`")
        if pdb_id:
            lines.append(f"- PDB：`{pdb_id}`")
        if len(lines) == 1:
            lines.append("- 未抽取到明确的序列、结构对象、UniProt/PDB 编号或蛋白名称。")
        lines.append("\n未调用任何分析工具。")
        return "\n".join(lines)

    @staticmethod
    def _is_negative_tool_context(text: str) -> bool:
        if not isinstance(text, str):
            return False
        lower = text.lower()
        return any(kw in lower for kw in [
            "禁止", "不要", "不允许", "别", "无需", "不能", "不得",
            "do not", "don't", "without", "no ", "not call", "forbid", "forbidden",
        ])

    @classmethod
    def _extract_forbidden_tools(cls, text: str) -> set[str]:
        if not cls._is_negative_tool_context(text):
            return set()
        lower = text.lower()
        forbidden: set[str] = set()
        tool_groups: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
            (("esmfold", "folding", "结构预测", "折叠预测", "折叠"), ("esmfold_folding", "alphafold_folding", "alphafold2_folding", "rosettafold_folding")),
            (("blast", "同源", "比对"), ("blast_search",)),
            (("家族预测", "家族分析", "保守分析", "保守位点", "motif", "family", "conservation"), ("blast_search", "protein_benchmark", "enzyme_function")),
            (("突变打分", "突变评分", "突变排序", "mutation scoring", "mutation score", "priority score"), ("mutation_priority_score", "mutation_scan", "protssn_score")),
            (("mutation_priority_score",), ("mutation_priority_score",)),
            (("mutation_scan", "突变扫描", "饱和突变"), ("mutation_scan",)),
            (("protssn",), ("protssn_score",)),
            (("predict_properties", "理化性质", "性质预测"), ("predict_properties",)),
            (("sequence_search", "序列搜索", "查库", "检索序列"), ("sequence_search",)),
            (("gromacs", "分子动力学", "rmsd", "rmsf"), ("gromacs_md",)),
            (("foldseek", "结构检索"), ("structure_search_foldseek",)),
            (("编号映射", "residue mapping", "sifts"), ("residue_mapping_sifts", "residue_numbering_gate")),
        ]
        for triggers, tools in tool_groups:
            if any(trigger in lower for trigger in triggers):
                forbidden.update(tools)
        return forbidden

    @classmethod
    def _apply_tool_constraints(cls, plan: list[PlanStep], task: str, context: str = "") -> list[PlanStep]:
        combined = f"{task}\n{context}".strip()
        if cls._task_requests_no_tools(combined):
            return []
        forbidden = cls._extract_forbidden_tools(combined)
        if not forbidden:
            return plan
        filtered = [step for step in plan if step.tool_name not in forbidden]
        for index, step in enumerate(filtered, start=1):
            step.id = index
        return filtered

    @classmethod
    def _classify_engineering_objectives(cls, text: str) -> set[str]:
        lower = text.lower()
        objectives: set[str] = set()
        if any(kw in lower for kw in ["耐热", "热稳定", "热稳定性", "thermostability", "thermal stability", "temperature stability", "melting temperature", "tm", "heat"]):
            objectives.add("thermostability")
        if any(kw in lower for kw in ["降低最适ph", "降低ph", "酸化", "耐酸", "酸性", "酸稳定", "lower ph", "ph lowering"]):
            objectives.add("ph_lowering")
        if any(kw in lower for kw in ["提高最适ph", "提高ph", "碱化", "耐碱", "碱性", "碱稳定", "raise ph", "ph raising"]):
            objectives.add("ph_raising")
        if any(kw in lower for kw in ["底物特异", "特异性", "选择性", "specificity", "substrate specificity", "selectivity"]):
            objectives.add("specificity")
        activity_context = lower
        for phrase in (
            "热稳定性",
            "热稳定",
            "温度稳定性",
            "温度稳定",
            "残余活性",
            "热处理后活性",
            "thermal stability",
            "thermostability",
            "residual activity",
        ):
            activity_context = activity_context.replace(phrase, " ")
        if any(kw in activity_context for kw in ["比活", "酶活", "活性", "催化效率", "kcat", "km", "activity", "specific activity", "catalytic efficiency"]):
            objectives.add("activity")
        if any(kw in lower for kw in ["可溶", "可溶性", "表达", "表达量", "solubility", "soluble expression", "expression yield"]):
            objectives.add("solubility")
        return objectives

    @staticmethod
    def _primary_engineering_goal(objectives: set[str]) -> str:
        if "activity" in objectives and "thermostability" in objectives:
            return "activity"
        for goal in ("activity", "thermostability", "ph_lowering", "ph_raising", "specificity"):
            if goal in objectives:
                return goal
        return "general"

    @staticmethod
    def _extract_assay_context(text: str) -> dict[str, Any]:
        """Extract only explicit assay context signals; absence remains missing evidence."""
        if not isinstance(text, str):
            return {}
        lower = text.lower()
        context: dict[str, Any] = {}
        if re.search(r"\btm\s*[=:]?\s*\d{2,3}", lower) or "熔解温度" in lower:
            context["tm"] = True
        if any(kw in lower for kw in ["half-life", "half life", "半衰期"]):
            context["half_life"] = True
        if any(kw in lower for kw in ["residual activity", "残余活性", "热处理后活性"]):
            context["residual_activity"] = True
        if any(kw in lower for kw in ["specific activity", "比活", "protein-normalized", "蛋白归一化"]):
            context["specific_activity"] = True
            context["protein_normalized"] = True
        if any(kw in lower for kw in ["kcat", "k_cat"]):
            context["kcat"] = True
        if re.search(r"\bkm\b", lower) or "米氏常数" in lower:
            context["km"] = True
        if any(kw in lower for kw in ["ph curve", "ph-activity curve", "ph 活性曲线", "ph曲线", "完整ph"]):
            context["ph_curve"] = True
        if re.search(r"ph\s*\d(?:\.\d)?\s*/\s*ph\s*\d(?:\.\d)?", lower) or any(
            kw in lower for kw in ["点比值", "point ratio", "单点比值"]
        ):
            context["point_ratio"] = True
        target_match = re.search(r"(?:target_substrate|目标底物)\s*[:：=]\s*([^,，;\n]+)", text, re.IGNORECASE)
        off_target_match = re.search(r"(?:off_target_substrate|非目标底物|对照底物)\s*[:：=]\s*([^,，;\n]+)", text, re.IGNORECASE)
        if target_match:
            context["target_substrate"] = target_match.group(1).strip()
        if off_target_match:
            context["off_target_substrate"] = off_target_match.group(1).strip()
        return context

    @staticmethod
    def _strip_attachment_metadata(text: str) -> str:
        """Remove file metadata blocks before parsing user residue/mutation text."""
        if not isinstance(text, str):
            return ""
        cleaned_lines: list[str] = []
        skip_attachment_block = False
        for raw_line in text.splitlines():
            line = raw_line.strip()
            lower = line.lower()
            if lower.startswith("[attached files") or lower.startswith("attached files"):
                skip_attachment_block = True
                continue
            if skip_attachment_block:
                if "]" in line:
                    skip_attachment_block = False
                continue
            if any(key in lower for key in ("object_name", "download_url", "/api/files/", "uploads/")):
                continue
            cleaned_lines.append(raw_line)
        cleaned = "\n".join(cleaned_lines)
        cleaned = re.sub(r"https?://\S+", " ", cleaned)
        cleaned = re.sub(r"/\S+", " ", cleaned)
        return cleaned

    @staticmethod
    def _extract_requested_positions(text: str) -> list[int]:
        """Extract residue positions that require numbering confirmation."""
        if not isinstance(text, str):
            return []
        text = AgentOrchestrator._strip_attachment_metadata(text)
        positions: set[int] = set()
        for match in re.finditer(r"(?<![A-Za-z0-9_/.-])([ACDEFGHIKLMNPQRSTVWY])([0-9]{1,5})([ACDEFGHIKLMNPQRSTVWY])(?![A-Za-z0-9_/.-])", text, re.IGNORECASE):
            prefix_start = max(0, match.start() - 24)
            prefix = text[prefix_start:match.start()].lower()
            if any(token in prefix for token in ("upload", "object_name", "download_url", "/api/files")):
                continue
            positions.add(int(match.group(2)))
        for match in re.finditer(r"(?:位点|残基|position|residue)\s*([0-9]{1,5})", text, re.IGNORECASE):
            positions.add(int(match.group(1)))
        return sorted(pos for pos in positions if pos > 0)

    @staticmethod
    def _extract_requested_mutations(text: str) -> list[str]:
        """Extract concrete point mutations in WT-position-mutant format."""
        if not isinstance(text, str):
            return []
        text = AgentOrchestrator._strip_attachment_metadata(text)
        mutations: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(
            r"(?<![A-Za-z0-9_/.-])([ACDEFGHIKLMNPQRSTVWY][0-9]{1,5}[ACDEFGHIKLMNPQRSTVWY])(?![A-Za-z0-9_/.-])",
            text,
            re.IGNORECASE,
        ):
            mutation = match.group(1).upper()
            if mutation not in seen:
                seen.add(mutation)
                mutations.append(mutation)
        return mutations

    @staticmethod
    def _parse_point_mutation_code(mutation: str) -> dict[str, Any] | None:
        match = re.match(
            r"^([ACDEFGHIKLMNPQRSTVWY])([0-9]{1,5})([ACDEFGHIKLMNPQRSTVWY])$",
            str(mutation or "").strip().upper(),
        )
        if not match:
            return None
        wt, pos, mt = match.groups()
        return {"mutation": f"{wt}{int(pos)}{mt}", "wild_type": wt, "position": int(pos), "mutant": mt}

    @classmethod
    def _message_requests_mutation_review(cls, message: str) -> bool:
        mutations = cls._extract_requested_mutations(message)
        if not mutations:
            return False
        lower = str(message or "").lower()
        review_tokens = (
            "指定突变", "这些突变", "这个突变", "复核", "重新分析", "怎么看", "怎么样",
            "实验反馈", "实验结果", "不一致", "冲突", "比活", "活性", "稳定性", "热稳定",
            "下降", "提高", "提升", "保留", "补偿", "risk", "review", "feedback",
            "variant review", "mutation review",
        )
        return any(token in lower for token in review_tokens)

    @classmethod
    def _build_requested_mutation_review_report(cls, task: str, tool_results: list[dict]) -> str:
        """Build a deterministic review for user-specified point mutations.

        This is intentionally conservative: it summarizes available structured
        evidence and clearly marks unknown feature fields instead of inventing
        residue-level mechanisms.
        """
        requested = cls._extract_requested_mutations(task)
        if not requested or not cls._message_requests_mutation_review(task):
            return ""

        parsed_mutations = [
            item for item in (cls._parse_point_mutation_code(code) for code in requested) if item
        ]
        if not parsed_mutations:
            return ""

        payloads: dict[str, dict[str, Any]] = {}
        for result in tool_results or []:
            tool_name = str(result.get("tool_name") or "")
            if not tool_name:
                continue
            payloads[tool_name] = cls._safe_parse_json(str(result.get("result", "")))

        identity_data = payloads.get("enzyme_identity_profile", {})
        objective_data = payloads.get("enzyme_objective_module_plan", {})
        mutation_data = payloads.get("mutation_priority_score") or payloads.get("mutation_scan") or {}
        rosetta_data = payloads.get("rosetta_ddg", {})
        mapping_data = payloads.get("residue_mapping_sifts", {})
        numbering_data = payloads.get("residue_numbering_gate", {})

        protected_positions: set[int] = set()
        for source in (identity_data, mutation_data):
            if not isinstance(source, dict):
                continue
            for key in ("protected_positions", "protected_user_positions", "protected_pdb_positions"):
                values = source.get(key)
                if isinstance(values, list):
                    for value in values:
                        try:
                            protected_positions.add(int(value))
                        except (TypeError, ValueError):
                            continue
            identity_gate = source.get("identity_gate")
            if isinstance(identity_gate, dict):
                values = identity_gate.get("protected_positions")
                if isinstance(values, list):
                    for value in values:
                        try:
                            protected_positions.add(int(value))
                        except (TypeError, ValueError):
                            continue

        candidate_rows: list[dict[str, Any]] = []
        if isinstance(mutation_data, dict):
            for key in ("experiment_design_table", "tier_1_candidates", "tier_2_candidates", "candidate_mutations"):
                values = mutation_data.get(key)
                if isinstance(values, list):
                    candidate_rows.extend(row for row in values if isinstance(row, dict))

        rows_by_mutation: dict[str, dict[str, Any]] = {}
        rows_by_position: dict[int, dict[str, Any]] = {}
        for row in candidate_rows:
            try:
                position = int(row.get("position") or row.get("user_position") or row.get("pdb_position"))
                rows_by_position.setdefault(position, row)
            except (TypeError, ValueError):
                position = None
            recommended = row.get("recommended_mutations")
            if isinstance(recommended, list):
                for item in recommended:
                    code = item.get("mutation") if isinstance(item, dict) else item
                    parsed = cls._parse_point_mutation_code(str(code or ""))
                    if parsed:
                        rows_by_mutation.setdefault(parsed["mutation"], row)

        ddg_by_mutation: dict[str, dict[str, Any]] = {}
        if isinstance(rosetta_data, dict):
            for item in rosetta_data.get("results") or []:
                if not isinstance(item, dict):
                    continue
                parsed = cls._parse_point_mutation_code(str(item.get("mutation") or ""))
                if parsed:
                    ddg_by_mutation[parsed["mutation"]] = item

        def _status_text() -> str:
            statuses = []
            if isinstance(identity_data, dict) and identity_data:
                statuses.append(f"身份={identity_data.get('identity_status', 'unknown')}")
            if isinstance(objective_data, dict) and objective_data:
                statuses.append(f"目标门控={objective_data.get('status', 'unknown')}")
            if isinstance(mutation_data, dict) and mutation_data:
                statuses.append(
                    "候选表="
                    + str(
                        mutation_data.get("candidate_table_status")
                        or (mutation_data.get("summary", {}) if isinstance(mutation_data.get("summary"), dict) else {}).get("candidate_table_status")
                        or "unknown"
                    )
                )
            if isinstance(mapping_data, dict) and mapping_data:
                statuses.append(f"编号映射={mapping_data.get('mapping_status') or mapping_data.get('status') or 'available'}")
            if isinstance(numbering_data, dict) and numbering_data:
                statuses.append(f"编号门控={numbering_data.get('status', 'available')}")
            if isinstance(rosetta_data, dict) and rosetta_data:
                rosetta_label = "real_rosetta" if rosetta_data.get("is_real_rosetta") else rosetta_data.get("evidence_level") or rosetta_data.get("status")
                statuses.append(f"ΔΔG={rosetta_label}")
            return "；".join(statuses) if statuses else "本轮没有完成的位点级工具证据"

        def _effect_from_row(row: dict[str, Any] | None, field: str, fallback: str) -> str:
            if not isinstance(row, dict):
                return fallback
            for key in (field, "expected_effect", "mutation_logic"):
                value = row.get(key)
                if value:
                    return str(value)
            return fallback

        def _ddg_text(mutation: str) -> str:
            item = ddg_by_mutation.get(mutation)
            if not item:
                return "未知；未见本轮 ΔΔG 结果"
            value = item.get("ddg_kcal_mol")
            label = item.get("ddg_label", "unknown")
            prefix = "Rosetta" if rosetta_data.get("is_real_rosetta") else "启发式ΔΔG"
            return f"{prefix}={value} kcal/mol；{label}"

        def _mechanism_hint(item: dict[str, Any], matched_row: dict[str, Any] | None) -> str:
            wt = item["wild_type"]
            mt = item["mutant"]
            if wt == "P" and mt == "T":
                return "Pro->Thr 可能解除局部构象刚性；若位于 loop/通道门控区，可能提高底物进出或产物释放，但常伴随稳定性下降风险。"
            if wt == "P":
                return "Pro 位点常影响主链刚性；突变需重点复核 loop、turn 和局部稳定性。"
            if mt == "P":
                return "引入 Pro 可能降低 loop 构象熵、提高局部刚性；也可能破坏二级结构或活性所需柔性。"
            if wt in {"D", "E", "H", "C", "S", "K", "R"} or mt in {"D", "E", "H", "C", "S", "K", "R"}:
                return "涉及可电离/催化常见侧链；需复核催化、金属/辅因子、pH 与盐桥网络。"
            if isinstance(matched_row, dict) and matched_row.get("mutation_logic"):
                return str(matched_row.get("mutation_logic"))
            return "缺少 pocket/channel/relSASA/保守性特征；只能作为指定突变人工复核项。"

        table_lines = [
            "| 突变 | 编号/区域 | 活性影响 | 稳定性影响 | 风险 | 实验动作 |",
            "|------|-----------|----------|------------|------|----------|",
        ]
        detail_lines: list[str] = []
        any_protected = False
        any_feedback = any(token in str(task).lower() for token in ("实验", "feedback", "不一致", "下降", "提高", "提升"))

        for item in parsed_mutations:
            mutation = item["mutation"]
            pos = item["position"]
            matched_row = rows_by_mutation.get(mutation) or rows_by_position.get(pos)
            protected = pos in protected_positions
            any_protected = any_protected or protected
            region = "unknown"
            if isinstance(matched_row, dict):
                region = str(
                    matched_row.get("region_type")
                    or matched_row.get("structural_region")
                    or matched_row.get("site_class")
                    or matched_row.get("category")
                    or "candidate_position"
                )
            numbering = f"pos={pos}；region={region}"
            if protected:
                numbering += "；protected"

            activity_effect = _effect_from_row(
                matched_row,
                "activity_effect",
                "未知；需底物/反应/活性 assay 证据",
            )
            stability_effect = _ddg_text(mutation)
            if stability_effect.startswith("未知") and isinstance(matched_row, dict):
                stability_effect = str(matched_row.get("stability_effect") or matched_row.get("expected_effect") or stability_effect)
            risk = "命中保护位点，No-Go" if protected else _mechanism_hint(item, matched_row)
            action = (
                "先确认编号和保护区，当前不排单"
                if protected
                else "作为 Watch 单点复核；需 WT 同批活性、稳定性、表达/纯化验证"
            )
            if any_feedback and item["wild_type"] == "P" and item["mutant"] == "T":
                action = "保留活性收益假设，优先筛周边/远端稳定性补偿位点；不要直接回退该突变。"
            table_lines.append(
                f"| {mutation} | {numbering} | {activity_effect} | {stability_effect} | {risk} | {action} |"
            )
            detail_lines.extend([
                f"### {mutation}",
                "",
                f"- **原残基/新残基**：{item['wild_type']} -> {item['mutant']}；位置={pos}。",
                f"- **机制解释**：{_mechanism_hint(item, matched_row)}",
                f"- **稳定性证据**：{_ddg_text(mutation)}。",
                f"- **候选来源**：{'匹配 mutation_priority_score 候选行' if matched_row else '未匹配到本轮候选行'}。",
                f"- **实验动作**：{action}",
                "",
            ])

        decision = "No-Go" if any_protected else "Watch"
        if rows_by_mutation and not any_protected:
            decision = "Watch；有候选行匹配但仍需实验验证"

        lines = [
            "# 指定突变复核",
            "",
            "## 复核结论",
            f"- **指定突变**：{', '.join(item['mutation'] for item in parsed_mutations)}。",
            f"- **当前决策**：{decision}。",
            "- **边界**：本复核只整合本轮已有工具证据和用户反馈；没有编号、结构口袋、保守性或 WT baseline 时，不声明确定提升。",
            "",
            "## 证据状态",
            f"- **工具/门控状态**：{_status_text()}。",
            "- **缺口**：若缺少 residue feature table，relSASA、pocket/channel、到催化簇距离和保守性字段只能标为 unknown。",
            "",
            "## 指定突变逐条复核",
            *table_lines,
            "",
            "## 位点机制与实验动作",
            *detail_lines,
        ]
        if any_feedback:
            lines.extend([
                "## 预测偏差处理",
                "- 若用户实验显示活性升、稳定性降，优先按 activity-stability trade-off 处理：保留活性收益假设，再找稳定性补偿位点。",
                "- 下一轮不应直接组合多点；先做单点复测、WT 同批对照、表达/纯化质量检查，再推进二点补偿。",
                "",
            ])
        lines.extend([
            "## 下一步",
            "- P0 后续需要把 relSASA、催化簇距离、pocket/channel、保守性、ddG、MD RMSF 统一写入 residue feature table。",
            "- 只有指定突变通过编号、保护区、目标 assay 和 WT baseline 复核后，才能从 Watch 升级为可排单候选。",
        ])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _extract_attached_object_name(text: str) -> str | None:
        """Extract an uploaded structure object name from the chat attachment block."""
        if not isinstance(text, str) or "object_name" not in text:
            return None

        candidates = re.findall(
            r"['\"]?object_name['\"]?\s*[:=]\s*['\"]?([^'\"\s,\]\}]+)",
            text,
        )
        for candidate in candidates:
            normalized = candidate.strip().strip("'\"")
            if AgentOrchestrator._is_uploaded_object_placeholder(normalized):
                continue
            lowered = normalized.lower()
            if lowered.endswith((".pdb", ".ent", ".cif")):
                return normalized

        for candidate in candidates:
            normalized = candidate.strip().strip("'\"")
            if AgentOrchestrator._is_uploaded_object_placeholder(normalized):
                continue
            if normalized.startswith("uploads/"):
                return normalized
        return None

    @classmethod
    def _has_concrete_protein_input(cls, text: str, context: str = "") -> bool:
        """Return true only when a request contains actionable protein input.

        This deliberately excludes broad natural-language questions. Without this
        gate, generic Chinese questions can fall through to a UniProt
        sequence_search using the whole sentence as a keyword query.
        """
        combined = f"{text}\n{context}".strip()
        if cls._extract_sequence(combined):
            return True
        if cls._extract_attached_object_name(combined):
            return True
        if cls._extract_uniprot_reference(text) or cls._extract_pdb_id_reference(text):
            return True
        if cls._extract_named_protein_reference(text):
            return True
        if "[Protein sequence detected" in context or "[Known protein target discussed" in context:
            return True
        uppercase_hits = re.findall(r"\b([A-Z][A-Z0-9]{1,14}(?:[-/][A-Z0-9]{1,14})*)\b", text)
        ignored = {"AI", "IT", "PDB", "MD", "SOP", "JSON", "CSV", "API", "RDS", "OSS"}
        mutation_code = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY][0-9]{1,5}[ACDEFGHIKLMNPQRSTVWY]$")
        if any(hit.upper() not in ignored and not mutation_code.match(hit.upper()) for hit in uppercase_hits):
            return True
        if re.search(r"\b[OPQ][0-9][A-Z0-9]{3}[0-9]\b", text):
            return True
        return False

    @staticmethod
    def _extract_named_protein_reference(text: str) -> str:
        """Extract explicit Chinese protein/enzyme naming fields from user text."""
        if not isinstance(text, str):
            return ""
        patterns = [
            r"(?:酶的?名称|蛋白(?:质)?名称|目标蛋白|目标酶|蛋白质?|酶)\s*(?:为|是|=|[:：])\s*([^\n，,。；;]+)",
            r"(?:enzyme|protein)\s+(?:name\s*)?(?:is|=|[:：])\s*([^\n,;]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                name = re.split(
                    r"(?:\s+|^)?(?:结构|目标|底物|反应|表达|条件|体系|突变|mutation|mutant|variant)\s*[:：]?",
                    name,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0].strip()
                if name:
                    return name[:120]
        return ""

    @staticmethod
    def _extract_uniprot_reference(text: str) -> str:
        """Extract an explicit UniProt accession from labelled user input."""
        if not isinstance(text, str):
            return ""
        patterns = [
            r"(?:uniprot(?:kb)?(?:\s*(?:id|accession|编号|号))?|UniProt编号)\s*[:：=]?\s*([A-Za-z0-9]{6,10}(?:-\d+)?)",
            r"(?:UniProt|uniprot)\s+([A-Za-z0-9]{6,10}(?:-\d+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                accession = match.group(1).strip().upper()
                if re.fullmatch(r"[A-Z][A-Z0-9]{5,9}(?:-\d+)?", accession):
                    return accession
        return ""

    @staticmethod
    def _extract_pdb_id_reference(text: str) -> str:
        """Extract an explicit PDB ID or an exact four-character attachment basename."""
        if not isinstance(text, str):
            return ""
        patterns = [
            r"(?:pdb(?:\s*(?:id|编号|号))?|PDB编号)\s*[:：=]?\s*([0-9][A-Za-z0-9]{3})",
            r"(?:PDB|pdb)\s+([0-9][A-Za-z0-9]{3})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().upper()
        attachment_names = re.findall(
            r"(?:^|[\s,\[])name\s*[:=]\s*['\"]?([^'\"\s,\]\}]+)",
            text,
            re.IGNORECASE,
        )
        object_names = re.findall(
            r"object_name\s*[:=]\s*['\"]?([^'\"\s,\]\}]+)",
            text,
            re.IGNORECASE,
        )
        for candidate in [*attachment_names, *object_names]:
            basename = candidate.replace("\\", "/").rsplit("/", 1)[-1]
            match = re.fullmatch(r"([0-9][A-Za-z0-9]{3})\.(?:pdb|ent|cif)", basename, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return ""

    @classmethod
    def _extract_lookup_target(cls, task: str) -> tuple[str, str]:
        """Return a conservative lookup query and target database."""
        named = cls._extract_named_protein_reference(task)
        if named:
            return named, "uniprot"
        uniprot_id = cls._extract_uniprot_reference(task)
        if uniprot_id:
            return uniprot_id, "uniprot"
        pdb_id = cls._extract_pdb_id_reference(task)
        if pdb_id:
            return pdb_id, "pdb"
        name = cls._extract_protein_name(task)
        return name, "uniprot"

    @classmethod
    def _is_model_meta_question(cls, message: str, context: str = "") -> bool:
        """Detect questions about the model/system itself, not a protein task."""
        if cls._has_concrete_protein_input(message, ""):
            return False
        lower = message.lower()
        subject_terms = [
            "模型", "系统", "平台", "你", "你们", "回答", "结果", "报告",
            "model", "system", "platform", "you", "your answer", "result",
        ]
        topic_terms = [
            "能力边界", "边界", "文献依据", "依据", "胡编", "编造", "可靠", "可信",
            "证据", "怎么用", "能不能", "会不会", "是否", "实验方案",
            "capability", "limitation", "citation", "evidence", "hallucinat",
            "reliable", "trust", "how to use",
        ]
        return any(term in lower for term in subject_terms) and any(term in lower for term in topic_terms)

    @staticmethod
    def _is_enzyme_engineering_request(message: str) -> bool:
        lower = message.lower()
        return any(kw in lower for kw in [
            "enzyme", "酶", "ph", "酸性", "碱性", "最适", "酶活", "engineering", "改造",
            "mutation", "mutant", "variant", "stability", "stabilize", "activity",
            "catalytic", "substrate", "kcat", "km", "specificity", "optimum",
            "突变", "耐酸", "耐碱", "耐热", "热稳定", "比活力",
        ])

    @classmethod
    def _should_clarify_before_tools(cls, message: str, route: str, context: str = "") -> bool:
        """Decide whether an apparent protein task lacks enough input for tools."""
        if cls._is_connectivity_status_request(message):
            return False
        if route == "general":
            return False
        if cls._has_concrete_protein_input(message, context):
            return False
        lower = message.lower()
        if route == "design":
            return True
        mutation_code_only = bool(
            re.search(r"\b[ACDEFGHIKLMNPQRSTVWY][0-9]{1,5}[ACDEFGHIKLMNPQRSTVWY]\b", message, re.IGNORECASE)
        )
        vague_subject = any(kw in lower for kw in [
            "这个酶", "该酶", "这个蛋白", "该蛋白", "this enzyme", "this protein",
            "这个模型", "这个序列", "只给你一句需求",
        ])
        search_without_target = any(kw in lower for kw in [
            "查", "搜索", "检索", "文献", "证据", "search", "find", "literature", "evidence",
        ]) and any(kw in lower for kw in ["酶", "蛋白", "protein", "enzyme"])
        return mutation_code_only or cls._is_enzyme_engineering_request(message) or vague_subject or search_without_target

    @staticmethod
    def _build_missing_input_reply(message: str, route: str) -> str:
        """Ask for missing scientific inputs instead of fabricating a report."""
        return (
            "## 任务理解\n"
            "你提出的是酶/蛋白分析或改造相关任务，但当前输入还不足以进入工具分析。\n\n"
            "## 已知输入\n"
            f"- 用户需求：{message.strip()[:300]}\n"
            f"- 初步任务类型：{route}\n\n"
            "## 缺失信息\n"
            "- 酶或蛋白名称、UniProt/PDB 编号，或完整氨基酸序列\n"
            "- 如需结构分析：PDB/mmCIF 结构或已上传结构文件\n"
            "- 明确改造目标：耐热、pH 适应性、活性、底物特异性、表达量等\n"
            "- 底物、反应条件、表达体系和实验筛选约束\n\n"
            "## 下一步\n"
            "请先补充上述至少一类可定位输入。补齐后我再选择检索、结构、突变评分或实验设计工具；"
            "在信息不足时不会直接给具体位点或强结论。"
        )

    @classmethod
    def _tool_results_have_no_evidence(cls, tool_results: list[dict]) -> bool:
        """Identify empty evidence paths before synthesis templates can mask them."""
        if not tool_results:
            return False

        saw_search = False
        saw_support = False
        for result in tool_results:
            tool_name = result.get("tool_name")
            status = result.get("status")
            payload = cls._safe_parse_json(str(result.get("result", "")))
            if tool_name == "sequence_search":
                saw_search = True
                count = payload.get("results_count")
                results = payload.get("results")
                if status == "completed" and ((isinstance(count, int) and count > 0) or bool(results)):
                    saw_support = True
                continue
            if status == "completed" and payload:
                saw_support = True

        return saw_search and not saw_support

    @classmethod
    def _build_connectivity_reply(cls, tool_results: list[dict]) -> str | None:
        """Build one concise, evidence-backed answer for a connectivity check."""
        result = next(
            (item for item in tool_results if item.get("tool_name") == "external_connectivity_check"),
            None,
        )
        if result is None:
            return None
        payload = cls._safe_parse_json(str(result.get("result") or ""))
        if not payload:
            return "当前无法确认平台联网状态：联网探测工具没有返回可核验结果。"

        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        successful = int(summary.get("successful_probes") or 0)
        total = int(summary.get("total_probes") or 0)
        probes = payload.get("probes") if isinstance(payload.get("probes"), list) else []
        reachable = [str(probe.get("source")) for probe in probes if isinstance(probe, dict) and probe.get("status") == "live"]
        blocked = [str(probe.get("source")) for probe in probes if isinstance(probe, dict) and probe.get("status") != "live"]

        if payload.get("connected") is True and successful > 0:
            lines = [
                f"已联网。本轮刚刚进行了实时外部探测，{successful}/{total or len(probes)} 个官方科学数据库接口可访问。",
            ]
            if reachable:
                lines.append(f"已连通：{'、'.join(reachable)}。")
            if blocked:
                lines.append(f"未连通：{'、'.join(blocked)}；这部分当前不能声称可用。")
            lines.append("该结果只证明上述接口当前可访问，不代表所有网页、数据库或计算工具都可用。")
            return "\n\n".join(lines)

        return (
            f"当前未连通。平台本轮已实际尝试 {total or len(probes)} 个官方科学数据库接口，"
            "但没有获得成功响应，因此不能声称已经联网。"
        )

    @staticmethod
    def _build_no_evidence_reply(task: str, tool_results: list[dict]) -> str:
        safe_task = AgentOrchestrator._display_task_summary(task)
        search_summaries = []
        for result in tool_results:
            if result.get("tool_name") != "sequence_search":
                continue
            payload = AgentOrchestrator._safe_parse_json(str(result.get("result", "")))
            query = payload.get("query", "")
            database = payload.get("database", "")
            status = payload.get("status", result.get("status", "unknown"))
            search_summaries.append(f"- `sequence_search`：query=`{query}`，database=`{database}`，status=`{status}`，results=0")
        summary = "\n".join(search_summaries) if search_summaries else "- 未获得可用检索证据"
        return (
            "## 任务理解\n"
            f"你希望分析：{safe_task}\n\n"
            "## 工具调用摘要\n"
            f"{summary}\n\n"
            "## 结论\n"
            "当前没有检索到可支撑结论的序列、结构或文献证据，因此不能给出确定性改造建议。\n\n"
            "## 建议补充\n"
            "- 提供完整氨基酸序列、UniProt/PDB 编号或明确酶名称\n"
            "- 说明改造目标、底物、pH/温度、表达体系和筛选约束\n"
            "- 如已有实验结果，请提供 WT 与突变体的活性、稳定性或表达数据\n\n"
            "补齐后再进入工具链分析。"
        )

    @staticmethod
    def _format_plan_params(params: dict) -> str:
        if not params:
            return "{}"
        display_params = dict(params)
        for key in ("pdb_object_name", "object_name", "download_url"):
            if key in display_params:
                display_params[key] = "[uploaded-object]"
        sequence_label = None
        if display_params.get("sequence_provenance") == "pdb_coordinate_derived":
            for key in ("sequence", "query_sequence", "protein_sequence", "input_sequence"):
                value = display_params.get(key)
                if isinstance(value, str) and value:
                    sequence_label = f"[pdb-coordinate-derived sequence; {len(value)} aa]"
                    display_params[key] = sequence_label
        if sequence_label is None:
            for key in ("sequence", "query_sequence", "protein_sequence"):
                value = display_params.get(key)
                if isinstance(value, str) and len(value) > 80 and re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWYBXZJUO]+", value.strip().upper()):
                    display_params[key] = f"[sequence; {len(value.strip())} aa]"
        try:
            rendered = json.dumps(display_params, ensure_ascii=False, default=str)
        except TypeError:
            rendered = str(display_params)
        return rendered if len(rendered) <= 320 else rendered[:317] + "..."

    @classmethod
    def _sanitize_plan_for_display(cls, plan: list[PlanStep] | list[dict]) -> list[dict]:
        """Return a browser-safe plan while retaining executable params server-side."""
        sanitized: list[dict] = []
        for index, step in enumerate(plan, start=1):
            if isinstance(step, PlanStep):
                step_id = step.id
                tool_name = step.tool_name
                description = step.description
                params = step.params
                status = step.status
            elif isinstance(step, dict):
                step_id = step.get("id", index)
                tool_name = step.get("tool_name") or step.get("tool")
                description = step.get("description", "")
                params = step.get("params") or {}
                status = step.get("status", "pending")
            else:
                continue
            safe_params = dict(params) if isinstance(params, dict) else {}
            for key in ("pdb_object_name", "object_name", "download_url"):
                if key in safe_params:
                    safe_params[key] = "[uploaded-object]"
            if safe_params.get("sequence_provenance") == "pdb_coordinate_derived":
                for key in ("sequence", "query_sequence", "protein_sequence", "input_sequence"):
                    value = safe_params.get(key)
                    if isinstance(value, str) and value:
                        safe_params[key] = f"[pdb-coordinate-derived sequence; {len(value)} aa]"
            else:
                for key in ("sequence", "query_sequence", "protein_sequence", "input_sequence"):
                    value = safe_params.get(key)
                    if isinstance(value, str) and len(value) > 80 and re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWYBXZJUO]+", value.strip().upper()):
                        safe_params[key] = f"[sequence; {len(value.strip())} aa]"
            sanitized.append({
                "id": step_id,
                "tool_name": tool_name,
                "description": description,
                "params": safe_params,
                "status": status,
            })
        return sanitized

    @classmethod
    def _restore_display_plan_payload(
        cls,
        plan: list[dict],
        task: str,
    ) -> list[dict]:
        """Restore only display placeholders before persisting a checkpoint.

        The browser never needs the object-store path, but the server checkpoint
        must retain it so a later confirmation can execute the exact plan.
        """
        object_name = cls._extract_attached_object_name(task)
        if not object_name:
            return plan
        restored: list[dict] = []
        for step in plan:
            item = dict(step)
            params = dict(item.get("params") or {})
            for key in ("pdb_object_name", "object_name"):
                if params.get(key) == "[uploaded-object]":
                    params[key] = object_name
            item["params"] = params
            restored.append(item)
        return restored

    @classmethod
    def _plan_signature(cls, plan: list[PlanStep] | list[dict]) -> str:
        """Stable signature for the exact strategy checkpoint shown to the user."""
        normalized: list[dict[str, Any]] = []
        for index, step in enumerate(plan, start=1):
            if isinstance(step, PlanStep):
                step_id = step.id
                tool_name = step.tool_name
                description = step.description
                params = step.params
            elif isinstance(step, dict):
                step_id = step.get("id", index)
                tool_name = step.get("tool_name") or step.get("tool")
                description = step.get("description", "")
                params = step.get("params") or {}
            else:
                continue
            normalized.append({
                "id": int(step_id) if str(step_id).isdigit() else index,
                "tool_name": str(tool_name or ""),
                "description": str(description or ""),
                "params": params if isinstance(params, dict) else {},
            })
        raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _task_fingerprint(cls, task: str, context: str = "") -> str:
        """Fingerprint task identity from durable anchors, not a fixed workflow."""
        combined = f"{task}\n{context}".strip()
        sequence = cls._extract_sequence(combined) or ""
        object_name = cls._extract_attached_object_name(combined) or ""
        uniprot = cls._extract_uniprot_reference(combined) or ""
        pdb_id = cls._extract_pdb_id_reference(combined) or ""
        named_target = cls._extract_named_protein_reference(combined) or ""
        if sequence:
            identity = {"sequence_sha256": hashlib.sha256(sequence.encode("utf-8")).hexdigest()}
        else:
            compact = re.sub(r"\s+", " ", combined.lower()).strip()[:1200]
            identity = {"task_text": compact}
        identity.update({
            "object_name": object_name,
            "uniprot": uniprot,
            "pdb_id": pdb_id,
            "named_target": named_target,
        })
        raw = json.dumps(identity, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _plan_steps_from_payload(cls, payload: Any) -> list[PlanStep]:
        """Convert a confirmed checkpoint payload into executable plan steps."""
        if not isinstance(payload, list):
            raise ValueError("confirmed_plan must be a list")
        steps: list[PlanStep] = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"confirmed_plan step {index} must be an object")
            tool_name = item.get("tool_name") or item.get("tool")
            if not isinstance(tool_name, str) or not tool_name.strip():
                raise ValueError(f"confirmed_plan step {index} is missing tool_name")
            params = item.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError(f"confirmed_plan step {index} params must be an object")
            step_id = item.get("id", index)
            try:
                resolved_id = int(step_id)
            except (TypeError, ValueError):
                resolved_id = index
            steps.append(PlanStep(
                id=resolved_id,
                tool_name=tool_name.strip(),
                description=str(item.get("description") or f"Execute {tool_name.strip()}"),
                params=params,
                status="pending",
            ))
        if not steps:
            raise ValueError("confirmed_plan is empty")
        return steps

    @classmethod
    def _confirmed_checkpoint_error(
        cls,
        *,
        confirmed_plan: Any,
        strategy_signature: str | None,
        task_fingerprint: str | None,
        effective_message: str,
        protein_context: str,
    ) -> str | None:
        """Return a fail-closed reason if the confirmed checkpoint is not valid."""
        if confirmed_plan is None and not strategy_signature:
            return "当前没有待确认的分析策略"
        try:
            plan = cls._plan_steps_from_payload(confirmed_plan)
        except ValueError as exc:
            return str(exc)
        expected_signature = cls._plan_signature(plan)
        if not strategy_signature:
            return "strategy_signature is missing"
        if str(strategy_signature).strip() != expected_signature:
            return "strategy_signature does not match confirmed_plan"
        # For execute_confirmed the visible/current message is often only a
        # control phrase such as "确认执行上述分析策略". The executable identity is
        # already locked by the plan signature. When the server-side active
        # checkpoint is unavailable and the client provides a signed plan, do
        # not recompute the task fingerprint from the control phrase and reject
        # an otherwise valid confirmation.
        return None

    @staticmethod
    def _build_checkpoint_missing_reply(reason: str) -> str:
        return (
            "策略检查点校验失败，当前不会执行工具。\n\n"
            f"- 原因：{reason}\n"
            "- 处理：请重新生成分析策略并再次确认；平台不能在缺失或不匹配的策略检查点下重新规划后冒充“按上面策略执行”。"
        )

    @staticmethod
    def _history_has_awaiting_strategy_checkpoint(history: list[dict]) -> bool:
        for message in reversed(history[-8:]):
            content = message.get("content", "") if isinstance(message, dict) else ""
            if not isinstance(content, str):
                continue
            if "状态：等待确认" in content and "策略指纹" in content:
                return True
        return False

    @staticmethod
    def _looks_like_strategy_confirmation(message: str) -> bool:
        compact = re.sub(r"[\s，。！？!?.]+", "", str(message or "").lower())
        if not compact:
            return False
        exact = {re.sub(r"[\s，。！？!?.]+", "", token.lower()) for token in policy_tokens("confirmation_tokens")}
        if compact in exact:
            return True
        policy = get_agent_strategy_policy()["policy"]
        max_chars = int(policy.get("max_typed_confirmation_chars") or 24)
        return (
            any(token in compact for token in exact if token)
            and len(compact) <= max_chars
        )

    @classmethod
    def _has_followup_payload_after_continuation(cls, message: str) -> bool:
        """Detect continuation requests that contain real task content."""
        if not isinstance(message, str):
            return False
        lower = message.lower()
        for token in policy_tokens("continuation_tokens"):
            token = token.strip().lower()
            if not token or token not in lower:
                continue
            remainder = lower.replace(token, "", 1)
            remainder = re.sub(r"[\s，。！？!?.、,;；:：]+", "", remainder)
            if len(remainder) >= 4:
                return True
        return False

    @classmethod
    def _is_unbound_strategy_confirmation(cls, message: str, history: list[dict], control: str) -> bool:
        return (
            control != "execute_confirmed"
            and cls._looks_like_strategy_confirmation(message)
            and not cls._has_followup_payload_after_continuation(message)
            and cls._history_has_awaiting_strategy_checkpoint(history)
        )

    @staticmethod
    def _sequence_strategy_profile(sequence: str) -> dict[str, Any]:
        seq = re.sub(r"[^ACDEFGHIKLMNPQRSTVWY]", "", (sequence or "").upper())
        if not seq:
            return {}
        length = len(seq)
        counts = {aa: seq.count(aa) for aa in "ACDEFGHIKLMNPQRSTVWY"}

        def pct(chars: str) -> float:
            return round(sum(counts.get(aa, 0) for aa in chars) * 100.0 / length, 1)

        motifs: list[str] = []
        if re.search(r"G[A-Z]S[A-Z]G", seq):
            motifs.append("GXSXG-like serine hydrolase motif present; catalytic-near residues must be protected until identity is confirmed")
        if re.search(r"D[ST]G", seq):
            motifs.append("D[ST]G-like acidic protease motif present; Asp-centered catalytic hypotheses need numbering confirmation")
        ngly = [match.start() + 1 for match in re.finditer(r"N[^P][ST]", seq)]
        if ngly:
            motifs.append(f"{len(ngly)} potential N-glycosylation motif(s), first positions {ngly[:4]}")
        cys_count = counts["C"]
        if cys_count >= 2:
            motifs.append(f"{cys_count} cysteines; disulfide/free-Cys state must be checked before mutation design")

        gly_pct = pct("G")
        pro_pct = pct("P")
        hydrophobic_pct = pct("AILMFWVY")
        charged_pct = pct("DEKRH")
        acidic_basic_delta = (counts["D"] + counts["E"]) - (counts["K"] + counts["R"] + counts["H"])
        fingerprint = hashlib.sha1(seq.encode("ascii")).hexdigest()[:10]
        focus: list[str] = []
        if gly_pct >= 9:
            focus.append("Gly-rich/flexible segments are likely candidate regions for stability work, after active-site protection")
        if pro_pct <= 3:
            focus.append("low Pro content suggests loop entropy-reduction substitutions may be worth testing")
        elif pro_pct >= 8:
            focus.append("high Pro content means extra Pro substitutions should be conservative and structure-gated")
        if hydrophobic_pct >= 42:
            focus.append("hydrophobic-rich sequence raises packing/aggregation trade-off; expose/core status must be separated")
        if charged_pct >= 25:
            focus.append("charge-rich sequence makes pH/salt effects important; surface charge changes need gradient assays")
        if acidic_basic_delta >= 8:
            focus.append("acidic bias suggests alkaline-shift strategies should avoid over-neutralizing stabilizing salt bridges")
        elif acidic_basic_delta <= -8:
            focus.append("basic bias suggests acid-shift strategies should avoid disrupting cationic binding patches")

        return {
            "fingerprint": fingerprint,
            "length": length,
            "gly_pct": gly_pct,
            "pro_pct": pro_pct,
            "cys_count": cys_count,
            "hydrophobic_pct": hydrophobic_pct,
            "charged_pct": charged_pct,
            "acidic_basic_delta": acidic_basic_delta,
            "motifs": motifs,
            "focus": focus,
        }

    @classmethod
    def _build_customization_lines(cls, task: str) -> list[str]:
        seq = cls._extract_sequence(task) or ""
        profile = cls._sequence_strategy_profile(seq)
        pdb_object_name = cls._extract_attached_object_name(task)
        attached_file_name = cls._extract_attached_file_name(task)
        uniprot_id = cls._extract_uniprot_reference(task)
        pdb_id = cls._extract_pdb_id_reference(task)
        assay_context = cls._extract_assay_context(task)
        lines: list[str] = []
        if profile:
            lines.append(
                "序列指纹 "
                f"`{profile['fingerprint']}`：{profile['length']} aa，"
                f"疏水={profile['hydrophobic_pct']}%，带电={profile['charged_pct']}%，"
                f"Gly={profile['gly_pct']}%，Pro={profile['pro_pct']}%，Cys={profile['cys_count']}。"
            )
            for item in profile["motifs"][:3]:
                lines.append(item)
            for item in profile["focus"][:4]:
                lines.append(item)
        elif pdb_object_name:
            lines.append("当前消息未提供独立 FASTA；已上传 PDB 的结构/序列信息会先通过预读、Foldseek 和 SIFTS/编号门控恢复，不能冒充 UniProt 或成熟蛋白编号。")
        else:
            lines.append("当前消息没有完整氨基酸序列；策略只能先做目标/结构/编号门控，不能冒充序列专属候选。")
        if pdb_object_name:
            display_name = attached_file_name or "uploaded PDB"
            lines.append(f"本轮绑定上传结构 `{display_name}`；真实对象路径仅用于工具取数，不作为残基编号证据。结构相关结论必须先过 Foldseek/SIFTS/编号门控。")
        elif pdb_id:
            lines.append(f"本轮绑定 PDB `{pdb_id}`，需要先解析结构和编号再给位点级结构建议。")
        elif uniprot_id:
            lines.append(f"本轮绑定 UniProt `{uniprot_id}`，先解析真实序列/注释再进入候选排序。")
        if assay_context:
            lines.append(f"已识别实验上下文键：{', '.join(sorted(assay_context.keys()))}；候选排序必须围绕这些证据。")
        else:
            lines.append("未识别到完整 assay context；候选位点只能作为计算假设，不能写成实验已验证策略。")
        return lines

    @classmethod
    def _strategy_input_mode(
        cls,
        task: str,
        pdb_preflight: dict[str, Any] | None = None,
    ) -> str:
        has_sequence = bool(cls._extract_sequence(task))
        has_uploaded_pdb = bool(cls._extract_attached_object_name(task))
        has_pdb_id = bool(cls._extract_pdb_id_reference(task))
        has_uniprot = bool(cls._extract_uniprot_reference(task))
        if has_uploaded_pdb and has_sequence:
            return "PDB + FASTA"
        if has_uploaded_pdb:
            return "PDB-only"
        if has_sequence and has_uniprot:
            return "FASTA + UniProt"
        if has_sequence:
            return "FASTA-only"
        if has_pdb_id:
            return "PDB ID-only"
        if has_uniprot:
            return "UniProt-only"
        if isinstance(pdb_preflight, dict):
            return "PDB-only" if pdb_preflight.get("status") == "readable" else "PDB-unreadable"
        return "insufficient-input"

    @classmethod
    def _build_input_evidence_audit_lines(
        cls,
        task: str,
        pdb_preflight: dict[str, Any] | None = None,
    ) -> list[str]:
        mode = cls._strategy_input_mode(task, pdb_preflight)
        assay_context = cls._extract_assay_context(task)
        lines = [f"- **输入类型**：{mode}。"]

        if mode == "PDB + FASTA":
            lines.append("- **已具备**：上传结构和独立 FASTA；可先做结构解析、序列/编号一致性和身份门控。")
            lines.append("- **主要门控**：PDB 链与 FASTA 是否一致、成熟蛋白/标签边界、外部编号映射、催化/辅因子/底物证据。")
        elif mode == "PDB-only":
            if isinstance(pdb_preflight, dict) and pdb_preflight.get("status") == "readable":
                lines.append(
                    "- **已具备**：上传 PDB 可预读，链/残基/坐标序列可作为结构输入；该序列仍标记为 PDB-coordinate-derived。"
                )
            else:
                lines.append("- **已具备**：上传 PDB 对象；执行前只可做结构读取和编号门控假设。")
            lines.append("- **主要门控**：缺少独立 FASTA/UniProt 实证映射；不能把坐标顺序编号冒充成熟蛋白或 UniProt 编号。")
            lines.append("- **候选边界**：身份、编号、催化/关键位点未确认前，不输出位点级突变候选表。")
        elif mode == "FASTA + UniProt":
            lines.append("- **已具备**：完整序列和 UniProt 线索；可优先核对功能注释、催化位点、结构模板和构建体边界。")
            lines.append("- **主要门控**：UniProt 记录是否匹配输入序列、成熟链/信号肽边界、目标 assay 条件。")
        elif mode == "FASTA-only":
            lines.append("- **已具备**：完整氨基酸序列；可做序列性质、同源/功能证据和必要时结构预测。")
            lines.append("- **主要门控**：缺少实测结构、外部编号、底物/assay 和催化位点证据时，位点级结构解释必须降级。")
        elif mode == "PDB ID-only":
            lines.append("- **已具备**：PDB 编号线索；需先拉取/解析对应结构并确认链 ID。")
            lines.append("- **主要门控**：PDB 链、序列、UniProt/SIFTS 映射和构建体边界未确认前，不投射残基位点。")
        elif mode == "UniProt-only":
            lines.append("- **已具备**：UniProt 编号线索；需先恢复真实序列和注释证据。")
            lines.append("- **主要门控**：没有结构或可靠同源模型时，不能输出口袋/通道/二壳层结构结论。")
        else:
            lines.append("- **已具备**：当前输入不足以绑定具体蛋白对象。")
            lines.append("- **主要门控**：需要 FASTA、PDB、UniProt 或明确对象后才能执行酶工程分析。")

        if assay_context:
            lines.append(f"- **已识别 assay context**：{', '.join(sorted(assay_context.keys()))}。")
        else:
            lines.append("- **assay 缺口**：未识别到底物、pH/温度、WT 基线、Tm/半衰期或蛋白归一化等完整实验上下文。")
        return lines

    @staticmethod
    def _objective_label(objective: str) -> str:
        labels = {
            "activity": "比活力/催化效率",
            "thermostability": "热稳定性",
            "specificity": "底物特异性",
            "ph_lowering": "降低 pH 最适/耐受",
            "ph_raising": "提高 pH 最适/耐受",
            "solubility": "可溶表达",
        }
        return labels.get(objective, objective)

    @classmethod
    def _build_objective_decomposition_lines(cls, task: str) -> list[str]:
        objectives = sorted(cls._classify_engineering_objectives(task))
        if not objectives:
            return [
                "- **识别目标**：未识别到可门控的具体工程目标。",
                "- **处理方式**：先补充目标和 assay，再进入候选工具；不生成通用突变表。",
            ]
        labels = [cls._objective_label(item) for item in objectives]
        lines = [f"- **识别目标**：{'；'.join(labels)}。"]
        if "activity" in objectives:
            lines.append("- **比活力线**：必须证明 specific activity、kcat 或 kcat/Km 改善，不能用总活或表达量替代。")
        if "thermostability" in objectives:
            lines.append("- **热稳定线**：必须同时看 Tm、热半衰期或热处理残余活性，并复核原始条件活性保持。")
        if "specificity" in objectives:
            lines.append("- **底物特异线**：必须有目标底物和对照底物，不能只用单底物活性声称选择性。")
        if "ph_lowering" in objectives or "ph_raising" in objectives:
            lines.append("- **pH 线**：需区分最适 pH 偏移、pH 稳定性和单点活性比值，不能混写。")
        if "solubility" in objectives:
            lines.append("- **表达线**：必须区分总表达、可溶表达和可溶活性蛋白，改表达不等于改催化。")
        if "activity" in objectives and "thermostability" in objectives:
            lines.append("- **协同点**：二壳层、入口 loop 和局部网络可能同时影响催化与稳定。")
            lines.append("- **冲突点**：增稳常会降低局部柔性，增活常会提高动态性；候选排序必须同时保留活性和稳定性指标。")
        lines.append("- **门控输出**：证据通过时才输出候选表；门控未通过时只输出缺口、保护区和补证据路线。")
        return lines

    @staticmethod
    def _sequence_preview_from_pdb_analysis(analysis: dict[str, Any]) -> str:
        seqres = analysis.get("seqres_sequence")
        if isinstance(seqres, str) and seqres.strip():
            return seqres.strip()
        chains = analysis.get("chains")
        if isinstance(chains, list):
            for chain in chains:
                if isinstance(chain, dict) and isinstance(chain.get("sequence"), str) and chain["sequence"].strip():
                    return chain["sequence"].strip()
        return ""

    async def _build_pdb_preflight_summary(self, task: str) -> dict[str, Any] | None:
        """Lightweight uploaded-PDB readability check for the plan confirmation screen."""
        object_name = self._extract_attached_object_name(task)
        if not object_name:
            return None
        display_name = self._extract_attached_file_name(task) or "uploaded PDB"
        try:
            from app.services.storage import download_file
            from app.services.pdb_parser import parse_pdb

            data = await download_file(object_name)
            text = data.decode("utf-8", errors="replace")
            analysis = parse_pdb(text)
            chains = analysis.get("chains") if isinstance(analysis.get("chains"), list) else []
            sequence = self._sequence_preview_from_pdb_analysis(analysis)
            return {
                "status": "readable",
                "display_name": display_name,
                "bytes": len(data),
                "line_count": len(text.splitlines()),
                "chain_count": analysis.get("chain_count") if analysis.get("chain_count") is not None else len(chains),
                "total_residues": analysis.get("total_residues"),
                "total_atoms": analysis.get("total_atoms"),
                "chains": chains[:6],
                "sequence_length": len(sequence) if sequence else 0,
                "sequence_preview": sequence[:40] if sequence else "",
                "coordinate_sequence": sequence,
            }
        except Exception as exc:
            logger.exception("Uploaded PDB preflight failed for plan confirmation")
            return {
                "status": "failed",
                "display_name": display_name,
                "error": self._sanitize_uploaded_metadata_text(str(exc), limit=240),
            }

    async def _hydrate_uploaded_pdb_sequence_for_plan(
        self,
        plan: list[PlanStep],
        task: str,
    ) -> list[PlanStep]:
        """Freeze a readable uploaded chain sequence into the pre-confirmation plan.

        The sequence is deterministically derived from the uploaded PDB's
        SEQRES/ATOM records before strategy signing. It is therefore an explicit
        plan input, not an execution-time parameter rewrite. It remains a
        PDB-coordinate-derived sequence until a separate external mapping is
        validated.
        """
        if not plan or not self._extract_attached_object_name(task):
            return plan

        needs_sequence = any(
            step.tool_name in {
                "predict_properties",
                "annotation_bundle",
                "enzyme_identity_profile",
                "protein_benchmark",
                "enzyme_function",
                "mutation_priority_score",
                "kcat_predict",
                "mutation_scan",
                "protssn_score",
                "blast_search",
                "rosetta_ddg",
            }
            for step in plan
        )
        if not needs_sequence:
            return plan

        preflight = await self._build_pdb_preflight_summary(task)
        sequence = str(preflight.get("coordinate_sequence") or "") if isinstance(preflight, dict) else ""
        if len(sequence) < 10:
            return plan

        parameter_names = {
            "predict_properties": "sequence",
            "annotation_bundle": "sequence",
            "enzyme_identity_profile": "sequence",
            "protein_benchmark": "query_sequence",
            "enzyme_function": "sequence",
            "mutation_priority_score": "sequence",
            "kcat_predict": "protein_sequence",
            "mutation_scan": "sequence",
            "protssn_score": "sequence",
            "blast_search": "sequence",
            "rosetta_ddg": "sequence",
        }
        for step in plan:
            if step.tool_name == "residue_mapping_sifts" and not step.params.get("input_sequence"):
                step.params = {
                    **step.params,
                    "input_sequence": sequence,
                }
            parameter = parameter_names.get(step.tool_name)
            if parameter and not step.params.get(parameter):
                step.params = {
                    **step.params,
                    parameter: sequence,
                    "sequence_provenance": "pdb_coordinate_derived",
                }
        return plan

    @staticmethod
    def _format_pdb_preflight_summary(pdb_preflight: dict[str, Any] | None) -> list[str]:
        if not isinstance(pdb_preflight, dict):
            return []
        display_name = pdb_preflight.get("display_name") or "uploaded PDB"
        if pdb_preflight.get("status") != "readable":
            return [
                f"已检测到上传结构 `{display_name}`，但确认页轻量预读失败：{pdb_preflight.get('error', 'unknown error')}。执行阶段仍会按工具门控重试读取。"
            ]
        chain_bits: list[str] = []
        chains = pdb_preflight.get("chains")
        if isinstance(chains, list):
            for chain in chains[:6]:
                if not isinstance(chain, dict):
                    continue
                chain_bits.append(
                    f"链{chain.get('chain_id', '?')}:{chain.get('residue_count', '?')} aa"
                    f"({chain.get('residue_range', 'range N/A')})"
                )
        sequence_preview = pdb_preflight.get("sequence_preview") or ""
        sequence_part = (
            f"；序列前缀=`{sequence_preview}`"
            if sequence_preview
            else "；未从 SEQRES/坐标恢复序列前缀"
        )
        chain_part = f"；{'；'.join(chain_bits)}" if chain_bits else ""
        return [
            f"已预读上传结构 `{display_name}`：{pdb_preflight.get('line_count', 'N/A')} 行，"
            f"{pdb_preflight.get('bytes', 'N/A')} bytes，链数={pdb_preflight.get('chain_count', 'N/A')}，"
            f"残基数={pdb_preflight.get('total_residues', 'N/A')}，原子数={pdb_preflight.get('total_atoms', 'N/A')}"
            f"{chain_part}{sequence_part}。"
        ]

    @classmethod
    def _build_strategy_checkpoint(cls, task: str) -> dict:
        """Describe the design hypothesis before listing executable tools."""
        objectives = cls._classify_engineering_objectives(task)
        goal = cls._primary_engineering_goal(objectives)
        if "activity" in objectives and "thermostability" in objectives:
            return {
                "title": "比活力 + 热稳定性双目标：先判定身份和活性中心，再分线设计",
                "logic": [
                    "第一优先级是确认酶身份、底物、催化/结合位点和编号体系；这些不清楚时不能给位点级突变建议。",
                    "比活力路线只分析底物入口、通道、口袋边缘和二壳层；不把表面电荷或远端柔性区直接解释成催化增益。",
                    "热稳定性路线只在非催化柔性区、局部疏松区、盐桥/氢键网络和构建体边界内找候选。",
                    "两个目标可能冲突：增稳突变可能降低活性，增活突变可能增加柔性；实验必须同时测比活力、Tm/半衰期、表达和可溶性。",
                    "如果身份、编号、底物或热稳定性基线缺失，本轮只输出证据缺口和可复核区域，不承诺具体突变表。",
                ],
                "output": "门控通过时输出候选位点、替换方向、双目标取舍、风险和实验优先级；门控未通过时只输出不可下单的证据审计和补证据路线。",
            }
        if goal == "thermostability":
            return {
                "title": "热稳定性：先加固非催化柔性区，再逐级验证组合",
                "logic": [
                    "先保护催化中心、金属结合位点和可能影响底物通道的关键残基。",
                    "优先从表面暴露、保守性较低、远离活性中心的 loop/局部疏松区域找候选。",
                    "候选替换按机制分组：降低 loop 构象熵、改善核心 packing、降低游离 Cys 氧化风险。",
                    "实验顺序是 P1 单点验证，P2 第二梯队单点，P3 仅组合已验证且机制互补的位点。",
                ],
                "output": "门控通过时输出候选突变位点、增稳逻辑、风险提示和实验优先级；门控未通过时只输出证据缺口和不可下单的预筛区域。",
            }
        if goal in {"ph_lowering", "ph_raising"}:
            direction = "降低" if goal == "ph_lowering" else "提高"
            return {
                "title": f"pH 改造：围绕表面电荷/pKa 调整，优先保持催化效率",
                "logic": [
                    f"目标是{direction}最适或耐受 pH，不是简单按分数挑位点。",
                    "优先筛选表面暴露、远离催化核心的电荷残基，并保留同一位点的多个替换方向形成梯度。",
                    "活性中心和底物结合位点作为保护约束，任何 pH 改善都要同时比较原始条件活性。",
                    "实验顺序是表面电荷单点梯度、不同机制单点、最后再做组合。",
                ],
                "output": "门控通过时输出候选位点、具体替换方向、pH 改造逻辑、活性保持风险和实验优先级；门控未通过时只输出证据缺口。",
            }
        if goal in {"activity", "specificity"}:
            target = "比活力/催化效率" if goal == "activity" else "底物特异性"
            return {
                "title": f"{target}：保护催化核心，优先调节口袋边缘和二壳层",
                "logic": [
                    f"先确认催化残基、底物结合约束和结构编号，再围绕{target}拆解可调区域。",
                    "候选优先来自口袋入口、通道和二壳层，而不是直接改造催化核心。",
                    "同时评估活性收益、底物谱、表达和稳定性风险，避免只输出单一活性分数。",
                    "实验顺序是单点方向验证、机制互补单点、通过上位性检查后再组合。",
                ],
                "output": "门控通过时输出候选位点、具体替换方向、催化/底物作用逻辑、风险和实验优先级；门控未通过时不生成突变清单。",
            }
        return {
            "title": "通用改造：先建立酶画像，再按目标筛选可解释候选",
            "logic": [
                "先核验序列、结构、功能和编号，区分已知事实、计算推断和未知项。",
                "保护催化、金属结合、二硫键和其他功能核心，再按暴露度、保守性和结构距离筛选。",
                "每个候选都要绑定具体突变逻辑、预期影响、风险和实验优先级。",
            ],
            "output": "门控通过时才输出可进入实验设计的候选位点和突变方向；门控未通过时只输出对象审计和补证据路线。",
        }

    @classmethod
    def _build_plan_confirmation_reply(
        cls,
        task: str,
        plan: list[PlanStep],
        research_notes: str = "",
        *,
        revised: bool = False,
        pdb_preflight: dict[str, Any] | None = None,
    ) -> str:
        """Build a user-visible strategy checkpoint before tools execute."""
        if len(plan) == 1 and plan[0].tool_name == "external_connectivity_check":
            return (
                "平台已配置只读实时联网探测，将现场访问 UniProt、NCBI 和 InterPro 官方接口。\n\n"
                "点“确认执行”后开始检测；当前尚未执行，因此这里不提前声称已联网。"
            )
        heading = "## 修改后的分析策略" if revised else "## 分析策略确认"
        lines = [heading, ""]
        lines.append("我已按平台人工分析流程 v1 生成本次策略，当前还没有执行任何分析工具。")
        lines.append("")
        lines.append("### 任务理解")
        lines.append(f"- 用户目标：{cls._display_task_summary(task)}")
        if research_notes:
            compact_research = " ".join(research_notes.split())[:500]
            if compact_research:
                lines.append(f"- 初步背景：{compact_research}")
        lines.append("")
        lines.append("### 输入证据审计")
        for item in cls._build_input_evidence_audit_lines(task, pdb_preflight):
            lines.append(item)
        lines.append("")
        lines.append("### 目标拆解")
        for item in cls._build_objective_decomposition_lines(task):
            lines.append(item)
        lines.append("")
        strategy = cls._build_strategy_checkpoint(task)
        lines.append("### 改造策略（先确认方向，再执行分析）")
        lines.append(f"**{strategy['title']}**")
        lines.append("")
        lines.append("#### 本轮定制化依据")
        for item in cls._format_pdb_preflight_summary(pdb_preflight):
            lines.append(f"- {item}")
        for item in cls._build_customization_lines(task):
            lines.append(f"- {item}")
        lines.append("")
        lines.append("#### 策略逻辑")
        for item in strategy["logic"]:
            lines.append(f"- {item}")
        lines.append(f"- **候选输出边界：** {strategy['output']}")
        lines.append("")
        lines.append("### 执行流程")
        if not plan:
            lines.append("- 当前输入不足，暂未生成可执行工具流程。")
        else:
            for step in plan:
                lines.append(
                    f"{step.id}. `{step.tool_name}`：{step.description}；参数：`{cls._format_plan_params(step.params)}`"
                )
        if any(step.tool_name == "rosetta_ddg" for step in plan):
            lines.append("")
            lines.append("### Rosetta ΔΔG 判读规则")
            lines.append("- 约定：ΔΔG 为负值表示突变体预测更稳定；正值表示预测更不稳定。")
            lines.append("- 默认阈值：<= -2.0 强稳定；(-2.0, -1.0] 稳定；(-1.0, 1.0] 中性/不确定；(1.0, 2.0] 不稳定；> 2.0 强不稳定。")
            lines.append("- 该工具必须核实残基编号、链 ID、PDB/UniProt/用户序列映射后才能用于实验排单。")
        lines.append("")
        lines.append("### 确认方式")
        plan_signature = cls._plan_signature(plan)
        lines.append(f"- 策略指纹：`{plan_signature}`。")
        lines.append("- 点“确认执行”后，只按上面列出的工具和参数执行；不会临时换成另一套通用流程。")
        lines.append("- 如果要调整策略，请在输入框写修改要求，我会重新出策略，不会直接执行。")
        lines.append("")
        lines.append("状态：等待确认，未执行工具。")
        return "\n".join(lines)

    async def stream_chat(
        self, user_message: str, history: list[dict],
        model_id: str | None = None,
        analysis_depth: str = "standard",
        agent_control: str | None = None,
        confirmed_plan: list[dict] | None = None,
        strategy_signature: str | None = None,
        task_fingerprint: str | None = None,
        current_user: dict | None = None,
        audit_session: Any | None = None,
        conversation_id: int | None = None,
        project_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Main entry: route → research → plan → execute → synthesize."""
        self._snapshot = ChatSnapshot(stage="router")
        # Shadow-only v2 governance: derive a property route for observability
        # without altering the legacy intent router or dispatch plan.
        self._snapshot.workflow_shadow = PropertyWorkflowRouter.route(user_message)
        analysis_depth = (analysis_depth or "standard").strip().lower()
        if analysis_depth not in {"fast", "standard", "deep"}:
            analysis_depth = "standard"
        control = (agent_control or "plan_only").strip().lower()
        if control not in {"plan_only", "execute_confirmed", "revise_plan"}:
            control = "plan_only"
        effective_message = self._normalize_confirmed_task(user_message, control)
        protein_context = self._build_context_for_message(effective_message, history)
        self._snapshot.task_contract = evaluate_enzyme_workflow_runtime(
            effective_message,
            history=history,
            session_id=conversation_id,
        )
        if control in {"plan_only", "revise_plan"}:
            memory_planning_context = await self._load_recent_strategy_planning_context(
                current_user=current_user,
                audit_session=audit_session,
                conversation_id=conversation_id,
                project_id=project_id,
                message=effective_message,
            )
            if memory_planning_context:
                protein_context = "\n".join(
                    part for part in (protein_context, memory_planning_context) if part
                )
        confirmed_checkpoint_plan: list[PlanStep] | None = None

        # --- Stage 1: ROUTER ---
        yield self._emit_state()
        runtime_contract = self._snapshot.task_contract
        if control != "execute_confirmed" and runtime_contract["route_reason"] == "conceptual_question":
            self._snapshot.stage = "done"
            yield self._emit_state()
            reply = await self._chat_reply(effective_message, history, model_id)
            for chunk in self._iter_text_stream_chunks(reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return
        if control != "execute_confirmed" and runtime_contract["intake_status"] == "WAITING_FOR_USER_INPUT":
            self._snapshot.stage = "done"
            self._snapshot.waiting_for = "clarification"
            yield self._emit_state()
            reply = self._build_missing_input_reply(effective_message, "enzyme_property_intake")
            for chunk in self._iter_text_stream_chunks(reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return
        if control != "execute_confirmed" and runtime_contract["intent"] == "FOLLOW_UP":
            self._snapshot.stage = "done"
            yield self._emit_state()
            reply = await self._chat_reply(
                f"{effective_message}\n\n[续问约束] 这是已有酶改造任务的续问。只基于历史回答；不要重新规划或调用工具。",
                history,
                model_id,
            )
            for chunk in self._iter_text_stream_chunks(reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return
        if self._is_unbound_strategy_confirmation(effective_message, history, control):
            self._snapshot.stage = "done"
            self._snapshot.waiting_for = "plan_confirmation"
            yield self._emit_state()
            reply = self._build_checkpoint_missing_reply(
                "user confirmation was detected, but no structured strategy checkpoint was attached"
            )
            for chunk in self._iter_text_stream_chunks(reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return
        quality_review_records: list[dict[str, Any]] = []
        if control == "plan_only" and self._message_contains_report_quality_feedback(effective_message):
            quality_review_records = await self._load_recent_strategy_memory_records(
                current_user=current_user,
                audit_session=audit_session,
                conversation_id=conversation_id,
                project_id=project_id,
                log_label="report quality review",
            )
        if control == "plan_only" and (
            self._is_report_quality_review_followup(effective_message, protein_context, history)
            or quality_review_records
        ):
            self._snapshot.stage = "done"
            self._snapshot.research_notes = "report_quality_review_followup"
            yield self._emit_state()
            reply = self._build_report_quality_review_reply(
                effective_message,
                history,
                protein_context,
                strategy_records=quality_review_records,
            )
            for chunk in self._iter_text_stream_chunks(reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return
        if control == "plan_only" and self._is_p0_followup_review(effective_message, protein_context, history):
            self._snapshot.stage = "done"
            self._snapshot.research_notes = "p0_followup_review"
            yield self._emit_state()
            reply = self._build_p0_followup_review_reply(effective_message, history, protein_context)
            for chunk in self._iter_text_stream_chunks(reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return
        if control == "plan_only" and self._is_same_problem_synthesis_followup(effective_message, protein_context):
            self._snapshot.stage = "done"
            self._snapshot.research_notes = "same_problem_synthesis_followup"
            yield self._emit_state()
            memory_context = await self._load_recent_strategy_memory_context(
                current_user=current_user,
                audit_session=audit_session,
                conversation_id=conversation_id,
                project_id=project_id,
            )
            memory_block = f"\n\n{memory_context}" if memory_context else ""
            followup_prompt = (
                f"{effective_message}\n\n"
                "[同一问题续问约束]\n"
                "这是基于上一轮同一蛋白/同一项目结果的解释或整理型追问。"
                "不要重新规划工具流程，不要声称新工具已执行；只基于对话历史、已展示结果和同项目策略记忆回答。"
                "状态为 awaiting_confirmation 的策略只能说仍待确认；状态为 executing/completed 的策略只能作为历史策略背景。"
                "不要把计算预测或项目级校准背景写成候选级湿实验验证。"
                f"{memory_block}"
            )
            reply = await self._chat_reply(followup_prompt, history, model_id)
            for chunk in self._iter_text_stream_chunks(reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return
        if control == "execute_confirmed":
            checkpoint_error = self._confirmed_checkpoint_error(
                confirmed_plan=confirmed_plan,
                strategy_signature=strategy_signature,
                task_fingerprint=task_fingerprint,
                effective_message=effective_message,
                protein_context=protein_context,
            )
            if checkpoint_error:
                self._snapshot.stage = "done"
                self._snapshot.waiting_for = "plan_confirmation"
                yield self._emit_state()
                reply = self._build_checkpoint_missing_reply(checkpoint_error)
                for chunk in self._iter_text_stream_chunks(reply):
                    yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
                yield json.dumps({"type": "done"})
                return
            confirmed_checkpoint_plan = self._plan_steps_from_payload(confirmed_plan)
            route = "confirmed_checkpoint"
            self._snapshot.research_notes = ""
            plan = confirmed_checkpoint_plan
            self._snapshot.stage = "plan"
        else:
            if self._task_requests_no_tools(f"{effective_message}\n{protein_context}".strip()):
                self._snapshot.stage = "done"
                yield self._emit_state()
                reply = self._build_extraction_only_reply(effective_message)
                for chunk in self._iter_text_stream_chunks(reply):
                    yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
                yield json.dumps({"type": "done"})
                return

            route = await self._route_intent(effective_message, protein_context, model_id)
            if self._is_connectivity_status_request(effective_message):
                route = "research"
            if self._is_governance_evidence_request(effective_message):
                route = "research"
            if self._wants_live_literature_search(effective_message):
                route = "research"
            self._snapshot.stage = route

            # --- General chat shortcut: no protein intent → direct LLM reply ---
            if route == "general":
                self._snapshot.stage = "done"
                yield self._emit_state()
                reply = await self._chat_reply(effective_message, history, model_id)
                for chunk in self._iter_text_stream_chunks(reply):
                    yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
                yield json.dumps({"type": "done"})
                return

            clarification = None
            if self._should_clarify_before_tools(effective_message, route, protein_context):
                clarification = self._build_missing_input_reply(effective_message, route)
            if clarification:
                self._snapshot.stage = "done"
                self._snapshot.waiting_for = "clarification"
                yield self._emit_state()
                for chunk in self._iter_text_stream_chunks(clarification):
                    yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
                yield json.dumps({"type": "done"})
                return

            # --- Stage 2+3: RESEARCH (PI) + PLAN (CB) — parallel ---
            yield self._emit_state()
            yield json.dumps({"type": "text", "content": "\n\n"}, ensure_ascii=False)
            if route in ("research", "design", "analyze") and not self._is_connectivity_status_request(effective_message):
                # Run research+plan concurrently — knowledge gathering is fire-and-forget
                # with a short timeout so it doesn't block the pipeline
                async def _fast_research():
                    try:
                        return await asyncio.wait_for(
                            self._research_pi(effective_message, history, protein_context, model_id, task_type=route),
                            timeout=15,  # cap research at 15s
                        )
                    except asyncio.TimeoutError:
                        logger.info("Research PI timed out after 15s, proceeding without")
                        return ""

                research_task = asyncio.create_task(_fast_research())
                plan_task = asyncio.create_task(
                    self._plan_cb(effective_message, "", history, model_id, protein_context, analysis_depth=analysis_depth)
                )
                research, plan = await asyncio.gather(research_task, plan_task)
                self._snapshot.research_notes = research
                yield self._emit_state()
            else:
                self._snapshot.research_notes = ""
                plan = await self._plan_cb(effective_message, "", history, model_id, protein_context, analysis_depth=analysis_depth)

            plan = await self._hydrate_uploaded_pdb_sequence_for_plan(
                plan,
                f"{effective_message}\n{protein_context}".strip(),
            )

        # Scientific preflight: reject plans that cannot even satisfy their
        # declared input/gate prerequisites before confirmation or dispatch.
        # Foundation steps included in the same plan may satisfy later gates;
        # terminal evidence is still checked again during ordered execution.
        plan_contract = validate_tool_plan(
            [
                {"tool_name": step.tool_name, "params": step.params}
                for step in plan
            ],
            evidence={
                "has_sequence": bool(
                    self._extract_sequence(f"{effective_message}\n{protein_context}")
                    or any(isinstance(step.params, dict) and step.params.get("sequence") for step in plan)
                ),
                "has_pdb": bool(
                    self._extract_attached_object_name(f"{effective_message}\n{protein_context}")
                    or any(
                        isinstance(step.params, dict)
                        and any(step.params.get(key) for key in ("pdb_data", "pdb_structure", "pdb_object_name", "pdb_path"))
                        for step in plan
                    )
                ),
            },
            # Plan-only confirmation may include future candidate steps. Their
            # identity/objective gates are enforced again at ordered execution;
            # hard sequence/structure input requirements remain fail-closed here.
            enforce_candidate_gates=False,
            enforce_dependency_order=confirmed_checkpoint_plan is not None,
        )
        preflight_blocked: dict[int, dict[str, Any]] = {}
        if not plan_contract["allowed"] and confirmed_checkpoint_plan is not None:
            dependency_violations = [
                item for item in plan_contract["violations"] if item.get("code") == "dependency_required"
            ]
            other_violations = [
                item for item in plan_contract["violations"] if item.get("code") != "dependency_required"
            ]
            if dependency_violations and not other_violations:
                for violation in dependency_violations:
                    index = int(violation.get("index", -1))
                    if 0 <= index < len(plan):
                        preflight_blocked[index] = {
                            "status": "blocked",
                            "code": "DEPENDENCY_REQUIRED",
                            "dependency": violation.get("dependency"),
                            "reason": (
                                f"Step requires terminal evidence for {violation.get('dependency')}; "
                                "the prerequisite was not completed in this plan."
                            ),
                        }
                plan_contract["allowed"] = True

        if not plan_contract["allowed"]:
            self._snapshot.stage = "done"
            self._snapshot.waiting_for = "clarification"
            self._snapshot.next_action = None
            self._snapshot.raw_plan_payload = []
            self._snapshot.plan = []
            yield self._emit_state()
            reasons = ", ".join(sorted({item["code"] for item in plan_contract["violations"]}))
            blocked_reply = (
                "当前工具组合未通过科学前置检查，未执行任何工具。"
                f" 阻断原因：{reasons}。请补充所需序列/结构输入后再确认。"
            )
            for chunk in self._iter_text_stream_chunks(blocked_reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return

        raw_plan_payload = [{
            "id": s.id, "tool_name": s.tool_name,
            "description": s.description, "params": s.params,
            "status": s.status,
        } for s in plan]
        declared_policy = None
        if runtime_contract.get("workflow_id"):
            declared_policy = WorkflowPolicyValidator.validate_declared_tools(
                runtime_contract["workflow_id"], [step.tool_name for step in plan]
            )
            self._snapshot.task_contract["declared_policy"] = declared_policy
            if declared_policy["status"] == "NEEDS_REVIEW":
                self._snapshot.task_contract["final_status"] = "NEEDS_REVIEW"
                self._snapshot.stage = "done"
                self._snapshot.waiting_for = "clarification"
                yield self._emit_state()
                reason = ", ".join(declared_policy["forbidden_tool_calls"] + declared_policy["unknown_tool_calls"])
                reply = f"当前计划包含未获准工具（{reason}），已拦截执行。请调整目标或请求人工复核。"
                for chunk in self._iter_text_stream_chunks(reply):
                    yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
                yield json.dumps({"type": "done"})
                return
        if confirmed_checkpoint_plan is None:
            self._snapshot.workflow_shadow = compare_legacy_plan(
                effective_message,
                [step.tool_name for step in plan],
            )
            if current_user and audit_session:
                await persist_shadow_audit(
                    audit_session,
                    user_id=int(current_user["id"]),
                    conversation_id=conversation_id,
                    project_id=project_id,
                    message=effective_message,
                    shadow=self._snapshot.workflow_shadow,
                )
        self._snapshot.raw_plan_payload = raw_plan_payload
        self._snapshot.plan = self._sanitize_plan_for_display(raw_plan_payload)
        self._snapshot.strategy_signature = self._plan_signature(plan)
        self._snapshot.task_fingerprint = task_fingerprint or self._task_fingerprint(effective_message, protein_context)
        self._snapshot.artifacts = {}
        if confirmed_checkpoint_plan is None:
            self._snapshot.waiting_for = "plan_confirmation"
            self._snapshot.next_action = "confirm_execute"
        else:
            self._snapshot.waiting_for = None
            self._snapshot.next_action = None
        yield self._emit_state()

        # If no plan steps were generated, use research notes as the reply
        if not plan:
            self._snapshot.stage = "done"
            yield self._emit_state()
            reply = self._snapshot.research_notes or self._build_missing_input_reply(effective_message, route)
            for chunk in self._iter_text_stream_chunks(reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return

        if confirmed_checkpoint_plan is None:
            self._snapshot.stage = "done"
            self._snapshot.waiting_for = "plan_confirmation"
            yield self._emit_state()
            pdb_preflight = None
            preflight_task = f"{effective_message}\n{protein_context}".strip()
            if self._extract_attached_object_name(preflight_task):
                pdb_preflight = await self._build_pdb_preflight_summary(preflight_task)
            reply = self._build_plan_confirmation_reply(
                preflight_task,
                plan,
                self._snapshot.research_notes,
                revised=control == "revise_plan",
                pdb_preflight=pdb_preflight,
            )
            for chunk in self._iter_text_stream_chunks(reply):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return

        self._snapshot.waiting_for = None
        self._snapshot.next_action = None

        # --- Stage 4: EXECUTE (MLS) — parallel where possible ---
        self._snapshot.stage = "execute"
        yield self._emit_state()

        # Per-step timeout cap — prevents slow external APIs from blocking the pipeline
        PER_STEP_TIMEOUT = 300  # seconds (enzyme_function needs ~2min, esmfold up to 5min)

        def _resolve_step_timeout(tool_name: str) -> int:
            tool_def = ToolRegistry.get_tool(tool_name)
            if tool_def and tool_def.timeout_seconds:
                return max(PER_STEP_TIMEOUT, int(tool_def.timeout_seconds))
            return PER_STEP_TIMEOUT

        # --- Execute plan: design pipelines are dependency-ordered; analysis can stay parallel ---
        # Keep planned steps pending until execution actually starts. Marking
        # every step running up front makes the UI look stuck during slow calls.
        for i, step in enumerate(plan):
            step = await self._attach_wet_lab_calibration_context(
                step,
                current_user=current_user,
                audit_session=audit_session,
                project_id=project_id,
            )
            if self._should_submit_interactive_async_step(step):
                step = self._normalize_interactive_async_params(step)
            plan[i] = step
            if confirmed_checkpoint_plan is None:
                self._snapshot.plan[i]["description"] = step.description
                self._snapshot.plan[i]["params"] = step.params
            self._snapshot.plan[i]["status"] = step.status
        yield self._emit_state()

        # Semaphore: max 2 tools concurrently (safe with 8GB VM memory)
        _tool_semaphore = asyncio.Semaphore(2)

        async def _run_step(i: int, step: PlanStep) -> tuple[int, PlanStep]:
            """Execute a single tool step with caching and timeout."""
            if i in preflight_blocked:
                step.status = "failed"
                step.result = preflight_blocked[i]
                step.error = str(preflight_blocked[i].get("reason") or "Scientific dependency prerequisite is incomplete")
                step.duration = 0.0
                return i, step
            cache_key = self._cache_key(step.tool_name, step.params)
            cacheable = step.tool_name != "external_connectivity_check"
            cached = self._cache_get(cache_key) if cacheable else None
            if cached is not None:
                step.status = "completed"
                step.result = cached
                step.duration = 0.0
                logger.info("Tool cache hit: %s", step.tool_name)
                return i, step

            async with _tool_semaphore:
                start = time.time()
                step_timeout = _resolve_step_timeout(step.tool_name)
                try:
                    step.status = "running"
                    self._snapshot.plan[i]["status"] = "running"
                    if self._should_submit_interactive_async_step(step):
                        result = await self._submit_interactive_async_step(
                            step,
                            current_user=current_user,
                            audit_session=audit_session,
                        )
                        step.status = "submitted"
                    else:
                        result = await asyncio.wait_for(
                            ToolRegistry.execute(step.tool_name, step.params),
                            timeout=step_timeout,
                        )
                        step.status = "completed"
                    step.result = result
                    step.duration = round(time.time() - start, 2)
                    if step.status == "completed" and cacheable:
                        self._cache_put(cache_key, result)
                except asyncio.TimeoutError:
                    step.status = "failed"
                    step.error = f"Step timed out after {step_timeout}s"
                    step.duration = round(time.time() - start, 2)
                except Exception as e:
                    step.status = "failed"
                    step.error = str(e)
                    step.duration = round(time.time() - start, 2)
                    # Retry once on transient errors
                    if self._should_retry(step):
                        try:
                            result = await asyncio.wait_for(
                                ToolRegistry.execute(step.tool_name, step.params),
                                timeout=step_timeout,
                            )
                            step.status = "completed"
                            step.result = result
                            step.error = None
                            if cacheable:
                                self._cache_put(cache_key, result)
                        except Exception:
                            logger.exception("Retry failed for tool %s", step.tool_name)
            return i, step

        is_ordered_pipeline = self._requires_ordered_execution(plan)
        results: list[Any] = []
        completed_steps: list[PlanStep] = []
        structure_gate_failed = False
        structure_gate_error = ""
        if is_ordered_pipeline:
            for i, step in enumerate(plan):
                if i in preflight_blocked:
                    step.status = "completed"
                    step.result = preflight_blocked[i]
                    step.duration = 0.0
                    self._snapshot.plan[i]["status"] = "completed"
                    completed_steps.append(step)
                    results.append((i, step))
                    continue
                step = self._bridge_step_params(step, completed_steps)
                step = await self._attach_wet_lab_calibration_context(
                    step,
                    current_user=current_user,
                    audit_session=audit_session,
                    project_id=project_id,
                )
                plan[i] = step
                if confirmed_checkpoint_plan is None:
                    self._snapshot.plan[i]["params"] = step.params
                if step.tool_name in _IDENTITY_GATED_CANDIDATE_TOOLS and not self._identity_gate_passed(completed_steps):
                    step.status = "completed"
                    step.result = {
                        "status": "blocked",
                        "code": "IDENTITY_OR_NUMBERING_NOT_CONFIRMED",
                        "reason": (
                            "Candidate-generation tool was not run because enzyme family identity "
                            "or residue numbering was not confirmed by enzyme_identity_profile."
                        ),
                    }
                    step.duration = 0.0
                    self._snapshot.plan[i]["status"] = "completed"
                    completed_steps.append(step)
                    results.append((i, step))
                    continue
                if step.tool_name in _OBJECTIVE_GATED_CANDIDATE_TOOLS and not self._objective_gate_passed(completed_steps):
                    step.status = "completed"
                    step.result = {
                        "status": "blocked",
                        "code": "OBJECTIVE_MODULE_NOT_READY",
                        "reason": (
                            "Candidate-generation tool was not run because the objective-specific "
                            "module did not have the required assay/evidence context."
                        ),
                    }
                    step.duration = 0.0
                    self._snapshot.plan[i]["status"] = "completed"
                    completed_steps.append(step)
                    results.append((i, step))
                    continue
                if structure_gate_failed and self._is_structure_dependent_step(step.tool_name):
                    step.status = "failed"
                    step.error = (
                        "Skipped: uploaded/predicted structure gate did not pass; "
                        f"{structure_gate_error or 'structure evidence is unavailable or unconfirmed'}"
                    )
                    step.duration = 0.0
                    self._snapshot.plan[i]["status"] = "failed"
                    completed_steps.append(step)
                    results.append((i, step))
                    continue
                res = await _run_step(i, step)
                if not isinstance(res, Exception):
                    _, resolved_step = res
                    completed_steps.append(resolved_step)
                    if self._is_structure_gate_step(resolved_step.tool_name) and not self._structure_gate_passed(resolved_step):
                        structure_gate_failed = True
                        structure_gate_error = self._sanitize_uploaded_metadata_text(
                            resolved_step.error or self._compact_result(
                                resolved_step.tool_name,
                                resolved_step.result,
                            ),
                            limit=400,
                        )
                results.append(res)
        else:
            results = await asyncio.gather(
                *[_run_step(i, step) for i, step in enumerate(plan)],
                return_exceptions=True,
            )

        # Collect results in order and build tool_messages
        tool_messages = []
        for res in results:
            if isinstance(res, Exception):
                logger.error("Parallel step exception: %s", res)
                continue
            i, step = res
            self._snapshot.plan[i]["status"] = step.status
            self._snapshot.current_step = i + 1
            result_payload_dict = step.result if isinstance(step.result, dict) else self._safe_parse_json(str(step.result or ""))
            evidence_source = (
                result_payload_dict.get("evidence_source")
                if isinstance(result_payload_dict, dict) and isinstance(result_payload_dict.get("evidence_source"), dict)
                else None
            )
            result_preview = self._sanitize_uploaded_metadata_text(
                self._compact_result(step.tool_name, step.result) if step.result else step.error,
                limit=2000,
            )
            raw_result = self._sanitize_uploaded_metadata_text(
                self._raw_tool_result(step.result) if step.result else (step.error or ""),
                limit=120000,
            )
            self._snapshot.step_results.append({
                "step": i + 1, "tool": step.tool_name,
                "status": step.status,
                "result_preview": result_preview,
                "raw_result": raw_result,
                "duration": step.duration,
                "evidence_source": evidence_source,
            })
            self._snapshot.task_contract.setdefault("trace", []).append({
                "step": i + 1,
                "tool_id": step.tool_name,
                "status": step.status,
                "duration": step.duration,
                "input": {"keys": sorted(step.params) if isinstance(step.params, dict) else []},
                "output": {"status": step.status, "has_result": step.result is not None},
            })
            if step.tool_name == "enzyme_identity_profile" and isinstance(step.result, dict):
                sequence = str((step.params or {}).get("sequence") or (step.params or {}).get("query_sequence") or "")
                if sequence:
                    consistency = check_identity_consistency(
                        sequence,
                        step.result,
                        model_version=str(step.result.get("model_version") or "") or None,
                        evidence_version=str(step.result.get("evidence_version") or "") or None,
                    )
                    self._snapshot.task_contract["identity_consistency"] = consistency
                    await self._persist_identity_consistency(
                        sequence,
                        step.result,
                        consistency,
                        current_user=current_user,
                        audit_session=audit_session,
                    )
                    if consistency["status"] == "NEEDS_REVIEW":
                        self._snapshot.task_contract["final_status"] = "NEEDS_REVIEW"
            if step.status in {"failed", "blocked"}:
                self._snapshot.task_contract.setdefault("fallback_trace", []).append({
                    "primary_tool": step.tool_name,
                    "selected_tool": None,
                    "fallback_level": "DEGRADED",
                    "fallback_reason": self._sanitize_uploaded_metadata_text(
                        step.error or self._compact_result(step.tool_name, step.result) or "tool did not produce usable evidence",
                        limit=500,
                    ),
                })
            if step.status == "submitted":
                self._snapshot.task_contract.setdefault("fallback_trace", [])
            self._append_artifact_handoff(step_index=i, step=step)
            result_payload = self._sanitize_uploaded_metadata_text(
                self._compact_result(step.tool_name, step.result) if step.result else step.error
            )
            tool_messages.append({
                "role": "tool",
                "tool_name": step.tool_name,
                "result": result_payload,
                "status": step.status,
            })

        yield self._emit_state()

        # --- Stage 4.5: SC REVIEW (multi-round iterative refinement) ---
        # MLEvolve-inspired: SC reviews results, may trigger supplementary tools,
        # records experience after each round. Up to MAX_REVIEW_ROUNDS iterations.
        # Smart review: skip for simple queries (≤3 tools), limit to 1 for moderate, 2 for complex
        num_tools = len(plan)
        if confirmed_checkpoint_plan is not None:
            MAX_REVIEW_ROUNDS = 0
        elif num_tools <= 3:
            MAX_REVIEW_ROUNDS = 0  # skip review entirely
        elif num_tools <= 6:
            MAX_REVIEW_ROUNDS = 1
        else:
            MAX_REVIEW_ROUNDS = 2
        execution_start = time.time()
        review_round = 0

        for review_round in range(1, MAX_REVIEW_ROUNDS + 1):
            self._snapshot.stage = "review"
            yield self._emit_state()

            review_result = await self._review_results_sc(
                effective_message, tool_messages, self._snapshot.research_notes, model_id
            )

            # If SC is satisfied, break out of the loop
            if not review_result.get("needs_supplement"):
                break

            # If this is the last round, don't execute more supplements
            if review_round >= MAX_REVIEW_ROUNDS:
                logger.info("Max review rounds (%d) reached", MAX_REVIEW_ROUNDS)
                break

            # SC found gaps — execute supplementary tools
            has_sequence = bool(self._extract_sequence(effective_message))
            has_pdb = any(
                "pdb" in str(r.get("result", "")).lower() and "ATOM" in str(r.get("result", ""))
                for r in tool_messages
            )

            for extra in review_result.get("supplementary_steps", []):
                tool_name = extra["tool_name"]
                if tool_name in self._extract_forbidden_tools(f"{effective_message}\n{protein_context}".strip()):
                    tool_messages.append({
                        "role": "tool",
                        "tool_name": tool_name,
                        "result": f"Skipped: user explicitly forbade {tool_name}.",
                        "status": "skipped",
                    })
                    continue

                # Skip tools that need a sequence when none is available
                if not has_sequence and tool_name in _SEQUENCE_REQUIRED_TOOLS:
                    tool_messages.append({
                        "role": "tool",
                        "tool_name": tool_name,
                        "result": f"Skipped: no protein sequence available. Provide a sequence to use {tool_name}.",
                        "status": "skipped",
                    })
                    continue

                # Skip tools that need a PDB structure when none is available
                if not has_pdb and tool_name in _PDB_REQUIRED_TOOLS:
                    tool_messages.append({
                        "role": "tool",
                        "tool_name": tool_name,
                        "result": f"Skipped: no PDB structure available. Upload a PDB file or run structure prediction first.",
                        "status": "skipped",
                    })
                    continue
                extra_step = PlanStep(
                    id=len(plan) + 1,
                    tool_name=extra["tool_name"],
                    description=extra.get("description", f"Supplementary: {extra['tool_name']}"),
                    params=extra.get("params", {}),
                    status="running",
                )
                if self._should_submit_interactive_async_step(extra_step):
                    extra_step = self._normalize_interactive_async_params(extra_step)
                extra_step = await self._attach_wet_lab_calibration_context(
                    extra_step,
                    current_user=current_user,
                    audit_session=audit_session,
                    project_id=project_id,
                )
                plan.append(extra_step)
                self._snapshot.plan.append({
                    "id": extra_step.id, "tool_name": extra_step.tool_name,
                    "description": extra_step.description, "params": extra_step.params,
                    "status": "running",
                })
                self._snapshot.current_step = extra_step.id
                yield self._emit_state()

                # Validate params: check required parameters exist for the tool
                tool_def = ToolRegistry.get_tool(extra_step.tool_name)
                if tool_def and tool_def.parameters:
                    required = tool_def.parameters.get("required", [])
                    missing = [p for p in required if p not in extra_step.params or not extra_step.params[p]]
                    if missing:
                        reason = f"missing required parameters: {missing}"
                        tool_messages.append({
                            "role": "tool",
                            "tool_name": extra_step.tool_name,
                            "result": f"Skipped: {reason}",
                            "status": "skipped",
                        })
                        self._snapshot.task_contract.setdefault("trace", []).append({
                            "step": extra_step.id, "tool_id": extra_step.tool_name,
                            "status": "skipped", "duration": 0.0,
                            "input": {"keys": sorted(extra_step.params)},
                            "output": {"status": "skipped", "has_result": False},
                        })
                        self._snapshot.task_contract.setdefault("fallback_trace", []).append({
                            "primary_tool": extra_step.tool_name, "selected_tool": None,
                            "fallback_level": "DEGRADED", "fallback_reason": reason,
                        })
                        continue

                start = time.time()
                step_timeout = _resolve_step_timeout(extra_step.tool_name)
                try:
                    if self._should_submit_interactive_async_step(extra_step):
                        result = await self._submit_interactive_async_step(
                            extra_step,
                            current_user=current_user,
                            audit_session=audit_session,
                        )
                        extra_step.status = "submitted"
                    else:
                        result = await asyncio.wait_for(
                            ToolRegistry.execute(extra_step.tool_name, extra_step.params),
                            timeout=step_timeout,
                        )
                        extra_step.status = "completed"
                    extra_step.result = result
                    extra_step.duration = round(time.time() - start, 2)
                    idx = extra_step.id - 1
                    self._snapshot.plan[idx]["status"] = extra_step.status
                    self._snapshot.step_results.append({
                        "step": extra_step.id, "tool": extra_step.tool_name,
                        "status": extra_step.status,
                        "result_preview": self._sanitize_uploaded_metadata_text(
                            self._compact_result(extra_step.tool_name, result),
                            limit=2000,
                        ),
                        "raw_result": self._sanitize_uploaded_metadata_text(
                            self._raw_tool_result(result),
                            limit=120000,
                        ),
                        "duration": extra_step.duration,
                    })
                    self._snapshot.task_contract.setdefault("trace", []).append({
                        "step": extra_step.id, "tool_id": extra_step.tool_name,
                        "status": extra_step.status, "duration": extra_step.duration,
                        "input": {"keys": sorted(extra_step.params)},
                        "output": {"status": extra_step.status, "has_result": extra_step.result is not None},
                    })
                    if extra_step.status in {"failed", "blocked"}:
                        self._snapshot.task_contract.setdefault("fallback_trace", []).append({
                            "primary_tool": extra_step.tool_name, "selected_tool": None,
                            "fallback_level": "DEGRADED",
                            "fallback_reason": self._sanitize_uploaded_metadata_text(
                                extra_step.error or "supplementary tool did not produce usable evidence", limit=500
                            ),
                        })
                    self._append_artifact_handoff(step_index=idx, step=extra_step)
                    tool_messages.append({
                        "role": "tool",
                        "tool_name": extra_step.tool_name,
                        "result": self._sanitize_uploaded_metadata_text(
                            self._compact_result(extra_step.tool_name, result)
                        ),
                        "status": extra_step.status,
                    })
                except asyncio.TimeoutError:
                    extra_step.status = "failed"
                    extra_step.error = f"Step timed out after {step_timeout}s"
                    extra_step.duration = round(time.time() - start, 2)
                    idx = extra_step.id - 1
                    self._snapshot.plan[idx]["status"] = "failed"
                    self._snapshot.task_contract.setdefault("trace", []).append({
                        "step": extra_step.id, "tool_id": extra_step.tool_name,
                        "status": "failed", "duration": extra_step.duration,
                        "input": {"keys": sorted(extra_step.params)},
                        "output": {"status": "failed", "has_result": False},
                    })
                    self._snapshot.task_contract.setdefault("fallback_trace", []).append({
                        "primary_tool": extra_step.tool_name, "selected_tool": None,
                        "fallback_level": "DEGRADED", "fallback_reason": extra_step.error,
                    })
                    tool_messages.append({
                        "role": "tool",
                        "tool_name": extra_step.tool_name,
                        "result": extra_step.error,
                        "status": "failed",
                    })
                except Exception as e:
                    extra_step.status = "failed"
                    extra_step.error = str(e)
                    idx = extra_step.id - 1
                    self._snapshot.plan[idx]["status"] = "failed"
                    self._snapshot.task_contract.setdefault("trace", []).append({
                        "step": extra_step.id, "tool_id": extra_step.tool_name,
                        "status": "failed", "duration": extra_step.duration,
                        "input": {"keys": sorted(extra_step.params)},
                        "output": {"status": "failed", "has_result": False},
                    })
                    self._snapshot.task_contract.setdefault("fallback_trace", []).append({
                        "primary_tool": extra_step.tool_name, "selected_tool": None,
                        "fallback_level": "DEGRADED", "fallback_reason": extra_step.error,
                    })
                    tool_messages.append({
                        "role": "tool",
                        "tool_name": extra_step.tool_name,
                        "result": str(e)[:500],
                        "status": "failed",
                    })

            yield self._emit_state()

        # Record experience after execution (before synthesis)
        total_duration = time.time() - execution_start
        await self._record_experience(
            effective_message, route, plan, tool_messages,
            self._snapshot.research_notes, total_duration, round_number=review_round,
        )

        # --- Stage 5: SYNTHESIZE (SC) ---
        self._snapshot.stage = "synthesize"
        yield self._emit_state()
        final_report = await self._synthesize_sc(
            effective_message, tool_messages, self._snapshot.research_notes, history, model_id
        )
        fallback_trace = self._snapshot.task_contract.get("fallback_trace") or []
        if fallback_trace:
            notices = []
            for item in fallback_trace[:6]:
                tool_name = str(item.get("primary_tool") or "工具")
                reason = str(item.get("fallback_reason") or "未产生可用证据")
                notices.append(f"- {tool_name} 未成功完成，已降级为可用证据范围内的分析：{reason}")
            final_report = "### 执行降级提示\n\n" + "\n".join(notices) + "\n\n" + str(final_report)
        self._snapshot.final_report = final_report
        completion = assess_enzyme_report_completion(final_report)
        self._snapshot.task_contract["final_status"] = completion["final_status"]
        if completion["violations"]:
            self._snapshot.task_contract["report_quality_violations"] = [
                {"code": item.code, "message": item.message}
                for item in completion["violations"]
            ]
        self._snapshot.stage = "done"
        yield self._emit_state()

        # Stream final report as text tokens
        for chunk in self._iter_text_stream_chunks(final_report):
            yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)

        yield json.dumps({"type": "done"})

    async def _record_experience(
        self, user_message: str, task_type: str, plan: list, tool_messages: list[dict],
        research_notes: str, total_duration: float, round_number: int = 1,
    ) -> None:
        """Record this execution as an experience for future reference."""
        try:
            store, ExperienceRecord = _get_experience_store()
            sequence = self._extract_sequence(user_message) or ""
            protein_name = self._extract_protein_name(user_message)

            # Determine task type from route
            pipeline = [step.tool_name for step in plan]
            completed = sum(1 for m in tool_messages if m["status"] == "completed")
            total = len(tool_messages) if tool_messages else 1

            record = ExperienceRecord(
                task_type=task_type,
                protein_family=protein_name or "unknown",
                sequence_hash=ExperienceRecord.hash_sequence(sequence),
                pipeline=pipeline,
                pipeline_hash=ExperienceRecord.hash_pipeline(pipeline),
                step_results={m["tool_name"]: m["status"] for m in tool_messages},
                success_rate=completed / total,
                total_duration=total_duration,
                user_message_short=user_message[:100],
                research_notes_short=research_notes[:200],
                round_number=round_number,
            )
            await store.record(record)
        except Exception:
            logger.debug("Failed to record experience")

    async def _get_experience_hints(self, user_message: str, task_type: str) -> str:
        """Query past experiences for planning hints."""
        try:
            store, _ = _get_experience_store()
            protein_name = self._extract_protein_name(user_message)
            sequence = self._extract_sequence(user_message) or ""

            experiences = await store.search_similar(
                task_type=task_type,
                protein_family=protein_name or "",
                sequence=sequence,
                top_k=3,
            )
            if not experiences:
                return ""

            lines = ["Past execution experiences for similar tasks:"]
            for exp in experiences:
                status = "✓" if exp.success_rate >= 0.8 else "⚠"
                lines.append(
                    f"- {status} Pipeline [{', '.join(exp.pipeline[:5])}...] "
                    f"({exp.success_rate:.0%} success, {exp.total_duration:.0f}s)"
                )
            best = await store.get_best_pipeline(task_type, protein_name or "")
            if best:
                lines.append(f"Recommended pipeline: {' → '.join(best)}")
            return "\n".join(lines)
        except Exception:
            logger.debug("Experience query failed")
            return ""

    def _emit_state(self) -> str:
        """Emit full state snapshot as JSON (sse-starlette handles SSE framing)."""
        if self._snapshot is None:
            return ""
        return json.dumps({
            "type": "state",
            "stage": self._snapshot.stage,
            "plan": self._snapshot.plan,
            "current_step": self._snapshot.current_step,
            "step_results": self._snapshot.step_results,
            "research_notes": self._snapshot.research_notes[:200],
            "waiting_for": self._snapshot.waiting_for,
            "strategy_signature": self._snapshot.strategy_signature,
            "task_fingerprint": self._snapshot.task_fingerprint,
            "next_action": self._snapshot.next_action,
            "artifacts": self._snapshot.artifacts,
            "workflow_shadow": self._snapshot.workflow_shadow,
            "task_contract": self._snapshot.task_contract,
        }, ensure_ascii=False)

    # --- Role Implementations ---

    async def _route_intent(self, message: str, context: str, model_id: str | None = None) -> str:
        """Router: classify user intent into workflow type."""
        lower = message.lower()

        # Deterministic overrides for common patterns
        if self._is_connectivity_status_request(message):
            return "research"
        if self._is_model_meta_question(message, context):
            return "general"
        design_intent = (
            any(kw in lower for kw in [
                "binder", "de novo", "backbone", "scaffold", "生成序列", "generate sequence",
                "结合蛋白", "蛋白设计", "从头设计", "骨架设计",
            ])
            or ("design" in lower and any(kw in lower for kw in ["protein", "binder", "sequence", "backbone", "scaffold"]))
            or ("设计" in lower and any(kw in lower for kw in ["蛋白", "序列", "骨架", "结合"]))
        )
        if design_intent:
            return "design"
        has_explicit_reference = bool(
            self._extract_named_protein_reference(message)
            or self._extract_uniprot_reference(message)
            or self._extract_pdb_id_reference(message)
        )
        if has_explicit_reference and any(kw in lower for kw in [
            "目标", "提高", "降低", "分析", "改造", "优化", "稳定性", "热", "酸", "碱",
            "ph", "activity", "stability", "improve", "optimize", "engineer",
        ]):
            return "analyze"
        if has_explicit_reference:
            return "research"
        if self._extract_attached_object_name(message) and any(kw in lower for kw in [
            "上传", "结构", "pdb", "object_name", "uploaded", "structure",
        ]) and "附件" not in lower:
            return "research"
        if re.search(r"\b[ACDEFGHIKLMNPQRSTVWY][0-9]{1,5}[ACDEFGHIKLMNPQRSTVWY]\b", message, re.IGNORECASE):
            return "analyze"
        if any(kw in lower for kw in ["突变", "mutation", "mutant", "variant", "ddg"]):
            return "analyze"
        if any(kw in lower for kw in ["对接", "docking", "dock", "结合", "binding"]):
            return "analyze"
        if any(kw in lower for kw in ["ph", "酸性", "碱性", "最适", "酶活", "活性", "engineering", "改造",
                                        "stability", "stabilize", "catalytic", "substrate", "kcat", "km",
                                        "specificity", "optimum", "耐酸", "耐碱", "耐热", "热稳定", "稳定性"]):
            return "analyze"
        if any(kw in lower for kw in ["结构", "structure", "fold", "pdb", "预测结构"]):
            return "research"
        if any(kw in lower for kw in ["性质", "property", "properties", "理化", "predict", "预测", "analyze", "分析"]):
            return "analyze"
        if any(kw in lower for kw in ["ec", "酶功能", "enzyme function", "classify", "分类", "ec number"]):
            return "research"
        if any(kw in lower for kw in ["kcat", "km", "turnover", "动力学", "kinetics", "催化效率", "催化速率"]):
            return "analyze"
        if any(kw in lower for kw in [
            "搜索", "search", "blast", "查找", "find", "查一下", "查询", "检索",
            "文献", "literature", "evidence", "证据",
        ]):
            return "research"

        # Messages with protein sequences → analyze or research
        if self._extract_sequence(message):
            return "analyze"

        # Short messages without protein context → general chat
        protein_kw = ["protein", "蛋白", "sequence", "序列", "peptide", "residue",
                      "amino", "mutation", "structure", "docking", "binder"]
        has_protein_context = any(kw in lower for kw in protein_kw)
        if not has_protein_context and len(message.split()) < 15:
            return "general"

        # LLM-based routing for ambiguous queries
        skills_hint = "\n".join([
            f"- {s['name']}: {s['description'][:80]}"
            for s in self.skills_metadata[:5]
        ])

        try:
            resp = await self._call_llm([
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT.format(skills=skills_hint)},
                {"role": "user", "content": message},
            ], model_id=model_id, max_tokens=10)
            route = (resp.choices[0].message.content or "general").strip().lower()
            if route in ("design", "research", "analyze", "general"):
                return route
        except Exception:
            logger.exception("Router LLM call failed")
        return "general"

    async def _get_knowledge_context(self, message: str, task_type: str = "research") -> str:
        """Gather knowledge context via Coordinator (parallel Data + Literature agents).

        Replaces the old inline sequential queries. The Coordinator runs:
        1. DataAgent — enzyme knowledge graph + ESM-2 vector search
        2. LiteratureAgent — PubMed/Europe PMC + ChromaDB RAG + experience memory
        Both agents run in parallel with a shared timeout.

        Returns a combined context string for injection into PI/SC prompts.
        Gracefully degrades if any source is unavailable.
        """
        result = await self._coordinator.gather(message, task_type=task_type)
        return result.context

    async def _research_pi(
        self, message: str, history: list[dict], context: str,
        model_id: str | None = None,
        task_type: str = "research",
    ) -> str:
        """PI: Research phase — gather background, clarify requirements."""
        # Gather knowledge graph + literature + vector search context (via Coordinator)
        knowledge_context = await self._get_knowledge_context(message, task_type=task_type)

        user_content = f"Task: {self._display_task_summary(message)}\nProtein context: {self._sanitize_uploaded_metadata_text(context)}"
        if knowledge_context:
            user_content += f"\n\n{knowledge_context}"

        messages = [
            {"role": "system", "content": PI_SYSTEM_PROMPT},
            *history[-6:],  # Last 3 turns for context
            {"role": "user", "content": user_content},
        ]
        try:
            resp = await self._call_llm(messages, model_id=model_id, max_tokens=600)
            return resp.choices[0].message.content or ""
        except Exception:
            logger.exception("PI research LLM call failed")
            return ""

    async def _plan_cb(
        self, message: str, research: str, history: list[dict],
        model_id: str | None = None,
        context: str = "",
        analysis_depth: str = "standard",
    ) -> list[PlanStep]:
        """CB: Planning phase — create tool execution plan."""
        skills_text = "\n".join([
            f"- {s['name']}: {s['description']}"
            for s in self.skills_metadata
        ])
        tools_text = "\n".join([
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in (self.tools_schema or [])
        ])

        # Extract sequence from message to help the LLM fill params
        seq = self._extract_sequence(message)
        seq_hint = f"\n\nDetected protein sequence: {seq}" if seq else ""

        plan_prompt = CB_SYSTEM_PROMPT.format(
            skills=skills_text,
            tools=tools_text,
            research=research,
            task=message + seq_hint,
        )

        messages = [
            {"role": "system", "content": plan_prompt},
            *history[-4:],
            {"role": "user", "content": f"Create a step-by-step tool execution plan for: {message}"},
        ]

        # Query past experiences for planning hints (MLEvolve retrospective memory)
        # Infer task type from message keywords (same logic as router)
        lower = message.lower()
        if any(kw in lower for kw in ["design", "binder", "de novo", "backbone", "scaffold"]):
            task_type_hint = "design"
        elif any(kw in lower for kw in ["mutat", "stability", "engineer", "optim", "enhanc"]):
            task_type_hint = "analyze"
        else:
            task_type_hint = "research"
        await self._get_experience_hints(message, task_type_hint)

        # Use deterministic fallback plan — LLM-generated plans are unreliable for now
        # (wrong parameter names, missing essential steps). The fallback covers all
        # common enzyme engineering tasks with correct tool params.
        return self._generate_fallback_plan(message, context=context, analysis_depth=analysis_depth)

    def _parse_plan(self, response: Any, task: str) -> list[PlanStep]:
        """Parse CB's response into structured PlanSteps."""
        steps = []
        msg = response.choices[0].message

        # If LLM returned tool calls, use them directly
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for i, tc in enumerate(msg.tool_calls):
                try:
                    params = json.loads(tc.function.arguments) if isinstance(
                        tc.function.arguments, str
                    ) else tc.function.arguments
                except (json.JSONDecodeError, TypeError):
                    params = {}
                steps.append(PlanStep(
                    id=i + 1,
                    tool_name=tc.function.name,
                    description=f"Execute {tc.function.name}",
                    params=params,
                ))
            return self._apply_tool_constraints(steps, task)

        # Otherwise extract from text
        content = msg.content or ""
        # Look for JSON plan blocks
        if "```json" in content:
            try:
                json_str = content.split("```json")[1].split("```")[0].strip()
                plan_data = json.loads(json_str)
                if isinstance(plan_data, list):
                    for i, step_data in enumerate(plan_data):
                        steps.append(PlanStep(
                            id=i + 1,
                            tool_name=step_data.get("tool", step_data.get("tool_name", "")),
                            description=step_data.get("description", ""),
                            params=step_data.get("params", {}),
                        ))
                    return self._apply_tool_constraints(steps, task)
            except (json.JSONDecodeError, IndexError):
                pass

        return self._generate_fallback_plan(task)

    def _generate_fallback_plan(self, task: str, context: str = "", analysis_depth: str = "standard") -> list[PlanStep]:
        """Generate the deterministic tool plan for enzyme/protein analysis.

        This is the fallback when the LLM fails to produce a valid plan. Enzyme
        engineering follows the platform's manual analysis flow: validate input,
        acquire or summarize structure status, build a minimal enzyme profile,
        then route objective-specific deep analysis and candidate ranking.
        Slow external tools such as BLAST and MD are still opt-in.
        """
        core_fallback_tools = {
            "predict_properties",
            "sequence_search",
            "esmfold_folding",
            "external_connectivity_check",
        }
        if not core_fallback_tools.issubset(ToolRegistry._tools):
            ToolRegistry.discover()

        steps = []
        combined_task = f"{task}\n{context}".strip()
        lower = combined_task.lower()
        analysis_depth = (analysis_depth or "standard").strip().lower()
        if analysis_depth not in {"fast", "standard", "deep"}:
            analysis_depth = "standard"
        depth_allows_slow = analysis_depth == "deep"
        tool_names = set(ToolRegistry._tools.keys())
        seq = self._extract_sequence(combined_task) or ""
        pdb_object_name = self._extract_attached_object_name(combined_task)
        requested_positions = self._extract_requested_positions(combined_task)
        requested_mutations = self._extract_requested_mutations(combined_task)
        if self._task_requests_no_tools(combined_task):
            return []
        if self._is_model_meta_question(task, context):
            return []
        if self._is_governance_evidence_request(combined_task) and "external_research_evidence" in tool_names:
            return [PlanStep(
                1,
                "external_research_evidence",
                "Read audited local training, model-claim, customer-delivery, and release evidence",
                {"scope": "all"},
            )]
        if self._is_connectivity_status_request(task) and "external_connectivity_check" in tool_names:
            return [PlanStep(
                1,
                "external_connectivity_check",
                "Probe current outbound access to official UniProt, NCBI, and InterPro APIs",
                {},
            )]
        if self._wants_live_literature_search(combined_task) and "literature_live_search" in tool_names:
            literature_steps: list[PlanStep] = []
            if self._has_concrete_protein_input(task, context) and "sequence_search" in tool_names:
                search_query, search_database = self._extract_lookup_target(task)
                literature_steps.append(PlanStep(
                    1,
                    "sequence_search",
                    f"Resolve the protein target before literature synthesis: {search_query}",
                    {"query": search_query, "database": search_database, "max_results": 5},
                ))
            literature_steps.append(PlanStep(
                len(literature_steps) + 1,
                "literature_live_search",
                "Search live PubMed and Crossref literature evidence for the user's query",
                {"query": self._clean_literature_query(combined_task), "max_results": 8},
            ))
            return literature_steps

        # Detect enzyme engineering intent
        is_enzyme_eng = any(kw in lower for kw in [
            "enzyme", "酶", "ph", "酸性", "碱性", "最适", "酶活", "engineering", "改造",
            "mutation", "stability", "stabilize", "activity", "catalytic",
            "substrate", "kcat", "km", "specificity", "optimum",
            "耐酸", "耐碱", "耐热", "热稳定", "比活力",
        ])

        objectives = self._classify_engineering_objectives(combined_task)
        eng_goal = self._primary_engineering_goal(objectives)
        objective_signals = sorted(objectives)

        # Detect binder / de novo protein design intent
        is_binder_design = any(kw in lower for kw in [
            "binder", "bind", "de novo", "backbone", "scaffold",
            "design a", "design binder", "结合蛋白", "蛋白设计",
            "从头设计", "骨架设计", "设计蛋白",
        ])
        wants_deep = depth_allows_slow or any(kw in lower for kw in [
            "deep", "deep analysis", "comprehensive", "full report", "full pipeline",
            "深入", "深度", "全面", "完整", "全量", "完整版", "详细报告",
        ])
        wants_quick = analysis_depth == "fast" or any(kw in lower for kw in [
            "quick", "fast", "rapid", "screen", "summary",
            "快速", "尽快", "先粗筛", "先给结论", "简要", "摘要",
        ])
        wants_structure = any(kw in lower for kw in [
            "structure", "fold", "folding", "pdb", "3d", "surface", "active site",
            "结构", "折叠", "三维", "pdb", "表面", "活性位点",
        ])
        wants_blast = any(kw in lower for kw in [
            "blast", "homolog", "homology", "conservation", "family", "motif",
            "同源", "保守", "家族", "模体", "比对",
        ])
        wants_md = bool(re.search(r"\bmd\b", lower)) or any(kw in lower for kw in [
            "gromacs", "molecular dynamics", "md simulation", "md analysis",
            "rmsd", "rmsf", "分子动力学", "md模拟", "md 模拟", "md分析", "md 分析",
        ])
        wants_scan = any(kw in lower for kw in [
            "scan", "saturation", "alanine", "all mutations", "systematic scan",
            "扫描", "全位点", "饱和突变", "丙氨酸扫描", "系统扫描",
        ])
        wants_variant_scoring = any(kw in lower for kw in [
            "protssn", "variant effect", "effect score", "突变效应", "效应评分",
        ])
        wants_pocket = any(kw in lower for kw in [
            "pocket", "p2rank", "fpocket", "ligand contacts", "口袋", "结合口袋", "底物口袋", "通道",
        ])
        wants_rosetta_ddg = any(kw in lower for kw in [
            "rosetta", "ddg", "Δδg", "δδg", "delta delta g", "cartesian_ddg",
            "稳定能量", "突变能量", "负值", "正值", "更稳定", "不稳定",
        ])
        kinetics_context = lower
        for phrase in (
            "热稳定性",
            "热稳定",
            "温度稳定性",
            "温度稳定",
            "残余活性",
            "热处理后活性",
            "thermal stability",
            "thermostability",
            "residual activity",
        ):
            kinetics_context = kinetics_context.replace(phrase, " ")
        wants_kinetics = any(kw in kinetics_context for kw in [
            "kcat", "km", "kinetics", "activity", "specificity",
            "酶活", "活性", "比活", "动力学", "特异性",
        ])

        has_sequence = len(seq) >= 10
        query_pdb_id = self._extract_pdb_id_reference(combined_task)
        step_id = 0

        if pdb_object_name:
            if "structure_search_foldseek" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "structure_search_foldseek",
                    "Parse and summarize the uploaded experimental structure before any structure-dependent analysis",
                    {
                        "pdb_object_name": pdb_object_name,
                        **({"pdb_id": query_pdb_id} if query_pdb_id else {}),
                        "database": "pdb",
                        "max_results": 5,
                    }))
            if "residue_mapping_sifts" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "residue_mapping_sifts",
                    "Build a residue numbering map for the uploaded structure before projecting positions or structural claims",
                    {
                        "pdb_object_name": pdb_object_name,
                        "chain_id": "A",
                        **({"pdb_id": query_pdb_id} if query_pdb_id else {}),
                        **({"input_sequence": seq} if has_sequence else {}),
                    }))
            if requested_positions and "residue_numbering_gate" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "residue_numbering_gate",
                    "Validate requested residue numbering before using residue-level structure claims",
                    {
                        "requested_positions": requested_positions,
                        "user_confirmed": False,
                    }))
            # PDB-only deep analysis must continue after structure parsing. The
            # coordinate-derived chain sequence is hydrated into these empty
            # sequence parameters before the strategy is signed, so confirmation
            # executes the exact frozen inputs rather than an execution-time
            # rewrite. It remains explicitly PDB-coordinate-derived, not
            # UniProt-numbered.
            if wants_deep and is_enzyme_eng and not has_sequence:
                pdb_sequence_params = {"sequence": ""}
                annotation_uniprot_id = self._extract_uniprot_reference(combined_task)
                assay_context = self._extract_assay_context(combined_task)
                if objective_signals:
                    assay_context = {**assay_context, "objective_signals": objective_signals}

                if "predict_properties" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "predict_properties",
                        "Compute baseline physicochemical features from the PDB coordinate-derived chain sequence",
                        dict(pdb_sequence_params),
                    ))
                if "annotation_bundle" in tool_names:
                    step_id += 1
                    annotation_params = dict(pdb_sequence_params)
                    if annotation_uniprot_id:
                        annotation_params["uniprot_id"] = annotation_uniprot_id
                    steps.append(PlanStep(
                        step_id,
                        "annotation_bundle",
                        "Annotate family/domain, catalytic-site, cofactor, and signal-peptide evidence from the recovered PDB chain sequence",
                        annotation_params,
                    ))
                if "enzyme_identity_profile" in tool_names:
                    step_id += 1
                    profile_params = {
                        **pdb_sequence_params,
                        "structure_id": query_pdb_id or "uploaded_pdb_coordinate_model",
                        "chain_id": "A",
                    }
                    if annotation_uniprot_id:
                        profile_params["uniprot_id"] = annotation_uniprot_id
                    steps.append(PlanStep(
                        step_id,
                        "enzyme_identity_profile",
                        "Identify enzyme family, catalytic motifs, protected residues, and PDB-coordinate numbering guardrails before ranking",
                        profile_params,
                    ))
                if "enzyme_objective_module_plan" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "enzyme_objective_module_plan",
                        "Gate objective-specific evidence and candidate-table boundary",
                        {"objective": eng_goal, "objective_signals": objective_signals, "assay_context": assay_context},
                    ))
                if "protein_benchmark" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "protein_benchmark",
                        "Analyze family constraints and conservation from the recovered PDB chain sequence",
                        {"query_sequence": ""},
                    ))
                if "enzyme_function" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "enzyme_function",
                        "Predict enzyme class only after the recovered sequence and identity profile are available",
                        dict(pdb_sequence_params),
                    ))
                if "build_site_structure_function_features" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "build_site_structure_function_features",
                        "Build residue-level CA geometry, B-factor, contact, and protected-site features before mutation ranking",
                        {"pdb_object_name": pdb_object_name, "chain_id": "A"},
                    ))
                if "pocket_residue_lookup" in tool_names and wants_pocket:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "pocket_residue_lookup",
                        "Run P2Rank/fpocket when installed and return parsed pocket residue coordinates; otherwise return a runtime-blocked contract",
                        {"pdb_object_name": pdb_object_name, "chain_id": "A", "engine": "auto"},
                    ))

                run_priority = bool(objectives & {
                    "thermostability", "ph_lowering", "ph_raising", "activity", "specificity",
                }) or any(kw in lower for kw in ["突变", "mutation", "mutant", "variant", "位点", "residue"])
                if run_priority and "mutation_priority_score" in tool_names:
                    step_id += 1
                    priority_params = {"sequence": "", "engineering_goal": eng_goal, "objective_signals": objective_signals}
                    if requested_mutations:
                        priority_params["specified_mutations"] = requested_mutations
                    steps.append(PlanStep(
                        step_id,
                        "mutation_priority_score",
                        f"Rank PDB-coordinate residue hypotheses for {eng_goal} after identity and objective gates",
                        priority_params,
                    ))
                if "activity" in objectives and "kcat_predict" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "kcat_predict",
                        "Estimate the wild-type catalytic baseline from the recovered PDB chain sequence",
                        {"protein_sequence": ""},
                    ))
                if "activity" in objectives and "mutation_scan" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "mutation_scan",
                        "Scan substitutions only if identity and objective gates permit candidate generation",
                        {"sequence": "", "scan_type": "saturation"},
                    ))
                if "protssn_score" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "protssn_score",
                        "Run secondary sequence-based variant scoring only if identity and objective gates permit it",
                        {"sequence": "", "mutations": []},
                    ))
                if "blast_search" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(
                        step_id,
                        "blast_search",
                        "Search NCBI curated protein homologs with the recovered PDB chain sequence for family and conservation evidence",
                        {
                            "sequence": "",
                            "program": "blastp",
                            "database": "swissprot",
                            "max_results": 8,
                        },
                    ))

        # --- Binder Design Pipeline (with sequence) ---
        if has_sequence and is_binder_design:
            # 1. Inverse folding — redesign sequence for the given backbone
            if "proteinmpnn_design" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "proteinmpnn_design",
                    "Inverse folding: design novel sequences that stably fold into the target backbone",
                    {"temperature": 0.1, "num_sequences": 3}))

            # 2. Solubility optimization
            if "soluble_mpnn_design" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "soluble_mpnn_design",
                    "Optimize designed sequences for solubility and expression",
                    {"sequence": seq}))

            # 3. Structure validation — verify designed sequences fold correctly
            if "esmfold_folding" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "esmfold_folding",
                    "Validate folding of designed sequences — high pLDDT confirms stable backbone",
                    {"sequence": seq}))

            # 4. Physicochemical baseline
            if "predict_properties" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "predict_properties",
                    "Compute MW, pI, stability, GRAVY for designed sequences",
                    {"sequence": seq}))

            return self._apply_tool_constraints(steps, task, context)

        if has_sequence:
            # Follow the manual enzyme analysis flow: basic sequence validation,
            # structure status, minimal enzyme profile, then objective-specific tools.
            # BLAST is part of the identity lane whenever an uploaded structure
            # is being engineered; otherwise a model without an accession can
            # be incorrectly treated as an anonymous sequence. MD remains opt-in.
            quick_mode = wants_quick or not wants_deep
            run_structure = is_enzyme_eng or wants_deep or wants_structure
            run_blast = wants_deep or wants_blast or bool(pdb_object_name)
            run_scan = wants_deep or wants_scan
            run_md = wants_md
            run_protssn = wants_deep or wants_variant_scoring
            run_kinetics = wants_kinetics

            # 1. Physicochemical properties — baseline metrics (instant)
            if "predict_properties" in tool_names:
                prop_subset = None
                if objectives & {"thermostability", "ph_lowering", "ph_raising"}:
                    prop_subset = ["molecular_weight", "isoelectric_point", "instability_index", "gravy", "secondary_structure"]
                elif "solubility" in objectives and objectives.isdisjoint({"activity", "specificity", "thermostability", "ph_lowering", "ph_raising"}):
                    prop_subset = ["gravy", "instability_index", "disorder", "amino_acid_composition"]
                params = {"sequence": seq}
                if prop_subset:
                    params["properties"] = prop_subset
                step_id += 1
                steps.append(PlanStep(step_id, "predict_properties",
                    "Compute objective-relevant physicochemical sequence features",
                    params))

            run_family_context = is_enzyme_eng or wants_deep or wants_blast or bool(objectives & {"activity", "specificity"})
            annotation_uniprot_id = self._extract_uniprot_reference(combined_task)

            # 3. Curated annotation evidence — family/function/site data must be
            # resolved before the profile translates them into engineering guardrails.
            if "annotation_bundle" in tool_names and is_enzyme_eng:
                step_id += 1
                annotation_params = {"sequence": seq}
                if annotation_uniprot_id:
                    annotation_params["uniprot_id"] = annotation_uniprot_id
                steps.append(PlanStep(step_id, "annotation_bundle",
                    "Resolve curated family/domain, EC, catalytic-site, cofactor, and signal-peptide evidence before engineering",
                    annotation_params))

            # 4. Identity profile — gate family / key residues before ranking and function calls
            if "enzyme_identity_profile" in tool_names and is_enzyme_eng:
                step_id += 1
                profile_params = {"sequence": seq}
                if pdb_object_name:
                    profile_params.update({
                        "structure_id": query_pdb_id or "uploaded_pdb_coordinate_model",
                        "chain_id": "A",
                    })
                if annotation_uniprot_id:
                    profile_params["uniprot_id"] = annotation_uniprot_id
                steps.append(PlanStep(step_id, "enzyme_identity_profile",
                    "Identify enzyme family, catalytic motifs, protected residues, and numbering guardrails before candidate ranking",
                    profile_params))

            # 4.5. Objective module gate — separates thermostability, activity,
            # specificity, pH, and expression evidence before candidate tables.
            if "enzyme_objective_module_plan" in tool_names and is_enzyme_eng:
                step_id += 1
                assay_context = self._extract_assay_context(combined_task)
                if objective_signals:
                    assay_context = {**assay_context, "objective_signals": objective_signals}
                steps.append(PlanStep(step_id, "enzyme_objective_module_plan",
                    "Gate the objective-specific module and decide whether mutation candidate output is allowed",
                    {
                        "objective": eng_goal,
                        "objective_signals": objective_signals,
                        "assay_context": assay_context,
                    }))

            # 5. Protein benchmark — minimal family/motif/catalytic profile before target-specific claims
            if "protein_benchmark" in tool_names and is_enzyme_eng and run_family_context:
                step_id += 1
                steps.append(PlanStep(step_id, "protein_benchmark",
                    "Characterize enzyme family, motifs, catalytic residues, and conserved constraints relevant to the objective",
                    {"query_sequence": seq}))

            # 6. Enzyme function prediction — minimal EC/function profile for all enzyme engineering targets
            if is_enzyme_eng and "enzyme_function" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "enzyme_function",
                    "Predict EC number and enzyme class from sequence using curated motifs and ESM-2 embeddings",
                    {"sequence": seq}))

            if pdb_object_name and wants_deep and is_enzyme_eng and "build_site_structure_function_features" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "build_site_structure_function_features",
                    "Build residue-level CA geometry, B-factor, contact, and protected-site features before mutation ranking",
                    {"pdb_object_name": pdb_object_name, "chain_id": "A"}))
            if pdb_object_name and is_enzyme_eng and "pocket_residue_lookup" in tool_names and wants_pocket:
                step_id += 1
                steps.append(PlanStep(step_id, "pocket_residue_lookup",
                    "Run P2Rank/fpocket when installed and return parsed pocket residue coordinates; otherwise return a runtime-blocked contract",
                    {"pdb_object_name": pdb_object_name, "chain_id": "A", "engine": "auto"}))

            # 7. Structure prediction follows the identity/function foundation.
            # It is required before pocket/exposure/network interpretation, not
            # before sequence-based retrieval and catalytic-site mapping.
            if run_structure and not pdb_object_name and "esmfold_folding" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "esmfold_folding",
                    "Predict 3D structure for subsequent pocket, exposure, and catalytic-network interpretation",
                    {"sequence": seq}))

            # 8. Mutation priority scoring — target-specific residue ranking
            run_priority = is_enzyme_eng and (
                bool(objectives & {
                    "thermostability",
                    "ph_lowering",
                    "ph_raising",
                    "activity",
                    "specificity",
                })
                or wants_deep
                or any(kw in lower for kw in ["突变", "mutation", "mutant", "variant", "位点", "residue"])
            )
            if run_priority and "mutation_priority_score" in tool_names:
                step_id += 1
                priority_params = {"sequence": seq, "engineering_goal": eng_goal, "objective_signals": objective_signals}
                if requested_mutations:
                    priority_params["specified_mutations"] = requested_mutations
                steps.append(PlanStep(step_id, "mutation_priority_score",
                    f"Score residues for {eng_goal} engineering and rank Tier 1/2 candidates",
                    priority_params))

            if requested_mutations and wants_rosetta_ddg and "rosetta_ddg" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "rosetta_ddg",
                    "Calculate mutation ΔΔG with Rosetta when runtime is available; otherwise return a blocked/runtime contract",
                    {
                        "sequence": seq,
                        "mutations": requested_mutations,
                        "pdb_object_name": pdb_object_name,
                        "allow_local_estimate": False,
                    }))

            # 6. Enzyme kinetics prediction — activity/kinetics-focused only.
            if is_enzyme_eng and (
                "activity" in objectives
                or (run_kinetics and "specificity" not in objectives)
            ) and "kcat_predict" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "kcat_predict",
                    "Predict enzyme turnover number (Kcat) and catalytic efficiency",
                    {"protein_sequence": seq}))

            # 7. Residue scan — default for activity/specificity redesign, explicit/deep otherwise
            if (run_scan or bool(objectives & {"activity", "specificity"})) and "mutation_scan" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "mutation_scan",
                    "Scan substitutions around candidate residues for activity/specificity engineering",
                    {"sequence": seq, "scan_type": "saturation" if wants_deep else "alanine"}))

            # 8. Solubility/expression design — only for soluble-expression objectives
            if "solubility" in objectives and "soluble_mpnn_design" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "soluble_mpnn_design",
                    "Redesign sequence positions for soluble expression and lower aggregation propensity",
                    {"sequence": seq, "mode": "soluble", "temperature": 0.1}))

            # 9. ML-enhanced mutation scoring — only when explicitly requested or deep mode
            if is_enzyme_eng and run_protssn and "protssn_score" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "protssn_score",
                    "ML-enhanced mutation scoring with sequence-structure fusion for higher accuracy",
                    {"sequence": seq, "mutations": []}))

            # 10. BLAST search — external and slow; do not run by default in quick mode
            if run_blast and "blast_search" in tool_names:
                blast_db = "swissprot"
                blast_hits = 3 if quick_mode and not wants_deep else 5
                step_id += 1
                steps.append(PlanStep(step_id, "blast_search",
                    "Identify enzyme family homologs and conserved residues via BLAST (external NCBI)",
                    {"sequence": seq, "database": blast_db, "max_results": blast_hits}))

            # 11. MD simulation — only when explicitly requested.
            if run_md and "gromacs_md" in tool_names and pdb_object_name:
                md_ns = 1.0 if quick_mode and not wants_deep else 10.0
                step_id += 1
                steps.append(PlanStep(step_id, "gromacs_md",
                    "Submit a molecular dynamics job for stability and flexibility review",
                    {
                        "sequence": seq,
                        "pdb_object_name": pdb_object_name,
                        "simulation_time_ns": md_ns,
                        "replicate_plan_only": False,
                        "upload_artifacts": True,
                    }))

        if (
            pdb_object_name
            and wants_md
            and not (not has_sequence and "activity" in objectives and not wants_md)
            and "gromacs_md" in tool_names
            and not any(step.tool_name == "gromacs_md" for step in steps)
        ):
            step_id += 1
            steps.append(PlanStep(step_id, "gromacs_md",
                "Submit a molecular dynamics job from the attached structure",
                {
                    "pdb_object_name": pdb_object_name,
                    "simulation_time_ns": 1.0 if wants_quick and not wants_deep else 10.0,
                    "replicate_plan_only": False,
                    "upload_artifacts": True,
                }))

        # If no sequence, try to extract a protein name and search for it
        if not steps:
            if pdb_object_name:
                return self._apply_tool_constraints(steps, task, context)
            has_lookup_target = self._has_concrete_protein_input(task, context)
            search_query, search_database = self._extract_lookup_target(task) if has_lookup_target else ("", "uniprot")

            # --- Binder Design Pipeline (no sequence) ---
            if is_binder_design:
                if not has_lookup_target:
                    return self._apply_tool_constraints(steps, task, context)
                # 1. Search for target protein sequence
                if "sequence_search" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "sequence_search",
                        f"Search for target protein: {search_query}",
                        {"query": search_query, "database": search_database, "max_results": 5}))

                # 2. RFdiffusion — generate binder backbone scaffolds
                if "rfdiffusion_design" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "rfdiffusion_design",
                        f"Generate de novo binder backbone scaffolds targeting {search_query}",
                        {"target": "binder", "length": 100, "num_designs": 3}))

                # 3. Chroma — joint structure-sequence generation
                if "chroma_design" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "chroma_design",
                        "Joint structure-sequence generation for binder design",
                        {"length": 100, "num_designs": 3, "target_shape": "binder-like globular scaffold"}))

                # 4. ProteinMPNN — inverse folding on generated backbones
                if "proteinmpnn_design" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "proteinmpnn_design",
                        "Inverse folding: design sequences for generated binder backbones",
                        {"temperature": 0.1, "num_sequences": 3}))

                # 5. ESMFold — validate folding of designed sequences
                if "esmfold_folding" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "esmfold_folding",
                        "Validate designed binder sequences fold into intended backbone",
                        {}))

                return self._apply_tool_constraints(steps, task, context)

            # Generic fallback: search for protein sequence
            if has_lookup_target and "sequence_search" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "sequence_search",
                    f"Search for protein/gene: {search_query}",
                    {"query": search_query, "database": search_database, "max_results": 5}))

        return self._apply_tool_constraints(steps, task, context)

    @staticmethod
    def _extract_protein_name(task: str) -> str:
        """Extract a likely protein/gene name from a natural language query.

        Handles patterns like:
        - "Design a binder for PD-L1" → "PD-L1"
        - "Analyze the structure of EGFR" → "EGFR"
        - "What is the sequence of human p53" → "p53"
        """
        named = AgentOrchestrator._extract_named_protein_reference(task)
        if named:
            return named
        uniprot_id = AgentOrchestrator._extract_uniprot_reference(task)
        if uniprot_id:
            return uniprot_id
        pdb_id = AgentOrchestrator._extract_pdb_id_reference(task)
        if pdb_id:
            return pdb_id

        # Common prefixes that introduce a protein name (case-insensitive)
        prefix_str = (
            r'(?i:design|bind(?:er)?|for|target(?:ing)?|against|of|on|about|analy[sz]e|study|'
            r'investigate|engineer|mutate|optimize|improve|enhance|modify|evolve|screen)\s+'
            r'(?:a\s+|an\s+|the\s+)?'
            r'(?:(?:high|low)[\s-]*(?:affinity|specificity)\s+)?'
            r'(?:protein\s+|enzyme\s+|binder\s+)?'
            r'(?:for\s+|of\s+|to\s+|against\s+|targeting\s+)?'
        )
        # Protein/gene name pattern: UPPERCASE letters, numbers, hyphens (case-sensitive)
        protein_pattern = r'([A-Z][A-Z0-9]+(?:[-/][A-Z0-9]+)*)'

        # Try to find protein names after prefix patterns
        match = re.search(prefix_str + protein_pattern, task)
        if match:
            name = match.group(1).strip()
            if len(name) >= 2:
                return name

        # Fallback: find any uppercase identifier (2-15 chars) in the text
        matches = re.findall(r'\b([A-Z][A-Z0-9]+(?:[-/][A-Z0-9]+)*)\b', task)
        if matches:
            # Prefer longer matches and exclude common English words
            english_upper = {'A', 'I', 'THE', 'IS', 'ARE', 'BE', 'DO', 'FOR', 'AND', 'NOT', 'BUT', 'OR', 'NOR', 'SO', 'YET', 'THIS'}
            candidates = [m for m in matches if m.upper() not in english_upper and len(m) >= 2]
            if candidates:
                return max(candidates, key=len)

        # Last resort: use a cleaned version of the query
        return task[:150]

    async def _review_results_sc(
        self, task: str, tool_results: list[dict], research: str,
        model_id: str | None = None,
    ) -> dict:
        """SC Review: critically examine tool results and identify gaps.

        Returns a dict with:
          - needs_supplement: bool — whether additional tools are needed
          - supplementary_steps: list[dict] — extra tool calls to make
          - critique: str — brief assessment of what's missing
        """
        results_text = "\n".join([
            f"- {r['tool_name']}: {r['status']} | {str(r.get('result', ''))[:200]}"
            for r in tool_results
        ])

        tools_list = "\n".join([
            f"- {t['function']['name']}: {t['function']['description'][:120]}"
            for t in (self.tools_schema or [])[:25]
        ])

        review_prompt = (
            "You are the Scientific Critic (SC) of a protein engineering team. "
            "Your job is to CRITICALLY examine the tool execution results and determine "
            "if they are sufficient to answer the user's question with SPECIFIC, actionable recommendations.\n\n"
            f"User task: {self._display_task_summary(task)}\n\n"
            f"Research notes: {research[:300]}\n\n"
            "Tool execution results so far:\n"
            f"{results_text}\n\n"
            "Available additional tools:\n"
            f"{tools_list}\n\n"
            "CRITICAL ASSESSMENT CRITERIA:\n"
            "1. If the task involves enzyme engineering (pH, stability, activity, mutation design):\n"
            "   - Do we know the enzyme FAMILY and catalytic MECHANISM?\n"
            "   - Do we have SPECIFIC residue numbers to recommend (not just generic regions)?\n"
            "   - Do we have a 3D structure or structural model to reason about?\n"
            "   - Have we identified which residues MUST NOT be mutated?\n"
            "2. If the task involves protein analysis:\n"
            "   - Do we have quantitative results with proper units?\n"
            "   - Are there benchmarks or comparisons to known proteins?\n"
            "3. If the task involves binder / de novo protein design:\n"
            "   - Were backbone scaffolds generated (rfdiffusion/chroma)?\n"
            "   - Do we have designed sequences with inverse folding (proteinmpnn)?\n"
            "   - Are folding validation results available (esmfold pLDDT > 70)?\n"
            "   - Is sequence diversity and recovery rate reported?\n\n"
            "Respond with a JSON object:\n"
            '{"needs_supplement": true/false,'
            ' "critique": "one-line assessment of gap",'
            ' "supplementary_steps": ['
            '   {"tool_name": "tool_name", "description": "...", "params": {...}}'
            ' ]}\n\n'
            "Only request supplementary tools if they would SIGNIFICANTLY improve the answer. "
            "If results are already comprehensive, set needs_supplement: false and leave steps empty. "
            "Request at most 3 supplementary steps."
        )

        try:
            resp = await self._call_llm(
                [{"role": "system", "content": review_prompt}],
                model_id=model_id, max_tokens=400,
            )
            content = resp.choices[0].message.content or ""
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = self._safe_parse_json(json_match.group())
                if isinstance(parsed, dict) and parsed:
                    return parsed
                logger.warning("SC review returned non-parseable JSON payload: %s", content[:500])
        except Exception:
            logger.exception("SC review JSON parse failed")

        return {"needs_supplement": False, "supplementary_steps": [], "critique": ""}

    async def _synthesize_sc(
        self, task: str, tool_results: list[dict], research: str, history: list[dict],
        model_id: str | None = None,
    ) -> str:
        """SC: Synthesize phase — validate and create final report."""
        connectivity_reply = self._build_connectivity_reply(tool_results)
        if connectivity_reply is not None:
            return connectivity_reply
        mutation_review_reply = self._build_requested_mutation_review_report(task, tool_results)
        if mutation_review_reply:
            return mutation_review_reply
        if self._tool_results_have_no_evidence(tool_results):
            return self._build_no_evidence_reply(task, tool_results)
        if self._has_plan_only_md_result(tool_results):
            return self._build_fallback_report(task, tool_results)
        if self._should_use_deterministic_structure_report(task, tool_results):
            return self._build_fallback_report(task, tool_results)
        if self._should_use_deterministic_enzyme_report(task, tool_results):
            return self._build_fallback_report(task, tool_results)

        results_text = "\n".join([
            f"Step {i+1}: {r['tool_name']} → {r['status']}\n{self._format_tool_result_for_synthesis(r)}"
            for i, r in enumerate(tool_results)
        ])
        no_hit_context = self._structure_no_hit_synthesis_context(tool_results)
        evidence_context = self._evidence_lineage_synthesis_context(tool_results)
        claim_audit_context = self._claim_audit_synthesis_context(tool_results)
        mutation_boundary_context = self._mutation_candidate_boundary_synthesis_context(tool_results)

        # Inject relevant domain skill content for deeper synthesis
        domain_context = self._load_relevant_skills(task)

        # Inject knowledge graph + literature context for synthesis
        knowledge_context = await self._get_knowledge_context(task)

        system_content = SC_SYSTEM_PROMPT + domain_context
        if knowledge_context:
            system_content += f"\n\n{knowledge_context}"

        messages = [
            {"role": "system", "content": system_content},
            *history[-4:],
            {"role": "user", "content": (
                f"Task: {self._display_task_summary(task)}\n\n"
                f"Research notes: {research[:500]}\n\n"
                f"Tool results:\n{results_text}\n\n"
                f"{no_hit_context}"
                f"{evidence_context}"
                f"{claim_audit_context}"
                f"{mutation_boundary_context}"
                "Synthesize a comprehensive scientific report with SPECIFIC residue-level "
                "recommendations. Include: enzyme family classification, catalytic residue "
                "identification, proposed mutations with positions and rationales, tiered "
                "priority ranking, experimental validation plan. "
                "Use explicit evidence sections named 序列级结论, 预测结构结论, 实验结构结论, "
                "and 编号/映射门控 when those evidence types are present. Do not mix predicted "
                "structure evidence with uploaded experimental structure evidence, and do not "
                "reuse task_id/status from prior turns unless it appears in the current Tool results. "
                "Always separate facts, analysis-based inferences, uncertainties, and "
                "items requiring wet-lab validation. If tool evidence is empty or weak, "
                "say so explicitly and ask for missing inputs instead of producing a full "
                "confident report. "
                "Use the Matvenus-derived enzyme engineering report protocol from the system "
                "prompt when the task involves enzyme activity, thermostability, mutation "
                "selection, or wet-lab feedback. "
                "Cite relevant literature (PMIDs) from the knowledge context when available. "
                "NEVER give generic advice."
            )},
        ]
        try:
            resp = await self._call_llm(messages, model_id=model_id, max_tokens=3000)
            content = resp.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except TimeoutError:
            logger.warning("SC synthesize LLM call timed out; using deterministic fallback report")
        except Exception as e:
            logger.exception("SC synthesize LLM call failed")

        # Fallback: build a structured report from tool results
        return self._build_fallback_report(task, tool_results)

    @classmethod
    def _should_use_deterministic_structure_report(cls, task: str, tool_results: list[dict]) -> bool:
        """Avoid slow LLM synthesis for uploaded-PDB structure/search gate outputs."""
        if not cls._extract_attached_object_name(task):
            return False
        if cls._extract_sequence(task):
            return False
        tool_names = {
            str(result.get("tool_name") or "")
            for result in tool_results
            if result.get("tool_name")
        }
        if not tool_names:
            return False
        return tool_names.issubset({
            "structure_search_foldseek",
            "residue_mapping_sifts",
            "residue_numbering_gate",
            "blast_search",
        })

    @classmethod
    def _should_use_deterministic_enzyme_report(cls, task: str, tool_results: list[dict]) -> bool:
        """Avoid slow LLM synthesis when enzyme-engineering tools already produced report data."""
        text = task.lower()
        enzyme_goal = any(
            marker in text
            for marker in (
                "比活力",
                "催化",
                "kcat",
                "km",
                "活性",
                "热稳定",
                "耐热",
                "ph稳定",
                "底物特异",
                "可溶性",
                "表达",
                "enzyme",
                "activity",
                "thermostability",
                "specificity",
            )
        )
        tool_names = {
            str(result.get("tool_name") or "")
            for result in tool_results
            if result.get("status") in {"completed", "submitted", "failed"} and result.get("tool_name")
        }
        if not tool_names:
            return False
        if "mutation_priority_score" in tool_names:
            return True
        if enzyme_goal and tool_names.intersection({
            "enzyme_identity_profile",
            "enzyme_objective_module_plan",
            "protein_benchmark",
            "enzyme_function",
            "kcat_predict",
        }):
            return True
        return False

    @classmethod
    def _has_plan_only_md_result(cls, tool_results: list[dict]) -> bool:
        for result in tool_results:
            if result.get("tool_name") != "gromacs_md":
                continue
            parsed = cls._safe_parse_json(str(result.get("result", "")))
            if parsed.get("status") == "planned" or parsed.get("is_real_md") is False:
                return True
        return False

    @classmethod
    def _evidence_lineage_synthesis_context(cls, tool_results: list[dict]) -> str:
        sequence_tools = []
        predicted_structure_tools = []
        uploaded_structure_tools = []
        numbering_tools = []
        async_task_ids = []

        for result in tool_results:
            tool_name = str(result.get("tool_name") or "")
            status = str(result.get("status") or "")
            payload = cls._safe_parse_json(str(result.get("result", "")))
            if tool_name in {
                "predict_properties",
                "annotation_bundle",
                "enzyme_objective_module_plan",
                "protein_benchmark",
                "enzyme_function",
                "mutation_priority_score",
                "rosetta_ddg",
                "blast_search",
                "kcat_predict",
                "protssn_score",
            }:
                sequence_tools.append(f"{tool_name}:{status}")
            if tool_name == "esmfold_folding":
                predicted_structure_tools.append(f"{tool_name}:{status}")
            if tool_name == "structure_search_foldseek":
                uploaded_structure_tools.append(f"{tool_name}:{status}")
            if tool_name in {"residue_mapping_sifts", "residue_numbering_gate"}:
                numbering_tools.append(f"{tool_name}:{status}")
            if tool_name == "enzyme_identity_profile":
                identity_status = payload.get("identity_status") if isinstance(payload, dict) else None
                family_candidates = payload.get("family_candidates") if isinstance(payload, dict) else None
                top_family = ""
                if isinstance(family_candidates, list) and family_candidates and isinstance(family_candidates[0], dict):
                    top_family = str(family_candidates[0].get("name") or "")
                label = f"{tool_name}:{status}"
                if identity_status:
                    label += f"({identity_status})"
                if top_family:
                    label += f"[{top_family}]"
                sequence_tools.append(label)
            task_id = payload.get("task_id") if isinstance(payload, dict) else None
            if task_id:
                async_task_ids.append(str(task_id))

        lines = ["Evidence lineage constraints:"]
        lines.append(f"- Sequence-level evidence tools: {', '.join(sequence_tools) if sequence_tools else 'none'}")
        lines.append(f"- Predicted-structure evidence tools: {', '.join(predicted_structure_tools) if predicted_structure_tools else 'none'}")
        lines.append(f"- Uploaded/experimental-structure evidence tools: {', '.join(uploaded_structure_tools) if uploaded_structure_tools else 'none'}")
        lines.append(f"- Numbering/mapping gates: {', '.join(numbering_tools) if numbering_tools else 'none'}")
        lines.append(f"- Current-turn async task IDs: {', '.join(async_task_ids) if async_task_ids else 'none'}")
        lines.append(
            "Report structural claims only under the matching evidence layer. "
            "If numbering/mapping gates are failed or blocked, keep residue-level structural recommendations blocked."
        )
        return "\n".join(lines) + "\n\n"

    @classmethod
    def _structure_no_hit_synthesis_context(cls, tool_results: list[dict]) -> str:
        for result in tool_results:
            if result.get("tool_name") != "structure_search_foldseek":
                continue
            if result.get("status") != "completed":
                continue
            parsed = cls._safe_parse_json(str(result.get("result", "")))
            query_structure = parsed.get("query_structure")
            if not isinstance(query_structure, dict) or not query_structure:
                continue
            results = parsed.get("results")
            results_count = parsed.get("results_count")
            has_hits = bool(results) or (isinstance(results_count, int) and results_count > 0)
            if not has_hits:
                return (
                    "Important synthesis constraint: the uploaded structure was parsed successfully, "
                    "but Foldseek returned zero homolog/template hits. Continue the analysis using the "
                    "query structure summary and explicitly separate structure-intrinsic observations, "
                    "model-based hypotheses, uncertainty, and required wet-lab/MD validation. Do not stop "
                    "only because no homolog was found; do not invent family, catalytic-site, Tm, pH curve, "
                    "or mutation-ranking evidence that is not present.\n\n"
                )
        return ""

    @classmethod
    def _build_claim_audit(cls, tool_results: list[dict]) -> dict[str, Any]:
        """Create report-grade claim controls from current tool outputs."""
        claims: list[dict[str, Any]] = []
        for result in tool_results:
            tool_name = str(result.get("tool_name") or "")
            status = str(result.get("status") or "")
            payload = cls._safe_parse_json(str(result.get("result", "")))
            if not isinstance(payload, dict):
                payload = {}
            evidence_source = payload.get("evidence_source") if isinstance(payload.get("evidence_source"), dict) else {}
            evidence_status = evidence_source.get("status")
            live_query = evidence_source.get("live_query_executed") is True

            if tool_name == "enzyme_identity_profile":
                guardrail = payload.get("guardrail") if isinstance(payload.get("guardrail"), dict) else {}
                ready = payload.get("identity_status") == "identified" and guardrail.get("status") == "ready"
                claims.append({
                    "claim_id": "FOUNDATION_PROFILE",
                    "claim": "Enzyme family/numbering foundation profile is confirmed enough for residue-level recommendations.",
                    "status": "SUPPORTED" if status == "completed" and ready else "MISSING",
                    "source": tool_name,
                })

            if tool_name == "enzyme_objective_module_plan":
                allowed = payload.get("candidate_output_allowed") is True and payload.get("status") == "ready"
                claims.append({
                    "claim_id": "OBJECTIVE_MODULE_READY",
                    "claim": "Objective-specific assay evidence is sufficient for report-grade candidate ranking.",
                    "status": "SUPPORTED" if allowed else "DESIGN_HYPOTHESIS",
                    "source": tool_name,
                    "notes": payload.get("missing_evidence"),
                })

            if tool_name == "annotation_bundle":
                claims.append({
                    "claim_id": "ANNOTATION_BUNDLE_LIVE_QUERY",
                    "claim": "Annotation bundle used live UniProt/InterPro/M-CSA/SignalP evidence in this turn.",
                    "status": "SUPPORTED" if status == "completed" and evidence_status == "live" and live_query else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": evidence_source.get("reason") or evidence_source.get("mode"),
                })

            if tool_name == "blast_search":
                claims.append({
                    "claim_id": "BLAST_LIVE_QUERY",
                    "claim": "BLAST evidence was obtained from a live NCBI query in this turn.",
                    "status": "SUPPORTED" if status == "completed" and evidence_status == "live" and live_query else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": evidence_source.get("reason") or evidence_source.get("mode") or payload.get("warning"),
                })

            if tool_name == "sequence_search":
                claims.append({
                    "claim_id": "SEQUENCE_SEARCH_LIVE_QUERY",
                    "claim": "Sequence search evidence was obtained from a live external UniProt/BLAST query in this turn.",
                    "status": "SUPPORTED" if status == "completed" and evidence_status == "live" and live_query else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": evidence_source.get("reason") or evidence_source.get("mode") or payload.get("warning"),
                })

            if tool_name == "interpro_live_lookup":
                claims.append({
                    "claim_id": "INTERPRO_LIVE_QUERY",
                    "claim": "InterPro evidence was obtained from a live InterPro API query in this turn.",
                    "status": "SUPPORTED" if status == "completed" and evidence_status == "live" and live_query else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": evidence_source.get("reason") or evidence_source.get("mode") or payload.get("warning"),
                })

            if tool_name == "interproscan_sequence_submit":
                claims.append({
                    "claim_id": "INTERPROSCAN_SEQUENCE_SUBMITTED",
                    "claim": "InterProScan sequence analysis was submitted to a live InterProScan service in this turn.",
                    "status": "SUPPORTED" if status in {"completed", "submitted"} and evidence_status == "live" and live_query else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": evidence_source.get("reason") or evidence_source.get("mode") or payload.get("warning"),
                })

            if tool_name == "interproscan_sequence_status":
                result_ready = (
                    payload.get("status") == "completed"
                    and payload.get("result_available") is True
                    and bool(payload.get("results") or payload.get("results_count"))
                )
                claims.append({
                    "claim_id": "INTERPROSCAN_SEQUENCE_RESULT",
                    "claim": "InterProScan sequence annotations were retrieved and parsed from a live InterProScan result in this turn.",
                    "status": "SUPPORTED" if status == "completed" and result_ready and evidence_status == "live" and live_query else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": evidence_source.get("reason") or evidence_source.get("mode") or payload.get("message") or payload.get("warning"),
                })

            if tool_name == "literature_live_search":
                claims.append({
                    "claim_id": "LITERATURE_LIVE_QUERY",
                    "claim": "Literature evidence was obtained from live PubMed/Crossref APIs in this turn.",
                    "status": "SUPPORTED" if status == "completed" and evidence_status == "live" and live_query else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": evidence_source.get("reason") or evidence_source.get("mode") or payload.get("warning"),
                })

            if tool_name == "mutation_priority_score":
                table_status = payload.get("candidate_table_status") or payload.get("summary", {}).get("candidate_table_status")
                has_table = bool(payload.get("experiment_design_table") or payload.get("tier_1_candidates") or payload.get("tier_2_candidates"))
                identity_gate = payload.get("identity_gate") if isinstance(payload.get("identity_gate"), dict) else {}
                objective_gate = payload.get("objective_gate") if isinstance(payload.get("objective_gate"), dict) else {}
                exploratory_table = has_table and str(table_status or "").startswith("exploratory")
                claims.append({
                    "claim_id": "MUTATION_SITE_TABLE",
                    "claim": "Mutation site table is available for experimental planning.",
                    "status": (
                        "SUPPORTED"
                        if has_table and identity_gate.get("status") == "passed" and table_status == "ready"
                        else "DESIGN_HYPOTHESIS"
                        if exploratory_table
                        else "MISSING"
                    ),
                    "source": tool_name,
                    "notes": table_status,
                })
                calibration_context = payload.get("wet_lab_calibration_context")
                if isinstance(calibration_context, dict) and calibration_context:
                    try:
                        measured_variant_count = int(calibration_context.get("measured_variant_count") or 0)
                    except (TypeError, ValueError):
                        measured_variant_count = 0
                    claims.append({
                        "claim_id": "PROJECT_WET_LAB_CALIBRATION_CONTEXT",
                        "claim": "Project-level wet-lab feedback/calibration context is available for ranking interpretation.",
                        "status": (
                            "SUPPORTED"
                            if calibration_context.get("evidence_level") in {"wet_lab_feedback", "wet_lab_calibrated"}
                            and measured_variant_count > 0
                            else "MISSING"
                        ),
                        "source": tool_name,
                        "notes": calibration_context.get("boundary") or calibration_context.get("candidate_scope"),
                    })
                    claims.append({
                        "claim_id": "CANDIDATE_DIRECT_WET_LAB_VALIDATION",
                        "claim": "The proposed mutations themselves have direct wet-lab validation in this project.",
                        "status": "MISSING",
                        "source": tool_name,
                        "notes": "Project-level calibration does not validate each newly proposed mutation; direct experiment is still required.",
                    })
                if str(table_status or "").startswith("exploratory"):
                    claims.append({
                        "claim_id": "MUTATION_EFFECT_VALIDATED",
                        "claim": "Predicted mutations are validated to improve the requested enzyme property.",
                        "status": "MISSING",
                        "source": tool_name,
                        "notes": objective_gate.get("missing_evidence") or payload.get("candidate_table_boundary"),
                    })

            if tool_name in {"kcat_predict", "protssn_score", "alphafold2_folding", "rfdiffusion_design", "proteinmpnn_design", "diffdock_docking"}:
                is_real = payload.get("is_real_inference") is True or payload.get("is_real_runtime") is True
                capability = payload.get("capability_status")
                claims.append({
                    "claim_id": f"{tool_name.upper()}_REAL_RUNTIME",
                    "claim": f"{tool_name} produced report-grade real model/runtime evidence.",
                    "status": "SUPPORTED" if is_real and capability not in {"proxy", "runtime_unverified"} else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": payload.get("report_boundary") or capability,
                })

            if tool_name == "gromacs_md":
                real_md = payload.get("is_real_md") is True
                claims.append({
                    "claim_id": "GROMACS_REAL_MD",
                    "claim": "GROMACS molecular dynamics was executed in this turn and produced report-grade MD artifacts.",
                    "status": "SUPPORTED" if real_md else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": payload.get("note") or payload.get("status"),
                })

            if tool_name == "rosetta_ddg":
                real_rosetta = payload.get("is_real_rosetta") is True
                claims.append({
                    "claim_id": "ROSETTA_REAL_DDG",
                    "claim": "Rosetta ddG was executed and produced report-grade score artifacts.",
                    "status": "SUPPORTED" if real_rosetta else "RUNTIME_UNVERIFIED",
                    "source": tool_name,
                    "notes": payload.get("note") or payload.get("reason"),
                })

        summary_gate = scientific_claim_gate(claims, report_section="summary")
        body_gate = scientific_claim_gate(claims, report_section="body")
        return {
            "claims": claims,
            "summary_gate": summary_gate,
            "body_gate": body_gate,
        }

    @classmethod
    def _compact_claim_audit_summary(cls, audit: dict[str, Any]) -> dict[str, Any]:
        """Keep only user-visible claim gate status for checkpoint memory."""
        if not isinstance(audit, dict) or not audit.get("claims"):
            return {}
        summary_gate = audit.get("summary_gate") if isinstance(audit.get("summary_gate"), dict) else {}
        body_gate = audit.get("body_gate") if isinstance(audit.get("body_gate"), dict) else {}

        def _claim_items(gate: dict[str, Any], key: str) -> list[str]:
            values = gate.get(key)
            if not isinstance(values, list):
                return []
            items: list[str] = []
            for item in values[:12]:
                if not isinstance(item, dict):
                    continue
                claim_id = str(item.get("claim_id") or "").strip()
                status = str(item.get("status") or "").strip()
                if claim_id:
                    items.append(f"{claim_id}={status or 'unknown'}")
            return items

        summary_counts = summary_gate.get("summary") if isinstance(summary_gate.get("summary"), dict) else {}
        body_counts = body_gate.get("summary") if isinstance(body_gate.get("summary"), dict) else {}
        return {
            "summary_gate": {
                "status": summary_gate.get("status"),
                "counts": {
                    "allowed": summary_counts.get("allowed_count", 0),
                    "downgraded": summary_counts.get("downgraded_count", 0),
                    "blocked": summary_counts.get("blocked_count", 0),
                },
            },
            "body_gate": {
                "status": body_gate.get("status"),
                "counts": {
                    "allowed": body_counts.get("allowed_count", 0),
                    "downgraded": body_counts.get("downgraded_count", 0),
                    "blocked": body_counts.get("blocked_count", 0),
                },
            },
            "allowed": _claim_items(summary_gate, "allowed_claims"),
            "downgraded": _claim_items(summary_gate, "downgraded_claims"),
            "blocked": _claim_items(summary_gate, "blocked_claims"),
        }

    @classmethod
    def _claim_audit_synthesis_context(cls, tool_results: list[dict]) -> str:
        audit = cls._build_claim_audit(tool_results)
        summary_gate = audit["summary_gate"]
        body_gate = audit["body_gate"]
        lines = ["Claim audit constraints:"]
        lines.append(
            f"- Summary gate: {summary_gate.get('status')} "
            f"(allowed={summary_gate.get('summary', {}).get('allowed_count', 0)}, "
            f"downgraded={summary_gate.get('summary', {}).get('downgraded_count', 0)}, "
            f"blocked={summary_gate.get('summary', {}).get('blocked_count', 0)})"
        )
        allowed_ids = [str(item.get("claim_id")) for item in summary_gate.get("allowed_claims", [])]
        blocked = summary_gate.get("blocked_claims", [])
        downgraded = summary_gate.get("downgraded_claims", [])
        if allowed_ids:
            lines.append(f"- Claims allowed in summary/conclusion: {', '.join(allowed_ids)}")
        if downgraded:
            lines.append(
                "- Claims downgraded out of summary/conclusion: "
                + "; ".join(f"{item.get('claim_id')}={item.get('status')}" for item in downgraded[:8])
            )
        if blocked:
            lines.append(
                "- Claims blocked as facts: "
                + "; ".join(f"{item.get('claim_id')}={item.get('status')}" for item in blocked[:8])
            )
        lines.append(
            "- Report rule: final summary/conclusion may contain only SUPPORTED claims. "
            "WEAK/DESIGN_HYPOTHESIS can appear only as labeled body/method hypotheses. "
            "MISSING/CONFLICTING/RUNTIME_UNVERIFIED must be written as missing evidence, "
            "runtime boundary, or validation need."
        )
        if body_gate.get("blocked_claims"):
            lines.append(
                "- Body blocked claims: "
                + "; ".join(
                    f"{item.get('claim_id')}={item.get('status')}"
                    for item in body_gate.get("blocked_claims", [])[:8]
                )
            )
        return "\n".join(lines) + "\n\n"

    @classmethod
    def _mutation_candidate_boundary_synthesis_context(cls, tool_results: list[dict]) -> str:
        """Emit explicit natural-language constraints for mutation candidate tables."""
        contexts: list[str] = []
        for result in tool_results:
            if result.get("tool_name") != "mutation_priority_score":
                continue
            if result.get("status") != "completed":
                continue
            payload = cls._safe_parse_json(str(result.get("result", "")))
            if not isinstance(payload, dict) or not payload:
                continue

            table_status = payload.get("candidate_table_status") or payload.get("summary", {}).get("candidate_table_status")
            boundary = payload.get("candidate_table_boundary") if isinstance(payload.get("candidate_table_boundary"), dict) else {}
            objective_gate = payload.get("objective_gate") if isinstance(payload.get("objective_gate"), dict) else {}
            experiment_rows = payload.get("experiment_design_table") if isinstance(payload.get("experiment_design_table"), list) else []

            missing = []
            if isinstance(objective_gate.get("missing_evidence"), list):
                missing.extend(map(str, objective_gate.get("missing_evidence", [])[:5]))
            row_upgrade_conditions: list[str] = []
            row_evidence_statuses: set[str] = set()
            row_priorities: set[str] = set()
            for row in experiment_rows[:8]:
                if not isinstance(row, dict):
                    continue
                if row.get("candidate_evidence_status"):
                    row_evidence_statuses.add(str(row.get("candidate_evidence_status")))
                if row.get("experiment_priority"):
                    row_priorities.add(str(row.get("experiment_priority")))
                conditions = row.get("blocked_upgrade_conditions")
                if isinstance(conditions, list):
                    row_upgrade_conditions.extend(str(item) for item in conditions[:3])
                row_missing = row.get("objective_missing_evidence")
                if isinstance(row_missing, list):
                    missing.extend(str(item) for item in row_missing[:3])

            if not table_status and not boundary and not experiment_rows:
                continue

            lines = ["Mutation candidate boundary constraints:"]
            lines.append(f"- Candidate table status: {table_status or 'unknown'}")
            if boundary:
                lines.append(f"- Boundary mode: {boundary.get('mode', 'unknown')}")
                lines.append(f"- Evidence level: {boundary.get('evidence_level', 'unknown')}")
                if boundary.get("no_wet_lab_claim") is True:
                    lines.append("- No wet-lab claim: true; do not write these candidates as validated improvements.")
                upgrade_requires = boundary.get("upgrade_requires")
                if isinstance(upgrade_requires, list) and upgrade_requires:
                    lines.append("- Upgrade requires: " + "; ".join(map(str, upgrade_requires[:5])))
            if row_evidence_statuses:
                lines.append("- Row evidence statuses: " + ", ".join(sorted(row_evidence_statuses)))
            if row_priorities:
                lines.append("- Row experiment priorities: " + ", ".join(sorted(row_priorities)))
            if missing:
                lines.append("- Missing evidence to mention: " + "; ".join(dict.fromkeys(missing[:8])))
            if row_upgrade_conditions:
                lines.append("- Row blocked upgrade conditions: " + "; ".join(dict.fromkeys(row_upgrade_conditions[:8])))
            if str(table_status or "").startswith("exploratory"):
                lines.append(
                    "- Report rule: describe mutation rows as Watch/P2-exploratory computational hypotheses only; "
                    "do not promote them to Go/P1, supported summary claims, or wet-lab-equivalent predictions."
                )
            contexts.append("\n".join(lines))

        return ("\n\n".join(contexts) + "\n\n") if contexts else ""

    @classmethod
    def _format_tool_result_for_synthesis(cls, result: dict) -> str:
        result_str = str(result.get("result", ""))
        if result.get("tool_name") != "structure_search_foldseek":
            return result_str[:1200]

        parsed = cls._safe_parse_json(result_str)
        if not parsed:
            return result_str[:1200]

        compact = {
            "found": parsed.get("found"),
            "status": parsed.get("status"),
            "backend": parsed.get("backend"),
            "database": parsed.get("database"),
            "results_count": parsed.get("results_count"),
            "warning": parsed.get("warning"),
            "query_structure": parsed.get("query_structure"),
            "top_results": (parsed.get("results") or [])[:5],
        }
        return json.dumps(compact, ensure_ascii=False, default=str)[:4000]

    def _load_relevant_skills(self, task: str) -> str:
        """Load domain skill content relevant to the task for synthesis context."""
        lower = task.lower()
        relevant = []

        if any(kw in lower for kw in ["ph", "酸性", "碱性", "最适", "耐酸", "耐碱", "酸化"]):
            skill = read_skill("ph_engineering")
            if skill:
                relevant.append(skill)

        if any(kw in lower for kw in ["thermostability", "耐热", "热稳定", "tm", "temperature", "温度"]):
            skill = read_skill("thermostability")
            if skill:
                relevant.append(skill)

        if any(kw in lower for kw in ["mutation", "突变", "mutant", "library", "saturation"]):
            skill = read_skill("mutation_design")
            if skill:
                relevant.append(skill)

        if any(kw in lower for kw in ["kcat", "km", "catalytic", "酶活", "activity", "specificity"]):
            skill = read_skill("enzyme_kinetics")
            if skill:
                relevant.append(skill)

        if any(kw in lower for kw in ["benchmark", "compare", "homolog", "family", "conservation", "比对", "同源"]):
            skill = read_skill("protein_benchmarking")
            if skill:
                relevant.append(skill)

        if any(kw in lower for kw in ["rosetta", "ddg", "ΔΔg", "delta delta g", "稳定能量", "更稳定", "不稳定"]):
            skill = read_skill("mutation_analysis")
            if skill:
                relevant.append(skill)

        if any(kw in lower for kw in ["design", "binder", "de novo", "backbone", "scaffold", "蛋白设计", "从头设计"]):
            skill = read_skill("protein_design")
            if skill:
                relevant.append(skill)

        if not relevant:
            return ""

        return "\n\n--- DOMAIN KNOWLEDGE FOR THIS TASK ---\n\n" + "\n\n".join(relevant)

    @staticmethod
    def _parse_residue_range(value: Any) -> tuple[int, int] | None:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return int(value[0]), int(value[1])
            except (TypeError, ValueError):
                return None
        text = str(value or "")
        match = re.search(r"(-?\d+)\s*[-–]\s*(-?\d+)", text)
        if not match:
            return None
        try:
            return int(match.group(1)), int(match.group(2))
        except ValueError:
            return None

    @classmethod
    def _mutation_direction_for_residue(cls, aa: str, site_label: str) -> tuple[str, str]:
        aa = (aa or "X").upper()[:1]
        if aa == "C":
            return "默认不改；先检查二硫键/金属配位，若确认游离再考虑 C→S/A", "Cys 可能维持二硫键、金属配位或局部氧化还原状态"
        if aa in {"G", "P"}:
            if aa == "G":
                return f"{site_label}A / {site_label}S（只在非紧密转角时）", "Gly 可能提供主链柔性；突变会刚化局部构象"
            return f"{site_label}A / {site_label}G（只在非关键构象锁时）", "Pro 可能固定环区或 cis/trans 构象；突变可能破坏折叠"
        if aa in {"D", "E", "K", "R", "H"}:
            if aa in {"D", "E"}:
                return f"{site_label}N / {site_label}Q / 保守 {site_label}{'E' if aa == 'D' else 'D'}", "电荷改变可能影响底物进入、pH 响应或盐桥网络"
            return f"{site_label}Q / {site_label}N / 保守 {site_label}{'R' if aa == 'K' else 'K'}", "正电荷残基可能参与底物/辅因子结合或盐桥"
        if aa in {"S", "T", "N", "Q", "Y"}:
            return f"{site_label}A / {site_label}V / 保守氢键替换", "极性残基可能参与水网络或底物识别，需避免破坏必要氢键"
        if aa in {"A", "V", "L", "I", "M", "F", "W"}:
            hydrophobic_choices = [candidate for candidate in ["V", "L", "I", "F"] if candidate != aa]
            volume_options = " / ".join(f"{site_label}{candidate}" for candidate in hydrophobic_choices[:3])
            small_option = "" if aa == "A" else f" / 小体积 {site_label}A"
            return f"{volume_options}{small_option}（按口袋空间选择）", "疏水体积调节可能影响口袋形状、产物释放或核心包装"
        return f"{site_label}A / {site_label}S / {site_label}V", "残基类型未可靠识别，只能做低置信探索"

    @classmethod
    def _build_exploratory_pdb_activity_sites(
        cls,
        structure_data: dict[str, Any],
        mapping_data: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Generate low-confidence PDB-coordinate site windows for deep PDB-only activity work."""
        mappings = mapping_data.get("mappings") if isinstance(mapping_data.get("mappings"), list) else []
        chain_counts: dict[str, int] = {}
        for row in mappings:
            if not isinstance(row, dict):
                continue
            chain_id = str(row.get("chain_id") or "A")
            chain_counts[chain_id] = chain_counts.get(chain_id, 0) + 1
        primary_chain = max(chain_counts, key=chain_counts.get) if chain_counts else ""

        residues: list[tuple[int, str]] = []
        if primary_chain:
            seen: set[int] = set()
            for row in mappings:
                if not isinstance(row, dict) or str(row.get("chain_id") or "A") != primary_chain:
                    continue
                try:
                    pos = int(row.get("pdb_residue_no"))
                except (TypeError, ValueError):
                    continue
                if pos in seen:
                    continue
                seen.add(pos)
                residues.append((pos, str(row.get("residue_aa") or row.get("residue_name") or "X")[:1].upper()))
            residues.sort(key=lambda item: item[0])

        if not residues:
            query_structure = structure_data.get("query_structure") if isinstance(structure_data.get("query_structure"), dict) else {}
            chains = query_structure.get("chains") if isinstance(query_structure.get("chains"), list) else []
            primary = None
            for chain in chains:
                if not isinstance(chain, dict):
                    continue
                if primary is None or int(chain.get("residue_count") or 0) > int(primary.get("residue_count") or 0):
                    primary = chain
            if primary:
                primary_chain = str(primary.get("chain_id") or "A")
                parsed_range = cls._parse_residue_range(primary.get("residue_range"))
                if parsed_range:
                    start, end = parsed_range
                    residues = [(pos, "X") for pos in range(min(start, end), max(start, end) + 1)]

        if len(residues) < 20:
            return []

        aa_rank = {
            "D": 95, "E": 93, "K": 91, "R": 89, "H": 87,
            "S": 82, "T": 80, "N": 78, "Q": 76, "Y": 72,
            "G": 70, "P": 68,
            "A": 62, "V": 60, "L": 58, "I": 56, "M": 54, "F": 52, "W": 50,
            "X": 35,
        }
        seq_len = len(residues)
        scored: list[tuple[float, int, str, str]] = []
        for index, (pos, aa) in enumerate(residues):
            aa = (aa or "X").upper()[:1]
            if aa == "C":
                continue
            relative = (index + 1) / max(seq_len, 1)
            if relative < 0.08 or relative > 0.92:
                continue
            central_bonus = 18.0 * (1.0 - abs(relative - 0.5) * 2.0)
            local_diversity_bonus = 0.0
            lo = max(0, index - 2)
            hi = min(seq_len, index + 3)
            window_aas = {item[1] for item in residues[lo:hi]}
            if len(window_aas) >= 3:
                local_diversity_bonus = 6.0
            score = aa_rank.get(aa, 35) + central_bonus + local_diversity_bonus
            category = (
                "charge_gate" if aa in {"D", "E", "K", "R", "H"}
                else "polar_network" if aa in {"S", "T", "N", "Q", "Y"}
                else "loop_flexibility" if aa in {"G", "P"}
                else "pocket_volume" if aa in {"A", "V", "L", "I", "M", "F", "W"}
                else "unknown_coordinate"
            )
            scored.append((score, pos, aa, category))
        scored.sort(key=lambda item: (-item[0], item[1]))

        category_order = ["charge_gate", "polar_network", "loop_flexibility", "pocket_volume", "unknown_coordinate"]
        category_quota = {
            "charge_gate": 2,
            "polar_network": 2,
            "loop_flexibility": 2,
            "pocket_volume": 2,
            "unknown_coordinate": 1,
        }
        category_label = {
            "charge_gate": "带电门控",
            "polar_network": "极性/水网络",
            "loop_flexibility": "柔性环/构象熵",
            "pocket_volume": "疏水体积/通道",
            "unknown_coordinate": "未知坐标",
        }

        rows: list[dict[str, str]] = []
        used: set[int] = set()
        category_counts: dict[str, int] = {}

        def _try_add_site(pos: int, aa: str, category: str, *, min_spacing: int) -> bool:
            if len(rows) >= 8:
                return False
            if any(abs(pos - prev) < min_spacing for prev in used):
                return False
            used.add(pos)
            category_counts[category] = category_counts.get(category, 0) + 1
            site_label = f"{aa}{pos}" if aa and aa != "X" else f"X{pos}"
            direction, risk = cls._mutation_direction_for_residue(aa, site_label)
            priority = "P2" if category in {"charge_gate", "polar_network", "loop_flexibility"} else "P3"
            logic = {
                "charge_gate": "带电/可质子化残基预筛；可能影响底物入口静电、pH 响应或盐桥网络",
                "polar_network": "极性网络预筛；可能影响水网络、底物识别或产物释放",
                "loop_flexibility": "环区柔性预筛；可能影响口袋开合或局部构象熵",
                "pocket_volume": "疏水体积预筛；可能影响口袋形状、通道宽度或核心包装",
                "unknown_coordinate": "PDB 坐标预筛；残基类型未可靠识别",
            }.get(category, "PDB 坐标预筛")
            rows.append({
                "priority": f"{priority}-{len(rows) + 1}",
                "window": f"{primary_chain or 'A'}:{pos - 2}-{pos + 2}",
                "site": f"{primary_chain or 'A'}:{site_label}",
                "category": category_label.get(category, category),
                "direction": direction,
                "logic": logic + "；尚未定位真实催化口袋",
                "risk": risk,
                "upgrade": "补齐 FASTA-PDB 编号、催化残基、底物/配体或口袋检测后，保留靠近口袋入口/二壳层且不碰催化核心的位点",
            })
            return True

        by_category: dict[str, list[tuple[float, int, str, str]]] = {category: [] for category in category_order}
        for item in scored:
            by_category.setdefault(item[3], []).append(item)

        # First pass: force mechanism diversity when the PDB sequence contains usable residue classes.
        made_progress = True
        while len(rows) < 8 and made_progress:
            made_progress = False
            for category in category_order:
                if len(rows) >= 8:
                    break
                if category_counts.get(category, 0) >= category_quota.get(category, 1):
                    continue
                for _score, pos, aa, item_category in by_category.get(category, []):
                    if pos in used:
                        continue
                    if _try_add_site(pos, aa, item_category, min_spacing=12):
                        made_progress = True
                        break

        # Second pass: fill remaining rows by score, relaxing spacing only if the chain is sparse.
        for min_spacing in (12, 8, 5):
            if len(rows) >= 8:
                break
            for _score, pos, aa, category in scored:
                if len(rows) >= 8:
                    break
                if pos in used:
                    continue
                _try_add_site(pos, aa, category, min_spacing=min_spacing)
        return rows

    def _build_fallback_report(self, task: str, tool_results: list[dict]) -> str:
        """Build a structured scientific report from tool results when LLM fails."""
        # Extract data from results
        seq_data = {}
        props_data = {}
        identity_data = {}
        annotation_data = {}
        objective_data = {}
        mutation_data = {}
        mutation_priority_data = {}
        mutation_scan_data = {}
        benchmark_data = {}
        enzyme_data = {}
        kcat_data = {}
        md_data = {}
        rosetta_data = {}
        design_data = []  # proteinmpnn / rfdiffusion / chroma results
        blast_sections = []
        blast_data = {}
        blast_submitted_data: dict[str, Any] = {}
        structure_data = {}
        mapping_data = {}
        numbering_data = {}
        site_feature_data = {}
        failed_tool_data: list[dict[str, Any]] = []
        submitted_tool_data: list[dict[str, Any]] = []
        task_evidence = classify_task_evidence(tool_results)
        scientific_result_ids = {id(item) for item in task_evidence["scientific_evidence"]}
        decision_status_tools = {"enzyme_identity_profile", "enzyme_objective_module_plan", "residue_numbering_gate"}
        # Reports must remain valid for every uploaded structure; never bake a
        # benchmark filename into scientific boundary text.
        structure_display_name = self._extract_attached_file_name(task) or "uploaded PDB"

        for r in tool_results:
            result_str = str(r.get("result", ""))
            tool = r["tool_name"]
            status = r["status"]
            # A Celery SUCCESS wrapper around a tool-level blocked/failed
            # payload is not evidence. Treat it as blocked everywhere below,
            # including report section extraction.
            if status == "completed" and tool not in decision_status_tools and id(r) not in scientific_result_ids:
                status = "blocked"

            if tool == "predict_properties" and status == "completed":
                props_data = self._safe_parse_json(result_str)
            elif tool == "annotation_bundle" and status == "completed":
                annotation_data = self._safe_parse_json(result_str)
            elif tool == "enzyme_identity_profile" and status == "completed":
                identity_data = self._safe_parse_json(result_str)
            elif tool == "enzyme_objective_module_plan" and status == "completed":
                objective_data = self._safe_parse_json(result_str)
            elif tool == "mutation_scan" and status == "completed":
                mutation_scan_data = self._safe_parse_json(result_str)
            elif tool == "mutation_priority_score" and status == "completed":
                mutation_priority_data = self._safe_parse_json(result_str)
            elif tool == "protein_benchmark" and status == "completed":
                benchmark_data = self._safe_parse_json(result_str)
            elif tool == "enzyme_function" and status == "completed":
                enzyme_data = self._safe_parse_json(result_str)
            elif tool == "kcat_predict" and status == "completed":
                kcat_data = self._safe_parse_json(result_str)
            elif tool == "gromacs_md" and status == "completed":
                md_data = self._safe_parse_json(result_str)
            elif tool == "structure_search_foldseek" and status == "completed":
                structure_data = self._safe_parse_json(result_str)
            elif tool == "residue_mapping_sifts" and status == "completed":
                mapping_data = self._safe_parse_json(result_str)
            elif tool == "residue_numbering_gate" and status == "completed":
                numbering_data = self._safe_parse_json(result_str)
            elif tool == "build_site_structure_function_features" and status == "completed":
                site_feature_data = self._safe_parse_json(result_str)
            elif tool == "rosetta_ddg" and status == "completed":
                rosetta_data = self._safe_parse_json(result_str)
            elif tool in ("proteinmpnn_design", "rfdiffusion_design", "chroma_design") and status == "completed":
                design_data.append({"tool": tool, "data": self._safe_parse_json(result_str)})
            elif tool == "blast_search" and status == "completed":
                blast_data = self._safe_parse_json(result_str)
                blast_sections.append(f"```\n{self._sanitize_uploaded_metadata_text(result_str, limit=500)}\n```\n")
            elif tool == "blast_search" and status == "submitted":
                blast_submitted_data = self._safe_parse_json(result_str)
            if status == "submitted":
                submitted_tool_data.append({
                    "tool": tool,
                    "status": status,
                    "payload": self._safe_parse_json(result_str),
                    "raw": self._sanitize_uploaded_metadata_text(result_str, limit=500),
                })
            elif status != "completed":
                failed_tool_data.append({
                    "tool": tool,
                    "status": status,
                    "payload": self._safe_parse_json(result_str),
                    "raw": self._sanitize_uploaded_metadata_text(result_str, limit=500),
                })

        # Candidate table semantics come from mutation_priority_score.  A later
        # mutation_scan is a broad substitution scan and must not erase ranked
        # experiment rows already generated by mutation_priority_score.
        mutation_data = mutation_priority_data or mutation_scan_data

        # Queued/background jobs remain receipts in this report.  Claim gates
        # consume only terminal, usable tool payloads and therefore cannot turn
        # a submitted BLAST/MD/InterPro job into current scientific evidence.
        claim_audit = self._build_claim_audit(task_evidence["scientific_evidence"])
        summary_gate = claim_audit.get("summary_gate", {})
        body_gate = claim_audit.get("body_gate", {})

        has_uploaded_structure_evidence = bool(structure_data or mapping_data or numbering_data)

        def _first_screen_summary() -> list[str]:
            summary: list[str] = []
            mutation_rows_raw = []
            if isinstance(mutation_data, dict):
                raw_rows = mutation_data.get("experiment_design_table")
                if isinstance(raw_rows, list):
                    mutation_rows_raw = [row for row in raw_rows if isinstance(row, dict)]
                if not mutation_rows_raw:
                    for key in ("tier_1_candidates", "tier_2_candidates"):
                        rows = mutation_data.get(key)
                        if isinstance(rows, list):
                            mutation_rows_raw.extend(row for row in rows if isinstance(row, dict))

            table_status = ""
            identity_gate = {}
            objective_gate = {}
            if isinstance(mutation_data, dict):
                summary_data = mutation_data.get("summary", {})
                table_status = str(
                    mutation_data.get("candidate_table_status")
                    or (summary_data.get("candidate_table_status") if isinstance(summary_data, dict) else "")
                    or ""
                )
                identity_gate = mutation_data.get("identity_gate", {}) if isinstance(mutation_data.get("identity_gate"), dict) else {}
                objective_gate = mutation_data.get("objective_gate", {}) if isinstance(mutation_data.get("objective_gate"), dict) else {}

            identity_blocked = (
                table_status == "blocked_by_identity_gate"
                or str(identity_gate.get("status") or "").lower() == "blocked"
                or str(identity_data.get("identity_status") or "").lower() in {"unresolved", "unknown"}
            )
            objective_blocked = (
                str(objective_gate.get("status") or objective_data.get("status") or "").lower()
                in {"blocked", "failed"}
            )
            can_order = (
                table_status == "ready"
                and bool(mutation_rows_raw)
                and not identity_blocked
                and not objective_blocked
            )

            if can_order:
                summary.append(f"- **能否下单**：可以进入单点验证设计；本轮候选数={len(mutation_rows_raw)}，仍需 WT 同批实验确认。\n")
            elif mutation_data:
                reason = "身份/编号门控未通过" if identity_blocked else "目标证据或候选表门控未通过"
                summary.append(f"- **能否下单**：不能直接下单；{reason}。\n")
            else:
                summary.append("- **能否下单**：当前没有候选表门控结果，不能直接下单。\n")

            # Keep formal ordering and coordinate-derived exploration separate. An unresolved
            # identity gate must not erase useful structure-local hypotheses from the report.
            if mutation_data:
                summary.append(
                    f"- **候选计数**：正式候选={len(mutation_rows_raw) if table_status == 'ready' and not identity_blocked else 0}；"
                    f"探索性候选={len(mutation_rows_raw) if str(table_status).startswith('exploratory') else 0}；"
                    "探索性候选证据等级=computational_hypothesis。\n"
                )

            evidence_bits: list[str] = []
            if structure_data:
                query_structure = structure_data.get("query_structure", {}) if isinstance(structure_data, dict) else {}
                residues = query_structure.get("total_residues") or structure_data.get("total_residues")
                if residues:
                    evidence_bits.append(f"上传结构已解析（{residues} aa）")
                else:
                    evidence_bits.append("上传结构已解析")
            if mapping_data:
                mapping_status = mapping_data.get("source") or mapping_data.get("status") or "编号映射结果"
                evidence_bits.append(f"编号映射={mapping_status}")
            if props_data:
                length = props_data.get("length")
                evidence_bits.append(f"理化性质基线{'（' + str(length) + ' aa）' if length else ''}")
            if kcat_data:
                evidence_bits.append("kcat 为启发式背景")
            if submitted_tool_data:
                evidence_bits.append("存在后台任务未完成")
            summary.append(f"- **主要证据**：{'；'.join(evidence_bits[:5]) if evidence_bits else '仅有用户请求，尚无可用工具证据'}。\n")

            completed_names = {
                str(item.get("tool_name"))
                for item in tool_results
                if str(item.get("status") or "") == "completed"
            }
            pending_names = {
                str(item.get("tool_name"))
                for item in tool_results
                if str(item.get("status") or "") in {"submitted", "running"}
            }
            if pending_names:
                summary.append(
                    "- **本轮变化**：没有可升级的新证据；后台工具仍未完成（"
                    f"{', '.join(sorted(pending_names))}），当前结果不能视为最终结论。\n"
                )
            elif objective_data and isinstance(objective_data, dict) and objective_data.get("status") == "blocked":
                summary.append(
                    "- **本轮变化**：工具结果已完成，但目标门控仍为 blocked；"
                    "在补齐目标实验基线前，候选不会升级或改变。\n"
                )
            elif completed_names:
                summary.append(
                    "- **本轮变化**：本轮工具均已完成；如输入指纹和实验上下文未变化，"
                    "重复运行将保持相同候选与证据等级。\n"
                )

            gaps: list[str] = []
            identity_status = identity_data.get("identity_status") if isinstance(identity_data, dict) else None
            if identity_status and str(identity_status).lower() not in {"identified", "ready", "confirmed"}:
                gaps.append(f"酶身份={identity_status}")
            numbering = identity_data.get("numbering", {}) if isinstance(identity_data, dict) else {}
            if isinstance(numbering, dict):
                numbering_status = numbering.get("status")
                if numbering_status and str(numbering_status).lower() not in {"ready", "confirmed"}:
                    gaps.append(f"编号={numbering_status}")
            objective_missing = []
            if isinstance(objective_data, dict):
                objective_missing = objective_data.get("missing_evidence", []) if isinstance(objective_data.get("missing_evidence"), list) else []
            if not objective_missing and isinstance(objective_gate, dict):
                objective_missing = (
                    objective_gate.get("missing_evidence", [])
                    if isinstance(objective_gate.get("missing_evidence"), list)
                    else []
                )
            if objective_missing:
                gaps.extend(str(item) for item in objective_missing[:3])
            if submitted_tool_data:
                gaps.append("后台任务需要轮询终态")
            if not gaps and not can_order:
                gaps.append("缺少身份、编号、催化/关键位点或目标 assay 的完整门控证据")
            summary.append(f"- **主要缺口**：{'；'.join(dict.fromkeys(gaps[:6])) if gaps else '暂无阻断缺口，但突变收益仍需湿实验确认'}。\n")

            if can_order:
                summary.append("- **下一步**：按 P1/P2 单点构建，WT 同批测比活力、动力学和稳定性，再判断是否组合。\n")
            else:
                summary.append("- **下一步**：先补齐 FASTA/同源身份、催化/保护位点、编号映射和目标实验基线，再生成可执行突变表。\n")
            return summary

        lines = ["# 酶蛋白工程分析报告\n"]
        lines.append("## 任务理解\n")
        lines.append(f"- 用户目标：{self._display_task_summary(task)}\n")
        lines.append("- 报告边界：本报告只整合本轮已完成工具输出；失败、未运行或缺证据的内容不会写成确定结论。\n")
        lines.extend(_first_screen_summary())
        lines.append("\n")

        tool_role_labels = {
            "structure_search_foldseek": "上传结构解析/结构同源检索",
            "residue_mapping_sifts": "残基编号映射",
            "residue_numbering_gate": "编号门控",
            "build_site_structure_function_features": "位点结构-功能特征表",
            "predict_properties": "理化性质基线",
            "annotation_bundle": "家族/功能/位点注释证据",
            "enzyme_identity_profile": "酶身份与保护位点画像",
            "enzyme_objective_module_plan": "目标模块门控",
            "protein_benchmark": "家族与保守性背景",
            "enzyme_function": "EC/酶类预测背景",
            "mutation_priority_score": "突变候选排序",
            "mutation_scan": "候选突变扫描",
            "protssn_score": "突变效应辅助评分",
            "blast_search": "序列同源检索",
            "kcat_predict": "kcat 启发式估算",
            "gromacs_md": "MD 稳定性/柔性验证",
            "rosetta_ddg": "突变 ΔΔG 辅助验证",
        }
        tool_evidence_layers = {
            "structure_search_foldseek": "输入/结构证据",
            "residue_mapping_sifts": "编号证据",
            "residue_numbering_gate": "编号门控",
            "build_site_structure_function_features": "结构几何特征",
            "predict_properties": "背景基线",
            "annotation_bundle": "身份/功能证据",
            "enzyme_identity_profile": "身份/保护位点门控",
            "enzyme_objective_module_plan": "目标门控",
            "protein_benchmark": "家族/保守性背景",
            "enzyme_function": "功能预测背景",
            "mutation_priority_score": "候选门控/排序",
            "mutation_scan": "候选辅助扫描",
            "protssn_score": "突变效应辅助评分",
            "blast_search": "序列同源证据",
            "kcat_predict": "启发式动力学背景",
            "gromacs_md": "结构动态验证",
            "rosetta_ddg": "稳定性辅助验证",
        }

        def _tool_report_usage(tool_name: str, status: str, payload: dict[str, Any]) -> str:
            if status == "submitted":
                return "后台任务已提交；当前不作为完成证据"
            if status != "completed":
                return "只记录失败/阻断原因，不进入科学结论"
            if isinstance(payload, dict) and payload.get("report_boundary") and tool_name in {
                "structure_search_foldseek",
                "residue_mapping_sifts",
                "build_site_structure_function_features",
                "predict_properties",
                "annotation_bundle",
                "enzyme_function",
                "protein_benchmark",
            }:
                capability = payload.get("capability_status")
                prefix = f"{capability}；" if capability else ""
                return prefix + str(payload.get("report_boundary"))
            if tool_name == "kcat_predict":
                return "启发式背景；不能证明比活力或突变增益"
            if tool_name == "blast_search":
                return "完成后可支持序列同源/家族判断；与弱结构命中冲突时优先"
            if tool_name in {"mutation_priority_score", "mutation_scan", "protssn_score"}:
                table_status = payload.get("candidate_table_status") if isinstance(payload, dict) else None
                if table_status:
                    return f"候选相关输出；受 candidate_table_status={table_status} 约束"
                return "候选相关输出；必须受身份、编号和目标门控约束"
            if tool_name in {"structure_search_foldseek", "residue_mapping_sifts", "residue_numbering_gate"}:
                return "支撑结构/编号边界；不能单独确认酶身份"
            if tool_name in {"enzyme_identity_profile", "enzyme_objective_module_plan"}:
                return "决定保护位点、目标证据缺口和候选表是否放行"
            return "作为对应章节的背景或事实来源"

        if tool_results:
            lines.append("## 工具来源说明\n\n")
            lines.append("| 工具 | 状态 | 作用 | 证据层级 | 报告用途 |\n")
            lines.append("|---|---|---|---|---|\n")
            for result in tool_results[:20]:
                tool_name = str(result.get("tool_name") or "unknown")
                status = str(result.get("status") or "unknown")
                if status == "completed" and tool_name not in decision_status_tools and id(result) not in scientific_result_ids:
                    status = "blocked"
                payload = self._safe_parse_json(str(result.get("result", "")))
                usage = _tool_report_usage(tool_name, status, payload)
                lines.append(
                    "| {tool} | {status} | {role} | {layer} | {usage} |\n".format(
                        tool=tool_name.replace("|", "/"),
                        status=status.replace("|", "/"),
                        role=tool_role_labels.get(tool_name, "工具输出").replace("|", "/"),
                        layer=tool_evidence_layers.get(tool_name, "未分类").replace("|", "/"),
                        usage=self._sanitize_uploaded_metadata_text(usage, limit=160).replace("|", "/"),
                    )
                )
            lines.append("- **解释规则**：completed 才能进入事实层；submitted 只表示后台任务已提交；failed/blocked 只作为失败原因和补证据需求。\n\n")

        def _mutation_experiment_rows() -> list[dict]:
            experiment_rows = mutation_data.get("experiment_design_table", [])
            if experiment_rows:
                return experiment_rows
            tier1 = mutation_data.get("tier_1_candidates", [])
            tier2 = mutation_data.get("tier_2_candidates", [])
            return [
                {
                    "experiment_priority": c.get("experiment_priority", "P?"),
                    "position": c.get("position"),
                    "wild_type": c.get("wild_type"),
                    "recommended_mutations": [
                        m.get("mutation")
                        for m in c.get("recommended_mutations", [])
                        if isinstance(m, dict)
                    ],
                    "mutation_logic": c.get("logic", "candidate"),
                    "expected_effect": c.get("expected_effect", "需实验确认"),
                    "risk_flags": c.get("risk_flags", []),
                    "candidate_evidence_status": c.get("candidate_evidence_status"),
                    "calibration_evidence_status": c.get("calibration_evidence_status"),
                    "user_position": c.get("user_position") or c.get("position"),
                    "pdb_position": c.get("pdb_position"),
                    "uniprot_position": c.get("uniprot_position"),
                    "numbering_status": c.get("numbering_status"),
                    "structure_feature_status": c.get("structure_feature_status"),
                    "ca_b_factor": c.get("ca_b_factor"),
                    "nearest_catalytic_distance_ca_angstrom": c.get("nearest_catalytic_distance_ca_angstrom"),
                    "contact_count_ca_8a": c.get("contact_count_ca_8a"),
                    "ca_contact_environment": c.get("ca_contact_environment"),
                    "secondary_structure": c.get("secondary_structure"),
                    "secondary_structure_source": c.get("secondary_structure_source"),
                    "rel_sasa": c.get("rel_sasa"),
                    "residue_sasa_angstrom2": c.get("residue_sasa_angstrom2"),
                    "rel_sasa_status": c.get("rel_sasa_status"),
                    "pocket_channel_interface_status": c.get("pocket_channel_interface_status"),
                    "nonpolymer_proximity_status": c.get("nonpolymer_proximity_status"),
                    "nearest_nonpolymer_heteroatom_distance_angstrom": c.get("nearest_nonpolymer_heteroatom_distance_angstrom"),
                    "nearest_nonpolymer_component_id": c.get("nearest_nonpolymer_component_id"),
                    "nearest_nonpolymer_component_position": c.get("nearest_nonpolymer_component_position"),
                    "nonpolymer_component_ids_within_4a": c.get("nonpolymer_component_ids_within_4a", []),
                    "phi_deg": c.get("phi_deg"),
                    "psi_deg": c.get("psi_deg"),
                    "backbone_torsion_status": c.get("backbone_torsion_status"),
                    "backbone_torsion_reason": c.get("backbone_torsion_reason"),
                    "backbone_torsion_source": c.get("backbone_torsion_source"),
                    "structure_feature_risk_flags": c.get("structure_feature_risk_flags", []),
                    "experiment_action": c.get("experiment_action"),
                    "blocked_upgrade_conditions": c.get("blocked_upgrade_conditions", []),
                }
                for c in (tier1 + tier2)[:12]
            ]

        def _format_site(row: dict) -> str:
            wild_type = row.get("wild_type", "")
            position = row.get("position", "?")
            return f"{wild_type}{position}"

        def _format_mutations(row: dict) -> str:
            mutations = row.get("recommended_mutations", [])
            return ", ".join(map(str, mutations[:3])) if isinstance(mutations, list) and mutations else "—"

        def _format_risk(row: dict) -> str:
            risk_flags = row.get("risk_flags", [])
            return "；".join(map(str, risk_flags[:3])) if isinstance(risk_flags, list) and risk_flags else "需实验确认"

        def _format_optional_position(row: dict, key: str) -> str:
            value = row.get(key)
            return str(value) if value not in {None, ""} else "未映射"

        def _format_structure_feature_value(value: Any, *, digits: int = 1) -> str:
            if isinstance(value, (int, float)):
                return f"{value:.{digits}f}"
            return "NA"

        def _format_structure_features(row: dict) -> str | None:
            if row.get("structure_feature_status") != "available":
                return None
            risk_flags = row.get("structure_feature_risk_flags", [])
            risk_text = (
                "；".join(map(str, risk_flags[:3]))
                if isinstance(risk_flags, list) and risk_flags
                else "未见结构特征风险标记"
            )
            return (
                "CA B-factor="
                f"{_format_structure_feature_value(row.get('ca_b_factor'))}；"
                "最近催化CA距离="
                f"{_format_structure_feature_value(row.get('nearest_catalytic_distance_ca_angstrom')) if row.get('nearest_catalytic_distance_ca_angstrom') is not None else 'NA（无可靠催化位点）'} A；"
                "8A CA接触数="
                f"{_format_structure_feature_value(row.get('contact_count_ca_8a'), digits=0)}；"
                f"CA接触环境={row.get('ca_contact_environment') or 'NA'}；"
                f"二级结构={row.get('secondary_structure') or 'unknown'}；"
                f"relSASA={row.get('rel_sasa') if isinstance(row.get('rel_sasa'), (int, float)) else (row.get('rel_sasa_status') or 'not_computed')}；"
                f"口袋/通道={row.get('pocket_channel_interface_status') or 'not_computed'}；"
                "最近非聚合HETATM距离="
                f"{_format_structure_feature_value(row.get('nearest_nonpolymer_heteroatom_distance_angstrom'))} A"
                f"（{row.get('nearest_nonpolymer_component_id') or row.get('nonpolymer_proximity_status') or 'not_available'}）；"
                f"主链phi/psi={row.get('phi_deg') if isinstance(row.get('phi_deg'), (int, float)) else 'NA'}"
                f"/{row.get('psi_deg') if isinstance(row.get('psi_deg'), (int, float)) else 'NA'}"
                f"（{row.get('backbone_torsion_status') or 'not_computed'}）；"
                f"结构风险={risk_text}"
            )

        def _format_experiment_action(row: dict) -> str:
            return str(row.get("experiment_action") or "构建单点突变体；与 WT 同批表达纯化；按目标性质做主实验，并复测活性、稳定性和可溶性。")

        def _format_upgrade_conditions(row: dict) -> str:
            conditions = row.get("blocked_upgrade_conditions", [])
            return "；".join(map(str, conditions[:3])) if isinstance(conditions, list) and conditions else "直接湿实验数据和编号/目标证据补齐前不得升级"

        mutation_rows = _mutation_experiment_rows() if mutation_data else []
        if has_uploaded_structure_evidence:
            lines.append("## 输入与结构证据\n\n")
            if structure_data:
                query_structure = structure_data.get("query_structure") if isinstance(structure_data.get("query_structure"), dict) else {}
                chains = query_structure.get("chains") if isinstance(query_structure, dict) else []
                lines.append(f"- **Foldseek/结构解析状态**：{structure_data.get('status', 'N/A')}；后端={structure_data.get('backend', 'N/A')}；数据库={structure_data.get('database', 'N/A')}。\n")
                lines.append(f"- **同源命中数**：{structure_data.get('results_count', 0)}；found={structure_data.get('found', False)}。\n")
                if isinstance(query_structure, dict) and query_structure:
                    lines.append(
                        f"- **上传结构摘要**：链数={query_structure.get('chain_count', 'N/A')}；"
                        f"残基数={query_structure.get('total_residues', 'N/A')}；"
                        f"原子数={query_structure.get('total_atoms', 'N/A')}。\n"
                    )
                if isinstance(chains, list) and chains:
                    chain_bits = []
                    for item in chains[:6]:
                        if not isinstance(item, dict):
                            continue
                        chain_bits.append(
                            f"链{item.get('chain_id', '?')}:{item.get('residue_count', '?')} aa"
                            f"({item.get('residue_range', 'range N/A')})"
                        )
                    if chain_bits:
                        lines.append(f"- **链级摘要**：{'；'.join(chain_bits)}。\n")
                nonpolymer_components = (
                    query_structure.get("nonpolymer_components")
                    if isinstance(query_structure, dict) and isinstance(query_structure.get("nonpolymer_components"), list)
                    else []
                )
                if nonpolymer_components:
                    component_bits = [
                        f"{item.get('component_id', '?')}链{item.get('chain_id', '?')}"
                        for item in nonpolymer_components[:12]
                        if isinstance(item, dict)
                    ]
                    if component_bits:
                        lines.append(f"- **非聚合组分**：{'；'.join(component_bits)}（不计入蛋白链和序列映射）。\n")
                top_hits = structure_data.get("results") if isinstance(structure_data.get("results"), list) else []
                if top_hits:
                    hit_bits = []
                    top_tm_scores: list[float] = []
                    for hit in top_hits[:3]:
                        if not isinstance(hit, dict):
                            continue
                        tm_value = hit.get("aligned_tm_score", hit.get("tm_score"))
                        try:
                            top_tm_scores.append(float(tm_value))
                        except (TypeError, ValueError):
                            pass
                        hit_bits.append(
                            f"{hit.get('target', hit.get('pdb_id', 'hit'))}"
                            f"(TM={hit.get('aligned_tm_score', hit.get('tm_score', 'N/A'))}, "
                            f"E={hit.get('evalue', 'N/A')})"
                        )
                    if hit_bits:
                        lines.append(f"- **Top 同源结构**：{'；'.join(hit_bits)}。\n")
                    if top_tm_scores and max(top_tm_scores) < 0.30:
                        lines.append(
                            "- **结构同源证据等级**：弱。Top Foldseek TM-score < 0.30，"
                            "只能作为结构检索线索，不能单独支撑酶家族、催化残基或功能身份结论；"
                            "需等待序列同源、结构编号和人工机制复核。\n"
                        )
                if structure_data.get("warning"):
                    lines.append(f"- **结构检索警告**：{structure_data.get('warning')}\n")
                query_annotation = structure_data.get("query_rcsb_annotation")
                query_hits = (
                    query_annotation.get("hits")
                    if isinstance(query_annotation, dict) and isinstance(query_annotation.get("hits"), list)
                    else []
                )
                if query_hits:
                    lines.append("\n### 查询 PDB 直接注释（优先于结构同源）\n\n")
                    lines.append(
                        f"- **证据角色**：direct_query_entry_annotation；PDB={structure_data.get('query_pdb_id') or query_annotation.get('pdb_id', 'N/A')}；"
                        f"来源=RCSB Data API；状态={query_annotation.get('status', 'N/A')}。\n"
                    )
                    for hit in query_hits[:2]:
                        if not isinstance(hit, dict):
                            continue
                        lines.append(
                            f"- **官方标题/实体**：{hit.get('title') or 'N/A'}；{hit.get('entity_description') or 'N/A'}。\n"
                        )
                        ligands = hit.get("nonpolymer_entities") if isinstance(hit.get("nonpolymer_entities"), list) else []
                        ligand_bits = [
                            f"{item.get('component_id') or '?'}={item.get('name') or '名称未返回'}"
                            for item in ligands if isinstance(item, dict)
                        ]
                        if ligand_bits:
                            lines.append(f"- **查询条目非聚合配体**：{'；'.join(ligand_bits)}。\n")
                rcsb_annotations = structure_data.get("rcsb_annotations")
                rcsb_hits = (
                    rcsb_annotations.get("hits")
                    if isinstance(rcsb_annotations, dict) and isinstance(rcsb_annotations.get("hits"), list)
                    else []
                )
                if rcsb_hits:
                    lines.append("\n### RCSB/PDB 专业库命中注释\n\n")
                    lines.append(
                        f"- **注释来源**：RCSB Data API；状态={rcsb_annotations.get('status', 'N/A')}。"
                        f"这些是 Foldseek 命中模板的官方结构注释，不等同于 {structure_display_name} 已完成酶身份确认。\n\n"
                    )
                    lines.append("| PDB | 官方标题 | 聚合物实体 | 方法 | 分辨率 | 参考序列 |\n")
                    lines.append("|-----|----------|------------|------|--------|----------|\n")
                    for hit in rcsb_hits[:5]:
                        if not isinstance(hit, dict):
                            continue
                        refs = hit.get("reference_sequence_identifiers")
                        ref_bits = []
                        if isinstance(refs, list):
                            for ref in refs[:3]:
                                if not isinstance(ref, dict):
                                    continue
                                accession = ref.get("database_accession")
                                database_name = ref.get("database_name")
                                coverage = ref.get("entity_sequence_coverage")
                                if accession:
                                    ref_bits.append(
                                        f"{database_name or 'ref'}:{accession}"
                                        + (f" cov={coverage}" if coverage is not None else "")
                                    )
                        methods = hit.get("experimental_methods")
                        method_text = ", ".join(map(str, methods)) if isinstance(methods, list) else ""
                        lines.append(
                            f"| {hit.get('pdb_id', 'N/A')} | {hit.get('title', 'N/A')} | "
                            f"{hit.get('entity_description', 'N/A')} | "
                            f"{method_text or 'N/A'} | {hit.get('resolution', 'N/A')} | "
                            f"{'; '.join(ref_bits) or 'N/A'} |\n"
                        )
            if mapping_data or numbering_data:
                lines.append("\n## 结构同源与编号映射\n\n")
                if mapping_data:
                    lines.append(
                        f"- **SIFTS/编号映射状态**：found={mapping_data.get('found', 'N/A')}；"
                        f"source={mapping_data.get('source', 'N/A')}；"
                        f"mapping_count={mapping_data.get('mapping_count', 'N/A')}。\n"
                    )
                    mappings = mapping_data.get("mappings") if isinstance(mapping_data.get("mappings"), list) else []
                    if mappings:
                        preview = []
                        for item in mappings[:5]:
                            if not isinstance(item, dict):
                                continue
                            preview.append(
                                f"{item.get('chain_id', '?')}:{item.get('residue_aa', item.get('residue_name', '?'))}"
                                f"{item.get('pdb_residue_no', '?')}->UniProt {item.get('uniprot_position', 'N/A')}"
                            )
                        if preview:
                            lines.append(f"- **映射预览**：{'；'.join(preview)}。\n")
                    limitations = mapping_data.get("limitations")
                    if isinstance(limitations, list) and limitations:
                        lines.append(f"- **映射限制**：{'；'.join(map(str, limitations[:4]))}。\n")
                if numbering_data:
                    lines.append(
                        f"- **残基编号门控状态**：{numbering_data.get('status', 'N/A')}；"
                        f"user_confirmed={numbering_data.get('user_confirmed', 'N/A')}。\n"
                    )
                    if numbering_data.get("reason"):
                        lines.append(f"- **编号门控原因**：{numbering_data.get('reason')}\n")
            if site_feature_data:
                lines.append("\n## 位点结构-功能特征表\n\n")
                summary = site_feature_data.get("summary") if isinstance(site_feature_data.get("summary"), dict) else {}
                protected_count = summary.get("protected_count", 0)
                try:
                    protected_count = int(protected_count or 0)
                except (TypeError, ValueError):
                    protected_count = 0
                lines.append(
                    f"- **状态**：{site_feature_data.get('status', 'N/A')}；"
                    f"特征数={site_feature_data.get('feature_count', summary.get('feature_count', 'N/A'))}；"
                    f"CA 可用={summary.get('ca_available_count', 'N/A')}；"
                    f"已映射={summary.get('mapped_count', 'N/A')}；"
                    f"保护位点={summary.get('protected_count', 'N/A')}；"
                    f"非聚合HETATM={summary.get('nonpolymer_proximity_status', 'N/A')}；"
                    f"主链phi/psi={summary.get('backbone_torsion_status', 'N/A')}。"
                    "\n"
                )
                if site_feature_data.get("report_boundary"):
                    lines.append(f"- **解释边界**：{site_feature_data.get('report_boundary')}\n")
                features = site_feature_data.get("features") if isinstance(site_feature_data.get("features"), list) else []
                if features:
                    distance_header = "最近推断保护位点CA距离(A)" if protected_count else "催化位点距离(A)"
                    lines.append(f"| 位点 | WT | PDB编号 | UniProt | CA坐标 | B-factor | relSASA | {distance_header} | 非聚合HETATM距离(A) | phi/psi | 8A接触数 | CA环境 | 二级结构 | 风险 |\n")
                    lines.append("|------|----|---------|---------|--------|----------|---------|-------------------|-----------------------|---------|----------|--------|----------|------|\n")
                    for feature in features[:8]:
                        if not isinstance(feature, dict):
                            continue
                        coord = feature.get("ca_coord") if isinstance(feature.get("ca_coord"), dict) else {}
                        coord_text = (
                            f"{coord.get('x')},{coord.get('y')},{coord.get('z')}"
                            if coord else "无CA"
                        )
                        risks = feature.get("risk_flags")
                        risk_text = "；".join(map(str, risks[:3])) if isinstance(risks, list) and risks else "需人工复核"
                        catalytic_distance = feature.get('nearest_catalytic_distance_ca_angstrom', 'N/A')
                        if not protected_count and catalytic_distance in (None, "", "N/A"):
                            catalytic_distance = "NA（无可靠催化位点）"
                        lines.append(
                            f"| {feature.get('position', 'N/A')} | {feature.get('wild_type', 'N/A')} | "
                            f"{feature.get('pdb_position', 'N/A')} | {feature.get('uniprot_position', '未映射')} | "
                            f"{coord_text} | {feature.get('b_factor', 'N/A')} | "
                            f"{feature.get('rel_sasa', feature.get('rel_sasa_status', 'N/A'))} | "
                            f"{catalytic_distance} | "
                            f"{feature.get('nearest_nonpolymer_heteroatom_distance_angstrom', 'N/A')} "
                            f"{feature.get('nearest_nonpolymer_component_id', '')} | "
                            f"{feature.get('phi_deg', 'N/A')}/{feature.get('psi_deg', 'N/A')} | "
                            f"{feature.get('contact_count_ca_8a', 'N/A')} | "
                            f"{feature.get('ca_contact_environment', 'N/A')} | "
                            f"{feature.get('secondary_structure', 'unknown')} | "
                            f"{self._sanitize_uploaded_metadata_text(risk_text, limit=160).replace('|', '/')} |\n"
                        )
                lines.append("\n")
            # PDB geometry alone is never a candidate-generation authority.  The
            # former fallback emitted residue substitutions even when identity,
            # numbering, pocket evidence, or objective assays were unresolved.
            # Keep the geometry helper available for future review tooling, but
            # only expose rows after the independent candidate gate is ready.
            exploratory_sites: list[dict[str, Any]] = []
            if isinstance(mutation_data, dict):
                mutation_status = str(
                    mutation_data.get("candidate_table_status")
                    or (mutation_data.get("summary", {}).get("candidate_table_status")
                        if isinstance(mutation_data.get("summary"), dict) else "")
                    or ""
                )
                identity_ready = str(identity_data.get("identity_status") or "").lower() == "identified"
                guardrail = identity_data.get("guardrail") if isinstance(identity_data.get("guardrail"), dict) else {}
                identity_ready = identity_ready and str(guardrail.get("status") or "").lower() == "ready"
                candidate_objective_gate = (
                    mutation_data.get("objective_gate")
                    if isinstance(mutation_data.get("objective_gate"), dict)
                    else objective_data
                )
                objective_ready = (
                    isinstance(candidate_objective_gate, dict)
                    and str(candidate_objective_gate.get("status") or "").lower() == "ready"
                    and candidate_objective_gate.get("candidate_output_allowed") is True
                )
                if mutation_status == "ready" and identity_ready and objective_ready:
                    exploratory_sites = self._build_exploratory_pdb_activity_sites(structure_data, mapping_data)
            if not mutation_data:
                if blast_data or blast_submitted_data:
                    lines.append("\n## 序列级专业库检索（BLAST）\n\n")
                if blast_submitted_data:
                    lines.append(
                        "- **状态**：已提交后台专业库检索任务，当前报告不把 BLAST 结果写成已完成证据。\n"
                    )
                    lines.append(
                        f"- **任务 ID**：{blast_submitted_data.get('task_id', 'N/A')}；"
                        f"队列={blast_submitted_data.get('queue', 'N/A')}；"
                        f"状态查询={blast_submitted_data.get('status_url', 'N/A')}。\n"
                    )
                    lines.append(
                        "- **解释边界**：待任务完成并返回命中表后，才能用序列级同源证据修正 Foldseek 弱结构命中的家族判断；"
                        "submitted 状态只证明任务进入队列，不证明已获得 NCBI 结果。\n"
                    )
                if blast_data:
                    hits = blast_data.get("results") if isinstance(blast_data.get("results"), list) else []
                    if not hits and isinstance(blast_data.get("hits"), list):
                        hits = blast_data.get("hits")
                    lines.append(
                        f"- **数据库**：{blast_data.get('database', 'N/A')}；"
                        f"程序={blast_data.get('program', 'blastp')}；"
                        f"状态={blast_data.get('status', 'N/A')}；"
                        f"命中数={blast_data.get('results_count', len(hits))}。\n"
                    )
                    if hits:
                        lines.append("| Rank | 命中 | 注释 | E-value | Identity | Coverage |\n")
                        lines.append("|------|------|------|---------|----------|----------|\n")
                        for idx, hit in enumerate(hits[:8], start=1):
                            if not isinstance(hit, dict):
                                continue
                            hsps = hit.get("hsps") if isinstance(hit.get("hsps"), list) else []
                            best = hsps[0] if hsps and isinstance(hsps[0], dict) else {}
                            align_len = best.get("alignment_length")
                            q_from = best.get("query_from")
                            q_to = best.get("query_to")
                            coverage = f"{q_from}-{q_to} / {align_len} aa" if q_from and q_to and align_len else "N/A"
                            identity = best.get("identity_percent")
                            lines.append(
                                f"| {idx} | {hit.get('accession', hit.get('hit_id', 'N/A'))} | "
                                f"{hit.get('description') or hit.get('definition') or hit.get('hit_def', 'N/A')} | "
                                f"{best.get('e_value', hit.get('e_value', 'N/A'))} | "
                                f"{identity if identity is not None else 'N/A'}% | {coverage} |\n"
                            )
                        lines.append(
                            "\n- **解释规则**：序列级 BLAST 对酶家族/功能判断的权重高于弱结构折叠相似；"
                            "如果 BLAST 与 Foldseek 家族不一致，报告应把 Foldseek 命中降级为结构模板假设。\n"
                        )
                lines.append("\n## 当前不能下结论的事项\n\n")
                lines.append("- 当前没有序列级身份画像、催化残基、底物/反应条件、结构质量指标和候选打分工具结果，因此不能给出高置信具体突变或声称比活力会提升。\n")
                lines.append("- 上传 PDB 可用于后续提取链、口袋、二壳层和编号体系；但在活性位点和编号未确认前，不能把文件名、哈希或自动解析片段当作残基位点。\n")
                lines.append("- 如果目标是提高比活力，下一步应先确定酶家族/催化残基/底物结合口袋，再围绕口袋入口、通道和二壳层做单点假设，而不是直接改催化核心。\n\n")
                if exploratory_sites:
                    lines.append("## PDB坐标探索性位点预筛（低置信，不等于最终突变推荐）\n\n")
                    lines.append(f"- 下面位点只使用当前 {structure_display_name} 的链和残基编号，用于深度模式下的首轮人工审查/口袋定位优先级；它们不能直接等同于 UniProt、基因构建体或文献编号。\n")
                    lines.append("- 替换方向是按残基化学性质给出的探索性方向，不是模型预测增益；最终是否构建必须等催化核心、底物口袋、保守性和编号映射补齐后再筛。\n\n")
                    lines.append("| 优先级 | PDB窗口 | 代表位点 | 机制类别 | 探索性替换方向 | 结构逻辑 | 风险 | 升级条件 |\n")
                    lines.append("|--------|---------|----------|----------|----------------|----------|------|----------|\n")
                    for row in exploratory_sites:
                        lines.append(
                            f"| {row['priority']} | {row['window']} | {row['site']} | "
                            f"{row.get('category', 'PDB预筛')} | {row['direction']} | "
                            f"{row['logic']} | {row['risk']} | {row['upgrade']} |\n"
                        )
                    lines.append("\n")

        if submitted_tool_data:
            lines.append("## 后台任务状态\n\n")
            for item in submitted_tool_data[:8]:
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                task_id = payload.get("task_id", "N/A")
                status_url = payload.get("status_url", "N/A")
                queue = payload.get("queue", "N/A")
                lines.append(
                    f"- **{item.get('tool')}**：状态=submitted；task_id={task_id}；queue={queue}；status_url={status_url}。\n"
                )
            lines.append("- submitted 表示已进入后台 worker，不是完成结果；需要轮询任务终态后再把结果升级为科学证据。\n\n")

        if failed_tool_data:
            lines.append("## 工具执行结果与失败原因\n\n")
            for item in failed_tool_data[:8]:
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                reason = (
                    payload.get("error")
                    or payload.get("reason")
                    or payload.get("message")
                    or payload.get("status")
                    or item.get("raw")
                    or "未返回结构化失败原因"
                )
                reason = self._sanitize_uploaded_metadata_text(reason, limit=500)
                lines.append(f"- **{item.get('tool')}**：状态={item.get('status')}；原因/摘要={reason}。\n")
            lines.append("- 失败工具不作为科学证据；如果需要 MD、ΔΔG 或对接，应在运行环境和输入门控通过后重新提交。\n\n")

        strategy = mutation_data.get("strategy", {}) if isinstance(mutation_data, dict) else {}
        if isinstance(strategy, dict) and strategy:
            lines.append("## 改造策略及说明\n\n")
            lines.append(f"- **目标**：{strategy.get('objective', 'N/A')}\n")
            lines.append(f"- **设计原则**：{strategy.get('design_principle', 'N/A')}\n")
            for item in strategy.get("screening_logic", [])[:6]:
                lines.append(f"- **筛选逻辑**：{item}\n")
            lines.append("\n")

        mutation_core_lines: list[str] = []
        if mutation_data:
            report_lines = lines
            lines = mutation_core_lines
            is_blocked = mutation_data.get("status") == "blocked"
            priorities = {str(row.get("experiment_priority", "")) for row in mutation_rows}
            table_status = (
                mutation_data.get("candidate_table_status")
                or mutation_data.get("summary", {}).get("candidate_table_status")
                or ("blocked" if is_blocked else "candidate_hypotheses")
            )
            identity_gate = mutation_data.get("identity_gate", {})
            identity_blocked = (
                table_status == "blocked_by_identity_gate"
                or (
                    isinstance(identity_gate, dict)
                    and str(identity_gate.get("status") or "").lower() == "blocked"
                )
            )
            exploratory_table = str(table_status or "").startswith("exploratory")
            hard_identity_blocked = identity_blocked and not exploratory_table
            objective_gate = mutation_data.get("objective_gate", {})
            objective_blocked = (
                isinstance(objective_gate, dict)
                and str(objective_gate.get("status") or "").lower() in {"blocked", "failed"}
            )
            table_requires_upgrade = any(
                marker in str(table_status or "").lower()
                for marker in ("exploratory", "requires", "blocked")
            )
            current_decision = (
                "No-Go"
                if (is_blocked and not exploratory_table) or (not mutation_rows and not exploratory_table)
                else "Watch"
                if objective_blocked or table_requires_upgrade
                else ("Go" if "P1" in priorities else "Watch")
            )
            specified_reviews = [
                row for row in mutation_data.get("specified_mutation_reviews", [])
                if isinstance(row, dict)
            ]
            if specified_reviews:
                decision_labels = {
                    "watch_review": "Watch",
                    "no_go_protected_position": "No-Go",
                    "blocked_numbering_mismatch": "No-Go",
                }
                lines.append("## 用户指定突变复核\n\n")
                lines.append(
                    "- **解释边界**：这里复核用户点名突变，不等同于平台自动推荐；"
                    "只有编号、保护位点、目标 assay 和直接湿实验都通过后才能升级。\n"
                )
                lines.append("| 突变 | 决策 | 编号匹配 | 保护位点 | 权衡解释 | 主要风险 |\n")
                lines.append("|------|------|----------|----------|----------|----------|\n")
                for review in specified_reviews[:8]:
                    decision = decision_labels.get(
                        str(review.get("review_decision") or ""),
                        str(review.get("review_decision") or "Watch"),
                    )
                    risk_flags = review.get("risk_flags", [])
                    risk_text = "；".join(map(str, risk_flags[:3])) if isinstance(risk_flags, list) and risk_flags else "需实验确认"
                    tradeoff = str(review.get("tradeoff_interpretation") or "requires review")
                    lines.append(
                        "| {mutation} | {decision} | {match} | {protected} | {tradeoff} | {risk} |\n".format(
                            mutation=str(review.get("mutation") or "N/A").replace("|", "/"),
                            decision=decision.replace("|", "/"),
                            match=("是" if review.get("wild_type_match") is True else "否"),
                            protected=("是" if review.get("is_protected") is True else "否"),
                            tradeoff=self._sanitize_uploaded_metadata_text(tradeoff, limit=140).replace("|", "/"),
                            risk=self._sanitize_uploaded_metadata_text(risk_text, limit=160).replace("|", "/"),
                        )
                    )
                lines.append("\n")
            if hard_identity_blocked:
                lines.append("## 突变位点探索清单（未放行）\n\n")
                lines.append(f"- **当前决策**：{current_decision}\n")
                lines.append(f"- **主表状态**：{table_status}\n")
                lines.append("- **状态**：身份或残基编号门控未通过，本轮不输出具体突变候选表。\n")
                lines.append(
                    "- **原因**：在酶身份、催化/关键残基和编号映射未确认前，"
                    "表面电荷翻转或通用位点排序不能作为比活力改造建议。\n"
                )
                if isinstance(identity_gate, dict):
                    if identity_gate.get("identity_status"):
                        lines.append(f"- **身份状态**：{identity_gate.get('identity_status')}\n")
                    if identity_gate.get("reason"):
                        lines.append(f"- **门控说明**：{identity_gate.get('reason')}\n")
                lines.append("- **本轮输出**：0 个可排单候选；不生成任何突变候选清单。\n")
                lines.append(
                    "- **下一步**：完成序列同源/家族确认、催化位点确认和结构编号映射，"
                    "再围绕底物口袋入口、通道和二壳层生成候选。\n\n"
                )
            else:
                table_heading = (
                    "## 突变位点主表（实验排单）\n\n"
                    if table_status == "ready"
                    else "## 突变位点探索清单（不可直接排单）\n\n"
                )
                lines.append(table_heading)
                lines.append(f"- **当前决策**：{current_decision}\n")
                lines.append(f"- **主表状态**：{table_status}\n")
                if exploratory_table:
                    lines.append(
                        "- **状态说明**：这是 PDB 坐标探索性候选清单，已输出探索性候选；这不是正式候选表，"
                        "不能直接下单、不能进行组合设计，也不代表已确认酶身份或突变收益。\n"
                    )
                lines.append(
                    "- **结论边界**：本报告只把已运行工具输出转成实验排单假设；没有实验证据、实时运行证据或编号映射确认时，不写入确定结论。\n"
                )
                if is_blocked:
                    lines.append("- **状态**：blocked\n")
                    lines.append(f"- **原因**：{mutation_data.get('reason', 'candidate output is not allowed by gates')}\n")
            if isinstance(objective_gate, dict):
                missing = objective_gate.get("missing_evidence", [])
                if missing:
                    lines.append(f"- **目标证据缺口**：{'；'.join(map(str, missing[:4]))}\n")
            calibration_context = mutation_data.get("wet_lab_calibration_context")
            if isinstance(calibration_context, dict) and calibration_context:
                lines.append(
                    "- **湿实验校准背景**："
                    f"{calibration_context.get('evidence_level', 'computational_hypothesis')}；"
                    f"样本数={calibration_context.get('measured_variant_count', 0)}；"
                    f"命中率={calibration_context.get('hit_rate', '未计算')}。"
                    "这是项目/assay 级排序校准，不是下方具体候选的直接湿实验验证。\n"
                )
            if mutation_rows and not hard_identity_blocked:
                lines.append("\n| 优先级 | 位点 | 推荐突变 | 机制逻辑 | 主要风险 |\n")
                lines.append("|--------|------|----------|----------|----------|\n")
                for row in mutation_rows[:12]:
                    lines.append(
                        f"| {row.get('experiment_priority', 'P?')} | {_format_site(row)} | "
                        f"{_format_mutations(row)} | {row.get('mutation_logic', 'candidate')} | "
                        f"{_format_risk(row)} |\n"
                    )
            elif not hard_identity_blocked:
                lines.append("- 暂无可排单候选；补齐身份、编号、结构或目标实验证据后再生成位点表。\n")
            lines.append("\n")

            suggestion_lines: list[str] = []
            mutation_report_lines = lines
            lines = suggestion_lines

            if hard_identity_blocked:
                lines.append("## 探索性验证建议\n\n")
                lines.append(f"- 补齐独立序列同源或家族证据，确认 {structure_display_name} 的酶身份。\n")
                lines.append("- 确认催化残基、底物结合约束和 PDB/UniProt 编号关系。\n")
                lines.append("- 仅在上述门控通过后，重新生成口袋边缘和二壳层候选。\n\n")
            else:
                lines.append("## 探索性验证建议\n\n")
                if table_status == "ready":
                    lines.append("- **批次定位**：下列位点可进入单点验证排单，但仍需与 WT 同批验证。\n")
            if mutation_rows and not hard_identity_blocked:
                priority_groups: dict[str, list[str]] = {}
                for row in mutation_rows[:12]:
                    priority = str(row.get("experiment_priority", "P?"))
                    priority_groups.setdefault(priority, []).append(f"{_format_site(row)}:{_format_mutations(row)}")
                for priority in sorted(priority_groups):
                    priority_root = priority.split("-", 1)[0]
                    batch_name = (
                        {
                            "P1": "第一批单点验证",
                            "P2": "第二批机制互补单点",
                            "P3": "第三批组合前候选",
                        }.get(priority_root, "待定批次")
                        if table_status == "ready"
                        else "人工审查清单"
                    )
                    lines.append(f"- **{priority} {batch_name}**：{'; '.join(priority_groups[priority])}\n")
                if table_status == "ready":
                    lines.append("- **组合原则**：先验证单点；只有机制互补且单点数据通过后，才进入二点组合。\n")
                else:
                    lines.append("- **使用边界**：这些位点只能作为人工审查和补充计算输入；补齐编号、结构质量、保守性和 WT 热稳定性基线前，不应直接排实验批次。\n")
            elif not hard_identity_blocked:
                lines.append("- No-Go：当前没有足够证据排实验批次。\n")
            lines.append("\n")

            lines = mutation_report_lines

            lines.append("## 位点突变逻辑 / 风险 / 实验动作\n\n")
            if hard_identity_blocked:
                lines.append("- 本轮未生成位点级突变逻辑。身份、编号、催化/关键位点和目标 assay 证据未通过前，不把通用表面位点或启发式扫描结果写成突变建议。\n\n")
            elif exploratory_table:
                lines.append("- 下列为 PDB 坐标探索性位点解释，不是已验证的突变建议；催化位点未可靠确认时，距离字段仅作几何缺口提示。\n\n")
            if mutation_rows and not hard_identity_blocked:
                for row in mutation_rows[:12]:
                    lines.append(f"### {_format_site(row)} -> {_format_mutations(row)}\n\n")
                    lines.append(
                        f"- **编号**：用户={_format_optional_position(row, 'user_position')}；"
                        f"PDB={_format_optional_position(row, 'pdb_position')}；"
                        f"UniProt={_format_optional_position(row, 'uniprot_position')}\n"
                    )
                    lines.append(
                        f"- **证据/校准**：{row.get('candidate_evidence_status', '待确认')}；"
                        f"{row.get('calibration_evidence_status', 'not_calibrated')}\n"
                    )
                    structure_feature_text = _format_structure_features(row)
                    if structure_feature_text:
                        lines.append(
                            f"- **结构特征**：{structure_feature_text}。"
                            "这些字段仅来自 PDB CA 几何与编号映射，不能单独证明突变收益。\n"
                        )
                    lines.append(f"- **突变逻辑**：{row.get('mutation_logic', 'candidate')}\n")
                    lines.append(f"- **预期方向**：{row.get('expected_effect', '需实验确认')}\n")
                    lines.append(f"- **风险提示**：{_format_risk(row)}\n")
                    lines.append(f"- **实验动作**：{_format_experiment_action(row)}\n\n")
                    lines.append(f"- **升级条件**：{_format_upgrade_conditions(row)}\n\n")
            elif not hard_identity_blocked:
                lines.append("- **实验动作**：先补齐序列/结构编号、目标条件、底物和对照体系，再生成候选位点。\n\n")

            if suggestion_lines:
                suggestion_lines.append("- **Go**：仅当单点突变体在目标条件下重复实验优于 WT，且表达/可溶性/基础活性未明显下降时进入组合或放大验证。\n")
                suggestion_lines.append("- **Watch**：当前候选若仍属于计算/规则假设，只能作为人工审查清单，不能直接排实验批次。\n")
                suggestion_lines.append("- **No-Go**：候选命中催化/保守/配体或二硫键关键位点、编号映射冲突、目标证据缺失，或单点实验低于预设阈值时停止。\n\n")
                lines.extend(suggestion_lines)

        if mutation_data:
            lines = report_lines

        audit_appendix_lines: list[str] = []
        report_lines = lines
        lines = audit_appendix_lines

        lines.append("### 证据分层\n\n")
        lines.append("| 层级 | 状态 | 解读 |\n")
        lines.append("|------|------|------|\n")
        lines.append("| 已知事实 | 依赖工具输出 | 只使用本轮完成工具返回的直接值。 |\n")
        lines.append("| 分析推断 | 条件性 | 只作为基于工具输出的假设，不能等同实验结论。 |\n")
        lines.append("| 不确定项 | 存在 | 缺少序列、结构质量、文献、底物或 assay context 会限制置信度。 |\n")
        lines.append("| 湿实验验证 | 必需 | 任何突变、活性、稳定性或命中率结论都必须实验确认。 |\n\n")

        if claim_audit.get("claims"):
            lines.append("### 科学声明审计门控\n\n")
            lines.append(
                f"- **摘要/结论门控**：{summary_gate.get('status', 'N/A')} "
                f"(allowed={summary_gate.get('summary', {}).get('allowed_count', 0)}, "
                f"downgraded={summary_gate.get('summary', {}).get('downgraded_count', 0)}, "
                f"blocked={summary_gate.get('summary', {}).get('blocked_count', 0)})\n"
            )
            blocked_claims = summary_gate.get("blocked_claims", [])
            downgraded_claims = summary_gate.get("downgraded_claims", [])
            if downgraded_claims:
                lines.append("- **不得进入摘要/结论的降级声明**：\n")
                for item in downgraded_claims[:6]:
                    lines.append(f"  - {item.get('claim_id')}: {item.get('status')}\n")
            if blocked_claims:
                lines.append("- **被阻断为事实声明的内容**：\n")
                for item in blocked_claims[:6]:
                    lines.append(f"  - {item.get('claim_id')}: {item.get('status')}\n")
            if body_gate.get("blocked_claims"):
                lines.append("- **正文边界**：运行未验证或证据缺失的声明只能写成验证需求。\n")
            lines.append("\n")

        for section in blast_sections:
            lines.append("### 序列同源检索结果（BLAST）\n")
            lines.append(section)

        lines = report_lines

        # Properties section
        if props_data:
            lines.append("## Physicochemical Properties\n")
            lines.append(f"- **分子量**：{props_data.get('molecular_weight_kda', 'N/A')} kDa\n")
            lines.append(f"- **等电点 pI**：{props_data.get('isoelectric_point', 'N/A')}\n")
            lines.append(f"- **GRAVY**: {props_data.get('gravy', 'N/A')}\n")
            lines.append(f"- **稳定性指数判读**：{props_data.get('stability', 'N/A')}（不是热稳定性实验证据）\n")
            lines.append(f"- **序列长度**：{props_data.get('length', 'N/A')} aa\n\n")

        if identity_data:
            lines.append("## Enzyme Foundation Profile\n\n")
            family_candidates = identity_data.get("family_candidates", [])
            ec_candidates = identity_data.get("ec_candidates", [])
            key_residues = identity_data.get("key_residues", [])
            protected_positions = identity_data.get("protected_positions", [])
            if family_candidates and isinstance(family_candidates[0], dict):
                top_family = family_candidates[0]
                lines.append(f"- **家族候选**：{top_family.get('name', 'N/A')}\n")
                lines.append(f"- **家族置信度**：{top_family.get('confidence', 'N/A')}\n")
            if ec_candidates and isinstance(ec_candidates[0], dict):
                top_ec = ec_candidates[0]
                lines.append(f"- **EC 候选**：{top_ec.get('ec', 'N/A')}（{top_ec.get('status', 'N/A')}）\n")
            lines.append(f"- **身份状态**：{identity_data.get('identity_status', 'N/A')}\n")
            numbering = identity_data.get("numbering", {})
            if isinstance(numbering, dict):
                lines.append(f"- **编号状态**：{numbering.get('status', 'N/A')}\n")
                lines.append(f"- **映射依据**：{numbering.get('mapping_basis', 'N/A')}\n")
            if protected_positions:
                lines.append(f"- **保护位点**：{protected_positions}\n")
            if key_residues:
                residue_bits = []
                for residue in key_residues[:8]:
                    if not isinstance(residue, dict):
                        continue
                    residue_bits.append(
                        f"{residue.get('residue', '?')}{residue.get('position', '?')} ({residue.get('role', 'key residue')})"
                    )
                if residue_bits:
                    lines.append(f"- **关键残基**：{', '.join(residue_bits)}\n")
            domains = identity_data.get("functional_domains", [])
            if domains:
                domain_bits = [
                    f"{item.get('name', 'domain')} ({item.get('accession', 'N/A')})"
                    for item in domains[:5] if isinstance(item, dict)
                ]
                if domain_bits:
                    lines.append(f"- **结构域**：{', '.join(domain_bits)}\n")
            cofactors = identity_data.get("cofactors", [])
            if cofactors:
                lines.append(f"- **辅因子**：{', '.join(map(str, cofactors))}\n")
            signal = identity_data.get("signal_peptide")
            if isinstance(signal, dict):
                lines.append(
                    f"- **信号肽**：{signal.get('has_signal_peptide', 'N/A')} "
                    f"（{signal.get('cleavage_site') or '未见切割位点'}）\n"
                )
            missing_evidence = identity_data.get("missing_evidence", [])
            if missing_evidence:
                lines.append(f"- **缺失证据**：{'；'.join(map(str, missing_evidence[:3]))}\n")
            conflicts = identity_data.get("conflicts", [])
            if conflicts:
                lines.append(f"- **证据冲突数**：{len(conflicts)}\n")
            lines.append("\n")

        if annotation_data and not identity_data:
            lines.append("## Enzyme Foundation Profile\n\n")
            coordinate = annotation_data.get("coordinate_system", {})
            protein = annotation_data.get("protein", {})
            lines.append(f"- **是否命中审校酶记录**：{annotation_data.get('query', {}).get('has_curated_enzyme', False)}\n")
            if isinstance(coordinate, dict):
                lines.append(f"- **坐标状态**：{coordinate.get('status', 'N/A')}\n")
            if isinstance(protein, dict) and protein.get("protein_name"):
                lines.append(f"- **蛋白名称**：{protein['protein_name']}\n")
            lines.append("\n")

        protected_from_identity = []
        if isinstance(identity_data, dict):
            protected_from_identity = identity_data.get("protected_positions", []) or []
        mutation_summary = mutation_data.get("summary", {}) if isinstance(mutation_data, dict) else {}
        never_mutate = mutation_summary.get("never_mutate_positions", []) if isinstance(mutation_summary, dict) else []
        identity_gate_for_protection = mutation_data.get("identity_gate", {}) if isinstance(mutation_data, dict) else {}
        protected_from_gate = (
            identity_gate_for_protection.get("protected_positions_from_profile", [])
            if isinstance(identity_gate_for_protection, dict)
            else []
        )
        if protected_from_identity or never_mutate or protected_from_gate:
            lines.append("## 保护位点\n\n")
            if protected_from_identity:
                lines.append(f"- **身份画像保护位点**：{protected_from_identity}\n")
            if protected_from_gate:
                lines.append(f"- **候选门控保护位点**：{protected_from_gate}\n")
            if never_mutate:
                lines.append(f"- **禁止突变位点**：{never_mutate}\n")
            lines.append("- **使用边界**：保护位点只在身份、编号和证据来源可追溯时作为禁改依据；inferred 编号不能冒充 UniProt 实证映射。\n\n")

        if objective_data:
            lines.append("## Objective Module Gate\n\n")
            lines.append(f"- **目标模块**：{objective_data.get('module', objective_data.get('objective', 'N/A'))}\n")
            objective_signals = objective_data.get("objective_signals", [])
            if isinstance(objective_signals, list) and objective_signals:
                lines.append(f"- **目标拆解**：{'；'.join(map(str, objective_signals))}\n")
            if objective_data.get("multi_objective") is True:
                lines.append("- **多目标门控**：是；候选排序必须同时满足各目标证据要求，不能按单一主目标解释。\n")
            objective_modules = objective_data.get("objective_modules", [])
            if isinstance(objective_modules, list) and objective_modules:
                lines.append("- **目标模块明细**：\n")
                for module_item in objective_modules[:5]:
                    if not isinstance(module_item, dict):
                        continue
                    module_name = module_item.get("module") or module_item.get("objective") or "N/A"
                    question = module_item.get("primary_question") or "N/A"
                    metrics = module_item.get("validation_metrics")
                    metric_text = "；".join(map(str, metrics[:4])) if isinstance(metrics, list) and metrics else "N/A"
                    lines.append(f"  - {module_name}：{question}；验证指标：{metric_text}\n")
            combined_required = objective_data.get("combined_required_evidence", [])
            if isinstance(combined_required, list) and combined_required:
                lines.append("- **合并证据要求**：\n")
                for item in combined_required[:6]:
                    lines.append(f"  - {item}\n")
            combined_metrics = objective_data.get("combined_validation_metrics", [])
            if isinstance(combined_metrics, list) and combined_metrics:
                lines.append(f"- **合并验证指标**：{'；'.join(map(str, combined_metrics[:8]))}\n")
            lines.append(f"- **状态**：{objective_data.get('status', 'N/A')}\n")
            lines.append(f"- **是否允许输出候选表**：{objective_data.get('candidate_output_allowed', False)}\n")
            question = objective_data.get("primary_question")
            if question:
                lines.append(f"- **核心问题**：{question}\n")
            missing = objective_data.get("missing_evidence", [])
            if missing:
                lines.append("- **缺失证据**：\n")
                for item in missing[:6]:
                  lines.append(f"  - {item}\n")
            forbidden = objective_data.get("forbidden_shortcuts", [])
            if forbidden:
                lines.append("- **禁止捷径**：\n")
                for item in forbidden[:4]:
                    lines.append(f"  - {item}\n")
            lines.append("\n")

        if mutation_core_lines:
            lines.extend(mutation_core_lines)

        # Benchmark section
        if benchmark_data and not mutation_data:
            lines.append("## 家族与保守性分析\n\n")
            family = benchmark_data.get("family", {})
            if family:
                lines.append(f"- **家族**：{family.get('name', 'Unknown')}\n")
                lines.append(f"- **EC**: {family.get('ec', 'N/A')}\n")
                lines.append(f"- **机制**：{family.get('mechanism', 'N/A')}\n\n")

            motifs_found = benchmark_data.get("family_motifs", [])
            if motifs_found:
                lines.append("### 保守模体\n\n")
                for m in motifs_found:
                    lines.append(f"- **{m.get('region', '?')}** ({m['pattern']}): {m.get('found_at', 'not found')}\n")
                lines.append("\n")

            known_successes = benchmark_data.get("known_engineering_successes", [])
            if known_successes:
                lines.append("### 同家族已知工程案例\n\n")
                for s in known_successes:
                    if isinstance(s, dict):
                        lines.append(f"- {s.get('mutation', '?')}: {s.get('effect', '?')} ({s.get('organism', '?')})\n")
                lines.append("\n")

        # Enzyme function section
        if enzyme_data and not mutation_data:
            lines.append("## 酶功能预测（EC 号）\n\n")
            predictions = enzyme_data.get("predictions", [])
            if predictions:
                lines.append("| # | EC 号 | 类型 | 置信度 | 名称 |\n")
                lines.append("|---|-----------|-------|------------|------|\n")
                for i, p in enumerate(predictions[:5]):
                    conf = p.get("confidence", "?")
                    lines.append(
                        f"| {i+1} | {p.get('ec_number', '?')} | {p.get('class', '?')} | "
                        f"{conf} | {p.get('name', '?')} |\n"
                    )
                lines.append("\n")
            lines.append(f"- **模型/方法**：{enzyme_data.get('model', 'N/A')}\n\n")

        # Kcat kinetics section
        if kcat_data and not mutation_data:
            lines.append("## kcat 估算的使用边界\n\n")
            kcat = kcat_data.get("predicted_kcat_s1")
            if kcat is not None:
                lines.append(f"- **估算 kcat**：{kcat:.4f} s⁻¹\n")
                lines.append(f"- **log10(kcat)**：{kcat_data.get('predicted_log10_kcat', 'N/A')}\n")
                lines.append(f"- **粗分类**：{kcat_data.get('enzyme_class', 'N/A')}\n")
                ci = kcat_data.get("confidence_interval_kcat_s1", [None, None])
                if ci[0] is not None:
                    lines.append(f"- **95% 区间**：{ci[0]:.4f} 至 {ci[1]:.4f} s⁻¹\n")
                lines.append("- **判读**：该结果只能作为启发式背景，不作为比活力、催化效率或突变收益证据。\n")
                lines.append(f"- **方法**：{kcat_data.get('method', 'N/A')}\n")
                lines.append("\n")

        # MD plan-only section
        if md_data:
            lines.append("## MD 执行计划（压缩）\n\n")
            lines.append(f"- **Status**: {md_data.get('status', 'N/A')}\n")
            lines.append(f"- **Real MD executed**: {md_data.get('is_real_md', 'N/A')}\n")
            if md_data.get("note"):
                lines.append(f"- **Note**: {md_data['note']}\n")
            review = md_data.get("protocol_review") or {}
            if isinstance(review, dict) and review:
                lines.append(f"- **Protocol review**: {review.get('status', 'available')}\n")
            plan = md_data.get("replicate_execution_plan") or {}
            tasks = plan.get("tasks") if isinstance(plan, dict) else []
            if tasks:
                lines.append("\n| Task | Variant | Replicate | Time (ns) | Force Field | Water |\n")
                lines.append("|------|---------|-----------|-----------|-------------|-------|\n")
                for task_item in tasks[:8]:
                    lines.append(
                        f"| {task_item.get('task_id', 'N/A')} | {task_item.get('variant', 'N/A')} | "
                        f"{task_item.get('replicate_index', 'N/A')} | {task_item.get('simulation_time_ns', 'N/A')} | "
                        f"{task_item.get('force_field', 'N/A')} | {task_item.get('water_model', 'N/A')} |\n"
                    )
                lines.append("\n")
            lines.append(
                "This chat response did not execute GROMACS inline. Submit the real MD run "
                "from the PDB workspace or background task runner to avoid blocking the chat stream.\n\n"
            )

        if rosetta_data:
            lines.append("## Rosetta ΔΔG 结果（压缩）\n\n")
            lines.append(f"- **Status**: {rosetta_data.get('status', 'N/A')}\n")
            lines.append(f"- **Real Rosetta executed**: {rosetta_data.get('is_real_rosetta', False)}\n")
            if rosetta_data.get("reason"):
                lines.append(f"- **Blocked reason**: {rosetta_data.get('reason')}\n")
            if rosetta_data.get("missing"):
                lines.append(f"- **Missing**: {', '.join(map(str, rosetta_data.get('missing', [])))}\n")
            if rosetta_data.get("note"):
                lines.append(f"- **Note**: {rosetta_data.get('note')}\n")
            lines.append("\n### ΔΔG Interpretation Thresholds\n\n")
            lines.append("| Range (kcal/mol) | Label | Interpretation |\n")
            lines.append("|------------------|-------|----------------|\n")
            lines.append("| <= -2.0 | strong_stabilizing | Strong stabilizing candidate; manual structural review required. |\n")
            lines.append("| (-2.0, -1.0] | stabilizing | Likely stabilizing. |\n")
            lines.append("| (-1.0, 1.0] | neutral_or_uncertain | Small/uncertain effect; do not over-interpret. |\n")
            lines.append("| (1.0, 2.0] | destabilizing | Likely destabilizing. |\n")
            lines.append("| > 2.0 | strong_destabilizing | High destabilization risk. |\n\n")
            results = rosetta_data.get("results", [])
            if isinstance(results, list) and results:
                lines.append("### Mutation Results\n\n")
                lines.append("| Mutation | ΔΔG | Class | Manual Review |\n")
                lines.append("|----------|-----|-------|---------------|\n")
                for item in results[:12]:
                    flags = item.get("manual_review_flags", [])
                    flag_text = "; ".join(map(str, flags[:2])) if isinstance(flags, list) else "required"
                    lines.append(
                        f"| {item.get('mutation', '?')} | {item.get('ddg_kcal_mol', '—')} | "
                        f"{item.get('ddg_label', '—')} | {flag_text} |\n"
                    )
                lines.append("\n")
            lines.append(
                "Manual review is required before execution: confirm residue numbering, chain mapping, "
                "active-site/cofactor/disulfide overlap, local packing, and agreement with other tools or experiments.\n\n"
            )

        # Design results section (binder / de novo design)
        if design_data:
            lines.append("## 蛋白设计结果（压缩）\n\n")
            for d in design_data:
                tool = d["tool"]
                data = d["data"]

                if tool == "proteinmpnn_design":
                    lines.append("### Inverse Folding (ProteinMPNN)\n\n")
                    lines.append(f"- **Target length**: {data.get('target_length', 'N/A')} residues\n")
                    lines.append(f"- **Best recovery rate**: {data.get('best_recovery_rate', 'N/A')}\n")
                    lines.append(f"- **Best confidence**: {data.get('best_confidence', 'N/A')}\n")
                    lines.append(f"- **Sequences generated**: {data.get('num_sequences_generated', 'N/A')}\n\n")
                    designs = data.get("designs", [])
                    if designs:
                        lines.append("| Rank | Sequence (first 40 aa) | Recovery | Confidence | Mutations |\n")
                        lines.append("|------|------------------------|----------|------------|----------|\n")
                        for des in designs[:5]:
                            seq_preview = des.get("sequence", "")[:40] + "…"
                            lines.append(
                                f"| {des.get('rank', '?')} | `{seq_preview}` | "
                                f"{des.get('recovery_rate', '?')} | {des.get('mean_confidence', '?')} | "
                                f"{des.get('num_mutations', '?')} |\n"
                            )
                        lines.append("\n")

                elif tool == "rfdiffusion_design":
                    lines.append("### Backbone Generation (RFdiffusion)\n\n")
                    lines.append(f"```\n{str(data)[:500]}\n```\n\n")

                elif tool == "chroma_design":
                    lines.append("### Joint Structure-Sequence (Chroma)\n\n")
                    lines.append(f"```\n{str(data)[:500]}\n```\n\n")

        if not mutation_data:
            # Recommendations
            lines.append("## 下一步专业分析建议\n\n")
            if has_uploaded_structure_evidence:
                lines.append("- **位点表使用方式**：上面的 PDB 坐标预筛位点可作为深度分析的人工审查清单；当前仍不足以升级为高置信具体突变或直接湿实验排单。\n")
                lines.append("- **比活力方向**：在催化核心受保护的前提下，优先检查口袋入口、底物通道、二壳层氢键/疏水网络和可能影响产物释放的柔性区域。\n")
                lines.append("- **工具顺序**：完成结构质量审查和编号确认后，再运行酶身份画像、口袋/保守性分析、候选打分；MD 只用于验证柔性假设，失败或未运行时不能作为结论。\n\n")
            lines.append("### 不建议直接突变的区域\n")
            lines.append("- 已确认或疑似催化残基，包括亲核残基、酸碱残基和稳定过渡态的残基。\n")
            lines.append("- Ca2+/Zn2+ 等金属或辅因子结合残基。\n")
            lines.append("- 保守半胱氨酸、二硫键、核心折叠支架和结构质量异常区域。\n\n")

            lines.append("### 实验验证流程\n")
            lines.append("1. **设计确认**：人工确认序列/PDB/UniProt 编号、链 ID、催化残基、辅因子、二硫键和最终突变列表。\n")
            lines.append("2. **单点构建**：先做优先级最高的单点突变；设置 WT、空载体和已知阳性/阴性对照。\n")
            lines.append("3. **表达与可溶性检查**：比较表达量、可溶组分、SDS-PAGE/Western、SEC 单体比例和聚集/降解。\n")
            lines.append("4. **主活性筛选**：目标条件与原始条件并行检测，建议 n>=3。\n")
            lines.append("5. **稳定性筛选**：检测 Tm/DSF、热处理或 pH 处理后的残余活性，以及工艺相关半衰期。\n")
            lines.append("6. **动力学确认**：对 Top hit 测 kcat/Km，并复核底物特异性或抑制风险。\n")
            lines.append("7. **组合梯度**：单点通过后先做二点组合；高阶组合必须等待二点数据通过 Go/No-Go。\n")
            lines.append("8. **最终复核**：Top 3 候选重新纯化，重复完整动力学、稳定性和结构/MD 复核。\n\n")

        if audit_appendix_lines:
            lines.append("## 附录：证据审计与工具原始输出\n\n")
            lines.extend(audit_appendix_lines)

        lines.append("---\n")
        lines.append("*本报告由酶蛋白 AI 平台生成；所有候选需经编号、功能和湿实验复核后才能进入结论。*\n")

        return "\n".join(lines)

    @staticmethod
    def _raw_tool_result(result: Any) -> str:
        """Serialize the exact tool payload for UI/API inspection, separate from LLM summaries."""
        if isinstance(result, dict):
            try:
                return json.dumps(result, ensure_ascii=False, indent=2, default=str)
            except Exception:
                return str(result)
        return str(result)

    @staticmethod
    def _compact_result(tool_name: str, result: Any) -> str:
        """Build a compact JSON string from a tool result, prioritizing key fields.

        Large results (e.g., mutation_priority_score at 80KB) need key field extraction
        so the LLM and fallback report can see the summary and top candidates.
        """
        if not isinstance(result, dict):
            return str(result)[:5000]

        # Tools with known large outputs — extract key fields into a compact dict
        if tool_name == "enzyme_identity_profile":
            compact = {}
            for key in (
                "profile_version",
                "identity_status",
                "family_candidates",
                "ec_candidates",
                "protected_positions",
                "key_residues",
                "functional_domains",
                "cofactors",
                "signal_peptide",
                "numbering",
                "missing_evidence",
                "conflicts",
                "guardrail",
                "confidence_summary",
            ):
                if key in result:
                    compact[key] = result[key]
            if isinstance(compact.get("family_candidates"), list):
                compact["family_candidates"] = compact["family_candidates"][:3]
            if isinstance(compact.get("ec_candidates"), list):
                compact["ec_candidates"] = compact["ec_candidates"][:3]
            if isinstance(compact.get("key_residues"), list):
                compact["key_residues"] = compact["key_residues"][:8]
            try:
                return json.dumps(compact, ensure_ascii=False, default=str)
            except Exception:
                logger.debug("Compact JSON failed for enzyme_identity_profile, falling through")

        if tool_name == "enzyme_objective_module_plan":
            compact = {}
            for key in (
                "status",
                "objective",
                "module",
                "primary_question",
                "foundation_gate",
                "missing_evidence",
                "candidate_output_allowed",
                "ranking_boundary",
                "validation_metrics",
                "forbidden_shortcuts",
            ):
                if key in result:
                    compact[key] = result[key]
            try:
                return json.dumps(compact, ensure_ascii=False, default=str)
            except Exception:
                logger.debug("Compact JSON failed for enzyme_objective_module_plan, falling through")

        if tool_name == "mutation_priority_score":
            compact = {}
            for key in ("status", "reason", "identity_gate", "objective_gate",
                        "candidate_table_status", "candidate_table_boundary", "experiment_design_table",
                        "specified_mutation_reviews",
                        "summary", "strategy", "tier_1_candidates", "tier_2_candidates",
                        "engineering_goal", "sequence_length"):
                if key in result:
                    compact[key] = result[key]
            if isinstance(compact.get("experiment_design_table"), list):
                compact["experiment_design_table"] = compact["experiment_design_table"][:12]
            if isinstance(compact.get("specified_mutation_reviews"), list):
                compact["specified_mutation_reviews"] = compact["specified_mutation_reviews"][:20]
            # Limit tier lists to top 10
            for tier_key in ("tier_1_candidates", "tier_2_candidates"):
                if tier_key in compact and isinstance(compact[tier_key], list):
                    compact[tier_key] = compact[tier_key][:10]
            try:
                return json.dumps(compact, ensure_ascii=False, default=str)
            except Exception:
                logger.debug("Compact JSON failed for mutation_priority_score, falling through")

        if tool_name == "build_site_structure_function_features":
            compact = {}
            for key in (
                "found", "status", "source", "capability_status", "evidence_level",
                "report_boundary", "chain_id", "contact_radius_angstrom",
                "catalytic_positions", "protected_positions", "target_positions",
                "feature_count", "summary", "features",
            ):
                if key in result:
                    compact[key] = result[key]
            if isinstance(compact.get("features"), list):
                compact["features"] = compact["features"][:50]
            try:
                return json.dumps(compact, ensure_ascii=False, default=str)
            except Exception:
                logger.debug("Compact JSON failed for build_site_structure_function_features, falling through")

        if tool_name == "mutation_scan":
            compact = {}
            for key in ("sequence_length", "scan_type", "positions_scanned", "results"):
                if key in result:
                    compact[key] = result[key] if key != "results" else result[key][:15]
            try:
                return json.dumps(compact, ensure_ascii=False, default=str)
            except Exception:
                logger.debug("Compact JSON failed for mutation_scan, falling through")

        if tool_name == "rosetta_ddg":
            compact = {}
            for key in (
                "status", "requested_mutations", "thresholds", "manual_review_required",
                "manual_review_checklist", "runtime", "pdb_input", "sequence_validation_errors",
                "reason", "missing", "recovery", "is_real_rosetta", "evidence_level",
                "results", "note",
            ):
                if key in result:
                    compact[key] = result[key]
            if isinstance(compact.get("results"), list):
                compact["results"] = compact["results"][:20]
            try:
                return json.dumps(compact, ensure_ascii=False, default=str)
            except Exception:
                logger.debug("Compact JSON failed for rosetta_ddg, falling through")

        # Default: JSON-serialized full result (much more compact than Python repr)
        try:
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception:
            logger.debug("JSON serialization failed, truncating raw result")
            return str(result)[:5000]

    @staticmethod
    def _safe_parse_json(text: str) -> dict:
        """Try to parse a string as JSON or Python repr, return empty dict on failure."""
        if not isinstance(text, str) or not text.strip():
            return {}
        # Try JSON first
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        # Try ast.literal_eval for Python repr strings (safe — no code execution)
        try:
            import ast
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            pass
        # Handle truncated Python repr: trim to last complete closing bracket
        try:
            import ast
            trimmed = text[:text.rfind('}')+1] if '}' in text else text
            if trimmed.strip():
                return ast.literal_eval(trimmed)
        except (ValueError, SyntaxError):
            pass
        return {}

    async def _chat_reply(
        self, message: str, history: list[dict],
        model_id: str | None = None,
    ) -> str:
        """Direct LLM chat reply for non-protein general conversation."""
        wants_document = self._is_document_reply_request(message)
        system_prompt = (
            "You are a helpful protein engineering AI assistant. "
            "The user's message does not appear to contain a specific protein analysis task. "
            "Respond naturally and helpfully. If you can, guide them toward describing "
            "a protein engineering goal — such as analyzing a sequence, designing a binder, "
            "predicting a structure, or scanning mutations."
        )
        if wants_document:
            system_prompt += (
                " The user is asking for an execution document, SOP, checklist, schedule, "
                "template, or table. Preserve clear Markdown structure, section breaks, "
                "lists, and tables. Do not shorten the document unless the user asks for a summary. "
                "When the document concerns enzyme mutation design, stability, activity, or "
                "experimental feedback, follow this protocol:\n"
                f"{ENZYME_ENGINEERING_REPORT_PROTOCOL}"
            )
        else:
            system_prompt += " Keep your response concise."
        try:
            resp = await self._call_llm(
                [{"role": "system", "content": system_prompt}, *history[-4:], {"role": "user", "content": message}],
                model_id=model_id, max_tokens=2200 if wants_document else 512,
            )
            return resp.choices[0].message.content or "Hello! How can I help with your protein research today?"
        except Exception:
            logger.exception("Chat reply LLM call failed")
            return "Hello! I'm a protein engineering AI assistant. How can I help you today?"

    @staticmethod
    def _sanitize_messages(messages: list[dict]) -> list[dict]:
        """Sanitize messages for API compatibility.

        Dashscope/Qwen and some other providers require 'content' to be a string.
        This strips tool_calls fields and coerces non-string content to str.
        """
        sanitized = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Coerce non-string content (list, dict, None) to string
            if content is None:
                content = ""
            elif isinstance(content, list):
                # Multi-modal content list → extract text parts
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                content = "\n".join(text_parts)
            elif not isinstance(content, str):
                content = str(content)

            clean: dict = {"role": role, "content": content}

            # Preserve tool_call_id for tool response messages
            if role == "tool" and "tool_call_id" in msg:
                clean["tool_call_id"] = msg["tool_call_id"]

            # Drop assistant messages with no content (pure tool_calls)
            if role == "assistant" and not content.strip():
                continue

            sanitized.append(clean)
        return sanitized

    async def _call_llm(self, messages: list[dict], model_id: str | None = None, **kwargs) -> Any:
        """Run the unified LLM gateway in a thread pool to avoid blocking the event loop."""
        messages = self._sanitize_messages(messages)
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            None,
            functools.partial(llm_gateway.complete_sync, messages, model_id=model_id, **kwargs),
        )
        return await asyncio.wait_for(
            future,
            timeout=max(float(settings.LLM_REQUEST_TIMEOUT), 0.05),
        )

    # Errors that are transient and worth retrying once
    _RETRYABLE_ERRORS = ("connection", "timeout", "rate_limit", "rate_limited", "503", "502", "429")

    def _should_retry(self, step: PlanStep) -> bool:
        """Determine if a failed step should be retried once for transient errors."""
        error_lower = str(step.error).lower()
        return any(pattern in error_lower for pattern in self._RETRYABLE_ERRORS)

    async def _persist_identity_consistency(
        self,
        sequence: str,
        profile: dict[str, Any],
        consistency: dict[str, Any],
        *,
        current_user: dict | None,
        audit_session: Any | None,
    ) -> None:
        """Persist identity classification without making storage availability a gate."""
        if not current_user or not audit_session or not isinstance(consistency, dict):
            return
        try:
            from app.services.identity_consistency_store import persist_identity_record

            await persist_identity_record(
                audit_session,
                user_id=int(current_user["id"]),
                sequence_hash=str(consistency.get("sequence_hash") or sequence_hash(sequence)),
                model_version=str(consistency.get("model_version") or profile.get("model_version") or ""),
                evidence_version=str(consistency.get("evidence_version") or profile.get("evidence_version") or ""),
                identity=str(
                    consistency.get("identity")
                    or profile.get("identity_label")
                    or profile.get("family")
                    or "unknown"
                ),
                status=str(consistency.get("status") or "NEEDS_REVIEW"),
            )
        except Exception as exc:
            logger.warning("Failed to persist identity consistency record: %s", exc)


orchestrator = AgentOrchestrator()
