"""Theoretical/homology model evidence: parsing, strategy wiring, identity gate."""
import asyncio
import copy

import pytest

from app.core.agent_graph import AgentOrchestrator, PlanStep
from app.services.pdb_parser import parse_pdb
from app.services.structure_strategy import (
    select_structure_strategy,
    theoretical_template_evidence,
)
from app.tools.registry import ToolRegistry


SEQ = "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY"

ToolRegistry.discover()


def _pdb(remark_lines=(), method="HOMOLOGY MODEL", b_factor=0.5):
    lines = [
        "HEADER    HYDROLASE                               01-JAN-26   MODEL",
        f"EXPDTA    {method}",
        "REMARK   3",
        "REMARK   3   RESOLUTION. NOT APPLICABLE",
        "TITLE     STRUCTURE OF A GLYCOSIDE HYDROLASE",
        "SEQRES   1 A   10  ALA CYS ASP GLU PHE GLY HIS ILE LYS LEU",
    ]
    lines.extend(remark_lines)
    for index, aa in enumerate("ACDEFGHIKL", start=1):
        code = {
            "A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE",
            "G": "GLY", "H": "HIS", "I": "ILE", "K": "LYS", "L": "LEU",
        }[aa]
        column = b_factor[index - 1] if isinstance(b_factor, (list, tuple)) else b_factor
        lines.append(
            f"ATOM  {index:5d}  CA  {code} A{index:4d}    "
            f"{float(index):8.3f}{0.0:8.3f}{0.0:8.3f}{1.00:6.2f}{column:6.2f}           C"
        )
    lines.append("END")
    return "\n".join(lines) + "\n"


SWISS_REMARKS = (
    "REMARK  99 SWISS-MODEL HOMOLOGY MODEL",
    "REMARK  99 TEMPLATE 3GBX.A  SEQUENCE IDENTITY 93.0  SEQUENCE COVERAGE 98.0",
    "REMARK  99 GMQE 0.82",
    "REMARK  99 QMEAN -2.10  QMEAN Z-SCORE -1.35",
)


def _templates(preflight):
    return theoretical_template_evidence(preflight)


def test_parser_extracts_swiss_model_header_evidence():
    analysis = parse_pdb(_pdb(SWISS_REMARKS))
    model = analysis["theoretical_model"]
    assert model["is_theoretical"] is True
    assert model["source"] == "SWISS-MODEL"
    assert [t["template_id"] for t in model["templates"]] == ["3gbx"]
    assert model["template_sequence_identity"] == pytest.approx(0.93)
    assert model["template_coverage"] == pytest.approx(0.98)
    assert model["gmqe"] == pytest.approx(0.82)
    assert model["qmean"] == pytest.approx(-2.1)
    assert model["qmean_z"] == pytest.approx(-1.35)
    assert model["b_factor_semantics"] == "model_quality_per_residue_score"
    assert "quality score" in analysis["b_factor_scope"]


def test_parser_multiple_templates_and_old_remark_999():
    remarks = (
        "REMARK 999 TEMPLATE 1ABC  SEQUENCE IDENTITY 71.5",
        "REMARK 999 TEMPLATE 2DEF  SEQUENCE IDENTITY 55.0",
        "REMARK 999 GMQE 0.61",
    )
    model = parse_pdb(_pdb(remarks))["theoretical_model"]
    assert [t["template_id"] for t in model["templates"]] == ["1abc", "2def"]
    assert model["template_sequence_identity"] == pytest.approx(0.715)
    assert model["qmean"] is None


def test_parser_experimental_structure_is_not_theoretical():
    analysis = parse_pdb(_pdb(method="X-RAY DIFFRACTION", b_factor=24.0))
    model = analysis["theoretical_model"]
    assert model == {"status": "not_theoretical", "is_theoretical": False}
    assert "theoretical_model" not in (analysis.get("b_factor_scope") or "")


def test_parser_model_without_template_stays_explicit():
    model = parse_pdb(_pdb(("REMARK  99 SWISS-MODEL HOMOLOGY MODEL",)))["theoretical_model"]
    assert model["is_theoretical"] is True
    assert model["templates"] == []
    assert model["template_sequence_identity"] is None


