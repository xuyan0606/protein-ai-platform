#!/usr/bin/env python3
"""Dependency-free local HTTP service for KWB-EnzymeDesigner rule MVP."""

from __future__ import annotations

import argparse
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULE_MVP = ROOT / "prototype" / "kwb_enzyme_designer_rule.py"


def load_rule_module():
    spec = importlib.util.spec_from_file_location("kwb_enzyme_designer_rule", RULE_MVP)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load rule MVP from {RULE_MVP}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RULE_MODULE = load_rule_module()


def write_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class KWBHandler(BaseHTTPRequestHandler):
    server_version = "KWBEnzymeDesignerLocal/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            write_json(self, 200, {
                "status": "ok",
                "model": "KWB-EnzymeDesigner",
                "version": "0.1.0-rule-mvp",
                "mode": "local-only",
            })
            return
        write_json(self, 404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/v1/enzyme-design":
            write_json(self, 404, {"error": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length)
            case = json.loads(body.decode("utf-8"))
            result = RULE_MODULE.design(case)
        except json.JSONDecodeError as exc:
            write_json(self, 400, {"error": "invalid_json", "detail": str(exc)})
            return
        except Exception as exc:
            write_json(self, 500, {"error": "model_error", "detail": str(exc)})
            return

        write_json(self, 200, result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local KWB-EnzymeDesigner HTTP service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), KWBHandler)
    print(f"KWB-EnzymeDesigner local service listening on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

