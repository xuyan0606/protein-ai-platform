from celery.result import AsyncResult
def test_dispatch_tool_uses_profile_queue_and_time_limits(monkeypatch):
    from app.services import scheduler

    captured = {}

    class FakeAsyncResult:
        id = "queued-task-1"

    def fake_apply_async(*, args, queue, soft_time_limit, time_limit):
        captured["args"] = args
        captured["queue"] = queue
        captured["soft_time_limit"] = soft_time_limit
        captured["time_limit"] = time_limit
        return FakeAsyncResult()

    monkeypatch.setattr(scheduler.run_tool_task, "apply_async", fake_apply_async)

    task_id = scheduler.dispatch_tool("gromacs_md", {"pdb_object_name": "uploads/demo.pdb"})

    assert task_id == "queued-task-1"
    assert captured["args"] == ["gromacs_md", {"pdb_object_name": "uploads/demo.pdb"}]
    assert captured["queue"] == "md_cpu"
    assert captured["soft_time_limit"] == 3600
    assert captured["time_limit"] == 5400


def test_blast_search_is_async_on_default_queue_with_polling_budget(monkeypatch):
    from app.services import scheduler

    captured = {}

    class FakeAsyncResult:
        id = "queued-blast-task-1"

    def fake_apply_async(*, args, queue, soft_time_limit, time_limit):
        captured["args"] = args
        captured["queue"] = queue
        captured["soft_time_limit"] = soft_time_limit
        captured["time_limit"] = time_limit
        return FakeAsyncResult()

    monkeypatch.setattr(scheduler.run_tool_task, "apply_async", fake_apply_async)

    task_id = scheduler.dispatch_tool("blast_search", {"sequence": "ACDEFGHIKL", "database": "pdb"})

    assert task_id == "queued-blast-task-1"
    assert captured["args"] == ["blast_search", {"sequence": "ACDEFGHIKL", "database": "pdb"}]
    assert captured["queue"] == "default"
    assert captured["soft_time_limit"] == 420
    assert captured["time_limit"] == 600


def test_get_task_status_normalizes_success_payload(monkeypatch):
    from app.services import scheduler

    class FakeResult:
        state = "SUCCESS"
        info = {
            "progress": 100,
            "result": {"status": "completed", "tool": "gromacs_md", "result": {"ok": True}},
        }
        result = info

    monkeypatch.setattr(scheduler, "AsyncResult", lambda task_id, app=None: FakeResult())

    status = scheduler.get_task_status("task-1")

    assert status["status"] == "completed"
    assert status["result"] == {"status": "completed", "tool": "gromacs_md", "result": {"ok": True}}
    assert status["error"] is None


def test_get_task_status_surfaces_running_stage_metadata(monkeypatch):
    from app.services import scheduler

    class FakeResult:
        state = "STARTED"
        info = {
            "progress": 61,
            "message": "Running NVT equilibration",
            "stage": "09_mdrun_nvt",
            "current_step": 9,
            "total_steps": 15,
        }
        result = info

    monkeypatch.setattr(scheduler, "AsyncResult", lambda task_id, app=None: FakeResult())

    status = scheduler.get_task_status("task-running")

    assert status["status"] == "running"
    assert status["progress"] == 61
    assert status["message"] == "Running NVT equilibration"
    assert status["stage"] == "09_mdrun_nvt"
    assert status["current_step"] == 9
    assert status["total_steps"] == 15


def test_get_task_status_normalizes_tool_level_failed_payload(monkeypatch):
    from app.services import scheduler

    class FakeResult:
        state = "SUCCESS"
        info = {
            "progress": 100,
            "result": {
                "status": "failed",
                "error": "GROMACS executable not found",
                "error_code": "GROMACS_NOT_INSTALLED",
            },
        }
        result = info

    monkeypatch.setattr(scheduler, "AsyncResult", lambda task_id, app=None: FakeResult())

    status = scheduler.get_task_status("task-tool-failed")

    assert status["status"] == "failed"
    assert status["result"] == {
        "status": "failed",
        "error": "GROMACS executable not found",
        "error_code": "GROMACS_NOT_INSTALLED",
    }
    assert status["error"] == "GROMACS executable not found"


