"""Plan-Execute-Synthesize Agent Graph with checkpoint-based pause/resume.

Inspired by VenusFactory2's multi-role agent pattern:
  PI (Principal Investigator) → CB (Computational Biologist)
  → MLS (Machine Learning Specialist) → SC (Scientific Critic)
"""

from dataclasses import dataclass, field
from typing import TypedDict, Annotated, Any, AsyncGenerator
import asyncio
import functools
import json
import logging
import re
import time

logger = logging.getLogger(__name__)

from app.core.llm import chat_completion, chat_completion_sync
from app.tools.registry import ToolRegistry
from app.core.skills import get_skills_metadata, read_skill
from app.core.agent_roles import (
    PI_SYSTEM_PROMPT, CB_SYSTEM_PROMPT,
    MLS_SYSTEM_PROMPT, SC_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
)
from app.services.literature_client import LiteratureClient, Paper as LitPaper
from app.services.literature_store import LiteratureStore

# Lazy import for experience store (avoids circular import at module load)
def _get_experience_store():
    from app.memory.experience_store import get_experience_store, ExperienceRecord
    return get_experience_store(), ExperienceRecord

# Tools that require a protein sequence — skip if no sequence available
_SEQUENCE_REQUIRED_TOOLS = frozenset({
    "alphafold_folding", "esmfold_folding", "predict_properties",
    "mutation_scan", "mutation_priority_score", "protein_benchmark",
    "enzyme_function", "kcat_predict", "protssn_score", "blast_search",
    "gromacs_md",
})

# Tools that require a PDB structure — skip if no PDB available
_PDB_REQUIRED_TOOLS = frozenset({
    "proteinmpnn_design",
    "esm_if1_design",
})


@dataclass
class PlanStep:
    id: int
    tool_name: str
    description: str
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending | running | completed | failed
    result: Any = None
    error: str | None = None
    duration: float = 0.0


@dataclass
class ChatSnapshot:
    """Full state snapshot for SSE streaming (inspired by VenusFactory2)."""
    stage: str  # router | research | plan | execute | synthesize | done
    plan: list[dict] = field(default_factory=list)
    current_step: int = 0
    step_results: list[dict] = field(default_factory=list)
    research_notes: str = ""
    final_report: str = ""
    waiting_for: str | None = None  # plan_confirmation | step_review | clarification
    tokens: str = ""
    error: str | None = None


