from app.services.model_runtime_readiness import collect_model_runtime_readiness


def test_model_runtime_readiness_reports_blocked_when_torch_is_unavailable(monkeypatch):
    monkeypatch.setattr("app.services.model_runtime_readiness.importlib.util.find_spec", lambda name: None)

    result = collect_model_runtime_readiness()

    assert result["esm2"]["status"] == "blocked"
    assert "torch" in result["esm2"]["missing_dependencies"]
