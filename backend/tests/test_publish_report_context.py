import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock

from app.api import publish as publish_api
from app.api.publish import GenerateReportRequest, _extract_report_source


def test_report_source_uses_latest_user_turn_and_its_execution_trace():
    old_execution = {"execution_trace": [{
        "tool": "old_tool",
        "status": "completed",
        "raw_result": '{"value": "old"}',
    }]}
    current_execution = {
        "type": "done",
        "task_contract": {"final_status": "NEEDS_REVIEW", "report_quality_status": "READY"},
        "execution_trace": [
            {
                "tool": "enzyme_objective_module_plan",
                "status": "blocked",
                "result_preview": '{"status": "blocked", "reason": "missing WT baseline"}',
                "reason": "missing WT baseline",
            },
            {
                "tool": "blast_search",
                "status": "submitted",
                "result_preview": '{"status": "submitted", "task_id": "task-2"}',
            },
            {
                "tool": "mutation_scan",
                "status": "completed",
                "raw_result": '{"status": "completed", "result": {}}',
            },
        ],
    }
    messages = [
        SimpleNamespace(role="user", content="分析旧蛋白", tool_calls=None),
        SimpleNamespace(
            role="assistant", content="旧报告", tool_calls=json.dumps(old_execution),
            tool_call_records=[],
        ),
        SimpleNamespace(role="user", content="继续分析这条新序列", tool_calls=None),
        SimpleNamespace(
            role="assistant", content="当前报告", tool_calls=json.dumps(current_execution),
            tool_call_records=[],
        ),
    ]

    user_message, final_report, plan, tool_results, task_contract = _extract_report_source(messages)

    assert user_message == "继续分析这条新序列"
    assert final_report == "当前报告"
    assert [item["tool_name"] for item in plan] == [
        "enzyme_objective_module_plan", "blast_search", "mutation_scan",
    ]
    assert [item["status"] for item in plan] == ["blocked", "submitted", "failed"]
    assert [item["status"] for item in tool_results] == ["blocked", "submitted", "failed"]
    assert task_contract["final_status"] == "NEEDS_REVIEW"


def test_report_source_keeps_missing_assistant_output_unknown():
    messages = [
        SimpleNamespace(role="user", content="分析蛋白", tool_calls=None),
        SimpleNamespace(
            role="assistant", content="报告", tool_calls=json.dumps({
                "execution_trace": [{"tool": "enzyme_identity_profile", "status": "completed"}],
            }), tool_call_records=[],
        ),
    ]

    _, _, plan, tool_results, _ = _extract_report_source(messages)

    assert plan[0]["status"] == "failed"
    assert tool_results[0]["status"] == "failed"


def test_report_source_supports_legacy_tool_call_lists_without_inventing_success():
    messages = [
        SimpleNamespace(role="user", content="分析蛋白", tool_calls=None),
        SimpleNamespace(
            role="assistant", content="报告", tool_calls=json.dumps([
                {"function": {"name": "enzyme_identity_profile"}},
            ]), tool_call_records=[],
        ),
    ]

    _, _, plan, _, _ = _extract_report_source(messages)

    assert len(plan) == 1
    assert plan[0]["tool_name"] == "enzyme_identity_profile"
    assert plan[0]["status"] == "unknown"


def test_report_source_uses_message_id_to_break_same_timestamp_ties():
    timestamp = datetime(2026, 10, 13, 10, 0, 0)
    messages = [
        SimpleNamespace(id=4, created_at=timestamp, role="assistant", content="最新报告", tool_calls=None),
        SimpleNamespace(id=3, created_at=timestamp, role="user", content="最新任务", tool_calls=None),
        SimpleNamespace(id=2, created_at=timestamp, role="assistant", content="旧报告", tool_calls=None),
        SimpleNamespace(id=1, created_at=timestamp, role="user", content="旧任务", tool_calls=None),
    ]

    user_message, final_report, _, _, _ = _extract_report_source(messages)

    assert user_message == "最新任务"
    assert final_report == "最新报告"


def test_report_source_falls_back_to_normalized_tool_records():
    messages = [
        SimpleNamespace(role="user", content="分析蛋白", tool_calls=None),
        SimpleNamespace(
            role="assistant",
            content="阶段报告",
            tool_calls=json.dumps({"execution_trace": []}),
            tool_call_records=[
                SimpleNamespace(
                    id=2,
                    tool_name="blast_search",
                    status="submitted",
                    result='{"result_preview": "task-2"}',
                    error=None,
                    duration_ms=10,
                ),
                SimpleNamespace(
                    id=1,
                    tool_name="enzyme_objective_module_plan",
                    status="blocked",
                    result=None,
                    error="assay baseline missing",
                    duration_ms=2,
                ),
            ],
        ),
    ]

    _, _, plan, _, _ = _extract_report_source(messages)

    assert [item["tool_name"] for item in plan] == [
        "enzyme_objective_module_plan", "blast_search",
    ]
    assert [item["status"] for item in plan] == ["blocked", "submitted"]


