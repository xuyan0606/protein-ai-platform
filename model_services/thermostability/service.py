"""Private HTTP endpoint with isolated jobs, authentication and resource bounds.

The server itself needs only Python 3.11 stdlib. Each model uses its own venv.
Health distinguishes process availability from retained real smoke receipts.
"""
from __future__ import annotations

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import signal
import socketserver
import subprocess
import sys
import threading
import time
import uuid

ROUTES = {"/ddgun/predict": "ddgun", "/colabfold/predict": "colabfold",
          "/evcouplings/couplings": "evcouplings", "/esm/predict": "esm"}
MAX_BODY = 16_100_000
MAX_RESULT = 16_000_000
JOB_LOCK = threading.Lock()


def terminate_tree(process):
    """Terminate model descendants even if upstream starts another session."""
    descendants = {process.pid}
    groups = {process.pid}
    table = []
    for entry in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = entry.read_text().rsplit(")", 1)[1].split()
            table.append((int(entry.parent.name), int(fields[1]), int(fields[2])))
        except (OSError, ValueError, IndexError):
            continue
    while True:
        found = {pid for pid, parent, group in table if parent in descendants}
        if found <= descendants:
            break
        descendants.update(found)
    groups.update(group for pid, parent, group in table if pid in descendants)
    groups.discard(os.getpgrp())
    for group in groups:
        try:
            os.killpg(group, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # Parent exit does not establish that separately-sessioned children exited.
    for group in groups:
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def execute(model: str, payload: dict, root: Path, timeout: int) -> dict:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    job = root / uuid.uuid4().hex
    job.mkdir(mode=0o700)
    request_file, result_file = job / "request.json", job / "result.json"
    request_file.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    interpreter = os.getenv(model.upper() + "_RUNNER_PYTHON", sys.executable)
    env = {**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2",
           "MKL_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "2"}
    module_root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (module_root, env.get("PYTHONPATH"))))
    started = time.time()
    status = "failed"
    with (job / "worker.log").open("wb") as logfile:
        process = subprocess.Popen(
            [interpreter, "-m", "model_services.thermostability.worker", model,
             str(request_file), str(result_file)],
            stdout=logfile, stderr=subprocess.STDOUT, env=env, cwd=job, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
            if code or not result_file.is_file() or result_file.stat().st_size > MAX_RESULT:
                raise RuntimeError("Model worker failed; inspect private job log")
            result = json.loads(result_file.read_text())
            if not isinstance(result, dict):
                raise RuntimeError("Invalid scientific result")
            status = result.get("status", "failed")
        except subprocess.TimeoutExpired as exc:
            terminate_tree(process)
            status = "timeout"
            raise RuntimeError("Scientific job exceeded its configured runtime limit") from exc
        finally:
            receipt = {"job_id": job.name, "model": model, "status": status,
                       "elapsed_seconds": round(time.time() - started, 3),
                       "input_sha256": hashlib.sha256(request_file.read_bytes()).hexdigest()}
            if result_file.is_file():
                receipt["result_sha256"] = hashlib.sha256(result_file.read_bytes()).hexdigest()
            (job / "receipt.json").write_text(json.dumps(receipt, sort_keys=True))
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "ThermostabilityRuntime/1"

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, fmt, *args):
        # Log status and route only; never input sequences, authorization or query text.
        sys.stderr.write(f"model-http {self.command} {self.path.split('?')[0][:80]} {args[1] if len(args)>1 else ''}\n")

    def reply(self, code, value):
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def authorized(self):
        expected = "Bearer " + self.server.auth_token
        return hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected.encode())

    def do_GET(self):
        if not self.authorized():
            return self.reply(401, {"status": "unauthorized"})
        if self.path != "/health":
            return self.reply(404, {"status": "not_found"})
        # Real readiness receipts are written by independent smoke, never by file existence alone.
        receipts = {}
        for model in ROUTES.values():
            path = self.server.run_root.parent / "readiness" / (model + ".json")
            try:
                data = json.loads(path.read_text())
                receipts[model] = {k: data[k] for k in ("status", "verified_at", "result_sha256") if k in data}
            except (OSError, ValueError):
                receipts[model] = {"status": "not_verified"}
        return self.reply(200, {"status": "ok", "busy": JOB_LOCK.locked(), "models": receipts})

    def do_POST(self):
        if not self.authorized():
            return self.reply(401, {"status": "unauthorized"})
        model = ROUTES.get(self.path)
        if not model:
            return self.reply(404, {"status": "not_found"})
        if self.headers.get("Transfer-Encoding"):
            return self.reply(400, {"status": "blocked", "blocked_reason": "Transfer encoding is unsupported"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                return self.reply(413, {"status": "blocked", "blocked_reason": "Request body exceeds bounds"})
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("Truncated request")
            payload = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
            if not isinstance(payload, dict):
                raise ValueError("Request must be an object")
        except (ValueError, UnicodeError, TimeoutError, RecursionError):
            return self.reply(400, {"status": "blocked", "blocked_reason": "Invalid JSON request"})
        if not JOB_LOCK.acquire(blocking=False):
            return self.reply(429, {"status": "blocked", "blocked_reason": "Scientific worker is busy; retry later"})
        try:
            result = execute(model, payload, self.server.run_root, self.server.job_timeout)
            return self.reply(200, result)
        except (ValueError, OSError, RuntimeError) as exc:
            return self.reply(503, {"status": "blocked", "blocked_reason": str(exc)[:300]})
        finally:
            JOB_LOCK.release()


class Server(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, address, token, root, timeout=3600):
        if len(token) < 32:
            raise ValueError("MODEL_SERVICE_TOKEN requires at least 32 characters")
        super().__init__(address, Handler)
        self.auth_token, self.run_root, self.job_timeout = token, root, timeout
        self.slots = threading.BoundedSemaphore(8)

    def process_request(self, request, address):
        if not self.slots.acquire(False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def main():
    os.umask(0o077)
    host = os.environ["MODEL_SERVICE_BIND"]
    port = int(os.getenv("MODEL_SERVICE_PORT", "4270"))
    if not 4200 <= port <= 4299:
        raise ValueError("Service port must be in 4200–4299")
    root = Path(os.environ["MODEL_SERVICE_RUN_ROOT"])
    timeout = int(os.getenv("MODEL_SERVICE_TIMEOUT_SECONDS", "3600"))
    if not 1 <= timeout <= 14400:
        raise ValueError("Timeout must be 1–14400 seconds")
    Server((host, port), os.environ["MODEL_SERVICE_TOKEN"], root, timeout).serve_forever()


if __name__ == "__main__":
    main()
