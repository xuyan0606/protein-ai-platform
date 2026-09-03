#!/usr/bin/env python3
"""Build MSA runtime command plans without executing homolog searches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CONFIG = AI_ROOT / "config" / "msa_runtime.local.example.json"
RUNTIME_REPORT = AI_ROOT / "reports" / "msa_runtime_readiness_report.json"
EXECUTION_PLAN = AI_ROOT / "datasets" / "curation" / "msa_execution_plan.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "msa_runtime_commands.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "msa_runtime_command_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def rel_or_none(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MSA runtime command plans")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--runtime-report", type=Path, default=RUNTIME_REPORT)
    parser.add_argument("--execution-plan", type=Path, default=EXECUTION_PLAN)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    config = load_json(args.config)
    runtime = load_json(args.runtime_report)
    jobs = load_jsonl(args.execution_plan)
    homolog_db_cfg = config.get("homolog_database", {}) or {}
    homolog_db_value = homolog_db_cfg.get("database_path")
    homolog_db_path = (AI_ROOT / homolog_db_value) if homolog_db_value else None
    homolog_db_ready = bool(homolog_db_path and homolog_db_path.exists())
    local_binary_value = (config.get("local_binary", {}) or {}).get("binary_path")
    local_binary_path = (AI_ROOT / local_binary_value) if local_binary_value else None
    local_binary_command = rel_or_none(local_binary_path) if local_binary_path and local_binary_path.exists() else "mmseqs"
    docker_cfg = config.get("docker_image", {}) or {}
    docker_image = docker_cfg.get("selected_image") or (docker_cfg.get("image_candidates") or [None])[0]
    input_fasta = "datasets/curation/msa_inputs/msa_targets.fasta"
    hit_table = "cache/msa/mmseqs_hits.m8"
    tmp_dir = "cache/msa/tmp"

    blockers = list(runtime.get("blockers") or [])
    if not homolog_db_ready and "homolog database path is not configured or does not exist" not in blockers:
        blockers.append("homolog database path is not configured or does not exist")

    command_rows: list[dict[str, Any]] = []
    local_command = [
        local_binary_command,
        "easy-search",
        input_fasta,
        rel_or_none(homolog_db_path) or "<homolog_database>",
        hit_table,
        tmp_dir,
        "--format-output",
        "query,target,pident,alnlen,mismatch,gapopen,qstart,qend,tstart,tend,evalue,bits",
    ]
    command_rows.append({
        "command_id": "msa_mmseqs_local_binary_batch_001",
        "runtime": "local_binary",
        "status": "ready_to_run" if runtime.get("selected_runtime") == "local_binary" and homolog_db_ready else "blocked",
        "command": local_command,
        "expected_input": input_fasta,
        "homolog_database": rel_or_none(homolog_db_path),
        "expected_hit_table": hit_table,
        "expected_target_jobs": len(jobs),
        "blockers": [] if runtime.get("selected_runtime") == "local_binary" and homolog_db_ready else blockers,
        "policy": "command plan only; not executed by this script",
    })
    command_rows.append({
        "command_id": "msa_mmseqs_docker_batch_001",
        "runtime": "docker_image",
        "status": "ready_to_run" if runtime.get("selected_runtime") == "docker_image" and homolog_db_ready else "blocked",
        "command": [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{AI_ROOT}:/work",
            "-w",
            "/work",
            docker_image or "<mmseqs2_image>",
            "mmseqs",
            "easy-search",
            input_fasta,
            rel_or_none(homolog_db_path) or "<homolog_database>",
            hit_table,
            tmp_dir,
            "--format-output",
            "query,target,pident,alnlen,mismatch,gapopen,qstart,qend,tstart,tend,evalue,bits",
        ],
        "image": docker_image,
        "pull_allowed": bool(docker_cfg.get("pull_allowed")),
        "expected_input": input_fasta,
        "homolog_database": rel_or_none(homolog_db_path),
        "expected_hit_table": hit_table,
        "expected_target_jobs": len(jobs),
        "blockers": [] if runtime.get("selected_runtime") == "docker_image" and homolog_db_ready else blockers,
        "policy": "command plan only; docker pull/run requires explicit user action outside this script",
    })
    command_rows.append({
        "command_id": "msa_trusted_cache_import_001",
        "runtime": "trusted_cache",
        "status": "ready_to_validate" if runtime.get("selected_runtime") == "trusted_cache" else "blocked",
        "command": [
            "python3",
            "scripts/validate_msa_conservation_cache.py",
            "--manifest",
            (config.get("trusted_cache", {}) or {}).get("manifest_path", "reports/msa_conservation_manifest.json"),
        ],
        "expected_target_jobs": len(jobs),
        "blockers": [] if runtime.get("selected_runtime") == "trusted_cache" else blockers,
        "policy": "placeholder validation command; cache validator must verify source version and checksums before feature use",
    })

    write_jsonl(args.output, command_rows)
    report = {
        "runtime_ready": runtime.get("runtime_ready"),
        "selected_runtime": runtime.get("selected_runtime"),
        "execution_jobs": len(jobs),
        "command_rows": len(command_rows),
        "ready_commands": sum(1 for row in command_rows if str(row.get("status")).startswith("ready")),
        "blocked_commands": sum(1 for row in command_rows if row.get("status") == "blocked"),
        "homolog_database_ready": homolog_db_ready,
        "homolog_database": rel_or_none(homolog_db_path),
        "blockers": blockers,
        "output": str(args.output),
        "policy": "command planning only; no external downloads, docker pulls, MSA searches, or conservation features are generated",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "command_rows": report["command_rows"],
        "ready_commands": report["ready_commands"],
        "blocked_commands": report["blocked_commands"],
        "homolog_database_ready": report["homolog_database_ready"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
