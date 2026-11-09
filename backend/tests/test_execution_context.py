from app.core.execution_context import ExecutionContext


def test_context_restores_only_completed_tool_results():
    stored = {
        "objective": "specific_activity",
        "workflow_id": "enzyme_specific_activity_runtime_v1",
        "execution_trace": [
            {
                "tool": "mutation_priority_score",
                "status": "completed",
                "result_preview": "score=8.2",
            },
            {
                "tool": "esmfold_folding",
                "status": "blocked",
                "result_preview": "fake",
            },
            {
                "tool": "protein_benchmark",
                "status": "failed",
                "result_preview": "fake too",
            },
        ],
    }

    context = ExecutionContext.from_done_event(stored)

    assert context.objective == "specific_activity"
    assert context.workflow_id == "enzyme_specific_activity_runtime_v1"
    assert context.completed_evidence == [
        {"tool": "mutation_priority_score", "result_preview": "score=8.2"}
    ]


def test_context_parses_json_and_fails_closed_for_invalid_payloads():
    context = ExecutionContext.from_json(
        '{"execution_trace":[{"tool":"annotation_bundle",'
        '"status":"completed","result_preview":"live"}]}'
    )
    invalid = ExecutionContext.from_json("not-json")

    assert context.completed_evidence == [
        {"tool": "annotation_bundle", "result_preview": "live"}
    ]
    assert invalid is None


def test_context_does_not_promote_missing_nested_blocked_or_submitted_results():
    context = ExecutionContext.from_done_event({
        "execution_trace": [
            {"tool": "empty_tool", "status": "completed"},
            {
                "tool": "blocked_tool",
                "status": "completed",
                "raw_result": '{"status": "completed", "result": {"status": "blocked", "reason": "gate"}}',
                "result_preview": "completed wrapper around blocked result",
            },
            {
                "tool": "pending_tool",
                "status": "submitted",
                "raw_result": '{"status": "submitted", "task_id": "task-1"}',
            },
            {
                "tool": "empty_payload_tool",
                "status": "completed",
                "raw_result": '{"status": "completed", "result": {}}',
            },
            {
                "tool": "usable_tool",
                "status": "completed",
                "result_preview": "score=8.2",
            },
        ],
    })

    assert context.completed_evidence == [
        {"tool": "usable_tool", "result_preview": "score=8.2"}
    ]


def test_context_does_not_promote_nested_result_preview_metadata():
    context = ExecutionContext.from_done_event({
        "execution_trace": [{
            "tool": "preview_only",
            "status": "completed",
            "raw_result": '{"status": "completed", "result_preview": "score=8.2"}',
            "result_preview": "score=8.2",
        }],
    })

    assert context.completed_evidence == []


def test_context_limits_evidence_exposed_to_prompts():
    stored = {
        "execution_trace": [
            {
                "tool": f"tool_{index}",
                "status": "completed",
                "result_preview": "x" * 1200,
            }
            for index in range(25)
        ]
    }

    context = ExecutionContext.from_done_event(stored)

    assert len(context.completed_evidence) == 20
    assert context.completed_evidence[0]["tool"] == "tool_5"
    assert all(len(row["result_preview"]) == 1000 for row in context.completed_evidence)
    assert "tool_24" in context.as_prompt_text()
