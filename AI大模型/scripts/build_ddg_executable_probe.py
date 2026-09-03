#!/usr/bin/env python3
"""Probe local Rosetta/PyRosetta/FoldX executables without running ddG jobs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_backend_config import default_ddg_config_path
from ddg_python_module_discovery import module_probe_row


AI_ROOT = Path(__file__).resolve().parents[1]
CONFIG = default_ddg_config_path()
OUT = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
LOCAL_EXECUTABLE_DIRS = [
    AI_ROOT / "cache" / "external" / "RosettaConda" / "bin",
    AI_ROOT / "cache" / "external" / "FoldX",
    AI_ROOT / "cache" / "external" / "FoldX" / "bin",
    Path.home() / "foldx",
    Path.home() / "FoldX",
    Path.home() / "Applications" / "FoldX",
]


PROBES = {
    "rosetta": {
        "executables": [
            "cartesian_ddg",
            "cartesian_ddg.cxx11threadserialization.macosclangrelease",
            "cartesian_ddg.default.macosclangrelease",
            "cartesian_ddg.default.linuxgccrelease",
            "rosetta_scripts",
            "rosetta_scripts.cxx11threadserialization.macosclangrelease",
            "rosetta_scripts.default.macosclangrelease",
            "rosetta_scripts.default.linuxgccrelease",
        ],
        "version_args": ["-help"],
        "requires_license_review": True,
    },
    "foldx": {
        "executables": ["foldx", "FoldX"],
        "version_args": ["--help"],
        "requires_license_review": True,
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def candidate_paths(name: str) -> list[Path]:
    paths: list[Path] = []
    env_path = os.environ.get("FOLDX_BINARY") if name.lower() == "foldx" else None
    if env_path:
        paths.append(Path(env_path))
    path = shutil.which(name)
    if path:
        paths.append(Path(path))
    for directory in LOCAL_EXECUTABLE_DIRS:
        local = directory / name
        if local.exists():
            paths.append(local)
    deduped: list[Path] = []
    seen = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def probe_env(path: Path) -> dict[str, str] | None:
    rosetta_bin = AI_ROOT / "cache" / "external" / "RosettaConda" / "bin"
    try:
        path.relative_to(rosetta_bin)
    except ValueError:
        return None
    env = os.environ.copy()
    existing = env.get("DYLD_LIBRARY_PATH")
    env["DYLD_LIBRARY_PATH"] = str(rosetta_bin) if not existing else f"{rosetta_bin}:{existing}"
    return env


def probe_executable(name: str, version_args: list[str]) -> dict[str, Any]:
    paths = candidate_paths(name)
    path = str(paths[0]) if paths else None
    result: dict[str, Any] = {
        "name": name,
        "path": path,
        "found": bool(path),
        "is_file": Path(path).is_file() if path else False,
        "executable_bit": os.access(path, os.X_OK) if path else False,
        "version_probe_attempted": False,
        "version_probe_returncode": None,
        "version_probe_succeeded": False,
        "version_probe_stdout_head": "",
        "version_probe_stderr_head": "",
        "ddg_job_executed": False,
    }
    if not path:
        return result
    try:
        process = subprocess.run(
            [path, *version_args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
            env=probe_env(Path(path)),
            cwd=str(Path(path).parent) if name.lower() in {"foldx"} else None,
        )
        result.update({
            "version_probe_attempted": True,
            "version_probe_returncode": process.returncode,
            "version_probe_succeeded": process.returncode == 0,
            "version_probe_stdout_head": process.stdout[:500],
            "version_probe_stderr_head": process.stderr[:500],
        })
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.update({
            "version_probe_attempted": True,
            "version_probe_error": str(exc),
        })
    return result


def module_probe(name: str) -> dict[str, Any]:
    return module_probe_row(name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe local ddG executables")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    config = load_json(args.config)
    backend_config = config.get("backends") or {}
    backend_rows: list[dict[str, Any]] = []
    for backend, probe in PROBES.items():
        executable_results = [probe_executable(name, probe["version_args"]) for name in probe["executables"]]
        found = [row for row in executable_results if row["found"]]
        version_probe_succeeded = [row for row in executable_results if row["version_probe_succeeded"]]
        enabled = bool((backend_config.get(backend) or {}).get("enabled"))
        technical_ready = enabled and bool(found) and bool(version_probe_succeeded)
        backend_rows.append({
            "backend": backend,
            "enabled_in_config": enabled,
            "executable_found": bool(found),
            "executable_with_version_probe_succeeded": bool(version_probe_succeeded),
            "candidate_executables": executable_results,
            "ready_for_ddg_execution": technical_ready,
            "blockers": [
                reason
                for reason, blocked in [
                    ("backend_disabled_in_config", not enabled),
                    ("executable_not_found_on_path", not found),
                    ("executable_version_probe_not_successful", not version_probe_succeeded),
                ]
                if blocked
            ],
            "policy": "Executable discovery only. ready_for_ddg_execution means technically callable; license, receipt, smoke artifacts and model claims remain separate gates.",
        })

    pyrosetta = module_probe("pyrosetta")
    pyrosetta_enabled = bool((backend_config.get("pyrosetta") or {}).get("enabled"))
    pyrosetta_technical_ready = pyrosetta_enabled and bool(pyrosetta["available"])
    backend_rows.append({
        "backend": "pyrosetta",
        "enabled_in_config": pyrosetta_enabled,
        "python_module_available": pyrosetta["available"],
        "python_module_probe": pyrosetta,
        "ready_for_ddg_execution": pyrosetta_technical_ready,
        "blockers": [
            reason
            for reason, blocked in [
                ("backend_disabled_in_config", not pyrosetta_enabled),
                ("pyrosetta_module_not_available", not pyrosetta["available"]),
            ]
            if blocked
        ],
        "policy": "Module discovery only. ready_for_ddg_execution means technically callable; license, receipt, smoke artifacts and model claims remain separate gates.",
    })

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "config": str(args.config),
        "backend_rows": backend_rows,
        "rosetta_executable_found": any(row["backend"] == "rosetta" and row.get("executable_found") for row in backend_rows),
        "foldx_executable_found": any(row["backend"] == "foldx" and row.get("executable_found") for row in backend_rows),
        "pyrosetta_module_available": bool(pyrosetta["available"]),
        "version_probe_succeeded_rows": sum(
            1
            for row in backend_rows
            for probe in row.get("candidate_executables", [])
            if probe.get("version_probe_succeeded")
        ),
        "ready_for_ddg_execution_rows": sum(1 for row in backend_rows if row.get("ready_for_ddg_execution")),
        "executable_ddg_backend_ready": any(row.get("ready_for_ddg_execution") for row in backend_rows),
        "ddg_smoke_job_executed": False,
        "physics_ddg_ready": False,
        "claim_eligible_rows_now": 0,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "runtime_probe_scope": "PATH executable help/version probe and Python module discovery only; no ddG protocol or mutation scoring.",
        "policy": "Probe is technical evidence only. A true executable_ddg_backend_ready here does not approve license use, runtime receipt, training labels, model claims, or release.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "rosetta_executable_found": report["rosetta_executable_found"],
        "foldx_executable_found": report["foldx_executable_found"],
        "pyrosetta_module_available": report["pyrosetta_module_available"],
        "version_probe_succeeded_rows": report["version_probe_succeeded_rows"],
        "executable_ddg_backend_ready": report["executable_ddg_backend_ready"],
        "physics_ddg_ready": report["physics_ddg_ready"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
