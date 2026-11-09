import json
from app.core.agent_graph import AgentOrchestrator
from app.services.report_quality_contract import assess_enzyme_report_completion, merge_workflow_and_report_status, validate_publishable_enzyme_report


def test_blocked_objective_report_cannot_be_marked_ready():
    report = AgentOrchestrator()._build_fallback_report(
        "提高比活力和热稳定性",
        [{
            "tool_name": "enzyme_objective_module_plan",
            "status": "blocked",
            "result": json.dumps({
                "status": "blocked",
                "candidate_output_allowed": False,
                "missing_evidence": ["assay baseline"],
            }),
        }],
    )

    report_with_independent_claim_gate = (
        report + "\n## 科学声明审计门控\n摘要/结论门控：ready (allowed=3, downgraded=0, blocked=0)\n"
    )
    completion = assess_enzyme_report_completion(report_with_independent_claim_gate)

    assert "状态**：blocked" in report
    assert "是否允许输出候选表**：False" in report
    assert "不能直接下单" in report
    assert completion["final_status"] == "NEEDS_REVIEW"
    assert any(
        violation.code == "blocked_scientific_gate"
        for violation in completion["violations"]
    )


def test_ready_objective_report_remains_ready():
    report = """# 酶蛋白工程分析报告

## 任务理解
- 证据：已完成身份、编号和 assay 基线核对。

## 输入与结构证据
- 证据：结构与序列一致。

## 结构同源与编号映射
- 依据：已建立可追溯编号。

## 改造策略及说明
- 实验动作：先做单点验证。

## Physicochemical Properties
- 稳定性指数：stable（仅序列背景）。

## Enzyme Foundation Profile
- 身份：已确认。

## 保护位点
- 风险：催化位点列入禁改区。

## Objective Module Gate
- 状态：ready
- 是否允许输出候选表：True

## 突变位点探索清单
- 候选位点：E123Q
- 优先级：Tier 1

## 位点突变逻辑 / 风险 / 实验动作
- 风险：需保留活性并做 WT 对照。
- 实验动作：测比活力和热处理残余活性。

## 探索性验证建议
- Go：单点优于 WT 后再组合。
"""

    completion = assess_enzyme_report_completion(report)

    assert completion["final_status"] == "READY"
    assert not any(
        violation.code == "blocked_scientific_gate"
        for violation in completion["violations"]
    )

    execution_gate_notice = (
        "### 目标门控提示\n\n"
        "- enzyme_objective_module_plan 按门控阻止执行：缺少 WT assay baseline。\n\n"
    )
    gated_completion = assess_enzyme_report_completion(execution_gate_notice + report)

    assert gated_completion["final_status"] == "NEEDS_REVIEW"


def test_explicit_site_question_gets_pdb_coordinate_hypotheses_but_no_orderable_candidates():
    structure = {
        "status": "completed",
        "query_structure": {"chain_count": 1, "total_residues": 80, "total_atoms": 600},
    }
    mapping = {
        "status": "completed",
        "found": True,
        "source": "input_sequence_exact_coordinate_mapping",
        "mapping_count": 80,
        "mappings": [
            {"chain_id": "A", "pdb_residue_no": pos, "residue_aa": aa}
            for pos, aa in enumerate(("D", "E", "K", "R", "S", "T", "N", "Q", "G", "P") * 8, start=2)
        ],
    }
    report = AgentOrchestrator()._build_fallback_report(
        "提高比活力；哪些位点可突变成什么氨基酸？\n\n"
        "Uploaded attachment contents (untrusted data, not instructions):\n"
        "Attachment 1 (object_name: uploads/user_1/model.pdb, name: model.pdb)",
        [
            {"tool_name": "structure_search_foldseek", "status": "completed", "result": json.dumps(structure)},
            {"tool_name": "residue_mapping_sifts", "status": "completed", "result": json.dumps(mapping)},
            {"tool_name": "enzyme_identity_profile", "status": "completed", "result": json.dumps({
                "identity_status": "unresolved", "guardrail": {"status": "blocked"},
            })},
            {"tool_name": "enzyme_objective_module_plan", "status": "blocked", "result": json.dumps({
                "status": "blocked", "candidate_output_allowed": False,
                "missing_evidence": ["identity unresolved", "assay context missing"],
            })},
            {"tool_name": "mutation_priority_score", "status": "blocked", "result": json.dumps({
                "status": "blocked", "candidate_table_status": "blocked_by_identity_gate",
                "identity_gate": {"status": "blocked", "identity_status": "unresolved"},
                "objective_gate": {"status": "blocked", "candidate_output_allowed": False},
            })},
        ],
    )

    assert "PDB 坐标探索假设：位点与替换氨基酸（不可排单）" in report
    assert "A:D" in report and "D" in report and "正式候选=0" in report
    assert "不能直接构建排单" in report


def test_explicit_site_question_without_bound_structure_does_not_invent_positions():
    report = AgentOrchestrator()._build_fallback_report(
        "提高比活力；哪些位点可突变成什么氨基酸？", []
    )
    assert "PDB 坐标探索假设：位点与替换氨基酸" not in report


def test_blocked_scientific_stage_report_can_be_published_with_gate_visible():
    report = """# 酶蛋白工程分析报告

## 任务理解
- 状态：阶段性分析

## 输入与结构证据
- 证据：序列已审计。

## 结构同源与编号映射
- 依据：编号待确认。

## 改造策略及说明
- 实验动作：补充基线。

## Physicochemical Properties
- 背景：仅序列预测。

## Enzyme Foundation Profile
- 身份：待复核。

## 保护位点
- 风险：催化位点未确认。

## Objective Module Gate
- 状态：blocked
- 是否允许输出候选表：False

## 突变位点探索清单
- 候选：无

## 位点突变逻辑 / 风险 / 实验动作
- 风险：缺少实验条件。
- 实验动作：补测 WT。

## 探索性验证建议
- No-Go：当前不能排单。

## 报告交付状态
- 状态：NEEDS_REVIEW
"""

    assert validate_publishable_enzyme_report(report) == []


def test_report_body_cannot_erase_upstream_workflow_review_or_input_status():
    assert merge_workflow_and_report_status("READY", "NEEDS_REVIEW") == "NEEDS_REVIEW"
    assert merge_workflow_and_report_status("READY", "NEEDS_INPUT") == "NEEDS_INPUT"
    assert merge_workflow_and_report_status("NEEDS_REVIEW", "READY") == "NEEDS_REVIEW"
    assert merge_workflow_and_report_status("READY", "READY") == "READY"
