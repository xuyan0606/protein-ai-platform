#!/usr/bin/env python3
"""Build and optionally execute a fail-closed physical ddG smoke harness.

The default mode is contract generation only. Passing --execute may run a smoke
job, but only when an approved Rosetta/PyRosetta/FoldX runtime receipt and a
ready ddG execution-plan row already exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_backend_config import default_ddg_config_path
from foldx_buildmodel_parser import write_ddg_table as write_foldx_ddg_table
from ddg_python_module_discovery import add_local_module_paths


AI_ROOT = Path(__file__).resolve().parents[1]
CONFIG = default_ddg_config_path()
READINESS = AI_ROOT / "reports" / "ddg_backend_readiness_report.json"
EXECUTION_PLAN = AI_ROOT / "datasets" / "curation" / "ddg_backend_execution_plan.jsonl"
RECEIPT_STATUS = AI_ROOT / "datasets" / "governance" / "ddg_backend_runtime_receipt_status.jsonl"
RECEIPT_REPORT = AI_ROOT / "reports" / "ddg_backend_runtime_receipt_validation_report.json"
OUTPUT_JSONL = AI_ROOT / "datasets" / "governance" / "ddg_physical_smoke_harness_plan.jsonl"
OUTPUT_REPORT = AI_ROOT / "reports" / "ddg_physical_smoke_harness_report.json"
OUTPUT_MD = AI_ROOT / "reports" / "ddg_physical_smoke_harness.md"
SMOKE_ROOT = AI_ROOT / "cache" / "advanced_features" / "ddg_physical_smoke"

BACKENDS = ["rosetta", "pyrosetta", "foldx"]
REQUIRED_ARTIFACTS = [
    "parameters.json",
    "input_structure.sha256",
    "mutation_list.json",
    "ddg_table.json",
    "runtime.log",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def resolve_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else AI_ROOT / path


def backend_rows(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("backend")): row
        for row in report.get("backends") or []
        if isinstance(row, dict) and row.get("backend")
    }


def approved_status_by_backend(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        backend = str(row.get("backend") or "")
        if backend in BACKENDS and row.get("approved_for_physical_ddg_runtime") is True and row.get("ready_for_ddg_smoke") is True:
            result[backend] = row
    return result


def ready_plans_by_backend(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {backend: [] for backend in BACKENDS}
    for row in rows:
        backend = str(row.get("backend") or "")
        if backend in result and row.get("status") == "ready_to_execute":
            result[backend].append(row)
    return result


def receipt_rows(path: Path) -> list[dict[str, Any]]:
    return load_jsonl(path)


def receipts_by_backend(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {backend: [] for backend in BACKENDS}
    for row in rows:
        backend = str(row.get("backend") or "")
        if backend in result:
            result[backend].append(row)
    return result


def selected_approved_receipt(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    for row in receipts:
        if (
            row.get("receipt_decision") == "approved_runtime_ready"
            and row.get("approved_for_physical_ddg_runtime") is True
        ):
            return row
    return {}


def command_template(config: dict[str, Any], backend: str) -> list[str]:
    return list(((config.get("backends") or {}).get(backend) or {}).get("command_template") or [])


def artifact_map(output_dir: Path) -> dict[str, str]:
    result = {}
    for name in REQUIRED_ARTIFACTS:
        path = output_dir / name
        if path.exists() and path.is_file():
            result[rel(path)] = sha256_file(path)
    return result


def receipt_artifact_map(receipt: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    expected = receipt.get("smoke_artifact_sha256") if isinstance(receipt.get("smoke_artifact_sha256"), dict) else {}
    artifacts: dict[str, str] = {}
    errors: list[str] = []
    for artifact in receipt.get("smoke_artifact_paths") or []:
        path = resolve_path(artifact)
        if path is None or not path.exists() or not path.is_file():
            errors.append(f"missing_artifact:{artifact}")
            continue
        observed = sha256_file(path)
        expected_sha = str(expected.get(str(artifact)) or "").lower()
        if observed != expected_sha:
            errors.append(f"sha256_mismatch:{artifact}")
            continue
        artifacts[str(artifact)] = observed
    missing_names = sorted(set(REQUIRED_ARTIFACTS) - {Path(path).name for path in artifacts})
    for name in missing_names:
        errors.append(f"missing_required_artifact:{name}")
    return artifacts, errors


def first_mutation(plan: dict[str, Any]) -> dict[str, Any]:
    mutations = plan.get("mutations") or []
    return mutations[0] if mutations and isinstance(mutations[0], dict) else {}


def write_rosetta_mutfile(path: Path, plan: dict[str, Any]) -> None:
    mutation = first_mutation(plan)
    chain = str(plan.get("chain_id") or "A")
    position = int(
        mutation.get("pose_position")
        or mutation.get("rosetta_pose_position")
        or plan.get("pose_position")
        or 0
    )
    mutant = str(mutation.get("mutant") or "")[:1]
    if position <= 0 or not mutant:
        raise ValueError(
            "missing Rosetta pose_position or mutant residue; "
            "PDB/chain numbering is not accepted for Cartesian ddG mutfiles"
        )
    path.write_text(f"total 1\n1\n{chain} {position} {mutant}\n", encoding="utf-8")


def write_foldx_mutfile(path: Path, plan: dict[str, Any]) -> None:
    mutation = first_mutation(plan)
    chain = str(plan.get("chain_id") or "A")
    wt = str(mutation.get("wild_type") or "")[:1]
    position = int(mutation.get("mutation_position") or 0)
    mutant = str(mutation.get("mutant") or "")[:1]
    if not wt or position <= 0 or not mutant:
        raise ValueError("missing mutation components for FoldX mutant file")
    path.write_text(f"{wt}{chain}{position}{mutant};\n", encoding="utf-8")


def existing_executable(receipt: dict[str, Any], names: list[str]) -> Path | None:
    for value in receipt.get("executable_paths") or []:
        path = resolve_path(value)
        if path and path.exists() and os.access(path, os.X_OK):
            return path
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def prepare_common_artifacts(output_dir: Path, backend: str, plan: dict[str, Any], receipt: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    structure_path = resolve_path(plan.get("structure_path"))
    if structure_path is None or not structure_path.exists():
        raise FileNotFoundError(f"input structure not found: {plan.get('structure_path')}")
    (output_dir / "parameters.json").write_text(
        json.dumps(
            {
                "backend": backend,
                "plan_id": plan.get("plan_id"),
                "runtime_receipt_id": receipt.get("runtime_receipt_id"),
                "negative_ddg_is_stabilizing": plan.get("negative_ddg_is_stabilizing"),
                "smoke_scope": "single reviewed-structure mutation smoke",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "input_structure.sha256").write_text(sha256_file(structure_path) + "\n", encoding="utf-8")
    (output_dir / "mutation_list.json").write_text(
        json.dumps(plan.get("mutations") or [], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_command(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    env = os.environ.copy()
    rosetta_bin = AI_ROOT / "cache" / "external" / "RosettaConda" / "bin"
    try:
        Path(command[0]).resolve().relative_to(rosetta_bin.resolve())
        existing = env.get("DYLD_LIBRARY_PATH")
        env["DYLD_LIBRARY_PATH"] = str(rosetta_bin) if not existing else f"{rosetta_bin}:{existing}"
    except (IndexError, OSError, ValueError):
        env = None
    process = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        env=env,
    )
    return {
        "command": command,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def execute_rosetta(config: dict[str, Any], plan: dict[str, Any], receipt: dict[str, Any], output_dir: Path, timeout: int) -> dict[str, Any]:
    executable = existing_executable(
        receipt,
        [
            "cartesian_ddg",
            "cartesian_ddg.cxx11threadserialization.macosclangrelease",
            "cartesian_ddg.default.macosclangrelease",
            "cartesian_ddg.default.linuxgccrelease",
            "rosetta_scripts",
            "rosetta_scripts.cxx11threadserialization.macosclangrelease",
            "rosetta_scripts.default.macosclangrelease",
            "rosetta_scripts.default.linuxgccrelease",
        ],
    )
    if executable is None:
        raise FileNotFoundError("approved Rosetta receipt did not resolve to an executable")
    mutation_file = output_dir / "mutation_file.txt"
    write_rosetta_mutfile(mutation_file, plan)
    structure_path = resolve_path(plan.get("structure_path"))
    template = command_template(config, "rosetta")
    substitutions = {
        "cartesian_ddg": str(executable),
        "input_pdb": str(structure_path),
        "mutation_file": str(mutation_file),
        "iterations": "1",
        "database": str(AI_ROOT / "cache" / "external" / "RosettaConda" / "database"),
        "output_dir": str(output_dir),
    }
    command = [part.format(**substitutions) for part in template]
    return run_command(command, output_dir, timeout)


def execute_foldx(config: dict[str, Any], plan: dict[str, Any], receipt: dict[str, Any], output_dir: Path, timeout: int) -> dict[str, Any]:
    executable = existing_executable(receipt, ["foldx", "FoldX"])
    if executable is None:
        raise FileNotFoundError("approved FoldX receipt did not resolve to an executable")
    mutation_file = output_dir / "individual_list.txt"
    write_foldx_mutfile(mutation_file, plan)
    structure_path = resolve_path(plan.get("structure_path"))
    if structure_path is None:
        raise FileNotFoundError("input structure not found")
    local_pdb = output_dir / structure_path.name
    if not local_pdb.exists():
        shutil.copy2(structure_path, local_pdb)
    template = command_template(config, "foldx")
    substitutions = {
        "foldx": str(executable),
        "input_pdb": str(local_pdb),
        "input_pdb_name": local_pdb.name,
        "mutation_file": str(mutation_file),
        "output_dir": str(output_dir),
    }
    command = [part.format(**substitutions) for part in template]
    return run_command(command, output_dir, timeout)


def execute_pyrosetta(plan: dict[str, Any], receipt: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    add_local_module_paths([receipt.get("install_path")])
    try:
        import pyrosetta  # type: ignore
        from pyrosetta.toolbox.mutants import mutate_residue  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on licensed local install.
        raise RuntimeError(f"PyRosetta import failed: {exc}") from exc

    structure_path = resolve_path(plan.get("structure_path"))
    if structure_path is None or not structure_path.exists():
        raise FileNotFoundError(f"input structure not found: {plan.get('structure_path')}")
    mutation = first_mutation(plan)
    chain = str(plan.get("chain_id") or "A")
    pdb_position = int(mutation.get("mutation_position") or 0)
    mutant = str(mutation.get("mutant") or "")[:1]
    if pdb_position <= 0 or not mutant:
        raise ValueError("missing mutation position or mutant residue for PyRosetta smoke")

    pyrosetta.init("-mute all")
    pose = pyrosetta.pose_from_pdb(str(structure_path))
    pose_index = pose.pdb_info().pdb2pose(chain, pdb_position)
    if pose_index <= 0:
        raise ValueError(f"could not map chain {chain} residue {pdb_position} into PyRosetta pose")
    scorefxn = pyrosetta.get_fa_scorefxn()
    wild_score = float(scorefxn(pose))
    mutant_pose = pose.clone()
    mutate_residue(mutant_pose, pose_index, mutant)
    mutant_score = float(scorefxn(mutant_pose))
    ddg = mutant_score - wild_score
    table = {
        "backend": "pyrosetta",
        "protocol": "minimal_scorefxn_single_mutation_smoke",
        "rows": [
            {
                "chain_id": chain,
                "pdb_position": pdb_position,
                "mutant": mutant,
                "wild_score_reu": wild_score,
                "mutant_score_reu": mutant_score,
                "ddg_reu": ddg,
                "negative_ddg_is_stabilizing": True,
            }
        ],
    }
    (output_dir / "ddg_table.json").write_text(json.dumps(table, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"command": [sys.executable, "-c", "pyrosetta minimal smoke"], "returncode": 0, "stdout": json.dumps(table), "stderr": ""}


def execute_backend(config: dict[str, Any], backend: str, plan: dict[str, Any], receipt: dict[str, Any], output_dir: Path, timeout: int) -> dict[str, Any]:
    prepare_common_artifacts(output_dir, backend, plan, receipt)
    if backend == "rosetta":
        result = execute_rosetta(config, plan, receipt, output_dir, timeout)
    elif backend == "foldx":
        result = execute_foldx(config, plan, receipt, output_dir, timeout)
    elif backend == "pyrosetta":
        result = execute_pyrosetta(plan, receipt, output_dir)
    else:
        raise ValueError(f"unsupported backend: {backend}")
    (output_dir / "runtime.log").write_text(
        json.dumps(
            {
                "command": result.get("command"),
                "returncode": result.get("returncode"),
                "stdout_head": str(result.get("stdout") or "")[:4000],
                "stderr_head": str(result.get("stderr") or "")[:4000],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if backend == "foldx" and result.get("returncode") == 0:
        mutation = first_mutation(plan)
        write_foldx_ddg_table(
            output_dir,
            {
                "chain_id": plan.get("chain_id") or "A",
                "pdb_position": mutation.get("mutation_position"),
                "wild_type": mutation.get("wild_type"),
                "mutant": mutation.get("mutant"),
            },
        )
    elif backend in {"rosetta", "foldx"}:
        table = {
            "backend": backend,
            "parse_status": "not_parsed_by_harness",
            "rows": [],
            "policy": "Command execution smoke only. This table is not valid unless a backend-specific parser extracts ddG values from runtime outputs.",
        }
        (output_dir / "ddg_table.json").write_text(json.dumps(table, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def build_backend_row(
    backend: str,
    created_at: str,
    config: dict[str, Any],
    ready_rows: dict[str, dict[str, Any]],
    approved_rows: dict[str, dict[str, Any]],
    receipt_map: dict[str, list[dict[str, Any]]],
    ready_plan_rows: dict[str, list[dict[str, Any]]],
    execute: bool,
    timeout: int,
) -> dict[str, Any]:
    readiness = ready_rows.get(backend, {})
    approved_status = approved_rows.get(backend, {})
    approved_receipt = selected_approved_receipt(receipt_map.get(backend, []))
    plans = ready_plan_rows.get(backend, [])
    can_execute = bool(readiness.get("ready_for_execution")) and bool(approved_status) and bool(approved_receipt) and bool(plans)
    blockers = []
    if not readiness.get("ready_for_execution"):
        blockers.extend(readiness.get("blockers") or ["backend_not_ready_for_execution"])
    if not approved_status:
        blockers.append("approved_runtime_receipt_status_missing")
    if not approved_receipt:
        blockers.append("approved_runtime_receipt_row_missing")
    if not plans:
        blockers.append("ddg_execution_plan_has_no_ready_rows")

    row: dict[str, Any] = {
        "harness_id": f"P205-ddg-physical-smoke-harness-{backend}",
        "created_at": created_at,
        "backend": backend,
        "executor_contract_status": "implemented",
        "supported_execution_modes": ["plan_only", "execute_after_approved_runtime_receipt"],
        "backend_ready_for_execution_from_readiness": bool(readiness.get("ready_for_execution")),
        "approved_runtime_receipt_present": bool(approved_status),
        "ready_plan_rows": len(plans),
        "can_execute_physical_smoke_now": can_execute,
        "execute_requested": execute,
        "execute_attempted": False,
        "physical_smoke_passed": False,
        "ddg_job_executed": False,
        "artifact_contract": {
            "required_artifacts": REQUIRED_ARTIFACTS,
            "output_root": rel(SMOKE_ROOT / backend),
            "artifact_sha256_required": True,
        },
        "execution_blockers": sorted(set(str(item) for item in blockers)),
        "thermompnn_proxy_allowed": False,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Harness contract plus receipt artifact recognition. Runtime smoke artifacts can be recognized from an approved receipt even when no training execution plan is ready.",
    }
    if approved_receipt:
        receipt_artifacts, receipt_artifact_errors = receipt_artifact_map(approved_receipt)
        receipt_smoke_passed = len(receipt_artifacts) == len(REQUIRED_ARTIFACTS) and not receipt_artifact_errors
        row.update({
            "receipt_smoke_artifact_present": bool(receipt_artifacts),
            "receipt_smoke_artifact_errors": receipt_artifact_errors,
            "smoke_artifact_sha256": receipt_artifacts,
        })
        if receipt_smoke_passed:
            row.update({
                "ddg_job_executed": True,
                "physical_smoke_passed": True,
                "smoke_output_dir": str(Path(next(iter(receipt_artifacts))).parent),
                "runtime_receipt_id": approved_receipt.get("runtime_receipt_id"),
            })
    if execute and can_execute:
        plan = plans[0]
        plan_hash = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        output_dir = SMOKE_ROOT / backend / plan_hash
        try:
            result = execute_backend(config, backend, plan, approved_receipt, output_dir, timeout)
            artifacts = artifact_map(output_dir)
            row.update(
                {
                    "execute_attempted": True,
                    "ddg_job_executed": result.get("returncode") == 0,
                    "physical_smoke_passed": result.get("returncode") == 0 and len(artifacts) == len(REQUIRED_ARTIFACTS),
                    "smoke_output_dir": rel(output_dir),
                    "smoke_artifact_sha256": artifacts,
                    "runtime_returncode": result.get("returncode"),
                }
            )
        except Exception as exc:
            row.update(
                {
                    "execute_attempted": True,
                    "ddg_job_executed": False,
                    "physical_smoke_passed": False,
                    "smoke_error": str(exc),
                }
            )
    return row


def build_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# P205 Physical ddG Smoke Harness",
        "",
        f"Created: `{report['created_at']}`",
        "",
        "This harness prepares the non-human execution contract for Rosetta/PyRosetta/FoldX physical ddG smoke jobs. It does not approve licenses, fabricate ddG values, import training labels, or open model/release claims.",
        "",
        "| Backend | Harness | Runtime receipt | Ready plan rows | Can execute now | Smoke passed | Blockers |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {backend} | {harness} | {receipt} | {plans} | {can_execute} | {passed} | {blockers} |".format(
                backend=row["backend"],
                harness=row["executor_contract_status"],
                receipt="present" if row["approved_runtime_receipt_present"] else "missing",
                plans=row["ready_plan_rows"],
                can_execute=row["can_execute_physical_smoke_now"],
                passed=row["physical_smoke_passed"],
                blockers=", ".join(row["execution_blockers"]) or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Current Boundary",
            "",
            f"- Harness contract rows: {report['harness_contract_rows']}",
            f"- Contract implemented rows: {report['executor_contract_implemented_rows']}",
            f"- Can execute physical smoke now rows: {report['can_execute_physical_smoke_now_rows']}",
            f"- Physical smoke passed rows: {report['physical_smoke_passed_rows']}",
            "- `safe_for_model_claim=false`; `release_ready=false`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build physical ddG smoke harness")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--readiness", type=Path, default=READINESS)
    parser.add_argument("--execution-plan", type=Path, default=EXECUTION_PLAN)
    parser.add_argument("--receipt-status", type=Path, default=RECEIPT_STATUS)
    parser.add_argument("--receipt-report", type=Path, default=RECEIPT_REPORT)
    parser.add_argument("--runtime-receipts", type=Path, default=AI_ROOT / "datasets" / "governance" / "ddg_backend_runtime_receipts.local.jsonl")
    parser.add_argument("--output-jsonl", type=Path, default=OUTPUT_JSONL)
    parser.add_argument("--output-report", type=Path, default=OUTPUT_REPORT)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    config = load_json(args.config)
    readiness = load_json(args.readiness)
    plan_rows = load_jsonl(args.execution_plan)
    status_rows = load_jsonl(args.receipt_status)
    receipt_validation = load_json(args.receipt_report)
    local_receipts = receipt_rows(args.runtime_receipts)

    ready_rows = backend_rows(readiness)
    approved = approved_status_by_backend(status_rows)
    receipt_map = receipts_by_backend(local_receipts)
    plan_ready = ready_plans_by_backend(plan_rows)
    rows = [
        build_backend_row(
            backend,
            created_at,
            config,
            ready_rows,
            approved,
            receipt_map,
            plan_ready,
            args.execute,
            args.timeout_seconds,
        )
        for backend in BACKENDS
    ]
    report = {
        "created_at": created_at,
        "local_only": True,
        "task_id": "P205",
        "harness_contract_rows": len(rows),
        "executor_contract_implemented_rows": sum(1 for row in rows if row["executor_contract_status"] == "implemented"),
        "approved_runtime_receipt_rows": int(receipt_validation.get("approved_runtime_rows") or 0),
        "runtime_receipt_status_rows": len(status_rows),
        "ready_execution_plan_rows": sum(len(value) for value in plan_ready.values()),
        "can_execute_physical_smoke_now_rows": sum(1 for row in rows if row["can_execute_physical_smoke_now"]),
        "execute_requested": args.execute,
        "execute_attempted_rows": sum(1 for row in rows if row["execute_attempted"]),
        "ddg_job_executed_rows": sum(1 for row in rows if row["ddg_job_executed"]),
        "physical_smoke_passed_rows": sum(1 for row in rows if row["physical_smoke_passed"]),
        "license_install_runtime_blocker_rows": sum(1 for row in rows if row["execution_blockers"]),
        "thermompnn_proxy_allowed_rows": sum(1 for row in rows if row["thermompnn_proxy_allowed"]),
        "physics_ddg_ready": any(row["physical_smoke_passed"] for row in rows),
        "executable_ddg_backend_ready": bool(readiness.get("executable_ddg_backend_ready")),
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "inputs": {
            "config": str(args.config),
            "readiness": str(args.readiness),
            "execution_plan": str(args.execution_plan),
            "receipt_status": str(args.receipt_status),
            "receipt_report": str(args.receipt_report),
            "runtime_receipts": str(args.runtime_receipts),
        },
        "outputs": {
            "jsonl": str(args.output_jsonl),
            "report": str(args.output_report),
            "markdown": str(args.output_md),
        },
        "backends": rows,
        "policy": "Physical ddG smoke harness is implemented. It recognizes checksumed approved runtime-receipt artifacts, while training/model/release gates remain false.",
    }
    write_jsonl(args.output_jsonl, rows)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(build_markdown(report, rows), encoding="utf-8")
    print(
        json.dumps(
            {
                "harness_contract_rows": report["harness_contract_rows"],
                "executor_contract_implemented_rows": report["executor_contract_implemented_rows"],
                "can_execute_physical_smoke_now_rows": report["can_execute_physical_smoke_now_rows"],
                "physical_smoke_passed_rows": report["physical_smoke_passed_rows"],
                "safe_for_model_claim": False,
                "output": str(args.output_report),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
