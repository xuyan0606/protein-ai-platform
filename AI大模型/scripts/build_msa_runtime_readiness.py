#!/usr/bin/env python3
"""Build fail-closed readiness for MSA runtime options."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CONFIG = AI_ROOT / "config" / "msa_runtime.local.example.json"
TARGETS = AI_ROOT / "datasets" / "curation" / "msa_conservation_targets.jsonl"
CACHE_VALIDATION = AI_ROOT / "reports" / "msa_conservation_cache_validation_report.json"
REPORT_OUT = AI_ROOT / "reports" / "msa_runtime_readiness_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_docker_probe(args: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["docker", *args],
            cwd=AI_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": "docker_not_found"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "docker_probe_timeout"}
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def run_probe(command: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=AI_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": "not_found"}
    except OSError as exc:
        return {"returncode": 126, "stdout": "", "stderr": f"os_error:{exc.strerror or exc.__class__.__name__}"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "probe_timeout"}
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def resolve_project_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else AI_ROOT / path


def cache_ready(
    config: dict[str, Any],
    targets: list[dict[str, Any]],
    validation: dict[str, Any],
    validation_report: Path,
) -> dict[str, Any]:
    trusted = config.get("trusted_cache", {})
    enabled = bool(trusted.get("enabled", True))
    msa_root = AI_ROOT / str(trusted.get("msa_cache_root") or "cache/msa")
    conservation_root = AI_ROOT / str(trusted.get("conservation_cache_root") or "datasets/curation/msa_conservation")
    present_msa = 0
    present_conservation = 0
    for target in targets:
        uniprot_id = target.get("uniprot_id")
        if not uniprot_id:
            continue
        if (msa_root / f"{uniprot_id}.aln.fasta").exists():
            present_msa += 1
        if (conservation_root / f"{uniprot_id}.conservation.json").exists():
            present_conservation += 1
    validation_target_rows = validation.get("target_rows_expected")
    validation_target_rows_match = validation_target_rows == len(targets)
    validation_ready = bool(validation.get("ready")) and validation_target_rows_match
    return {
        "enabled": enabled,
        "msa_cache_root": str(msa_root),
        "conservation_cache_root": str(conservation_root),
        "target_rows": len(targets),
        "present_msa": present_msa,
        "present_conservation": present_conservation,
        "validation_ready": validation_ready,
        "validation_report": str(validation_report),
        "validation_target_rows_expected": validation_target_rows,
        "validation_target_rows_match": validation_target_rows_match,
        "validation_error_counts": validation.get("error_counts"),
        "ready": enabled and validation_ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MSA runtime readiness")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--targets", type=Path, default=TARGETS)
    parser.add_argument("--cache-validation", type=Path, default=CACHE_VALIDATION)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    config = load_json(args.config)
    targets = load_jsonl(args.targets)
    cache_validation = load_json(args.cache_validation)
    local_cfg = config.get("local_binary", {}) or {}
    local_required = local_cfg.get("required_executables", ["mmseqs"])
    configured_binary_path = resolve_project_path(local_cfg.get("binary_path"))
    local_paths = {}
    for name in local_required:
        configured = str(configured_binary_path) if name == "mmseqs" and configured_binary_path and configured_binary_path.exists() else None
        local_paths[name] = configured or shutil.which(name)
    local_executable_ready = all(local_paths.values()) if local_required else False
    local_version_probes = {
        name: run_probe([path, "version"]) if path else {"returncode": 127, "stdout": "", "stderr": "executable_missing"}
        for name, path in local_paths.items()
    }
    homolog_db_cfg = config.get("homolog_database", {}) or {}
    homolog_db_path = resolve_project_path(homolog_db_cfg.get("database_path"))
    homolog_database_ready = bool(homolog_db_path and homolog_db_path.exists())
    local_ready = local_executable_ready and homolog_database_ready

    docker_cli = shutil.which("docker")
    docker_version = run_docker_probe(["--version"]) if docker_cli else {"returncode": 127, "stdout": "", "stderr": "docker_not_found"}
    docker_info = run_docker_probe(["info", "--format", "{{json .ServerVersion}}"]) if docker_cli else {"returncode": 127, "stdout": "", "stderr": "docker_not_found"}
    docker_daemon_ready = docker_info["returncode"] == 0
    docker_cfg = config.get("docker_image", {}) or {}
    selected_image = docker_cfg.get("selected_image")
    image_candidates = docker_cfg.get("image_candidates", [])
    image_probe = {"returncode": None, "stdout": "", "stderr": "no_selected_image"}
    if docker_daemon_ready and selected_image:
        image_probe = run_docker_probe(["image", "inspect", selected_image])
    docker_image_present = docker_daemon_ready and selected_image and image_probe["returncode"] == 0
    docker_image_ready = docker_image_present and homolog_database_ready

    trusted_cache = cache_ready(config, targets, cache_validation, args.cache_validation)
    runtime_ready = bool(local_ready or docker_image_ready or trusted_cache["ready"])
    blockers = []
    if not local_executable_ready:
        blockers.append("mmseqs local binary not found on PATH or configured project path")
    if local_executable_ready and not homolog_database_ready:
        blockers.append("homolog database path is not configured or does not exist")
    if not docker_cli:
        blockers.append("docker CLI not found")
    elif not docker_daemon_ready:
        blockers.append("docker daemon not reachable or not running")
    elif not selected_image:
        blockers.append("docker selected_image not configured")
    elif image_probe["returncode"] != 0:
        blockers.append("configured docker image is not present locally")
    elif not homolog_database_ready:
        blockers.append("homolog database path is not configured or does not exist")
    if not trusted_cache["enabled"]:
        blockers.append("trusted MSA/conservation cache is disabled")
    elif not trusted_cache["validation_target_rows_match"]:
        blockers.append("trusted MSA/conservation cache validation target count does not match current targets")
    elif not trusted_cache["validation_ready"]:
        blockers.append("trusted MSA/conservation cache validation is not ready")

    report = {
        "local_only": True,
        "config": str(args.config),
        "target_rows": len(targets),
        "runtime_ready": runtime_ready,
        "selected_runtime": (
            "local_binary"
            if local_ready
            else ("docker_image" if docker_image_ready else ("trusted_cache" if trusted_cache["ready"] else None))
        ),
        "homolog_database": {
            "database_path": str(homolog_db_path) if homolog_db_path else None,
            "database_name": homolog_db_cfg.get("database_name"),
            "database_version": homolog_db_cfg.get("database_version"),
            "checksum_manifest": homolog_db_cfg.get("checksum_manifest"),
            "ready": homolog_database_ready,
        },
        "local_binary": {
            "required_executables": local_required,
            "configured_binary_path": str(configured_binary_path) if configured_binary_path else None,
            "paths": local_paths,
            "version_probes": local_version_probes,
            "executable_ready": local_executable_ready,
            "ready": local_ready,
        },
        "docker_image": {
            "docker_cli": docker_cli,
            "docker_version": docker_version,
            "docker_daemon_ready": docker_daemon_ready,
            "pull_allowed": bool(docker_cfg.get("pull_allowed")),
            "selected_image": selected_image,
            "image_candidates": image_candidates,
            "image_present": bool(docker_image_present),
            "image_probe": image_probe,
            "ready": bool(docker_image_ready),
        },
        "trusted_cache": trusted_cache,
        "blockers": blockers,
        "recommended_next_actions": [
            "Start Docker Desktop and configure selected_image, or approve a Docker pull for MMseqs2.",
            "Alternatively install a local MMseqs2 binary and ensure `mmseqs` is on PATH.",
            "Alternatively provide a trusted precomputed MSA/conservation cache with checksums.",
        ],
        "policy": "readiness only; no MSA, homolog search, docker pull, or conservation feature generation is performed here",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "runtime_ready": report["runtime_ready"],
        "selected_runtime": report["selected_runtime"],
        "blockers": report["blockers"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