def test_done_envelope_is_authoritative_over_stale_tool_records_and_merges_metadata():
    """A newer empty done trace must not resurrect an older normalized call."""
    execution = {
        "type": "done",
        "status": "blocked",
        "blocked_reason": "等待补充 WT 基线",
        "objective": "thermostability",
        "workflow_id": "WF-STABILITY",
        "missing_capabilities": ["baseline_tm"],
        "task_contract": {"final_status": "NEEDS_REVIEW"},
        "execution_trace": [],
    }
    messages = [
        SimpleNamespace(role="user", content="继续这个蛋白", tool_calls=None),
        SimpleNamespace(
            role="assistant",
            content="当前报告",
            tool_calls=json.dumps(execution),
            tool_call_records=[
                SimpleNamespace(
                    id=99,
                    tool_name="old_tool",
                    status="completed",
                    result='{"result_preview":"stale"}',
                    error=None,
                    duration_ms=1,
                ),
            ],
        ),
    ]

    _, _, plan, tool_results, task_contract = _extract_report_source(messages)

    assert plan == []
    assert tool_results == []
    assert task_contract["final_status"] == "NEEDS_REVIEW"
    assert task_contract["stream_status"] == "BLOCKED"
    assert task_contract["blocked_reason"] == "等待补充 WT 基线"
    assert task_contract["objective"] == "thermostability"
    assert task_contract["workflow_id"] == "WF-STABILITY"
    assert task_contract["missing_capabilities"] == ["baseline_tm"]
    assert task_contract["terminal_source"] == "done_event"


def test_legacy_execution_list_still_uses_normalized_records_when_trace_is_absent():
    """Pre-done records remain readable for genuinely legacy conversations."""
    messages = [
        SimpleNamespace(role="user", content="分析蛋白", tool_calls=None),
        SimpleNamespace(
            role="assistant",
            content="旧报告",
            tool_calls=json.dumps({"task_contract": {"final_status": "READY"}}),
            tool_call_records=[
                SimpleNamespace(
                    id=1,
                    tool_name="legacy_tool",
                    status="completed",
                    result='{"result_preview":"legacy"}',
                    error=None,
                    duration_ms=1,
                ),
            ],
        ),
    ]

    _, _, plan, tool_results, task_contract = _extract_report_source(messages)

    assert [item["tool_name"] for item in plan] == ["legacy_tool"]
    assert [item["status"] for item in tool_results] == ["completed"]
    assert task_contract["final_status"] == "READY"


@pytest.mark.asyncio
async def test_generate_report_does_not_load_other_users_or_projects_conversation(monkeypatch):
    monkeypatch.setattr(
        publish_api,
        "_require_project_access",
        AsyncMock(return_value=(SimpleNamespace(name="project"), "editor")),
    )
    result = SimpleNamespace(scalar_one_or_none=lambda: None)
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(HTTPException) as exc:
        await publish_api.generate_report(
            "project-id",
            GenerateReportRequest(conversation_id=77),
            session=session,
            user={"id": 12},
        )

    assert exc.value.status_code == 404
    query = str(session.execute.await_args.args[0])
    assert "conversations.project_id" in query
    assert "conversations.user_id" in query
    assert "conversations.id" in query


@pytest.mark.asyncio
async def test_generate_report_passes_latest_turn_and_real_statuses_to_renderer(monkeypatch):
    execution = {
        "type": "done",
        "task_contract": {"final_status": "NEEDS_REVIEW"},
        "execution_trace": [
            {
                "tool": "enzyme_objective_module_plan",
                "status": "blocked",
                "raw_result": '{"status": "blocked", "reason": "baseline missing"}',
            },
            {
                "tool": "blast_search",
                "status": "submitted",
                "raw_result": '{"status": "submitted", "task_id": "task-7"}',
            },
        ],
    }
    conversation = SimpleNamespace(
        id=77,
        title="enzyme report",
        messages=[
            SimpleNamespace(role="user", content="旧任务", tool_calls=None),
            SimpleNamespace(role="assistant", content="旧报告", tool_calls=None, tool_call_records=[]),
            SimpleNamespace(role="user", content="继续这个蛋白", tool_calls=None),
            SimpleNamespace(
                role="assistant", content="当前报告", tool_calls=json.dumps(execution),
                tool_call_records=[],
            ),
        ],
    )
    result = SimpleNamespace(scalar_one_or_none=lambda: conversation)
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    captured = {}
    monkeypatch.setattr(
        publish_api,
        "_require_project_access",
        AsyncMock(return_value=(SimpleNamespace(name="project"), "editor")),
    )

    def render(**kwargs):
        captured.update(kwargs)
        return "preview markdown"

    monkeypatch.setattr(publish_api._generator, "generate_conversation_report", render)
    response = await publish_api.generate_report(
        "project-id",
        GenerateReportRequest(conversation_id=77),
        session=session,
        user={"id": 12},
    )

    assert response["content"] == "preview markdown"
    assert captured["user_message"] == "继续这个蛋白"
    assert captured["final_report"] == "当前报告"
    assert [item["status"] for item in captured["plan"]] == ["blocked", "submitted"]
    assert [item["status"] for item in captured["tool_results"]] == ["blocked", "submitted"]
    assert captured["task_contract"]["final_status"] == "NEEDS_REVIEW"
