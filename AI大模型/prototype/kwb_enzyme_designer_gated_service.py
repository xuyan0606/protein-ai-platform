#!/usr/bin/env python3
"""Local HTTP service for the gated KWB-EnzymeDesigner adapter."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from platform_integration.kwb_tool_adapter_local import (  # noqa: E402
    WorkflowContext,
    run_local_adapter,
)


SERVICE_VERSION = "0.3.0-gated-local-dashboard"
HOME_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KWB-EnzymeDesigner Local</title>
  <style>
    :root { color-scheme: dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #0e1726; color: #e8eef8; }
    main { max-width: 920px; margin: 48px auto; padding: 0 24px; }
    .panel { background: #152238; border: 1px solid #2a3b58; border-radius: 10px; padding: 24px; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    p { color: #aebbd0; }
    .status { display: inline-flex; gap: 8px; align-items: center; color: #7ee2a8; }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: #43d17a; }
    code, pre, textarea { font-family: "SFMono-Regular", Consolas, monospace; }
    textarea { width: 100%; min-height: 240px; box-sizing: border-box; margin-top: 14px; padding: 12px; color: #e8eef8; background: #0b1220; border: 1px solid #344865; border-radius: 6px; }
    button { margin: 14px 8px 0 0; padding: 10px 14px; color: white; background: #2f73d9; border: 0; border-radius: 6px; cursor: pointer; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; padding: 14px; background: #0b1220; border-radius: 6px; }
    .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin: 20px 0; }
    .meta div { padding: 12px; background: #101b2d; border-radius: 6px; }
    small { color: #8fa1bb; }
  </style>
</head>
<body>
  <main>
    <div class="panel">
      <div class="status"><span class="dot"></span> Local service running</div>
      <h1>KWB-EnzymeDesigner</h1>
      <p>Gated local deployment for structure-aware enzyme design.</p>
      <div class="meta">
        <div><small>Version</small><br><code id="service-version">0.3.0-gated-local-dashboard</code></div>
        <div><small>Mode</small><br><code>local-only-gated</code></div>
        <div><small>Production integration</small><br><code>false</code></div>
      </div>
      <div id="status-grid" class="meta"></div>
      <button onclick="checkHealth()">Check health</button>
      <button onclick="loadStatus()">Refresh research status</button>
      <button onclick="runExample()">Run example</button>
      <textarea id="payload">{
  "case_id": "browser-demo",
  "objective": {"primary_goal": "stability"},
  "enzyme": {"name": "demo-enzyme", "sequence": "MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM"},
  "structure": {"source_type": "uploaded_pdb", "object_name": "uploads/demo.pdb", "chain_id": "A", "numbering_verified": true},
  "mutations": [{"code": "A42P", "position": 42, "wild_type": "A", "mutant": "P", "status": "untested", "risk_flags": []}]
}</textarea>
      <pre id="output">Ready.</pre>
    </div>
  </main>
  <script>
    async function checkHealth() {
      const response = await fetch("/health");
      document.getElementById("output").textContent = JSON.stringify(await response.json(), null, 2);
    }
    async function loadStatus() {
      const response = await fetch("/v1/status");
      const data = await response.json();
      const summary = data.summary || {};
      const items = [
        ["Readiness", summary.overall_status || "unknown"],
        ["Ready streams", `${summary.ready_streams || 0}/${summary.total_streams || 0}`],
        ["Pipeline", `${summary.pipeline_steps_run || 0}/${summary.pipeline_steps_requested || 0}`],
        ["Strict labels", summary.strict_supervised_rows ?? 0],
        ["Domain intervals", `${summary.domain_usable_rows || 0}/${summary.domain_invalid_rows || 0}`],
        ["MSA inputs", `${summary.msa_fasta_ready || 0}/${summary.msa_targets || 0}`]
      ];
      document.getElementById("status-grid").innerHTML = items.map(item =>
        `<div><small>${item[0]}</small><br><code>${item[1]}</code></div>`
      ).join("");
      document.getElementById("output").textContent = JSON.stringify(data, null, 2);
    }
    async function runExample() {
      const payload = JSON.parse(document.getElementById("payload").value);
      payload._kwb_context = {session_id: "browser-session", conversation_id: "browser-conversation", request_turn_id: "browser-turn"};
      const response = await fetch("/v1/enzyme-design", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
      document.getElementById("output").textContent = JSON.stringify(await response.json(), null, 2);
    }
    loadStatus();
  </script>
</body>
</html>
"""


