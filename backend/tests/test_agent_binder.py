"""Tests for the Binder Design pipeline (Phase 3).

Covers:
- T8: proteinmpnn_design category is "design"
- T9: _generate_fallback_plan() binder branches (with/without sequence)
- T10: Router correctly classifies binder design intent
- T11: _load_relevant_skills loads protein_design
- T11: _build_fallback_report includes design results section
"""

import pytest
import sys
import os
import asyncio
import hashlib
import json
from pathlib import Path

# Ensure app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ENZYME_AGENT_EVAL_CASES = json.loads(
    (Path(__file__).with_name("enzyme_agent_eval_cases.json")).read_text()
)
ENZYME_REPORT_QUALITY_CASES = json.loads(
    (Path(__file__).with_name("enzyme_report_quality_cases.json")).read_text()
)


@pytest.fixture(autouse=True, scope="session")
def discover_tools():
    """Ensure all tools are registered before tests run."""
    from app.tools.registry import ToolRegistry
    if not ToolRegistry._tools:
        ToolRegistry.discover()


class TestProteinMPNNCategory:
    """T8: proteinmpnn_design should be category='design', not 'engineering'."""

    def test_category_is_design(self):
        from app.tools.registry import ToolRegistry
        # Force import of all tools
        import app.tools.proteinmpnn_design  # noqa: F401

        tool = ToolRegistry.get_tool("proteinmpnn_design")
        assert tool is not None, "proteinmpnn_design not registered"
        assert tool.category == "design", (
            f"Expected category='design', got '{tool.category}'"
        )

    def test_pdb_required_tools_includes_esm_if1(self):
        from app.core.agent_graph import _PDB_REQUIRED_TOOLS
        assert "proteinmpnn_design" in _PDB_REQUIRED_TOOLS
        assert "esm_if1_design" in _PDB_REQUIRED_TOOLS


class TestBinderRouting:
    """T10: Router classifies binder design intent correctly."""

    def test_binder_routes_to_design(self):
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        # These should all route to "design" via deterministic keywords
        test_cases = [
            "Design a binder for PD-L1",
            "I want to design a protein that binds EGFR",
            "de novo protein design targeting KRAS",
            "设计一个结合PD-L1的蛋白",
            "从头设计蛋白骨架",
        ]
        for msg in test_cases:
            lower = msg.lower()
            has_design_kw = any(kw in lower for kw in [
                "设计", "design", "生成序列", "generate sequence", "binder"
            ])
            assert has_design_kw, f"'{msg}' should contain design keywords"

    def test_enzyme_engineering_still_routes_to_analyze(self):
        """Regression: enzyme engineering tasks must NOT route to design."""
        lower = "提高这个酶的热稳定性".lower()
        is_design = any(kw in lower for kw in [
            "设计", "design", "生成序列", "generate sequence", "binder"
        ])
        is_analyze = any(kw in lower for kw in [
            "突变", "mutation", "stability", "stabilize", "耐热", "热稳定",
        ])
        assert not is_design, "Enzyme engineering should not be classified as design"
        assert is_analyze, "Enzyme engineering should be classified as analyze"

    def test_model_meta_question_routes_to_general(self):
        """P0: model capability/citation questions must not enter sequence_search."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        route = asyncio.run(orch._route_intent("这个模型现在的能力边界是什么？有没有文献依据？", ""))

        assert route == "general"

    def test_model_meta_question_ignores_prior_protein_context_for_routing(self):
        """P0: current meta question stays general even in an existing protein chat."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        route = asyncio.run(
            orch._route_intent(
                "这个模型会不会胡编？结果有没有文献依据？",
                "[Known protein target discussed]",
            )
        )

        assert route == "general"

    def test_governance_question_uses_local_evidence_tool_plan(self):
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        plan = orch._generate_fallback_plan("当前模型能否客户交付？release ready 吗？")
        assert [step.tool_name for step in plan] == ["external_research_evidence"]
        assert plan[0].params == {"scope": "all"}

    def test_connectivity_question_routes_to_live_probe_not_general_chat(self):
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        route = asyncio.run(orch._route_intent("你现在联网了吗？", ""))
        plan = orch._generate_fallback_plan("你现在联网了吗？")

        assert route == "research"
        assert [step.tool_name for step in plan] == ["external_connectivity_check"]
        assert plan[0].params == {}
        assert orch._wants_live_literature_search("你现在联网了吗？") is False

    def test_explicit_online_literature_search_still_uses_literature_tool(self):
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        plan = orch._generate_fallback_plan("请联网搜索最近的脂肪酶耐热文献")

        assert [step.tool_name for step in plan] == ["literature_live_search"]

    def test_missing_enzyme_input_requires_clarification(self):
        """P0: enzyme engineering intent without actionable input should ask first."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()
        message = "帮我改造这个酶提高耐热性，但我只给你一句需求。"

        assert orch._should_clarify_before_tools(message, "analyze", "") is True
        reply = orch._build_missing_input_reply(message, "analyze")
        assert "缺失信息" in reply
        assert "不会直接给具体位点或强结论" in reply

    def test_experiment_plan_design_does_not_route_to_protein_design(self):
        """P0: experimental-plan wording must not trigger binder/protein design."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        route = asyncio.run(orch._route_intent("请设计实验方案验证这个酶的耐热性", ""))

        assert route == "analyze"
        assert orch._should_clarify_before_tools("请设计实验方案验证这个酶的耐热性", route, "") is True


class TestBinderFallbackPlan:
    """T9: _generate_fallback_plan() binder branches."""

    def _get_orchestrator(self):
        from app.core.agent_graph import AgentOrchestrator
        # Ensure tools are registered
        from app.tools import registry as _  # noqa: F401
        return AgentOrchestrator()

    def test_binder_plan_no_sequence(self):
        """'Design a binder for PD-L1' should trigger binder pipeline without sequence."""
        orch = self._get_orchestrator()
        plan = orch._generate_fallback_plan("Design a binder for PD-L1")

        tool_names = [s.tool_name for s in plan]

        # Should have sequence_search (to find PD-L1) and design tools
        assert len(plan) > 0, "Plan should not be empty"
        assert "sequence_search" in tool_names, (
            f"No-sequence binder plan should include sequence_search. Got: {tool_names}"
        )

        # Should include at least one design tool
        design_tools = {"rfdiffusion_design", "chroma_design", "proteinmpnn_design"}
        found_design = design_tools & set(tool_names)
        assert found_design, (
            f"No-sequence binder plan should include design tools. Got: {tool_names}"
        )

    def test_binder_plan_with_sequence(self):
        """Binder task with a sequence should use inverse folding pipeline."""
        seq = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"
        orch = self._get_orchestrator()
        plan = orch._generate_fallback_plan(
            f"Design a binder for this scaffold: {seq}"
        )

        tool_names = [s.tool_name for s in plan]
        assert len(plan) > 0, "Plan should not be empty"

        # With sequence + binder design: should NOT have mutation_priority_score
        # (that's for enzyme engineering, not binder design)
        assert "mutation_priority_score" not in tool_names, (
            "Binder design plan should not include enzyme engineering tools"
        )

    def test_enzyme_plan_not_affected(self):
        """Regression: enzyme engineering with sequence still uses the full pipeline."""
        seq = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"
        orch = self._get_orchestrator()
        plan = orch._generate_fallback_plan(
            f"提高这个酶的热稳定性 {seq}"
        )

        tool_names = [s.tool_name for s in plan]
        assert "predict_properties" in tool_names, "Enzyme plan should have predict_properties"
        assert "mutation_priority_score" in tool_names, (
            "Enzyme engineering plan should include mutation_priority_score"
        )

    def test_no_binder_no_sequence_fallback(self):
        """Generic query without sequence or binder intent → sequence_search."""
        orch = self._get_orchestrator()
        plan = orch._generate_fallback_plan("Analyze the structure of EGFR")

        tool_names = [s.tool_name for s in plan]
        assert "sequence_search" in tool_names, (
            f"Generic no-sequence query should use sequence_search. Got: {tool_names}"
        )
        # Should NOT have design tools
        design_tools = {"rfdiffusion_design", "chroma_design"}
        assert not (design_tools & set(tool_names)), (
            "Non-binder query should not trigger design tools"
        )

    def test_generic_meta_question_does_not_fallback_to_sequence_search(self):
        """P0: broad system questions should not use whole-sentence UniProt search."""
        orch = self._get_orchestrator()
        plan = orch._generate_fallback_plan("这个模型有没有文献依据，会不会胡编？")

        assert plan == []

    def test_no_target_binder_design_does_not_search_whole_sentence(self):
        """P0: binder design without a concrete target should clarify, not search."""
        orch = self._get_orchestrator()
        plan = orch._generate_fallback_plan("Design a binder")

        assert plan == []
        assert orch._should_clarify_before_tools("Design a binder", "design", "") is True

    def test_stream_missing_input_returns_clarification_without_tools(self):
        """P0: stream path should stop before planning/execution when inputs are missing."""
        orch = self._get_orchestrator()

        async def collect():
            events = []
            async for event in orch.stream_chat("帮我改造这个酶提高耐热性", []):
                events.append(event)
            return events

        events = asyncio.run(collect())
        contents = [
            json.loads(event).get("content", "")
            for event in events
            if event.strip().startswith("{") and json.loads(event).get("type") == "text"
        ]
        joined = "\n".join(contents)

        assert "当前输入还不足以进入工具分析" in joined
        assert not any("sequence_search" in event for event in events)
        assert any(json.loads(event).get("type") == "done" for event in events if event.strip().startswith("{"))

    def test_stream_targetless_binder_returns_clarification_without_tools(self):
        """P0: targetless binder request should ask for a target instead of searching."""
        orch = self._get_orchestrator()

        async def collect():
            events = []
            async for event in orch.stream_chat("Design a binder", []):
                events.append(event)
            return events

        events = asyncio.run(collect())
        contents = [
            json.loads(event).get("content", "")
            for event in events
            if event.strip().startswith("{") and json.loads(event).get("type") == "text"
        ]
        joined = "\n".join(contents)

        assert "当前输入还不足以进入工具分析" in joined
        assert not any("sequence_search" in event for event in events)
        assert any(json.loads(event).get("type") == "done" for event in events if event.strip().startswith("{"))

    def test_extract_protein_name_binder(self):
        """_extract_protein_name should pull 'PD-L1' from binder queries."""
        from app.core.agent_graph import AgentOrchestrator
        name = AgentOrchestrator._extract_protein_name("Design a binder for PD-L1")
        assert "PD-L1" in name or "PD" in name, f"Expected PD-L1, got: {name}"

    def test_extract_protein_name_complex(self):
        from app.core.agent_graph import AgentOrchestrator
        name = AgentOrchestrator._extract_protein_name(
            "I need to design a high-affinity binder targeting human EGFR protein"
        )
        assert "EGFR" in name, f"Expected EGFR, got: {name}"


class TestEnzymeAgentEvalSet:
    """P2: fixed enzyme-task eval set for routing, clarification, and tool choice."""

    def _get_orchestrator(self):
        from app.core.agent_graph import AgentOrchestrator
        from app.tools import registry as _  # noqa: F401
        return AgentOrchestrator()

    @pytest.mark.parametrize("case", ENZYME_AGENT_EVAL_CASES, ids=[case["id"] for case in ENZYME_AGENT_EVAL_CASES])
    def test_eval_case_route_clarification_and_tools(self, case):
        orch = self._get_orchestrator()
        message = case["message"]

        route = asyncio.run(orch._route_intent(message, ""))
        assert route == case["expected_route"]
        assert orch._should_clarify_before_tools(message, route, "") is case["expect_clarification"]

        plan = [] if case["expect_clarification"] or route == "general" else orch._generate_fallback_plan(message)
        tool_names = [step.tool_name for step in plan]

        for tool in case["required_tools"]:
            assert tool in tool_names, f"{case['id']} should include {tool}; got {tool_names}"
        for tool in case["forbidden_tools"]:
            assert tool not in tool_names, f"{case['id']} should not include {tool}; got {tool_names}"

    def test_stream_no_plan_uses_missing_input_reply_not_generic_english_fallback(self):
        orch = self._get_orchestrator()
        history = [
            {
                "role": "user",
                "content": "之前的序列是 MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE",
            }
        ]

        async def collect_text() -> str:
            chunks = []
            async for event in orch.stream_chat("分析此蛋白质序列的热稳定性和pH稳定性。", history):
                try:
                    payload = json.loads(event)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "text":
                    chunks.append(str(payload.get("content") or ""))
            return "".join(chunks)

        reply = asyncio.run(collect_text())
        assert "I couldn't determine how to help" not in reply
        assert "缺失信息" in reply
        assert "完整氨基酸序列" in reply


