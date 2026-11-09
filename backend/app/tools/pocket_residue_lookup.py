"""Runtime-gated pocket residue extraction using P2Rank or fpocket.

The adapter never invents a pocket.  It reports ``blocked`` when neither
professional runtime is installed, and only emits residue positions parsed
from the selected tool's output when a command actually completed.
"""

from __future__ import annotations

import csv
import hashlib
import os
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.services import storage
from app.tools.registry import ToolRegistry


def _contract(*, status: str, tool: str | None, pdb_text: str, **extra: Any) -> dict[str, Any]:
    digest = hashlib.sha256(pdb_text.encode("utf-8")).hexdigest() if pdb_text else ""
    return {
        "status": status,
        "capability_status": "real_runtime_gated",
        "tool": tool,
        "input_sha256": digest,
        "residue_positions": extra.pop("residue_positions", []),
        "logs": extra.pop("logs", []),
        "artifact_manifest": {"version": 1, "total_count": len(extra.get("artifacts", [])), "artifacts": extra.get("artifacts", [])},
        "scientific_boundary": (
            "P2Rank/fpocket output identifies geometric pocket residues; it does not prove catalytic function, affinity, or mutation benefit."
        ),
        **extra,
    }


def _parse_p2rank_csv(path: Path, chain_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            raw = row.get("residue_ids") or row.get("residues") or row.get("residue_numbers") or ""
            for token in str(raw).replace(";", ",").split(","):
                token = token.strip()
                if not token:
                    continue
                number = "".join(ch for ch in token if ch.isdigit() or ch == "-")
                try:
                    position = int(number)
                except ValueError:
                    continue
                rows.append({
                    "chain_id": chain_id,
                    "pdb_residue_no": position,
                    "pocket_id": row.get("name") or row.get("pocket_id"),
                    "pocket_score": row.get("score") or row.get("probability"),
                    "source": "p2rank",
                })
    return rows


def _parse_fpocket_atoms(path: Path, default_chain: str) -> list[dict[str, Any]]:
    """Parse fpocket pocket*_atm.pdb residue coordinates conservatively."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    pocket_id = path.stem.split("_")[0]
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line[:6].strip().upper() not in {"ATOM", "HETATM"} or len(line) < 26:
            continue
        try:
            chain = line[21].strip() or default_chain
            position = int(line[22:26].strip())
        except (IndexError, ValueError):
            continue
        insertion = line[26].strip()
        key = (chain, position, insertion)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "chain_id": chain,
            "pdb_residue_no": position,
            "insertion_code": insertion or None,
            "pocket_id": pocket_id,
            "source": "fpocket",
        })
    return rows


def _resolve_executable(name: str) -> str | None:
    configured = os.getenv(f"{name.upper()}_BINARY", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file() and candidate.stat().st_mode & 0o111:
            return str(candidate)
        discovered = shutil.which(configured)
        if discovered:
            return discovered
    return shutil.which(name)


async def pocket_residue_lookup(
    pdb_data: str = "",
    pdb_object_name: str = "",
    chain_id: str = "A",
    engine: str = "auto",
) -> dict[str, Any]:
    """Run P2Rank/fpocket and return parsed pocket residue coordinates."""
    if not pdb_data and pdb_object_name:
        pdb_data = (await storage.download_file(pdb_object_name)).decode("utf-8", errors="replace")
    if not pdb_data.strip():
        return _contract(status="failed", tool=None, pdb_text="", error_code="MISSING_PDB", error="Provide pdb_data or pdb_object_name.")

    choices = [engine] if engine in {"p2rank", "fpocket"} else ["p2rank", "fpocket"]
    executables = {name: _resolve_executable(name) for name in choices}
    selected = next((name for name in choices if executables.get(name)), None)
    if not selected:
        return _contract(
            status="blocked",
            tool=None,
            pdb_text=pdb_data,
            error_code="RUNTIME_UNAVAILABLE",
            error="Neither P2Rank nor fpocket executable is installed on this worker.",
            required_runtime=["p2rank", "fpocket"],
        )

    logs: list[str] = []
    artifacts: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pocket-residue-") as tmp:
        root = Path(tmp)
        pdb_path = root / "input.pdb"
        pdb_path.write_text(pdb_data, encoding="utf-8")
        try:
            if selected == "p2rank":
                proc = subprocess.run([executables[selected], "-predict", str(pdb_path)], cwd=root, capture_output=True, text=True, timeout=180)
                logs.extend([proc.stdout[-4000:], proc.stderr[-4000:]])
                csv_candidates = list(root.rglob("*_predictions.csv")) + list(root.rglob("*.csv"))
                residues = []
                for candidate in csv_candidates:
                    residues.extend(_parse_p2rank_csv(candidate, chain_id))
                    artifacts.append(str(candidate.name))
            else:
                proc = subprocess.run([executables[selected], "-f", str(pdb_path)], cwd=root, capture_output=True, text=True, timeout=180)
                logs.extend([proc.stdout[-4000:], proc.stderr[-4000:]])
                residues = []
                for pocket_file in root.rglob("pocket*_atm.pdb"):
                    residues.extend(_parse_fpocket_atoms(pocket_file, chain_id))
                    artifacts.append(str(pocket_file.name))
            if proc.returncode != 0:
                return _contract(status="failed", tool=selected, pdb_text=pdb_data, logs=logs, artifacts=artifacts, error_code="RUNTIME_FAILED", error=f"{selected} exited with code {proc.returncode}.")
            return _contract(status="completed", tool=selected, pdb_text=pdb_data, logs=logs, artifacts=artifacts, residue_positions=residues, residue_count=len(residues))
        except subprocess.TimeoutExpired:
            return _contract(status="failed", tool=selected, pdb_text=pdb_data, logs=logs, artifacts=artifacts, error_code="TIMEOUT", error=f"{selected} exceeded 180 seconds.")


ToolRegistry.register(
    name="pocket_residue_lookup",
    description="Run real P2Rank/fpocket and return auditable pocket residue coordinates; blocks when runtime is unavailable.",
    handler=pocket_residue_lookup,
    is_async=True,
    category="engineering",
    timeout_seconds=210,
    parameters={
        "type": "object",
        "properties": {
            "pdb_data": {"type": "string"},
            "pdb_object_name": {"type": "string"},
            "chain_id": {"type": "string", "default": "A"},
            "engine": {"type": "string", "enum": ["auto", "p2rank", "fpocket"], "default": "auto"},
        },
    },
)