def write_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def request_context(payload: dict[str, Any]) -> WorkflowContext:
    context = payload.get("_kwb_context") or {}
    return WorkflowContext(
        session_id=str(context.get("session_id") or "local-http-session"),
        conversation_id=(
            str(context["conversation_id"])
            if context.get("conversation_id") is not None
            else None
        ),
        request_turn_id=str(context.get("request_turn_id") or "local-http-turn"),
    )


def load_json_report(name: str) -> dict[str, Any]:
    path = ROOT / "reports" / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def local_status() -> dict[str, Any]:
    board = load_json_report("master_readiness_board.json")
    readiness = load_json_report("training_readiness_report.json")
    pipeline = load_json_report("safe_training_pipeline_run.json")
    domain = load_json_report("domain_interval_repair_report.json")
    domain_apply = load_json_report("domain_interval_apply_report.json")
    msa = load_json_report("msa_executor_readiness_report.json")
    structure = load_json_report("structure_acquisition_readiness_report.json")
    return {
        "service": {
            "model": "KWB-EnzymeDesigner",
            "version": SERVICE_VERSION,
            "mode": "local-only-gated",
            "production_integration": False,
        },
        "summary": {
            "overall_status": board.get("overall_status"),
            "ready_streams": board.get("ready_streams", 0),
            "total_streams": board.get("total_streams", 0),
            "pipeline_steps_run": pipeline.get("steps_run", 0),
            "pipeline_steps_requested": pipeline.get("steps_requested", 0),
            "strict_supervised_rows": readiness.get("label_integrity", {}).get("strict_supervised_rows", 0),
            "domain_usable_rows": domain_apply.get("usable_for_position_features", 0),
            "domain_invalid_rows": domain.get("invalid_rows", 0),
            "msa_fasta_ready": msa.get("fasta_ready", 0),
            "msa_targets": msa.get("target_rows", 0),
            "structure_entries": structure.get("entries", 0),
            "structure_missing": structure.get("missing", 0),
        },
        "streams": board.get("streams", []),
        "blockers": readiness.get("blockers", []),
    }


class KWBGatedHandler(BaseHTTPRequestHandler):
    server_version = "KWBEnzymeDesignerGatedLocal/0.2"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_HEAD(self) -> None:
        if self.path in {"/", ""}:
            body = HOME_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if self.path.rstrip("/") in {"/health", "/v1/status"}:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:
        if self.path in {"/", ""}:
            body = HOME_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.rstrip("/") == "/health":
            write_json(self, 200, {
                "status": "ok",
                "model": "KWB-EnzymeDesigner",
                "version": SERVICE_VERSION,
                "mode": "local-only-gated",
                "production_integration": False,
            })
            return
        if self.path.rstrip("/") == "/v1/status":
            write_json(self, 200, local_status())
            return
        write_json(self, 404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/v1/enzyme-design":
            write_json(self, 404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            case = {key: value for key, value in payload.items() if not key.startswith("_")}
            result = run_local_adapter(
                case,
                request_context(payload),
                completed_tools=payload.get("_completed_tools") or [],
                tool_result_refs=payload.get("_tool_result_refs") or [],
            )
        except json.JSONDecodeError as exc:
            write_json(self, 400, {"error": "invalid_json", "detail": str(exc)})
            return
        except ValueError as exc:
            write_json(self, 400, {"error": "invalid_request", "detail": str(exc)})
            return
        except Exception as exc:
            write_json(self, 500, {"error": "model_error", "detail": str(exc)})
            return
        write_json(self, 200, result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run gated local KWB-EnzymeDesigner service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), KWBGatedHandler)
    print(f"KWB-EnzymeDesigner gated local service listening on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
