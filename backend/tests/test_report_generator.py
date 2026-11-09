import json

from app.services.report_generator import ReportGenerator


def _generate(tool_results, *, final_report="# 酶蛋白工程分析报告\n\n## 任务理解\n\n阶段报告", task_contract=None):
    return ReportGenerator().generate_conversation_report(
        project_name="test",
        conversation_title="enzyme report",
        user_message="提高比活力",
        research_notes="",
        plan=[],
        tool_results=tool_results,
        final_report=final_report,
        task_contract=task_contract,
    )


def test_wiki_export_uses_nested_terminal_status_for_completed_scheduler_wrapper():
    report = _generate([{
        "tool_name": "enzyme_objective_module_plan",
        "status": "completed",
        "result": json.dumps({
            "status": "completed",
            "result": {"status": "blocked", "reason": "assay baseline missing"},
        }),
    }])

    assert "### enzyme_objective_module_plan (blocked)" in report
    assert "### enzyme_objective_module_plan (completed)" not in report


def test_wiki_export_keeps_submitted_as_a_receipt():
    report = _generate([{
        "tool_name": "blast_search",
        "status": "completed",
        "result": json.dumps({"status": "submitted", "task_id": "qa-1"}),
    }])

    assert "### blast_search (submitted)" in report
    assert "### blast_search (completed)" not in report


def test_wiki_export_does_not_mark_completed_scheduler_record_without_result_as_completed():
    report = _generate([{
        "tool_name": "enzyme_identity_profile",
        "status": "completed",
        "result": None,
    }])

    assert "### enzyme_identity_profile (failed)" in report
    assert "### enzyme_identity_profile (completed)" not in report


def test_wiki_export_does_not_treat_nested_result_preview_as_scientific_payload():
    report = _generate([{
        "tool_name": "enzyme_identity_profile",
        "status": "completed",
        "result": '{"status": "completed", "result_preview": "identified"}',
    }])

    assert "### enzyme_identity_profile (failed)" in report
    assert "### enzyme_identity_profile (completed)" not in report


def test_wiki_export_labels_blocked_structured_report_as_needs_review():
    report = _generate([{
        "tool_name": "enzyme_objective_module_plan",
        "status": "blocked",
        "result": '{"status": "blocked", "candidate_output_allowed": false}',
    }])

    assert 'report_status: "NEEDS_REVIEW"' in report
    assert "## 报告交付状态" in report
    assert "- 状态：NEEDS_REVIEW" in report
    assert "阶段报告复核" in report


def test_wiki_export_marks_missing_gate_trace_as_not_recorded():
    report = _generate([])

    assert 'execution_gate_status: "NOT_RECORDED"' in report
    assert 'execution_gate_status: "NO_BLOCKED_GATE_RECORDED"' not in report


def test_wiki_export_does_not_erase_upstream_review_when_report_body_is_complete():
    ready_report = """# 酶蛋白工程分析报告

## 任务理解
- 证据：完整。
- 候选位点：E123Q。
- 优先级：Tier 1。
- 风险：需实验复核。
- 实验动作：比较 WT 与变体。

## Objective Module Gate
- 状态：ready
- 是否允许输出候选表：True
"""
    report = _generate(
        [],
        final_report=ready_report,
        task_contract={"final_status": "NEEDS_REVIEW"},
    )

    assert 'report_status: "NEEDS_REVIEW"' in report
    assert 'report_quality_status: "READY"' in report
    assert 'workflow_status: "NEEDS_REVIEW"' in report


def test_wiki_export_checks_critical_gate_trace_when_older_report_omits_it():
    ready_report = """# 酶蛋白工程分析报告

## 任务理解
- 证据：完整。
- 候选位点：E123Q。
- 优先级：Tier 1。
- 风险：需实验复核。
- 实验动作：比较 WT 与变体。

## Objective Module Gate
- 状态：ready
- 是否允许输出候选表：True
"""
    report = _generate([{
        "tool_name": "enzyme_objective_module_plan",
        "status": "completed",
        "result": '{"status": "blocked", "candidate_output_allowed": false}',
    }], final_report=ready_report)

    assert 'report_status: "NEEDS_REVIEW"' in report
    assert 'execution_gate_status: "NEEDS_REVIEW"' in report


def test_wiki_export_requires_explicit_identity_guardrail():
    report = _generate([{
        "tool_name": "enzyme_identity_profile",
        "status": "completed",
        "result": '{"identity_status": "identified"}',
    }])

    assert 'execution_gate_status: "NEEDS_REVIEW"' in report
    assert 'report_status: "NEEDS_REVIEW"' in report


def test_wiki_export_requires_every_critical_gate_not_only_one_successful_gate():
    report = _generate([{
        "tool_name": "enzyme_identity_profile",
        "status": "completed",
        "result": json.dumps({
            "identity_status": "identified",
            "guardrail": {"status": "ready"},
            "protected_positions": [54],
        }),
    }])

    assert 'execution_gate_status: "NEEDS_REVIEW"' in report
    assert 'report_status: "NEEDS_REVIEW"' in report


def test_wiki_export_does_not_unlock_from_mutation_score_preview_only():
    report = _generate([{
        "tool_name": "mutation_priority_score",
        "status": "completed",
        "result_preview": "score=8.2",
    }])

    assert 'execution_gate_status: "NEEDS_REVIEW"' in report
    assert 'report_status: "NEEDS_REVIEW"' in report


def test_wiki_export_uses_latest_gate_attempt_after_rerun():
    report = _generate([
        {
            "tool_name": "enzyme_identity_profile",
            "status": "blocked",
            "result": '{"status": "blocked", "guardrail": {"status": "blocked"}}',
        },
        {
            "tool_name": "enzyme_identity_profile",
            "status": "completed",
            "result": '{"status": "identified_family", "identity_status": "identified", "guardrail": {"status": "ready"}, "protected_positions": [42]}',
        },
        {
            "tool_name": "enzyme_objective_module_plan",
            "status": "completed",
            "result": '{"status": "ready", "candidate_output_allowed": true}',
        },
        {
            "tool_name": "residue_numbering_gate",
            "status": "completed",
            "result": '{"status": "ready"}',
        },
        {
            "tool_name": "mutation_priority_score",
            "status": "completed",
            "result": '{"tier_1_candidates": []}',
        },
    ])

    assert 'execution_gate_status: "NEEDS_REVIEW"' in report


def test_wiki_export_still_recognizes_structured_report_after_long_gate_notices():
    final_report = (
        "### 目标门控提示\n\n- mutation_priority_score 按门控阻止执行："
        + ("assay context missing; " * 80)
        + "\n\n# 酶蛋白工程分析报告\n\n## 任务理解\n\n阶段报告\n"
    )

    report = _generate([], final_report=final_report)

    assert "## 报告交付状态" in report
    assert 'report_status: "NEEDS_REVIEW"' in report


def test_wiki_pipeline_icons_distinguish_pending_blocked_failed_and_completed():
    report = ReportGenerator().generate_conversation_report(
        project_name="test",
        conversation_title="enzyme report",
        user_message="分析蛋白",
        research_notes="",
        plan=[
            {"tool_name": "queued_tool", "status": "submitted"},
            {"tool_name": "gated_tool", "status": "blocked"},
            {"tool_name": "broken_tool", "status": "failed"},
            {"tool_name": "ready_tool", "status": "completed"},
        ],
        tool_results=[],
        final_report="# ordinary report",
    )

    assert "1. ⏳ **queued_tool**" in report
    assert "2. ⚠️ **gated_tool**" in report
    assert "3. ❌ **broken_tool**" in report
    assert "4. ✅ **ready_tool**" in report
