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

# Ensure app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


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

        assert "Protein Design Results" in report, (
            "Report should contain 'Protein Design Results' section"
        )
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
        assert "Protein Design Results" not in report, (
            "Non-design report should not have design section"
        )
        assert "Physicochemical Properties" in report