class AgentOrchestrator:
    """Multi-role agent orchestrator with Plan-Execute-Synthesize pattern."""

    def __init__(self):
        self._snapshot: ChatSnapshot | None = None

    @property
    def tools_schema(self) -> list[dict]:
        """Lazy-load tools schema — ToolRegistry is populated after import."""
        return ToolRegistry.get_tools_schema()

    @property
    def skills_metadata(self) -> list[dict]:
        """Lazy-load skills — SkillRegistry is populated after import."""
        return get_skills_metadata()

    def _build_context(self, history: list[dict]) -> str:
        """Build protein context from conversation history."""
        context_parts = []
        for msg in history:
            content = msg.get("content", "")
            if isinstance(content, str) and ">" in content:
                # Extract potential FASTA sequences
                if content.count(">") >= 1:
                    context_parts.append("[Protein sequence detected in conversation]")
                if any(kw in content.lower() for kw in ["pd-l1", "egfr", "her2", "kras", "p53"]):
                    context_parts.append("[Known protein target discussed]")
        return "\n".join(context_parts) if context_parts else ""

    @staticmethod
    def _extract_sequence(text: str) -> str | None:
        """Extract a valid amino-acid sequence (10+ consecutive standard AAs) from text."""
        # Look for a contiguous block of standard AA letters (10+ chars)
        matches = re.findall(r'[ACDEFGHIKLMNPQRSTVWY]{10,}', text, re.IGNORECASE)
        if matches:
            # Return the longest match
            return max(matches, key=len).upper()
        return None

    async def stream_chat(
        self, user_message: str, history: list[dict],
        provider: str | None = None, model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Main entry: route → research → plan → execute → synthesize."""
        self._snapshot = ChatSnapshot(stage="router")
        protein_context = self._build_context(history)

        # --- Stage 1: ROUTER ---
        yield self._emit_state()
        route = await self._route_intent(user_message, protein_context, provider, model)
        self._snapshot.stage = route

        # --- General chat shortcut: no protein intent → direct LLM reply ---
        if route == "general":
            self._snapshot.stage = "done"
            yield self._emit_state()
            reply = await self._chat_reply(user_message, history, provider, model)
            for word in reply.split():
                yield json.dumps({"type": "text", "content": f"{word} "}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return

        # --- Stage 2: RESEARCH (PI) ---
        yield self._emit_state()
        yield json.dumps({"type": "text", "content": "\n\n"}, ensure_ascii=False)
        if route in ("research", "design", "analyze"):
            research = await self._research_pi(user_message, history, protein_context, provider, model)
            self._snapshot.research_notes = research
            yield self._emit_state()
        else:
            self._snapshot.research_notes = ""

        # --- Stage 3: PLAN (CB) ---
        self._snapshot.stage = "plan"
        yield self._emit_state()
        plan = await self._plan_cb(user_message, self._snapshot.research_notes, history, provider, model)
        self._snapshot.plan = [{
            "id": s.id, "tool_name": s.tool_name,
            "description": s.description, "params": s.params,
            "status": s.status,
        } for s in plan]
        self._snapshot.waiting_for = "plan_confirmation"
        yield self._emit_state()

        # Auto-approve plan for MVP (HITL checkpoint can be added here)
        self._snapshot.waiting_for = None

        # If no plan steps were generated, use research notes as the reply
        if not plan:
            self._snapshot.stage = "done"
            yield self._emit_state()
            reply = self._snapshot.research_notes or "I couldn't determine how to help with that request. Could you provide more details about your protein engineering task?"
            for word in reply.split():
                yield json.dumps({"type": "text", "content": f"{word} "}, ensure_ascii=False)
            yield json.dumps({"type": "done"})
            return

        # --- Stage 4: EXECUTE (MLS) ---
        self._snapshot.stage = "execute"
        yield self._emit_state()

        # Per-step timeout cap — prevents slow external APIs from blocking the pipeline
        PER_STEP_TIMEOUT = 120  # seconds

        tool_messages = []
        for i, step in enumerate(plan):
            self._snapshot.current_step = i + 1
            step.status = "running"
            self._snapshot.plan[i]["status"] = "running"
            yield self._emit_state()

            start = time.time()
            try:
                result = await asyncio.wait_for(
                    ToolRegistry.execute(step.tool_name, step.params),
                    timeout=PER_STEP_TIMEOUT,
                )
                step.status = "completed"
                step.result = result
                step.duration = round(time.time() - start, 2)
                self._snapshot.plan[i]["status"] = "completed"
                self._snapshot.step_results.append({
                    "step": i + 1, "tool": step.tool_name,
                    "status": "completed", "result_preview": self._compact_result(step.tool_name, result)[:2000],
                    "duration": step.duration,
                })
            except asyncio.TimeoutError:
                step.status = "failed"
                step.error = f"Step timed out after {PER_STEP_TIMEOUT}s"
                step.duration = round(time.time() - start, 2)
                self._snapshot.plan[i]["status"] = "failed"
                self._snapshot.step_results.append({
                    "step": i + 1, "tool": step.tool_name,
                    "status": "failed", "error": step.error,
                    "duration": step.duration,
                })
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                step.duration = round(time.time() - start, 2)
                self._snapshot.plan[i]["status"] = "failed"
                self._snapshot.step_results.append({
                    "step": i + 1, "tool": step.tool_name,
                    "status": "failed", "error": str(e),
                    "duration": step.duration,
                })
                if self._should_retry(step):
                    yield self._emit_state()
                    step.status = "running"
                    self._snapshot.plan[i]["status"] = "running"
                    try:
                        result = await ToolRegistry.execute(step.tool_name, step.params)
                        step.status = "completed"
                        step.result = result
                        self._snapshot.plan[i]["status"] = "completed"
                    except Exception:
                        logger.exception("Retry failed for tool %s", step.tool_name)

            yield self._emit_state()

            # Build compact result for LLM/report: extract key fields from large results
            result_payload = self._compact_result(step.tool_name, step.result) if step.result else step.error
            tool_messages.append({
                "role": "tool",
                "tool_name": step.tool_name,
                "result": result_payload,
                "status": step.status,
            })

        # --- Stage 4.5: SC REVIEW (multi-round iterative refinement) ---
        # MLEvolve-inspired: SC reviews results, may trigger supplementary tools,
        # records experience after each round. Up to MAX_REVIEW_ROUNDS iterations.
        MAX_REVIEW_ROUNDS = 3
        execution_start = time.time()

        for review_round in range(1, MAX_REVIEW_ROUNDS + 1):
            self._snapshot.stage = "review"
            yield self._emit_state()

            review_result = await self._review_results_sc(
                user_message, tool_messages, self._snapshot.research_notes, provider, model
            )

            # If SC is satisfied, break out of the loop
            if not review_result.get("needs_supplement"):
                break

            # If this is the last round, don't execute more supplements
            if review_round >= MAX_REVIEW_ROUNDS:
                logger.info("Max review rounds (%d) reached", MAX_REVIEW_ROUNDS)
                break

            # SC found gaps — execute supplementary tools
            has_sequence = bool(self._extract_sequence(user_message))
            has_pdb = any(
                "pdb" in str(r.get("result", "")).lower() and "ATOM" in str(r.get("result", ""))
                for r in tool_messages
            )

            for extra in review_result.get("supplementary_steps", []):
                tool_name = extra["tool_name"]

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
                        tool_messages.append({
                            "role": "tool",
                            "tool_name": extra_step.tool_name,
                            "result": f"Skipped: missing required parameters: {missing}",
                            "status": "skipped",
                        })
                        continue

                start = time.time()
                try:
                    result = await asyncio.wait_for(
                        ToolRegistry.execute(extra_step.tool_name, extra_step.params),
                        timeout=PER_STEP_TIMEOUT,
                    )
                    extra_step.status = "completed"
                    extra_step.result = result
                    extra_step.duration = round(time.time() - start, 2)
                    idx = extra_step.id - 1
                    self._snapshot.plan[idx]["status"] = "completed"
                    self._snapshot.step_results.append({
                        "step": extra_step.id, "tool": extra_step.tool_name,
                        "status": "completed", "result_preview": self._compact_result(extra_step.tool_name, result)[:2000],
                        "duration": extra_step.duration,
                    })
                    tool_messages.append({
                        "role": "tool",
                        "tool_name": extra_step.tool_name,
                        "result": self._compact_result(extra_step.tool_name, result),
                        "status": "completed",
                    })
                except asyncio.TimeoutError:
                    extra_step.status = "failed"
                    extra_step.error = f"Step timed out after {PER_STEP_TIMEOUT}s"
                    extra_step.duration = round(time.time() - start, 2)
                    idx = extra_step.id - 1
                    self._snapshot.plan[idx]["status"] = "failed"
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
            user_message, route, plan, tool_messages,
            self._snapshot.research_notes, total_duration, round_number=review_round,
        )

        # --- Stage 5: SYNTHESIZE (SC) ---
        self._snapshot.stage = "synthesize"
        yield self._emit_state()
        final_report = await self._synthesize_sc(
            user_message, tool_messages, self._snapshot.research_notes, history, provider, model
        )
        self._snapshot.final_report = final_report
        self._snapshot.stage = "done"
        yield self._emit_state()

        # Stream final report as text tokens
        for word in final_report.split():
            yield json.dumps({"type": "text", "content": f"{word} "}, ensure_ascii=False)

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
        }, ensure_ascii=False)

    # --- Role Implementations ---

    async def _route_intent(self, message: str, context: str, provider: str | None = None, model: str | None = None) -> str:
        """Router: classify user intent into workflow type."""
        lower = message.lower()

        # Deterministic overrides for common patterns
        if any(kw in lower for kw in ["设计", "design", "生成序列", "generate sequence", "binder"]):
            return "design"
        if any(kw in lower for kw in ["突变", "mutation", "mutant", "variant", "ddg"]):
            return "analyze"
        if any(kw in lower for kw in ["对接", "docking", "dock", "结合", "binding"]):
            return "analyze"
        if any(kw in lower for kw in ["ph", "酸性", "碱性", "最适", "酶活", "活性", "engineering", "改造",
                                        "stability", "stabilize", "catalytic", "substrate", "kcat", "km",
                                        "specificity", "optimum", "耐酸", "耐碱", "耐热", "热稳定"]):
            return "analyze"
        if any(kw in lower for kw in ["结构", "structure", "fold", "pdb", "预测结构"]):
            return "research"
        if any(kw in lower for kw in ["性质", "property", "properties", "理化", "predict", "预测", "analyze", "分析"]):
            return "analyze"
        if any(kw in lower for kw in ["ec", "酶功能", "enzyme function", "classify", "分类", "ec number"]):
            return "research"
        if any(kw in lower for kw in ["kcat", "km", "turnover", "动力学", "kinetics", "催化效率", "催化速率"]):
            return "analyze"
        if any(kw in lower for kw in ["搜索", "search", "blast", "查找", "find"]):
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
            ], provider=provider, model=model, max_tokens=10)
            route = (resp.choices[0].message.content or "general").strip().lower()
            if route in ("design", "research", "analyze", "general"):
                return route
        except Exception:
            logger.exception("Router LLM call failed")
        return "general"

    async def _get_knowledge_context(self, message: str) -> str:
        """Gather knowledge graph + literature + vector search context for a task.

        Queries three sources in parallel:
        1. Enzyme Knowledge Graph — structured data from 15 domain tables
        2. Literature Client — PubMed/Europe PMC paper search
        3. ESM-2 Vector Search — similar enzymes by sequence embedding

        Returns a combined context string for injection into PI/SC prompts.
        Gracefully degrades if any source is unavailable.
        """
        protein_name = self._extract_protein_name(message)
        sequence = self._extract_sequence(message)
        sections = []

        # 1. Knowledge graph query (sync, run in executor)
        if protein_name:
            kg_context = await self._query_knowledge_graph(protein_name)
            if kg_context:
                sections.append(f"--- ENZYME KNOWLEDGE GRAPH ---\n{kg_context}")

        # 2. Literature search
        if protein_name:
            lit_context = await self._search_literature(protein_name)
            if lit_context:
                sections.append(f"--- RELATED LITERATURE ---\n{lit_context}")

        # 3. ESM-2 vector search for similar enzymes
        if sequence and len(sequence) >= 20:
            similar_context = await self._search_similar_enzymes(sequence)
            if similar_context:
                sections.append(f"--- SIMILAR ENZYMES (ESM-2 embedding) ---\n{similar_context}")

        return "\n\n".join(sections) if sections else ""

    async def _query_knowledge_graph(self, protein_name: str) -> str:
        """Query enzyme knowledge graph in a thread executor."""
        def _sync_query():
            try:
                from app.core.database import _engine
                from sqlalchemy import create_engine
                from sqlalchemy.orm import Session as SyncSession
                from app.services.knowledge_graph import EnzymeKnowledgeGraph

                # Create sync engine from async URL
                sync_url = str(_engine.url).replace("+asyncpg", "+psycopg2").replace("+aiosqlite", "+sqlite")
                sync_engine = create_engine(sync_url, echo=False)
                with SyncSession(sync_engine) as session:
                    kg = EnzymeKnowledgeGraph(session)
                    # Try exact match first, then fuzzy
                    enzyme = kg.query_by_name(protein_name)
                    if enzyme:
                        context = kg.query_enzyme_context(enzyme.uniprot_id)
                        return kg.to_natural_language(context)
                    # Try EC number search
                    if protein_name.startswith("EC"):
                        results = kg.query_by_ec(protein_name)
                        if results:
                            return kg.to_natural_language(results[0])
                return ""
            except Exception:
                logger.debug("Knowledge graph query unavailable: %s", protein_name)
                return ""

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_query)

    async def _search_literature(self, protein_name: str) -> str:
        """Search PubMed/Europe PMC for relevant papers."""
        try:
            client = LiteratureClient()
            papers = await client.search_by_protein(protein_name, max_results=3)
            if papers:
                return LiteratureClient.format_citations(papers)
        except Exception:
            logger.debug("Literature search failed for: %s", protein_name)
        return ""

    async def _search_similar_enzymes(self, sequence: str) -> str:
        """Search for similar enzymes using ESM-2 vector embeddings."""
        try:
            from app.ml.vector_search import EnzymeVectorSearch
            vsearch = EnzymeVectorSearch()
            results = vsearch.search_by_sequence(sequence, top_k=3)
            if results:
                lines = ["Similar enzymes found by ESM-2 embedding similarity:"]
                for r in results:
                    uniprot_id = r.get("uniprot_id", "unknown")
                    distance = r.get("distance", 1.0)
                    similarity = round(1.0 - distance, 3)
                    lines.append(f"- {uniprot_id} (cosine similarity: {similarity})")
                return "\n".join(lines)
        except Exception:
            logger.debug("ESM-2 vector search unavailable")
        return ""

    async def _research_pi(
        self, message: str, history: list[dict], context: str,
        provider: str | None = None, model: str | None = None,
    ) -> str:
        """PI: Research phase — gather background, clarify requirements."""
        # Gather knowledge graph + literature + vector search context
        knowledge_context = await self._get_knowledge_context(message)

        user_content = f"Task: {message}\nProtein context: {context}"
        if knowledge_context:
            user_content += f"\n\n{knowledge_context}"

        messages = [
            {"role": "system", "content": PI_SYSTEM_PROMPT},
            *history[-6:],  # Last 3 turns for context
            {"role": "user", "content": user_content},
        ]
        try:
            resp = await self._call_llm(messages, provider=provider, model=model, max_tokens=600)
            return resp.choices[0].message.content or ""
        except Exception:
            logger.exception("PI research LLM call failed")
            return ""

    async def _plan_cb(
        self, message: str, research: str, history: list[dict],
        provider: str | None = None, model: str | None = None,
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
        return self._generate_fallback_plan(message)

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
            return steps

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
                    return steps
            except (json.JSONDecodeError, IndexError):
                pass

        return self._generate_fallback_plan(task)

    def _generate_fallback_plan(self, task: str) -> list[PlanStep]:
        """Generate a comprehensive tool execution plan for enzyme/protein analysis.

        This is the fallback when the LLM fails to produce a valid plan.
        For any task with a protein sequence, we run a deep pipeline:
        blast_search → esmfold_folding → predict_properties → mutation_scan
        """
        steps = []
        lower = task.lower()
        tool_names = set(ToolRegistry._tools.keys())
        seq = self._extract_sequence(task) or ""

        # Detect enzyme engineering intent
        is_enzyme_eng = any(kw in lower for kw in [
            "ph", "酸性", "碱性", "最适", "酶活", "engineering", "改造",
            "mutation", "stability", "stabilize", "activity", "catalytic",
            "substrate", "kcat", "km", "specificity", "optimum",
            "耐酸", "耐碱", "耐热", "热稳定", "比活力",
        ])

        # Detect specific engineering goal for mutation_priority_score
        # Check thermo FIRST — "提高热稳定性" should match thermo, not ph_raising
        is_thermo = any(kw in lower for kw in ["耐热", "热稳定", "thermostability", "tm", "温度", "heat", "热稳定性"])
        is_ph_lowering = any(kw in lower for kw in ["降低最适ph", "降低ph", "酸化", "耐酸", "酸性", "酸稳定", "lower ph", "ph lowering"])
        is_ph_raising = any(kw in lower for kw in ["提高最适ph", "提高ph", "碱化", "耐碱", "碱性", "碱稳定", "raise ph", "ph raising"])
        if is_thermo:
            eng_goal = "thermostability"
        elif is_ph_lowering:
            eng_goal = "ph_lowering"
        elif is_ph_raising:
            eng_goal = "ph_raising"
        else:
            eng_goal = "general"

        # Detect binder / de novo protein design intent
        is_binder_design = any(kw in lower for kw in [
            "binder", "bind", "de novo", "backbone", "scaffold",
            "design a", "design binder", "结合蛋白", "蛋白设计",
            "从头设计", "骨架设计", "设计蛋白",
        ])

        has_sequence = len(seq) >= 10
        step_id = 0

        # --- Binder Design Pipeline (with sequence) ---
        if has_sequence and is_binder_design:
            # 1. Inverse folding — redesign sequence for the given backbone
            if "proteinmpnn_design" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "proteinmpnn_design",
                    "Inverse folding: design novel sequences that stably fold into the target backbone",
                    {"pdb_structure": "", "temperature": 0.1, "num_sequences": 3}))

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

            return steps

        if has_sequence:
            # FAST LOCAL TOOLS FIRST — produce results immediately without external API dependency

            # 1. Physicochemical properties — baseline metrics (instant)
            if "predict_properties" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "predict_properties",
                    "Compute molecular weight, isoelectric point, stability index, GRAVY, and secondary structure propensity",
                    {"sequence": seq}))

            # 2. Protein benchmark — deep family analysis with built-in expert knowledge (instant)
            if "protein_benchmark" in tool_names and is_enzyme_eng:
                step_id += 1
                steps.append(PlanStep(step_id, "protein_benchmark",
                    "Deep enzyme family characterization: motif search, catalytic residue prediction, domain architecture, conservation analysis, engineering targets",
                    {"query_sequence": seq}))

            # 3. Enzyme function prediction — EC number classification (instant, local motifs)
            if is_enzyme_eng and "enzyme_function" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "enzyme_function",
                    "Predict EC number and enzyme class from sequence using curated motifs and ESM-2 embeddings",
                    {"sequence": seq}))

            # 4. Mutation scan — systematic residue-level engineering targets (instant)
            if "mutation_scan" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "mutation_scan",
                    "Systematically scan surface and active-site proximal residues for engineering candidates",
                    {"sequence": seq}))

            # 5. Multi-dimensional mutation priority scoring (core expert tool, instant)
            if is_enzyme_eng and "mutation_priority_score" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "mutation_priority_score",
                    f"Score every residue on 5 dimensions for {eng_goal} engineering — Tier 1/2 candidates with specific mutations",
                    {"sequence": seq, "engineering_goal": eng_goal}))

            # 6. Enzyme kinetics prediction — Kcat estimation (instant, local statistics)
            if is_enzyme_eng and "kcat_predict" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "kcat_predict",
                    "Predict enzyme turnover number (Kcat) and catalytic efficiency",
                    {"protein_sequence": seq}))

            # 7. Structure prediction — 3D model for visualization (may be slow on CPU)
            if "esmfold_folding" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "esmfold_folding",
                    "Predict 3D protein structure for visualization and structural analysis",
                    {"sequence": seq}))

            # 8. ML-enhanced mutation scoring — ProtSSN sequence+structure fusion
            if is_enzyme_eng and "protssn_score" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "protssn_score",
                    "ML-enhanced mutation scoring with sequence-structure fusion for higher accuracy",
                    {"sequence": seq, "mutations": []}))

            # 9. BLAST search — LAST because it depends on external NCBI API (slow/unreliable)
            if "blast_search" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "blast_search",
                    "Identify enzyme family homologs and conserved residues via BLAST (external NCBI)",
                    {"sequence": seq, "database": "swissprot", "max_results": 5}))

            # 10. MD simulation — optional, compute-intensive
            if is_enzyme_eng and "gromacs_md" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "gromacs_md",
                    "Run molecular dynamics simulation to assess structural stability and identify flexible regions",
                    {"sequence": seq, "simulation_time_ns": 10.0}))

        # If no sequence, try to extract a protein name and search for it
        if not steps:
            search_query = self._extract_protein_name(task)

            # --- Binder Design Pipeline (no sequence) ---
            if is_binder_design:
                # 1. Search for target protein sequence
                if "sequence_search" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "sequence_search",
                        f"Search for target protein: {search_query}",
                        {"query": search_query, "database": "uniprot", "max_results": 5}))

                # 2. RFdiffusion — generate binder backbone scaffolds
                if "rfdiffusion_design" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "rfdiffusion_design",
                        f"Generate de novo binder backbone scaffolds targeting {search_query}",
                        {"target_name": search_query, "length": 100, "num_designs": 3}))

                # 3. Chroma — joint structure-sequence generation
                if "chroma_design" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "chroma_design",
                        "Joint structure-sequence generation for binder design",
                        {"target_name": search_query, "num_designs": 3}))

                # 4. ProteinMPNN — inverse folding on generated backbones
                if "proteinmpnn_design" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "proteinmpnn_design",
                        "Inverse folding: design sequences for generated binder backbones",
                        {"pdb_structure": "", "temperature": 0.1, "num_sequences": 3}))

                # 5. ESMFold — validate folding of designed sequences
                if "esmfold_folding" in tool_names:
                    step_id += 1
                    steps.append(PlanStep(step_id, "esmfold_folding",
                        "Validate designed binder sequences fold into intended backbone",
                        {"sequence": ""}))

                return steps

            # Generic fallback: search for protein sequence
            if "sequence_search" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "sequence_search",
                    f"Search for protein/gene: {search_query}",
                    {"query": search_query, "database": "uniprot", "max_results": 5}))

        return steps

    @staticmethod
    def _extract_protein_name(task: str) -> str:
        """Extract a likely protein/gene name from a natural language query.

        Handles patterns like:
        - "Design a binder for PD-L1" → "PD-L1"
        - "Analyze the structure of EGFR" → "EGFR"
        - "What is the sequence of human p53" → "p53"
        """
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
        provider: str | None = None, model: str | None = None,
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
            f"User task: {task}\n\n"
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
                provider=provider, model=model, max_tokens=400,
            )
            content = resp.choices[0].message.content or ""
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            logger.exception("SC review JSON parse failed")

        return {"needs_supplement": False, "supplementary_steps": [], "critique": ""}

    async def _synthesize_sc(
        self, task: str, tool_results: list[dict], research: str, history: list[dict],
        provider: str | None = None, model: str | None = None,
    ) -> str:
        """SC: Synthesize phase — validate and create final report."""
        results_text = "\n".join([
            f"Step {i+1}: {r['tool_name']} → {r['status']}\n{r['result'][:300]}"
            for i, r in enumerate(tool_results)
        ])

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
                f"Task: {task}\n\n"
                f"Research notes: {research[:500]}\n\n"
                f"Tool results:\n{results_text}\n\n"
                "Synthesize a comprehensive scientific report with SPECIFIC residue-level "
                "recommendations. Include: enzyme family classification, catalytic residue "
                "identification, proposed mutations with positions and rationales, tiered "
                "priority ranking, experimental validation plan. "
                "Cite relevant literature (PMIDs) from the knowledge context when available. "
                "NEVER give generic advice."
            )},
        ]
        try:
            resp = await self._call_llm(messages, provider=provider, model=model, max_tokens=3000)
            content = resp.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except Exception as e:
            logger.exception("SC synthesize LLM call failed")

        # Fallback: build a structured report from tool results
        return self._build_fallback_report(task, tool_results)

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

        if any(kw in lower for kw in ["design", "binder", "de novo", "backbone", "scaffold", "蛋白设计", "从头设计"]):
            skill = read_skill("protein_design")
            if skill:
                relevant.append(skill)

        if not relevant:
            return ""

        return "\n\n--- DOMAIN KNOWLEDGE FOR THIS TASK ---\n\n" + "\n\n".join(relevant)

    def _build_fallback_report(self, task: str, tool_results: list[dict]) -> str:
        """Build a structured scientific report from tool results when LLM fails."""
        lines = ["# Protein Engineering Analysis Report\n"]

        # Extract data from results
        seq_data = {}
        props_data = {}
        mutation_data = {}
        benchmark_data = {}
        enzyme_data = {}
        kcat_data = {}
        design_data = []  # proteinmpnn / rfdiffusion / chroma results

        for r in tool_results:
            result_str = str(r.get("result", ""))
            tool = r["tool_name"]
            status = r["status"]

            if tool == "predict_properties" and status == "completed":
                props_data = self._safe_parse_json(result_str)
            elif tool == "mutation_scan" and status == "completed":
                mutation_data = self._safe_parse_json(result_str)
            elif tool == "mutation_priority_score" and status == "completed":
                mutation_data = self._safe_parse_json(result_str)
            elif tool == "protein_benchmark" and status == "completed":
                benchmark_data = self._safe_parse_json(result_str)
            elif tool == "enzyme_function" and status == "completed":
                enzyme_data = self._safe_parse_json(result_str)
            elif tool == "kcat_predict" and status == "completed":
                kcat_data = self._safe_parse_json(result_str)
            elif tool in ("proteinmpnn_design", "rfdiffusion_design", "chroma_design") and status == "completed":
                design_data.append({"tool": tool, "data": self._safe_parse_json(result_str)})
            elif tool == "blast_search" and status == "completed":
                lines.append("## Enzyme Family Identification (BLAST)\n")
                lines.append(f"```\n{result_str[:500]}\n```\n")

        # Properties section
        if props_data:
            lines.append("## Physicochemical Properties\n")
            lines.append(f"- **Molecular Weight**: {props_data.get('molecular_weight_kda', 'N/A')} kDa\n")
            lines.append(f"- **Isoelectric Point (pI)**: {props_data.get('isoelectric_point', 'N/A')}\n")
            lines.append(f"- **GRAVY**: {props_data.get('gravy', 'N/A')}\n")
            lines.append(f"- **Stability**: {props_data.get('stability', 'N/A')}\n")
            lines.append(f"- **Length**: {props_data.get('length', 'N/A')} residues\n\n")

        # Mutation priority section
        if mutation_data:
            lines.append("## Mutation Priority Analysis\n\n")
            summary = mutation_data.get("summary", {})
            if summary:
                lines.append(f"- **Tier 1 candidates**: {summary.get('tier_1_count', 0)}\n")
                lines.append(f"- **Tier 2 candidates**: {summary.get('tier_2_count', 0)}\n")
                never_mutate = summary.get('never_mutate_positions', [])
                if never_mutate:
                    lines.append(f"- **NEVER MUTATE positions**: {never_mutate}\n")
                lines.append("\n")

            # Tier 1 candidates with specific mutations
            tier1 = mutation_data.get("tier_1_candidates", [])
            if tier1:
                lines.append("### Tier 1 — High Priority Engineering Candidates\n\n")
                lines.append("| Position | WT | Proposed Mutation | Purpose | Priority Score |\n")
                lines.append("|----------|----|--------------------|---------|----------------|\n")
                for c in tier1[:8]:
                    muts = c.get("recommended_mutations", [])
                    mut_str = ", ".join(m["mutation"] for m in muts[:2]) if muts else "—"
                    purpose = muts[0]["purpose"] if muts else "candidate"
                    lines.append(
                        f"| {c['position']} | {c['wild_type']} | {mut_str} | "
                        f"{purpose} | {c.get('composite_priority', '—')} |\n"
                    )
                lines.append("\n")

        # Benchmark section
        if benchmark_data:
            lines.append("## Family & Conservation Analysis\n\n")
            family = benchmark_data.get("family", {})
            if family:
                lines.append(f"- **Family**: {family.get('name', 'Unknown')}\n")
                lines.append(f"- **EC**: {family.get('ec', 'N/A')}\n")
                lines.append(f"- **Mechanism**: {family.get('mechanism', 'N/A')}\n\n")

            motifs_found = benchmark_data.get("family_motifs", [])
            if motifs_found:
                lines.append("### Conserved Motifs\n\n")
                for m in motifs_found:
                    lines.append(f"- **{m.get('region', '?')}** ({m['pattern']}): {m.get('found_at', 'not found')}\n")
                lines.append("\n")

            known_successes = benchmark_data.get("known_engineering_successes", [])
            if known_successes:
                lines.append("### Known Engineering Successes in this Family\n\n")
                for s in known_successes:
                    if isinstance(s, dict):
                        lines.append(f"- {s.get('mutation', '?')}: {s.get('effect', '?')} ({s.get('organism', '?')})\n")
                lines.append("\n")

        # Enzyme function section
        if enzyme_data:
            lines.append("## Enzyme Function Prediction (EC Number)\n\n")
            predictions = enzyme_data.get("predictions", [])
            if predictions:
                lines.append("| # | EC Number | Class | Confidence | Name |\n")
                lines.append("|---|-----------|-------|------------|------|\n")
                for i, p in enumerate(predictions[:5]):
                    conf = p.get("confidence", "?")
                    lines.append(
                        f"| {i+1} | {p.get('ec_number', '?')} | {p.get('class', '?')} | "
                        f"{conf} | {p.get('name', '?')} |\n"
                    )
                lines.append("\n")
            lines.append(f"- **Model**: {enzyme_data.get('model', 'N/A')}\n\n")

        # Kcat kinetics section
        if kcat_data:
            lines.append("## Catalytic Kinetics (Kcat Prediction)\n\n")
            kcat = kcat_data.get("predicted_kcat_s1")
            if kcat is not None:
                lines.append(f"- **Predicted Kcat**: {kcat:.4f} s⁻¹\n")
                lines.append(f"- **Log10(Kcat)**: {kcat_data.get('predicted_log10_kcat', 'N/A')}\n")
                lines.append(f"- **Enzyme Class**: {kcat_data.get('enzyme_class', 'N/A')}\n")
                ci = kcat_data.get("confidence_interval_kcat_s1", [None, None])
                if ci[0] is not None:
                    lines.append(f"- **95% CI**: {ci[0]:.4f} — {ci[1]:.4f} s⁻¹\n")
                lines.append(f"- **Assessment**: {kcat_data.get('efficiency_assessment', 'N/A')}\n")
                lines.append(f"- **Method**: {kcat_data.get('method', 'N/A')}\n")
                lines.append("\n")

        # Design results section (binder / de novo design)
        if design_data:
            lines.append("## Protein Design Results\n\n")
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

        # Recommendations
        lines.append("## Recommendations & Experimental Plan\n\n")
        lines.append("### DO NOT MUTATE\n")
        lines.append("- Catalytic triad residues (Asp/Glu nucleophile, acid/base, stabilizer)\n")
        lines.append("- Ca²⁺/Zn²⁺ binding site residues\n")
        lines.append("- Conserved Cys in disulfide bonds\n\n")

        lines.append("### Experimental Validation Pipeline\n")
        lines.append("1. **Primary Screen**: Activity assay at target pH + original pH (n=3)\n")
        lines.append("2. **Secondary Screen**: kcat/Km determination for top 20% hits\n")
        lines.append("3. **Tertiary Screen**: Tm, t1/2 measurement at target conditions\n")
        lines.append("4. **Final**: Full kinetics + structural validation for top 3 candidates\n\n")

        lines.append("---\n")
        lines.append("*Report generated by Protein AI Platform — Expert Cluster Analysis Engine*\n")

        return "\n".join(lines)

    @staticmethod
    def _compact_result(tool_name: str, result: Any) -> str:
        """Build a compact JSON string from a tool result, prioritizing key fields.

        Large results (e.g., mutation_priority_score at 80KB) need key field extraction
        so the LLM and fallback report can see the summary and top candidates.
        """
        if not isinstance(result, dict):
            return str(result)[:5000]

        # Tools with known large outputs — extract key fields into a compact dict
        if tool_name == "mutation_priority_score":
            compact = {}
            for key in ("summary", "tier_1_candidates", "tier_2_candidates",
                        "engineering_goal", "sequence_length"):
                if key in result:
                    compact[key] = result[key]
            # Limit tier lists to top 10
            for tier_key in ("tier_1_candidates", "tier_2_candidates"):
                if tier_key in compact and isinstance(compact[tier_key], list):
                    compact[tier_key] = compact[tier_key][:10]
            try:
                return json.dumps(compact, ensure_ascii=False, default=str)
            except Exception:
                logger.debug("Compact JSON failed for mutation_priority_score, falling through")

        if tool_name == "mutation_scan":
            compact = {}
            for key in ("sequence_length", "scan_type", "positions_scanned", "results"):
                if key in result:
                    compact[key] = result[key] if key != "results" else result[key][:15]
            try:
                return json.dumps(compact, ensure_ascii=False, default=str)
            except Exception:
                logger.debug("Compact JSON failed for mutation_scan, falling through")

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
        provider: str | None = None, model: str | None = None,
    ) -> str:
        """Direct LLM chat reply for non-protein general conversation."""
        system_prompt = (
            "You are a helpful protein engineering AI assistant. "
            "The user's message does not appear to contain a specific protein analysis task. "
            "Respond naturally and helpfully. If you can, guide them toward describing "
            "a protein engineering goal — such as analyzing a sequence, designing a binder, "
            "predicting a structure, or scanning mutations. Keep your response concise."
        )
        try:
            resp = await self._call_llm(
                [{"role": "system", "content": system_prompt}, *history[-4:], {"role": "user", "content": message}],
                provider=provider, model=model, max_tokens=512,
            )
            return resp.choices[0].message.content or "Hello! How can I help with your protein research today?"
        except Exception:
            logger.exception("Chat reply LLM call failed")
            return "Hello! I'm a protein engineering AI assistant. How can I help you today?"

    async def _call_llm(self, messages: list[dict], provider: str | None = None, model: str | None = None, **kwargs) -> Any:
        """Run a sync chat_completion call in a thread pool to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(chat_completion_sync, messages, provider=provider, model=model, **kwargs),
        )

    # Errors that are transient and worth retrying once
    _RETRYABLE_ERRORS = ("connection", "timeout", "rate_limit", "rate_limited", "503", "502", "429")

    def _should_retry(self, step: PlanStep) -> bool:
        """Determine if a failed step should be retried once for transient errors."""
        error_lower = str(step.error).lower()
        return any(pattern in error_lower for pattern in self._RETRYABLE_ERRORS)


orchestrator = AgentOrchestrator()
