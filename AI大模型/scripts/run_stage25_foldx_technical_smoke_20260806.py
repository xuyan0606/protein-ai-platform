#!/usr/bin/env python3
"""Run an isolated FoldX technical smoke without opening any production gate.

This exercises RepairPDB and BuildModel on the existing 10mh/T10A engineering
fixture. Its output is computational runtime evidence only: it is not a
formal runtime receipt, a wet-lab label, a training import, or a release claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foldx_buildmodel_parser import write_ddg_table


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTABLE = AI_ROOT / "cache" / "external" / "FoldX" / "foldx"
DEFAULT_PACKAGE = AI_ROOT / "cache" / "external" / "foldx5_MacSilicon_0"
DEFAULT_INPUT = AI_ROOT / "cache" / "structures" / "pdb" / "10mh.pdb"
DEFAULT_OUTPUT = AI_ROOT / "cache" / "advanced_features" / "ddg_physical_smoke" / "foldx" / "stage25_technical_smoke_20260806"
DEFAULT_REPORT = AI_ROOT / "reports" / "stage25_foldx_technical_smoke_20260806.json"
PARAMETERIZATION_WARNING = "External parametrized molecules were detected"
ENERGETIC_DEPENDENCY_WARNING = "Final energetic values will depend of the correct parametrization of this molecules."


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(AI_ROOT))
    except ValueError:
        return str(path.resolve())


def run(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "returncode": None, "stdout": "", "stderr": str(exc), "error": str(exc)}


def artifact_hashes(output_dir: Path) -> dict[str, str]:
    names = ["parameters.json", "input_structure.sha256", "mutation_list.json", "ddg_table.json", "runtime.log"]
    return {rel(output_dir / name): sha256(output_dir / name) for name in names if (output_dir / name).is_file()}


def parameterization_warning_commands(repair: dict[str, Any], build: dict[str, Any]) -> list[str]:
    commands = []
    for name, payload in (("RepairPDB", repair), ("BuildModel", build)):
        stdout = str(payload.get("stdout") or "")
        if PARAMETERIZATION_WARNING in stdout and ENERGETIC_DEPENDENCY_WARNING in stdout:
            commands.append(name)
    return commands


def unrecognized_molecule_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False, "line_count": 0, "molecule_names": [], "sha256": None}
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    names = sorted({line.split()[2] for line in lines if line.startswith("Unrecognised atom:") and len(line.split()) >= 3})
    return {"present": True, "line_count": len(lines), "molecule_names": names, "sha256": sha256(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated FoldX technical smoke")
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXECUTABLE)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    executable = args.executable if args.executable.is_absolute() else AI_ROOT / args.executable
    package_dir = args.package_dir if args.package_dir.is_absolute() else AI_ROOT / args.package_dir
    input_path = args.input if args.input.is_absolute() else AI_ROOT / args.input
    output_dir = args.output_dir if args.output_dir.is_absolute() else AI_ROOT / args.output_dir
    report_path = args.report if args.report.is_absolute() else AI_ROOT / args.report

    output_dir.mkdir(parents=True, exist_ok=True)
    stale_outputs = [output_dir / name for name in ("Dif_10mh_Repair.fxout", "Average_10mh_Repair.fxout", "Raw_10mh_Repair.fxout", "10mh_Repair.pdb")]
    if any(path.exists() for path in stale_outputs):
        raise SystemExit(f"output directory contains prior FoldX outputs; use a fresh --output-dir: {output_dir}")
    if not executable.is_file() or not input_path.is_file() or not (package_dir / "rotabase.txt").is_file():
        raise SystemExit("FoldX executable, input PDB, or rotabase.txt is missing")

    local_pdb = output_dir / input_path.name
    shutil.copy2(input_path, local_pdb)
    shutil.copy2(package_dir / "rotabase.txt", output_dir / "rotabase.txt")
    molecules = package_dir / "molecules"
    if molecules.is_dir():
        shutil.copytree(molecules, output_dir / "molecules", dirs_exist_ok=True)

    repair = run([str(executable), "--command=RepairPDB", f"--pdb={local_pdb.name}"], output_dir, args.timeout_seconds)
    repaired = output_dir / "10mh_Repair.pdb"
    build: dict[str, Any] = {"command": [], "returncode": None, "stdout": "", "stderr": "", "skipped": True}
    if repair.get("returncode") == 0 and repaired.is_file():
        (output_dir / "individual_list.txt").write_text("TA10A;\n", encoding="utf-8")
        build = run(
            [
                str(executable),
                "--command=BuildModel",
                f"--pdb={repaired.name}",
                "--mutant-file=individual_list.txt",
                "--numberOfRuns=1",
            ],
            output_dir,
            args.timeout_seconds,
        )

    mutation_context = {"chain_id": "A", "pdb_position": 10, "wild_type": "T", "mutant": "A"}
    table = write_ddg_table(output_dir, mutation_context)
    (output_dir / "parameters.json").write_text(
        json.dumps(
            {
                "backend": "foldx",
                "protocol": "BuildModel",
                "input_structure": rel(input_path),
                "input_structure_sha256": sha256(input_path),
                "mutation": "T10A",
                "foldx_mutation_token": "TA10A;",
                "number_of_runs": 1,
                "technical_smoke_only": True,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "input_structure.sha256").write_text(sha256(input_path) + "\n", encoding="utf-8")
    (output_dir / "mutation_list.json").write_text(
        json.dumps([mutation_context], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "runtime.log").write_text(
        json.dumps({"repair": repair, "buildmodel": build}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    warning_commands = parameterization_warning_commands(repair, build)
    unrecognized = unrecognized_molecule_summary(output_dir / "Unrecognized_molecules.txt")
    passed = repair.get("returncode") == 0 and build.get("returncode") == 0 and table.get("parse_status") == "parsed" and len(table.get("rows") or []) == 1
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": 25,
        "backend": "foldx",
        "status": "technical_smoke_passed" if passed else "technical_smoke_failed",
        "technical_smoke_passed": passed,
        "executable_path": str(executable),
        "input_structure": rel(input_path),
        "output_dir": rel(output_dir),
        "repair_returncode": repair.get("returncode"),
        "buildmodel_returncode": build.get("returncode"),
        "parsed_rows": len(table.get("rows") or []),
        "parse_errors": table.get("parse_errors") or [],
        "ddg_table_rows": len(table.get("rows") or []),
        "artifact_sha256": artifact_hashes(output_dir),
        "parameterization_dependency_warning_detected": bool(warning_commands),
        "parameterization_warning_commands": warning_commands,
        "parameterization_warning_command_count": len(warning_commands),
        "unrecognized_molecule_diagnostic_present": unrecognized["present"],
        "unrecognized_atom_rows": unrecognized["line_count"],
        "unrecognized_molecule_names": unrecognized["molecule_names"],
        "unrecognized_molecule_diagnostic_sha256": unrecognized["sha256"],
        "parameterization_review_completed": False,
        "ddg_value_technical_only": True,
        "energetic_interpretation_approved": False,
        "physical_ddg_comparable": False,
        "safe_for_benchmark_intake": False,
        "formal_runtime_receipt_written": False,
        "approved_for_physical_ddg_runtime": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "export_safe_released": False,
        "release_ready": False,
        "policy": "Technical smoke only. FoldX reported an external-molecule parameterization dependency, so energetic interpretation and physical-ddG comparability remain unapproved until parameterization review. This does not approve a license, formal runtime receipt, wet-lab label, training import, benchmark intake, model claim, customer delivery, or release.",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "technical_smoke_passed": passed, "parsed_rows": report["parsed_rows"], "output": str(report_path)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
