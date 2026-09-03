import pytest

from app.services import tool_task_store


@pytest.mark.asyncio
async def test_tool_task_owner_round_trip():
    await tool_task_store.record_tool_task_owner("task-owner-1", "42", "gromacs_md")

    owner = await tool_task_store.get_tool_task_owner("task-owner-1")

    assert owner is not None
    assert owner["user_id"] == 42
    assert owner["tool"] == "gromacs_md"
    assert owner["submitted_at"]


@pytest.mark.asyncio
async def test_tool_task_owner_missing_returns_none():
    owner = await tool_task_store.get_tool_task_owner("missing-task-owner")

    assert owner is None


async def test_tool_task_cancel_request_is_persisted():
    await tool_task_store.record_tool_task_owner("task-cancel-1", 42, "gromacs_md")

    owner = await tool_task_store.record_tool_task_cancel_requested("task-cancel-1", 42)

    assert owner is not None
    assert owner["cancel_requested"] is True
    assert owner["cancel_requested_by"] == 42
    assert owner["cancel_requested_at"]


async def test_tool_task_cancel_request_missing_returns_none():
    owner = await tool_task_store.record_tool_task_cancel_requested("missing-cancel-task", 42)

    assert owner is None


async def test_tool_task_runtime_policy_is_persisted():
    await tool_task_store.record_tool_task_owner("task-runtime-1", 42, "gromacs_md")

    owner = await tool_task_store.record_tool_task_runtime_policy(
        "task-runtime-1",
        queue="md_cpu",
        soft_time_limit=3600,
        time_limit=5400,
    )

    assert owner is not None
    assert owner["queue"] == "md_cpu"
    assert owner["soft_time_limit"] == 3600
    assert owner["time_limit"] == 5400


async def test_tool_task_terminal_state_is_persisted():
    await tool_task_store.record_tool_task_owner("task-terminal-1", 42, "gromacs_md")
    await tool_task_store.record_tool_task_cancel_requested("task-terminal-1", 42)

    owner = await tool_task_store.record_tool_task_terminal_state("task-terminal-1", "canceled")

    assert owner is not None
    assert owner["terminal_status"] == "canceled"
    assert owner["terminal_recorded_at"]
    assert owner["cancel_effective_at"]


async def test_tool_artifact_owner_round_trip():
    await tool_task_store.record_tool_artifact_owner(
        "md/job-1/rmsd.xvg",
        42,
        tool_name="gromacs_md",
        task_id="task-artifact-1",
    )

    owner = await tool_task_store.get_tool_artifact_owner("md/job-1/rmsd.xvg")

    assert owner is not None
    assert owner["user_id"] == 42
    assert owner["tool"] == "gromacs_md"
    assert owner["task_id"] == "task-artifact-1"
    assert owner["recorded_at"]


async def test_tool_artifact_owner_missing_returns_none():
    owner = await tool_task_store.get_tool_artifact_owner("md/missing/none.xvg")

    assert owner is None
