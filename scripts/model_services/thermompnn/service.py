#!/usr/bin/env python3
"""Small host-side HTTP service for the bundled ThermoMPNN runtime."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MODEL_ROOT = Path(__file__).resolve().parents[1] / "cache" / "external" / "ThermoMPNN"
INFERENCE_SCRIPT = MODEL_ROOT / "analysis" / "custom_inference.py"
MODEL_PATH = MODEL_ROOT / "models" / "thermoMPNN_default.pt"
MODEL_VERSION = MODEL_PATH.name
_MUTATION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])(\d+)([ACDEFGHIKLMNPQRSTVWY])$")
_INFERENCE_LOCK = threading.Lock()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _select_predictions(rows: list[dict[str, str]], mutations: list[str]) -> list[dict[str, Any]]:
    """Map API 1-based sequence mutation notation to ThermoMPNN 0-based rows."""
    selected = []
    for mutation in mutations:
        match = _MUTATION.fullmatch(mutation)
        if not match:
            raise ValueError(f"Invalid mutation: {mutation}")
        model_position = int(match.group(2)) - 1
        row = next((
            item for item in rows
            if int(item["position"]) == model_position
            and item["wildtype"] == match.group(1)
            and item["mutation"] == match.group(3)
        ), None)
        if row is None:
            raise ValueError(f"No matching ThermoMPNN row for {mutation}")
        selected.append({
            "mutation": mutation,
            "ddg_pred": round(float(row["ddG_pred"]), 6),
            "model_position": model_position,
        })
    return selected


def predict(payload: dict[str, Any]) -> dict[str, Any]:
    pdb_data = str(payload.get("pdb_data") or "")
    mutations = [str(item).strip().upper() for item in payload.get("mutations") or []]
    chain_id = str(payload.get("chain_id") or "A")[:1]
    if not pdb_data or "ATOM" not in pdb_data:
        raise ValueError("A valid PDB structure is required")
    if len(pdb_data.encode("utf-8")) > 10 * 1024 * 1024:
        raise ValueError("PDB payload exceeds 10 MiB")
    if not mutations or len(mutations) > 500:
        raise ValueError("Provide between 1 and 500 mutations")

    with tempfile.TemporaryDirectory(prefix="thermompnn-service-") as tmp:
        workdir = Path(tmp)
        pdb_path = workdir / "input.pdb"
        pdb_path.write_text(pdb_data, encoding="utf-8")
        command = [
            sys.executable,
            str(INFERENCE_SCRIPT),
            "--pdb", str(pdb_path),
            "--chain", chain_id,
            "--model_path", str(MODEL_PATH),
            "--out_dir", str(workdir),
            # custom_inference uses 0-based model positions; the API remains
            # 1-based for user-facing mutation notation.
            "--mutations", ",".join(
                f"{item[0]}{int(item[1:-1]) - 1}{item[-1]}" for item in mutations
            ),
        ]
        with _INFERENCE_LOCK:
            completed = subprocess.run(command, text=True, capture_output=True, timeout=180, check=False)
        if completed.returncode != 0:
            raise RuntimeError("ThermoMPNN inference failed: " + completed.stderr[-1000:])
        output = workdir / "ThermoMPNN_inference_input.csv"
        if not output.exists():
            raise RuntimeError("ThermoMPNN did not produce its expected CSV artifact")
        with output.open(newline="", encoding="utf-8") as handle:
            predictions = _select_predictions(list(csv.DictReader(handle)), mutations)

    return {
        "status": "completed",
        "model": "ThermoMPNN",
        "model_version": MODEL_VERSION,
        "model_sha256": _sha256(MODEL_PATH),
        "input_sha256": hashlib.sha256(pdb_data.encode("utf-8")).hexdigest(),
        "chain_id": chain_id,
        "device": "cpu",
        "predictions": predictions,
    }


def health() -> dict[str, Any]:
    ready = INFERENCE_SCRIPT.is_file() and MODEL_PATH.is_file()
    return {
        "status": "ready" if ready else "not_ready",
        "model": "ThermoMPNN",
        "model_version": MODEL_VERSION,
        "model_sha256": _sha256(MODEL_PATH) if MODEL_PATH.is_file() else None,
        "python": sys.version.split()[0],
        "device": "cpu",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ThermoMPNNService/1.0"

    def _reply(self, code: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._reply(200, health())
        else:
            self._reply(404, {"status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/predict":
            self._reply(404, {"status": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 11 * 1024 * 1024:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length))
            self._reply(200, predict(payload))
        except ValueError as exc:
            self._reply(422, {"status": "blocked_invalid_input", "error": str(exc)})
        except subprocess.TimeoutExpired:
            self._reply(504, {"status": "blocked_timeout", "error": "Inference exceeded 180 seconds"})
        except Exception as exc:
            self._reply(500, {"status": "failed", "error": str(exc)[-1500:]})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)


def main() -> None:
    host = os.getenv("THERMOMPNN_HOST", "127.0.0.1")
    port = int(os.getenv("THERMOMPNN_PORT", "8100"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(json.dumps({"event": "started", "listen": f"{host}:{port}", **health()}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
