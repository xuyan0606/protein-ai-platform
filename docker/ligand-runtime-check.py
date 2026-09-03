#!/usr/bin/env python
from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import subprocess
from typing import Any


LOADER_ERROR_MARKERS = (
    "error while loading shared libraries",
    "failed to open elf",
    "version `",
    "not found (required by",
)


def command_status(*names: str, require_all: bool = False) -> dict[str, Any]:
    commands = {name: shutil.which(name) for name in names}
    command_checks: dict[str, dict[str, Any]] = {}
    version = None
    for name, path in commands.items():
        if not path:
            command_checks[name] = {"path": None, "loadable": False, "returncode": None}
            continue
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=8, check=False)
            output = result.stdout or result.stderr
            load_error = any(marker in output for marker in LOADER_ERROR_MARKERS)
            # Open Babel returns 1 for its informational --version/usage path;
            # loader failures (including foreign-architecture ELF binaries)
            # remain hard failures.
            loadable = result.returncode in {0, 1} and not load_error
            command_checks[name] = {"path": path, "loadable": loadable, "returncode": result.returncode}
            if version is None:
                version = output.splitlines()[:3]
        except Exception as exc:
            command_checks[name] = {"path": path, "loadable": False, "returncode": None, "error": str(exc)}
            if version is None:
                version = [f"version check failed: {exc}"]
    loadable_values = [
        check["loadable"]
        for name, check in command_checks.items()
        if commands.get(name)
    ]
    available = (len(loadable_values) == len(names) and all(loadable_values)) if require_all else any(loadable_values)
    return {"available": available, "commands": commands, "command_checks": command_checks, "version": version}


def module_status(name: str) -> dict[str, Any]:
    return {"available": importlib.util.find_spec(name) is not None, "module": name}


def build_payload() -> dict[str, Any]:
    tools = {
        "openbabel": command_status("obabel"),
        "rdkit": module_status("rdkit"),
        "vina": command_status("vina"),
        "acpype": command_status("acpype"),
        "ambertools": command_status("antechamber", "parmchk2", "teLeap", require_all=True),
        "gromacs": command_status(os.getenv("GROMACS_BIN", "gmx"), "gmx_mpi"),
    }
    requirements = {
        "conformer_generation": tools["openbabel"]["available"] or tools["rdkit"]["available"],
        "pdbqt_preparation": tools["openbabel"]["available"],
        "vina_docking": tools["vina"]["available"],
        "ligand_topology": tools["acpype"]["available"],
        "ambertools_topology_backend": tools["ambertools"]["available"],
        "gromacs_md_assembly": tools["gromacs"]["available"],
    }
    missing = [name for name, ready in requirements.items() if not ready]
    host_architecture = platform.machine().lower()
    architecture_compatible = host_architecture in {"x86_64", "amd64"}
    if not architecture_compatible:
        missing.append("linux_amd64_worker")
    return {
        "name": "ligand_worker_runtime_check",
        "status": "ready" if not missing else "blocked_toolchain_missing",
        "execution_status": "capability_ready" if not missing else "capability_blocked",
        "scientific_smoke_status": "not_run",
        "evidence_level": "runtime_capability_only",
        "runtime_boundary": os.getenv("LIGAND_RUNTIME_BOUNDARY", "ligand_worker_only"),
        "host_architecture": host_architecture,
        "expected_architecture": "x86_64/amd64",
        "architecture_compatible": architecture_compatible,
        "tools": tools,
        "requirements": requirements,
        "missing_requirements": missing,
    }


def main() -> int:
    payload = build_payload()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
