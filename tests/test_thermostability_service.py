import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from model_services.thermostability import service


@pytest.fixture
def server(tmp_path):
    instance = service.Server(("127.0.0.1", 4279), "x" * 40, tmp_path)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join()


def request(server, path="/health", body=None, token="x" * 40):
    return urlopen(Request(
        f"http://127.0.0.1:{server.server_port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + token}), timeout=2)


def test_requires_authentication(server):
    with pytest.raises(HTTPError) as error:
        request(server, token="wrong")
    assert error.value.code == 401


def test_health_does_not_claim_model_readiness(server):
    with request(server) as response:
        data = json.load(response)
    assert data["models"]["ddgun"]["status"] == "not_verified"


def test_busy_scientific_worker_returns_backpressure(server):
    service.JOB_LOCK.acquire()
    try:
        with pytest.raises(HTTPError) as error:
            request(server, "/ddgun/predict", {"sequence": "ACDE"})
        assert error.value.code == 429
    finally:
        service.JOB_LOCK.release()


def test_private_job_and_receipt_are_preserved(tmp_path, monkeypatch):
    class Process:
        def __init__(self, args, **kwargs):
            assert kwargs["start_new_session"]
            assert kwargs["env"]["OMP_NUM_THREADS"] == "2"
            assert kwargs["cwd"].parent == tmp_path
            assert kwargs["cwd"].stat().st_mode & 0o777 == 0o700
            assert "PYTHONPATH" in kwargs["env"]
            Path(args[-1]).write_text('{"status":"blocked","blocked_reason":"missing runtime"}')

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(service.subprocess, "Popen", Process)
    result = service.execute("ddgun", {"sequence": "ACDE"}, tmp_path, 10)
    assert result["status"] == "blocked"
    job = next(tmp_path.iterdir())
    assert job.stat().st_mode & 0o777 == 0o700
    receipt = json.loads((job / "receipt.json").read_text())
    assert receipt["status"] == "blocked"
    assert len(receipt["result_sha256"]) == 64


def test_timeout_kills_process_group(tmp_path, monkeypatch):
    calls = []

    class Process:
        pid = 123

        def __init__(self, *args, **kwargs):
            self.first = True

        def wait(self, timeout=None):
            if self.first:
                self.first = False
                raise service.subprocess.TimeoutExpired("test", timeout)
            return 0

    monkeypatch.setattr(service.subprocess, "Popen", Process)
    monkeypatch.setattr(service.os, "killpg", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="runtime limit"):
        service.execute("colabfold", {"sequence": "ACDE"}, tmp_path, 1)
    assert calls == [(123, service.signal.SIGTERM), (123, service.signal.SIGKILL)]
    receipt = json.loads(next(tmp_path.glob("*/receipt.json")).read_text())
    assert receipt["status"] == "timeout"


def test_worker_wraps_real_evidence(monkeypatch, tmp_path):
    import sys
    import types
    from model_services.thermostability import worker
    runner = types.ModuleType("model_services.thermostability.evcouplings_runner")
    runner.run_evcouplings = lambda payload, root: {
        "result": {"couplings": [{"position_i": 1, "position_j": 2, "score": 0.1}]},
        "model_version": "test-version", "algorithm_commit": "abcdef1234",
        "database_version": "local-test-alignment", "raw_result": "actual raw log"}
    monkeypatch.setitem(sys.modules, runner.__name__, runner)
    payload = {"sequence": "ACDE"}
    result = worker.run("evcouplings", payload, tmp_path)
    assert result["model"] == "EVcouplings"
    assert result["input_sha256"] == worker.digest(payload)
    assert result["evidence"]["raw_result_sha256"] == worker.digest("actual raw log")
