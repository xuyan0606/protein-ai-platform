from app.services import thermostability_limits as limits
from app.services.scheduler import get_task_profile


def test_cpu_http_registry_and_worker_deadlines_are_ordered(monkeypatch):
    for prefix in limits.DEFAULT_HTTP:
        monkeypatch.setenv(prefix + "_SERVICE_TIMEOUT_SECONDS", "3660")
    for name in limits.TOOL_PREFIX:
        budget = limits.tool_timeout(name, 210)
        profile = get_task_profile(name)
        assert 3660 < budget < profile.soft_time_limit < profile.time_limit
    workflow_budget = limits.tool_timeout("thermostability_candidate_workflow", 1800)
    assert workflow_budget > 3 * 3660
    profile = get_task_profile("thermostability_candidate_workflow")
    assert workflow_budget < profile.soft_time_limit < profile.time_limit
