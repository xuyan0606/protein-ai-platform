#!/usr/bin/env python3
"""Plan or execute allow-listed external production gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

try:
    from scripts.external_gate_contract import GateStatus, evaluate_inputs, gate_contracts
except ModuleNotFoundError:  # Direct `python scripts/run_external_gate.py` execution.
    from external_gate_contract import GateStatus, evaluate_inputs, gate_contracts


def _execute_gate(contract, values: Mapping[str, object]) -> dict[str, object]:
    command = build_command(contract.name, values)
    if not _entrypoint_exists(command[1]):
        return {"name": contract.name, "status": GateStatus.FAILED.value, "exit_code": None, "detail": "adapter entrypoint missing", "command_id": contract.command_id}
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, **{str(k): str(v) for k, v in values.items()}},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "name": contract.name,
            "status": GateStatus.FAILED.value,
            "exit_code": None,
            "detail": str(exc),
            "command_id": contract.command_id,
        }

    try:
        evidence = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError):
        evidence = None
    status = classify_result(contract.name, completed.returncode, evidence)
    return {
        "name": contract.name,
        "status": status.value,
        "exit_code": completed.returncode,
        "detail": "evidence accepted" if status is GateStatus.PASSED else "invalid or non-terminal evidence",
        "command_id": contract.command_id,
    }


REPO_ROOT = Path(__file__).resolve().parents[1]
_COMMANDS: dict[str, tuple[str, ...]] = {
    "production_https": (str(REPO_ROOT / "scripts/check_production_config.py"), "--strict"),
    "foldseek_live": (str(REPO_ROOT / "backend/scripts/structure_smoke_readiness.py"), "--require-live"),
    "gpu_md": (str(REPO_ROOT / "backend/scripts/smoke_md_topology.py"), "--require-live"),
    "ligand_runtime": (str(REPO_ROOT / "backend/scripts/smoke_ligand_toolchain.py"), "--require-ligand-ready"),
    "oss_minio": (str(REPO_ROOT / "scripts/smoke_oss_minio_contract.py"), "--require-live"),
    "admin_screenshot": (str(REPO_ROOT / "scripts/smoke_admin_oidc_tools_live.py"), "--require-live"),
    "maintenance_restore": (str(REPO_ROOT / "scripts/run_release_acceptance.py"), "--json"),
}


def build_command(gate_name: str, values: Mapping[str, object]) -> list[str]:
    """Build a fixed argv command; input values are supplied through the environment."""
    del values
    contract = gate_contracts().get(gate_name)
    if contract is None or gate_name not in _COMMANDS:
        raise ValueError(f"no command adapter for gate: {gate_name}")
    return [sys.executable, *_COMMANDS[gate_name]]


def _entrypoint_exists(path: str) -> bool:
    return Path(path).is_file()


def _secret_inputs_present(contract, values: Mapping[str, object]) -> list[str]:
    return [
        name
        for name in contract.secret_inputs
        if values.get(name) is not None and bool(str(values[name]).strip())
    ]


def _redact(value: Any) -> Any:
    """Remove values from fields conventionally used for credentials."""
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]"
            if any(marker in str(key).lower() for marker in ("secret", "password", "token", "access_key"))
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def write_evidence(payload: Mapping[str, object], output_root: Path | str) -> Path:
    """Write redacted evidence and a self-describing SHA-256 manifest."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = root / f"run-{stamp}-{os.getpid()}"
    run_dir.mkdir()

    evidence_path = run_dir / "evidence.json"
    evidence_path.write_text(
        json.dumps(_redact(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    files = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.name == "evidence-manifest.json":
            continue
        files.append(
            {
                "path": str(path.relative_to(run_dir)),
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (run_dir / "evidence-manifest.json").write_text(
        json.dumps({"files": files}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run_dir


def classify_result(gate_name: str, exit_code: Optional[int], evidence: object) -> GateStatus:
    """Accept only successful processes with an explicit terminal passed status."""
    contract = gate_contracts().get(gate_name)
    if contract is None or exit_code != 0 or not isinstance(evidence, Mapping):
        return GateStatus.FAILED
    status = evidence.get("status")
    if not isinstance(status, str) and isinstance(evidence.get("summary"), Mapping):
        status = evidence["summary"].get("status")
    terminal = {"passed", "ready", "live-ready", "live_ready", *contract.terminal_statuses}
    if not isinstance(status, str) or status not in terminal:
        return GateStatus.FAILED
    return GateStatus.PASSED


def run(
    *,
    selected: Sequence[str],
    execute: bool,
    values: Mapping[str, object],
    output_root: Path | str,
) -> tuple[dict[str, object], int]:
    contracts = gate_contracts()
    rows: list[dict[str, object]] = []
    executed = False
    for name in selected:
        if name not in contracts:
            rows.append({"name": name, "status": GateStatus.BLOCKED.value, "detail": "unknown gate"})
            continue
        contract = contracts[name]
        evaluation = evaluate_inputs(name, values)
        if execute and evaluation.status is GateStatus.ARMED:
            executed = True
            row = _execute_gate(contract, values)
            row["secret_inputs_present"] = _secret_inputs_present(contract, values)
            rows.append(row)
            continue
        rows.append(
            {
                "name": name,
                "status": evaluation.status.value,
                "missing_inputs": list(evaluation.missing),
                "command_id": contract.command_id,
                "secret_inputs_present": _secret_inputs_present(contract, values),
            }
        )

    all_passed = bool(rows) and all(row["status"] == GateStatus.PASSED.value for row in rows)
    payload: dict[str, object] = {
        "mode": "execute" if execute else "plan_only",
        "gates": rows,
        "network_io": "executed" if executed else "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
    }
    write_evidence(payload, output_root)
    return payload, 0 if all_passed else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--gate", action="append", choices=sorted(gate_contracts()))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output-root", default="docs/manuals/external-gate-runs")
    return parser


def main() -> int:
    args = _parser().parse_args()
    selected = list(gate_contracts()) if args.all or not args.gate else args.gate
    payload, exit_code = run(
        selected=selected,
        execute=bool(args.execute),
        values=os.environ,
        output_root=Path(args.output_root),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