def test_get_task_status_normalizes_failure_payload(monkeypatch):
    from app.services import scheduler

    class FakeResult:
        state = "FAILURE"
        info = {"progress": 100, "error": "boom"}
        result = RuntimeError("boom")

    monkeypatch.setattr(scheduler, "AsyncResult", lambda task_id, app=None: FakeResult())

    status = scheduler.get_task_status("task-2")

    assert status["status"] == "failed"
    assert status["result"] is None
    assert status["error"] == "boom"


def test_get_task_status_normalizes_revoked_payload(monkeypatch):
    from app.services import scheduler

    class FakeResult:
        state = "REVOKED"
        info = {"progress": 25, "error": "terminated by revoke"}
        result = RuntimeError("terminated by revoke")

    monkeypatch.setattr(scheduler, "AsyncResult", lambda task_id, app=None: FakeResult())

    status = scheduler.get_task_status("task-3")

    assert status["status"] == "canceled"
    assert status["result"] is None
    assert status["error"] == "terminated by revoke"


def test_get_task_status_downgrades_backend_decode_errors(monkeypatch):
    from app.services import scheduler

    class ExplodingResult:
        @property
        def state(self):
            raise ValueError("Exception information must include the exception type")

        @property
        def info(self):
            raise ValueError("Exception information must include the exception type")

        @property
        def result(self):
            raise ValueError("Exception information must include the exception type")

    monkeypatch.setattr(scheduler, "AsyncResult", lambda task_id, app=None: ExplodingResult())

    status = scheduler.get_task_status("task-4")

    assert status["status"] == "failed"
    assert status["result"] is None
    assert "Task backend decode error:" in status["error"]
    assert "Exception information must include the exception type" in status["error"]
    assert status["progress"] == 100


def test_run_tool_task_discovers_tools_when_worker_registry_is_empty(monkeypatch):
    from app.services import scheduler

    state_updates = []

    class FakeLoop:
        def run_until_complete(self, value):
            return value

        def close(self):
            return None

    execute_calls = []
    discover_calls = []

    monkeypatch.setattr(
        "app.tools.registry.ToolRegistry._tools",
        {},
        raising=False,
    )
    monkeypatch.setattr(
        "app.tools.registry.ToolRegistry.discover",
        lambda: discover_calls.append("discover"),
    )
    def fake_execute(name, params, internal_params=None):
        execute_calls.append((name, params, internal_params))
        if internal_params and callable(internal_params.get("progress_callback")):
            internal_params["progress_callback"](42, "Running energy minimization", "07_mdrun_minim", 7, 15)
        return {"ok": True}

    monkeypatch.setattr(
        "app.tools.registry.ToolRegistry.execute",
        fake_execute,
    )
    monkeypatch.setattr(
        scheduler.run_tool_task,
        "update_state",
        lambda *, state, meta, task_id=None: state_updates.append((state, meta, task_id)),
    )
    monkeypatch.setattr("asyncio.new_event_loop", lambda: FakeLoop())
    monkeypatch.setattr("asyncio.set_event_loop", lambda loop: None)

    result = scheduler.run_tool_task.run("gromacs_md", {"pdb_object_name": "uploads/demo.pdb"})

    assert result["status"] == "completed"
    assert result["tool"] == "gromacs_md"
    assert result["result"] == {"ok": True}
    assert discover_calls == ["discover"]
    assert len(execute_calls) == 1
    assert execute_calls[0][0] == "gromacs_md"
    assert execute_calls[0][1] == {"pdb_object_name": "uploads/demo.pdb"}
    assert callable(execute_calls[0][2]["progress_callback"])
    assert state_updates[0][0] == "RUNNING"
    assert state_updates[0][1]["stage"] == "queued_in_worker"
    assert state_updates[0][2] is None
    assert state_updates[1][1]["progress"] == 42
    assert state_updates[1][1]["stage"] == "07_mdrun_minim"
    assert state_updates[-1][0] == "SUCCESS"
