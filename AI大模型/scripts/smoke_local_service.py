#!/usr/bin/env python3
"""Smoke test the local KWB-EnzymeDesigner HTTP service in-process."""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "prototype" / "kwb_enzyme_designer_service.py"
SAMPLE_CASE = ROOT / "datasets" / "sample_case.json"


def load_service_module():
    spec = importlib.util.spec_from_file_location("kwb_enzyme_designer_service", SERVICE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load service from {SERVICE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    service = load_service_module()
    server = ThreadingHTTPServer(("127.0.0.1", 0), service.KWBHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        health = request_json(f"{base}/health")
        if health.get("status") != "ok":
            raise AssertionError(f"bad health response: {health}")
        case = json.loads(SAMPLE_CASE.read_text(encoding="utf-8"))
        result = request_json(f"{base}/v1/enzyme-design", case)
        if result.get("model", {}).get("name") != "KWB-EnzymeDesigner":
            raise AssertionError(f"bad model response: {result}")
        if not result.get("candidates"):
            raise AssertionError("missing candidates")
        print("local_service_smoke_ok")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
