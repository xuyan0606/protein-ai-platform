"""Tests for the enzyme report quality contract helpers."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_validate_report_quality_contract_reports_all_violation_types():
    from app.services.report_quality_contract import validate_report_quality_contract

    report = "\n".join([
        "## 任务理解",
        "## 探索性验证建议",
        "## Objective Module Gate",
        "## 结论卡片 / 状态摘要",
    ])

    violations = validate_report_quality_contract(
        report,
        required=["必须出现的证据边界"],
        forbidden=["不应出现的短语"],
        ordered_headings=[
            "## 任务理解",
            "## Objective Module Gate",
            "## 探索性验证建议",
        ],
    )

    codes = {item.code for item in violations}
    assert "missing_required_text" in codes
    assert "forbidden_text_present" in codes
    assert "heading_order_broken" in codes


def test_validate_report_quality_contract_allows_explicit_opt_out_of_default_forbidden():
    from app.services.report_quality_contract import validate_report_quality_contract

    report = "## 结论卡片 / 状态摘要\n"

    assert validate_report_quality_contract(report)
    assert not validate_report_quality_contract(report, include_default_forbidden=False)


def test_validate_publishable_enzyme_report_applies_only_to_structured_enzyme_reports():
    from app.services.report_quality_contract import validate_publishable_enzyme_report

    generic_report = "# 普通文献摘要\n\n## 用户提问\n\n检索文献"
    assert validate_publishable_enzyme_report(generic_report) == []

    incomplete_enzyme_report = "\n".join([
        "# 酶蛋白工程分析报告",
        "",
        "## 任务理解",
        "- 用户目标：提高比活力",
        "",
        "## Objective Module Gate",
        "- 状态：blocked",
    ])
    violations = validate_publishable_enzyme_report(incomplete_enzyme_report)
    messages = [item.message for item in violations]

    assert any("missing ordered heading: ## 输入与结构证据" in msg for msg in messages)
    assert any("missing ordered heading: ## 探索性验证建议" in msg for msg in messages)


def test_validate_publishable_enzyme_report_accepts_fixed_core_order():
    from app.services.report_quality_contract import (
        CORE_SECTION_ORDER,
        validate_publishable_enzyme_report,
    )

    report = "# 酶蛋白工程分析报告\n\n" + "\n\n".join(
        f"{heading}\n- 占位说明。" for heading in CORE_SECTION_ORDER
    )

    assert validate_publishable_enzyme_report(report) == []


def test_assess_enzyme_report_completion_blocks_empty_delivery_fields():
    from app.services.report_quality_contract import assess_enzyme_report_completion

    result = assess_enzyme_report_completion(
        "# 酶蛋白工程分析报告\n\n## 任务理解\n- 提高稳定性\n\n## Objective Module Gate\n- blocked"
    )

    assert result["final_status"] == "NEEDS_REVIEW"
    codes = {item.code for item in result["violations"]}
    assert "missing_completion_evidence" in codes
    assert "missing_completion_candidate_sites" in codes
    assert "missing_completion_priority" in codes
    assert "missing_completion_risk" in codes
    assert "missing_completion_experimental_action" in codes


def test_assess_enzyme_report_completion_accepts_actionable_report():
    from app.services.report_quality_contract import assess_enzyme_report_completion

    report = "\n".join([
        "# 酶蛋白工程分析报告",
        "## 输入与结构证据\n- 依据：序列级证据",
        "## 突变位点探索清单\n- 候选位点：S42",
        "## 位点突变逻辑 / 风险 / 实验动作",
        "- 优先级：Tier 1；风险：需实验验证；实验动作：测定活性与热稳定性",
    ])

    assert assess_enzyme_report_completion(report)["final_status"] == "READY"


def test_assess_enzyme_report_completion_rejects_explicitly_empty_delivery_fields():
    from app.services.report_quality_contract import assess_enzyme_report_completion

    report = "\n".join([
        "# 酶蛋白工程分析报告",
        "## 输入与结构证据\n- 依据：无",
        "## 突变位点探索清单\n- 候选位点：无",
        "## 位点突变逻辑 / 风险 / 实验动作\n- 优先级：无；风险：未评估；实验动作：无",
    ])

    result = assess_enzyme_report_completion(report)
    assert result["final_status"] == "NEEDS_REVIEW"
    assert {item.code for item in result["violations"]} >= {
        "empty_completion_evidence",
        "empty_completion_candidate_sites",
        "empty_completion_priority",
        "empty_completion_experimental_action",
    }
