#!/usr/bin/env python3
"""Run and receipt a reproducible Rosetta Cartesian ddG smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
ROSETTA_BIN = AI_ROOT / "cache" / "external" / "RosettaConda" / "bin" / "cartesian_ddg"
ROSETTA_DB = AI_ROOT / "cache" / "external" / "RosettaConda" / "database"
INPUT_PDB = AI_ROOT / "cache" / "structures" / "pdb" / "10mh.pdb"
OUTPUT_DIR = AI_ROOT / "cache" / "advanced_features" / "ddg_physical_smoke" / "rosetta" / "10MH_A_T10A_cartesian_smoke_v3"
REPORT = AI_ROOT / "reports" / "rosetta_physical_smoke_bootstrap_report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    resolved = path if path.is_absolute() else AI_ROOT / path
    return str(resolved.resolve().relative_to(AI_ROOT))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_score_lines(path: Path) -> dict[str, float]:
    pattern = re.compile(r"COMPLEX:\s+Round1:\s+(WT_|MUT_[A-Z0-9]+):\s+([-+]?\d+(?:\.\d+)?)")
    scores: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            scores[match.group(1)] = float(match.group(2))
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Rosetta Cartesian ddG smoke")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--random-seed", type=int, default=20260802)
    args = parser.parse_args()

    output_dir = args.output_dir if args.output_dir.is_absolute() else AI_ROOT / args.output_dir
    report_path = args.report if args.report.is_absolute() else AI_ROOT / args.report
    stale_outputs = [
        output_dir / "mutation_file.ddg",
        output_dir / "ROSETTA_CRASH.log",
        output_dir / "WT__bj1.pdb",
        output_dir / "MUT_34ALA_bj1.pdb",
    ]
    if any(path.exists() for path in stale_outputs):
        raise RuntimeError(
            "output directory contains prior Rosetta outputs; use a fresh --output-dir "
            "to preserve reproducible evidence"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    mutation_file = output_dir / "mutation_file.txt"
    mutation_file.write_text("total 1\n1\nT 34 A\n", encoding="utf-8")

    command = [
        str(ROSETTA_BIN),
        "-database", str(ROSETTA_DB),
        "-s", str(INPUT_PDB),
        "-ddg::mut_file", mutation_file.name,
        "-ddg::iterations", "1",
        "-score:weights", "ref2015_cart",
        "-ddg::legacy", "false",
        "-constant_seed",
        "-jran", str(args.random_seed),
        "-out:path:all", ".",
    ]
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH"] = str(ROSETTA_BIN.parent)
    process = subprocess.run(
        command,
        cwd=output_dir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=args.timeout_seconds,
        check=False,
    )
    runtime_log = output_dir / "runtime.log"
    runtime_log.write_text(
        json.dumps(
            {
                "command": command,
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    parameters = {
        "backend": "rosetta",
        "protocol": "cartesian_ddg",
        "rosetta_version_probe": "2025.06+HEAD.e5e4b278be",
        "input_structure": rel(INPUT_PDB),
        "input_structure_sha256": sha256(INPUT_PDB),
        "pdb_chain": "A",
        "pdb_position": 10,
        "pose_position": 34,
        "wild_type": "T",
        "mutant": "A",
        "mutation_token": "T10A",
        "mutfile_token": "T 34 A",
        "score_weights": "ref2015_cart",
        "iterations": 1,
        "random_seed": args.random_seed,
        "constant_seed": True,
        "ddg_units": "REU",
        "negative_ddg_is_stabilizing": True,
        "license_authorization_status": "self_attested",
        "verification_required": True,
    }
    write_json(output_dir / "parameters.json", parameters)
    (output_dir / "input_structure.sha256").write_text(sha256(INPUT_PDB) + "\n", encoding="utf-8")
    write_json(
        output_dir / "mutation_list.json",
        [{
            "chain_id": "A",
            "pdb_position": 10,
            "pose_position": 34,
            "wild_type": "T",
            "mutant": "A",
            "mutation": "T10A",
        }],
    )

    score_file = output_dir / "mutation_file.ddg"
    scores = parse_score_lines(score_file) if score_file.exists() else {}
    wt_score = scores.get("WT_")
    mutant_score = next((value for key, value in scores.items() if key.startswith("MUT_")), None)
    ddg = mutant_score - wt_score if wt_score is not None and mutant_score is not None else None
    if process.returncode != 0 or ddg is None:
        report = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backend": "rosetta",
            "status": "failed",
            "returncode": process.returncode,
            "random_seed": args.random_seed,
            "scores": scores,
            "physical_smoke_passed": False,
            "output_dir": rel(output_dir),
            "runtime_log": rel(runtime_log),
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 1

    write_json(
        output_dir / "ddg_table.json",
        {
            "backend": "rosetta",
            "protocol": "cartesian_ddg",
            "rows": [{
                "structure_id": "10MH",
                "chain_id": "A",
                "pdb_position": 10,
                "pose_position": 34,
                "mutation": "T10A",
                "wild_type": "T",
                "mutant": "A",
                "wild_score_reu": wt_score,
                "mutant_score_reu": mutant_score,
                "ddg_reu": ddg,
                "ddg_units": "REU",
                "negative_ddg_is_stabilizing": True,
                "manual_review_required": True,
                "training_label": False,
                "safe_for_model_claim": False,
                "release_ready": False,
                "limitations": [
                    "single mutation smoke only",
                    "Rosetta Energy Units are not wet-lab kcal/mol labels",
                    "self_attested component authorization is not verified license clearance",
                    "not training-import eligible without separate reviewed label authorization",
                ],
            }],
        },
    )

    artifact_paths = [
        output_dir / "parameters.json",
        output_dir / "input_structure.sha256",
        output_dir / "mutation_list.json",
        output_dir / "ddg_table.json",
        output_dir / "runtime.log",
    ]
    artifact_sha256 = {rel(path): sha256(path) for path in artifact_paths}
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": "rosetta",
        "status": "completed",
        "returncode": process.returncode,
        "pyrosetta_init_executed": False,
        "ddg_protocol_executed": True,
        "random_seed": args.random_seed,
        "constant_seed": True,
        "physical_smoke_passed": True,
        "structure_id": "10MH",
        "mutation": "T10A",
        "pdb_position": 10,
        "pose_position": 34,
        "ddg_reu": ddg,
        "ddg_units": "REU",
        "artifact_count": len(artifact_paths),
        "artifact_paths": [rel(path) for path in artifact_paths],
        "artifact_sha256": artifact_sha256,
        "output_dir": rel(output_dir),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Rosetta technical runtime smoke only; computed ddG is computational evidence, not a wet-lab label or release/customer authorization.",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "physical_smoke_passed": report["physical_smoke_passed"],
        "ddg_reu": report["ddg_reu"],
        "artifact_count": report["artifact_count"],
        "output": str(report_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