def _plddt(value, index):
    return value[index % len(value)]


def test_parser_recognizes_alphafold_plddt_column():
    # AlphaFold exports write per-residue confidence in the B-factor column on a
    # 0-100 scale; it must not be read as a local-quality score or B-factor.
    analysis = parse_pdb(_pdb(b_factor=[29.38, 95.0, 98.99, 91.2, 88.0, 99.0, 97.5, 86.0, 93.0, 90.9]))
    model = analysis["theoretical_model"]
    assert model["b_factor_semantics"] == "plddt_confidence_score"
    assert analysis["b_factor_semantics"] == "plddt_confidence_score"
    scope = analysis["b_factor_scope"]
    assert "pLDDT" in scope and "0-100" in scope
    assert "temperature factor" in scope


def test_parser_keeps_unclassified_score_distinct():
    # A 0-100 spread with a mediocre mean is not confidently pLDDT, and it is not
    # a 0-1 quality score either; it stays unnamed rather than being guessed.
    analysis = parse_pdb(_pdb(b_factor=40.0))
    assert analysis["theoretical_model"]["b_factor_semantics"] == "unclassified_score"
    assert analysis.get("b_factor_scope") is None or "quality" not in analysis["b_factor_scope"]


def _strategy(question, preflight_extra=None):
    preflight = {
        "status": "readable",
        "chains": [{"chain_id": "A", "sequence": SEQ, "residue_count": len(SEQ)}],
        "nonpolymer_components": [],
        "reference_binding": {"verified": False},
        **(preflight_extra or {}),
    }
    return select_structure_strategy(
        question, preflight, object_name="model.pdb", depth="deep",
        tools=set(ToolRegistry._tools),
        runtimes={"foldseek": False, "pocket": False, "esm2": False},
    )


def _identity_step(strategy):
    return next(row for row in strategy["steps"] if row["tool_name"] == "enzyme_identity_profile")


def test_strategy_passes_template_evidence_and_records_numbering_boundary():
    theoretical = parse_pdb(_pdb(SWISS_REMARKS))["theoretical_model"]
    strategy = _strategy("提高比活力", {"theoretical_model": theoretical})
    params = _identity_step(strategy)["params"]
    assert params["template_evidence"]["templates"] == [{"template_id": "3gbx"}]
    assert params["template_evidence"]["provenance"] == "model_header_declared"
    assert any("作者编号" in note for note in strategy["deferred"])


def test_strategy_without_theoretical_model_omits_template_params():
    strategy = _strategy("提高比活力", {"theoretical_model": {"status": "not_theoretical", "is_theoretical": False}})
    assert "template_evidence" not in _identity_step(strategy)["params"]


def _profile(**kwargs):
    ToolRegistry.discover()
    handler = ToolRegistry.get_tool("enzyme_identity_profile").handler
    return handler(sequence=SEQ, structure_id="uploaded_pdb_coordinate_model", **kwargs)


def test_identity_gate_high_identity_qualifies_but_caps_confidence():
    profile = _profile(template_evidence={
        "source": "SWISS-MODEL", "is_theoretical": True,
        "templates": [{"template_id": "3gbx"}],
        "template_sequence_identity": 0.95, "template_coverage": 0.98,
        "gmqe": 0.82, "qmean": -2.1, "qmean_z": -1.35,
    })
    assert profile["identity_basis"] == "template_homology"
    assert profile["identity_status"] == "identified"
    assert profile["confidence_summary"]["family"] <= 0.75
    assert profile["template_evidence"]["status"] == "qualifies"
    assert profile["query"]["template_frame"] == "isolated"
    assert any("template" in row["source"] for row in profile["evidence_table"])
    assert any("theoretical-model template homology" in item for item in profile["missing_evidence"])


def test_identity_gate_low_identity_does_not_call_family():
    profile = _profile(template_evidence={
        "source": "SWISS-MODEL", "is_theoretical": True,
        "templates": [{"template_id": "3gbx"}],
        "template_sequence_identity": 0.55, "template_coverage": 0.9,
    })
    assert profile["identity_status"] == "unresolved"
    assert profile["identity_basis"] == "none"
    assert profile["template_evidence"]["status"] == "below_threshold"
    assert profile["guardrail"]["status"] == "blocked"


