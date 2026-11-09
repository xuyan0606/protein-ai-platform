import asyncio

from app.api import capabilities
from app.core.config import Settings


def test_capabilities_route_precedes_outline_proxy():
    from app.main import app

    matches = [route for route in app.routes if getattr(route, "path", None) == "/api/capabilities"]
    assert len(matches) == 1
    assert matches[0].endpoint is capabilities.capability_status


def test_capability_status_reports_model_boundaries(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "ready", "model": "ThermoMPNN", "model_version": "model.pt",
                "model_sha256": "abc", "device": "cpu",
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            assert url in {"http://model:8100/health", "http://assistant:8105/health"}
            if url == "http://assistant:8105/health":
                return AssistantResponse()
            return Response()

    class AssistantResponse(Response):
        def json(self):
            return {"status": "ok", "service_version": "enzyme-assistant-v0-20261026"}

    monkeypatch.setenv("THERMOMPNN_SERVICE_URL", "http://model:8100")
    monkeypatch.setenv("ENZYME_ASSISTANT_SERVICE_URL", "http://assistant:8105")
    monkeypatch.delenv("P2RANK_SERVICE_URL", raising=False)
    monkeypatch.setattr(capabilities.httpx, "AsyncClient", lambda timeout: Client())
    monkeypatch.setattr(capabilities.shutil, "which", lambda _: None)
    result = asyncio.run(capabilities.capability_status())

    assert result["thermompnn"]["status"] == "ready"
    assert result["enzyme_assistant"]["status"] == "available"
    assert result["enzyme_assistant"]["evidence_level"] == "research_only_heuristic"
    assert result["enzyme_assistant"]["manual_review_required"] is True
    assert result["km_prediction"]["status"] == "missing_validated_model"
    assert result["interproscan"]["status"] == "missing_contact_email"
    assert result["tm_prediction"]["status"] == "missing_validated_model"
    assert result["tm_prediction"]["evidence_level"] == "runtime_smoke_unapproved"
    assert result["tm_prediction"]["research_execution"]["scope"] == "research_only"
    assert result["tm_prediction"]["benchmark"]["sample_count"] == 531
    assert result["rosetta_ddg"]["status"] == "missing_executable"
    assert result["rosetta_ddg"]["commercial_gate"]["status"] == "blocked"
    assert "mutation_priority_score" in result["rosetta_ddg"]["alternative_path"]["tools"]
    assert result["pocket_prediction"]["fpocket"]["status"] == "missing_executable"
    assert result["pocket_prediction"]["p2rank"]["status"] == "missing_executable"
    assert result["registered_tool_count"] >= 40


def test_capability_status_reports_configured_pocket_binary(monkeypatch, tmp_path):
    executable = tmp_path / "fpocket"
    executable.write_bytes(b"fpocket test binary")
    executable.chmod(0o755)
    monkeypatch.setenv("FPOCKET_BIN", str(executable))
    monkeypatch.delenv("FPOCKET_BINARY", raising=False)
    monkeypatch.setenv("P2RANK_BIN", "")
    monkeypatch.setattr(capabilities.shutil, "which", lambda _: None)
    result = asyncio.run(capabilities.capability_status())

    assert result["pocket_prediction"]["fpocket"]["status"] == "available"
    assert result["pocket_prediction"]["fpocket"]["sha256"]
    assert result["pocket_prediction"]["fpocket"]["commercial_gate"]["status"] == "blocked"


def test_redis_url_includes_and_escapes_password():
    settings = Settings(REDIS_HOST="redis.example", REDIS_PASSWORD="p(a)s#word")
    assert settings.REDIS_URL == "redis://:p%28a%29s%23word@redis.example:6379/0"