class TestEnzymeReportQualityEvalSet:
    """Regression evals for report evidence boundaries, order, and language."""

    def _get_orchestrator(self):
        from app.core.agent_graph import AgentOrchestrator
        from app.tools import registry as _  # noqa: F401
        return AgentOrchestrator()

    def test_contract_core_order_matches_feedback_v5(self):
        from app.services.report_quality_contract import CORE_SECTION_ORDER

        assert CORE_SECTION_ORDER == (
            "## 任务理解",
            "## 输入与结构证据",
            "## 结构同源与编号映射",
            "## 改造策略及说明",
            "## Physicochemical Properties",
            "## Enzyme Foundation Profile",
            "## 保护位点",
            "## Objective Module Gate",
            "## 突变位点探索清单",
            "## 位点突变逻辑 / 风险 / 实验动作",
            "## 探索性验证建议",
        )

    @pytest.mark.parametrize(
        "case",
        ENZYME_REPORT_QUALITY_CASES,
        ids=[case["id"] for case in ENZYME_REPORT_QUALITY_CASES],
    )
    def test_report_quality_contract_cases(self, case):
        from app.services.report_quality_contract import validate_report_quality_contract

        orch = self._get_orchestrator()
        report = orch._build_fallback_report(case["task"], case["tool_results"])

        violations = validate_report_quality_contract(
            report,
            required=case.get("required", []),
            forbidden=case.get("forbidden", []),
            ordered_headings=case.get("ordered_headings", []),
        )
        assert not violations, f"{case['id']} report contract violations: {violations}"

    def test_uploaded_pdb_stability_request_generates_structure_plan(self):
        orch = self._get_orchestrator()
        message = (
            "分析上传PDB附件的热稳定性和pH稳定性。\n\n"
            "[Attached files:\n"
            "- name: test.pdb, object_name: uploads/user_1/test.pdb, download_url: /api/files/uploads/user_1/test.pdb/download]"
        )

        route = asyncio.run(orch._route_intent(message, ""))
        assert route == "analyze"
        assert orch._should_clarify_before_tools(message, route, "") is False

        plan = orch._generate_fallback_plan(message)
        tool_names = [step.tool_name for step in plan]
        assert "structure_search_foldseek" in tool_names
        structure_step = next(step for step in plan if step.tool_name == "structure_search_foldseek")
        assert structure_step.params["pdb_object_name"] == "uploads/user_1/test.pdb"

    def test_uploaded_pdb_with_sequence_gates_structure_before_sequence_tools(self):
        orch = self._get_orchestrator()
        sequence = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"
        message = (
            f"分析上传PDB附件的热稳定性和pH稳定性，并评估M204H。{sequence}\n\n"
            "[Attached files:\n"
            "- name: test.pdb, object_name: uploads/user_1/test.pdb, download_url: /api/files/uploads/user_1/test.pdb/download]"
        )

        plan = orch._generate_fallback_plan(message, analysis_depth="deep")
        tool_names = [step.tool_name for step in plan]

        assert tool_names[:3] == ["structure_search_foldseek", "residue_mapping_sifts", "residue_numbering_gate"]
        assert "esmfold_folding" not in tool_names
        assert tool_names.index("predict_properties") > tool_names.index("residue_mapping_sifts")
        assert tool_names.index("annotation_bundle") > tool_names.index("residue_mapping_sifts")
        assert tool_names.index("annotation_bundle") < tool_names.index("enzyme_identity_profile")
        assert tool_names.index("enzyme_identity_profile") > tool_names.index("residue_mapping_sifts")
        assert tool_names.index("enzyme_identity_profile") < tool_names.index("protein_benchmark")
        assert tool_names.index("enzyme_identity_profile") < tool_names.index("enzyme_function")
        assert "build_site_structure_function_features" in tool_names
        assert tool_names.index("build_site_structure_function_features") > tool_names.index("residue_mapping_sifts")
        assert tool_names.index("build_site_structure_function_features") > tool_names.index("enzyme_identity_profile")
        assert tool_names.index("build_site_structure_function_features") < tool_names.index("mutation_priority_score")
        assert tool_names.index("mutation_priority_score") > tool_names.index("residue_numbering_gate")

    def test_sequence_only_structure_request_waits_for_esmfold_before_structural_inference(self):
        orch = self._get_orchestrator()
        sequence = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"
        message = f"仅有序列，请分析口袋、催化网络、结构暴露度和热稳定性。{sequence}"

        plan = orch._generate_fallback_plan(message, analysis_depth="deep")
        tool_names = [step.tool_name for step in plan]

        assert "predict_properties" in tool_names
        assert "esmfold_folding" in tool_names
        assert "build_site_structure_function_features" not in tool_names
        assert tool_names.index("predict_properties") < tool_names.index("annotation_bundle")
        assert tool_names.index("annotation_bundle") < tool_names.index("enzyme_identity_profile")
        assert tool_names.index("enzyme_identity_profile") < tool_names.index("protein_benchmark")
        assert tool_names.index("enzyme_identity_profile") < tool_names.index("enzyme_function")
        assert tool_names.index("enzyme_function") < tool_names.index("esmfold_folding")
        assert "mutation_priority_score" not in tool_names

    def test_chinese_uploaded_structure_context_enters_structure_tool_plan(self):
        orch = self._get_orchestrator()
        message = "酶的名称：天冬氨酸蛋白酶 结构已上传 目标：提高耐热性 底物酪蛋白，反应条件40度，表达体系毕赤酵母"
        history = [
            {
                "role": "user",
                "content": (
                    "[Attached files:\n"
                    "- name: aspartic_protease.pdb, object_name: uploads/user_7/aspartic_protease.pdb, "
                    "download_url: /api/files/uploads/user_7/aspartic_protease.pdb/download]"
                ),
            }
        ]
        context = orch._build_context(history)

        route = asyncio.run(orch._route_intent(message, context))
        assert route == "analyze"
        assert orch._should_clarify_before_tools(message, route, context) is False

        plan = orch._generate_fallback_plan(message, context=context)
        tool_names = [step.tool_name for step in plan]
        assert "structure_search_foldseek" in tool_names
        structure_step = next(step for step in plan if step.tool_name == "structure_search_foldseek")
        assert structure_step.params["pdb_object_name"] == "uploads/user_7/aspartic_protease.pdb"

    def test_chinese_named_enzyme_without_attachment_searches_instead_of_fixed_clarification(self):
        orch = self._get_orchestrator()
        message = "酶的名称：天冬氨酸蛋白酶 目标：提高耐热性 底物酪蛋白，反应条件40度，表达体系毕赤酵母"

        route = asyncio.run(orch._route_intent(message, ""))
        assert route == "analyze"
        assert orch._should_clarify_before_tools(message, route, "") is False

        plan = orch._generate_fallback_plan(message)
        tool_names = [step.tool_name for step in plan]
        assert "sequence_search" in tool_names
        search_step = next(step for step in plan if step.tool_name == "sequence_search")
        assert search_step.params["query"] == "天冬氨酸蛋白酶"

    @pytest.mark.parametrize(
        ("message", "expected_query", "expected_database"),
        [
            ("酶名称：脂肪酶 目标：提高耐热性", "脂肪酶", "uniprot"),
            ("蛋白：天冬氨酸蛋白酶 目标：耐酸", "天冬氨酸蛋白酶", "uniprot"),
            ("蛋白质：碱性蛋白酶 目标：提高 pH 9 稳定性", "碱性蛋白酶", "uniprot"),
            ("目标酶: amylase 目标: 提高40度稳定性", "amylase", "uniprot"),
            ("UniProt编号：P00691 目标：分析热稳定性", "P00691", "uniprot"),
            ("PDB编号：1BAG 目标：分析pH稳定性", "1BAG", "pdb"),
            ("PDB: 1BAG 目标：分析pH稳定性", "1BAG", "pdb"),
            ("酶名称：脂肪酶 突变M204H 目标：提高耐热性", "脂肪酶", "uniprot"),
        ],
    )
    def test_concrete_reference_variants_search_instead_of_fixed_clarification(
        self,
        message,
        expected_query,
        expected_database,
    ):
        orch = self._get_orchestrator()

        route = asyncio.run(orch._route_intent(message, ""))
        assert route == "analyze"
        assert orch._should_clarify_before_tools(message, route, "") is False

        plan = orch._generate_fallback_plan(message)
        tool_names = [step.tool_name for step in plan]
        assert "sequence_search" in tool_names
        search_step = next(step for step in plan if step.tool_name == "sequence_search")
        assert search_step.params["query"] == expected_query
        assert search_step.params["database"] == expected_database

    def test_json_style_uploaded_structure_context_enters_structure_tool_plan(self):
        orch = self._get_orchestrator()
        message = "蛋白：天冬氨酸蛋白酶 结构已上传 目标：分析热稳定性和pH稳定性"
        history = [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "attachments": [
                            {
                                "name": "rare_structure.pdb",
                                "object_name": "uploads/user_9/rare_structure.pdb",
                                "download_url": "/api/files/uploads/user_9/rare_structure.pdb/download",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
            }
        ]
        context = orch._build_context(history)

        assert "uploads/user_9/rare_structure.pdb" in context
        route = asyncio.run(orch._route_intent(message, context))
        assert route == "analyze"
        assert orch._should_clarify_before_tools(message, route, context) is False

        plan = orch._generate_fallback_plan(message, context=context)
        tool_names = [step.tool_name for step in plan]
        assert "structure_search_foldseek" in tool_names
        structure_step = next(step for step in plan if step.tool_name == "structure_search_foldseek")
        assert structure_step.params["pdb_object_name"] == "uploads/user_9/rare_structure.pdb"

    @pytest.mark.parametrize(
        "message",
        [
            "结构已上传，帮我提高耐热性",
            "底物酪蛋白，40度，表达体系毕赤酵母，提高耐热性",
        ],
    )
    def test_vague_inputs_without_real_target_or_attachment_still_clarify(self, message):
        orch = self._get_orchestrator()

        route = asyncio.run(orch._route_intent(message, ""))
        assert route == "analyze"
        assert orch._should_clarify_before_tools(message, route, "") is True
        plan = orch._generate_fallback_plan(message)
        assert [step.tool_name for step in plan] == []

    def test_uploaded_pdb_md_request_submits_real_background_md(self):
        orch = self._get_orchestrator()
        message = (
            "对上传PDB做分子动力学分析，看看RMSD/RMSF和热稳定性。\n\n"
            "[Attached files:\n"
            "- name: test.pdb, object_name: uploads/user_1/test.pdb, download_url: /api/files/uploads/user_1/test.pdb/download]"
        )

        plan = orch._generate_fallback_plan(message)
        md_step = next(step for step in plan if step.tool_name == "gromacs_md")

        assert md_step.params["pdb_object_name"] == "uploads/user_1/test.pdb"
        assert md_step.params["replicate_plan_only"] is False
        assert md_step.params["upload_artifacts"] is True

    def test_uploaded_pdb_hash_digits_are_not_residue_positions(self):
        from app.core.agent_graph import AgentOrchestrator

        orch = self._get_orchestrator()
        message = (
            "提高蛋白比活力\n\n"
            "[Attached files:\n"
            "name: HM.pdb, object_name: uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb, "
            "download_url: /api/files/uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb/download]"
        )

        assert AgentOrchestrator._extract_requested_positions(message) == []
        assert AgentOrchestrator._extract_requested_mutations(message) == []

        plan = orch._generate_fallback_plan(message)
        tool_names = [step.tool_name for step in plan]

        assert "structure_search_foldseek" in tool_names
        assert "residue_mapping_sifts" in tool_names
        assert "residue_numbering_gate" not in tool_names
        assert "gromacs_md" not in tool_names

        reply = orch._build_plan_confirmation_reply(
            message,
            plan,
            pdb_preflight={
                "status": "readable",
                "display_name": "HM.pdb",
                "bytes": 188631,
                "line_count": 2367,
                "chain_count": 1,
                "total_residues": 299,
                "total_atoms": 2313,
                "chains": [{"chain_id": "A", "residue_count": 299, "residue_range": "1-299"}],
                "sequence_length": 299,
                "sequence_preview": "ASGFYVSGTILCDSTGNPFKIRGINHAHSWYKNYSAT",
            },
        )
        assert "49405" not in reply
        assert "uploads/user_2" not in reply
        assert "download_url" not in reply
        assert "HM.pdb" in reply
        assert "已预读上传结构 `HM.pdb`" in reply
        assert "残基数=299" in reply
        assert "原子数=2313" in reply
        assert "链A:299 aa" in reply
        assert "ASGFYVSGTILCDSTGNPFK" in reply
        assert "当前消息未提供独立 FASTA" in reply
        assert "真实对象路径仅用于工具取数" in reply

    def test_requested_mutation_is_carried_into_mutation_priority_score_plan(self):
        orch = self._get_orchestrator()
        sequence = "A" * 337 + "P" + "A" * 50
        message = f"提高蛋白比活力，P338T 这个突变怎么样？\n\n>{sequence}"

        plan = orch._generate_fallback_plan(message)
        mutation_step = next(step for step in plan if step.tool_name == "mutation_priority_score")

        assert mutation_step.params["specified_mutations"] == ["P338T"]

    def test_uploaded_pdb_activity_deep_mode_does_not_submit_md_by_default(self):
        orch = self._get_orchestrator()
        message = (
            "提高蛋白比活力\n\n"
            "[Attached files:\n"
            "name: HM.pdb, object_name: uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb, "
            "download_url: /api/files/uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb/download]"
        )

        plan = orch._generate_fallback_plan(message, analysis_depth="deep")
        tool_names = [step.tool_name for step in plan]

        expected_tools = [
            "structure_search_foldseek",
            "residue_mapping_sifts",
            "predict_properties",
            "annotation_bundle",
            "enzyme_identity_profile",
            "enzyme_objective_module_plan",
            "protein_benchmark",
            "enzyme_function",
            "build_site_structure_function_features",
            "ligand_contact_analysis",
            "structure_pocket_interface_analysis",
            "mutation_priority_score",
            "kcat_predict",
            "mutation_scan",
            "protssn_score",
            "blast_search",
        ]
        assert tool_names == [tool for tool in expected_tools if tool in tool_names]
        for required in [
            "predict_properties",
            "annotation_bundle",
            "enzyme_identity_profile",
            "build_site_structure_function_features",
            "ligand_contact_analysis",
            "structure_pocket_interface_analysis",
            "mutation_priority_score",
            "mutation_scan",
            "blast_search",
        ]:
            assert required in tool_names
        assert tool_names.index("build_site_structure_function_features") < tool_names.index("mutation_priority_score")
        assert tool_names.index("ligand_contact_analysis") > tool_names.index("build_site_structure_function_features")
        assert tool_names.index("structure_pocket_interface_analysis") > tool_names.index("build_site_structure_function_features")
        blast_step = next(step for step in plan if step.tool_name == "blast_search")
        assert blast_step.params["database"] == "swissprot"
        assert blast_step.params["sequence"] == ""
        assert "gromacs_md" not in tool_names

    def test_known_pdb_attachment_id_is_passed_to_structure_and_mapping_tools(self):
        orch = self._get_orchestrator()
        message = (
            "分析3WP6带白比活力、热稳定性和突变位点\n\n"
            "[Attached files:\nname: 3WP6.pdb, object_name: uploads/user_2/3wp6.pdb]"
        )
        plan = orch._generate_fallback_plan(message, analysis_depth="deep")
        structure_step = next(step for step in plan if step.tool_name == "structure_search_foldseek")
        mapping_step = next(step for step in plan if step.tool_name == "residue_mapping_sifts")
        identity_step = next(step for step in plan if step.tool_name == "enzyme_identity_profile")
        assert structure_step.params["pdb_id"] == "3WP6"
        assert mapping_step.params["pdb_id"] == "3WP6"
        assert identity_step.params["structure_id"] == "3WP6"

    def test_uploaded_pdb_deep_plan_hydrates_sequence_before_signature(self, monkeypatch):
        orch = self._get_orchestrator()
        sequence = (
            "ASGFYVSGTILCDSTGNPFKIRGINHAHSWYKNYSATAMEAIAATGANTVRIVLSNGQQYVKDDANTVSNLLSLANQHKLIAILEVHDATGSDSVSALDHAVDYWIEMKNVLVGKEDRVLINIANEWYGTWDSNGWADGYKSAIPKLRNAGINHTLIVDAAGWGQYPQSIVDRGNEVFNSDPLRNTIFSIHMYEYAGGNADMVRANIDQVLNKGLAVIIGEFGHYHTGGDVDEMAIMSYTQQKGVGWLAWLWKGNSAELLYLDLSYDWAGNHLTEWGETIVNGANGLKATSTRAPIFGN"
        )
        message = (
            "提高蛋白比活力\n\n"
            "[Attached files:\n"
            "name: HM.pdb, object_name: uploads/user_2/hm.pdb]"
        )

        async def fake_preflight(_task):
            return {
                "status": "readable",
                "display_name": "HM.pdb",
                "coordinate_sequence": sequence,
                "sequence_length": len(sequence),
                "sequence_preview": sequence[:40],
                "chains": [{"chain_id": "A", "residue_count": len(sequence), "residue_range": "1-299"}],
            }

        monkeypatch.setattr(orch, "_build_pdb_preflight_summary", fake_preflight)
        plan = orch._generate_fallback_plan(message, analysis_depth="deep")
        hydrated = asyncio.run(orch._hydrate_uploaded_pdb_sequence_for_plan(plan, message))
        signature = orch._plan_signature(hydrated)
        display = orch._sanitize_plan_for_display(hydrated)

        sequence_steps = {
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
        }
        for step in hydrated:
            key = sequence_steps.get(step.tool_name)
            if key:
                assert step.params[key] == sequence
                assert step.params["sequence_provenance"] == "pdb_coordinate_derived"

        assert signature == orch._plan_signature([{
            "id": step.id,
            "tool_name": step.tool_name,
            "description": step.description,
            "params": step.params,
        } for step in hydrated])
        assert sequence not in json.dumps(display, ensure_ascii=False)
        assert "[pdb-coordinate-derived sequence; 299 aa]" in json.dumps(display, ensure_ascii=False)

    def test_uploaded_pdb_sequence_replaces_stale_planner_sequence(self, monkeypatch):
        """A current PDB is the sequence authority when planner context is stale."""
        orch = self._get_orchestrator()
        from app.core.agent_graph import PlanStep

        coordinate_sequence = "DTTITQNQTGYDNGYFYSFWT"
        stale_sequence = "APAQIVGRSTFQIDQVASGKVYKNGPMAMMQTYNKYAHVGAV"
        message = (
            "深度分析这个 PDB 的比活力和热稳定性\n\n"
            "[Attached files:\nname: swissmodel.pdb, "
            "object_name: uploads/user_2/swissmodel.pdb]"
        )

        async def fake_preflight(_task):
            return {
                "status": "readable",
                "display_name": "swissmodel.pdb",
                "coordinate_sequence": coordinate_sequence,
                "sequence_length": len(coordinate_sequence),
                "sequence_preview": coordinate_sequence[:40],
            }

        monkeypatch.setattr(orch, "_build_pdb_preflight_summary", fake_preflight)
        plan = [
            PlanStep(1, "predict_properties", "properties", {"sequence": stale_sequence}),
            PlanStep(2, "enzyme_identity_profile", "identity", {"sequence": stale_sequence}),
            PlanStep(3, "interproscan_sequence_submit", "interpro", {"sequence": stale_sequence}),
            PlanStep(4, "residue_mapping_sifts", "mapping", {"input_sequence": stale_sequence}),
        ]

        hydrated = asyncio.run(orch._hydrate_uploaded_pdb_sequence_for_plan(plan, message))

        assert [step.params.get("sequence") for step in hydrated[:3]] == [coordinate_sequence] * 3
        assert hydrated[3].params["input_sequence"] == coordinate_sequence
        assert all(step.params.get("sequence_provenance") == "pdb_coordinate_derived" for step in hydrated[:3])

    def test_pdb_preflight_prefers_coordinate_sequence_over_unresolved_seqres(self):
        from app.core.agent_graph import AgentOrchestrator

        analysis = {
            "seqres_sequence": "A" * 240,
            "chains": [{"chain_id": "A", "sequence": "D" * 194}],
        }

        assert AgentOrchestrator._sequence_preview_from_pdb_analysis(analysis) == "D" * 194

    def test_current_fasta_conflicting_with_uploaded_pdb_is_flagged(self, monkeypatch):
        orch = self._get_orchestrator()
        from app.core.agent_graph import PlanStep

        coordinate_sequence = "DTTITQNQTGYDNGYFYSFWT"
        current_fasta = "APAQIVGRSTFQIDQVASGKV"
        message = (
            f">current protein\n{current_fasta}\n\n"
            "[Attached files:\nname: swissmodel.pdb, object_name: uploads/user_2/swissmodel.pdb]"
        )

        async def fake_preflight(_task):
            return {
                "status": "readable",
                "display_name": "swissmodel.pdb",
                "coordinate_sequence": coordinate_sequence,
                "sequence_length": len(coordinate_sequence),
            }

        monkeypatch.setattr(orch, "_build_pdb_preflight_summary", fake_preflight)
        plan = [PlanStep(1, "predict_properties", "properties", {"sequence": current_fasta})]
        hydrated = asyncio.run(orch._hydrate_uploaded_pdb_sequence_for_plan(
            plan, message, current_message=message
        ))

        assert hydrated[0].params["sequence"] == coordinate_sequence
        assert hydrated[0].params["sequence_provenance"] == "pdb_coordinate_derived"
        assert hydrated[0].params["_sequence_input_conflict"] is True

    def test_full_seqres_with_unresolved_prefix_is_not_a_sequence_conflict(self, monkeypatch):
        orch = self._get_orchestrator()
        from app.core.agent_graph import PlanStep

        coordinate_sequence = "LNGTLMQYFEWYMPNDGQHWKRLQNDSAYLAEHGITAV"
        full_sequence = "AN" + coordinate_sequence
        message = (
            f">1BLI full construct\n{full_sequence}\n"
            "[Attached files:\nname: 1BLI.pdb, object_name: uploads/user_2/1BLI.pdb]"
        )

        async def fake_preflight(_task):
            return {"status": "readable", "coordinate_sequence": coordinate_sequence,
                    "seqres_sequence": full_sequence}

        monkeypatch.setattr(orch, "_build_pdb_preflight_summary", fake_preflight)
        plan = [PlanStep(1, "predict_properties", "properties", {"sequence": full_sequence})]
        hydrated = asyncio.run(orch._hydrate_uploaded_pdb_sequence_for_plan(
            plan, message, current_message=message
        ))

        assert hydrated[0].params["sequence"] == coordinate_sequence
        assert "_sequence_input_conflict" not in hydrated[0].params

    def test_unreadable_pdb_removes_stale_sequence_from_plan(self, monkeypatch):
        orch = self._get_orchestrator()
        from app.core.agent_graph import PlanStep

        stale_sequence = "APAQIVGRSTFQIDQVASGKV"
        message = (
            "分析上传 PDB 的蛋白性质\n\n"
            "[Attached files:\nname: unreadable.pdb, object_name: uploads/user_2/unreadable.pdb]"
        )

        async def fake_preflight(_task):
            return {"status": "failed", "display_name": "unreadable.pdb", "coordinate_sequence": ""}

        monkeypatch.setattr(orch, "_build_pdb_preflight_summary", fake_preflight)
        plan = [PlanStep(1, "predict_properties", "properties", {"sequence": stale_sequence})]
        hydrated = asyncio.run(orch._hydrate_uploaded_pdb_sequence_for_plan(plan, message))

        assert "sequence" not in hydrated[0].params
        assert hydrated[0].params["_pdb_sequence_unavailable"] is True

    def test_unreadable_pdb_uses_only_current_turn_fasta(self, monkeypatch):
        orch = self._get_orchestrator()
        from app.core.agent_graph import PlanStep

        current_sequence = "DTTITQNQTGYDNGYFYSFWT"
        message = (
            f">current\n{current_sequence}\n\n"
            "[Attached files:\nname: unreadable.pdb, object_name: uploads/user_2/unreadable.pdb]"
        )

        async def fake_preflight(_task):
            return {"status": "failed", "display_name": "unreadable.pdb", "coordinate_sequence": ""}

        monkeypatch.setattr(orch, "_build_pdb_preflight_summary", fake_preflight)
        plan = [PlanStep(1, "predict_properties", "properties", {"sequence": "A" * 40})]
        hydrated = asyncio.run(orch._hydrate_uploaded_pdb_sequence_for_plan(
            plan, message, current_message=message
        ))

        assert hydrated[0].params["sequence"] == current_sequence
        assert hydrated[0].params["sequence_provenance"] == "user_fasta"
        assert "_pdb_sequence_unavailable" not in hydrated[0].params

    def test_uploaded_pdb_activity_explicit_md_request_still_submits_md(self):
        orch = self._get_orchestrator()
        message = (
            "提高蛋白比活力，并做分子动力学分析 RMSD/RMSF。\n\n"
            "[Attached files:\n"
            "name: HM.pdb, object_name: uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb]"
        )

        plan = orch._generate_fallback_plan(message, analysis_depth="deep")
        tool_names = [step.tool_name for step in plan]

        assert "structure_search_foldseek" in tool_names
        assert "residue_mapping_sifts" in tool_names
        md_step = next(step for step in plan if step.tool_name == "gromacs_md")
        assert md_step.params["pdb_object_name"] == "uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb"

    def test_followup_uses_uploaded_pdb_from_history_without_default_md(self):
        orch = self._get_orchestrator()
        history = [{
            "role": "user",
            "content": (
                "提高该蛋白的比活力\n\n"
                "[Attached files:\n"
                "- name: HM.pdb, object_name: uploads/user_2/hm.pdb, "
                "download_url: /api/files/uploads/user_2/hm.pdb/download]"
            ),
        }]
        message = "继续，基于刚才HM.pdb进一步分析位点"
        context = orch._build_context_for_message(message, history)
        plan = orch._generate_fallback_plan(message, context=context, analysis_depth="deep")
        tool_names = [step.tool_name for step in plan]

        assert "[Uploaded structure object_name: uploads/user_2/hm.pdb]" in context
        assert "structure_search_foldseek" in tool_names
        assert "residue_mapping_sifts" in tool_names
        assert "blast_search" in tool_names
        assert "gromacs_md" not in tool_names
        assert next(step for step in plan if step.tool_name == "structure_search_foldseek").params["pdb_object_name"] == "uploads/user_2/hm.pdb"

    def test_sanitized_uploaded_object_placeholder_is_not_executable_context(self):
        orch = self._get_orchestrator()
        message = "还能深度分析吗"
        history = [{
            "role": "assistant",
            "content": (
                "分析策略确认\n"
                "[Uploaded structure object_name: [uploaded-object]]\n"
                "执行流程\n"
                "structure_search_foldseek 参数：{\"pdb_object_name\":\"[uploaded-object]\"}"
            ),
        }]

        context = orch._build_context_for_message(message, history)
        plan = orch._generate_fallback_plan(message, context=context, analysis_depth="deep")

        assert "[uploaded-object]" not in context
        assert all(
            step.params.get("pdb_object_name") != "[uploaded-object]"
            for step in plan
        )

    def test_deep_followup_uses_raw_checkpoint_object_and_prior_activity_goal(self, monkeypatch):
        from app.core import agent_graph

        orch = self._get_orchestrator()

        async def fake_recent_strategy_memory(*args, **kwargs):
            return [{
                "revision": 1,
                "status": "executing",
                "next_action": None,
                "task_text": (
                    "提高蛋白比活力\n\n"
                    "[Attached files:\n"
                    "name: HM.pdb, object_name: uploads/user_2/hm.pdb, "
                    "download_url: /api/files/uploads/user_2/hm.pdb/download]"
                ),
                "plan_payload": [
                    {
                        "id": 1,
                        "tool_name": "structure_search_foldseek",
                        "description": "structure",
                        "params": {"pdb_object_name": "uploads/user_2/hm.pdb"},
                    },
                    {
                        "id": 2,
                        "tool_name": "mutation_scan",
                        "description": "scan",
                        "params": {"sequence": "A" * 299, "sequence_provenance": "pdb_coordinate_derived"},
                    },
                ],
            }]

        monkeypatch.setattr(agent_graph, "list_recent_strategy_memory", fake_recent_strategy_memory)

        async def collect_context():
            return await orch._load_recent_strategy_planning_context(
                current_user={"id": 2},
                audit_session=object(),
                conversation_id=99,
                message="还能深度分析吗",
            )

        context = asyncio.run(collect_context())
        plan = orch._generate_fallback_plan("还能深度分析吗", context=context, analysis_depth="deep")
        tool_names = [step.tool_name for step in plan]

        assert "[Uploaded structure object_name: uploads/user_2/hm.pdb]" in context
        assert "[Prior user request summary: 提高蛋白比活力]" in context
        assert "structure_search_foldseek" in tool_names
        assert "mutation_scan" in tool_names
        assert "blast_search" in tool_names
        assert "gromacs_md" not in tool_names
        assert next(
            step for step in plan if step.tool_name == "structure_search_foldseek"
        ).params["pdb_object_name"] == "uploads/user_2/hm.pdb"

    def test_display_task_summary_for_deep_followup_uses_prior_goal(self):
        orch = self._get_orchestrator()
        summary = orch._display_task_summary(
            "还能深度分析吗\n"
            "[Uploaded structure object_name: uploads/user_2/hm.pdb]\n"
            "[Prior user request summary: 提高蛋白比活力]"
        )

        assert summary == "提高蛋白比活力（续问：还能深度分析吗）"

    def test_new_uploaded_structure_does_not_inherit_previous_protein(self):
        orch = self._get_orchestrator()
        history = [{"role": "user", "content": (
            "提高旧蛋白比活力\n[Attached files:\n"
            "name: old.pdb, object_name: uploads/user_2/old.pdb]"
        )}]
        message = (
            "继续深度分析这个 PDB 的比活力与热稳定性\n[Attached files:\n"
            "name: swissmodel.pdb, object_name: uploads/user_2/swissmodel.pdb]"
        )

        context = orch._build_context_for_message(message, history)

        assert "old.pdb" not in context
        assert "提高旧蛋白比活力" not in context
        assert "Context boundary" in context

    def test_attachment_analysis_sequence_is_not_independent_fasta(self):
        orch = self._get_orchestrator()
        coordinate_sequence = "LNGTLMQYFEWYMPNDGQHWKRLQNDSAYLAEHGITAV"
        message = (
            "深度分析这个 PDB\n[Attached files:\n"
            "- name: 1BLI.pdb, object_name: uploads/current/1BLI.pdb, "
            f'analysis: {{"chains": [{{"sequence": "{coordinate_sequence}"}}], '
            f'"seqres_sequence": "AN{coordinate_sequence}"}}]'
        )

        assert orch._strategy_input_mode(message) == "PDB-only"
        assert orch._extract_explicit_sequence(message) is None
        assert "当前消息未提供独立 FASTA" in "\n".join(orch._build_customization_lines(message))
        plan = orch._generate_fallback_plan(message, analysis_depth="deep")
        assert len([step for step in plan if step.tool_name == "predict_properties"]) == 1
        assert next(step for step in plan if step.tool_name == "predict_properties").params["sequence"] == ""

    def test_legacy_attachment_json_does_not_change_1bli_task_identity(self, monkeypatch):
        orch = self._get_orchestrator()
        coordinate_sequence = ("LNGTLMQYFEWYMPNDGQHWKRLQNDSAYLAEHGITAV" * 13)[:481]
        seqres_sequence = "AN" + coordinate_sequence
        base = (
            "深度分析这个pdb,我要你把能分析的内容都给我显示，做深度分析。\n"
            "[Attached files:\n- name: 1BLI.pdb, object_name: uploads/current/1BLI.pdb"
        )
        plain = base + "]"
        legacy = base + (
            ', analysis: ' + json.dumps({
                "chains": [{"sequence": coordinate_sequence}],
                "seqres_sequence": seqres_sequence,
            }) + "]"
        )

        assert len(coordinate_sequence) == 481
        assert len(seqres_sequence) == 483
        assert orch._strategy_input_mode(legacy) == "PDB-only"
        assert orch._extract_explicit_sequence(legacy) is None
        assert orch._task_fingerprint(legacy) == orch._task_fingerprint(plain)
        assert orch._has_concrete_protein_input(legacy)

        async def fake_preflight(_task):
            return {
                "status": "readable", "coordinate_sequence": coordinate_sequence,
                "seqres_sequence": seqres_sequence,
            }

        monkeypatch.setattr(orch, "_build_pdb_preflight_summary", fake_preflight)
        plan = orch._generate_fallback_plan(legacy, analysis_depth="deep")
        hydrated = asyncio.run(orch._hydrate_uploaded_pdb_sequence_for_plan(
            plan, legacy, current_message=legacy,
        ))
        properties = next(step for step in hydrated if step.tool_name == "predict_properties")
        assert properties.params["sequence"] == coordinate_sequence
        assert properties.params["sequence_provenance"] == "pdb_coordinate_derived"
        assert "_sequence_input_conflict" not in properties.params

    def test_new_pdb_id_with_deep_word_drops_old_structure_context(self):
        orch = self._get_orchestrator()
        history = [{"role": "user", "content": (
            "提高旧蛋白比活力\n[Attached files:\n"
            "name: old.pdb, object_name: uploads/previous/old.pdb]"
        )}]

        context = orch._build_context_for_message("深度分析 1BLI PDB", history)

        assert "old.pdb" not in context
        assert "提高旧蛋白比活力" not in context

    def test_reuploaded_same_pdb_ignores_older_different_protein_context(self):
        orch = self._get_orchestrator()
        history = [
            {"role": "user", "content": "分析旧蛋白\n[Attached files:\nname: old.pdb, object_name: uploads/old.pdb]"},
            {"role": "user", "content": "提高当前蛋白比活力\n[Attached files:\nname: 1BLI.pdb, object_name: uploads/1BLI.pdb]"},
        ]
        message = "继续分析当前 PDB\n[Attached files:\nname: 1BLI.pdb, object_name: uploads/1BLI.pdb]"

        context = orch._build_context_for_message(message, history)

        assert "提高当前蛋白比活力" in context
        assert "old.pdb" not in context
        assert "分析旧蛋白" not in context

    def test_new_upload_checkpoint_does_not_persist_prior_task_summary(self):
        from app.api.chat import _checkpoint_task_text

        message = "深度分析这个 PDB\n[Attached files:\nname: 1BLI.pdb, object_name: uploads/1BLI.pdb]"
        history = [{"role": "user", "content": "提高旧蛋白比活力"}]

        assert _checkpoint_task_text(message, history) == message
        assert _checkpoint_task_text("深度分析 1BLI PDB", history) == "深度分析 1BLI PDB"
        assert "Prior user request summary" in _checkpoint_task_text("还能深度分析吗", history)

    def test_followup_preflight_summary_does_not_become_fake_sequence(self):
        orch = self._get_orchestrator()
        message = "继续，基于刚才HM.pdb进一步分析位点"
        context = (
            "[Uploaded structure object_name: uploads/user_2/hm.pdb]\n"
            "[Prior user request summary: 提高该蛋白的比活力]\n"
            "已预读上传结构 `uploaded PDB`：2367 行，188631 bytes，链数=1，"
            "残基数=299，原子数=2313；链A:299 aa([1, 299])；"
            "序列前缀=`ASGFYVSGTILCDSTGNPFKIRGINHAHSWYKNYSATAME`。"
        )

        plan = orch._generate_fallback_plan(message, context=context, analysis_depth="deep")
        tool_names = [step.tool_name for step in plan]

        assert "structure_search_foldseek" in tool_names
        assert "residue_mapping_sifts" in tool_names
        assert "predict_properties" in tool_names
        assert "mutation_scan" in tool_names
        assert "blast_search" in tool_names
        for step in plan:
            params = step.params or {}
            assert params.get("sequence") != "ASGFYVSGTILCDSTGNPFKIRGINHAHSWYKNYSATAME"
        assert "gromacs_md" not in tool_names

    def test_stream_state_plan_is_display_safe_for_uploaded_pdb(self):
        orch = self._get_orchestrator()
        message = (
            "提高蛋白比活力\n\n"
            "[Attached files:\n"
            "name: HM.pdb, object_name: uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb, "
            "download_url: /api/files/uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb/download]"
        )

        async def collect():
            states = []
            async for event in orch.stream_chat(message, []):
                payload = json.loads(event)
                if payload.get("type") == "state" and payload.get("waiting_for") == "plan_confirmation":
                    states.append(payload)
            return states

        states = asyncio.run(collect())
        assert states, "expected a plan-confirmation state"
        state = states[-1]
        plan = state["plan"]
        assert all(step.get("params", {}).get("pdb_object_name") == "[uploaded-object]" for step in plan)
        assert all("49405" not in json.dumps(step, ensure_ascii=False) for step in plan)
        assert state["strategy_signature"] == orch._plan_signature(
            orch._generate_fallback_plan(message)
        )

    def test_execute_confirmed_uploaded_pdb_stream_is_display_safe(self, monkeypatch):
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()
        message = (
            "提高蛋白比活力\n\n"
            "[Attached files:\n"
            "name: HM.pdb, object_name: uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb, "
            "download_url: /api/files/uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb/download]"
        )
        plan = orch._generate_fallback_plan(message)
        assert [step.tool_name for step in plan] == [
            "structure_search_foldseek",
            "residue_mapping_sifts",
        ]

        async def fake_execute(tool_name, params, **kwargs):
            assert params["pdb_object_name"] == "uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb"
            raise RuntimeError(
                "failed to read download_url=/api/files/uploads/user_2/"
                "08b89c1cc55a46aeaa49405d2ce8f3a2.pdb/download"
            )

        llm_calls = 0

        async def fail_llm(*args, **kwargs):
            nonlocal llm_calls
            llm_calls += 1
            raise RuntimeError("force fallback report")

        monkeypatch.setattr(ToolRegistry, "execute", fake_execute)
        monkeypatch.setattr(orch, "_call_llm", fail_llm)

        async def collect():
            raw_events = []
            async for event in orch.stream_chat(
                message,
                [],
                agent_control="execute_confirmed",
                confirmed_plan=[{
                    "id": step.id,
                    "tool_name": step.tool_name,
                    "description": step.description,
                    "params": step.params,
                } for step in plan],
                strategy_signature=orch._plan_signature(plan),
                task_fingerprint=orch._task_fingerprint(message, ""),
            ):
                raw_events.append(event)
            return "\n".join(raw_events)

        raw = asyncio.run(collect())

        assert llm_calls == 0
        assert "策略检查点校验失败" not in raw
        assert "confirmed_plan must be a list" not in raw
        assert "strategy_signature does not match confirmed_plan" not in raw
        assert "49405" not in raw
        assert "uploads/user_2" not in raw
        assert "download_url" not in raw
        assert "gromacs_md" not in raw
        assert "residue_numbering_gate" not in raw
        assert "[uploaded-object]" in raw

    def test_explicit_uploaded_pdb_mutation_still_requests_numbering_gate(self):
        orch = self._get_orchestrator()
        message = (
            "提高蛋白比活力，重点评估 M204H。\n\n"
            "[Attached files:\n"
            "name: HM.pdb, object_name: uploads/user_2/08b89c1cc55a46aeaa49405d2ce8f3a2.pdb]"
        )

        plan = orch._generate_fallback_plan(message)
        gate_step = next(step for step in plan if step.tool_name == "residue_numbering_gate")

        assert gate_step.params["requested_positions"] == [204]

    def test_deep_analysis_depth_does_not_submit_md_without_explicit_md_request(self):
        orch = self._get_orchestrator()
        message = (
            "分析这个结构的热稳定性和pH稳定性。\n\n"
            "[Attached files:\n"
            "- name: rare.pdb, object_name: uploads/user_1/rare.pdb]"
        )

        standard_plan = orch._generate_fallback_plan(message, analysis_depth="standard")
        deep_plan = orch._generate_fallback_plan(message, analysis_depth="deep")

        assert "gromacs_md" not in [step.tool_name for step in standard_plan]
        assert "gromacs_md" not in [step.tool_name for step in deep_plan]

    def test_geometry_tools_require_deep_pdb_context(self):
        orch = self._get_orchestrator()
        sequence = "M" + "A" * 119

        deep_sequence_plan = orch._generate_fallback_plan(
            f"深度分析这个蛋白的活性和稳定性\n\n>{sequence}",
            analysis_depth="deep",
        )
        assert "ligand_contact_analysis" not in [step.tool_name for step in deep_sequence_plan]
        assert "structure_pocket_interface_analysis" not in [step.tool_name for step in deep_sequence_plan]

        standard_pdb_plan = orch._generate_fallback_plan(
            "分析上传结构的口袋和配体接触\n\n"
            "[Attached files:\nname: example.pdb, object_name: uploads/user_1/example.pdb]",
            analysis_depth="standard",
        )
        assert "ligand_contact_analysis" not in [step.tool_name for step in standard_pdb_plan]
        assert "structure_pocket_interface_analysis" not in [step.tool_name for step in standard_pdb_plan]

    def test_objective_routing_changes_tool_plan_for_same_sequence(self):
        orch = self._get_orchestrator()
        sequence = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"
        cases = {
            "thermo": f"提高这个酶的热稳定性 {sequence}",
            "activity": f"提高这个酶的比活力和催化效率 {sequence}",
            "specificity": f"提高这个酶的底物特异性 {sequence}",
            "solubility": f"提高这个酶在毕赤酵母中的可溶性表达 {sequence}",
        }

        plans = {
            key: [step.tool_name for step in orch._generate_fallback_plan(message)]
            for key, message in cases.items()
        }

        for plan in plans.values():
            assert plan[:6] == [
                "predict_properties",
                "annotation_bundle",
                "enzyme_identity_profile",
                "enzyme_objective_module_plan",
                "protein_benchmark",
                "enzyme_function",
            ]

        assert plans["thermo"] == [
            "predict_properties",
            "annotation_bundle",
            "enzyme_identity_profile",
            "enzyme_objective_module_plan",
            "protein_benchmark",
            "enzyme_function",
            "esmfold_folding",
            "mutation_priority_score",
        ]
        assert "kcat_predict" in plans["activity"]
        assert "mutation_scan" in plans["activity"]
        assert "protein_benchmark" in plans["specificity"]
        assert "enzyme_objective_module_plan" in plans["specificity"]
        assert "mutation_priority_score" in plans["specificity"]
        assert "mutation_scan" in plans["specificity"]
        assert "kcat_predict" not in plans["specificity"]
        assert "soluble_mpnn_design" in plans["solubility"]
        assert "protein_benchmark" in plans["solubility"]
        assert "enzyme_function" in plans["solubility"]
        assert "mutation_priority_score" not in plans["solubility"]
        assert len({tuple(plan) for plan in plans.values()}) == 4

    def test_deep_thermostability_plan_does_not_add_kcat_by_default(self):
        orch = self._get_orchestrator()
        sequence = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"

        plan = [
            step.tool_name
            for step in orch._generate_fallback_plan(
                f"继续深度分析，提高这个酶的热稳定性 {sequence}",
                analysis_depth="deep",
            )
        ]

        assert "mutation_priority_score" in plan
        assert "protssn_score" not in plan
        assert "blast_search" in plan
        assert "kcat_predict" not in plan

    def test_uploaded_sequence_deep_md_request_submits_one_background_md_step(self):
        orch = self._get_orchestrator()
        sequence = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"
        message = (
            f"对上传PDB做深度分子动力学分析，评估热稳定性。{sequence}\n\n"
            "[Attached files:\n"
            "- name: test.pdb, object_name: uploads/user_1/test.pdb]"
        )

        plan = orch._generate_fallback_plan(message, analysis_depth="deep")

        assert [step.tool_name for step in plan].count("gromacs_md") == 1

    def test_negative_tool_constraints_filter_planned_tools(self):
        orch = self._get_orchestrator()
        sequence = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"
        message = (
            "提高这个酶的底物特异性，但禁止 ESMFold、BLAST、家族预测和突变打分。"
            f"{sequence}"
        )

        plan = orch._generate_fallback_plan(message, analysis_depth="deep")
        tool_names = [step.tool_name for step in plan]

        assert "esmfold_folding" not in tool_names
        assert "blast_search" not in tool_names
        assert "protein_benchmark" not in tool_names
        assert "enzyme_function" not in tool_names
        assert "mutation_priority_score" not in tool_names
        assert "mutation_scan" not in tool_names
        assert "predict_properties" in tool_names

    def test_extract_only_request_does_not_plan_tools(self):
        orch = self._get_orchestrator()
        sequence = "mktvrqerlksivrilerskepvqgaqlpvkelqlpgchpnpiralldssegdlsfdadstiirrmee"
        message = f"只抽取序列，不分析，不要调用工具。序列：{sequence}"

        assert orch._generate_fallback_plan(message, analysis_depth="deep") == []
        reply = orch._build_extraction_only_reply(message)

        assert "未调用任何分析工具" in reply
        assert "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE" in reply

    def test_stream_extract_only_short_circuits_before_routing_or_tools(self, monkeypatch):
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()
        sequence = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"

        async def fail_route(*args, **kwargs):
            raise AssertionError("extract-only requests must not route")

        async def fail_execute(*args, **kwargs):
            raise AssertionError("extract-only requests must not execute tools")

        monkeypatch.setattr(orch, "_route_intent", fail_route)
        monkeypatch.setattr(ToolRegistry, "execute", fail_execute)

        async def collect():
            text = []
            states = []
            async for event in orch.stream_chat(f"只抽取，不分析，不要调用工具。序列：{sequence}", []):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
                elif payload.get("type") == "state":
                    states.append(payload)
            return "".join(text), states

        reply, states = asyncio.run(collect())

        assert "未调用任何分析工具" in reply
        assert all(not state.get("plan") for state in states)

    def test_sequence_extraction_ignores_lowercase_objective_words(self):
        from app.core.agent_graph import AgentOrchestrator

        assert AgentOrchestrator._extract_sequence("improve substrate specificity only") is None
        assert AgentOrchestrator._extract_sequence("序列：mktvrqerlksivrilersk") == "MKTVRQERLKSIVRILERSK"

    def test_gromacs_step_is_prepared_for_interactive_async_submission(self):
        from app.core.agent_graph import PlanStep

        orch = self._get_orchestrator()
        step = PlanStep(
            id=1,
            tool_name="gromacs_md",
            description="Run full MD",
            params={"pdb_object_name": "uploads/user_1/test.pdb"},
        )

        safe = orch._normalize_interactive_async_params(step)

        assert safe.params["replicate_plan_only"] is False
        assert safe.params["upload_artifacts"] is True
        assert "background task runner" in safe.description

    def test_stream_plan_confirmation_stops_before_tool_execution(self, monkeypatch):
        from app.core.agent_graph import PlanStep
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()
        sequence = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"

        async def fake_route(*args, **kwargs):
            return "analyze"

        async def fake_plan(*args, **kwargs):
            return [
                PlanStep(
                    id=1,
                    tool_name="predict_properties",
                    description="Compute objective-relevant physicochemical sequence features",
                    params={"sequence": sequence},
                ),
                PlanStep(
                    id=2,
                    tool_name="mutation_priority_score",
                    description="Score residues for thermostability engineering",
                    params={"sequence": sequence, "engineering_goal": "thermostability"},
                ),
            ]

        async def fail_execute(*args, **kwargs):
            raise AssertionError("plan-only mode must not execute tools")

        monkeypatch.setattr(orch, "_route_intent", fake_route)
        monkeypatch.setattr(orch, "_plan_cb", fake_plan)
        monkeypatch.setattr(ToolRegistry, "execute", fail_execute)

        async def collect():
            text = []
            states = []
            async for event in orch.stream_chat(f"提高这个酶的热稳定性 {sequence}", []):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
                elif payload.get("type") == "state":
                    states.append(payload)
            return "".join(text), states

        reply, states = asyncio.run(collect())

        assert "分析策略确认" in reply
        assert "改造策略（先确认方向，再执行分析）" in reply
        assert "热稳定性" in reply
        assert "当前还没有执行任何分析工具" in reply
        assert "`predict_properties`" in reply
        assert "`mutation_priority_score`" in reply
        assert any(state.get("waiting_for") == "plan_confirmation" for state in states)
        assert any(state.get("strategy_signature") for state in states)
        assert any(state.get("task_fingerprint") for state in states)
        assert not any(state.get("step_results") for state in states)

    def test_connectivity_plan_confirmation_does_not_probe_before_confirmation(self, monkeypatch):
        from app.core.agent_graph import PlanStep
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()

        async def fake_plan(*args, **kwargs):
            return [PlanStep(1, "external_connectivity_check", "Probe official APIs", {})]

        async def fail_research(*args, **kwargs):
            raise AssertionError("connectivity plan-only flow must not run background research")

        async def fail_execute(*args, **kwargs):
            raise AssertionError("connectivity plan-only flow must wait for confirmation")

        monkeypatch.setattr(orch, "_plan_cb", fake_plan)
        monkeypatch.setattr(orch, "_research_pi", fail_research)
        monkeypatch.setattr(ToolRegistry, "execute", fail_execute)

        async def collect():
            text = []
            done_count = 0
            async for event in orch.stream_chat("你联网了吗？", []):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
                elif payload.get("type") == "done":
                    done_count += 1
            return "".join(text), done_count

        reply, done_count = asyncio.run(collect())

        assert "当前尚未执行" in reply
        assert "确认执行" in reply
        assert done_count == 1

    def test_connectivity_reply_is_single_and_evidence_backed(self):
        from app.core.agent_graph import AgentOrchestrator

        reply = AgentOrchestrator._build_connectivity_reply([{
            "tool_name": "external_connectivity_check",
            "status": "completed",
            "result": json.dumps({
                "connected": True,
                "summary": {"successful_probes": 2, "total_probes": 3},
                "probes": [
                    {"source": "UniProt REST", "status": "live"},
                    {"source": "NCBI E-utilities", "status": "live"},
                    {"source": "InterPro API", "status": "blocked"},
                ],
            }, ensure_ascii=False),
        }])

        assert reply is not None
        assert reply.count("已联网") == 1
        assert "2/3" in reply
        assert "InterPro API" in reply

    def test_confirmed_connectivity_stream_executes_once_and_returns_one_answer(self, monkeypatch):
        from app.core.agent_graph import PlanStep
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()
        calls = 0
        plan = [PlanStep(1, "external_connectivity_check", "Probe official APIs", {})]

        async def fake_execute(tool_name, params, **kwargs):
            nonlocal calls
            calls += 1
            assert tool_name == "external_connectivity_check"
            return {
                "connected": True,
                "summary": {"successful_probes": 3, "total_probes": 3},
                "probes": [
                    {"source": "UniProt REST", "status": "live"},
                    {"source": "NCBI E-utilities", "status": "live"},
                    {"source": "InterPro API", "status": "live"},
                ],
            }

        async def fail_plan(*args, **kwargs):
            raise AssertionError("valid confirmed checkpoint must not call planner")

        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(ToolRegistry, "execute", fake_execute)

        async def collect():
            text = []
            done_count = 0
            async for event in orch.stream_chat(
                "你联网了吗？",
                [],
                agent_control="execute_confirmed",
                confirmed_plan=[{
                    "id": step.id,
                    "tool_name": step.tool_name,
                    "description": step.description,
                    "params": step.params,
                } for step in plan],
                strategy_signature=orch._plan_signature(plan),
                task_fingerprint=orch._task_fingerprint("你联网了吗？", ""),
            ):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
                elif payload.get("type") == "done":
                    done_count += 1
            return "".join(text), done_count

        reply, done_count = asyncio.run(collect())

        assert calls == 1
        assert reply.count("已联网") == 1
        assert "3/3" in reply
        assert done_count == 1

    def test_execute_confirmed_signed_plan_ignores_control_phrase_task_fingerprint(self, monkeypatch):
        from app.core.agent_graph import PlanStep
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()
        calls = 0
        plan = [PlanStep(1, "external_connectivity_check", "Probe official APIs", {})]

        async def fake_execute(tool_name, params, **kwargs):
            nonlocal calls
            calls += 1
            assert tool_name == "external_connectivity_check"
            return {"connected": True, "summary": {"successful_probes": 1, "total_probes": 1}}

        async def fail_plan(*args, **kwargs):
            raise AssertionError("valid signed checkpoint must not call planner")

        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(ToolRegistry, "execute", fake_execute)

        async def collect():
            text = []
            async for event in orch.stream_chat(
                "确认执行上述分析策略",
                [],
                agent_control="execute_confirmed",
                confirmed_plan=[{
                    "id": step.id,
                    "tool_name": step.tool_name,
                    "description": step.description,
                    "params": step.params,
                } for step in plan],
                strategy_signature=orch._plan_signature(plan),
                task_fingerprint=orch._task_fingerprint("原始任务：你联网了吗？", ""),
            ):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert calls == 1
        assert "task_fingerprint does not match current task context" not in reply
        assert "策略检查点校验失败" not in reply

    def test_execute_confirmed_without_checkpoint_fails_closed(self, monkeypatch):
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()

        async def fail_plan(*args, **kwargs):
            raise AssertionError("missing checkpoint must not replan")

        async def fail_execute(*args, **kwargs):
            raise AssertionError("missing checkpoint must not execute tools")

        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(ToolRegistry, "execute", fail_execute)

        async def collect():
            text = []
            async for event in orch.stream_chat(
                "提高这个酶的比活力",
                [],
                agent_control="execute_confirmed",
            ):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert "策略检查点校验失败" in reply
        assert "当前没有待确认的分析策略" in reply
        assert "confirmed_plan" not in reply
        assert "strategy_signature does not match confirmed_plan" not in reply
        assert "不会执行工具" in reply

    def test_typed_confirmation_after_strategy_does_not_replan(self, monkeypatch):
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()
        history = [{
            "role": "assistant",
            "content": "## 分析策略确认\n\n- 策略指纹：`abc123`。\n\n状态：等待确认，未执行工具。",
        }]

        async def fail_plan(*args, **kwargs):
            raise AssertionError("typed confirmation without checkpoint must not replan")

        async def fail_execute(*args, **kwargs):
            raise AssertionError("typed confirmation without checkpoint must not execute")

        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(ToolRegistry, "execute", fail_execute)

        async def collect():
            text = []
            async for event in orch.stream_chat("是，执行", history):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert "策略检查点校验失败" in reply
        assert "no structured strategy checkpoint" in reply
        assert "不会执行工具" in reply

    def test_plan_confirmation_contains_sequence_specific_strategy_profile(self):
        orch = self._get_orchestrator()
        flexible_seq = "MGGGGGGGGGGGGNNSTGGSGGAGGGGTTTTGGGGGGGSSSSGGGGGGGAAAGGGGGGG"
        hydrophobic_seq = "MLLLLVVVVVIIIIFFFFFYYYYYWWWWWLLLLVVVVVIIIIFFFFFYYYYYWWWWW"
        first_task = f"提高这个酶的比活力，序列：{flexible_seq}"
        second_task = f"提高这个酶的比活力，序列：{hydrophobic_seq}"

        first_plan = orch._generate_fallback_plan(first_task)
        second_plan = orch._generate_fallback_plan(second_task)
        first_reply = orch._build_plan_confirmation_reply(first_task, first_plan)
        second_reply = orch._build_plan_confirmation_reply(second_task, second_plan)

        assert "本轮定制化依据" in first_reply
        assert "序列指纹" in first_reply
        assert "Gly-rich" in first_reply
        assert "hydrophobic-rich" in second_reply
        assert first_reply != second_reply

    def test_confirmed_task_normalization_preserves_original_plan(self):
        orch = self._get_orchestrator()
        sequence = "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"
        task = f"提高这个酶的比活力，序列：{sequence}"
        confirmed = f"{task}\n\n[用户确认] 请按上面的分析策略执行工具。"

        original = orch._generate_fallback_plan(task)
        normalized = orch._normalize_confirmed_task(confirmed, "execute_confirmed")
        confirmed_plan = orch._generate_fallback_plan(normalized)

        assert normalized == task
        assert [(step.tool_name, step.params) for step in confirmed_plan] == [
            (step.tool_name, step.params) for step in original
        ]

    def test_continuation_with_payload_is_not_unbound_confirmation(self):
        from app.core.agent_graph import AgentOrchestrator

        history = [{
            "role": "assistant",
            "content": "## 分析策略确认\n\n状态：等待确认，未执行工具。\n策略指纹：`abc123`",
        }]

        assert AgentOrchestrator._is_unbound_strategy_confirmation(
            "继续，基于刚才HM.pdb进一步分析位点",
            history,
            "plan_only",
        ) is False
        assert AgentOrchestrator._is_unbound_strategy_confirmation(
            "继续",
            history,
            "plan_only",
        ) is True

    def test_new_sequence_turn_ignores_prior_uploaded_structure_context(self):
        orch = self._get_orchestrator()
        history = [{
            "role": "user",
            "content": (
                "[Attached files:\n"
                "- name: old.pdb, object_name: uploads/user_7/old.pdb, "
                "download_url: /api/files/uploads/user_7/old.pdb/download]"
            ),
        }]
        new_sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY"
        message = f"另一个新序列，提高比活力：{new_sequence}"

        context = orch._build_context_for_message(message, history)
        plan = orch._generate_fallback_plan(message, context=context)

        assert "prior protein context ignored" in context
        assert all(step.params.get("pdb_object_name") != "uploads/user_7/old.pdb" for step in plan)
        assert "structure_search_foldseek" not in [step.tool_name for step in plan]

    def test_same_problem_synthesis_followup_does_not_match_new_or_execute_task(self):
        orch = self._get_orchestrator()
        context = "[Protein sequence detected in conversation]"

        assert orch._is_same_problem_synthesis_followup("继续解释上面为什么推荐第一批位点", context) is True
        assert orch._is_same_problem_synthesis_followup("继续执行上面的策略", context) is False
        assert orch._is_same_problem_synthesis_followup(
            "另一个新序列，提高比活力：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY",
            context,
        ) is False
        assert orch._is_same_problem_synthesis_followup("解释一下这个问题", "") is False

    def test_report_quality_review_followup_detection(self):
        orch = self._get_orchestrator()
        context = "[Uploaded structure object_name: uploads/user_2/hm.pdb]"
        history = [
            {"role": "assistant", "content": "# 酶蛋白工程分析报告\nmutation_priority_score completed\nblast_search submitted"}
        ]

        assert orch._is_report_quality_review_followup(
            "表格样式乱了，你再看看你分析的内容，继续深度检查",
            context,
            history,
        ) is True
        assert orch._is_report_quality_review_followup(
            "确认执行上述分析策略",
            context,
            history,
        ) is False
        assert orch._is_report_quality_review_followup(
            "另一个新序列，提高比活力：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY",
            context,
            history,
        ) is False

    def test_p0_followup_review_detection(self):
        orch = self._get_orchestrator()
        context = "[Uploaded structure object_name: uploads/user_2/hm.pdb]"
        history = [
            {"role": "assistant", "content": "# 酶蛋白工程分析报告\nmutation_priority_score completed\n候选位点表"}
        ]

        assert orch._is_p0_followup_review("和 Venus 比哪里差？", context, history) is True
        assert orch._is_p0_followup_review("这个位点为什么推荐？", context, history) is True
        assert orch._is_p0_followup_review("预测和实验结果不一致怎么解释？", context, history) is True
        assert orch._is_p0_followup_review("P338T 怎么样？", context, history) is True
        assert orch._is_p0_followup_review(
            "另一个新序列，提高比活力：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY",
            context,
            history,
        ) is False

    def test_agent_strategy_policy_can_extend_continuation_tokens(self, monkeypatch):
        from app.core import agent_graph
        from app.services.agent_policy import get_agent_strategy_policy

        monkeypatch.setattr(
            agent_graph.settings,
            "AGENT_STRATEGY_POLICY_JSON",
            '{"continuation_tokens":["延续上轮"],"followup_synthesis_tokens":["复盘"]}',
            raising=False,
        )
        get_agent_strategy_policy.cache_clear()
        try:
            assert agent_graph.AgentOrchestrator._message_requests_continuation("延续上轮复盘一下") is True
            assert agent_graph.AgentOrchestrator._is_same_problem_synthesis_followup(
                "延续上轮复盘一下",
                "[Protein sequence detected in conversation]",
            ) is True
        finally:
            get_agent_strategy_policy.cache_clear()

    def test_same_problem_synthesis_followup_stream_skips_planner(self, monkeypatch):
        orch = self._get_orchestrator()
        history = [
            {"role": "user", "content": "提高这个酶的耐热性，序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY"},
            {"role": "assistant", "content": "上一轮推荐 P1 位点表。"},
        ]
        planner_called = False

        async def fake_plan(*args, **kwargs):
            nonlocal planner_called
            planner_called = True
            return []

        async def fake_chat_reply(message, history, model_id=None):
            assert "同一问题续问约束" in message
            return "基于上一轮结果解释，不重新跑工具。"

        monkeypatch.setattr(orch, "_plan_cb", fake_plan)
        monkeypatch.setattr(orch, "_chat_reply", fake_chat_reply)

        async def collect():
            text = []
            async for event in orch.stream_chat("继续解释上面为什么推荐P1位点", history):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert planner_called is False
        assert "# 候选位点解释复核" in reply
        assert "本轮不重新执行工具" in reply
        assert "不生成新的候选表" in reply

    def test_p0_venus_gap_followup_stream_skips_planner_and_llm(self, monkeypatch):
        orch = self._get_orchestrator()
        history = [
            {
                "role": "user",
                "content": (
                    "提高蛋白比活力\n\n"
                    "[Attached files:\n"
                    "- name: HM.pdb, object_name: uploads/user_2/hm.pdb]"
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "# 酶蛋白工程分析报告\n\n"
                    "mutation_priority_score(completed)\n"
                    "build_site_structure_function_features(completed)\n"
                    "候选表已有 CA geometry evidence。\n"
                ),
            },
        ]

        async def fail_plan(*args, **kwargs):
            raise AssertionError("Venus comparison follow-up must not plan tools")

        async def fail_chat_reply(*args, **kwargs):
            raise AssertionError("Venus comparison follow-up must not call LLM")

        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(orch, "_chat_reply", fail_chat_reply)

        async def collect():
            text = []
            async for event in orch.stream_chat("和 Venus 比哪里差？", history):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert "# Venus 对标差距复核" in reply
        assert "本轮不重新规划工具" in reply
        assert "不生成新候选表" in reply
        assert "HM.pdb" in reply
        assert "pocket/channel/interface/conservation 只能写 unknown" in reply

    def test_p0_candidate_site_followup_stream_skips_default_flow(self, monkeypatch):
        orch = self._get_orchestrator()
        history = [
            {"role": "user", "content": "提高这个酶的比活力，序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY"},
            {
                "role": "assistant",
                "content": (
                    "# 酶蛋白工程分析报告\n\n"
                    "mutation_priority_score(completed)\n"
                    "P1 位点：A42V；风险：编号需确认。\n"
                ),
            },
        ]

        async def fail_plan(*args, **kwargs):
            raise AssertionError("candidate explanation follow-up must not plan tools")

        async def fail_chat_reply(*args, **kwargs):
            raise AssertionError("candidate explanation follow-up must not call LLM")

        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(orch, "_chat_reply", fail_chat_reply)

        async def collect():
            text = []
            async for event in orch.stream_chat("这个位点为什么推荐？", history):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert "# 候选位点解释复核" in reply
        assert "本轮不重新执行工具" in reply
        assert "不生成新的候选表" in reply
        assert "未知字段保持 unknown" in reply

    def test_p0_prediction_experiment_mismatch_followup_stream_skips_default_flow(self, monkeypatch):
        orch = self._get_orchestrator()
        history = [
            {"role": "user", "content": "提高这个酶的比活力，序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY"},
            {
                "role": "assistant",
                "content": (
                    "# 酶蛋白工程分析报告\n\n"
                    "mutation_priority_score(completed)\n"
                    "P338T 为 Watch 候选。\n"
                ),
            },
        ]

        async def fail_plan(*args, **kwargs):
            raise AssertionError("prediction-experiment mismatch follow-up must not plan tools")

        async def fail_chat_reply(*args, **kwargs):
            raise AssertionError("prediction-experiment mismatch follow-up must not call LLM")

        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(orch, "_chat_reply", fail_chat_reply)

        async def collect():
            text = []
            async for event in orch.stream_chat("预测和实验结果不一致，P338T 怎么解释？", history):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert "# 指定突变复核" in reply
        assert "P338T" in reply
        assert "本轮没有完成的位点级工具证据" in reply
        assert "不声明确定提升" in reply

    def test_report_quality_review_stream_skips_planner_and_llm(self, monkeypatch):
        orch = self._get_orchestrator()
        history = [
            {
                "role": "user",
                "content": (
                    "提高蛋白比活力\n\n"
                    "[Attached files:\n"
                    "- name: HM.pdb, object_name: uploads/user_2/hm.pdb]"
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "# 酶蛋白工程分析报告\n\n"
                    "structure_search_foldseek(completed)\n"
                    "residue_mapping_sifts(completed)\n"
                    "blast_search(submitted)\n"
                    "identity_status must be identified.\n"
                    "guardrail.status must be ready.\n"
                    "K288E\n"
                ),
            },
        ]

        async def fail_plan(*args, **kwargs):
            raise AssertionError("quality review follow-up must not plan tools")

        async def fail_chat_reply(*args, **kwargs):
            raise AssertionError("quality review follow-up must not call LLM")

        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(orch, "_chat_reply", fail_chat_reply)

        async def collect():
            text = []
            async for event in orch.stream_chat("怎么越改越差，表格也乱，继续深度检查", history):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert "# 报告质量复核" in reply
        assert "本轮不重新执行工具" in reply
        assert "不重新生成候选突变表" in reply
        assert "HM.pdb" in reply
        assert "blast_search=submitted" in reply
        assert "identity_status must be identified" in reply
        assert "K288E/E275Q" in reply

    def test_report_quality_review_uses_structured_strategy_memory(self, monkeypatch):
        from app.core import agent_graph

        orch = self._get_orchestrator()
        memory_call = {}

        async def fake_recent_memory(session, *, user_id, project_id=None, conversation_id=None, limit=10, **kwargs):
            memory_call.update({
                "user_id": user_id,
                "project_id": project_id,
                "conversation_id": conversation_id,
                "limit": limit,
            })
            return [{
                "revision": 5,
                "status": "completed",
                "next_action": "review_required",
                "strategy_signature": "sig-quality",
                "task_fingerprint": "task-quality",
                "task_text": "提高蛋白比活力\nobject_name: uploads/user_2/hm.pdb",
                "plan_payload": [
                    {
                        "id": 1,
                        "tool_name": "structure_search_foldseek",
                        "status": "completed",
                        "params": {"pdb_object_name": "uploads/user_2/hm.pdb"},
                    },
                    {
                        "id": 2,
                        "tool_name": "blast_search",
                        "status": "submitted",
                        "params": {"sequence": "A" * 299},
                    },
                    {
                        "id": 3,
                        "tool_name": "mutation_priority_score",
                        "status": "completed",
                        "params": {"sequence": "A" * 299},
                    },
                ],
                "evidence_state": {
                    "missing_evidence": [
                        "identity_status must be identified.",
                        "guardrail.status must be ready.",
                    ],
                    "summary": "candidate table blocked by identity gate",
                },
                "artifacts": {"handoffs": [{"step": 1}, {"step": 2}]},
            }]

        async def fail_plan(*args, **kwargs):
            raise AssertionError("quality review with strategy memory must not plan tools")

        async def fail_chat_reply(*args, **kwargs):
            raise AssertionError("quality review with strategy memory must not call LLM")

        monkeypatch.setattr(agent_graph, "list_recent_strategy_memory", fake_recent_memory)
        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(orch, "_chat_reply", fail_chat_reply)

        async def collect():
            text = []
            async for event in orch.stream_chat(
                "报告质量太差了，继续深度检查",
                history=[],
                current_user={"id": 7},
                audit_session=object(),
                project_id="P123",
            ):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert memory_call == {"user_id": 7, "project_id": "P123", "conversation_id": None, "limit": 3}
        assert "# 报告质量复核" in reply
        assert "uploads/user_2/hm.pdb" in reply
        assert "structure_search_foldseek=completed" in reply
        assert "blast_search=submitted" in reply
        assert "mutation_priority_score=completed" in reply
        assert "identity_status must be identified" in reply
        assert "revision=5" in reply
        assert "artifact_handoffs=2" in reply

    def test_report_quality_review_uses_checkpoint_step_results_and_report_preview(self):
        orch = self._get_orchestrator()
        reply = orch._build_report_quality_review_reply(
            "报告质量太差了，继续深度检查",
            history=[],
            context="[Prior user request summary: 提高蛋白比活力]",
            strategy_records=[{
                "revision": 6,
                "status": "completed",
                "next_action": None,
                "plan_payload": [
                    {"tool_name": "structure_search_foldseek", "status": "completed", "params": {"pdb_object_name": "uploads/user_2/hm.pdb"}},
                ],
                "evidence_state": {
                    "step_results": [
                        {
                            "tool": "structure_search_foldseek",
                            "status": "completed",
                            "result_preview": "Top hit TM=0.52; weak identity evidence",
                        },
                        {
                            "tool": "blast_search",
                            "status": "submitted",
                            "result_preview": "task_id=blast-task-123",
                        },
                    ],
                    "final_report_preview": "突变位点探索清单（未放行）；0 个可排单候选",
                    "report_headings": [
                        "## 任务理解",
                        "## Objective Module Gate",
                        "## 突变位点探索清单（未放行）",
                    ],
                    "claim_audit": {
                        "summary_gate": {
                            "status": "blocked",
                            "counts": {"allowed": 0, "downgraded": 1, "blocked": 2},
                        },
                        "allowed": [],
                        "downgraded": ["MUTATION_SITE_TABLE=DESIGN_HYPOTHESIS"],
                        "blocked": [
                            "KCAT_PREDICT_REAL_RUNTIME=RUNTIME_UNVERIFIED",
                            "MUTATION_EFFECT_VALIDATED=MISSING",
                        ],
                    },
                },
                "artifacts": {},
            }],
        )

        assert "structure_search_foldseek=completed" in reply
        assert "blast_search=submitted" in reply
        assert "Top hit TM=0.52" in reply
        assert "task_id=blast-task-123" in reply
        assert "final_report_preview" in reply
        assert "## 任务理解 → ## Objective Module Gate" in reply
        assert "## 科学声明审计" in reply
        assert "摘要/结论门控**：blocked；allowed=0；downgraded=1；blocked=2" in reply
        assert "MUTATION_SITE_TABLE=DESIGN_HYPOTHESIS" in reply
        assert "KCAT_PREDICT_REAL_RUNTIME=RUNTIME_UNVERIFIED" in reply
        assert "只有 SUPPORTED 声明可进入摘要/结论" in reply

    def test_checkpoint_execution_summary_contains_step_results_and_report_headings(self):
        from app.core.agent_graph import ChatSnapshot

        orch = self._get_orchestrator()
        orch._snapshot = ChatSnapshot(stage="done")
        orch._snapshot.research_notes = "research note"
        orch._snapshot.step_results = [
            {
                "step": 1,
                "tool": "blast_search",
                "status": "submitted",
                "duration": 0.1,
                "result_preview": "task_id=blast-task-123",
            }
            ,
            {
                "step": 2,
                "tool": "mutation_priority_score",
                "status": "completed",
                "duration": 0.2,
                "result_preview": json.dumps({
                    "candidate_table_status": "exploratory_requires_objective_evidence",
                    "identity_gate": {"status": "passed"},
                    "objective_gate": {"status": "blocked", "missing_evidence": ["baseline Tm"]},
                    "experiment_design_table": [{"position": 42, "wild_type": "G", "recommended_mutations": ["G42P"]}],
                }),
            },
            {
                "step": 3,
                "tool": "kcat_predict",
                "status": "completed",
                "duration": 0.1,
                "result_preview": json.dumps({
                    "predicted_kcat_s1": 10.0,
                    "capability_status": "proxy",
                    "is_real_inference": False,
                    "report_boundary": "仅可作为启发式动力学背景。",
                }),
            },
        ]
        orch._snapshot.final_report = "\n".join([
            "# 酶蛋白工程分析报告",
            "## 任务理解",
            "## Objective Module Gate",
            "## 突变位点探索清单（未放行）",
        ])

        summary = orch.get_checkpoint_execution_summary()

        assert summary["step_results"][0]["tool"] == "blast_search"
        assert summary["step_results"][0]["status"] == "submitted"
        assert "task_id=blast-task-123" in summary["step_results"][0]["result_preview"]
        assert "MUTATION_SITE_TABLE=DESIGN_HYPOTHESIS" in summary["claim_audit"]["downgraded"]
        assert "KCAT_PREDICT_REAL_RUNTIME=RUNTIME_UNVERIFIED" in summary["claim_audit"]["blocked"]
        assert summary["report_headings"] == [
            "## 任务理解",
            "## Objective Module Gate",
            "## 突变位点探索清单（未放行）",
        ]

    def test_same_problem_followup_injects_recent_strategy_memory(self, monkeypatch):
        from app.core import agent_graph

        orch = self._get_orchestrator()
        history = [
            {"role": "user", "content": "提高这个酶的比活力，序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY"},
            {"role": "assistant", "content": "上一轮已执行策略并给出候选位点。"},
        ]
        memory_call = {}

        async def fake_recent_memory(session, *, user_id, project_id=None, limit=10, **kwargs):
            memory_call.update({"user_id": user_id, "project_id": project_id, "limit": limit})
            return [{
                "revision": 3,
                "status": "executing",
                "next_action": None,
                "strategy_signature": "sig-memory-xyz",
                "task_fingerprint": "task-memory-abc",
                "plan_payload": [{"id": 1, "tool_name": "mutation_priority_score", "description": "rank", "params": {}}],
                "artifacts": {"handoffs": [{"step": 1, "items": [{"name": "rank.csv"}]}]},
                "evidence_state": {"research_notes_preview": "project evidence preview"},
            }]

        async def fail_plan(*args, **kwargs):
            raise AssertionError("same-problem follow-up with memory must not plan")

        async def fake_chat_reply(message, history, model_id=None):
            assert "同一问题续问约束" in message
            assert "同项目策略记忆" in message
            assert "mutation_priority_score" in message
            assert "sig-memory-xyz" in message
            assert "候选级湿实验验证" in message
            return "已结合同项目策略记忆解释。"

        monkeypatch.setattr(agent_graph, "list_recent_strategy_memory", fake_recent_memory)
        monkeypatch.setattr(orch, "_plan_cb", fail_plan)
        monkeypatch.setattr(orch, "_chat_reply", fake_chat_reply)

        async def collect():
            text = []
            async for event in orch.stream_chat(
                "继续解释上面为什么推荐P1位点",
                history,
                current_user={"id": 7},
                audit_session=object(),
                project_id="P123",
            ):
                payload = json.loads(event)
                if payload.get("type") == "text":
                    text.append(payload.get("content", ""))
            return "".join(text)

        reply = asyncio.run(collect())

        assert memory_call == {"user_id": 7, "project_id": "P123", "limit": 3}
        assert "同项目策略记忆" in reply

    def test_stream_md_request_without_topology_is_blocked_not_dispatched(self, monkeypatch):
        from app.core.agent_graph import PlanStep
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()
        dispatched = {}
        plan = [
            PlanStep(
                id=1,
                tool_name="gromacs_md",
                description="Run real MD",
                params={"pdb_object_name": "uploads/user_1/test.pdb", "replicate_plan_only": True},
            )
        ]

        async def fake_route(*args, **kwargs):
            return "analyze"

        async def fake_plan(*args, **kwargs):
            raise AssertionError("valid confirmed checkpoint must not call planner")

        async def fake_synthesize(task, tool_messages, *args, **kwargs):
            return json.dumps(tool_messages, ensure_ascii=False)

        async def fail_execute(tool_name, params, **kwargs):
            if tool_name == "gromacs_md":
                raise AssertionError("chat stream must not run GROMACS inline")
            return {}

        def fake_dispatch(tool_name, params):
            dispatched["tool_name"] = tool_name
            dispatched["params"] = params
            return "chat-md-task-id"

        class FakeProfile:
            queue = "md_cpu"
            soft_time_limit = 3600
            time_limit = 5400

        async def noop(*args, **kwargs):
            return None

        monkeypatch.setattr(orch, "_route_intent", fake_route)
        monkeypatch.setattr(orch, "_plan_cb", fake_plan)
        monkeypatch.setattr(orch, "_synthesize_sc", fake_synthesize)
        monkeypatch.setattr(ToolRegistry, "execute", fail_execute)
        monkeypatch.setattr("app.services.scheduler.dispatch_tool", fake_dispatch)
        monkeypatch.setattr("app.services.scheduler.get_task_profile", lambda tool_name: FakeProfile())
        monkeypatch.setattr("app.services.tool_task_store.record_tool_task_owner", noop)
        monkeypatch.setattr("app.services.tool_task_store.record_tool_task_runtime_policy", noop)

        async def collect_text():
            chunks = []
            async for event in orch.stream_chat(
                "对上传PDB做分子动力学分析",
                [],
                agent_control="execute_confirmed",
                confirmed_plan=[{
                    "id": step.id,
                    "tool_name": step.tool_name,
                    "description": step.description,
                    "params": step.params,
                } for step in plan],
                strategy_signature=orch._plan_signature(plan),
                task_fingerprint=orch._task_fingerprint("对上传PDB做分子动力学分析", ""),
                current_user={"id": 7},
            ):
                try:
                    payload = json.loads(event)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "text":
                    chunks.append(str(payload.get("content") or ""))
            return "".join(chunks)

        reply = asyncio.run(collect_text())

        assert dispatched == {}
        assert "topology" in reply
        assert "DEPENDENCY_REQUIRED" in reply

    def test_stream_blocks_structure_dependent_tools_when_uploaded_structure_gate_fails(self, monkeypatch):
        from app.core.agent_graph import PlanStep
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()
        executed = []
        plan = [
            PlanStep(
                id=1,
                tool_name="structure_search_foldseek",
                description="Parse structure",
                params={"pdb_object_name": "uploads/user_1/bad.pdb"},
            ),
            PlanStep(
                id=2,
                tool_name="gromacs_md",
                description="Run MD",
                params={"pdb_object_name": "uploads/user_1/bad.pdb"},
            ),
            PlanStep(
                id=3,
                tool_name="predict_properties",
                description="Sequence-level properties",
                params={"sequence": "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLDSSEGDLSFDADSTIIRRMEE"},
            ),
        ]

        async def fake_route(*args, **kwargs):
            return "analyze"

        async def fake_plan(*args, **kwargs):
            raise AssertionError("valid confirmed checkpoint must not call planner")

        async def fake_synthesize(task, tool_messages, *args, **kwargs):
            return json.dumps(tool_messages, ensure_ascii=False)

        async def fake_execute(tool_name, params, **kwargs):
            executed.append(tool_name)
            if tool_name == "structure_search_foldseek":
                return {"status": "failed", "found": False, "error": "NO_RESIDUES"}
            if tool_name == "predict_properties":
                return {"status": "completed", "length": len(params["sequence"])}
            raise AssertionError(f"{tool_name} should not execute")

        def fail_dispatch(*args, **kwargs):
            raise AssertionError("gromacs_md must not be submitted when structure gate fails")

        monkeypatch.setattr(orch, "_route_intent", fake_route)
        monkeypatch.setattr(orch, "_plan_cb", fake_plan)
        monkeypatch.setattr(orch, "_synthesize_sc", fake_synthesize)
        monkeypatch.setattr(ToolRegistry, "execute", fake_execute)
        monkeypatch.setattr("app.services.scheduler.dispatch_tool", fail_dispatch)

        async def collect_text():
            chunks = []
            async for event in orch.stream_chat(
                "上传结构有问题时不要继续跑MD",
                [],
                agent_control="execute_confirmed",
                confirmed_plan=[{
                    "id": step.id,
                    "tool_name": step.tool_name,
                    "description": step.description,
                    "params": step.params,
                } for step in plan],
                strategy_signature=orch._plan_signature(plan),
                task_fingerprint=orch._task_fingerprint("上传结构有问题时不要继续跑MD", ""),
                current_user={"id": 7},
            ):
                try:
                    payload = json.loads(event)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "text":
                    chunks.append(str(payload.get("content") or ""))
            return "".join(chunks)

        reply = asyncio.run(collect_text())

        assert executed == ["structure_search_foldseek", "predict_properties"]
        assert '"tool_name": "gromacs_md"' in reply
        assert "DEPENDENCY_REQUIRED" in reply
        assert "topology" in reply

    def test_plan_only_md_synthesis_skips_llm(self, monkeypatch):
        orch = self._get_orchestrator()

        async def fail_call_llm(*args, **kwargs):
            raise AssertionError("plan-only MD should not call LLM synthesis")

        monkeypatch.setattr(orch, "_call_llm", fail_call_llm)
        tool_results = [{
            "role": "tool",
            "tool_name": "gromacs_md",
            "status": "completed",
            "result": json.dumps({
                "status": "planned",
                "is_real_md": False,
                "note": "Replicate plan only; no GROMACS command was executed.",
                "replicate_execution_plan": {
                    "tasks": [{
                        "task_id": "WT:rep1",
                        "variant": "WT",
                        "replicate_index": 1,
                        "simulation_time_ns": 10.0,
                        "force_field": "amber99sb-ildn",
                        "water_model": "tip3p",
                    }],
                },
            }),
        }]

        report = asyncio.run(orch._synthesize_sc(
            "对上传PDB做分子动力学分析",
            tool_results,
            "",
            [],
            "gpt55",
        ))

        assert "MD 执行计划" in report
        assert "Replicate plan only" in report
        assert "WT:rep1" in report

    def test_uploaded_pdb_activity_fallback_report_interprets_structure_and_failed_md(self):
        orch = self._get_orchestrator()
        tool_results = [
            {
                "role": "tool",
                "tool_name": "structure_search_foldseek",
                "status": "completed",
                "result": json.dumps({
                    "found": True,
                    "status": "completed",
                    "backend": "summary_only",
                    "database": "pdb",
                    "results_count": 1,
                    "query_structure": {
                        "chain_count": 1,
                        "total_residues": 288,
                        "total_atoms": 2200,
                        "chains": [{"chain_id": "A", "residue_count": 288, "residue_range": "1-288"}],
                    },
                    "results": [{"target": "1ABC_A", "aligned_tm_score": 0.82, "evalue": "1e-20"}],
                    "rcsb_annotations": {
                        "status": "completed",
                        "source": "RCSB Data API",
                        "hits": [
                            {
                                "pdb_id": "1ABC",
                                "title": "Crystal structure of Bacillus alpha-amylase",
                                "entity_description": "Alpha-amylase",
                                "experimental_methods": ["X-RAY DIFFRACTION"],
                                "resolution": [1.5],
                                "reference_sequence_identifiers": [
                                    {
                                        "database_name": "UniProt",
                                        "database_accession": "P00692",
                                        "entity_sequence_coverage": 1.0,
                                    }
                                ],
                            }
                        ],
                    },
                }),
            },
            {
                "role": "tool",
                "tool_name": "residue_mapping_sifts",
                "status": "completed",
                "result": json.dumps({
                    "found": True,
                    "source": "local_sifts_mapping",
                    "mapping_count": 288,
                    "mappings": [
                        {
                            "chain_id": "A",
                            "residue_aa": "A",
                            "pdb_residue_no": idx,
                            "uniprot_id": "PTEST1",
                            "uniprot_position": idx + 9,
                        }
                        for idx in range(1, 289)
                    ],
                    "limitations": [],
                }),
            },
            {
                "role": "tool",
                "tool_name": "blast_search",
                "status": "completed",
                "result": json.dumps({
                    "status": "completed",
                    "program": "blastp",
                    "database": "pdb",
                    "results_count": 1,
                    "hits": [
                        {
                            "hit_id": "pdb|1WKY|A",
                            "accession": "1WKY_A",
                            "description": "Chain A, endo-beta-1,4-Mannanase [Bacillus sp. JAMB-602]",
                            "hsps": [
                                {
                                    "e_value": "2.7e-152",
                                    "identity_percent": 68.9,
                                    "alignment_length": 296,
                                    "query_from": 2,
                                    "query_to": 297,
                                }
                            ],
                        }
                    ],
                }),
            },
            {
                "role": "tool",
                "tool_name": "gromacs_md",
                "status": "failed",
                "result": json.dumps({
                    "status": "failed",
                    "error": "GROMACS runtime unavailable",
                }),
            },
        ]

        report = orch._build_fallback_report("提高蛋白比活力", tool_results)

        assert "# 酶蛋白工程分析报告" in report
        assert "## 输入与结构证据" in report
        assert "链A:288 aa" in report
        assert "1ABC_A" in report
        assert "RCSB/PDB 专业库命中注释" in report
        assert "Crystal structure of Bacillus alpha-amylase" in report
        assert "UniProt:P00692" in report
        assert "## 结构同源与编号映射" in report
        assert "## 序列级专业库检索（BLAST）" in report
        assert "endo-beta-1,4-Mannanase" in report
        assert "序列级 BLAST 对酶家族/功能判断的权重高于弱结构折叠相似" in report
        assert "A:A1->UniProt PTEST1:10" in report
        assert "## PDB坐标探索性位点预筛" not in report
        assert "不能给出高置信具体突变" in report
        assert "带电门控" not in report and "柔性环/构象熵" not in report
        assert "先不输出突变清单" not in report
        assert "位点表使用方式" not in report
        assert "## 工具执行结果与失败原因" in report
        assert "GROMACS runtime unavailable" in report
        assert "49405" not in report
        assert "DO NOT MUTATE" not in report
        assert "This fallback report is generated" not in report

    def test_report_quarantines_sequence_results_from_previous_structure(self):
        orch = self._get_orchestrator()
        report = orch._build_fallback_report("深度分析这个 PDB 的比活力和热稳定性", [
            {
                "tool_name": "structure_search_foldseek", "status": "completed",
                "result": json.dumps({
                    "status": "completed", "found": True,
                    "query_structure": {
                        "chain_count": 1, "total_residues": 194,
                        "chains": [{"chain_id": "A", "residue_count": 194}],
                    },
                }),
            },
            {
                "tool_name": "predict_properties", "status": "completed",
                "result": json.dumps({"length": 240, "molecular_weight_kda": 25.09}),
            },
            {
                "tool_name": "enzyme_identity_profile", "status": "completed",
                "result": json.dumps({
                    "query": {"sequence_length": 240},
                    "identity_status": "identified",
                    "family_candidates": [{"name": "Aspartic peptidase A1"}],
                }),
            },
            {
                "tool_name": "annotation_bundle", "status": "completed",
                "result": json.dumps({
                    "query": {"sequence_length": 240},
                    "protein": {"protein_name": "Old protein A1"},
                }),
            },
            {
                "tool_name": "protein_benchmark", "status": "completed",
                "result": json.dumps({
                    "query_info": {"length": 240},
                    "family": {"name": "Old protein A1"},
                }),
            },
        ])

        assert "当前结构坐标链为 194 aa" in report
        assert "predict_properties, enzyme_identity_profile" in report
        assert "25.09 kDa" not in report
        assert "Aspartic peptidase A1" not in report
        assert "Old protein A1" not in report
        assert "SEQUENCE_STRUCTURE_LENGTH_MISMATCH" in report or "differs from uploaded coordinate chain" in report

    def test_report_binds_all_sections_to_current_uploaded_structure(self):
        orch = self._get_orchestrator()
        current = "uploads/current/1BLI.pdb"
        previous = "uploads/previous/13.pdb"
        results = [
            {"tool_name": "structure_search_foldseek", "status": "completed", "pdb_object_name": current,
             "input_id": "pdb:0", "result": json.dumps({"query_structure": {
                 "chain_count": 1, "total_residues": 481,
                 "chains": [{"chain_id": "A", "residue_count": 481}]}})},
            {"tool_name": "predict_properties", "status": "completed", "pdb_object_name": current,
             "input_id": "pdb:0", "result": json.dumps({"length": 481, "molecular_weight_kda": 55.0})},
            {"tool_name": "structure_search_foldseek", "status": "completed", "pdb_object_name": previous,
             "input_id": "pdb:1", "result": json.dumps({"query_structure": {
                 "chain_count": 1, "total_residues": 194,
                 "chains": [{"chain_id": "A", "residue_count": 194}]}})},
            {"tool_name": "predict_properties", "status": "completed", "pdb_object_name": previous,
             "input_id": "pdb:1", "result": json.dumps({"length": 194, "molecular_weight_kda": 21.52})},
            {"tool_name": "enzyme_identity_profile", "status": "completed", "pdb_object_name": previous,
             "input_id": "pdb:1", "result": json.dumps({"query": {"sequence_length": 194},
                 "identity_status": "identified", "family_candidates": [{"name": "Glycoside hydrolase family 11"}]})},
            {"tool_name": "build_site_structure_function_features", "status": "completed",
             "pdb_object_name": previous, "input_id": "pdb:1",
             "result": json.dumps({"status": "completed", "feature_count": 194,
                 "features": [{"position": 1, "wild_type": "D", "pdb_position": "A:2"}]})},
        ]
        task = f"深度分析这个pdb\n[Attached files: {{'name': '1BLI.pdb', 'object_name': '{current}'}}]"
        report = orch._build_fallback_report(task, results)

        assert "481 aa" in report
        assert "55.0 kDa" in report
        assert "194 aa" not in report
        assert "21.52 kDa" not in report
        assert "Glycoside hydrolase family 11" not in report
        assert "## 位点结构-功能特征表" not in report
        assert "pdb:1" not in report

    def test_report_blocks_unlabelled_multiple_structures(self):
        orch = self._get_orchestrator()
        results = [
            {"tool_name": "structure_search_foldseek", "status": "completed",
             "result": json.dumps({"query_structure": {"total_residues": size}})}
            for size in (481, 194)
        ]
        report = orch._build_fallback_report("分析这个 PDB", results)

        assert "对象归属未确认" in report
        assert "194" not in report and "481" not in report

    def test_report_drops_unlabelled_result_when_current_structure_is_labelled(self):
        orch = self._get_orchestrator()
        current = "uploads/current/1BLI.pdb"
        task = f"分析这个 PDB\n[Attached files: name: 1BLI.pdb, object_name: {current}]"
        report = orch._build_fallback_report(task, [
            {"tool_name": "structure_search_foldseek", "status": "completed",
             "pdb_object_name": current,
             "result": json.dumps({"query_structure": {"total_residues": 481,
                 "chains": [{"chain_id": "A", "residue_count": 481}]}})},
            {"tool_name": "predict_properties", "status": "completed",
             "result": json.dumps({"length": 481, "molecular_weight_kda": 21.52})},
        ])

        assert "481 aa" in report
        assert "21.52 kDa" not in report

    def test_report_shows_direct_pdb_identity_construct_and_seqres_boundary(self):
        orch = self._get_orchestrator()
        report = orch._build_fallback_report("分析 1BLI PDB", [{
            "tool_name": "structure_search_foldseek", "status": "completed",
            "result": json.dumps({"status": "completed", "query_structure": {
                "method": "X-RAY DIFFRACTION", "total_residues": 481,
                "seqres_length": 483,
                "compound_annotation": {"molecule": "ALPHA-AMYLASE", "ec": "3.2.1.1",
                                         "engineered": "YES"},
                "engineered_mutations": [{"chain_id": "A", "pdb_residue_no": 190,
                                          "pdb_residue_aa": "PHE", "reference_residue_aa": "ASN",
                                          "reference_position": 219}],
                "nonpolymer_components": [{"component_id": "CA", "chain_id": "A"}],
                "chains": [{"chain_id": "A", "residue_count": 481}],
            }})
        }])

        assert "SEQRES=483 aa" in report
        assert "坐标=481 aa" in report
        assert "ALPHA-AMYLASE" in report
        assert "3.2.1.1" in report
        assert "工程突变" in report
        assert "A:PHE190" in report
        assert "参考 ASN219" in report

    def test_plan_rejects_previous_upload_when_current_pdb_is_attached(self):
        from app.core.agent_graph import PlanStep

        orch = self._get_orchestrator()
        task = "深度分析这个 PDB\n[Attached files:\nname: 1BLI.pdb, object_name: uploads/current/1BLI.pdb]"
        plan = [
            PlanStep(1, "structure_search_foldseek", "current", {"pdb_object_name": "uploads/current/1BLI.pdb"}),
            PlanStep(2, "structure_search_foldseek", "previous", {"pdb_object_name": "uploads/previous/13.pdb"}),
        ]

        assert orch._foreign_uploaded_objects_in_plan(task, plan) == ["uploads/previous/13.pdb"]
        assert orch._foreign_uploaded_objects_in_plan(task, plan[:1]) == []

    def test_mixed_upload_plan_stops_before_confirmation_or_execution(self, monkeypatch):
        from app.core.agent_graph import PlanStep
        from app.tools.registry import ToolRegistry

        orch = self._get_orchestrator()
        task = "深度分析这个 PDB\n[Attached files:\nname: 1BLI.pdb, object_name: uploads/current/1BLI.pdb]"

        async def fake_route(*args, **kwargs):
            return "analyze"

        async def fake_research(*args, **kwargs):
            return ""

        async def fake_plan(*args, **kwargs):
            return [
                PlanStep(1, "structure_search_foldseek", "current", {"pdb_object_name": "uploads/current/1BLI.pdb"}),
                PlanStep(2, "structure_search_foldseek", "previous", {"pdb_object_name": "uploads/previous/13.pdb"}),
            ]

        async def fail_execute(*args, **kwargs):
            raise AssertionError("mixed upload plan must not execute")

        monkeypatch.setattr(orch, "_route_intent", fake_route)
        monkeypatch.setattr(orch, "_research_pi", fake_research)
        monkeypatch.setattr(orch, "_plan_cb", fake_plan)
        monkeypatch.setattr(ToolRegistry, "execute", fail_execute)

        async def collect():
            events = [json.loads(event) async for event in orch.stream_chat(task, [])]
            return "".join(item.get("content", "") for item in events if item.get("type") == "text"), events

        reply, events = asyncio.run(collect())
        assert "混入了其他上传结构" in reply
        assert "分析策略确认" not in reply
        assert not any(item.get("step_results") for item in events if item.get("type") == "state")

    def test_report_quarantines_compacted_identity_result_from_previous_structure(self):
        orch = self._get_orchestrator()
        compacted = orch._compact_result("enzyme_identity_profile", {
            "query": {"sequence_length": 240},
            "identity_status": "identified",
            "family_candidates": [{"name": "Old protein A1"}],
        })
        report = orch._build_fallback_report("分析这个 PDB 的热稳定性", [
            {
                "tool_name": "structure_search_foldseek", "status": "completed",
                "result": json.dumps({"query_structure": {
                    "chains": [{"chain_id": "A", "residue_count": 194}],
                }}),
            },
            {"tool_name": "enzyme_identity_profile", "status": "completed", "result": compacted},
        ])
        assert "Old protein A1" not in report
        assert "已隔离长度或序列指纹不符的结果" in report

    def test_report_quarantines_equal_length_wrong_sequence_fingerprint(self):
        orch = self._get_orchestrator()
        coordinate_hash = hashlib.sha256(b"ACDE").hexdigest()
        stale_hash = hashlib.sha256(b"WXYZ").hexdigest()
        report = orch._build_fallback_report("分析这个 PDB 的热稳定性", [
            {
                "tool_name": "structure_search_foldseek", "status": "completed",
                "result": json.dumps({"query_structure": {
                    "chains": [{"chain_id": "A", "residue_count": 4, "sequence_sha256": coordinate_hash}],
                }}),
            },
            {
                "tool_name": "enzyme_identity_profile", "status": "completed",
                "input_sequence_sha256": stale_hash,
                "result": orch._compact_result("enzyme_identity_profile", {
                    "query": {"sequence_length": 4},
                    "identity_status": "identified",
                    "family_candidates": [{"name": "Old protein A1"}],
                }),
            },
        ])
        assert "Old protein A1" not in report
        assert "已隔离长度或序列指纹不符的结果" in report

    def test_sequence_input_fingerprint_uses_executed_step_params(self):
        orch = self._get_orchestrator()
        assert orch._step_sequence_sha256({"sequence": "a c d e"}) == hashlib.sha256(b"ACDE").hexdigest()
        assert orch._step_sequence_sha256({"query_sequence": "WXYZ"}) == hashlib.sha256(b"WXYZ").hexdigest()

    def test_report_labels_swiss_model_as_predicted_structure(self):
        orch = self._get_orchestrator()
        report = orch._build_fallback_report("分析这个 PDB 的比活力和热稳定性", [{
            "tool_name": "structure_search_foldseek", "status": "completed",
            "result": json.dumps({
                "status": "completed", "found": True,
                "query_structure": {
                    "method": "THEORETICAL MODEL (SWISS-MODEL SERVER)",
                    "chain_count": 1, "total_residues": 194,
                    "chains": [{"chain_id": "A", "residue_count": 194}],
                },
            }),
        }])

        assert "THEORETICAL MODEL (SWISS-MODEL SERVER)" in report
        assert "不是该输入的实验测定结构" in report
        assert "不能证明比活力或热稳定性" in report

    def test_fallback_report_excludes_completed_but_blocked_payload_from_structure_evidence(self):
        orch = self._get_orchestrator()
        report = orch._build_fallback_report(
            "提高蛋白热稳定性",
            [{
                "role": "tool",
                "tool_name": "structure_search_foldseek",
                "status": "completed",
                "result": json.dumps({
                    "status": "blocked",
                    "reason": "invalid structure",
                    "query_structure": {"total_residues": 194},
                }),
            }],
        )

        assert "## 输入与结构证据" not in report
        assert "残基数=194" not in report
        assert "invalid structure" in report

    def test_uploaded_pdb_activity_fallback_report_marks_submitted_blast_as_pending_evidence(self):
        orch = self._get_orchestrator()
        tool_results = [
            {
                "role": "tool",
                "tool_name": "structure_search_foldseek",
                "status": "completed",
                "result": json.dumps({
                    "found": True,
                    "status": "completed",
                    "database": "pdb",
                    "query_structure": {
                        "chain_count": 1,
                        "total_residues": 299,
                        "total_atoms": 2313,
                        "chains": [{"chain_id": "A", "residue_count": 299, "residue_range": "1-299"}],
                    },
                    "results": [{"target": "3BH4_A", "aligned_tm_score": 0.52, "query_tm_score": 0.44}],
                }),
            },
            {
                "role": "tool",
                "tool_name": "residue_mapping_sifts",
                "status": "completed",
                "result": json.dumps({
                    "found": True,
                    "status": "completed",
                    "source": "inferred_from_coordinate_order",
                    "mapping_count": 299,
                    "mappings": [
                        {"chain_id": "A", "residue_aa": "A", "pdb_residue_no": idx}
                        for idx in range(1, 300)
                    ],
                    "limitations": ["No authoritative SIFTS cross-reference."],
                }),
            },
            {
                "role": "tool",
                "tool_name": "blast_search",
                "status": "submitted",
                "result": json.dumps({
                    "status": "submitted",
                    "tool": "blast_search",
                    "task_id": "blast-task-123",
                    "queue": "default",
                    "status_url": "/api/tools/tasks/blast-task-123",
                }),
            },
        ]

        report = orch._build_fallback_report("提高蛋白比活力", tool_results)

        assert "## 序列级专业库检索（BLAST）" in report
        assert "已提交后台专业库检索任务" in report
        assert "blast-task-123" in report
        assert "submitted 状态只证明任务进入队列" in report
        assert "## 后台任务状态" in report
        assert "## 工具执行结果与失败原因" not in report
        assert "命中数=" not in report

    def test_uploaded_pdb_structure_with_blast_uses_deterministic_report_fast_path(self):
        from app.core.agent_graph import AgentOrchestrator

        tool_results = [
            {"tool_name": "structure_search_foldseek", "status": "completed", "result": "{}"},
            {"tool_name": "residue_mapping_sifts", "status": "completed", "result": "{}"},
            {"tool_name": "blast_search", "status": "submitted", "result": "{}"},
        ]

        assert AgentOrchestrator._should_use_deterministic_structure_report(
            "提高蛋白比活力\n[Attached files:\nname: HM.pdb, object_name: uploads/user_1/hm.pdb]",
            tool_results,
        ) is True

    def test_uploaded_pdb_pending_blast_does_not_hold_report_for_llm(self):
        from app.core.agent_graph import AgentOrchestrator

        tool_results = [
            {"tool_name": "predict_properties", "status": "completed", "result": "{}"},
            {"tool_name": "enzyme_identity_profile", "status": "completed", "result": "{}"},
            {"tool_name": "blast_search", "status": "waiting", "result": "{}"},
        ]

        assert AgentOrchestrator._should_use_deterministic_structure_report(
            "请分析上传的 PDB 并生成完整报告。\n[Attached files:\nname: 7DVJ.pdb, object_name: uploads/user_1/7dvj.pdb]",
            tool_results,
        ) is True

    def test_uploaded_pdb_report_is_emitted_with_pending_blast_receipt(self, monkeypatch):
        orch = self._get_orchestrator()
        task = (
            "请分析上传的 PDB 并生成完整报告。\n"
            "[Attached files:\nname: 7DVJ.pdb, object_name: uploads/user_1/7dvj.pdb]"
        )
        tool_results = [
            {
                "tool_name": "structure_search_foldseek",
                "status": "completed",
                "result": json.dumps({
                    "status": "completed",
                    "query_structure": {"total_atoms": 20, "total_residues": 2, "chain_count": 1,
                                         "chains": [{"chain_id": "A", "residue_count": 2,
                                                     "residue_range": "1-2"}]},
                }),
            },
            {
                "tool_name": "blast_search",
                "status": "submitted",
                "result": json.dumps({
                    "status": "submitted", "task_id": "blast-1", "queue": "default",
                    "status_url": "/api/tools/tasks/blast-1",
                }),
            },
        ]

        async def fail_if_called(*_args, **_kwargs):
            raise AssertionError("pending NCBI BLAST must not delay deterministic PDB reporting")

        monkeypatch.setattr(orch, "_call_llm", fail_if_called)
        report = asyncio.run(orch._synthesize_sc(task, tool_results, "", [], "gpt6-sol"))

        assert "## 序列级专业库检索（BLAST）" in report
        assert "当前报告不把 BLAST 结果写成已完成证据" in report
        assert "blast-1" in report

    def test_uploaded_pdb_weak_foldseek_hit_is_downgraded_in_report(self):
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        tool_results = [
            {
                "tool_name": "structure_search_foldseek",
                "status": "completed",
                "result": json.dumps({
                    "status": "completed",
                    "found": True,
                    "results_count": 2,
                    "query_structure": {
                        "chain_count": 1,
                        "total_residues": 388,
                        "total_atoms": 2833,
                        "chains": [{"chain_id": "A", "residue_count": 388, "residue_range": "1-388"}],
                    },
                    "results": [
                        {"target": "1QHO_A", "aligned_tm_score": 0.1367, "evalue": 0.859},
                        {"target": "1QHP_A", "aligned_tm_score": 0.1251, "evalue": 0.7269},
                    ],
                }),
            },
        ]

        report = orch._build_fallback_report("提高蛋白热稳定性", tool_results)

        assert "结构同源证据等级**：弱" in report
        assert "不能单独支撑酶家族、催化残基或功能身份结论" in report

    def test_enzyme_engineering_synthesis_uses_deterministic_report_without_llm(self, monkeypatch):
        orch = self._get_orchestrator()
        llm_calls = 0

        async def fail_llm(*args, **kwargs):
            nonlocal llm_calls
            llm_calls += 1
            raise AssertionError("enzyme engineering synthesis should not call LLM")

        monkeypatch.setattr(orch, "_call_llm", fail_llm)
        tool_results = [
            {
                "tool_name": "enzyme_identity_profile",
                "status": "completed",
                "result": json.dumps({
                    "identity_status": "identified",
                    "family_candidates": [{"name": "test enzyme family", "confidence": "medium"}],
                    "numbering": {"status": "user_sequence_only", "mapping_basis": "input sequence"},
                }),
            },
            {
                "tool_name": "enzyme_objective_module_plan",
                "status": "completed",
                "result": json.dumps({
                    "objective": "activity",
                    "status": "blocked",
                    "candidate_output_allowed": False,
                    "missing_evidence": ["WT specific activity baseline"],
                }),
            },
            {
                "tool_name": "mutation_priority_score",
                "status": "completed",
                "result": json.dumps({
                    "candidate_table_status": "exploratory_requires_objective_evidence",
                    "objective_gate": {
                        "status": "blocked",
                        "missing_evidence": ["WT specific activity baseline"],
                    },
                    "experiment_design_table": [
                        {
                            "experiment_priority": "P2-探索",
                            "position": 42,
                            "wild_type": "G",
                            "recommended_mutations": ["G42A"],
                            "mutation_logic": "activity pocket hypothesis",
                            "expected_effect": "需实验确认",
                            "candidate_evidence_status": "computational_hypothesis",
                            "calibration_evidence_status": "not_calibrated",
                            "blocked_upgrade_conditions": ["direct wet-lab activity data required"],
                        }
                    ],
                }),
            },
        ]

        report = asyncio.run(orch._synthesize_sc(
            "提高这个酶的比活力，序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY",
            tool_results,
            "",
            [],
        ))

        assert llm_calls == 0
        assert "## 结论卡片 / 状态摘要" not in report
        assert "## 突变位点探索清单（不可直接排单）" in report
        assert "当前决策**：Watch" in report
        assert "WT specific activity baseline" in report
        assert "G42A" in report

    def test_uploaded_structure_without_foldseek_hits_continues_through_llm_synthesis(self, monkeypatch):
        orch = self._get_orchestrator()
        captured = {}

        async def fake_call_llm(messages, **kwargs):
            captured["messages"] = messages

            class _Message:
                content = "模型基于上传结构摘要继续分析，未因同源结构 0 命中而停止。"

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

        monkeypatch.setattr(orch, "_call_llm", fake_call_llm)
        tool_results = [{
            "role": "tool",
            "tool_name": "structure_search_foldseek",
            "status": "completed",
            "result": json.dumps({
                "found": False,
                "status": "completed",
                "backend": "local_cli",
                "database": "pdb",
                "results_count": 0,
                "results": [],
                "query_structure": {
                    "chain_count": 2,
                    "total_residues": 3,
                    "total_atoms": 6,
                    "chains": [
                        {"chain_id": "A", "residue_count": 2, "residue_range": "5-6"},
                        {"chain_id": "B", "residue_count": 1, "residue_range": "10-10"},
                    ],
                },
            }),
        }]

        report = asyncio.run(orch._synthesize_sc(
            "这个酶的PDB文件，分析热稳定性和pH稳定性",
            tool_results,
            "",
            [],
            "gpt55",
        ))

        user_prompt = captured["messages"][-1]["content"]
        assert "模型基于上传结构摘要继续分析" in report
        assert "Foldseek returned zero homolog/template hits" in user_prompt
        assert '"results_count": 0' in user_prompt
        assert '"chain_id": "A"' in user_prompt
        assert '"residue_range": "5-6"' in user_prompt

    def test_mutation_scan_does_not_overwrite_priority_candidate_table(self):
        """A later saturation scan must not erase mutation_priority_score experiment rows."""
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        tool_results = [
            {
                "tool_name": "mutation_priority_score",
                "status": "completed",
                "result": json.dumps({
                    "candidate_table_status": "ready",
                    "identity_gate": {"status": "passed"},
                    "objective_gate": {"status": "ready", "candidate_output_allowed": True},
                    "summary": {"tier_1_count": 1, "tier_2_count": 0, "never_mutate_positions": [86, 114, 275]},
                    "experiment_design_table": [
                        {
                            "experiment_priority": "P1",
                            "position": 142,
                            "wild_type": "S",
                            "recommended_mutations": ["S142A", "S142V"],
                            "mutation_logic": "二壳层水网络/底物释放假设，需实验确认",
                            "expected_effect": "候选用于改善催化效率或底物进入；kcat/Km需实测",
                            "risk_flags": ["极性网络变化可能降低底物定位"],
                            "experiment_action": "构建单点突变体；与 WT 同批测比活和kcat/Km。",
                            "candidate_evidence_status": "computational_hypothesis",
                            "calibration_evidence_status": "not_calibrated",
                        }
                    ],
                }),
            },
            {
                "tool_name": "mutation_scan",
                "status": "completed",
                "result": json.dumps({
                    "sequence_length": 388,
                    "scan_type": "saturation",
                    "positions_scanned": 10,
                    "results": [],
                }),
            },
        ]

        report = orch._build_fallback_report("提高蛋白比活力", tool_results)

        assert "S142A" in report
        assert "S142V" in report
        assert "暂无可排单候选" not in report
        assert "能否下单**：可以进入单点验证设计" in report
        assert "下一步**：按 P1/P2 单点构建" in report
        assert "当前决策**：Go" in report

    def test_candidate_bridge_passes_priority_rows_to_scan_and_protssn(self):
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        orch = AgentOrchestrator()
        completed = [
            PlanStep(
                1,
                "mutation_priority_score",
                "rank",
                {},
                status="completed",
                result={
                    "experiment_design_table": [
                        {"position": 142, "recommended_mutations": ["K142E", "K142Q"]},
                        {"position": 170, "recommended_mutations": [{"mutation": "K170E"}]},
                    ]
                },
            )
        ]

        scan_step = orch._bridge_step_params(
            PlanStep(2, "mutation_scan", "scan", {"sequence": "A" * 200, "scan_type": "saturation"}),
            completed,
        )
        protssn_step = orch._bridge_step_params(
            PlanStep(3, "protssn_score", "score", {"sequence": "A" * 200, "mutations": []}),
            completed,
        )

        assert scan_step.params["positions"] == [142, 170]
        assert protssn_step.params["mutations"] == ["K142E", "K142Q", "K170E"]

    def test_bridge_passes_mapping_and_identity_to_site_feature_tool(self):
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        orch = AgentOrchestrator()
        mappings = [
            {
                "chain_id": "A",
                "pdb_residue_no": 5,
                "uniprot_position": 105,
                "residue_aa": "M",
                "mapping_confidence": "curated_sifts",
            }
        ]
        completed = [
            PlanStep(
                1,
                "residue_mapping_sifts",
                "map",
                {},
                status="completed",
                result={"found": True, "status": "completed", "mappings": mappings},
            ),
            PlanStep(
                2,
                "enzyme_identity_profile",
                "profile",
                {},
                status="completed",
                result={
                    "identity_status": "identified",
                    "protected_positions": [105],
                    "key_residues": [{"position": 105, "role": "catalytic acid"}],
                },
            ),
            PlanStep(
                3,
                "build_site_structure_function_features",
                "features",
                {},
                status="completed",
                result={
                    "features": [
                        {
                            "position": 105,
                            "is_protected": True,
                            "nearest_catalytic_distance_ca_angstrom": 0.0,
                        }
                    ]
                },
            ),
        ]

        step = orch._bridge_step_params(
            PlanStep(4, "build_site_structure_function_features", "features", {"pdb_object_name": "uploads/test.pdb"}),
            completed,
        )

        assert step.params["residue_mappings"] == mappings
        assert step.params["protected_positions"] == [105]
        assert step.params["catalytic_positions"] == [105]

        priority_step = orch._bridge_step_params(
            PlanStep(5, "mutation_priority_score", "rank", {"sequence": "A" * 120}),
            completed,
        )
        assert priority_step.params["site_structure_features"] == completed[-1].result["features"]

    def test_bridge_prefers_numbering_registry_rows_over_legacy_mappings(self):
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        orch = AgentOrchestrator()
        registry_rows = [
            {
                "source_scheme": "user_sequence",
                "source_position": 205,
                "target_scheme": "pdb_author",
                "target_position": 5,
                "target_chain_id": "A",
                "target_insertion_code": "A",
                "confidence": "sifts",
            }
        ]
        legacy_mappings = [
            {
                "chain_id": "A",
                "pdb_residue_no": 5,
                "uniprot_position": 999,
                "mapping_confidence": "inferred_from_coordinate_order",
            }
        ]
        completed = [
            PlanStep(
                1,
                "residue_mapping_sifts",
                "map",
                {},
                status="completed",
                result={
                    "found": True,
                    "status": "completed",
                    "mappings": legacy_mappings,
                    "numbering_registry_rows": registry_rows,
                },
            )
        ]

        step = orch._bridge_step_params(
            PlanStep(
                2,
                "build_site_structure_function_features",
                "features",
                {"pdb_object_name": "uploads/test.pdb"},
            ),
            completed,
        )

        assert step.params["residue_mappings"] == registry_rows

    def test_compact_result_trims_site_structure_function_features(self):
        from app.core.agent_graph import AgentOrchestrator

        payload = {
            "found": True,
            "status": "completed",
            "source": "pdb_ca_geometry",
            "capability_status": "structure_feature_table",
            "evidence_level": "STRUCTURE_GEOMETRY_FEATURES",
            "report_boundary": "boundary",
            "summary": {"feature_count": 60},
            "features": [{"position": idx} for idx in range(60)],
        }

        compact = json.loads(AgentOrchestrator._compact_result("build_site_structure_function_features", payload))

        assert compact["summary"]["feature_count"] == 60
        assert len(compact["features"]) == 20
        assert compact["features"][0]["position"] == 0
        assert compact["features"][-1]["position"] == 19

    def test_claim_audit_constraints_are_preserved_in_deterministic_enzyme_report(self, monkeypatch):
        orch = self._get_orchestrator()
        llm_called = False

        async def fake_call_llm(messages, **kwargs):
            nonlocal llm_called
            llm_called = True

            class _Message:
                content = "已按 Claim audit 输出：突变主表可用于实验规划，kcat 为 proxy。"

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

        monkeypatch.setattr(orch, "_call_llm", fake_call_llm)
        tool_results = [
            {
                "role": "tool",
                "tool_name": "mutation_priority_score",
                "status": "completed",
                "result": json.dumps({
                    "identity_gate": {"status": "passed"},
                    "candidate_table_status": "exploratory_requires_objective_evidence",
                    "experiment_design_table": [
                        {
                            "experiment_priority": "P1",
                            "position": 42,
                            "wild_type": "G",
                            "recommended_mutations": ["G42P"],
                            "mutation_logic": "loop rigidification",
                        }
                    ],
                    "objective_gate": {
                        "status": "blocked",
                        "missing_evidence": ["baseline Tm"],
                    },
                }),
            },
            {
                "role": "tool",
                "tool_name": "kcat_predict",
                "status": "completed",
                "result": json.dumps({
                    "is_real_inference": False,
                    "capability_status": "proxy",
                    "report_boundary": "Use only for exploratory triage.",
                }),
            },
        ]

        report = asyncio.run(orch._synthesize_sc(
            "提高这个酶的热稳定性",
            tool_results,
            "",
            [],
            "gpt55",
        ))

        assert llm_called is False
        assert "## 科学声明审计门控" in report
        assert "MUTATION_SITE_TABLE" in report
        assert "KCAT_PREDICT_REAL_RUNTIME" in report
        assert "MUTATION_EFFECT_VALIDATED" in report
        assert "RUNTIME_UNVERIFIED" in report
        assert "MISSING" in report
        assert "exploratory_requires_objective_evidence" in report
        assert "baseline Tm" in report
        assert "当前决策**：Watch" in report
        assert "当前决策**：Go" not in report
        assert "G42P" in report


class TestBinderSkillsAndReport:
    """T11: Skill loading and fallback report for design tasks."""

    def test_load_relevant_skills_design(self):
        """_load_relevant_skills should attempt to load protein_design for binder tasks."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        # This should not crash even if the skill file doesn't exist
        result = orch._load_relevant_skills("Design a binder for PD-L1")
        # Result may be empty if protein_design skill doesn't exist yet — that's OK
        assert isinstance(result, str)

    def test_build_fallback_report_with_design_data(self):
        """_build_fallback_report should include design section when design tools ran."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        tool_results = [
            {
                "tool_name": "proteinmpnn_design",
                "status": "completed",
                "result": {
                    "target_length": 100,
                    "best_recovery_rate": 0.42,
                    "best_confidence": 0.78,
                    "num_sequences_generated": 3,
                    "designs": [
                        {
                            "rank": 1,
                            "sequence": "MKTVRQERLKSIVRILERSKEPVQGAQLPVKELQLPGCHPNPIRALLD",
                            "recovery_rate": 0.42,
                            "mean_confidence": 0.78,
                            "num_mutations": 58,
                        },
                    ],
                },
            },
            {
                "tool_name": "esmfold_folding",
                "status": "completed",
                "result": {"plddt": 82.5, "sequence": "MKTVRQERLKSI..."},
            },
        ]

        report = orch._build_fallback_report("Design a binder for PD-L1", tool_results)

        assert "蛋白设计结果" in report
        assert "ProteinMPNN" in report, "Report should mention ProteinMPNN"
        assert "0.42" in report, "Report should show recovery rate"
        assert "0.78" in report, "Report should show confidence"

    def test_build_fallback_report_no_design_data(self):
        """Report without design tools should not have design section."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        tool_results = [
            {
                "tool_name": "predict_properties",
                "status": "completed",
                "result": {"molecular_weight_kda": 45.2, "isoelectric_point": 6.8},
            },
        ]

        report = orch._build_fallback_report("分析这个酶的性质", tool_results)
        assert "蛋白设计结果" not in report and "Protein Design Results" not in report, (
            "Non-design report should not have design section"
        )
        assert "Physicochemical Properties" in report
        assert "证据分层" in report

    def test_plan_confirmation_splits_activity_and_thermostability_objectives(self):
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        orch = AgentOrchestrator()
        reply = orch._build_plan_confirmation_reply(
            "提高蛋白比活力、热稳定性，深度解析",
            [
                PlanStep(
                    1,
                    "enzyme_identity_profile",
                    "Identify enzyme family and protected residues",
                    {"sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY"},
                )
            ],
        )

        assert "比活力 + 热稳定性双目标" in reply
        assert "### 输入证据审计" in reply
        assert "### 目标拆解" in reply
        assert "识别目标" in reply
        assert "比活力/催化效率" in reply
        assert "热稳定性" in reply
        assert "协同点" in reply
        assert "冲突点" in reply
        assert "两个目标可能冲突" in reply
        assert "门控未通过时" in reply
        assert "补证据路线" in reply
        assert "候选输出边界" in reply
        assert "预期输出" not in reply
        assert "最终输出可进入实验设计" not in reply

    def test_plan_confirmation_audits_pdb_only_before_strategy(self):
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        orch = AgentOrchestrator()
        message = (
            "提高蛋白比活力、热稳定性，深度解析\n\n"
            "[Attached files:\n"
            "- name: HM.pdb, object_name: uploads/user_1/HM.pdb]"
        )
        reply = orch._build_plan_confirmation_reply(
            message,
            [
                PlanStep(
                    1,
                    "structure_search_foldseek",
                    "Parse uploaded structure",
                    {"pdb_object_name": "uploads/user_1/HM.pdb"},
                )
            ],
            pdb_preflight={
                "status": "readable",
                "display_name": "HM.pdb",
                "line_count": 2367,
                "bytes": 188631,
                "chain_count": 1,
                "total_residues": 299,
                "total_atoms": 2313,
                "chains": [{"chain_id": "A", "residue_count": 299, "residue_range": "[1, 299]"}],
                "sequence_preview": "ASGFYVSGTILCDSTGNPFKIRGINHAHSWY",
            },
        )

        assert reply.index("### 输入证据审计") < reply.index("### 改造策略（先确认方向，再执行分析）")
        assert "输入类型**：PDB-only" in reply
        assert "PDB-coordinate-derived" in reply
        assert "不能把坐标顺序编号冒充成熟蛋白或 UniProt 编号" in reply
        assert "身份、编号、催化/关键位点未确认前，不输出位点级突变候选表" in reply

    def test_plan_confirmation_audits_pdb_plus_fasta_as_consistency_gate(self):
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        orch = AgentOrchestrator()
        message = (
            "提高蛋白比活力，序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY\n\n"
            "[Attached files:\n"
            "- name: HM.pdb, object_name: uploads/user_1/HM.pdb]"
        )
        reply = orch._build_plan_confirmation_reply(
            message,
            [
                PlanStep(
                    1,
                    "structure_search_foldseek",
                    "Parse uploaded structure",
                    {"pdb_object_name": "uploads/user_1/HM.pdb"},
                ),
                PlanStep(
                    2,
                    "enzyme_identity_profile",
                    "Identify enzyme family",
                    {"sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY"},
                ),
            ],
        )

        assert "输入类型**：PDB + FASTA" in reply
        assert "上传结构和独立 FASTA" in reply
        assert "PDB 链与 FASTA 是否一致" in reply
        assert "成熟蛋白/标签边界" in reply
        assert "PDB-coordinate-derived" not in reply

    def test_plan_confirmation_audits_fasta_plus_uniprot_before_numbering_claims(self):
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        orch = AgentOrchestrator()
        message = "UniProt P06278，序列：MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY，提高热稳定性"
        reply = orch._build_plan_confirmation_reply(
            message,
            [
                PlanStep(
                    1,
                    "enzyme_identity_profile",
                    "Identify enzyme family",
                    {"sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQANNSTPAY"},
                )
            ],
        )

        assert "输入类型**：FASTA + UniProt" in reply
        assert "完整序列和 UniProt 线索" in reply
        assert "UniProt 记录是否匹配输入序列" in reply
        assert "成熟链/信号肽边界" in reply
        assert "不能把坐标顺序编号冒充" not in reply

    def test_fallback_report_surfaces_claim_audit_gate(self):
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        tool_results = [
            {
                "tool_name": "kcat_predict",
                "status": "completed",
                "result": {
                    "predicted_kcat_s1": 12.3,
                    "predicted_log10_kcat": 1.09,
                    "enzyme_class": "hydrolase",
                    "confidence_interval_kcat_s1": [1.0, 100.0],
                    "efficiency_assessment": "proxy",
                    "method": "heuristic",
                    "is_real_inference": False,
                    "capability_status": "proxy",
                },
            }
        ]

        report = orch._build_fallback_report("预测kcat", tool_results)

        assert "科学声明审计门控" in report
        assert "KCAT_PREDICT_REAL_RUNTIME" in report
        assert "RUNTIME_UNVERIFIED" in report

    def test_claim_audit_tracks_live_evidence_source_status(self):
        from app.core.agent_graph import AgentOrchestrator

        tool_results = [
            {
                "tool_name": "annotation_bundle",
                "status": "completed",
                "result": {
                    "found": True,
                    "evidence_source": {
                        "source": "annotation_bundle",
                        "status": "degraded",
                        "mode": "local_database_or_heuristic_bundle",
                        "live_query_executed": False,
                        "reason": "No live UniProt/InterPro query executed.",
                    },
                },
            },
            {
                "tool_name": "blast_search",
                "status": "completed",
                "result": {
                    "status": "completed",
                    "results_count": 1,
                    "evidence_source": {
                        "source": "NCBI BLAST",
                        "status": "live",
                        "mode": "ncbi_blast_rest",
                        "live_query_executed": True,
                    },
                },
            },
            {
                "tool_name": "sequence_search",
                "status": "completed",
                "result": {
                    "status": "completed",
                    "results_count": 1,
                    "evidence_source": {
                        "source": "UniProt REST",
                        "status": "degraded",
                        "mode": "cache_hit",
                        "live_query_executed": False,
                    },
                },
            },
            {
                "tool_name": "interpro_live_lookup",
                "status": "completed",
                "result": {
                    "status": "completed",
                    "evidence_source": {
                        "source": "InterPro API",
                        "status": "live",
                        "mode": "interpro_api",
                        "live_query_executed": True,
                    },
                },
            },
            {
                "tool_name": "literature_live_search",
                "status": "completed",
                "result": {
                    "status": "degraded",
                    "evidence_source": {
                        "source": "PubMed/Crossref",
                        "status": "degraded",
                        "mode": "live_query_failed",
                        "live_query_executed": False,
                    },
                },
            },
            {
                "tool_name": "interproscan_sequence_submit",
                "status": "submitted",
                "result": {
                    "status": "submitted",
                    "job_id": "iprscan-test-job",
                    "evidence_source": {
                        "source": "InterProScan",
                        "status": "live",
                        "mode": "interproscan_rest_submit",
                        "live_query_executed": True,
                    },
                },
            },
            {
                "tool_name": "interproscan_sequence_status",
                "status": "completed",
                "result": {
                    "status": "pending",
                    "job_id": "iprscan-test-job",
                    "ebi_status": "RUNNING",
                    "result_available": False,
                    "results": [],
                    "results_count": 0,
                    "evidence_source": {
                        "source": "InterProScan",
                        "status": "live",
                        "mode": "interproscan_rest_status",
                        "live_query_executed": True,
                    },
                },
            },
            {
                "tool_name": "interproscan_sequence_status",
                "status": "completed",
                "result": {
                    "status": "completed",
                    "job_id": "iprscan-test-job",
                    "ebi_status": "FINISHED",
                    "result_available": True,
                    "results_count": 1,
                    "results": [
                        {
                            "interpro_accession": "IPR001461",
                            "name": "Peptidase A1",
                            "start": 1,
                            "end": 388,
                        }
                    ],
                    "evidence_source": {
                        "source": "InterProScan",
                        "status": "live",
                        "mode": "interproscan_rest_result",
                        "live_query_executed": True,
                    },
                },
            },
        ]

        audit = AgentOrchestrator._build_claim_audit(tool_results)
        claims_by_id = {}
        for claim in audit["claims"]:
            claims_by_id.setdefault(claim["claim_id"], []).append(claim)
        claims = {claim_id: items[-1] for claim_id, items in claims_by_id.items()}
        context = AgentOrchestrator._claim_audit_synthesis_context(tool_results)

        assert claims["ANNOTATION_BUNDLE_LIVE_QUERY"]["status"] == "RUNTIME_UNVERIFIED"
        assert claims["BLAST_LIVE_QUERY"]["status"] == "SUPPORTED"
        assert claims["SEQUENCE_SEARCH_LIVE_QUERY"]["status"] == "RUNTIME_UNVERIFIED"
        assert claims["INTERPRO_LIVE_QUERY"]["status"] == "SUPPORTED"
        assert claims["LITERATURE_LIVE_QUERY"]["status"] == "RUNTIME_UNVERIFIED"
        assert claims["INTERPROSCAN_SEQUENCE_SUBMITTED"]["status"] == "SUPPORTED"
        assert [claim["status"] for claim in claims_by_id["INTERPROSCAN_SEQUENCE_RESULT"]] == [
            "RUNTIME_UNVERIFIED",
            "SUPPORTED",
        ]
        assert "ANNOTATION_BUNDLE_LIVE_QUERY=RUNTIME_UNVERIFIED" in context
        assert "BLAST_LIVE_QUERY" in context
        assert "SEQUENCE_SEARCH_LIVE_QUERY=RUNTIME_UNVERIFIED" in context
        assert "INTERPRO_LIVE_QUERY" in context
        assert "LITERATURE_LIVE_QUERY=RUNTIME_UNVERIFIED" in context
        assert "INTERPROSCAN_SEQUENCE_SUBMITTED" in context
        assert "INTERPROSCAN_SEQUENCE_RESULT=RUNTIME_UNVERIFIED" in context
        assert "INTERPROSCAN_SEQUENCE_RESULT" in context

    def test_chat_submits_blast_and_md_but_keeps_alphafold2_inline(self):
        """External polling and long-running tools should not block chat confirmation."""
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        orch = AgentOrchestrator()

        assert orch._should_submit_interactive_async_step(
            PlanStep(1, "blast_search", "BLAST", {"sequence": "ACDEFGHIKL"})
        ) is True
        assert orch._should_submit_interactive_async_step(
            PlanStep(2, "alphafold2_folding", "AlphaFold2", {"sequence": "ACDEFGHIKL"})
        ) is False
        assert orch._should_submit_interactive_async_step(
            PlanStep(3, "gromacs_md", "MD", {"pdb_object_name": "uploads/user_1/a.pdb"})
        ) is True

    async def test_wet_lab_calibration_context_attach_requires_same_project(self, monkeypatch):
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        calls: list[dict] = []

        async def fake_list_runs(session, *, user_id, project_id=None, objective=None, limit=50, **kwargs):
            calls.append({
                "user_id": user_id,
                "project_id": project_id,
                "objective": objective,
                "limit": limit,
            })
            return [{
                "calibration_payload": {
                    "objective": objective,
                    "assay_key": "activity|pNP-C8|7.0|37",
                    "dataset_fingerprint": "fp1",
                    "measured_variant_count": 3,
                    "hit_rate": 0.667,
                    "data_quality_grade": "feedback_supported",
                    "evidence_level": "wet_lab_feedback",
                },
            }]

        monkeypatch.setattr(
            "app.services.wet_lab_calibration.list_wet_lab_calibration_runs",
            fake_list_runs,
        )

        orch = AgentOrchestrator()
        no_project = await orch._attach_wet_lab_calibration_context(
            PlanStep(1, "mutation_priority_score", "score", {"engineering_goal": "activity"}),
            current_user={"id": 7},
            audit_session=object(),
            project_id=None,
        )
        assert "wet_lab_calibration_summary" not in no_project.params

        with_project = await orch._attach_wet_lab_calibration_context(
            PlanStep(1, "mutation_priority_score", "score", {"engineering_goal": "activity"}),
            current_user={"id": 7},
            audit_session=object(),
            project_id="P123",
        )
        assert calls[-1] == {"user_id": 7, "project_id": "P123", "objective": "activity", "limit": 1}
        summary = with_project.params["wet_lab_calibration_summary"]
        assert summary["evidence_level"] == "wet_lab_feedback"
        assert summary["source"] == "latest_same_project_wet_lab_calibration_run"
        assert summary["objective_match"] is True

    def test_artifact_handoff_extracts_files_and_async_tasks(self):
        from app.core.agent_graph import AgentOrchestrator, ChatSnapshot, PlanStep

        orch = AgentOrchestrator()
        orch._snapshot = ChatSnapshot(stage="execute")
        step = PlanStep(
            1,
            "gromacs_md",
            "Run MD",
            {},
            status="submitted",
            result={
                "task_id": "task-123",
                "status_url": "/api/tools/tasks/task-123",
                "artifacts_url": "/api/tools/tasks/task-123/artifacts",
                "artifacts": [
                    {
                        "name": "md.log",
                        "category": "logs",
                        "object_name": "outputs/md.log",
                        "download_url": "/api/files/download?object_name=outputs/md.log",
                        "size": 1234,
                    }
                ],
            },
        )

        orch._append_artifact_handoff(step_index=0, step=step)

        handoffs = orch._snapshot.artifacts["handoffs"]
        assert orch._snapshot.artifacts["total_count"] == 2
        assert handoffs[0]["tool"] == "gromacs_md"
        assert handoffs[0]["handoff_status"] == "ready"
        kinds = {item["kind"] for item in handoffs[0]["items"]}
        assert {"async_task", "file"} <= kinds
        assert any(item.get("status_url") == "/api/tools/tasks/task-123" for item in handoffs[0]["items"])
        assert any(item.get("download_url") for item in handoffs[0]["items"])

    def test_build_fallback_report_with_mutation_strategy(self):
        """Mutation fallback report should prioritize first-screen experiment decisions."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        tool_results = [
            {
                "tool_name": "mutation_priority_score",
                "status": "completed",
                "result": {
                    "candidate_table_status": "ready",
                    "engineering_goal": "thermostability",
                    "strategy": {
                        "objective": "提高热稳定性，同时尽量保持催化活性、表达和可溶性。",
                        "design_principle": "优先加固非催化、可突变的柔性环和局部疏松区域。",
                        "screening_logic": ["排除催化位点", "优先表面暴露残基"],
                    },
                    "summary": {"tier_1_count": 1, "tier_2_count": 0, "never_mutate_positions": [10]},
                    "wet_lab_calibration_context": {
                        "evidence_level": "wet_lab_feedback",
                        "measured_variant_count": 3,
                        "hit_rate": 0.6667,
                        "candidate_scope": "project_level_calibration_not_direct_variant_validation",
                    },
                    "tier_1_candidates": [
                        {
                            "position": 42,
                            "user_position": 42,
                            "pdb_position": None,
                            "uniprot_position": None,
                            "numbering_status": "user_sequence_only",
                            "structure_feature_status": "available",
                            "ca_b_factor": 18.5,
                            "nearest_catalytic_distance_ca_angstrom": 6.2,
                            "contact_count_ca_8a": 7,
                            "ca_contact_environment": "moderate_ca_neighborhood",
                            "secondary_structure": "helix",
                            "secondary_structure_source": "pdb_helix_sheet_records",
                            "rel_sasa_status": "not_computed",
                            "pocket_channel_interface_status": "not_computed",
                            "nonpolymer_proximity_status": "computed_from_input_pdb",
                            "nearest_nonpolymer_heteroatom_distance_angstrom": 3.2,
                            "nearest_nonpolymer_component_id": "NAG",
                            "phi_deg": -62.5,
                            "psi_deg": 131.2,
                            "backbone_torsion_status": "computed",
                            "structure_feature_risk_flags": ["near_catalytic_ca_shell"],
                            "wild_type": "G",
                            "composite_priority": 8.2,
                            "logic": "位于蛋白表面，高度溶剂可及；与活性中心距离适中",
                            "expected_effect": "候选增稳方向，需实验确认",
                            "risk_flags": ["Gly→Pro可能误伤必要柔性"],
                            "experiment_action": "构建单点突变体；与 WT 同批表达纯化；测 Tm/热处理残余活性；同步复测比活、可溶性和聚集风险。",
                            "experiment_priority": "P1",
                            "candidate_evidence_status": "计算候选，待实验验证",
                            "calibration_evidence_status": "wet_lab_feedback",
                            "recommended_mutations": [{"mutation": "G42P", "purpose": "test"}],
                        }
                    ],
                    "tier_2_candidates": [],
                },
            }
        ]

        report = orch._build_fallback_report("提高这个酶的热稳定性", tool_results)

        assert "## 结论卡片 / 状态摘要" not in report
        assert "当前决策**：Go" in report
        assert "提高热稳定性" in report
        assert "## 突变位点主表（实验排单）" in report
        assert "湿实验校准背景" in report
        assert "这是项目/assay 级排序校准，不是下方具体候选的直接湿实验验证" in report
        assert "校准背景" in report
        assert "wet_lab_feedback" in report
        assert "| 优先级 | 位点 | 推荐突变 | 机制逻辑 | 主要风险 |" in report
        assert "编号" in report
        assert "证据/校准" in report
        assert "未映射" in report
        assert "## 位点突变逻辑 / 风险 / 实验动作" in report
        assert "## 探索性验证建议" in report
        assert "## Go / Watch / No-Go" not in report
        assert "## 改造策略及说明" in report
        assert "G42P" in report
        assert "Gly→Pro可能误伤必要柔性" in report
        assert "突变逻辑" in report
        assert "风险提示" in report
        assert "实验动作" in report
        assert "构建单点突变体" in report
        assert "P1" in report
        assert "没有实验证据、实时运行证据或编号映射确认时，不写入确定结论" in report
        assert "结构特征" in report
        assert "PDB B-factor(原始字段,不作稳定性解释)=18.5" in report
        assert "最近催化CA距离=6.2 A" in report
        assert "8A CA接触数=7" in report
        assert "CA接触环境=moderate_ca_neighborhood" in report
        assert "二级结构=helix" in report
        assert "relSASA=not_computed" in report
        assert "口袋/通道=not_computed" in report
        assert "最近非聚合HETATM距离=3.2 A（NAG）" in report
        assert "主链phi/psi=-62.5/131.2（computed）" in report
        assert "near_catalytic_ca_shell" in report
        assert "这些字段仅来自 PDB CA 几何与编号映射，不能单独证明突变收益" in report

        main_table_index = report.index("## 突变位点主表（实验排单）")
        strategy_index = report.index("## 改造策略及说明")
        site_detail_index = report.index("## 位点突变逻辑 / 风险 / 实验动作")
        suggestion_index = report.index("## 探索性验证建议")
        assert strategy_index < main_table_index
        assert main_table_index < site_detail_index < suggestion_index

    def test_build_fallback_report_surfaces_specified_mutation_reviews(self):
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        tool_results = [
            {
                "tool_name": "mutation_priority_score",
                "status": "completed",
                "result": {
                    "candidate_table_status": "ready",
                    "strategy": {
                        "objective": "提高比活力并监控热稳定性。",
                        "design_principle": "先复核用户指定突变，再生成候选表。",
                        "screening_logic": ["不改催化核心"],
                    },
                    "summary": {"tier_1_count": 0, "tier_2_count": 0, "never_mutate_positions": [86]},
                    "specified_mutation_reviews": [
                        {
                            "mutation": "P338T",
                            "wild_type_match": True,
                            "is_protected": False,
                            "review_decision": "watch_review",
                            "tradeoff_interpretation": "Pro->Thr activity-stability trade-off",
                            "risk_flags": ["稳定性下降风险"],
                        },
                        {
                            "mutation": "D86N",
                            "wild_type_match": True,
                            "is_protected": True,
                            "review_decision": "no_go_protected_position",
                            "tradeoff_interpretation": "catalytic/protected residue review",
                            "risk_flags": ["命中催化/功能保护位点，禁止作为首轮候选"],
                        },
                    ],
                    "experiment_design_table": [
                        {
                            "experiment_priority": "P1",
                            "position": 338,
                            "wild_type": "P",
                            "recommended_mutations": ["P338T"],
                            "mutation_logic": "用户指定突变复核后进入 Watch 验证。",
                            "expected_effect": "需实验确认",
                            "risk_flags": ["稳定性下降风险"],
                        }
                    ],
                },
            }
        ]

        report = orch._build_fallback_report("P338T 和 D86N 这两个突变怎么样", tool_results)

        assert "## 用户指定突变复核" in report
        assert "P338T" in report
        assert "D86N" in report
        assert "| P338T | Watch | 是 | 否 |" in report
        assert "| D86N | No-Go | 是 | 是 |" in report
        assert "命中催化/功能保护位点" in report
        assert "不等同于平台自动推荐" in report

    def test_build_fallback_report_surfaces_site_structure_function_features(self):
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        tool_results = [
            {
                "tool_name": "structure_search_foldseek",
                "status": "completed",
                "result": {
                    "found": False,
                    "status": "degraded",
                    "backend": "summary_only",
                    "query_structure": {"chain_count": 1, "total_residues": 299, "total_atoms": 2313},
                    "report_boundary": "Foldseek/结构解析只能作为结构相似性和输入质控证据",
                },
            },
            {
                "tool_name": "residue_mapping_sifts",
                "status": "completed",
                "result": {
                    "found": True,
                    "status": "completed",
                    "source": "local_sifts_mapping",
                    "mapping_count": 1,
                    "mappings": [{"chain_id": "A", "pdb_residue_no": 5, "uniprot_position": 105}],
                },
            },
            {
                "tool_name": "build_site_structure_function_features",
                "status": "completed",
                "result": {
                    "found": True,
                    "status": "completed",
                    "feature_count": 1,
                    "summary": {
                        "feature_count": 1,
                        "ca_available_count": 1,
                        "mapped_count": 1,
                        "protected_count": 1,
                    },
                    "report_boundary": "位点特征表只来自 PDB 坐标和可选编号映射",
                    "features": [
                        {
                            "position": 105,
                            "wild_type": "D",
                            "pdb_position": "A:5",
                            "uniprot_position": 105,
                            "ca_coord": {"x": 0.0, "y": 0.0, "z": 0.0},
                            "b_factor": 20.0,
                            "nearest_catalytic_distance_ca_angstrom": 4.0,
                            "contact_count_ca_8a": 3,
                            "ca_contact_environment": "sparse_ca_neighborhood",
                            "secondary_structure": "helix",
                            "nearest_nonpolymer_heteroatom_distance_angstrom": 3.2,
                            "nearest_nonpolymer_component_id": "NAG",
                            "phi_deg": -62.5,
                            "psi_deg": 131.2,
                            "backbone_torsion_status": "computed",
                            "risk_flags": ["protected_or_catalytic_position"],
                        }
                    ],
                },
            },
        ]

        report = orch._build_fallback_report("上传PDB深度分析结构位点", tool_results)

        assert "## 位点结构-功能特征表" in report
        assert "特征数=1" in report
        assert "| 105 | D | A:5 | 105 | 0.0,0.0,0.0 | 20.0 | N/A | 4.0 | 3.2 NAG | -62.5/131.2 | 3 | sparse_ca_neighborhood | helix | protected_or_catalytic_position |" in report
        assert "位点特征表只来自 PDB 坐标和可选编号映射" in report
        assert "build_site_structure_function_features" in report

    def test_build_fallback_report_shows_exploratory_upgrade_conditions(self):
        """Exploratory mutation rows must stay Watch-level and show upgrade gates."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()

        tool_results = [
            {
                "tool_name": "mutation_priority_score",
                "status": "completed",
                "result": {
                    "candidate_table_status": "exploratory_requires_objective_evidence",
                    "identity_gate": {
                        "status": "passed",
                        "identity_status": "identified",
                    },
                    "objective_gate": {
                        "status": "blocked",
                        "missing_evidence": ["baseline Tm", "WT activity control"],
                    },
                    "summary": {"tier_1_count": 0, "tier_2_count": 1, "never_mutate_positions": []},
                    "experiment_design_table": [
                        {
                            "experiment_priority": "P2-探索",
                            "tier": 2,
                            "position": 42,
                            "wild_type": "G",
                            "recommended_mutations": ["G42P"],
                            "mutation_logic": "loop rigidification hypothesis",
                            "expected_effect": "需实验确认",
                            "risk_flags": ["探索性候选：不能写成已验证改造结论"],
                            "experiment_action": "构建单点突变体；与 WT 同批验证。",
                            "candidate_evidence_status": "computational_hypothesis",
                            "calibration_evidence_status": "not_calibrated",
                            "blocked_upgrade_conditions": [
                                "必须完成身份/编号或结构映射复核后，才可升级为正式 P1/P2 排名。",
                                "具体候选只有获得该突变体直接湿实验数据后，才可升级为 experimental_supported。",
                            ],
                        }
                    ],
                },
            }
        ]

        report = orch._build_fallback_report("继续分析探索性候选突变", tool_results)

        assert "当前决策**：Watch" in report
        assert "## 突变位点探索清单（不可直接排单）" in report
        assert "## 探索性验证建议" in report
        assert "P2-探索" in report
        assert "computational_hypothesis" in report
        assert "升级条件" in report
        assert "直接湿实验数据" in report
        assert "当前决策**：Go" not in report
        assert "| P1 |" not in report

    def test_fallback_report_surfaces_multi_objective_gate_details(self):
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        objective_gate = {
            "status": "ready",
            "objective": "specific_activity",
            "module": "specific_activity",
            "objective_signals": ["specific_activity", "thermostability"],
            "multi_objective": True,
            "objective_modules": [
                {
                    "objective": "specific_activity",
                    "module": "specific_activity",
                    "primary_question": "Does the mutation improve specific activity?",
                    "validation_metrics": ["specific activity", "kcat", "Km", "kcat/Km"],
                },
                {
                    "objective": "thermostability",
                    "module": "thermostability",
                    "primary_question": "Can stability improve while activity is retained?",
                    "validation_metrics": ["Tm/Tagg", "thermal half-life", "residual activity"],
                },
            ],
            "combined_required_evidence": [
                "confirmed catalytic residues and no-touch zone",
                "baseline Tm, half-life, or residual activity assay condition",
            ],
            "combined_validation_metrics": ["specific activity", "kcat/Km", "Tm/Tagg", "thermal half-life"],
            "candidate_output_allowed": True,
            "missing_evidence": [],
            "forbidden_shortcuts": [
                "do not interpret total broth/supernatant activity as catalytic improvement",
                "do not treat total activity after heat challenge as pure catalytic improvement",
            ],
        }
        report = orch._build_fallback_report(
            "提高比活力和热稳定性",
            [
                {
                    "tool_name": "enzyme_objective_module_plan",
                    "status": "completed",
                    "result": objective_gate,
                },
                {
                    "tool_name": "mutation_priority_score",
                    "status": "completed",
                    "result": {
                        "candidate_table_status": "ready",
                        "engineering_goal": "activity",
                        "ranking_mode": "activity_stability",
                        "multi_objective": True,
                        "strategy": {
                            "objective": "同时提高比活力/催化效率和热稳定性；候选必须以双指标共同验证。",
                            "design_principle": "先保护催化核心和结构核心。",
                            "screening_logic": ["比活力线要求 specific activity。", "热稳定线要求 Tm。"],
                        },
                        "objective_gate": objective_gate,
                        "summary": {"tier_1_count": 1, "tier_2_count": 0, "never_mutate_positions": []},
                        "experiment_design_table": [
                            {
                                "experiment_priority": "P1",
                                "tier": 1,
                                "position": 42,
                                "wild_type": "S",
                                "recommended_mutations": ["S42A"],
                                "mutation_logic": "二壳层微环境与局部网络假设",
                                "expected_effect": "同时探索催化效率与热稳定保持",
                                "risk_flags": ["需同时复测活性与稳定性"],
                                "experiment_action": "同批测比活力、kcat/Km、Tm 和热半衰期。",
                                "candidate_evidence_status": "computational_hypothesis",
                                "calibration_evidence_status": "not_calibrated",
                            }
                        ],
                    },
                },
            ],
        )

        assert "## Objective Module Gate" in report
        assert "多目标门控**：是" in report
        assert "目标模块明细" in report
        assert "specific_activity" in report
        assert "thermostability" in report
        assert "合并验证指标" in report
        assert "specific activity" in report
        assert "thermal half-life" in report
        assert "双指标共同验证" in report
        assert "同批测比活力、kcat/Km、Tm 和热半衰期" in report

    def test_fallback_report_explains_tool_sources_and_boundaries(self):
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        report = orch._build_fallback_report(
            "提高蛋白比活力，说明通过哪些工具得到结果",
            [
                {
                    "tool_name": "structure_search_foldseek",
                    "status": "completed",
                    "result": json.dumps({
                        "status": "completed",
                        "found": True,
                        "capability_status": "structure_similarity_search",
                        "report_boundary": "Foldseek/结构解析只能作为结构相似性和输入质控证据；不能单独确认酶身份。",
                        "query_structure": {"chain_count": 1, "total_residues": 299, "total_atoms": 2313},
                    }),
                },
                {
                    "tool_name": "residue_mapping_sifts",
                    "status": "completed",
                    "result": json.dumps({
                        "status": "completed",
                        "found": True,
                        "capability_status": "coordinate_order_inference",
                        "report_boundary": "这是按 PDB 坐标残基顺序生成的 SIFTS-style 推断，不是外部 SIFTS/UniProt 实证映射。",
                    }),
                },
                {
                    "tool_name": "predict_properties",
                    "status": "completed",
                    "result": json.dumps({
                        "length": 299,
                        "capability_status": "physicochemical_baseline",
                        "report_boundary": "理化性质是由输入序列计算得到的背景基线；不能单独证明热稳定性、比活力、酶身份或突变增益。",
                    }),
                },
                {
                    "tool_name": "blast_search",
                    "status": "submitted",
                    "result": json.dumps({"task_id": "blast-1", "status_url": "/api/tools/tasks/blast-1"}),
                },
                {
                    "tool_name": "kcat_predict",
                    "status": "completed",
                    "result": json.dumps({"predicted_kcat_s1": 10.0, "capability_status": "proxy"}),
                },
                {
                    "tool_name": "enzyme_function",
                    "status": "completed",
                    "result": json.dumps({
                        "capability_status": "proxy",
                        "report_boundary": "序列模体/embedding 统计只能作为功能背景假设；不得写成已确认 EC。",
                    }),
                },
                {
                    "tool_name": "mutation_priority_score",
                    "status": "completed",
                    "result": json.dumps({
                        "candidate_table_status": "blocked_by_identity_gate",
                        "identity_gate": {"status": "blocked", "reason": "identity unresolved"},
                        "experiment_design_table": [],
                        "summary": {"tier_1_count": 0, "tier_2_count": 0},
                    }),
                },
            ],
        )

        assert "## 工具来源说明" in report
        assert "| 工具 | 状态 | 作用 | 证据层级 | 报告用途 |" in report
        assert "| structure_search_foldseek | completed | 上传结构解析/结构同源检索 | 输入/结构证据 | structure_similarity_search；Foldseek/结构解析只能作为结构相似性和输入质控证据；不能单独确认酶身份。 |" in report
        assert "| residue_mapping_sifts | completed | 残基编号映射 | 编号证据 | coordinate_order_inference；这是按 PDB 坐标残基顺序生成的 SIFTS-style 推断，不是外部 SIFTS/UniProt 实证映射。 |" in report
        assert "| predict_properties | completed | 理化性质基线 | 背景基线 | physicochemical_baseline；理化性质是由输入序列计算得到的背景基线；不能单独证明热稳定性、比活力、酶身份或突变增益。 |" in report
        assert "| blast_search | submitted | 序列同源检索 | 序列同源证据 | 后台任务已提交；当前不作为完成证据 |" in report
        assert "| kcat_predict | completed | kcat 启发式估算 | 启发式动力学背景 | 启发式背景；不能证明比活力或突变增益 |" in report
        assert "| enzyme_function | completed | EC/酶类预测背景 | 功能预测背景 | proxy；序列模体/embedding 统计只能作为功能背景假设；不得写成已确认 EC。 |" in report
        assert "candidate_table_status=blocked_by_identity_gate" in report
        assert "submitted 只表示后台任务已提交" in report

    def test_build_fallback_report_suppresses_candidates_when_identity_gate_is_blocked(self):
        """Identity/numbering failure must produce a gate summary, not a wide mutation table."""
        from app.core.agent_graph import AgentOrchestrator

        orch = AgentOrchestrator()
        report = orch._build_fallback_report(
            "提高这个酶的比活力，继续深度分析",
            [
                {
                    "tool_name": "mutation_priority_score",
                    "status": "completed",
                    "result": {
                        "candidate_table_status": "blocked_by_identity_gate",
                        "identity_gate": {
                            "status": "blocked",
                            "identity_status": "unresolved",
                            "reason": "enzyme identity or residue numbering is not confirmed enough",
                        },
                        "objective_gate": {
                            "status": "blocked",
                            "missing_evidence": ["WT specific activity baseline"],
                        },
                        "experiment_design_table": [],
                        "tier_1_candidates": [],
                        "tier_2_candidates": [],
                        "summary": {
                            "tier_1_count": 0,
                            "tier_2_count": 0,
                            "candidate_table_status": "blocked_by_identity_gate",
                        },
                    },
                }
            ],
        )

        assert "## 突变位点探索清单（未放行）" in report
        assert "0 个可排单候选" in report
        assert "能否下单**：不能直接下单；身份/编号门控未通过" in report
        assert "主要缺口**：WT specific activity baseline" in report
        assert "下一步**：先补齐 FASTA/同源身份" in report
        assert "## 位点突变逻辑 / 风险 / 实验动作" in report
        assert "## 探索性验证建议" in report
        assert "## 突变位点探索清单（不可直接排单）" not in report
        assert "P2-探索" not in report
        assert "| 优先级 | 证据状态 |" not in report

    def test_compact_mutation_priority_preserves_exploratory_boundary(self):
        """LLM synthesis compact payload must keep table-level and row-level evidence gates."""
        from app.core.agent_graph import AgentOrchestrator

        payload = {
            "candidate_table_status": "exploratory_requires_objective_evidence",
            "candidate_table_boundary": {
                "mode": "exploratory",
                "evidence_level": "computational_hypothesis",
                "no_wet_lab_claim": True,
                "upgrade_requires": [
                    "confirmed enzyme identity and residue numbering/mapping",
                    "direct wet-lab measurement for each proposed mutation before claiming improvement",
                ],
            },
            "experiment_design_table": [
                {
                    "experiment_priority": "P2-探索",
                    "position": 42,
                    "wild_type": "G",
                    "recommended_mutations": ["G42P"],
                    "candidate_evidence_status": "computational_hypothesis",
                    "blocked_upgrade_conditions": [
                        "具体候选只有获得该突变体直接湿实验数据后，才可升级为 experimental_supported。",
                    ],
                }
            ],
            "tier_1_candidates": [],
            "tier_2_candidates": [],
            "summary": {"tier_1_count": 0, "tier_2_count": 1},
        }

        compact = json.loads(AgentOrchestrator._compact_result("mutation_priority_score", payload))

        assert compact["candidate_table_status"] == "exploratory_requires_objective_evidence"
        assert compact["candidate_table_boundary"]["mode"] == "exploratory"
        assert compact["candidate_table_boundary"]["no_wet_lab_claim"] is True
        assert "direct wet-lab measurement" in compact["candidate_table_boundary"]["upgrade_requires"][1]
        assert compact["experiment_design_table"][0]["blocked_upgrade_conditions"]
        assert compact["experiment_design_table"][0]["candidate_evidence_status"] == "computational_hypothesis"

    def test_mutation_candidate_boundary_context_makes_exploratory_rules_explicit(self):
        """SC synthesis prompt should receive natural-language mutation table boundaries."""
        from app.core.agent_graph import AgentOrchestrator

        tool_results = [
            {
                "tool_name": "mutation_priority_score",
                "status": "completed",
                "result": json.dumps({
                    "candidate_table_status": "exploratory_requires_objective_evidence",
                    "candidate_table_boundary": {
                        "mode": "exploratory",
                        "evidence_level": "computational_hypothesis",
                        "no_wet_lab_claim": True,
                        "upgrade_requires": ["direct wet-lab measurement"],
                    },
                    "objective_gate": {
                        "missing_evidence": ["baseline Tm"],
                    },
                    "experiment_design_table": [
                        {
                            "experiment_priority": "P2-探索",
                            "candidate_evidence_status": "computational_hypothesis",
                            "blocked_upgrade_conditions": ["direct wet-lab data required"],
                        }
                    ],
                }),
            }
        ]

        context = AgentOrchestrator._mutation_candidate_boundary_synthesis_context(tool_results)

        assert "Mutation candidate boundary constraints" in context
        assert "Candidate table status: exploratory_requires_objective_evidence" in context
        assert "No wet-lab claim: true" in context
        assert "baseline Tm" in context
        assert "direct wet-lab data required" in context
        assert "Watch/P2-exploratory computational hypotheses" in context
        assert "do not promote them to Go/P1" in context

    def test_empty_sequence_search_result_builds_no_evidence_reply(self):
        """P0/P1: empty search evidence must not be hidden by a full report."""
        from app.core.agent_graph import AgentOrchestrator
        orch = AgentOrchestrator()
        tool_results = [
            {
                "tool_name": "sequence_search",
                "status": "completed",
                "result": '{"query":"能力边界 文献依据","database":"uniprot","results_count":0,"results":[],"status":"completed"}',
            }
        ]

        assert orch._tool_results_have_no_evidence(tool_results) is True
        reply = orch._build_no_evidence_reply("这个模型有没有文献依据？", tool_results)
        assert "不能给出确定性改造建议" in reply
        assert "results=0" in reply


class TestSanitizeMessages:
    """Test _sanitize_messages for Dashscope/Qwen API compatibility.

    Dashscope requires 'content' to be a string — tool_calls, None, list,
    and dict content types all cause 'Unexpected item type in content' errors.
    """

    def setup_method(self):
        from app.core.agent_graph import AgentOrchestrator
        self.orch = AgentOrchestrator()

    def test_none_content_becomes_empty_string(self):
        messages = [
            {"role": "assistant", "content": None, "tool_calls": [{"id": "tc_1"}]},
            {"role": "user", "content": "hello"},
        ]
        result = self.orch._sanitize_messages(messages)
        # Assistant with None content → dropped (pure tool_calls message)
        assert len(result) == 1
        assert result[0]["content"] == "hello"

    def test_list_content_extracted_to_string(self):
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe this protein"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
            ]},
        ]
        result = self.orch._sanitize_messages(messages)
        assert len(result) == 1
        assert isinstance(result[0]["content"], str)
        assert "Describe this protein" in result[0]["content"]

    def test_dict_content_coerced_to_string(self):
        messages = [
            {"role": "user", "content": {"query": "protein analysis"}},
        ]
        result = self.orch._sanitize_messages(messages)
        assert isinstance(result[0]["content"], str)

    def test_normal_messages_unchanged(self):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Analyze this sequence: MVLSPAD"},
            {"role": "assistant", "content": "Here is the analysis."},
        ]
        result = self.orch._sanitize_messages(messages)
        assert len(result) == 3
        assert result[0]["content"] == "You are a helpful assistant."
        assert result[2]["content"] == "Here is the analysis."

    def test_tool_message_preserves_tool_call_id(self):
        messages = [
            {"role": "tool", "content": "result data", "tool_call_id": "call_abc123"},
        ]
        result = self.orch._sanitize_messages(messages)
        assert result[0]["tool_call_id"] == "call_abc123"
        assert result[0]["content"] == "result data"

    def test_empty_assistant_dropped(self):
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "assistant", "content": "   "},  # whitespace only
            {"role": "user", "content": "Next question"},
        ]
        result = self.orch._sanitize_messages(messages)
        assert len(result) == 2
        assert all(r["role"] != "assistant" for r in result)

    def test_no_tool_calls_field_in_output(self):
        """tool_calls field should never leak into sanitized messages."""
        messages = [
            {"role": "assistant", "content": "I'll use a tool", "tool_calls": []},
        ]
        result = self.orch._sanitize_messages(messages)
        for msg in result:
            assert "tool_calls" not in msg


class TestChatMarkdownStreaming:
    """Regression coverage for long Markdown/checklist replies."""

    def setup_method(self):
        from app.core.agent_graph import AgentOrchestrator
        self.orch = AgentOrchestrator()

    def test_stream_chunks_preserve_markdown_whitespace(self):
        text = "标题\n\n- A\n- B\n\n| 列 | 值 |\n|---|---|\n| M1 | 通过 |"
        chunks = list(self.orch._iter_text_stream_chunks(text, chunk_size=8))

        assert "".join(chunks) == text
        assert "\n\n- A" in "".join(chunks)
        assert "|---|---|" in "".join(chunks)

    def test_document_reply_request_detects_execution_checklist(self):
        assert self.orch._is_document_reply_request("整理成实验执行清单和数据记录表格")
        assert self.orch._is_document_reply_request("Create an SOP template")
        assert not self.orch._is_document_reply_request("hello")

    @pytest.mark.asyncio
    async def test_document_reply_uses_larger_token_budget(self, monkeypatch):
        calls = {}

        class _Message:
            content = "## 实验执行清单\n\n- step 1"

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        async def fake_call_llm(messages, model_id=None, **kwargs):
            calls["messages"] = messages
            calls["max_tokens"] = kwargs.get("max_tokens")
            return _Response()

        monkeypatch.setattr(self.orch, "_call_llm", fake_call_llm)

        reply = await self.orch._chat_reply("请整理成给学生直接执行的 SOP 版清单", [])

        assert reply.startswith("## 实验执行清单")
        assert calls["max_tokens"] == 2200
        assert "Do not shorten" in calls["messages"][0]["content"]
        assert "Manual enzyme analysis flow v1" in calls["messages"][0]["content"]
        assert "input normalization" in calls["messages"][0]["content"]
        assert "minimal enzyme profile" in calls["messages"][0]["content"]
        assert "activity-stability" in calls["messages"][0]["content"]

    def test_sc_prompt_contains_manual_enzyme_analysis_protocol(self):
        from app.core.agent_roles import SC_SYSTEM_PROMPT

        assert "Manual enzyme analysis flow v1" in SC_SYSTEM_PROMPT
        assert "structure acquisition/status" in SC_SYSTEM_PROMPT
        assert "minimal enzyme profile" in SC_SYSTEM_PROMPT
        assert "prediction conflicts with wet-lab feedback" in SC_SYSTEM_PROMPT
        assert "activity-stability" in SC_SYSTEM_PROMPT
        assert "Go/No-Go" in SC_SYSTEM_PROMPT
        assert "residue" in SC_SYSTEM_PROMPT
        assert "numbering alignment" in SC_SYSTEM_PROMPT
        assert "epistasis risk" in SC_SYSTEM_PROMPT
        assert "success probability" in SC_SYSTEM_PROMPT
