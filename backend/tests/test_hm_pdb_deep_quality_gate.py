"""HM.pdb-style PDB-only deep analysis release gate.

This gate keeps the most complaint-prone scenario visible in acceptance output:
uploaded structure only, weak structure similarity, inferred coordinate-order
mapping, activity + thermostability objective, and blocked candidate output.
"""

from __future__ import annotations

import json
from pathlib import Path


def _hm_case() -> dict:
    cases = json.loads((Path(__file__).with_name("enzyme_report_quality_cases.json")).read_text())
    return next(case for case in cases if case["id"] == "pdb_only_identity_blocked_outputs_no_candidate_table")


def test_hm_pdb_only_deep_report_blocks_candidates_and_surfaces_boundaries():
    from app.core.agent_graph import AgentOrchestrator
    from app.services.report_quality_contract import validate_report_quality_contract

    case = _hm_case()
    tool_results = list(case["tool_results"])
    tool_results[0]["result"] = {
        **tool_results[0]["result"],
        "capability_status": "structure_similarity_search",
        "report_boundary": (
            "Foldseek/结构解析只能作为结构相似性和输入质控证据；弱 TM-score、模板 RCSB 注释或结构摘要"
            "不能单独确认 HM/input 的酶身份、催化残基、底物口袋或 UniProt 编号。"
        ),
    }
    tool_results[1]["result"] = {
        **tool_results[1]["result"],
        "capability_status": "coordinate_order_inference",
        "report_boundary": (
            "这是按 PDB 坐标残基顺序生成的 SIFTS-style 推断，不是外部 SIFTS/UniProt 实证映射；"
            "不能把 coordinate position 直接写成成熟蛋白或 UniProt 编号。"
        ),
    }
    tool_results.append(
        {
            "tool_name": "predict_properties",
            "status": "completed",
            "result": {
                "length": 299,
                "molecular_weight_kda": 32.73,
                "isoelectric_point": 5.27,
                "capability_status": "physicochemical_baseline",
                "report_boundary": (
                    "理化性质是由输入序列计算得到的背景基线；不能单独证明热稳定性、比活力、酶身份或突变增益。"
                ),
            },
        }
    )

    report = AgentOrchestrator()._build_fallback_report(case["task"], tool_results)
    carried_required = [
        item
        for item in case["required"]
        if item not in {
            "主要证据**：上传结构已解析（299 aa）；编号映射=local_sifts_style_inference；kcat 为启发式背景",
            "支撑结构/编号边界；不能单独确认酶身份",
        }
    ]
    violations = validate_report_quality_contract(
        report,
        required=[
            *carried_required,
            "主要证据**：上传结构已解析（299 aa）；编号映射=local_sifts_style_inference；理化性质基线（299 aa）；kcat 为启发式背景",
            "structure_similarity_search；Foldseek/结构解析只能作为结构相似性和输入质控证据",
            "coordinate_order_inference；这是按 PDB 坐标残基顺序生成的 SIFTS-style 推断",
            "physicochemical_baseline；理化性质是由输入序列计算得到的背景基线",
            "不能把 coordinate position 直接写成成熟蛋白或 UniProt 编号",
        ],
        forbidden=[
            *case["forbidden"],
            "α-淀粉酶已确认",
            "UniProt:P06278 cov=1.0",
            "NEVER MUTATE positions: [13, 40, 191]",
        ],
        ordered_headings=case["ordered_headings"],
    )

    assert not violations, f"HM.pdb deep quality gate violations: {violations}"
    assert "0 个可排单候选" in report
    assert "K288E" not in report
    assert "E275Q" not in report


def test_pdb_only_sop_documents_hm_release_gate_boundaries():
    project_root = Path(__file__).resolve().parents[2]
    sop = project_root / "docs" / "manuals" / "pdb-only-enzyme-analysis-sop.md"
    manual = project_root / "docs" / "manuals" / "productization-acceptance-manual.md"

    content = sop.read_text(encoding="utf-8")
    assert "PDB-only 输入不能直接输出可排单候选突变" in content
    assert "hm_pdb_deep_quality_gate" in content
    assert "弱 Foldseek 不确认身份" in content
    assert "坐标顺序推断不冒充真实 SIFTS/UniProt" in content
    assert "submitted BLAST 不进入完成证据" in content
    assert "启发式 kcat 不支持比活力结论" in content
    assert "experiment_ready_mutation" in content
    assert "coordinate_order_inference" in content
    assert "pdb-only-enzyme-analysis-sop.md" in manual.read_text(encoding="utf-8")
