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
import re
import time

from app.core.llm import chat_completion, chat_completion_sync
from app.tools.registry import ToolRegistry
from app.core.skills import get_skills_metadata, read_skill
from app.core.agent_roles import (
    PI_SYSTEM_PROMPT, CB_SYSTEM_PROMPT,
    MLS_SYSTEM_PROMPT, SC_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
)


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

        tool_messages = []
        for i, step in enumerate(plan):
            self._snapshot.current_step = i + 1
            step.status = "running"
            self._snapshot.plan[i]["status"] = "running"
            yield self._emit_state()

            start = time.time()
            try:
                result = await ToolRegistry.execute(step.tool_name, step.params)
                step.status = "completed"
                step.result = result
                step.duration = round(time.time() - start, 2)
                self._snapshot.plan[i]["status"] = "completed"
                self._snapshot.step_results.append({
                    "step": i + 1, "tool": step.tool_name,
                    "status": "completed", "result_preview": str(result)[:500],
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
                        pass

            yield self._emit_state()

            tool_messages.append({
                "role": "tool",
                "tool_name": step.tool_name,
                "result": str(step.result)[:1000] if step.result else step.error,
                "status": step.status,
            })

        # --- Stage 4.5: SC REVIEW ---
        # Cross-validation: SC critically examines results, identifies gaps,
        # and may trigger supplementary tool execution before final synthesis.
        self._snapshot.stage = "review"
        yield self._emit_state()

        review_result = await self._review_results_sc(
            user_message, tool_messages, self._snapshot.research_notes, provider, model
        )

        # If SC finds gaps and requests supplementary execution
        if review_result.get("needs_supplement"):
            for extra in review_result.get("supplementary_steps", []):
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

                start = time.time()
                try:
                    result = await ToolRegistry.execute(extra_step.tool_name, extra_step.params)
                    extra_step.status = "completed"
                    extra_step.result = result
                    extra_step.duration = round(time.time() - start, 2)
                    idx = extra_step.id - 1
                    self._snapshot.plan[idx]["status"] = "completed"
                    self._snapshot.step_results.append({
                        "step": extra_step.id, "tool": extra_step.tool_name,
                        "status": "completed", "result_preview": str(result)[:500],
                        "duration": extra_step.duration,
                    })
                    tool_messages.append({
                        "role": "tool",
                        "tool_name": extra_step.tool_name,
                        "result": str(result)[:1000],
                        "status": "completed",
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
            pass
        return "general"

    async def _research_pi(
        self, message: str, history: list[dict], context: str,
        provider: str | None = None, model: str | None = None,
    ) -> str:
        """PI: Research phase — gather background, clarify requirements."""
        messages = [
            {"role": "system", "content": PI_SYSTEM_PROMPT},
            *history[-6:],  # Last 3 turns for context
            {"role": "user", "content": f"Task: {message}\nProtein context: {context}"},
        ]
        try:
            resp = await self._call_llm(messages, provider=provider, model=model, max_tokens=600)
            return resp.choices[0].message.content or ""
        except Exception:
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

        try:
            resp = await self._call_llm(messages, tools=self.tools_schema, provider=provider, model=model, max_tokens=1200)
            return self._parse_plan(resp, message)
        except Exception:
            # Fallback: generate steps from tool schema
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
        is_ph_lowering = any(kw in lower for kw in ["降低", "lower", "酸化", "耐酸", "酸性", "酸稳定"])
        is_ph_raising = any(kw in lower for kw in ["提高", "raise", "碱化", "耐碱", "碱性", "碱稳定"])
        is_thermo = any(kw in lower for kw in ["耐热", "热稳定", "thermostability", "tm", "温度", "heat"])
        if is_ph_lowering:
            eng_goal = "ph_lowering"
        elif is_ph_raising:
            eng_goal = "ph_raising"
        elif is_thermo:
            eng_goal = "thermostability"
        else:
            eng_goal = "general"

        has_sequence = len(seq) >= 10
        step_id = 0

        if has_sequence:
            # 1. BLAST search — identify family, conserved residues, mechanism
            if "blast_search" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "blast_search",
                    "Identify enzyme family, conserved catalytic residues, and homologs via BLAST",
                    {"sequence": seq, "database": "swissprot", "max_results": 10}))

            # 2. Protein benchmark — deep family analysis with built-in expert knowledge
            if "protein_benchmark" in tool_names and is_enzyme_eng:
                step_id += 1
                steps.append(PlanStep(step_id, "protein_benchmark",
                    "Deep enzyme family characterization: motif search, catalytic residue prediction, domain architecture, conservation analysis, engineering targets",
                    {"query_sequence": seq}))

            # 3. Structure prediction — essential for surface/site analysis
            if "esmfold_folding" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "esmfold_folding",
                    "Predict 3D protein structure for surface electrostatic and active site analysis",
                    {"sequence": seq}))

            # 4. Physicochemical properties — baseline metrics
            if "predict_properties" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "predict_properties",
                    "Compute molecular weight, isoelectric point, stability index, GRAVY, and secondary structure propensity",
                    {"sequence": seq}))

            # 5. Mutation scan — systematic residue-level engineering targets
            if "mutation_scan" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "mutation_scan",
                    "Systematically scan surface and active-site proximal residues for engineering candidates",
                    {"sequence": seq}))

            # 6. Multi-dimensional mutation priority scoring (core expert tool)
            if is_enzyme_eng and "mutation_priority_score" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "mutation_priority_score",
                    f"Score every residue on 5 dimensions for {eng_goal} engineering — Tier 1/2 candidates with specific mutations",
                    {"sequence": seq, "engineering_goal": eng_goal}))

            # 7. For enzyme engineering tasks, add MD simulation for stability validation
            if is_enzyme_eng and "gromacs_md" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "gromacs_md",
                    "Run molecular dynamics simulation to assess structural stability and identify flexible regions",
                    {"sequence": seq, "simulation_time_ns": 10.0}))

        # If no sequence, fall back to basic search/analysis
        if not steps:
            if "predict_properties" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "predict_properties",
                    "Analyze protein properties", {}))
            if "sequence_search" in tool_names:
                step_id += 1
                steps.append(PlanStep(step_id, "sequence_search",
                    "Search for relevant sequences", {"query": task[:200]}))

        return steps

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
            "   - Are there benchmarks or comparisons to known proteins?\n\n"
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
            pass

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

        messages = [
            {"role": "system", "content": SC_SYSTEM_PROMPT + domain_context},
            *history[-4:],
            {"role": "user", "content": (
                f"Task: {task}\n\n"
                f"Research notes: {research[:500]}\n\n"
                f"Tool results:\n{results_text}\n\n"
                "Synthesize a comprehensive scientific report with SPECIFIC residue-level "
                "recommendations. Include: enzyme family classification, catalytic residue "
                "identification, proposed mutations with positions and rationales, tiered "
                "priority ranking, experimental validation plan. NEVER give generic advice."
            )},
        ]
        try:
            resp = await self._call_llm(messages, provider=provider, model=model, max_tokens=3000)
            content = resp.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except Exception as e:
            pass

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
            elif tool == "blast_search" and status == "completed":
                lines.append("## 1. Enzyme Family Identification\n")
                lines.append(f"```\n{result_str[:500]}\n```\n")

        # Properties section
        if props_data:
            lines.append("## 2. Physicochemical Properties\n")
            lines.append(f"- **Molecular Weight**: {props_data.get('molecular_weight_kda', 'N/A')} kDa\n")
            lines.append(f"- **Isoelectric Point (pI)**: {props_data.get('isoelectric_point', 'N/A')}\n")
            lines.append(f"- **GRAVY**: {props_data.get('gravy', 'N/A')}\n")
            lines.append(f"- **Stability**: {props_data.get('stability', 'N/A')}\n")
            lines.append(f"- **Length**: {props_data.get('length', 'N/A')} residues\n\n")

        # Mutation priority section
        if mutation_data:
            lines.append("## 3. Mutation Priority Analysis\n\n")
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
            lines.append("## 4. Family & Conservation Analysis\n\n")
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

        # Recommendations
        lines.append("## 5. Recommendations & Experimental Plan\n\n")
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
    def _safe_parse_json(text: str) -> dict:
        """Try to parse a string as JSON, return empty dict on failure."""
        try:
            return json.loads(text) if isinstance(text, str) and text.strip() else {}
        except (json.JSONDecodeError, TypeError):
            # Try to extract JSON from text using eval-style parsing
            try:
                return eval(text) if isinstance(text, str) else {}
            except Exception:
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
            return "Hello! I'm a protein engineering AI assistant. How can I help you today?"

    async def _call_llm(self, messages: list[dict], provider: str | None = None, model: str | None = None, **kwargs) -> Any:
        """Run a sync chat_completion call in a thread pool to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(chat_completion_sync, messages, provider=provider, model=model, **kwargs),
        )

    def _should_retry(self, step: PlanStep) -> bool:
        """Determine if a failed step should be retried (per-cause budget)."""
        if "connection" in str(step.error).lower():
            return True
        if "timeout" in str(step.error).lower():
            return True
        return False


orchestrator = AgentOrchestrator()