def test_identity_gate_low_coverage_blocks_family_call():
    profile = _profile(template_evidence={
        "source": "SWISS-MODEL", "is_theoretical": True,
        "templates": [{"template_id": "3gbx"}],
        "template_sequence_identity": 0.92, "template_coverage": 0.5,
    })
    assert profile["identity_status"] == "unresolved"
    assert profile["template_evidence"]["status"] == "below_threshold"


def test_identity_profile_without_template_has_no_template_frame():
    profile = _profile()
    assert profile["template_evidence"] is None
    assert profile["query"]["template_frame"] is None


def test_unlock_paths_name_structure_source_and_inputs():
    orchestrator = AgentOrchestrator()
    profile = _profile(template_evidence={
        "source": "SWISS-MODEL", "is_theoretical": True,
        "templates": [{"template_id": "3gbx"}],
        "template_sequence_identity": 0.55, "template_coverage": 0.9,
        "gmqe": 0.61, "qmean_z": -2.0,
    })
    paths = orchestrator._build_identity_unlock_paths(profile)
    joined = "；".join(paths)
    assert "3gbx" in joined and "UniProt" in joined and "FASTA" in joined
    ready = dict(profile, identity_status="identified", guardrail={"status": "ready"})
    assert orchestrator._build_identity_unlock_paths(ready) == []


def test_plan_coherence_drops_benchmark_without_identity_gate():
    orchestrator = AgentOrchestrator()
    strategy = {"deferred": []}
    steps = [
        PlanStep(1, "structure_search_foldseek", "parse", {}),
        PlanStep(2, "protein_benchmark", "family", {"query_sequence": SEQ}),
        PlanStep(3, "mutation_priority_score", "rank", {}),
    ]
    kept = orchestrator._enforce_plan_coherence(steps, strategy)
    assert [step.tool_name for step in kept] == ["structure_search_foldseek"]
    assert [step.id for step in kept] == [1]
    assert sum("依赖的" in note for note in strategy["deferred"]) == 2


def test_plan_coherence_keeps_gated_chain():
    orchestrator = AgentOrchestrator()
    strategy = {"deferred": []}
    steps = [
        PlanStep(1, "enzyme_identity_profile", "identity", {}),
        PlanStep(2, "protein_benchmark", "family", {"query_sequence": SEQ}),
    ]
    kept = orchestrator._enforce_plan_coherence(steps, strategy)
    assert [step.tool_name for step in kept] == ["enzyme_identity_profile", "protein_benchmark"]
    assert strategy["deferred"] == []


def test_uploaded_theoretical_model_plan_carries_template_evidence():
    orch = AgentOrchestrator()
    theoretical = parse_pdb(_pdb(SWISS_REMARKS))["theoretical_model"]
    preflight = {
        "status": "readable", "display_name": "model.pdb",
        "chains": [{"chain_id": "A", "sequence": SEQ, "residue_count": len(SEQ)}],
        "nonpolymer_components": [], "reference_binding": {"verified": False},
        "theoretical_model": theoretical,
        "coordinate_sequence": SEQ,
    }

    async def fake_preflight(task):
        return copy.deepcopy(preflight)

    async def fake_experience(*args, **kwargs):
        return ""

    orch._build_pdb_preflight_summary = fake_preflight
    orch._get_experience_hints = fake_experience
    task = '提高比活力\n[Attached files:\nname: model.pdb, object_name: uploads/user_999/model.pdb]'
    rows = asyncio.run(orch._plan_cb(task, "", [], analysis_depth="deep"))
    identity_rows = [step for step in rows if step.tool_name == "enzyme_identity_profile"]
    assert identity_rows, "identity gate must survive uploaded-structure plan rebuild"
    assert identity_rows[0].params.get("template_evidence", {}).get("templates") == [{"template_id": "3gbx"}]
    names = {step.tool_name for step in rows}
    assert "annotation_bundle" not in names
    assert "protein_benchmark" in names, "benchmark depends on identity gate, which is present"
